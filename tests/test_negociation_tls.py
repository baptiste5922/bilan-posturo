"""La négociation TLS a un délai, et se fait dans le fil de la connexion (C6-T8).

Avant la tâche, la socket d'écoute négociait TLS dans `accept()`, sur le fil de
`serve_forever()`, sans délai : une connexion TCP ouverte et muette suffisait à
figer tout le serveur, dépôts et `/sante` compris. La négociation a désormais
lieu dans `finish_request`, donc dans le fil de la connexion, bornée par
`DELAI_NEGOCIATION_TLS_SECONDES`.

  Unitaires    — `finish_request` sur une fausse requête : refus journalisés
                 sans adresse, jamais de gestionnaire sans canal chiffré ;
  Bac à sable  — un vrai serveur dont le délai est réglé à 2 s : une
                 connexion muette ou au compte-gouttes ne gêne personne et
                 est fermée au délai.

    python3 -m unittest tests.test_negociation_tls
    python3 -O -m unittest tests.test_negociation_tls

Bibliothèque standard seule. Pas d'`assert` nu : il s'évaporerait sous -O.
"""

import base64
import http.client
import os
import re
import shutil
import socket
import ssl
import sys
import threading
import time
import unittest
import unittest.mock

DOSSIER_TESTS = os.path.dirname(os.path.abspath(__file__))
PROJET = os.path.dirname(DOSSIER_TESTS)
sys.path.insert(0, os.path.join(PROJET, "serveur"))
sys.path.insert(0, DOSSIER_TESTS)

import serveur
from test_integration import (
    MOT_DE_PASSE, PDF, UTILISATEUR, chercher_adresse, cryptography_absente,
    demarrer_sandbox_court)

ANCRE_DELAI = b"DELAI_NEGOCIATION_TLS_SECONDES = 10\n"
DELAI_BAC = 2          # secondes : le délai du serveur du bac à sable
MARGE_HAUTE = 3        # secondes tolérées au-delà du délai (CI lente)
ADRESSE_TEST = "192.0.2.7"


# --------------------------------------------------------------------------
# Unitaires : finish_request sur une fausse requête
# --------------------------------------------------------------------------

class FausseRequete:
    """Une socket acceptée, réduite à ce que finish_request touche."""

    def __init__(self, erreur=None, version="TLSv1.3"):
        self.erreur = erreur
        self.version_rendue = version
        self.appels = []

    def settimeout(self, delai):
        self.appels.append(("settimeout", delai))

    def do_handshake(self):
        self.appels.append(("do_handshake",))
        if self.erreur is not None:
            raise self.erreur

    def version(self):
        self.appels.append(("version",))
        return self.version_rendue


class Gestionnaires:
    """Enregistre chaque instanciation du gestionnaire."""

    def __init__(self):
        self.instances = []

    def __call__(self, requete, adresse, serveur_):
        self.instances.append((requete, adresse, serveur_))


class FinishRequest(unittest.TestCase):

    def setUp(self):
        self.serveur = object.__new__(serveur.ServeurBilan)
        self.gestionnaires = Gestionnaires()
        self.serveur.RequestHandlerClass = self.gestionnaires
        patron = unittest.mock.patch.object(serveur, "journaliser")
        self.journal = patron.start()
        self.addCleanup(patron.stop)
        patron = unittest.mock.patch.object(serveur, "journaliser_technique")
        self.technique = patron.start()
        self.addCleanup(patron.stop)

    def finir(self, requete):
        self.serveur.finish_request(requete, (ADRESSE_TEST, 40123))

    def verifier_sans_adresse(self):
        for mock in (self.journal, self.technique):
            for appel in mock.call_args_list:
                self.assertNotIn(ADRESSE_TEST, repr(appel))
                self.assertNotIn("40123", repr(appel))

    def test_delai_de_negociation(self):
        self.assertEqual(serveur.DELAI_NEGOCIATION_TLS_SECONDES, 10)
        self.assertGreater(serveur.DELAI_NEGOCIATION_TLS_SECONDES, 0)
        self.assertLess(serveur.DELAI_NEGOCIATION_TLS_SECONDES,
                        serveur.INACTIVITE_CONNEXION_SECONDES)

    def test_get_request_retiree(self):
        # accept() ne négocie plus : une surcharge ne verrait jamais d'SSLError.
        self.assertNotIn("get_request", vars(serveur.ServeurBilan))

    def test_canal_negocie_cree_le_gestionnaire(self):
        # Le témoin des quatre refus ci-dessous : le chemin nominal passe.
        requete = FausseRequete()
        self.finir(requete)
        self.assertEqual(requete.appels[:2],
                         [("settimeout", serveur.DELAI_NEGOCIATION_TLS_SECONDES),
                          ("do_handshake",)])
        self.assertEqual(self.gestionnaires.instances,
                         [(requete, (ADRESSE_TEST, 40123), self.serveur)])
        self.journal.assert_not_called()
        self.technique.assert_not_called()

    def test_expiration_journalisee_sans_adresse(self):
        requete = FausseRequete(erreur=socket.timeout("timed out"))
        self.finir(requete)
        self.assertEqual(self.gestionnaires.instances, [])
        # Le délai est posé avant la négociation, sinon il ne borne rien.
        self.assertEqual(requete.appels[0],
                         ("settimeout", serveur.DELAI_NEGOCIATION_TLS_SECONDES))
        self.technique.assert_called_once_with("TLS_REFUSE", "raison=delai-depasse")
        self.assertEqual(self.journal.call_count, 1)
        ligne = self.journal.call_args[0][0]
        self.assertRegex(ligne, r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d "
                                r"TLS refusé : délai de négociation dépassé\n$")
        self.verifier_sans_adresse()

    def test_refus_ssl_lignes_inchangees(self):
        erreur = ssl.SSLError(1, "[SSL: WRONG_VERSION_NUMBER] version number")
        requete = FausseRequete(erreur=erreur)
        self.finir(requete)
        self.assertEqual(self.gestionnaires.instances, [])
        self.technique.assert_called_once_with(
            "TLS_REFUSE", "raison={}".format(erreur))
        self.assertEqual(self.journal.call_count, 1)
        ligne = self.journal.call_args[0][0]
        self.assertRegex(ligne, r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d TLS refusé : ")
        self.assertTrue(ligne.endswith("TLS refusé : {}\n".format(erreur)))
        self.verifier_sans_adresse()

    def test_autre_oserror_muette(self):
        requete = FausseRequete(erreur=ConnectionResetError("réinitialisée"))
        self.finir(requete)
        self.assertEqual(self.gestionnaires.instances, [])
        self.journal.assert_not_called()
        self.technique.assert_not_called()

    def test_canal_sans_version_ferme(self):
        # La négociation « réussit » mais aucun canal chiffré n'existe : le
        # gestionnaire ne doit jamais voir cette socket.
        requete = FausseRequete(version=None)
        self.finir(requete)
        self.assertEqual(self.gestionnaires.instances, [])
        self.assertIn(("version",), requete.appels)
        self.verifier_sans_adresse()


# --------------------------------------------------------------------------
# Bac à sable : un vrai serveur, délai réglé à DELAI_BAC
# --------------------------------------------------------------------------

def regler_delai(dossier):
    """Réécrit l'ancre du délai dans le serveur.py du bac. Levée si l'ancre
    n'est pas trouvée exactement une fois : un réglage silencieusement perdu
    ferait attendre 10 s à chaque test, ou pire, les ferait passer à vide."""
    chemin = os.path.join(dossier, "serveur", "serveur.py")
    with open(chemin, "rb") as f:
        source = f.read()
    if source.count(ANCRE_DELAI) != 1:
        raise AssertionError("ancre du délai trouvée {} fois".format(
            source.count(ANCRE_DELAI)))
    with open(chemin, "wb") as f:
        f.write(source.replace(
            ANCRE_DELAI,
            "DELAI_NEGOCIATION_TLS_SECONDES = {}\n".format(DELAI_BAC).encode("ascii")))


def lire(dossier, nom):
    chemin = os.path.join(dossier, nom)
    if not os.path.exists(chemin):
        return ""
    with open(chemin, encoding="utf-8") as f:
        return f.read()


@unittest.skipIf(cryptography_absente(),
                 "cryptography requis pour fabriquer les certificats")
class NegociationEnBac(unittest.TestCase):
    """Un serveur réel, démarré une fois pour la classe."""

    @classmethod
    def setUpClass(cls):
        cls.dossier, cls.port, cls.processus = demarrer_sandbox_court(
            avant_demarrage=regler_delai)
        # Le tube doit être vidé EN CONTINU : sous Windows son tampon est
        # petit, et un tube jamais lu fige toute requête qui journalise
        # (C7-T5). Le fil garde la sortie, à lire au débogage d'un échec.
        cls.sortie_serveur = []
        cls.lecteur = threading.Thread(
            target=lambda: cls.sortie_serveur.extend(
                iter(cls.processus.stdout.readline, "")),
            daemon=True)
        cls.lecteur.start()
        cls.contexte = ssl.create_default_context(
            cafile=os.path.join(cls.dossier, "autorite.crt"))

    @classmethod
    def tearDownClass(cls):
        cls.processus.terminate()
        cls.processus.wait(timeout=10)
        cls.lecteur.join(timeout=5)
        cls.processus.stdout.close()
        shutil.rmtree(cls.dossier, ignore_errors=True)

    # --- outillage ---------------------------------------------------------

    def ouvrir_brute(self):
        """Une connexion TCP nue, fermée à la fin du test."""
        brute = socket.create_connection(("127.0.0.1", self.port), 5)
        self.addCleanup(brute.close)
        return brute

    def requete(self, methode, chemin, corps=None, entetes=None):
        jeton = base64.b64encode(
            "{}:{}".format(UTILISATEUR, MOT_DE_PASSE).encode("utf-8"))
        entetes = dict(entetes or {})
        entetes["Authorization"] = "Basic " + jeton.decode("ascii")
        connexion = http.client.HTTPSConnection(
            "127.0.0.1", self.port, context=self.contexte, timeout=5)
        try:
            connexion.request(methode, chemin, body=corps, headers=entetes)
            reponse = connexion.getresponse()
            return reponse.status, reponse.read()
        finally:
            connexion.close()

    def lignes_technique(self, evenement):
        """Les lignes du journal technique dont le second mot est exactement
        `evenement` : jamais une sous-chaîne (DEMARRAGE préfixe DEMARRAGE_REFUSE)."""
        return [ligne for ligne in lire(self.dossier, "technique.log").splitlines()
                if ligne.split(" ", 2)[1:2] == [evenement]]

    def attendre_nouvelle_ligne(self, evenement, detail, avant, limite=10):
        """Attend qu'une ligne `evenement detail` exacte s'ajoute aux `avant`
        déjà comptées. Le serveur l'écrit depuis le fil de la connexion : elle
        n'est plus là au retour du client."""
        fin = time.monotonic() + limite
        while time.monotonic() < fin:
            lignes = [l for l in self.lignes_technique(evenement)
                      if l.split(" ", 2)[2:3] == [detail]]
            if len(lignes) > avant:
                return lignes[-1]
            time.sleep(0.02)
        self.fail("aucune nouvelle ligne « {} {} » dans technique.log après {} s"
                  .format(evenement, detail, limite))

    def compter(self, evenement, detail):
        return len([l for l in self.lignes_technique(evenement)
                    if l.split(" ", 2)[2:3] == [detail]])

    def attendre_fin_de_connexion(self, brute, depart):
        """Attend que le serveur ferme `brute` ; rend la durée écoulée depuis
        `depart`. Un EOF et une réinitialisation valent fermeture ; l'absence
        de toute réaction avant MARGE_HAUTE secondes de plus que le délai est
        l'échec que la tâche corrige."""
        brute.settimeout(DELAI_BAC + MARGE_HAUTE)
        try:
            brute.recv(1024)
        except (ConnectionResetError, ConnectionAbortedError):
            pass
        except socket.timeout:
            self.fail("la connexion n'a pas été fermée en {} s".format(
                DELAI_BAC + MARGE_HAUTE))
        return time.monotonic() - depart

    # --- A1, A8 : plus de gel ----------------------------------------------

    def test_connexion_muette_ne_bloque_ni_depot_ni_sante(self):
        journal_avant = lire(self.dossier, "journal.log")
        technique_avant = lire(self.dossier, "technique.log")
        self.ouvrir_brute()          # ouverte, muette, tenue pendant tout le test
        time.sleep(0.3)              # laisse le serveur l'accepter

        entete = base64.b64encode(b"Bilan_muette.pdf").decode("ascii")
        statut, _ = self.requete("POST", "/depot", PDF, {"X-Fichier": entete})
        self.assertEqual(statut, 200)
        self.assertTrue(os.path.isfile(
            os.path.join(self.dossier, "bilans", "Bilan_muette.pdf")))

        statut, corps = self.requete("GET", "/sante")
        self.assertEqual(statut, 200)
        self.assertEqual(corps.replace(b" ", b""), b'{"etat":"ok"}')

        # /sante reste muette dans les deux journaux, comme sans connexion
        # muette (A8) : on regarde ce qui s'est ajouté depuis le début.
        for nom, avant in (("journal.log", journal_avant),
                           ("technique.log", technique_avant)):
            nouveau = lire(self.dossier, nom)[len(avant):]
            self.assertNotIn("sante", nouveau)

    # --- A2, A3 : fermeture au délai ---------------------------------------

    def test_connexion_muette_fermee_au_delai(self):
        avant = self.compter("TLS_REFUSE", "raison=delai-depasse")
        journal_avant = lire(self.dossier, "journal.log")
        depart = time.monotonic()
        brute = self.ouvrir_brute()
        duree = self.attendre_fin_de_connexion(brute, depart)
        self.assertGreaterEqual(duree, 0.8 * DELAI_BAC)
        self.assertLessEqual(duree, DELAI_BAC + MARGE_HAUTE)

        ligne = self.attendre_nouvelle_ligne(
            "TLS_REFUSE", "raison=delai-depasse", avant)
        # Second mot exactement TLS_REFUSE, reste exactement raison=...
        self.assertEqual(ligne.split(" ", 2)[1:], ["TLS_REFUSE", "raison=delai-depasse"])
        technique = lire(self.dossier, "technique.log")
        self.assertIsNone(chercher_adresse(technique))

        nouveau = lire(self.dossier, "journal.log")[len(journal_avant):]
        self.assertIn("TLS refusé : délai de négociation dépassé", nouveau)

    def test_goutte_a_goutte_ferme_au_delai(self):
        # Un octet toutes les 0,4 s ne prolonge pas l'échéance : c'est une
        # échéance totale, pas un délai par lecture. L'en-tête d'enregistrement
        # annonce 16 384 octets : le serveur attend la suite sans jamais
        # pouvoir juger le message, donc sans refus anticipé.
        brute = self.ouvrir_brute()
        depart = time.monotonic()
        brute.sendall(b"\x16\x03\x01\x40\x00")
        brute.settimeout(0.4)
        fermee = False
        while time.monotonic() - depart < DELAI_BAC + MARGE_HAUTE:
            try:
                if brute.recv(1024) == b"":
                    fermee = True
                    break
            except socket.timeout:
                pass
            except (ConnectionResetError, ConnectionAbortedError):
                fermee = True
                break
            try:
                brute.sendall(b"\x00")
            except OSError:
                fermee = True
                break
        duree = time.monotonic() - depart
        self.assertTrue(fermee, "jamais fermée en {} s".format(DELAI_BAC + MARGE_HAUTE))
        self.assertGreaterEqual(duree, 0.8 * DELAI_BAC)
        self.assertLessEqual(duree, DELAI_BAC + MARGE_HAUTE)

    # --- A4 : aucun repli en clair -----------------------------------------

    def test_requete_en_clair_refusee(self):
        avant = len(self.lignes_technique("TLS_REFUSE"))
        brute = self.ouvrir_brute()
        brute.sendall(b"GET /sante HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
        brute.settimeout(DELAI_BAC + MARGE_HAUTE)
        recu = b""
        try:
            while True:
                morceau = brute.recv(4096)
                if not morceau:
                    break
                recu += morceau
        except (ConnectionResetError, ConnectionAbortedError):
            pass
        except socket.timeout:
            self.fail("la requête en clair n'a pas été refusée à temps")
        self.assertFalse(recu.startswith(b"HTTP/"), recu[:80])
        self.assertNotIn(b"etat", recu)

        fin = time.monotonic() + 10
        while time.monotonic() < fin:
            lignes = self.lignes_technique("TLS_REFUSE")
            if len(lignes) > avant:
                break
            time.sleep(0.02)
        else:
            self.fail("aucune ligne TLS_REFUSE après la requête en clair")
        self.assertTrue(any(l.split(" ", 2)[2].startswith("raison=")
                            for l in lignes[avant:]))

    # --- A5 : ALPN ----------------------------------------------------------

    def test_alpn_http11(self):
        contexte = ssl.create_default_context(
            cafile=os.path.join(self.dossier, "autorite.crt"))
        contexte.set_alpn_protocols(["h2", "http/1.1"])
        brute = self.ouvrir_brute()
        with contexte.wrap_socket(brute, server_hostname="127.0.0.1") as tls:
            self.assertEqual(tls.selected_alpn_protocol(), "http/1.1")


if __name__ == "__main__":
    unittest.main()
