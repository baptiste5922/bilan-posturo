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
import http.client
import io
import json
import os
import re
import shutil
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
        self.pilote.demarrer()
        if not maj.attendre_sante(self.port, 40):
            self.fail("le serveur du bac ne répond pas : " + self.pilote.console())
        self.courant = self.base

    # --- aides -------------------------------------------------------------------

    def noter_les_traces(self):
        TRACES.append((self.racine, self.technique()))

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
                avant = pe.instantane(self.racine)
                journaux_avant = pe.contenu_des_journaux(self.racine)
                archive = self.trio(version, modifs, base=self.base)

                code, _ = self.appliquer(archive)

                self.assertEqual(code, 1)
                self.assertEqual(pe.instantane(self.racine), avant)
                self.assertTrue(maj.sante_repond(self.port),
                                "le serveur restauré ne répond pas")
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
        # Le serveur est dans do_POST, son corps à moitié lu. Le test attend que le
        # compte le dise plutôt que de dormir un temps fixe.
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

        schema = self.base["formulaire/schema.json"]
        etapes = (("1.2.0", {}), ("1.3.0", {"formulaire/schema.json": schema + b"\n"}),
                  ("1.4.0", {}))
        for version, modifs in etapes:
            archive = self.trio(version, modifs)
            code, sortie = self.appliquer(archive)
            self.assertEqual(code, 0, sortie)
            self.courant = self.dernier_contenu

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
        self.dossier_maj = os.path.join(self.racine, "mise-a-jour")
        os.mkdir(self.dossier_maj)

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
