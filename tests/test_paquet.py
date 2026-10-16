"""Test du script de fabrication du paquet (outils/faire-paquet.sh).

Depuis la bascule (C1-T3b), `formulaire/index.html` — le formulaire de
production — EST le moteur : une coquille qui rend son corps au chargement
depuis `formulaire/schema.json` par `formulaire/moteur/rendu.js`. Ce test
vérifie donc l'inverse de ce qu'il vérifiait avant la bascule : que le
moteur et le schéma partent bel et bien dans l'archive livrée au cabinet
(un paquet qui en manquerait livrerait un formulaire VIDE), et que
`formulaire/index-v1.html` — la fiche de secours gelée — y est aussi.

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


@unittest.skipUnless(OUTILS_DISPONIBLES, "sh/zip/unzip requis pour fabriquer le paquet")
class FabricationDuPaquet(unittest.TestCase):
    """`outils/faire-paquet.sh`, rejoué sur une copie pour ne rien laisser dans le dépôt réel."""

    @classmethod
    def setUpClass(cls):
        cls.dossier = tempfile.mkdtemp(prefix="bilan-paquet-")
        for nom in ("formulaire", "serveur", "outils", "docs"):
            shutil.copytree(
                RACINE / nom, Path(cls.dossier) / nom,
                ignore=shutil.ignore_patterns(".DS_Store", "__pycache__"),
            )
        for nom in ("demarrer-serveur.bat", "installer-demarrage.ps1",
                    "desinstaller-demarrage.ps1", "LICENSE", "TIERS.md"):
            shutil.copy(RACINE / nom, Path(cls.dossier) / nom)

        cls.resultat = subprocess.run(
            ["sh", "outils/faire-paquet.sh"],
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


if __name__ == "__main__":
    sys.exit(unittest.main())
