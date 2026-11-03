"""Tests des fonctions pures du serveur.

Bibliothèque standard uniquement, comme le serveur lui-même.

    python3 -m unittest discover -s tests
"""

import base64
import contextlib
import email
import io
import json
import os
import re
import shutil
import stat
import sys
import tempfile
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
        for _ in range(serveur.JOURNAL_ARCHIVES + 2):
            self.ecrire(serveur.JOURNAL_TAILLE_MAX + 1)
            serveur.faire_tourner_journal()
        surnumeraire = "{}.{}".format(self.journal, serveur.JOURNAL_ARCHIVES + 1)
        self.assertTrue(os.path.exists(
            "{}.{}".format(self.journal, serveur.JOURNAL_ARCHIVES)))
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
