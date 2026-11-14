"""L'adresse de publication d'un client n'entre jamais dans le dépôt (C5-T2b, B21).

Le dépôt est public. L'adresse d'un paquet de mise à jour (D-M1, voie (d)) a la
forme `https://<hôte>/<32 caractères hexadécimaux>/<canal>.zip` : elle n'est pas un
secret cryptographique (elle protège du code public et un schéma, aucune donnée
de santé) mais elle **identifie un client** et ouvre son paquet. Elle vit dans le
`config.json` du cabinet et dans `adresse-publication.json`, dans le dossier de
travail de l'atelier : ces deux fichiers sont hors du dépôt.

Jusqu'ici aucune garde ne lisait le CONTENU des fichiers à la recherche d'une
adresse : le contrôle de la CI ne connaît que des noms de fichiers. Celle-ci
cherche, dans tout ce que le dépôt versionne et dans tout ce que la branche de
tâche y a fait entrer depuis le commit de repère, une URL dont un segment fait
exactement 32 caractères hexadécimaux.

Règle de cette suite, la même que celle de `test_confidentialite_prospect.py` :
un échec ne nomme **jamais** ce qu'il a trouvé, seulement un rang, un numéro de
ligne ou un SHA abrégé. Les journaux d'intégration continue sont publics, et une
adresse trouvée est justement ce qu'il ne faut pas y écrire. Les tests de
mise à jour n'emploient donc que des adresses de la forme
`https://127.0.0.1:<port>/essai/stable.zip`.

Bibliothèque standard seule ; aucun `assert` nu (il s'évaporerait sous `-O`).

    python3 -m unittest tests.test_confidentialite_publication -v
"""

import os
import re
import subprocess
import sys
import unittest

DOSSIER_TESTS = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(DOSSIER_TESTS)
sys.path.insert(0, DOSSIER_TESTS)
# Le dernier commit de `main` avant C5-T2b : la plage est celle de la branche.
COMMIT_DE_REPERE = "c4e9873e4a86f8648ef272d4e31c082c66f03958"
FICHIER_REGISTRE = "adresse-publication.json"

# Une URL dont un segment fait EXACTEMENT 32 caractères hexadécimaux, suivi d'une
# barre, d'un point ou de la fin du texte. Un SHA de 40 caractères dans un lien
# de commit ne correspond pas : le segment se poursuit.
MOTIF_ADRESSE = re.compile(r"https?://[^\s\"'<>]*/[0-9a-fA-F]{32}(/|\.|$)")


def git(*arguments, **options):
    return subprocess.run(("git",) + arguments, cwd=RACINE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, **options)


def git_disponible():
    try:
        return git("rev-parse", "--is-inside-work-tree").returncode == 0
    except OSError:
        return False


def lignes_porteuses(texte, motif=MOTIF_ADRESSE):
    """Les numéros (à partir de 1) des lignes de `texte` où le motif s'applique.

    Le motif est cherché ligne par ligne : une adresse ne s'étend pas sur deux
    lignes. Jamais la ligne elle-même."""
    return [numero for numero, ligne in enumerate(texte.split("\n"), 1)
            if motif.search(ligne)]


def fichiers_suivis():
    sortie = git("ls-files", "-z")
    if sortie.returncode != 0:
        raise RuntimeError("git ls-files a échoué (code %d)" % sortie.returncode)
    return [os.fsdecode(n) for n in sortie.stdout.split(b"\0") if n]


def trouver_dans_les_fichiers(noms, motif=MOTIF_ADRESSE, racine=RACINE):
    """Liste de (rang du fichier, numéro de ligne) ; jamais le chemin ni le texte."""
    trouves = []
    for rang, nom in enumerate(noms, 1):
        chemin = os.path.join(racine, nom)
        if not os.path.isfile(chemin):
            continue
        with open(chemin, "rb") as f:
            brut = f.read()
        if b"\0" in brut[:8000]:
            continue
        for numero in lignes_porteuses(brut.decode("utf-8", errors="replace"), motif):
            trouves.append((rang, numero))
    return trouves


def messages_de_commit():
    plage = COMMIT_DE_REPERE + "..HEAD"
    sortie = git("log", "-z", "--format=%H%x00%B", plage)
    if sortie.returncode != 0:
        raise RuntimeError("git log %s a échoué (code %d)" % (plage, sortie.returncode))
    morceaux = sortie.stdout.split(b"\0")
    if morceaux and morceaux[-1].strip() == b"":
        morceaux.pop()
    if len(morceaux) % 2 != 0:
        raise RuntimeError("sortie de git log inattendue")
    return [(morceaux[i].decode("ascii").strip(),
             morceaux[i + 1].decode("utf-8", errors="replace"))
            for i in range(0, len(morceaux), 2)]


def blobs_de_la_plage():
    """(sha complet, texte) de tout blob que la plage fait entrer, même retiré depuis."""
    plage = COMMIT_DE_REPERE + "..HEAD"
    liste = git("rev-list", "--objects", plage)
    if liste.returncode != 0:
        raise RuntimeError("git rev-list --objects a échoué (code %d)" % liste.returncode)
    ordre = []
    for ligne in liste.stdout.decode("utf-8", errors="replace").split("\n"):
        if ligne:
            sha = ligne.partition(" ")[0]
            if sha not in ordre:
                ordre.append(sha)
    lecture = git("cat-file", "--batch", input="".join(s + "\n" for s in ordre).encode("ascii"))
    if lecture.returncode != 0:
        raise RuntimeError("git cat-file --batch a échoué (code %d)" % lecture.returncode)
    sortie, blobs, lus, position = lecture.stdout, [], 0, 0
    while position < len(sortie):
        fin = sortie.index(b"\n", position)
        entete = sortie[position:fin].split()
        position = fin + 1
        if len(entete) == 2 and entete[1] == b"missing":
            raise RuntimeError("objet manquant dans la plage")
        if len(entete) != 3:
            raise RuntimeError("entête de git cat-file inattendu")
        taille = int(entete[2])
        contenu = sortie[position:position + taille]
        position += taille + 1
        lus += 1
        if entete[1] == b"blob" and b"\0" not in contenu[:8000]:
            blobs.append((entete[0].decode("ascii"),
                          contenu.decode("utf-8", errors="replace")))
    if lus != len(ordre):
        raise RuntimeError("git cat-file a rendu %d objets pour %d demandés"
                           % (lus, len(ordre)))
    return blobs


def objet_existe(sha):
    return git("cat-file", "-e", sha + "^{commit}").returncode == 0


class LeMotifVoitUneAdresse(unittest.TestCase):
    """Le motif lui-même : il reconnaît une adresse, pas un SHA ni une version."""

    def test_adresses_reconnues(self):
        for texte in ("https://exemple.invalid/" + "0123456789abcdef" * 2 + "/stable.zip",
                      "http://h:8443/a/" + "ABCDEF0123456789" * 2 + "/",
                      "voir https://h/" + "a" * 32,
                      "https://h/" + "a" * 32,
                      "https://h/x/" + "f" * 32 + ".zip"):
            with self.subTest(rang=len(texte)):
                self.assertEqual(lignes_porteuses(texte), [1])

    def test_ce_qui_n_est_pas_une_adresse(self):
        for texte in ("https://127.0.0.1:8443/essai/stable.zip",
                      "https://github.com/x/y/commit/" + "a" * 40,
                      "https://h/" + "a" * 31 + "/stable.zip",
                      "https://h/" + "a" * 33 + "/stable.zip",
                      "sha256 " + "a" * 64,
                      "un segment de " + "a" * 32 + " sans adresse"):
            with self.subTest(rang=len(texte)):
                self.assertEqual(lignes_porteuses(texte), [])

    def test_un_resultat_ne_porte_jamais_le_texte(self):
        faux = "x\nhttps://h/" + "a" * 32 + "/stable.zip\n"
        self.assertEqual(lignes_porteuses(faux), [2])
        for numero in lignes_porteuses(faux):
            self.assertIsInstance(numero, int)


class AdresseHorsDuDepot(unittest.TestCase):
    """Rien de ce que Git versionne ne porte l'adresse d'un client."""

    def setUp(self):
        if not git_disponible():
            self.skipTest("git indisponible ou dépôt absent : garde non jouée")

    def test_aucun_fichier_suivi_ne_porte_une_adresse(self):
        noms = fichiers_suivis()
        self.assertGreater(len(noms), 100)
        trouves = trouver_dans_les_fichiers(noms)
        # Un rang et une ligne, jamais le texte : le journal de CI est public.
        self.assertEqual(trouves, [], "adresse de publication dans un fichier suivi "
                                      "(rang du fichier, ligne) : %r" % (trouves,))

    def test_le_registre_de_l_editeur_n_est_pas_suivi(self):
        fautifs = [n for n in fichiers_suivis() if os.path.basename(n) == FICHIER_REGISTRE]
        self.assertEqual(fautifs, [], "le registre des adresses est suivi par Git")

    def test_le_registre_est_ignore_par_git(self):
        code = git("check-ignore", "-q", FICHIER_REGISTRE).returncode
        self.assertEqual(code, 0, "adresse-publication.json n'est pas ignoré")

    def test_aucun_message_de_commit_de_la_plage_ne_porte_une_adresse(self):
        if not objet_existe(COMMIT_DE_REPERE):
            self.skipTest("commit de repère absent (clone peu profond) : plage non jouée")
        messages = messages_de_commit()
        self.assertGreater(len(messages), 0)
        trouves = [(sha[:7], numero) for sha, texte in messages
                   for numero in lignes_porteuses(texte)]
        self.assertEqual(trouves, [], "adresse dans un message de commit "
                                      "(SHA abrégé, ligne) : %r" % (trouves,))

    def test_aucun_blob_de_la_plage_ne_porte_une_adresse(self):
        if not objet_existe(COMMIT_DE_REPERE):
            self.skipTest("commit de repère absent (clone peu profond) : plage non jouée")
        blobs = blobs_de_la_plage()
        self.assertGreater(len(blobs), 0)
        trouves = [(sha[:7], numero) for sha, texte in blobs
                   for numero in lignes_porteuses(texte)]
        self.assertEqual(trouves, [], "adresse dans un blob introduit par la plage "
                                      "(SHA abrégé, ligne) : %r" % (trouves,))


class GardesEnPlace(unittest.TestCase):
    """Les deux autres barrières nomment le registre : .gitignore et le motif de la CI."""

    def test_gitignore_nomme_le_registre(self):
        with open(os.path.join(RACINE, ".gitignore"), encoding="utf-8") as f:
            lignes = [l.strip() for l in f.read().splitlines()]
        self.assertIn(FICHIER_REGISTRE, lignes)

    def test_le_motif_de_la_ci_refuse_le_registre(self):
        from test_scripts_installation import lire_motif_des_secrets
        motif = lire_motif_des_secrets()
        self.assertIsNotNone(motif.search(FICHIER_REGISTRE))
        self.assertIsNotNone(motif.search("clients/cabinet-01/" + FICHIER_REGISTRE))
        self.assertIsNone(motif.search("clients/cabinet-01/schema.json"))


class LaGardeMord(unittest.TestCase):
    """Une garde jamais mise en échec ne garde rien (piège du dépôt)."""

    def test_un_fichier_suivi_porteur_fait_rougir_sans_nommer_l_adresse(self):
        import tempfile
        import shutil
        dossier = tempfile.mkdtemp(prefix="bilan-confid-")
        self.addCleanup(shutil.rmtree, dossier, True)
        segment = "0123456789abcdef" * 2
        with open(os.path.join(dossier, "propre.md"), "w") as f:
            f.write("rien ici\nhttps://127.0.0.1:8443/essai/stable.zip\n")
        with open(os.path.join(dossier, "fautif.md"), "w") as f:
            f.write("ligne 1\nligne 2\nhttps://exemple.invalid/%s/stable.zip\n" % segment)
        trouves = trouver_dans_les_fichiers(["propre.md", "fautif.md"], racine=dossier)
        self.assertEqual(trouves, [(2, 3)])
        # Ce que le test de production écrirait dans le journal de CI :
        message = "adresse de publication dans un fichier suivi (rang, ligne) : %r" % (trouves,)
        self.assertNotIn(segment, message)
        self.assertNotIn("exemple.invalid", message)

    def test_une_adresse_de_33_hexadecimaux_n_est_pas_vue(self):
        # Le témoin de la mise en échec N18 : un motif porté à 33 ne voit plus une
        # adresse réelle (32). Ce test dit ce que le bon motif voit.
        self.assertEqual(lignes_porteuses("https://h/" + "a" * 32 + "/stable.zip"), [1])
        self.assertEqual(lignes_porteuses("https://h/" + "a" * 33 + "/stable.zip"), [])


if __name__ == "__main__":
    unittest.main()
