"""Test du script de fabrication du paquet (outils/faire-paquet.sh).

Depuis la bascule (C1-T3b), `formulaire/index.html` — le formulaire de
production — EST le moteur : une coquille qui rend son corps au chargement
depuis `formulaire/schema.json` par `formulaire/moteur/rendu.js`. Ce test
vérifie donc l'inverse de ce qu'il vérifiait avant la bascule : que le
moteur et le schéma partent bel et bien dans l'archive livrée au cabinet
(un paquet qui en manquerait livrerait un formulaire VIDE), et que
`formulaire/index-v1.html` — la fiche de secours gelée — y est aussi.

Depuis C1-T4a, le script exige le client en argument (`cabinet-01`) et prend
le schéma dans `clients/<client>/schema.json` : les cas de refus (sans argument,
chemin, client inconnu) et la fidélité du schéma livré s'éprouvent chacun dans
leur propre copie.

Exécuté sur une copie du dépôt dans un dossier temporaire : le script
travaille à la racine du projet et laisserait un `.zip` dans l'arbre réel
sinon. Sauté si `sh`/`zip`/`unzip` ne sont pas disponibles : ce script ne
tourne que sur le poste de développement, jamais sur la tablette ni sur le
PC du cabinet (`outils/faire-paquet.sh`).

    python3 -m unittest tests.test_paquet
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def _outil_disponible(nom):
    return shutil.which(nom) is not None


OUTILS_DISPONIBLES = all(_outil_disponible(n) for n in ("sh", "zip", "unzip"))


def _copier_le_depot():
    """Copie temporaire du strict nécessaire au script ; l'appelant la supprime."""
    dossier = tempfile.mkdtemp(prefix="bilan-paquet-")
    for nom in ("formulaire", "serveur", "outils", "docs", "clients"):
        shutil.copytree(
            RACINE / nom, Path(dossier) / nom,
            ignore=shutil.ignore_patterns(".DS_Store", "__pycache__"),
        )
    for nom in ("demarrer-serveur.bat", "installer-demarrage.ps1",
                "desinstaller-demarrage.ps1", "LICENSE", "TIERS.md"):
        shutil.copy(RACINE / nom, Path(dossier) / nom)
    return dossier


@unittest.skipUnless(OUTILS_DISPONIBLES, "sh/zip/unzip requis pour fabriquer le paquet")
class FabricationDuPaquet(unittest.TestCase):
    """`outils/faire-paquet.sh`, rejoué sur une copie pour ne rien laisser dans le dépôt réel."""

    @classmethod
    def setUpClass(cls):
        cls.dossier = _copier_le_depot()
        cls.resultat = subprocess.run(
            ["sh", "outils/faire-paquet.sh", "cabinet-01"],
            cwd=cls.dossier, capture_output=True, text=True,
        )
        cls.zips = list(Path(cls.dossier).glob("BilanPosturo-*.zip"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dossier, ignore_errors=True)

    def _noms_dans_le_paquet(self):
        with zipfile.ZipFile(self.zips[0]) as archive:
            return archive.namelist()

    def test_le_script_reussit(self):
        self.assertEqual(self.resultat.returncode, 0, self.resultat.stderr)
        self.assertEqual(len(self.zips), 1, self.resultat.stdout)

    def test_moteur_present_dans_le_paquet(self):
        noms = self._noms_dans_le_paquet()
        self.assertTrue(
            any(n.endswith("formulaire/moteur/rendu.js") for n in noms),
            "le moteur de rendu manque dans le paquet : " + ", ".join(noms),
        )
        self.assertTrue(
            any(n.endswith("formulaire/schema.json") for n in noms),
            "le schéma du formulaire manque dans le paquet : " + ", ".join(noms),
        )

    def test_formulaire_de_production_present(self):
        noms = self._noms_dans_le_paquet()
        self.assertTrue(any(n.endswith("formulaire/index.html") for n in noms))
        self.assertTrue(any(n.endswith("formulaire/index-v1.html") for n in noms))
        self.assertTrue(any(n.endswith("formulaire/script.js") for n in noms))
        self.assertTrue(any(n.endswith("LICENSE") for n in noms))
        self.assertTrue(any(n.endswith("TIERS.md") for n in noms))


@unittest.skipUnless(OUTILS_DISPONIBLES, "sh/zip/unzip requis pour fabriquer le paquet")
class ClientDuPaquet(unittest.TestCase):
    """Le client est un argument obligatoire, et son schéma est celui du paquet (C1-T4a)."""

    def setUp(self):
        self.dossier = _copier_le_depot()
        self.addCleanup(shutil.rmtree, self.dossier, ignore_errors=True)

    def _lancer(self, *arguments):
        return subprocess.run(
            ["sh", "outils/faire-paquet.sh"] + list(arguments),
            cwd=self.dossier, capture_output=True, text=True,
        )

    def _aucune_archive(self):
        self.assertEqual(list(Path(self.dossier).glob("BilanPosturo-*")), [],
                         "un refus ne doit laisser ni archive ni dossier de paquet")

    def test_sans_argument_refuse_et_liste_les_clients(self):
        # Aujourd'hui (avant C1-T4a) le script réussit sans argument.
        resultat = self._lancer()
        self.assertNotEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("cabinet-01", resultat.stderr,
                      "le refus doit lister les clients disponibles")
        self._aucune_archive()

    def test_nom_de_client_hors_motif_refuse(self):
        # Le client entre dans un chemin : ni remontée, ni séparateur, ni saut de ligne.
        for mauvais in ("../formulaire", "cabinet-01/..", "cabinet-1",
                        "ville-fictive", "cabinet-01\n../x"):
            with self.subTest(client=mauvais):
                resultat = self._lancer(mauvais)
                self.assertNotEqual(resultat.returncode, 0, resultat.stdout)
                self._aucune_archive()

    def test_piece_absente_de_l_archive_efface_l_archive(self):
        # Pièce obligatoire retirée de la source : `cp -R formulaire` ne la livre
        # pas, le script zippe puis constate l'absence dans l'archive. Il sort en
        # erreur ET efface l'archive : un paquet incomplet ne doit pas rester sur
        # le disque sous un nom de paquet valide.
        (Path(self.dossier) / "formulaire" / "version.json").unlink()
        resultat = self._lancer("cabinet-01")
        self.assertNotEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("version.json", resultat.stderr)
        self._aucune_archive()

    def test_client_inexistant_refuse(self):
        resultat = self._lancer("cabinet-99")
        self.assertNotEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("cabinet-99", resultat.stderr)
        self._aucune_archive()

    def test_le_schema_du_paquet_est_celui_du_client_et_aucune_entree_clients(self):
        # Dans cette copie, le schéma du client DIFFÈRE de son miroir de
        # formulaire/ : sans cela, un script qui oublierait de copier le schéma
        # du client livrerait celui de formulaire/ sans que rien ne rougisse.
        schema_client = Path(self.dossier) / "clients" / "cabinet-01" / "schema.json"
        octets_client = schema_client.read_bytes() + b"\n"
        schema_client.write_bytes(octets_client)
        miroir = (Path(self.dossier) / "formulaire" / "schema.json").read_bytes()
        self.assertNotEqual(octets_client, miroir, "le préalable du test n'est pas posé")

        resultat = self._lancer("cabinet-01")
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        archives = list(Path(self.dossier).glob("BilanPosturo-*.zip"))
        self.assertEqual(len(archives), 1, resultat.stdout)
        with zipfile.ZipFile(archives[0]) as archive:
            livres = [n for n in archive.namelist() if n.endswith("/formulaire/schema.json")]
            self.assertEqual(len(livres), 1, livres)
            self.assertEqual(archive.read(livres[0]), octets_client)
            self.assertEqual([n for n in archive.namelist() if "/clients/" in n], [],
                             "le dossier clients/ ne doit jamais voyager")


if __name__ == "__main__":
    sys.exit(unittest.main())
