"""Paquet signé (C5-T1) : `serveur/paquet_signe.py`.

Principe directeur du contrat (D8) : l'empreinte de l'archive détecte toute
altération du zip. Si l'on se contente de modifier le zip, les gardes qui lisent
le zip (étapes 6 à 9) ne sont JAMAIS atteintes, et le test passe sans avoir rien
éprouvé. Ces tests fabriquent donc, avec le signataire de test, un manifeste
VALIDE ET SIGNÉ dont un seul point est faux, empreinte d'archive recalculée : le
refus attendu ne peut venir que de la garde visée.

Aucun test ici n'a besoin de `cryptography` : le signataire est en Python pur
(tests/outils/ed25519_essai.py).

    python3 -m unittest tests.test_paquet_signe
"""

import hashlib
import inspect
import json
import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile
from collections import namedtuple

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "serveur"))
sys.path.insert(0, os.path.join(RACINE, "tests", "outils"))

import paquet_signe as ps  # noqa: E402
import ed25519_essai as essai  # noqa: E402

PaquetRefuse = ps.PaquetRefuse
GRAINE_A = bytes(range(32))
GRAINE_B = bytes(range(100, 132))
CLE_A = essai.cle_publique(GRAINE_A)
CLE_B = essai.cle_publique(GRAINE_B)
DOSSIER_RACINE = "BilanPosturo-2026-11-08"
DATE_FIXE = (2026, 11, 8, 14, 3, 0)

Trio = namedtuple("Trio", "archive manifeste signature cles")


# --------------------------------------------------------------------------
# Fabrication d'un trio (archive, manifeste, signature)
# --------------------------------------------------------------------------

def contenus_normaux(version="1.2.0"):
    r = DOSSIER_RACINE + "/"
    return {
        r + "LICENSE": b"texte de licence\n",
        r + "formulaire/index.html": b"<html><body>formulaire</body></html>\n" * 40,
        r + "formulaire/schema.json": b'{"version": 2}\n',
        r + "formulaire/version.json": ('{"version": "%s"}\n' % version).encode(),
        r + "serveur/serveur.py": b"print('serveur')\n" * 60,
    }


def _entree_fichier(nom, octets, compression=zipfile.ZIP_DEFLATED):
    info = zipfile.ZipInfo(nom, DATE_FIXE)
    info.compress_type = compression
    info.external_attr = 0o100644 << 16
    return info, octets


def _entree_dossier(nom):
    info = zipfile.ZipInfo(nom, DATE_FIXE)
    info.external_attr = (0o40755 << 16) | 0x10
    return info, b""


def entrees_depuis(contenus):
    """Entrées de zip dans l'esprit de `zip -r` : dossiers puis fichiers."""
    dossiers = set()
    for nom in contenus:
        morceaux = nom.split("/")
        for i in range(1, len(morceaux)):
            dossiers.add("/".join(morceaux[:i]) + "/")
    entrees = [_entree_dossier(d) for d in sorted(dossiers)]
    entrees += [_entree_fichier(n, o) for n, o in sorted(contenus.items())]
    return entrees


def ecrire_zip(chemin, entrees):
    """Écrit un zip. Un doublon de nom fait avertir `zipfile` : on le veut parfois."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with zipfile.ZipFile(chemin, "w") as archive:
            for info, octets in entrees:
                archive.writestr(info, octets)


def sha(octets):
    return hashlib.sha256(octets).hexdigest()


def serialiser(manifeste):
    return (json.dumps(manifeste, ensure_ascii=True, indent=2, sort_keys=True)
            + "\n").encode("utf-8")


def manifeste_de(declares, octets_archive, version="1.2.0", minimale="1.1.0",
                 client="cabinet-01"):
    return {
        "archive": {"sha256": sha(octets_archive), "taille": len(octets_archive)},
        "client": client,
        "date": "2026-11-08T14:03:00Z",
        "fichiers": {nom: {"sha256": sha(o), "taille": len(o)}
                     for nom, o in declares.items()},
        "format": 1,
        "produit": "bilan-posturo",
        "type": "manifeste-mise-a-jour",
        "version": version,
        "version_minimale": minimale,
    }


class Atelier(unittest.TestCase):
    """Base : un dossier jetable par test et la fabrication de trios."""

    def setUp(self):
        self.dossier = tempfile.mkdtemp(prefix="bilan-paquet-signe-")
        self.addCleanup(shutil.rmtree, self.dossier, ignore_errors=True)
        self.numero = 0

    def fabriquer(self, declares=None, entrees=None, retoucher=None,
                  retoucher_zip=None, version="1.2.0", minimale="1.1.0",
                  client="cabinet-01", graine=GRAINE_A, cles=None, compact=False):
        """Trio signé. `declares` : ce que dit le manifeste ; `entrees` : ce que
        contient le zip (par défaut, la même chose) ; `retoucher` : modifie le
        dict du manifeste avant la signature ; `retoucher_zip` : modifie les
        octets du zip AVANT que le manifeste n'en prenne l'empreinte."""
        self.numero += 1
        if declares is None:
            declares = contenus_normaux(version)
        if entrees is None:
            entrees = entrees_depuis(declares)
        archive = os.path.join(self.dossier, "paquet%d.zip" % self.numero)
        ecrire_zip(archive, entrees)
        if retoucher_zip is not None:
            with open(archive, "rb") as f:
                octets = retoucher_zip(f.read())
            with open(archive, "wb") as f:
                f.write(octets)
        with open(archive, "rb") as f:
            octets_archive = f.read()
        manifeste = manifeste_de(declares, octets_archive, version, minimale, client)
        if retoucher is not None:
            retoucher(manifeste)
        # `compact` : sans espaces ni retraits, pour tenir 10 000 entrées sous le
        # plafond de 1 Mio du manifeste (la mise en forme de l'outil, elle, n'y
        # tiendrait pas).
        octets = (json.dumps(manifeste, sort_keys=True, separators=(",", ":")).encode()
                  if compact else serialiser(manifeste))
        return Trio(archive, octets, essai.signer(graine, octets),
                    (CLE_A,) if cles is None else cles)

    def signer_octets(self, octets, graine=GRAINE_A):
        return octets, essai.signer(graine, octets)

    def verifier(self, trio, installee="1.1.0", client="cabinet-01"):
        return ps.verifier_paquet(trio.archive, trio.manifeste, trio.signature,
                                  trio.cles, installee, client)

    def refus(self, code, trio, installee="1.1.0", client="cabinet-01"):
        with self.assertRaises(PaquetRefuse) as contexte:
            self.verifier(trio, installee, client)
        self.assertEqual(contexte.exception.code, code, contexte.exception.detail)
        return contexte.exception


# --------------------------------------------------------------------------
# Versions et chemins
# --------------------------------------------------------------------------

class AnalyseDesVersions(unittest.TestCase):

    def test_formes_valides(self):
        for texte, attendu in (("0.0.0", (0, 0, 0)), ("1.1.0", (1, 1, 0)),
                               ("1.10.0", (1, 10, 0)), ("12.0.7", (12, 0, 7)),
                               ("999999.999999.999999", (999999, 999999, 999999))):
            with self.subTest(texte=texte):
                self.assertEqual(ps.analyser_version(texte), attendu)

    def test_formes_invalides(self):
        for texte in ("", "1", "1.2", "1.2.3.4", "01.2.3", "1.02.3", "1.2.03",
                      "1.2.0-beta", "1.2.0+x", "v1.2.0", " 1.2.0", "1.2.0 ",
                      "1.2.0\n", "\n1.2.0", "1.2.-3", "1..3", "inconnue",
                      "1.2.1000000", "١.٢.٣", "1.2.٣", None, 120, 1.2, b"1.2.0"):
            with self.subTest(texte=texte):
                with self.assertRaises(PaquetRefuse) as c:
                    ps.analyser_version(texte)
                self.assertEqual(c.exception.code, "VERSION_MALFORMEE")

    def test_l_ordre_est_numerique_pas_alphabetique(self):
        self.assertGreater(ps.analyser_version("1.10.0"), ps.analyser_version("1.9.0"))
        self.assertGreater(ps.analyser_version("1.2.10"), ps.analyser_version("1.2.9"))
        self.assertGreater(ps.analyser_version("10.0.0"), ps.analyser_version("9.9.9"))
        # Le piège que la comparaison de chaînes ne voit pas.
        self.assertLess("1.10.0", "1.9.0")


class ValidationDesChemins(unittest.TestCase):

    DANGEREUX = [
        "/etc/x", "../x", "a/../../x", "a\\..\\x", "a\\b", "C:x", "C:/x", "a:flux",
        "a//b", "./a", "a/", ".cache/x", "a.", "CON", "nul.txt", "Com1.js", "é.js",
        "a b", "a\x00b", "x" * 241,
        # Au-delà du tableau du contrat : saut de ligne final (le `$` d'une
        # expression régulière l'accepterait), vide, nom caché, noms réservés.
        "", "a\n", "a/b\n", "..", ".", "a/./b", "a/.hidden", "aux", "PRN.tar.gz",
        "com0", "LPT9.txt", "a/b.", "a/CON/b", "dossier/NUL", " a", "a ", "a\tb",
        "a/ b", "ａ", "a\u202eb", "~", "a*b", "a?b", "a|b", "a<b", "a\"b", "a$b",
    ]

    def test_chemins_dangereux_refuses(self):
        for nom in self.DANGEREUX:
            with self.subTest(nom=nom):
                with self.assertRaises(PaquetRefuse) as c:
                    ps.valider_chemin(nom)
                self.assertEqual(c.exception.code, "CHEMIN_DANGEREUX")

    def test_types_faux_refuses(self):
        for nom in (None, 12, b"a", ["a"]):
            with self.subTest(nom=nom):
                with self.assertRaises(PaquetRefuse) as c:
                    ps.valider_chemin(nom)
                self.assertEqual(c.exception.code, "CHEMIN_DANGEREUX")

    def test_chemins_admis(self):
        for nom in ("a", "A.js", "LICENSE", "a/b.js", "x" * 240, "a-b_c.1/d",
                    "BilanPosturo-2026-11-08/formulaire/moteur/rendu.js",
                    "console/x", "comp/x", "auxiliaire.js", "lpt10", "com10.js",
                    "_x", "-x"):
            with self.subTest(nom=nom):
                self.assertIsNone(ps.valider_chemin(nom))

    def test_chaque_chemin_du_paquet_reel_est_admis(self):
        # Le paquet part de formulaire/, serveur/ et de quelques fichiers de
        # tête : la liste blanche ASCII ne doit refuser aucun fichier existant.
        try:
            sortie = subprocess.run(
                ["git", "ls-files", "-z", "--", "formulaire", "serveur"],
                cwd=RACINE, capture_output=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git indisponible")
        noms = [os.fsdecode(b) for b in sortie.split(b"\0") if b]
        self.assertGreater(len(noms), 10)
        for nom in noms + ["LICENSE", "TIERS.md", "demarrer-serveur.bat",
                           "installer-demarrage.ps1", "docs/Mode_emploi.md"]:
            with self.subTest(nom=nom):
                ps.valider_chemin(DOSSIER_RACINE + "/" + nom)


# --------------------------------------------------------------------------
# Clés de confiance
# --------------------------------------------------------------------------

def liste_de_cles(*publiques, **autres):
    contenu = {"format": 1, "cles": [
        {"nom": "publication-%d" % (2026 + i), "publique": p.hex()}
        for i, p in enumerate(publiques)]}
    contenu.update(autres)
    return json.dumps(contenu).encode("utf-8")


class ClesDeConfiance(unittest.TestCase):

    def refuse(self, octets):
        with self.assertRaises(PaquetRefuse) as c:
            ps.charger_cles_de_confiance(octets)
        self.assertEqual(c.exception.code, "CLES_DE_CONFIANCE_INVALIDES",
                         c.exception.detail)

    def test_liste_valide(self):
        self.assertEqual(ps.charger_cles_de_confiance(liste_de_cles(CLE_A)), (CLE_A,))
        self.assertEqual(ps.charger_cles_de_confiance(liste_de_cles(CLE_A, CLE_B)),
                         (CLE_A, CLE_B))

    def test_quatre_cles_admises_cinq_refusees(self):
        cles = [essai.cle_publique(bytes([i]) * 32) for i in range(5)]
        self.assertEqual(len(ps.charger_cles_de_confiance(liste_de_cles(*cles[:4]))), 4)
        self.refuse(liste_de_cles(*cles))

    def test_refus_de_forme(self):
        valide = {"format": 1, "cles": [{"nom": "publication-2026", "publique": CLE_A.hex()}]}
        def avec(modif):
            copie = json.loads(json.dumps(valide))
            modif(copie)
            return json.dumps(copie).encode()
        self.refuse(b"")
        self.refuse(b"pas du json")
        self.refuse(b"[]")
        self.refuse(b"\xef\xbb\xbf" + json.dumps(valide).encode())
        self.refuse(liste_de_cles())                                   # liste vide
        self.refuse(avec(lambda c: c.update(autre=1)))                 # clé inconnue
        self.refuse(avec(lambda c: c.pop("format")))
        self.refuse(avec(lambda c: c.update(format=2)))
        self.refuse(avec(lambda c: c.update(format=True)))
        self.refuse(avec(lambda c: c["cles"][0].update(extra="x")))
        self.refuse(avec(lambda c: c["cles"][0].pop("nom")))
        self.refuse(avec(lambda c: c["cles"][0].update(nom="Majuscule")))
        self.refuse(avec(lambda c: c["cles"][0].update(nom="")))
        self.refuse(avec(lambda c: c.update(cles="texte")))
        self.refuse(avec(lambda c: c.update(cles=[1])))
        self.refuse(b'{"format": 1, "format": 1, "cles": []}')          # clé en double
        self.refuse(b'{"format": NaN, "cles": []}')
        self.refuse("é".encode("latin-1"))

    def test_refus_de_cle(self):
        def avec(publique):
            return json.dumps({"format": 1, "cles": [
                {"nom": "publication-2026", "publique": publique}]}).encode()
        self.refuse(avec(CLE_A.hex().upper()))             # hexadécimal en majuscules
        self.refuse(avec(CLE_A.hex()[:-2]))                # trop courte
        self.refuse(avec(CLE_A.hex() + "00"))              # trop longue
        self.refuse(avec("zz" * 32))                       # hex invalide
        self.refuse(avec(CLE_A.hex() + "\n"))              # saut de ligne final
        self.refuse(avec(12))
        self.refuse(liste_de_cles(CLE_A, CLE_A))           # en double
        self.refuse(avec(("00" * 32)))                     # point d'ordre faible (y = 0)
        self.refuse(avec("01" + "00" * 31))                # le neutre
        # Un y qui n'est pas l'ordonnée d'un point de la courbe.
        y = 2
        from signature_ed25519 import _decoder_point
        while _decoder_point(y.to_bytes(32, "little")) is not None:
            y += 1
        self.refuse(avec(y.to_bytes(32, "little").hex()))

    def test_octets_obligatoires(self):
        for faux in (None, "texte", bytearray(b"{}")):
            self.refuse(faux)
        self.refuse(b" " * (ps.TAILLE_MAX_CLES + 1))


# --------------------------------------------------------------------------
# Manifeste
# --------------------------------------------------------------------------

class LectureDuManifeste(Atelier):

    def lire(self, octets, signature=Ellipsis, cles=(CLE_A,), graine=GRAINE_A):
        if signature is Ellipsis:
            signature = essai.signer(graine, octets)
        return ps.lire_manifeste(octets, signature, cles)

    def refuse(self, code, octets, **kwargs):
        with self.assertRaises(PaquetRefuse) as c:
            self.lire(octets, **kwargs)
        self.assertEqual(c.exception.code, code, c.exception.detail)

    def manifeste_valide(self):
        declares = contenus_normaux()
        return manifeste_de(declares, b"archive")

    def test_manifeste_valide_lu_tel_quel(self):
        manifeste = self.manifeste_valide()
        lu = self.lire(serialiser(manifeste))
        self.assertEqual(lu, manifeste)

    def test_l_ordre_la_signature_avant_toute_analyse(self):
        # M7 : un manifeste malformé ET non signé ne doit révéler aucun détail
        # de lecture ; seul SIGNATURE_INVALIDE sort.
        for octets in (b"", b"pas du json", b"[1, 2", b"\xff\xfe", b"{}",
                       b"\xef\xbb\xbf{}", b'{"a": 1, "a": 2}', b"NaN",
                       json.dumps({"type": "inconnu"}).encode(),
                       json.dumps({"format": 2}).encode()):
            with self.subTest(octets=octets[:20]):
                self.refuse("SIGNATURE_INVALIDE", octets,
                            signature=essai.signer(GRAINE_B, octets))
                self.refuse("SIGNATURE_INVALIDE", octets, signature=b"\0" * 64)

    def test_trop_grand_avant_tout_calcul(self):
        octets = b" " * (ps.TAILLE_MAX_MANIFESTE + 1)
        self.refuse("MANIFESTE_TROP_GRAND", octets, signature=b"\0" * 64)
        # Signé : la taille reste un refus, même pour un éditeur honnête.
        self.refuse("MANIFESTE_TROP_GRAND", octets)

    def test_pile_a_la_limite_la_taille_passe_le_cap(self):
        octets = serialiser(self.manifeste_valide())
        octets += b" " * (ps.TAILLE_MAX_MANIFESTE - len(octets))
        self.assertEqual(len(octets), ps.TAILLE_MAX_MANIFESTE)
        self.lire(octets)

    def test_signature_d_une_autre_cle_refusee(self):
        octets = serialiser(self.manifeste_valide())
        self.refuse("SIGNATURE_INVALIDE", octets, graine=GRAINE_B)

    def test_aucune_cle_fournie_refuse(self):
        # M8 : accepter quand la liste est vide serait la pire des portes.
        octets = serialiser(self.manifeste_valide())
        for cles in ((), [], None, (b"",), (None,), (b"x" * 32,), iter(())):
            with self.subTest(cles=repr(cles)):
                self.refuse("SIGNATURE_INVALIDE", octets, cles=cles)

    def test_une_des_cles_suffit(self):
        octets = serialiser(self.manifeste_valide())
        self.lire(octets, cles=(CLE_B, CLE_A), graine=GRAINE_A)
        self.lire(octets, cles=(CLE_A, CLE_B), graine=GRAINE_B)

    def test_signature_de_mauvaise_longueur(self):
        octets = serialiser(self.manifeste_valide())
        bonne = essai.signer(GRAINE_A, octets)
        for signature in (bonne[:63], bonne + b"\0", b"", None, bytearray(bonne)):
            with self.subTest(longueur=None if signature is None else len(signature)):
                self.refuse("SIGNATURE_INVALIDE", octets, signature=signature)

    def test_manifeste_pas_en_octets(self):
        with self.assertRaises(PaquetRefuse) as c:
            ps.lire_manifeste("texte", b"\0" * 64, (CLE_A,))
        self.assertEqual(c.exception.code, "MANIFESTE_MALFORME")

    def test_refus_signes_de_forme(self):
        valide = self.manifeste_valide()

        def modifie(fonction):
            copie = json.loads(json.dumps(valide))
            fonction(copie)
            return serialiser(copie)

        cas = {
            "clé inconnue": modifie(lambda m: m.update(extra=1)),
            "clé manquante": modifie(lambda m: m.pop("date")),
            "taille booléenne": modifie(lambda m: m["archive"].update(taille=True)),
            "taille de fichier booléenne": modifie(
                lambda m: next(iter(m["fichiers"].values())).update(taille=False)),
            "taille flottante": modifie(lambda m: m["archive"].update(taille=1.0)),
            "taille négative": modifie(lambda m: m["archive"].update(taille=-1)),
            "empreinte en majuscules": modifie(
                lambda m: m["archive"].update(sha256="A" * 64)),
            "empreinte courte": modifie(lambda m: m["archive"].update(sha256="a" * 63)),
            "empreinte à saut de ligne": modifie(
                lambda m: m["archive"].update(sha256="a" * 64 + "\n")),
            "archive avec clé de plus": modifie(lambda m: m["archive"].update(x=1)),
            "fichier avec clé de moins": modifie(
                lambda m: next(iter(m["fichiers"].values())).pop("sha256")),
            "fichiers en liste": modifie(lambda m: m.update(fichiers=[])),
            "produit inconnu": modifie(lambda m: m.update(produit="autre")),
            "client invalide": modifie(lambda m: m.update(client="cabinet-1")),
            "client à saut de ligne": modifie(lambda m: m.update(client="cabinet-01\n")),
            "date invalide": modifie(lambda m: m.update(date="2026-11-08")),
            "date à saut de ligne": modifie(lambda m: m.update(date="2026-11-08T14:03:00Z\n")),
            "version non texte": modifie(lambda m: m.update(version=120)),
            "racine non objet": b"[]",
            "racine nulle": b"null",
            "clé en double": b'{"format": 1, "format": 1}',
            "NaN": serialiser(valide).replace(b'"taille": ', b'"taille": NaN, "x": ', 1),
            "Infinity": serialiser(valide).replace(b'"taille": ', b'"taille": -Infinity, "x": ', 1),
            "BOM": b"\xef\xbb\xbf" + serialiser(valide),
            "UTF-8 invalide": serialiser(valide).replace(b"cabinet", b"cab\xffnet", 1),
            "JSON tronqué": serialiser(valide)[:-10],
            "imbrication profonde": b"[" * 100000 + b"]" * 100000,
        }
        for nom, octets in cas.items():
            with self.subTest(cas=nom):
                self.refuse("MANIFESTE_MALFORME", octets)

    def test_type_et_format_inconnus(self):
        valide = self.manifeste_valide()
        for nom, valeur, code in (
                ("type", "licence", "TYPE_INCONNU"), ("type", "", "TYPE_INCONNU"),
                ("type", None, "TYPE_INCONNU"), ("type", 1, "TYPE_INCONNU"),
                ("format", 2, "FORMAT_INCONNU"), ("format", 0, "FORMAT_INCONNU"),
                ("format", True, "FORMAT_INCONNU"), ("format", "1", "FORMAT_INCONNU"),
                ("format", 1.0, "FORMAT_INCONNU")):
            with self.subTest(champ=nom, valeur=valeur):
                copie = dict(valide)
                copie[nom] = valeur
                self.refuse(code, serialiser(copie))

    def test_format_futur_reconnu_comme_inconnu_meme_avec_d_autres_cles(self):
        # Un manifeste version 2 a d'autres clés : il doit être nommé « format
        # inconnu », pas « malformé ».
        futur = {"format": 2, "type": ps.TYPE_MANIFESTE, "autre": 1}
        self.refuse("FORMAT_INCONNU", serialiser(futur))

    def test_un_manifeste_de_licence_n_est_pas_un_manifeste_de_mise_a_jour(self):
        futur = dict(self.manifeste_valide(), type="licence")
        self.refuse("TYPE_INCONNU", serialiser(futur))

    def test_le_manifeste_n_est_jamais_reserialise(self):
        # Les octets signés sont ceux qui sont lus : des espaces superflus ou un
        # ordre de clés différent se signent tels quels et se lisent tels quels.
        manifeste = self.manifeste_valide()
        octets = json.dumps(manifeste, indent=None, separators=(",", ":")).encode()
        self.assertEqual(self.lire(octets), manifeste)


# --------------------------------------------------------------------------
# Vérification d'un paquet complet
# --------------------------------------------------------------------------

class PaquetAccepte(Atelier):

    def test_paquet_valide_accepte_et_en_lecture_seule(self):
        trio = self.fabriquer()
        verifie = self.verifier(trio)
        self.assertEqual((verifie.version, verifie.version_minimale, verifie.client),
                         ("1.2.0", "1.1.0", "cabinet-01"))
        self.assertEqual(verifie.date, "2026-11-08T14:03:00Z")
        chemin = DOSSIER_RACINE + "/LICENSE"
        self.assertEqual(verifie.fichiers[chemin],
                         (len(b"texte de licence\n"), sha(b"texte de licence\n")))
        self.assertEqual(len(verifie.fichiers), 5)
        with self.assertRaises(TypeError):
            verifie.fichiers["x"] = (1, "y")
        with self.assertRaises(AttributeError):
            verifie.version = "9.9.9"

    def test_chemin_archive_accepte_str_et_pathlike(self):
        import pathlib
        trio = self.fabriquer()
        self.verifier(trio)
        self.verifier(trio._replace(archive=pathlib.Path(trio.archive)))

    def test_aucun_fichier_ecrit_nulle_part(self):
        trio = self.fabriquer()
        avant = sorted(os.listdir(self.dossier))
        self.verifier(trio)
        self.assertEqual(sorted(os.listdir(self.dossier)), avant)

    def test_un_dossier_parent_est_admis_comme_entree(self):
        trio = self.fabriquer()
        with zipfile.ZipFile(trio.archive) as z:
            dossiers = [i.filename for i in z.infolist() if i.filename.endswith("/")]
        self.assertIn(DOSSIER_RACINE + "/formulaire/", dossiers)
        self.verifier(trio)

    def test_archive_sans_entrees_de_dossier_acceptee(self):
        declares = contenus_normaux()
        trio = self.fabriquer(
            entrees=[_entree_fichier(n, o) for n, o in declares.items()])
        self.verifier(trio)

    def test_entree_stockee_acceptee(self):
        declares = contenus_normaux()
        entrees = [_entree_fichier(n, o, zipfile.ZIP_STORED) for n, o in declares.items()]
        self.verifier(self.fabriquer(entrees=entrees))


class Versions(Atelier):

    def test_version_anterieure_refusee(self):
        self.refus("VERSION_NON_SUPERIEURE",
                   self.fabriquer(version="1.1.0", minimale="1.0.0"), installee="1.2.0")

    def test_version_egale_refusee(self):
        # M10 : `>=` au lieu de `>` laisserait réinstaller la même version.
        self.refus("VERSION_NON_SUPERIEURE",
                   self.fabriquer(version="1.2.0", minimale="1.0.0"), installee="1.2.0")

    def test_minimale_non_atteinte(self):
        # M11 : sans ce contrôle, un PC trop ancien recevrait un paquet qui
        # suppose des étapes intermédiaires.
        self.refus("VERSION_MINIMALE_NON_ATTEINTE",
                   self.fabriquer(version="1.2.0", minimale="1.1.0"), installee="1.0.9")

    def test_un_dix_apres_un_neuf_est_une_mise_a_jour(self):
        # M9 : comparées comme des chaînes, "1.10.0" < "1.9.0" et le paquet
        # serait refusé comme antérieur.
        trio = self.fabriquer(version="1.10.0", minimale="1.9.0")
        self.assertEqual(self.verifier(trio, installee="1.9.0").version, "1.10.0")

    def test_minimale_atteinte_pile(self):
        trio = self.fabriquer(version="1.2.0", minimale="1.1.0")
        self.verifier(trio, installee="1.1.0")

    def test_installee_inconnue_ou_illisible(self):
        trio = self.fabriquer()
        for installee in ("inconnue", "", "1.1", "1.1.0-beta", None, 110):
            with self.subTest(installee=installee):
                self.refus("VERSION_INSTALLEE_ILLISIBLE", trio, installee=installee)

    def test_version_du_manifeste_malformee(self):
        for mauvaise in ("1.2", "01.2.0", "1.2.0-rc1", "", "x"):
            with self.subTest(version=mauvaise):
                trio = self.fabriquer(retoucher=lambda m, v=mauvaise: m.update(version=v))
                self.refus("VERSION_MALFORMEE", trio)
        trio = self.fabriquer(retoucher=lambda m: m.update(version_minimale="1.1"))
        self.refus("VERSION_MALFORMEE", trio)

    def test_minimale_superieure_a_la_version_est_malformee(self):
        self.refus("MANIFESTE_MALFORME",
                   self.fabriquer(version="1.2.0", minimale="1.3.0"))

    def test_minimale_egale_a_la_version_est_inutilisable(self):
        # Aucune version installée ne peut être à la fois < version et >= minimale.
        trio = self.fabriquer(version="1.2.0", minimale="1.2.0")
        self.refus("VERSION_MINIMALE_NON_ATTEINTE", trio, installee="1.1.9")
        self.refus("VERSION_NON_SUPERIEURE", trio, installee="1.2.0")
        self.refus("VERSION_NON_SUPERIEURE", trio, installee="1.3.0")

    def test_autre_client(self):
        self.refus("CLIENT_DIFFERENT", self.fabriquer(client="cabinet-02"))
        self.refus("CLIENT_DIFFERENT", self.fabriquer(), client="cabinet-02")


class Chemins(Atelier):

    def test_chemin_dangereux_dans_le_manifeste(self):
        for nom in ParametresChemins.DANGEREUX_DU_CONTRAT:
            with self.subTest(nom=nom):
                declares = contenus_normaux()
                declares[nom] = b"x"
                trio = self.fabriquer(
                    declares=declares, entrees=entrees_depuis(contenus_normaux()))
                self.refus("CHEMIN_DANGEREUX", trio)

    def test_chemin_dangereux_comme_nom_d_entree_du_zip(self):
        # Le manifeste est sain : seul le nom de l'entrée du zip est en cause. Les
        # noms avec NUL et ceux modifiés par zipfile sous Windows passent par
        # d'autres tests.
        for nom in ParametresChemins.DANGEREUX_DU_CONTRAT:
            if "\x00" in nom or nom.endswith("/"):
                continue
            with self.subTest(nom=nom):
                entrees = entrees_depuis(contenus_normaux())
                entrees.append(_entree_fichier(nom, b"x"))
                trio = self.fabriquer(entrees=entrees)
                self.refus("CHEMIN_DANGEREUX", trio)

    def test_nom_avec_nul_dans_le_zip(self):
        # `zipfile` tronque le nom au NUL : filename ("…/ZQZ") diffère du nom brut.
        # M15 (juger le nom corrigé) le laisserait passer, ici comme à
        # `a\b` sous Windows.
        entrees = entrees_depuis(contenus_normaux())
        entrees.append(_entree_fichier(DOSSIER_RACINE + "/ZQZ", b"x"))
        trio = self.fabriquer(
            entrees=entrees,
            retoucher_zip=lambda o: o.replace(b"/ZQZ", b"/Z\x00Z"))
        with zipfile.ZipFile(trio.archive) as z:
            noms = [(i.orig_filename, i.filename) for i in z.infolist()]
        self.assertIn((DOSSIER_RACINE + "/Z\x00Z", DOSSIER_RACINE + "/Z"), noms)
        self.refus("CHEMIN_DANGEREUX", trio)

    def test_la_garde_juge_le_nom_brut_et_non_le_nom_corrige(self):
        # Même effet que `a\b` sous Windows (où zipfile le réécrit `a/b`) :
        # un nom dont `filename` est propre mais `orig_filename` ne l'est pas.
        class Entree:
            orig_filename = "a\\b"
            filename = "a/b"
            file_size = 1
            external_attr = 0
            flag_bits = 0
            compress_type = zipfile.ZIP_DEFLATED
        with self.assertRaises(PaquetRefuse) as c:
            ps._controler_entrees([Entree()])
        self.assertEqual(c.exception.code, "CHEMIN_DANGEREUX")

        class EntreeProprement(Entree):
            orig_filename = "a/b"
        fichiers, dossiers = ps._controler_entrees([EntreeProprement()])
        self.assertEqual((list(fichiers), dossiers), (["a/b"], set()))

    def test_entree_de_dossier_a_nom_de_dossier_avec_donnees(self):
        entrees = entrees_depuis(contenus_normaux())
        info = zipfile.ZipInfo(DOSSIER_RACINE + "/a/", DATE_FIXE)
        entrees.append((info, b"des octets"))
        self.refus("CHEMIN_DANGEREUX", self.fabriquer(entrees=entrees))

    def test_dossier_au_nom_dangereux(self):
        for nom in ("../", "a//", "C:/", ".cache/", "x y/"):
            with self.subTest(nom=nom):
                entrees = entrees_depuis(contenus_normaux()) + [_entree_dossier(nom)]
                self.refus("CHEMIN_DANGEREUX", self.fabriquer(entrees=entrees))

    def test_doublon_a_la_casse_pres_dans_le_manifeste(self):
        declares = contenus_normaux()
        declares[DOSSIER_RACINE + "/A.js"] = b"1"
        declares[DOSSIER_RACINE + "/a.js"] = b"2"
        self.refus("CHEMIN_EN_DOUBLE", self.fabriquer(declares=declares))

    def test_doublon_du_manifeste_refuse_avant_de_lire_l_archive(self):
        # Le zip, lui, n'a qu'une des deux graphies : seule la garde du MANIFESTE
        # (étape 4) peut dire CHEMIN_EN_DOUBLE ; sans elle, on lirait
        # FICHIER_MANQUANT à l'étape 7.
        declares = contenus_normaux()
        declares[DOSSIER_RACINE + "/A.js"] = b"1"
        declares[DOSSIER_RACINE + "/a.js"] = b"2"
        entrees = entrees_depuis(contenus_normaux())
        entrees.append(_entree_fichier(DOSSIER_RACINE + "/A.js", b"1"))
        self.refus("CHEMIN_EN_DOUBLE",
                   self.fabriquer(declares=declares, entrees=entrees))

    def test_doublon_a_la_casse_pres_dans_le_zip(self):
        declares = contenus_normaux()
        entrees = entrees_depuis(declares)
        entrees.append(_entree_fichier(DOSSIER_RACINE + "/A.js", b"1"))
        entrees.append(_entree_fichier(DOSSIER_RACINE + "/a.js", b"2"))
        self.refus("CHEMIN_EN_DOUBLE", self.fabriquer(declares=declares, entrees=entrees))

    def test_deux_entrees_de_meme_nom_dans_le_zip(self):
        declares = contenus_normaux()
        entrees = entrees_depuis(declares)
        entrees.append(_entree_fichier(DOSSIER_RACINE + "/LICENSE", b"autre"))
        self.refus("CHEMIN_EN_DOUBLE", self.fabriquer(declares=declares, entrees=entrees))

    def test_un_fichier_et_un_dossier_de_meme_nom(self):
        declares = contenus_normaux()
        entrees = entrees_depuis(declares) + [_entree_dossier(DOSSIER_RACINE + "/LICENSE/")]
        self.refus("CHEMIN_EN_DOUBLE", self.fabriquer(declares=declares, entrees=entrees))

    def test_plafond_du_nombre_de_fichiers(self):
        # 10 000 fichiers déclarés : le plafond n'est pas atteint (le refus vient
        # alors de l'archive, qui n'a pas ces fichiers) ; 10 001 : il l'est.
        for nombre, code in ((ps.NOMBRE_MAX_FICHIERS, "FICHIER_EN_TROP"),
                             (ps.NOMBRE_MAX_FICHIERS + 1, "MANIFESTE_MALFORME")):
            with self.subTest(nombre=nombre):
                declares = {"R/%05d" % i: b"" for i in range(nombre)}
                trio = self.fabriquer(
                    declares=declares, compact=True,
                    entrees=entrees_depuis(contenus_normaux()))
                self.assertLess(len(trio.manifeste), ps.TAILLE_MAX_MANIFESTE)
                self.refus(code, trio)

    def test_plafond_de_la_somme_des_tailles(self):
        nom = DOSSIER_RACINE + "/LICENSE"
        limite = ps.OCTETS_MAX_TOTAL
        total = len(contenus_normaux()[nom])

        def gonfler(supplement):
            def retoucher(manifeste):
                manifeste["fichiers"][nom]["taille"] += supplement
            return retoucher
        reste = sum(len(o) for o in contenus_normaux().values()) - total
        # Pile à la limite : le plafond ne parle pas (la taille fausse sera relevée
        # plus loin) ; un octet de plus, il parle.
        pile = limite - reste - total
        self.refus("FICHIER_ALTERE", self.fabriquer(retoucher=gonfler(pile)))
        self.refus("MANIFESTE_MALFORME", self.fabriquer(retoucher=gonfler(pile + 1)))

    def test_plusieurs_dossiers_racine_refuses(self):
        declares = contenus_normaux()
        declares["Autre/x.js"] = b"x"
        self.refus("MANIFESTE_MALFORME", self.fabriquer(declares=declares))


class ParametresChemins:
    """Le tableau de A11, partagé par les tests de manifeste et de zip."""
    DANGEREUX_DU_CONTRAT = [
        "/etc/x", "../x", "a/../../x", "a\\..\\x", "a\\b", "C:x", "C:/x", "a:flux",
        "a//b", "./a", "a/", ".cache/x", "a.", "CON", "nul.txt", "Com1.js", "é.js",
        "a b", "a\x00b", "x" * 241,
    ]


class ContenuDeLArchive(Atelier):

    def test_archive_modifiee_apres_signature(self):
        trio = self.fabriquer()
        with open(trio.archive, "r+b") as f:
            f.seek(100)
            octet = f.read(1)
            f.seek(100)
            f.write(bytes([octet[0] ^ 1]))
        self.refus("ARCHIVE_DIFFERENTE", trio)

    def test_archive_plus_longue_ou_plus_courte(self):
        trio = self.fabriquer()
        with open(trio.archive, "ab") as f:
            f.write(b"\0")
        # Le détail dit que c'est la TAILLE : elle se compare avant l'empreinte,
        # pour ne pas hacher un fichier démesuré.
        self.assertIn("taille", self.refus("ARCHIVE_DIFFERENTE", trio).detail)
        trio = self.fabriquer()
        with open(trio.archive, "r+b") as f:
            f.truncate(os.path.getsize(trio.archive) - 1)
        self.assertIn("taille", self.refus("ARCHIVE_DIFFERENTE", trio).detail)

    def test_taille_juste_empreinte_fausse(self):
        # La taille est comparée avant l'empreinte : sans cette seconde garde, un
        # octet modifié sans changer la longueur passerait.
        trio = self.fabriquer()
        with open(trio.archive, "rb") as f:
            octets = bytearray(f.read())
        octets[-1] ^= 0xFF
        with open(trio.archive, "wb") as f:
            f.write(octets)
        self.assertIn("empreinte", self.refus("ARCHIVE_DIFFERENTE", trio).detail)

    def test_empreinte_d_archive_fausse_dans_le_manifeste_signe(self):
        trio = self.fabriquer(retoucher=lambda m: m["archive"].update(sha256="0" * 64))
        self.refus("ARCHIVE_DIFFERENTE", trio)
        trio = self.fabriquer(retoucher=lambda m: m["archive"].update(
            taille=m["archive"]["taille"] + 1))
        self.refus("ARCHIVE_DIFFERENTE", trio)

    def test_archive_absente_ou_pas_un_fichier(self):
        trio = self.fabriquer()
        self.refus("ARCHIVE_ILLISIBLE", trio._replace(archive=trio.archive + ".absente"))
        self.refus("ARCHIVE_ILLISIBLE", trio._replace(archive=self.dossier))
        self.refus("ARCHIVE_ILLISIBLE", trio._replace(archive=None))

    def test_archive_qui_n_est_pas_un_zip(self):
        # Octets quelconques dont l'empreinte est signée : seul zipfile peut dire non.
        self.numero += 1
        archive = os.path.join(self.dossier, "faux.zip")
        with open(archive, "wb") as f:
            f.write(b"ceci n'est pas une archive zip" * 10)
        with open(archive, "rb") as f:
            octets = f.read()
        manifeste = manifeste_de(contenus_normaux(), octets)
        brut = serialiser(manifeste)
        trio = Trio(archive, brut, essai.signer(GRAINE_A, brut), (CLE_A,))
        self.refus("ARCHIVE_ILLISIBLE", trio)

    def test_lien_symbolique_refuse(self):
        declares = contenus_normaux()
        entrees = entrees_depuis(declares)
        info = zipfile.ZipInfo(DOSSIER_RACINE + "/lien", DATE_FIXE)
        info.external_attr = 0o120777 << 16
        entrees.append((info, b"formulaire/index.html"))
        self.refus("ENTREE_INTERDITE", self.fabriquer(declares=declares, entrees=entrees))

    def test_entree_chiffree_refusee(self):
        def chiffrer(octets):
            # Drapeau « chiffré » (bit 0) dans le répertoire central seulement :
            # zipfile ne sait pas écrire cet état, on le pose à la main.
            position = 0
            while True:
                position = octets.find(b"PK\x01\x02", position)
                if position < 0:
                    break
                longueur = struct.unpack_from("<H", octets, position + 28)[0]
                nom = octets[position + 46:position + 46 + longueur]
                if nom.endswith(b"/LICENSE"):
                    drapeaux = struct.unpack_from("<H", octets, position + 8)[0]
                    octets = (octets[:position + 8] + struct.pack("<H", drapeaux | 1)
                              + octets[position + 10:])
                position += 4
            return octets
        trio = self.fabriquer(retoucher_zip=chiffrer)
        self.refus("ENTREE_INTERDITE", trio)

    def test_compression_bzip2_refusee(self):
        declares = contenus_normaux()
        entrees = [e for e in entrees_depuis(declares)]
        entrees.append(_entree_fichier(DOSSIER_RACINE + "/b.js", b"x" * 100,
                                       zipfile.ZIP_BZIP2))
        declares[DOSSIER_RACINE + "/b.js"] = b"x" * 100
        self.refus("ENTREE_INTERDITE", self.fabriquer(declares=declares, entrees=entrees))

    def test_fichier_en_trop(self):
        declares = contenus_normaux()
        entrees = entrees_depuis(declares)
        entrees.append(_entree_fichier(DOSSIER_RACINE + "/serveur/porte_derobee.py", b"x"))
        exception = self.refus("FICHIER_EN_TROP",
                               self.fabriquer(declares=declares, entrees=entrees))
        self.assertIn("porte_derobee.py", exception.detail)

    def test_fichier_en_moins(self):
        declares = contenus_normaux()
        entrees = [e for e in entrees_depuis(declares)
                   if not e[0].filename.endswith("serveur/serveur.py")]
        self.refus("FICHIER_MANQUANT", self.fabriquer(declares=declares, entrees=entrees))

    def test_entree_de_dossier_orpheline(self):
        declares = contenus_normaux()
        entrees = entrees_depuis(declares) + [_entree_dossier(DOSSIER_RACINE + "/vide/")]
        self.refus("FICHIER_EN_TROP", self.fabriquer(declares=declares, entrees=entrees))

    def test_dossier_a_la_racine_orphelin(self):
        declares = contenus_normaux()
        entrees = entrees_depuis(declares) + [_entree_dossier("autre/")]
        self.refus("FICHIER_EN_TROP", self.fabriquer(declares=declares, entrees=entrees))

    def test_empreinte_de_fichier_fausse(self):
        def faux(m):
            m["fichiers"][DOSSIER_RACINE + "/LICENSE"]["sha256"] = "0" * 64
        self.refus("FICHIER_ALTERE", self.fabriquer(retoucher=faux))

    def test_taille_de_fichier_fausse(self):
        def faux(m):
            m["fichiers"][DOSSIER_RACINE + "/LICENSE"]["taille"] += 1
        self.refus("FICHIER_ALTERE", self.fabriquer(retoucher=faux))

    def test_contenu_different_du_manifeste_a_taille_egale(self):
        declares = contenus_normaux()
        entrees = [e for e in entrees_depuis(declares)
                   if not e[0].filename.endswith("/LICENSE")]
        entrees.append(_entree_fichier(DOSSIER_RACINE + "/LICENSE",
                                       b"TEXTE DE LICENCE\n"))
        self.assertEqual(len(b"TEXTE DE LICENCE\n"), len(declares[DOSSIER_RACINE + "/LICENSE"]))
        self.refus("FICHIER_ALTERE", self.fabriquer(declares=declares, entrees=entrees))

    def test_entree_qui_se_decompresse_au_dela_de_sa_taille_declaree(self):
        # Une entrée de 5 000 octets dont le répertoire central n'en déclare que
        # 10, le manifeste en déclarant 10 : zipfile borne la lecture à la taille
        # déclarée, puis constate que le CRC ne correspond pas.
        nom = DOSSIER_RACINE + "/bombe.bin"
        reel = b"A" * 5000
        declares = contenus_normaux()
        entrees = entrees_depuis(declares)
        entrees.append(_entree_fichier(nom, reel))

        def tronquer_la_taille(octets):
            position = 0
            while True:
                position = octets.find(b"PK\x01\x02", position)
                if position < 0:
                    return octets
                longueur = struct.unpack_from("<H", octets, position + 28)[0]
                if octets[position + 46:position + 46 + longueur] == nom.encode():
                    return (octets[:position + 24] + struct.pack("<I", 10)
                            + octets[position + 28:])
                position += 4
        declares[nom] = reel[:10]
        trio = self.fabriquer(declares=declares, entrees=entrees,
                              retoucher_zip=tronquer_la_taille)
        with zipfile.ZipFile(trio.archive) as z:
            self.assertEqual(z.getinfo(nom).file_size, 10)
        # La taille déclarée concorde avec le manifeste : c'est la LECTURE qui
        # échoue (CRC), pas la comparaison de tailles.
        self.assertIn("lecture impossible", self.refus("FICHIER_ALTERE", trio).detail)

    def test_taille_declaree_dans_le_zip_differente_de_celle_du_manifeste(self):
        nom = DOSSIER_RACINE + "/LICENSE"

        def mentir(octets):
            position = 0
            while True:
                position = octets.find(b"PK\x01\x02", position)
                if position < 0:
                    return octets
                longueur = struct.unpack_from("<H", octets, position + 28)[0]
                if octets[position + 46:position + 46 + longueur] == nom.encode():
                    return (octets[:position + 24] + struct.pack("<I", 3)
                            + octets[position + 28:])
                position += 4
        exception = self.refus("FICHIER_ALTERE", self.fabriquer(retoucher_zip=mentir))
        # Refusé AVANT toute lecture : c'est la comparaison de tailles qui parle.
        self.assertIn("taille déclarée", exception.detail)

    def test_lecture_bornee_a_taille_plus_un(self):
        # M19 : une lecture non bornée lirait tout le flux d'une entrée qui
        # déborde. Le flux ci-dessous sert 10 Mio ; sur une taille annoncée de 10
        # octets, on ne doit en demander que 11.
        class Flux:
            def __init__(self):
                self.servis = 0
                self.restant = 10 * 1024 * 1024

            def read(self, n=-1):
                n = self.restant if n is None or n < 0 else min(n, self.restant)
                self.restant -= n
                self.servis += n
                return b"\0" * n

        flux = Flux()
        empreinte, lus, _ = ps._lire_borne(flux, 10)
        self.assertEqual(lus, 11)
        self.assertEqual(flux.servis, 11)
        self.assertNotEqual(empreinte, sha(b"\0" * 10))

    def test_lecture_bornee_rend_taille_exacte_quand_le_flux_est_juste(self):
        import io
        empreinte, lus, donnees = ps._lire_borne(io.BytesIO(b"abc"), 3, garder=True)
        self.assertEqual((lus, donnees, empreinte), (3, b"abc", sha(b"abc")))
        empreinte, lus, donnees = ps._lire_borne(io.BytesIO(b"ab"), 3)
        self.assertEqual((lus, donnees), (2, None))

    def test_version_divergente_entre_manifeste_et_version_json(self):
        trio = self.fabriquer(declares=contenus_normaux("1.1.9"), version="1.2.0")
        self.refus("VERSION_INCOHERENTE", trio)

    def test_version_json_absent_du_manifeste(self):
        declares = contenus_normaux()
        del declares[DOSSIER_RACINE + "/formulaire/version.json"]
        self.refus("VERSION_INCOHERENTE", self.fabriquer(declares=declares))

    def test_version_json_illisible_ou_sans_version(self):
        for contenu in (b"pas du json", b"[]", b'{"autre": "1.2.0"}',
                        b'{"version": "1.2.0", "version": "1.2.0"}', b"\xff",
                        b'{"version": "1.2.0", "x": NaN}'):
            with self.subTest(contenu=contenu):
                declares = contenus_normaux()
                declares[DOSSIER_RACINE + "/formulaire/version.json"] = contenu
                self.refus("VERSION_INCOHERENTE", self.fabriquer(declares=declares))

    def test_version_json_demesure_refuse_sans_etre_charge_en_memoire(self):
        nom = DOSSIER_RACINE + "/formulaire/version.json"
        base = b'{"version": "1.2.0"}'
        # Pile à la limite : accepté ; un octet de plus : refusé.
        declares = contenus_normaux()
        declares[nom] = base + b" " * (ps.TAILLE_MAX_VERSION - len(base))
        self.verifier(self.fabriquer(declares=declares))
        declares[nom] = declares[nom] + b" "
        self.refus("VERSION_INCOHERENTE", self.fabriquer(declares=declares))

    def test_version_json_a_la_racine_d_un_autre_dossier_ne_compte_pas(self):
        declares = contenus_normaux()
        del declares[DOSSIER_RACINE + "/formulaire/version.json"]
        declares[DOSSIER_RACINE + "/serveur/formulaire/version.json"] = b'{"version": "1.2.0"}'
        self.refus("VERSION_INCOHERENTE", self.fabriquer(declares=declares))


class ConfianceEtAlterations(Atelier):

    def test_signature_d_une_cle_absente_de_la_liste(self):
        trio = self.fabriquer(graine=GRAINE_B)
        self.refus("SIGNATURE_INVALIDE", trio)

    def test_la_liste_embarquee_dans_le_paquet_de_l_attaquant_est_ignoree(self):
        # A8 : le paquet de l'attaquant embarque sa propre liste de clés, qui
        # contient sa clé. Vérifié avec la liste INSTALLÉE, il est refusé.
        declares = contenus_normaux()
        declares[DOSSIER_RACINE + "/serveur/cles_publication.json"] = liste_de_cles(CLE_B)
        trio = self.fabriquer(declares=declares, graine=GRAINE_B)
        self.assertEqual(
            ps.charger_cles_de_confiance(
                declares[DOSSIER_RACINE + "/serveur/cles_publication.json"]), (CLE_B,))
        self.refus("SIGNATURE_INVALIDE", trio._replace(cles=(CLE_A,)))
        # Témoin : avec la clé de l'attaquant en confiance, le même paquet passe.
        self.verifier(trio._replace(cles=(CLE_B,)))

    def test_un_octet_modifie_a_soixante_quatre_positions(self):
        trio = self.fabriquer()
        rng = random.Random(8032)
        with open(trio.archive, "rb") as f:
            archive = f.read()
        cas = (("manifeste", trio.manifeste, "SIGNATURE_INVALIDE"),
               ("signature", trio.signature, "SIGNATURE_INVALIDE"),
               ("archive", archive, "ARCHIVE_DIFFERENTE"))
        for nom, octets, code in cas:
            positions = {0, len(octets) - 1} | {
                rng.randrange(len(octets)) for _ in range(30)}
            for position in sorted(positions):
                with self.subTest(piece=nom, position=position):
                    alteres = bytearray(octets)
                    alteres[position] ^= 1 << rng.randrange(8)
                    if nom == "manifeste":
                        essai_trio = trio._replace(manifeste=bytes(alteres))
                    elif nom == "signature":
                        essai_trio = trio._replace(signature=bytes(alteres))
                    else:
                        copie = os.path.join(self.dossier, "alteree.zip")
                        with open(copie, "wb") as f:
                            f.write(alteres)
                        essai_trio = trio._replace(archive=copie)
                    self.refus(code, essai_trio)

    def test_fuzz_de_trois_cents_archives_resignees(self):
        # Archives tronquées ou altérées, MAIS dont le manifeste est recalculé et
        # signé : l'empreinte d'archive ne peut plus les arrêter, ce sont les
        # gardes qui lisent le zip qui sont éprouvées. Toute issue est une
        # acceptation ou une PaquetRefuse à code connu ; jamais une autre
        # exception (D7).
        graine = int.from_bytes(os.urandom(6), "big")
        rng = random.Random(graine)
        base = self.fabriquer()
        with open(base.archive, "rb") as f:
            original = f.read()
        declares = contenus_normaux()
        issues = {}
        for i in range(300):
            octets = bytearray(original)
            mode = rng.choice(("tronquer", "bits", "octets", "bloc"))
            if mode == "tronquer":
                octets = octets[:rng.randrange(len(octets))]
            elif mode == "bits":
                for _ in range(rng.randrange(1, 6)):
                    octets[rng.randrange(len(octets))] ^= 1 << rng.randrange(8)
            elif mode == "octets":
                for _ in range(rng.randrange(1, 4)):
                    octets[rng.randrange(len(octets))] = rng.randrange(256)
            else:
                debut = rng.randrange(len(octets))
                octets[debut:debut + rng.randrange(1, 40)] = bytes(
                    rng.randrange(256) for _ in range(rng.randrange(0, 40)))
            archive = os.path.join(self.dossier, "fuzz%d.zip" % i)
            with open(archive, "wb") as f:
                f.write(octets)
            brut = serialiser(manifeste_de(declares, bytes(octets)))
            try:
                ps.verifier_paquet(archive, brut, essai.signer(GRAINE_A, brut),
                                   (CLE_A,), "1.1.0", "cabinet-01")
                issues["accepte"] = issues.get("accepte", 0) + 1
            except PaquetRefuse as erreur:
                self.assertIn(erreur.code, ps.CODES, "graine %d, essai %d" % (graine, i))
                issues[erreur.code] = issues.get(erreur.code, 0) + 1
            except Exception as erreur:  # noqa: BLE001 - c'est précisément ce qu'on traque
                self.fail("graine %d, essai %d (%s) : %s %r"
                          % (graine, i, mode, type(erreur).__name__, erreur))
            os.remove(archive)
        # Le fuzz doit réellement atteindre les gardes de lecture du zip.
        print("\n[C5-T1] fuzz, issues des 300 archives : %r" % (issues,))
        gardes = set(issues) - {"accepte"}
        self.assertGreaterEqual(len(gardes), 2, issues)


class CodesDeRefus(unittest.TestCase):

    # Chaque code de D7 -> un test de ce fichier qui ne l'atteint que par sa garde.
    COUVERTURE = {
        "MANIFESTE_TROP_GRAND": "LectureDuManifeste.test_trop_grand_avant_tout_calcul",
        "SIGNATURE_INVALIDE": "LectureDuManifeste.test_l_ordre_la_signature_avant_toute_analyse",
        "MANIFESTE_MALFORME": "LectureDuManifeste.test_refus_signes_de_forme",
        "TYPE_INCONNU": "LectureDuManifeste.test_type_et_format_inconnus",
        "FORMAT_INCONNU": "LectureDuManifeste.test_type_et_format_inconnus",
        "CLES_DE_CONFIANCE_INVALIDES": "ClesDeConfiance.test_refus_de_forme",
        "VERSION_MALFORMEE": "AnalyseDesVersions.test_formes_invalides",
        "VERSION_INSTALLEE_ILLISIBLE": "Versions.test_installee_inconnue_ou_illisible",
        "VERSION_NON_SUPERIEURE": "Versions.test_version_egale_refusee",
        "VERSION_MINIMALE_NON_ATTEINTE": "Versions.test_minimale_non_atteinte",
        "CLIENT_DIFFERENT": "Versions.test_autre_client",
        "CHEMIN_DANGEREUX": "Chemins.test_chemin_dangereux_dans_le_manifeste",
        "CHEMIN_EN_DOUBLE": "Chemins.test_doublon_a_la_casse_pres_dans_le_manifeste",
        "ARCHIVE_DIFFERENTE": "ContenuDeLArchive.test_archive_modifiee_apres_signature",
        "ARCHIVE_ILLISIBLE": "ContenuDeLArchive.test_archive_qui_n_est_pas_un_zip",
        "ENTREE_INTERDITE": "ContenuDeLArchive.test_lien_symbolique_refuse",
        "FICHIER_EN_TROP": "ContenuDeLArchive.test_fichier_en_trop",
        "FICHIER_MANQUANT": "ContenuDeLArchive.test_fichier_en_moins",
        "FICHIER_ALTERE": "ContenuDeLArchive.test_empreinte_de_fichier_fausse",
        "VERSION_INCOHERENTE": "ContenuDeLArchive.test_version_divergente_entre_manifeste_et_version_json",
    }

    def test_la_table_couvre_exactement_les_codes_de_d7(self):
        self.assertEqual(sorted(self.COUVERTURE), sorted(ps.CODES))
        self.assertEqual(len(ps.CODES), len(set(ps.CODES)))

    def test_chaque_test_cite_existe(self):
        modules = sys.modules[__name__]
        for code, reference in self.COUVERTURE.items():
            classe, methode = reference.split(".")
            with self.subTest(code=code):
                self.assertTrue(hasattr(getattr(modules, classe), methode), reference)

    def test_un_code_inconnu_est_une_erreur_de_programmation(self):
        with self.assertRaises(ValueError):
            PaquetRefuse("CODE_QUI_N_EXISTE_PAS")

    def test_le_code_ne_contient_aucun_chemin_le_detail_le_peut(self):
        erreur = PaquetRefuse("FICHIER_EN_TROP", "fichier absent du manifeste : 'a/b'")
        self.assertEqual(erreur.code, "FICHIER_EN_TROP")
        self.assertNotIn("/", erreur.code)
        self.assertIn("a/b", erreur.detail)


class ImportsDuModule(unittest.TestCase):

    def test_le_module_ne_signe_jamais_et_n_importe_que_la_bibliotheque_standard(self):
        # Complété par la garde générale de tests/test_serveur.py ; celle-ci
        # nomme en plus les modules de signature qui n'ont rien à faire ici.
        source = inspect.getsource(ps)
        for interdit in ("cryptography", "ctypes", "subprocess", "socket"):
            self.assertNotIn("import " + interdit, source)


if __name__ == "__main__":
    unittest.main()
