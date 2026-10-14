"""Tests de non-régression de la licence BUSL 1.1.

Bibliothèque standard uniquement, compatible Python 3.9, comme le reste de
`tests/`.

    python3 -m unittest discover -s tests

Les contrôles qui ont besoin de `git` sont encadrés d'un `skipUnless` : le
paquet livré au cabinet (`outils/faire-paquet.sh`) ne contient pas `.git`, et
un test ne doit pas y échouer.
"""

import datetime
import json
import re
import subprocess
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
LICENSE = RACINE / "LICENSE"
LICENSE_MIT_HISTORIQUE = RACINE / "LICENSE-MIT-HISTORIQUE"
PACKAGE_JSON = RACINE / "package.json"
README = RACINE / "README.md"
TIERS = RACINE / "TIERS.md"

COMMIT_FRONTIERE = "9339ee9"


def _git(*arguments):
    """Lance une commande `git` dans le dépôt, sans lever sur échec.

    Rend un objet dont `returncode` vaut autre chose que zéro si la commande
    a échoué, et `None` si `git` n'est pas installé du tout.
    """
    try:
        return subprocess.run(
            ["git"] + list(arguments),
            cwd=RACINE, capture_output=True, text=True, check=False,
        )
    except OSError:
        return None


def _git_a_reussi(*arguments):
    resultat = _git(*arguments)
    return resultat is not None and resultat.returncode == 0


A_UN_DEPOT_GIT = (RACINE / ".git").exists()

# `actions/checkout` clone à la profondeur 1 : `.git` existe donc bien en
# intégration continue, mais les commits antérieurs à `HEAD` en sont absents.
# Un test qui a besoin du contenu du commit frontière doit vérifier que
# l'objet est là, pas que le dossier `.git` existe.
COMMIT_FRONTIERE_DISPONIBLE = A_UN_DEPOT_GIT and _git_a_reussi(
    "cat-file", "-e", "%s^{commit}" % COMMIT_FRONTIERE
)

# Dans un clone superficiel, la greffe prive `HEAD` de parent : un
# `git log -1 -- <fichier>` y renvoie la date de `HEAD` quel que soit
# l'historique réel. Toute mesure de date tirée de l'historique y est donc
# fausse, et silencieusement laxiste.
_etat_superficiel = _git("rev-parse", "--is-shallow-repository")
HISTORIQUE_COMPLET = (
    A_UN_DEPOT_GIT
    and _etat_superficiel is not None
    and _etat_superficiel.stdout.strip() != "true"
)

# Même motif et mêmes exclusions que le pas CI « Check that no contradictory
# licence notice remains » (.github/workflows/tests.yml, job lint) : ce test
# le reproduit pour qu'il tourne aussi en local, hors CI.
MOTIF_MIT_CONTRADICTOIRE = re.compile(
    r'"license": *"MIT"|badge/licence-MIT|Permission is hereby granted, free of charge'
)
# Ancré des deux côtés : sans le `$`, un `TIERS.md.bak` porteur d'une mention
# contradictoire serait exclu comme s'il était TIERS.md, soit exactement le
# trou que ce contrôle doit fermer. Seul `formulaire/lib/` reste un préfixe,
# puisqu'il désigne un dossier.
EXCLUS_DU_CONTROLE = re.compile(
    r"^(LICENSE-MIT-HISTORIQUE|TIERS\.md|package-lock\.json"
    r"|\.github/workflows/tests\.yml|tests/test_licence\.py)$"
    r"|^formulaire/lib/"
)


def _lire(chemin):
    return chemin.read_text(encoding="utf-8")


class LicenceBusl(unittest.TestCase):
    """`LICENSE` porte désormais la Business Source License 1.1."""

    def test_licence_est_busl(self):
        texte = _lire(LICENSE)
        self.assertGreaterEqual(texte.count("Business Source License 1.1"), 1)

    def test_parametres_busl_remplis(self):
        texte = _lire(LICENSE)
        for champ in (
            "Licensor",
            "Licensed Work",
            "Additional Use Grant",
            "Change Date",
            "Change License",
        ):
            with self.subTest(champ=champ):
                motif = re.search(
                    r"^" + re.escape(champ) + r":[ \t]*(\S.*)$", texte, re.MULTILINE
                )
                self.assertIsNotNone(motif, "paramètre %s absent ou vide" % champ)

    def test_licence_ne_porte_plus_le_texte_mit(self):
        # Ce test échoue aujourd'hui (avant la bascule) : LICENSE porte
        # encore "Permission is hereby granted, free of charge", la phrase
        # d'entrée du texte MIT.
        texte = _lire(LICENSE)
        self.assertEqual(texte.count("Permission is hereby granted, free of charge"), 0)

    @unittest.skipUnless(A_UN_DEPOT_GIT, "hors dépôt Git")
    def test_change_date_sous_quatre_ans(self):
        # Contrainte propre à BUSL 1.1 (§7 D2 du contrat) : la Change Date ne
        # peut pas dépasser quatre ans après « la première distribution
        # publique » de cette version. Tant que LICENSE est modifié ou non
        # suivi dans l'arbre de travail, cette distribution n'a pas encore eu
        # lieu : la référence est alors la date du jour, pas celle de
        # l'ancien commit, sans quoi le test resterait rouge à chaque future
        # édition de LICENSE — précisément ce que C5-T1 demande de faire à
        # chaque publication (repousser Change Date). Une fois LICENSE
        # commité et l'arbre propre, la référence redevient la date du
        # dernier commit qui l'a touché.
        texte = _lire(LICENSE)
        motif = re.search(r"^Change Date:[ \t]*(\S+)$", texte, re.MULTILINE)
        self.assertIsNotNone(motif, "Change Date absente")
        date_bascule = datetime.date.fromisoformat(motif.group(1))

        etat = subprocess.run(
            ["git", "status", "--porcelain", "--", "LICENSE"],
            cwd=RACINE, capture_output=True, text=True, check=True,
        ).stdout.strip()

        if etat:
            # Modifié ou non suivi : pas encore publié, la date de référence
            # est aujourd'hui.
            date_reference = datetime.date.today()
        else:
            # L'arbre est propre : la référence est la date du commit qui a
            # publié ce LICENSE. Encore faut-il que l'historique soit là —
            # dans un clone superficiel, cette date est celle de HEAD et ne
            # veut rien dire. Mieux vaut ne pas contrôler que contrôler faux.
            if not HISTORIQUE_COMPLET:
                self.skipTest(
                    "clone superficiel : la date de commit de LICENSE n'y est "
                    "pas fiable"
                )
            horodatage = subprocess.run(
                ["git", "log", "-1", "--format=%cI", "--", "LICENSE"],
                cwd=RACINE, capture_output=True, text=True, check=True,
            ).stdout.strip()
            date_reference = datetime.datetime.fromisoformat(horodatage).date()

        limite = date_reference.replace(year=date_reference.year + 4)
        self.assertLessEqual(date_bascule, limite)


class HistoriqueMit(unittest.TestCase):
    """L'historique publié sous MIT reste accessible, inchangé."""

    def test_mit_historique_conserve(self):
        self.assertTrue(LICENSE_MIT_HISTORIQUE.exists())
        texte = _lire(LICENSE_MIT_HISTORIQUE)
        self.assertIn(COMMIT_FRONTIERE, texte)

    @unittest.skipUnless(
        COMMIT_FRONTIERE_DISPONIBLE,
        "commit frontière absent du dépôt (clone superficiel ou paquet livré)",
    )
    def test_mit_historique_identique_au_commit_frontiere(self):
        texte_origine = subprocess.run(
            ["git", "show", "%s:LICENSE" % COMMIT_FRONTIERE],
            cwd=RACINE, capture_output=True, text=True, check=True,
        ).stdout
        texte_conserve = _lire(LICENSE_MIT_HISTORIQUE)
        # Le fichier conservé fait précéder le texte MIT d'un bloc de portée ;
        # le texte MIT lui-même doit s'y retrouver à l'octet.
        self.assertIn(texte_origine, texte_conserve)


class PaquetJson(unittest.TestCase):
    def test_package_json_declare_busl(self):
        donnees = json.loads(_lire(PACKAGE_JSON))
        self.assertEqual(donnees["license"], "BUSL-1.1")


class Readme(unittest.TestCase):
    def test_readme_nomme_le_commit_frontiere(self):
        texte = _lire(README)
        self.assertIn(COMMIT_FRONTIERE, texte)
        self.assertNotIn("badge/licence-MIT", texte)


class Tiers(unittest.TestCase):
    def test_tiers_attribue_les_dependances(self):
        self.assertTrue(TIERS.exists())
        texte = _lire(TIERS)
        for attendu in ("jsPDF", "4.2.1", "html2canvas", "1.4.1", "MIT"):
            with self.subTest(attendu=attendu):
                self.assertIn(attendu, texte)


class ControleDesMentionsContradictoires(unittest.TestCase):
    """Même contrôle que le pas CI, pour qu'il tourne aussi en local."""

    @unittest.skipUnless(A_UN_DEPOT_GIT, "hors dépôt Git")
    def test_aucune_mention_mit_contradictoire(self):
        # `-z` est indispensable : sans lui, git échappe les chemins non ASCII
        # à la façon du C et les entoure de guillemets, si bien qu'un fichier
        # au nom accentué — tous les documents de ce dépôt le sont — devient
        # introuvable et échappe au contrôle sans bruit.
        fichiers = [
            nom
            for nom in subprocess.run(
                ["git", "ls-files", "-z"],
                cwd=RACINE, capture_output=True, text=True, check=True,
            ).stdout.split("\0")
            if nom
        ]
        self.assertTrue(fichiers, "git ls-files n'a listé aucun fichier")

        suspects = []
        illisibles = []
        for nom_relatif in fichiers:
            if EXCLUS_DU_CONTROLE.match(nom_relatif):
                continue
            chemin = RACINE / nom_relatif
            if not chemin.is_file():
                # Un fichier listé par git et introuvable sur le disque n'est
                # pas un fichier sain à ignorer : c'est le symptôme du défaut
                # d'échappement ci-dessus. On le signale au lieu de le taire.
                illisibles.append(nom_relatif)
                continue
            try:
                contenu = chemin.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Fichier binaire : le motif cherché est du texte.
                continue
            except OSError:
                illisibles.append(nom_relatif)
                continue
            if MOTIF_MIT_CONTRADICTOIRE.search(contenu):
                suspects.append(nom_relatif)

        self.assertEqual(illisibles, [], "chemins listés par git mais illisibles")
        self.assertEqual(suspects, [])


if __name__ == "__main__":
    unittest.main()
