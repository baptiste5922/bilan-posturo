"""Logo propre au cabinet (contrat C2-T2).

Le chemin `cabinet.logo` de config.json est une saisie libre qui finit dans un
attribut `src` côté tablette. Le serveur le valide une fois, au démarrage, par
trois fonctions pures de la racine web :

  forme_logo     — la forme du texte, sans toucher au disque ;
  confiner_logo  — le chemin résolu pour de bon : sous la racine, sans lien ;
  valider_logo   — l'enchaînement, plus l'existence, la taille, la signature.

Tout refus donne « pas de logo », jamais un logo de repli. Les tests de
validation travaillent dans une racine temporaire ; ceux du démarrage lancent
un vrai serveur dans un bac à sable (patron de tests/test_integration.py).

    python3 -m unittest tests.test_logo
    python3 -O -m unittest tests.test_logo

Bibliothèque standard seule. Pas d'`assert` nu : il s'évaporerait sous -O.
"""

import ast
import base64
import contextlib
import http.client
import inspect
import io
import json
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

DOSSIER_TESTS = os.path.dirname(os.path.abspath(__file__))
PROJET = os.path.dirname(DOSSIER_TESTS)
sys.path.insert(0, os.path.join(PROJET, "serveur"))
sys.path.insert(0, DOSSIER_TESTS)

import serveur
from test_integration import (
    MOT_DE_PASSE, UTILISATEUR, cryptography_absente, demarrer_sandbox_court)

PNG = b"\x89PNG\r\n\x1a\n"
JPEG = b"\xff\xd8\xff\xe0"


def ecrire(chemin, debut, taille=64):
    """Écrit un fichier fictif d'au moins `taille` octets commençant par
    `debut` : le serveur ne décode jamais l'image, il en lit la signature."""
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "wb") as f:
        f.write(debut + b"\x00" * max(0, taille - len(debut)))


@contextlib.contextmanager
def windows_simule():
    """Simule les traits de Windows qui comptent ici : normcase ignore la
    casse, realpath rend la casse du disque, et lstat trouve un fichier sous
    n'importe quelle casse. Le disque réel peut être sensible à la casse
    (Linux) ou non (macOS) : le dernier composant est donc retrouvé en relisant
    le dossier parent. Le reste de lstat est le vrai."""
    realpath_reel = os.path.realpath
    lstat_reel = os.lstat

    def nom_du_disque(chemin):
        parent, nom = os.path.split(chemin)
        try:
            noms = os.listdir(parent)
        except OSError:
            return chemin
        for candidat in noms:
            if candidat.lower() == nom.lower():
                return os.path.join(parent, candidat)
        return chemin

    def realpath_disque(chemin, *args, **options):
        return nom_du_disque(realpath_reel(chemin, *args, **options))

    def lstat_disque(chemin, *args, **options):
        return lstat_reel(nom_du_disque(chemin), *args, **options)

    with unittest.mock.patch.object(serveur.os.path, "normcase", str.lower), \
         unittest.mock.patch.object(serveur.os.path, "realpath", realpath_disque), \
         unittest.mock.patch.object(serveur.os, "lstat", lstat_disque):
        yield


class RacineTemporaire(unittest.TestCase):
    """Une racine web jetable `web/`, avec à côté un PNG valide `hors.png`
    hors de la racine : la cible de toute remontée ou de tout lien externe."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bilan-test-logo-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.racine = os.path.join(self.tmp, "web")
        os.makedirs(os.path.join(self.racine, "images", "cabinet"))
        self.hors = os.path.join(self.tmp, "hors.png")
        ecrire(self.hors, PNG)

    def poser(self, relatif, debut=PNG, taille=64):
        chemin = os.path.join(self.racine, *relatif.split("/"))
        ecrire(chemin, debut, taille)
        return chemin

    def lier(self, cible, lien):
        """Crée un lien symbolique, ou saute le test (jamais vert à vide)
        quand le système ne le permet pas (Windows sans privilège)."""
        os.makedirs(os.path.dirname(lien), exist_ok=True)
        try:
            os.symlink(cible, lien)
        except (OSError, NotImplementedError) as erreur:
            self.skipTest("lien symbolique impossible ici : {}".format(erreur))


class FormeLogo(unittest.TestCase):
    """Première couche : la forme du texte seule, sans système de fichiers."""

    def test_remontee_et_chemins_absolus_sont_hors_racine(self):
        for chemin in ("../config.json", "images/../../x.png", "..", "../x.png",
                       "images/..\\x.png", "..\\x.png",
                       "/etc/x.png", "\\x.png", "C:/x.png", "c:\\x.png",
                       "C:x.png", "\\\\hote\\x.png", "//hote/x.png"):
            with self.subTest(chemin=chemin):
                self.assertEqual(serveur.forme_logo(chemin), "hors-racine")
                self.assertEqual(serveur.valider_logo(chemin),
                                 ("", "hors-racine"))

    def test_forme_invalide(self):
        for chemin in ("https://exemple.invalid/l.png",
                       "images/l.png?x", "images/l.png#x", "images/l o.png",
                       "images/été.png", "images/l.png\n", "images/l.png\r",
                       "images/\tl.png", "images/l.png ", " images/l.png",
                       "images\\l.png", "images/l.png:flux", "images/~1.png",
                       "images/a%2e.png", "images//l.png", "images/.l.png",
                       ".l.png", "images/", "images/l\x00.png", "", " "):
            with self.subTest(chemin=chemin):
                self.assertEqual(serveur.forme_logo(chemin), "forme-invalide")

    def test_seul_images_cabinet_ou_le_defaut_sont_admis(self):
        # Constat d'audit : un logo client posé ailleurs que sous
        # images/cabinet/ serait servi, non ignoré par Git et emballé par
        # faire-paquet.sh. Les deux seuls emplacements admis sont ce dossier,
        # sur un seul niveau, et exactement le logo par défaut.
        defaut = serveur.CONFIG_DEFAUT["cabinet"]["logo"]
        for chemin in ("images/cabinet/l.png", "images/cabinet/L.JPG",
                       "images/cabinet/a_b-c.d.jpeg", defaut):
            with self.subTest(admis=chemin):
                self.assertIsNone(serveur.forme_logo(chemin))
        for chemin in ("images/logo-client.png", "images/cabinet/sous/l.png",
                       "l.png", "logo.jpg", "images/cabinet.png",
                       "images/cabinet/", "Images/cabinet/l.png",
                       "images/Cabinet/l.png", "images/cabinet/../l.png",
                       "formulaire/images/cabinet/l.png",
                       "images/favicon.png", "images/favicon2.jpeg",
                       "images/squelette_dos.png", "images/empreintes_pieds.png",
                       "x/images/cabinet/l.png"):
            with self.subTest(refuse=chemin):
                self.assertIn(serveur.forme_logo(chemin),
                              ("forme-invalide", "hors-racine"))
        # Le motif est celui de la forme, pas un nouveau.
        self.assertEqual(serveur.forme_logo("images/logo-client.png"),
                         "forme-invalide")
        self.assertEqual(serveur.forme_logo("images/cabinet/sous/l.png"),
                         "forme-invalide")
        self.assertEqual(serveur.valider_logo("images/logo-client.png"),
                         ("", "forme-invalide"))

    def test_non_chaine_est_forme_invalide(self):
        for valeur in (None, 42, ["images/l.png"], {"a": 1}, True, b"l.png"):
            with self.subTest(valeur=valeur):
                self.assertEqual(serveur.forme_logo(valeur), "forme-invalide")
                self.assertEqual(serveur.valider_logo(valeur),
                                 ("", "forme-invalide"))

    def test_extension_hors_logo(self):
        for chemin in ("images/l.svg", "index.html", "schema.json",
                       "images/l.ico", "images/l.png.exe", "images/l",
                       "images/l.gif", "style.css"):
            with self.subTest(chemin=chemin):
                self.assertEqual(serveur.forme_logo(chemin),
                                 "extension-non-servie")
                self.assertEqual(serveur.valider_logo(chemin),
                                 ("", "extension-non-servie"))

    def test_formes_admises(self):
        for chemin in ("images/favicon.jpeg", "images/cabinet/enseigne.png",
                       "images/cabinet/L.PNG"):
            with self.subTest(chemin=chemin):
                self.assertIsNone(serveur.forme_logo(chemin))

    def test_extensions_logo_incluses_dans_extensions_servies(self):
        # Le filtre du serveur n'est jamais élargi pour le logo (D9).
        self.assertTrue(serveur.EXTENSIONS_LOGO <= serveur.EXTENSIONS_SERVIES)
        self.assertEqual(set(serveur.SIGNATURES_LOGO), set(serveur.EXTENSIONS_LOGO))

    def test_aucun_acces_au_disque(self):
        # « Purement textuelle » : la fonction ne doit toucher aucune des
        # primitives du système de fichiers.
        with unittest.mock.patch.object(serveur.os, "lstat",
                                        side_effect=AssertionError("disque")), \
             unittest.mock.patch.object(serveur.os.path, "realpath",
                                        side_effect=AssertionError("disque")), \
             unittest.mock.patch.object(serveur.os.path, "islink",
                                        side_effect=AssertionError("disque")), \
             unittest.mock.patch.object(serveur.os.path, "exists",
                                        side_effect=AssertionError("disque")):
            self.assertIsNone(serveur.forme_logo("images/cabinet/l.png"))
            self.assertEqual(serveur.forme_logo("../l.png"), "hors-racine")


class ConfinementLogo(RacineTemporaire):
    """Seconde couche : le chemin résolu pour de bon. Appelée seule, sans
    forme_logo : elle ne se fie pas à la première."""

    def test_remontee_directe_est_hors_racine(self):
        # Sans passer par forme_logo : seul le confinement tient ici.
        self.assertEqual(serveur.confiner_logo("../hors.png", self.racine),
                         ("", "hors-racine"))
        self.assertEqual(
            serveur.confiner_logo("images/../../hors.png", self.racine),
            ("", "hors-racine"))

    def test_fichier_sous_la_racine_accepte(self):
        chemin = self.poser("images/cabinet/l.png")
        absolu, motif = serveur.confiner_logo("images/cabinet/l.png", self.racine)
        self.assertIsNone(motif)
        self.assertEqual(absolu, os.path.realpath(chemin))

    def test_lien_vers_l_exterieur(self):
        self.lier(self.hors, os.path.join(self.racine, "images", "cabinet", "lien.png"))
        self.assertEqual(serveur.confiner_logo("images/cabinet/lien.png", self.racine),
                         ("", "lien-symbolique"))
        self.assertEqual(serveur.valider_logo("images/cabinet/lien.png", self.racine),
                         ("", "lien-symbolique"))

    def test_lien_vers_l_interieur(self):
        reel = self.poser("images/cabinet/reel.png")
        self.lier(reel, os.path.join(self.racine, "images", "cabinet", "lien.png"))
        self.assertEqual(serveur.confiner_logo("images/cabinet/lien.png", self.racine),
                         ("", "lien-symbolique"))
        self.assertEqual(serveur.valider_logo("images/cabinet/lien.png", self.racine),
                         ("", "lien-symbolique"))

    def test_dossier_parent_lie(self):
        self.poser("reel/l.png")
        self.lier(os.path.join(self.racine, "reel"),
                  os.path.join(self.racine, "images", "cabinet", "rep"))
        self.assertEqual(
            serveur.confiner_logo("images/cabinet/rep/l.png", self.racine),
            ("", "lien-symbolique"))

    def test_dossier_parent_lie_vers_l_exterieur(self):
        self.lier(self.tmp, os.path.join(self.racine, "images", "ext"))
        self.assertEqual(serveur.confiner_logo("images/ext/hors.png", self.racine),
                         ("", "lien-symbolique"))

    def test_racine_elle_meme_atteinte_par_un_lien(self):
        # /var -> /private/var sous macOS : une racine web atteinte par un
        # lien n'est pas un logo lié, c'est le chemin habituel de la machine.
        self.poser("images/cabinet/l.png")
        acces = os.path.join(self.tmp, "acces")
        self.lier(self.racine, acces)
        absolu, motif = serveur.confiner_logo("images/cabinet/l.png", acces)
        self.assertIsNone(motif)
        self.assertEqual(
            absolu, os.path.join(os.path.realpath(self.racine),
                                 "images", "cabinet", "l.png"))
        self.assertEqual(serveur.valider_logo("images/cabinet/l.png", acces),
                         ("images/cabinet/l.png", None))

    def test_jonction_invisible_a_islink(self):
        # Une jonction Windows n'est pas vue par os.path.islink avant
        # Python 3.12 : on simule cette cécité sur un vrai lien. C'est la
        # résolution (realpath, commonpath) qui doit alors tenir.
        reel = self.poser("images/reel.png")
        self.lier(reel, os.path.join(self.racine, "images", "interne.png"))
        self.lier(self.hors, os.path.join(self.racine, "images", "externe.png"))
        with unittest.mock.patch.object(serveur.os.path, "islink",
                                        return_value=False):
            self.assertEqual(
                serveur.confiner_logo("images/interne.png", self.racine),
                ("", "lien-symbolique"))
            self.assertEqual(
                serveur.confiner_logo("images/externe.png", self.racine),
                ("", "hors-racine"))

    def test_aucune_exception_ne_sort(self):
        for erreur in (OSError("disque"), ValueError("lecteurs")):
            with self.subTest(erreur=erreur), \
                 unittest.mock.patch.object(serveur.os.path, "realpath",
                                            side_effect=erreur):
                absolu, motif = serveur.confiner_logo("images/l.png", self.racine)
                self.assertEqual(absolu, "")
                self.assertIn(motif, serveur.MOTIFS_REFUS_LOGO)

    def test_lecteurs_differents_sont_hors_racine(self):
        # commonpath lève ValueError sous Windows entre deux lecteurs.
        self.poser("images/l.png")
        with unittest.mock.patch.object(serveur.os.path, "commonpath",
                                        side_effect=ValueError("lecteurs")):
            self.assertEqual(serveur.confiner_logo("images/l.png", self.racine),
                             ("", "hors-racine"))


class CasseWindows(RacineTemporaire):
    """Une différence de casse seule n'est pas un lien (C6-T6) : le logo est
    refusé comme « absent », le motif qui dirige le support vers le nom du
    fichier, et non vers un raccourci qui n'existe pas."""

    def test_casse_seule_est_absente_et_non_lien(self):
        self.poser("images/cabinet/logo.png")
        with windows_simule():
            self.assertEqual(
                serveur.valider_logo("images/cabinet/Logo.png", self.racine),
                ("", "absent"))
            self.assertEqual(
                serveur.confiner_logo("images/cabinet/Logo.png", self.racine),
                ("", "absent"))
            # Témoin : la bonne casse reste acceptée dans la même simulation.
            self.assertEqual(
                serveur.valider_logo("images/cabinet/logo.png", self.racine),
                ("images/cabinet/logo.png", None))


class ValidationLogo(RacineTemporaire):

    def test_png_et_jpeg_valides(self):
        self.poser("images/cabinet/a.png", PNG)
        self.poser("images/cabinet/b.jpg", JPEG)
        self.poser("images/cabinet/c.jpeg", JPEG)
        self.poser("images/cabinet/D.PNG", PNG)
        for chemin in ("images/cabinet/a.png", "images/cabinet/b.jpg",
                       "images/cabinet/c.jpeg", "images/cabinet/D.PNG"):
            with self.subTest(chemin=chemin):
                # Le chemin tel que validé, avec ses « / ».
                self.assertEqual(serveur.valider_logo(chemin, self.racine),
                                 (chemin, None))

    def test_logo_hors_emplacement_refuse_meme_s_il_existe(self):
        # Un vrai PNG valide sous formulaire/ mais hors images/cabinet/ n'est
        # jamais proposé : il serait servi, non ignoré par Git, et emballé.
        self.poser("images/logo-client.png")
        self.poser("images/cabinet/sous/l.png")
        self.poser("l.png")
        for chemin in ("images/logo-client.png", "images/cabinet/sous/l.png", "l.png"):
            with self.subTest(chemin=chemin):
                self.assertEqual(serveur.valider_logo(chemin, self.racine),
                                 ("", "forme-invalide"))
        # Témoin : le même fichier, sous images/cabinet/, est accepté.
        self.poser("images/cabinet/logo-client.png")
        self.assertEqual(
            serveur.valider_logo("images/cabinet/logo-client.png", self.racine),
            ("images/cabinet/logo-client.png", None))

    def test_pas_de_logo_est_un_choix(self):
        for vide in ("", " ", "\t\n"):
            with self.subTest(vide=vide):
                self.assertEqual(serveur.valider_logo(vide, self.racine),
                                 ("", None))

    def test_absent_et_dossier(self):
        self.assertEqual(serveur.valider_logo("images/cabinet/absent.png", self.racine),
                         ("", "absent"))
        # Dossier parent absent.
        shutil.rmtree(os.path.join(self.racine, "images", "cabinet"))
        self.assertEqual(serveur.valider_logo("images/cabinet/absent.png", self.racine),
                         ("", "absent"))
        # Un dossier à la place du fichier.
        os.makedirs(os.path.join(self.racine, "images", "cabinet", "d.png"))
        self.assertEqual(serveur.valider_logo("images/cabinet/d.png", self.racine),
                         ("", "absent"))
        # Un fichier à la place du dossier : NotADirectoryError, pas une levée.
        shutil.rmtree(os.path.join(self.racine, "images", "cabinet"))
        ecrire(os.path.join(self.racine, "images", "cabinet"), PNG)
        self.assertEqual(
            serveur.valider_logo("images/cabinet/l.png", self.racine),
            ("", "absent"))

    def test_vide_est_illisible(self):
        self.poser("images/cabinet/vide.png", b"", taille=0)
        self.assertEqual(serveur.valider_logo("images/cabinet/vide.png", self.racine),
                         ("", "illisible"))

    def test_taille(self):
        limite = serveur.LOGO_TAILLE_MAX
        self.poser("images/cabinet/pile.png", PNG, limite)
        self.poser("images/cabinet/trop.png", PNG, limite + 1)
        # Exactement la limite est accepté, un octet de plus ne l'est pas.
        self.assertEqual(serveur.valider_logo("images/cabinet/pile.png", self.racine),
                         ("images/cabinet/pile.png", None))
        self.assertEqual(serveur.valider_logo("images/cabinet/trop.png", self.racine),
                         ("", "trop-volumineux"))

    def test_signature(self):
        # PNG sous une extension .jpg, et l'inverse.
        self.poser("images/cabinet/faux.jpg", PNG)
        self.poser("images/cabinet/faux.png", JPEG)
        # Un fichier renommé : du texte sous une extension d'image.
        self.poser("images/cabinet/page.png", b"<html>")
        # Trop court pour porter une signature.
        self.poser("images/cabinet/court.png", b"\x89P", taille=2)
        for chemin in ("images/cabinet/faux.jpg", "images/cabinet/faux.png",
                       "images/cabinet/page.png", "images/cabinet/court.png"):
            with self.subTest(chemin=chemin):
                self.assertEqual(serveur.valider_logo(chemin, self.racine),
                                 ("", "illisible"))

    @unittest.skipIf(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
                     "droits de lecture non restreignables ici")
    def test_illisible_sans_droit_de_lecture(self):
        chemin = self.poser("images/cabinet/ferme.png")
        os.chmod(chemin, 0)
        self.addCleanup(os.chmod, chemin, 0o600)
        self.assertEqual(serveur.valider_logo("images/cabinet/ferme.png", self.racine),
                         ("", "illisible"))

    def test_racine_par_defaut_est_formulaire(self):
        # Résolue à l'appel : les tests (et eux seuls) peuvent la substituer.
        self.poser("images/cabinet/l.png")
        with unittest.mock.patch.object(serveur, "FORMULAIRE", self.racine):
            self.assertEqual(serveur.valider_logo("images/cabinet/l.png"),
                             ("images/cabinet/l.png", None))

    def test_le_logo_par_defaut_est_valide_dans_le_depot(self):
        # Le défaut de CONFIG_DEFAUT doit passer sa propre validation, sans
        # quoi chaque cabinet démarrerait avec un avertissement.
        defaut = serveur.CONFIG_DEFAUT["cabinet"]["logo"]
        self.assertEqual(serveur.valider_logo(defaut), (defaut, None))

    def test_motifs_rendus_derives_du_code(self):
        # Les motifs que les trois fonctions peuvent rendre, relevés dans leur
        # arbre syntaxique, sont exactement le vocabulaire fermé : un motif
        # ajouté sans être déclaré (ou déclaré et jamais rendu) fait échouer.
        rendus = set()
        for fonction in (serveur.forme_logo, serveur.confiner_logo,
                         serveur.valider_logo):
            source = inspect.getsource(fonction)
            arbre = ast.parse(source)
            for noeud in ast.walk(arbre):
                if not isinstance(noeud, ast.Return) or noeud.value is None:
                    continue
                valeur = noeud.value
                candidats = valeur.elts if isinstance(valeur, ast.Tuple) else [valeur]
                for candidat in candidats:
                    if (isinstance(candidat, ast.Constant)
                            and isinstance(candidat.value, str)
                            and candidat.value):
                        rendus.add(candidat.value)
        # Les chemins rendus (« chemin », « absolu ») ne sont pas des
        # constantes ; les seules chaînes non vides sont des motifs.
        self.assertEqual(rendus, set(serveur.MOTIFS_REFUS_LOGO))


class DetailRefusLogo(unittest.TestCase):

    def test_chaque_motif_du_vocabulaire(self):
        for motif in serveur.MOTIFS_REFUS_LOGO:
            with self.subTest(motif=motif):
                self.assertEqual(serveur.detail_refus_logo(motif),
                                 "refus motif={}".format(motif))

    def test_hors_vocabulaire_devient_motif_inconnu(self):
        # Le chemin configuré, ou n'importe quelle valeur libre, ne passe
        # jamais : c'est la garantie structurelle de technique.log (D8).
        for motif in ("images/cabinet/enseigne.png", "", None, 42, "Absent"):
            with self.subTest(motif=motif):
                self.assertEqual(serveur.detail_refus_logo(motif),
                                 "refus motif=motif-inconnu")

    def test_evenement_logo_dans_le_vocabulaire_technique(self):
        self.assertIn("LOGO", serveur.EVENEMENTS_TECHNIQUES)


@unittest.skipUnless(shutil.which("git"), "git requis")
class ConventionEmplacement(unittest.TestCase):
    """formulaire/images/cabinet/ : l'emplacement d'un logo client, ignoré par
    Git (donnée identifiante, dépôt public)."""

    def ignore(self, chemin):
        return subprocess.run(
            ["git", "check-ignore", "-q", chemin], cwd=PROJET).returncode

    def test_dossier_des_logos_clients_ignore(self):
        self.assertEqual(self.ignore("formulaire/images/cabinet/x.png"), 0)

    def test_le_logo_par_defaut_n_est_pas_ignore(self):
        # Témoin : l'ignorance est propre au dossier, pas à tout formulaire/images.
        defaut = "formulaire/" + serveur.CONFIG_DEFAUT["cabinet"]["logo"]
        self.assertEqual(self.ignore(defaut), 1)


class DefautFerme(unittest.TestCase):

    def test_sans_demarrer_aucun_logo_n_est_propose(self):
        # Un attribut de classe vide : le gestionnaire échoue fermé tant que
        # demarrer() n'a pas validé un chemin.
        self.assertEqual(serveur.Gestionnaire.logo, "")


class LogoConfig(unittest.TestCase):
    """`--config` avertit quand le chemin saisi serait refusé, et écrit quand
    même : l'installateur peut poser le fichier après."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bilan-test-logo-config-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.config_json = os.path.join(self.tmp, "config.json")
        # Jamais le config.json réel du cabinet.
        patch = unittest.mock.patch.object(serveur, "CONFIG", self.config_json)
        patch.start()
        self.addCleanup(patch.stop)

    def configurer(self, logo):
        """Joue `--config` avec `logo` à l'invite du logo ; rend la sortie."""
        reponses = iter([""] + [logo if cle == "logo" else ""
                                for cle in serveur.CLES_CABINET])
        sortie = io.StringIO()
        with unittest.mock.patch("builtins.input", lambda invite: next(reponses)), \
             unittest.mock.patch.object(
                 serveur.getpass, "getpass",
                 side_effect=["motdepasse123", "motdepasse123"]), \
             contextlib.redirect_stdout(sortie):
            code = serveur.definir_mot_de_passe()
        self.assertEqual(code, 0)
        with open(self.config_json, encoding="utf-8") as f:
            return sortie.getvalue(), json.load(f)

    def test_logo_refusable_avertit_et_ecrit_quand_meme(self):
        sortie, ecrit = self.configurer("../hors.png")
        self.assertIn("AVERTISSEMENT : ce logo sera refusé au démarrage "
                      "(hors-racine)", sortie)
        self.assertIn("images/cabinet/", sortie)
        self.assertEqual(ecrit["cabinet"]["logo"], "../hors.png")
        self.assertTrue(ecrit["mot_de_passe"].startswith("pbkdf2_sha256$"))

    def test_logo_absent_avertit(self):
        sortie, ecrit = self.configurer("images/cabinet/absent-fictif.png")
        self.assertIn("(absent)", sortie)
        self.assertEqual(ecrit["cabinet"]["logo"],
                         "images/cabinet/absent-fictif.png")

    def test_logo_valide_n_avertit_pas(self):
        # Saisie vide : la valeur par défaut est conservée, et elle est valide.
        sortie, ecrit = self.configurer("")
        self.assertNotIn("AVERTISSEMENT", sortie)
        self.assertEqual(ecrit["cabinet"]["logo"],
                         serveur.CONFIG_DEFAUT["cabinet"]["logo"])


def requete(dossier, port, chemin):
    """GET authentifié d'un bac à sable : (statut, en-têtes, corps)."""
    contexte = ssl.create_default_context(
        cafile=os.path.join(dossier, "autorite.crt"))
    jeton = base64.b64encode(
        "{}:{}".format(UTILISATEUR, MOT_DE_PASSE).encode("utf-8")).decode("ascii")
    connexion = http.client.HTTPSConnection(
        "127.0.0.1", port, context=contexte, timeout=10)
    try:
        connexion.request("GET", chemin, headers={"Authorization": "Basic " + jeton})
        reponse = connexion.getresponse()
        entetes = {nom.lower(): valeur for nom, valeur in reponse.getheaders()}
        return reponse.status, entetes, reponse.read()
    finally:
        connexion.close()


def lire(dossier, nom):
    chemin = os.path.join(dossier, nom)
    if not os.path.exists(chemin):
        return ""
    with open(chemin, encoding="utf-8") as f:
        return f.read()


@unittest.skipIf(cryptography_absente(),
                 "cryptography requis pour fabriquer les certificats")
class LogoDemarrage(unittest.TestCase):
    """Un vrai serveur dans un bac à sable : validation au démarrage,
    `/cabinet`, journaux. Lecture des journaux après une réponse de
    `/cabinet` : tout ce qui s'écrit avant `serve_forever()` l'est déjà."""

    IDENTITE = {"praticien": "Dr Témoin"}

    def lancer(self, logo, avant_demarrage=None):
        cabinet = dict(self.IDENTITE)
        if logo is not None:
            cabinet["logo"] = logo
        dossier, port, processus = demarrer_sandbox_court(
            {"cabinet": cabinet}, avant_demarrage=avant_demarrage)
        self.dossier, self.port, self.processus = dossier, port, processus
        self.addCleanup(shutil.rmtree, dossier, ignore_errors=True)
        self.addCleanup(self.arreter)

    def arreter(self):
        if self.processus.poll() is None:
            self.processus.terminate()
        # communicate vide le tube et attend la fin ; appelé une seule fois.
        if not hasattr(self, "sortie"):
            self.sortie, _ = self.processus.communicate(timeout=10)

    def cabinet(self):
        statut, _, corps = requete(self.dossier, self.port, "/cabinet")
        self.assertEqual(statut, 200)
        return json.loads(corps.decode("utf-8"))

    def evenements_logo(self):
        """Les lignes LOGO des deux journaux : (journal.log, technique.log)."""
        journal = [ligne for ligne in lire(self.dossier, "journal.log").splitlines()
                   if "LOGO" in ligne]
        technique = [ligne for ligne in
                     lire(self.dossier, "technique.log").splitlines()
                     if ligne.split(" ")[1:2] == ["LOGO"]]
        return journal, technique

    def test_logo_hors_racine_refuse_partout(self):
        # Critère 10 : un fichier réel existe à l'endroit visé par la
        # remontée, à la racine du bac à sable.
        def poser_hors(dossier):
            ecrire(os.path.join(dossier, "hors.png"), PNG)

        self.lancer("../hors.png", avant_demarrage=poser_hors)
        self.assertEqual(self.cabinet()["logo"], "")

        journal, technique = self.evenements_logo()
        self.assertEqual(len(journal), 1)
        self.assertIn("LOGO refusé motif=hors-racine", journal[0])
        self.assertIn("hors.png", journal[0])
        self.assertEqual(len(technique), 1)
        self.assertTrue(technique[0].endswith(" LOGO refus motif=hors-racine"))
        # Le chemin configuré n'entre jamais dans le journal qui circule.
        self.assertNotIn("hors.png", lire(self.dossier, "technique.log"))

        self.arreter()
        self.assertIn("AVERTISSEMENT : logo refusé (hors-racine)", self.sortie)

    def test_logo_absent_refuse_sans_le_chemin_dans_technique(self):
        self.lancer("images/cabinet/enseigne-fictive.png")
        self.assertEqual(self.cabinet()["logo"], "")
        journal, technique = self.evenements_logo()
        self.assertIn("motif=absent", journal[0])
        self.assertIn("enseigne-fictive", journal[0])
        self.assertTrue(technique[0].endswith(" LOGO refus motif=absent"))
        self.assertNotIn("enseigne", lire(self.dossier, "technique.log"))
        self.assertNotIn("fictive", lire(self.dossier, "technique.log"))

    def test_chemin_hostile_n_injecte_pas_de_ligne_dans_le_journal(self):
        # Une valeur écrite à la main avec un retour à la ligne ne doit pas
        # forger une ligne du journal nominatif : !r neutralise.
        self.lancer("a.png\n2026-01-01T00:00:00 127.0.0.1 LIGNE-FORGEE")
        self.assertEqual(self.cabinet()["logo"], "")
        journal = lire(self.dossier, "journal.log").splitlines()
        concernees = [ligne for ligne in journal if "LIGNE-FORGEE" in ligne]
        self.assertEqual(len(concernees), 1)
        self.assertIn("LOGO refusé", concernees[0])
        self.assertNotIn("LIGNE-FORGEE", lire(self.dossier, "technique.log"))

    def test_logo_valide_propose_et_servi(self):
        def poser_logo(dossier):
            ecrire(os.path.join(dossier, "formulaire", "images", "cabinet",
                                "logo-fictif.png"), PNG)

        self.lancer("images/cabinet/logo-fictif.png", avant_demarrage=poser_logo)
        self.assertEqual(self.cabinet()["logo"], "images/cabinet/logo-fictif.png")
        statut, entetes, _ = requete(
            self.dossier, self.port, "/images/cabinet/logo-fictif.png")
        self.assertEqual(statut, 200)
        self.assertEqual(entetes.get("content-type"), "image/png")
        self.assertEqual(self.evenements_logo(), ([], []))
        self.arreter()
        self.assertNotIn("logo refusé", self.sortie)

    def test_pas_de_logo_n_est_pas_une_anomalie(self):
        self.lancer("")
        self.assertEqual(self.cabinet()["logo"], "")
        self.assertEqual(self.evenements_logo(), ([], []))
        self.arreter()
        self.assertNotIn("logo refusé", self.sortie)

    def test_pas_de_repli_sur_le_logo_par_defaut(self):
        # D7 : un logo refusé donne « pas de logo », jamais l'emblème par
        # défaut (qui, lui, est bien présent dans le bac à sable).
        self.lancer("images/cabinet/absent.png")
        donnees = self.cabinet()
        self.assertEqual(donnees["logo"], "")
        self.assertNotEqual(donnees["logo"],
                            serveur.CONFIG_DEFAUT["cabinet"]["logo"])

    def test_logo_par_defaut_sans_anomalie(self):
        self.lancer(None)
        self.assertEqual(self.cabinet()["logo"],
                         serveur.CONFIG_DEFAUT["cabinet"]["logo"])
        self.assertEqual(self.evenements_logo(), ([], []))


if __name__ == "__main__":
    unittest.main()
