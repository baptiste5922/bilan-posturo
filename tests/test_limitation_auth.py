"""Limitation des tentatives d'authentification (contrat C6-T2).

Dix tentatives présentées et refusées, puis chaque refus suivant est retardé
(0,5 s, 1 s, 2 s, plafonné à 3 s). Un identifiant valide ne dort jamais et
remet le compteur à zéro ; une requête sans en-tête `Authorization` n'est pas
une tentative ; `/sante` ne traverse pas le mécanisme. Le journal technique
porte le compte agrégé, sans adresse.

  Unitaires    — le calcul pur, l'oubli à horloge injectée, le branchement
                 dans `authentifie` (U1 à U5, F1 à F5) ;
  Journal      — la forme du détail d'AUTH_REFUSEE et l'absence de fuite
                 (J1, J2) ;
  Gardes AST   — le sommeil est circonscrit, rien ne dort sous un verrou
                 (G1, G2), chacune avec son témoin « la garde mord » ;
  Intégration  — un vrai serveur en bac à sable (E1 à E4).

    python3 -m unittest tests.test_limitation_auth
    python3 -O -m unittest tests.test_limitation_auth

Bibliothèque standard seule. Pas d'`assert` nu : il s'évaporerait sous -O.
Aucun `sleep` dans les tests unitaires : l'horloge s'injecte, `attendre` se
remplace par un espion. Seul E1 fait dormir le vrai chemin, et il ne vérifie
qu'une borne inférieure.
"""

import ast
import base64
import email
import http.client
import io
import json
import os
import re
import shutil
import ssl
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock

DOSSIER_TESTS = os.path.dirname(os.path.abspath(__file__))
PROJET = os.path.dirname(DOSSIER_TESTS)
sys.path.insert(0, os.path.join(PROJET, "serveur"))
sys.path.insert(0, DOSSIER_TESTS)

import serveur
from test_integration import (
    MOT_DE_PASSE, PDF, UTILISATEUR, chercher_adresse, cryptography_absente,
    demarrer_sandbox_court)

# Le chiffre de la feuille de route (C6-T2), volontairement écrit ici et non
# dérivé de serveur.SEUIL_ECHECS_AUTH : un seuil abaissé dans le code doit faire
# rougir le test, pas l'entraîner avec lui.
SEUIL_DOCUMENTE = 10

# Un mot de passe haché à peu d'itérations : la limitation ne dépend pas du coût
# du hachage, et 50 vérifications à 240 000 itérations allongeraient la suite
# pour rien.
HACHAGE_RAPIDE = serveur.hacher(MOT_DE_PASSE, iterations=1000)

# Le vrai `attendre`, gardé avant que le banc ne le remplace par un espion.
ATTENDRE_REEL = serveur.attendre


def basic(utilisateur, mot_de_passe):
    jeton = base64.b64encode(
        "{}:{}".format(utilisateur, mot_de_passe).encode("utf-8")).decode("ascii")
    return "Basic " + jeton


def detail_des_lignes(texte, evenement):
    """Le détail (troisième champ) de chaque ligne de l'événement : jamais une
    sous-chaîne du texte entier (DEMARRAGE préfixe DEMARRAGE_REFUSE)."""
    details = []
    for ligne in texte.splitlines():
        champs = ligne.split(" ", 2)
        if len(champs) == 3 and champs[1] == evenement:
            details.append(champs[2])
    return details


def forme_detail_auth():
    """L'expression d'une ligne AUTH_REFUSEE, DÉRIVÉE des deux ensembles
    fermés : une route ou un motif ajouté demain en fait partie sans que ce
    fichier bouge, et un ensemble vidé fait échouer la forme."""
    routes = "|".join(sorted(re.escape(r) for r in serveur.ROUTES_TECHNIQUES))
    motifs = "|".join(sorted(re.escape(m) for m in serveur.MOTIFS_AUTH_REFUSEE))
    return re.compile(
        r"route=(?:{}) identifiants=(?:{}) echecs=[0-9]+ attente=[0-9]+\.[0-9]"
        .format(routes, motifs))


class EspionAttente:
    """Remplace `serveur.attendre` : enregistre, ne dort pas."""

    def __init__(self):
        self.appels = []

    def __call__(self, secondes):
        self.appels.append(secondes)

    def non_nuls(self):
        return [s for s in self.appels if s > 0]


class Banc(unittest.TestCase):
    """Journaux jetables, compteur remis à zéro, `attendre` espionné.

    Sans la substitution de TECHNIQUE et de JOURNAL, `journaliser` écrirait dans
    le journal.log réel, à la racine du dépôt (patron de test_conservation)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bilan-test-auth-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.technique = os.path.join(self.tmp, "technique.log")
        self.journal = os.path.join(self.tmp, "journal.log")
        for nom, valeur in (("TECHNIQUE", self.technique),
                            ("JOURNAL", self.journal),
                            ("JOURNAL_TECHNIQUE_ACTIF", True),
                            ("ecrire_stderr", lambda ligne: None)):
            patch = unittest.mock.patch.object(serveur, nom, valeur)
            patch.start()
            self.addCleanup(patch.stop)
        # Le processus de test est partagé entre les classes : l'état de la
        # limitation ne doit ni venir d'un test voisin, ni lui survivre.
        serveur.reinitialiser_echecs_authentification()
        self.addCleanup(serveur.reinitialiser_echecs_authentification)
        self.espion = EspionAttente()
        patch = unittest.mock.patch.object(serveur, "attendre", self.espion)
        patch.start()
        self.addCleanup(patch.stop)

    def gestionnaire(self, entete=None, chemin="/index.html", requetes=b""):
        """Un Gestionnaire sans socket (bypass de __init__), patron de
        tests/test_serveur.py::DepotEchecEcritureSansFuite."""
        instance = serveur.Gestionnaire.__new__(serveur.Gestionnaire)
        instance.command = "GET"
        instance.path = chemin
        instance.requestline = "GET {} HTTP/1.1".format(chemin)
        instance.client_address = ("203.0.113.9", 4242)
        instance.request_version = "HTTP/1.1"
        instance.close_connection = True
        instance.silencieux = False
        instance.config = {"utilisateur": UTILISATEUR,
                           "mot_de_passe": HACHAGE_RAPIDE}
        texte = "" if entete is None else "Authorization: {}\n".format(entete)
        instance.headers = email.message_from_string(texte)
        instance.rfile = io.BytesIO(requetes)
        instance.wfile = io.BytesIO()
        return instance

    def presenter(self, entete, chemin="/index.html"):
        """Ce que font les quatre appelants d'`authentifie` : le verdict, puis
        le 401 quand il est négatif. Rend (verdict, gestionnaire)."""
        instance = self.gestionnaire(entete, chemin)
        verdict = instance.authentifie()
        if not verdict:
            instance.exiger_authentification()
        return verdict, instance

    def refuser(self, nombre, utilisateur=UTILISATEUR, mot_de_passe="mauvais"):
        for _ in range(nombre):
            verdict, _ = self.presenter(basic(utilisateur, mot_de_passe))
            self.assertFalse(verdict)

    def accepter(self):
        verdict, instance = self.presenter(basic(UTILISATEUR, MOT_DE_PASSE))
        self.assertTrue(verdict)
        return instance

    def lire_technique(self):
        if not os.path.exists(self.technique):
            return ""
        with open(self.technique, encoding="utf-8") as f:
            return f.read()

    def details_auth(self):
        return detail_des_lignes(self.lire_technique(), "AUTH_REFUSEE")


# --------------------------------------------------------------------------
# Unitaires : le calcul pur et l'état
# --------------------------------------------------------------------------

class Calcul(Banc):
    """U1 à U5."""

    def test_u1_seuil(self):
        for n in range(SEUIL_DOCUMENTE + 1):
            with self.subTest(echecs=n):
                self.assertEqual(serveur.attente_apres_echec(n), 0.0)
        self.assertGreater(serveur.attente_apres_echec(SEUIL_DOCUMENTE + 1), 0)
        # Et le code porte bien le chiffre de la feuille de route.
        self.assertEqual(serveur.SEUIL_ECHECS_AUTH, SEUIL_DOCUMENTE)

    def test_u2_progression_et_plafond(self):
        suite = [serveur.attente_apres_echec(n) for n in range(11, 16)]
        self.assertEqual(suite, [0.5, 1.0, 2.0, 3.0, 3.0])
        self.assertEqual(suite, sorted(suite))
        # Un exposant sans borne ferait lever OverflowError (entier trop grand
        # pour un flottant) : l'éprouver bien au-delà de ce qu'une machine
        # atteindrait en pratique.
        for n in (100, 10 ** 3, 10 ** 6):
            with self.subTest(echecs=n):
                self.assertEqual(serveur.attente_apres_echec(n),
                                 serveur.ATTENTE_AUTH_MAX_SECONDES)
        # Strictement sous le plus court délai de la tablette (DELAI_CABINET =
        # 5 s, formulaire/script.js) et très au-dessous de l'attente de l'arrêt
        # concerté : c'est la raison du plafond.
        self.assertLess(serveur.ATTENTE_AUTH_MAX_SECONDES, 5.0)
        self.assertLess(serveur.ATTENTE_AUTH_MAX_SECONDES,
                        serveur.DELAI_FIN_DEPOTS_SECONDES)

    def test_u3_fenetre_d_oubli(self):
        fenetre = serveur.FENETRE_ECHECS_AUTH_SECONDES
        origine = 1000.0
        # Au-delà de la fenêtre : l'oubli, horloge injectée, aucun sleep.
        for i in range(15):
            echecs, attente = serveur.noter_echec_authentification(origine + i)
            self.assertEqual(echecs, i + 1)
        self.assertEqual(attente, 3.0)
        dernier = origine + 14
        echecs, attente = serveur.noter_echec_authentification(
            dernier + fenetre + 1)
        self.assertEqual((echecs, attente), (1, 0.0))

        # En deçà : le compteur continue de croître, et la fenêtre compte
        # depuis le DERNIER échec, pas depuis le premier.
        serveur.reinitialiser_echecs_authentification()
        for i in range(15):
            serveur.noter_echec_authentification(origine + i)
        echecs, attente = serveur.noter_echec_authentification(
            dernier + fenetre - 1)
        self.assertEqual(echecs, 16)
        self.assertEqual(attente, serveur.ATTENTE_AUTH_MAX_SECONDES)

        # La borne elle-même ne fait pas oublier : la comparaison est stricte.
        serveur.reinitialiser_echecs_authentification()
        serveur.noter_echec_authentification(origine)
        echecs, _ = serveur.noter_echec_authentification(origine + fenetre)
        self.assertEqual(echecs, 2)

    def test_u3_tablette_au_mot_de_passe_perime_franchit_seule_le_seuil(self):
        # La cadence de la file d'attente de la tablette (RELANCE_FILE, en ms
        # dans script.js), lue à la source plutôt que recopiée.
        with open(os.path.join(PROJET, "formulaire", "script.js"),
                  encoding="utf-8") as f:
            script = f.read()
        relance = int(re.search(r"const RELANCE_FILE = (\d+);", script).group(1)) / 1000
        delai_depot = int(re.search(r"const DELAI_DEPOT = (\d+);", script).group(1)) / 1000
        # La fenêtre glisse : un refus par relance ne la laisse jamais expirer.
        self.assertLess(relance, serveur.FENETRE_ECHECS_AUTH_SECONDES)

        origine = 5000.0
        attentes = []
        for i in range(SEUIL_DOCUMENTE + 5):
            echecs, attente = serveur.noter_echec_authentification(origine + i * relance)
            self.assertEqual(echecs, i + 1)         # jamais oublié
            attentes.append(attente)
        # Le seuil est franchi, seul, vers dix minutes de relances.
        self.assertEqual(attentes[:SEUIL_DOCUMENTE], [0.0] * SEUIL_DOCUMENTE)
        self.assertGreater(attentes[SEUIL_DOCUMENTE], 0)
        # Mais le retard reste sous le plafond, très sous le délai d'un dépôt :
        # la file ne prend pas ce refus pour une panne.
        self.assertLessEqual(max(attentes), serveur.ATTENTE_AUTH_MAX_SECONDES)
        self.assertLess(serveur.ATTENTE_AUTH_MAX_SECONDES, delai_depot)
        # Le bon mot de passe, ensuite, remet à zéro.
        serveur.reinitialiser_echecs_authentification()
        self.assertEqual(serveur.ECHECS_AUTH, 0)

    def test_u4_succes_remet_a_zero(self):
        self.refuser(12)
        self.assertEqual(serveur.ECHECS_AUTH, 12)
        self.assertIsNotNone(serveur.DERNIER_ECHEC_AUTH)
        self.accepter()
        self.assertEqual(serveur.ECHECS_AUTH, 0)
        self.assertIsNone(serveur.DERNIER_ECHEC_AUTH)
        # Le refus suivant repart de un, sans attente.
        self.refuser(1)
        self.assertEqual(serveur.ECHECS_AUTH, 1)
        self.assertEqual(self.details_auth()[-1].split(" ")[2:], ["echecs=1", "attente=0.0"])

    def test_u4_reinitialiser_directement(self):
        for i in range(5):
            serveur.noter_echec_authentification(float(i))
        serveur.reinitialiser_echecs_authentification()
        self.assertEqual(serveur.ECHECS_AUTH, 0)
        self.assertIsNone(serveur.DERNIER_ECHEC_AUTH)

    def test_u5_attendre_ne_dort_que_si_positif(self):
        self.assertIsNot(serveur.attendre, ATTENDRE_REEL)   # témoin : espionné
        with unittest.mock.patch.object(serveur.time, "sleep") as sommeil:
            ATTENDRE_REEL(0.0)
            ATTENDRE_REEL(-1.0)
            sommeil.assert_not_called()
            ATTENDRE_REEL(0.7)
            sommeil.assert_called_once_with(0.7)


# --------------------------------------------------------------------------
# Unitaires : le branchement dans authentifie()
# --------------------------------------------------------------------------

class Branchement(Banc):
    """F1 à F5."""

    def test_f1_identifiant_valide_jamais_retarde(self):
        self.refuser(50)
        # Ancrage : le refus 50 dormait bel et bien (sinon l'espion vide ne
        # prouverait rien).
        self.assertGreater(len(self.espion.non_nuls()), 30)
        avant = len(self.espion.appels)
        self.accepter()
        # Jamais d'appel du tout : l'identifiant valide n'attend pas, même à
        # zéro seconde (étape 4.3 du contrat).
        self.assertEqual(self.espion.appels[avant:], [])
        self.assertEqual(serveur.ECHECS_AUTH, 0)

    def test_f2_sans_entete_jamais_compte(self):
        for _ in range(200):
            verdict, _ = self.presenter(None)
            self.assertFalse(verdict)
        # Les autres formes de « pas d'identifiants présentés ».
        for entete in ("Bearer abcdef", "Basic !!!pas-du-base64!!!",
                       "Basic " + base64.b64encode(b"\xff\xfe\xfd").decode("ascii"),
                       "basic minuscule", ""):
            with self.subTest(entete=entete):
                verdict, _ = self.presenter(entete)
                self.assertFalse(verdict)
        self.assertEqual(serveur.ECHECS_AUTH, 0)
        self.assertIsNone(serveur.DERNIER_ECHEC_AUTH)
        self.assertEqual(self.espion.non_nuls(), [])
        details = self.details_auth()
        self.assertEqual(len(details), 205)
        for detail in details:
            self.assertRegex(detail, r"identifiants=absents echecs=0 attente=0\.0$")

    def test_f3_mauvais_identifiant_et_mauvais_mot_de_passe_comptent_pareil(self):
        cas = (("mauvais identifiant", "cabinèt", MOT_DE_PASSE),    # accentué
               ("mauvais mot de passe", UTILISATEUR, "faux"),
               ("les deux", "autre", "faux"))
        # Les deux vérifications sont TOUJOURS exécutées, quelle que soit celle
        # qui échoue : le temps ne dit pas laquelle a refusé.
        for numero, (nom, utilisateur, mot_de_passe) in enumerate(cas, start=1):
            with self.subTest(cas=nom):
                with unittest.mock.patch.object(
                        serveur, "verifier_mot_de_passe",
                        wraps=serveur.verifier_mot_de_passe) as verif, \
                        unittest.mock.patch.object(
                            serveur.hmac, "compare_digest",
                            wraps=serveur.hmac.compare_digest) as comparaison:
                    verdict, _ = self.presenter(basic(utilisateur, mot_de_passe))
                self.assertFalse(verdict)
                verif.assert_called_once()
                # Une comparaison de l'identifiant, sur des OCTETS (une chaîne
                # accentuée lèverait TypeError), puis celle du mot de passe.
                premiere = comparaison.call_args_list[0][0]
                self.assertTrue(all(isinstance(a, bytes) for a in premiere))
                self.assertGreaterEqual(comparaison.call_count, 2)
                self.assertEqual(serveur.ECHECS_AUTH, numero)

    def test_f4_remise_a_zero_entre_requetes_d_une_meme_connexion(self):
        # Deux requêtes sur la MÊME instance, par le vrai handle_one_request :
        # la seconde, sans identifiants, ne doit rien hériter du verdict de la
        # première.
        premiere = ("GET /index.html HTTP/1.1\r\nHost: x\r\nAuthorization: {}\r\n"
                    "\r\n".format(basic(UTILISATEUR, "faux")))
        seconde = "GET /cabinet HTTP/1.1\r\nHost: x\r\n\r\n"
        instance = self.gestionnaire(
            requetes=(premiere + seconde).encode("ascii"))
        instance.handle_one_request()
        instance.handle_one_request()
        details = self.details_auth()
        self.assertEqual(len(details), 2, details)
        self.assertEqual(details[0], "route=formulaire identifiants=refuses "
                                     "echecs=1 attente=0.0")
        self.assertEqual(details[1], "route=cabinet identifiants=absents "
                                     "echecs=0 attente=0.0")

    def test_f4_handle_one_request_remet_les_trois_attributs(self):
        instance = self.gestionnaire()
        instance._auth_motif = "refuses"
        instance._auth_echecs = 42
        instance._auth_attente = 3.0
        instance.handle_one_request()       # rfile vide : rien à servir
        self.assertEqual(instance._auth_motif, "absents")
        self.assertEqual(instance._auth_echecs, 0)
        self.assertEqual(instance._auth_attente, 0.0)

    def test_f5_aucun_verrou_tenu_pendant_le_sommeil(self):
        # Le vrai `attendre` (celui du module), mais un `time.sleep` qui
        # bloque le seul fil du refus jusqu'à ce qu'on le libère : on observe
        # alors, depuis un autre fil, ce que ce refus tient.
        vrai = ATTENDRE_REEL
        sommeil_reel = time.sleep
        endormi = threading.Event()
        reveil = threading.Event()
        fils = {}

        def sommeil(secondes):
            if threading.current_thread() is fils.get("refus"):
                endormi.set()
                reveil.wait(10)
            else:
                sommeil_reel(secondes)

        # Au-delà du seuil : le prochain refus dort.
        with serveur._verrou_auth:
            serveur.ECHECS_AUTH = SEUIL_DOCUMENTE + 2
            serveur.DERNIER_ECHEC_AUTH = time.monotonic()

        with unittest.mock.patch.object(serveur, "attendre", vrai), \
                unittest.mock.patch.object(serveur.time, "sleep", sommeil):
            fil = threading.Thread(
                target=lambda: self.presenter(basic(UTILISATEUR, "faux")),
                daemon=True)
            fils["refus"] = fil
            fil.start()
            try:
                self.assertTrue(endormi.wait(10), "le refus n'a pas dormi")
                for nom in ("_verrou_auth", "_verrou_journal", "_verrou_compteurs"):
                    verrou = getattr(serveur, nom)
                    with self.subTest(verrou=nom):
                        self.assertTrue(verrou.acquire(timeout=3),
                                        "{} tenu pendant le sommeil".format(nom))
                        verrou.release()
                # Et un second fil journalise pendant ce temps.
                ecrivain = threading.Thread(
                    target=lambda: serveur.journaliser_technique("DEPOT", "ok 1 octets"),
                    daemon=True)
                ecrivain.start()
                ecrivain.join(5)
                self.assertFalse(ecrivain.is_alive(), "journal bloqué par le sommeil")
                self.assertTrue(detail_des_lignes(self.lire_technique(), "DEPOT"))
            finally:
                reveil.set()
                fil.join(10)
        self.assertFalse(fil.is_alive())


# --------------------------------------------------------------------------
# Journal : la forme du détail, et l'absence de fuite
# --------------------------------------------------------------------------

class Journal(Banc):
    """J1 et J2."""

    CHEMINS = ("/depot", "/cabinet", "/etat", "/index.html", "/Dupont-Lea.pdf")

    def test_j1_forme_du_detail_derivee(self):
        # Ancrages : une dérivation sur des ensembles vides passerait.
        self.assertGreaterEqual(len(serveur.MOTIFS_AUTH_REFUSEE), 2)
        self.assertGreaterEqual(len(serveur.ROUTES_TECHNIQUES), 2)
        forme = forme_detail_auth()

        routes_vues = set()
        for chemin in self.CHEMINS:
            self.presenter(None, chemin)
            self.presenter(basic(UTILISATEUR, "faux"), chemin)
        for detail in self.details_auth():
            with self.subTest(detail=detail):
                self.assertRegex(detail, forme.pattern)
                self.assertIsNotNone(forme.fullmatch(detail))
                routes_vues.add(detail.split(" ")[0])
        self.assertEqual(len(self.details_auth()), 2 * len(self.CHEMINS))
        self.assertGreaterEqual(len(routes_vues), 4)
        # Les deux motifs se rencontrent, et se lisent sans ambiguïté.
        motifs = {d.split(" ")[1] for d in self.details_auth()}
        self.assertEqual(motifs, {"identifiants=" + m
                                  for m in serveur.MOTIFS_AUTH_REFUSEE})

        # Vocabulaire fermé : un motif hors de l'ensemble ne se recopie pas.
        for hostile in ("Dupont-Lea", "192.168.1.13", "\x1b[31m", "", None):
            with self.subTest(motif=hostile):
                detail = serveur.detail_auth_refusee("formulaire", hostile, 3, 0.5)
                self.assertEqual(
                    detail,
                    "route=formulaire identifiants=motif-inconnu echecs=3 attente=0.5")

    def test_j2_aucune_fuite_dans_le_detail(self):
        hostiles = ("Dupont-Lea", "192.168.1.13", "\x1b[31mrouge", "fe80::1")
        for hostile in hostiles:
            self.refuser(1, utilisateur=hostile, mot_de_passe=hostile)
            self.refuser(1, utilisateur=UTILISATEUR, mot_de_passe=hostile)
        # Les en-têtes et le chemin viennent eux aussi du client.
        entete = basic("Dupont-Lea", "192.168.1.13")
        self.presenter(entete, "/Dupont-Lea_192.168.1.13.pdf")
        contenu = self.lire_technique()
        self.assertGreater(len(self.details_auth()), 8)

        interdits = list(hostiles) + [
            "Authorization", "Basic", entete, "Dupont", "Lea",
            "203.0.113.9",            # l'adresse du client du banc
            "_192.168", "x1b"]
        for interdit in interdits:
            with self.subTest(interdit=interdit):
                self.assertNotIn(interdit, contenu)
        self.assertIsNone(chercher_adresse(contenu))
        self.assertNotIn("\x1b", contenu)
        # Témoin : le journal NOMINATIF, lui, porte l'adresse (sinon l'absence
        # ci-dessus ne dirait rien du banc).
        with open(self.journal, encoding="utf-8") as f:
            self.assertIn("203.0.113.9", f.read())


# --------------------------------------------------------------------------
# Gardes structurelles : dérivées de l'arbre syntaxique
# --------------------------------------------------------------------------

def arbre_serveur():
    with open(serveur.__file__, encoding="utf-8") as f:
        return ast.parse(f.read())


def fonctions(arbre):
    """nom -> définitions : les fonctions du module et les méthodes de
    Gestionnaire (les seules que les gardes suivent)."""
    table = {}
    for noeud in arbre.body:
        if isinstance(noeud, ast.FunctionDef):
            table.setdefault(noeud.name, []).append(noeud)
        elif isinstance(noeud, ast.ClassDef) and noeud.name == "Gestionnaire":
            for methode in noeud.body:
                if isinstance(methode, ast.FunctionDef):
                    table.setdefault(methode.name, []).append(methode)
    return table


def appelle_sleep(noeud):
    return (isinstance(noeud, ast.Call)
            and isinstance(noeud.func, ast.Attribute)
            and noeud.func.attr == "sleep"
            and isinstance(noeud.func.value, ast.Name)
            and noeud.func.value.id == "time")


def appelle_attendre(noeud):
    return (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
            and noeud.func.id == "attendre")


def noms_appeles(definition):
    noms = set()
    for noeud in ast.walk(definition):
        if not isinstance(noeud, ast.Call):
            continue
        f = noeud.func
        if isinstance(f, ast.Name):
            noms.add(f.id)
        elif (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
              and f.value.id == "self"):
            noms.add(f.attr)
    return noms


def atteignables(racines, table):
    vus = set()
    pile = list(racines)
    while pile:
        nom = pile.pop()
        if nom in vus or nom not in table:
            continue
        vus.add(nom)
        for definition in table[nom]:
            pile.extend(noms_appeles(definition))
    return vus


FONCTIONS_DU_CHEMIN = ("authentifie", "exiger_authentification",
                       "repondre_sante", "do_GET", "do_HEAD")


def problemes_sommeil(arbre):
    """Liste des manquements de la garde G1 (vide = vert). Les ancrages sont
    des manquements eux aussi : une dérivation qui ne trouve rien passerait au
    vert, c'est le piège du dépôt."""
    problemes = []
    table = fonctions(arbre)

    definitions = table.get("attendre", [])
    if len(definitions) != 1:
        return ["ancrage : `attendre` introuvable ou en double"]
    if not any(appelle_sleep(n) for n in ast.walk(definitions[0])):
        problemes.append("ancrage : `attendre` ne dort pas")
    absentes = [n for n in FONCTIONS_DU_CHEMIN if n not in table]
    if absentes:
        return problemes + ["ancrage : introuvables " + ", ".join(absentes)]

    chemin = atteignables(FONCTIONS_DU_CHEMIN, table)
    for attendu in ("authentifie", "exiger_authentification",
                    "noter_echec_authentification", "journaliser_technique"):
        if attendu not in chemin:
            problemes.append("ancrage : {} non atteint depuis le chemin".format(attendu))

    for nom in sorted(chemin - {"attendre"}):
        for definition in table[nom]:
            if any(appelle_sleep(n) for n in ast.walk(definition)):
                problemes.append("time.sleep dans {}".format(nom))

    # Le seul appelant d'`attendre` est authentifie().
    sites = 0
    for nom, definitions in table.items():
        for definition in definitions:
            if nom != "authentifie" and any(
                    appelle_attendre(n) for n in ast.walk(definition)):
                problemes.append("attendre() appelé depuis {}".format(nom))
            if nom == "authentifie":
                sites += sum(1 for n in ast.walk(definition) if appelle_attendre(n))
    if sites < 1:
        problemes.append("ancrage : authentifie() n'appelle pas attendre()")

    # La sonde de santé n'atteint rien de la limitation, par aucune voie.
    sante = atteignables(["repondre_sante"], table)
    for interdit in ("authentifie", "exiger_authentification", "attendre",
                     "noter_echec_authentification"):
        if interdit in sante:
            problemes.append("repondre_sante atteint {}".format(interdit))
    return problemes


VERROUS = ("_verrou_auth", "_verrou_journal", "_verrou_compteurs")


def problemes_verrous(arbre):
    """Manquements de la garde G2 : un sommeil ou un appel à `attendre`
    lexicalement sous un `with <verrou>`, dans tout le fichier."""
    problemes = []
    vus = {nom: 0 for nom in VERROUS}
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.With):
            continue
        tenus = [i.context_expr.id for i in noeud.items
                 if isinstance(i.context_expr, ast.Name)
                 and i.context_expr.id in VERROUS]
        for nom in tenus:
            vus[nom] += 1
        if not tenus:
            continue
        for sous in noeud.body:
            for n in ast.walk(sous):
                if appelle_sleep(n) or appelle_attendre(n):
                    problemes.append("{} sous {} (ligne {})".format(
                        "time.sleep" if appelle_sleep(n) else "attendre()",
                        "+".join(tenus), n.lineno))
    # Ancrages : les trois verrous existent et sont pris.
    if vus["_verrou_auth"] < 2:
        problemes.append("ancrage : _verrou_auth pris moins de deux fois")
    for nom in ("_verrou_journal", "_verrou_compteurs"):
        if vus[nom] < 1:
            problemes.append("ancrage : {} jamais pris".format(nom))
    return problemes


def injecter(arbre, fonction, instruction, sous_verrou=None):
    """Ajoute une instruction en fin de `fonction`, ou de son `with
    <sous_verrou>`. Lève si rien n'a été injecté : un témoin qui ne mute rien
    passerait pour une garde qui mord."""
    neuf = ast.parse(instruction).body[0]
    for definition in fonctions(arbre)[fonction]:
        if sous_verrou is None:
            definition.body.append(neuf)
            return arbre
        for noeud in ast.walk(definition):
            if (isinstance(noeud, ast.With)
                    and any(isinstance(i.context_expr, ast.Name)
                            and i.context_expr.id == sous_verrou
                            for i in noeud.items)):
                noeud.body.append(neuf)
                ast.fix_missing_locations(arbre)
                return arbre
    raise AssertionError("injection impossible dans {}".format(fonction))


class GardesStructurelles(unittest.TestCase):

    def test_g1_le_sommeil_est_circonscrit(self):
        self.assertEqual(problemes_sommeil(arbre_serveur()), [])

    def test_g1_mord(self):
        # Chacune de ces sources mutées doit rougir la garde.
        for fonction, instruction in (
                ("repondre_sante", "attendre(1.0)"),
                ("repondre_sante", "time.sleep(1.0)"),
                ("authentifie", "time.sleep(1.0)"),
                ("exiger_authentification", "attendre(1.0)"),
                ("do_GET", "time.sleep(1.0)")):
            with self.subTest(fonction=fonction, instruction=instruction):
                muté = injecter(arbre_serveur(), fonction, instruction)
                ast.fix_missing_locations(muté)
                self.assertNotEqual(problemes_sommeil(muté), [])
        # Une garde sans cible échoue plutôt que de passer : `attendre` retiré.
        sans = arbre_serveur()
        sans.body = [n for n in sans.body
                     if not (isinstance(n, ast.FunctionDef) and n.name == "attendre")]
        self.assertTrue(problemes_sommeil(sans)[0].startswith("ancrage"))

    def test_g2_rien_ne_dort_sous_le_verrou(self):
        self.assertEqual(problemes_verrous(arbre_serveur()), [])

    def test_g2_mord(self):
        for fonction, verrou, instruction in (
                ("noter_echec_authentification", "_verrou_auth", "attendre(1.0)"),
                ("noter_echec_authentification", "_verrou_auth", "time.sleep(1.0)"),
                ("journaliser_technique", "_verrou_journal", "attendre(1.0)"),
                ("marquer_activite", "_verrou_compteurs", "time.sleep(1.0)")):
            with self.subTest(fonction=fonction, verrou=verrou):
                muté = injecter(arbre_serveur(), fonction, instruction,
                                sous_verrou=verrou)
                self.assertNotEqual(problemes_verrous(muté), [])
        # Sans aucun verrou pris, les ancrages font échouer la garde.
        vide = ast.Module(body=[], type_ignores=[])
        self.assertNotEqual(problemes_verrous(vide), [])


# --------------------------------------------------------------------------
# Intégration : un vrai serveur, en bac à sable
# --------------------------------------------------------------------------

def requete(dossier, port, chemin, methode="GET", utilisateur=UTILISATEUR,
            mot_de_passe=MOT_DE_PASSE, corps=None, entetes=None):
    """(statut, corps) d'une requête sur un bac à sable. `utilisateur=None` :
    aucun en-tête Authorization."""
    contexte = ssl.create_default_context(
        cafile=os.path.join(dossier, "autorite.crt"))
    en_tetes = dict(entetes or {})
    if utilisateur is not None:
        en_tetes["Authorization"] = basic(utilisateur, mot_de_passe)
    connexion = http.client.HTTPSConnection(
        "127.0.0.1", port, context=contexte, timeout=30)
    try:
        connexion.request(methode, chemin, body=corps, headers=en_tetes)
        reponse = connexion.getresponse()
        return reponse.status, reponse.read()
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
class Essai(unittest.TestCase):
    """Un serveur réel, démarré une fois pour la classe. Chaque test repart d'un
    accès valide, qui remet le compteur à zéro : aucun ne dépend de l'ordre."""

    @classmethod
    def setUpClass(cls):
        cls.dossier, cls.port, cls.processus = demarrer_sandbox_court(
            {"mot_de_passe": HACHAGE_RAPIDE})
        # Le tube doit être vidé EN CONTINU : sous Windows son tampon est
        # petit, et un tube jamais lu fige toute requête qui journalise — seule
        # /sante, muette, répondrait encore, et A6 passerait au vert pour une
        # mauvaise raison (C7-T5).
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

    def setUp(self):
        self.assertEqual(self.demander("/cabinet")[0], 200)

    def demander(self, chemin, **options):
        return requete(self.dossier, self.port, chemin, **options)

    def refuser(self, mot_de_passe="faux"):
        return self.demander("/index.html", mot_de_passe=mot_de_passe)[0]

    def quinze_refus(self):
        """Quinze refus simultanés : la limitation les retarde chacun dans son
        propre fil, donc l'ensemble coûte au plus le plafond, pas la somme."""
        statuts = []
        fils = [threading.Thread(
            target=lambda: statuts.append(self.refuser()), daemon=True)
            for _ in range(15)]
        for fil in fils:
            fil.start()
        for fil in fils:
            fil.join(60)
        self.assertEqual(statuts, [401] * 15)

    def test_e1_le_onzieme_refus_dort_vraiment(self):
        durees = []
        for _ in range(SEUIL_DOCUMENTE + 1):
            debut = time.monotonic()
            self.assertEqual(self.refuser(), 401)
            durees.append(time.monotonic() - debut)
        for duree in durees[:3]:
            self.assertLess(duree, 1.0)
        # Borne inférieure seule : elle ne devient pas instable sur un agent
        # chargé (0,5 s nominales).
        self.assertGreaterEqual(durees[SEUIL_DOCUMENTE], 0.4, durees)

        details = detail_des_lignes(lire(self.dossier, "technique.log"),
                                    "AUTH_REFUSEE")
        forme = forme_detail_auth()
        refuses = [d for d in details if "identifiants=refuses" in d]
        self.assertGreaterEqual(len(refuses), SEUIL_DOCUMENTE + 1)
        self.assertTrue(refuses[-1].endswith("echecs=11 attente=0.5"), refuses[-1])
        for detail in details:
            self.assertIsNotNone(forme.fullmatch(detail), detail)
        self.assertIsNone(chercher_adresse(lire(self.dossier, "technique.log")))

    def test_e2_sante_intacte_apres_quinze_echecs(self):
        self.quinze_refus()
        technique = lire(self.dossier, "technique.log")
        journal = lire(self.dossier, "journal.log")
        debut = time.monotonic()
        for _ in range(10):
            statut, corps = self.demander("/sante", utilisateur=None)
            self.assertEqual(statut, 200)
            self.assertEqual(corps, b'{"etat":"ok"}')
        # Marge d'un facteur 10 sur un plafond de 3 s par requête ralentie : si
        # /sante traversait la limitation, dix requêtes coûteraient 30 s.
        self.assertLess(time.monotonic() - debut, 5.0)
        self.assertEqual(lire(self.dossier, "technique.log"), technique)
        self.assertEqual(lire(self.dossier, "journal.log"), journal)

    def test_e3_service_ordinaire_intact(self):
        self.quinze_refus()
        for chemin in ("/", "/index.html", "/style.css", "/script.js",
                       "/schema.json", "/version.json", "/cabinet"):
            with self.subTest(chemin=chemin):
                self.assertEqual(self.demander(chemin)[0], 200)
        nom = base64.b64encode("Bilan_essai-limitation.pdf".encode("utf-8")).decode("ascii")
        statut, corps = self.demander("/depot", methode="POST", corps=PDF,
                                      entetes={"X-Fichier": nom})
        self.assertEqual(statut, 200)
        self.assertIn("fichier", json.loads(corps.decode("utf-8")))
        self.assertEqual(self.demander("/index.html")[0], 200)

    def test_e4_un_depot_legitime_aboutit_pendant_que_des_refus_dorment(self):
        fils = [threading.Thread(target=self.refuser, daemon=True)
                for _ in range(15)]
        for fil in fils:
            fil.start()
        # Le temps que les derniers refus soient en sommeil (3 s au plus pour
        # les deux plus lents), sans autre synchronisation possible côté client.
        time.sleep(0.4)
        nom = base64.b64encode("Bilan_essai-concurrent.pdf".encode("utf-8")).decode("ascii")
        debut = time.monotonic()
        statut, _ = self.demander("/depot", methode="POST", corps=PDF,
                                  entetes={"X-Fichier": nom})
        duree = time.monotonic() - debut
        for fil in fils:
            fil.join(60)
        self.assertEqual(statut, 200)
        # Un dépôt n'attend aucun des refus endormis : il aboutit bien avant
        # le plafond de 3 s, qu'il dépasserait s'il en attendait un.
        self.assertLess(duree, 2.0)


if __name__ == "__main__":
    unittest.main()
