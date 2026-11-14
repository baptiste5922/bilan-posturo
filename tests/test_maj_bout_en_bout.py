"""Mise à jour de bout en bout (C5-T2a) : un vrai serveur, un vrai `maj.py`.

Chaque test installe un bac à sable complet (arbre du produit, certificats,
configuration, bilan fictif), démarre son `serveur.py` par le pilote d'essai, puis
applique de vrais paquets signés par des clés jetables. Le zip n'est pas fabriqué
par `faire-paquet.sh` : ces tests tournent donc aussi sous Windows.

Les délais de production (60 s de santé, 90 s d'arrêt) passent en PARAMÈTRE ; les
constantes elles-mêmes sont lues par un test de `tests/test_maj.py`.

Exigent `cryptography` pour les certificats du bac à sable : sautés sous le Python
3.9.6 du Mac, qui n'en a pas ; exécutés en intégration continue.

    python3 -m unittest tests.test_maj_bout_en_bout -v
"""

import base64
import contextlib
import datetime
import http.client
import io
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock

DOSSIER_TESTS = os.path.dirname(os.path.abspath(__file__))
PROJET = os.path.dirname(DOSSIER_TESTS)
sys.path.insert(0, os.path.join(PROJET, "serveur"))
sys.path.insert(0, DOSSIER_TESTS)
sys.path.insert(0, os.path.join(DOSSIER_TESTS, "outils"))

import faux_hebergement  # noqa: E402
import maj  # noqa: E402
import paquet_essai as pe  # noqa: E402
import paquet_signe  # noqa: E402
import pilote_essai  # noqa: E402
import serveur  # noqa: E402
from test_integration import chercher_adresse, cryptography_absente  # noqa: E402

# Délais des essais : assez courts pour qu'une suite entière tienne en quelques
# minutes, assez longs pour un runner chargé.
DELAI_SANTE = 8
DELAI_AUTO_CONTROLE = 40
PDF = b"%PDF-1.4\n1 0 obj\ncontenu du bilan fictif\n%%EOF\n"

# Les textes de technique.log de chaque bac, rassemblés avant sa suppression pour
# le contrôle d'ensemble de tearDownModule (A12).
TRACES = []
# Les deux journaux de chaque bac, pour le contrôle B21 : le chemin configuré de
# l'adresse de publication (« /essai/ ») n'y figure jamais ; seul l'hôte peut y être.
JOURNAUX = []

MOTIF_MAJ_LIGNE = re.compile(r"(?P<champ>[a-z]+)=(?P<valeur>\S+)")
CHAMPS_ADMIS = {"code", "cause", "resultat", "de", "vers", "cles"}


def problemes_de_traces(texte, racine):
    """Les défauts des lignes MAJ_* de technique.log (A12) ; liste vide si tout va
    bien. Fonction de module : un test la met en échec sur des lignes forgées."""
    problemes = []
    codes = set(maj.CODES_MAJ) | set(paquet_signe.CODES)
    nom_du_bac = os.path.basename(racine)
    for ligne in texte.splitlines():
        mots = ligne.split(" ")
        if len(mots) < 2 or not mots[1].startswith("MAJ_"):
            continue
        if mots[1] not in serveur.EVENEMENTS_TECHNIQUES:
            problemes.append("événement hors vocabulaire : " + ligne)
        for mot in mots[2:]:
            correspondance = MOTIF_MAJ_LIGNE.fullmatch(mot)
            if correspondance is None or correspondance.group("champ") not in CHAMPS_ADMIS:
                problemes.append("champ interdit %r : %s" % (mot, ligne))
            elif correspondance.group("champ") in ("code", "cause") \
                    and correspondance.group("valeur") not in codes:
                problemes.append("code hors vocabulaire : " + ligne)
        reste = ligne.partition(" ")[2]
        for interdit in (nom_du_bac, "/", "\\", ".zip", ".json"):
            if interdit in reste:
                problemes.append("%r dans la ligne : %s" % (interdit, ligne))
        adresse = chercher_adresse(ligne)
        if adresse:
            problemes.append(adresse)
    return problemes


def tearDownModule():
    # Levée explicite, jamais `assert` : il s'évaporerait sous python -O.
    problemes = []
    for racine, texte in TRACES:
        problemes.extend(problemes_de_traces(texte, racine))
    for racine, texte in JOURNAUX:
        if "/essai/" in texte or "stable.zip" in texte:
            problemes.append("le chemin de l'adresse de publication figure dans un journal du bac %s"
                             % os.path.basename(racine))
    if problemes:
        raise AssertionError("traces MAJ_* fautives :\n" + "\n".join(problemes[:10]))


@unittest.skipIf(cryptography_absente(),
                 "cryptography requis pour fabriquer les certificats du bac à sable")
class BacDeMiseAJour(unittest.TestCase):
    """Un bac complet avec son serveur en marche, version 1.1.0, clé A installée."""

    cles_installees = (pe.CLE_A,)

    def setUp(self):
        self.base = pe.fichiers_de_base("1.1.0", cles=self.cles_installees)
        self.racine = pe.fabriquer_installation(self.base)
        self.sortie = tempfile.mkdtemp(prefix="bilan-maj-sortie-")
        self.paquets = tempfile.mkdtemp(prefix="bilan-maj-paquets-")
        for dossier in (self.racine, self.sortie, self.paquets):
            self.addCleanup(shutil.rmtree, dossier, True)
        self.addCleanup(self.noter_les_traces)
        self.pilote = pilote_essai.PiloteProcessus(self.racine, self.sortie)
        self.addCleanup(self.pilote.arreter)
        with open(os.path.join(self.racine, "config.json")) as f:
            self.port = json.load(f)["port"]
        self.avant_demarrage()
        self.pilote.demarrer()
        if not maj.attendre_sante(self.port, 40):
            self.fail("le serveur du bac ne répond pas : " + self.pilote.console())
        self.courant = self.base

    # --- aides -------------------------------------------------------------------

    def avant_demarrage(self):
        """Pour les classes qui modifient l'installation avant que le serveur ne
        démarre."""

    def modifier_serveur(self, ancien, nouveau):
        """Remplace un texte, présent UNE fois, dans le serveur.py de l'installation
        (et non dans le paquet) : un serveur d'essai qui se comporte autrement à un
        endroit précis."""
        chemin = os.path.join(self.racine, "serveur", "serveur.py")
        with open(chemin, "rb") as f:
            source = f.read()
        if source.count(ancien) != 1:
            raise AssertionError("ancre trouvée %d fois : %r" % (source.count(ancien), ancien))
        with open(chemin, "wb") as f:
            f.write(source.replace(ancien, nouveau))

    def planter_pycache(self):
        """Un .pyc que personne n'a le droit de réutiliser (D12). Le pilote d'essai
        lance le serveur en -B, donc aucun n'existe jamais : sans celui-ci posé à
        la main, rien ne verrait l'effacement. Rend son chemin."""
        dossier = os.path.join(self.racine, "serveur", "__pycache__")
        os.makedirs(dossier, exist_ok=True)
        chemin = os.path.join(dossier, "serveur.cpython-39.pyc")
        with open(chemin, "wb") as f:
            f.write(b"\x00pyc de la version quittee")
        return dossier

    def noter_les_traces(self):
        TRACES.append((self.racine, self.technique()))
        for nom in ("journal.log", "technique.log"):
            try:
                with open(os.path.join(self.racine, nom), encoding="utf-8", errors="replace") as f:
                    JOURNAUX.append((self.racine, f.read()))
            except OSError:
                pass

    def technique(self):
        try:
            with open(os.path.join(self.racine, "technique.log"), encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""

    def lignes(self, jeton):
        return [l for l in self.technique().splitlines() if " %s" % jeton in l]

    def etat_json(self):
        return maj.lire_etat(self.racine)

    def trio(self, version, modifs=None, graine=pe.GRAINE_A, base=None, **kw):
        """Archive de la version `version`, bâtie sur `base` (par défaut ce qui est
        installé) avec ces modifications ; None supprime le fichier."""
        contenu = dict(self.courant if base is None else base)
        for relatif, octets in (modifs or {}).items():
            if octets is None:
                contenu.pop(relatif, None)
            else:
                contenu[relatif] = octets
        contenu = pe.avec_version(contenu, version)
        archive = pe.fabriquer_trio(self.paquets, contenu, version, graine=graine, **kw)
        self.dernier_contenu = contenu
        return archive

    def appliquer(self, archive, pilote=None, **kw):
        options = dict(calme_secondes=0, delai_sante=DELAI_SANTE,
                       delai_auto_controle=DELAI_AUTO_CONTROLE, delai_reponse=20,
                       delai_arret=30)
        options.update(kw)
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(io.StringIO()):
            code = maj.appliquer(self.racine, archive, pilote or self.pilote, **options)
        return code, sortie.getvalue()

    def requete(self, chemin, methode="GET", corps=None, entetes=None, utilisateur=True):
        contexte = ssl.create_default_context(
            cafile=os.path.join(self.racine, "autorite.crt"))
        connexion = http.client.HTTPSConnection(
            "127.0.0.1", self.port, context=contexte, timeout=60)
        en_tetes = dict(entetes or {})
        if utilisateur:
            en_tetes["Authorization"] = "Basic " + base64.b64encode(
                ("%s:%s" % (pe.UTILISATEUR, pe.MOT_DE_PASSE)).encode()).decode()
        try:
            connexion.request(methode, chemin, body=corps, headers=en_tetes)
            reponse = connexion.getresponse()
            return reponse.status, reponse.read()
        finally:
            connexion.close()

    def etat_http(self):
        statut, corps = self.requete("/etat", entetes={"Accept": "application/json"})
        self.assertEqual(statut, 200)
        return json.loads(corps.decode("utf-8"))

    def attendre_ligne(self, jeton, nombre=1, delai=15):
        limite = time.monotonic() + delai
        while time.monotonic() < limite:
            if len(self.lignes(jeton)) >= nombre:
                return
            time.sleep(0.05)
        self.fail("%r n'apparaît pas %d fois dans technique.log" % (jeton, nombre))

    def changees(self, avant):
        apres = pe.instantane(self.racine)
        return sorted(set(k for k in set(avant) | set(apres) if avant.get(k) != apres.get(k)))


# ==============================================================================
# A1 — une mise à jour cassée revient seule
# ==============================================================================

class Retour(BacDeMiseAJour):

    def test_quatre_variantes_cassees_reviennent_seules(self):
        variantes = (
            ("serveur-qui-sort-en-1", "1.2.0",
             {"serveur/serveur.py": pe.SERVEUR_QUI_SORT_EN_1}, "SANTE_MUETTE"),
            ("serveur-qui-ne-lie-jamais", "1.3.0",
             {"serveur/serveur.py": pe.SERVEUR_QUI_NE_LIE_JAMAIS}, "SANTE_MUETTE"),
            ("refus-racine-web-indeterminee", "1.4.0",
             {"serveur/serveur.py": pe.serveur_a_racine_web_indeterminee(
                 self.base["serveur/serveur.py"])}, "SANTE_MUETTE"),
            ("auto-controle-en-echec", "1.5.0",
             {"serveur/maj.py": pe.maj_a_auto_controle_en_echec(
                 self.base["serveur/maj.py"])}, "AUTO_CONTROLE_ECHOUE"),
        )
        for nom, version, modifs, cause in variantes:
            with self.subTest(variante=nom):
                pycache = self.planter_pycache()
                avant = pe.instantane(self.racine)
                journaux_avant = pe.contenu_des_journaux(self.racine)
                archive = self.trio(version, modifs, base=self.base)

                code, _ = self.appliquer(archive)

                self.assertEqual(code, 1)
                self.assertEqual(pe.instantane(self.racine), avant)
                self.assertTrue(maj.sante_repond(self.port),
                                "le serveur restauré ne répond pas")
                # D12 : le retour efface le .pyc de la version quittée.
                self.assertFalse(os.path.lexists(pycache))
                self.assertIn(
                    "MAJ_RETOUR cause=%s resultat=ok de=1.1.0 vers=%s" % (cause, version),
                    self.technique())
                etat = self.etat_json()
                self.assertEqual((etat["etape"], etat["resultat"]), ("repos", "revenue"))
                self.assertIn(version, etat["ecartees"])
                for nom_journal, octets in journaux_avant.items():
                    apres = pe.contenu_des_journaux(self.racine)[nom_journal]
                    self.assertTrue(apres.startswith(octets), nom_journal)

                # Le même trio, une seconde fois : écarté, sans arrêter le serveur.
                arrets = len(self.lignes("ARRET motif=mise-a-jour"))
                appels = list(self.pilote.appels)
                code, _ = self.appliquer(archive)
                self.assertEqual(code, 1)
                self.assertIn("MAJ_REFUSEE code=VERSION_ECARTEE", self.technique())
                self.assertEqual(len(self.lignes("ARRET motif=mise-a-jour")), arrets)
                self.assertEqual(self.pilote.appels, appels)
                self.assertTrue(maj.sante_repond(self.port))


# ==============================================================================
# A2 — un dépôt en cours n'est pas altéré
# ==============================================================================

class DepotEnCours(BacDeMiseAJour):

    def test_un_depot_commence_refuse_l_arret_et_aboutit(self):
        corps = PDF + os.urandom(4000)
        moitie = len(corps) // 2
        contexte = ssl.create_default_context(
            cafile=os.path.join(self.racine, "autorite.crt"))
        connexion = http.client.HTTPSConnection(
            "127.0.0.1", self.port, context=contexte, timeout=120)
        self.addCleanup(connexion.close)
        connexion.putrequest("POST", "/depot")
        connexion.putheader("Content-Length", str(len(corps)))
        connexion.putheader("X-Fichier", base64.b64encode(b"Bilan_lent.pdf").decode())
        connexion.putheader("Authorization", "Basic " + base64.b64encode(
            ("%s:%s" % (pe.UTILISATEUR, pe.MOT_DE_PASSE)).encode()).decode())
        connexion.endheaders()
        connexion.send(corps[:moitie])
        # Le serveur est dans do_POST, son corps à moitié lu. Le compte des dépôts
        # n'est lisible d'aucun autre processus : il n'y a rien à attendre d'autre
        # qu'un court délai. 0,5 s suffit, car appliquer met bien plus longtemps à
        # fabriquer le paquet, le contrôler et écrire sa demande d'arrêt.
        time.sleep(0.5)

        archive = self.trio("1.2.0")
        code, _ = self.appliquer(archive)

        self.assertEqual(code, 3)
        self.assertIn("MAJ_REPORTEE code=ARRET_REFUSE", self.technique())
        with open(os.path.join(self.racine, "mise-a-jour", "arret.reponse")) as f:
            reponse = json.load(f)
        self.assertEqual((reponse["verdict"], reponse["motif"]), ("refuse", "depot-en-cours"))

        connexion.send(corps[moitie:])
        reponse_http = connexion.getresponse()
        reponse_http.read()
        self.assertEqual(reponse_http.status, 200)
        dossier_bilans = os.path.join(self.racine, "bilans")
        with open(os.path.join(dossier_bilans, "Bilan_lent.pdf"), "rb") as f:
            self.assertEqual(f.read(), corps)
        self.assertEqual([n for n in os.listdir(dossier_bilans) if n.endswith(".part")], [])
        self.assertEqual(maj.lire_etat(self.racine)["version"], None)

        # Le calme passé (une seconde sans requête), la même mise à jour réussit.
        time.sleep(1.5)
        code, sortie = self.appliquer(archive, calme_secondes=1)
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.etat_json()["resultat"], "appliquee")

    def test_une_activite_recente_refuse_l_arret(self):
        archive = self.trio("1.2.0")
        self.requete("/cabinet")
        code, _ = self.appliquer(archive, calme_secondes=3600)
        self.assertEqual(code, 3)
        with open(os.path.join(self.racine, "mise-a-jour", "arret.reponse")) as f:
            self.assertEqual(json.load(f)["motif"], "activite")
        self.assertTrue(maj.sante_repond(self.port))


# ==============================================================================
# A3 — la configuration survit à trois montées
# ==============================================================================

class TroisMontees(BacDeMiseAJour):

    def test_le_cabinet_survit_a_trois_montees(self):
        possessions = ("config.json", "cle.pem", "certificat.pem", "autorite.crt",
                       "autorite-cle.pem", "bilans/Bilan_fictif.pdf",
                       "formulaire/images/cabinet/logo.png", "fichier-inconnu.txt")
        avant = pe.instantane(self.racine)
        journaux = pe.contenu_des_journaux(self.racine)
        for relatif in possessions:
            self.assertIn(relatif, avant)

        pycache = self.planter_pycache()
        schema = self.base["formulaire/schema.json"]
        etapes = (("1.2.0", {}), ("1.3.0", {"formulaire/schema.json": schema + b"\n"}),
                  ("1.4.0", {}))
        for version, modifs in etapes:
            archive = self.trio(version, modifs)
            code, sortie = self.appliquer(archive)
            self.assertEqual(code, 0, sortie)
            self.courant = self.dernier_contenu
            # D12 : la bascule efface le .pyc de la version quittée.
            self.assertFalse(os.path.lexists(pycache), version)
            pycache = self.planter_pycache()

        apres = pe.instantane(self.racine)
        for relatif in possessions:
            with self.subTest(fichier=relatif):
                self.assertEqual(apres[relatif], avant[relatif])
        for nom, octets in journaux.items():
            self.assertTrue(pe.contenu_des_journaux(self.racine)[nom].startswith(octets), nom)
        with open(os.path.join(self.racine, "formulaire", "version.json")) as f:
            self.assertEqual(json.load(f)["version"], "1.4.0")
        etat = self.etat_http()
        self.assertEqual((etat["maj_etape"], etat["maj_resultat"], etat["maj_version"]),
                         ("repos", "appliquee", "1.4.0"))
        self.assertEqual(len(self.lignes("MAJ_APPLIQUEE")), 3)
        # Chaque montée arrête le serveur PAR LA VOIE CONCERTÉE (jamais par la force).
        self.assertEqual(len(self.lignes("ARRET motif=mise-a-jour")), 3)
        self.assertEqual(problemes_de_traces(self.technique(), self.racine), [])
        with open(os.path.join(self.racine, "journal.log"), encoding="utf-8") as f:
            self.assertIn("MAJ_APPLIQUEE", f.read())


# ==============================================================================
# A4 — coupure en pleine bascule
# ==============================================================================

SCRIPT_ENFANT = r'''
import os, sys
serveur_dir, outils_dir, racine, archive, sortie, k, phase, commande = sys.argv[1:9]
sys.path.insert(0, serveur_dir)
sys.path.insert(0, outils_dir)
import maj, pilote_essai
k = int(k)
pilote = pilote_essai.PiloteProcessus(racine, sortie)
compteur = [0]
actif = [phase == "bascule"]
reel = os.replace
dossier_maj = os.path.join(racine, "mise-a-jour")
def faux(src, dst, *a, **kw):
    absolu = os.path.abspath(dst)
    if actif[0] and absolu.startswith(racine) and not absolu.startswith(dossier_maj):
        compteur[0] += 1
        if compteur[0] == k:
            os._exit(137)
    return reel(src, dst, *a, **kw)
os.replace = faux
if phase == "retour":
    origine = maj._restaurer
    def restaurer(*a, **kw):
        actif[0] = True
        return origine(*a, **kw)
    maj._restaurer = restaurer
if commande == "appliquer":
    code = maj.appliquer(racine, archive, pilote, calme_secondes=0, delai_sante=8,
                         delai_auto_controle=40, delai_reponse=20, delai_arret=30)
else:
    code = maj.reprendre_commande(racine, pilote, delai_sante=8)
sys.exit(code)
'''


class Interruption(BacDeMiseAJour):

    def modifs(self):
        resultat = {}
        for relatif in ("formulaire/style.css", "formulaire/script.js", "formulaire/index.html"):
            resultat[relatif] = self.base[relatif] + b"\n/* mise a jour d'essai */\n"
        return resultat

    def enfant(self, archive, k, phase, commande="appliquer"):
        return subprocess.run(
            [sys.executable, "-B", "-c", SCRIPT_ENFANT, os.path.join(PROJET, "serveur"),
             os.path.join(DOSSIER_TESTS, "outils"), self.racine, archive, self.sortie,
             str(k), phase, commande],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=180)

    def reprendre(self):
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(io.StringIO()):
            return maj.reprendre_commande(self.racine, self.pilote, delai_sante=DELAI_SANTE)

    def remplacements_pendant(self, travail):
        """Nombre de os.replace hors mise-a-jour/ faits par `travail()`."""
        compteur = [0]
        reel = os.replace
        dossier_maj = os.path.join(self.racine, "mise-a-jour")

        def compte(src, dst, *a, **kw):
            absolu = os.path.abspath(dst)
            if absolu.startswith(self.racine) and not absolu.startswith(dossier_maj):
                compteur[0] += 1
            return reel(src, dst, *a, **kw)

        with unittest.mock.patch("os.replace", compte):
            resultat = travail()
        return resultat, compteur[0]

    def test_coupure_pendant_la_bascule(self):
        archive = self.trio("1.2.0", self.modifs())
        # Fichiers changés : version.json, Mode_emploi.md et les trois ci-dessus.
        total = 5
        for k in (1, 3, total):
            with self.subTest(k=k):
                avant = pe.instantane(self.racine)
                enfant = self.enfant(archive, k, "bascule")
                self.assertEqual(enfant.returncode, 137, enfant.stderr.decode("utf-8", "replace"))
                self.assertNotEqual(pe.instantane(self.racine), avant,
                                    "la bascule n'a rien changé : la coupure n'a rien testé")
                self.assertEqual(self.etat_json()["etape"], "bascule")

                code = self.reprendre()

                self.assertEqual(code, 0)
                self.assertEqual(pe.instantane(self.racine), avant)
                self.assertTrue(maj.sante_repond(self.port))
                self.assertIn("MAJ_RETOUR cause=INTERROMPUE resultat=ok de=1.1.0 vers=1.2.0",
                              self.technique())
                etat = self.etat_json()
                self.assertEqual((etat["etape"], etat["resultat"]), ("repos", "revenue"))
                # Une coupure n'est pas un défaut du paquet : la version n'est pas écartée.
                self.assertEqual(etat["ecartees"], [])

    def test_coupure_pendant_le_retour_puis_deux_reprises(self):
        cassee = self.modifs()
        cassee["serveur/maj.py"] = pe.maj_a_auto_controle_en_echec(self.base["serveur/maj.py"])
        archive = self.trio("1.2.0", cassee)
        avant = pe.instantane(self.racine)

        # Six fichiers changent. Le retour en restaure deux avant d'être coupé.
        enfant = self.enfant(archive, 3, "retour")
        self.assertEqual(enfant.returncode, 137, enfant.stderr.decode("utf-8", "replace"))
        self.assertEqual(self.etat_json()["etape"], "retour")
        # Seconde interruption, cette fois pendant la reprise elle-même : elle ne
        # refait pas les deux premiers, en restaure un, puis est coupée.
        enfant = self.enfant(archive, 2, "retour", commande="reprendre")
        self.assertEqual(enfant.returncode, 137, enfant.stderr.decode("utf-8", "replace"))
        interrompu = pe.instantane(self.racine)
        self.assertNotEqual(interrompu, avant)

        code, remplaces = self.remplacements_pendant(self.reprendre)

        self.assertEqual(code, 0)
        self.assertEqual(pe.instantane(self.racine), avant)
        # Idempotence : la dernière reprise ne refait que ce qui reste.
        a_refaire = len([r for r in avant if avant[r] != interrompu.get(r)])
        self.assertEqual(remplaces, a_refaire)
        self.assertEqual(remplaces, 3)
        self.assertTrue(maj.sante_repond(self.port))


# ==============================================================================
# A5 — retour impossible
# ==============================================================================

class PiloteCorrupteur(pilote_essai.PiloteProcessus):
    """Abîme la sauvegarde au premier démarrage qui suit la bascule."""

    def __init__(self, *args, **kwargs):
        pilote_essai.PiloteProcessus.__init__(self, *args, **kwargs)
        self.cible = None

    def demarrer(self):
        if self.cible is not None:
            with open(self.cible, "wb") as f:
                f.write(b"abime par le test")
            self.cible = None
        pilote_essai.PiloteProcessus.demarrer(self)


class RetourImpossible(BacDeMiseAJour):

    def test_sauvegarde_abimee_laisse_echec_retour(self):
        pilote = PiloteCorrupteur(self.racine, self.sortie)
        pilote.processus = self.pilote.processus
        self.pilote = pilote
        self.addCleanup(pilote.arreter)
        pilote.cible = os.path.join(self.racine, "mise-a-jour", "sauvegarde", "serveur", "maj.py")
        archive = self.trio("1.2.0", {
            "serveur/maj.py": pe.maj_a_auto_controle_en_echec(self.base["serveur/maj.py"])})

        code, _ = self.appliquer(archive, pilote=pilote)

        self.assertEqual(code, 1)
        self.assertIn("MAJ_RETOUR cause=AUTO_CONTROLE_ECHOUE resultat=echec", self.technique())
        self.assertEqual(self.etat_json()["etape"], "echec-retour")
        # Le serveur a été relancé malgré tout, et la page d'état le dit.
        self.assertTrue(maj.attendre_sante(self.port, 20))
        self.assertEqual(self.etat_http()["maj_etape"], "echec-retour")

        # Un appliquer suivant est refusé tant que l'étape n'est pas revenue à repos.
        code, _ = self.appliquer(self.trio("1.3.0", base=self.base))
        self.assertEqual(code, 1)
        self.assertIn("MAJ_REFUSEE code=RETOUR_IMPOSSIBLE", self.technique())
        self.assertEqual(self.etat_json()["etape"], "echec-retour")


# ==============================================================================
# Retour manuel
# ==============================================================================

class RetourManuel(BacDeMiseAJour):

    def test_revenir_defait_et_ecarte(self):
        avant = pe.instantane(self.racine)
        code, _ = self.appliquer(self.trio("1.2.0"))
        self.assertEqual(code, 0)
        self.assertNotEqual(pe.instantane(self.racine), avant)

        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(io.StringIO()):
            code = maj.revenir(self.racine, self.pilote, delai_sante=DELAI_SANTE)

        self.assertEqual(code, 0)
        self.assertEqual(pe.instantane(self.racine), avant)
        self.assertIn("MAJ_RETOUR cause=RETOUR_MANUEL resultat=ok de=1.1.0 vers=1.2.0",
                      self.technique())
        self.assertEqual(self.etat_json()["ecartees"], ["1.2.0"])
        code, _ = self.appliquer(self.trio("1.2.0"))
        self.assertEqual(code, 1)
        self.assertIn("MAJ_REFUSEE code=VERSION_ECARTEE", self.technique())
        # Rien à défaire une seconde fois.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(maj.revenir(self.racine, self.pilote, delai_sante=DELAI_SANTE), 1)
        self.assertIn("MAJ_REFUSEE code=RETOUR_IMPOSSIBLE", self.technique())


# ==============================================================================
# A9 — les clés installées jugent, la rotation passe par un paquet
# ==============================================================================

class Rotation(BacDeMiseAJour):

    def test_un_paquet_ne_se_donne_pas_confiance_a_lui_meme(self):
        avant = pe.instantane(self.racine)
        # Signé par B, dont la clé figure dans le cles_publication.json EMBARQUÉ.
        hostile = self.trio("1.2.0", {"serveur/cles_publication.json":
                                      pe.liste_de_cles(pe.CLE_A, pe.CLE_B)},
                            graine=pe.GRAINE_B)
        code, _ = self.appliquer(hostile)
        self.assertEqual(code, 1)
        self.assertIn("MAJ_REFUSEE code=SIGNATURE_INVALIDE", self.technique())
        self.assertEqual(pe.instantane(self.racine), avant)
        self.assertEqual(self.pilote.appels, ["demarrer"])

    def test_rotation_en_deux_temps(self):
        # N+1 signé par A porte la liste {A, B} ; N+2 signé par B est alors accepté.
        liste = pe.liste_de_cles(pe.CLE_A, pe.CLE_B)
        code, sortie = self.appliquer(self.trio("1.2.0", {"serveur/cles_publication.json": liste}))
        self.assertEqual(code, 0, sortie)
        self.assertIn("MAJ_APPLIQUEE de=1.1.0 vers=1.2.0 cles=changees", self.technique())
        self.courant = self.dernier_contenu
        code, sortie = self.appliquer(self.trio("1.3.0", graine=pe.GRAINE_B))
        self.assertEqual(code, 0, sortie)
        self.assertIn("MAJ_APPLIQUEE de=1.2.0 vers=1.3.0", self.technique())


# ==============================================================================
# A14 — l'arrêt concerté, côté serveur réel
# ==============================================================================

class ArretConcerte(BacDeMiseAJour):

    def setUp(self):
        BacDeMiseAJour.setUp(self)
        # Le serveur n'obéit qu'à un dossier réservé : c'est le client qui le crée.
        maj.preparer_dossier_prive(self.racine)
        self.dossier_maj = os.path.join(self.racine, "mise-a-jour")

    def demander(self, **champs):
        demande = {"jeton": "ab" * 16, "calme_secondes": 0, "demarrage": False}
        demande.update(champs)
        serveur.ecrire_atomiquement(os.path.join(self.dossier_maj, "arret.demande"),
                                    json.dumps(demande).encode())
        return demande["jeton"]

    def lire_reponse(self, delai=10):
        chemin = os.path.join(self.dossier_maj, "arret.reponse")
        limite = time.monotonic() + delai
        while time.monotonic() < limite:
            try:
                with open(chemin) as f:
                    return json.load(f)
            except (OSError, ValueError):
                time.sleep(0.05)
        self.fail("aucune réponse d'arrêt")

    def test_demandes_invalides_ignorees_serveur_en_marche(self):
        chemin = os.path.join(self.dossier_maj, "arret.demande")

        def ecrire(contenu):
            with open(chemin, "w") as f:
                f.write(contenu)

        valide = {"jeton": "ab" * 16, "calme_secondes": 0, "demarrage": False}
        cas = {
            "malformee": lambda: ecrire("{pas du json"),
            "sans-jeton": lambda: ecrire(json.dumps(
                {"calme_secondes": 0, "demarrage": False})),
            "jeton-inconnu": lambda: ecrire(json.dumps(dict(valide, jeton="zz"))),
            "trop-grosse": lambda: ecrire(json.dumps(dict(valide, remplissage="x" * 2048))),
            "dossier": lambda: os.mkdir(chemin),
        }
        for nom, poser in cas.items():
            with self.subTest(cas=nom):
                poser()
                time.sleep(2.5)
                self.assertTrue(maj.sante_repond(self.port))
                self.assertIsNone(self.pilote.attendre_la_sortie(0.01))
                self.assertEqual(self.lignes("ARRET motif=mise-a-jour"), [])
                if os.path.isdir(chemin):
                    os.rmdir(chemin)
                elif os.path.exists(chemin):
                    os.remove(chemin)

    def test_demande_acceptee_sortie_en_0(self):
        jeton = self.demander()
        reponse = self.lire_reponse()
        self.assertEqual(reponse["jeton"], jeton)
        # « accepte » d'abord, « arrete » une fois ARRET écrit et le port libéré.
        limite = time.monotonic() + 15
        while reponse["verdict"] != "arrete" and time.monotonic() < limite:
            time.sleep(0.05)
            reponse = self.lire_reponse()
        self.assertEqual(reponse["verdict"], "arrete")
        self.assertEqual(self.pilote.attendre_la_sortie(15), 0)
        self.assertEqual(len(self.lignes("ARRET motif=mise-a-jour")), 1)
        self.assertTrue(maj.port_ferme(self.port))

    def test_refus_selon_l_activite_et_le_demarrage(self):
        self.requete("/cabinet")
        jeton = self.demander(calme_secondes=3600)
        reponse = self.lire_reponse()
        self.assertEqual((reponse["jeton"], reponse["verdict"], reponse["motif"]),
                         (jeton, "refuse", "activite"))
        os.remove(os.path.join(self.dossier_maj, "arret.reponse"))
        self.demander(demarrage=True)
        self.assertEqual(self.lire_reponse()["motif"], "activite")
        self.assertTrue(maj.sante_repond(self.port))


# ==============================================================================
# Réaudit C5-T2a : abandon après l'acceptation, sauvegarde gardée, dépôt figé,
# dossier non réservé, gardes du serveur
# ==============================================================================

class AbandonApresAcceptation(BacDeMiseAJour):
    """Le serveur a accepté l'arrêt puis quitté en code 0 : la tâche ne le relance
    pas. Chaque chemin d'abandon du client doit le relancer, /sante répondre à la
    fin (sonde S1b de l'audit)."""

    def avant_demarrage(self):
        if self._testMethodName == "test_arret_jamais_confirme":
            # La confirmation « arrete » se perd (écriture refusée, sous Windows).
            self.modifier_serveur(
                b'ecrire_reponse_arret(DOSSIER_MAJ, arret_concerte.jeton, "arrete", "aucun")',
                b"pass")

    def verifier_serveur_relance(self, avant, appels_avant=0):
        self.assertTrue(maj.attendre_sante(self.port, 40), "le serveur n'a pas été relancé")
        self.assertGreater(self.pilote.appels.count("demarrer"), appels_avant)
        self.assertEqual(pe.instantane(self.racine), avant)

    def test_arret_jamais_confirme(self):
        avant = pe.instantane(self.racine)
        code, _ = self.appliquer(self.trio("1.2.0"), delai_arret=3)
        self.assertEqual(code, 3)
        self.assertIn("MAJ_REPORTEE code=ARRET_SANS_REPONSE", self.technique())
        self.verifier_serveur_relance(avant, appels_avant=1)
        # La sauvegarde n'a pas été substituée : l'arrêt n'a pas abouti.
        self.assertFalse(os.path.lexists(os.path.join(self.racine, "mise-a-jour", "sauvegarde")))

    def test_etat_bascule_impossible_a_ecrire(self):
        reel = maj.ecrire_etat
        echecs = []

        def ecrire_etat(racine, **champs):
            if champs.get("etape") == "bascule" and not echecs:
                echecs.append(1)
                raise OSError(5, "écriture refusée par le test")
            return reel(racine, **champs)

        avant = pe.instantane(self.racine)
        with unittest.mock.patch.object(maj, "ecrire_etat", ecrire_etat):
            code, _ = self.appliquer(self.trio("1.2.0"))
        self.assertEqual(code, 1)
        self.assertEqual(echecs, [1])
        self.assertIn("MAJ_RETOUR cause=ECRITURE_IMPOSSIBLE resultat=ok de=1.1.0 vers=1.2.0",
                      self.technique())
        self.verifier_serveur_relance(avant, appels_avant=1)

    def test_exception_imprevue_entre_acceptation_et_bascule(self):
        def adopter(racine):
            raise RuntimeError("panne d'essai")

        avant = pe.instantane(self.racine)
        with unittest.mock.patch.object(maj, "adopter_sauvegarde", adopter):
            with self.assertRaises(RuntimeError):
                self.appliquer(self.trio("1.2.0"))
        self.verifier_serveur_relance(avant, appels_avant=1)

    def test_interruption_au_clavier_pendant_le_repit_apres_l_arret(self):
        avant = pe.instantane(self.racine)
        reel = maj.time.sleep

        def dormir(secondes):
            if secondes == maj.PAUSE_APRES_ARRET_SECONDES:
                raise KeyboardInterrupt()
            return reel(secondes)

        with unittest.mock.patch.object(maj.time, "sleep", dormir):
            with self.assertRaises(KeyboardInterrupt):
                self.appliquer(self.trio("1.2.0"))
        self.verifier_serveur_relance(avant, appels_avant=1)


class SauvegardeApresReport(BacDeMiseAJour):

    def test_un_report_ne_detruit_pas_le_retour_possible(self):
        # Sonde S2 de l'audit : 1.2.0 appliquée ; une requête non authentifiée puis
        # un second appliquer reporté ; revenir doit encore fonctionner.
        initial = pe.instantane(self.racine)
        code, _ = self.appliquer(self.trio("1.2.0"))
        self.assertEqual(code, 0)
        self.courant = self.dernier_contenu
        statut, _ = self.requete("/", utilisateur=False)
        self.assertEqual(statut, 401)

        code, _ = self.appliquer(self.trio("1.3.0"), calme_secondes=3600)

        self.assertEqual(code, 3)
        self.assertIn("MAJ_REPORTEE code=ARRET_REFUSE", self.technique())
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(maj.revenir(self.racine, self.pilote, delai_sante=DELAI_SANTE), 0)
        self.assertEqual(pe.instantane(self.racine), initial)
        self.assertTrue(maj.sante_repond(self.port))


class BacAInactiviteCourte(BacDeMiseAJour):
    """Un bac dont le délai d'inactivité des connexions est réduit (120 s en
    production), pour éprouver ce qui se passe quand il expire."""

    INACTIVITE_BAC = 8

    def avant_demarrage(self):
        self.modifier_serveur(
            b"INACTIVITE_CONNEXION_SECONDES = 120\n",
            ("INACTIVITE_CONNEXION_SECONDES = %d\n" % self.INACTIVITE_BAC).encode())

    def ouvrir_depot(self, corps, nom):
        contexte = ssl.create_default_context(cafile=os.path.join(self.racine, "autorite.crt"))
        connexion = http.client.HTTPSConnection("127.0.0.1", self.port, context=contexte,
                                                timeout=120)
        self.addCleanup(connexion.close)
        connexion.putrequest("POST", "/depot")
        connexion.putheader("Content-Length", str(len(corps)))
        connexion.putheader("X-Fichier", base64.b64encode(nom).decode())
        connexion.putheader("Authorization", "Basic " + base64.b64encode(
            ("%s:%s" % (pe.UTILISATEUR, pe.MOT_DE_PASSE)).encode()).decode())
        connexion.endheaders()
        return connexion


class DepotFige(BacAInactiviteCourte):
    """Un dépôt qui ne progresse plus cesse de compter comme « en cours »
    (inactivité de 8 s dans ce bac, 120 s en production) ; un dépôt lent mais
    actif aboutit toujours, quelle que soit sa durée totale.

    8 s et non 2 : le premier appliquer (fabriquer le paquet, le contrôler,
    l'extraire, sauvegarder une centaine de fichiers) doit atteindre sa demande
    d'arrêt AVANT l'expiration, y compris sur un exécuteur aux disques lents. Si cet
    essai échoue un jour, le capturer : ne jamais le relancer à l'aveugle."""

    def test_un_depot_fige_ne_bloque_pas_les_mises_a_jour(self):
        connexion = self.ouvrir_depot(PDF + b"x" * 1000, b"Bilan_fige.pdf")
        connexion.send(PDF[:20])
        silence_depuis = time.monotonic()
        # Il se tait. Tant que le serveur le tient pour « en cours », il refuse.
        code, _ = self.appliquer(self.trio("1.2.0"))
        refus_apres = time.monotonic() - silence_depuis
        self.assertEqual(
            code, 3, "le premier appliquer a pris %.1f s pour une inactivité de %d s"
            % (refus_apres, self.INACTIVITE_BAC))
        self.assertIn("MAJ_REPORTEE code=ARRET_REFUSE", self.technique())
        # Silence complet : plus de dix secondes sans un octet, soit deux de plus
        # que le délai du bac.
        time.sleep(max(0.0, silence_depuis + self.INACTIVITE_BAC + 2.5 - time.monotonic()))
        code, sortie = self.appliquer(self.trio("1.2.0"))
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.etat_json()["resultat"], "appliquee")

    def test_un_depot_lent_mais_actif_aboutit(self):
        morceau = 600
        corps = PDF + os.urandom(12 * morceau - len(PDF))
        connexion = self.ouvrir_depot(corps, b"Bilan_lent_actif.pdf")
        debut = time.monotonic()
        for i in range(0, len(corps), morceau):
            connexion.send(corps[i:i + morceau])
            time.sleep(0.8)            # jamais plus de 0,8 s de silence
        duree = time.monotonic() - debut
        reponse = connexion.getresponse()
        reponse.read()
        self.assertEqual(reponse.status, 200)
        # La durée totale dépasse le délai d'inactivité : seul le silence compte.
        self.assertGreater(duree, self.INACTIVITE_BAC + 1)
        with open(os.path.join(self.racine, "bilans", "Bilan_lent_actif.pdf"), "rb") as f:
            self.assertEqual(f.read(), corps)


class ExpirationDesConnexions(BacAInactiviteCourte):
    """Ce que l'expiration écrit, vue dans un bac : une connexion jamais utilisée
    (un navigateur en ouvre une par anticipation) ne laisse AUCUNE ligne ; un dépôt
    qui s'arrête laisse la trace fermée d'un transfert interrompu, sans adresse
    dans technique.log."""

    INACTIVITE_BAC = 2

    def journal(self):
        with open(os.path.join(self.racine, "journal.log"), encoding="utf-8") as f:
            return f.read()

    def test_connexion_preouverte_et_jamais_utilisee_est_muette(self):
        technique_avant, journal_avant = self.technique(), self.journal()
        contexte = ssl.create_default_context(cafile=os.path.join(self.racine, "autorite.crt"))
        brut = socket.create_connection(("127.0.0.1", self.port), 10)
        tls = contexte.wrap_socket(brut, server_hostname="127.0.0.1")
        self.addCleanup(tls.close)
        time.sleep(self.INACTIVITE_BAC + 1.5)
        self.assertEqual(self.technique(), technique_avant)
        self.assertEqual(self.journal(), journal_avant)
        self.assertTrue(maj.sante_repond(self.port))

    def test_depot_qui_s_arrete_est_un_transfert_interrompu(self):
        connexion = self.ouvrir_depot(PDF + b"x" * 1000, b"Bilan_coupe.pdf")
        connexion.send(PDF[:20])
        time.sleep(self.INACTIVITE_BAC + 1.5)
        technique = self.technique()
        self.assertIn("DEPOT refus motif=transfert-interrompu", technique)
        self.assertNotIn("code=0", technique)
        self.assertNotIn("timed out", technique)
        self.assertIsNone(chercher_adresse(technique))
        # La page d'état, qui circule en capture, n'en dit pas plus.
        etat = self.etat_http()
        self.assertIsNone(chercher_adresse("\n".join(etat["journal_technique"])))
        # Le journal nominatif garde la ligne de la réponse, pas « Request timed out ».
        self.assertNotIn("timed out", self.journal())
        bilans = os.path.join(self.racine, "bilans")
        self.assertEqual([n for n in os.listdir(bilans) if n.endswith(".part")], [])
        self.assertNotIn("Bilan_coupe.pdf", os.listdir(bilans))


class ObeissanceAuDossier(BacDeMiseAJour):

    def test_demande_dans_un_dossier_non_reserve_est_ignoree(self):
        dossier = os.path.join(self.racine, "mise-a-jour")
        os.mkdir(dossier)
        if os.name != "nt":
            os.chmod(dossier, 0o777)         # n'importe qui peut y écrire
        serveur.ecrire_atomiquement(os.path.join(dossier, "arret.demande"), json.dumps(
            {"jeton": "ab" * 16, "calme_secondes": 0, "demarrage": False}).encode())
        time.sleep(3)
        self.assertTrue(maj.sante_repond(self.port))
        self.assertIsNone(self.pilote.attendre_la_sortie(0.01))
        self.assertEqual(self.lignes("ARRET motif=mise-a-jour"), [])
        self.assertFalse(os.path.exists(os.path.join(dossier, "arret.reponse")))
        self.assertFalse(os.path.exists(os.path.join(dossier, "arret.demande")))
        with open(os.path.join(self.racine, "journal.log"), encoding="utf-8") as f:
            self.assertIn("demande d'arrêt ignorée", f.read())

    def test_la_meme_demande_est_obeie_une_fois_le_dossier_reserve(self):
        maj.preparer_dossier_prive(self.racine)
        serveur.ecrire_atomiquement(
            os.path.join(self.racine, "mise-a-jour", "arret.demande"), json.dumps(
                {"jeton": "ab" * 16, "calme_secondes": 0, "demarrage": False}).encode())
        self.assertEqual(self.pilote.attendre_la_sortie(20), 0)
        self.assertEqual(len(self.lignes("ARRET motif=mise-a-jour")), 1)


class GardesDuServeur(BacDeMiseAJour):

    def test_une_demande_perimee_n_arrete_pas_le_serveur_relance(self):
        # X15 : une demande laissée par une coupure entre son écriture et sa lecture
        # arrêterait le serveur relancé par la tâche dans la seconde, en code 0.
        maj.preparer_dossier_prive(self.racine)
        self.pilote.arreter()
        serveur.ecrire_atomiquement(
            os.path.join(self.racine, "mise-a-jour", "arret.demande"), json.dumps(
                {"jeton": "cd" * 16, "calme_secondes": 0, "demarrage": False}).encode())
        self.pilote.demarrer()
        self.assertTrue(maj.attendre_sante(self.port, 40), self.pilote.console())
        time.sleep(3)
        self.assertTrue(maj.sante_repond(self.port))
        self.assertIsNone(self.pilote.attendre_la_sortie(0.01))
        self.assertNotIn("ARRET motif=mise-a-jour", self.technique())
        self.assertFalse(os.path.exists(os.path.join(self.racine, "mise-a-jour", "arret.demande")))


class DepotCommenceApresLaDecision(BacDeMiseAJour):

    def avant_demarrage(self):
        # Entre la décision et l'arrêt de la boucle, le serveur sert encore : trois
        # secondes pour qu'un dépôt commence.
        self.modifier_serveur(
            b"                arret.evenement.set()\n                serveur.shutdown()\n",
            b"                arret.evenement.set()\n                time.sleep(3)\n"
            b"                serveur.shutdown()\n")

    def test_un_depot_commence_apres_la_decision_est_attendu(self):
        # X9 : sans attendre_fin_depots, la sortie du processus tuerait ce dépôt.
        dossier = os.path.join(self.racine, "mise-a-jour")
        maj.preparer_dossier_prive(self.racine)
        serveur.ecrire_atomiquement(os.path.join(dossier, "arret.demande"), json.dumps(
            {"jeton": "ab" * 16, "calme_secondes": 0, "demarrage": False}).encode())
        chemin = os.path.join(dossier, "arret.reponse")
        limite = time.monotonic() + 15
        accepte = False
        while time.monotonic() < limite and not accepte:
            try:
                with open(chemin) as f:
                    accepte = json.load(f).get("verdict") == "accepte"
            except (OSError, ValueError):
                pass
            time.sleep(0.02)
        self.assertTrue(accepte, "l'arrêt n'a pas été accepté")

        corps = PDF + os.urandom(3000)
        contexte = ssl.create_default_context(cafile=os.path.join(self.racine, "autorite.crt"))
        connexion = http.client.HTTPSConnection("127.0.0.1", self.port, context=contexte,
                                                timeout=60)
        self.addCleanup(connexion.close)
        connexion.putrequest("POST", "/depot")
        connexion.putheader("Content-Length", str(len(corps)))
        connexion.putheader("X-Fichier", base64.b64encode(b"Bilan_apres_decision.pdf").decode())
        connexion.putheader("Authorization", "Basic " + base64.b64encode(
            ("%s:%s" % (pe.UTILISATEUR, pe.MOT_DE_PASSE)).encode()).decode())
        connexion.endheaders()
        connexion.send(corps[:1500])
        time.sleep(4.5)            # la boucle s'arrête pendant ce temps, dépôt en cours
        connexion.send(corps[1500:])
        reponse = connexion.getresponse()
        reponse.read()
        self.assertEqual(reponse.status, 200)
        with open(os.path.join(self.racine, "bilans", "Bilan_apres_decision.pdf"), "rb") as f:
            self.assertEqual(f.read(), corps)
        self.assertEqual(self.pilote.attendre_la_sortie(20), 0)
        self.assertEqual(len(self.lignes("ARRET motif=mise-a-jour")), 1)


# ==============================================================================
# C5-T2b — `verifier` : le client va chercher lui-même, et applique à son heure
# ==============================================================================

HEURE_DU_JOUR = datetime.datetime(2026, 11, 16, 12, 0, 0)
HEURE_DE_NUIT = datetime.datetime(2026, 11, 16, 23, 0, 0)
DELAIS_ESSAI = {"sante": DELAI_SANTE, "auto_controle": DELAI_AUTO_CONTROLE, "reponse": 20,
                "arret": 30, "operation": 10, "manifeste": 20, "archive": 60}
ENTETES_DE_REQUETE = ["Accept-Encoding", "Connection", "Host", "User-Agent"]
CHEMIN_PUBLIE = "/essai/stable.zip"


def sans_la_configuration(instantane):
    """L'arbre du bac hors config.json : un test qui reconfigure le client entre deux
    instantanés change ce fichier, et lui seul."""
    return dict((k, v) for k, v in instantane.items() if k != "config.json")


class BacVerifier(BacDeMiseAJour):
    """Le bac complet, plus un faux hébergement HTTPS qui sert les trios fabriqués."""

    def setUp(self):
        BacDeMiseAJour.setUp(self)
        self.heb = faux_hebergement.FauxHebergement()
        self.addCleanup(self.heb.arreter)
        self.contexte = faux_hebergement.contexte_client()
        self.configurer()

    def configurer(self, **bloc):
        chemin = os.path.join(self.racine, "config.json")
        with open(chemin) as f:
            config = json.load(f)
        reglage = {"client": "cabinet-01", "adresse": self.heb.adresse(CHEMIN_PUBLIE),
                   "plage": "00:00-23:59", "au_demarrage": False}
        reglage.update(bloc)
        config["mise_a_jour"] = dict((k, v) for k, v in reglage.items() if v is not None)
        with open(chemin, "w") as f:
            json.dump(config, f)

    def verifier(self, maintenant=HEURE_DU_JOUR, depuis_demarrage=100000, pilote=None,
                 delais=None, contexte=None):
        options = dict(DELAIS_ESSAI)
        options.update(delais or {})
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(io.StringIO()):
            return maj.verifier(self.racine, pilote or self.pilote, maintenant=maintenant,
                                depuis_demarrage=lambda: depuis_demarrage,
                                contexte=contexte or self.contexte, delais=options)

    def publier(self, version, modifs=None, **kw):
        archive = self.trio(version, modifs, **kw)
        self.heb.publier(archive)
        return archive


class VerifierMontee(BacVerifier):
    """B1 : une montée complète par `verifier`, trois requêtes, rien de plus."""

    def test_une_montee_complete(self):
        self.publier("1.2.0", {"formulaire/style.css": self.base["formulaire/style.css"]
                               + b"\n/* verifier */\n"})
        avant = pe.instantane(self.racine)
        privees = dict((nom, avant[nom]) for nom in avant if nom in (
            "config.json", "certificat.pem", "cle.pem", "autorite.crt", "autorite-cle.pem",
            "formulaire/images/cabinet/logo.png", "bilans/Bilan_fictif.pdf",
            "fichier-inconnu.txt"))
        self.assertEqual(len(privees), 8)
        journaux = pe.contenu_des_journaux(self.racine)

        code = self.verifier()

        self.assertEqual(code, 0)
        self.assertEqual(self.heb.chemins(), [
            CHEMIN_PUBLIE + ".manifeste.json", CHEMIN_PUBLIE + ".manifeste.sig", CHEMIN_PUBLIE])
        for requete in self.heb.requetes:
            self.assertEqual(requete["methode"], "GET")
            self.assertEqual(requete["longueur_du_corps"], 0)
            self.assertEqual(sorted(n for n, _ in requete["entetes"]), ENTETES_DE_REQUETE)
        self.assertEqual(maj.lire_version_installee(self.racine), "1.2.0")
        self.assertTrue(maj.sante_repond(self.port))
        apres = pe.instantane(self.racine)
        for nom, empreinte in privees.items():
            self.assertEqual(apres[nom], empreinte, nom)
        for nom_journal, octets in journaux.items():
            self.assertTrue(pe.contenu_des_journaux(self.racine)[nom_journal].startswith(octets))
        self.assertIn("MAJ_CONTROLE resultat=disponible de=1.1.0 vers=1.2.0", self.technique())
        self.assertIn("MAJ_APPLIQUEE de=1.1.0 vers=1.2.0", self.technique())
        etat = self.etat_json()
        self.assertEqual((etat["etape"], etat["resultat"], etat["attente"], etat["arret_en_cours"]),
                         ("repos", "appliquee", None, False))
        self.assertEqual(os.listdir(os.path.join(self.racine, "mise-a-jour", "reception")), [])
        # L'adresse n'est dans aucun journal, hôte compris dans technique.log.
        for nom_journal, octets in pe.contenu_des_journaux(self.racine).items():
            self.assertNotIn(b"/essai", octets, nom_journal)
            self.assertNotIn(b"stable.zip", octets, nom_journal)
        self.assertNotIn("127.0.0.1", self.technique())

    def test_etat_http_porte_la_date_du_dernier_controle(self):
        self.publier("1.1.0")
        self.assertEqual(self.verifier(), 0)
        etat = self.etat_http()
        self.assertEqual(etat["maj_controle_le"], "2026-11-16T12:00:00")
        self.assertEqual(list(etat), list(serveur.CLES_ETAT))
        statut, corps = self.requete("/etat", entetes={"Accept": "text/html"})
        self.assertEqual(statut, 200)
        self.assertIn("dernier contrôle le 2026-11-16 12:00:00", corps.decode("utf-8"))
        for nom, texte in (("json", json.dumps(etat)), ("html", corps.decode("utf-8"))):
            self.assertNotIn("/essai", texte, nom)
            self.assertNotIn("stable.zip", texte, nom)

    def test_une_version_deja_installee_ne_touche_a_rien(self):
        self.publier("1.1.0")
        avant = pe.instantane(self.racine)
        self.assertEqual(self.verifier(), 0)
        self.assertEqual(pe.instantane(self.racine), avant)
        self.assertEqual(self.pilote.appels.count("demarrer"), 1)     # celui de setUp

    @unittest.skipIf(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
                     "droits POSIX, hors root")
    def test_le_client_n_ouvre_jamais_le_dossier_des_bilans(self):
        # B16 : aucune donnée de santé n'est lue, comptée ni listée.
        self.publier("1.2.0")
        dossier = os.path.join(self.racine, "bilans")
        os.chmod(dossier, 0o000)
        self.addCleanup(os.chmod, dossier, 0o755)
        code = self.verifier()
        os.chmod(dossier, 0o755)
        self.assertEqual(code, 0)
        self.assertEqual(maj.lire_version_installee(self.racine), "1.2.0")
        self.assertTrue(maj.sante_repond(self.port))


class VerifierEligibilite(BacVerifier):
    """B8 : hors plage, au démarrage, après une requête. Le serveur reste juge."""

    def test_hors_plage_sans_demarrage_rien_n_est_demande(self):
        self.configurer(plage="20:00-07:00", au_demarrage=False)
        self.publier("1.2.0")
        avant = pe.instantane(self.racine)
        self.assertEqual(self.verifier(HEURE_DU_JOUR), 3)
        self.assertIn("MAJ_REPORTEE code=HORS_PLAGE", self.technique())
        self.assertFalse(os.path.lexists(os.path.join(self.racine, "mise-a-jour", "arret.demande")))
        self.assertFalse(os.path.lexists(os.path.join(self.racine, "mise-a-jour", "prepare")))
        self.assertEqual(pe.instantane(self.racine), avant)
        etat = self.etat_json()
        self.assertEqual((etat["etape"], etat["resultat"], etat["code"]),
                         ("repos", "reportee", "HORS_PLAGE"))
        self.assertTrue(maj.sante_repond(self.port))

    def test_demarrage_depasse_c_est_le_meme_resultat(self):
        self.configurer(plage="20:00-07:00", au_demarrage=True)
        self.publier("1.2.0")
        self.assertEqual(self.verifier(HEURE_DU_JOUR, depuis_demarrage=901), 3)
        self.assertIn("MAJ_REPORTEE code=HORS_PLAGE", self.technique())
        self.assertFalse(os.path.lexists(os.path.join(self.racine, "mise-a-jour", "prepare")))

    def test_un_demarrage_recent_sans_requete_est_applique(self):
        self.configurer(plage="20:00-07:00", au_demarrage=True)
        self.publier("1.2.0")
        self.assertEqual(self.verifier(HEURE_DU_JOUR, depuis_demarrage=120), 0)
        self.assertIn("MAJ_APPLIQUEE de=1.1.0 vers=1.2.0", self.technique())
        self.assertEqual(maj.lire_version_installee(self.racine), "1.2.0")
        self.assertTrue(maj.sante_repond(self.port))

    def test_apres_une_requete_le_serveur_refuse_le_demarrage(self):
        self.configurer(plage="20:00-07:00", au_demarrage=True)
        self.publier("1.2.0")
        statut, _ = self.requete("/cabinet")
        self.assertIn(statut, (200, 404))
        avant = pe.instantane(self.racine)
        self.assertEqual(self.verifier(HEURE_DU_JOUR, depuis_demarrage=120), 3)
        self.assertIn("MAJ_REPORTEE code=ARRET_REFUSE", self.technique())
        with open(os.path.join(self.racine, "mise-a-jour", "arret.reponse")) as f:
            reponse = json.load(f)
        self.assertEqual((reponse["verdict"], reponse["motif"]), ("refuse", "activite"))
        self.assertEqual(pe.instantane(self.racine), avant)
        self.assertTrue(maj.sante_repond(self.port))
        self.assertFalse(self.etat_json()["arret_en_cours"])
        # Rien n'est perdu : la version attend, sans nouveau téléchargement.
        self.assertEqual(self.etat_json()["attente"], "1.2.0")
        trois = len(self.heb.requetes)
        plus_tard = HEURE_DU_JOUR + datetime.timedelta(minutes=30)
        self.assertEqual(self.verifier(plus_tard, depuis_demarrage=100000), 3)
        self.assertEqual(len(self.heb.requetes), trois)

    def test_dans_la_plage_le_calme_est_exige(self):
        self.configurer(plage="20:00-07:00", calme_minutes=30)
        self.publier("1.2.0")
        self.requete("/cabinet")
        self.assertEqual(self.verifier(HEURE_DE_NUIT), 3)
        with open(os.path.join(self.racine, "mise-a-jour", "arret.reponse")) as f:
            reponse = json.load(f)
        self.assertEqual((reponse["verdict"], reponse["motif"]), ("refuse", "activite"))


class VerifierDesactiveEtCoupure(BacVerifier):
    """B11 : même désactivé, `verifier` défait ce qu'une coupure a laissé."""

    def test_un_etat_a_la_bascule_est_defait_meme_sans_adresse(self):
        archive = self.trio("1.2.0", {f: self.base[f] + b"\n/* essai */\n" for f in (
            "formulaire/style.css", "formulaire/script.js", "formulaire/index.html")})
        avant = pe.instantane(self.racine)
        enfant = subprocess.run(
            [sys.executable, "-B", "-c", SCRIPT_ENFANT, os.path.join(PROJET, "serveur"),
             os.path.join(DOSSIER_TESTS, "outils"), self.racine, archive, self.sortie,
             "3", "bascule", "appliquer"],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=180)
        self.assertEqual(enfant.returncode, 137, enfant.stderr.decode("utf-8", "replace"))
        self.assertEqual(self.etat_json()["etape"], "bascule")
        self.assertNotEqual(pe.instantane(self.racine), avant)
        self.configurer(adresse="")

        code = self.verifier()

        self.assertEqual(code, 3)
        self.assertIn("MAJ_RETOUR cause=INTERROMPUE resultat=ok de=1.1.0 vers=1.2.0",
                      self.technique())
        self.assertIn("MAJ_REPORTEE code=DESACTIVEE", self.technique())
        self.assertEqual(sans_la_configuration(pe.instantane(self.racine)),
                         sans_la_configuration(avant))
        self.assertTrue(maj.sante_repond(self.port))
        self.assertEqual(self.heb.requetes, [])
        self.assertEqual(self.etat_json()["ecartees"], [])


SCRIPT_ENFANT_VERIFIER = r'''
import datetime, os, sys
serveur_dir, outils_dir, racine, sortie, autorite = sys.argv[1:6]
sys.path.insert(0, serveur_dir)
sys.path.insert(0, outils_dir)
import maj, pilote_essai, faux_hebergement
pilote = pilote_essai.PiloteProcessus(racine, sortie)
# Juste après la lecture de « accepte » (et de « arrete ») : le serveur a quitté en
# code 0, la sauvegarde courante n'est pas encore substituée, aucun fichier du
# cabinet n'a été touché. C'est là que ce processus meurt.
maj.adopter_sauvegarde = lambda racine_: os._exit(137)
code = maj.verifier(
    racine, pilote, maintenant=datetime.datetime(2026, 11, 16, 12, 0, 0),
    depuis_demarrage=lambda: 100000, contexte=faux_hebergement.contexte_client(autorite),
    delais={"sante": 8, "auto_controle": 40, "reponse": 20, "arret": 30,
            "operation": 10, "manifeste": 20, "archive": 60})
sys.exit(code)
'''


class PiloteQuiNeRelancePas(pilote_essai.PiloteProcessus):
    """Un pilote dont /Run n'a aucun effet : la santé reste muette."""

    def demarrer(self):
        self.appels.append("demarrer")


class VerifierMortApresAcceptation(BacVerifier):
    """R1 : `maj.py` meurt entre l'acceptation de l'arrêt et la bascule."""

    def mourir_apres_acceptation(self):
        self.publier("1.2.0")
        enfant = subprocess.run(
            [sys.executable, "-B", "-c", SCRIPT_ENFANT_VERIFIER, os.path.join(PROJET, "serveur"),
             os.path.join(DOSSIER_TESTS, "outils"), self.racine, self.sortie,
             os.path.join(self.racine, "autorite.crt")],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=180)
        self.assertEqual(enfant.returncode, 137, enfant.stderr.decode("utf-8", "replace"))
        # Le serveur a accepté et quitté : plus personne n'écoute.
        limite = time.monotonic() + 15
        while not maj.port_ferme(self.port) and time.monotonic() < limite:
            time.sleep(0.1)
        self.assertTrue(maj.port_ferme(self.port), "le serveur n'a pas quitté")
        etat = self.etat_json()
        self.assertEqual((etat["etape"], etat["arret_en_cours"], etat["attente"]),
                         ("preparee", True, "1.2.0"))

    def test_le_passage_suivant_relance_le_serveur_sans_toucher_un_fichier(self):
        avant = pe.instantane(self.racine)
        self.mourir_apres_acceptation()
        self.assertEqual(pe.instantane(self.racine), avant)
        # Hors plage et sans démarrage : on ne regarde QUE la reprise.
        self.configurer(plage="20:00-07:00", au_demarrage=False)

        code = self.verifier(HEURE_DU_JOUR)

        self.assertEqual(code, 3)
        self.assertTrue(maj.sante_repond(self.port), "le serveur n'a pas été relancé")
        self.assertIn("MAJ_REPORTEE code=INTERROMPUE", self.technique())
        self.assertFalse(self.etat_json()["arret_en_cours"])
        self.assertEqual(sans_la_configuration(pe.instantane(self.racine)),
                         sans_la_configuration(avant))

    def test_une_sante_muette_garde_le_drapeau_jusqu_a_ce_qu_un_passage_relance(self):
        self.mourir_apres_acceptation()
        self.configurer(plage="20:00-07:00", au_demarrage=False)
        muet = PiloteQuiNeRelancePas(self.racine, self.sortie)

        self.verifier(HEURE_DU_JOUR, pilote=muet, delais={"sante": 2})

        self.assertTrue(self.etat_json()["arret_en_cours"], "le passage suivant doit réessayer")
        self.assertIn("MAJ_REPORTEE code=INTERROMPUE", self.technique())
        self.assertFalse(maj.sante_repond(self.port))
        self.verifier(HEURE_DU_JOUR)
        self.assertTrue(maj.sante_repond(self.port))
        self.assertFalse(self.etat_json()["arret_en_cours"])

    def test_un_passage_suivant_dans_la_plage_applique_la_version(self):
        self.mourir_apres_acceptation()
        self.assertEqual(self.verifier(HEURE_DU_JOUR), 0)
        self.assertIn("MAJ_REPORTEE code=INTERROMPUE", self.technique())
        self.assertIn("MAJ_APPLIQUEE de=1.1.0 vers=1.2.0", self.technique())
        self.assertEqual(maj.lire_version_installee(self.racine), "1.2.0")


class VerifierReponsesPerdues(BacVerifier):
    """O1 : le serveur accepte, mais ni « accepte » ni « arrete » n'arrivent."""

    def avant_demarrage(self):
        # Le serveur du bac n'écrit plus AUCUNE réponse d'arrêt : il accepte et
        # quitte en code 0, que sa tâche ne relance pas.
        self.modifier_serveur(
            b"def ecrire_reponse_arret(dossier, jeton, verdict, motif):\n",
            b"def ecrire_reponse_arret(dossier, jeton, verdict, motif):\n    return\n")

    def test_le_serveur_est_relance_dans_le_meme_passage(self):
        avant = pe.instantane(self.racine)
        self.publier("1.2.0")
        code = self.verifier(delais={"reponse": 3})
        self.assertEqual(code, 3)
        self.assertIn("MAJ_REPORTEE code=ARRET_SANS_REPONSE", self.technique())
        self.assertTrue(maj.attendre_sante(self.port, 40), "le serveur n'a pas été relancé")
        with open(os.path.join(self.racine, "journal.log"), encoding="utf-8") as f:
            self.assertIn("relance du serveur après abandon", f.read())
        self.assertFalse(self.etat_json()["arret_en_cours"])
        self.assertEqual(pe.instantane(self.racine), avant)
        self.assertEqual(self.etat_json()["attente"], "1.2.0")


# ==============================================================================
# Garde des traces (A12), sans serveur
# ==============================================================================

class GardeDesTraces(unittest.TestCase):

    RACINE = os.path.join(tempfile.gettempdir(), "bilan-maj-xq7")

    def test_lignes_conformes_passent(self):
        texte = ("2026-11-12T08:00:00 MAJ_APPLIQUEE de=1.1.0 vers=1.2.0 cles=changees\n"
                 "2026-11-12T08:00:01 MAJ_RETOUR cause=SANTE_MUETTE resultat=ok de=1.1.0 vers=1.2.0\n"
                 "2026-11-12T08:00:02 MAJ_REFUSEE code=SIGNATURE_INVALIDE\n"
                 "2026-11-12T08:00:03 DEPOT ok 12 octets\n")
        self.assertEqual(problemes_de_traces(texte, self.RACINE), [])

    def test_la_garde_mord(self):
        base = "2026-11-12T08:00:00 "
        fautives = [
            base + "MAJ_INCONNUE code=SIGNATURE_INVALIDE",
            base + "MAJ_REFUSEE code=SIGNATURE_INVALIDE detail=x",
            base + "MAJ_REFUSEE code=PAS_UN_CODE",
            base + "MAJ_REFUSEE code=SIGNATURE_INVALIDE /tmp/x",
            base + "MAJ_REFUSEE code=SIGNATURE_INVALIDE C:\\Users\\x",
            base + "MAJ_REFUSEE code=SIGNATURE_INVALIDE x.zip",
            base + "MAJ_REFUSEE code=SIGNATURE_INVALIDE manifeste.json",
            base + "MAJ_REFUSEE code=SIGNATURE_INVALIDE vers=192.168.1.4",
            base + "MAJ_REFUSEE code=SIGNATURE_INVALIDE " + os.path.basename(self.RACINE),
        ]
        for ligne in fautives:
            with self.subTest(ligne=ligne):
                self.assertTrue(problemes_de_traces(ligne + "\n", self.RACINE))


if __name__ == "__main__":
    unittest.main()
