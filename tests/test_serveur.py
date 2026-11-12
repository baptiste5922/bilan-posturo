"""Tests des fonctions pures du serveur.

Bibliothèque standard uniquement, comme le serveur lui-même.

    python3 -m unittest discover -s tests
"""

import ast
import base64
import contextlib
import copy
import datetime
import email
import importlib.util
import io
import ipaddress
import json
import os
import random
import re
import shutil
import socket
import ssl
import stat
import sys
import tempfile
import threading
import unittest
import unittest.mock

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "serveur"))

import serveur

# Garde-fou, pas un correctif (constat de revue C2-T1) : serveur.CONFIG
# pointe par défaut sur config.json du cabinet réel, à la racine du dépôt
# (serveur.py:42-43). Chaque test de ce module qui écrit une configuration
# le repatche explicitement vers un fichier temporaire (ConfigurationCabinet
# .setUp, plus bas) ; celui qui l'oublierait écrirait silencieusement
# par-dessus le fichier réel d'un cabinet en exercice. On empoisonne donc la
# valeur par défaut pour toute la durée de ce module, avant le premier
# test : un oubli futur écrit dans un fichier jetable, jamais dans
# config.json réel. Portée volontairement limitée à ce module : c'est ici,
# et seulement ici, que des fonctions qui écrivent CONFIG
# (definir_mot_de_passe, saisir_cabinet) sont appelées en mémoire plutôt que
# dans un sous-processus isolé (tests/test_integration.py démarre toujours
# serveur.py dans un bac à sable séparé, où CONFIG se recalcule depuis un
# autre __file__).
_CONFIG_REEL_NE_JAMAIS_RESTAURER_PAR_DEFAUT = serveur.CONFIG


def setUpModule():
    serveur.CONFIG = os.path.join(
        tempfile.gettempdir(), "bilan-posturo-config-de-test-jamais-ecrit.json")


def tearDownModule():
    serveur.CONFIG = _CONFIG_REEL_NE_JAMAIS_RESTAURER_PAR_DEFAUT


class AssainirNom(unittest.TestCase):
    """Le nom vient de la tablette : il est tenu pour hostile."""

    def test_nom_simple_conserve(self):
        self.assertEqual(serveur.assainir_nom("bilan.pdf"), "bilan.pdf")

    def test_espaces_et_tirets_conserves(self):
        # Le cabinet nomme ses bilans "Bilan_2026-08-22_Dupont-Lea.pdf" :
        # ce format doit traverser l'assainissement intact.
        self.assertEqual(serveur.assainir_nom("Bilan_2026-08-22_Dupont-Lea.pdf"),
                         "Bilan_2026-08-22_Dupont-Lea.pdf")

    def test_traversee_de_repertoire(self):
        for attaque in ("../../../../etc/passwd.pdf",
                        "../../secret.pdf",
                        "/etc/passwd.pdf"):
            with self.subTest(attaque=attaque):
                nom = serveur.assainir_nom(attaque)
                self.assertNotIn("/", nom)
                self.assertNotIn("..", nom)

    def test_traversee_avec_antislash_windows(self):
        # os.path.basename ne reconnaît pas "\" comme séparateur sous POSIX :
        # sans la conversion préalable, le nom entier passerait.
        nom = serveur.assainir_nom(r"..\..\Windows\System32\evil.pdf")
        self.assertNotIn("\\", nom)
        self.assertEqual(nom, "evil.pdf")

    def test_accents_translitteres(self):
        self.assertEqual(serveur.assainir_nom("Bilan Élodie Dupré.pdf"),
                         "Bilan Elodie Dupre.pdf")

    def test_caracteres_speciaux_remplaces(self):
        nom = serveur.assainir_nom("bilan;rm -rf *.pdf")
        self.assertTrue(nom.endswith(".pdf"))
        for interdit in ";*$`\"'":
            self.assertNotIn(interdit, nom)

    def test_nom_vide_donne_un_repli(self):
        for entree in ("", "...", "///"):
            with self.subTest(entree=entree):
                self.assertEqual(serveur.assainir_nom(entree), "bilan.pdf")

    def test_nom_reduit_a_rien_reste_un_pdf_sur(self):
        # Un nom entièrement non-ASCII est vidé par la translittération.
        # Le repli exact importe peu ; ce qui compte est qu'il reste un nom
        # de fichier isolé, non vide et portant l'extension .pdf.
        for entree in (".pdf", "🙂.pdf", "🙂"):
            with self.subTest(entree=entree):
                nom = serveur.assainir_nom(entree)
                self.assertTrue(nom.endswith(".pdf"))
                self.assertNotIn("/", nom)
                self.assertEqual(nom, os.path.basename(nom))
                self.assertTrue(os.path.splitext(nom)[0])

    def test_nom_tres_long_garde_son_extension(self):
        # La troncature a lieu avant que ".pdf" soit remis : couper après
        # produirait un fichier sans extension, que Windows n'ouvrirait pas.
        nom = serveur.assainir_nom("A" * 500 + ".pdf")
        self.assertTrue(nom.endswith(".pdf"))
        self.assertLessEqual(len(nom), 120)

    def test_extension_toujours_pdf(self):
        for entree in ("bilan.exe", "bilan", "bilan.PDF", "bilan.pdf.exe"):
            with self.subTest(entree=entree):
                self.assertTrue(serveur.assainir_nom(entree).endswith(".pdf"))

    def test_octet_nul_neutralise(self):
        nom = serveur.assainir_nom("bilan\x00.pdf")
        self.assertNotIn("\x00", nom)


class MotDePasse(unittest.TestCase):

    def test_aller_retour(self):
        empreinte = serveur.hacher("motdepasse123")
        self.assertTrue(serveur.verifier_mot_de_passe("motdepasse123", empreinte))

    def test_mauvais_mot_de_passe(self):
        empreinte = serveur.hacher("motdepasse123")
        self.assertFalse(serveur.verifier_mot_de_passe("motdepasse124", empreinte))
        self.assertFalse(serveur.verifier_mot_de_passe("", empreinte))

    def test_jamais_stocke_en_clair(self):
        self.assertNotIn("motdepasse123", serveur.hacher("motdepasse123"))

    def test_sel_aleatoire(self):
        # Deux comptes ayant le même mot de passe ne doivent pas partager la
        # même empreinte, sinon une table précalculée les casse d'un coup.
        self.assertNotEqual(serveur.hacher("identique"),
                            serveur.hacher("identique"))

    def test_mot_de_passe_non_ascii(self):
        empreinte = serveur.hacher("clé-d'accès-éùà")
        self.assertTrue(serveur.verifier_mot_de_passe("clé-d'accès-éùà", empreinte))

    def test_empreinte_malformee_refusee(self):
        # Un config.json corrompu ou tronqué doit refuser la connexion, pas
        # lever une exception qui tuerait le thread.
        for stocke in ("", "n'importe quoi", "pbkdf2_sha256$abc",
                       "pbkdf2_sha256$240000$zz$zz", "md5$1$aa$bb",
                       "pbkdf2_sha256$240000$aa$bb$cc"):
            with self.subTest(stocke=stocke):
                self.assertFalse(serveur.verifier_mot_de_passe("x", stocke))


class CheminLibre(unittest.TestCase):

    def setUp(self):
        self.dossier = tempfile.mkdtemp()

    def test_dossier_vide(self):
        self.assertEqual(os.path.basename(serveur.chemin_libre(self.dossier, "b.pdf")),
                         "b.pdf")

    def test_collision_suffixee_jamais_ecrasee(self):
        # Deux bilans le même jour pour le même patient ne doivent pas se
        # remplacer l'un l'autre : ce serait une perte de donnée de santé.
        open(os.path.join(self.dossier, "b.pdf"), "w").close()
        self.assertEqual(os.path.basename(serveur.chemin_libre(self.dossier, "b.pdf")),
                         "b-2.pdf")

        open(os.path.join(self.dossier, "b-2.pdf"), "w").close()
        self.assertEqual(os.path.basename(serveur.chemin_libre(self.dossier, "b.pdf")),
                         "b-3.pdf")


class EcritureAtomique(unittest.TestCase):

    def setUp(self):
        self.dossier = tempfile.mkdtemp()
        self.cible = os.path.join(self.dossier, "bilan.pdf")

    def test_contenu_ecrit(self):
        serveur.ecrire_atomiquement(self.cible, b"%PDF-1.4 contenu")
        with open(self.cible, "rb") as f:
            self.assertEqual(f.read(), b"%PDF-1.4 contenu")

    @unittest.skipIf(os.name == "nt",
                     "chmod ne gère que le drapeau lecture seule sous Windows")
    def test_permissions_restreintes(self):
        # Le fichier contient des données de santé : lisible par le seul
        # compte qui fait tourner le serveur.
        serveur.ecrire_atomiquement(self.cible, b"%PDF-")
        mode = stat.S_IMODE(os.stat(self.cible).st_mode)
        self.assertEqual(mode, 0o600)

    def test_aucun_fichier_temporaire_residuel(self):
        serveur.ecrire_atomiquement(self.cible, b"%PDF-")
        self.assertEqual(os.listdir(self.dossier), ["bilan.pdf"])

    def test_echec_ne_laisse_rien(self):
        # Si l'écriture casse en cours de route, le dossier surveillé par le
        # cabinet ne doit contenir ni PDF partiel ni .part orphelin.
        with unittest.mock.patch("os.replace",
                                 side_effect=OSError("disque plein")):
            with self.assertRaises(OSError):
                serveur.ecrire_atomiquement(self.cible, b"%PDF-")
        self.assertEqual(os.listdir(self.dossier), [])

    def test_remplacement_est_atomique(self):
        # os.replace écrase d'un bloc : à aucun instant la cible n'existe
        # avec un contenu tronqué.
        serveur.ecrire_atomiquement(self.cible, b"%PDF- ancien")
        serveur.ecrire_atomiquement(self.cible, b"%PDF- nouveau")
        with open(self.cible, "rb") as f:
            self.assertEqual(f.read(), b"%PDF- nouveau")


if __name__ == "__main__":
    unittest.main()


class PortabiliteWindows(unittest.TestCase):
    """Le serveur tourne sur le PC Windows du cabinet.

    La console y travaille en cp1252 : un caractère absent de ce jeu lève
    UnicodeEncodeError et interrompt le script. Une flèche « → » dans les
    consignes d'installation a suffi à faire échouer la génération du
    certificat sous Windows, sans que macOS ni Linux ne le voient.
    """

    SERVEUR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "serveur")

    def test_scripts_powershell_avec_bom(self):
        """PowerShell 5.1 — celui livre avec Windows — lit un .ps1 sans BOM
        comme de l'ANSI : les accents et les guillemets typographiques
        deviennent illisibles dans les messages affiches au praticien."""
        racine = os.path.dirname(self.SERVEUR)
        scripts = [n for n in os.listdir(racine) if n.endswith(".ps1")]
        self.assertTrue(scripts, "aucun script PowerShell trouve")
        for nom in scripts:
            with self.subTest(fichier=nom):
                with open(os.path.join(racine, nom), "rb") as f:
                    self.assertEqual(f.read(3), b"\xef\xbb\xbf",
                                     nom + " doit etre encode en UTF-8 avec BOM")

    def test_scripts_powershell_en_crlf(self):
        """Un .ps1 en fins de ligne Unix se comporte de facon erratique sous
        PowerShell 5.1, notamment autour des continuations en accent grave."""
        racine = os.path.dirname(self.SERVEUR)
        for nom in [n for n in os.listdir(racine) if n.endswith(".ps1")]:
            with self.subTest(fichier=nom):
                with open(os.path.join(racine, nom), "rb") as f:
                    contenu = f.read()
                self.assertEqual(contenu.count(b"\n"), contenu.count(b"\r\n"),
                                 nom + " contient des fins de ligne Unix")

    def test_aucun_caractere_hors_cp1252(self):
        for nom in ("serveur.py", "generer_autorite.py"):
            chemin = os.path.join(self.SERVEUR, nom)
            with open(chemin, encoding="utf-8") as f:
                for numero, ligne in enumerate(f, 1):
                    for caractere in ligne:
                        if caractere.isascii():
                            continue
                        with self.subTest(fichier=nom, ligne=numero,
                                          caractere=caractere):
                            try:
                                caractere.encode("cp1252")
                            except UnicodeEncodeError:
                                self.fail(
                                    "{}:{} contient {!r}, non encodable par la "
                                    "console Windows".format(nom, numero, caractere))


class RotationDuJournal(unittest.TestCase):
    """Le serveur tourne en service, donc en continu : le journal doit
    s'arrêter de croître tout seul."""

    def setUp(self):
        self.dossier = tempfile.mkdtemp(prefix="bilan-journal-")
        self.journal = os.path.join(self.dossier, "journal.log")
        self.patch = unittest.mock.patch.object(serveur, "JOURNAL",
                                                self.journal)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(shutil.rmtree, self.dossier, ignore_errors=True)

    def ecrire(self, octets):
        with open(self.journal, "w", encoding="utf-8") as f:
            f.write("x" * octets)

    def test_journal_court_conserve(self):
        self.ecrire(100)
        serveur.faire_tourner_journal()
        self.assertEqual(os.path.getsize(self.journal), 100)
        self.assertFalse(os.path.exists(self.journal + ".1"))

    def test_journal_plein_archive(self):
        self.ecrire(serveur.JOURNAL_TAILLE_MAX + 1)
        serveur.faire_tourner_journal()
        self.assertFalse(os.path.exists(self.journal))
        self.assertTrue(os.path.exists(self.journal + ".1"))

    def test_generations_limitees(self):
        # La borne n'est plus JOURNAL_ARCHIVES seul (C4-T2, D4) : elle se
        # dérive de generations_maximales(), jamais d'un chiffre transcrit.
        borne = serveur.generations_maximales()
        for _ in range(borne + 2):
            self.ecrire(serveur.JOURNAL_TAILLE_MAX + 1)
            serveur.faire_tourner_journal()
        surnumeraire = "{}.{}".format(self.journal, borne + 1)
        self.assertTrue(os.path.exists("{}.{}".format(self.journal, borne)))
        self.assertFalse(os.path.exists(surnumeraire))

    def test_journal_absent_ne_leve_pas(self):
        serveur.faire_tourner_journal()      # aucun fichier : rien à faire

    def test_journaliser_sans_stderr(self):
        # Sous pythonw.exe, celui du service Windows, sys.stderr vaut None.
        # Un write direct tuerait le thread de la requête en cours.
        with unittest.mock.patch.object(serveur.sys, "stderr", None):
            serveur.journaliser("ligne\n")
        with open(self.journal, encoding="utf-8") as f:
            self.assertEqual(f.read(), "ligne\n")

    def test_journaliser_avec_stderr_ferme(self):
        flux = io.StringIO()
        flux.close()
        with unittest.mock.patch.object(serveur.sys, "stderr", flux):
            serveur.journaliser("ligne\n")
        with open(self.journal, encoding="utf-8") as f:
            self.assertEqual(f.read(), "ligne\n")


# Certificat jetable, pour tester empreinte_certificat() sans dépendre de
# cryptography côté test : auto-signé, généré une fois par openssl, jamais
# utilisé pour autre chose qu'un aller-retour PEM -> DER -> SHA-256.
CERTIFICAT_PEM_TEST = """-----BEGIN CERTIFICATE-----
MIICmjCCAYICCQDCkfBRhF/sizANBgkqhkiG9w0BAQsFADAPMQ0wCwYDVQQDDAR0
ZXN0MB4XDTI2MTAxOTExMzAwMFoXDTI2MTAyMDExMzAwMFowDzENMAsGA1UEAwwE
dGVzdDCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAOsUssXBtF2cU0ND
LdROgAnCnIAmsvRsWrpkuM5KrIEEVATp9wufrCxrX908fPzVB40CqjdG/HMx2Y7T
l7jy8xBMAXem4Yx1Vnthywr6JelzWZw1pi5vaf8R9TLt5CWgXOFxFdLVa3ye5caP
ZxSmsDmY/swBRtRyKcZaEQltQGalvxrg3WXG0E5kgPv6XhbZoPJrV+EVt/arUQrh
Oaryb7ubEGCE3Ryieax937L/GOpUewa1x1HkawRNYQ366eIzxCwO0MjoRhRyXhYc
acyG8bovEDWq1v16LKuSJjPTOPzShynzcmJiUrLz1OUOImTAIeAFxCDyIwe0r6yc
D8xYeOsCAwEAATANBgkqhkiG9w0BAQsFAAOCAQEAUgsboUSYEQgTQU853yjrNFGL
ygOtik8jAOO0tdTo+VVZ+wpPvb0PSGC4U45m7d83CBGJOuZKON9+xa9TABjhSI43
+C3dN8+YGHO50ldP7aDiXgVjVhja3VYMR4NB6+A3OgVGXReKg8bkjiT/Xxmq0JVf
SvI7WDGjLls9wf/F4TOUodEAgvxNX9CCPAtJ3qb7ByY2XbVK11fzE0AkQ3MH/yva
j1vJiEvP9Mx5C02CzrJe2xUIFmwYqEH4s0MOLSa1nq1/pEpniv52zSMqGwho1Bmm
nsT6lqOHUXYtr3OFWzLNo3JuTpeNzJcabcDsGd0WGQZ1ag0BinrZRKKH8Q9eLw==
-----END CERTIFICATE-----
"""


class JournalTechnique(unittest.TestCase):
    """Le second journal (C4-T1) : non identifiant par construction.

    Chaque test qui écrit redirige serveur.TECHNIQUE vers un dossier
    temporaire plutôt que vers la racine du projet, qui héberge le journal
    réel d'un cabinet quand ce code tourne hors du dépôt.
    """

    def setUp(self):
        self.dossier = tempfile.mkdtemp(prefix="bilan-technique-")
        self.addCleanup(shutil.rmtree, self.dossier, ignore_errors=True)
        self.technique = os.path.join(self.dossier, "technique.log")

    def lire(self):
        with open(self.technique, encoding="utf-8") as f:
            return f.read()

    def test_fichier_cree_a_la_racine(self):
        # Emplacement du *vrai* chemin (non substitué) : à la racine du
        # projet, jamais dans la racine web.
        self.assertEqual(os.path.dirname(serveur.TECHNIQUE), serveur.RACINE)
        self.assertNotEqual(os.path.dirname(serveur.TECHNIQUE), serveur.FORMULAIRE)
        self.assertEqual(os.path.basename(serveur.TECHNIQUE), "technique.log")

        # Et le fichier apparaît bien après une écriture, dans le bac à
        # sable substitué pour ce test.
        with unittest.mock.patch.object(serveur, "TECHNIQUE", self.technique):
            serveur.journaliser_technique("DEMARRAGE", "port=8000")
        self.assertTrue(os.path.exists(self.technique))

    def test_tous_les_evenements_couverts(self):
        with unittest.mock.patch.object(serveur, "TECHNIQUE", self.technique):
            # ROTATION n'est jamais appelée en direct : on la déclenche une
            # fois, avant tout le reste, pour que la rotation qui archive le
            # fichier n'emporte avec elle aucun des événements qui suivent.
            with open(self.technique, "w", encoding="utf-8") as f:
                f.write("x" * (serveur.JOURNAL_TAILLE_MAX + 1))
            serveur.journaliser_technique("DEPOT", "ok 1 octets")

            for evenement in serveur.EVENEMENTS_TECHNIQUES - {"ROTATION", "DEPOT"}:
                serveur.journaliser_technique(evenement, "detail")

            contenu = self.lire()

        evenements_exerces = {
            ligne.split(" ", 2)[1] for ligne in contenu.splitlines() if ligne}
        # Égalité, et non inclusion : seuls les événements déclarés doivent
        # apparaître, et tous doivent apparaître.
        self.assertEqual(evenements_exerces, serveur.EVENEMENTS_TECHNIQUES)

    def test_detail_hostile_ne_ressort_pas(self):
        nom_patient = "Bilan_2026-08-22_Dupont-Lea.pdf"
        adresse = "192.168.1.13"

        for hostile in (nom_patient, adresse):
            route = serveur.classe_route("/" + hostile)
            self.assertIn(route, serveur.ROUTES_TECHNIQUES)
            self.assertNotIn(hostile, route)

        erreur = OSError(13, "Permission denied")
        erreur.filename = os.path.join("/bilans", nom_patient)
        detail = serveur.detail_echec_ecriture(erreur)
        self.assertEqual(detail, "errno=13 Permission denied")
        self.assertNotIn(nom_patient, detail)
        self.assertNotIn(adresse, detail)

        for hostile in (nom_patient, adresse):
            # Vocabulaire fermé : un motif hors de MOTIFS_REFUS_DEPOT ne se
            # recopie jamais.
            self.assertNotIn(hostile, serveur.detail_refus_depot(hostile))

    def test_evenement_inconnu_ne_leve_pas(self):
        with unittest.mock.patch.object(serveur, "TECHNIQUE", self.technique):
            serveur.journaliser_technique("CECI_N_EXISTE_PAS", "detail")
        self.assertIn("EVENEMENT_INCONNU", self.lire())

    @unittest.skipIf(os.name == "nt",
                     "chmod ne restreint l'écriture d'un dossier que sous POSIX")
    def test_journal_illisible_ne_leve_pas(self):
        open(self.technique, "w", encoding="utf-8").close()
        os.chmod(self.technique, 0o400)
        os.chmod(self.dossier, 0o500)
        try:
            with unittest.mock.patch.object(serveur, "TECHNIQUE", self.technique):
                serveur.journaliser_technique("DEMARRAGE", "port=8000")
        finally:
            os.chmod(self.dossier, 0o700)
            os.chmod(self.technique, 0o600)

    def test_verdict_certificat_non_decodable_ne_leve_pas(self):
        # Réenregistré en ANSI par un correspondant, ou tronqué en plein
        # caractère multi-octets par un disque plein : le fichier existe et
        # se lit en octets, mais pas en UTF-8. UnicodeDecodeError dérive de
        # ValueError, pas d'OSError : sans ce second type, l'exception
        # remonte et empêche le serveur de démarrer (constat d'audit).
        ligne = ("2026-10-19T08:00:00 DEMARRAGE port=8000 certificat=abc "
                "premier démarrage observé\n")
        with open(self.technique, "wb") as f:
            f.write(ligne.encode("cp1252"))
        with unittest.mock.patch.object(serveur, "TECHNIQUE", self.technique):
            verdict = serveur.verdict_certificat("abc")
        self.assertEqual(verdict, "premier démarrage observé")

    def test_rotation_partagee(self):
        with unittest.mock.patch.object(serveur, "TECHNIQUE", self.technique):
            with open(self.technique, "w", encoding="utf-8") as f:
                f.write("x" * (serveur.JOURNAL_TAILLE_MAX + 1))
            serveur.faire_tourner_journal(serveur.TECHNIQUE)
        self.assertTrue(os.path.exists(self.technique + ".1"))
        self.assertFalse(os.path.exists(self.technique + ".4"))

    def test_empreinte_certificat_stable_et_courte(self):
        chemin = os.path.join(self.dossier, "certificat.pem")
        with open(chemin, "w", encoding="ascii") as f:
            f.write(CERTIFICAT_PEM_TEST)

        premiere = serveur.empreinte_certificat(chemin)
        seconde = serveur.empreinte_certificat(chemin)
        self.assertEqual(premiere, seconde)
        self.assertEqual(len(premiere), 16)
        int(premiere, 16)      # lève ValueError si ce n'est pas de l'hexadécimal

        invalide = os.path.join(self.dossier, "invalide.pem")
        with open(invalide, "w", encoding="utf-8") as f:
            f.write("ceci n'est pas un certificat")
        self.assertEqual(serveur.empreinte_certificat(invalide), "indisponible")

        self.assertEqual(
            serveur.empreinte_certificat(
                os.path.join(self.dossier, "absent.pem")),
            "indisponible")

    def test_vocabulaire_derive_du_source(self):
        chemin_source = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "serveur", "serveur.py")
        with open(chemin_source, encoding="utf-8") as f:
            source = f.read()

        appels = re.findall(r'journaliser_technique\(\s*"([^"]+)"', source)
        self.assertTrue(appels, "aucun appel à journaliser_technique trouvé")
        for evenement in appels:
            with self.subTest(evenement=evenement):
                self.assertIn(evenement, serveur.EVENEMENTS_TECHNIQUES)

    def test_rotation_derivee_de_la_constante(self):
        # ROTATION échappe de nécessité à journaliser_technique() (sans quoi
        # ce serait un interblocage), donc à la garde ci-dessus qui ne relève
        # que les appels journaliser_technique("…". Ce test-ci couvre ce
        # deuxième site d'écriture (constat d'audit C4-T1) : le libellé ne
        # doit être transcrit nulle part ailleurs que dans sa déclaration.
        self.assertEqual(serveur.EVENEMENT_ROTATION, "ROTATION")
        self.assertIn(serveur.EVENEMENT_ROTATION, serveur.EVENEMENTS_TECHNIQUES)

        chemin_source = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "serveur", "serveur.py")
        with open(chemin_source, encoding="utf-8") as f:
            source = f.read()

        occurrences = re.findall(r'"ROTATION"', source)
        self.assertEqual(
            len(occurrences), 2,
            "« ROTATION » apparaît {} fois entre guillemets dans le source, "
            "attendu 2 (le vocabulaire fermé, et EVENEMENT_ROTATION) : un "
            "troisième site l'aurait retranscrit plutôt que dérivé de la "
            "constante".format(len(occurrences)))


class DepotEchecEcritureSansFuite(unittest.TestCase):
    """Reproduit un échec RÉEL au renommage (os.replace), pas à la création
    du temporaire (mkstemp) : c'est seulement là que l'OSError porte le nom
    du patient, et donc le seul cas qui mette la décision D4 à l'épreuve.

    chemin_libre() ne renvoie jamais un chemin déjà existant : on ne peut
    donc pas provoquer ce cas par une simple collision de fichier sans
    introduire une condition de course sur le vrai système de fichiers,
    instable par nature. do_POST() est donc appelé en direct, sur un
    Gestionnaire construit sans socket (bypass de __init__), avec
    os.replace() substitué par une OSError portant la destination réelle —
    exactement ce qu'une vraie panne de renommage produirait.
    """

    UTILISATEUR = "cabinet"
    MOT_DE_PASSE = "motdepasse123"

    def setUp(self):
        self.dossier_bilans = tempfile.mkdtemp(prefix="bilan-depot-")
        self.addCleanup(shutil.rmtree, self.dossier_bilans, ignore_errors=True)
        self.dossier_journaux = tempfile.mkdtemp(prefix="bilan-technique-")
        self.addCleanup(shutil.rmtree, self.dossier_journaux, ignore_errors=True)

        self.technique = os.path.join(self.dossier_journaux, "technique.log")
        self.journal = os.path.join(self.dossier_journaux, "journal.log")
        for nom_attribut, valeur in (("TECHNIQUE", self.technique),
                                     ("JOURNAL", self.journal)):
            patch = unittest.mock.patch.object(serveur, nom_attribut, valeur)
            patch.start()
            self.addCleanup(patch.stop)

    def gestionnaire_sans_socket(self, corps, nom_fichier):
        """Un Gestionnaire minimal : do_POST() n'a besoin ni de socket ni de
        serveur réel, seulement des attributs qu'il lit lui-même."""
        instance = serveur.Gestionnaire.__new__(serveur.Gestionnaire)
        instance.command = "POST"
        instance.path = "/depot"
        instance.requestline = "POST /depot HTTP/1.1"
        instance.client_address = ("127.0.0.1", 0)
        instance.request_version = "HTTP/1.1"
        instance.close_connection = True
        instance.silencieux = False
        instance.config = {"utilisateur": self.UTILISATEUR,
                           "mot_de_passe": serveur.hacher(self.MOT_DE_PASSE)}
        instance.dossier_pdf = self.dossier_bilans

        jeton = base64.b64encode(
            "{}:{}".format(self.UTILISATEUR, self.MOT_DE_PASSE)
            .encode("utf-8")).decode("ascii")
        entete_nom = base64.b64encode(
            nom_fichier.encode("utf-8")).decode("ascii")
        instance.headers = email.message_from_string(
            "Content-Length: {}\nX-Fichier: {}\nAuthorization: Basic {}\n"
            .format(len(corps), entete_nom, jeton))
        instance.rfile = io.BytesIO(corps)
        instance.wfile = io.BytesIO()
        return instance

    def test_echec_au_renommage_ne_fuite_pas_le_nom(self):
        nom = "Bilan_2026-08-22_Dupont-Lea.pdf"
        instance = self.gestionnaire_sans_socket(b"%PDF-1.4 contenu", nom)

        # Le même chemin que do_POST calculera lui-même (dossier vide : pas
        # de suffixe de collision) : c'est ce que porterait une vraie
        # PermissionError au renommage.
        destination = os.path.join(self.dossier_bilans, nom)
        echec_reel = PermissionError(13, "Permission denied", destination)

        with unittest.mock.patch.object(serveur.os, "replace",
                                        side_effect=echec_reel):
            instance.do_POST()

        with open(self.technique, encoding="utf-8") as f:
            contenu_technique = f.read()

        self.assertIn("ECHEC_ECRITURE", contenu_technique)
        # La garde : ni le nom du fichier, ni le dossier qui le contient.
        self.assertNotIn(nom, contenu_technique)
        self.assertNotIn(self.dossier_bilans, contenu_technique)

        # Témoin négatif : le journal nominatif, lui, continue de porter le
        # nom (décision D4 ne s'applique qu'au journal technique).
        with open(self.journal, encoding="utf-8") as f:
            self.assertIn(nom, f.read())


class ConfigurationCabinet(unittest.TestCase):
    """Bloc "cabinet" (C2-T1) : fusion profonde, liste blanche, classe de route.

    Le config.json réel du cabinet n'est jamais lu ni écrit ici : CONFIG est
    systématiquement substitué par un fichier temporaire.
    """

    def setUp(self):
        self.dossier = tempfile.mkdtemp(prefix="bilan-test-config-")
        self.addCleanup(shutil.rmtree, self.dossier, ignore_errors=True)
        self.config_json = os.path.join(self.dossier, "config.json")
        self.patch = unittest.mock.patch.object(serveur, "CONFIG", self.config_json)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def ecrire(self, contenu):
        with open(self.config_json, "w", encoding="utf-8") as f:
            json.dump(contenu, f)

    def test_cles_cabinet_derivees_de_config_defaut(self):
        self.assertEqual(
            serveur.CLES_CABINET, tuple(serveur.CONFIG_DEFAUT["cabinet"]))
        self.assertEqual(
            set(serveur.CLES_CABINET),
            {"nom", "praticien", "adresse", "courriel", "telephone",
             "logo", "convention_nommage"})

    def test_cabinet_absent_complete_par_defaut(self):
        self.ecrire({"mot_de_passe": "x"})
        config = serveur.charger_config()
        self.assertEqual(config["cabinet"], serveur.CONFIG_DEFAUT["cabinet"])

    def test_cabinet_partiel_fusionne_cle_a_cle(self):
        # "Dr Martin" et "1 rue du Test" : des valeurs plates, jamais un
        # courriel ni un numéro de téléphone littéral — tests/test_identite_
        # absente.py balaie l'arbre suivi par git, ce fichier compris, et de
        # tels motifs y seraient détectés comme une fuite.
        self.ecrire({"cabinet": {"praticien": "Dr Martin", "adresse": "1 rue du Test"}})
        config = serveur.charger_config()
        self.assertEqual(config["cabinet"]["praticien"], "Dr Martin")
        self.assertEqual(config["cabinet"]["adresse"], "1 rue du Test")
        # Les clés absentes du fichier restent aux valeurs par défaut,
        # jamais écrasées par la fusion.
        self.assertEqual(config["cabinet"]["telephone"], "")
        self.assertEqual(config["cabinet"]["logo"], "images/favicon.jpeg")
        self.assertEqual(
            config["cabinet"]["convention_nommage"], "Bilan_{date}_{patient}")

    def test_cabinet_non_dictionnaire_tolere(self):
        for valeur in (None, "n'importe quoi", 42, []):
            with self.subTest(valeur=valeur):
                self.ecrire({"cabinet": valeur})
                config = serveur.charger_config()
                self.assertEqual(config["cabinet"], serveur.CONFIG_DEFAUT["cabinet"])

    def test_sous_cle_cabinet_non_textuelle_toleree(self):
        # Un config.json corrigé à la main peut porter "praticien": null :
        # la sous-clé retombe sur sa valeur par défaut au lieu de faire
        # lever demarrer() sur .strip(), et les autres sous-clés valides
        # sont conservées.
        for valeur in (None, 42, {"a": 1}, ["x"], True):
            with self.subTest(valeur=valeur):
                self.ecrire({"cabinet": {"praticien": valeur,
                                         "adresse": "1 rue du Test"}})
                config = serveur.charger_config()
                self.assertEqual(config["cabinet"]["praticien"], "")
                self.assertEqual(config["cabinet"]["adresse"], "1 rue du Test")
                self.assertEqual(config["cabinet"]["praticien"].strip(), "")

    def test_classe_route_cabinet(self):
        self.assertEqual(serveur.classe_route("/cabinet"), "cabinet")
        self.assertIn("cabinet", serveur.ROUTES_TECHNIQUES)

    def test_config_saisit_les_champs_cabinet(self):
        self.ecrire({"utilisateur": "cabinet",
                     "cabinet": {"praticien": "Ancien Nom"}})

        reponses = iter([
            "",              # identifiant : conserve "cabinet"
            "",               # nom
            "Nouveau Nom",   # praticien : remplace "Ancien Nom"
            "",               # adresse
            "contact-cabinet-test",  # courriel (jamais un "@" littéral :
                                      # tests/test_identite_absente.py le
                                      # relèverait comme une fuite)
            "",               # telephone
            "",               # logo
            "",               # convention_nommage
        ])

        # Capturée : definir_mot_de_passe() imprime sur la sortie standard
        # ("Configuration écrite...", "Identifiant : ..."), qui est aussi là
        # où unittest affiche son verdict ("Ran N tests ... OK"). Un message
        # qui ressemble à un incident, juste avant ce verdict, a déjà fait
        # craindre qu'un test venait d'écraser le config.json réel du
        # cabinet (constat de revue C2-T1) — alors qu'il est correctement
        # redirigé vers self.config_json (setUp ci-dessus).
        with unittest.mock.patch("builtins.input", lambda invite: next(reponses)), \
             unittest.mock.patch.object(
                 serveur.getpass, "getpass",
                 side_effect=["motdepasse123", "motdepasse123"]), \
             contextlib.redirect_stdout(io.StringIO()):
            code = serveur.definir_mot_de_passe()

        self.assertEqual(code, 0)
        with open(self.config_json, encoding="utf-8") as f:
            ecrit = json.load(f)

        self.assertEqual(set(ecrit["cabinet"]), set(serveur.CLES_CABINET))
        self.assertEqual(ecrit["cabinet"]["praticien"], "Nouveau Nom")
        self.assertEqual(ecrit["cabinet"]["courriel"], "contact-cabinet-test")
        # Les champs laissés vides conservent la valeur antérieure.
        self.assertEqual(ecrit["cabinet"]["logo"], "images/favicon.jpeg")
        self.assertTrue(ecrit["mot_de_passe"].startswith("pbkdf2_sha256$"))


# Seul module de serveur/ autorisé à importer autre chose que la bibliothèque
# standard : il fabrique les certificats, hors du chemin d'exécution du serveur.
EXEMPTE_DE_LA_GARDE_STDLIB = "generer_autorite.py"


def imports_hors_bibliotheque_standard(source, standard, voisins):
    """Les modules importés par `source` qui ne sont ni de la bibliothèque
    standard ni des modules voisins du même dossier (listés par l'appelant).

    Dérivé de l'arbre syntaxique : un import dans une fonction, ou sur une ligne
    multiple, est vu comme un import de tête.
    """
    modules = set()
    for noeud in ast.walk(ast.parse(source)):
        if isinstance(noeud, ast.Import):
            modules.update(a.name.split(".")[0] for a in noeud.names)
        elif isinstance(noeud, ast.ImportFrom) and noeud.module and noeud.level == 0:
            modules.add(noeud.module.split(".")[0])
    return sorted(modules - set(standard) - set(voisins))


# --------------------------------------------------------------------------
# Page d'état (C4-T3)
# --------------------------------------------------------------------------

def cryptography_absente():
    """cryptography ne sert qu'à fabriquer des certificats de comparaison,
    jamais au serveur : son absence fait sauter ces tests, pas échouer la
    suite."""
    return importlib.util.find_spec("cryptography") is None


def der(etiquette, contenu):
    """Encode un élément DER (formes courte et longue de la longueur).

    Écrit à la main, indépendamment de serveur._element_der : un encodeur et
    un décodeur qui partageraient leur code se donneraient raison à tort.
    """
    n = len(contenu)
    if n < 0x80:
        longueur = bytes([n])
    else:
        octets = n.to_bytes((n.bit_length() + 7) // 8, "big")
        longueur = bytes([0x80 | len(octets)]) + octets
    return bytes([etiquette]) + longueur + contenu


def faux_certificat(debut=(0x17, b"260101000000Z"), fin=(0x17, b"290101000000Z"),
                    adresses=(), version=True, extensions=True, remplissage=0):
    """Un certificat DER minimal mais structurellement fidèle : version [0]
    facultative, une extension sans rapport avant le subjectAltName, noms
    DNS et IP mêlés. `remplissage` gonfle le subject pour exercer les
    longueurs longues."""
    algorithme = der(0x30, der(0x06, bytes((0x2A, 0x86, 0x48, 0xCE, 0x3D, 0x04, 0x03, 0x02))))
    noms = der(0x82, b"localhost") + b"".join(
        der(0x87, ipaddress.ip_address(a).packed) for a in adresses)
    contraintes = der(0x30, der(0x06, bytes((0x55, 0x1D, 0x13)))
                      + der(0x01, b"\xff") + der(0x04, der(0x30, b"")))
    alternatifs = der(0x30, der(0x06, bytes((0x55, 0x1D, 0x11)))
                      + der(0x04, der(0x30, noms)))
    champs = [
        der(0xA0, der(0x02, b"\x02")) if version else b"",
        der(0x02, b"\x01"),
        algorithme,
        der(0x30, b""),
        der(0x30, der(debut[0], debut[1]) + der(fin[0], fin[1])),
        der(0x30, der(0x04, b"x" * remplissage)),
        der(0x30, b""),
        der(0xA3, der(0x30, contraintes + alternatifs)) if extensions else b"",
    ]
    return der(0x30, der(0x30, b"".join(champs)) + algorithme + der(0x03, b"\x00"))


def ecrire_pem(dossier, der_octets, nom="certificat.pem"):
    chemin = os.path.join(dossier, nom)
    with open(chemin, "w", encoding="ascii") as f:
        f.write(ssl.DER_cert_to_PEM_cert(der_octets))
    return chemin


UTC = datetime.timezone.utc


class LecteurCertificat(unittest.TestCase):
    """lire_certificat : expiration et adresses IP, bibliothèque standard
    seule, sans jamais lever (C4-T3, étape 3)."""

    def setUp(self):
        self.dossier = tempfile.mkdtemp(prefix="bilan-test-certificat-")
        self.addCleanup(shutil.rmtree, self.dossier, ignore_errors=True)

    def lire(self, der_octets):
        return serveur.lire_certificat(ecrire_pem(self.dossier, der_octets))

    def fabriquer(self, fin, adresses, critique=False):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID

        cle = ec.generate_private_key(ec.SECP256R1())
        nom = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "essai")])
        certificat = (
            x509.CertificateBuilder()
            .subject_name(nom).issuer_name(nom)
            .public_key(cle.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(fin - datetime.timedelta(days=30))
            .not_valid_after(fin)
            .add_extension(x509.SubjectAlternativeName(
                [x509.DNSName("localhost")]
                + [x509.IPAddress(ipaddress.ip_address(a)) for a in adresses]),
                critical=critique)
            .sign(cle, hashes.SHA256()))
        chemin = os.path.join(self.dossier, "reference.pem")
        with open(chemin, "wb") as f:
            f.write(certificat.public_bytes(serialization.Encoding.PEM))
        return certificat, chemin

    @staticmethod
    def expiration_de(certificat):
        lue = getattr(certificat, "not_valid_after_utc", None)
        if lue is None:
            lue = certificat.not_valid_after.replace(tzinfo=UTC)
        return lue

    @unittest.skipIf(cryptography_absente(), "cryptography requis pour la référence")
    def test_conforme_a_cryptography(self):
        # Les mêmes valeurs que la bibliothèque de référence, sur un
        # certificat IPv4 + IPv6 + boucle : une date de début prise pour une
        # date de fin, ou un mauvais [3], se verrait ici.
        adresses = ("192.0.2.7", "2001:db8::1", "127.0.0.1", "::1")
        fin = datetime.datetime(2030, 3, 4, 5, 6, 7, tzinfo=UTC)
        certificat, chemin = self.fabriquer(fin, adresses)

        lu = serveur.lire_certificat(chemin)

        self.assertEqual(lu["expire_le"], self.expiration_de(certificat))
        self.assertEqual(lu["expire_le"], fin)
        self.assertEqual(
            list(lu["adresses"]),
            [ipaddress.ip_address(a) for a in adresses])
        self.assertTrue(all(isinstance(a, (ipaddress.IPv4Address,
                                           ipaddress.IPv6Address))
                            for a in lu["adresses"]))

    @unittest.skipIf(cryptography_absente(), "cryptography requis pour la référence")
    def test_san_critique_conforme_a_cryptography(self):
        # Une extension critique porte un BOOLEAN entre l'OID et la valeur :
        # lire la deuxième partie au lieu de la dernière ne se voit que sur
        # un certificat de ce genre (RFC 5280 exige le SAN critique quand le
        # subject est vide ; un certificat fabriqué ailleurs peut l'être).
        adresses = ("192.0.2.7", "2001:db8::1", "127.0.0.1", "::1")
        fin = datetime.datetime(2030, 3, 4, 5, 6, 7, tzinfo=UTC)
        certificat, chemin = self.fabriquer(fin, adresses, critique=True)
        from cryptography import x509
        san = certificat.extensions.get_extension_for_class(
            x509.SubjectAlternativeName)
        self.assertTrue(san.critical)

        lu = serveur.lire_certificat(chemin)

        self.assertEqual(lu["expire_le"], fin)
        self.assertEqual(
            list(lu["adresses"]),
            san.value.get_values_for_type(x509.IPAddress))
        self.assertEqual(
            list(lu["adresses"]), [ipaddress.ip_address(a) for a in adresses])

    @unittest.skipIf(cryptography_absente(), "cryptography requis pour la référence")
    def test_utctime_et_generalizedtime_de_cryptography(self):
        # cryptography écrit un UTCTime jusqu'en 2049 et un GeneralizedTime
        # à partir de 2050 ; 1999 exerce le siècle « 19AA ».
        for annee in (1999, 2049, 2051):
            with self.subTest(annee=annee):
                fin = datetime.datetime(annee, 12, 31, 23, 59, 58, tzinfo=UTC)
                certificat, chemin = self.fabriquer(fin, ("192.0.2.7",))
                self.assertEqual(serveur.lire_certificat(chemin)["expire_le"], fin)

    def test_utctime_et_generalizedtime(self):
        cas = [
            ((0x17, b"491231235959Z"), datetime.datetime(2049, 12, 31, 23, 59, 59, tzinfo=UTC)),
            ((0x17, b"500101000000Z"), datetime.datetime(1950, 1, 1, tzinfo=UTC)),
            ((0x17, b"991231000000Z"), datetime.datetime(1999, 12, 31, tzinfo=UTC)),
            ((0x17, b"000229120000Z"), datetime.datetime(2000, 2, 29, 12, tzinfo=UTC)),
            ((0x18, b"20510101000000Z"), datetime.datetime(2051, 1, 1, tzinfo=UTC)),
        ]
        for fin, attendu in cas:
            with self.subTest(fin=fin):
                lu = self.lire(faux_certificat(fin=fin))
                self.assertEqual(lu["expire_le"], attendu)

    def test_la_fin_est_la_seconde_date(self):
        lu = self.lire(faux_certificat(debut=(0x17, b"200101000000Z"),
                                       fin=(0x17, b"300101000000Z")))
        self.assertEqual(lu["expire_le"].year, 2030)

    def test_dates_mal_formees_rendent_vide(self):
        # Sans secondes, avec décalage, avec fraction, jour impossible,
        # étiquette inattendue : refusées plutôt que devinées.
        for fin in ((0x17, b"4912312359Z"), (0x17, b"491231235959+0100"),
                    (0x18, b"20510101000000.5Z"), (0x17, b"261301000000Z"),
                    (0x17, b"260230000000Z"), (0x04, b"260101000000Z"),
                    (0x17, b"26010100000\xe9Z")):
            with self.subTest(fin=fin):
                lu = self.lire(faux_certificat(fin=fin))
                self.assertEqual(lu, {"expire_le": None, "adresses": ()})

    def test_adresses_ipv4_et_ipv6_sans_cryptography(self):
        adresses = ("192.0.2.7", "2001:db8::1", "127.0.0.1")
        lu = self.lire(faux_certificat(adresses=adresses))
        self.assertEqual(list(lu["adresses"]),
                         [ipaddress.ip_address(a) for a in adresses])

    def test_certificat_version_1_et_sans_extension(self):
        lu = self.lire(faux_certificat(version=False, extensions=False))
        self.assertEqual(lu["expire_le"],
                         datetime.datetime(2029, 1, 1, tzinfo=UTC))
        self.assertEqual(lu["adresses"], ())

    def test_longueurs_longues(self):
        # 0x81 (< 256 octets), 0x82 (< 65 536) et 0x83 : les formes longues
        # de la longueur, devant et après le champ qui nous intéresse.
        for remplissage in (200, 300, 70000):
            with self.subTest(remplissage=remplissage):
                lu = self.lire(faux_certificat(
                    adresses=("192.0.2.7",), remplissage=remplissage))
                self.assertEqual(lu["expire_le"].year, 2029)
                self.assertEqual(lu["adresses"], (ipaddress.ip_address("192.0.2.7"),))

    def test_structures_invalides_rendent_vide(self):
        vide = {"expire_le": None, "adresses": ()}
        valide = faux_certificat(adresses=("192.0.2.7",))
        self.assertNotEqual(self.lire(valide), vide)
        cas = {
            "longueur indéfinie": b"\x30\x80" + valide[2:],
            "étiquette sur plusieurs octets": b"\x1f" + valide[1:],
            "séquence attendue": der(0x04, valide),
            "élément plus long que son conteneur": valide[:-1],
            "longueur de 5 octets": b"\x30\x85\x00\x00\x00\x00\x10" + valide[4:],
            "vide": b"",
            "un seul octet": b"\x30",
            "séquence vide": der(0x30, b""),
            "tbs vide": der(0x30, der(0x30, b"")),
        }
        for nom, contenu in cas.items():
            with self.subTest(cas=nom):
                self.assertEqual(self.lire(contenu), vide)

    def test_adresse_de_longueur_impossible_rend_vide(self):
        # Un iPAddress de 5 octets n'est ni IPv4 ni IPv6.
        lu = serveur.lire_certificat(
            ecrire_pem(self.dossier, self.certificat_adresse_de_cinq_octets()))
        self.assertEqual(lu, {"expire_le": None, "adresses": ()})

    @staticmethod
    def certificat_adresse_de_cinq_octets():
        # Construit le certificat avec un iPAddress de 5 octets, longueurs
        # parentes recalculées : un simple remplacement d'octets les
        # laisserait fausses, et l'échec viendrait d'ailleurs.
        algorithme = der(0x30, der(0x06, b"\x2a"))
        noms = der(0x87, bytes((192, 0, 2, 7, 1)))
        alternatifs = der(0x30, der(0x06, bytes((0x55, 0x1D, 0x11)))
                          + der(0x04, der(0x30, noms)))
        champs = (der(0x02, b"\x01") + algorithme + der(0x30, b"")
                  + der(0x30, der(0x17, b"260101000000Z") + der(0x17, b"290101000000Z"))
                  + der(0x30, b"") + der(0x30, b"")
                  + der(0xA3, der(0x30, alternatifs)))
        return der(0x30, der(0x30, champs) + algorithme + der(0x03, b"\x00"))

    def test_entrees_abimees_sans_levee(self):
        vide = {"expire_le": None, "adresses": ()}
        valide = faux_certificat(adresses=("192.0.2.7", "2001:db8::1"))

        # Chaque troncature : l'élément extérieur dépasse alors son tampon.
        for longueur in range(len(valide)):
            with self.subTest(troncature=longueur):
                self.assertEqual(self.lire(valide[:longueur]), vide)

        # Un octet corrompu à la fois : le résultat peut varier, la levée
        # jamais. Graine fixe : un échec doit se rejouer.
        hasard = random.Random(20261106)
        for _ in range(500):
            octets = bytearray(valide)
            octets[hasard.randrange(len(octets))] = hasard.randrange(256)
            lu = self.lire(bytes(octets))
            self.assertEqual(set(lu), {"expire_le", "adresses"})

        # Du bruit pur, dans un PEM valide.
        for taille in (1, 2, 3, 10, 100, 1000):
            lu = self.lire(bytes(hasard.randrange(256) for _ in range(taille)))
            self.assertEqual(set(lu), {"expire_le", "adresses"})

    def test_fichiers_inutilisables_rendent_vide(self):
        vide = {"expire_le": None, "adresses": ()}
        chemin = os.path.join(self.dossier, "x.pem")
        contenus = {
            "vide": b"",
            "texte": b"ceci n'est pas un certificat\n",
            "pem sans corps": b"-----BEGIN CERTIFICATE-----\n-----END CERTIFICATE-----\n",
            "base64 invalide": b"-----BEGIN CERTIFICATE-----\n!!!\n-----END CERTIFICATE-----\n",
            "non ascii": "-----BEGIN CERTIFICATE-----\né\n".encode("utf-8"),
        }
        for nom, contenu in contenus.items():
            with self.subTest(cas=nom):
                with open(chemin, "wb") as f:
                    f.write(contenu)
                self.assertEqual(serveur.lire_certificat(chemin), vide)
        # Absent, et un dossier à la place d'un fichier.
        self.assertEqual(serveur.lire_certificat(os.path.join(self.dossier, "absent")), vide)
        self.assertEqual(serveur.lire_certificat(self.dossier), vide)


class VerdictAdresse(unittest.TestCase):
    """Le certificat couvre-t-il encore une adresse de ce PC ? (C4-T3, étape 4)"""

    def test_trois_issues(self):
        boucle = ipaddress.ip_address("127.0.0.1")
        boucle6 = ipaddress.ip_address("::1")
        reseau = ipaddress.ip_address("192.0.2.7")
        reseau6 = ipaddress.ip_address("2001:db8::1")
        appels = []

        def portee(valeur):
            def predicat(adresse):
                appels.append(adresse)
                return valeur
            return predicat

        cas = [
            ((), portee(True), "indéterminé"),
            ((boucle, boucle6), portee(True), "indéterminé"),
            ((boucle, reseau), portee(True), "conforme"),
            ((reseau6,), portee(True), "conforme"),
            ((boucle, reseau, reseau6), portee(False), "adresse changée"),
        ]
        for adresses, predicat, attendu in cas:
            with self.subTest(attendu=attendu, adresses=adresses):
                verdict = serveur.verdict_adresse(adresses, est_portee=predicat)
                self.assertEqual(verdict, attendu)
                self.assertIn(verdict, serveur.VERDICTS_ADRESSE)

        # Les adresses de boucle ne sont jamais soumises au prédicat : le PC
        # les porte toujours, elles ne diraient rien d'un changement de box.
        self.assertTrue(appels)
        self.assertFalse([a for a in appels if a.is_loopback])

    def test_une_seule_adresse_portee_suffit(self):
        a, b = ipaddress.ip_address("192.0.2.7"), ipaddress.ip_address("192.0.2.8")
        self.assertEqual(
            serveur.verdict_adresse((a, b), est_portee=lambda x: x == b), "conforme")

    def test_les_trois_verdicts_sont_les_trois_attendus(self):
        self.assertEqual(len(serveur.VERDICTS_ADRESSE), 3)

    def test_bind_reel(self):
        # Aucun paquet n'est émis : on demande au système si l'adresse est
        # celle d'une de ses interfaces. 192.0.2.1 est TEST-NET-1 (RFC 5737),
        # réservée à la documentation, donc jamais portée par un PC.
        self.assertTrue(serveur.adresse_portee("127.0.0.1"))
        self.assertTrue(serveur.adresse_portee(ipaddress.ip_address("127.0.0.1")))
        self.assertFalse(serveur.adresse_portee("192.0.2.1"))
        self.assertFalse(serveur.adresse_portee(ipaddress.ip_address("192.0.2.1")))
        self.assertFalse(serveur.adresse_portee("pas une adresse"))

    def test_bind_reel_ipv6(self):
        try:
            with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as essai:
                essai.bind(("::1", 0))
        except OSError:
            self.skipTest("pas de pile IPv6 sur cette machine")
        self.assertTrue(serveur.adresse_portee("::1"))
        # 2001:db8::/32 : plage de documentation (RFC 3849).
        self.assertFalse(serveur.adresse_portee("2001:db8::1"))

    def test_la_socket_d_essai_est_fermee(self):
        creees = []
        reelle = socket.socket

        def espion(*args, **kwargs):
            s = reelle(*args, **kwargs)
            creees.append(s)
            return s

        with unittest.mock.patch.object(serveur.socket, "socket", espion):
            serveur.adresse_portee("127.0.0.1")
            serveur.adresse_portee("192.0.2.1")
        self.assertEqual(len(creees), 2)
        self.assertTrue(all(s.fileno() == -1 for s in creees))


def problemes_adresse_client(source):
    """Défauts de la source vis-à-vis de l'adresse du client : liste vide si
    aucun. Une fonction introuvable est un défaut, jamais un succès à vide
    (une garde qui ne trouve rien ne garde rien).

    Suit, de proche en proche, toute fonction de module appelée par les
    quatre fonctions de la page : une adresse glissée dans une aide serait
    sinon invisible.
    """
    arbre = ast.parse(source)
    modulaires = {n.name: n for n in arbre.body if isinstance(n, ast.FunctionDef)}
    classes = [n for n in arbre.body
               if isinstance(n, ast.ClassDef) and n.name == "Gestionnaire"]
    methodes = {n.name: n for n in classes[0].body
                if isinstance(n, ast.FunctionDef)} if classes else {}

    problemes = []
    a_voir = []
    for nom in ("construire_etat", "rendre_etat_html", "rendre_etat_json"):
        if nom in modulaires:
            a_voir.append(modulaires[nom])
        else:
            problemes.append("fonction introuvable : " + nom)
    if "repondre_etat" in methodes:
        a_voir.append(methodes["repondre_etat"])
    else:
        problemes.append("méthode introuvable : Gestionnaire.repondre_etat")

    vus = set()
    while a_voir:
        fonction = a_voir.pop()
        if fonction.name in vus:
            continue
        vus.add(fonction.name)
        for noeud in ast.walk(fonction):
            if (isinstance(noeud, ast.Attribute)
                    and noeud.attr in ("client_address", "address_string")):
                problemes.append("{} lit {} (ligne {})".format(
                    fonction.name, noeud.attr, noeud.lineno))
            if isinstance(noeud, ast.Name) and noeud.id in modulaires:
                a_voir.append(modulaires[noeud.id])
    return problemes


def feuilles_texte(valeur):
    """Toutes les chaînes d'une structure imbriquée, par parcours."""
    if isinstance(valeur, str):
        yield valeur
    elif isinstance(valeur, dict):
        for v in valeur.values():
            for feuille in feuilles_texte(v):
                yield feuille
    elif isinstance(valeur, (list, tuple)):
        for v in valeur:
            for feuille in feuilles_texte(v):
                yield feuille


class PageEtat(unittest.TestCase):
    """La page de diagnostic GET /etat (C4-T3) : construction et rendus.

    Les fonctions testées ne reçoivent pas le gestionnaire de requête ;
    technique.log est redirigé vers un dossier temporaire, comme pour
    JournalTechnique : la racine du projet peut héberger celui d'un cabinet.
    """

    def setUp(self):
        self.dossier = tempfile.mkdtemp(prefix="bilan-test-etat-")
        self.addCleanup(shutil.rmtree, self.dossier, ignore_errors=True)
        self.technique = os.path.join(self.dossier, "technique.log")
        for nom, valeur in (("TECHNIQUE", self.technique),
                            ("JOURNAL", os.path.join(self.dossier, "journal.log")),
                            ("JOURNAL_TECHNIQUE_ACTIF", True),
                            ("VERSION_EN_COURS", None), ("DEMARRE_LE", None),
                            ("DERNIER_DEPOT", None), ("CERTIFICAT_CHARGE", None)):
            patch = unittest.mock.patch.object(serveur, nom, valeur)
            patch.start()
            self.addCleanup(patch.stop)

    def ecrire_journal(self, lignes, chemin=None, fin="\n"):
        with open(chemin or self.technique, "w", encoding="utf-8", newline="") as f:
            f.write("".join(ligne + fin for ligne in lignes))

    def config(self):
        return copy.deepcopy(serveur.CONFIG_DEFAUT)

    # --- vocabulaire ---------------------------------------------------------

    def test_classe_route_etat(self):
        self.assertEqual(serveur.classe_route("/etat"), "etat")
        self.assertIn(serveur.classe_route("/etat"), serveur.ROUTES_TECHNIQUES)
        self.assertIn("etat", serveur.ROUTES_TECHNIQUES)
        # Seule la route exacte : un fichier du formulaire ne devient pas "etat".
        self.assertEqual(serveur.classe_route("/etat.html"), "formulaire")
        self.assertEqual(serveur.classe_route("/etats"), "autre")

    def test_interrupteur_par_defaut(self):
        self.assertIs(serveur.CONFIG_DEFAUT["page_etat"], True)

    def test_quatorze_cles_horodatage_inclus(self):
        # Neuf depuis C4-T3, cinq de plus (maj_*) depuis C5-T2a.
        self.assertEqual(len(serveur.CLES_ETAT), 14)
        self.assertEqual(len(set(serveur.CLES_ETAT)), 14)
        self.assertTrue(serveur.CHAMPS_ETAT_HORODATES <= set(serveur.CLES_ETAT))
        self.assertIn("maj_le", serveur.CHAMPS_ETAT_HORODATES)

    def test_explications_couvrent_les_verdicts(self):
        self.assertEqual(set(serveur.EXPLICATIONS_ADRESSE), serveur.VERDICTS_ADRESSE)

    def test_identite_renseignee(self):
        config = self.config()
        self.assertFalse(serveur.identite_renseignee(config))
        config["cabinet"]["praticien"] = "   "
        self.assertFalse(serveur.identite_renseignee(config))
        config["cabinet"]["praticien"] = "Dr Témoin"
        self.assertTrue(serveur.identite_renseignee(config))

    # --- la queue du journal technique ---------------------------------------

    def test_queue_bornee(self):
        lignes = ["2026-11-06T10:00:00 REPONSE methode=GET route=formulaire code=200 n={}".format(i)
                  for i in range(200)]
        self.ecrire_journal(lignes)
        rendu = serveur.dernieres_lignes_techniques()
        self.assertEqual(rendu, lignes[-serveur.LIGNES_ETAT:])
        self.assertEqual(len(rendu), 30)

    def test_queue_d_un_fichier_d_un_mo(self):
        # 1 Mo : seule la fin compte, et le début n'est jamais lu en entier.
        ligne = "2026-11-06T10:00:00 REPONSE methode=GET route=formulaire code=200 n={:07d}"
        lignes = [ligne.format(i) for i in range(14000)]
        self.ecrire_journal(lignes)
        self.assertGreater(os.path.getsize(self.technique), 1024 * 1024)
        octets_lus = []
        reel = open

        def espion(chemin, *args, **kwargs):
            f = reel(chemin, *args, **kwargs)
            lire = f.read
            def lire_et_compter(*a):
                donnees = lire(*a)
                octets_lus.append(len(donnees))
                return donnees
            f.read = lire_et_compter
            return f

        with unittest.mock.patch("builtins.open", espion):
            rendu = serveur.dernieres_lignes_techniques()
        self.assertEqual(rendu, lignes[-30:])
        self.assertLessEqual(sum(octets_lus), serveur.QUEUE_ETAT_OCTETS)

    def test_queue_ecarte_la_ligne_coupee(self):
        lignes = ["2026-11-06T10:00:00 REPONSE n={:04d}".format(i) for i in range(400)]
        self.ecrire_journal(lignes)
        with unittest.mock.patch.object(serveur, "QUEUE_ETAT_OCTETS", 200), \
             unittest.mock.patch.object(serveur, "LIGNES_ETAT", 1000):
            rendu = serveur.dernieres_lignes_techniques()
        self.assertGreater(len(rendu), 3)
        # Toutes complètes, y compris la première, et contiguës jusqu'à la fin.
        self.assertEqual(rendu, lignes[-len(rendu):])

    def test_queue_fichier_court_garde_sa_premiere_ligne(self):
        lignes = ["2026-11-06T10:00:00 DEMARRAGE", "2026-11-06T10:00:01 DEPOT ok 5 octets"]
        self.ecrire_journal(lignes)
        self.assertEqual(serveur.dernieres_lignes_techniques(), lignes)

    def test_queue_fins_de_ligne_windows(self):
        lignes = ["2026-11-06T10:00:00 A", "2026-11-06T10:00:01 B"]
        self.ecrire_journal(lignes, fin="\r\n")
        self.assertEqual(serveur.dernieres_lignes_techniques(), lignes)

    def test_queue_absente(self):
        self.assertFalse(os.path.exists(self.technique))
        self.assertEqual(serveur.dernieres_lignes_techniques(), [])

    def test_queue_vide(self):
        self.ecrire_journal([])
        self.assertEqual(serveur.dernieres_lignes_techniques(), [])

    def test_queue_desactivee(self):
        self.ecrire_journal(["2026-11-06T10:00:00 DEMARRAGE"])
        with unittest.mock.patch.object(serveur, "JOURNAL_TECHNIQUE_ACTIF", False):
            self.assertIsNone(serveur.dernieres_lignes_techniques())

    def test_queue_octets_invalides_sans_levee(self):
        with open(self.technique, "wb") as f:
            f.write(b"2026-11-06T10:00:00 TLS_REFUSE raison=\xff\xfe\n2026-11-06T10:00:01 B\n")
        rendu = serveur.dernieres_lignes_techniques()
        self.assertEqual(len(rendu), 2)
        self.assertEqual(rendu[1], "2026-11-06T10:00:01 B")

    def test_queue_ne_lit_ni_archive_ni_journal_nominatif(self):
        self.ecrire_journal(["2026-11-06T10:00:00 DEMARRAGE"])
        self.ecrire_journal(["2026-11-06T10:00:00 192.0.2.9 NOMINATIF"], self.technique + ".1")
        self.ecrire_journal(["2026-11-06T10:00:00 192.0.2.9 NOMINATIF"], serveur.JOURNAL)
        rendu = serveur.dernieres_lignes_techniques()
        self.assertEqual(rendu, ["2026-11-06T10:00:00 DEMARRAGE"])

    def test_queue_prend_le_verrou_des_journaux(self):
        # Sans le verrou, elle pourrait ouvrir le fichier au milieu d'une
        # rotation, qui le renomme. Le verrou n'est pas réentrant : on le
        # tient ici depuis ce fil, et la lecture doit attendre dans un autre.
        self.ecrire_journal(["2026-11-06T10:00:00 DEMARRAGE"])
        resultat = []
        fil = threading.Thread(
            target=lambda: resultat.append(serveur.dernieres_lignes_techniques()))
        with serveur._verrou_journal:
            fil.start()
            fil.join(0.3)
            self.assertTrue(fil.is_alive(), "lecture sans le verrou des journaux")
        fil.join(10)
        self.assertFalse(fil.is_alive())
        self.assertEqual(resultat, [["2026-11-06T10:00:00 DEMARRAGE"]])

    # --- construction ----------------------------------------------------------

    def test_cles_exactes(self):
        etat = serveur.construire_etat(self.config(), self.dossier)
        self.assertEqual(set(etat), set(serveur.CLES_ETAT))
        self.assertEqual(list(etat), list(serveur.CLES_ETAT))
        self.assertLessEqual(serveur.CHAMPS_ETAT_HORODATES, set(etat))

    def test_valeurs_par_defaut_avant_demarrage(self):
        etat = serveur.construire_etat(self.config(), self.dossier)
        self.assertEqual(etat["version"], serveur.VERSION_INCONNUE)
        self.assertIsNone(etat["demarre_le"])
        # Serveur neuf : aucun dépôt depuis le démarrage.
        self.assertIsNone(etat["dernier_depot"])
        self.assertIsNone(etat["certificat_expire_le"])
        self.assertEqual(etat["certificat_empreinte"], "indisponible")
        self.assertEqual(etat["certificat_adresse"], "indéterminé")
        self.assertIs(etat["identite_cabinet"], False)
        self.assertIsInstance(etat["disque_libre_octets"], int)
        self.assertEqual(etat["journal_technique"], [])

    def test_valeurs_posees_au_demarrage(self):
        fin = datetime.datetime(2029, 2, 3, 4, 5, 6, tzinfo=UTC)
        charge = {"expire_le": fin, "adresses": (ipaddress.ip_address("127.0.0.1"),),
                  "empreinte": "0123456789abcdef"}
        with unittest.mock.patch.object(serveur, "VERSION_EN_COURS", "9.8.7"), \
             unittest.mock.patch.object(serveur, "DEMARRE_LE", "2026-11-06T08:00:00"), \
             unittest.mock.patch.object(serveur, "DERNIER_DEPOT", "2026-11-06T09:30:00"), \
             unittest.mock.patch.object(serveur, "CERTIFICAT_CHARGE", charge):
            config = self.config()
            config["cabinet"]["praticien"] = "Dr Témoin"
            etat = serveur.construire_etat(config, self.dossier)
        self.assertEqual(etat["version"], "9.8.7")
        self.assertEqual(etat["demarre_le"], "2026-11-06T08:00:00")
        self.assertEqual(etat["dernier_depot"], "2026-11-06T09:30:00")
        self.assertEqual(etat["certificat_expire_le"], "2029-02-03T04:05:06Z")
        self.assertEqual(etat["certificat_empreinte"], "0123456789abcdef")
        self.assertEqual(etat["certificat_adresse"], "indéterminé")
        self.assertIs(etat["identite_cabinet"], True)

    def test_disque_libre_est_celui_du_dossier(self):
        libre = shutil.disk_usage(self.dossier).free
        etat = serveur.construire_etat(self.config(), self.dossier)
        # Le disque bouge entre les deux lectures : même ordre de grandeur.
        self.assertLess(abs(etat["disque_libre_octets"] - libre), 1024 ** 3)

    def test_disque_indisponible_ne_divulgue_rien(self):
        absent = os.path.join(self.dossier, "Dupont-Léa-introuvable")
        etat = serveur.construire_etat(self.config(), absent)
        self.assertIsNone(etat["disque_libre_octets"])
        for rendu in (serveur.rendre_etat_json(etat), serveur.rendre_etat_html(etat)):
            self.assertNotIn("Dupont", rendu)
            self.assertNotIn(self.dossier, rendu)
            self.assertNotIn("Errno", rendu)

    # --- rendus --------------------------------------------------------------

    def etat_complet(self, **remplacements):
        etat = {
            "version": "1.1.0", "demarre_le": "2026-11-06T08:00:00",
            "dernier_depot": "2026-11-06T09:30:00",
            "disque_libre_octets": int(12.34 * 1024 ** 3),
            "certificat_expire_le": "2029-02-03T04:05:06Z",
            "certificat_empreinte": "0123456789abcdef",
            "certificat_adresse": "conforme", "identite_cabinet": True,
            "maj_etape": "repos", "maj_resultat": "appliquee", "maj_code": None,
            "maj_le": "2026-11-06T03:00:00", "maj_version": "1.2.0",
            "journal_technique": ["2026-11-06T08:00:00 DEMARRAGE version=1.1.0"],
        }
        etat.update(remplacements)
        self.assertEqual(set(etat), set(serveur.CLES_ETAT))
        return etat

    def test_json_aller_retour(self):
        etat = self.etat_complet(journal_technique=["2026-11-06T08:00:00 TLS_REFUSE é"])
        rendu = serveur.rendre_etat_json(etat)
        self.assertEqual(json.loads(rendu), etat)
        self.assertIn("é", rendu)       # ensure_ascii=False

    def test_html_echappe(self):
        piege = '2026-11-06T08:00:00 TLS_REFUSE raison=<script>alert(1)</script>'
        for etat in (self.etat_complet(journal_technique=[piege]),
                     self.etat_complet(certificat_empreinte="<script>x</script>",
                                       version="<img src=x onerror=y>",
                                       certificat_adresse="<script>")):
            with self.subTest(etat=etat["journal_technique"]):
                page = serveur.rendre_etat_html(etat)
                self.assertNotIn("<script", page.lower())
                self.assertNotIn("<img", page.lower())
        page = serveur.rendre_etat_html(self.etat_complet(journal_technique=[piege]))
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)

    def test_html_autonome(self):
        page = serveur.rendre_etat_html(self.etat_complet())
        minuscules = page.lower()
        self.assertIn('<html lang="fr">', page)
        self.assertIn('<meta charset="utf-8">', page)
        self.assertNotIn("<script", minuscules)
        for ressource in ("http://", "https://", "src=", "href=", "@import", "url("):
            self.assertNotIn(ressource, minuscules)
        # Le dossier est nommé par son rôle, jamais par son chemin.
        self.assertIn("dossier des PDF", page)

    def test_html_espace_en_go_a_virgule(self):
        page = serveur.rendre_etat_html(self.etat_complet())
        self.assertIn("12,3 Go", page)
        page = serveur.rendre_etat_html(self.etat_complet(disque_libre_octets=None))
        self.assertNotIn(" Go", page)

    def test_html_certificat_jours_restants(self):
        maintenant = datetime.datetime(2029, 1, 4, 4, 5, 6, tzinfo=UTC)
        cas = [
            ("2029-02-03T04:05:06Z", "dans 30 jours", False),
            ("2029-02-02T04:05:06Z", "dans 29 jours", True),
            ("2029-01-05T04:05:06Z", "dans 1 jour", True),
            ("2029-01-03T04:05:06Z", "expiré", None),
        ]
        for expire, attendu, a_renouveler in cas:
            with self.subTest(expire=expire):
                page = serveur.rendre_etat_html(
                    self.etat_complet(certificat_expire_le=expire), maintenant)
                self.assertIn(attendu, page)
                if a_renouveler is not None:
                    self.assertEqual("à renouveler" in page, a_renouveler)
        page = serveur.rendre_etat_html(
            self.etat_complet(certificat_expire_le=None), maintenant)
        self.assertIn("inconnue", page)

    def test_rendus_avec_valeurs_nulles(self):
        etat = self.etat_complet(
            demarre_le=None, dernier_depot=None, disque_libre_octets=None,
            certificat_expire_le=None, journal_technique=None,
            identite_cabinet=False)
        self.assertEqual(json.loads(serveur.rendre_etat_json(etat)), etat)
        page = serveur.rendre_etat_html(etat)
        self.assertIn("aucun depuis le démarrage", page)
        self.assertIn("Désactivé", page)
        self.assertIn("export des bilans est refusé", page)
        vide = self.etat_complet(journal_technique=[])
        self.assertIn("Aucune ligne", serveur.rendre_etat_html(vide))

    def test_html_dit_chaque_verdict(self):
        for verdict in sorted(serveur.VERDICTS_ADRESSE):
            with self.subTest(verdict=verdict):
                page = serveur.rendre_etat_html(
                    self.etat_complet(certificat_adresse=verdict))
                self.assertIn(verdict, page)

    # --- aucune donnée de configuration ----------------------------------------

    def test_aucune_valeur_de_configuration(self):
        # La configuration est dérivée de CONFIG_DEFAUT, chaque feuille texte
        # remplacée par une sentinelle : une clé ajoutée plus tard au défaut
        # est couverte sans qu'on y pense. Le parcours est celui de
        # feuilles_texte, jamais une liste de clés écrite à la main.
        config = self.config()

        def sentinelles(noeud, chemin):
            for cle in list(noeud):
                if isinstance(noeud[cle], dict):
                    sentinelles(noeud[cle], chemin + cle + "-")
                elif isinstance(noeud[cle], str):
                    noeud[cle] = "SENTINELLE-{}{}-xq7".format(chemin, cle)

        sentinelles(config, "")
        config["dossier_pdf"] = os.path.join(self.dossier, "SENTINELLE-dossier-xq7")
        feuilles = [f for f in feuilles_texte(config) if len(f) >= 6]
        # Ancrage : sans lui, une config vide validerait la garde à vide.
        self.assertGreaterEqual(len(feuilles), 10)
        self.assertTrue(all(f.startswith(("SENTINELLE", self.dossier)) for f in feuilles))

        etat = serveur.construire_etat(config, config["dossier_pdf"])
        self.assertIs(etat["identite_cabinet"], True)
        for rendu in (serveur.rendre_etat_json(etat), serveur.rendre_etat_html(etat)):
            for feuille in feuilles:
                with self.subTest(feuille=feuille):
                    self.assertNotIn(feuille, rendu)

    # --- gardes statiques ------------------------------------------------------

    def source_serveur(self):
        with open(serveur.__file__, encoding="utf-8") as f:
            return f.read()

    def test_garde_statique_sans_adresse_client(self):
        self.assertEqual(problemes_adresse_client(self.source_serveur()), [])

    def test_garde_statique_mise_en_echec(self):
        # Une garde qui ne mord pas ne garde rien : elle doit rougir sur une
        # adresse dans chacune des quatre fonctions, dans une aide appelée,
        # et sur une fonction introuvable.
        source = self.source_serveur()
        mutations = {
            "construire_etat": ("def construire_etat(config, dossier_pdf):\n",
                                "    x = self.client_address\n"),
            "rendre_etat_html": ("def rendre_etat_html(etat, maintenant=None):\n",
                                 "    x = self.address_string()\n"),
            "rendre_etat_json": ("def rendre_etat_json(etat):\n",
                                 "    x = self.client_address[0]\n"),
            "repondre_etat": ("    def repondre_etat(self, avec_corps):\n",
                              "        x = self.client_address[0]\n"),
            "_go": ("def _go(octets):\n", "    x = octets.client_address\n"),
        }
        for nom, (entete, ligne) in mutations.items():
            with self.subTest(fonction=nom):
                self.assertEqual(source.count(entete), 1)
                muee = source.replace(entete, entete + ligne)
                self.assertTrue(problemes_adresse_client(muee))
        for nom in ("construire_etat", "rendre_etat_html", "rendre_etat_json"):
            with self.subTest(introuvable=nom):
                renommee = source.replace("def {}(".format(nom), "def x_{}(".format(nom))
                self.assertTrue(problemes_adresse_client(renommee))
        renommee = source.replace("def repondre_etat(", "def x_repondre_etat(")
        self.assertTrue(problemes_adresse_client(renommee))

    def test_etat_construit_avant_send_response(self):
        # L'état se construit avant send_response(), qui journalise donc prend
        # le verrou des journaux (non réentrant) que la lecture de la queue
        # prend aussi.
        arbre = ast.parse(self.source_serveur())
        methode = [n for c in arbre.body
                   if isinstance(c, ast.ClassDef) and c.name == "Gestionnaire"
                   for n in c.body
                   if isinstance(n, ast.FunctionDef) and n.name == "repondre_etat"]
        self.assertEqual(len(methode), 1)
        lignes = {}
        for noeud in ast.walk(methode[0]):
            if isinstance(noeud, ast.Call):
                f = noeud.func
                nom = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
                lignes.setdefault(nom, []).append(noeud.lineno)
        for nom in ("authentifie", "construire_etat", "send_response"):
            self.assertIn(nom, lignes)
        self.assertLess(max(lignes["authentifie"]), min(lignes["construire_etat"]))
        self.assertLess(max(lignes["construire_etat"]), min(lignes["send_response"]))

    def test_aucun_import_hors_bibliotheque_standard_ajoute(self):
        # Garde du critère 16, jouable sur toute version : le code qui tourne au
        # cabinet n'importe que des modules fournis avec Python. Depuis C5-T1 elle
        # couvre TOUS les modules de serveur/ : un `import cryptography` glissé
        # dans paquet_signe.py (le vérificateur) casserait l'installation au
        # cabinet, qui n'a pas ce module. Seul generer_autorite.py, qui fabrique
        # les certificats hors du chemin d'exécution du serveur, en est exempté,
        # et par son NOM.
        standard = getattr(sys, "stdlib_module_names", None)
        if standard is None:
            self.skipTest("sys.stdlib_module_names absent avant Python 3.10")
        dossier = os.path.dirname(os.path.abspath(serveur.__file__))
        modules_du_dossier = {os.path.splitext(n)[0] for n in os.listdir(dossier)
                              if n.endswith(".py")}
        controles = sorted(n for n in os.listdir(dossier)
                           if n.endswith(".py") and n != EXEMPTE_DE_LA_GARDE_STDLIB)
        self.assertIn("serveur.py", controles)
        self.assertIn("paquet_signe.py", controles)
        self.assertIn("signature_ed25519.py", controles)
        for nom in controles:
            with open(os.path.join(dossier, nom), encoding="utf-8") as f:
                source = f.read()
            with self.subTest(module=nom):
                self.assertEqual(
                    imports_hors_bibliotheque_standard(
                        source, standard, modules_du_dossier), [])

    def test_la_garde_stdlib_mord_et_l_exemption_est_justifiee(self):
        standard = getattr(sys, "stdlib_module_names", None)
        if standard is None:
            self.skipTest("sys.stdlib_module_names absent avant Python 3.10")
        # Mise en échec de la garde elle-même : elle doit voir un import tiers,
        # sous toutes ses formes, et laisser passer un module voisin.
        for source in ("import cryptography\n", "import os, cryptography.x509\n",
                       "from cryptography import x509\n",
                       "def f():\n    import cryptography\n"):
            with self.subTest(source=source):
                self.assertEqual(
                    imports_hors_bibliotheque_standard(source, standard, set()),
                    ["cryptography"])
        self.assertEqual(
            imports_hors_bibliotheque_standard(
                "import paquet_signe\nimport json\n", standard, {"paquet_signe"}), [])
        # L'exemption n'est pas gratuite : generer_autorite.py importe bien
        # cryptography. Si ce n'était plus le cas, l'exemption n'aurait plus lieu d'être.
        dossier = os.path.dirname(os.path.abspath(serveur.__file__))
        with open(os.path.join(dossier, EXEMPTE_DE_LA_GARDE_STDLIB), encoding="utf-8") as f:
            self.assertEqual(
                imports_hors_bibliotheque_standard(f.read(), standard, set()),
                ["cryptography"])


# --------------------------------------------------------------------------
# Mise à jour (C5-T2a) : arrêt concerté, état, vocabulaire
# --------------------------------------------------------------------------

JETON = "ab" * 16


def demande_arret(calme=120, demarrage=False, jeton=JETON):
    return {"jeton": jeton, "calme_secondes": calme, "demarrage": demarrage}


class DeciderArret(unittest.TestCase):
    """`decider_arret` : fonction pure, jouée en table (A14)."""

    def test_table(self):
        # (demande, dépôts, dernière activité, démarré depuis, maintenant) -> verdict
        cas = [
            ("dépôt en cours refuse, même sans activité", demande_arret(0), 1, None, 10, 1000,
             ("refuse", "depot-en-cours")),
            ("dépôt en cours refuse, même très calme", demande_arret(0), 3, 0.0, 10, 5000,
             ("refuse", "depot-en-cours")),
            ("aucune activité : accepte", demande_arret(120), 0, None, 10, 1000,
             ("accepte", "aucun")),
            ("activité 1 s avant : refuse", demande_arret(120), 0, 999.0, 10, 1000.0,
             ("refuse", "activite")),
            ("activité 119 s avant, calme 120 : refuse", demande_arret(120), 0, 881.0, 10,
             1000.0, ("refuse", "activite")),
            ("activité exactement 120 s avant : accepte (borne incluse)", demande_arret(120),
             0, 880.0, 10, 1000.0, ("accepte", "aucun")),
            ("activité 121 s avant : accepte", demande_arret(120), 0, 879.0, 10, 1000.0,
             ("accepte", "aucun")),
            ("calme 0 : accepte juste après une requête", demande_arret(0), 0, 1000.0, 10,
             1000.0, ("accepte", "aucun")),
            ("calme maximal 86400", demande_arret(86400), 0, 1000.0, 10, 1000.0 + 86399,
             ("refuse", "activite")),
            ("calme maximal atteint", demande_arret(86400), 0, 1000.0, 10, 1000.0 + 86400,
             ("accepte", "aucun")),
            ("démarrage, rien reçu, 0 s : accepte", demande_arret(0, True), 0, None, 0, 5.0,
             ("accepte", "aucun")),
            ("démarrage, rien reçu, 900 s : accepte (borne incluse)", demande_arret(0, True),
             0, None, 900, 5000.0, ("accepte", "aucun")),
            ("démarrage, rien reçu, 900,5 s : dépassé", demande_arret(0, True), 0, None,
             900.5, 5000.0, ("refuse", "demarrage-depasse")),
            ("démarrage, rien reçu, 3600 s : dépassé", demande_arret(0, True), 0, None, 3600,
             5000.0, ("refuse", "demarrage-depasse")),
            ("démarrage, une requête reçue : refuse", demande_arret(0, True), 0, 5.0, 100,
             5000.0, ("refuse", "activite")),
            ("démarrage, requête ancienne, calme respecté : refuse quand même",
             demande_arret(0, True), 0, 1.0, 100, 9999.0, ("refuse", "activite")),
            ("démarrage, requête et délai dépassé : le délai d'abord",
             demande_arret(0, True), 0, 5.0, 1000, 5000.0, ("refuse", "demarrage-depasse")),
            ("démarrage, dépôt en cours : le dépôt d'abord", demande_arret(0, True), 1, None,
             10, 5000.0, ("refuse", "depot-en-cours")),
        ]
        for nom, demande, depots, activite, depuis, maintenant, attendu in cas:
            with self.subTest(nom):
                self.assertEqual(
                    serveur.decider_arret(demande, depots, activite, depuis, maintenant),
                    attendu)
        self.assertGreaterEqual(len(cas), 12)

    def test_demandes_invalides(self):
        invalides = [
            None, [], "x", 3, {},
            {"jeton": JETON, "calme_secondes": 0},
            dict(demande_arret(), supplement=1),
            demande_arret(jeton="AB" * 16),
            demande_arret(jeton="ab" * 15),
            demande_arret(jeton="ab" * 17),
            demande_arret(jeton="zz" * 16),
            demande_arret(jeton=12),
            demande_arret(calme=-1),
            demande_arret(calme=86401),
            demande_arret(calme=True),
            demande_arret(calme=1.5),
            demande_arret(calme="120"),
            demande_arret(demarrage=1),
            demande_arret(demarrage="oui"),
        ]
        for demande in invalides:
            with self.subTest(demande=demande):
                self.assertFalse(serveur.demande_arret_valide(demande))
                self.assertEqual(serveur.decider_arret(demande, 0, None, 0, 1.0),
                                 ("refuse", "demande-invalide"))
        self.assertTrue(serveur.demande_arret_valide(demande_arret(0)))
        self.assertTrue(serveur.demande_arret_valide(demande_arret(86400, True)))

    def test_motifs_et_verdicts_du_contrat(self):
        for motif in ("aucun", "depot-en-cours", "activite", "demarrage-depasse",
                      "demande-invalide"):
            self.assertIn(motif, serveur.MOTIFS_ARRET)
        self.assertEqual(len(serveur.MOTIFS_ARRET), 5)


class SurveillanceDeLArret(unittest.TestCase):
    """Un passage de la surveillance sur un dossier jetable : le serveur lit,
    répond et efface ; il ne crée jamais le dossier."""

    def setUp(self):
        self.dossier = tempfile.mkdtemp(prefix="bilan-test-arret-")
        self.addCleanup(shutil.rmtree, self.dossier, ignore_errors=True)
        self.demande = os.path.join(self.dossier, serveur.DEMANDE_ARRET)
        self.reponse = os.path.join(self.dossier, serveur.REPONSE_ARRET)
        for nom, valeur in (("DEPOTS_EN_COURS", 0), ("DERNIERE_ACTIVITE", None)):
            patch = unittest.mock.patch.object(serveur, nom, valeur)
            patch.start()
            self.addCleanup(patch.stop)
        if os.name == "nt":
            # Un dossier jetable n'y est pas réservé aux administrateurs ; la
            # vérification réelle est éprouvée par tests/test_maj_windows.py.
            patch = unittest.mock.patch.object(
                serveur, "dossier_reserve_de_confiance", lambda dossier: True)
            patch.start()
            self.addCleanup(patch.stop)

    def poser(self, contenu, mode="w"):
        with open(self.demande, mode) as f:
            f.write(contenu)

    def passer(self, depuis=10):
        arret = serveur.ArretConcerte()
        return serveur.traiter_demande_arret(self.dossier, arret, depuis), arret

    def lire_reponse(self):
        with open(self.reponse) as f:
            return json.load(f)

    def test_demande_acceptee(self):
        self.poser(json.dumps(demande_arret(0)))
        accepte, arret = self.passer()
        self.assertTrue(accepte)
        self.assertEqual(arret.jeton, JETON)
        self.assertEqual(self.lire_reponse(), {"jeton": JETON, "verdict": "accepte",
                                               "motif": "aucun"})
        self.assertFalse(os.path.exists(self.demande))

    def test_demande_refusee_pendant_un_depot(self):
        self.poser(json.dumps(demande_arret(0)))
        with unittest.mock.patch.object(serveur, "DEPOTS_EN_COURS", 1):
            accepte, arret = self.passer()
        self.assertFalse(accepte)
        self.assertIsNone(arret.jeton)
        self.assertEqual(self.lire_reponse()["motif"], "depot-en-cours")
        self.assertFalse(os.path.exists(self.demande))

    def test_aucune_demande(self):
        accepte, _ = self.passer()
        self.assertFalse(accepte)
        self.assertFalse(os.path.exists(self.reponse))

    def test_demandes_ignorees_et_effacees(self):
        cas = {
            "malformée": lambda: self.poser("{pas du json"),
            "tronquée": lambda: self.poser('{"jeton": "' + JETON),
            "sans jeton": lambda: self.poser(json.dumps(
                {"calme_secondes": 0, "demarrage": False})),
            "jeton inconnu": lambda: self.poser(json.dumps(demande_arret(jeton="zz"))),
            "clé en double": lambda: self.poser(
                '{"jeton": "%s", "jeton": "%s", "calme_secondes": 0, "demarrage": false}'
                % (JETON, JETON)),
            "NaN": lambda: self.poser(
                '{"jeton": "%s", "calme_secondes": NaN, "demarrage": false}' % JETON),
            "2 Kio": lambda: self.poser(json.dumps(dict(demande_arret(0), x="y" * 2048))),
            "octets invalides": lambda: self.poser(b"\xff\xfe\x00", mode="wb"),
            "vide": lambda: self.poser(""),
            "dossier": lambda: os.mkdir(self.demande),
        }
        for nom, poser in cas.items():
            with self.subTest(nom):
                poser()
                accepte, arret = self.passer()
                self.assertFalse(accepte)
                self.assertIsNone(arret.jeton)
                self.assertFalse(os.path.lexists(self.demande))
                self.assertFalse(os.path.exists(self.reponse))

    def test_forme_invalide_mais_jeton_lisible_recoit_une_reponse(self):
        self.poser(json.dumps({"jeton": JETON, "calme_secondes": -5, "demarrage": False}))
        accepte, _ = self.passer()
        self.assertFalse(accepte)
        self.assertEqual(self.lire_reponse(), {"jeton": JETON, "verdict": "refuse",
                                               "motif": "demande-invalide"})

    @unittest.skipUnless(hasattr(os, "mkfifo"), "pas de tube nommé sur ce système")
    def test_un_tube_nomme_n_est_jamais_ouvert(self):
        os.mkfifo(self.demande)
        accepte, _ = self.passer()       # bloquerait à l'infini si le tube était ouvert
        self.assertFalse(accepte)
        self.assertFalse(os.path.lexists(self.demande))

    def test_un_lien_n_est_pas_suivi(self):
        cible = os.path.join(self.dossier, "cible.json")
        with open(cible, "w") as f:
            json.dump(demande_arret(0), f)
        try:
            os.symlink(cible, self.demande)
        except (OSError, NotImplementedError):
            self.skipTest("lien symbolique impossible sur ce poste")
        accepte, _ = self.passer()
        self.assertFalse(accepte)
        self.assertFalse(os.path.lexists(self.demande))
        self.assertTrue(os.path.exists(cible))

    def test_le_serveur_ne_cree_pas_le_dossier(self):
        absent = os.path.join(self.dossier, "absent")
        accepte, _ = (serveur.traiter_demande_arret(absent, serveur.ArretConcerte(), 10),
                      None)
        self.assertFalse(accepte)
        serveur.ecrire_reponse_arret(absent, JETON, "refuse", "activite")
        self.assertFalse(os.path.exists(absent))

    def test_demandes_perimees_effacees_au_demarrage(self):
        self.poser(json.dumps(demande_arret(0)))
        with open(self.reponse, "w") as f:
            f.write("{}")
        serveur.effacer_demandes_perimees(self.dossier)
        self.assertEqual(os.listdir(self.dossier), [])

    def test_surveillance_arrete_le_serveur_et_pose_l_evenement(self):
        class FauxServeur(object):
            arrete = False

            def shutdown(self):
                FauxServeur.arrete = True

        self.poser(json.dumps(demande_arret(0)))
        arret = serveur.ArretConcerte()
        fin = threading.Event()
        serveur.surveiller_demande_arret(FauxServeur(), arret, fin, self.dossier)
        self.assertTrue(FauxServeur.arrete)
        self.assertTrue(arret.evenement.is_set())

    def test_surveillance_survit_a_une_exception(self):
        class FauxServeur(object):
            def shutdown(self):
                pass

        appels = []
        fin = threading.Event()

        def instable(dossier, arret, depuis, maintenant=None):
            appels.append(1)
            if len(appels) == 1:
                raise RuntimeError("panne d'essai")
            fin.set()
            return False

        with unittest.mock.patch.object(serveur, "traiter_demande_arret", instable), \
             unittest.mock.patch.object(serveur, "INTERVALLE_SURVEILLANCE_SECONDES", 0.01):
            serveur.surveiller_demande_arret(FauxServeur(), serveur.ArretConcerte(), fin,
                                             self.dossier)
        self.assertEqual(len(appels), 2)

    def test_attendre_fin_depots(self):
        with unittest.mock.patch.object(serveur, "DEPOTS_EN_COURS", 0):
            self.assertTrue(serveur.attendre_fin_depots(0.1))
        with unittest.mock.patch.object(serveur, "DEPOTS_EN_COURS", 2):
            self.assertFalse(serveur.attendre_fin_depots(0.15, pas=0.01))


class CompteursDeDepots(unittest.TestCase):
    """Le compte des dépôts en cours et l'heure de la dernière requête."""

    def setUp(self):
        for nom, valeur in (("DEPOTS_EN_COURS", 0), ("DERNIERE_ACTIVITE", None)):
            patch = unittest.mock.patch.object(serveur, nom, valeur)
            patch.start()
            self.addCleanup(patch.stop)

    def instance(self, chemin):
        gestionnaire = serveur.Gestionnaire.__new__(serveur.Gestionnaire)
        gestionnaire.path = chemin
        return gestionnaire

    def test_la_sonde_de_sante_ne_compte_pas(self):
        for chemin in ("/sante", "/sante?x=1", "/sante#a"):
            with self.subTest(chemin=chemin):
                self.instance(chemin).noter_activite()
                self.assertIsNone(serveur.DERNIERE_ACTIVITE)
        for chemin in ("/", "/cabinet", "/etat", "/depot", "/schema.json", "/santé", "/sante/"):
            with self.subTest(chemin=chemin):
                serveur.DERNIERE_ACTIVITE = None
                self.instance(chemin).noter_activite()
                self.assertIsNotNone(serveur.DERNIERE_ACTIVITE)

    def test_le_compte_couvre_tout_le_traitement_et_retombe_a_zero(self):
        vus = []
        gestionnaire = self.instance("/depot")
        gestionnaire.traiter_post = lambda: vus.append(serveur.lire_compteurs()[0])
        gestionnaire.do_POST()
        self.assertEqual(vus, [1])
        self.assertEqual(serveur.DEPOTS_EN_COURS, 0)

    def test_le_compte_retombe_a_zero_meme_si_le_traitement_leve(self):
        gestionnaire = self.instance("/depot")

        def panne():
            raise RuntimeError("panne d'essai")

        gestionnaire.traiter_post = panne
        with self.assertRaises(RuntimeError):
            gestionnaire.do_POST()
        self.assertEqual(serveur.DEPOTS_EN_COURS, 0)

    def test_la_fin_d_un_depot_note_l_activite(self):
        self.assertIsNone(serveur.DERNIERE_ACTIVITE)
        serveur.entrer_depot()
        self.assertIsNone(serveur.DERNIERE_ACTIVITE)
        serveur.sortir_depot()
        self.assertIsNotNone(serveur.DERNIERE_ACTIVITE)

    def test_gardes_ast_de_do_post_do_get_do_head(self):
        with open(serveur.__file__, encoding="utf-8") as f:
            arbre = ast.parse(f.read())
        methodes = {}
        for classe in arbre.body:
            if isinstance(classe, ast.ClassDef) and classe.name == "Gestionnaire":
                methodes = {n.name: n for n in classe.body if isinstance(n, ast.FunctionDef)}

        def premier_appel(fonction):
            for instruction in fonction.body:
                if isinstance(instruction, ast.Expr) and isinstance(instruction.value, ast.Call):
                    return getattr(instruction.value.func, "attr", None)
            return None

        for nom in ("do_GET", "do_HEAD", "do_POST"):
            with self.subTest(nom):
                self.assertEqual(premier_appel(methodes[nom]), "noter_activite")
        essais = [n for n in methodes["do_POST"].body if isinstance(n, ast.Try)]
        self.assertEqual(len(essais), 1)
        sortie = [getattr(getattr(i.value, "func", None), "id", None)
                  for i in essais[0].finalbody if isinstance(i, ast.Expr)]
        self.assertEqual(sortie, ["sortir_depot"])


class EtatDeLaMiseAJour(unittest.TestCase):
    """Les cinq clés maj_* de /etat, lues dans un fichier écrit par un AUTRE
    processus : validées une à une, jamais recopiées (A13)."""

    def setUp(self):
        self.dossier = tempfile.mkdtemp(prefix="bilan-test-etat-maj-")
        self.addCleanup(shutil.rmtree, self.dossier, ignore_errors=True)
        self.fichier = os.path.join(self.dossier, serveur.ETAT_MAJ)

    def ecrire(self, objet=None, brut=None):
        with open(self.fichier, "wb") as f:
            f.write(brut if brut is not None else json.dumps(objet).encode("utf-8"))

    def lire(self):
        return serveur.lire_etat_maj(self.dossier)

    VALIDE = {"format": 1, "etape": "repos", "resultat": "appliquee", "code": None,
              "le": "2026-11-12T03:14:15", "version": "1.2.0", "de": "1.1.0", "vers": "1.2.0",
              "ecartees": []}

    def illisible(self):
        return {"maj_etape": "illisible", "maj_resultat": None, "maj_code": None,
                "maj_le": None, "maj_version": None}

    def test_etat_valide(self):
        self.ecrire(self.VALIDE)
        self.assertEqual(self.lire(), {
            "maj_etape": "repos", "maj_resultat": "appliquee", "maj_code": None,
            "maj_le": "2026-11-12T03:14:15", "maj_version": "1.2.0"})

    def test_fichier_absent(self):
        self.assertEqual(self.lire(), {"maj_etape": "absente", "maj_resultat": None,
                                       "maj_code": None, "maj_le": None, "maj_version": None})

    def test_dossier_absent(self):
        self.assertEqual(serveur.lire_etat_maj(os.path.join(self.dossier, "x"))["maj_etape"],
                         "absente")

    def test_chaque_etape_du_vocabulaire(self):
        for etape in serveur.ETAPES_MAJ:
            with self.subTest(etape=etape):
                self.ecrire(dict(self.VALIDE, etape=etape))
                self.assertEqual(self.lire()["maj_etape"], etape)

    def test_chaque_resultat_du_vocabulaire(self):
        for resultat in serveur.RESULTATS_MAJ:
            with self.subTest(resultat=resultat):
                self.ecrire(dict(self.VALIDE, resultat=resultat))
                self.assertEqual(self.lire()["maj_resultat"], resultat)

    def test_illisible_et_rien_ailleurs(self):
        mauvais = {
            "tronqué": dict(brut=b'{"etape": "rep'),
            "vide": dict(brut=b""),
            "pas un objet": dict(objet=[1, 2]),
            "clé en double": dict(brut=b'{"etape": "repos", "etape": "bascule"}'),
            "NaN": dict(brut=b'{"etape": "repos", "version": NaN}'),
            "BOM": dict(brut=b"\xef\xbb\xbf" + json.dumps(self.VALIDE).encode()),
            "octets invalides": dict(brut=b"\xff\xfe\x00"),
            "étape hors vocabulaire": dict(objet=dict(self.VALIDE, etape="inconnue")),
            "étape absente": dict(objet={k: v for k, v in self.VALIDE.items() if k != "etape"}),
            "résultat hors vocabulaire": dict(objet=dict(self.VALIDE, resultat="peut-etre")),
            "résultat qui est un chemin": dict(objet=dict(self.VALIDE, resultat="/etc/passwd")),
            "code en minuscules": dict(objet=dict(self.VALIDE, code="signature_invalide")),
            "code trop long": dict(objet=dict(self.VALIDE, code="A" * 41)),
            "code qui porte un chemin": dict(objet=dict(self.VALIDE, code="C:\\Users\\Léa")),
            "code qui porte une adresse": dict(objet=dict(self.VALIDE, code="192.168.1.13")),
            "horodatage hors forme": dict(objet=dict(self.VALIDE, le="hier")),
            "horodatage avec fuseau": dict(objet=dict(self.VALIDE, le="2026-11-12T03:14:15Z")),
            "horodatage avec saut de ligne": dict(objet=dict(self.VALIDE, le="2026-11-12T03:14:15\n")),
            "version avec suffixe": dict(objet=dict(self.VALIDE, version="1.2.0-beta")),
            "version avec chemin": dict(objet=dict(self.VALIDE, version="/srv/1.2.0")),
            "version numérique": dict(objet=dict(self.VALIDE, version=120)),
            "zéro de tête": dict(objet=dict(self.VALIDE, version="01.2.0")),
            "chemin dans un champ": dict(objet=dict(self.VALIDE, code="CHEMIN", version="/a/b")),
        }
        for nom, argument in mauvais.items():
            with self.subTest(nom):
                self.ecrire(**argument)
                self.assertEqual(self.lire(), self.illisible())

    def test_fichier_de_plus_de_16_kio(self):
        self.ecrire(dict(self.VALIDE, remplissage="x" * 17000))
        self.assertGreater(os.path.getsize(self.fichier), 16 * 1024)
        self.assertEqual(self.lire(), self.illisible())

    def test_cles_supplementaires_ne_sont_jamais_recopiees(self):
        self.ecrire(dict(self.VALIDE, chemin="/home/Dupont", ecartees=["1.0.0"]))
        etat = self.lire()
        self.assertEqual(sorted(etat), sorted(k for k in serveur.CLES_ETAT if k.startswith("maj_")))
        self.assertNotIn("Dupont", json.dumps(etat))

    def test_un_dossier_a_la_place_du_fichier(self):
        os.mkdir(self.fichier)
        self.assertEqual(self.lire(), self.illisible())

    def test_un_lien_n_est_pas_lu(self):
        cible = os.path.join(self.dossier, "cible.json")
        with open(cible, "w") as f:
            json.dump(self.VALIDE, f)
        try:
            os.symlink(cible, self.fichier)
        except (OSError, NotImplementedError):
            self.skipTest("lien symbolique impossible sur ce poste")
        self.assertEqual(self.lire(), self.illisible())

    def construire(self):
        with unittest.mock.patch.object(serveur, "DOSSIER_MAJ", self.dossier), \
             unittest.mock.patch.object(serveur, "TECHNIQUE",
                                        os.path.join(self.dossier, "technique.log")):
            return serveur.construire_etat(copy.deepcopy(serveur.CONFIG_DEFAUT), self.dossier)

    def test_construire_etat_porte_les_cinq_cles_dans_l_ordre(self):
        self.ecrire(self.VALIDE)
        etat = self.construire()
        self.assertEqual(list(etat), list(serveur.CLES_ETAT))
        self.assertEqual((etat["maj_etape"], etat["maj_resultat"], etat["maj_version"]),
                         ("repos", "appliquee", "1.2.0"))
        self.assertEqual(etat["maj_le"], "2026-11-12T03:14:15")

    def test_construire_etat_sans_fichier(self):
        self.assertEqual(self.construire()["maj_etape"], "absente")

    def test_construire_etat_ne_recopie_pas_un_fichier_hostile(self):
        self.ecrire(dict(self.VALIDE, code="/home/Dupont/Bilan.pdf"))
        etat = self.construire()
        self.assertEqual(etat["maj_etape"], "illisible")
        for rendu in (serveur.rendre_etat_json(etat), serveur.rendre_etat_html(etat)):
            self.assertNotIn("Dupont", rendu)

    def test_page_html_porte_la_ligne_mise_a_jour_echappee(self):
        etat = self.construire()
        for maj_etape, attendu in (("absente", "aucune mise à jour enregistrée"),
                                   ("illisible", "état illisible")):
            with self.subTest(maj_etape):
                page = serveur.rendre_etat_html(dict(etat, maj_etape=maj_etape))
                self.assertIn("<th>Mise à jour</th>", page)
                self.assertIn(attendu, page)
        page = serveur.rendre_etat_html(dict(
            etat, maj_etape="repos", maj_resultat="appliquee", maj_version="1.2.0",
            maj_le="2026-11-12T03:14:15", maj_code="SANTE_MUETTE"))
        self.assertIn("dernier résultat : appliquee", page)
        self.assertIn("version : 1.2.0", page)
        self.assertIn("code : SANTE_MUETTE", page)
        self.assertIn("le 2026-11-12 03:14:15", page)
        # Même une valeur qui aurait échappé à la validation est échappée.
        piege = serveur.rendre_etat_html(dict(etat, maj_etape="<script>x</script>"))
        self.assertNotIn("<script>x", piege)
        self.assertIn("&lt;script&gt;", piege)

    def test_page_et_json_sans_adresse(self):
        # Le motif du test d'intégration est importé, pas recopié.
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from test_integration import chercher_adresse
        self.ecrire(self.VALIDE)
        etat = self.construire()
        for rendu in (serveur.rendre_etat_json(etat), serveur.rendre_etat_html(etat)):
            self.assertIsNone(chercher_adresse(rendu, ipv6=False))
        for cle in ("maj_etape", "maj_resultat", "maj_code", "maj_version"):
            self.assertIsNone(chercher_adresse(str(etat[cle])))
        self.assertIn("maj_le", serveur.CHAMPS_ETAT_HORODATES)
        # Témoin : la garde mord sur un code qui porterait une adresse.
        self.assertIsNotNone(chercher_adresse("code 192.168.1.13", ipv6=False))


class ObeissanceALaDemandeDArret(unittest.TestCase):
    """Le serveur n'obéit qu'à une demande posée dans un dossier réservé (C5-T2a,
    réaudit) : sinon un programme de la session du cabinet l'arrêterait."""

    def setUp(self):
        # realpath : sous macOS /var est un lien vers /private/var, et la
        # comparaison « résolu / écrit » ne doit pas rougir pour cette seule raison.
        self.dossier = os.path.realpath(tempfile.mkdtemp(prefix="bilan-test-confiance-"))
        self.addCleanup(shutil.rmtree, self.dossier, ignore_errors=True)
        self.demande = os.path.join(self.dossier, serveur.DEMANDE_ARRET)
        for nom, valeur in (("DEPOTS_EN_COURS", 0), ("DERNIERE_ACTIVITE", None),
                            ("_PROTECTION_SIGNALEE", False),
                            ("JOURNAL", os.path.join(self.dossier, "journal.log")),
                            ("TECHNIQUE", os.path.join(self.dossier, "technique.log"))):
            patch = unittest.mock.patch.object(serveur, nom, valeur)
            patch.start()
            self.addCleanup(patch.stop)
        patch = unittest.mock.patch.object(serveur, "ecrire_stderr", lambda ligne: None)
        patch.start()
        self.addCleanup(patch.stop)

    def poser_demande(self):
        with open(self.demande, "w") as f:
            json.dump(demande_arret(0), f)

    def test_demande_dans_un_dossier_qui_n_est_pas_de_confiance_est_ignoree(self):
        self.poser_demande()
        with unittest.mock.patch.object(serveur, "dossier_reserve_de_confiance",
                                        lambda dossier: False):
            arret = serveur.ArretConcerte()
            self.assertFalse(serveur.traiter_demande_arret(self.dossier, arret, 10))
        self.assertIsNone(arret.jeton)
        self.assertFalse(os.path.lexists(self.demande))
        self.assertFalse(os.path.exists(os.path.join(self.dossier, serveur.REPONSE_ARRET)))
        with open(serveur.JOURNAL, encoding="utf-8") as f:
            self.assertIn("demande d'arrêt ignorée", f.read())

    def test_la_meme_demande_est_acceptee_dans_un_dossier_de_confiance(self):
        self.poser_demande()
        with unittest.mock.patch.object(serveur, "dossier_reserve_de_confiance",
                                        lambda dossier: True):
            self.assertTrue(serveur.traiter_demande_arret(
                self.dossier, serveur.ArretConcerte(), 10))

    def test_le_refus_n_est_journalise_qu_une_fois(self):
        with unittest.mock.patch.object(serveur, "dossier_reserve_de_confiance",
                                        lambda dossier: False):
            for _ in range(3):
                self.poser_demande()
                serveur.traiter_demande_arret(self.dossier, serveur.ArretConcerte(), 10)
        with open(serveur.JOURNAL, encoding="utf-8") as f:
            self.assertEqual(f.read().count("demande d'arrêt ignorée"), 1)

    def test_la_verification_a_lieu_avant_toute_lecture(self):
        # Même un fichier illisible, ou énorme, n'est pas lu dans un dossier
        # qui n'est pas de confiance : il est seulement effacé.
        with open(self.demande, "wb") as f:
            f.write(b"x" * 100000)
        lectures = []
        reel = serveur.lire_demande_arret
        with unittest.mock.patch.object(serveur, "dossier_reserve_de_confiance",
                                        lambda dossier: False), \
             unittest.mock.patch.object(serveur, "lire_demande_arret",
                                        lambda c: lectures.append(c) or reel(c)):
            serveur.traiter_demande_arret(self.dossier, serveur.ArretConcerte(), 10)
        self.assertEqual(lectures, [])

    @unittest.skipIf(os.name == "nt", "critère POSIX : propriétaire et droits")
    def test_criteres_posix(self):
        def dossier_avec(mode):
            chemin = tempfile.mkdtemp(prefix="bilan-test-mode-", dir=self.dossier)
            os.chmod(chemin, mode)
            return chemin

        for mode, attendu in ((0o700, True), (0o750, True), (0o755, True),
                              (0o770, False), (0o775, False), (0o777, False),
                              (0o702, False), (0o722, False)):
            with self.subTest(mode=oct(mode)):
                self.assertEqual(serveur.dossier_reserve_de_confiance(dossier_avec(mode)),
                                 attendu)

    @unittest.skipIf(os.name == "nt", "critère POSIX : propriétaire et droits")
    def test_proprietaire_etranger_ou_lien_ou_fichier_refuses(self):
        propre = tempfile.mkdtemp(prefix="bilan-test-mode-", dir=self.dossier)
        os.chmod(propre, 0o700)
        self.assertTrue(serveur.dossier_reserve_de_confiance(propre))
        # Le dossier d'un autre compte (ni le nôtre, ni root) n'est pas de confiance.
        autre = os.geteuid() + 4242
        reel = os.lstat(propre)
        faux = os.stat_result((reel.st_mode, reel.st_ino, reel.st_dev, reel.st_nlink,
                               autre, reel.st_gid, reel.st_size, reel.st_atime,
                               reel.st_mtime, reel.st_ctime))
        with unittest.mock.patch.object(serveur.os, "lstat", lambda c: faux):
            self.assertFalse(serveur.dossier_reserve_de_confiance(propre))
        fichier = os.path.join(self.dossier, "fichier")
        with open(fichier, "w") as f:
            f.write("x")
        self.assertFalse(serveur.dossier_reserve_de_confiance(fichier))
        lien = os.path.join(self.dossier, "lien")
        try:
            os.symlink(propre, lien)
        except (OSError, NotImplementedError):
            self.skipTest("lien symbolique impossible sur ce poste")
        self.assertFalse(serveur.dossier_reserve_de_confiance(lien))
        self.assertFalse(serveur.dossier_reserve_de_confiance(os.path.join(self.dossier, "absent")))

    def test_jonction_simulee_n_est_pas_de_confiance(self):
        # Sous Windows, lstat rend S_IFDIR pour une jonction : seule la comparaison
        # du chemin résolu à celui qu'on a écrit la voit. Simulée ici par realpath.
        cible = tempfile.mkdtemp(prefix="bilan-test-jonction-", dir=self.dossier)
        reserve = os.path.join(self.dossier, "mise-a-jour")
        os.mkdir(reserve)
        os.chmod(reserve, 0o700)
        reel = os.path.realpath

        def realpath(chemin, *a, **k):
            return cible if os.fspath(chemin) == reserve else reel(chemin, *a, **k)

        with unittest.mock.patch.object(serveur, "lire_sddl_windows",
                                        lambda d: "D:PAI(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)"), \
             unittest.mock.patch.object(serveur, "proprietaire_windows",
                                        lambda d: serveur.SID_ADMINISTRATEURS):
            self.assertTrue(serveur.dossier_reserve_de_confiance(reserve))
            with unittest.mock.patch("os.path.realpath", realpath):
                self.assertFalse(serveur.dossier_reserve_de_confiance(reserve))

    def test_la_surveillance_efface_les_restes_au_demarrage(self):
        # X15 : une demande ou une réponse laissées par un processus précédent
        # arrêteraient le serveur relancé dans la seconde.
        with open(self.demande, "w") as f:
            json.dump(demande_arret(0), f)
        reponse = os.path.join(self.dossier, serveur.REPONSE_ARRET)
        with open(reponse, "w") as f:
            f.write("{}")

        class FauxServeur(object):
            def shutdown(self):
                raise RuntimeError("ne doit pas être appelé")

        with unittest.mock.patch.object(serveur, "DOSSIER_MAJ", self.dossier):
            fin = serveur.demarrer_surveillance_arret(FauxServeur(), serveur.ArretConcerte())
        fin.set()
        self.assertFalse(os.path.lexists(self.demande))
        self.assertFalse(os.path.lexists(reponse))


class EcrituresPatientes(unittest.TestCase):
    """Sous Windows, un os.replace sur un fichier que l'autre processus lit à cet
    instant est refusé : les fichiers d'échange sont repris."""

    def setUp(self):
        self.dossier = tempfile.mkdtemp(prefix="bilan-test-patient-")
        self.addCleanup(shutil.rmtree, self.dossier, ignore_errors=True)

    def remplacement_refuse(self, fois):
        reel = os.replace
        etat = {"restant": fois, "appels": 0}

        def faux(source, destination, *a, **k):
            etat["appels"] += 1
            if etat["restant"] > 0:
                etat["restant"] -= 1
                raise PermissionError(13, "refusé par le test")
            return reel(source, destination, *a, **k)

        return etat, unittest.mock.patch("os.replace", faux)

    def test_remplacement_momentanement_refuse(self):
        destination = os.path.join(self.dossier, "x.json")
        etat, patch = self.remplacement_refuse(3)
        with patch:
            serveur.ecrire_atomiquement_patient(destination, b"{}", tentatives=10, pause=0)
        self.assertEqual(etat["appels"], 4)
        with open(destination, "rb") as f:
            self.assertEqual(f.read(), b"{}")
        self.assertEqual([n for n in os.listdir(self.dossier) if n.endswith(".part")], [])

    def test_refus_durable_leve_apres_les_tentatives(self):
        destination = os.path.join(self.dossier, "x.json")
        etat, patch = self.remplacement_refuse(100)
        with patch, self.assertRaises(PermissionError):
            serveur.ecrire_atomiquement_patient(destination, b"{}", tentatives=4, pause=0)
        self.assertEqual(etat["appels"], 4)
        self.assertEqual(os.listdir(self.dossier), [])

    def test_une_autre_erreur_n_est_pas_reprise(self):
        etat = {"appels": 0}

        def faux(*a, **k):
            etat["appels"] += 1
            raise OSError(28, "disque plein")

        with unittest.mock.patch("os.replace", faux), self.assertRaises(OSError):
            serveur.ecrire_atomiquement_patient(
                os.path.join(self.dossier, "x"), b"{}", tentatives=10, pause=0)
        self.assertEqual(etat["appels"], 1)

    def test_la_reponse_d_arret_survit_a_un_remplacement_refuse(self):
        etat, patch = self.remplacement_refuse(2)
        with patch, unittest.mock.patch.object(serveur, "PAUSE_REPRISES_SECONDES", 0):
            serveur.ecrire_reponse_arret(self.dossier, JETON, "arrete", "aucun")
        with open(os.path.join(self.dossier, serveur.REPONSE_ARRET)) as f:
            self.assertEqual(json.load(f)["verdict"], "arrete")
        self.assertEqual(etat["appels"], 3)

    def test_delai_d_inactivite_des_connexions(self):
        # Inactivité, pas durée : posé sur la socket, il s'applique à chaque lecture.
        self.assertEqual(serveur.INACTIVITE_CONNEXION_SECONDES, 120)
        self.assertEqual(serveur.Gestionnaire.timeout, serveur.INACTIVITE_CONNEXION_SECONDES)


def modules_importes(source):
    modules = set()
    for noeud in ast.walk(ast.parse(source)):
        if isinstance(noeud, ast.Import):
            modules.update(a.name for a in noeud.names)
        elif isinstance(noeud, ast.ImportFrom) and noeud.level == 0:
            modules.add(noeud.module)
            modules.update("%s.%s" % (noeud.module, a.name) for a in noeud.names)
    return modules


class VocabulaireDeLaMiseAJour(unittest.TestCase):

    def test_les_cinq_evenements_sont_declares(self):
        for evenement in ("MAJ_REFUSEE", "MAJ_REPORTEE", "MAJ_APPLIQUEE", "MAJ_RETOUR",
                          "MAJ_CONTROLE"):
            self.assertIn(evenement, serveur.EVENEMENTS_TECHNIQUES)

    def test_aucun_jeton_n_est_prefixe_d_un_autre(self):
        # Un lecteur de journal cherche un jeton exact (CLAUDE.md), mais un préfixe
        # le piégerait. DEMARRAGE / DEMARRAGE_REFUSE (C6-T7) est l'unique cas hérité :
        # il est nommé, pour qu'un second ne passe pas inaperçu (erratum 3).
        paires = sorted((a, b) for a in serveur.EVENEMENTS_TECHNIQUES
                        for b in serveur.EVENEMENTS_TECHNIQUES
                        if a != b and b.startswith(a))
        self.assertEqual(paires, [("DEMARRAGE", "DEMARRAGE_REFUSE")])
        for jeton in serveur.EVENEMENTS_TECHNIQUES:
            if jeton.startswith("MAJ_"):
                for autre in serveur.EVENEMENTS_TECHNIQUES - {jeton}:
                    self.assertFalse(autre.startswith(jeton), (jeton, autre))
                    self.assertFalse(jeton.startswith(autre), (jeton, autre))

    def test_les_etapes_et_resultats_du_contrat(self):
        self.assertEqual(serveur.ETAPES_MAJ, ("repos", "preparee", "bascule", "verification",
                                              "retour", "echec-retour"))
        self.assertEqual(serveur.RESULTATS_MAJ, ("appliquee", "revenue", "refusee", "reportee"))

    def test_les_noms_du_dossier_reserve(self):
        self.assertEqual((serveur.ETAT_MAJ, serveur.DEMANDE_ARRET, serveur.REPONSE_ARRET),
                         ("etat.json", "arret.demande", "arret.reponse"))

    def test_serveur_py_n_importe_ni_urllib_ni_http_client(self):
        with open(serveur.__file__, encoding="utf-8") as f:
            source = f.read()
        interdits = [m for m in modules_importes(source)
                     if m.split(".")[0] == "urllib" or m == "http.client"]
        self.assertEqual(interdits, [])
        # La garde mord.
        for mutation in ("import urllib.request\n", "from urllib import parse\n",
                         "import http.client\n", "from http import client\n",
                         "def f():\n    import http.client\n"):
            with self.subTest(mutation=mutation):
                modules = modules_importes(mutation)
                self.assertTrue([m for m in modules if m.split(".")[0] == "urllib"
                                 or m == "http.client"], mutation)
        # Ancrage : la garde voit bien les imports qui existent.
        self.assertIn("http.server", modules_importes(source))

    def test_serveur_py_importe_paquet_signe(self):
        with open(serveur.__file__, encoding="utf-8") as f:
            source = f.read()
        self.assertIn("paquet_signe", modules_importes(source))
