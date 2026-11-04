"""Gardes de confidentialité du premier prospect (C1-T6).

Le dépôt est public. `fiche_presentation.html`, à la racine, reprend le
protocole d'examen d'un formateur : elle est ignorée par Git (`.gitignore`) et
rien de ce qu'elle contient n'a le droit d'entrer dans un fichier versionné,
sauf accord écrit. Trois gardes, de la plus générale à la plus fine :

* `FicheNonSuivie` : la fiche n'est ni suivie, ni oubliée par l'ignorance ;
* `VocabulaireFictif` : les données de test et les exemples de grille de la
  spécification n'emploient que le vocabulaire fictif de D9 ;
* `AucunMarqueurDeLaFiche` : aucun texte de la fiche, qui ne soit déjà public,
  ne figure dans un fichier modifié ou ajouté depuis le commit de repère.

Règle de cette suite : un échec ne nomme **jamais** ce qu'il a trouvé, seulement
le fichier et le numéro de ligne (même règle que la garde d'identité de
C1-T1). Les journaux d'intégration continue sont publics eux aussi.

Bibliothèque standard seule. Aucun `assert` nu : sous `python -O` ils
s'évaporent, et une garde qui ne garde plus rien est le piège le plus coûteux de
ce dépôt.
"""

import html.parser
import json
import os
import re
import subprocess
import unicodedata
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FICHE = "fiche_presentation.html"
COMMIT_DE_REPERE = "1ec796c"
DONNEES = os.path.join(RACINE, "tests", "donnees")
SPECIFICATION = os.path.join(RACINE, "docs", "schema-formulaire.md")

# D9 : seul vocabulaire admis dans ce qui est versionné.
MOTIF_LIBELLE = re.compile(r"^(Grille|Groupe|Colonne|Ligne|Texte|Bloc) [0-9]+( ?:)?$")
MOTIF_CLE = re.compile(r"^(grille|groupe|colonne|ligne|texte|bloc)-[0-9]+$")
# Valeurs structurelles du format (types, natures, dispositions…) : un mot du
# vocabulaire du moteur, jamais une phrase.
MOTIF_STRUCTURE = re.compile(r"^[a-z0-9_-]+$")
CLES_STRUCTURELLES = ("type", "nature", "titre_apparence", "disposition", "balise", "apparence")
LONGUEUR_MARQUEUR = 8
# Deux exemptions, écrites parce que le contrat se heurtait à lui-même au premier
# essai (écart signalé dans le compte rendu de C1-T6) : D9 impose des clés
# « grille-N » que la fiche emploie aussi, et la décision D12 nomme l'attribut
# standard `aria-label`, qui n'était pas encore dans le dépôt. Un texte du
# vocabulaire fictif est public par construction ; un nom d'attribut WAI-ARIA
# l'est par la norme. Cette liste est fermée et ne s'allonge pas à la volée : un
# nouveau faux positif est une décision de l'architecte, pas un réglage.
JETONS_TECHNIQUES_PUBLICS = frozenset(["aria-label"])
MOTIF_LIBELLE_NORMALISE = re.compile(MOTIF_LIBELLE.pattern, re.I)


def git(*arguments, **options):
    """Exécute git à la racine ; retourne le processus terminé (sortie en octets)."""
    return subprocess.run(
        ("git",) + arguments, cwd=RACINE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, **options)


def git_disponible():
    try:
        return git("rev-parse", "--is-inside-work-tree").returncode == 0
    except OSError:
        return False


def noms_zero(sortie):
    """Découpe une sortie `-z` en noms décodés (les chemins accentués restent bruts)."""
    return [os.fsdecode(n) for n in sortie.split(b"\0") if n]


def normaliser(texte):
    """NFC, minuscules, espaces réduites : la forme sous laquelle on compare."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", texte).lower()).strip()


# ------------------------------------------------------------- vocabulaire fictif

def verifier_vocabulaire(valeur, chemin="$"):
    """Retourne la liste des chemins JSON dont la valeur sort du vocabulaire fictif.

    Un chemin, jamais la valeur : une valeur hors vocabulaire est peut-être
    justement ce que la garde est là pour ne pas laisser passer dans un journal.
    Toute `cle` du jeu fictif est soumise au motif de clés de D9, qu'elle soit
    celle d'une grille, d'une ligne, d'une colonne, d'un bloc ou d'un champ.
    """
    fautes = []
    if isinstance(valeur, list):
        for i, element in enumerate(valeur):
            fautes += verifier_vocabulaire(element, "%s[%d]" % (chemin, i))
        return fautes
    if not isinstance(valeur, dict):
        return fautes

    for nom, enfant in valeur.items():
        sous = "%s.%s" % (chemin, nom)
        if isinstance(enfant, (dict, list)):
            if nom == "neutralisees" and isinstance(enfant, list):
                for i, cle in enumerate(enfant):
                    if not (isinstance(cle, str) and MOTIF_CLE.match(cle)):
                        fautes.append("%s[%d]" % (sous, i))
                continue
            fautes += verifier_vocabulaire(enfant, sous)
            continue
        if not isinstance(enfant, str):
            continue
        if nom in ("libelle", "titre"):
            if enfant != "" and not MOTIF_LIBELLE.match(enfant):
                fautes.append(sous)
        elif nom == "cle" or nom == "titre_cle":
            if not MOTIF_CLE.match(enfant):
                fautes.append(sous)
        elif nom in CLES_STRUCTURELLES:
            if not MOTIF_STRUCTURE.match(enfant):
                fautes.append(sous)
        else:
            # Tout autre texte libre (indication, texte_alternatif, defaut…)
            # n'est couvert par aucun motif : refusé, donc jamais copié.
            fautes.append(sous)
    return fautes


def blocs_json_de_la_specification():
    with open(SPECIFICATION, encoding="utf-8") as f:
        texte = f.read().replace("\r\n", "\n")
    return re.findall(r"```json\n(.*?)```", texte, re.S)


# ----------------------------------------------------------- marqueurs de la fiche

def litteraux_js(source):
    """Les littéraux de chaîne d'un script, commentaires exclus.

    Une simple expression régulière prenait pour des chaînes la prose française
    des commentaires (« l'en-tête … d'une … ») : ses apostrophes se répondaient
    d'un mot à l'autre. D'où ce petit parcours, qui saute `//` et `/* */`.
    """
    trouves = []
    i, n = 0, len(source)
    while i < n:
        c = source[i]
        if c == "/" and source[i + 1:i + 2] == "/":
            fin = source.find("\n", i)
            i = n if fin == -1 else fin
        elif c == "/" and source[i + 1:i + 2] == "*":
            fin = source.find("*/", i + 2)
            i = n if fin == -1 else fin + 2
        elif c in "\"'`":
            j = i + 1
            while j < n and source[j] != c:
                j += 2 if source[j] == "\\" else 1
            trouves.append(source[i + 1:j])
            i = j + 1
        else:
            i += 1
    return trouves


class _ExtracteurDeFiche(html.parser.HTMLParser):
    """Récolte les nœuds texte et, dans les scripts, les littéraux entre guillemets."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.textes = []
        self._dans_script = False
        self._dans_style = False

    def handle_starttag(self, balise, attributs):
        if balise == "script":
            self._dans_script = True
        elif balise == "style":
            self._dans_style = True

    def handle_endtag(self, balise):
        if balise == "script":
            self._dans_script = False
        elif balise == "style":
            self._dans_style = False

    def handle_data(self, donnee):
        if self._dans_style:
            return
        if self._dans_script:
            self.textes.extend(litteraux_js(donnee))
        else:
            self.textes.append(donnee)


def marqueurs_de_la_fiche():
    """Textes de la fiche d'au moins huit caractères, normalisés, absents du dépôt public.

    Retourne un ensemble vide si la fiche manque. Ne journalise rien.
    """
    chemin = os.path.join(RACINE, FICHE)
    if not os.path.isfile(chemin):
        return set()
    extracteur = _ExtracteurDeFiche()
    with open(chemin, encoding="utf-8", errors="replace") as f:
        extracteur.feed(f.read())
        extracteur.close()
    candidats = {normaliser(t) for t in extracteur.textes}
    candidats = {t for t in candidats if len(t) >= LONGUEUR_MARQUEUR}
    candidats = {
        t for t in candidats
        if not MOTIF_CLE.match(t) and not MOTIF_LIBELLE_NORMALISE.match(t)
        and t not in JETONS_TECHNIQUES_PUBLICS}
    publics = corpus_public()
    return {t for t in candidats if t not in publics}


def corpus_public():
    """Tout le texte des fichiers suivis au commit de repère, normalisé : déjà public."""
    noms = git("ls-tree", "-r", "-z", "--name-only", COMMIT_DE_REPERE).stdout.split(b"\0")
    requete = b"".join(
        COMMIT_DE_REPERE.encode() + b":" + n + b"\n" for n in noms if n)
    sortie = git("cat-file", "--batch", input=requete).stdout
    morceaux = []
    position = 0
    while position < len(sortie):
        fin = sortie.index(b"\n", position)
        entete = sortie[position:fin].split()
        position = fin + 1
        if len(entete) != 3 or entete[1] != b"blob":
            continue
        taille = int(entete[2])
        contenu = sortie[position:position + taille]
        position += taille + 1
        if b"\0" in contenu[:8000]:
            continue
        morceaux.append(normaliser(contenu.decode("utf-8", errors="replace")))
    return "\n".join(morceaux)


def fichiers_modifies_ou_ajoutes():
    """Fichiers texte changés depuis le commit de repère, plus les non suivis non ignorés."""
    noms = set(noms_zero(git("diff", "--name-only", "-z", COMMIT_DE_REPERE).stdout))
    noms |= set(noms_zero(
        git("ls-files", "-z", "--others", "--exclude-standard").stdout))
    noms.discard(FICHE)
    return sorted(n for n in noms if os.path.isfile(os.path.join(RACINE, n)))


def localiser_marqueurs(marqueurs):
    """Liste de (fichier, ligne) où figure un marqueur. Jamais le marqueur lui-même."""
    trouves = []
    for nom in fichiers_modifies_ou_ajoutes():
        with open(os.path.join(RACINE, nom), "rb") as f:
            brut = f.read()
        if b"\0" in brut[:8000]:
            continue
        texte = brut.decode("utf-8", errors="replace")
        ligne_trouvee = False
        for numero, ligne in enumerate(texte.split("\n"), 1):
            normalisee = normaliser(ligne)
            if any(m in normalisee for m in marqueurs):
                trouves.append((nom, numero))
                ligne_trouvee = True
        if not ligne_trouvee and any(m in normaliser(texte) for m in marqueurs):
            trouves.append((nom, 0))   # un marqueur à cheval sur plusieurs lignes
    return trouves


# ----------------------------------------------------------------------- gardes

class FicheNonSuivie(unittest.TestCase):
    """La fiche n'est jamais dans l'index, et reste ignorée."""

    def setUp(self):
        if not git_disponible():
            self.skipTest("git indisponible ou dépôt absent : garde non jouée")

    def test_absente_de_l_index(self):
        # -z : sans lui, git échappe les chemins accentués à la façon du C et un
        # nom que l'on croit absent peut ne pas l'être.
        suivis = noms_zero(git("ls-files", "-z").stdout)
        fautifs = [n for n in suivis if os.path.basename(n) == FICHE]
        self.assertEqual(fautifs, [], "la fiche de démonstration est suivie par Git")

    def test_toujours_ignoree(self):
        code = git("check-ignore", "-q", FICHE).returncode
        self.assertEqual(
            code, 0,
            "la fiche n'est plus ignorée par Git (code %d) : retirer la ligne "
            "du .gitignore l'exposerait à un « git add »" % code)


class VocabulaireFictif(unittest.TestCase):
    """Les données de test et les exemples de grille n'emploient que le vocabulaire de D9."""

    def test_le_verificateur_mord(self):
        # Garde de la garde : un libellé hors vocabulaire doit être vu, et le
        # chemin rendu ne doit pas contenir la valeur.
        schema = {"blocs": [{"cle": "bloc-1", "champs": [
            {"type": "grille", "cle": "grille-1", "libelle": "Un mot de trop",
             "colonnes": [{"cle": "Colonne_1", "libelle": "Colonne 1", "nature": "case"}],
             "lignes": [{"cle": "ligne-1", "libelle": "Ligne 1", "neutralisees": ["x"]}]}]}]}
        fautes = verifier_vocabulaire(schema)
        self.assertEqual(
            sorted(fautes),
            sorted(["$.blocs[0].champs[0].libelle",
                    "$.blocs[0].champs[0].colonnes[0].cle",
                    "$.blocs[0].champs[0].lignes[0].neutralisees[0]"]))
        self.assertFalse(any("mot de trop" in f for f in fautes))

    def test_donnees_de_test(self):
        fichiers = sorted(f for f in os.listdir(DONNEES) if f.endswith(".json"))
        self.assertTrue(fichiers, "tests/donnees/ ne contient aucun fichier .json à contrôler")
        for nom in fichiers:
            with open(os.path.join(DONNEES, nom), encoding="utf-8") as f:
                fautes = verifier_vocabulaire(json.load(f))
            self.assertEqual(
                fautes, [],
                "tests/donnees/%s : valeur(s) hors du vocabulaire fictif aux chemins %s"
                % (nom, ", ".join(fautes)))

    def test_exemples_de_grille_de_la_specification(self):
        exemples = [b for b in blocs_json_de_la_specification() if '"grille"' in b]
        self.assertTrue(exemples, "la spécification ne porte aucun exemple JSON de grille")
        for i, bloc in enumerate(exemples):
            fautes = verifier_vocabulaire(json.loads(bloc))
            self.assertEqual(
                fautes, [],
                "docs/schema-formulaire.md, exemple de grille n°%d : valeur(s) hors du "
                "vocabulaire fictif aux chemins %s" % (i + 1, ", ".join(fautes)))


class AucunMarqueurDeLaFiche(unittest.TestCase):
    """Aucun texte propre à la fiche n'est entré dans un fichier modifié ou ajouté."""

    def setUp(self):
        if not os.path.isfile(os.path.join(RACINE, FICHE)):
            self.skipTest(FICHE + " absente de ce poste : garde non jouée (normal en CI)")
        if not git_disponible():
            self.skipTest("git indisponible : garde non jouée")
        if git("cat-file", "-e", COMMIT_DE_REPERE + "^{commit}").returncode != 0:
            self.skipTest("commit de repère absent (clone superficiel) : garde non jouée")

    def test_aucun_marqueur_dans_les_fichiers_changes(self):
        marqueurs = marqueurs_de_la_fiche()
        # Une fiche dont on ne tire aucun marqueur ferait passer la garde à vide.
        self.assertTrue(marqueurs, "aucun marqueur extrait de la fiche : la garde ne garderait rien")
        trouves = localiser_marqueurs(marqueurs)
        self.assertEqual(
            trouves, [],
            "texte de la fiche retrouvé dans : %s (le texte n'est volontairement pas "
            "affiché)" % ", ".join("%s:%d" % t for t in trouves))


if __name__ == "__main__":
    unittest.main()
