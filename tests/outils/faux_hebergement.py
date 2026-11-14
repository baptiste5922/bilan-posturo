"""Un faux hébergement HTTPS local, pour éprouver le client de mise à jour (C5-T2b).

Un serveur TLS sur 127.0.0.1 (certificat du bac à sable, `paquet_essai.certificats()`),
une table de routes, et la liste de ce qu'il a REÇU : méthode, chemin, en-têtes tels
qu'ils sont arrivés, taille du corps. C'est ce journal que les tests lisent pour
dire « trois requêtes exactement, dans cet ordre, rien de plus ».

Les comportements (corps, redirection, silence, goutte-à-goutte, coupure) sont des
fonctions `comportement(gestionnaire)` ; aucune ne dort plus de quelques secondes
et toutes s'arrêtent à la fermeture de l'hébergement.

Le faux mandataire (`FauxMandataire`) lit une ligne `CONNECT hôte:port` puis relaie
vers l'hébergement : de quoi montrer que le client passe par lui, et seulement
quand on le lui demande.

NE PART JAMAIS AU CABINET : il vit sous `tests/`. Exige `cryptography` (certificats).
"""

import http.server
import os
import socket
import socketserver
import ssl
import sys
import threading
import time

DOSSIER_OUTILS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DOSSIER_OUTILS)

import paquet_essai as pe  # noqa: E402


def contexte_client(autorite=None):
    """Un contexte TLS qui fait confiance à l'autorité du bac à sable (et à elle
    seule), vérification complète : celui des tests qui réussissent."""
    autorite = autorite or os.path.join(pe.certificats(), "autorite.crt")
    contexte = ssl.create_default_context(cafile=autorite)
    contexte.minimum_version = ssl.TLSVersion.TLSv1_2
    return contexte


class _Serveur(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, hebergement):
        socketserver.ThreadingTCPServer.__init__(self, ("127.0.0.1", 0), _Gestionnaire)
        self.hebergement = hebergement

    def finish_request(self, request, client_address):
        try:
            tls = self.hebergement.contexte.wrap_socket(request, server_side=True)
        except (ssl.SSLError, OSError):
            return              # un client qui refuse notre certificat : rien à servir
        try:
            self.RequestHandlerClass(tls, client_address, self)
        finally:
            try:
                tls.close()
            except OSError:
                pass

    def handle_error(self, request, client_address):
        pass                    # une coupure voulue par un test n'est pas un défaut


class _Gestionnaire(http.server.BaseHTTPRequestHandler):
    # HTTP/1.0 : sans Content-Length, le corps se termine à la fermeture, ce qui est
    # le cas « corps sans longueur » que le client doit borner lui-même.
    protocol_version = "HTTP/1.0"
    timeout = 20

    def log_message(self, *arguments):
        pass

    def _repondre(self):
        hebergement = self.server.hebergement
        hebergement.noter(self)
        comportement = hebergement.routes.get(self.path)
        if comportement is None:
            envoyer(self, b"introuvable", statut=404)
        else:
            comportement(self)

    do_GET = do_POST = do_PUT = do_HEAD = do_DELETE = _repondre


def envoyer(gestionnaire, corps, statut=200, entetes=(), avec_longueur=True):
    gestionnaire.send_response(statut)
    if avec_longueur:
        gestionnaire.send_header("Content-Length", str(len(corps)))
    for nom, valeur in entetes:
        gestionnaire.send_header(nom, valeur)
    gestionnaire.end_headers()
    gestionnaire.wfile.write(corps)


def corps(octets, statut=200):
    return lambda g: envoyer(g, octets, statut)


def redirection(cible, statut=302):
    return lambda g: envoyer(g, b"", statut, entetes=(("Location", cible),))


def statut(code):
    return lambda g: envoyer(g, b"statut d'essai", code)


def sans_corps_annonce(taille):
    """Annonce `taille` octets et n'en envoie AUCUN : un client qui lit avant de
    juger la taille reste suspendu."""
    def comportement(g):
        g.send_response(200)
        g.send_header("Content-Length", str(taille))
        g.end_headers()
        g.wfile.flush()
        g.server.hebergement.attendre(8)
    return comportement


def corps_sans_longueur(taille, puis_goutte=20):
    """Un corps de `taille` octets, sans Content-Length, puis un octet toutes les
    demi-secondes pendant `puis_goutte` secondes SANS fermer : un client qui lit
    jusqu'à la fin (`read()`) au lieu de s'arrêter à sa limite reste suspendu."""
    def comportement(g):
        g.send_response(200)
        g.end_headers()
        restant = taille
        try:
            while restant > 0 and not g.server.hebergement.fermeture.is_set():
                bloc = min(restant, 64 * 1024)
                g.wfile.write(b"x" * bloc)
                restant -= bloc
            g.wfile.flush()
            fin = time.monotonic() + puis_goutte
            while time.monotonic() < fin and not g.server.hebergement.fermeture.is_set():
                g.wfile.write(b"x")
                g.wfile.flush()
                time.sleep(0.5)
        except OSError:
            pass
    return comportement


def tronque(annonce, envoye):
    """Annonce `annonce` octets, en envoie `envoye`, puis ferme."""
    def comportement(g):
        g.send_response(200)
        g.send_header("Content-Length", str(annonce))
        g.end_headers()
        g.wfile.write(b"y" * envoye)
    return comportement


def muet(duree=8):
    """Accepte la requête et ne répond jamais (pendant `duree` secondes)."""
    return lambda g: g.server.hebergement.attendre(duree)


def goutte_a_goutte(pause=0.2, nombre=100):
    """Un octet toutes les `pause` secondes, sans longueur annoncée."""
    def comportement(g):
        g.send_response(200)
        g.end_headers()
        g.wfile.flush()
        try:
            for _ in range(nombre):
                if g.server.hebergement.fermeture.is_set():
                    return
                g.wfile.write(b"z")
                g.wfile.flush()
                time.sleep(pause)
        except OSError:
            pass
    return comportement


class FauxHebergement(object):
    """Un hébergement HTTPS sur 127.0.0.1, en tâche de fond."""

    def __init__(self):
        dossier = pe.certificats()
        self.contexte = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.contexte.load_cert_chain(os.path.join(dossier, "certificat.pem"),
                                      os.path.join(dossier, "cle.pem"))
        self.routes = {}
        self.requetes = []
        self.verrou = threading.Lock()
        self.fermeture = threading.Event()
        self.serveur = _Serveur(self)
        self.port = self.serveur.server_address[1]
        self.fil = threading.Thread(target=self.serveur.serve_forever,
                                    kwargs={"poll_interval": 0.05}, daemon=True)
        self.fil.start()

    def adresse(self, chemin="/essai/stable.zip"):
        return "https://127.0.0.1:%d%s" % (self.port, chemin)

    def noter(self, gestionnaire):
        with self.verrou:
            self.requetes.append({
                "methode": gestionnaire.command, "chemin": gestionnaire.path,
                "entetes": list(gestionnaire.headers.items()),
                "longueur_du_corps": int(gestionnaire.headers.get("Content-Length") or 0)})

    def chemins(self):
        with self.verrou:
            return [r["chemin"] for r in self.requetes]

    def attendre(self, secondes):
        self.fermeture.wait(secondes)

    def publier(self, archive, chemin="/essai/stable.zip", suffixe_manifeste=".manifeste.json",
                suffixe_signature=".manifeste.sig"):
        """Sert le trio (archive, manifeste, signature) d'un paquet fabriqué."""
        for suffixe, source in (("", archive), (suffixe_manifeste, archive + suffixe_manifeste),
                                (suffixe_signature, archive + suffixe_signature)):
            with open(source, "rb") as f:
                self.routes[chemin + suffixe] = corps(f.read())

    def arreter(self):
        self.fermeture.set()
        self.serveur.shutdown()
        self.serveur.server_close()
        self.fil.join(10)


class FauxMandataire(object):
    """Un mandataire HTTP minimal : lit `CONNECT hôte:port`, répond 200 puis relaie
    les octets vers la cible. Note la ligne CONNECT reçue."""

    def __init__(self, refuser=False):
        self.refuser = refuser
        self.lignes = []
        self.verrou = threading.Lock()
        self.fermeture = threading.Event()
        self.ecoute = socket.socket()
        self.ecoute.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.ecoute.bind(("127.0.0.1", 0))
        self.ecoute.listen(5)
        self.ecoute.settimeout(0.1)
        self.port = self.ecoute.getsockname()[1]
        self.fil = threading.Thread(target=self._servir, daemon=True)
        self.fil.start()

    def adresse(self):
        return "http://127.0.0.1:%d" % self.port

    def _servir(self):
        while not self.fermeture.is_set():
            try:
                connexion, _ = self.ecoute.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            threading.Thread(target=self._relayer, args=(connexion,), daemon=True).start()

    def _relayer(self, client):
        client.settimeout(10)
        try:
            tampon = b""
            while b"\r\n\r\n" not in tampon:
                morceau = client.recv(4096)
                if not morceau:
                    return
                tampon += morceau
            premiere = tampon.split(b"\r\n", 1)[0].decode("ascii", "replace")
            with self.verrou:
                self.lignes.append(premiere)
            if self.refuser:
                client.sendall(b"HTTP/1.0 403 Forbidden\r\n\r\n")
                return
            _, cible, _ = premiere.split(" ", 2)
            hote, _, port = cible.rpartition(":")
            serveur = socket.create_connection((hote, int(port)), 10)
            client.sendall(b"HTTP/1.0 200 Connection established\r\n\r\n")
            reste = tampon.split(b"\r\n\r\n", 1)[1]
            if reste:
                serveur.sendall(reste)
            self._pomper(client, serveur)
        except (OSError, ValueError):
            pass
        finally:
            client.close()

    def _pomper(self, client, serveur):
        def sens(source, destination):
            try:
                while True:
                    morceau = source.recv(65536)
                    if not morceau:
                        break
                    destination.sendall(morceau)
            except OSError:
                pass
            finally:
                try:
                    destination.shutdown(socket.SHUT_WR)
                except OSError:
                    pass

        retour = threading.Thread(target=sens, args=(serveur, client), daemon=True)
        retour.start()
        sens(client, serveur)
        retour.join(10)
        serveur.close()

    def arreter(self):
        self.fermeture.set()
        self.ecoute.close()
        self.fil.join(5)
