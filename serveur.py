#!/usr/bin/env python3
"""
Serveur du bilan posturologique.

Trois rôles :
  1. servir le formulaire (index.html, style.css, script.js, lib/, images/) ;
  2. recevoir les PDF générés sur la tablette et les écrire dans le dossier
     patient du PC (route POST /depot) ;
  3. protéger l'ensemble par un mot de passe et par TLS, tous deux
     obligatoires : sans certificat, le serveur refuse de démarrer.

N'utilise que la bibliothèque standard : rien à installer au cabinet.
Le certificat, lui, se fabrique avec generer_autorite.py.

    python3 generer_autorite.py 192.168.1.13   # certificat, une fois
    python3 serveur.py --config                # identifiant et mot de passe
    python3 serveur.py                         # démarrage
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
import unicodedata
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

RACINE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(RACINE, "config.json")
JOURNAL = os.path.join(RACINE, "journal.log")

TAILLE_MAX = 30 * 1024 * 1024      # 30 Mo : un bilan pèse ~1 à 3 Mo
ITERATIONS = 240_000               # coût du hachage PBKDF2

# Seuls ces fichiers sont servis. Tout le reste est refusé, ce qui met hors
# d'atteinte config.json, journal.log, serveur.py et les certificats.
EXTENSIONS_SERVIES = {".html", ".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".ico"}

CONFIG_DEFAUT = {
    "port": 8000,
    "dossier_pdf": "bilans",
    "utilisateur": "cabinet",
    "mot_de_passe": "",
    "certificat": "certificat.pem",
    "cle_privee": "cle.pem",
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
            sys.stderr.write("{} TLS refusé : {}\n".format(
                datetime.datetime.now().isoformat(timespec="seconds"), erreur))
            try:
                with open(JOURNAL, "a", encoding="utf-8") as f:
                    f.write("{} TLS refusé : {}\n".format(
                        datetime.datetime.now().isoformat(timespec="seconds"),
                        erreur))
            except OSError:
                pass
            raise


class Gestionnaire(SimpleHTTPRequestHandler):
    config = None
    dossier_pdf = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=RACINE, **kwargs)

    # --- journalisation ----------------------------------------------------

    def log_message(self, format, *args):
        ligne = "{} {} {}\n".format(
            datetime.datetime.now().isoformat(timespec="seconds"),
            self.address_string(), format % args)
        sys.stderr.write(ligne)
        try:
            with open(JOURNAL, "a", encoding="utf-8") as f:
                f.write(ligne)
        except OSError:
            pass

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

        chemin = self.path.split("?", 1)[0].split("#", 1)[0]
        if chemin in ("/", ""):
            chemin = "/index.html"

        extension = os.path.splitext(chemin)[1].lower()
        if extension not in EXTENSIONS_SERVIES:
            self.send_error(HTTPStatus.FORBIDDEN, "Type de fichier non servi")
            return False

        self.path = chemin
        return True

    def do_GET(self):
        if self.autorise_lecture():
            super().do_GET()

    def do_HEAD(self):
        if self.autorise_lecture():
            super().do_HEAD()

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
            self.repondre_json(HTTPStatus.BAD_REQUEST,
                               {"erreur": "Content-Length invalide"})
            return

        if taille <= 0:
            self.repondre_json(HTTPStatus.BAD_REQUEST,
                               {"erreur": "Corps de requête vide"})
            return
        if taille > TAILLE_MAX:
            self.repondre_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                               {"erreur": "Fichier trop volumineux"})
            return

        contenu = self.rfile.read(taille)
        if len(contenu) != taille:
            # Connexion coupée en cours d'envoi : le PDF serait tronqué.
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
            self.repondre_json(HTTPStatus.BAD_REQUEST,
                               {"erreur": "Le fichier reçu n'est pas un PDF"})
            return

        nom = assainir_nom(nom_brut)
        destination = chemin_libre(self.dossier_pdf, nom)

        try:
            ecrire_atomiquement(destination, contenu)
        except OSError as erreur:
            self.log_message("ECHEC ecriture %s : %s", destination, erreur)
            self.repondre_json(HTTPStatus.INTERNAL_SERVER_ERROR,
                               {"erreur": "Écriture impossible sur le PC"})
            return

        self.log_message("DEPOT %s (%d octets)",
                         os.path.basename(destination), len(contenu))
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
        print("Lancez d'abord :  python3 serveur.py --config")
        return 1

    dossier_pdf = config["dossier_pdf"]
    if not os.path.isabs(dossier_pdf):
        dossier_pdf = os.path.join(RACINE, dossier_pdf)
    os.makedirs(dossier_pdf, exist_ok=True)

    Gestionnaire.config = config
    Gestionnaire.dossier_pdf = dossier_pdf

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
        print("Générez le certificat :  python3 generer_autorite.py <ip-du-pc>")
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
        print("Regénérez-le :  python3 generer_autorite.py <ip-du-pc>")
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

    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du serveur.")
    finally:
        serveur.server_close()
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
