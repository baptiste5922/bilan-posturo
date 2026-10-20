#!/usr/bin/env python3
"""
Serveur du bilan posturologique.

Trois rôles :
  1. servir le formulaire, qui vit dans formulaire/ ;
  2. recevoir les PDF générés sur la tablette et les écrire dans le dossier
     patient du PC (route POST /depot) ;
  3. protéger l'ensemble par un mot de passe et par TLS, tous deux
     obligatoires : sans certificat, le serveur refuse de démarrer.

N'utilise que la bibliothèque standard : rien à installer au cabinet.
Le certificat, lui, se fabrique avec generer_autorite.py.

    python3 serveur/generer_autorite.py 192.168.1.13   # certificat, une fois
    python3 serveur/serveur.py --config                # identifiant, mot de passe
    python3 serveur/serveur.py                         # démarrage
"""

import argparse
import base64
import binascii
import datetime
import getpass
import hashlib
import hmac
import json
import os
import re
import secrets
import socket
import socketserver
import ssl
import sys
import tempfile
import threading
import unicodedata
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

# Le script vit dans serveur/ : la racine du projet est le dossier parent.
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(RACINE, "config.json")
JOURNAL = os.path.join(RACINE, "journal.log")
# Journal technique : non identifiant par construction (C4-T1). Il coexiste
# avec JOURNAL, qui reste nominatif et ne quitte jamais le cabinet.
TECHNIQUE = os.path.join(RACINE, "technique.log")

# Racine web : elle ne contient que le formulaire. Ni config.json, ni les
# clés privées, ni le code Python n'y figurent, si bien qu'aucune requête ne
# peut les atteindre même si le filtre d'extensions venait à être contourné.
FORMULAIRE = os.path.join(RACINE, "formulaire")

TAILLE_MAX = 30 * 1024 * 1024      # 30 Mo : un bilan pèse ~1 à 3 Mo
ITERATIONS = 240_000               # coût du hachage PBKDF2

# Le serveur tourne désormais en service, donc en continu : sans rotation, le
# journal croîtrait indéfiniment. 5 Mo représentent environ 40 000 requêtes.
JOURNAL_TAILLE_MAX = 5 * 1024 * 1024
JOURNAL_ARCHIVES = 3

# Vocabulaire fermé du journal technique : la source dont les tests se
# dérivent, jamais recopiée. Un nom d'événement hors de cet ensemble devient
# "EVENEMENT_INCONNU" plutôt que de lever (journaliser_technique).
EVENEMENTS_TECHNIQUES = frozenset({
    "DEMARRAGE", "ARRET", "TLS_REFUSE", "AUTH_REFUSEE",
    "REPONSE", "DEPOT", "ECHEC_ECRITURE", "ROTATION",
})

# ROTATION échappe de nécessité à journaliser_technique() (interblocage
# certain : le verrou n'est pas réentrant), donc à la garde qui ne relève
# que les appels littéraux à cette fonction. Le libellé se dérive ici une
# seule fois, jamais retranscrit au site d'écriture
# (_ajouter_ligne_technique, plus bas) : constat d'audit C4-T1.
EVENEMENT_ROTATION = "ROTATION"
if EVENEMENT_ROTATION not in EVENEMENTS_TECHNIQUES:
    # Levée explicite, jamais `assert` : sous python -O, un `assert` nu au
    # niveau du module disparaîtrait aussi silencieusement qu'ailleurs, et
    # ce lien ne serait plus vérifié du tout (constat d'audit C4-T1).
    raise AssertionError(
        "EVENEMENT_ROTATION ({!r}) doit appartenir à EVENEMENTS_TECHNIQUES"
        .format(EVENEMENT_ROTATION))

# Classes de route fermées : jamais un chemin brut, contrôlé par le client,
# n'atteint le journal technique (décision D3).
ROUTES_TECHNIQUES = frozenset({"depot", "sante", "formulaire", "autre"})

# Motifs de refus de dépôt, fermés eux aussi : un motif hors de cet ensemble
# devient "motif-inconnu" (detail_refus_depot).
MOTIFS_REFUS_DEPOT = frozenset({
    "content-length-invalide", "corps-vide", "trop-volumineux",
    "transfert-interrompu", "non-pdf",
})

# Interrupteur de retour arrière (étape 8) : à False, le journal technique
# n'est jamais écrit. Positionné depuis la configuration dans demarrer().
JOURNAL_TECHNIQUE_ACTIF = True

# Seuls ces fichiers sont servis. Le filtre double la séparation des dossiers :
# même si la racine web venait à contenir autre chose, rien d'autre ne sortirait.
# .json y figure pour schema.json (moteur de rendu, C1-T3) : la racine web ne
# contient que le formulaire, et config.json vit un niveau au-dessus (RACINE,
# pas FORMULAIRE) — inatteignable même maintenant que l'extension est servie.
EXTENSIONS_SERVIES = {".html", ".css", ".js", ".json", ".png", ".jpg", ".jpeg", ".svg", ".ico"}

CONFIG_DEFAUT = {
    "port": 8000,
    "dossier_pdf": "bilans",
    "utilisateur": "cabinet",
    "mot_de_passe": "",
    "certificat": "certificat.pem",
    "cle_privee": "cle.pem",
    "journal_technique": True,
}


# --------------------------------------------------------------------------
# Configuration et mots de passe
# --------------------------------------------------------------------------

def charger_config():
    if not os.path.exists(CONFIG):
        return None
    with open(CONFIG, encoding="utf-8") as f:
        config = json.load(f)
    complet = dict(CONFIG_DEFAUT)
    complet.update(config)
    return complet


def hacher(mot_de_passe, sel=None, iterations=ITERATIONS):
    """Hachage PBKDF2-SHA256. Le mot de passe n'est jamais stocké en clair."""
    if sel is None:
        sel = secrets.token_bytes(16)
    empreinte = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode("utf-8"),
                                    sel, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations, sel.hex(), empreinte.hex())


def verifier_mot_de_passe(mot_de_passe, stocke):
    """Comparaison à temps constant : ne renseigne pas sur le nombre de
    caractères corrects, contrairement à un == classique."""
    try:
        algo, iterations, sel_hex, attendu_hex = stocke.split("$")
        if algo != "pbkdf2_sha256":
            return False
        candidat = hashlib.pbkdf2_hmac(
            "sha256", mot_de_passe.encode("utf-8"),
            bytes.fromhex(sel_hex), int(iterations))
        return hmac.compare_digest(candidat.hex(), attendu_hex)
    except (ValueError, binascii.Error):
        return False


def definir_mot_de_passe():
    config = charger_config() or dict(CONFIG_DEFAUT)

    utilisateur = input("Identifiant [{}] : ".format(config["utilisateur"])).strip()
    if utilisateur:
        config["utilisateur"] = utilisateur

    premier = getpass.getpass("Mot de passe : ")
    if len(premier) < 8:
        print("Refusé : 8 caractères minimum.")
        return 1
    if premier != getpass.getpass("Confirmation : "):
        print("Refusé : les deux saisies diffèrent.")
        return 1

    config["mot_de_passe"] = hacher(premier)
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    os.chmod(CONFIG, 0o600)      # lisible par le seul propriétaire

    print("\nConfiguration écrite dans config.json (permissions 600).")
    print("Identifiant : {}".format(config["utilisateur"]))
    return 0


# --------------------------------------------------------------------------
# Nom de fichier
# --------------------------------------------------------------------------

def assainir_nom(nom):
    """Réduit un nom fourni par le client à une forme sûre.

    Neutralise la traversée de répertoire (../), les séparateurs de chemin et
    les caractères spéciaux. Le résultat ne peut désigner qu'un fichier du
    dossier de dépôt.
    """
    nom = os.path.basename(nom.replace("\\", "/"))
    nom = unicodedata.normalize("NFKD", nom)
    nom = nom.encode("ascii", "ignore").decode("ascii")
    nom = re.sub(r"[^A-Za-z0-9 ._-]", "_", nom).strip(" .")
    nom = re.sub(r"_{2,}", "_", nom)

    if nom.lower().endswith(".pdf"):
        nom = nom[:-4]
    if not nom:
        nom = "bilan"
    # Tronquer AVANT de remettre l'extension, sinon un nom très long
    # ressortirait sans ".pdf"
    return nom[:116] + ".pdf"


def chemin_libre(dossier, nom):
    """Ajoute un suffixe numérique plutôt que d'écraser un bilan existant."""
    base, ext = os.path.splitext(nom)
    candidat = os.path.join(dossier, nom)
    n = 2
    while os.path.exists(candidat):
        candidat = os.path.join(dossier, "{}-{}{}".format(base, n, ext))
        n += 1
    return candidat


def ecrire_atomiquement(destination, contenu):
    """Écrit le PDF sans jamais laisser de fichier partiel dans le dossier.

    Le contenu part dans un fichier temporaire du même dossier — donc du même
    système de fichiers, sans quoi le renommage ne serait pas atomique — puis
    est renommé. Le logiciel du cabinet qui surveille le dossier ne peut donc
    ouvrir qu'un bilan complet : un transfert interrompu ne laisse rien.
    """
    dossier = os.path.dirname(destination)
    descripteur, temporaire = tempfile.mkstemp(dir=dossier, suffix=".part")
    try:
        with open(descripteur, "wb") as f:
            f.write(contenu)
            f.flush()
            os.fsync(f.fileno())     # sinon un arrêt brutal perd le contenu
        os.chmod(temporaire, 0o600)
        os.replace(temporaire, destination)
    except BaseException:
        # Ne pas laisser traîner de .part si l'écriture échoue.
        try:
            os.unlink(temporaire)
        except OSError:
            pass
        raise


# --------------------------------------------------------------------------
# Journal
# --------------------------------------------------------------------------

# Le serveur est multithreadé : deux requêtes simultanées peuvent vouloir
# écrire, et surtout faire tourner le journal, au même instant.
_verrou_journal = threading.Lock()


def ecrire_stderr(ligne):
    """Écrit sur la sortie d'erreur quand il y en a une.

    Lancé par le service Windows, le serveur tourne sous `pythonw.exe`, qui
    n'ouvre pas de console : `sys.stderr` vaut alors None. Un write direct
    lèverait AttributeError au milieu d'une requête, et le thread mourrait
    sans réponse — un dépôt perdu pour une ligne de journal.
    """
    if sys.stderr is None:
        return
    try:
        sys.stderr.write(ligne)
    except (ValueError, OSError):
        pass


def faire_tourner_journal(chemin=None):
    """Archive le journal au-delà de JOURNAL_TAILLE_MAX.

    Partagée par les deux journaux : le défaut se résout ici, dans le corps,
    et non dans la signature — sinon il serait figé à l'import, et les tests
    qui remplacent le global JOURNAL (RotationDuJournal) cesseraient d'agir
    sur cette fonction.

    Conserve JOURNAL_ARCHIVES générations. Toute erreur est ignorée : un
    journal qu'on ne peut pas faire tourner ne doit pas empêcher le serveur
    de répondre. Rend True si une rotation a eu lieu, pour que l'appelant
    (déjà sous verrou dans journaliser_technique) puisse noter l'événement
    sans ré-acquérir ce verrou.
    """
    if chemin is None:
        chemin = JOURNAL

    try:
        if os.path.getsize(chemin) < JOURNAL_TAILLE_MAX:
            return False
    except OSError:
        return False

    try:
        plus_ancienne = "{}.{}".format(chemin, JOURNAL_ARCHIVES)
        if os.path.exists(plus_ancienne):
            os.remove(plus_ancienne)
        for rang in range(JOURNAL_ARCHIVES - 1, 0, -1):
            source = "{}.{}".format(chemin, rang)
            if os.path.exists(source):
                os.replace(source, "{}.{}".format(chemin, rang + 1))
        os.replace(chemin, chemin + ".1")
        return True
    except OSError:
        return False


def journaliser(ligne):
    """Trace une ligne sur la sortie d'erreur et dans le journal."""
    ecrire_stderr(ligne)
    with _verrou_journal:
        faire_tourner_journal()
        try:
            with open(JOURNAL, "a", encoding="utf-8") as f:
                f.write(ligne)
        except OSError:
            pass


# --------------------------------------------------------------------------
# Journal technique (C4-T1) — non identifiant, conçu pour circuler
# --------------------------------------------------------------------------

def empreinte_certificat(chemin):
    """Seize premiers chiffres hexadécimaux du SHA-256 du certificat.

    Substitut d'adresse (décision D2) : le certificat porte l'adresse en
    subjectAltName, donc toute réémission pour une nouvelle adresse change
    l'empreinte, sans que celle-ci ne soit elle-même une adresse ni ne
    s'inverse. Bibliothèque standard seule ; aucune clé privée n'est lue.
    """
    try:
        with open(chemin, encoding="ascii") as f:
            pem = f.read()
        der = ssl.PEM_cert_to_DER_cert(pem)
        return hashlib.sha256(der).hexdigest()[:16]
    except (OSError, ValueError, ssl.SSLError):
        return "indisponible"


def verdict_certificat(empreinte):
    """Compare l'empreinte courante à celle inscrite au dernier démarrage.

    Relit la dernière ligne DEMARRAGE de technique.log, sans lire d'archive
    ni tenir d'état séparé (étape 7) : si rien n'est trouvé, ou en cas
    d'erreur de lecture, le verdict est "premier démarrage observé". Un
    fichier non décodable (réenregistré en ANSI par un correspondant, ou
    tronqué en plein caractère multi-octets par un disque plein) lève
    UnicodeDecodeError, qui dérive de ValueError et non d'OSError : sans ce
    second type, l'exception remonte et empêche le serveur de démarrer —
    exactement ce que le §11 du contrat interdit à ce journal de faire.
    """
    try:
        with open(TECHNIQUE, encoding="utf-8") as f:
            lignes = f.readlines()
    except (OSError, ValueError):
        return "premier démarrage observé"

    precedente = None
    for ligne in reversed(lignes):
        if "DEMARRAGE" in ligne:
            correspondance = re.search(r"certificat=([0-9a-f]+)", ligne)
            if correspondance:
                precedente = correspondance.group(1)
            break

    if precedente is None:
        return "premier démarrage observé"
    if precedente == empreinte:
        return "certificat identique au démarrage précédent"
    return "certificat différent du démarrage précédent"


def classe_route(chemin):
    """Classe un chemin canonique en une des quatre catégories fermées.

    Jamais un chemin brut, contrôlé par le client, n'atteint le journal
    technique (décision D3) : une tentative de traversée ou un nom de
    fichier ne traverse jamais cette fonction, qui ne rend que des membres
    de ROUTES_TECHNIQUES.
    """
    if chemin == "/depot":
        return "depot"
    if chemin == "/sante":
        return "sante"
    if chemin in ("/", ""):
        return "formulaire"
    extension = os.path.splitext(chemin)[1].lower()
    if extension in EXTENSIONS_SERVIES:
        return "formulaire"
    return "autre"


def detail_refus_depot(motif):
    """Compose le détail d'un dépôt refusé, sur un vocabulaire fermé : une
    valeur hors de MOTIFS_REFUS_DEPOT devient "motif-inconnu" plutôt que
    d'être recopiée telle quelle."""
    if motif not in MOTIFS_REFUS_DEPOT:
        motif = "motif-inconnu"
    return "refus motif={}".format(motif)


def detail_depot_ok(octets):
    """Compose le détail d'un dépôt réussi : une taille, jamais un nom."""
    return "ok {} octets".format(octets)


def detail_echec_ecriture(erreur):
    """Compose le détail d'un échec d'écriture à partir d'errno et de
    strerror seuls : str(OSError) inclurait le chemin complet, donc le nom
    du patient (décision D4). C'est le point le plus facile à rater de tout
    le contrat — d'où une fonction dédiée, plutôt qu'un formatage recopié à
    chaque site."""
    return "errno={} {}".format(erreur.errno, erreur.strerror)


def _ajouter_ligne_technique(ligne):
    try:
        with open(TECHNIQUE, "a", encoding="utf-8") as f:
            f.write(ligne)
    except OSError:
        pass


def journaliser_technique(evenement, detail=""):
    """Trace une ligne dans technique.log, sans jamais rien écrire sur
    stderr (décision D5, pour ne pas doubler chaque ligne), ni lever sur un
    nom d'événement fautif : un journal ne doit jamais coûter un dépôt.
    """
    if not JOURNAL_TECHNIQUE_ACTIF:
        return
    if evenement not in EVENEMENTS_TECHNIQUES:
        evenement = "EVENEMENT_INCONNU"

    # L'horodatage est sans espace (isoformat, timespec="seconds") : le
    # premier mot de chaque ligne en est un, et le test anti-fuite s'appuie
    # sur ce fait pour appliquer le motif IPv6 à la ligne privée de son
    # premier mot.
    horodatage = datetime.datetime.now().isoformat(timespec="seconds")

    with _verrou_journal:
        # faire_tourner_journal() est appelée ici, sous le verrou déjà
        # acquis : surtout ne jamais rappeler journaliser_technique() depuis
        # l'intérieur de ce bloc, ce serait un interblocage (verrou non
        # réentrant). L'événement ROTATION s'écrit donc directement.
        if faire_tourner_journal(TECHNIQUE):
            _ajouter_ligne_technique("{} {} archive\n".format(
                datetime.datetime.now().isoformat(timespec="seconds"),
                EVENEMENT_ROTATION))
        _ajouter_ligne_technique("{} {} {}\n".format(
            horodatage, evenement, detail))


# --------------------------------------------------------------------------
# Serveur
# --------------------------------------------------------------------------

class ServeurBilan(ThreadingHTTPServer):
    """Serveur d'écoute, en double pile quand la machine le permet.

    `localhost` se résout d'abord en ::1 : un serveur lié au seul 0.0.0.0 y
    est injoignable, et le praticien qui ouvre le formulaire sur le PC lui-même
    obtient un refus de connexion. On écoute donc en IPv6 avec IPV6_V6ONLY
    désactivé, ce qui couvre aussi l'IPv4.

    Si la pile IPv6 est absente, ou si IPV6_V6ONLY ne peut pas être désactivé,
    on retombe entièrement en IPv4 : mieux vaut perdre l'accès par ::1 que
    d'écouter en IPv6 pur, ce qui rendrait la tablette incapable de se
    connecter tout en laissant croire que le serveur tourne.
    """

    address_family = socket.AF_INET6
    daemon_threads = True

    # Sous Windows, SO_REUSEADDR n'a pas la sémantique POSIX : il laisse deux
    # processus se lier au même port, l'ancien continuant de répondre pendant
    # que le nouveau annonce un démarrage réussi. Un port déjà pris doit
    # échouer franchement.
    allow_reuse_address = (os.name != "nt")

    def __init__(self, adresse, gestionnaire):
        try:
            super().__init__(adresse, gestionnaire)
        except OSError:
            if self.address_family != socket.AF_INET6:
                raise
            self.address_family = socket.AF_INET
            super().__init__(adresse, gestionnaire)

    def server_bind(self):
        if self.address_family == socket.AF_INET6:
            # Si IPV6_V6ONLY ne peut pas être désactivé, l'écoute resterait
            # purement IPv6. La tablette se connecte en 192.168.1.x : elle
            # serait injoignable, et le serveur paraîtrait pourtant démarré.
            # L'erreur est donc laissée remonter, pour que __init__ retombe
            # franchement en IPv4.
            self.socket.setsockopt(socket.IPPROTO_IPV6,
                                   socket.IPV6_V6ONLY, 0)

        # HTTPServer.server_bind() appelle socket.getfqdn(), c'est-à-dire une
        # résolution DNS inverse, entre le bind() et le listen(). Sur un
        # réseau sans DNS joignable — celui du cabinet comme celui d'un
        # runner d'intégration continue — elle peut bloquer plusieurs
        # dizaines de secondes, pendant lesquelles le serveur semble démarré
        # mais refuse toute connexion. On saute donc l'appel : server_name ne
        # sert qu'aux en-têtes CGI, que ce serveur n'émet pas.
        socketserver.TCPServer.server_bind(self)
        self.server_name = "bilan-posturo"
        self.server_port = self.server_address[1]

    def get_request(self):
        """Remonte les échecs de négociation TLS.

        Quand la socket d'écoute est chiffrée, le handshake a lieu ici, et
        socketserver avale les OSError sans rien journaliser : le navigateur
        affiche une erreur pendant que le serveur reste parfaitement muet.
        """
        try:
            return super().get_request()
        except ssl.SSLError as erreur:
            journaliser("{} TLS refusé : {}\n".format(
                datetime.datetime.now().isoformat(timespec="seconds"), erreur))
            # self.client_address n'est pas disponible à ce stade, et ne
            # doit pas y être cherché : aucune adresse dans technique.log
            # (décision D1).
            journaliser_technique("TLS_REFUSE", "raison={}".format(erreur))
            raise


class Gestionnaire(SimpleHTTPRequestHandler):
    config = None
    dossier_pdf = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=FORMULAIRE, **kwargs)

    # --- journalisation ----------------------------------------------------

    def handle_one_request(self):
        # Une connexion persistante sert plusieurs requêtes avec la même
        # instance : sans remise à zéro, une sonde de santé rendrait muettes
        # toutes les requêtes suivantes de la même connexion, et un code de
        # réponse laissé en place ferait porter à cette requête le code
        # d'une précédente.
        self.silencieux = False
        self._code_reponse_technique = 0
        super().handle_one_request()

    def log_request(self, code="-", size="-"):
        # Capture le code AVANT qu'il ne soit mis en forme dans la chaîne de
        # log_message() : log_message() est aussi appelée par log_error()
        # avec une tout autre forme d'arguments (vu par exemple à l'étape 4,
        # évaluation de la fuite), et reconstruire le code à partir du
        # format interne de BaseHTTPRequestHandler serait fragile — une
        # version de Python qui modifie cette chaîne romprait
        # silencieusement l'extraction, sans rien faire échouer d'autre.
        if isinstance(code, HTTPStatus):
            code = code.value
        self._code_reponse_technique = code
        super().log_request(code, size)

    def log_message(self, format, *args):
        # La sonde de santé est interrogée toutes les quelques dizaines de
        # secondes par chaque tablette allumée : la journaliser noierait les
        # dépôts et les erreurs sous des milliers de lignes par jour.
        if getattr(self, "silencieux", False):
            return
        journaliser("{} {} {}\n".format(
            datetime.datetime.now().isoformat(timespec="seconds"),
            self.address_string(), format % args))

        # Voie technique : ni adresse (self.address_string() n'y est jamais
        # passé), ni chemin brut — route est une classe fermée. Le code de
        # réponse n'est fiable que lorsque log_request() a déjà tourné pour
        # cette requête (remis à 0 par handle_one_request sinon) : un appel
        # ad hoc à log_message(), comme ceux de DEPOT ou ECHEC_ECRITURE, n'a
        # pas encore de code de réponse à cet instant.
        methode = getattr(self, "command", None)
        if methode not in ("GET", "HEAD", "POST"):
            methode = "autre"
        chemin = getattr(self, "path", "") or ""
        route = classe_route(chemin.split("?", 1)[0].split("#", 1)[0])
        code = getattr(self, "_code_reponse_technique", 0)
        journaliser_technique("REPONSE", "methode={} route={} code={}".format(
            methode, route, code))

    # --- authentification --------------------------------------------------

    def authentifie(self):
        entete = self.headers.get("Authorization", "")
        if not entete.startswith("Basic "):
            return False
        try:
            decode = base64.b64decode(entete[6:]).decode("utf-8")
            utilisateur, _, mot_de_passe = decode.partition(":")
        except (ValueError, binascii.Error, UnicodeDecodeError):
            return False

        # La comparaison porte sur les octets UTF-8 : compare_digest lève
        # TypeError sur une chaîne contenant un caractère non-ASCII, et un
        # identifiant accentué tuerait le thread sans qu'aucune réponse ne
        # parte.
        identifiant_ok = hmac.compare_digest(
            utilisateur.encode("utf-8"),
            self.config["utilisateur"].encode("utf-8"))
        mot_de_passe_ok = verifier_mot_de_passe(mot_de_passe,
                                                self.config["mot_de_passe"])
        # Les deux vérifications sont toujours exécutées : le temps de réponse
        # ne révèle pas si c'est l'identifiant ou le mot de passe qui est faux.
        return identifiant_ok and mot_de_passe_ok

    def exiger_authentification(self):
        # Ni identifiant, ni mot de passe, ni adresse : seule la classe de
        # route, fermée (décision D3). Un compteur d'échecs par identité
        # relève de C6, pas d'ici.
        journaliser_technique("AUTH_REFUSEE", "route={}".format(
            classe_route(self.chemin_demande())))
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("WWW-Authenticate", 'Basic realm="Bilan posturologique"')
        self.send_header("Content-Length", "0")
        self.end_headers()

    # --- en-têtes de sécurité ---------------------------------------------

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        super().end_headers()

    # --- GET ---------------------------------------------------------------

    def chemin_demande(self):
        """Chemin seul, sans chaîne de requête ni fragment."""
        return self.path.split("?", 1)[0].split("#", 1)[0]

    def autorise_lecture(self):
        """Filtre commun à GET et HEAD.

        Normalise le chemin et refuse tout ce qui n'est pas une ressource du
        formulaire. Appliqué aussi à HEAD : sans cela, un HEAD sur
        config.json confirmerait son existence et sa taille.

        Retourne False si la réponse a déjà été envoyée.
        """
        if not self.authentifie():
            self.exiger_authentification()
            return False

        chemin = self.chemin_demande()
        if chemin in ("/", ""):
            chemin = "/index.html"

        extension = os.path.splitext(chemin)[1].lower()
        if extension not in EXTENSIONS_SERVIES:
            self.send_error(HTTPStatus.FORBIDDEN, "Type de fichier non servi")
            return False

        self.path = chemin
        return True

    def do_GET(self):
        if self.chemin_demande() == "/sante":
            self.repondre_sante(avec_corps=True)
            return
        if self.autorise_lecture():
            super().do_GET()

    def do_HEAD(self):
        if self.chemin_demande() == "/sante":
            self.repondre_sante(avec_corps=False)
            return
        if self.autorise_lecture():
            super().do_HEAD()

    # --- sonde de santé ----------------------------------------------------

    def repondre_sante(self, avec_corps):
        """Répond « je suis là », sans authentification.

        La tablette interroge cette route en tâche de fond pour distinguer les
        pannes, que le navigateur confond toutes en une erreur de connexion :
        serveur arrêté, mauvaise adresse, mot de passe refusé. Elle est donc
        volontairement hors authentification — un 401 ne dirait pas si le
        serveur tourne.

        Elle ne révèle rien de plus que le port ouvert, qui répond déjà 401 à
        qui le sollicite : ni version, ni chemins, ni nombre de bilans.
        """
        self.silencieux = True
        corps = b'{"etat":"ok"}'
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        if avec_corps:
            self.wfile.write(corps)

    # --- POST /depot -------------------------------------------------------

    def do_POST(self):
        if not self.authentifie():
            self.exiger_authentification()
            return

        if self.path.split("?", 1)[0] != "/depot":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        try:
            taille = int(self.headers.get("Content-Length", 0))
        except ValueError:
            journaliser_technique("DEPOT",
                                  detail_refus_depot("content-length-invalide"))
            self.repondre_json(HTTPStatus.BAD_REQUEST,
                               {"erreur": "Content-Length invalide"})
            return

        if taille <= 0:
            journaliser_technique("DEPOT", detail_refus_depot("corps-vide"))
            self.repondre_json(HTTPStatus.BAD_REQUEST,
                               {"erreur": "Corps de requête vide"})
            return
        if taille > TAILLE_MAX:
            journaliser_technique("DEPOT", detail_refus_depot("trop-volumineux"))
            self.repondre_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                               {"erreur": "Fichier trop volumineux"})
            return

        contenu = self.rfile.read(taille)
        if len(contenu) != taille:
            # Connexion coupée en cours d'envoi : le PDF serait tronqué.
            journaliser_technique("DEPOT",
                                  detail_refus_depot("transfert-interrompu"))
            self.repondre_json(HTTPStatus.BAD_REQUEST,
                               {"erreur": "Transfert interrompu"})
            return

        # Le nom voyage en base64 : un en-tête HTTP ne transporte pas
        # fiablement les accents.
        nom_brut = "bilan.pdf"
        entete_nom = self.headers.get("X-Fichier")
        if entete_nom:
            try:
                nom_brut = base64.b64decode(entete_nom).decode("utf-8")
            except (ValueError, binascii.Error, UnicodeDecodeError):
                pass

        if not contenu.startswith(b"%PDF"):
            journaliser_technique("DEPOT", detail_refus_depot("non-pdf"))
            self.repondre_json(HTTPStatus.BAD_REQUEST,
                               {"erreur": "Le fichier reçu n'est pas un PDF"})
            return

        nom = assainir_nom(nom_brut)
        destination = chemin_libre(self.dossier_pdf, nom)

        try:
            ecrire_atomiquement(destination, contenu)
        except OSError as erreur:
            self.log_message("ECHEC ecriture %s : %s", destination, erreur)
            # errno/strerror seuls, jamais str(erreur) : il contient le
            # chemin complet, donc le nom du patient (décision D4).
            journaliser_technique("ECHEC_ECRITURE", detail_echec_ecriture(erreur))
            self.repondre_json(HTTPStatus.INTERNAL_SERVER_ERROR,
                               {"erreur": "Écriture impossible sur le PC"})
            return

        self.log_message("DEPOT %s (%d octets)",
                         os.path.basename(destination), len(contenu))
        journaliser_technique("DEPOT", detail_depot_ok(len(contenu)))
        self.repondre_json(HTTPStatus.OK, {
            "ok": True,
            "fichier": os.path.basename(destination),
            "octets": len(contenu),
        })

    def repondre_json(self, statut, donnees):
        corps = json.dumps(donnees, ensure_ascii=False).encode("utf-8")
        self.send_response(statut)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)


# --------------------------------------------------------------------------
# Démarrage
# --------------------------------------------------------------------------

def demarrer():
    config = charger_config()
    if config is None or not config.get("mot_de_passe"):
        print("Aucun mot de passe défini.")
        print("Lancez d'abord :  python3 serveur/serveur.py --config")
        return 1

    dossier_pdf = config["dossier_pdf"]
    if not os.path.isabs(dossier_pdf):
        dossier_pdf = os.path.join(RACINE, dossier_pdf)
    os.makedirs(dossier_pdf, exist_ok=True)

    Gestionnaire.config = config
    Gestionnaire.dossier_pdf = dossier_pdf

    global JOURNAL_TECHNIQUE_ACTIF
    JOURNAL_TECHNIQUE_ACTIF = config["journal_technique"]

    certificat = os.path.join(RACINE, config["certificat"])
    cle = os.path.join(RACINE, config["cle_privee"])

    # Pas de repli silencieux en clair : le formulaire transporte des données
    # de santé et le mot de passe voyage en HTTP Basic, donc en base64
    # réversible. Sans TLS, les deux circulent en clair sur le réseau du
    # cabinet. Mieux vaut un refus visible qu'un serveur qui paraît marcher.
    manquants = [os.path.basename(c) for c in (certificat, cle)
                 if not os.path.exists(c)]
    if manquants:
        print("Refus de démarrer : {} introuvable.".format(
            " et ".join(manquants)))
        print("Générez le certificat :  python3 serveur/generer_autorite.py <ip>")
        return 1

    contexte = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexte.minimum_version = ssl.TLSVersion.TLSv1_2
    # Sans ALPN, Chrome ferme la connexion sans envoyer un octet là où curl
    # bascule sans bruit en HTTP/1.1 : un ERR_EMPTY_RESPONSE sans la moindre
    # trace côté serveur.
    contexte.set_alpn_protocols(["http/1.1"])
    try:
        contexte.load_cert_chain(certificat, cle)
    except (ssl.SSLError, OSError) as erreur:
        print("Certificat inutilisable : {}".format(erreur))
        print("Regénérez-le :  python3 serveur/generer_autorite.py <ip>")
        return 1

    try:
        serveur = ServeurBilan(("", config["port"]), Gestionnaire)
    except OSError as erreur:
        print("Port {} indisponible : {}".format(config["port"], erreur))
        print("Une autre instance du serveur tourne probablement déjà.")
        return 1

    serveur.socket = contexte.wrap_socket(serveur.socket, server_side=True)

    print("Bilan posturologique — serveur démarré")
    print("  sur ce PC     : https://localhost:{}".format(config["port"]))
    print("  tablette      : https://<ip-du-pc>:{}".format(config["port"]))
    print("  identifiant   : {}".format(config["utilisateur"]))
    print("  dépôt des PDF : {}".format(dossier_pdf))
    print("  journal       : {}".format(JOURNAL))
    print("\nCtrl+C pour arrêter.\n")

    empreinte = empreinte_certificat(certificat)
    journaliser_technique("DEMARRAGE", "port={} certificat={} {}".format(
        config["port"], empreinte, verdict_certificat(empreinte)))

    motif_arret = "autre"
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du serveur.")
        motif_arret = "interruption"
    finally:
        # Le port se libère d'abord, sans dépendre d'une écriture de
        # journal : un journal ne doit jamais coûter autre chose que
        # lui-même (§10 du contrat), et surtout pas la disponibilité du
        # port pour une relance.
        serveur.server_close()
        journaliser_technique("ARRET", "motif={}".format(motif_arret))
    return 0


def main():
    analyseur = argparse.ArgumentParser(
        description="Serveur du bilan posturologique.")
    analyseur.add_argument("--config", action="store_true",
                           help="configure l'identifiant et le mot de passe")
    arguments = analyseur.parse_args()

    if arguments.config:
        return definir_mot_de_passe()
    return demarrer()


if __name__ == "__main__":
    sys.exit(main())
