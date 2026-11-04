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
import stat
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

# Source unique du numéro de version (C4-T4) : le formulaire la lit par la
# même route que schema.json, le serveur la lit ici au démarrage, et
# tests/test_version.py échoue si package.json en diverge.
FICHIER_VERSION = os.path.join(FORMULAIRE, "version.json")
VERSION_INCONNUE = "inconnue"


def lire_version(chemin=FICHIER_VERSION):
    """Le numéro de version, ou "inconnue" — jamais une levée.

    Un fichier absent, illisible ou malformé ne doit pas empêcher le cabinet
    de démarrer. Le numéro est restreint à [0-9A-Za-z.+-] : il part dans
    technique.log, le journal qui circule, et rien d'autre qu'un numéro ne
    doit pouvoir y entrer par ce chemin.
    """
    try:
        with open(chemin, encoding="utf-8") as f:
            version = json.load(f).get("version")
    except (OSError, ValueError, AttributeError):
        return VERSION_INCONNUE
    if isinstance(version, str) and re.fullmatch(r"[0-9A-Za-z.+-]{1,32}", version):
        return version
    return VERSION_INCONNUE

TAILLE_MAX = 30 * 1024 * 1024      # 30 Mo : un bilan pèse ~1 à 3 Mo
ITERATIONS = 240_000               # coût du hachage PBKDF2

# Le serveur tourne désormais en service, donc en continu : sans rotation, le
# journal croîtrait indéfiniment. 5 Mo représentent environ 40 000 requêtes.
JOURNAL_TAILLE_MAX = 5 * 1024 * 1024
JOURNAL_ARCHIVES = 3

# Durée de conservation des deux journaux (C4-T2). Un cabinet qui fait une
# cinquantaine de requêtes par jour met plus de deux ans à remplir 5 Mo : la
# taille seule ne borne donc pas la durée. Un mois vaut 30 jours, écrit ici
# une seule fois : la rotation mensuelle et la purge s'en dérivent toutes
# deux, jamais d'un calendrier (un mois de calendrier varie de 28 à 31 jours).
JOURS_PAR_MOIS = 30
CONSERVATION_MOIS_DEFAUT = 6
CONSERVATION_MOIS_MAX = 120
# Une archive est purgée quand sa première ligne a plus de N mois MOINS ce
# délai, et la purge est revérifiée à l'écriture au plus à cet intervalle
# (D3 bis). Les deux sont liés : la première ligne était, à la vérification
# précédente, plus jeune que le seuil ; elle ne peut donc pas avoir dépassé N
# mois à la suivante. Une constante, pour ne pas les désaccorder.
PURGE_INTERVALLE = datetime.timedelta(days=1)
# Fil de purge périodique (voir boucle_purge_periodique) : il tient la promesse
# « au plus N mois » même quand plus rien ne s'écrit. Son intervalle doit rester
# inférieur à PURGE_INTERVALLE, sans quoi l'avance d'un jour ne couvre plus
# l'attente entre deux tours (un test le vérifie).
PURGE_PERIODIQUE_SECONDES = 6 * 3600
# Positionné depuis la configuration dans demarrer(). Toujours relu via
# conservation_mois(), qui le revalide : une valeur absurde ne lève jamais.
CONSERVATION_JOURNAUX_MOIS = CONSERVATION_MOIS_DEFAUT

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
# n'atteint le journal technique (décision D3). "cabinet" (C2-T1, décision
# D5) permet de distinguer, à distance, « la tablette n'a jamais demandé
# l'identité » de « elle l'a demandée et a reçu 401 ».
ROUTES_TECHNIQUES = frozenset({"depot", "sante", "formulaire", "cabinet", "autre"})

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
    # Durée de conservation des deux journaux, en mois de 30 jours (C4-T2).
    "conservation_journaux_mois": CONSERVATION_MOIS_DEFAUT,
    # Identité du cabinet (C2-T1) : chaînes vides par défaut, jamais un
    # exemple générique — un exemple finit tôt ou tard imprimé sur un bilan
    # réel (décision D3 du contrat). Sert à remplir l'en-tête du formulaire
    # via GET /cabinet, et à nommer le fichier PDF (convention_nommage).
    "cabinet": {
        "nom": "",
        "praticien": "",
        "adresse": "",
        "courriel": "",
        "telephone": "",
        "logo": "images/favicon.jpeg",
        "convention_nommage": "Bilan_{date}_{patient}",
    },
}

# Dérivée de CONFIG_DEFAUT, jamais retranscrite : la route /cabinet, la
# saisie de --config et les tests s'appuient tous sur cette même liste
# (piège « une liste normative recopiée finit fausse »).
CLES_CABINET = tuple(CONFIG_DEFAUT["cabinet"])


# --------------------------------------------------------------------------
# Configuration et mots de passe
# --------------------------------------------------------------------------

def normaliser_conservation_mois(valeur):
    """Rend la durée de conservation si c'est un entier de 1 à
    CONSERVATION_MOIS_MAX, sinon la valeur par défaut, sans jamais lever.

    Un booléen est écarté explicitement : en Python, True est un entier, et
    `"conservation_journaux_mois": true` donnerait un mois de conservation.
    Des `if` plutôt que des `assert`, qui s'évaporeraient sous python -O.
    """
    if isinstance(valeur, bool) or not isinstance(valeur, int):
        return CONSERVATION_MOIS_DEFAUT
    if valeur < 1 or valeur > CONSERVATION_MOIS_MAX:
        return CONSERVATION_MOIS_DEFAUT
    return valeur


def charger_config():
    if not os.path.exists(CONFIG):
        return None
    with open(CONFIG, encoding="utf-8") as f:
        config = json.load(f)
    complet = dict(CONFIG_DEFAUT)
    complet.update(config)

    # Fusion à deux niveaux pour la seule clé "cabinet" : une fusion de
    # surface écraserait un bloc partiel au lieu de le compléter clé à clé,
    # ce qui romprait tout config.json d'un cabinet déjà installé avant
    # cette version. Aucune levée : un "cabinet" absent, null, ou qui n'est
    # pas un dictionnaire retombe simplement sur les défauts. Une sous-clé
    # qui n'est pas une chaîne (null, nombre, objet, écrits à la main) y
    # retombe aussi : sinon demarrer() lève sur .strip() et le cabinet ne
    # redémarre plus après la réparation manuelle que la doc conseille.
    cabinet = dict(CONFIG_DEFAUT["cabinet"])
    brut = config.get("cabinet")
    if isinstance(brut, dict):
        for cle in CLES_CABINET:
            if isinstance(brut.get(cle), str):
                cabinet[cle] = brut[cle]
    complet["cabinet"] = cabinet

    # Même tolérance que pour « cabinet » : une valeur écrite à la main qui
    # n'est pas un entier de 1 à 120 retombe sur 6 au lieu d'empêcher le
    # démarrage.
    complet["conservation_journaux_mois"] = normaliser_conservation_mois(
        complet.get("conservation_journaux_mois"))

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


def saisir_cabinet(config):
    """Demande chaque champ de l'identité du cabinet, valeur courante entre
    crochets ; une saisie vide la conserve. Ne fait aucune entrée-sortie
    fichier : travaille uniquement sur le dictionnaire reçu.

    Dérivée de CLES_CABINET, jamais retranscrite : un champ ajouté au bloc
    "cabinet" de CONFIG_DEFAUT est saisi ici sans modification de cette
    fonction.
    """
    # Copie défensive : config["cabinet"] peut être le dictionnaire partagé
    # de CONFIG_DEFAUT (repli de definir_mot_de_passe sur un config.json
    # absent) — le modifier en place altérerait les défauts pour le reste
    # du processus.
    cabinet = dict(config.get("cabinet") or CONFIG_DEFAUT["cabinet"])

    print("\nIdentité du cabinet, affichée sur chaque bilan généré.")
    for cle in CLES_CABINET:
        saisie = input("{} [{}] : ".format(cle, cabinet.get(cle, ""))).strip()
        if saisie:
            cabinet[cle] = saisie

    config["cabinet"] = cabinet
    return config


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

    config = saisir_cabinet(config)

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


def conservation_mois():
    """Durée de conservation en vigueur, toujours valide."""
    return normaliser_conservation_mois(CONSERVATION_JOURNAUX_MOIS)


def seuil_purge():
    """Âge au-delà duquel la première ligne d'une archive la condamne :
    N mois moins PURGE_INTERVALLE (D3 bis). L'avance garantit qu'aucune ligne
    ne dépasse N mois entre deux vérifications ; elle coûte au plus un jour
    de conservation."""
    return (datetime.timedelta(days=JOURS_PAR_MOIS * conservation_mois())
            - PURGE_INTERVALLE)


def generations_maximales():
    """Nombre maximal d'archives d'un journal (décision D4).

    Avec une rotation mensuelle, JOURNAL_ARCHIVES = 3 couperait la
    conservation à trois mois : le compte ne doit jamais être la borne de
    durée. N + 1 générations laissent l'âge, et lui seul, décider ; la borne
    disque reste finie (au plus JOURNAL_TAILLE_MAX par génération).
    """
    return max(JOURNAL_ARCHIVES, conservation_mois() + 1)


def _horodatage_de_tete(chemin):
    """Date de la première ligne du fichier, ou None si elle est illisible.

    Les deux journaux commencent chaque ligne par
    datetime.now().isoformat(timespec="seconds"), naïf et sans espace. Le
    motif est strict à dessein : fromisoformat() accepte plus de formes
    depuis Python 3.11 qu'en 3.9 (« 20261019 », fuseaux), et un même fichier
    ne doit pas être daté différemment selon l'interpréteur.
    """
    try:
        with open(chemin, "rb") as f:
            tete = f.readline(64)
    except OSError:
        return None
    mots = tete.decode("utf-8", errors="replace").split()
    if not mots or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", mots[0]):
        return None
    try:
        return datetime.datetime.fromisoformat(mots[0])
    except ValueError:
        return None


def _age_premiere_ligne(chemin, maintenant):
    """Âge de la première ligne du fichier, ou None si rien ne permet de le
    dire.

    Horodatage illisible, ou postérieur à l'horloge (corrompu, ou horloge
    reculée : sinon il rendrait le fichier immortel) : repli sur la date de
    modification, plus prudente. La décision D1 n'est pas tenue sur un
    fichier corrompu, mais rien ne lève.
    """
    horodatage = _horodatage_de_tete(chemin)
    if horodatage is not None and horodatage <= maintenant:
        return maintenant - horodatage
    try:
        modification = datetime.datetime.fromtimestamp(os.lstat(chemin).st_mtime)
    except (OSError, OverflowError, ValueError):
        return None
    return maintenant - modification


# Instant de la dernière purge de chaque journal, pour la limiter à une par
# intervalle. Lu et écrit sous _verrou_journal (ou hors de tout fil concurrent,
# au démarrage et dans les tests).
_derniere_purge = {}


def _est_fichier_ordinaire(chemin):
    """Vrai pour un fichier ordinaire, faux pour un lien symbolique, un
    dossier, un chemin absent ou illisible. lstat, jamais stat : un lien n'est
    pas suivi."""
    try:
        return stat.S_ISREG(os.lstat(chemin).st_mode)
    except OSError:
        return False


def purger_archives(chemin=None, maintenant=None):
    """Supprime les archives dont la première ligne a plus de N mois.

    Point nommé de l'audit (décision D6) : ne supprime que des chemins de la
    forme exacte « <journal>.<entier> », entier de 1 à CONSERVATION_MOIS_MAX + 1
    (D6 bis : baisser N ne laisse pas d'archives orphelines hors d'atteinte),
    construits un à un — jamais de recherche par motif (glob) : un
    « journal.log.bak », un « journal.log.1.x » ou un autre fichier du
    dossier ne peuvent pas être désignés. Un lien symbolique ou un dossier de
    ce nom est laissé tel quel (lstat, jamais stat). Ne lève pas, et ne
    journalise rien : elle est appelée sous _verrou_journal, non réentrant,
    et journaliser_technique() le reprendrait (interblocage).

    Mémorise l'instant de la purge (_derniere_purge) pour que l'écriture ne la
    refasse pas plus d'une fois par PURGE_INTERVALLE.

    Rend le nombre d'archives supprimées. Le défaut de chemin et d'horloge se
    résout dans le corps, comme dans faire_tourner_journal().
    """
    if chemin is None:
        chemin = JOURNAL
    if maintenant is None:
        maintenant = datetime.datetime.now()

    _derniere_purge[chemin] = maintenant
    limite = seuil_purge()
    supprimees = 0
    for rang in range(1, CONSERVATION_MOIS_MAX + 2):
        archive = "{}.{}".format(chemin, rang)
        try:
            if not _est_fichier_ordinaire(archive):
                continue
            age = _age_premiere_ligne(archive, maintenant)
            if age is not None and age > limite:
                os.remove(archive)
                supprimees += 1
        except OSError:
            continue
    return supprimees


def purger_au_demarrage():
    """Purge les archives des deux journaux avant la première écriture.

    Un serveur arrêté plusieurs mois ne tourne pas et ne purge donc rien :
    sans ce passage, les archives périmées survivraient jusqu'à la prochaine
    rotation. Les deux journaux, même si journal_technique est désactivé : la
    promesse vaut pour les fichiers déjà là.
    """
    with _verrou_journal:
        for chemin in (JOURNAL, TECHNIQUE):
            purger_archives(chemin)


def entretenir_journaux(maintenant=None):
    """Passe d'entretien des deux journaux, hors de toute écriture : rotation
    si le courant a plus d'un mois ou dépasse la taille, puis purge
    inconditionnelle des archives (le plafond d'un jour de purge_due ne
    s'applique pas ici : le fil appelle déjà à intervalle fixe).

    Sans écriture, le journal courant vieillirait seul et ses lignes
    passeraient N mois. La rotation d'un technique.log par ce chemin
    n'inscrit pas de ligne ROTATION : l'écrire créerait le fichier même
    quand journal_technique est désactivé.

    Prend _verrou_journal et ne journalise rien dessous (interblocage).
    """
    if maintenant is None:
        maintenant = datetime.datetime.now()
    with _verrou_journal:
        for chemin in (JOURNAL, TECHNIQUE):
            faire_tourner_journal(chemin, maintenant)
            purger_archives(chemin, maintenant)


def boucle_purge_periodique(arret, attente=PURGE_PERIODIQUE_SECONDES,
                            horloge=None):
    """Corps du fil de purge : toutes les `attente` secondes, entretient les
    deux journaux, jusqu'à ce que `arret` (un threading.Event) soit levé.

    Attente et événement d'arrêt s'injectent : un test passe un événement
    simulé et n'attend jamais. `arret.wait()` rend True quand l'événement est
    levé, ce qui arrête la boucle sans attendre le délai. Aucune exception
    n'arrête la boucle (un journal ne doit jamais coûter autre chose que
    lui-même), et rien n'est journalisé : une erreur de purge se retrouvera
    à l'écriture suivante, qui repasse par les mêmes fonctions.
    """
    while not arret.wait(attente):
        try:
            entretenir_journaux(horloge() if horloge is not None else None)
        except Exception:
            pass


def demarrer_purge_periodique():
    """Lance le fil de purge, en démon : il meurt avec le processus. Rend le
    fil et son événement d'arrêt."""
    arret = threading.Event()
    fil = threading.Thread(target=boucle_purge_periodique, args=(arret,),
                           name="purge-journaux", daemon=True)
    fil.start()
    return fil, arret


# Nom provisoire du journal courant pendant une rotation. Hors de la forme
# « <journal>.<entier> » : la purge ne le voit pas, et il ne se confond avec
# aucune archive.
SUFFIXE_ROTATION = ".rotation"

# Dernier échec de rotation de chaque journal : on ne retente pas à chaque
# écriture un renommage qui échoue (journal tenu ouvert sous Windows), une
# fois par PURGE_INTERVALLE suffit. Même verrou que _derniere_purge.
_rotation_ratee = {}


def _rang(chemin, rang):
    return "{}.{}".format(chemin, rang)


def _liberer_le_rang_un(chemin):
    """Décale les archives pour que « <journal>.1 » soit libre. Lève OSError.

    Chaque archive monte d'un rang seulement jusqu'au premier trou : une
    archive n'est supprimée par le compte que si la chaîne est pleine. Un
    décalage interrompu à mi-chemin, relancé, ne perd donc rien (la boucle
    d'origine supprimait « la plus ancienne » avant de savoir si le courant
    pourrait être archivé : audit C4-T2).

    Une entrée qui n'est pas un fichier ordinaire (dossier, lien) à un rang
    est une barrière : on ne la touche jamais, et le décalage s'arrête sous
    elle. Une archive part alors un peu plus tôt, ce que D1 tolère ; le
    journal courant, lui, continue de tourner. Seule une barrière au rang 1
    interdit toute rotation.
    """
    borne = generations_maximales()
    plafond = borne
    for rang in range(1, borne + 1):
        nom = _rang(chemin, rang)
        if os.path.lexists(nom) and not _est_fichier_ordinaire(nom):
            plafond = rang - 1
            break
    if plafond < 1:
        raise OSError("le rang 1 des archives est occupé par autre chose "
                      "qu'un fichier")

    libre = None
    for rang in range(1, plafond + 1):
        if not os.path.lexists(_rang(chemin, rang)):
            libre = rang
            break
    if libre is None:
        # Chaîne pleine : la plus ancienne part par le compte.
        os.remove(_rang(chemin, plafond))
        libre = plafond
    for rang in range(libre - 1, 0, -1):
        os.replace(_rang(chemin, rang), _rang(chemin, rang + 1))


def _replacer_le_temporaire(chemin):
    """Place en « .1 » le journal laissé sous son nom provisoire par une
    rotation interrompue. Sans effet s'il n'y en a pas. Ne lève pas."""
    temporaire = chemin + SUFFIXE_ROTATION
    if not _est_fichier_ordinaire(temporaire):
        return
    try:
        _liberer_le_rang_un(chemin)
        os.replace(temporaire, _rang(chemin, 1))
    except OSError:
        pass


def purge_due(chemin, maintenant):
    """Vrai si la dernière purge de ce journal remonte à PURGE_INTERVALLE ou
    plus, ou n'a jamais eu lieu. Une horloge reculée (écart négatif) compte
    comme due : mieux vaut purger trop que laisser vieillir."""
    derniere = _derniere_purge.get(chemin)
    if derniere is None:
        return True
    ecart = maintenant - derniere
    return ecart < datetime.timedelta(0) or ecart >= PURGE_INTERVALLE


def faire_tourner_journal(chemin=None, maintenant=None):
    """Archive le journal au-delà de JOURNAL_TAILLE_MAX, ou dès que sa
    première ligne a plus d'un mois (décision D2), puis purge les archives
    périmées (D3). Sans rotation, la purge est quand même revérifiée, au plus
    une fois par jour (D3 bis) : sans cela, une archive devenue éligible
    attendrait la rotation suivante et ses lignes dépasseraient N mois.

    Partagée par les deux journaux : le défaut se résout ici, dans le corps,
    et non dans la signature — sinon il serait figé à l'import, et les tests
    qui remplacent le global JOURNAL (RotationDuJournal) cesseraient d'agir
    sur cette fonction. L'horloge (`maintenant`, un datetime naïf local) suit
    la même règle et s'injecte dans les tests : jamais de sleep.

    Conserve generations_maximales() générations. Toute erreur est ignorée :
    un journal qu'on ne peut pas faire tourner ne doit pas empêcher le
    serveur de répondre. Rend True si une rotation a eu lieu, pour que
    l'appelant (déjà sous verrou dans journaliser_technique) puisse noter
    l'événement sans ré-acquérir ce verrou.
    """
    if chemin is None:
        chemin = JOURNAL
    if maintenant is None:
        maintenant = datetime.datetime.now()

    # D'abord, une rotation interrompue : ses lignes ne sont dans aucune
    # archive reconnue tant qu'elles restent sous le nom provisoire.
    _replacer_le_temporaire(chemin)

    try:
        taille = os.path.getsize(chemin)
        a_tourner = taille >= JOURNAL_TAILLE_MAX
        # Un fichier vide n'a rien à archiver, quelle que soit sa date.
        if not a_tourner and taille > 0:
            age = _age_premiere_ligne(chemin, maintenant)
            a_tourner = (age is not None
                         and age > datetime.timedelta(days=JOURS_PAR_MOIS))
    except OSError:
        # Journal absent : pas de rotation, mais des archives peuvent
        # attendre leur purge.
        a_tourner = False
    if a_tourner:
        derniere = _rotation_ratee.get(chemin)
        if (derniere is not None
                and datetime.timedelta(0) <= maintenant - derniere
                < PURGE_INTERVALLE):
            a_tourner = False
    # Un nom provisoire encore là écraserait des lignes non archivées.
    if a_tourner and os.path.lexists(chemin + SUFFIXE_ROTATION):
        a_tourner = False
    # Un non-fichier au rang 1 interdit toute rotation : on ne déplace pas le
    # courant sous son nom provisoire pour ne pas pouvoir le replacer.
    rang_un = _rang(chemin, 1)
    if a_tourner and os.path.lexists(rang_un) and not _est_fichier_ordinaire(rang_un):
        a_tourner = False
    if not a_tourner:
        if purge_due(chemin, maintenant):
            purger_archives(chemin, maintenant)
        return False

    # Le courant passe d'abord sous son nom provisoire : si ce renommage
    # échoue (journal tenu ouvert sous Windows), aucune archive n'a bougé ni
    # disparu. Le décalage ne vient qu'ensuite (audit C4-T2).
    temporaire = chemin + SUFFIXE_ROTATION
    try:
        os.replace(chemin, temporaire)
    except OSError:
        _rotation_ratee[chemin] = maintenant
        if purge_due(chemin, maintenant):
            purger_archives(chemin, maintenant)
        return False
    try:
        _liberer_le_rang_un(chemin)
        os.replace(temporaire, _rang(chemin, 1))
    except OSError:
        # Le courant reste sous son nom provisoire ; _replacer_le_temporaire
        # le placera à l'écriture suivante (et tant qu'il est là, aucune
        # nouvelle rotation ne part : pas besoin de la limite quotidienne).
        return False
    _rotation_ratee.pop(chemin, None)

    # Après le décalage, pour que l'archive qui vient d'être créée soit jugée
    # elle aussi : un journal courant resté plus de N mois sans écriture
    # s'archive puis disparaît dans le même passage.
    purger_archives(chemin, maintenant)
    return True


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
    if chemin == "/cabinet":
        return "cabinet"
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
        if self.chemin_demande() == "/cabinet":
            self.repondre_cabinet(avec_corps=True)
            return
        if self.autorise_lecture():
            super().do_GET()

    def do_HEAD(self):
        if self.chemin_demande() == "/sante":
            self.repondre_sante(avec_corps=False)
            return
        if self.chemin_demande() == "/cabinet":
            self.repondre_cabinet(avec_corps=False)
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

    # --- identité du cabinet (C2-T1) ----------------------------------------

    def repondre_cabinet(self, avec_corps):
        """Répond l'identité du cabinet, authentifiée contrairement à
        /sante : des coordonnées professionnelles ne sont pas un secret,
        mais rien n'oblige à les offrir à qui scanne le port (décision D2).

        Construit par itération sur CLES_CABINET, jamais par sérialisation
        du sous-dictionnaire lu dans le fichier (décision D4) : un
        config.json bricolé pourrait porter n'importe quoi sous "cabinet",
        la réponse ne rend que ce qu'elle a promis.
        """
        if not self.authentifie():
            self.exiger_authentification()
            return

        cabinet = self.config.get("cabinet") or {}
        donnees = {cle: cabinet.get(cle, "") for cle in CLES_CABINET}
        corps = json.dumps(donnees, ensure_ascii=False).encode("utf-8")

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        # Pas de Cache-Control ici : end_headers() l'émet déjà, un second
        # appel produirait l'en-tête en double.
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

    # Un cabinet mis à jour sans relancer --config n'a pas encore saisi son
    # identité : ce n'est pas un refus de démarrer (le formulaire reste
    # utile pour tout sauf l'export), mais un bilan ne pourra pas sortir
    # (D7) tant que l'identité manque. L'avertissement nomme le geste.
    identite_absente = not config["cabinet"]["praticien"].strip()

    dossier_pdf = config["dossier_pdf"]
    if not os.path.isabs(dossier_pdf):
        dossier_pdf = os.path.join(RACINE, dossier_pdf)
    os.makedirs(dossier_pdf, exist_ok=True)

    Gestionnaire.config = config
    Gestionnaire.dossier_pdf = dossier_pdf

    global JOURNAL_TECHNIQUE_ACTIF
    JOURNAL_TECHNIQUE_ACTIF = config["journal_technique"]
    global CONSERVATION_JOURNAUX_MOIS
    CONSERVATION_JOURNAUX_MOIS = config["conservation_journaux_mois"]

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
    print("  version       : {}".format(lire_version()))
    print("  identifiant   : {}".format(config["utilisateur"]))
    print("  dépôt des PDF : {}".format(dossier_pdf))
    print("  journal       : {}".format(JOURNAL))
    if identite_absente:
        print("\nAVERTISSEMENT : identité du cabinet non configurée — les "
              "bilans ne pourront pas être exportés.")
        print("Lancez :  python3 serveur/serveur.py --config")
    print("\nCtrl+C pour arrêter.\n")

    purger_au_demarrage()
    _, arret_purge = demarrer_purge_periodique()

    empreinte = empreinte_certificat(certificat)
    journaliser_technique("DEMARRAGE", "version={} port={} certificat={} {}".format(
        lire_version(), config["port"], empreinte, verdict_certificat(empreinte)))

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
        arret_purge.set()
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
