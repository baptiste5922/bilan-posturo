"""Le client HTTPS du client de mise à jour (C5-T2b) contre un faux hébergement local.

Un vrai serveur TLS sur 127.0.0.1 (certificat du bac à sable), qui note tout ce
qu'il reçoit : on éprouve ce que `maj._telecharger` ENVOIE (trois requêtes, GET,
quatre en-têtes), ce qu'il REFUSE (TLS invalide, redirection vers http, corps trop
grand, hôte muet) et le temps qu'il y met (un délai total réellement borné).

Les délais passent en paramètre, réduits ; les constantes de production sont lues
par `tests/test_maj.py`. Exige `cryptography` pour les certificats : sauté sous le
Python 3.9.6 du Mac, exécuté en intégration continue sur les trois systèmes.

    python3 -m unittest tests.test_maj_reseau -v
"""

import contextlib
import datetime
import gc
import io
import os
import socket
import ssl
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock
import warnings

DOSSIER_TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DOSSIER_TESTS)
sys.path.insert(0, os.path.join(DOSSIER_TESTS, "outils"))

import faux_hebergement as faux  # noqa: E402
import maj  # noqa: E402
import paquet_essai as pe  # noqa: E402
import paquet_signe  # noqa: E402
import test_maj  # noqa: E402
from test_integration import cryptography_absente  # noqa: E402

SANS_CRYPTOGRAPHY = "cryptography requis pour fabriquer les certificats du bac à sable"


@unittest.skipIf(cryptography_absente(), SANS_CRYPTOGRAPHY)
class Hebergement(unittest.TestCase):
    """Un faux hébergement, un contexte qui lui fait confiance, un dossier de réception."""

    def setUp(self):
        self.heb = faux.FauxHebergement()
        self.addCleanup(self.heb.arreter)
        self.contexte = faux.contexte_client()
        self.dossier = tempfile.mkdtemp(prefix="bilan-maj-reseau-")
        self.addCleanup(self._effacer_dossier)
        self.destination = os.path.join(self.dossier, "recu")

    def _effacer_dossier(self):
        import shutil
        shutil.rmtree(self.dossier, ignore_errors=True)

    def telecharger(self, chemin="/essai/stable.zip", limite=1000000, total=10, **options):
        options.setdefault("contexte", self.contexte)
        return maj._telecharger(self.heb.adresse(chemin), self.destination, limite, total,
                                **options)

    def echec(self, code, chemin="/essai/stable.zip", **options):
        """Le téléchargement échoue avec ce code, ne laisse rien et ne dit pas où il
        allait. Rend (Refus, durée)."""
        debut = time.monotonic()
        with self.assertRaises(maj.Refus) as contexte:
            self.telecharger(chemin, **options)
        duree = time.monotonic() - debut
        self.assertEqual(contexte.exception.code, code, contexte.exception.detail)
        self.assertFalse(os.path.lexists(self.destination), "un fichier partiel est resté")
        for texte in (contexte.exception.detail, str(contexte.exception)):
            self.assertNotIn("/essai", texte)
            self.assertNotIn("stable", texte)
        return contexte.exception, duree

    def lu(self):
        with open(self.destination, "rb") as f:
            return f.read()


# ==============================================================================
# B1 — ce qui est envoyé
# ==============================================================================

class DonneesEnvoyees(Hebergement):

    def test_une_requete_get_de_quatre_en_tetes_et_rien_d_autre(self):
        self.heb.routes["/essai/stable.zip"] = faux.corps(b"contenu")
        self.assertEqual(self.telecharger(), 7)
        self.assertEqual(self.lu(), b"contenu")
        self.assertEqual(len(self.heb.requetes), 1)
        requete = self.heb.requetes[0]
        self.assertEqual(requete["methode"], "GET")
        self.assertEqual(requete["chemin"], "/essai/stable.zip")
        self.assertEqual(requete["longueur_du_corps"], 0)
        noms = [nom for nom, _ in requete["entetes"]]
        self.assertEqual(sorted(noms), ["Accept-Encoding", "Connection", "Host", "User-Agent"])
        valeurs = dict(requete["entetes"])
        self.assertEqual(valeurs["User-Agent"], "bilan-posturo")
        self.assertEqual(valeurs["Accept-Encoding"], "identity")
        self.assertEqual(valeurs["Connection"], "close")
        self.assertEqual(valeurs["Host"], "127.0.0.1:%d" % self.heb.port)

    def test_aucune_version_aucun_identifiant_aucun_cookie(self):
        self.heb.routes["/essai/stable.zip"] = faux.corps(b"x")
        self.telecharger()
        brut = repr(self.heb.requetes[0]["entetes"]).lower()
        for interdit in ("version", "authorization", "cookie", "x-", "referer", "client",
                         "cabinet", serveur_version()):
            self.assertNotIn(interdit, brut)

    def test_les_en_tetes_sont_ceux_de_la_constante(self):
        self.assertEqual(maj.ENTETES_DE_REQUETE, {
            "User-Agent": "bilan-posturo", "Accept-Encoding": "identity",
            "Connection": "close"})

    def test_le_fichier_recu_est_ecrit_en_0600(self):
        self.heb.routes["/essai/stable.zip"] = faux.corps(b"x")
        self.telecharger()
        if os.name != "nt":
            self.assertEqual(os.stat(self.destination).st_mode & 0o777, 0o600)

    def test_un_fichier_deja_present_n_est_jamais_efface_ni_ecrase(self):
        self.heb.routes["/essai/stable.zip"] = faux.corps(b"neuf")
        with open(self.destination, "wb") as f:
            f.write(b"ancien")
        with self.assertRaises(maj.Refus) as contexte:
            self.telecharger()
        self.assertEqual(contexte.exception.code, "ECRITURE_IMPOSSIBLE")
        self.assertEqual(self.lu(), b"ancien")

    def test_un_corps_vide_est_un_fichier_vide(self):
        self.heb.routes["/essai/stable.zip"] = faux.corps(b"")
        self.assertEqual(self.telecharger(), 0)
        self.assertEqual(self.lu(), b"")

    def test_un_corps_de_plusieurs_blocs(self):
        corps = os.urandom(300 * 1024)
        self.heb.routes["/essai/stable.zip"] = faux.corps(corps)
        self.assertEqual(self.telecharger(limite=len(corps)), len(corps))
        self.assertEqual(self.lu(), corps)

    def test_la_limite_est_atteinte_pas_depassee(self):
        self.heb.routes["/essai/stable.zip"] = faux.corps(b"1234567890")
        self.assertEqual(self.telecharger(limite=10), 10)
        os.remove(self.destination)
        self.echec("REPONSE_TROP_GRANDE", limite=9)


def serveur_version():
    """Le numéro de version du produit : il ne doit jamais partir sur le réseau."""
    import json
    with open(os.path.join(os.path.dirname(DOSSIER_TESTS), "formulaire", "version.json")) as f:
        return json.load(f)["version"]


# ==============================================================================
# B3 — TLS
# ==============================================================================

@unittest.skipIf(cryptography_absente(), SANS_CRYPTOGRAPHY)
class Tls(Hebergement):

    def test_le_contexte_par_defaut_exige_la_verification(self):
        contexte = maj.contexte_tls_par_defaut()
        self.assertEqual(contexte.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(contexte.check_hostname)
        self.assertGreaterEqual(contexte.minimum_version, ssl.TLSVersion.TLSv1_2)

    def test_le_contexte_par_defaut_refuse_un_certificat_d_autorite_inconnue(self):
        self.heb.routes["/essai/stable.zip"] = faux.corps(b"x")
        # Sans `contexte=` : le magasin du système, qui ne connaît pas l'autorité du bac.
        exception, _ = self.echec("TLS_INVALIDE", contexte=None)
        self.assertEqual(self.heb.requetes, [], "aucune requête ne doit partir avant la vérification")
        self.assertIn("127.0.0.1", exception.detail)

    def test_un_contexte_qui_fait_confiance_reussit(self):
        self.heb.routes["/essai/stable.zip"] = faux.corps(b"x")
        self.assertEqual(self.telecharger(), 1)

    def test_un_serveur_qui_ne_parle_pas_tls(self):
        # Un hébergeur mal configuré (http en clair sur le port) : TLS_INVALIDE, et
        # jamais un repli en clair.
        ecoute = socket.socket()
        ecoute.bind(("127.0.0.1", 0))
        ecoute.listen(1)
        self.addCleanup(ecoute.close)
        port = ecoute.getsockname()[1]
        arret = threading.Event()

        def servir():
            ecoute.settimeout(0.1)
            while not arret.is_set():
                try:
                    connexion, _ = ecoute.accept()
                except OSError:
                    continue
                with contextlib.suppress(OSError):
                    connexion.settimeout(2)
                    connexion.recv(1024)
                    connexion.sendall(b"HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\nok")
                connexion.close()

        fil = threading.Thread(target=servir, daemon=True)
        fil.start()
        self.addCleanup(fil.join, 5)
        self.addCleanup(arret.set)
        with self.assertRaises(maj.Refus) as contexte:
            maj._telecharger("https://127.0.0.1:%d/essai/stable.zip" % port,
                             self.destination, 1000, 10, contexte=self.contexte)
        self.assertEqual(contexte.exception.code, "TLS_INVALIDE")
        self.assertFalse(os.path.lexists(self.destination))

    def test_aucune_adresse_en_clair_n_est_acceptee(self):
        for adresse in ("http://127.0.0.1:%d/essai/stable.zip" % self.heb.port,
                        "ftp://127.0.0.1/x", "file:///etc/passwd", "127.0.0.1/x"):
            with self.subTest(adresse=adresse):
                with self.assertRaises(maj.Refus) as contexte:
                    maj._telecharger(adresse, self.destination, 100, 5, contexte=self.contexte)
                self.assertEqual(contexte.exception.code, "ADRESSE_INVALIDE")
        self.assertEqual(self.heb.requetes, [])


# ==============================================================================
# B4 — redirections
# ==============================================================================

@unittest.skipIf(cryptography_absente(), SANS_CRYPTOGRAPHY)
class Redirections(Hebergement):

    def chaine(self, longueur, statut=302):
        """/r0 → /r1 → … → /r<longueur> qui sert le corps : `longueur` redirections."""
        for i in range(longueur):
            self.heb.routes["/essai/r%d" % i] = faux.redirection(
                self.heb.adresse("/essai/r%d" % (i + 1)), statut)
        self.heb.routes["/essai/r%d" % longueur] = faux.corps(b"arrivee")

    def test_cinq_redirections_reussissent(self):
        self.chaine(5)
        self.assertEqual(self.telecharger("/essai/r0"), 7)
        self.assertEqual(self.lu(), b"arrivee")
        self.assertEqual(len(self.heb.requetes), 6)

    def test_six_redirections_sont_refusees(self):
        self.chaine(6)
        self.echec("REDIRECTION_REFUSEE", "/essai/r0")
        # La sixième est refusée sans que la septième requête parte.
        self.assertEqual(len(self.heb.requetes), 6)

    def test_chaque_statut_de_redirection_est_suivi(self):
        for code in (301, 302, 303, 307, 308):
            with self.subTest(code=code):
                self.heb.requetes.clear()
                self.heb.routes.clear()
                self.chaine(1, statut=code)
                self.assertEqual(self.telecharger("/essai/r0"), 7)
                os.remove(self.destination)

    def test_une_redirection_vers_http_est_refusee(self):
        self.heb.routes["/essai/a"] = faux.redirection(
            "http://127.0.0.1:%d/essai/b" % self.heb.port)
        self.echec("REDIRECTION_REFUSEE", "/essai/a")
        self.assertEqual(len(self.heb.requetes), 1)

    def test_une_redirection_vers_file_est_refusee(self):
        self.heb.routes["/essai/a"] = faux.redirection("file:///etc/passwd")
        self.echec("REDIRECTION_REFUSEE", "/essai/a")

    def test_une_redirection_portant_un_identifiant_est_refusee(self):
        self.heb.routes["/essai/a"] = faux.redirection(
            "https://utilisateur@127.0.0.1:%d/essai/b" % self.heb.port)
        self.echec("REDIRECTION_REFUSEE", "/essai/a")

    def test_une_redirection_avec_requete_ou_fragment_est_refusee(self):
        for cible in ("/essai/b?jeton=1", "/essai/b#x"):
            with self.subTest(cible=cible):
                self.heb.routes["/essai/a"] = faux.redirection(cible)
                self.echec("REDIRECTION_REFUSEE", "/essai/a")

    def test_une_redirection_sans_location_est_refusee(self):
        self.heb.routes["/essai/a"] = lambda g: faux.envoyer(g, b"", 302)
        self.echec("REDIRECTION_REFUSEE", "/essai/a")

    def test_une_location_relative_est_suivie(self):
        self.heb.routes["/essai/a"] = faux.redirection("/essai/b")
        self.heb.routes["/essai/b"] = faux.corps(b"relatif")
        self.assertEqual(self.telecharger("/essai/a"), 7)
        self.heb.routes["/essai/c"] = faux.redirection("b")
        os.remove(self.destination)
        self.assertEqual(self.telecharger("/essai/c"), 7)

    def test_une_location_a_chemin_relatif_se_resout_sur_l_url_courante(self):
        self.heb.routes["/essai/dossier/a"] = faux.redirection("../b")
        self.heb.routes["/essai/b"] = faux.corps(b"remonte")
        self.assertEqual(self.telecharger("/essai/dossier/a"), 7)

    def test_une_redirection_n_envoie_rien_de_plus_que_la_premiere(self):
        self.chaine(2)
        self.telecharger("/essai/r0")
        for requete in self.heb.requetes:
            self.assertEqual(sorted(n for n, _ in requete["entetes"]),
                             ["Accept-Encoding", "Connection", "Host", "User-Agent"])
            self.assertEqual(requete["methode"], "GET")

    def test_une_redirection_ne_donne_pas_un_statut_3xx_inconnu(self):
        # 300 et 304 ne sont pas des redirections que l'on suit.
        for code in (300, 304, 305):
            with self.subTest(code=code):
                self.heb.routes["/essai/a"] = lambda g, c=code: faux.envoyer(
                    g, b"", c, entetes=(("Location", g.server.hebergement.adresse("/essai/b")),))
                self.echec("HTTP_STATUT", "/essai/a")


# ==============================================================================
# B5 — tailles et délais
# ==============================================================================

@unittest.skipIf(cryptography_absente(), SANS_CRYPTOGRAPHY)
class TaillesEtDelais(Hebergement):

    def test_une_taille_annoncee_trop_grande_est_refusee_sans_lire_le_corps(self):
        self.heb.routes["/essai/stable.zip"] = faux.sans_corps_annonce(10 ** 9)
        _, duree = self.echec("REPONSE_TROP_GRANDE", limite=1000, total=30)
        self.assertLess(duree, 1.0, "le client a attendu un corps qui ne vient pas")

    def test_un_corps_sans_longueur_au_dela_de_la_limite(self):
        # 300 000 octets, puis un octet toutes les demi-secondes SANS fermer : un
        # client qui lit « jusqu'à la fin » reste suspendu vingt secondes.
        self.heb.routes["/essai/stable.zip"] = faux.corps_sans_longueur(300000)
        _, duree = self.echec("REPONSE_TROP_GRANDE", limite=100000, total=30)
        self.assertLess(duree, 3, "le client a lu au-delà de sa limite")

    def test_un_hote_muet_depasse_le_delai_d_operation(self):
        self.heb.routes["/essai/stable.zip"] = faux.muet(10)
        _, duree = self.echec("DELAI_DEPASSE", delai_operation=1, total=30)
        self.assertLess(duree, 3)
        self.assertGreater(duree, 0.5)

    def test_un_octet_toutes_les_deux_dixiemes_depasse_le_delai_total(self):
        # Chaque réception arrive dans le délai d'opération : sans échéance totale,
        # ce téléchargement durerait vingt secondes (cent octets).
        self.heb.routes["/essai/stable.zip"] = faux.goutte_a_goutte(0.2, 100)
        _, duree = self.echec("DELAI_DEPASSE", total=2, delai_operation=5)
        self.assertLess(duree, 4)
        self.assertGreater(duree, 1.5)

    def test_le_delai_total_court_aussi_avant_la_reponse(self):
        self.heb.routes["/essai/stable.zip"] = faux.muet(10)
        _, duree = self.echec("DELAI_DEPASSE", total=1, delai_operation=30)
        self.assertLess(duree, 3)

    def test_un_port_ferme(self):
        ecoute = socket.socket()
        ecoute.bind(("127.0.0.1", 0))
        port = ecoute.getsockname()[1]
        ecoute.close()
        with self.assertRaises(maj.Refus) as contexte:
            maj._telecharger("https://127.0.0.1:%d/essai/stable.zip" % port,
                             self.destination, 1000, 5, contexte=self.contexte)
        self.assertEqual(contexte.exception.code, "RESEAU_INJOIGNABLE")
        self.assertNotIn("/essai", contexte.exception.detail)

    def test_un_hote_qui_n_existe_pas(self):
        with self.assertRaises(maj.Refus) as contexte:
            maj._telecharger("https://hote-qui-n-existe-pas.invalid/essai/stable.zip",
                             self.destination, 1000, 10, contexte=self.contexte)
        self.assertEqual(contexte.exception.code, "RESEAU_INJOIGNABLE")
        self.assertNotIn("/essai", contexte.exception.detail)

    def test_un_statut_autre_que_200(self):
        for code in (400, 401, 403, 404, 410, 500, 503):
            with self.subTest(code=code):
                self.heb.routes["/essai/stable.zip"] = faux.statut(code)
                exception, _ = self.echec("HTTP_STATUT")
                self.assertIn(str(code), exception.detail)

    def test_une_reponse_tronquee(self):
        self.heb.routes["/essai/stable.zip"] = faux.tronque(1000, 10)
        self.echec("RESEAU_INJOIGNABLE")

    def test_une_longueur_annoncee_illisible(self):
        def comportement(g):
            g.send_response(200)
            g.send_header("Content-Length", "beaucoup")
            g.end_headers()
            g.wfile.write(b"x")

        self.heb.routes["/essai/stable.zip"] = comportement
        self.echec("RESEAU_INJOIGNABLE")

    def test_aucun_fichier_partiel_apres_un_depassement_du_delai(self):
        self.heb.routes["/essai/stable.zip"] = faux.goutte_a_goutte(0.2, 100)
        self.echec("DELAI_DEPASSE", total=1, delai_operation=5)
        self.assertEqual(os.listdir(self.dossier), [])

    def test_les_constantes_de_production(self):
        # Lues, pas supposées : le budget d'un passage (tests.test_maj) en dépend.
        self.assertEqual(maj.DELAI_OPERATION_RESEAU_SECONDES, 30)
        self.assertEqual(maj.DELAI_TOTAL_MANIFESTE_SECONDES, 60)
        self.assertEqual(maj.DELAI_TOTAL_ARCHIVE_SECONDES, 900)
        self.assertEqual(maj.TAILLE_MAX_ARCHIVE, 64 * 1024 * 1024)
        self.assertEqual(maj.FREQUENCE_CONTROLE_SECONDES, 21600)
        self.assertEqual(maj.REDIRECTIONS_MAX, 5)


# ==============================================================================
# B6 — le proxy ne vient que de la configuration
# ==============================================================================

@unittest.skipIf(cryptography_absente(), SANS_CRYPTOGRAPHY)
class Proxy(Hebergement):

    def fermer_un_port(self):
        ecoute = socket.socket()
        ecoute.bind(("127.0.0.1", 0))
        port = ecoute.getsockname()[1]
        ecoute.close()
        return port

    def test_l_environnement_n_est_jamais_lu(self):
        mort = "http://127.0.0.1:%d" % self.fermer_un_port()
        self.heb.routes["/essai/stable.zip"] = faux.corps(b"direct")
        environnement = dict((n, mort) for n in (
            "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"))
        with unittest.mock.patch.dict(os.environ, environnement):
            self.assertEqual(self.telecharger(proxy=""), 6)
        self.assertEqual(self.lu(), b"direct")

    def test_le_proxy_configure_recoit_un_connect_vers_la_cible(self):
        mandataire = faux.FauxMandataire()
        self.addCleanup(mandataire.arreter)
        self.heb.routes["/essai/stable.zip"] = faux.corps(b"par le tunnel")
        self.assertEqual(self.telecharger(proxy=mandataire.adresse()), 13)
        self.assertEqual(self.lu(), b"par le tunnel")
        self.assertEqual(len(mandataire.lignes), 1)
        self.assertTrue(mandataire.lignes[0].startswith("CONNECT 127.0.0.1:%d " % self.heb.port),
                        mandataire.lignes)
        # Le nom vérifié par TLS est celui de la CIBLE : la requête qui traverse porte
        # son Host, jamais celui du mandataire.
        self.assertEqual(dict(self.heb.requetes[0]["entetes"])["Host"],
                         "127.0.0.1:%d" % self.heb.port)

    def test_un_proxy_qui_refuse_le_tunnel(self):
        mandataire = faux.FauxMandataire(refuser=True)
        self.addCleanup(mandataire.arreter)
        self.heb.routes["/essai/stable.zip"] = faux.corps(b"x")
        # http.client (3.9 au moins) laisse la réponse du CONNECT refusé sans la
        # fermer : sa socket est libérée au ramasse-miettes avec un ResourceWarning
        # qui n'est pas du client. On la fait tomber ici, sous un filtre, plutôt que
        # dans le test d'un autre fichier.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            self.echec("RESEAU_INJOIGNABLE", proxy=mandataire.adresse())
            gc.collect()
        self.assertEqual(self.heb.requetes, [])

    def test_un_proxy_mort_n_est_pas_contourne(self):
        # Pas de repli en direct : un proxy configuré qui ne répond pas est un échec.
        self.heb.routes["/essai/stable.zip"] = faux.corps(b"x")
        self.echec("RESEAU_INJOIGNABLE", proxy="http://127.0.0.1:%d" % self.fermer_un_port())
        self.assertEqual(self.heb.requetes, [])

    def test_un_proxy_mal_forme_est_refuse_avant_toute_connexion(self):
        self.heb.routes["/essai/stable.zip"] = faux.corps(b"x")
        for proxy in ("https://127.0.0.1:3128", "127.0.0.1", "http://127.0.0.1"):
            with self.subTest(proxy=proxy):
                with self.assertRaises(ValueError):
                    maj.analyser_proxy(proxy)
        self.assertEqual(self.heb.requetes, [])


# ==============================================================================
# B2, B1 — le manifeste est jugé avant que l'archive soit demandée
# ==============================================================================

@unittest.skipIf(cryptography_absente(), SANS_CRYPTOGRAPHY)
class Entete(test_maj.Installation):
    """`maj.verifier` contre un vrai hébergement HTTPS : ce qu'il demande, dans quel
    ordre, et ce qu'il ne demande jamais."""

    def setUp(self):
        test_maj.Installation.setUp(self)
        self.heb = faux.FauxHebergement()
        self.addCleanup(self.heb.arreter)
        self.contexte = faux.contexte_client()
        self.patch(maj, "attendre_sante", lambda *a, **k: True)
        self.ecrire_config(mise_a_jour={
            "client": "cabinet-01", "adresse": self.heb.adresse(), "au_demarrage": False})
        self.addCleanup(self.aucune_adresse_dans_les_journaux)

    def aucune_adresse_dans_les_journaux(self):
        """B21 : le chemin de l'adresse n'est dans aucun des deux journaux ; seul
        l'hôte (127.0.0.1 ici) peut figurer dans journal.log."""
        for nom in ("technique.log", "journal.log"):
            chemin = os.path.join(self.racine, nom)
            if not os.path.exists(chemin):
                continue
            with open(chemin, encoding="utf-8") as f:
                texte = f.read()
            for interdit in ("/essai/", "stable.zip"):
                if interdit in texte:
                    raise AssertionError("%s porte une partie de l'adresse de publication" % nom)
            if nom == "technique.log" and "127.0.0.1" in texte:
                raise AssertionError("technique.log porte un hôte")

    def passer(self, maintenant=datetime.datetime(2026, 11, 16, 12, 0, 0)):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return maj.verifier(
                self.racine, self.pilote, maintenant=maintenant,
                depuis_demarrage=lambda: 100000, contexte=self.contexte,
                delais={"sante": 1, "auto_controle": 5, "reponse": 1, "arret": 1,
                        "operation": 5, "manifeste": 10, "archive": 20})

    CHEMIN = "/essai/stable.zip"

    def sans_archive(self):
        self.assertEqual(self.heb.chemins(), [
            self.CHEMIN + paquet_signe.SUFFIXE_MANIFESTE,
            self.CHEMIN + paquet_signe.SUFFIXE_SIGNATURE])

    def test_signature_invalide(self):
        self.heb.publier(self.trio("1.2.0", graine=pe.GRAINE_B))
        self.assertEqual(self.passer(), 1)
        self.assertIn("MAJ_REFUSEE code=SIGNATURE_INVALIDE", self.technique())
        self.sans_archive()

    def test_version_non_superieure(self):
        self.heb.publier(self.trio("1.1.0"))
        self.assertEqual(self.passer(), 0)
        self.assertIn("MAJ_CONTROLE resultat=a-jour de=1.1.0", self.technique())
        self.sans_archive()

    def test_version_minimale_non_atteinte(self):
        self.heb.publier(self.trio("1.3.0", version_minimale="1.2.0"))
        self.assertEqual(self.passer(), 1)
        self.assertIn("MAJ_REFUSEE code=VERSION_MINIMALE_NON_ATTEINTE", self.technique())
        self.sans_archive()

    def test_client_different(self):
        self.heb.publier(self.trio("1.2.0", client="cabinet-02"))
        self.assertEqual(self.passer(), 1)
        self.assertIn("MAJ_REFUSEE code=CLIENT_DIFFERENT", self.technique())
        self.sans_archive()

    def test_version_ecartee(self):
        with maj.contexte_serveur(self.racine):
            maj.preparer_dossier_prive(self.racine)
            maj.ecrire_etat(self.racine, ecartees=["1.2.0"])
        self.heb.publier(self.trio("1.2.0"))
        self.assertEqual(self.passer(), 0)
        self.assertIn("MAJ_CONTROLE resultat=a-jour", self.technique())
        self.sans_archive()

    def test_signature_forgee_sur_un_manifeste_d_une_autre_version(self):
        # Un manifeste signé par la bonne clé, une signature d'un autre manifeste :
        # l'archive n'est pas demandée, et le refus ne dit pas pourquoi en détail.
        bon = self.trio("1.2.0")
        autre = self.trio("1.3.0")
        self.heb.publier(bon)
        with open(autre + paquet_signe.SUFFIXE_SIGNATURE, "rb") as f:
            self.heb.routes[self.CHEMIN + paquet_signe.SUFFIXE_SIGNATURE] = faux.corps(f.read())
        self.assertEqual(self.passer(), 1)
        self.assertIn("MAJ_REFUSEE code=SIGNATURE_INVALIDE", self.technique())
        self.sans_archive()

    def test_trois_requetes_dans_l_ordre_quand_une_version_est_disponible(self):
        self.heb.publier(self.trio("1.2.0"))
        # Hors plage et hors démarrage : la version est reçue, jugée, et attend.
        self.assertEqual(self.passer(), 3)
        self.assertIn("MAJ_REPORTEE code=HORS_PLAGE", self.technique())
        self.assertEqual(self.heb.chemins(), [
            self.CHEMIN + paquet_signe.SUFFIXE_MANIFESTE,
            self.CHEMIN + paquet_signe.SUFFIXE_SIGNATURE,
            self.CHEMIN])
        for requete in self.heb.requetes:
            self.assertEqual(requete["methode"], "GET")
            self.assertEqual(requete["longueur_du_corps"], 0)
            self.assertEqual(sorted(n for n, _ in requete["entetes"]),
                             ["Accept-Encoding", "Connection", "Host", "User-Agent"])
        self.assertEqual(self.etat()["attente"], "1.2.0")
        self.assertTrue(os.path.isfile(os.path.join(
            self.racine, "mise-a-jour", "reception", "archive.zip")))

    def test_une_publication_en_cours_donne_un_refus_propre_et_un_nouvel_essai(self):
        # Un manifeste neuf servi avec l'archive ancienne (l'hébergement statique n'a
        # pas de remplacement atomique d'un trio) : ARCHIVE_DIFFERENTE au moment
        # d'appliquer, jamais une version à moitié posée.
        ancienne = self.trio("1.2.0")
        neuve = self.trio("1.3.0")
        self.heb.publier(neuve)
        with open(ancienne, "rb") as f:
            self.heb.routes[self.CHEMIN] = faux.corps(f.read())
        self.ecrire_config(mise_a_jour={
            "client": "cabinet-01", "adresse": self.heb.adresse(), "plage": "00:00-23:59"})
        arbre = self.arbre()
        code = self.passer(datetime.datetime(2026, 11, 16, 12, 0, 0))
        self.assertEqual(code, 1)
        self.assertIn("MAJ_REFUSEE code=ARCHIVE_DIFFERENTE", self.technique())
        self.assertEqual(self.arbre(), arbre)
        self.assertEqual(self.demandes, [])
        self.assertIsNone(self.etat()["attente"])
        self.assertEqual(self.etat()["ecartees"], [])


if __name__ == "__main__":
    unittest.main()
