"""Tests des fonctions pures du serveur.

Bibliothèque standard uniquement, comme le serveur lui-même.

    python3 -m unittest discover -s tests
"""

import os
import stat
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import serveur


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
