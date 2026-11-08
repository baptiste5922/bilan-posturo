"""Outil de l'éditeur (C5-T1) : `outils/signer-paquet.py`, de bout en bout.

Le paquet est le VRAI : fabriqué par `outils/faire-paquet.sh` dans une copie du
dépôt faite par `git ls-files -z` (jamais par copie d'arborescence : la racine du
dépôt porte les données réelles d'un cabinet), avec une liste de confiance et une
clé JETABLES, rangées dans des dossiers temporaires. Aucune vraie clé de
publication n'existe pour ces tests, ni dans le dépôt.

Les tests qui signent ou génèrent une clé exigent `cryptography` (sautés sous le
Python 3.9.6 de macOS, exécutés en CI). Ceux de `verifier` n'en dépendent pas :
ils signent par le signataire de test en Python pur.

    python3 -m unittest tests.test_signer_paquet
"""

import ast
import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import unicodedata
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "serveur"))
sys.path.insert(0, str(RACINE / "tests" / "outils"))
sys.path.insert(0, str(RACINE / "tests"))

import paquet_signe as ps  # noqa: E402
import ed25519_essai as essai  # noqa: E402
from test_scripts_installation import lire_motif_des_secrets  # noqa: E402

SCRIPT = RACINE / "outils" / "signer-paquet.py"
PHRASE = "phrase de passe jetable pour les tests"


def _charger_outil():
    spec = importlib.util.spec_from_file_location("signer_paquet_outil", str(SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OUTIL = _charger_outil()


def cryptography_absente():
    return importlib.util.find_spec("cryptography") is None


OUTILS_DISPONIBLES = all(shutil.which(n) for n in ("sh", "zip", "unzip", "git"))

CRYPTO_ET_OUTILS = unittest.skipIf(
    cryptography_absente() or not OUTILS_DISPONIBLES,
    "cryptography et sh/zip/unzip/git requis pour signer un vrai paquet")


def lancer(script, *arguments, entree=None, cwd=None, sans_cryptography=False):
    """Lance un script Python en sous-processus ; sortie décodée en UTF-8."""
    commande = [sys.executable, "-B"]
    if sans_cryptography:
        # `sys.modules["cryptography"] = None` : tout import lève ImportError, y
        # compris pour une cryptography réellement installée.
        commande += ["-c",
                     "import sys, runpy; sys.modules['cryptography'] = None; "
                     "sys.argv = sys.argv[1:]; "
                     "runpy.run_path(sys.argv[0], run_name='__main__')"]
    commande += [str(script)] + [str(a) for a in arguments]
    environnement = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    return subprocess.run(
        commande, input=entree, cwd=cwd, env=environnement,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
        encoding="utf-8")


def copier_le_depot(destination):
    """Copie du dépôt par `git ls-files -z`, jamais par copie d'arborescence."""
    liste = subprocess.run(["git", "ls-files", "-z"], cwd=str(RACINE),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if liste.returncode != 0:
        raise RuntimeError("git ls-files a échoué : "
                           + liste.stderr.decode("utf-8", "replace"))
    for brut in liste.stdout.split(b"\0"):
        if not brut:
            continue
        relatif = os.fsdecode(brut)
        source = RACINE / relatif
        if not source.is_file():
            continue
        cible = Path(destination) / relatif
        cible.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(str(source), str(cible))


def reconditionner(entree, sortie, remplacer=None, supprimer=(), ajouter=None):
    """Recopie un zip en changeant quelques entrées (noms et attributs conservés)."""
    remplacer, ajouter = remplacer or {}, ajouter or {}
    with zipfile.ZipFile(entree) as source, zipfile.ZipFile(sortie, "w") as cible:
        for info in source.infolist():
            if any(info.filename.endswith(s) for s in supprimer):
                continue
            donnees = source.read(info)
            for fin, nouveau in remplacer.items():
                if info.filename.endswith(fin):
                    donnees = nouveau
            copie = zipfile.ZipInfo(info.filename, info.date_time)
            copie.compress_type = info.compress_type
            copie.external_attr = info.external_attr
            cible.writestr(copie, donnees)
        for nom, donnees in ajouter.items():
            attributs = 0o100644 << 16
            if isinstance(donnees, tuple):
                donnees, attributs = donnees
            info = zipfile.ZipInfo(nom, (2026, 11, 8, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = attributs
            cible.writestr(info, donnees)


class PaquetSigne(unittest.TestCase):
    """Un vrai paquet, signé une fois pour toutes les tests de la classe."""

    @classmethod
    def setUpClass(cls):
        if cryptography_absente() or not OUTILS_DISPONIBLES:
            raise unittest.SkipTest("cryptography et sh/zip/unzip/git requis")
        cls.travail = tempfile.mkdtemp(prefix="bilan-signer-")
        try:
            cls.depot = os.path.join(cls.travail, "depot")
            cls.cles = os.path.join(cls.travail, "cles-jetables")
            os.makedirs(cls.depot)
            os.makedirs(cls.cles)
            copier_le_depot(cls.depot)
            cls.outil = os.path.join(cls.depot, "outils", "signer-paquet.py")

            cls.liste = cls.generer("publication-2026")
            cls.autre = cls.generer("publication-2099")
            with open(os.path.join(cls.depot, "serveur", "cles_publication.json"),
                      "w", encoding="utf-8") as f:
                f.write(cls.liste["json"])

            fabrication = subprocess.run(
                ["sh", "outils/faire-paquet.sh", "cabinet-01"], cwd=cls.depot,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True)
            if fabrication.returncode != 0:
                raise RuntimeError("faire-paquet.sh : " + fabrication.stderr)
            archives = [p for p in os.listdir(cls.depot)
                        if p.startswith("BilanPosturo-") and p.endswith(".zip")]
            if len(archives) != 1:
                raise RuntimeError("une archive attendue : %r" % archives)
            cls.archive = os.path.join(cls.depot, archives[0])
            cls.version = json.loads(
                (RACINE / "formulaire" / "version.json").read_text("utf-8"))["version"]
            cls.signature = cls.signer(cls.archive, cls.liste["cle"])
            if cls.signature.returncode != 0:
                raise RuntimeError("signer : " + cls.signature.stderr)
        except BaseException:
            shutil.rmtree(cls.travail, ignore_errors=True)
            raise

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.travail, ignore_errors=True)

    @classmethod
    def generer(cls, nom):
        resultat = lancer(cls.outil, "generer-cle", "--dossier", cls.cles,
                          "--nom", nom, "--phrase-stdin", entree=PHRASE + "\n")
        if resultat.returncode != 0:
            raise RuntimeError("generer-cle : " + resultat.stderr)
        return {"json": resultat.stdout, "stderr": resultat.stderr,
                "publique": json.loads(resultat.stdout)["cles"][0]["publique"],
                "cle": os.path.join(cls.cles, nom + OUTIL.SUFFIXE_CLE_PRIVEE)}

    @classmethod
    def signer(cls, archive, cle, client="cabinet-01", minimale="1.0.0",
               phrase=PHRASE):
        return lancer(cls.outil, "signer", "--cle", cle, "--client", client,
                      "--version-minimale", minimale, "--phrase-stdin", archive,
                      entree=phrase + "\n")

    # -- A6 : le paquet réel signé est accepté ---------------------------------

    def verifier_cmd(self, archive=None, installee="1.0.0", client="cabinet-01",
                     **options):
        return lancer(SCRIPT, "verifier", "--cles",
                      os.path.join(self.depot, "serveur", "cles_publication.json"),
                      "--version-installee", installee, "--client", client,
                      archive or self.archive, **options)

    def test_a6_le_paquet_reel_signe_est_accepte(self):
        resultat = self.verifier_cmd()
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
        self.assertEqual(resultat.stdout.strip(), "PAQUET ACCEPTÉ " + self.version)

    def test_la_signature_liste_les_entrees_signees(self):
        sortie = self.signature.stdout
        self.assertIn("serveur/paquet_signe.py", sortie)
        self.assertIn("serveur/signature_ed25519.py", sortie)
        self.assertIn("serveur/cles_publication.json", sortie)
        self.assertIn("fichiers signés", sortie)

    def test_le_paquet_emporte_verificateur_et_liste_de_confiance(self):
        with zipfile.ZipFile(self.archive) as z:
            noms = z.namelist()
        for attendu in ("serveur/signature_ed25519.py", "serveur/paquet_signe.py",
                        "serveur/cles_publication.json"):
            self.assertTrue(any(n.endswith(attendu) for n in noms), attendu)

    def test_le_manifeste_ne_signe_que_des_chemins_de_la_liste_blanche(self):
        with open(self.archive + OUTIL.SUFFIXE_MANIFESTE, "rb") as f:
            manifeste = json.loads(f.read().decode("utf-8"))
        self.assertGreater(len(manifeste["fichiers"]), 15)
        for chemin in manifeste["fichiers"]:
            ps.valider_chemin(chemin)
        self.assertEqual(manifeste["client"], "cabinet-01")
        self.assertEqual(manifeste["version"], self.version)
        self.assertEqual(manifeste["version_minimale"], "1.0.0")
        self.assertEqual(manifeste["type"], "manifeste-mise-a-jour")

    def test_le_manifeste_est_ecrit_comme_le_contrat_le_dit(self):
        with open(self.archive + OUTIL.SUFFIXE_MANIFESTE, "rb") as f:
            brut = f.read()
        manifeste = json.loads(brut.decode("utf-8"))
        attendu = (json.dumps(manifeste, ensure_ascii=True, indent=2,
                              sort_keys=True) + "\n").encode("utf-8")
        self.assertEqual(brut, attendu)
        with open(self.archive + OUTIL.SUFFIXE_SIGNATURE, "rb") as f:
            self.assertEqual(len(f.read()), 64)

    # -- A5 : temps ------------------------------------------------------------

    def test_a5_verifier_paquet_sur_le_paquet_reel_en_moins_de_deux_secondes(self):
        chemin_liste = os.path.join(self.depot, "serveur", "cles_publication.json")
        with open(chemin_liste, "rb") as f:
            cles = ps.charger_cles_de_confiance(f.read())
        with open(self.archive + OUTIL.SUFFIXE_MANIFESTE, "rb") as f:
            manifeste = f.read()
        with open(self.archive + OUTIL.SUFFIXE_SIGNATURE, "rb") as f:
            signature = f.read()
        debut = time.perf_counter()
        ps.verifier_paquet(self.archive, manifeste, signature, cles,
                           "1.0.0", "cabinet-01")
        duree = time.perf_counter() - debut
        taille = os.path.getsize(self.archive) / 1e6
        print("\n[C5-T1] verifier_paquet sur le paquet réel (%.1f Mo) : %.3f s "
              "(Python %s)" % (taille, duree, sys.version.split()[0]))
        self.assertLess(duree, 2.0)

    # -- A7 : un octet modifié, soixante-quatre positions et plus --------------

    def test_a7_un_octet_modifie_est_refuse_partout(self):
        positions_prises = 0
        archive_alteree = self.archive + ".essai.zip"
        with open(self.archive, "rb") as f:
            octets_archive = f.read()
        with open(self.archive + OUTIL.SUFFIXE_MANIFESTE, "rb") as f:
            octets_manifeste = f.read()
        with open(self.archive + OUTIL.SUFFIXE_SIGNATURE, "rb") as f:
            octets_signature = f.read()
        # Le trio est copié sous un autre nom : l'original reste intact.
        for suffixe, contenu in ((OUTIL.SUFFIXE_MANIFESTE, octets_manifeste),
                                 (OUTIL.SUFFIXE_SIGNATURE, octets_signature)):
            with open(archive_alteree + suffixe, "wb") as f:
                f.write(contenu)
        with open(archive_alteree, "wb") as f:
            f.write(octets_archive)

        def lancer_en_place():
            sortie = io.StringIO()
            with contextlib.redirect_stdout(sortie):
                code = OUTIL.main([
                    "verifier", "--cles",
                    os.path.join(self.depot, "serveur", "cles_publication.json"),
                    "--version-installee", "1.0.0", "--client", "cabinet-01",
                    archive_alteree])
            return code, sortie.getvalue()

        code, texte = lancer_en_place()
        self.assertEqual(code, 0, texte)

        import random
        hasard = random.Random(32)
        cas = (
            ("manifeste", archive_alteree + OUTIL.SUFFIXE_MANIFESTE, octets_manifeste,
             "SIGNATURE_INVALIDE"),
            ("signature", archive_alteree + OUTIL.SUFFIXE_SIGNATURE, octets_signature,
             "SIGNATURE_INVALIDE"),
            ("archive", archive_alteree, octets_archive, "ARCHIVE_DIFFERENTE"),
        )
        for nom, chemin, original, code_attendu in cas:
            positions = {0, len(original) - 1} | set(
                hasard.randrange(len(original)) for _ in range(30))
            for position in sorted(positions):
                alteree = bytearray(original)
                alteree[position] ^= 1 << hasard.randrange(8)
                with open(chemin, "wb") as f:
                    f.write(alteree)
                try:
                    code, texte = lancer_en_place()
                finally:
                    with open(chemin, "wb") as f:
                        f.write(original)
                positions_prises += 1
                self.assertEqual(code, 1, "%s, octet %d" % (nom, position))
                self.assertIn("PAQUET REFUSÉ " + code_attendu, texte,
                              "%s, octet %d" % (nom, position))
        self.assertGreaterEqual(positions_prises, 64)
        code, texte = lancer_en_place()
        self.assertEqual(code, 0, "le trio de contrôle doit rester valide : " + texte)

    # -- A8, A9 : confiance et versions, par la ligne de commande --------------

    def test_a8_signature_d_une_cle_absente_de_la_liste(self):
        copie = os.path.join(self.travail, "etrangere.zip")
        shutil.copy(self.archive, copie)
        # La clé « autre » n'est pas dans la liste du paquet : l'outil refuse de
        # signer (M20) ; on signe donc avec le signataire de test en Python pur.
        graine_etrangere = bytes(range(40, 72))
        with open(self.archive + OUTIL.SUFFIXE_MANIFESTE, "rb") as f:
            manifeste = f.read()
        with open(copie + OUTIL.SUFFIXE_MANIFESTE, "wb") as f:
            f.write(manifeste)
        with open(copie + OUTIL.SUFFIXE_SIGNATURE, "wb") as f:
            f.write(essai.signer(graine_etrangere, manifeste))
        resultat = self.verifier_cmd(archive=copie)
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("PAQUET REFUSÉ SIGNATURE_INVALIDE", resultat.stdout)
        # Témoin : le même manifeste, signé par la vraie clé, est accepté.
        self.assertEqual(self.verifier_cmd().returncode, 0)

    def test_a9_versions_par_la_ligne_de_commande(self):
        resultat = self.verifier_cmd(installee=self.version)
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("PAQUET REFUSÉ VERSION_NON_SUPERIEURE", resultat.stdout)
        resultat = self.verifier_cmd(installee="inconnue")
        self.assertIn("PAQUET REFUSÉ VERSION_INSTALLEE_ILLISIBLE", resultat.stdout)
        resultat = self.verifier_cmd(client="cabinet-02")
        self.assertIn("PAQUET REFUSÉ CLIENT_DIFFERENT", resultat.stdout)
        resultat = self.verifier_cmd(installee="0.9.0")
        self.assertIn("PAQUET REFUSÉ VERSION_MINIMALE_NON_ATTEINTE", resultat.stdout)

    # -- A16 : verifier n'a pas besoin de cryptography -------------------------

    def test_a16_verifier_reussit_avec_cryptography_inimportable(self):
        resultat = self.verifier_cmd(sans_cryptography=True)
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
        self.assertIn("PAQUET ACCEPTÉ", resultat.stdout)

    def test_le_blocage_de_cryptography_est_reel(self):
        # Témoin de A16 : sous le même blocage, generer-cle, qui en a besoin, échoue.
        resultat = lancer(SCRIPT, "generer-cle", "--dossier", self.cles, "--nom",
                          "publication-2077", "--phrase-stdin",
                          entree=PHRASE + "\n", sans_cryptography=True)
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("cryptography", resultat.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.cles, "publication-2077-privee.pem")))

    # -- A14 : generer-cle -----------------------------------------------------

    def test_a14_generer_cle_refuse_un_dossier_sous_la_racine_du_depot(self):
        sous_depot = os.path.join(self.depot, "docs")
        for dossier in (sous_depot, self.depot, os.path.join(sous_depot, "..", "serveur")):
            with self.subTest(dossier=dossier):
                resultat = lancer(self.outil, "generer-cle", "--dossier", dossier,
                                  "--nom", "publication-2055", "--phrase-stdin",
                                  entree=PHRASE + "\n")
                self.assertEqual(resultat.returncode, 1, resultat.stdout)
                self.assertIn("dépôt", resultat.stderr)
                self.assertFalse(os.path.exists(
                    os.path.join(dossier, "publication-2055-privee.pem")))

    @unittest.skipIf(os.name == "nt", "lien symbolique : droits requis sous Windows")
    def test_a14_un_lien_vers_le_depot_est_resolu_avant_la_comparaison(self):
        lien = os.path.join(self.travail, "lien-vers-le-depot")
        os.symlink(os.path.join(self.depot, "docs"), lien)
        resultat = lancer(self.outil, "generer-cle", "--dossier", lien, "--nom",
                          "publication-2056", "--phrase-stdin", entree=PHRASE + "\n")
        self.assertEqual(resultat.returncode, 1)
        self.assertFalse(os.path.exists(
            os.path.join(self.depot, "docs", "publication-2056-privee.pem")))

    def test_a14_generer_cle_ne_remplace_jamais_une_cle_existante(self):
        chemin = self.liste["cle"]
        with open(chemin, "rb") as f:
            avant = f.read()
        resultat = lancer(self.outil, "generer-cle", "--dossier", self.cles,
                          "--nom", "publication-2026", "--phrase-stdin",
                          entree=PHRASE + "\n")
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("existe déjà", resultat.stderr)
        with open(chemin, "rb") as f:
            self.assertEqual(f.read(), avant)

    def test_a14_phrase_trop_courte_refusee_sans_rien_ecrire(self):
        # Le minimum est de 20 caractères (la fiche le dit : le fichier n'est
        # chiffré que par 2 048 tours de PBKDF2). 19 refusés, 20 acceptés.
        dix_neuf, vingt = "dix-neuf-caracteres", "vingt-caracteres-ok!"
        self.assertEqual((len(dix_neuf), len(vingt)), (19, 20))
        self.assertEqual(OUTIL.LONGUEUR_MIN_PHRASE, 20)
        resultat = lancer(self.outil, "generer-cle", "--dossier", self.cles,
                          "--nom", "publication-2057", "--phrase-stdin",
                          entree=dix_neuf + "\n")
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("trop courte", resultat.stderr)
        self.assertIn("20 caractères", resultat.stderr)
        self.assertFalse(os.path.exists(
            os.path.join(self.cles, "publication-2057-privee.pem")))
        # Un ancien minimum (12) ne suffit plus.
        resultat = lancer(self.outil, "generer-cle", "--dossier", self.cles,
                          "--nom", "publication-2057", "--phrase-stdin",
                          entree="douze.chars!\n")
        self.assertEqual(resultat.returncode, 1)
        self.assertFalse(os.path.exists(
            os.path.join(self.cles, "publication-2057-privee.pem")))
        # Témoin : vingt caractères exactement passent.
        resultat = lancer(self.outil, "generer-cle", "--dossier", self.cles,
                          "--nom", "publication-2058", "--phrase-stdin",
                          entree=vingt + "\n")
        self.assertEqual(resultat.returncode, 0, resultat.stderr)

    def test_a14_nom_hors_motif_est_un_refus_d_usage(self):
        for nom in ("cle", "publication-26", "Publication-2026", "publication-2026_x",
                    "publication-2026/../x", "publication-2026\n"):
            with self.subTest(nom=nom):
                resultat = lancer(self.outil, "generer-cle", "--dossier", self.cles,
                                  "--nom", nom, "--phrase-stdin",
                                  entree=PHRASE + "\n")
                self.assertEqual(resultat.returncode, 2, resultat.stderr)

    @unittest.skipIf(os.name == "nt", "les modes POSIX n'existent pas sous Windows")
    def test_a14_la_cle_est_ecrite_en_0600(self):
        mode = stat.S_IMODE(os.stat(self.liste["cle"]).st_mode)
        self.assertEqual(mode, 0o600)

    def test_a14_la_cle_est_chiffree_et_n_apparait_pas_sur_la_sortie(self):
        from cryptography.hazmat.primitives import serialization
        with open(self.liste["cle"], "rb") as f:
            pem = f.read()
        self.assertIn(b"ENCRYPTED PRIVATE KEY", pem)
        with self.assertRaises(TypeError):
            serialization.load_pem_private_key(pem, password=None)
        with self.assertRaises(ValueError):
            serialization.load_pem_private_key(pem, password=b"mauvaise phrase")
        privee = serialization.load_pem_private_key(pem, password=PHRASE.encode())
        graine = privee.private_bytes(
            serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
            serialization.NoEncryption())
        # Les deux flux de generer-cle : ni la graine, ni le PEM, ni la phrase.
        tout = self.liste["json"] + self.liste["stderr"]
        self.assertNotIn(graine.hex(), tout)
        self.assertNotIn("PRIVATE KEY", tout)
        self.assertNotIn(PHRASE, tout)
        # Sortie standard = exactement l'objet à placer dans cles_publication.json.
        contenu = json.loads(self.liste["json"])
        self.assertEqual(set(contenu), {"format", "cles"})
        self.assertEqual(contenu["cles"][0]["nom"], "publication-2026")
        self.assertEqual(
            ps.charger_cles_de_confiance(self.liste["json"].encode()),
            (bytes.fromhex(self.liste["publique"]),))
        # La clé publique imprimée est bien celle de la clé écrite.
        publique = privee.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.assertEqual(publique.hex(), self.liste["publique"])

    # -- A15 : signer refuse ---------------------------------------------------

    def _aucun_fichier_de_signature(self, archive):
        self.assertFalse(os.path.exists(archive + OUTIL.SUFFIXE_MANIFESTE),
                         "le manifeste ne doit pas rester")
        self.assertFalse(os.path.exists(archive + OUTIL.SUFFIXE_SIGNATURE),
                         "la signature ne doit pas rester")

    def _variante(self, nom, **options):
        destination = os.path.join(self.travail, nom + ".zip")
        reconditionner(self.archive, destination, **options)
        return destination

    def test_a15_cle_sous_la_racine_du_depot(self):
        dedans = os.path.join(self.depot, "docs", "copie-privee.pem")
        shutil.copy(self.liste["cle"], dedans)
        self.addCleanup(os.remove, dedans)
        archive = self._variante("cle-dedans")
        resultat = self.signer(archive, dedans)
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("dépôt", resultat.stderr)
        self._aucun_fichier_de_signature(archive)

    def test_a15_archive_sans_liste_de_cles_de_confiance(self):
        archive = self._variante("sans-liste", supprimer=("serveur/cles_publication.json",))
        resultat = self.signer(archive, self.liste["cle"])
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("aucune clé de confiance dans le paquet : générez la clé de "
                      "publication (docs/cle-publication.md)", resultat.stderr)
        self._aucun_fichier_de_signature(archive)

    def test_a15_cle_absente_de_la_liste_du_paquet(self):
        # M20 : sans ce refus, le cabinet ne pourrait pas vérifier la mise à jour
        # suivante, et rien ne le dirait avant qu'il soit trop tard.
        archive = self._variante("autre-cle")
        resultat = self.signer(archive, self.autre["cle"])
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("ne figure pas", resultat.stderr)
        self._aucun_fichier_de_signature(archive)

    def test_a15_phrase_incorrecte(self):
        archive = self._variante("mauvaise-phrase")
        resultat = self.signer(archive, self.liste["cle"], phrase="mauvaise phrase de passe")
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("phrase de passe incorrecte", resultat.stderr)
        self._aucun_fichier_de_signature(archive)

    def test_a15_schema_different_de_celui_du_client(self):
        archive = self._variante("schema-autre",
                                 remplacer={"formulaire/schema.json": b'{"autre": 1}\n'})
        resultat = self.signer(archive, self.liste["cle"])
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("schema.json", resultat.stderr)
        self._aucun_fichier_de_signature(archive)

    def test_a15_manifeste_deja_present_n_est_jamais_ecrase(self):
        for suffixe in (OUTIL.SUFFIXE_MANIFESTE, OUTIL.SUFFIXE_SIGNATURE):
            with self.subTest(deja=suffixe):
                archive = self._variante("deja" + suffixe.replace(".", "-"))
                with open(archive + suffixe, "wb") as f:
                    f.write(b"preexistant")
                resultat = self.signer(archive, self.liste["cle"])
                self.assertEqual(resultat.returncode, 1)
                # Refus AVANT toute saisie de phrase ni lecture de clé : le message
                # est celui de la première garde, pas celui de l'écriture exclusive.
                self.assertIn("supprimez-le délibérément", resultat.stderr)
                with open(archive + suffixe, "rb") as f:
                    self.assertEqual(f.read(), b"preexistant")
                autre = (OUTIL.SUFFIXE_SIGNATURE if suffixe == OUTIL.SUFFIXE_MANIFESTE
                         else OUTIL.SUFFIXE_MANIFESTE)
                self.assertFalse(os.path.exists(archive + autre))

    def test_a15_version_json_hors_forme_stricte(self):
        archive = self._variante(
            "version-bete",
            remplacer={"formulaire/version.json": b'{"version": "1.2.0-beta"}\n'})
        resultat = self.signer(archive, self.liste["cle"])
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("X.Y.Z", resultat.stderr)
        self._aucun_fichier_de_signature(archive)

    def test_a15_version_minimale_non_inferieure_a_la_version(self):
        archive = self._variante("minimale-egale")
        resultat = self.signer(archive, self.liste["cle"], minimale=self.version)
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("strictement inférieure", resultat.stderr)
        self._aucun_fichier_de_signature(archive)

    def test_a15_chemin_hors_liste_blanche_dans_l_archive(self):
        archive = self._variante("chemin-accentue", ajouter={"racine/é.js": b"x"})
        resultat = self.signer(archive, self.liste["cle"])
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("entrée refusée", resultat.stderr)
        self._aucun_fichier_de_signature(archive)

    def test_a15_deux_dossiers_racine(self):
        archive = self._variante("deux-racines", ajouter={"Autre/x.js": b"x"})
        resultat = self.signer(archive, self.liste["cle"])
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("un seul dossier racine", resultat.stderr)
        self._aucun_fichier_de_signature(archive)

    def test_a15_la_reverification_efface_ce_qu_elle_refuse(self):
        # Un lien symbolique passe les gardes de l'outil (nom de la liste blanche)
        # mais pas la vérification du cabinet : la revérification, par le même
        # code, doit EFFACER le manifeste et la signature qu'elle vient d'écrire.
        # Sans elle, une signature que le cabinet refuserait sortirait d'ici.
        with zipfile.ZipFile(self.archive) as z:
            racine = z.namelist()[0].split("/")[0]
        archive = self._variante(
            "lien", ajouter={racine + "/lien": (b"formulaire/index.html", 0o120777 << 16)})
        resultat = self.signer(archive, self.liste["cle"])
        self.assertEqual(resultat.returncode, 1, resultat.stdout + resultat.stderr)
        self.assertIn("ENTREE_INTERDITE", resultat.stderr)
        self.assertIn("effacés", resultat.stderr)
        self._aucun_fichier_de_signature(archive)

    # -- effacement complet quand une écriture échoue -------------------------

    def _signer_en_processus(self, archive, injection=None):
        """`signer` dans ce processus, une erreur injectée à l'endroit voulu.

        `injection` : "fdopen:N" casse la N-ième écriture après en avoir fait la
        moitié (disque plein simulé) ; "reverification" lève KeyboardInterrupt
        dans la revérification. Rend (code de sortie, exception ou None).
        """
        from unittest import mock
        appels = []
        fdopen_reel = os.fdopen

        class FichierQuiCasse(object):
            def __init__(self, reel):
                self.reel = reel

            def __enter__(self):
                return self

            def __exit__(self, *_):
                self.reel.close()
                return False

            def write(self, octets):
                self.reel.write(octets[:len(octets) // 2])
                self.reel.flush()
                raise OSError("disque plein simulé")

        def fdopen_qui_casse(descripteur, mode):
            appels.append(descripteur)
            reel = fdopen_reel(descripteur, mode)
            if injection == "fdopen:%d" % len(appels):
                return FichierQuiCasse(reel)
            return reel

        def reverification_interrompue(*_args, **_kwargs):
            raise KeyboardInterrupt()

        arguments = ["signer", "--cle", self.liste["cle"], "--client", "cabinet-01",
                     "--version-minimale", "1.0.0", "--phrase-stdin", archive]
        contextes = [mock.patch.object(sys, "stdin", io.StringIO(PHRASE + "\n")),
                     contextlib.redirect_stdout(io.StringIO()),
                     contextlib.redirect_stderr(io.StringIO())]
        if injection and injection.startswith("fdopen"):
            contextes.append(mock.patch.object(OUTIL.os, "fdopen", fdopen_qui_casse))
        if injection == "reverification":
            contextes.append(mock.patch.object(
                OUTIL.paquet_signe, "verifier_paquet", reverification_interrompue))
        with contextlib.ExitStack() as pile:
            for contexte in contextes:
                pile.enter_context(contexte)
            try:
                return OUTIL.main(arguments), None
            except BaseException as erreur:  # noqa: BLE001 - c'est ce qu'on observe
                return None, erreur

    def test_effacement_temoin_sans_injection(self):
        archive = self._variante("temoin-injection")
        code, erreur = self._signer_en_processus(archive)
        self.assertEqual((code, erreur), (0, None))
        self.assertTrue(os.path.exists(archive + OUTIL.SUFFIXE_MANIFESTE))
        self.assertTrue(os.path.exists(archive + OUTIL.SUFFIXE_SIGNATURE))

    def test_ecriture_du_manifeste_interrompue_ne_laisse_rien(self):
        archive = self._variante("casse-manifeste")
        code, erreur = self._signer_en_processus(archive, "fdopen:1")
        self.assertEqual((code, erreur), (1, None))
        self._aucun_fichier_de_signature(archive)

    def test_ecriture_de_la_signature_interrompue_ne_laisse_rien(self):
        # Le manifeste est déjà écrit en entier, la signature est à moitié
        # écrite : ni l'un ni l'autre ne doit rester.
        archive = self._variante("casse-signature")
        code, erreur = self._signer_en_processus(archive, "fdopen:2")
        self.assertEqual((code, erreur), (1, None))
        self._aucun_fichier_de_signature(archive)

    def test_interruption_pendant_la_reverification_ne_laisse_rien(self):
        # Une interruption (Ctrl-C) n'est pas une Exception : c'est la branche
        # `except BaseException` qui efface, puis laisse l'interruption remonter.
        archive = self._variante("interrompue")
        code, erreur = self._signer_en_processus(archive, "reverification")
        self.assertIsNone(code)
        self.assertIsInstance(erreur, KeyboardInterrupt)
        self._aucun_fichier_de_signature(archive)

    def test_ecriture_de_la_cle_interrompue_ne_laisse_pas_de_cle_tronquee(self):
        # La même fonction écrit la clé privée : un fichier tronqué bloquerait la
        # génération suivante (« existe déjà »).
        from unittest import mock

        class Casse(object):
            def __init__(self, reel):
                self.reel = reel

            def __enter__(self):
                return self

            def __exit__(self, *_):
                self.reel.close()
                return False

            def write(self, octets):
                self.reel.write(octets[:5])
                self.reel.flush()
                raise OSError("disque plein simulé")

        reel = os.fdopen
        chemin = os.path.join(self.cles, "essai-tronque-privee.pem")
        with mock.patch.object(OUTIL.os, "fdopen", lambda d, m: Casse(reel(d, m))):
            with self.assertRaises(OUTIL.Echec):
                OUTIL._ecrire_exclusif(chemin, b"contenu de cle a ecrire", 0o600)
        self.assertFalse(os.path.exists(chemin))

    def test_a15_client_inexistant_ou_mal_forme(self):
        archive = self._variante("client")
        resultat = self.signer(archive, self.liste["cle"], client="cabinet-99")
        self.assertEqual(resultat.returncode, 1)
        self._aucun_fichier_de_signature(archive)
        resultat = self.signer(archive, self.liste["cle"], client="../x")
        self.assertEqual(resultat.returncode, 2)
        self._aucun_fichier_de_signature(archive)

    def test_a15_un_zip_qui_n_en_est_pas_un(self):
        faux = os.path.join(self.travail, "faux.zip")
        with open(faux, "wb") as f:
            f.write(b"pas un zip")
        resultat = self.signer(faux, self.liste["cle"])
        self.assertEqual(resultat.returncode, 1)
        self._aucun_fichier_de_signature(faux)

    def test_resigner_exige_de_supprimer_l_ancienne_signature(self):
        resultat = self.signer(self.archive, self.liste["cle"])
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("existe déjà", resultat.stderr)


class VerifierSansCryptography(unittest.TestCase):
    """`verifier` sans `cryptography` : tourne partout, y compris sous le 3.9.6 de macOS."""

    def setUp(self):
        self.dossier = tempfile.mkdtemp(prefix="bilan-verifier-")
        self.addCleanup(shutil.rmtree, self.dossier, ignore_errors=True)
        graine = bytes(range(60, 92))
        racine = "BilanPosturo-2026-11-08/"
        contenus = {racine + "formulaire/version.json": b'{"version": "1.2.0"}\n',
                    racine + "LICENSE": b"licence\n"}
        self.archive = os.path.join(self.dossier, "p.zip")
        with zipfile.ZipFile(self.archive, "w") as z:
            for nom, donnees in sorted(contenus.items()):
                info = zipfile.ZipInfo(nom, (2026, 11, 8, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, donnees)
        import hashlib
        with open(self.archive, "rb") as f:
            brut = f.read()
        manifeste = {
            "archive": {"sha256": hashlib.sha256(brut).hexdigest(), "taille": len(brut)},
            "client": "cabinet-01", "date": "2026-11-08T14:03:00Z",
            "fichiers": {n: {"sha256": hashlib.sha256(d).hexdigest(), "taille": len(d)}
                         for n, d in contenus.items()},
            "format": 1, "produit": "bilan-posturo",
            "type": "manifeste-mise-a-jour", "version": "1.2.0",
            "version_minimale": "1.1.0"}
        octets = (json.dumps(manifeste, ensure_ascii=True, indent=2, sort_keys=True)
                  + "\n").encode()
        with open(self.archive + OUTIL.SUFFIXE_MANIFESTE, "wb") as f:
            f.write(octets)
        with open(self.archive + OUTIL.SUFFIXE_SIGNATURE, "wb") as f:
            f.write(essai.signer(graine, octets))
        self.cles = os.path.join(self.dossier, "cles_publication.json")
        with open(self.cles, "w", encoding="utf-8") as f:
            json.dump({"format": 1, "cles": [
                {"nom": "publication-2026",
                 "publique": essai.cle_publique(graine).hex()}]}, f)

    def verifier(self, installee="1.1.0", client="cabinet-01", **options):
        return lancer(SCRIPT, "verifier", "--cles", self.cles, "--version-installee",
                      installee, "--client", client, self.archive, **options)

    def test_accepte_avec_et_sans_cryptography(self):
        for bloquee in (False, True):
            with self.subTest(sans_cryptography=bloquee):
                resultat = self.verifier(sans_cryptography=bloquee)
                self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
                self.assertEqual(resultat.stdout.strip(), "PAQUET ACCEPTÉ 1.2.0")

    def test_refus_avec_code_et_detail_sans_cryptography(self):
        resultat = self.verifier(installee="1.2.0", sans_cryptography=True)
        self.assertEqual(resultat.returncode, 1)
        self.assertRegex(resultat.stdout, r"^PAQUET REFUSÉ VERSION_NON_SUPERIEURE : .+")

    def test_manifeste_ou_signature_introuvable(self):
        os.remove(self.archive + OUTIL.SUFFIXE_SIGNATURE)
        resultat = self.verifier()
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("PAQUET REFUSÉ SIGNATURE_INVALIDE", resultat.stdout)

    def test_liste_de_cles_invalide(self):
        with open(self.cles, "w", encoding="utf-8") as f:
            f.write("{}")
        resultat = self.verifier()
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("PAQUET REFUSÉ CLES_DE_CONFIANCE_INVALIDES", resultat.stdout)

    def test_liste_de_cles_introuvable(self):
        os.remove(self.cles)
        resultat = self.verifier()
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("ERREUR", resultat.stderr)

    def test_usage_incorrect_sort_en_deux(self):
        for arguments in ([], ["verifier"], ["signer"], ["generer-cle"],
                          ["inconnue"], ["verifier", "--cles", "x"]):
            with self.subTest(arguments=arguments):
                resultat = lancer(SCRIPT, *arguments)
                self.assertEqual(resultat.returncode, 2, resultat.stderr)

    def test_les_messages_d_usage_sont_en_francais(self):
        resultat = lancer(SCRIPT, "verifier")
        self.assertIn("erreur d'usage", resultat.stderr)
        aide = lancer(SCRIPT, "--help")
        self.assertEqual(aide.returncode, 0)
        self.assertNotIn("positional arguments", aide.stdout)
        self.assertNotIn("show this help", aide.stdout)


class EcritureExclusive(unittest.TestCase):
    """`O_EXCL` : la seconde ligne de défense, quand le fichier apparaît entre le test et l'écriture."""

    def setUp(self):
        self.dossier = tempfile.mkdtemp(prefix="bilan-exclusif-")
        self.addCleanup(shutil.rmtree, self.dossier, ignore_errors=True)

    def test_ne_remplace_jamais_un_fichier_existant(self):
        chemin = os.path.join(self.dossier, "x-privee.pem")
        with open(chemin, "wb") as f:
            f.write(b"ancienne cle")
        with self.assertRaises(OUTIL.Echec) as contexte:
            OUTIL._ecrire_exclusif(chemin, b"nouvelle", 0o600)
        self.assertIn("ne sera pas écrasé", str(contexte.exception))
        with open(chemin, "rb") as f:
            self.assertEqual(f.read(), b"ancienne cle")

    def test_cree_un_fichier_neuf_avec_le_mode_demande(self):
        chemin = os.path.join(self.dossier, "neuf.pem")
        OUTIL._ecrire_exclusif(chemin, b"contenu", 0o600)
        with open(chemin, "rb") as f:
            self.assertEqual(f.read(), b"contenu")
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(os.stat(chemin).st_mode) & 0o077, 0)

    def test_un_lien_symbolique_pendant_n_est_pas_suivi(self):
        if os.name == "nt":
            self.skipTest("lien symbolique : droits requis sous Windows")
        cible = os.path.join(self.dossier, "cible-qui-n-existe-pas")
        lien = os.path.join(self.dossier, "lien-privee.pem")
        os.symlink(cible, lien)
        with self.assertRaises(OUTIL.Echec):
            OUTIL._ecrire_exclusif(lien, b"x", 0o600)
        self.assertFalse(os.path.exists(cible))


class EstSousLaRacine(unittest.TestCase):
    """La garde « jamais dans le dépôt », éprouvée dans une racine jetable."""

    def setUp(self):
        self.dossier = tempfile.mkdtemp(prefix="bilan-racine-")
        self.addCleanup(shutil.rmtree, self.dossier, ignore_errors=True)
        # realpath : sous macOS et Windows, le dossier temporaire passe par un
        # chemin court ou un lien (C6-T7).
        self.dossier = os.path.realpath(self.dossier)
        self.racine = os.path.join(self.dossier, unicodedata.normalize("NFC", "dépôt"))
        os.makedirs(os.path.join(self.racine, "sous"))
        os.makedirs(os.path.join(self.dossier, "dehors"))
        self.ancienne = OUTIL.RACINE_DEPOT
        OUTIL.RACINE_DEPOT = self.racine
        self.addCleanup(setattr, OUTIL, "RACINE_DEPOT", self.ancienne)

    def test_dedans_et_dehors(self):
        self.assertTrue(OUTIL.est_sous_la_racine_du_depot(self.racine))
        self.assertTrue(OUTIL.est_sous_la_racine_du_depot(os.path.join(self.racine, "sous")))
        self.assertTrue(OUTIL.est_sous_la_racine_du_depot(
            os.path.join(self.racine, "sous", "n-existe-pas-encore")))
        self.assertTrue(OUTIL.est_sous_la_racine_du_depot(
            os.path.join(self.racine, "sous", "..", "sous")))
        self.assertFalse(OUTIL.est_sous_la_racine_du_depot(os.path.join(self.dossier, "dehors")))
        self.assertFalse(OUTIL.est_sous_la_racine_du_depot(self.dossier))
        # Un frère dont le nom commence pareil n'est pas dessous.
        os.makedirs(self.racine + "-frere")
        self.assertFalse(OUTIL.est_sous_la_racine_du_depot(self.racine + "-frere"))

    def test_les_deux_ecritures_unicode_d_un_meme_nom(self):
        # macOS écrit « dépôt » en NFD, Linux et Windows en NFC : la comparaison se
        # fait en NFC, dans le sens sûr (refuser).
        nfd = unicodedata.normalize("NFD", "dépôt")
        self.assertNotEqual(nfd, "dépôt")
        self.assertTrue(OUTIL.est_sous_la_racine_du_depot(
            os.path.join(self.dossier, nfd, "cles")))

    @unittest.skipIf(os.name == "nt", "lien symbolique : droits requis sous Windows")
    def test_un_lien_est_resolu(self):
        lien = os.path.join(self.dossier, "dehors", "lien")
        os.symlink(os.path.join(self.racine, "sous"), lien)
        self.assertTrue(OUTIL.est_sous_la_racine_du_depot(lien))

    def test_la_casse_seule_sur_un_disque_insensible(self):
        majuscule = os.path.join(self.dossier, unicodedata.normalize("NFC", "DÉPÔT"))
        if not os.path.exists(majuscule):
            self.skipTest("système de fichiers sensible à la casse")
        self.assertTrue(OUTIL.est_sous_la_racine_du_depot(os.path.join(majuscule, "x")))


class GardesDeStructure(unittest.TestCase):

    CHEMINS = ("serveur/signature_ed25519.py", "serveur/paquet_signe.py",
               "outils/signer-paquet.py")

    def _arbre(self, relatif):
        return ast.parse((RACINE / relatif).read_text(encoding="utf-8"))

    def test_a21_aucun_assert_nu_dans_le_code_livre(self):
        # Sous `python -O`, un `assert` disparaît : il ne garde rien. Dérivé de
        # l'arbre syntaxique, donc ni commentaire ni chaîne ne le trompe.
        for relatif in self.CHEMINS:
            with self.subTest(fichier=relatif):
                arbre = self._arbre(relatif)
                self.assertEqual(
                    [n.lineno for n in ast.walk(arbre) if isinstance(n, ast.Assert)], [])

    def test_cryptography_n_est_importee_que_dans_une_fonction_de_l_outil(self):
        arbre = self._arbre("outils/signer-paquet.py")

        def importe_cryptography(noeud):
            if isinstance(noeud, ast.ImportFrom):
                return (noeud.module or "").split(".")[0] == "cryptography"
            if isinstance(noeud, ast.Import):
                return any(a.name.split(".")[0] == "cryptography" for a in noeud.names)
            return False

        # Rien au niveau du module (y compris dans un try ou un if de tête).
        niveau_module = [n for corps in arbre.body
                         if not isinstance(corps, (ast.FunctionDef, ast.ClassDef))
                         for n in ast.walk(corps) if importe_cryptography(n)]
        self.assertEqual(niveau_module, [])
        # Une seule fonction l'importe, et seules generer_cle et signer l'appellent.
        importeuses = [f.name for f in ast.walk(arbre) if isinstance(f, ast.FunctionDef)
                       and any(importe_cryptography(n) for n in ast.walk(f))]
        self.assertEqual(importeuses, ["_importer_cryptography"])
        appelantes = sorted(
            f.name for f in ast.walk(arbre) if isinstance(f, ast.FunctionDef)
            and any(isinstance(n, ast.Call) and getattr(n.func, "id", None)
                    == "_importer_cryptography" for n in ast.walk(f)))
        self.assertEqual(appelantes, ["generer_cle", "signer"])

    def test_le_code_livre_ne_signe_jamais(self):
        # Le serveur ne sait que vérifier : aucune fonction de signature dans les
        # deux modules de serveur/ (une arithmétique en Python sur des entiers de
        # taille variable fuirait la clé par le temps de calcul).
        for relatif in ("serveur/signature_ed25519.py", "serveur/paquet_signe.py"):
            noms = [n.name for n in ast.walk(self._arbre(relatif))
                    if isinstance(n, ast.FunctionDef)]
            with self.subTest(fichier=relatif):
                self.assertGreater(len(noms), 3)
                self.assertEqual([n for n in noms if "sign" in n.lower()
                                  and "signature" not in n.lower()], [])

    def test_a17_le_suffixe_de_cle_privee_est_refuse_par_le_motif_de_la_ci(self):
        motif = lire_motif_des_secrets()
        for nom in ("publication-2026", "publication-2099-b"):
            produit = "cles/" + nom + OUTIL.SUFFIXE_CLE_PRIVEE
            with self.subTest(nom=produit):
                self.assertIsNotNone(motif.search(produit))
        # Témoins : un fichier ordinaire, et la liste de clés publiques, passent.
        self.assertIsNone(motif.search(OUTIL.NOM_CLES_DE_CONFIANCE))
        self.assertIsNone(motif.search("x" + OUTIL.SUFFIXE_MANIFESTE))
        self.assertIsNone(motif.search("x" + OUTIL.SUFFIXE_SIGNATURE))

    def test_a17_aucune_cle_n_est_versionnee(self):
        try:
            sortie = subprocess.run(["git", "ls-files", "-z"], cwd=str(RACINE),
                                    stdout=subprocess.PIPE, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git indisponible")
        suivis = [os.fsdecode(b) for b in sortie.split(b"\0") if b]
        self.assertGreater(len(suivis), 100, "la liste des fichiers suivis doit exister")
        fautifs = [s for s in suivis if s.endswith(OUTIL.SUFFIXE_CLE_PRIVEE)
                   or s.endswith("cles_publication.json")
                   or s == OUTIL.NOM_CLES_DE_CONFIANCE]
        self.assertEqual(fautifs, [])

    def test_le_motif_des_secrets_n_a_pas_ete_touche(self):
        # La tâche ne modifie pas le motif : il couvre déjà le nom produit.
        texte = (RACINE / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
        self.assertIn(r"_privee\.|-privee\.", texte)
        self.assertIn(r"\.pem$", texte)

    def test_pyflakes_couvre_l_outil_dans_la_ci(self):
        texte = (RACINE / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
        ligne = [l for l in texte.splitlines() if "pyflakes serveur/" in l]
        self.assertEqual(len(ligne), 1)
        self.assertIn("outils/signer-paquet.py", ligne[0])


class FicheDeLaClePublication(unittest.TestCase):
    """A24 : la fiche existe, ses huit sections aussi, et ses commandes sont réelles."""

    @classmethod
    def setUpClass(cls):
        cls.fiche = (RACINE / "docs" / "cle-publication.md").read_text(encoding="utf-8")

    def test_les_huit_sections(self):
        titres = re.findall(r"^## (\d+)\. (.+)$", self.fiche, re.MULTILINE)
        self.assertEqual([n for n, _ in titres], [str(i) for i in range(1, 9)])

    def test_chaque_commande_et_option_citee_existe_dans_l_aide(self):
        aide_generale = lancer(SCRIPT, "--help").stdout
        aides = {}
        commandes = re.findall(r"signer-paquet\.py ((?:generer-cle|signer|verifier)[^\n`]*)",
                               self.fiche)
        self.assertGreaterEqual(len(commandes), 3)
        vues = set()
        for ligne in commandes:
            sous = ligne.split()[0]
            vues.add(sous)
            self.assertIn(sous, aide_generale)
            if sous not in aides:
                aides[sous] = lancer(SCRIPT, sous, "--help").stdout
            for option in re.findall(r"--[a-z][a-z-]*", ligne):
                with self.subTest(commande=sous, option=option):
                    self.assertIn(option, aides[sous])
                    self.assertIn(option, aide_generale)
        self.assertEqual(vues, {"generer-cle", "signer", "verifier"})

    def test_la_fiche_ne_nomme_aucun_secret_reel(self):
        # Aucune clé, aucune phrase : seulement des modèles.
        self.assertNotRegex(self.fiche, r"[0-9a-f]{64}")
        self.assertNotIn("PRIVATE KEY", self.fiche)


if __name__ == "__main__":
    unittest.main()
