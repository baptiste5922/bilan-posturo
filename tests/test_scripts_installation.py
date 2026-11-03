"""Tests des scripts d'installation livrés au cabinet (C3-T3a).

`installer-demarrage.ps1` calculait sa racine comme le PARENT de son propre
dossier. Or le paquet le dépose à côté de `serveur\\` et `formulaire\\` : au
premier lancement chez un client, il s'arrêtait sur « serveur\\serveur.py
introuvable ». Le défaut tenait en une ligne, et aucun test ne pouvait le voir :
l'intégration continue ne vérifiait que la syntaxe des `.ps1`, et PowerShell
n'existe pas sur le poste de développement.

Deux classes :

- `RacineDesScriptsDansLePaquet` tourne partout, sans PowerShell. Elle fabrique
  le paquet RÉEL par `outils/faire-paquet.sh`, l'extrait, puis évalue le calcul
  de racine de chaque `.ps1` à l'emplacement où l'archive le livre. La position
  vient de l'archive, pas d'une constante : déplacer un script dans le paquet
  fait rougir le test.
- `ExecutionReelleSousWindows` lance un vrai `powershell.exe`, à sec
  (`-Verifier`), dans un dossier factice. Elle ne tourne que sous Windows.

    python3 -m unittest tests.test_scripts_installation
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SCRIPT_INSTALLATION = RACINE / "installer-demarrage.ps1"

OUTILS_DISPONIBLES = all(
    shutil.which(n) is not None for n in ("sh", "zip", "unzip", "git"))


# ---------------------------------------------------------------------------
# Évaluateur de la racine : vocabulaire FERMÉ.
#
# Un évaluateur qui « essaie de comprendre » une ligne qu'il ne connaît pas et
# la laisse passer est un garde-fou qui ne garde rien. Toute forme hors de la
# grammaire ci-dessous fait donc échouer le test, au lieu d'être ignorée.
# ---------------------------------------------------------------------------

class FormeNonReconnue(Exception):
    pass


def _retirer_commentaires(texte):
    """Retire les commentaires d'aide `<# … #>` et les lignes `# …`.

    Seulement les lignes entières : un commentaire en fin de ligne d'affectation
    reste dans l'expression et la rend non reconnue, ce qui est voulu.
    """
    texte = re.sub(r"<#.*?#>", "", texte, flags=re.DOTALL)
    return "\n".join(
        ligne for ligne in texte.splitlines()
        if not ligne.lstrip().startswith("#"))


def _lire_script(chemin):
    # utf-8-sig : le BOM exigé par PortabiliteWindows ne doit pas coller au
    # premier jeton.
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        return f.read()


def _affectations(texte, variable):
    """Toutes les expressions assignées à `$variable`, y compris dans un `if`.

    Les variables PowerShell ne distinguent pas la casse. Un opérateur composé
    (`+=`, …) lève FormeNonReconnue : il dépend de la valeur précédente.
    """
    trouvees = []
    motif = re.compile(
        r"\$" + variable + r"\s*([-+*/%]?)=(?!=)(.*)$",
        re.IGNORECASE | re.MULTILINE)
    for m in motif.finditer(texte):
        if m.group(1):
            raise FormeNonReconnue(
                "opérateur composé sur $" + variable + " : " + m.group(0).strip())
        expression = m.group(2).strip()
        # Une affectation écrite dans un `if (...) { $racine = ... }` sur une
        # seule ligne se termine par l'accolade fermante du bloc.
        if expression.endswith("}"):
            expression = expression[:-1].rstrip()
        trouvees.append(expression)
    return trouvees


def evaluer_racine(expression, dossier_script, chemin_script):
    """Évalue `expression` comme le ferait PowerShell, dans cette grammaire :

        expr := '(' expr ')'
              | '$PSScriptRoot'
              | '$MyInvocation.MyCommand.Path'
              | 'Split-Path' '-Parent' expr
    """
    reste = expression.strip()

    def refuser():
        raise FormeNonReconnue(
            "forme non reconnue : étendre l'évaluateur (" + expression + ")")

    def lire(reste):
        reste = reste.strip()
        if reste.startswith("("):
            if not reste.endswith(")"):
                refuser()
            return lire(reste[1:-1])
        if reste.lower() == "$psscriptroot":
            return str(dossier_script)
        if reste.lower() == "$myinvocation.mycommand.path":
            return str(chemin_script)
        m = re.match(r"split-path\s+-parent\s+(.+)$", reste, re.IGNORECASE)
        if m:
            return os.path.dirname(lire(m.group(1)))
        refuser()

    return lire(reste)


# ---------------------------------------------------------------------------
# Fabrication du paquet réel, en bac à sable.
# ---------------------------------------------------------------------------

def fabriquer_paquet_extrait():
    """Fabrique le paquet par `outils/faire-paquet.sh` et l'extrait.

    Rend (dossier_de_travail, dossier_extrait).

    La copie du dépôt se fait par `git ls-files -z` et JAMAIS par copie
    d'arborescence : la racine du dépôt porte les données réelles d'un cabinet
    (config.json, clés .pem, journaux, bilans), exclues du suivi Git, qui ne
    doivent entrer ni dans un bac à sable ni dans une archive de test.
    """
    travail = tempfile.mkdtemp(prefix="bilan-scripts-")
    try:
        liste = subprocess.run(
            ["git", "ls-files", "-z"], cwd=str(RACINE), capture_output=True)
        if liste.returncode != 0:
            raise RuntimeError(
                "git ls-files a échoué : "
                + liste.stderr.decode("utf-8", "replace"))
        for brut in liste.stdout.split(b"\0"):
            if not brut:
                continue
            relatif = os.fsdecode(brut)
            source = RACINE / relatif
            # Un fichier suivi mais supprimé de l'arbre, sans commit encore :
            # absent de la copie, comme il le serait du paquet.
            if not source.is_file():
                continue
            cible = Path(travail) / relatif
            cible.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(str(source), str(cible))

        resultat = subprocess.run(
            ["sh", "outils/faire-paquet.sh"],
            cwd=travail, capture_output=True, text=True)
        if resultat.returncode != 0:
            raise RuntimeError(
                "faire-paquet.sh a échoué : " + resultat.stdout + resultat.stderr)
        archives = list(Path(travail).glob("BilanPosturo-*.zip"))
        if len(archives) != 1:
            raise RuntimeError("une archive attendue, trouvé : " + repr(archives))

        extrait = Path(travail) / "extrait"
        with zipfile.ZipFile(str(archives[0])) as archive:
            archive.extractall(str(extrait))
        racines = [p for p in extrait.iterdir() if p.is_dir()]
        if len(racines) != 1:
            raise RuntimeError("un seul dossier attendu dans l'archive : "
                               + repr(racines))
        return travail, racines[0]
    except BaseException:
        shutil.rmtree(travail, ignore_errors=True)
        raise


@unittest.skipUnless(
    OUTILS_DISPONIBLES, "sh/zip/unzip/git requis pour fabriquer le paquet")
class RacineDesScriptsDansLePaquet(unittest.TestCase):
    """Le calcul de racine de chaque script, évalué dans le paquet livré."""

    # Jetons qui trahissent un calcul de chemin que l'évaluateur ne modélise
    # pas : un script sans `$racine` n'a aucune raison de les contenir.
    JETONS_DE_CHEMIN = ("$psscriptroot", "$myinvocation", "split-path",
                        "join-path", "set-location", "..")

    @classmethod
    def setUpClass(cls):
        cls.travail, cls.paquet = fabriquer_paquet_extrait()
        cls.scripts = sorted(cls.paquet.rglob("*.ps1"))
        cls.lanceurs = sorted(cls.paquet.rglob("*.bat"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.travail, ignore_errors=True)

    def _racines_de(self, script):
        texte = _retirer_commentaires(_lire_script(script))
        return texte, _affectations(texte, "racine")

    def test_bac_a_sable_sans_donnees_reelles(self):
        """Le paquet de test ne contient ni clé, ni configuration, ni journal."""
        interdits = []
        for chemin in Path(self.travail).rglob("*"):
            nom = chemin.name.lower()
            if (nom in ("config.json", "journal.log", "technique.log")
                    or nom.endswith(".pem") or nom == "autorite.crt"
                    or (nom == "bilans" and chemin.is_dir())):
                interdits.append(str(chemin))
        self.assertEqual(interdits, [], "données réelles dans le bac à sable")

    def test_au_moins_un_script_evalue(self):
        """Garde anti-vide : si l'archive ne contient plus de `.ps1` calculant
        une racine, les autres tests passeraient sans rien évaluer."""
        evalues = 0
        for script in self.scripts:
            _, racines = self._racines_de(script)
            if racines:
                evalues += 1
        self.assertGreater(
            evalues, 0,
            "aucun .ps1 de l'archive n'affecte $racine : rien n'est évalué ("
            + ", ".join(str(s.relative_to(self.paquet)) for s in self.scripts)
            + ")")

    def test_racine_contient_serveur(self):
        for script in self.scripts:
            relatif = script.relative_to(self.paquet).as_posix()
            with self.subTest(script=relatif):
                texte, racines = self._racines_de(script)
                if not racines:
                    continue
                for expression in racines:
                    try:
                        racine = evaluer_racine(
                            expression, script.parent, script)
                    except FormeNonReconnue as erreur:
                        self.fail(relatif + " : " + str(erreur))
                    self.assertTrue(
                        os.path.isfile(os.path.join(
                            racine, "serveur", "serveur.py")),
                        "{} : la racine calculée « {} » (à partir de {}) ne "
                        "contient pas serveur/serveur.py".format(
                            relatif, racine, expression))
                    self.assertTrue(
                        os.path.isdir(os.path.join(racine, "formulaire")),
                        "{} : la racine calculée « {} » ne contient pas "
                        "formulaire/".format(relatif, racine))
                self._exiger_chemins_joints_a_la_racine(relatif, texte)

    def _exiger_chemins_joints_a_la_racine(self, relatif, texte):
        attendus = (
            ("serveur", r'^Join-Path \$racine "serveur\\serveur\.py"$'),
            ("config", r'^Join-Path \$racine "config\.json"$'),
        )
        for variable, motif in attendus:
            try:
                valeurs = _affectations(texte, variable)
            except FormeNonReconnue as erreur:
                self.fail(relatif + " : " + str(erreur))
            self.assertTrue(
                valeurs, relatif + " : $" + variable + " n'est jamais affecté")
            for valeur in valeurs:
                self.assertTrue(
                    re.match(motif, valeur, re.IGNORECASE),
                    "{} : ${} doit être joint à $racine, trouvé « {} »".format(
                        relatif, variable, valeur))

    def test_forme_inconnue_refusee(self):
        """Le vocabulaire est fermé : `Resolve-Path`, par exemple, échoue au
        lieu d'être admis sur la foi de sa seule apparence."""
        for expression in ('Resolve-Path "$PSScriptRoot\\.."',
                           "Split-Path $PSScriptRoot",
                           "$PSScriptRoot + 'x'",
                           "(Get-Location).Path"):
            with self.subTest(expression=expression):
                with self.assertRaises(FormeNonReconnue):
                    evaluer_racine(expression, Path("/p"), Path("/p/s.ps1"))
        with self.assertRaises(FormeNonReconnue):
            _affectations("$racine += 'x'", "racine")
        # Les formes connues, elles, s'évaluent comme PowerShell.
        script = Path("/a/b/s.ps1")
        self.assertEqual(
            evaluer_racine("$PSScriptRoot", script.parent, script), "/a/b")
        self.assertEqual(
            evaluer_racine("Split-Path -Parent $PSScriptRoot",
                           script.parent, script), "/a")
        self.assertEqual(
            evaluer_racine(
                "Split-Path -Parent (Split-Path -Parent "
                "$MyInvocation.MyCommand.Path)", script.parent, script), "/a")

    def test_evaluation_de_toutes_les_affectations(self):
        """Le repli d'une ligne suivante est évalué comme la première affectation."""
        texte = ("$racine = $PSScriptRoot\n"
                 "if (-not $racine) { $racine = Split-Path -Parent "
                 "$MyInvocation.MyCommand.Path }\n")
        self.assertEqual(
            _affectations(texte, "racine"),
            ["$PSScriptRoot",
             "Split-Path -Parent $MyInvocation.MyCommand.Path"])

    def test_script_sans_racine_ne_calcule_aucun_chemin(self):
        for script in self.scripts:
            relatif = script.relative_to(self.paquet).as_posix()
            with self.subTest(script=relatif):
                texte, racines = self._racines_de(script)
                if racines:
                    continue
                minuscules = texte.lower()
                for jeton in self.JETONS_DE_CHEMIN:
                    self.assertFalse(
                        jeton in minuscules,
                        "{} : calcule un chemin non modélisé ({})".format(
                            relatif, jeton))

    def test_lanceur_bat_dans_son_dossier(self):
        self.assertTrue(
            self.lanceurs, "aucun lanceur .bat dans l'archive : rien à contrôler")
        for lanceur in self.lanceurs:
            relatif = lanceur.relative_to(self.paquet).as_posix()
            with self.subTest(lanceur=relatif):
                contenu = lanceur.read_text(encoding="utf-8", errors="replace")
                self.assertNotIn(
                    "..", contenu, relatif + " remonte d'un dossier")
                commandes_cd = [
                    ligne.strip() for ligne in contenu.splitlines()
                    if re.match(r"\s*cd\b", ligne, re.IGNORECASE)]
                self.assertEqual(
                    commandes_cd, ['cd /d "%~dp0"'],
                    relatif + " doit se placer dans son propre dossier")


# ---------------------------------------------------------------------------
# Exécution réelle, sous Windows seulement.
# ---------------------------------------------------------------------------

def _normaliser(sortie):
    """Supprime tout blanc : PowerShell peut replier une erreur longue au milieu
    d'un mot, et la recherche d'« introuvable » ne doit pas en dépendre."""
    return re.sub(r"\s+", "", sortie)


@unittest.skipUnless(os.name == "nt", "exécution de powershell.exe : Windows seulement")
class ExecutionReelleSousWindows(unittest.TestCase):
    """`installer-demarrage.ps1 -Verifier`, exécuté pour de bon.

    Ni tâche planifiée ni règle de pare-feu : le commutateur sort avant. Le vrai
    `serveur.py` n'est ni copié ni lancé, le dossier factice n'en a qu'un vide.

    Le script exige `#Requires -RunAsAdministrator`. Si le lanceur ne l'est pas,
    le test ÉCHOUE avec un message explicite : le sauter donnerait une
    exécution réelle qui n'a jamais lieu et que personne ne verrait.
    """

    def setUp(self):
        self.dossier = tempfile.mkdtemp(prefix="bilan-ps1-")
        self.addCleanup(shutil.rmtree, self.dossier, ignore_errors=True)
        os.makedirs(os.path.join(self.dossier, "serveur"))
        with open(os.path.join(self.dossier, "serveur", "serveur.py"), "w"):
            pass
        with open(os.path.join(self.dossier, "config.json"), "w") as f:
            f.write('{"port": 8000}')

    def _lancer(self, script):
        powershell = shutil.which("powershell") or shutil.which("powershell.exe")
        if powershell is None:
            self.fail("powershell.exe est introuvable : sous Windows, c'est un "
                      "échec et non un saut")
        resultat = subprocess.run(
            [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(script), "-Verifier"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, timeout=120)
        sortie = resultat.stdout.decode("utf-8", errors="replace")
        brut = sortie.lower()
        if "requires" in brut and "administrat" in brut:
            self.fail(
                "le lanceur n'est pas administrateur : #Requires "
                "-RunAsAdministrator refuse le script. Ce test ne se saute pas "
                "(C3-T3a, étape 9) ; remonter au donneur d'ordre.\n" + sortie)
        return resultat.returncode, sortie

    def test_verifier_depuis_la_racine(self):
        script = Path(self.dossier) / "installer-demarrage.ps1"
        shutil.copy(str(SCRIPT_INSTALLATION), str(script))
        code, sortie = self._lancer(script)
        self.assertEqual(code, 0, sortie)
        trouve = re.search(r"^Application : (.+?)\s*$", sortie, re.MULTILINE)
        self.assertIsNotNone(trouve, "ligne « Application : » absente :\n" + sortie)
        # Jamais de comparaison de chaînes : le lanceur peut abréger son
        # dossier temporaire (RUNNER~1).
        self.assertTrue(
            os.path.samefile(trouve.group(1), self.dossier),
            "racine annoncée : {} ; attendue : {}".format(
                trouve.group(1), self.dossier))

    def test_lance_d_un_sous_dossier_s_arrete(self):
        """Une recherche ascendante de `serveur\\` réussirait ici, en pointant
        sur une AUTRE installation : le script doit s'arrêter (D1)."""
        sous_dossier = Path(self.dossier) / "outils"
        sous_dossier.mkdir()
        script = sous_dossier / "installer-demarrage.ps1"
        shutil.copy(str(SCRIPT_INSTALLATION), str(script))
        code, sortie = self._lancer(script)
        self.assertNotEqual(code, 0, sortie)
        self.assertIn("introuvable", _normaliser(sortie), sortie)


if __name__ == "__main__":
    sys.exit(unittest.main())
