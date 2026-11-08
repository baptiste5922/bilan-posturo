"""Le gestionnaire statique ne suit pas les liens (contrat C6-T6).

Un lien symbolique ou une jonction posés sous `formulaire/` étaient suivis, et
leur cible partait chez tout client authentifié dès que le nom du lien portait
une extension servie. Le serveur résout désormais chaque fichier statique
avant de l'ouvrir : un lien, une jonction ou une cible hors de `formulaire/`
rendent une 404 identique à celle d'un fichier absent. Une différence de casse
seule reste servie sous Windows (amendement A1) ; le logo, lui, la refuse.

  Unitaires    — confiner_fichier_servi et la tolérance de casse, sur une
                 racine temporaire (U1 à U12) ;
  Gardes AST   — le contrôle est sur le chemin de toute lecture (G1, G2) et
                 la tolérance n'a qu'un appelant (G3) ;
  Intégration  — un vrai serveur en bac à sable, liens posés avant le
                 démarrage (I1 à I9) ;
  Jonction     — de vraies jonctions NTFS, sous Windows seulement (W1, W2).

    python3 -m unittest tests.test_liens_servis
    python3 -O -m unittest tests.test_liens_servis

Bibliothèque standard seule. Pas d'`assert` nu : il s'évaporerait sous -O.
"""

import ast
import base64
import contextlib
import http.client
import inspect
import json
import os
import shutil
import ssl
import stat
import subprocess
import sys
import tempfile
import threading
import types
import unittest
import unittest.mock

DOSSIER_TESTS = os.path.dirname(os.path.abspath(__file__))
PROJET = os.path.dirname(DOSSIER_TESTS)
sys.path.insert(0, os.path.join(PROJET, "serveur"))
sys.path.insert(0, DOSSIER_TESTS)

import serveur
from test_integration import (
    MOT_DE_PASSE, UTILISATEUR, cryptography_absente, demarrer_sandbox_court)
# Une fonction et un gestionnaire de contexte : aucune classe de test, que la
# découverte rejouerait.
from test_logo import PNG, ecrire, windows_simule


def lier(testcase, cible, lien, dossier=False):
    """Crée un lien symbolique, ou saute le test (jamais vert à vide) quand le
    système ne le permet pas (Windows sans privilège)."""
    os.makedirs(os.path.dirname(lien), exist_ok=True)
    try:
        os.symlink(cible, lien, target_is_directory=dossier)
    except (OSError, NotImplementedError) as erreur:
        testcase.skipTest("lien symbolique impossible ici : {}".format(erreur))


class RacineServie(unittest.TestCase):
    """Une racine web jetable `web/` avec un fichier ordinaire et un
    `index.html`, et à côté `hors/` : la cible de tout lien externe."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bilan-test-liens-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.racine = os.path.join(self.tmp, "web")
        self.hors = os.path.join(self.tmp, "hors")
        ecrire(os.path.join(self.racine, "index.html"), b"<html>")
        ecrire(os.path.join(self.racine, "images", "ordinaire.png"), PNG)
        ecrire(os.path.join(self.hors, "cible.png"), PNG)

    def chemin(self, *morceaux):
        return os.path.join(self.racine, *morceaux)

    def juge(self, *morceaux, racine=None):
        return serveur.confiner_fichier_servi(
            os.path.join(racine or self.racine, *morceaux), racine or self.racine)


class ConfinementServi(RacineServie):
    """U1 à U8, U10, U11 : la fonction pure, sur le disque réel."""

    def test_u1_fichier_ordinaire_passe(self):
        self.assertIsNone(self.juge("images", "ordinaire.png"))
        self.assertIsNone(self.juge("index.html"))

    def test_u2_fichier_absent_laisse_la_404_de_la_bibliotheque(self):
        self.assertIsNone(self.juge("images", "inexistant.png"))
        self.assertIsNone(self.juge("dossier-absent", "x.png"))

    def test_u3_lien_vers_l_exterieur(self):
        lier(self, os.path.join(self.hors, "cible.png"),
             self.chemin("images", "externe.png"))
        self.assertEqual(self.juge("images", "externe.png"), "lien-symbolique")

    def test_u4_lien_vers_l_interieur(self):
        lier(self, self.chemin("images", "ordinaire.png"),
             self.chemin("images", "interne.png"))
        self.assertEqual(self.juge("images", "interne.png"), "lien-symbolique")

    def test_u5_dossier_parent_lie_vers_l_exterieur(self):
        lier(self, self.hors, self.chemin("ext"), dossier=True)
        self.assertEqual(self.juge("ext", "cible.png"), "lien-symbolique")

    def test_u6_lien_pendant(self):
        lier(self, os.path.join(self.tmp, "disparu.png"),
             self.chemin("images", "pendant.png"))
        self.assertEqual(self.juge("images", "pendant.png"), "lien-symbolique")

    def test_u7_racine_elle_meme_atteinte_par_un_lien(self):
        # /var -> /private/var sous macOS : une racine atteinte par un lien est
        # le chemin ordinaire de la machine, pas un détour (décision D2).
        acces = os.path.join(self.tmp, "acces")
        lier(self, self.racine, acces, dossier=True)
        self.assertIsNone(self.juge("images", "ordinaire.png", racine=acces))
        self.assertIsNone(self.juge("index.html", racine=acces))

    def test_u8_jonction_simulee_invisible_a_islink(self):
        # Une jonction n'est pas vue par islink avant Python 3.12 : on simule
        # cette cécité sur un vrai lien. La résolution doit alors tenir seule.
        lier(self, self.chemin("images", "ordinaire.png"),
             self.chemin("images", "interne.png"))
        lier(self, os.path.join(self.hors, "cible.png"),
             self.chemin("images", "externe.png"))
        with unittest.mock.patch.object(serveur.os.path, "islink",
                                        return_value=False):
            self.assertEqual(self.juge("images", "interne.png"),
                             "lien-symbolique")
            self.assertEqual(self.juge("images", "externe.png"), "hors-racine")

    def test_u10_octet_nul_dans_le_chemin_traduit(self):
        motif = self.juge("images", "x\x00.png")
        self.assertIn(motif, serveur.MOTIFS_REFUS_LOGO)

    def test_u10_l_octet_nul_est_refuse_meme_si_realpath_le_laisse_passer(self):
        # Selon la version de Python, realpath lève ou non sur un octet nul :
        # le refus ne doit pas dépendre de lui.
        with unittest.mock.patch.object(serveur.os.path, "realpath",
                                        side_effect=lambda chemin: chemin):
            self.assertEqual(self.juge("images", "x\x00.png"), "forme-invalide")

    def test_u11_aucune_exception_ne_sort(self):
        for erreur in (OSError("disque"), ValueError("lecteurs")):
            with self.subTest(erreur=erreur), \
                 unittest.mock.patch.object(serveur.os.path, "realpath",
                                            side_effect=erreur):
                self.assertIn(self.juge("images", "ordinaire.png"),
                              serveur.MOTIFS_REFUS_LOGO)

    def test_u11_relpath_qui_leve(self):
        # Lecteurs différents ou octet nul sous Windows.
        with unittest.mock.patch.object(serveur.os.path, "relpath",
                                        side_effect=ValueError("lecteurs")):
            self.assertEqual(self.juge("images", "ordinaire.png"), "hors-racine")


@contextlib.contextmanager
def lstat_truque(reconnait, faux):
    """Dans la simulation de Windows, fait répondre `faux` à lstat pour les
    chemins que `reconnait` désigne, et islink aveugle (comme avant Python 3.12
    pour une jonction). realpath, lui, voit le disque simulé : sur certaines
    versions de Python il appelle os.lstat, et un faux lien lui ferait lire un
    lien qui n'existe pas."""
    with windows_simule():
        lstat_simule = os.lstat
        realpath_simule = os.path.realpath

        def lstat_pipeau(chemin, *args, **options):
            if reconnait(chemin):
                return faux
            return lstat_simule(chemin, *args, **options)

        def realpath_protege(chemin, *args, **options):
            with unittest.mock.patch.object(serveur.os, "lstat", lstat_simule):
                return realpath_simule(chemin, *args, **options)

        with unittest.mock.patch.object(serveur.os.path, "islink",
                                        return_value=False), \
             unittest.mock.patch.object(serveur.os.path, "realpath",
                                        realpath_protege), \
             unittest.mock.patch.object(serveur.os, "lstat", lstat_pipeau):
            yield


@contextlib.contextmanager
def realpath_casse_des_parents():
    """Fait rendre à realpath la casse du disque pour chaque composante
    existante, comme Windows (le chemin absent, lui, reste tel que demandé).
    windows_simule ne corrige que la dernière composante : insuffisant pour
    un fichier absent dans un dossier écrit avec une autre casse, le cas de
    C6-T7. À ouvrir AVANT windows_simule ou lstat_truque, qui capturent le
    realpath courant."""
    realpath_reel = os.path.realpath

    def realpath_windows(chemin, *args, **options):
        reel = realpath_reel(chemin, *args, **options)
        morceaux = reel.split(os.sep)
        courant = morceaux[0] or os.sep
        for i, morceau in enumerate(morceaux[1:], start=1):
            try:
                noms = os.listdir(courant)
            except OSError:
                return os.path.join(courant, *morceaux[i:])
            trouve = next((n for n in noms if n.lower() == morceau.lower()),
                          None)
            if trouve is None:
                return os.path.join(courant, *morceaux[i:])
            courant = os.path.join(courant, trouve)
        return courant

    with unittest.mock.patch.object(serveur.os.path, "realpath",
                                    realpath_windows):
        yield


class ToleranceDeLaCasse(RacineServie):
    """U9, U9b, U9c : Windows simulé. La casse seule est servie, mais aucun
    détour ne passe par cette tolérance."""

    def test_u9_casse_seule_est_servie(self):
        with windows_simule():
            self.assertIsNone(self.juge("INDEX.HTML"))
            self.assertIsNone(self.juge("Images", "ORDINAIRE.png"))

    def test_u9b_a_lstat_voit_un_lien_que_islink_ne_voit_pas(self):
        # Reconnu par son suffixe : la racine peut être résolue ou non selon
        # la version de Python (/var -> /private/var, macOS).
        suffixe = os.sep + os.path.join("images", "ORDINAIRE.png")
        with lstat_truque(
                lambda chemin: chemin.endswith(suffixe),
                types.SimpleNamespace(st_mode=stat.S_IFLNK | 0o777)):
            self.assertEqual(self.juge("images", "ORDINAIRE.png"),
                             "lien-symbolique")

    def test_u9b_b_point_de_reparse_sur_un_dossier_parent(self):
        with lstat_truque(
                lambda chemin: os.path.basename(chemin) == "images",
                types.SimpleNamespace(
                    st_mode=stat.S_IFDIR | 0o777,
                    st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)):
            self.assertEqual(self.juge("images", "ORDINAIRE.png"),
                             "lien-symbolique")

    def test_u9b_c_resolution_vers_un_dossier_hors_racine(self):
        # Le dossier résolu porte le nom attendu à la casse près (WEB pour
        # web), mais sous un autre parent : il est hors de la racine, et
        # commonpath tranche avant la tolérance.
        base = os.path.realpath(self.racine)
        autre = os.path.join(os.path.dirname(base) + "-ailleurs", "WEB")

        with windows_simule():
            realpath_simule = os.path.realpath

            def realpath_dehors(chemin, *args, **options):
                reel = realpath_simule(chemin, *args, **options)
                if reel == base:
                    return reel
                return os.path.join(autre, os.path.relpath(reel, base))

            with unittest.mock.patch.object(serveur.os.path, "realpath",
                                            realpath_dehors):
                self.assertEqual(self.juge("images", "ordinaire.png"),
                                 "hors-racine")

    def test_u13a_fichier_absent_dans_un_dossier_d_une_autre_casse(self):
        # Windows : realpath rend la casse du disque pour les dossiers
        # existants, pas pour le fichier absent. reel et attendu diffèrent
        # donc par la casse, et la boucle lstat atteignait le fichier absent :
        # « illisible » au journal, au lieu de la 404 ordinaire (C6-T7).
        with realpath_casse_des_parents(), windows_simule():
            self.assertIsNone(self.juge("Images", "absent.png"))
            # Témoin : le fichier présent, lui, reste servi.
            self.assertIsNone(self.juge("Images", "ORDINAIRE.png"))

    def test_u13b_parent_en_point_de_reparse_reste_refuse_si_le_fichier_est_absent(self):
        # `continue` et non `return` : le fichier absent est passé, mais son
        # parent, une jonction que islink ne voit pas, est encore examiné.
        with realpath_casse_des_parents(), lstat_truque(
                lambda chemin: os.path.basename(chemin).lower() == "images",
                types.SimpleNamespace(
                    st_mode=stat.S_IFDIR | 0o777,
                    st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)):
            self.assertEqual(self.juge("Images", "absent.png"),
                             "lien-symbolique")

    def test_u9c_le_logo_garde_le_refus(self):
        # Même simulation que U9 : le logo, lui, ne tolère pas la casse.
        with windows_simule():
            self.assertEqual(
                serveur.confiner_logo("images/ORDINAIRE.png", self.racine),
                ("", "absent"))

    def test_u9_le_defaut_est_le_refus(self):
        with windows_simule():
            self.assertEqual(
                serveur.confiner_sous_racine("INDEX.HTML", self.racine),
                ("", "absent"))
            self.assertEqual(
                serveur.confiner_sous_racine("INDEX.HTML", self.racine,
                                             tolerer_casse=True)[1], None)


class FichiersSuivis(unittest.TestCase):
    """U12 : ce que le dépôt sert aujourd'hui reste servi."""

    def test_u12_tout_fichier_suivi_servi_passe(self):
        sortie = subprocess.run(
            ["git", "ls-files", "-z", "formulaire"], cwd=PROJET,
            capture_output=True, check=True)
        noms = [n.decode("utf-8") for n in sortie.stdout.split(b"\0") if n]
        vus = 0
        for nom in noms:
            extension = os.path.splitext(nom)[1].lower()
            if extension not in serveur.EXTENSIONS_SERVIES:
                continue
            chemin = os.path.join(PROJET, *nom.split("/"))
            if not os.path.isfile(chemin):
                continue
            vus += 1
            with self.subTest(fichier=nom):
                self.assertIsNone(
                    serveur.confiner_fichier_servi(chemin, serveur.FORMULAIRE))
        # Ancrage : une liste vide rendrait la boucle verte à vide.
        self.assertGreaterEqual(vus, 10)


# --------------------------------------------------------------------------
# Gardes dérivées de l'arbre syntaxique
# --------------------------------------------------------------------------

def arbre_serveur():
    with open(os.path.join(PROJET, "serveur", "serveur.py"), encoding="utf-8") as f:
        return ast.parse(f.read())


def fonction(arbre, nom, classe=None):
    """La définition `nom` du module, ou de la classe `classe`."""
    portee = arbre.body
    if classe is not None:
        portee = next(n.body for n in arbre.body
                      if isinstance(n, ast.ClassDef) and n.name == classe)
    return next(n for n in portee
                if isinstance(n, ast.FunctionDef) and n.name == nom)


def parents(arbre):
    table = {}
    for noeud in ast.walk(arbre):
        for enfant in ast.iter_child_nodes(noeud):
            table[enfant] = noeud
    return table


def est_appel_de(noeud, objet, methode):
    """Vrai pour `objet.methode(...)`, `objet` étant un nom simple."""
    return (isinstance(noeud, ast.Call)
            and isinstance(noeud.func, ast.Attribute)
            and noeud.func.attr == methode
            and isinstance(noeud.func.value, ast.Name)
            and noeud.func.value.id == objet)


def est_super_de(noeud, methode):
    """Vrai pour `super().methode(...)`."""
    return (isinstance(noeud, ast.Call)
            and isinstance(noeud.func, ast.Attribute)
            and noeud.func.attr == methode
            and isinstance(noeud.func.value, ast.Call)
            and isinstance(noeud.func.value.func, ast.Name)
            and noeud.func.value.func.id == "super")


class GardesStructurelles(unittest.TestCase):

    def test_g1_toute_lecture_passe_par_autorise_lecture(self):
        arbre = arbre_serveur()
        for methode in ("do_GET", "do_HEAD"):
            with self.subTest(methode=methode):
                definition = fonction(arbre, methode, "Gestionnaire")
                table = parents(definition)
                appels = [n for n in ast.walk(definition)
                          if est_super_de(n, methode)]
                # Ancrage : un appel super() et un seul par méthode.
                self.assertEqual(len(appels), 1)
                noeud = appels[0]
                gardes = []
                while noeud is not definition:
                    pere = table[noeud]
                    if (isinstance(pere, ast.If) and noeud in pere.body
                            and est_appel_de(pere.test, "self", "autorise_lecture")):
                        gardes.append(pere)
                    noeud = pere
                self.assertEqual(len(gardes), 1)

    def test_g2_une_seule_forme_du_chemin_et_chaque_etape_a_sa_place(self):
        # C6-T5 : le filtre d'extension et l'ouverture portent sur une seule
        # chaîne, le chemin traduit que send_head ouvrira. Chaque ancrage est
        # « trouvé exactement une fois » : une garde qui ne trouve rien ne
        # garde rien.
        definition = fonction(arbre_serveur(), "autorise_lecture", "Gestionnaire")
        corps = definition.body

        def niveau(noeud):
            """Indice, dans le corps, de l'instruction qui contient noeud."""
            trouves = [i for i, instruction in enumerate(corps)
                       if any(n is noeud for n in ast.walk(instruction))]
            self.assertEqual(len(trouves), 1)
            return trouves[0]

        def appels(predicat):
            return [n for n in ast.walk(definition) if predicat(n)]

        def appelle(nom):
            return lambda n: (isinstance(n, ast.Call)
                              and isinstance(n.func, ast.Name)
                              and n.func.id == nom)

        def appelle_attribut(attribut):
            return lambda n: (isinstance(n, ast.Call)
                              and isinstance(n.func, ast.Attribute)
                              and n.func.attr == attribut)

        # L'authentification : un seul appel, dans le test d'un « if » du
        # premier niveau.
        authentifie = appels(lambda n: est_appel_de(n, "self", "authentifie"))
        self.assertEqual(len(authentifie), 1)
        garde_auth = corps[niveau(authentifie[0])]
        self.assertIsInstance(garde_auth, ast.If)
        self.assertTrue(any(n is authentifie[0] for n in ast.walk(garde_auth.test)))

        # Le 400 d'un chemin non absolu : un « if » du premier niveau dont le
        # test cherche la barre initiale, et dont le corps répond 400.
        erreurs_400 = appels(lambda n: est_appel_de(n, "self", "send_error")
                             and n.args
                             and isinstance(n.args[0], ast.Attribute)
                             and n.args[0].attr == "BAD_REQUEST")
        self.assertEqual(len(erreurs_400), 1)
        garde_400 = corps[niveau(erreurs_400[0])]
        self.assertIsInstance(garde_400, ast.If)
        self.assertTrue(any(
            appelle_attribut("startswith")(n) and n.args
            and isinstance(n.args[0], ast.Constant) and n.args[0].value == "/"
            for n in ast.walk(garde_400.test)))
        self.assertIsInstance(garde_400.body[-1], ast.Return)

        # La forme unique : « fichier » est affecté une fois, au premier
        # niveau, depuis self.translate_path(<nom>).
        affectations = [n for n in ast.walk(definition)
                        if isinstance(n, ast.Assign)
                        and any(isinstance(c, ast.Name) and c.id == "fichier"
                                for c in n.targets)]
        self.assertEqual(len(affectations), 1)
        traduction = affectations[0]
        self.assertIn(traduction, corps)
        self.assertTrue(est_appel_de(traduction.value, "self", "translate_path"))
        self.assertEqual(len(traduction.value.args), 1)
        nom_traduit = traduction.value.args[0]
        self.assertIsInstance(nom_traduit, ast.Name)
        self.assertEqual(len(appels(appelle_attribut("translate_path"))), 1)

        # Le filtre d'extension et le confinement lisent ce même « fichier ».
        extensions = appels(appelle_attribut("splitext"))
        controles = appels(appelle("confiner_fichier_servi"))
        self.assertEqual(len(extensions), 1)
        self.assertEqual(len(controles), 1)
        for appel in extensions + controles:
            self.assertTrue(appel.args)
            self.assertIsInstance(appel.args[0], ast.Name)
            self.assertEqual(appel.args[0].id, "fichier")
            # Au premier niveau : une affectation, qu'aucune branche ne saute.
            self.assertIsInstance(corps[niveau(appel)], ast.Assign)

        # Le chemin affecté à self.path est celui qui a été traduit.
        chemins = [n for n in ast.walk(definition)
                   if isinstance(n, ast.Assign)
                   and any(isinstance(c, ast.Attribute) and c.attr == "path"
                           and isinstance(c.value, ast.Name) and c.value.id == "self"
                           for c in n.targets)]
        self.assertEqual(len(chemins), 1)
        self.assertIn(chemins[0], corps)
        self.assertIsInstance(chemins[0].value, ast.Name)
        self.assertEqual(chemins[0].value.id, nom_traduit.id)

        retours_vrai = [i for i, n in enumerate(corps)
                        if isinstance(n, ast.Return)
                        and isinstance(n.value, ast.Constant)
                        and n.value.value is True]
        self.assertEqual(len(retours_vrai), 1)

        ordre = [niveau(authentifie[0]), niveau(erreurs_400[0]),
                 niveau(traduction), niveau(extensions[0]),
                 niveau(controles[0]), niveau(chemins[0]), retours_vrai[0]]
        self.assertEqual(ordre, sorted(set(ordre)),
                         "authentifie < 400 < translate_path < splitext < "
                         "confiner_fichier_servi < self.path < return True")

    def test_g3_la_tolerance_de_casse_n_a_qu_un_appelant(self):
        arbre = arbre_serveur()
        table = parents(arbre)
        a_true = []
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            for mot in noeud.keywords:
                if (mot.arg == "tolerer_casse"
                        and not (isinstance(mot.value, ast.Constant)
                                 and mot.value.value is False)):
                    a_true.append(noeud)
            # Passé en position : un contournement de la garde par mot-clé.
            if (isinstance(noeud.func, ast.Name)
                    and noeud.func.id in ("confiner_sous_racine", "confiner_logo")):
                self.assertLessEqual(len(noeud.args), 2, ast.dump(noeud))
        # Ancrage : l'appel est trouvé, une fois.
        self.assertEqual(len(a_true), 1)
        appel = a_true[0]
        self.assertTrue(isinstance(appel.func, ast.Name)
                        and appel.func.id == "confiner_sous_racine")
        self.assertTrue(any(mot.arg == "tolerer_casse"
                            and isinstance(mot.value, ast.Constant)
                            and mot.value.value is True
                            for mot in appel.keywords))
        noeud = appel
        while not isinstance(noeud, ast.FunctionDef):
            noeud = table[noeud]
        self.assertEqual(noeud.name, "confiner_fichier_servi")

        # Le défaut de la fonction partagée est la constante False.
        definition = fonction(arbre, "confiner_sous_racine")
        noms = [a.arg for a in definition.args.args]
        self.assertEqual(noms, ["chemin", "racine_web", "tolerer_casse"])
        defaut = definition.args.defaults[-1]
        self.assertTrue(isinstance(defaut, ast.Constant) and defaut.value is False)

    def test_g3_valider_logo_appelle_avec_deux_arguments(self):
        definition = fonction(arbre_serveur(), "valider_logo")
        appels = [n for n in ast.walk(definition)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id == "confiner_logo"]
        self.assertEqual(len(appels), 1)
        self.assertEqual(len(appels[0].args), 2)
        self.assertEqual(appels[0].keywords, [])

    def test_alias_est_le_meme_objet(self):
        self.assertIs(serveur.confiner_logo, serveur.confiner_sous_racine)
        # Le test des motifs de test_logo lit confiner_logo par getsource.
        self.assertIn("def confiner_sous_racine", inspect.getsource(serveur.confiner_logo))


# --------------------------------------------------------------------------
# Intégration : un vrai serveur, des liens posés avant le démarrage
# --------------------------------------------------------------------------

def requete(dossier, port, chemin, methode="GET", authentifie=True):
    """(statut, en-têtes, corps) d'une requête sur un bac à sable."""
    contexte = ssl.create_default_context(
        cafile=os.path.join(dossier, "autorite.crt"))
    en_tetes = {}
    if authentifie:
        jeton = base64.b64encode(
            "{}:{}".format(UTILISATEUR, MOT_DE_PASSE).encode("utf-8")).decode("ascii")
        en_tetes["Authorization"] = "Basic " + jeton
    connexion = http.client.HTTPSConnection(
        "127.0.0.1", port, context=contexte, timeout=10)
    try:
        connexion.request(methode, chemin, headers=en_tetes)
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


def sans_horodatage(lignes):
    """Les lignes d'un journal technique privées de leur premier mot."""
    return [ligne.split(" ", 1)[1] for ligne in lignes]


@unittest.skipIf(cryptography_absente(),
                 "cryptography requis pour fabriquer les certificats")
class LiensServis(unittest.TestCase):
    """Un serveur réel, démarré une fois pour la classe, avec trois liens :
    vers `config.json` (relatif), vers un fichier interne, et un dossier lié
    vers la racine du bac à sable."""

    @classmethod
    def setUpClass(cls):
        etat = {}

        def poser_liens(dossier):
            etat["dossier"] = dossier
            formulaire = os.path.join(dossier, "formulaire")
            try:
                os.symlink(os.path.join("..", "..", "config.json"),
                           os.path.join(formulaire, "images", "fuite.png"))
                os.symlink("favicon.jpeg",
                           os.path.join(formulaire, "images", "interne.jpeg"))
                os.symlink(dossier, os.path.join(formulaire, "ext"),
                           target_is_directory=True)
            except (OSError, NotImplementedError) as erreur:
                raise unittest.SkipTest(
                    "lien symbolique impossible ici : {}".format(erreur))

        try:
            cls.dossier, cls.port, cls.processus = demarrer_sandbox_court(
                avant_demarrage=poser_liens)
        except BaseException:
            # Un bac créé mais jamais démarré (lien refusé) : on le retire.
            if "dossier" in etat:
                shutil.rmtree(etat["dossier"], ignore_errors=True)
            raise
        # Le tube doit être vidé EN CONTINU : sous Windows son tampon est
        # petit, et un tube jamais lu fige toute requête qui journalise
        # (C7-T5). Le fil garde la sortie, à lire au débogage d'un échec.
        cls.sortie_serveur = []
        cls.lecteur = threading.Thread(
            target=lambda: cls.sortie_serveur.extend(
                iter(cls.processus.stdout.readline, "")),
            daemon=True)
        cls.lecteur.start()

    @classmethod
    def tearDownClass(cls):
        cls.processus.terminate()
        cls.processus.wait(timeout=10)
        cls.lecteur.join(timeout=5)
        cls.processus.stdout.close()
        shutil.rmtree(cls.dossier, ignore_errors=True)

    def demander(self, chemin, **options):
        return requete(self.dossier, self.port, chemin, **options)

    def empreinte(self):
        with open(os.path.join(self.dossier, "config.json"), encoding="utf-8") as f:
            return json.load(f)["mot_de_passe"]

    def test_i1_le_lien_vers_config_rend_la_meme_404_qu_un_absent(self):
        statut, entetes, corps = self.demander("/images/fuite.png")
        statut_abs, entetes_abs, corps_abs = self.demander("/images/inexistant.png")
        self.assertEqual(statut_abs, 404)   # témoin : l'absent est bien une 404
        self.assertEqual(statut, 404)
        self.assertEqual(entetes["content-type"], entetes_abs["content-type"])
        self.assertEqual(corps, corps_abs)
        self.assertNotIn(b"mot_de_passe", corps)
        self.assertNotIn(self.empreinte().encode("utf-8"), corps)
        statut_tete, _, corps_tete = self.demander("/images/fuite.png",
                                                   methode="HEAD")
        self.assertEqual(statut_tete, 404)
        self.assertEqual(corps_tete, b"")

    def test_i2_lien_interne_refuse(self):
        self.assertEqual(self.demander("/images/interne.jpeg")[0], 404)

    def test_i3_dossier_lie_vers_l_exterieur_refuse(self):
        statut, _, corps = self.demander("/ext/config.json")
        self.assertEqual(statut, 404)
        self.assertNotIn(b"mot_de_passe", corps)

    def test_i4_nom_du_lien_encode_refuse(self):
        statut, _, corps = self.demander("/images/fu%69te.png")
        self.assertEqual(statut, 404)
        self.assertNotIn(b"mot_de_passe", corps)

    def test_i5_le_service_ordinaire_est_intact(self):
        statut, _, corps = self.demander("/")
        self.assertEqual(statut, 200)
        self.assertGreater(len(corps), 0)
        self.assertEqual(self.demander("/images/favicon.jpeg")[0], 200)
        self.assertEqual(self.demander("/images/favicon.jpeg", methode="HEAD")[0], 200)

    def test_i6_sans_identifiants_401_et_corps_vide(self):
        statut, _, corps = self.demander("/images/fuite.png", authentifie=False)
        self.assertEqual(statut, 401)
        self.assertEqual(corps, b"")

    def test_i7_journaux(self):
        technique_avant = lire(self.dossier, "technique.log")
        self.demander("/images/fuite.png")
        technique_lien = lire(self.dossier, "technique.log")
        self.demander("/images/inexistant.png")
        technique_absent = lire(self.dossier, "technique.log")

        journal = lire(self.dossier, "journal.log")
        self.assertIn("lecture refusée motif=lien-symbolique", journal)
        self.assertIn("fuite.png", journal)

        for interdit in ("fuite", "ext/", "lecture refusée"):
            self.assertNotIn(interdit, technique_absent)

        ajoutees_lien = technique_lien[len(technique_avant):].splitlines()
        ajoutees_absent = technique_absent[len(technique_lien):].splitlines()
        # Ancrage : la requête a bien écrit quelque chose.
        self.assertGreater(len(ajoutees_lien), 0)
        self.assertEqual(sans_horodatage(ajoutees_lien),
                         sans_horodatage(ajoutees_absent))

    def test_i10_octet_nul_encode_rend_404_et_non_une_connexion_fermee(self):
        # Effet de bord assumé (R4) : /x%00.json fermait la connexion sans
        # réponse. C6-T5 a unifié le calcul de l'extension et de l'ouverture
        # (tests/test_requetes_malformees.py) ; la 404 reste celle d'un absent.
        for chemin in ("/images/x%00.json", "/images/x%00.png", "/x%00.html"):
            with self.subTest(chemin=chemin):
                self.assertEqual(self.demander(chemin)[0], 404)

    @unittest.skipUnless(os.name == "nt", "casse insensible : Windows seulement")
    def test_i9_la_casse_seule_reste_servie_sous_windows(self):
        statut, _, corps = self.demander("/INDEX.HTML")
        statut_ref, _, corps_ref = self.demander("/index.html")
        self.assertEqual(statut_ref, 200)
        self.assertEqual(statut, 200)
        self.assertEqual(corps, corps_ref)


# --------------------------------------------------------------------------
# Vraies jonctions NTFS
# --------------------------------------------------------------------------

@unittest.skipUnless(os.name == "nt", "jonction NTFS : Windows seulement")
class JonctionsReelles(RacineServie):

    def jonction(self, lien, cible):
        os.makedirs(os.path.dirname(lien), exist_ok=True)
        sortie = subprocess.run(
            ["cmd", "/c", "mklink", "/J", lien, cible],
            capture_output=True, text=True)
        self.assertEqual(sortie.returncode, 0, sortie.stdout + sortie.stderr)

    def test_w1_jonction_interne_et_externe_refusees(self):
        ecrire(self.chemin("reel", "a.png"), PNG)
        self.jonction(self.chemin("interne"), self.chemin("reel"))
        self.jonction(self.chemin("externe"), self.hors)
        # Témoin : le dossier réel, lui, est servi.
        self.assertIsNone(self.juge("reel", "a.png"))
        self.assertEqual(self.juge("interne", "a.png"), "lien-symbolique")
        self.assertEqual(self.juge("externe", "cible.png"), "hors-racine")
        # Aucun chemin n'est rendu : le contenu de la cible n'est jamais proposé.
        self.assertEqual(
            serveur.confiner_sous_racine("externe/cible.png", self.racine),
            ("", "hors-racine"))
        self.assertEqual(
            serveur.confiner_sous_racine("interne/a.png", self.racine),
            ("", "lien-symbolique"))

    def test_w1_la_jonction_porte_le_point_de_reparse(self):
        # Ce que la tolérance de casse relit par lstat : la jonction doit bien
        # y apparaître comme un point de reparse.
        self.jonction(self.chemin("externe"), self.hors)
        infos = os.lstat(self.chemin("externe"))
        self.assertTrue(
            getattr(infos, "st_file_attributes", 0)
            & stat.FILE_ATTRIBUTE_REPARSE_POINT)

    def test_w2_casse_reelle_servie_et_jonction_en_casse_refusee(self):
        ecrire(self.chemin("images", "Logo.png"), PNG)
        self.assertIsNone(self.juge("images", "LOGO.PNG"))
        ecrire(self.chemin("reel", "a.png"), PNG)
        self.jonction(self.chemin("interne"), self.chemin("reel"))
        self.assertEqual(self.juge("INTERNE", "A.PNG"), "lien-symbolique")


if __name__ == "__main__":
    unittest.main()
