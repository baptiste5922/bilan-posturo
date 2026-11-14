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


def affectations_racine(texte):
    """Les affectations de `$racine`, sous la seule forme que l'évaluateur sait lire.

    `$script:racine =`, `${racine} =`, `Set-Variable -Name racine`,
    `-OutVariable racine` rétabliraient le défaut d'origine sans qu'aucune
    affectation reconnue ne bouge : le mot « racine » est donc refusé partout où
    il n'est pas précédé de `$`. Les formes à portée ou à accolades en ont une
    autre devant (`:`, `{`) ; les lectures `$racine` restent libres.
    """
    for m in re.finditer(r"(?<!\$)racine", texte, re.IGNORECASE):
        ligne = texte[texte.rfind("\n", 0, m.start()) + 1:].split("\n")[0]
        raise FormeNonReconnue(
            "forme non reconnue : « racine » hors de la forme $racine "
            "(étendre l'évaluateur) : " + ligne.strip())
    return _affectations(texte, "racine")


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


# Verbes à effet de bord : tâche planifiée, pare-feu, fichiers, services.
# `New-ScheduledTaskAction` & co. ne modifient rien et ne sont pas visés ; seul
# `New-NetFirewall*` (et `New-Item`) crée quelque chose. La liste est un motif
# sur les verbes, pas une énumération de commandes : une commande ajoutée un
# jour au script est couverte sans toucher au test.
EFFETS_DE_BORD = re.compile(
    r"\b(?:(?:Register|Unregister|Set|Start|Stop|Restart|Remove|Add|Enable"
    r"|Disable|Invoke|Clear|Copy|Move|Rename)-\w+|New-NetFirewall\w*|New-Item)\b",
    re.IGNORECASE)


def verifier_ordre_des_effets(texte):
    """Rend la liste des défauts de l'ordre `-Verifier` ; vide si tout va bien.

    Le bloc `if ($Verifier) { … exit 0 }` doit précéder tout effet de bord. Un
    bloc déplacé après `Register-ScheduledTask` laissait la suite verte, et un
    essai à sec aurait écrasé la tâche SYSTEM de la machine d'essai.
    """
    debut = re.search(r"^[ \t]*if\s*\(\s*\$Verifier\s*\)\s*\{", texte,
                      re.IGNORECASE | re.MULTILINE)
    if debut is None:
        return ["bloc if ($Verifier) { … } introuvable"]
    profondeur, fin = 0, None
    for i in range(debut.end() - 1, len(texte)):
        if texte[i] == "{":
            profondeur += 1
        elif texte[i] == "}":
            profondeur -= 1
            if profondeur == 0:
                fin = i
                break
    if fin is None:
        return ["bloc -Verifier non refermé"]
    bloc = texte[debut.start():fin]
    sortie = re.search(r"^[ \t]*exit\s+0\s*$", bloc, re.IGNORECASE | re.MULTILINE)
    if sortie is None:
        return ["le bloc -Verifier ne contient pas « exit 0 »"]
    defauts = []
    for m in EFFETS_DE_BORD.finditer(texte[:fin]):
        defauts.append("effet de bord « {} » avant la sortie de -Verifier".format(
            m.group(0)))
    if not EFFETS_DE_BORD.search(texte[fin:]):
        defauts.append("aucun effet de bord après le bloc -Verifier : la garde "
                       "ne garderait rien")
    return defauts


# ---------------------------------------------------------------------------
# Contrôle des données réelles : le motif est celui de la CI, lu dans le fichier.
# ---------------------------------------------------------------------------

def lire_motif_des_secrets():
    """Le motif du pas « Check that no secret is committed » de la CI.

    Lu dans `.github/workflows/tests.yml` plutôt que recopié : une liste tenue à
    la main avait déjà oublié `journal.log.*`, `Bilan_entrants/` et
    `cles-editeur/`. Échoue si le motif est introuvable.
    """
    texte = (RACINE / ".github" / "workflows" / "tests.yml").read_text(
        encoding="utf-8")
    pas = texte.find("Check that no secret is committed")
    if pas < 0:
        raise RuntimeError("pas « Check that no secret is committed » introuvable")
    # Les lignes doivent se suivre : chercher chacune séparément attraperait le
    # `motif=` d'un pas voisin (celui des licences) quand celui-ci disparaît ou
    # change de forme. Depuis C5-T2b le motif compte plus de deux lignes
    # (identite-cabinet.json, adresse-publication.json) : toutes sont lues, sans
    # quoi un motif ajouté à la suite resterait invisible de cette garde.
    suite = re.search(
        r"""^\s*motif='([^'\n]+)'\s*\n"""
        r"""((?:[ \t]*(?:motif="\$motif"'[^'\n]+'|#[^\n]*)[ \t]*\n?)+)""",
        texte[pas:], re.MULTILINE)
    if suite is None:
        raise RuntimeError("les lignes motif= du contrôle des secrets "
                           "sont introuvables dans tests.yml")
    premier = suite.group(1)
    lignes = re.findall(r"""motif="\$motif"'([^'\n]+)'""", suite.group(2))
    second = "".join(lignes)
    # Garde contre un motif vidé : il doit au moins nommer les clés.
    if r"\.pem$" not in premier or "cles-editeur" not in second:
        raise RuntimeError("le motif lu dans tests.yml ne ressemble plus à "
                           "celui du contrôle des secrets")
    # Concaténation pure, comme `motif="$motif"'…'` : chaque ligne commence
    # elle-même par « | ». Un « | » de plus créerait une alternative vide, qui
    # accepte tous les chemins.
    motif = re.compile(premier + second, re.IGNORECASE)
    if motif.search("formulaire/index.html"):
        raise RuntimeError("le motif lu dans tests.yml accepte un fichier ordinaire")
    return motif


def fichiers_sensibles(dossier, motif):
    """Les fichiers de `dossier` (chemins relatifs, séparateur /) que le motif refuse."""
    trouves = []
    for chemin in Path(dossier).rglob("*"):
        if chemin.is_file():
            relatif = chemin.relative_to(dossier).as_posix()
            if motif.search(relatif):
                trouves.append(relatif)
    return sorted(trouves)


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
            ["sh", "outils/faire-paquet.sh", "cabinet-01"],
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
        try:
            return texte, affectations_racine(texte)
        except FormeNonReconnue as erreur:
            self.fail(script.name + " : " + str(erreur))

    def test_bac_a_sable_sans_donnees_reelles(self):
        """Ni le bac à sable, ni l'archive extraite ne contiennent ce que la CI
        refuse de versionner : clés, configuration, journaux, bilans."""
        motif = lire_motif_des_secrets()
        # Le bac à sable est une copie de la racine du dépôt ; l'archive
        # extraite est jugée depuis la racine du paquet, comme au cabinet.
        extrait = Path(self.travail) / "extrait"
        trouves = [
            f for f in fichiers_sensibles(self.travail, motif)
            if not f.startswith("extrait/")]
        trouves += ["paquet/" + f for f in fichiers_sensibles(self.paquet, motif)]
        self.assertEqual(trouves, [], "données réelles dans le bac à sable")
        self.assertTrue(extrait.is_dir())

    def test_detecteur_de_donnees_reelles_mord(self):
        """Des fichiers factices de chaque forme, déposés dans un dossier
        temporaire seulement, sont tous refusés ; un fichier ordinaire passe."""
        motif = lire_motif_des_secrets()
        formes = ("config.json", "journal.log", "journal.log.1", "technique.log",
                  "technique.log.2", "serveur.pem", "autorite.crt",
                  "bilans/2026/bilan.pdf", "Bilan_entrants/x.pdf",
                  "cles-editeur/licence.key", "cles-editeur/sous/x.txt",
                  "x.p12", "x.pfx", "id_ed25519", "cle_privee.txt",
                  "cle-privee.txt")
        with tempfile.TemporaryDirectory(prefix="bilan-detecteur-") as dossier:
            for forme in formes + ("serveur/serveur.py",):
                cible = Path(dossier) / forme
                cible.parent.mkdir(parents=True, exist_ok=True)
                cible.write_bytes(b"")
            self.assertEqual(
                fichiers_sensibles(dossier, motif), sorted(formes))

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

    def test_verifier_precede_les_effets_de_bord(self):
        """Dans l'archive comme dans le dépôt, `-Verifier` sort avant tout effet."""
        avec_verifier = [s for s in self.scripts
                         if re.search(r"\$Verifier\b",
                                      _retirer_commentaires(_lire_script(s)),
                                      re.IGNORECASE)]
        self.assertTrue(
            avec_verifier, "aucun .ps1 de l'archive ne porte -Verifier : "
            "la garde ne garderait rien")
        for script in avec_verifier + [SCRIPT_INSTALLATION]:
            with self.subTest(script=str(script)):
                texte = _retirer_commentaires(_lire_script(script))
                self.assertEqual(verifier_ordre_des_effets(texte), [])

    def test_garde_d_ordre_de_verifier_mord(self):
        """La garde elle-même, sur des textes fabriqués."""
        bon = ("param([switch]$Verifier)\nGet-Content x\n"
               "if ($Verifier) {\n    Write-Host 'a'\n    exit 0\n}\n"
               "Register-ScheduledTask -TaskName x\n")
        self.assertEqual(verifier_ordre_des_effets(bon), [])
        apres = bon.replace("Register-ScheduledTask -TaskName x\n", "") \
            .replace("if ($Verifier)", "Register-ScheduledTask -TaskName x\n"
                     "if ($Verifier)") + "Start-ScheduledTask -TaskName x\n"
        self.assertTrue(verifier_ordre_des_effets(apres))
        self.assertTrue(verifier_ordre_des_effets(
            bon.replace("exit 0", "return")))
        self.assertTrue(verifier_ordre_des_effets(
            bon.replace("$Verifier)", "$Autre)")))
        self.assertTrue(verifier_ordre_des_effets(
            bon.replace("Register-ScheduledTask -TaskName x\n", "")))

    def test_formes_d_affectation_non_evaluees_refusees(self):
        for ligne in ("$script:racine = Split-Path -Parent $PSScriptRoot",
                      "${racine} = Split-Path -Parent $PSScriptRoot",
                      "Set-Variable -Name racine -Value (Split-Path -Parent "
                      "$PSScriptRoot)",
                      "Get-Item . -OutVariable racine"):
            with self.subTest(ligne=ligne):
                with self.assertRaises(FormeNonReconnue):
                    affectations_racine("$racine = $PSScriptRoot\n" + ligne)
        self.assertEqual(
            affectations_racine("$racine = $PSScriptRoot\nJoin-Path $racine 'x'"),
            ["$PSScriptRoot"])

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
# La seconde tâche (C5-T2b), vérifiée PAR LECTURE.
#
# Aucun lancement de powershell.exe ici, et aucune installation réelle : le délai
# de 120 s de ExecutionReelleSousWindows est celui du démarrage de PowerShell sur
# un exécuteur lent, et enregistrer des tâches SYSTEM sur l'exécuteur de la CI
# serait pire. Ce qui se lit : l'ordre, les noms, les réglages. Ce que Windows en
# fait est relevé sur la VM (fiche d'essai, partie B) et, pour le dossier protégé,
# par tests/test_maj_windows.py.
# ---------------------------------------------------------------------------

SCRIPT_DESINSTALLATION = RACINE / "desinstaller-demarrage.ps1"
NOM_TACHE_MAJ = "BilanPosturo-MiseAJour"


def _bloc_accolades(texte, debut):
    """Le texte entre l'accolade ouvrante qui suit `debut` et sa fermante."""
    ouvrante = texte.index("{", debut)
    profondeur = 0
    for i in range(ouvrante, len(texte)):
        if texte[i] == "{":
            profondeur += 1
        elif texte[i] == "}":
            profondeur -= 1
            if profondeur == 0:
                return texte[ouvrante + 1:i]
    raise ValueError("accolade non refermée")


def defauts_de_l_installateur(texte):
    """Les défauts de la seconde tâche dans `installer-demarrage.ps1` ; liste vide
    si tout va bien. Fonction de module : un test la met en échec sur des textes
    fabriqués (une garde jamais mise en échec ne garde rien)."""
    defauts = []
    # Les commentaires peuvent nommer ce que le script ne fait pas (« aucun
    # -RestartCount ») : seul le code est jugé.
    texte = _retirer_commentaires(texte)
    sortie = re.search(r"^[ \t]*if\s*\(\s*\$Verifier\s*\)\s*\{", texte,
                       re.IGNORECASE | re.MULTILINE)
    if sortie is None:
        return ["bloc -Verifier introuvable"]
    fin_verifier = sortie.start() + len(_bloc_accolades(texte, sortie.start())) + 2
    avant, apres = texte[:fin_verifier], texte[fin_verifier:]

    # Avant la sortie de -Verifier : de simples tests de présence, aucun processus.
    for motif in (r"Start-Process", r"Start-Job", r"Invoke-\w+", r"&\s*[\$\"']",
                  r"\bpython(?:w)?\.exe\s+[\"'$]", r"ConvertFrom-Json\s*.*mise_a_jour"):
        if re.search(motif, avant, re.IGNORECASE):
            defauts.append("avant la sortie de -Verifier : %s" % motif)
    if not re.search(r"Test-Path\s+\$maj", avant, re.IGNORECASE):
        defauts.append("la présence de maj.py n'est pas testée avant -Verifier")
    if not re.search(r"Client de mise a jour :", avant):
        defauts.append("la ligne « Client de mise a jour » est absente")

    if not re.search(r'^\$maj\s*=\s*Join-Path \$racine "serveur\\maj\.py"\s*$', texte,
                     re.MULTILINE):
        defauts.append("$maj n'est pas joint à $racine")
    if len(re.findall(r"Register-ScheduledTask", apres)) != 2:
        defauts.append("deux Register-ScheduledTask attendus après -Verifier")
    if len(re.findall(r"Register-ScheduledTask", avant)) != 0:
        defauts.append("un enregistrement de tâche avant la sortie de -Verifier")
    if len(re.findall(r"Start-Process", apres)) != 1:
        defauts.append("un seul Start-Process attendu (proteger)")
    if len(re.findall(r"-RestartCount", texte)) != 1:
        defauts.append("-RestartCount doit n'apparaître qu'une fois (tâche du serveur)")

    # Le lancement de proteger : Start-Process, -B, proteger, attente du code.
    lancement = re.search(r"\$protection\s*=\s*Start-Process\b(.*?)\n\s*if\b", apres,
                          re.DOTALL | re.IGNORECASE)
    if lancement is None:
        defauts.append("le lancement de proteger est introuvable")
    else:
        for exigence in (r"-FilePath\s+\$python", r"'-B'", r"\$maj", r"'proteger'", r"-Wait",
                         r"-PassThru", r"-WindowStyle\s+Hidden", r"-WorkingDirectory\s+\$racine"):
            if not re.search(exigence, lancement.group(1)):
                defauts.append("proteger : %s absent" % exigence)

    # L'enregistrement de la seconde tâche est subordonné au code de sortie.
    condition = re.search(r"if\s*\(\s*\$protection\.ExitCode\s+-ne\s+0\s*\)", apres)
    if condition is None:
        defauts.append("le code de sortie de proteger n'est pas testé")
    else:
        branche_echec = _bloc_accolades(apres, condition.start())
        reste = apres[condition.end():]
        autre = re.search(r"\}\s*else\s*\{", reste)
        if autre is None:
            defauts.append("pas de branche else après l'échec de proteger")
        else:
            branche_succes = _bloc_accolades(reste, autre.start())
            if "Register-ScheduledTask" in branche_echec:
                defauts.append("la tâche est enregistrée même quand proteger échoue")
            if "Register-ScheduledTask" not in branche_succes \
                    or "$NOM_TACHE_MAJ" not in branche_succes:
                defauts.append("la seconde tâche n'est pas enregistrée par la branche de succès")
            for exigence, motif in (
                    ("execution", r"-ExecutionTimeLimit\s+\(New-TimeSpan\s+-Hours\s+1\)"),
                    ("instances", r"-MultipleInstances\s+IgnoreNew"),
                    ("argument", r"verifier['\"]"), ("option -B", r"'-B"),
                    ("SYSTEM", r"-Principal\s+\$principal"),
                    ("répertoire", r"-WorkingDirectory\s+\$racine"),
                    ("démarrage", r"-AtStartup"), ("délai", r"PT3M"),
                    ("heure", r"-RepetitionInterval\s+\(New-TimeSpan\s+-Hours\s+1\)"),
                    ("forcer", r"-Force")):
                if not re.search(motif, branche_succes):
                    defauts.append("seconde tâche : %s absent" % exigence)
            if "-RestartCount" in branche_succes:
                defauts.append("la seconde tâche ne redémarre pas sur échec")
            if "exit" in branche_echec.lower() or "throw" in branche_echec.lower():
                defauts.append("un échec de proteger ne doit pas sauter le pare-feu")

    # Après la tâche du serveur, avant le pare-feu (dont « exit 1 » ne doit pas sauter
    # le client).
    serveur = apres.find("Register-ScheduledTask -TaskName $NOM_TACHE ")
    maj_ = apres.find("$protection")
    pare_feu = apres.find("New-NetFirewallRule")
    if not 0 <= serveur < maj_ < pare_feu:
        defauts.append("ordre : tâche du serveur, puis mise à jour, puis pare-feu")
    if NOM_TACHE_MAJ not in texte or not re.search(
            r'^\$NOM_TACHE_MAJ\s*=\s*"%s"\s*$' % NOM_TACHE_MAJ, texte, re.MULTILINE):
        defauts.append("$NOM_TACHE_MAJ absent ou différent")
    return defauts


def defauts_du_desinstallateur(texte):
    """B14 : retire les deux tâches, celle de mise à jour d'abord, et refuse tant
    qu'elle tourne."""
    defauts = []
    maj_ = texte.find("Unregister-ScheduledTask -TaskName $NOM_TACHE_MAJ")
    serveur = texte.find("Unregister-ScheduledTask -TaskName $NOM_TACHE ")
    if maj_ < 0 or serveur < 0:
        defauts.append("les deux tâches ne sont pas retirées")
    elif maj_ > serveur:
        defauts.append("la tâche de mise à jour doit être retirée d'abord")
    etat = re.search(r"\.State\s+-eq\s+'Running'", texte)
    if etat is None:
        defauts.append("l'état « Running » n'est pas testé")
    else:
        branche = _bloc_accolades(texte, etat.start())
        if not re.search(r"^\s*exit\s+1\s*$", branche, re.MULTILINE):
            defauts.append("une mise à jour en cours ne fait pas sortir en code 1")
        if "Unregister" in branche or "Stop-ScheduledTask" in branche:
            defauts.append("rien ne doit être arrêté ni retiré pendant une mise à jour")
        if "reprendre" not in branche or "etat" not in branche:
            defauts.append("le message ne rappelle pas maj.py etat / reprendre")
        if maj_ >= 0 and etat.start() > maj_:
            defauts.append("le refus doit précéder le retrait")
    if "Stop-ScheduledTask -TaskName $NOM_TACHE_MAJ" in texte:
        defauts.append("la tâche de mise à jour ne s'arrête jamais de force")
    if not re.search(r'^\$NOM_TACHE_MAJ\s*=\s*"%s"\s*$' % NOM_TACHE_MAJ, texte, re.MULTILINE):
        defauts.append("$NOM_TACHE_MAJ absent ou différent")
    return defauts


class SecondeTache(unittest.TestCase):
    """B13, B14. Trois systèmes, sans paquet, sans zip, sans PowerShell."""

    @classmethod
    def setUpClass(cls):
        cls.installateur = _lire_script(SCRIPT_INSTALLATION)
        cls.desinstallateur = _lire_script(SCRIPT_DESINSTALLATION)

    def test_l_installateur_est_conforme(self):
        self.assertEqual(defauts_de_l_installateur(self.installateur), [])

    def test_la_garde_d_ordre_passe_et_voit_les_effets_apres_la_sortie(self):
        self.assertEqual(verifier_ordre_des_effets(self.installateur), [])
        apres = self.installateur[self.installateur.index("exit 0"):]
        self.assertEqual(len(re.findall(r"Register-ScheduledTask", apres)), 2)
        self.assertIsNotNone(re.search(r"Start-Process", apres))
        self.assertNotIn("Start-Process", self.installateur[:self.installateur.index("exit 0")])

    def test_le_nom_de_la_tache_et_son_argument(self):
        self.assertIn('$NOM_TACHE_MAJ = "BilanPosturo-MiseAJour"', self.installateur)
        self.assertIn("verifier", self.installateur)
        self.assertIn("'proteger'", self.installateur)
        code = _retirer_commentaires(self.installateur)
        self.assertEqual(len(re.findall(r"-RestartCount", code)), 1)

    def test_aucune_regle_de_la_mise_a_jour_n_est_recopiee_en_powershell(self):
        # La règle (adresse, plage, calme, droits du dossier) vit dans maj.py : le
        # script ne lit pas le bloc, ne connaît ni plage ni SDDL.
        sans_commentaires = _retirer_commentaires(self.installateur)
        for terme in ("mise_a_jour", "plage", "calme_minutes", "au_demarrage", "icacls",
                      "SDDL", "Set-Acl", "S-1-5-32-544", "publication"):
            self.assertNotIn(terme.lower(), sans_commentaires.lower(), terme)

    def test_le_desinstallateur_est_conforme(self):
        self.assertEqual(defauts_du_desinstallateur(self.desinstallateur), [])

    def test_les_deux_scripts_gardent_leur_forme_de_fichier(self):
        for script in (SCRIPT_INSTALLATION, SCRIPT_DESINSTALLATION):
            with self.subTest(script=script.name):
                brut = script.read_bytes()
                self.assertTrue(brut.startswith(b"\xef\xbb\xbf"), "BOM absent")
                self.assertEqual(brut.count(b"\n"), brut.count(b"\r\n"), "fins de ligne mêlées")
                self.assertEqual(brut.decode("utf-8-sig").count("\x00"), 0)

    # --- les gardes mordent ----------------------------------------------------

    def muter(self, texte, ancien, nouveau, fois=1):
        self.assertEqual(texte.count(ancien), fois, ancien)
        return texte.replace(ancien, nouveau)

    def test_la_garde_de_l_installateur_mord(self):
        t = self.installateur
        cas = {
            "Start-Process avant -Verifier": self.muter(
                t, 'Write-Host "Client de mise a jour : $presenceMaj"',
                'Start-Process notepad.exe\nWrite-Host "Client de mise a jour : $presenceMaj"'),
            "python lancé avant -Verifier": self.muter(
                t, 'Write-Host "Client de mise a jour : $presenceMaj"',
                '& $python -c "1"\nWrite-Host "Client de mise a jour : $presenceMaj"'),
            "tâche enregistrée sans condition": self.muter(
                t, "if ($protection.ExitCode -ne 0)", "if ($false)"),
            "pas de limite d'une heure": self.muter(
                t, "-ExecutionTimeLimit (New-TimeSpan -Hours 1)", "-ExecutionTimeLimit (New-TimeSpan -Hours 3)"),
            "second RestartCount": self.muter(
                t, "-MultipleInstances IgnoreNew `\r\n            -ExecutionTimeLimit",
                "-MultipleInstances IgnoreNew -RestartCount 3 `\r\n            -ExecutionTimeLimit"),
            "mauvais nom": self.muter(t, '$NOM_TACHE_MAJ = "BilanPosturo-MiseAJour"',
                                      '$NOM_TACHE_MAJ = "BilanPosturo-Maj"'),
            "sans -B": self.muter(t, "'-B', ('\"' + $maj", "('\"' + $maj"),
            "sans proteger": self.muter(t, "'proteger'", "'etat'"),
            "sans attendre": self.muter(t, "-WorkingDirectory $racine -Wait -PassThru",
                                        "-WorkingDirectory $racine -PassThru"),
            "pare-feu avant": self.muter(
                t, "# --- La mise a jour automatique", "New-NetFirewallRule -x\n# --- La mise a jour automatique"),
            "sans répétition horaire": self.muter(
                t, "-RepetitionInterval (New-TimeSpan -Hours 1)", "-RepetitionInterval (New-TimeSpan -Hours 2)"),
        }
        for nom, texte in cas.items():
            with self.subTest(nom):
                self.assertTrue(defauts_de_l_installateur(texte.replace("\r\n", "\n"))
                                or verifier_ordre_des_effets(texte.replace("\r\n", "\n")), nom)

    def test_la_garde_du_desinstallateur_mord(self):
        t = self.desinstallateur
        cas = {
            "serveur retiré d'abord": t.replace(
                "Unregister-ScheduledTask -TaskName $NOM_TACHE_MAJ", "Unregister-ScheduledTask -TaskName $XX", 1)
            + "\nUnregister-ScheduledTask -TaskName $NOM_TACHE_MAJ\n",
            "pas de refus": self.muter(t, "exit 1", "exit 0"),
            "arrêt de force": t + "\nStop-ScheduledTask -TaskName $NOM_TACHE_MAJ\n",
            "état non testé": self.muter(t, "'Running'", "'Ready'"),
            "mauvais nom": self.muter(t, '"BilanPosturo-MiseAJour"', '"BilanPosturo-Maj"'),
        }
        for nom, texte in cas.items():
            with self.subTest(nom):
                self.assertTrue(defauts_du_desinstallateur(texte.replace("\r\n", "\n")), nom)


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
        # La garde d'ordre est rejouée ICI, avant toute exécution : elle vit
        # aussi dans RacineDesScriptsDansLePaquet, mais cette classe est
        # sautée sous Windows faute de zip. Sans cet appel, un script où
        # l'ordre de -Verifier aurait régressé serait lancé en administrateur
        # et écraserait la tâche SYSTEM de la machine d'essai.
        defauts = verifier_ordre_des_effets(
            Path(script).read_text(encoding="utf-8-sig"))
        if defauts:
            self.fail("exécution refusée, -Verifier ne sort pas avant tout "
                      "effet de bord : " + " ; ".join(defauts))
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
