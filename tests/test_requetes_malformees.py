"""Une requête malformée reçoit un code, pas un silence (contrat C6-T5).

Avant la tâche, une demi-paire de substitution isolée dans le chemin
(`/%ed%a0%80.html`) fermait la connexion sans un octet sous Python 3.9 : le
navigateur la rapporte comme une panne réseau. Le filtre d'extension lisait le
chemin brut quand le disque ouvrait le chemin décodé, une forme non absolue
(`index.html`) était servie, l'en-tête `Server` donnait la version exacte de
Python, et `journal.log` recevait brut tout caractère de contrôle venu du
client.

  Serveur neutre — en-tête `Server`, partout (S1 à S3) ;
  Chemins        — extension et ouverture sur une seule forme, 400, index de
                   dossier fermé, aucun silence (E1 à E8, A1) ;
  Unitaires      — confiner_fichier_servi, le filet de send_head,
                   list_directory, log_message (U1 à U7) ;
  Journaux       — route « autre » et échappement (J1 à J3).

    python3 -m unittest tests.test_requetes_malformees
    python3 -O -m unittest tests.test_requetes_malformees

Variable d'environnement facultative `BILAN_PYTHON_CERTIFICATS` : chemin d'un
interpréteur qui possède `cryptography`. Elle ne sert qu'à fabriquer les
certificats du bac à sable quand l'interpréteur des tests, lui, ne l'a pas (le
Python 3.9 d'un poste) ; le serveur, lui, tourne toujours sous l'interpréteur
des tests.

Bibliothèque standard seule. Pas d'`assert` nu : il s'évaporerait sous -O.
Aucun test ne touche au `journal.log` du dépôt : les unitaires qui journalisent
simulent `serveur.journaliser`, les autres écrivent dans un bac à sable.
"""

import ast
import base64
import collections
import http.server
import io
import os
import platform
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
import unittest.mock
from http import HTTPStatus

DOSSIER_TESTS = os.path.dirname(os.path.abspath(__file__))
PROJET = os.path.dirname(DOSSIER_TESTS)
sys.path.insert(0, os.path.join(PROJET, "serveur"))
sys.path.insert(0, DOSSIER_TESTS)

import serveur
from test_integration import (
    MOT_DE_PASSE, UTILISATEUR, chercher_adresse, cryptography_absente,
    demarrer_sandbox_court)

INTERPRETE_CERTIFICATS = os.environ.get("BILAN_PYTHON_CERTIFICATS")


# --------------------------------------------------------------------------
# Client TLS brut : http.client refuse l'octet nul, BONJOUR, le chemin sans /
# --------------------------------------------------------------------------

Reponse = collections.namedtuple(
    "Reponse", "brut statut entetes corps code erreur")


def analyser_reponse(brut, erreur=None):
    """(statut, en-têtes, corps, code) d'une réponse reçue telle quelle.

    Une ligne de requête illisible reçoit de la bibliothèque un corps d'erreur
    sans ligne d'état (réponse « à la HTTP/0.9 ») : le code se lit alors dans
    le corps. Les valeurs d'en-tête ne sont pas rognées à droite : une espace
    finale dans `Server` doit rester visible.
    """
    statut = None
    entetes = {}
    corps = brut
    if brut.startswith(b"HTTP/"):
        tete, _, corps = brut.partition(b"\r\n\r\n")
        lignes = tete.split(b"\r\n")
        statut = int(lignes[0].split(b" ", 2)[1])
        for ligne in lignes[1:]:
            nom, _, valeur = ligne.partition(b":")
            valeur = valeur.decode("latin-1")
            if valeur.startswith(" "):
                valeur = valeur[1:]
            entetes[nom.decode("latin-1").lower()] = valeur
    code = statut
    if code is None:
        trouve = re.search(rb"Error code: (\d+)", corps)
        code = int(trouve.group(1)) if trouve else None
    return Reponse(brut, statut, entetes, corps, code, erreur)


def echanger(dossier, port, octets):
    """Envoie des octets bruts sur une socket TLS qui se ferme toujours, et
    lit jusqu'à la fin de la connexion. Une réponse vide, ou une connexion
    réinitialisée, rend un brut vide : c'est le test qui nomme le silence."""
    contexte = ssl.create_default_context(
        cafile=os.path.join(dossier, "autorite.crt"))
    recu = bytearray()
    erreur = None
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=10) as brute:
            with contexte.wrap_socket(brute, server_hostname="127.0.0.1") as tls:
                try:
                    tls.sendall(octets)
                except OSError as cause:
                    # Un serveur qui répond 414 avant d'avoir tout lu ferme
                    # la connexion : la réponse reste à lire.
                    erreur = cause
                try:
                    while True:
                        morceau = tls.recv(65536)
                        if not morceau:
                            break
                        recu += morceau
                except OSError as cause:
                    erreur = erreur or cause
    except OSError as cause:
        erreur = erreur or cause
    return analyser_reponse(bytes(recu), erreur)


def jeton():
    return base64.b64encode(
        "{}:{}".format(UTILISATEUR, MOT_DE_PASSE).encode("utf-8")).decode("ascii")


# Une requête de la table : la ligne de requête telle qu'elle part, les
# identifiants, le code attendu et des en-têtes en plus.
Cas = collections.namedtuple("Cas", "ligne auth attendu entetes")


def cas(ligne, attendu, auth=True, entetes=b""):
    return Cas(ligne, auth, attendu, entetes)


def octets_de(c):
    """La requête complète d'un cas, en octets, `Connection: close`."""
    corps = c.ligne + b"\r\nHost: 127.0.0.1\r\n"
    if c.auth:
        corps += b"Authorization: Basic " + jeton().encode("ascii") + b"\r\n"
    corps += b"Connection: close\r\n" + c.entetes + b"\r\n"
    return corps


def table_a4():
    """La table de codes du critère A4, une ligne par requête. Elle sert à
    E7, mais aussi à S1 (l'en-tête Server de chacune de ces réponses), E8 et
    J3 : ce qui est envoyé n'est écrit qu'ici."""
    lignes = []
    for cible in (b"index.html", b"*", b"https://127.0.0.1/index.html"):
        for methode in (b"GET", b"HEAD"):
            lignes.append(cas(methode + b" " + cible + b" HTTP/1.1", 400))
    lignes.append(cas(b"GET index.html HTTP/1.1", 401, auth=False))
    lignes.append(cas(b"GET /index%2ehtml HTTP/1.1", 200))
    for cible in (b"/journal.log%2f.html", b"/images%2f.html", b"/x.html%",
                  b"/moteur%2f", b"/moteur/", b"/moteur", b"/cabinet%00"):
        for methode in (b"GET", b"HEAD"):
            lignes.append(cas(methode + b" " + cible + b" HTTP/1.1", 403))
    for cible in (b"/%zz.html", b"/x%.html", b"/%ff.html", b"/%ed%a0%80.html",
                  b"/%c0%ae%c0%ae/config.json", b"/x%01.html",
                  b"/x%0d%0a.html", b"/x\xff.html", b"/x\x00.html"):
        for methode in (b"GET", b"HEAD"):
            lignes.append(cas(methode + b" " + cible + b" HTTP/1.1", 404))
    for auth in (True, False):
        lignes.append(cas(b"GET /" + b"a" * 70000 + b".html HTTP/1.1", 414, auth))
        lignes.append(cas(b"FOO / HTTP/1.1", 501, auth))
        lignes.append(cas(b"PUT / HTTP/1.1", 501, auth))
    lignes.append(cas(b"GET / HTTP/1.1", 431,
                      entetes=b"X-Long: " + b"a" * 70000 + b"\r\n"))
    lignes.append(cas(b"GET / HTTP/1.1", 431, entetes=b"".join(
        b"X-" + str(i).encode("ascii") + b": v\r\n" for i in range(150))))
    for cible in (b"/depot%00", b"/%ff"):
        lignes.append(cas(b"POST " + cible + b" HTTP/1.1", 404,
                          entetes=b"Content-Length: 0\r\n"))
        lignes.append(cas(b"POST " + cible + b" HTTP/1.1", 401, auth=False,
                          entetes=b"Content-Length: 0\r\n"))
    lignes.append(cas(b"GET /sante HTTP/1.1", 200, auth=False))
    lignes.append(cas(b"GET /sante%00 HTTP/1.1", 401, auth=False))
    return lignes


def table_illisibles():
    """Les trois lignes que la bibliothèque rejette avant tout gestionnaire :
    une réponse sans ligne d'état, dont le code se lit dans le corps."""
    return [cas(b"BONJOUR", 400),
            cas(b"GET / HTTP/2.0", 505),
            cas(b"GET / HTTP/x", 400)]


def cible_de(c):
    """La cible d'un cas, pour chercher qu'elle n'est pas dans un journal."""
    mots = c.ligne.split(b" ")
    return mots[1].decode("latin-1") if len(mots) > 1 else ""


# --------------------------------------------------------------------------
# Serveur partagé
# --------------------------------------------------------------------------

def lancer_bac(avant_demarrage=None):
    """demarrer_sandbox_court, mais les certificats peuvent venir d'un autre
    interpréteur (voir l'en-tête du module). Rien d'autre ne change : le
    serveur est lancé par sys.executable."""
    if not INTERPRETE_CERTIFICATS:
        return demarrer_sandbox_court(avant_demarrage=avant_demarrage)
    reel = subprocess.run

    def run_certificats(commande, *args, **options):
        if any("generer_autorite.py" in str(mot) for mot in commande):
            commande = [INTERPRETE_CERTIFICATS] + list(commande[1:])
        return reel(commande, *args, **options)

    with unittest.mock.patch.object(subprocess, "run", run_certificats):
        # Le patch ne vaut que pour generer_autorite.py ; Popen, qui lance le
        # serveur, n'est pas touché.
        return demarrer_sandbox_court(avant_demarrage=avant_demarrage)


def peut_fabriquer_les_certificats():
    return bool(INTERPRETE_CERTIFICATS) or not cryptography_absente()


def verifier_neutre(testcase, reponse, libelle):
    """L'en-tête Server vaut exactement Gestionnaire.server_version, et
    aucun en-tête ni aucun corps ne dit la version de Python."""
    testcase.assertTrue(reponse.brut, "silence : " + libelle)
    attendu = serveur.Gestionnaire.server_version
    if reponse.entetes:
        testcase.assertEqual(reponse.entetes.get("server"), attendu, libelle)
    version = platform.python_version()
    motif = re.compile(r"python/\d", re.IGNORECASE)
    for nom, valeur in reponse.entetes.items():
        testcase.assertNotIn(version, valeur, libelle + " : " + nom)
        testcase.assertIsNone(motif.search(valeur), libelle + " : " + nom)
    texte = reponse.corps.decode("latin-1")
    testcase.assertNotIn(version, texte, libelle)
    testcase.assertIsNone(motif.search(texte), libelle)


def chemins_des_routes():
    """Les chemins comparés au chemin demandé dans do_GET et do_HEAD,
    dérivés de l'arbre syntaxique comme dans test_integration (jamais écrits
    ici : une route ajoutée demain est servie par S2 sans qu'on y pense)."""
    with open(serveur.__file__, encoding="utf-8") as f:
        arbre = ast.parse(f.read())

    def designe_le_chemin(noeud, variables):
        if isinstance(noeud, ast.Call):
            return getattr(noeud.func, "attr", None) == "chemin_demande"
        if isinstance(noeud, ast.Attribute):
            return noeud.attr == "path"
        return isinstance(noeud, ast.Name) and noeud.id in variables

    chemins = set()
    methodes_vues = set()
    for classe in arbre.body:
        if not (isinstance(classe, ast.ClassDef) and classe.name == "Gestionnaire"):
            continue
        for definition in classe.body:
            if not (isinstance(definition, ast.FunctionDef)
                    and definition.name in ("do_GET", "do_HEAD")):
                continue
            methodes_vues.add(definition.name)
            variables = {
                a.targets[0].id for a in ast.walk(definition)
                if isinstance(a, ast.Assign) and len(a.targets) == 1
                and isinstance(a.targets[0], ast.Name)
                and designe_le_chemin(a.value, ())}
            for comparaison in ast.walk(definition):
                if not isinstance(comparaison, ast.Compare):
                    continue
                operandes = [comparaison.left] + comparaison.comparators
                if not any(designe_le_chemin(o, variables) for o in operandes):
                    continue
                for operande in operandes:
                    for c in ast.walk(operande):
                        if (isinstance(c, ast.Constant) and isinstance(c.value, str)
                                and c.value.startswith("/")):
                            chemins.add(c.value)
    return methodes_vues, chemins


def taille(dossier, nom):
    chemin = os.path.join(dossier, nom)
    return os.path.getsize(chemin) if os.path.exists(chemin) else 0


def ajoute(dossier, nom, avant):
    """Ce qu'un journal a reçu depuis `avant` octets, décodé sans rien
    traduire : un caractère de contrôle brut doit rester visible."""
    chemin = os.path.join(dossier, nom)
    if not os.path.exists(chemin):
        return ""
    with open(chemin, "rb") as f:
        f.seek(avant)
        return f.read().decode("utf-8", errors="replace")


@unittest.skipUnless(peut_fabriquer_les_certificats(),
                     "cryptography requis pour fabriquer les certificats")
class RequetesMalformees(unittest.TestCase):
    """Un vrai serveur, démarré une fois pour la classe, avec un dossier
    `formulaire/dossier.html/sous/` : un nom de dossier qui porte une
    extension servie, pour éprouver l'index de dossier."""

    @classmethod
    def setUpClass(cls):
        def poser_dossier(dossier):
            os.makedirs(os.path.join(dossier, "formulaire", "dossier.html", "sous"))

        cls.dossier, cls.port, cls.processus = lancer_bac(poser_dossier)
        # Le tube doit être vidé EN CONTINU : sous Windows son tampon est
        # petit, et un tube jamais lu fige toute requête qui journalise
        # (C7-T5).
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

    # --- outils ------------------------------------------------------------

    def envoyer(self, c):
        return echanger(self.dossier, self.port, octets_de(c))

    def demander(self, cible, methode="GET", auth=True):
        """Une requête ordinaire, cible en `str` ou en octets."""
        if isinstance(cible, str):
            cible = cible.encode("latin-1")
        return self.envoyer(cas(
            methode.encode("ascii") + b" " + cible + b" HTTP/1.1", None, auth))

    def exiger_reponse(self, reponse, libelle):
        """Un silence est un échec nommé, jamais une erreur de test."""
        self.assertTrue(
            reponse.brut,
            "silence : aucune réponse à {} ({})".format(libelle, reponse.erreur))

    def octets_du_bac(self, *morceaux):
        with open(os.path.join(self.dossier, "formulaire", *morceaux), "rb") as f:
            return f.read()

    # --- A1, A2 : l'octet nul ------------------------------------------------

    def test_e1_octet_nul_extension_servie_et_refusee(self):
        # Critère de la feuille de route, déjà acquis par C6-T6 et gardé ici.
        absent = self.demander("/absent.html")
        self.assertEqual(absent.statut, 404)     # témoin
        for cible in ("/index%00.html", "/style%00.css",
                      "/journal.log%00.json", "/x%00.json"):
            with self.subTest(cible=cible, methode="GET"):
                reponse = self.demander(cible)
                self.exiger_reponse(reponse, cible)
                self.assertEqual(reponse.statut, 404)
                self.assertEqual(reponse.corps, absent.corps)
            with self.subTest(cible=cible, methode="HEAD"):
                reponse = self.demander(cible, methode="HEAD")
                self.exiger_reponse(reponse, "HEAD " + cible)
                self.assertEqual(reponse.statut, 404)
        with self.subTest(cible="/x%00.log"):
            self.assertEqual(self.demander("/x%00.log").statut, 403)
        with self.subTest(cible="octet nul brut"):
            reponse = self.demander(b"/x\x00.html")
            self.exiger_reponse(reponse, "octet nul brut")
            self.assertEqual(reponse.statut, 404)

    # --- A3 : le silence --------------------------------------------------

    def test_e3_demi_paire_isolee_404(self):
        # Sous Python 3.9 POSIX, open() lève UnicodeEncodeError que send_head
        # ne rattrape pas : la connexion se fermait sans un octet.
        for cible in ("/%ed%a0%80.html", "/x%ed%a0%80.json",
                      "/images/%ed%a0%80.png"):
            for methode in ("GET", "HEAD"):
                with self.subTest(cible=cible, methode=methode):
                    reponse = self.demander(cible, methode=methode)
                    self.exiger_reponse(reponse, methode + " " + cible)
                    self.assertEqual(reponse.statut, 404)

    # --- A4, A3 : les formes de chemin ----------------------------------------

    def test_e2_chemin_non_absolu_400(self):
        for cible in ("index.html", "*", "https://127.0.0.1/index.html"):
            for methode in ("GET", "HEAD"):
                with self.subTest(cible=cible, methode=methode):
                    reponse = self.demander(cible, methode=methode)
                    self.exiger_reponse(reponse, cible)
                    self.assertEqual(reponse.statut, 400)
        # Le 400 ne dit rien du chemin : un test de contenu, pas de code.
        corps = self.demander("index.html").corps
        self.assertNotIn(b"index.html", corps)

    def test_e4_extension_lue_sur_la_forme_decodee(self):
        # /index%2ehtml désigne /index.html : une seule forme du chemin pour
        # le filtre d'extension et pour l'ouverture.
        reference = self.demander("/index.html")
        self.assertEqual(reference.statut, 200)     # témoin
        reponse = self.demander("/index%2ehtml")
        self.exiger_reponse(reponse, "/index%2ehtml")
        self.assertEqual(reponse.statut, 200)
        self.assertEqual(reponse.corps, reference.corps)
        tete = self.demander("/index%2ehtml", methode="HEAD")
        self.assertEqual(tete.statut, 200)
        self.assertEqual(tete.entetes["content-length"],
                         reference.entetes["content-length"])

    def test_e5_dernier_segment_decode_sans_extension(self):
        # Le dernier segment décodé est « .html » : aucune extension.
        for cible in ("/journal.log%2f.html", "/images%2f.html"):
            with self.subTest(cible=cible):
                reponse = self.demander(cible)
                self.exiger_reponse(reponse, cible)
                self.assertEqual(reponse.statut, 403)

    def test_e6_aucun_index_de_dossier(self):
        cibles = ("/dossier.html", "/dossier.html/", "/dossier.html%2f",
                  "/dossier.html%2F", "/dossier.html/.",
                  "/dossier.html/sous/..", "/dossier.html/%2e")
        for cible in cibles:
            for methode in ("GET", "HEAD"):
                with self.subTest(cible=cible, methode=methode):
                    reponse = self.demander(cible, methode=methode)
                    self.exiger_reponse(reponse, cible)
                    self.assertIn(reponse.statut, (301, 403, 404))
                    self.assertNotIn(b"Directory listing", reponse.corps)
                    self.assertNotIn(b"sous/", reponse.corps)

    def test_e7_table_des_codes(self):
        lignes = table_a4() + table_illisibles()
        # Ancrage : la table couvre bien tous les codes de A4.
        self.assertGreaterEqual(
            {c.attendu for c in lignes}, {200, 400, 401, 403, 404, 414, 431, 501})
        for c in lignes:
            libelle = "{} (auth={})".format(c.ligne[:60], c.auth)
            with self.subTest(requete=libelle):
                reponse = self.envoyer(c)
                self.exiger_reponse(reponse, libelle)
                self.assertEqual(reponse.code, c.attendu)

    def test_e8_service_ordinaire_intact(self):
        fichiers = (("/", "index.html"), ("/index.html", "index.html"),
                    ("/index-v1.html", "index-v1.html"),
                    ("/style.css", "style.css"), ("/script.js", "script.js"),
                    ("/schema.json", "schema.json"),
                    ("/version.json", "version.json"),
                    ("/images/favicon.jpeg", "images/favicon.jpeg"))
        for cible, nom in fichiers:
            with self.subTest(cible=cible):
                reponse = self.demander(cible)
                self.assertEqual(reponse.statut, 200)
                self.assertEqual(reponse.corps,
                                 self.octets_du_bac(*nom.split("/")))
        # Après toutes les requêtes malformées : le témoin de fin.
        for c in table_a4() + table_illisibles():
            self.envoyer(c)
        reponse = self.demander("/index.html")
        self.assertEqual(reponse.statut, 200)
        self.assertEqual(reponse.corps, self.octets_du_bac("index.html"))

    # --- A1 de l'authentification : le 400 vient après le 401 -----------------

    def test_a1_sans_identifiants_401_avant_le_400(self):
        for cible in ("index.html", "*", "https://127.0.0.1/index.html",
                      "/index%00.html"):
            for methode in ("GET", "HEAD"):
                with self.subTest(cible=cible, methode=methode):
                    reponse = self.demander(cible, methode=methode, auth=False)
                    self.exiger_reponse(reponse, cible)
                    self.assertEqual(reponse.statut, 401)
                    self.assertEqual(reponse.corps, b"")

    # --- A7 : l'en-tête Server -----------------------------------------------

    def test_s1_server_neutre_sur_les_reponses_d_erreur(self):
        lignes = table_a4() + table_illisibles()
        vus = set()
        for c in lignes:
            libelle = "{} (auth={})".format(c.ligne[:60], c.auth)
            with self.subTest(requete=libelle):
                reponse = self.envoyer(c)
                verifier_neutre(self, reponse, libelle)
                if reponse.statut is not None:
                    vus.add(reponse.statut)
        # Ancrage : 400, 401, 403, 404, 414, 431 et 501 ont tous été
        # inspectés, avec leurs en-têtes.
        self.assertGreaterEqual(vus, {400, 401, 403, 404, 414, 431, 501})

    def test_s2_server_neutre_sur_toutes_les_routes_derivees(self):
        methodes, chemins = chemins_des_routes()
        # Ancrages : sans eux, une dérivation qui ne trouve rien passerait au
        # vert (c'est le piège du dépôt).
        self.assertEqual(methodes, {"do_GET", "do_HEAD"})
        self.assertIn("/sante", chemins)
        self.assertGreaterEqual(len(chemins - {"/sante"}), 2)
        for chemin in sorted(chemins):
            for methode in ("GET", "HEAD"):
                for auth in (True, False):
                    libelle = "{} {} auth={}".format(methode, chemin, auth)
                    with self.subTest(requete=libelle):
                        verifier_neutre(
                            self, self.demander(chemin, methode, auth), libelle)
        for auth in (True, False):
            libelle = "POST /depot auth={}".format(auth)
            with self.subTest(requete=libelle):
                verifier_neutre(self, self.envoyer(cas(
                    b"POST /depot HTTP/1.1", None, auth,
                    entetes=b"Content-Length: 0\r\n")), libelle)

    # --- A9, A10 : les journaux ----------------------------------------------

    def test_j1_route_autre_sur_requete_non_analysee(self):
        # 414, 505 et 400 de syntaxe sont émis avant que le chemin soit lu :
        # la route n'est pas « formulaire ».
        lignes = [cas(b"GET /" + b"a" * 70000 + b".html HTTP/1.1", 414),
                  cas(b"GET / HTTP/2.0", 505), cas(b"BONJOUR", 400)]
        for c in lignes:
            with self.subTest(code=c.attendu):
                avant = taille(self.dossier, "technique.log")
                reponse = self.envoyer(c)
                self.exiger_reponse(reponse, c.ligne[:30].decode("latin-1"))
                self.assertEqual(reponse.code, c.attendu)
                ajoutees = ajoute(self.dossier, "technique.log", avant)
                self.assertIn("REPONSE methode=autre route=autre code={}".format(
                    c.attendu), ajoutees)
                self.assertNotIn("route=formulaire code={}".format(c.attendu),
                                 ajoutees)

    def test_j2_journal_sans_caractere_de_controle(self):
        avant = taille(self.dossier, "journal.log")
        reponse = self.envoyer(cas(b"GET /x\x1b[31m\x00.html HTTP/1.1", 404))
        self.exiger_reponse(reponse, "ligne avec 0x1b et 0x00")
        self.assertEqual(reponse.statut, 404)
        ajoutees = ajoute(self.dossier, "journal.log", avant)
        # Ancrage : le refus de lecture a bien été journalisé.
        self.assertIn("lecture refusée motif=forme-invalide", ajoutees)
        self.assertIn("\\x1b[31m", ajoutees)
        # Sous Windows le journal, ouvert en mode texte, termine ses lignes par
        # \r\n : le terminateur du système n'est pas un caractère du client. Un
        # \r venu du client resterait, lui, devant son propre terminateur.
        # Pas splitlines : il coupe aussi sur 0x1c.
        lignes = ajoutees.replace(os.linesep, "\n").split("\n")
        self.assertEqual(lignes[-1], "")
        for ligne in lignes[:-1]:
            for caractere in ligne:
                interdit = (ord(caractere) < 0x20
                            or 0x7f <= ord(caractere) < 0xa0)
                self.assertFalse(
                    interdit, "caractère de contrôle brut {!r} dans {!r}".format(
                        caractere, ligne))

    def test_j2b_demi_paire_journalisee_forme_invalide(self):
        avant = taille(self.dossier, "journal.log")
        self.assertEqual(self.demander("/%ed%a0%80.html").statut, 404)
        self.assertEqual(self.demander("/x%00.json").statut, 404)
        ajoutees = ajoute(self.dossier, "journal.log", avant)
        # L'octet nul est toujours refusé. La demi-paire ne l'est que là où le
        # système ne sait pas l'encoder : sous Windows (PEP 529) elle s'encode,
        # et c'est la 404 d'un absent qui répond, sans motif au journal. Le
        # nombre attendu suit le système, il n'est pas transcrit.
        try:
            os.fsencode("x\ud800.html")
            attendu = 1
        except UnicodeEncodeError:
            attendu = 2
        if os.name == "posix":
            self.assertEqual(attendu, 2)     # ancrage
        self.assertEqual(ajoutees.count("lecture refusée motif=forme-invalide"),
                         attendu)

    def test_j3_technique_sans_chemin_ni_adresse_et_sante_muette(self):
        lignes = table_a4() + table_illisibles()
        avant = taille(self.dossier, "technique.log")
        for c in lignes:
            self.envoyer(c)
        technique = ajoute(self.dossier, "technique.log", 0)
        # Ancrage : la table a bien écrit dans le journal technique.
        self.assertGreater(len(ajoute(self.dossier, "technique.log", avant)), 0)
        self.assertIsNone(chercher_adresse(technique))
        for c in lignes:
            cible = cible_de(c).lstrip("/")
            if len(cible) < 5:
                continue
            with self.subTest(cible=cible[:30]):
                self.assertNotIn(cible, technique)
        # /sante est muette dans les deux journaux.
        avant_journal = taille(self.dossier, "journal.log")
        avant_technique = taille(self.dossier, "technique.log")
        self.assertEqual(self.demander("/sante", auth=False).statut, 200)
        self.assertEqual(taille(self.dossier, "journal.log"), avant_journal)
        self.assertEqual(taille(self.dossier, "technique.log"), avant_technique)


# --------------------------------------------------------------------------
# Unitaires
# --------------------------------------------------------------------------

def gestionnaire_nu(**attributs):
    """Un Gestionnaire sans socket ni requête : __init__ traiterait une
    requête entière."""
    gestionnaire = serveur.Gestionnaire.__new__(serveur.Gestionnaire)
    gestionnaire.client_address = ("127.0.0.1", 40000)
    for nom, valeur in attributs.items():
        setattr(gestionnaire, nom, valeur)
    return gestionnaire


class VersionNeutre(unittest.TestCase):

    def test_s3_version_string_rend_le_nom_seul(self):
        gestionnaire = gestionnaire_nu()
        self.assertEqual(gestionnaire.version_string(),
                         serveur.Gestionnaire.server_version)
        self.assertEqual(serveur.Gestionnaire.server_version, "bilan-posturo")
        self.assertEqual(serveur.Gestionnaire.sys_version, "")
        # Pas d'espace finale : la bibliothèque concatène server_version,
        # une espace et sys_version.
        self.assertEqual(gestionnaire.version_string(),
                         gestionnaire.version_string().strip())
        self.assertNotIn("Python", gestionnaire.version_string())
        self.assertNotIn(platform.python_version(), gestionnaire.version_string())


class ConfinementFormeInvalide(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bilan-test-forme-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.racine = os.path.join(self.tmp, "web")
        os.makedirs(self.racine)

    def test_u1_chemin_non_encodable_forme_invalide(self):
        chemin = os.path.join(self.racine, "x\ud800.html")
        # Le résultat attendu suit le système, il n'est pas transcrit : sous
        # POSIX une demi-paire isolée n'est pas encodable ; sous Windows
        # (PEP 529) elle l'est, et la 404 d'un absent répond.
        try:
            os.fsencode(chemin)
            attendu = None
        except UnicodeEncodeError:
            attendu = "forme-invalide"
        if os.name == "posix":
            self.assertEqual(attendu, "forme-invalide")     # ancrage
        # realpath est remplacé par l'identité : selon la version de Python il
        # lève (3.14) ou rend la chaîne (3.9), le refus ne doit pas en dépendre.
        with unittest.mock.patch.object(serveur.os.path, "realpath",
                                        side_effect=lambda c: c):
            self.assertEqual(serveur.confiner_fichier_servi(chemin, self.racine),
                             attendu)

    def test_u2_octet_nul_forme_invalide(self):
        chemin = os.path.join(self.racine, "x\x00.png")
        self.assertEqual(serveur.confiner_fichier_servi(chemin, self.racine),
                         "forme-invalide")
        with unittest.mock.patch.object(serveur.os.path, "realpath",
                                        side_effect=lambda c: c):
            self.assertEqual(serveur.confiner_fichier_servi(chemin, self.racine),
                             "forme-invalide")
        self.assertIn("forme-invalide", serveur.MOTIFS_REFUS_LOGO)


class FiletEtIndex(unittest.TestCase):

    def test_u3_filet_send_head_valueerror_404(self):
        for erreur in (ValueError("embedded null byte"),
                       UnicodeEncodeError("utf-8", "\ud800", 0, 1, "surrogate")):
            with self.subTest(erreur=type(erreur).__name__):
                gestionnaire = gestionnaire_nu(path="/x\x00.html")
                gestionnaire.send_error = unittest.mock.MagicMock()
                with unittest.mock.patch.object(serveur, "journaliser") as jour, \
                     unittest.mock.patch.object(
                         http.server.SimpleHTTPRequestHandler, "send_head",
                         side_effect=erreur):
                    resultat = gestionnaire.send_head()
                self.assertIsNone(resultat)
                gestionnaire.send_error.assert_called_once_with(
                    HTTPStatus.NOT_FOUND, "File not found")
                self.assertEqual(jour.call_count, 1)
                ligne = jour.call_args[0][0]
                self.assertIn("lecture refusée motif=forme-invalide", ligne)
                self.assertIn(repr("/x\x00.html"), ligne)

    def test_u3b_le_filet_ne_masque_que_valueerror(self):
        gestionnaire = gestionnaire_nu(path="/x.html")
        gestionnaire.send_error = unittest.mock.MagicMock()
        with unittest.mock.patch.object(serveur, "journaliser"):
            with unittest.mock.patch.object(
                    http.server.SimpleHTTPRequestHandler, "send_head",
                    side_effect=RuntimeError("défaut de programmation")):
                with self.assertRaises(RuntimeError):
                    gestionnaire.send_head()
            sentinelle = object()
            with unittest.mock.patch.object(
                    http.server.SimpleHTTPRequestHandler, "send_head",
                    return_value=sentinelle):
                self.assertIs(gestionnaire.send_head(), sentinelle)
        gestionnaire.send_error.assert_not_called()

    def test_u4_list_directory_rend_404(self):
        tmp = tempfile.mkdtemp(prefix="bilan-test-index-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        os.makedirs(os.path.join(tmp, "sous"))
        gestionnaire = gestionnaire_nu(path="/dossier.html/")
        gestionnaire.send_error = unittest.mock.MagicMock()
        # Si la bibliothèque produisait un index, elle passerait par ces trois
        # méthodes : on les rend inoffensives pour que l'échec soit une
        # assertion et non une erreur d'attribut.
        gestionnaire.send_response = unittest.mock.MagicMock()
        gestionnaire.send_header = unittest.mock.MagicMock()
        gestionnaire.end_headers = unittest.mock.MagicMock()
        gestionnaire.wfile = io.BytesIO()
        resultat = gestionnaire.list_directory(tmp)
        self.assertIsNone(resultat)
        gestionnaire.send_error.assert_called_once_with(
            HTTPStatus.NOT_FOUND, "File not found")
        gestionnaire.send_response.assert_not_called()


class JournalisationUnitaire(unittest.TestCase):
    """log_message avec journaliser et journaliser_technique simulés : rien
    n'est écrit dans le journal du dépôt."""

    def appeler(self, format, *args, **attributs):
        defaut = {"silencieux": False, "_code_reponse_technique": 0}
        defaut.update(attributs)
        gestionnaire = gestionnaire_nu(**defaut)
        with unittest.mock.patch.object(serveur, "journaliser") as jour, \
             unittest.mock.patch.object(serveur, "journaliser_technique") as tech:
            gestionnaire.log_message(format, *args)
        return jour, tech

    def test_u5_echappement_des_caracteres_de_controle(self):
        table = serveur.ECHAPPEMENT_CONTROLE
        self.assertEqual("\x1b\x00\x9f".translate(table), "\\x1b\\x00\\x9f")
        # La barre oblique inverse n'est pas échappée (D9) : le chemin d'un
        # fichier Windows de la ligne ECHEC ecriture reste lisible.
        windows = "C:\\Users\\x"
        self.assertEqual(windows.translate(table), windows)
        # Les bornes : C0, DEL et C1 sont échappés, ce qui les entoure non.
        for code in (0x00, 0x0a, 0x0d, 0x1b, 0x1f, 0x7f, 0x80, 0x85, 0x9f):
            with self.subTest(code=code):
                self.assertEqual(chr(code).translate(table),
                                 "\\x{:02x}".format(code))
        for code in (0x20, 0x41, 0x7e, 0xa0, 0xe9):
            with self.subTest(code=code):
                self.assertEqual(chr(code).translate(table), chr(code))

    def test_u6_log_message_echappe_avant_de_journaliser(self):
        jour, _ = self.appeler('"%s" %s', "GET /x\x1b[31m\x00 HTTP/1.1", "404",
                               command="GET", path="/x")
        ligne = jour.call_args[0][0]
        self.assertIn('"GET /x\\x1b[31m\\x00 HTTP/1.1" 404', ligne)
        self.assertTrue(ligne.endswith("\n"))
        # Seul le saut de ligne final reste brut.
        self.assertEqual([c for c in ligne[:-1] if ord(c) < 0x20], [])

    def test_u7_route_autre_quand_la_requete_n_est_pas_analysee(self):
        for command in (None, ""):
            with self.subTest(command=command):
                _, tech = self.appeler("x", command=command, path="",
                                       _code_reponse_technique=414)
                tech.assert_called_once_with(
                    "REPONSE", "methode=autre route=autre code=414")
        # Sans attribut `command` du tout (instance jamais passée par
        # parse_request).
        _, tech = self.appeler("x", _code_reponse_technique=400)
        tech.assert_called_once_with(
            "REPONSE", "methode=autre route=autre code=400")

    def test_u7b_route_inchangee_quand_la_requete_est_analysee(self):
        for chemin, route in (("/index.html", "formulaire"), ("/sante", "sante"),
                              ("/depot", "depot"), ("/x.log", "autre")):
            with self.subTest(chemin=chemin):
                _, tech = self.appeler("x", command="GET", path=chemin,
                                       _code_reponse_technique=200)
                tech.assert_called_once_with(
                    "REPONSE", "methode=GET route={} code=200".format(route))


if __name__ == "__main__":
    unittest.main()
