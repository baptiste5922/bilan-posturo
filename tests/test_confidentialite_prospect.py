"""Gardes de confidentialité du premier prospect (C1-T6).

Le dépôt est public. `fiche_presentation.html`, à la racine, reprend le
protocole d'examen d'un formateur : elle est ignorée par Git (`.gitignore`) et
rien de ce qu'elle contient n'a le droit d'entrer dans un fichier versionné,
sauf accord écrit. Trois gardes, de la plus générale à la plus fine :

* `FicheNonSuivie` : la fiche n'est ni suivie, ni oubliée par l'ignorance ;
* `VocabulaireFictif` : les données de test et les exemples de grille de la
  spécification n'emploient que le vocabulaire fictif de D9 ;
* `AucunMarqueurDeLaFiche` : aucun texte de la fiche, qui ne soit déjà public,
  ne figure dans un fichier modifié ou ajouté depuis le commit de repère, ni
  dans un message de commit de la plage `repère..HEAD`, ni dans le nom d'une
  branche ou d'une étiquette locale, ni dans aucun blob introduit dans cette
  plage, même retiré depuis (C1-T6b : tout cela part sur GitHub, et un texte
  commité puis retiré avant la poussée reste public dans l'historique).

Règle de cette suite : un échec ne nomme **jamais** ce qu'il a trouvé, seulement
le fichier et le numéro de ligne, le SHA abrégé et la ligne d'un message, le SHA
abrégé, le chemin et la ligne d'un blob, ou le rang d'une référence (même règle
que la garde d'identité de C1-T1). Les journaux d'intégration continue sont
publics eux aussi.

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
COMMIT_DE_REPERE = "1ec796c172bf1dcc9129bd0331fa6368edddb8c0"
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
# Attributs HTML dont la valeur est un identifiant ou un texte propre à la fiche
# (audit de C1-T6) : `id`, `class` (découpée en jetons), `name`, `for`, les textes
# affichés ou lus par un lecteur d'écran, et tout `aria-*` / `data-*`. Le schéma
# d'un prospect est fait de clés et de libellés : les identifiants comptent
# autant que le texte visible.
ATTRIBUTS_TEXTUELS = frozenset(
    ["id", "class", "name", "for", "placeholder", "title", "alt", "value", "label"])
PREFIXES_ATTRIBUTS = ("aria-", "data-")
# Deux exemptions, écrites parce que le contrat se heurtait à lui-même au premier
# essai (voir « Un vrai positif, trouvé en cours de route » dans
# docs/audits/C1-T6-mises-en-echec.md) : D9 impose des clés
# « grille-N » que la fiche emploie aussi, et la décision D12 nomme l'attribut
# standard `aria-label`, qui n'était pas encore dans le dépôt. Un texte du
# vocabulaire fictif est public par construction ; un nom d'attribut WAI-ARIA
# l'est par la norme. Cette liste est fermée et ne s'allonge pas à la volée : un
# nouveau faux positif est une décision de l'architecte, pas un réglage.
JETONS_TECHNIQUES_PUBLICS = frozenset(["aria-label"])
# Attributs qui portent une adresse ou une image embarquée : `src` et `href`
# sont récoltés en entier (C1-T6b), car la fiche embarque des images en URI
# `data:` et porte des ancres `#…` dont le nom est un identifiant de la fiche.
ATTRIBUTS_DE_REFERENCE = frozenset(["src", "href"])
# Une exemption de message est un couple (SHA complet, numéro de ligne) : elle
# ne peut couvrir qu'une ligne d'un commit immuable, ne recopie aucun texte, et
# `test_exemptions_toujours_justifiees` l'empêche de survivre à sa raison. Elle
# désigne la ligne 1 d'un commit où la garde a trouvé une correspondance
# fortuite, jugée par l'audit de C1-T6 (constat « Faible — messages de
# commit ») ; ce commit est déjà poussé, l'historique ne se récrit pas. Liste
# fermée : une entrée nouvelle est une décision de l'architecte, pas un réglage.
# Le texte en cause n'est jamais recopié.
MESSAGES_EXEMPTES = frozenset([("fbf905a144aba6895a0835c9ecc396225c2473cb", 1)])
# Ces deux SHA appartiennent à l'historique de `c1-t6-grille`. Une fusion qui le
# réécrit (squash, rebase) les fera disparaître : `test_exemptions_toujours_
# justifiees` échouera alors sur le poste qui détient la fiche, et la conduite
# est de retirer l'exemption devenue sans objet — pas d'en ajouter une autre
# sans décision de l'architecte.
# Même principe pour un blob de l'historique : un couple (SHA complet du blob,
# numéro de ligne), jamais un texte. Il désigne la ligne 620 de l'ancienne
# version de la feuille de style que ce commit a introduite et que le suivant a
# remplacée : la garde y a trouvé la même correspondance fortuite de huit
# caractères que celle qui exempte le message ci-dessus (audit de C1-T6b). Ce
# blob est déjà poussé ; l'historique ne se récrit pas. Liste fermée, une seule
# entrée, couverte par `test_exemptions_toujours_justifiees` : une entrée
# nouvelle est une décision de l'architecte, pas un réglage. Le texte en cause
# n'est jamais recopié.
BLOBS_EXEMPTES = frozenset([("81f06a971edcf5b5c11945dbb32e53f72b6acab1", 620)])
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
    """Récolte les nœuds texte, les valeurs d'attributs textuels ou de référence
    (`src`, `href`) et, dans les scripts, les littéraux entre guillemets.
    `style` reste non récolté."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.textes = []
        self._dans_script = False
        self._dans_style = False

    def handle_starttag(self, balise, attributs):
        for nom, valeur in attributs:
            if not valeur:
                continue
            if nom in ATTRIBUTS_TEXTUELS or nom.startswith(PREFIXES_ATTRIBUTS):
                if nom == "class":
                    self.textes.extend(valeur.split())
                else:
                    self.textes.append(valeur)
            elif nom in ATTRIBUTS_DE_REFERENCE:
                self.textes.append(valeur)
                # L'ancre sans son « # » : c'est l'identifiant qu'un fichier
                # versionné recopierait. La charge utile d'une URI `data:`
                # sans son en-tête : c'est elle qui est propre à la fiche.
                if nom == "href" and valeur.startswith("#"):
                    self.textes.append(valeur[1:])
                if valeur.startswith("data:") and "," in valeur:
                    self.textes.append(valeur.split(",", 1)[1])
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
    arbre = git("ls-tree", "-r", "-z", "--name-only", COMMIT_DE_REPERE)
    if arbre.returncode != 0:
        raise RuntimeError("git ls-tree a échoué (code %d)" % arbre.returncode)
    noms = arbre.stdout.split(b"\0")
    requete = b"".join(
        COMMIT_DE_REPERE.encode() + b":" + n + b"\n" for n in noms if n)
    lecture = git("cat-file", "--batch", input=requete)
    if lecture.returncode != 0:
        raise RuntimeError("git cat-file a échoué (code %d)" % lecture.returncode)
    sortie = lecture.stdout
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
    diff = git("diff", "--name-only", "-z", COMMIT_DE_REPERE)
    autres = git("ls-files", "-z", "--others", "--exclude-standard")
    # Un git en échec ferait passer la garde à vide : il doit lever.
    for sortie in (diff, autres):
        if sortie.returncode != 0:
            raise RuntimeError("git a échoué (code %d) en listant les fichiers changés"
                               % sortie.returncode)
    noms = set(noms_zero(diff.stdout))
    noms |= set(noms_zero(autres.stdout))
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
        # Le texte entier n'est normalisé qu'une fois, hors du générateur : dans
        # `any(...)`, il l'était une fois par marqueur.
        entier = None if ligne_trouvee else normaliser(texte)
        if entier is not None and any(m in entier for m in marqueurs):
            trouves.append((nom, 0))   # un marqueur à cheval sur plusieurs lignes
    return trouves


def localiser_dans_messages(messages, marqueurs, exemptions):
    """Liste triée de (sha complet, ligne) d'un message qui porte un marqueur.

    `messages` : liste de (sha complet, texte). Les couples de `exemptions` sont
    retirés : une exemption est ancrée sur un commit et une ligne, jamais sur un
    texte. Jamais le marqueur lui-même.
    """
    trouves = set()
    for sha, texte in messages:
        ligne_trouvee = False
        for numero, ligne in enumerate(texte.split("\n"), 1):
            normalisee = normaliser(ligne)
            if any(m in normalisee for m in marqueurs):
                trouves.add((sha, numero))
                ligne_trouvee = True
        entier = None if ligne_trouvee else normaliser(texte)
        if entier is not None and any(m in entier for m in marqueurs):
            trouves.add((sha, 0))   # un marqueur à cheval sur plusieurs lignes
    return sorted(trouves - set(exemptions))


def localiser_dans_blobs(blobs, marqueurs, exemptions):
    """Liste triée de (sha complet, chemin, ligne) d'un blob qui porte un marqueur.

    `blobs` : liste de (sha complet, chemin ou "", texte ou None) ; un texte à
    None est un blob binaire, qu'on ne lit pas. Les couples (sha, ligne) de
    `exemptions` sont retirés : une exemption est ancrée sur un blob et une
    ligne, jamais sur un texte. Jamais le marqueur lui-même.
    """
    trouves = set()
    for sha, chemin, texte in blobs:
        if texte is None:
            continue
        # Un premier passage sur le blob entier évite de normaliser chaque ligne
        # des blobs qui ne portent rien (la plupart) : ce qu'une ligne contient,
        # le texte entier le contient aussi. Le texte n'est normalisé qu'une
        # fois par blob, hors du générateur (il l'était une fois par marqueur).
        entier = normaliser(texte)
        if not any(m in entier for m in marqueurs):
            continue
        ligne_trouvee = False
        for numero, ligne in enumerate(texte.split("\n"), 1):
            normalisee = normaliser(ligne)
            if any(m in normalisee for m in marqueurs):
                trouves.add((sha, chemin, numero))
                ligne_trouvee = True
        if not ligne_trouvee:
            trouves.add((sha, chemin, 0))   # un marqueur à cheval sur plusieurs lignes
    exemptes = set(exemptions)
    return sorted(t for t in trouves if (t[0], t[2]) not in exemptes)


def localiser_dans_noms(noms, marqueurs):
    """Rangs (à partir de 1) des noms de référence qui portent un marqueur.

    Le rang et jamais le nom : un nom de branche porteur est justement ce que la
    garde est là pour ne pas laisser passer dans un journal public.
    """
    return [rang for rang, nom in enumerate(noms, 1)
            if any(m in normaliser(nom) for m in marqueurs)]


def messages_de_commit():
    """Liste de (sha complet, texte) des commits de `repère..HEAD`."""
    plage = COMMIT_DE_REPERE + "..HEAD"
    sortie = git("log", "-z", "--format=%H%x00%B", plage)
    if sortie.returncode != 0:
        raise RuntimeError("git log %s a échoué (code %d)" % (plage, sortie.returncode))
    morceaux = sortie.stdout.split(b"\0")
    if morceaux and morceaux[-1].strip() == b"":
        morceaux.pop()
    if len(morceaux) % 2 != 0:
        raise RuntimeError("sortie de git log inattendue : %d morceaux" % len(morceaux))
    return [(morceaux[i].decode("ascii").strip(),
             morceaux[i + 1].decode("utf-8", errors="replace"))
            for i in range(0, len(morceaux), 2)]


def nombre_de_commits_de_la_plage():
    """Compte indépendant (`rev-list --count`), pour que la lecture ne soit pas muette."""
    sortie = git("rev-list", "--count", COMMIT_DE_REPERE + "..HEAD")
    if sortie.returncode != 0:
        raise RuntimeError("git rev-list a échoué (code %d)" % sortie.returncode)
    return int(sortie.stdout.strip())


def blobs_de_la_plage():
    """Liste de (sha complet, chemin, texte ou None) des blobs introduits dans `repère..HEAD`.

    Tout blob que la plage fait entrer dans le dépôt, qu'il figure encore dans
    l'arbre ou non : c'est ce que l'état final des fichiers ne montre pas. Le
    chemin est celui sous lequel `git rev-list --objects` rencontre le blob en
    premier. Un texte à None est un blob binaire. Un objet manquant lève.
    """
    plage = COMMIT_DE_REPERE + "..HEAD"
    liste = git("rev-list", "--objects", plage)
    if liste.returncode != 0:
        raise RuntimeError("git rev-list --objects %s a échoué (code %d)" % (plage, liste.returncode))
    chemins, ordre = {}, []
    for ligne in liste.stdout.decode("utf-8", errors="replace").split("\n"):
        if not ligne:
            continue
        sha, _, chemin = ligne.partition(" ")
        if sha not in chemins:
            chemins[sha] = chemin
            ordre.append(sha)
    lecture = git("cat-file", "--batch", input="".join(s + "\n" for s in ordre).encode("ascii"))
    if lecture.returncode != 0:
        raise RuntimeError("git cat-file --batch a échoué (code %d)" % lecture.returncode)
    sortie = lecture.stdout
    blobs, lus, position = [], 0, 0
    while position < len(sortie):
        fin = sortie.index(b"\n", position)
        entete = sortie[position:fin].split()
        position = fin + 1
        if len(entete) == 2 and entete[1] == b"missing":
            raise RuntimeError("objet manquant dans la plage : %s" % entete[0].decode("ascii")[:12])
        if len(entete) != 3:
            raise RuntimeError("entête de git cat-file inattendu")
        taille = int(entete[2])
        contenu = sortie[position:position + taille]
        position += taille + 1
        lus += 1
        if entete[1] != b"blob":
            continue
        sha = entete[0].decode("ascii")
        if b"\0" in contenu[:8000]:
            blobs.append((sha, chemins[sha], None))
        else:
            blobs.append((sha, chemins[sha], contenu.decode("utf-8", errors="replace")))
    if lus != len(ordre):
        raise RuntimeError("git cat-file a rendu %d objets pour %d demandés" % (lus, len(ordre)))
    return blobs


def nombre_de_blobs_de_la_plage():
    """Compte indépendant (`rev-list` puis `cat-file --batch-check`), pour que la lecture ne soit pas muette."""
    liste = git("rev-list", "--objects", COMMIT_DE_REPERE + "..HEAD")
    if liste.returncode != 0:
        raise RuntimeError("git rev-list --objects a échoué (code %d)" % liste.returncode)
    shas = []
    for ligne in liste.stdout.split(b"\n"):
        if ligne.strip():
            sha = ligne.split(b" ", 1)[0]
            if sha not in shas:
                shas.append(sha)
    types = git("cat-file", "--batch-check=%(objecttype)", input=b"".join(s + b"\n" for s in shas))
    if types.returncode != 0:
        raise RuntimeError("git cat-file --batch-check a échoué (code %d)" % types.returncode)
    return len([t for t in types.stdout.split(b"\n") if t.strip() == b"blob"])


def noms_de_reference():
    """Noms courts des branches et étiquettes locales : ce qui peut être poussé."""
    sortie = git("for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/tags")
    if sortie.returncode != 0:
        raise RuntimeError("git for-each-ref a échoué (code %d)" % sortie.returncode)
    return [n for n in sortie.stdout.decode("utf-8", errors="replace").split("\n") if n]


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


class ExtractionDeLaFiche(unittest.TestCase):
    """Garde de la garde : l'extraction voit les attributs, sans fiche ni git."""

    def test_valeurs_d_attributs_et_litteraux(self):
        extracteur = _ExtracteurDeFiche()
        extracteur.feed(
            '<p id="un-identifiant" class="classe-a classe-b" name="un-nom" for="un-for" '
            'placeholder="un-texte" title="un-titre" alt="un-alt" value="une-valeur" '
            'label="une-etiquette" aria-label="une-aria" data-cle="une-donnee" '
            'href="#une-ancre" src="data:image/png;base64,UNECHARGE" '
            'style="pas-recolte-non-plus">Un texte</p>'
            '<script>var a = "un-litteral"; // l\'apostrophe d\'un commentaire\n</script>')
        extracteur.close()
        attendus = ["un-identifiant", "classe-a", "classe-b", "un-nom", "un-for", "un-texte",
                    "un-titre", "un-alt", "une-valeur", "une-etiquette", "une-aria",
                    "une-donnee", "Un texte", "un-litteral",
                    "#une-ancre", "une-ancre",
                    "data:image/png;base64,UNECHARGE", "UNECHARGE"]
        for attendu in attendus:
            self.assertIn(attendu, extracteur.textes, "valeur non récoltée par l'extraction")
        self.assertNotIn("pas-recolte-non-plus", extracteur.textes)
        self.assertFalse(any("apostrophe" in t for t in extracteur.textes))


class ReperageHorsFichiers(unittest.TestCase):
    """Garde de la garde pour les messages et les noms : sans fiche ni git, donc en CI."""

    MARQUEUR = "un-marqueur-factice"
    SHA_A = "a" * 40
    SHA_B = "b" * 40

    def test_un_marqueur_est_trouve_a_la_bonne_ligne(self):
        messages = [(self.SHA_A, "Un titre\n\nUn corps avec %s dedans\n" % self.MARQUEUR)]
        self.assertEqual(
            localiser_dans_messages(messages, {self.MARQUEUR}, frozenset()),
            [(self.SHA_A, 3)])

    def test_l_exemption_ne_couvre_que_sa_ligne(self):
        messages = [(self.SHA_A, "%s\nrien\n%s" % (self.MARQUEUR, self.MARQUEUR))]
        self.assertEqual(
            localiser_dans_messages(messages, {self.MARQUEUR}, frozenset([(self.SHA_A, 1)])),
            [(self.SHA_A, 3)])

    def test_l_exemption_ne_couvre_pas_un_autre_commit(self):
        messages = [(self.SHA_B, self.MARQUEUR)]
        self.assertEqual(
            localiser_dans_messages(messages, {self.MARQUEUR}, frozenset([(self.SHA_A, 1)])),
            [(self.SHA_B, 1)])

    def test_un_marqueur_coupe_par_un_saut_de_ligne_donne_la_ligne_zero(self):
        coupe = "un-marqueur\nfactice"
        messages = [(self.SHA_A, "Titre\n" + coupe)]
        self.assertEqual(
            localiser_dans_messages(messages, {"un-marqueur factice"}, frozenset()),
            [(self.SHA_A, 0)])

    def test_aucun_element_rendu_ne_contient_le_marqueur(self):
        messages = [(self.SHA_A, "Titre\n%s" % self.MARQUEUR)]
        rendu = localiser_dans_messages(messages, {self.MARQUEUR}, frozenset())
        self.assertTrue(rendu, "la garde de la garde ne trouve rien : elle ne mord pas")
        self.assertNotIn(self.MARQUEUR, repr(rendu))
        rangs = localiser_dans_noms(["main", "x-%s" % self.MARQUEUR], {self.MARQUEUR})
        self.assertNotIn(self.MARQUEUR, repr(rangs))

    def test_un_nom_de_branche_porteur_est_rendu_par_son_rang(self):
        noms = ["main", "c1-t6-grille", "essai-%s-fin" % self.MARQUEUR, "autre"]
        self.assertEqual(localiser_dans_noms(noms, {self.MARQUEUR}), [3])

    def test_un_blob_porteur_est_trouve_avec_son_chemin_et_sa_ligne(self):
        blobs = [(self.SHA_A, "dossier/fichier.css", "a\nb\n%s\n" % self.MARQUEUR)]
        rendu = localiser_dans_blobs(blobs, {self.MARQUEUR}, frozenset())
        self.assertEqual(rendu, [(self.SHA_A, "dossier/fichier.css", 3)])
        self.assertNotIn(self.MARQUEUR, repr(rendu))

    def test_l_exemption_de_blob_ne_couvre_que_sa_ligne_et_son_blob(self):
        blobs = [(self.SHA_A, "x", "%s\n%s" % (self.MARQUEUR, self.MARQUEUR)),
                 (self.SHA_B, "y", self.MARQUEUR)]
        self.assertEqual(
            localiser_dans_blobs(blobs, {self.MARQUEUR}, frozenset([(self.SHA_A, 1)])),
            [(self.SHA_A, "x", 2), (self.SHA_B, "y", 1)])

    def test_un_marqueur_de_blob_coupe_par_un_saut_de_ligne_donne_la_ligne_zero(self):
        blobs = [(self.SHA_A, "x", "debut\nun-marqueur\nfactice")]
        self.assertEqual(
            localiser_dans_blobs(blobs, {"un-marqueur factice"}, frozenset()),
            [(self.SHA_A, "x", 0)])

    def test_un_blob_binaire_n_est_pas_lu(self):
        self.assertEqual(
            localiser_dans_blobs([(self.SHA_A, "x.png", None)], {self.MARQUEUR}, frozenset()), [])

    def test_aucun_marqueur_aucun_resultat(self):
        self.assertEqual(localiser_dans_messages([(self.SHA_A, "Titre")], {self.MARQUEUR}, frozenset()), [])
        self.assertEqual(localiser_dans_noms(["main"], {self.MARQUEUR}), [])


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

    def test_aucun_marqueur_dans_les_messages_de_commit(self):
        marqueurs = marqueurs_de_la_fiche()
        self.assertTrue(marqueurs, "aucun marqueur extrait de la fiche : la garde ne garderait rien")
        messages = messages_de_commit()
        # Une lecture muette (git log qui ne rend rien) ferait passer la garde à vide.
        self.assertEqual(
            len(messages), nombre_de_commits_de_la_plage(),
            "la lecture des messages ne rend pas autant de commits que la plage en compte")
        trouves = localiser_dans_messages(messages, marqueurs, MESSAGES_EXEMPTES)
        self.assertEqual(
            trouves, [],
            "texte de la fiche retrouvé dans les messages de : %s (le texte n'est "
            "volontairement pas affiché ; un message non poussé se corrige par "
            "git commit --amend)" % ", ".join("%s:%d" % (sha[:12], n) for sha, n in trouves))

    def test_aucun_marqueur_dans_les_blobs_de_la_plage(self):
        # Un texte commité puis retiré avant la poussée n'est plus dans l'arbre,
        # mais il reste public dans l'historique : seul le blob le montre.
        marqueurs = marqueurs_de_la_fiche()
        self.assertTrue(marqueurs, "aucun marqueur extrait de la fiche : la garde ne garderait rien")
        blobs = blobs_de_la_plage()
        self.assertEqual(
            len(blobs), nombre_de_blobs_de_la_plage(),
            "la lecture des blobs ne rend pas autant d'objets que la plage en compte")
        trouves = localiser_dans_blobs(blobs, marqueurs, BLOBS_EXEMPTES)
        self.assertEqual(
            trouves, [],
            "texte de la fiche retrouvé dans les blobs : %s (le texte n'est volontairement "
            "pas affiché ; un blob non poussé se retire en réécrivant les commits)"
            % ", ".join("%s (%s):%d" % (sha[:12], chemin, n) for sha, chemin, n in trouves))

    def test_aucun_marqueur_dans_les_noms_de_reference(self):
        marqueurs = marqueurs_de_la_fiche()
        self.assertTrue(marqueurs, "aucun marqueur extrait de la fiche : la garde ne garderait rien")
        noms = noms_de_reference()
        self.assertTrue(noms, "aucune branche ni étiquette lue : la garde ne garderait rien")
        rangs = localiser_dans_noms(noms, marqueurs)
        self.assertEqual(
            rangs, [],
            "texte de la fiche retrouvé dans le nom des références de rang : %s (le nom "
            "n'est volontairement pas affiché)" % ", ".join(str(r) for r in rangs))

    def test_exemptions_toujours_justifiees(self):
        # Une exemption ne doit pas survivre à sa raison : elle désigne un commit
        # encore dans la plage et une ligne qui porte encore un marqueur.
        marqueurs = marqueurs_de_la_fiche()
        self.assertTrue(marqueurs, "aucun marqueur extrait de la fiche : la garde ne garderait rien")
        messages = messages_de_commit()
        presents = {sha for sha, _ in messages}
        encore_porteurs = set(localiser_dans_messages(messages, marqueurs, frozenset()))
        sans_objet = [
            "message %s:%d" % (sha[:12], ligne) for sha, ligne in sorted(MESSAGES_EXEMPTES)
            if sha not in presents or (sha, ligne) not in encore_porteurs]
        blobs = blobs_de_la_plage()
        blobs_presents = {sha for sha, _, _ in blobs}
        # Seuls les blobs exemptés comptent ici : relire toute la plage doublerait
        # le temps de la garde sans rien prouver de plus.
        exemptes = {sha for sha, _ in BLOBS_EXEMPTES}
        blobs_porteurs = {(sha, ligne) for sha, _, ligne in localiser_dans_blobs(
            [b for b in blobs if b[0] in exemptes], marqueurs, frozenset())}
        sans_objet += [
            "blob %s:%d" % (sha[:12], ligne) for sha, ligne in sorted(BLOBS_EXEMPTES)
            if sha not in blobs_presents or (sha, ligne) not in blobs_porteurs]
        self.assertEqual(
            sans_objet, [],
            "exemption sans objet (objet absent de la plage ou ligne sans marqueur) : %s"
            % ", ".join(sans_objet))


if __name__ == "__main__":
    unittest.main()
