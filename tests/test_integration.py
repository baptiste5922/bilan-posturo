"""Test de bout en bout : autorité, TLS, authentification et dépôt.

Recopie le projet dans un dossier temporaire, y fabrique une autorité et un
certificat, lance le serveur en sous-processus, puis l'interroge en HTTPS en
vérifiant la chaîne contre l'autorité produite. Rien n'est touché dans le
dossier du projet.

    python3 -m unittest discover -s tests
"""

import base64
import http.client
import importlib.util
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import unittest
import warnings

PROJET = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJET)

import serveur

UTILISATEUR = "cabinét"          # accentué : couvre la régression compare_digest
MOT_DE_PASSE = "motdepasse123"
PDF = b"%PDF-1.4\n1 0 obj\ncontenu\n%%EOF\n"


def port_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def cryptography_absente():
    """cryptography ne sert qu'à fabriquer les certificats, jamais au
    serveur : son absence fait sauter ce test, pas échouer la suite."""
    return importlib.util.find_spec("cryptography") is None


@unittest.skipIf(cryptography_absente(),
                 "cryptography requis pour fabriquer les certificats")
class ServeurEnMarche(unittest.TestCase):
    """Un serveur réel, démarré une fois pour toute la classe."""

    @classmethod
    def setUpClass(cls):
        cls.dossier = tempfile.mkdtemp(prefix="bilan-test-")
        for nom in ("serveur.py", "generer_autorite.py", "index.html",
                    "style.css", "script.js"):
            shutil.copy(os.path.join(PROJET, nom), cls.dossier)

        sortie = subprocess.run(
            [sys.executable, "generer_autorite.py", "127.0.0.1"],
            cwd=cls.dossier, capture_output=True, text=True)
        assert sortie.returncode == 0, sortie.stderr

        cls.port = port_libre()
        with open(os.path.join(cls.dossier, "config.json"), "w") as f:
            json.dump({"port": cls.port, "dossier_pdf": "bilans",
                       "utilisateur": UTILISATEUR,
                       "mot_de_passe": serveur.hacher(MOT_DE_PASSE),
                       "certificat": "certificat.pem",
                       "cle_privee": "cle.pem"}, f)

        cls.processus = subprocess.Popen(
            [sys.executable, "serveur.py"], cwd=cls.dossier,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        cls.contexte = ssl.create_default_context(
            cafile=os.path.join(cls.dossier, "autorite.crt"))

        # Attendre que le port réponde plutôt que de dormir un temps fixe.
        limite = time.monotonic() + 15
        while time.monotonic() < limite:
            if cls.processus.poll() is not None:
                raise AssertionError("le serveur s'est arrêté : "
                                     + cls.processus.stdout.read())
            try:
                with socket.create_connection(("127.0.0.1", cls.port), 0.2):
                    break
            except OSError:
                time.sleep(0.05)
        else:
            raise AssertionError("le serveur n'a pas démarré à temps")

    @classmethod
    def tearDownClass(cls):
        cls.processus.terminate()
        cls.processus.wait(timeout=10)
        cls.processus.stdout.close()
        shutil.rmtree(cls.dossier, ignore_errors=True)

    # --- outillage ---------------------------------------------------------

    def requete(self, methode, chemin, corps=None, entetes=None,
                utilisateur=UTILISATEUR, mot_de_passe=MOT_DE_PASSE):
        entetes = dict(entetes or {})
        if utilisateur is not None:
            jeton = base64.b64encode(
                "{}:{}".format(utilisateur, mot_de_passe).encode("utf-8"))
            entetes["Authorization"] = "Basic " + jeton.decode("ascii")

        connexion = http.client.HTTPSConnection(
            "127.0.0.1", self.port, context=self.contexte, timeout=10)
        try:
            connexion.request(methode, chemin, body=corps, headers=entetes)
            reponse = connexion.getresponse()
            return reponse.status, reponse.getheaders(), reponse.read()
        finally:
            connexion.close()

    def deposer(self, nom, contenu=PDF):
        entete = base64.b64encode(nom.encode("utf-8")).decode("ascii")
        return self.requete("POST", "/depot", contenu, {"X-Fichier": entete})

    @property
    def bilans(self):
        return os.path.join(self.dossier, "bilans")

    # --- TLS ---------------------------------------------------------------

    def test_certificat_valide_pour_l_autorite(self):
        # create_default_context vérifie la chaîne ET le nom : la connexion
        # n'aboutit que si le subjectAltName contient 127.0.0.1.
        statut, _, _ = self.requete("GET", "/")
        self.assertEqual(statut, 200)

    def test_tls_ancien_refuse(self):
        contexte = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        contexte.check_hostname = False
        contexte.verify_mode = ssl.CERT_NONE
        with warnings.catch_warnings():
            # TLSv1_1 est déprécié côté client ; c'est précisément ce qu'on
            # veut proposer au serveur pour le voir refuser.
            warnings.simplefilter("ignore", DeprecationWarning)
            contexte.maximum_version = ssl.TLSVersion.TLSv1_1
        with self.assertRaises(ssl.SSLError):
            with socket.create_connection(("127.0.0.1", self.port), 10) as brute:
                with contexte.wrap_socket(brute):
                    pass

    def test_alpn_annonce_http11(self):
        contexte = ssl.create_default_context(
            cafile=os.path.join(self.dossier, "autorite.crt"))
        contexte.set_alpn_protocols(["h2", "http/1.1"])
        with socket.create_connection(("127.0.0.1", self.port), 10) as brute:
            with contexte.wrap_socket(brute, server_hostname="127.0.0.1") as tls:
                # Le client propose h2 en premier ; le serveur ne parlant que
                # HTTP/1.1 doit le dire, sinon Chrome coupe sans un octet.
                self.assertEqual(tls.selected_alpn_protocol(), "http/1.1")

    # --- authentification --------------------------------------------------

    def test_sans_authentification(self):
        statut, entetes, _ = self.requete("GET", "/", utilisateur=None)
        self.assertEqual(statut, 401)
        self.assertIn("WWW-Authenticate", dict(entetes))

    def test_mauvais_mot_de_passe(self):
        statut, _, _ = self.requete("GET", "/", mot_de_passe="faux")
        self.assertEqual(statut, 401)

    def test_mauvais_utilisateur(self):
        statut, _, _ = self.requete("GET", "/", utilisateur="intrus")
        self.assertEqual(statut, 401)

    def test_identifiant_accentue_accepte(self):
        # Régression : compare_digest lève TypeError sur une str non-ASCII,
        # ce qui tuait le thread et fermait la connexion sans réponse.
        statut, _, _ = self.requete("GET", "/")
        self.assertEqual(statut, 200)

    # --- surface exposée ---------------------------------------------------

    def test_fichiers_sensibles_inatteignables(self):
        for chemin in ("/config.json", "/serveur.py", "/cle.pem",
                       "/autorite-cle.pem", "/journal.log"):
            for methode in ("GET", "HEAD"):
                with self.subTest(chemin=chemin, methode=methode):
                    statut, _, _ = self.requete(methode, chemin)
                    self.assertEqual(statut, 403)

    def test_ressources_du_formulaire_servies(self):
        for chemin in ("/", "/index.html", "/style.css", "/script.js"):
            with self.subTest(chemin=chemin):
                statut, _, _ = self.requete("GET", chemin)
                self.assertEqual(statut, 200)

    def test_entetes_de_securite(self):
        _, entetes, _ = self.requete("GET", "/")
        entetes = {c.lower(): v for c, v in entetes}
        self.assertEqual(entetes.get("x-content-type-options"), "nosniff")
        self.assertEqual(entetes.get("referrer-policy"), "no-referrer")
        self.assertEqual(entetes.get("cache-control"), "no-store")
        self.assertEqual(entetes.get("x-frame-options"), "DENY")

    # --- dépôt -------------------------------------------------------------

    def test_depot_nominal(self):
        statut, _, corps = self.deposer("Bilan Élodie Dupré.pdf")
        self.assertEqual(statut, 200)
        resultat = json.loads(corps)
        self.assertTrue(resultat["ok"])
        self.assertEqual(resultat["fichier"], "Bilan Elodie Dupre.pdf")
        with open(os.path.join(self.bilans, resultat["fichier"]), "rb") as f:
            self.assertEqual(f.read(), PDF)

    def test_depot_sans_authentification(self):
        statut, _, _ = self.requete("POST", "/depot", PDF, utilisateur=None)
        self.assertEqual(statut, 401)

    def test_non_pdf_refuse(self):
        statut, _, corps = self.deposer("faux.pdf", b"MZ\x90\x00 pas un pdf")
        self.assertEqual(statut, 400)
        self.assertIn("erreur", json.loads(corps))

    def test_traversee_reste_dans_le_dossier(self):
        statut, _, corps = self.deposer("../../../../tmp/evasion-test.pdf")
        self.assertEqual(statut, 200)
        self.assertEqual(json.loads(corps)["fichier"], "evasion-test.pdf")
        self.assertTrue(os.path.exists(
            os.path.join(self.bilans, "evasion-test.pdf")))
        self.assertFalse(os.path.exists("/tmp/evasion-test.pdf"))

    def test_collision_ne_perd_aucun_bilan(self):
        _, _, premier = self.deposer("collision.pdf")
        _, _, second = self.deposer("collision.pdf")
        self.assertEqual(json.loads(premier)["fichier"], "collision.pdf")
        self.assertEqual(json.loads(second)["fichier"], "collision-2.pdf")

    def test_aucun_fichier_partiel_dans_le_dossier(self):
        self.deposer("propre.pdf")
        self.assertEqual([f for f in os.listdir(self.bilans)
                          if f.endswith(".part")], [])

    def test_corps_vide_refuse(self):
        statut, _, _ = self.requete("POST", "/depot", b"")
        self.assertEqual(statut, 400)

    def test_route_inconnue(self):
        statut, _, _ = self.requete("POST", "/autre", PDF)
        self.assertEqual(statut, 404)


class RefusDeDemarrer(unittest.TestCase):

    def test_sans_certificat_le_serveur_refuse(self):
        # Le repli silencieux en HTTP ferait circuler données de santé et mot
        # de passe en clair sur le réseau du cabinet.
        dossier = tempfile.mkdtemp(prefix="bilan-test-")
        self.addCleanup(shutil.rmtree, dossier, ignore_errors=True)
        shutil.copy(os.path.join(PROJET, "serveur.py"), dossier)
        with open(os.path.join(dossier, "config.json"), "w") as f:
            json.dump({"port": port_libre(), "dossier_pdf": "bilans",
                       "utilisateur": "cabinet",
                       "mot_de_passe": serveur.hacher(MOT_DE_PASSE),
                       "certificat": "absent.pem",
                       "cle_privee": "absent-cle.pem"}, f)

        sortie = subprocess.run([sys.executable, "serveur.py"], cwd=dossier,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(sortie.returncode, 1)
        self.assertIn("Refus de démarrer", sortie.stdout)


if __name__ == "__main__":
    unittest.main()
