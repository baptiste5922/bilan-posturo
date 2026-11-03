"""Garde d'absence de l'identité du cabinet dans le dépôt (contrat C2-T1).

Avant cette tâche, l'identité de la praticienne (nom, adresse, courriel,
téléphone) était écrite en dur dans `formulaire/index.html` et
`formulaire/index-v1.html`. Elle vit désormais dans `config.json`, hors
suivi Git, lue par la route authentifiée `GET /cabinet`. Le pas
d'intégration continue qui protégeait ce fait (`.github/workflows/tests.yml`)
dérivait ses motifs du contenu de `#infos_podo` — devenu vide, il n'a plus
rien à lire, et une garde qui dériverait encore de cette source serait verte
à vide. Ce module la remplace par un contrôle d'**absence**, qui ne suppose
plus la présence de l'identité qu'il cherche.

Trois contrôles indépendants, aucun n'écrit la donnée recherchée :

1. **structurel** — l'ancre `<section id="infos_podo">` existe, dans les
   deux pages servies, et ne contient aucun caractère non blanc une fois les
   balises retirées. Échoue bruyamment si l'ancre est introuvable, plutôt
   que de rendre un résultat vide qui passerait au vert à tort — c'est
   exactement le défaut qui a fait échouer six travaux d'intégration
   continue le 14 octobre, et celui qu'a révélé un comparateur de C1-T3 le
   15 (`CLAUDE.md`, pièges connus) ;
2. **par motif générique, sur tout l'arbre suivi par `git`** — aucune
   adresse de courriel, aucun numéro de téléphone français complet, nulle
   part dans le dépôt, à l'exception des bibliothèques tierces vendues
   (`formulaire/lib/`, auteurs des bibliothèques, pas du cabinet). Aucune
   autre exclusion : une liste fermée de cibles autoriserait implicitement
   tout fichier absent de la liste à recopier une coordonnée sans que rien
   ne s'en aperçoive — c'est le constat moyen n°2 de l'audit C1-T3b, et
   c'est précisément ce qui est arrivé une fois à `tests/test_coquille.py`,
   jamais ajouté à l'ancienne liste ;
3. **par empreinte de token et de bigramme, sur le même arbre** — les deux
   contrôles précédents ne couvrent ni un nom ni une adresse recopiés HORS
   de l'ancre `#infos_podo`. Ce n'était pas théorique : `docs/contrats/
   C2-T1.md` portait lui-même, dans sa version d'origine, le motif de grep
   de l'inventaire — nom et prénom de la praticienne, nom de rue, préfixe
   de courriel — en clair, et les contrôles 1 et 2 passaient au vert dessus
   (le motif de courriel n'y figurait qu'en fragment sans `@`, celui de
   téléphone qu'en fragment à trois groupes sur les cinq attendus). Corrigé
   dans le contrat ; fermé ici mécaniquement (constat de revue C2-T1).

En cas d'échec, seuls un chemin, un numéro de ligne et — pour le contrôle 3 —
la NATURE de la forme trouvée (jamais sa valeur) sont nommés : le journal
d'intégration continue est public, et c'est précisément le canal que cette
garde existe pour fermer (même raison que `tests/test_coquille.py:140-146`).

Bibliothèque standard uniquement, compatible Python 3.9 et `python3 -O` (pas
d'`assert` nu : il s'évaporerait sous `-O`).

    python3 -m unittest tests.test_identite_absente
    python3 -O -m unittest tests.test_identite_absente
"""

import hashlib
import re
import subprocess
import unicodedata
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# Motifs dérivés du contrat (§9, étape 9), jamais resserrés ni élargis à la
# volée : un courriel standard, un numéro de téléphone français à dix
# chiffres (séparateurs espace/point/tiret facultatifs).
MOTIF_COURRIEL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
MOTIF_TELEPHONE = re.compile(r"\b0[1-9]([ .-]?[0-9]{2}){4}\b")

# Unique exclusion, et elle est justifiée : formulaire/lib/jspdf.umd.min.js
# porte le courriel de ses propres auteurs, une bibliothèque tierce vendue
# telle quelle, pas une coordonnée du cabinet (bruit mesuré avant écriture
# du contrat : zéro occurrence de téléphone dans tout le dépôt, une seule de
# courriel, à cet unique endroit).
EXCLUS = re.compile(r"^formulaire/lib/")

# Empreintes SHA-256 de formes jugées sans ambiguïté avec le concédant de la
# licence (homonyme partiel, §4 du contrat C2-T1) : jamais le nom de famille
# partagé seul — il ferait rougir LICENSE et confondrait les deux personnes,
# ce que le critère d'acceptation dédié interdit. Chaque entrée est
# justifiée par sa NATURE, jamais par sa valeur : écrire la valeur ici
# réintroduirait la donnée que ce fichier existe pour retirer.
#
# Limite honnête (à ne jamais maquiller en garantie) : une empreinte de
# token protège contre la RECOPIE LITTÉRALE d'une forme exacte, normalisée
# en minuscules et sans accent — pas contre une paraphrase, pas contre une
# césure qui couperait une forme composée en deux lignes ou deux fichiers,
# et un dictionnaire de prénoms ou de noms de rue plausibles suffirait à
# retrouver la valeur par force brute. C'est un filet, pas une preuve.
EMPREINTES_INTERDITES = {
    "b737901092b6ecca05d631bbcb6a231709b3a5e1881d8d21e2abaf8cf48cbb7f":
        "le prénom de la praticienne",
    "06b694153e57f6a9ad488fefe26d2acfc9c34ac654ed2db7fa96d00af49b0ada":
        "le second nom de famille de la praticienne, en bigramme avec "
        "l'article qui le précède (le premier est partagé avec le "
        "concédant de la licence et n'entre jamais dans cette liste)",
    "3a63ecacc86558496968499ac124c0ec741d7b25639d3792d8f124900e1e52b6":
        "le nom de la voie du cabinet, en bigramme (forme composée de "
        "deux mots)",
    "db00df3ba07025d210752817068871420ab02306685cdc9ca2d5eb1b16e3d633":
        "le préfixe local (avant l'arobase) du courriel professionnel",
}


def _fichiers_suivis():
    """Les chemins suivis par `git`, plus les fichiers nouveaux non ignorés.

    `git ls-files -z`, jamais `git ls-files | tr` : sans `-z`, git échappe
    les chemins non ASCII à la façon du C et les entoure de guillemets — or
    tous les documents de ce dépôt sont accentués. C'est ce qui a fait
    échouer six travaux d'intégration continue le 14 octobre (CLAUDE.md).

    `--others --exclude-standard` ajoute les fichiers créés mais pas encore
    indexés : ce sont ceux qui partiront au prochain `git add -A`, et l'arbre
    suivi seul ne les verrait qu'une fois poussés dans le dépôt public. Les
    fichiers ignorés (`config.json`, journaux, bilans) restent exclus.
    """
    sortie = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=str(RACINE), capture_output=True, check=True,
    ).stdout
    return [p for p in sortie.decode("utf-8").split("\0") if p]


def _extraire_balise(texte, nom_balise, nom_fichier):
    """Le fragment `<nom_balise ...>…</nom_balise>`, première occurrence.

    Reprise exacte de l'algorithme de `tests/test_coquille.py` (lui-même
    partagé avec `tests/test_comparaison_dom.js`) : une seconde version
    écrite à la main diverge tôt ou tard subtilement de la première.
    """
    motif = re.compile(r"<(/?)" + nom_balise + r"\b[^>]*>")
    debut = texte.find("<" + nom_balise)
    if debut == -1:
        raise AssertionError(
            "balise <%s> introuvable dans %s" % (nom_balise, nom_fichier)
        )
    profondeur = 0
    for m in motif.finditer(texte, debut):
        if m.group(1) == "/":
            profondeur -= 1
            if profondeur == 0:
                return texte[debut:m.end()]
        else:
            profondeur += 1
    raise AssertionError(
        "balise fermante </%s> introuvable dans %s" % (nom_balise, nom_fichier)
    )


def _tokeniser(texte):
    """Tokens alphanumériques, casse et accents neutralisés.

    Même méthode que `assainir_nom()` côté serveur (NFKD puis repli ASCII) :
    pas une seconde normalisation inventée qui diverge subtilement de la
    première.
    """
    texte = unicodedata.normalize("NFKD", texte)
    texte = texte.encode("ascii", "ignore").decode("ascii").lower()
    return re.findall(r"[a-z0-9]+", texte)


def _empreintes_dune_ligne(ligne):
    """Empreintes SHA-256 de chaque token, et de chaque bigramme (deux
    tokens consécutifs séparés d'une espace), d'une ligne — jamais au-delà
    d'une ligne : une forme composée coupée par un retour à la ligne y
    échappe, c'est la limite documentée ci-dessus."""
    tokens = _tokeniser(ligne)
    empreintes = {hashlib.sha256(tok.encode("ascii")).hexdigest() for tok in tokens}
    for i in range(len(tokens) - 1):
        bigramme = tokens[i] + " " + tokens[i + 1]
        empreintes.add(hashlib.sha256(bigramme.encode("ascii")).hexdigest())
    return empreintes


class AncreIdentiteVideDesDeuxPages(unittest.TestCase):
    """Contrôle structurel : `#infos_podo` existe et est vide, dans les deux
    pages servies (`formulaire/index.html` et `formulaire/index-v1.html`)."""

    def test_ancre_vide_dans_les_deux_pages(self):
        for nom in ("formulaire/index.html", "formulaire/index-v1.html"):
            chemin = RACINE / nom
            if not chemin.exists():
                raise AssertionError("%s n'existe pas" % nom)
            texte = chemin.read_text(encoding="utf-8")
            if '<section id="infos_podo">' not in texte:
                raise AssertionError(
                    "ancre <section id=\"infos_podo\"> introuvable dans %s : "
                    "cette garde ne peut plus localiser le bloc d'identité."
                    % nom
                )
            section = _extraire_balise(
                texte[texte.index('<section id="infos_podo">'):],
                "section", nom,
            )
            reste = re.sub(r"<[^>]*>", "", section).strip()
            if reste:
                raise AssertionError(
                    "%s : l'ancre #infos_podo porte encore du texte — "
                    "l'identité du cabinet ne doit plus être écrite dans "
                    "le dépôt (contrat C2-T1)" % nom
                )


class AucuneCoordonneeDansLArbreSuivi(unittest.TestCase):
    """Contrôle par motif générique, sur tout l'arbre suivi par `git` :
    aucune liste fermée de fichiers cibles, pour ne pas reproduire le
    constat moyen n°2 de l'audit C1-T3b (un fichier absent de la liste fuit
    sans alerte)."""

    def test_identite_absente_de_l_arbre_suivi(self):
        fautifs = []
        for chemin_relatif in _fichiers_suivis():
            if EXCLUS.match(chemin_relatif):
                continue

            chemin = RACINE / chemin_relatif
            if not chemin.is_file():
                # Un chemin que git liste mais que le disque ne porte plus
                # est un défaut de l'inventaire lui-même : la garde doit le
                # dire bruyamment, pas l'ignorer en silence.
                raise AssertionError(
                    "chemin suivi par git mais introuvable : %s"
                    % chemin_relatif
                )

            try:
                contenu = chemin.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                # Fichier binaire (image, archive…) : aucune coordonnée
                # textuelle n'y a de sens, et read_text lèverait dessus.
                continue

            for numero, ligne in enumerate(contenu.splitlines(), start=1):
                if MOTIF_COURRIEL.search(ligne) or MOTIF_TELEPHONE.search(ligne):
                    # Jamais le texte relevé, seulement sa coordonnée : le
                    # journal d'intégration continue est public, et c'est
                    # précisément le canal que cette garde ferme.
                    fautifs.append("%s:%d" % (chemin_relatif, numero))

        if fautifs:
            self.fail(
                "coordonnée (courriel ou téléphone) détectée, voir : "
                + ", ".join(fautifs)
            )


class AucunNomNiAdresseRecopiesAilleurs(unittest.TestCase):
    """Troisième contrôle, par empreinte de token et de bigramme (constat de
    revue C2-T1) : les deux contrôles précédents ne couvrent ni un nom ni
    une adresse recopiés HORS de l'ancre `#infos_podo` — et ce n'était pas
    théorique, voir le module ci-dessus.

    Chercher un nom suppose de l'écrire ; l'écrire dans ce fichier le
    réintroduirait dans le dépôt public. On compare donc des EMPREINTES
    (`EMPREINTES_INTERDITES`) : jamais la donnée elle-même, le mécanisme
    déjà éprouvé par le gel de `formulaire/index-v1.html`
    (`tests/test_coquille.py`)."""

    def test_aucune_empreinte_sensible_dans_l_arbre_suivi(self):
        fautifs = []
        for chemin_relatif in _fichiers_suivis():
            if EXCLUS.match(chemin_relatif):
                continue

            chemin = RACINE / chemin_relatif
            if not chemin.is_file():
                continue  # déjà signalé bruyamment par le contrôle précédent

            try:
                contenu = chemin.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            for numero, ligne in enumerate(contenu.splitlines(), start=1):
                trouvees = _empreintes_dune_ligne(ligne) & set(EMPREINTES_INTERDITES)
                if trouvees:
                    nature = EMPREINTES_INTERDITES[sorted(trouvees)[0]]
                    fautifs.append("%s:%d (%s)" % (chemin_relatif, numero, nature))

        if fautifs:
            self.fail(
                "forme correspondant à une empreinte interdite détectée, "
                "voir : " + ", ".join(fautifs)
            )



if __name__ == "__main__":
    unittest.main()
