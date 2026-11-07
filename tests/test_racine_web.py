"""La racine web ne contient jamais la racine du cabinet (contrat C6-T7).

D2 de C6-T6 accepte une racine web atteinte par un lien : indispensable sous
macOS (/var) et sous une jonction. Mais un `formulaire` lié à la racine du
cabinet englobait `config.json`, servi en 200 faute de toute barrière sauf le
filtre d'extensions. Le serveur refuse désormais de démarrer quand la racine
web résolue contient la racine du cabinet, ou le dossier des bilans.

  Unitaires    — motif_refus_racine_web sur des arborescences temporaires
                 (U1 à U8) et signaler_refus_racine_web ;
  Gardes AST   — vocabulaire fermé, ordre des opérations de demarrer()
                 (G1, G2) ;
  Intégration  — un vrai serveur en bac à sable dont `formulaire` est lié
                 (I1 à I3, I6) ;
  Jonction     — une vraie jonction NTFS, sous Windows seulement (W1).

    python3 -m unittest tests.test_racine_web
    python3 -O -m unittest tests.test_racine_web

Bibliothèque standard seule. Pas d'`assert` nu : il s'évaporerait sous -O.
"""

import ast
import contextlib
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import types
import unicodedata
import unittest
import unittest.mock

DOSSIER_TESTS = os.path.dirname(os.path.abspath(__file__))
PROJET = os.path.dirname(DOSSIER_TESTS)
sys.path.insert(0, os.path.join(PROJET, "serveur"))
sys.path.insert(0, DOSSIER_TESTS)

import serveur
import test_integration
from test_integration import (
    cryptography_absente, demarrer_sandbox_court, preparer_sandbox)
from test_liens_servis import lier, lire, requete
from test_logo import windows_simule


# --------------------------------------------------------------------------
# Unitaires : la fonction pure
# --------------------------------------------------------------------------

class Arborescence(unittest.TestCase):
    """Un cabinet jetable `tmp/cab/` avec son `formulaire/` ordinaire, et à
    côté un dossier `tmp/ailleurs/`."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bilan-test-racine-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.cabinet = os.path.join(self.tmp, "cab")
        self.web = os.path.join(self.cabinet, "formulaire")
        self.bilans = os.path.join(self.cabinet, "bilans")
        self.ailleurs = os.path.join(self.tmp, "ailleurs")
        for dossier in (self.web, self.bilans, self.ailleurs):
            os.makedirs(dossier)

    def motif(self, web=None, cabinet=None, bilans=None):
        return serveur.motif_refus_racine_web(
            web or self.web, cabinet or self.cabinet, bilans or self.bilans)

    def remplacer_web_par_un_lien(self, cible):
        """Remplace `formulaire` par un lien vers `cible` (texte du lien)."""
        shutil.rmtree(self.web)
        lier(self, cible, self.web, dossier=True)


class MotifRefusRacineWeb(Arborescence):

    def test_u1_temoin_le_depot_reel_n_est_pas_refuse(self):
        self.assertIsNone(serveur.motif_refus_racine_web(
            serveur.FORMULAIRE, serveur.RACINE,
            os.path.join(serveur.RACINE, "bilans")))

    def test_u1_temoin_une_arborescence_ordinaire(self):
        self.assertIsNone(self.motif())

    def test_u2_web_lie_au_cabinet_par_un_lien_absolu(self):
        self.remplacer_web_par_un_lien(self.cabinet)
        self.assertEqual(self.motif(), "racine-cabinet")

    def test_u2_web_lie_au_cabinet_par_un_lien_relatif_point(self):
        # Le lien « . » : le cas que le contrat nomme, sans aucun chemin
        # absolu dans le lien.
        self.remplacer_web_par_un_lien(os.curdir)
        self.assertEqual(self.motif(), "racine-cabinet")

    def test_u3_web_lie_a_un_ancetre_du_cabinet(self):
        self.remplacer_web_par_un_lien(self.tmp)
        self.assertEqual(self.motif(), "racine-cabinet")

    def test_u4_racine_non_resolue_d_un_seul_cote(self):
        # Le cabinet est atteint par `acces`, un lien vers `reel`. Ne pas
        # partir de os.getcwd(), déjà résolu sous macOS : le test ne mordrait
        # sur aucune des deux résolutions.
        reel = os.path.join(self.tmp, "reel")
        acces = os.path.join(self.tmp, "acces")
        os.makedirs(os.path.join(reel, "cab", "formulaire"))
        lier(self, reel, acces, dossier=True)
        cabinet_non_resolu = os.path.join(acces, "cab")
        cabinet_resolu = os.path.join(reel, "cab")
        # La racine web, formulaire, est un lien vers le cabinet résolu.
        web = os.path.join(cabinet_resolu, "formulaire")
        shutil.rmtree(web)
        lier(self, cabinet_resolu, web, dossier=True)
        bilans = os.path.join(cabinet_resolu, "bilans")

        with self.subTest(cote="cabinet non résolu"):
            self.assertEqual(
                serveur.motif_refus_racine_web(
                    web, cabinet_non_resolu, bilans),
                "racine-cabinet")
        with self.subTest(cote="racine web non résolue"):
            self.assertEqual(
                serveur.motif_refus_racine_web(
                    os.path.join(cabinet_non_resolu, "formulaire"),
                    cabinet_resolu, bilans),
                "racine-cabinet")

    def test_u5_dossier_des_bilans_sous_la_racine_web(self):
        shutil.rmtree(self.bilans)
        # Inexistants au moment du contrôle : realpath ne doit pas lever.
        formes = {
            "absolu": os.path.join(self.web, "bilans"),
            "relatif joint comme demarrer()":
                os.path.join(self.cabinet, "formulaire/bilans"),
            "avec détour": os.path.join(self.web, "x", "..", "bilans"),
            "profond": os.path.join(self.web, "a", "b", "c"),
        }
        for nom, chemin in formes.items():
            with self.subTest(forme=nom):
                self.assertFalse(os.path.exists(chemin))
                self.assertEqual(self.motif(bilans=chemin), "dossier-pdf")

    def test_u5_dossier_des_bilans_atteint_par_un_lien(self):
        lier(self, self.web, os.path.join(self.ailleurs, "sortie"), dossier=True)
        self.assertEqual(
            self.motif(bilans=os.path.join(self.ailleurs, "sortie", "b")),
            "dossier-pdf")

    def test_u5_dossier_des_bilans_hors_de_la_racine_web(self):
        self.assertIsNone(self.motif(
            bilans=os.path.join(self.ailleurs, "bilans")))

    def test_u5_la_racine_du_cabinet_l_emporte_sur_les_bilans(self):
        # Quand formulaire englobe le cabinet, il englobe aussi bilans : le
        # motif le plus général gagne.
        self.remplacer_web_par_un_lien(self.cabinet)
        self.assertEqual(self.motif(), "racine-cabinet")

    def test_u6_voisin_par_prefixe_de_chaine(self):
        # /cab-x commence par /cab : une comparaison de chaînes refuserait.
        # C'est la racine web qui est le préfixe de chaîne, jamais l'inverse :
        # seul ce sens mord un startswith.
        voisin_cabinet = os.path.join(self.tmp, "cab-x")
        os.makedirs(os.path.join(voisin_cabinet, "bilans"))
        self.assertIsNone(self.motif(
            web=self.cabinet, cabinet=voisin_cabinet,
            bilans=os.path.join(voisin_cabinet, "bilans")))
        # Le sens du contrat, gardé : web = cab-web, cabinet = cab.
        voisin_web = os.path.join(self.tmp, "cab-web")
        os.makedirs(voisin_web)
        self.assertIsNone(self.motif(web=voisin_web))
        # Même piège pour le dossier des bilans.
        voisin_bilans = os.path.join(self.web + "-x", "bilans")
        os.makedirs(voisin_bilans)
        self.assertIsNone(self.motif(bilans=voisin_bilans))

    def test_u7_windows_la_casse_est_ignoree(self):
        # normcase est l'identité sous POSIX et str.lower sous Windows
        # (windows_simule). Le cabinet est donné avec un parent d'une autre
        # casse, que realpath ne corrige pas pour un chemin absent.
        sous_cabinet = os.path.join(self.tmp, "CAB", "formulaire")
        with windows_simule():
            self.assertEqual(
                serveur.motif_refus_racine_web(
                    self.cabinet, sous_cabinet, self.bilans),
                "racine-cabinet")
            self.assertEqual(
                serveur.motif_refus_racine_web(
                    self.cabinet, os.path.join(self.tmp, "CAB"), self.bilans),
                "racine-cabinet")
            # Témoin : une vraie différence de nom n'est pas gommée.
            self.assertIsNone(
                serveur.motif_refus_racine_web(
                    os.path.join(self.tmp, "CAB-WEB"), self.cabinet,
                    self.bilans))

    def test_u8_realpath_qui_leve_echoue_ferme(self):
        for erreur in (OSError("disque"), ValueError("octet nul")):
            with self.subTest(erreur=erreur), \
                 unittest.mock.patch.object(serveur.os.path, "realpath",
                                            side_effect=erreur):
                self.assertEqual(self.motif(), "indetermine")

    def test_u8_commonpath_qui_leve_vaut_ne_contient_pas(self):
        # Lecteurs différents sous Windows, ou chemin UNC contre C: .
        with unittest.mock.patch.object(serveur.os.path, "commonpath",
                                        side_effect=ValueError("lecteurs")):
            self.assertIsNone(self.motif())


class FormesUnicode(Arborescence):
    """Sous macOS, deux écritures (NFC, NFD) d'un même nom désignent le même
    dossier, et realpath rend chacune telle qu'écrite. Ailleurs, le système de
    fichiers les distingue : le test reste valable, car la normalisation ne
    peut que confondre deux noms, donc refuser (échec fermé)."""

    NOM_NFC = unicodedata.normalize("NFC", "cabinet-caf\u00e9")
    NOM_NFD = unicodedata.normalize("NFD", NOM_NFC)

    def setUp(self):
        super().setUp()
        self.assertNotEqual(self.NOM_NFC, self.NOM_NFD)   # ancrage

    def creer(self, *morceaux):
        chemin = os.path.join(self.tmp, *morceaux)
        try:
            os.makedirs(chemin)
        except OSError as erreur:
            self.skipTest("nom accentué impossible ici : {}".format(erreur))
        return chemin

    def test_u9_cabinet_en_nfd_racine_web_liee_en_nfc(self):
        cabinet = self.creer(self.NOM_NFD)
        web = os.path.join(cabinet, "formulaire")
        # Le texte du lien est en NFC, le dossier du cabinet est stocké en NFD.
        lier(self, os.path.join(self.tmp, self.NOM_NFC), web, dossier=True)
        self.assertEqual(
            serveur.motif_refus_racine_web(
                web, cabinet, os.path.join(cabinet, "bilans")),
            "racine-cabinet")

    def test_u9_dossier_des_bilans_ecrit_en_nfd_sous_une_racine_web_en_nfc(self):
        web = self.creer(self.NOM_NFC)
        bilans = os.path.join(self.tmp, self.NOM_NFD, "bilans")
        self.assertEqual(
            serveur.motif_refus_racine_web(web, self.cabinet, bilans),
            "dossier-pdf")

    def test_u9_temoin_deux_noms_vraiment_differents_ne_sont_pas_confondus(self):
        web = self.creer(self.NOM_NFC)
        autre = unicodedata.normalize("NFD", self.NOM_NFC + "-autre")
        self.assertIsNone(serveur.motif_refus_racine_web(
            web, self.cabinet, os.path.join(self.tmp, autre, "bilans")))


# --------------------------------------------------------------------------
# Journaux et console du refus
# --------------------------------------------------------------------------

class SignalementDuRefus(Arborescence):

    def setUp(self):
        super().setUp()
        self.journal = os.path.join(self.tmp, "journal.log")
        self.technique = os.path.join(self.tmp, "technique.log")
        for nom, valeur in (("JOURNAL", self.journal),
                            ("TECHNIQUE", self.technique),
                            ("RACINE", self.cabinet),
                            ("FORMULAIRE", self.web),
                            ("JOURNAL_TECHNIQUE_ACTIF", True)):
            patch = unittest.mock.patch.object(serveur, nom, valeur)
            patch.start()
            self.addCleanup(patch.stop)

    def signaler(self, motif):
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie), \
             contextlib.redirect_stderr(io.StringIO()):
            serveur.signaler_refus_racine_web(motif, self.bilans)
        return sortie.getvalue()

    def test_chaque_motif_a_son_message_et_ses_deux_lignes(self):
        messages = set()
        for motif in sorted(serveur.MOTIFS_REFUS_DEMARRAGE):
            with self.subTest(motif=motif):
                for chemin in (self.journal, self.technique):
                    if os.path.exists(chemin):
                        os.remove(chemin)
                console = self.signaler(motif)
                self.assertIn("Refus de démarrer", console)
                messages.add(console)
                self.assertIn("DEMARRAGE refusé motif=" + motif,
                              lire(self.tmp, "journal.log"))
                lignes = lire(self.tmp, "technique.log").splitlines()
                self.assertEqual(len(lignes), 1)
                self.assertRegex(
                    lignes[0],
                    r"^\S+ DEMARRAGE_REFUSE refus motif={}$".format(motif))
        self.assertEqual(len(messages), len(serveur.MOTIFS_REFUS_DEMARRAGE))

    def test_le_message_nomme_le_dossier_et_le_geste(self):
        self.assertIn("formulaire", self.signaler("racine-cabinet"))
        console = self.signaler("dossier-pdf")
        self.assertIn("dossier_pdf", console)
        self.assertIn("config.json", console)

    def test_le_journal_nominatif_porte_les_chemins_resolus_en_repr(self):
        self.signaler("racine-cabinet")
        ligne = lire(self.tmp, "journal.log")
        self.assertIn("racine_web=" + repr(os.path.realpath(self.web)), ligne)
        self.assertIn("cible=" + repr(os.path.realpath(self.cabinet)), ligne)

    def test_un_chemin_a_retour_a_la_ligne_ne_forge_pas_de_ligne(self):
        sale = os.path.join(self.tmp, "x\n2026-01-01T00:00:00 FAUX")
        with unittest.mock.patch.object(serveur, "RACINE", sale):
            self.signaler("racine-cabinet")
        lignes = lire(self.tmp, "journal.log").splitlines()
        self.assertEqual(len(lignes), 1)

    def test_aucun_chemin_dans_le_journal_technique(self):
        for motif in serveur.MOTIFS_REFUS_DEMARRAGE:
            self.signaler(motif)
        texte = lire(self.tmp, "technique.log")
        self.assertNotIn(self.tmp, texte)
        self.assertNotIn(os.path.realpath(self.tmp), texte)

    def test_l_interrupteur_du_journal_technique_est_respecte(self):
        with unittest.mock.patch.object(serveur, "JOURNAL_TECHNIQUE_ACTIF",
                                        False):
            self.signaler("racine-cabinet")
        self.assertFalse(os.path.exists(self.technique))
        self.assertIn("DEMARRAGE refusé", lire(self.tmp, "journal.log"))


class VerdictApresUnRefus(unittest.TestCase):
    """verdict_certificat relit la dernière ligne DEMARRAGE. DEMARRAGE_REFUSE
    n'en est pas une : sans empreinte, il faisait annoncer « premier
    démarrage observé » après tout refus."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bilan-test-verdict-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.technique = os.path.join(self.tmp, "technique.log")

    def verdict(self, lignes, empreinte):
        with open(self.technique, "w", encoding="utf-8") as f:
            f.write("".join(ligne + "\n" for ligne in lignes))
        with unittest.mock.patch.object(serveur, "TECHNIQUE", self.technique):
            return serveur.verdict_certificat(empreinte)

    def test_un_refus_apres_un_demarrage_ne_change_pas_le_verdict(self):
        demarrage = ["2026-11-07T08:00:00 DEMARRAGE version=1.1.0 port=8000 "
                     "certificat=abcdef0123456789 certificat identique"]
        refus = ["2026-11-07T08:05:00 DEMARRAGE_REFUSE refus motif=racine-cabinet"]
        for empreinte, attendu in (
                ("abcdef0123456789", "certificat identique au démarrage précédent"),
                ("0000000000000000", "certificat différent du démarrage précédent")):
            with self.subTest(empreinte=empreinte):
                sans = self.verdict(demarrage, empreinte)
                self.assertEqual(sans, attendu)   # ancrage
                self.assertEqual(self.verdict(demarrage + refus, empreinte), sans)
                self.assertEqual(self.verdict(demarrage + refus + refus, empreinte), sans)

    def test_un_refus_seul_reste_un_premier_demarrage(self):
        self.assertEqual(
            self.verdict(["2026-11-07T08:05:00 DEMARRAGE_REFUSE refus motif=dossier-pdf"],
                         "abcdef0123456789"),
            "premier démarrage observé")


# --------------------------------------------------------------------------
# Gardes dérivées de l'arbre syntaxique
# --------------------------------------------------------------------------

def arbre_serveur():
    with open(os.path.join(PROJET, "serveur", "serveur.py"),
              encoding="utf-8") as f:
        return ast.parse(f.read())


def definition(arbre, nom):
    return next(n for n in arbre.body
                if isinstance(n, ast.FunctionDef) and n.name == nom)


def nom_pointe(noeud):
    """`os.makedirs` -> "os.makedirs", `ServeurBilan` -> "ServeurBilan"."""
    if isinstance(noeud, ast.Name):
        return noeud.id
    if isinstance(noeud, ast.Attribute) and isinstance(noeud.value, ast.Name):
        return noeud.value.id + "." + noeud.attr
    return None


def lignes_des_appels(fonction, nom):
    return sorted(n.lineno for n in ast.walk(fonction)
                  if isinstance(n, ast.Call) and nom_pointe(n.func) == nom)


class Gardes(unittest.TestCase):

    def test_g1_les_motifs_rendus_sont_exactement_le_vocabulaire(self):
        fonction = definition(arbre_serveur(), "motif_refus_racine_web")
        rendus = set()
        for noeud in ast.walk(fonction):
            if isinstance(noeud, ast.Return) and noeud.value is not None:
                self.assertIsInstance(noeud.value, ast.Constant,
                                      "un retour doit être une constante")
                if noeud.value.value is not None:
                    rendus.add(noeud.value.value)
        self.assertEqual(rendus, set(serveur.MOTIFS_REFUS_DEMARRAGE))

    def test_g1_la_fonction_rend_aussi_none(self):
        # Ancrage : sans un `return None` explicite, la garde ci-dessus
        # laisserait passer une fonction qui ne rend jamais « tout va bien ».
        fonction = definition(arbre_serveur(), "motif_refus_racine_web")
        self.assertTrue(any(
            isinstance(n, ast.Return) and isinstance(n.value, ast.Constant)
            and n.value.value is None for n in ast.walk(fonction)))

    def test_g1_le_detail_ferme_le_vocabulaire(self):
        for motif in serveur.MOTIFS_REFUS_DEMARRAGE:
            self.assertEqual(serveur.detail_refus_demarrage(motif),
                             "refus motif=" + motif)
        for hors in ("/chemin/secret", "racine-cabinet\nFAUX", "", None):
            self.assertEqual(serveur.detail_refus_demarrage(hors),
                             "refus motif=motif-inconnu")

    def test_g1_l_evenement_appartient_au_vocabulaire_technique(self):
        self.assertIn("DEMARRAGE_REFUSE", serveur.EVENEMENTS_TECHNIQUES)

    def test_g1_le_signalement_n_ecrit_au_technique_que_le_detail_ferme(self):
        fonction = definition(arbre_serveur(), "signaler_refus_racine_web")
        appels = [n for n in ast.walk(fonction)
                  if isinstance(n, ast.Call)
                  and nom_pointe(n.func) == "journaliser_technique"]
        self.assertEqual(len(appels), 1)
        detail = appels[0].args[1]
        self.assertTrue(isinstance(detail, ast.Call)
                        and nom_pointe(detail.func) == "detail_refus_demarrage")

    def test_g2_le_controle_precede_l_ecriture_et_le_socket(self):
        arbre = arbre_serveur()
        demarrer = definition(arbre, "demarrer")
        controle = lignes_des_appels(demarrer, "motif_refus_racine_web")
        creation = lignes_des_appels(demarrer, "os.makedirs")
        socket_ouvert = lignes_des_appels(demarrer, "ServeurBilan")
        self.assertEqual(len(controle), 1)
        self.assertGreaterEqual(len(creation), 1)
        self.assertGreaterEqual(len(socket_ouvert), 1)
        self.assertLess(controle[0], creation[0])
        self.assertLess(controle[0], socket_ouvert[0])

        # L'interrupteur et la conservation sont posés avant le contrôle, pour
        # que la ligne de refus leur obéisse.
        for nom in ("JOURNAL_TECHNIQUE_ACTIF", "CONSERVATION_JOURNAUX_MOIS"):
            affectations = [
                n.lineno for n in ast.walk(demarrer)
                if isinstance(n, ast.Assign)
                and any(isinstance(c, ast.Name) and c.id == nom
                        for c in n.targets)]
            self.assertEqual(len(affectations), 1, nom)
            self.assertLess(affectations[0], controle[0], nom)

    def test_g3_preparer_sandbox_n_a_aucun_assert(self):
        # Un assert disparaît sous python -O : l'échec de l'autorité passerait
        # inaperçu et le bac servirait sans certificat.
        with open(os.path.join(DOSSIER_TESTS, "test_integration.py"),
                  encoding="utf-8") as f:
            arbre = ast.parse(f.read())
        preparer = definition(arbre, "preparer_sandbox")
        self.assertEqual(
            [n for n in ast.walk(preparer) if isinstance(n, ast.Assert)], [])

    def test_g3_preparer_sandbox_leve_avec_la_sortie_du_sous_processus(self):
        echec = types.SimpleNamespace(returncode=3, stdout="SORTIE-OUT",
                                      stderr="SORTIE-ERR")
        avant = set(os.listdir(tempfile.gettempdir()))
        with unittest.mock.patch.object(test_integration.subprocess, "run",
                                        return_value=echec):
            with self.assertRaises(AssertionError) as contexte:
                preparer_sandbox()
        message = str(contexte.exception)
        for attendu in ("code 3", "SORTIE-OUT", "SORTIE-ERR"):
            self.assertIn(attendu, message)
        # Le bac créé est retiré : personne ne tient son nom.
        crees = [n for n in set(os.listdir(tempfile.gettempdir())) - avant
                 if n.startswith("bilan-test-sandbox-")]
        self.assertEqual(crees, [])

    def test_g2_le_refus_sort_avec_le_code_1(self):
        demarrer = definition(arbre_serveur(), "demarrer")
        for si in (n for n in ast.walk(demarrer) if isinstance(n, ast.If)):
            appelle = any(isinstance(n, ast.Call)
                          and nom_pointe(n.func) == "signaler_refus_racine_web"
                          for corps in si.body for n in ast.walk(corps))
            if not appelle:
                continue
            retours = [n for n in si.body if isinstance(n, ast.Return)]
            self.assertEqual(len(retours), 1)
            self.assertEqual(retours[0].value.value, 1)
            return
        self.fail("aucun refus de démarrer ne signale la racine web")


# --------------------------------------------------------------------------
# Intégration : un vrai serveur, `formulaire` lié avant le démarrage
# --------------------------------------------------------------------------

def lancer_et_sonder(dossier, port):
    """Lance serveur.py dans le bac, attend sa sortie, et compte les
    connexions TCP que le port a acceptées pendant ce temps. Rend
    (processus terminé, connexions, durée).

    subprocess.run lit les tubes jusqu'au bout : jamais de tube laissé plein,
    qui figerait le test sous Windows (C7-T5)."""
    fin = threading.Event()
    connexions = []

    def sonder():
        while not fin.is_set():
            try:
                with socket.create_connection(("127.0.0.1", port), 0.05):
                    connexions.append(time.monotonic())
            except OSError:
                pass
            time.sleep(0.01)

    fil = threading.Thread(target=sonder, daemon=True)
    fil.start()
    debut = time.monotonic()
    try:
        processus = subprocess.run(
            [sys.executable, "-u", os.path.join("serveur", "serveur.py")],
            cwd=dossier, capture_output=True, text=True, timeout=30)
    finally:
        fin.set()
        fil.join(timeout=5)
    return processus, len(connexions), time.monotonic() - debut


def lier_formulaire_a_la_racine(cible):
    """avant_demarrage : remplace formulaire/ par un lien vers `cible`
    (texte du lien, relatif au bac ou absolu)."""
    def poser(dossier):
        formulaire = os.path.join(dossier, "formulaire")
        shutil.rmtree(formulaire)
        try:
            os.symlink(cible, formulaire, target_is_directory=True)
        except (OSError, NotImplementedError) as erreur:
            raise unittest.SkipTest(
                "lien symbolique impossible ici : {}".format(erreur))
    return poser


def jonction_formulaire(dossier):
    """avant_demarrage : formulaire/ devient une jonction NTFS vers le bac."""
    formulaire = os.path.join(dossier, "formulaire")
    shutil.rmtree(formulaire)
    sortie = subprocess.run(["cmd", "/c", "mklink", "/J", formulaire, dossier],
                            capture_output=True, text=True)
    if sortie.returncode != 0:
        raise AssertionError(sortie.stdout + sortie.stderr)


def defaire_la_jonction(dossier):
    """rmdir d'abord : shutil.rmtree ne doit jamais suivre une jonction qui
    remonte vers son propre parent."""
    formulaire = os.path.join(dossier, "formulaire")
    if os.path.lexists(formulaire):
        try:
            os.rmdir(formulaire)
        except OSError:
            pass


LIGNE_TECHNIQUE_REFUS = r"^\S+ DEMARRAGE_REFUSE refus motif={}$"


@unittest.skipIf(cryptography_absente(),
                 "cryptography requis pour fabriquer les certificats")
class RefusDeDemarrer(unittest.TestCase):

    def bac(self, config_extra=None, avant_demarrage=None):
        dossier, port = preparer_sandbox(config_extra, avant_demarrage)
        self.addCleanup(shutil.rmtree, dossier, ignore_errors=True)
        return dossier, port

    def refus(self, dossier, port, motif):
        """Lance le serveur et vérifie ce que tout refus a en commun."""
        processus, connexions, duree = lancer_et_sonder(dossier, port)
        sortie = processus.stdout + processus.stderr
        self.assertEqual(processus.returncode, 1, sortie)
        self.assertLess(duree, 10)
        self.assertEqual(connexions, 0, "le port a été ouvert avant le refus")
        self.assertIn("Refus de démarrer", sortie)
        # Le motif, lu dans journal.log, qui existe même sans journal
        # technique (I3) : un refus pour la mauvaise raison ne passe pas.
        self.assertIn("DEMARRAGE refusé motif={} ".format(motif),
                      lire(dossier, "journal.log"))
        return sortie

    def test_i1_formulaire_lie_a_la_racine_du_bac(self):
        dossier, port = self.bac(avant_demarrage=lier_formulaire_a_la_racine("."))
        self.refus(dossier, port, "racine-cabinet")

        technique = lire(dossier, "technique.log")
        lignes = [ligne for ligne in technique.splitlines() if ligne]
        self.assertRegex(
            lignes[-1], LIGNE_TECHNIQUE_REFUS.format("racine-cabinet"))

        journal = lire(dossier, "journal.log")
        self.assertIn("DEMARRAGE refusé motif=racine-cabinet", journal)
        self.assertIn(repr(os.path.realpath(dossier)), journal)

        # Ni chemin, ni nom de dossier, ni séparateur hors de l'horodatage.
        for forme in (dossier, os.path.realpath(dossier)):
            self.assertNotIn(forme, technique)
        self.assertNotIn("formulaire", technique)
        for ligne in lignes:
            reste = ligne.split(" ", 1)[1]
            self.assertNotIn("/", reste)
            self.assertNotIn("\\", reste)

        # Rien créé sur le chemin du refus.
        self.assertFalse(os.path.exists(os.path.join(dossier, "bilans")))

    def test_i1_le_lien_peut_aussi_etre_absolu(self):
        dossier, port = self.bac()
        lier_formulaire_a_la_racine(dossier)(dossier)
        self.refus(dossier, port, "racine-cabinet")
        self.assertRegex(
            lire(dossier, "technique.log").splitlines()[-1],
            LIGNE_TECHNIQUE_REFUS.format("racine-cabinet"))

    def test_i2_dossier_des_bilans_sous_la_racine_web(self):
        dossier, port = self.bac({"dossier_pdf": "formulaire/bilans"})
        self.refus(dossier, port, "dossier-pdf")
        self.assertRegex(
            lire(dossier, "technique.log").splitlines()[-1],
            LIGNE_TECHNIQUE_REFUS.format("dossier-pdf"))
        self.assertIn("DEMARRAGE refusé motif=dossier-pdf",
                      lire(dossier, "journal.log"))
        # Le refus précède makedirs : rien n'est créé sous la racine web.
        self.assertFalse(os.path.exists(
            os.path.join(dossier, "formulaire", "bilans")))

    def test_i2_le_dossier_des_bilans_absolu_est_refuse_aussi(self):
        dossier, port = self.bac()
        absolu = os.path.join(dossier, "formulaire", "archives")
        self.bac_config(dossier, {"dossier_pdf": absolu})
        self.refus(dossier, port, "dossier-pdf")
        self.assertFalse(os.path.exists(absolu))

    def bac_config(self, dossier, extra):
        """Complète le config.json d'un bac déjà préparé."""
        chemin = os.path.join(dossier, "config.json")
        with open(chemin, encoding="utf-8") as f:
            config = json.load(f)
        config.update(extra)
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(config, f)

    def test_i3_refus_sans_journal_technique(self):
        dossier, port = self.bac({"journal_technique": False},
                                 lier_formulaire_a_la_racine("."))
        self.refus(dossier, port, "racine-cabinet")
        self.assertIn("DEMARRAGE refusé motif=racine-cabinet",
                      lire(dossier, "journal.log"))
        self.assertNotIn("DEMARRAGE_REFUSE", lire(dossier, "technique.log"))

    def test_i6_temoin_formulaire_deplace_hors_du_bac_et_lie_demarre(self):
        # D2 de C6-T6 n'est pas rouverte : un lien qui déplace la racine web
        # sans lui faire englober le cabinet reste servi. Garde contre un
        # refus trop large.
        ailleurs = tempfile.mkdtemp(prefix="bilan-test-ailleurs-")
        self.addCleanup(shutil.rmtree, ailleurs, ignore_errors=True)

        def deplacer_et_lier(dossier):
            cible = os.path.join(ailleurs, "formulaire")
            shutil.move(os.path.join(dossier, "formulaire"), cible)
            try:
                os.symlink(cible, os.path.join(dossier, "formulaire"),
                           target_is_directory=True)
            except (OSError, NotImplementedError) as erreur:
                raise unittest.SkipTest(
                    "lien symbolique impossible ici : {}".format(erreur))

        dossier, port, processus = demarrer_sandbox_court(
            avant_demarrage=deplacer_et_lier)
        self.addCleanup(shutil.rmtree, dossier, ignore_errors=True)

        def arreter():
            processus.terminate()
            processus.wait(timeout=10)
            processus.stdout.close()
        self.addCleanup(arreter)
        # Le tube doit être vidé en continu (C7-T5).
        lecteur = threading.Thread(
            target=lambda: [None for _ in iter(processus.stdout.readline, "")],
            daemon=True)
        lecteur.start()

        statut, _, corps = requete(dossier, port, "/")
        self.assertEqual(statut, 200)
        self.assertGreater(len(corps), 0)


@unittest.skipUnless(os.name == "nt", "jonction NTFS : Windows seulement")
@unittest.skipIf(cryptography_absente(),
                 "cryptography requis pour fabriquer les certificats")
class RefusSousJonction(unittest.TestCase):

    def test_w1_formulaire_en_jonction_vers_la_racine_du_bac(self):
        dossier, port = preparer_sandbox(avant_demarrage=jonction_formulaire)
        # Les nettoyages s'exécutent en ordre inverse : la jonction se défait
        # avant que rmtree ne passe.
        self.addCleanup(shutil.rmtree, dossier, ignore_errors=True)
        self.addCleanup(defaire_la_jonction, dossier)

        processus, connexions, duree = lancer_et_sonder(dossier, port)
        self.assertEqual(processus.returncode, 1,
                         processus.stdout + processus.stderr)
        self.assertEqual(connexions, 0)
        self.assertLess(duree, 10)
        self.assertRegex(
            lire(dossier, "technique.log").splitlines()[-1],
            LIGNE_TECHNIQUE_REFUS.format("racine-cabinet"))


if __name__ == "__main__":
    unittest.main()
