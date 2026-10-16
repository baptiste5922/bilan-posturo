"""Tests de la coquille de production (contrat C1-T3b).

Depuis la bascule, `formulaire/index.html` n'est plus le formulaire écrit à
la main : c'est une coquille qui délègue le corps du bilan au moteur
(`formulaire/moteur/rendu.js`, `formulaire/schema.json`). `formulaire/index
-v1.html` est la copie gelée de l'ancien `index.html`, servie à la même
adresse comme fiche de secours (niveau 1 du retour arrière, contrat §11).

Quatre familles de vérifications, qui protègent chacune un défaut précis :

1. l'empreinte de la fiche de secours n'a pas bougé d'un octet — la modifier
   reviendrait à créer une seconde implémentation à maintenir ;
2. l'en-tête de la coquille reste identique à celui de la fiche de secours,
   et l'identité du cabinet (ancre `#infos_podo`) y est bien présente ;
3. les `id` que la coquille émet et ceux qu'`IDS_RESERVES_COQUILLE`
   (`formulaire/moteur/rendu.js`) réserve sont le même ensemble, dans les
   deux sens — une liste non vérifiée finit par mentir ;
4. la page provisoire du moteur (`formulaire/index-moteur.html`) n'est pas
   revenue.

Bibliothèque standard uniquement, compatible Python 3.9, comme le reste de
`tests/`.

    python3 -m unittest tests.test_coquille
"""

import hashlib
import re
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
INDEX_V1 = RACINE / "formulaire" / "index-v1.html"
COQUILLE = RACINE / "formulaire" / "index.html"
INDEX_MOTEUR = RACINE / "formulaire" / "index-moteur.html"
RENDU_JS = RACINE / "formulaire" / "moteur" / "rendu.js"

EMPREINTE_V1_ATTENDUE = (
    "589eee333e68bdbde9e46c1343392e767baa5cfa6b1abfee02026d9431958a6e"
)


def _lire(chemin):
    return chemin.read_text(encoding="utf-8")


def _empreinte(chemin):
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def _extraire_balise(texte, nom_balise, nom_fichier):
    """Le fragment `<nom_balise ...>…</nom_balise>`, première occurrence.

    Compte les ouvertures/fermetures pour supporter une balise imbriquée
    dans elle-même (aucun cas ici, mais c'est le même algorithme que
    `tests/test_comparaison_dom.js`, pour ne pas en réinventer un second qui
    diverge subtilement du premier).
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


def _ids_dans(texte):
    """Les `id="..."` littéraux, dans l'ordre d'apparition, doublons compris.

    Même forme que le `grep -o 'id="[^"]*"'` du contrat : si un `id` venait
    à s'écrire sous une autre forme (apostrophes, sans guillemet), ce test
    ne le verrait pas — mais la coquille n'en émet aujourd'hui aucun sous
    cette forme, et un tel changement serait lui-même visible ailleurs
    (groupe 8 de `tests/test_inventaire_formulaire.js`).
    """
    return re.findall(r'id="([^"]*)"', texte)


def _ids_reserves_coquille(texte_js):
    """Lit la ligne `IDS_RESERVES_COQUILLE = new Set([...])` de rendu.js.

    Échoue bruyamment si la ligne a changé de forme, plutôt que de rendre un
    ensemble vide qui ferait passer la comparaison au vert à vide.
    """
    m = re.search(
        r"IDS_RESERVES_COQUILLE\s*=\s*new Set\(\[([^\]]*)\]\)", texte_js
    )
    if not m:
        raise AssertionError(
            "la déclaration de IDS_RESERVES_COQUILLE n'a pas été trouvée "
            "sous la forme attendue dans formulaire/moteur/rendu.js"
        )
    return re.findall(r'"([^"]*)"', m.group(1))


class EmpreinteDeLaFicheDeSecours(unittest.TestCase):
    """`formulaire/index-v1.html` est gelé à l'empreinte de l'ancien `index.html`."""

    def test_empreinte_inchangee(self):
        self.assertTrue(INDEX_V1.exists(), "formulaire/index-v1.html n'existe pas")
        self.assertEqual(
            _empreinte(INDEX_V1), EMPREINTE_V1_ATTENDUE,
            "formulaire/index-v1.html a été modifié : ce n'est plus la V1 gelée. "
            "Le modifier n'est pas un retour arrière, c'est créer une seconde "
            "implémentation à maintenir.",
        )


class IntegriteDeLEnTete(unittest.TestCase):
    """L'en-tête de la coquille reste celui de la fiche de secours, identité comprise."""

    @classmethod
    def setUpClass(cls):
        cls.v1 = _lire(INDEX_V1)
        cls.coquille = _lire(COQUILLE)

    def test_en_tete_identique_hors_espaces(self):
        # Constat moyen n°1 (audit C1-T3b) : comparer les CHAÎNES elles-mêmes
        # ferait imprimer assertMultiLineEqual() en cas d'écart — nom,
        # adresse, courriel et téléphone du cabinet — dans la sortie
        # d'intégration continue, publique. On compare donc deux empreintes
        # SHA-256 : un écart se voit (les deux empreintes diffèrent), mais ne
        # publie jamais le texte qui a changé.
        en_tete_v1 = _extraire_balise(self.v1, "header", "formulaire/index-v1.html")
        en_tete_coquille = _extraire_balise(self.coquille, "header", "formulaire/index.html")
        normaliser = lambda t: re.sub(r"\s+", " ", t).strip()
        empreinte = lambda t: hashlib.sha256(t.encode("utf-8")).hexdigest()
        self.assertEqual(
            empreinte(normaliser(en_tete_v1)), empreinte(normaliser(en_tete_coquille)),
            "l'en-tête de la coquille a dérivé de celui de la fiche de secours "
            "(formulaire/index-v1.html) — empreintes différentes, contenu non affiché "
            "pour ne pas publier l'identité du cabinet dans ce journal",
        )

    def test_ancre_identite_presente_avec_son_texte(self):
        for nom, texte in (("formulaire/index.html", self.coquille),
                            ("formulaire/index-v1.html", self.v1)):
            self.assertIn('<section id="infos_podo">', texte, "ancre introuvable dans %s" % nom)
            section = _extraire_balise(
                texte[texte.index('<section id="infos_podo">'):], "section", nom
            )
            lignes = [
                l.strip() for l in re.sub(r"<[^>]*>", "\n", section).split("\n")
                if l.strip()
            ]
            self.assertTrue(lignes, "aucune ligne de texte dans l'ancre #infos_podo de %s" % nom)


class IdsReservesCoquille(unittest.TestCase):
    """`IDS_RESERVES_COQUILLE` (moteur) == les `id` réellement émis par la coquille."""

    def test_ensembles_egaux_dans_les_deux_sens(self):
        ids_coquille = set(_ids_dans(_lire(COQUILLE)))
        ids_reserves = set(_ids_reserves_coquille(_lire(RENDU_JS)))

        manquants_du_moteur = ids_coquille - ids_reserves
        en_trop_dans_le_moteur = ids_reserves - ids_coquille

        if manquants_du_moteur:
            self.fail(
                "id de la coquille non réservé(s) dans IDS_RESERVES_COQUILLE : "
                + ", ".join(sorted(manquants_du_moteur))
            )
        if en_trop_dans_le_moteur:
            self.fail(
                "entrée(s) de IDS_RESERVES_COQUILLE sans id correspondant dans "
                "la coquille : " + ", ".join(sorted(en_trop_dans_le_moteur))
            )

    def test_vingt_et_un_ids(self):
        ids_coquille = set(_ids_dans(_lire(COQUILLE)))
        self.assertEqual(
            len(ids_coquille), 21,
            "la coquille émet %d id unique(s), 21 attendus : %s"
            % (len(ids_coquille), ", ".join(sorted(ids_coquille))),
        )


class AbsenceDeLaPageProvisoire(unittest.TestCase):
    """`formulaire/index-moteur.html` a disparu, et ne doit pas réapparaître."""

    def test_index_moteur_absent(self):
        self.assertFalse(
            INDEX_MOTEUR.exists(),
            "formulaire/index-moteur.html est de retour : la production est "
            "désormais la coquille (formulaire/index.html), cette page "
            "provisoire n'a plus de raison d'être.",
        )


if __name__ == "__main__":
    unittest.main()
