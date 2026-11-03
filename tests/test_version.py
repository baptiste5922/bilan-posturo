"""Numéro de version (C4-T4) : une source unique, et rien qui en diverge.

`formulaire/version.json` est la source. Le serveur la lit au démarrage
(`lire_version()`, ligne DEMARRAGE de technique.log), le formulaire la lit
pour son pied de page (`afficherVersion()`, tests/test_version.js), et
`package.json` doit porter le même numéro : sinon une question de support
commencerait par deux réponses contradictoires à « quelle version avez-vous ? ».
"""

import json
import os
import sys
import tempfile
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "serveur"))

import serveur  # noqa: E402


def _lire_json(chemin):
    with open(os.path.join(RACINE, chemin), encoding="utf-8") as f:
        return json.load(f)


class SourceUnique(unittest.TestCase):

    def test_version_json_porte_un_numero_valide(self):
        version = _lire_json("formulaire/version.json").get("version")
        self.assertIsInstance(version, str)
        self.assertRegex(version, r"^[0-9A-Za-z.+-]{1,32}$")

    def test_package_json_ne_diverge_pas(self):
        if _lire_json("package.json").get("version") != _lire_json("formulaire/version.json").get("version"):
            self.fail("package.json et formulaire/version.json portent deux numéros différents")

    def test_le_serveur_lit_la_meme_version(self):
        if serveur.lire_version() != _lire_json("formulaire/version.json")["version"]:
            self.fail("lire_version() ne rend pas le numéro de formulaire/version.json")

    def test_le_paquet_emporte_la_version(self):
        with open(os.path.join(RACINE, "outils", "faire-paquet.sh"), encoding="utf-8") as f:
            script = f.read()
        if '"$PAQUET/formulaire/version.json"' not in script:
            self.fail("outils/faire-paquet.sh ne vérifie pas la présence de version.json")


class LectureSansLevee(unittest.TestCase):
    """Un fichier de version abîmé ne doit jamais empêcher le serveur de
    démarrer, ni faire entrer autre chose qu'un numéro dans technique.log."""

    def lire(self, contenu):
        dossier = tempfile.mkdtemp(prefix="bilan-test-version-")
        chemin = os.path.join(dossier, "version.json")
        if contenu is not None:
            with open(chemin, "w", encoding="utf-8") as f:
                f.write(contenu)
        try:
            return serveur.lire_version(chemin)
        finally:
            if os.path.exists(chemin):
                os.remove(chemin)
            os.rmdir(dossier)

    def test_fichier_absent(self):
        self.assertEqual(self.lire(None), serveur.VERSION_INCONNUE)

    def test_json_invalide(self):
        self.assertEqual(self.lire("{pas du json"), serveur.VERSION_INCONNUE)

    def test_racine_non_objet(self):
        self.assertEqual(self.lire('["1.0"]'), serveur.VERSION_INCONNUE)

    def test_numero_non_textuel(self):
        for valeur in ("null", "1", "{}", "true"):
            with self.subTest(valeur=valeur):
                self.assertEqual(self.lire('{"version": ' + valeur + "}"), serveur.VERSION_INCONNUE)

    def test_caracteres_hors_numero(self):
        # Ce qui ressemblerait à un champ de plus dans la ligne DEMARRAGE, un
        # chemin ou un saut de ligne ne passe jamais.
        for valeur in ("1.0 port=1", "../../x", "1.0\\nDEMARRAGE", "", "x" * 33):
            with self.subTest(valeur=valeur):
                self.assertEqual(self.lire(json.dumps({"version": valeur})), serveur.VERSION_INCONNUE)

    def test_numero_valide(self):
        self.assertEqual(self.lire('{"version": "2.0.0-rc.1+abc"}'), "2.0.0-rc.1+abc")


if __name__ == "__main__":
    unittest.main()
