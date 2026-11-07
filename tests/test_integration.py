"""Test de bout en bout : autorité, TLS, authentification et dépôt.

Recopie le projet dans un dossier temporaire, y fabrique une autorité et un
certificat, lance le serveur en sous-processus, puis l'interroge en HTTPS en
vérifiant la chaîne contre l'autorité produite. Rien n'est touché dans le
dossier du projet.

    python3 -m unittest discover -s tests
"""

import ast
import base64
import datetime
import http.client
import importlib.util
import json
import os
import re
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import warnings

PROJET = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJET, "serveur"))

import serveur

UTILISATEUR = "cabinét"          # accentué : couvre la régression compare_digest
MOT_DE_PASSE = "motdepasse123"
PDF = b"%PDF-1.4\n1 0 obj\ncontenu\n%%EOF\n"


def fragments_nom(nom):
    """Fragments dérivés du nom lui-même : jamais une liste transcrite.

    Fonction de module (pas une méthode) : tearDownClass (classmethod, sans
    self) doit pouvoir l'appeler aussi, pour le contrôle final qui porte sur
    l'intégralité du journal technique une fois tous les tests exécutés.
    """
    radical, _ = os.path.splitext(nom)
    fragments = [nom, radical]
    for segment in re.split(r"[_-]", radical):
        if len(segment) > 3:
            fragments.append(segment)
    return fragments


def chercher_adresse(texte, ipv6=True):
    """Rend un message si une adresse IPv4 ou IPv6 figure dans le texte,
    sinon None. Le motif IPv6 est laxiste et reconnaît l'horodatage lui-même
    (":12:03" dans "...T12:58:39...") : il s'applique donc à la ligne privée
    de son premier mot, l'horodatage, sans espace.

    ipv6=False pour un texte qui n'est pas un journal (le HTML de la page
    d'état, C4-T3) : ses horodatages ne sont pas en tête de ligne et le
    motif IPv6 y verrait des adresses partout. Seul l'IPv4 y est cherché."""
    correspondance = re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", texte)
    if correspondance:
        return ("une adresse IPv4 figure dans le journal technique : "
                + correspondance.group(0))
    if not ipv6:
        return None
    for ligne in texte.splitlines():
        _, _, reste = ligne.partition(" ")
        correspondance = re.search(
            r"(?:[0-9a-fA-F]{0,4}:){2,}[0-9a-fA-F]{0,4}", reste)
        if correspondance:
            return ("une adresse IPv6 figure dans le journal technique : "
                    + repr(ligne))
    return None


def port_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def cryptography_absente():
    """cryptography ne sert qu'à fabriquer les certificats, jamais au
    serveur : son absence fait sauter ce test, pas échouer la suite."""
    return importlib.util.find_spec("cryptography") is None


def attendre_ligne_technique(dossier, sous_chaine, limite=10):
    """Attend, de façon bornée et sans tolérance, qu'une ligne contenant
    sous_chaine apparaisse dans technique.log.

    Ferme une course précise : le port est lié et accepte des connexions TCP
    dès le constructeur de ServeurBilan (serveur/serveur.py), bien avant
    serve_forever() — et avant l'écriture de DEMARRAGE, elle-même avant le
    `try:` qui entoure serve_forever() dans demarrer(). Un signal envoyé
    avant que ce `try` soit atteint tombe hors de lui : son bloc `finally`,
    qui écrit ARRET, n'est alors jamais exécuté. Attendre que DEMARRAGE soit
    écrit garantit que ce `try` est déjà franchi au moment du signal.
    """
    chemin = os.path.join(dossier, "technique.log")
    limite_temps = time.monotonic() + limite
    while time.monotonic() < limite_temps:
        if os.path.exists(chemin):
            with open(chemin, encoding="utf-8") as f:
                if sous_chaine in f.read():
                    return
        time.sleep(0.02)
    raise AssertionError(
        "« {} » n'est jamais apparu dans technique.log après {}s".format(
            sous_chaine, limite))


def preparer_sandbox(config_extra=None, avant_demarrage=None):
    """Construit un bac à sable complet (arborescence, autorité, config.json)
    sans lancer le serveur. Rend (dossier, port) ; l'appelant supprime le
    dossier.

    avant_demarrage : fonction appelée avec le dossier juste avant de rendre
    la main, pour y poser des fichiers que le démarrage doit trouver. Si elle
    lève, le bac est supprimé avant que l'erreur remonte : personne ne tient
    encore le dossier pour le nettoyer (C6-T7).
    """
    dossier = tempfile.mkdtemp(prefix="bilan-test-sandbox-")
    os.mkdir(os.path.join(dossier, "serveur"))
    os.mkdir(os.path.join(dossier, "formulaire"))
    # Le logo par défaut (C2-T2) : le serveur le valide au démarrage, et son
    # absence journaliserait « LOGO refus motif=absent » dans chaque bac.
    os.makedirs(os.path.join(dossier, "formulaire", "images"))
    for nom in ("serveur/serveur.py", "serveur/generer_autorite.py",
                "formulaire/index.html", "formulaire/index-v1.html",
                "formulaire/style.css",
                "formulaire/script.js", "formulaire/schema.json",
                "formulaire/version.json", "formulaire/images/favicon.jpeg"):
        shutil.copy(os.path.join(PROJET, nom), os.path.join(dossier, nom))

    sortie = subprocess.run(
        [sys.executable, os.path.join("serveur", "generer_autorite.py"),
         "127.0.0.1"],
        cwd=dossier, capture_output=True, text=True)
    assert sortie.returncode == 0, sortie.stderr

    port = port_libre()
    config = {"port": port, "dossier_pdf": "bilans",
              "utilisateur": UTILISATEUR,
              "mot_de_passe": serveur.hacher(MOT_DE_PASSE),
              "certificat": "certificat.pem",
              "cle_privee": "cle.pem"}
    config.update(config_extra or {})
    with open(os.path.join(dossier, "config.json"), "w") as f:
        json.dump(config, f)

    if avant_demarrage is not None:
        try:
            avant_demarrage(dossier)
        except BaseException:
            shutil.rmtree(dossier, ignore_errors=True)
            raise
    return dossier, port


def demarrer_sandbox_court(config_extra=None, attendre_demarrage_technique=False,
                           avant_demarrage=None):
    """Construit et démarre un serveur complet dans son propre bac à sable.

    Pour un test qui a besoin d'arrêter lui-même son serveur (ARRET,
    l'interrupteur de journal technique) plutôt que de partager celui, à
    vie plus longue, de ServeurEnMarche. Rend (dossier, port, processus) ;
    l'appelant nettoie (terminer le processus, puis supprimer le dossier).

    attendre_demarrage_technique : à True pour un appelant qui va envoyer un
    signal au processus (voir attendre_ligne_technique) — False par défaut,
    car certains appelants désactivent le journal technique
    (journal_technique=False), où DEMARRAGE ne s'écrirait jamais.

    avant_demarrage : fonction appelée avec le dossier du bac à sable juste
    avant le lancement du serveur, pour y poser des fichiers que le
    démarrage doit trouver (archives de journal, C4-T2).
    """
    dossier, port = preparer_sandbox(config_extra, avant_demarrage)

    processus = subprocess.Popen(
        # -u : sortie non bufferisée. Sans cela, le bloc d'informations
        # affiché au démarrage (dont l'avertissement d'identité, C2-T1)
        # reste dans le tampon de Python et ne traverse jamais le tuyau
        # avant un terminate() — un test qui lit cette sortie après coup
        # verrait une chaîne vide, pas l'absence réelle de l'avertissement.
        [sys.executable, "-u", os.path.join("serveur", "serveur.py")],
        cwd=dossier, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True)

    limite = time.monotonic() + 30
    while time.monotonic() < limite:
        if processus.poll() is not None:
            raise AssertionError(
                "le serveur s'est arrêté : " + processus.stdout.read())
        try:
            with socket.create_connection(("127.0.0.1", port), 0.2):
                break
        except OSError:
            time.sleep(0.05)
    else:
        raise AssertionError("le serveur n'a pas démarré à temps")

    if attendre_demarrage_technique:
        attendre_ligne_technique(dossier, "DEMARRAGE")

    return dossier, port, processus


@unittest.skipIf(cryptography_absente(),
                 "cryptography requis pour fabriquer les certificats")
class ServeurEnMarche(unittest.TestCase):
    """Un serveur réel, démarré une fois pour toute la classe."""

    @classmethod
    def setUpClass(cls):
        # L'arborescence du projet est reproduite à l'identique : les scripts
        # calculent leurs chemins à partir de leur propre emplacement.
        cls.dossier = tempfile.mkdtemp(prefix="bilan-test-")
        os.mkdir(os.path.join(cls.dossier, "serveur"))
        os.mkdir(os.path.join(cls.dossier, "formulaire"))
        os.makedirs(os.path.join(cls.dossier, "formulaire", "images"))
        for nom in ("serveur/serveur.py", "serveur/generer_autorite.py",
                    "formulaire/index.html", "formulaire/index-v1.html",
                    "formulaire/style.css",
                    "formulaire/script.js", "formulaire/schema.json",
                    "formulaire/version.json", "formulaire/images/favicon.jpeg"):
            shutil.copy(os.path.join(PROJET, nom),
                        os.path.join(cls.dossier, nom))

        sortie = subprocess.run(
            [sys.executable, os.path.join("serveur", "generer_autorite.py"),
             "127.0.0.1"],
            cwd=cls.dossier, capture_output=True, text=True)
        assert sortie.returncode == 0, sortie.stderr

        cls.port = port_libre()
        # Noms à vérifier absents du journal technique une fois TOUS les
        # tests de la classe exécutés (tearDownClass). Un dépôt abouti
        # laisse toujours son fichier dans bilans/, quel que soit le chemin
        # par lequel il est arrivé (deposer() ou une requête directe comme
        # test_sante_ne_rend_pas_muettes_les_requetes_suivantes) : c'est là
        # que tearDownClass les redérive, à la toute fin, plutôt que de
        # dépendre d'un enregistrement manuel qui finirait incomplet — le
        # motif maison. cls.noms_sensibles ne couvre donc plus que ce qui ne
        # laisse AUCUN fichier : un dépôt refusé, ou une sonde hostile qui
        # ne dépose jamais (voir enregistrer_nom_sensible). Les deux sources
        # sont réunies dans tearDownClass.
        cls.noms_sensibles = []
        with open(os.path.join(cls.dossier, "config.json"), "w") as f:
            json.dump({"port": cls.port, "dossier_pdf": "bilans",
                       "utilisateur": UTILISATEUR,
                       "mot_de_passe": serveur.hacher(MOT_DE_PASSE),
                       "certificat": "certificat.pem",
                       "cle_privee": "cle.pem"}, f)

        # Borne basse de demarre_le (test_etat_demarrage_et_identite).
        cls.lance_a = datetime.datetime.now()
        cls.processus = subprocess.Popen(
            [sys.executable, os.path.join("serveur", "serveur.py")],
            cwd=cls.dossier,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        # Le tube doit être vidé EN CONTINU (C7-T5). Le serveur écrit une
        # ligne sur stderr par requête ; sous Windows, le tampon d'un tube
        # est petit, et un tube jamais lu finit plein : chaque requête qui
        # journalise se bloque alors dans sys.stderr.write(), sans réponse,
        # et les tests expirent un par un en lecture TLS (ssl.recv_into) —
        # seule /sante, muette, répond encore. C'est le symptôme du
        # 14 octobre et du 3 novembre ; aucun risque au cabinet, où
        # pythonw n'a pas de stderr. Le fil garde la sortie pour les
        # messages d'échec.
        cls.sortie_serveur = []
        cls.lecteur = threading.Thread(
            target=lambda: cls.sortie_serveur.extend(iter(cls.processus.stdout.readline, "")),
            daemon=True)
        cls.lecteur.start()

        cls.contexte = ssl.create_default_context(
            cafile=os.path.join(cls.dossier, "autorite.crt"))

        # Attendre que le port réponde plutôt que de dormir un temps fixe.
        try:
            limite = time.monotonic() + 30
            while time.monotonic() < limite:
                if cls.processus.poll() is not None:
                    cls.lecteur.join(timeout=5)
                    raise AssertionError("le serveur s'est arrêté : "
                                         + "".join(cls.sortie_serveur))
                try:
                    with socket.create_connection(("127.0.0.1", cls.port), 0.2):
                        break
                except OSError:
                    time.sleep(0.05)
            else:
                raise AssertionError(
                    "le serveur n'a pas démarré à temps ; il écoute peut-être "
                    "en IPv6 seul, ou reste bloqué avant le listen()")
        except BaseException:
            # Sans cela, un échec ici laisse le serveur tourner et le port
            # occupé pour les exécutions suivantes.
            cls.processus.terminate()
            cls.processus.wait(timeout=10)
            cls.lecteur.join(timeout=5)
            cls.processus.stdout.close()
            shutil.rmtree(cls.dossier, ignore_errors=True)
            raise

    @classmethod
    def tearDownClass(cls):
        cls.processus.terminate()
        cls.processus.wait(timeout=10)
        cls.lecteur.join(timeout=5)
        cls.processus.stdout.close()
        try:
            # Contrôle final, sur l'intégralité du fichier accumulé par
            # TOUS les tests de la classe, quel que soit l'ordre dans
            # lequel ils se sont exécutés : un contrôle fait au passage
            # d'un seul test ne voit que ce qui est déjà écrit à cet
            # instant, pas les lignes produites par les tests suivants
            # (constat d'audit C4-T1).
            technique = os.path.join(cls.dossier, "technique.log")
            if os.path.exists(technique):
                with open(technique, encoding="utf-8") as f:
                    contenu_technique = f.read()

                # Levées explicites, jamais `assert` : sous `python -O`, un
                # `assert` nu est éliminé et cette garde — celle qui prouve
                # qu'aucun nom de patient n'entre dans un fichier conçu pour
                # circuler — ne lèverait plus rien (constat d'audit).
                message = chercher_adresse(contenu_technique)
                if message is not None:
                    raise AssertionError(message)

                # Union des deux sources : les fichiers réellement
                # déposés (bilans/, qui couvre tout dépôt abouti, quel que
                # soit le chemin par lequel il est arrivé) et les noms
                # explicitement enregistrés pour ce qui ne laisse aucun
                # fichier (dépôt refusé, sonde hostile).
                bilans = os.path.join(cls.dossier, "bilans")
                noms_a_verifier = list(cls.noms_sensibles)
                if os.path.isdir(bilans):
                    noms_a_verifier.extend(os.listdir(bilans))

                restes = [ligne.partition(" ")[2]
                         for ligne in contenu_technique.splitlines()]
                # Toutes les violations sont collectées plutôt que de
                # s'arrêter à la première : un nom masqué par un autre dans
                # le même message serait une preuve ambiguë.
                fuites = []
                for nom in noms_a_verifier:
                    for fragment in fragments_nom(nom):
                        if any(fragment in reste for reste in restes):
                            fuites.append((nom, fragment))
                            break
                if fuites:
                    raise AssertionError(
                        "fragment(s) de nom figurant dans le journal "
                        "technique : " + "; ".join(
                            "« {} » (du nom « {} »)".format(fragment, nom)
                            for nom, fragment in fuites))

                if UTILISATEUR in contenu_technique:
                    raise AssertionError(
                        "l'identifiant de compte figure dans le journal "
                        "technique")
                if MOT_DE_PASSE in contenu_technique:
                    raise AssertionError(
                        "le mot de passe figure dans le journal technique")
        finally:
            shutil.rmtree(cls.dossier, ignore_errors=True)

    # --- outillage ---------------------------------------------------------

    def requete(self, methode, chemin, corps=None, entetes=None,
                utilisateur=UTILISATEUR, mot_de_passe=MOT_DE_PASSE):
        entetes = dict(entetes or {})
        if utilisateur is not None:
            jeton = base64.b64encode(
                "{}:{}".format(utilisateur, mot_de_passe).encode("utf-8"))
            entetes["Authorization"] = "Basic " + jeton.decode("ascii")

        connexion = http.client.HTTPSConnection(
            "127.0.0.1", self.port, context=self.contexte, timeout=10)
        try:
            connexion.request(methode, chemin, body=corps, headers=entetes)
            reponse = connexion.getresponse()
            return reponse.status, reponse.getheaders(), reponse.read()
        finally:
            connexion.close()

    def deposer(self, nom, contenu=PDF):
        self.enregistrer_nom_sensible(nom)
        entete = base64.b64encode(nom.encode("utf-8")).decode("ascii")
        return self.requete("POST", "/depot", contenu, {"X-Fichier": entete})

    def enregistrer_nom_sensible(self, nom):
        """Un nom à vérifier absent du journal technique, lu à la toute fin
        par tearDownClass — appelé par deposer(), et directement par un test
        qui emploie un nom sensible sans le déposer (une URL hostile, par
        exemple)."""
        type(self).noms_sensibles.append(nom)

    @property
    def bilans(self):
        return os.path.join(self.dossier, "bilans")

    @property
    def technique(self):
        return os.path.join(self.dossier, "technique.log")

    def fragments_nom(self, nom):
        """Délègue à la fonction de module : une seule dérivation, jamais
        retranscrite — sinon une règle changée d'un seul côté rendrait la
        garde fausse en silence (constat de revue C4-T1)."""
        return fragments_nom(nom)

    def aucune_adresse_dans(self, texte):
        """Délègue à chercher_adresse(), fonction de module : même motif
        qu'au-dessus."""
        message = chercher_adresse(texte)
        if message is not None:
            self.fail(message)

    # --- TLS ---------------------------------------------------------------

    def test_certificat_valide_pour_l_autorite(self):
        # create_default_context vérifie la chaîne ET le nom : la connexion
        # n'aboutit que si le subjectAltName contient 127.0.0.1.
        statut, _, _ = self.requete("GET", "/")
        self.assertEqual(statut, 200)

    def test_tls_ancien_refuse(self):
        contexte = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        contexte.check_hostname = False
        contexte.verify_mode = ssl.CERT_NONE
        with warnings.catch_warnings():
            # TLSv1_1 est déprécié côté client ; c'est précisément ce qu'on
            # veut proposer au serveur pour le voir refuser.
            warnings.simplefilter("ignore", DeprecationWarning)
            contexte.maximum_version = ssl.TLSVersion.TLSv1_1
        with self.assertRaises(ssl.SSLError):
            with socket.create_connection(("127.0.0.1", self.port), 10) as brute:
                with contexte.wrap_socket(brute):
                    pass

    def test_alpn_annonce_http11(self):
        contexte = ssl.create_default_context(
            cafile=os.path.join(self.dossier, "autorite.crt"))
        contexte.set_alpn_protocols(["h2", "http/1.1"])
        with socket.create_connection(("127.0.0.1", self.port), 10) as brute:
            with contexte.wrap_socket(brute, server_hostname="127.0.0.1") as tls:
                # Le client propose h2 en premier ; le serveur ne parlant que
                # HTTP/1.1 doit le dire, sinon Chrome coupe sans un octet.
                self.assertEqual(tls.selected_alpn_protocol(), "http/1.1")

    # --- authentification --------------------------------------------------

    def test_sans_authentification(self):
        statut, entetes, _ = self.requete("GET", "/", utilisateur=None)
        self.assertEqual(statut, 401)
        self.assertIn("WWW-Authenticate", dict(entetes))

    def test_mauvais_mot_de_passe(self):
        statut, _, _ = self.requete("GET", "/", mot_de_passe="faux")
        self.assertEqual(statut, 401)

    def test_mauvais_utilisateur(self):
        statut, _, _ = self.requete("GET", "/", utilisateur="intrus")
        self.assertEqual(statut, 401)

    def test_identifiant_accentue_accepte(self):
        # Régression : compare_digest lève TypeError sur une str non-ASCII,
        # ce qui tuait le thread et fermait la connexion sans réponse.
        statut, _, _ = self.requete("GET", "/")
        self.assertEqual(statut, 200)

    # --- surface exposée ---------------------------------------------------

    def test_fichiers_sensibles_inatteignables(self):
        # Filtrés par extension (.py, .pem, .log n'entrent jamais dans
        # EXTENSIONS_SERVIES) : toujours 403, quelle que soit la racine web.
        for chemin in ("/serveur.py", "/cle.pem",
                       "/autorite-cle.pem", "/journal.log"):
            for methode in ("GET", "HEAD"):
                with self.subTest(chemin=chemin, methode=methode):
                    statut, _, _ = self.requete(methode, chemin)
                    self.assertEqual(statut, 403)

    def test_config_json_inatteignable(self):
        # Depuis que .json est servi (C1-T3, pour schema.json), /config.json
        # n'est plus filtré par extension : il l'est par l'emplacement. Le
        # fichier vit à la racine du projet (RACINE), pas dans la racine web
        # (FORMULAIRE) : la requête devient 404 (fichier introuvable dans
        # formulaire/), là où elle était 403 (type de fichier) auparavant.
        # Les deux codes disent la même chose — inatteignable — donc les deux
        # sont acceptés ici plutôt que de figer un comportement interne.
        for methode in ("GET", "HEAD"):
            with self.subTest(methode=methode):
                statut, _, _ = self.requete(methode, "/config.json")
                self.assertIn(statut, (403, 404))

    def test_ressources_du_formulaire_servies(self):
        for chemin in ("/", "/index.html", "/style.css", "/script.js"):
            with self.subTest(chemin=chemin):
                statut, _, _ = self.requete("GET", chemin)
                self.assertEqual(statut, 200)

    def test_fiche_de_secours_servie_authentifiee(self):
        # formulaire/index-v1.html (C1-T3b) est le repli de consultation,
        # niveau 1 du retour arrière : derrière la même authentification que
        # le reste, ni plus accessible ni moins.
        statut, _, _ = self.requete("GET", "/index-v1.html")
        self.assertEqual(statut, 200)

    def test_fiche_de_secours_jamais_sans_authentification(self):
        statut, _, _ = self.requete("GET", "/index-v1.html", utilisateur=None)
        self.assertEqual(statut, 401)

    def test_json_du_formulaire_servi(self):
        # schema.json (C1-T3) doit être lisible, authentifié, avec le bon
        # type de contenu : c'est ce que lit formulaire/moteur/rendu.js.
        statut, entetes, corps = self.requete("GET", "/schema.json")
        self.assertEqual(statut, 200)
        entetes = {c.lower(): v for c, v in entetes}
        self.assertTrue(entetes.get("content-type", "").startswith("application/json"))
        json.loads(corps)  # le fichier copié dans le bac à sable est un JSON valide

    def test_json_du_formulaire_toujours_authentifie(self):
        statut, _, _ = self.requete("GET", "/schema.json", utilisateur=None)
        self.assertEqual(statut, 401)

    def test_entetes_de_securite(self):
        _, entetes, _ = self.requete("GET", "/")
        entetes = {c.lower(): v for c, v in entetes}
        self.assertEqual(entetes.get("x-content-type-options"), "nosniff")
        self.assertEqual(entetes.get("referrer-policy"), "no-referrer")
        self.assertEqual(entetes.get("cache-control"), "no-store")
        self.assertEqual(entetes.get("x-frame-options"), "DENY")

    # --- dépôt -------------------------------------------------------------

    def test_depot_nominal(self):
        statut, _, corps = self.deposer("Bilan Élodie Dupré.pdf")
        self.assertEqual(statut, 200)
        resultat = json.loads(corps)
        self.assertTrue(resultat["ok"])
        self.assertEqual(resultat["fichier"], "Bilan Elodie Dupre.pdf")
        with open(os.path.join(self.bilans, resultat["fichier"]), "rb") as f:
            self.assertEqual(f.read(), PDF)

    def test_depot_sans_authentification(self):
        statut, _, _ = self.requete("POST", "/depot", PDF, utilisateur=None)
        self.assertEqual(statut, 401)

    def test_non_pdf_refuse(self):
        statut, _, corps = self.deposer("faux.pdf", b"MZ\x90\x00 pas un pdf")
        self.assertEqual(statut, 400)
        self.assertIn("erreur", json.loads(corps))

    def test_traversee_reste_dans_le_dossier(self):
        statut, _, corps = self.deposer("../../../../tmp/evasion-test.pdf")
        self.assertEqual(statut, 200)
        self.assertEqual(json.loads(corps)["fichier"], "evasion-test.pdf")
        self.assertTrue(os.path.exists(
            os.path.join(self.bilans, "evasion-test.pdf")))
        self.assertFalse(os.path.exists("/tmp/evasion-test.pdf"))

    def test_collision_ne_perd_aucun_bilan(self):
        _, _, premier = self.deposer("collision.pdf")
        _, _, second = self.deposer("collision.pdf")
        self.assertEqual(json.loads(premier)["fichier"], "collision.pdf")
        self.assertEqual(json.loads(second)["fichier"], "collision-2.pdf")

    def test_aucun_fichier_partiel_dans_le_dossier(self):
        self.deposer("propre.pdf")
        self.assertEqual([f for f in os.listdir(self.bilans)
                          if f.endswith(".part")], [])

    def test_corps_vide_refuse(self):
        statut, _, _ = self.requete("POST", "/depot", b"")
        self.assertEqual(statut, 400)

    def test_route_inconnue(self):
        statut, _, _ = self.requete("POST", "/autre", PDF)
        self.assertEqual(statut, 404)

    # --- identité du cabinet (C2-T1) ----------------------------------------

    def test_cabinet_sans_authentification_401(self):
        # Contrairement à /sante : des coordonnées professionnelles ne sont
        # pas un secret, mais rien n'oblige à les offrir à qui scanne le
        # port (décision D2). Corps vide : rien ne doit fuiter avant même
        # l'authentification.
        statut, entetes, corps = self.requete("GET", "/cabinet", utilisateur=None)
        self.assertEqual(statut, 401)
        self.assertIn("WWW-Authenticate", dict(entetes))
        self.assertEqual(corps, b"")

    def test_cabinet_authentifie_200_liste_blanche(self):
        statut, entetes, corps = self.requete("GET", "/cabinet")
        self.assertEqual(statut, 200)
        entetes_min = {c.lower(): v for c, v in entetes}
        self.assertEqual(entetes_min.get("content-type"),
                         "application/json; charset=utf-8")
        donnees = json.loads(corps.decode("utf-8"))
        self.assertEqual(set(donnees), set(serveur.CLES_CABINET))

        # Liste blanche (décision D4) : aucune clé de CONFIG_DEFAUT en dehors
        # de "cabinet" ne doit jamais apparaître dans cette réponse, dérivée
        # du vocabulaire fermé plutôt que transcrite.
        interdites = set(serveur.CONFIG_DEFAUT) - {"cabinet"}
        self.assertEqual(interdites & set(donnees), set())
        for champ in ("mot_de_passe", "utilisateur", "certificat",
                     "cle_privee", "dossier_pdf", "port"):
            self.assertNotIn(champ, donnees)

    def test_cabinet_cache_control_unique(self):
        _, entetes, _ = self.requete("GET", "/cabinet")
        occurrences = [v for c, v in entetes if c.lower() == "cache-control"]
        self.assertEqual(occurrences, ["no-store"])

    def test_cabinet_rend_le_logo_par_defaut_servi(self):
        # C2-T2, critère 11. Le chemin est dérivé de la source, jamais
        # recopié ; il doit être servi, et rien n'a été journalisé : un logo
        # valide ne laisse aucune ligne LOGO.
        defaut = serveur.CONFIG_DEFAUT["cabinet"]["logo"]
        _, _, corps = self.requete("GET", "/cabinet")
        self.assertEqual(json.loads(corps.decode("utf-8"))["logo"], defaut)

        statut, entetes, _ = self.requete("GET", "/" + defaut)
        self.assertEqual(statut, 200)
        types = [v for c, v in entetes if c.lower() == "content-type"]
        self.assertEqual(types, ["image/jpeg"])

        with open(self.technique, encoding="utf-8") as f:
            evenements = [ligne.split(" ", 2)[1]
                          for ligne in f.read().splitlines() if ligne]
        self.assertNotIn("LOGO", evenements)
        journal = os.path.join(self.dossier, "journal.log")
        with open(journal, encoding="utf-8") as f:
            self.assertNotIn("LOGO", f.read())

    # --- sonde de santé ----------------------------------------------------

    def test_sante_repond_sans_authentification(self):
        # Toute la valeur de la sonde tient là : elle doit permettre de
        # distinguer « serveur arrêté » de « mot de passe refusé », donc
        # répondre à une tablette qui n'a pas encore d'identifiants.
        statut, entetes, corps = self.requete("GET", "/sante",
                                              utilisateur=None)
        self.assertEqual(statut, 200)
        self.assertEqual(json.loads(corps.decode("utf-8")), {"etat": "ok"})
        types = [v for n, v in entetes if n.lower() == "content-type"]
        self.assertEqual(types, ["application/json; charset=utf-8"])

    def test_sante_en_head_sans_corps(self):
        statut, _, corps = self.requete("HEAD", "/sante", utilisateur=None)
        self.assertEqual(statut, 200)
        self.assertEqual(corps, b"")

    def test_sante_ne_divulgue_rien(self):
        # Le port ouvert répond déjà 401 : la sonde ne doit rien apprendre de
        # plus à qui la sollicite. Ni version, ni chemins, ni identifiant.
        _, _, corps = self.requete("GET", "/sante", utilisateur=None)
        texte = corps.decode("utf-8")
        self.assertNotIn(UTILISATEUR, texte)
        self.assertNotIn("bilans", texte)
        self.assertNotIn(str(self.port), texte)

    def test_sante_n_encombre_pas_le_journal(self):
        journal = os.path.join(self.dossier, "journal.log")
        avant = os.path.getsize(journal) if os.path.exists(journal) else 0
        # Le journal technique doit rester silencieux aussi, sous peine de
        # milliers de lignes par jour (décision D2, point 3).
        avant_technique = (os.path.getsize(self.technique)
                           if os.path.exists(self.technique) else 0)
        for _ in range(5):
            self.requete("GET", "/sante", utilisateur=None)
        apres = os.path.getsize(journal) if os.path.exists(journal) else 0
        apres_technique = (os.path.getsize(self.technique)
                           if os.path.exists(self.technique) else 0)
        self.assertEqual(avant, apres)
        self.assertEqual(avant_technique, apres_technique)

    def test_sante_ne_rend_pas_muettes_les_requetes_suivantes(self):
        # Même instance de gestionnaire sur une connexion persistante : le
        # silence de la sonde ne doit pas déteindre sur le dépôt qui suit.
        connexion = http.client.HTTPSConnection(
            "127.0.0.1", self.port, context=self.contexte, timeout=10)
        self.addCleanup(connexion.close)
        connexion.request("GET", "/sante")
        connexion.getresponse().read()

        jeton = base64.b64encode(
            "{}:{}".format(UTILISATEUR, MOT_DE_PASSE).encode("utf-8"))
        nom = base64.b64encode("Bilan_trace.pdf".encode("utf-8"))
        connexion.request("POST", "/depot", PDF, {
            "Authorization": "Basic " + jeton.decode("ascii"),
            "X-Fichier": nom.decode("ascii")})
        self.assertEqual(connexion.getresponse().status, 200)

        with open(os.path.join(self.dossier, "journal.log"),
                  encoding="utf-8") as f:
            self.assertIn("Bilan_trace.pdf", f.read())

    # --- journal technique (C4-T1) ------------------------------------------

    def tls_1_1_refuse(self):
        """Reprend le patron de test_tls_ancien_refuse : une connexion TLS 1.1
        que le serveur doit refuser, ce qui produit un TLS_REFUSE."""
        contexte = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        contexte.check_hostname = False
        contexte.verify_mode = ssl.CERT_NONE
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            contexte.maximum_version = ssl.TLSVersion.TLSv1_1
        with self.assertRaises(ssl.SSLError):
            with socket.create_connection(("127.0.0.1", self.port), 10) as brute:
                with contexte.wrap_socket(brute):
                    pass

    def test_scenario_complet_reconstituable(self):
        # Dépôt authentifié réussi, dépôt refusé pour non-PDF, requête sans
        # authentification, requête avec mauvais mot de passe, connexion TLS
        # 1.1 refusée : l'ordre du §9.
        statut, _, corps = self.deposer("Bilan_scenario.pdf")
        self.assertEqual(statut, 200)
        self.requete("POST", "/depot", b"MZ pas un pdf", {
            "X-Fichier": base64.b64encode(b"faux.pdf").decode("ascii")})
        self.requete("GET", "/", utilisateur=None)
        self.requete("GET", "/", mot_de_passe="mauvais-mot-de-passe")
        self.tls_1_1_refuse()

        with open(self.technique, encoding="utf-8") as f:
            contenu = f.read()

        # La version vient de formulaire/version.json, la source unique
        # (C4-T4) : dérivée, jamais recopiée dans le motif.
        version = serveur.lire_version(os.path.join(PROJET, "formulaire", "version.json"))
        self.assertRegex(contenu, r"DEMARRAGE version=" + re.escape(version)
                         + r" port=\d+ certificat=[0-9a-f]{16} .+")
        self.assertIn("DEPOT ok {} octets".format(len(PDF)), contenu)
        self.assertIn("AUTH_REFUSEE", contenu)
        self.assertIn("TLS_REFUSE", contenu)
        # Premier démarrage de ce serveur : le dossier du bac à sable est
        # neuf, donc aucune ligne DEMARRAGE antérieure à comparer.
        self.assertIn("premier démarrage observé", contenu)

    def test_journal_technique_sans_donnee_identifiante(self):
        # Le test anti-fuite : celui qui tient lieu de preuve en audit. Le
        # nom déposé porte un accent et un motif de nom propre (ce qui a
        # déjà coûté deux fois dans ce dépôt).
        nom = "Bilan_2026-08-22_Dupré-Léa.pdf"
        statut, _, _ = self.deposer(nom)
        self.assertEqual(statut, 200)

        self.requete("POST", "/depot", b"MZ pas un pdf", {
            "X-Fichier": base64.b64encode(b"faux.pdf").decode("ascii")})
        self.requete("GET", "/", utilisateur=None)
        self.requete("GET", "/", mot_de_passe="mauvais-mot-de-passe")
        self.tls_1_1_refuse()

        if os.name != "nt":
            # Un échec d'écriture réel, avec un nom de patient dans le
            # chemin : la cause la plus probable de fuite (décision D4).
            os.chmod(self.bilans, 0o500)
            try:
                statut, _, _ = self.deposer(nom)
                self.assertEqual(statut, 500)
            finally:
                os.chmod(self.bilans, 0o700)

        with open(self.technique, encoding="utf-8") as f:
            contenu = f.read()

        self.aucune_adresse_dans(contenu)

        # Comme pour le motif IPv6, le fragment se cherche dans la ligne
        # privée de son premier mot : l'horodatage du jour même contient
        # littéralement l'année du bilan ("2026"), ce qui n'est pas une
        # fuite mais ferait rougir le test à tort.
        restes = [ligne.partition(" ")[2] for ligne in contenu.splitlines()]
        for fragment in self.fragments_nom(nom):
            with self.subTest(fragment=fragment):
                for reste in restes:
                    self.assertNotIn(fragment, reste)
        self.assertNotIn(UTILISATEUR, contenu)
        self.assertNotIn(MOT_DE_PASSE, contenu)

    def test_journal_nominatif_toujours_nominatif(self):
        # Garde-fou inverse : journal.log reste la traçabilité du cabinet.
        # Un futur « nettoyage » ne doit pas le vider à son tour.
        statut, _, _ = self.deposer("Bilan_toujours_nominatif.pdf")
        self.assertEqual(statut, 200)
        with open(os.path.join(self.dossier, "journal.log"),
                  encoding="utf-8") as f:
            self.assertIn("Bilan_toujours_nominatif.pdf", f.read())

    def test_chemin_hostile_absent_du_journal_technique(self):
        # Un nom de patient porté par l'URL elle-même (jamais déposé), une
        # traversée de répertoire, sa forme encodée en pourcents, et des
        # séparateurs Windows : classe_route() doit les absorber tous les
        # quatre dans le vocabulaire fermé de ROUTES_TECHNIQUES, sans qu'un
        # seul caractère du chemin brut ne s'y recopie. Le contrôle lui-même
        # a lieu à la fin, dans tearDownClass, sur le fichier complet.
        nom_dans_l_url = "Bilan_2026-11-03_Castel-Noe.pdf"
        self.enregistrer_nom_sensible(nom_dans_l_url)

        chemins_hostiles = (
            "/" + nom_dans_l_url,
            "/../../../../etc/passwd",
            "/%2e%2e/%2e%2e/%2e%2e/etc/passwd",
            "/..\\..\\..\\windows\\win.ini",
        )
        for chemin in chemins_hostiles:
            for methode in ("GET", "HEAD"):
                with self.subTest(chemin=chemin, methode=methode):
                    statut, _, _ = self.requete(methode, chemin)
                    self.assertIn(statut, (403, 404))

    def test_reponse_journalisee_avec_code_reel(self):
        # Rien n'ancrait l'émission de REPONSE (constat d'audit) : si cette
        # branche de log_message() disparaît ou se dégrade, la suite doit
        # rougir ici, pas seulement par ricochet sur le test anti-fuite.
        statut, _, _ = self.requete("GET", "/")
        self.assertEqual(statut, 200)
        statut, _, _ = self.requete("POST", "/autre", PDF)
        self.assertEqual(statut, 404)

        with open(self.technique, encoding="utf-8") as f:
            contenu = f.read()

        self.assertIn("REPONSE methode=GET route=formulaire code=200", contenu)
        self.assertIn("REPONSE methode=POST route=autre code=404", contenu)
        # Témoin : au moins une ligne REPONSE porte un code réel, non nul —
        # sans quoi l'extraction serait retombée sur son repli par défaut.
        self.assertRegex(contenu, r"REPONSE methode=\w+ route=\w+ code=[1-9]\d{2}")

    # --- page d'état (C4-T3) -------------------------------------------------

    def etat(self, **options):
        """GET /etat en JSON, authentifié : (statut, entêtes, dictionnaire)."""
        entetes = {"Accept": "application/json"}
        statut, retour, corps = self.requete("GET", "/etat", entetes=entetes, **options)
        return statut, {c.lower(): v for c, v in retour}, (
            json.loads(corps.decode("utf-8")) if statut == 200 else corps)

    def etat_html(self):
        statut, retour, corps = self.requete("GET", "/etat")
        self.assertEqual(statut, 200)
        return {c.lower(): v for c, v in retour}, corps.decode("utf-8")

    def test_etat_sans_authentification_401(self):
        statut, entetes, corps = self.requete("GET", "/etat", utilisateur=None)
        self.assertEqual(statut, 401)
        self.assertIn("WWW-Authenticate", dict(entetes))
        self.assertEqual(corps, b"")

    def test_etat_head_sans_authentification_401(self):
        statut, entetes, corps = self.requete("HEAD", "/etat", utilisateur=None)
        self.assertEqual(statut, 401)
        self.assertIn("WWW-Authenticate", dict(entetes))
        self.assertEqual(corps, b"")

    def test_etat_mauvais_mot_de_passe_401(self):
        for methode in ("GET", "HEAD"):
            with self.subTest(methode=methode):
                statut, entetes, corps = self.requete(
                    methode, "/etat", mot_de_passe="faux")
                self.assertEqual(statut, 401)
                self.assertIn("WWW-Authenticate", dict(entetes))
                self.assertEqual(corps, b"")
        statut, _, corps = self.requete("GET", "/etat", utilisateur="intrus")
        self.assertEqual(statut, 401)
        self.assertEqual(corps, b"")

    def test_etat_json_liste_blanche(self):
        statut, entetes, etat = self.etat()
        self.assertEqual(statut, 200)
        self.assertEqual(entetes["content-type"], "application/json; charset=utf-8")
        self.assertEqual(len(serveur.CLES_ETAT), 9)
        self.assertEqual(set(etat), set(serveur.CLES_ETAT))
        # Aucune clé de configuration n'y figure (« journal_technique » est
        # un nom partagé : ici, ce sont les lignes du journal, pas le réglage).
        for champ in ("mot_de_passe", "utilisateur", "port", "dossier_pdf",
                      "cabinet", "certificat", "cle_privee"):
            self.assertNotIn(champ, etat)

    def test_etat_html(self):
        entetes, page = self.etat_html()
        self.assertEqual(entetes["content-type"], "text/html; charset=utf-8")
        self.assertIn("default-src 'none'", entetes["content-security-policy"])
        self.assertNotIn("<script", page.lower())
        self.assertIn('<html lang="fr">', page)
        version = serveur.lire_version(
            os.path.join(self.dossier, "formulaire", "version.json"))
        self.assertNotEqual(version, serveur.VERSION_INCONNUE)
        self.assertIn(version, page)

    def test_etat_negociation_du_format(self):
        cas = [
            ("application/json", "application/json"),
            ("APPLICATION/JSON", "application/json"),
            ("text/html,application/json;q=0.9", "application/json"),
            ("text/html,application/xhtml+xml", "text/html"),
            ("*/*", "text/html"),
        ]
        for accept, attendu in cas:
            with self.subTest(accept=accept):
                statut, entetes, _ = self.requete(
                    "GET", "/etat", entetes={"Accept": accept})
                self.assertEqual(statut, 200)
                types = [v for c, v in entetes if c.lower() == "content-type"]
                self.assertEqual(len(types), 1)
                self.assertTrue(types[0].startswith(attendu), types)

    def test_etat_chaine_de_requete_ignoree(self):
        statut, _, _ = self.requete("GET", "/etat?x=1")
        self.assertEqual(statut, 200)

    def test_etat_head_authentifie_sans_corps(self):
        statut, entetes, corps = self.requete("HEAD", "/etat")
        self.assertEqual(statut, 200)
        self.assertEqual(corps, b"")
        longueur = [v for c, v in entetes if c.lower() == "content-length"]
        self.assertEqual(len(longueur), 1)
        self.assertGreater(int(longueur[0]), 0)

    def test_etat_content_length_exact(self):
        for accept in ("application/json", "text/html"):
            with self.subTest(accept=accept):
                _, entetes, corps = self.requete(
                    "GET", "/etat", entetes={"Accept": accept})
                longueur = [v for c, v in entetes if c.lower() == "content-length"]
                self.assertEqual(longueur, [str(len(corps))])

    def test_etat_cache_control_unique(self):
        _, entetes, _ = self.requete("GET", "/etat")
        occurrences = [v for c, v in entetes if c.lower() == "cache-control"]
        self.assertEqual(occurrences, ["no-store"])

    def test_etat_version_source_unique(self):
        version = serveur.lire_version(
            os.path.join(self.dossier, "formulaire", "version.json"))
        self.assertNotEqual(version, serveur.VERSION_INCONNUE)
        _, _, etat = self.etat()
        self.assertEqual(etat["version"], version)
        with open(self.technique, encoding="utf-8") as f:
            self.assertIn("DEMARRAGE version={} ".format(version), f.read())

        # Garde statique : un seul appel à lire_version() dans demarrer(), et
        # aucun dans les fonctions de la page. Une seconde source du numéro
        # finirait par diverger (C4-T4).
        with open(serveur.__file__, encoding="utf-8") as f:
            arbre = ast.parse(f.read())
        fonctions = {}
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.FunctionDef):
                fonctions[noeud.name] = noeud

        def appels(nom):
            if nom not in fonctions:
                self.fail("fonction introuvable : " + nom)
            return [n for n in ast.walk(fonctions[nom])
                    if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "lire_version"]

        self.assertEqual(len(appels("demarrer")), 1)
        for nom in ("construire_etat", "rendre_etat_html", "rendre_etat_json",
                    "repondre_etat", "dernieres_lignes_techniques"):
            with self.subTest(fonction=nom):
                self.assertEqual(appels(nom), [])

    def test_etat_dernier_depot(self):
        # ServeurEnMarche est partagé et l'ordre des tests n'est pas garanti :
        # la valeur « null » se vérifie en unitaire (PageEtat). Ici, la date
        # APRÈS un dépôt de ce test.
        statut, _, _ = self.deposer("Cuvelier-Océane_wk9.pdf")
        self.assertEqual(statut, 200)
        _, _, etat = self.etat()
        depot = datetime.datetime.fromisoformat(etat["dernier_depot"])
        ecart = abs((datetime.datetime.now() - depot).total_seconds())
        self.assertLess(ecart, 60)

    def test_etat_demarrage_et_identite(self):
        _, _, etat = self.etat()
        demarre = datetime.datetime.fromisoformat(etat["demarre_le"])
        # Ni après maintenant, ni avant le lancement du bac à sable : une
        # marge de 2 s couvre la troncature à la seconde de l'horodatage.
        marge = datetime.timedelta(seconds=2)
        self.assertLess(demarre, datetime.datetime.now() + marge)
        self.assertGreater(demarre, self.lance_a - marge)
        # Le bac à sable n'a pas de bloc "cabinet" : identité non renseignée.
        self.assertIs(etat["identite_cabinet"], False)
        self.assertIsInstance(etat["disque_libre_octets"], int)
        self.assertGreater(etat["disque_libre_octets"], 0)

    def test_etat_certificat(self):
        from cryptography import x509
        with open(os.path.join(self.dossier, "certificat.pem"), "rb") as f:
            certificat = x509.load_pem_x509_certificate(f.read())
        attendu = getattr(certificat, "not_valid_after_utc", None)
        if attendu is None:
            attendu = certificat.not_valid_after.replace(tzinfo=datetime.timezone.utc)

        _, _, etat = self.etat()
        lu = datetime.datetime.strptime(
            etat["certificat_expire_le"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=datetime.timezone.utc)
        self.assertEqual(lu, attendu.replace(microsecond=0))

        with open(self.technique, encoding="utf-8") as f:
            lignes = [l for l in f if " DEMARRAGE " in l]
        self.assertEqual(len(lignes), 1)
        empreinte = re.search(r"certificat=([0-9a-f]{16}) ", lignes[0]).group(1)
        self.assertEqual(etat["certificat_empreinte"], empreinte)

    def test_etat_verdict_adresse(self):
        _, _, etat = self.etat()
        self.assertIn(etat["certificat_adresse"], serveur.VERDICTS_ADRESSE)
        # Le certificat du bac à sable ne couvre que localhost, 127.0.0.1 et
        # ::1 : des adresses de boucle, rien à comparer.
        self.assertEqual(etat["certificat_adresse"], "indéterminé")

    def test_etat_sans_adresse(self):
        # Voie A (décision n°1) : aucune adresse sur la page, pas même celle
        # du serveur. chercher_adresse est importée, pas recopiée.
        self.requete("GET", "/", utilisateur=None)
        self.requete("GET", "/", mot_de_passe="faux")
        _, _, brut = self.requete(
            "GET", "/etat", entetes={"Accept": "application/json"})
        texte_json = brut.decode("utf-8")
        etat = json.loads(texte_json)
        _, page = self.etat_html()

        self.assertEqual(chercher_adresse(texte_json, ipv6=False), None)
        self.assertEqual(chercher_adresse(page, ipv6=False), None)
        # IPv6 : sur les valeurs hors horodatages, où « 12:34:56 » n'est pas
        # une adresse. Les lignes de journal passent par chercher_adresse,
        # qui ôte leur premier mot (l'horodatage).
        for cle, valeur in etat.items():
            if cle in serveur.CHAMPS_ETAT_HORODATES:
                continue
            texte = "\n".join(valeur) if isinstance(valeur, list) else str(valeur)
            with self.subTest(cle=cle):
                self.assertIsNone(chercher_adresse(texte))
        self.assertTrue(etat["journal_technique"])  # ancrage : il y a des lignes à fouiller
        # Témoin : la garde mord. Une adresse dans la page serait vue.
        self.assertIsNotNone(chercher_adresse(texte_json + " 192.0.2.7", ipv6=False))
        self.assertIsNotNone(chercher_adresse("2026-11-06T10:00:00 TLS fe80::1\n"))

    def test_etat_sans_nom_de_fichier(self):
        nom = "Quenehervé-Maëlys_xq7.pdf"
        statut, _, corps = self.deposer(nom)
        self.assertEqual(statut, 200)
        fichier = json.loads(corps)["fichier"]

        # Ancrage : le nom choisi donne des fragments qui mordent, et aucun
        # n'est un nombre (l'année du jour les ferait rougir à tort).
        fragments = self.fragments_nom(nom)
        self.assertGreaterEqual(len(fragments), 3)
        self.assertFalse([f for f in fragments if f.isdigit()])
        fragments = fragments + self.fragments_nom(fichier)

        with open(os.path.join(self.dossier, "config.json"), encoding="utf-8") as f:
            empreinte_mdp = json.load(f)["mot_de_passe"]
        interdits = [self.dossier, self.bilans, UTILISATEUR, MOT_DE_PASSE, empreinte_mdp]

        _, _, brut = self.requete("GET", "/etat", entetes={"Accept": "application/json"})
        _, page = self.etat_html()
        for nom_rendu, texte in (("JSON", brut.decode("utf-8")), ("HTML", page)):
            for chaine in fragments + interdits:
                with self.subTest(rendu=nom_rendu, chaine=chaine):
                    self.assertNotIn(chaine, texte)

    def test_etat_lignes_du_journal_technique(self):
        # Au-delà de 30 lignes, pour que la borne morde.
        for _ in range(serveur.LIGNES_ETAT + 2):
            self.requete("GET", "/schema.json")
        _, _, etat = self.etat()
        lignes = etat["journal_technique"]

        with open(self.technique, encoding="utf-8") as f:
            reel = f.read().splitlines()
        with open(os.path.join(self.dossier, "journal.log"), encoding="utf-8") as f:
            nominatif = f.read().splitlines()

        self.assertEqual(len(lignes), serveur.LIGNES_ETAT)
        for ligne in lignes:
            self.assertIn(ligne, reel)
        # Aucune ligne du journal nominatif : elles portent une adresse.
        absentes = [l for l in nominatif if l not in reel]
        self.assertTrue(absentes)      # ancrage : le journal nominatif en porte
        self.assertEqual([l for l in lignes if l in absentes], [])

    def test_etat_trace_dans_les_deux_journaux(self):
        self.requete("GET", "/etat")
        with open(self.technique, encoding="utf-8") as f:
            self.assertIn("REPONSE methode=GET route=etat code=200", f.read())
        with open(os.path.join(self.dossier, "journal.log"), encoding="utf-8") as f:
            self.assertRegex(f.read(), r'"GET /etat HTTP/1\.1" 200')

    def test_seule_sante_sans_authentification(self):
        # Les chemins comparés à self.chemin_demande() dans do_GET et do_HEAD
        # sont dérivés de l'arbre syntaxique, jamais écrits ici : une route
        # ajoutée demain sans authentification fait rougir ce test sans qu'on
        # ait à y penser.
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
            for fonction in classe.body:
                if not (isinstance(fonction, ast.FunctionDef)
                        and fonction.name in ("do_GET", "do_HEAD")):
                    continue
                methodes_vues.add(fonction.name)
                variables = {
                    a.targets[0].id for a in ast.walk(fonction)
                    if isinstance(a, ast.Assign) and len(a.targets) == 1
                    and isinstance(a.targets[0], ast.Name)
                    and designe_le_chemin(a.value, ())}
                for comparaison in ast.walk(fonction):
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

        # Ancrages : sans eux, une dérivation qui ne trouve rien passerait
        # au vert (c'est le piège du dépôt).
        self.assertEqual(methodes_vues, {"do_GET", "do_HEAD"})
        self.assertIn("/sante", chemins)
        a_proteger = sorted(chemins - {"/sante"})
        self.assertGreaterEqual(len(a_proteger), 2)

        for chemin in a_proteger:
            for methode in ("GET", "HEAD"):
                with self.subTest(chemin=chemin, methode=methode):
                    statut, _, corps = self.requete(methode, chemin, utilisateur=None)
                    self.assertEqual(statut, 401)
                    self.assertEqual(corps, b"")


class ServeurArret(unittest.TestCase):
    """L'arrêt se vérifie sur un serveur à lui seul : le bac à sable de
    ServeurEnMarche est démonté à la fin de toute la classe
    (tearDownClass), pas d'un test à l'autre — ARRET ne peut donc pas s'y
    observer.

    SIGINT est la seule voie portable vers un KeyboardInterrupt réel dans un
    sous-processus : sous Windows, CTRL_BREAK_EVENT ne déclenche pas la même
    exception Python, et le vérifier de façon fiable dépasserait ce contrat.
    """

    @unittest.skipIf(cryptography_absente(),
                     "cryptography requis pour fabriquer les certificats")
    @unittest.skipIf(os.name == "nt",
                     "SIGINT n'équivaut pas à un KeyboardInterrupt portable "
                     "sous Windows ; voir la note de la classe")
    def test_arret_journalise(self):
        dossier, port, processus = demarrer_sandbox_court(
            attendre_demarrage_technique=True)
        self.addCleanup(shutil.rmtree, dossier, ignore_errors=True)

        # communicate() vide le tube de sortie en même temps qu'il attend :
        # un wait(timeout=…) seul, sans lecture, bloque indéfiniment si le
        # tube se remplit (stdout=PIPE non drainé) — constat d'audit, ce
        # n'est pas le verrou du journal, qui ne porte pas sur stderr.
        processus.send_signal(signal.SIGINT)
        try:
            sortie, _ = processus.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            processus.kill()
            sortie, _ = processus.communicate(timeout=10)
            self.fail(
                "le serveur n'a pas quitté dans les 10 s après SIGINT "
                "(processus encore vivant : tube de sortie plein) ; "
                "sortie du processus :\n" + sortie)

        with open(os.path.join(dossier, "technique.log"),
                  encoding="utf-8") as f:
            contenu = f.read()
        self.assertIn("ARRET motif=interruption", contenu,
                     "sortie du processus :\n" + sortie)


class InterrupteurJournalTechnique(unittest.TestCase):
    """Retour arrière niveau 1 (§11) : journal_technique à false désactive
    entièrement le second journal, sans gêner le dépôt ni journal.log."""

    @unittest.skipIf(cryptography_absente(),
                     "cryptography requis pour fabriquer les certificats")
    def test_aucun_fichier_sans_interrupteur(self):
        dossier, port, processus = demarrer_sandbox_court(
            {"journal_technique": False})
        self.addCleanup(shutil.rmtree, dossier, ignore_errors=True)

        try:
            contexte = ssl.create_default_context(
                cafile=os.path.join(dossier, "autorite.crt"))
            jeton = base64.b64encode(
                "{}:{}".format(UTILISATEUR, MOT_DE_PASSE).encode("utf-8"))
            nom = base64.b64encode("Bilan_interrupteur.pdf".encode("utf-8"))
            connexion = http.client.HTTPSConnection(
                "127.0.0.1", port, context=contexte, timeout=10)
            try:
                connexion.request("POST", "/depot", PDF, {
                    "Authorization": "Basic " + jeton.decode("ascii"),
                    "X-Fichier": nom.decode("ascii")})
                reponse = connexion.getresponse()
                statut = reponse.status
                reponse.read()
            finally:
                connexion.close()
        finally:
            # Même exposition que ServeurArret (tube de sortie non drainé) :
            # communicate() plutôt que wait() seul.
            processus.terminate()
            processus.communicate(timeout=10)

        self.assertEqual(statut, 200)
        self.assertFalse(
            os.path.exists(os.path.join(dossier, "technique.log")))
        self.assertTrue(os.path.exists(os.path.join(dossier, "journal.log")))


class InterrupteurPageEtat(unittest.TestCase):
    """Retour arrière niveau 1 (C4-T3, §11) : page_etat à false, et /etat
    répond exactement comme avant la tâche."""

    @unittest.skipIf(cryptography_absente(),
                     "cryptography requis pour fabriquer les certificats")
    def test_etat_desactivee_retrouve_l_existant(self):
        dossier, port, processus = demarrer_sandbox_court({"page_etat": False})
        self.addCleanup(shutil.rmtree, dossier, ignore_errors=True)

        statuts = {}
        try:
            contexte = ssl.create_default_context(
                cafile=os.path.join(dossier, "autorite.crt"))
            jeton = base64.b64encode(
                "{}:{}".format(UTILISATEUR, MOT_DE_PASSE).encode("utf-8"))
            # Deux requêtes au plus : le tube de sortie de ce bac à sable
            # n'est pas lu en continu (piège C7-T5, Windows).
            for nom, entetes in (("authentifie", {"Authorization": "Basic "
                                                  + jeton.decode("ascii")}),
                                 ("anonyme", {})):
                connexion = http.client.HTTPSConnection(
                    "127.0.0.1", port, context=contexte, timeout=10)
                try:
                    connexion.request("GET", "/etat", headers=entetes)
                    reponse = connexion.getresponse()
                    statuts[nom] = reponse.status
                    reponse.read()
                finally:
                    connexion.close()
        finally:
            processus.terminate()
            processus.communicate(timeout=10)

        # 403 : « Type de fichier non servi », l'existant d'avant la tâche.
        self.assertEqual(statuts, {"authentifie": 403, "anonyme": 401})


class PurgeAuDemarrage(unittest.TestCase):
    """C4-T2 : un serveur arrêté des mois ne purge rien tout seul. Le
    démarrage doit donc le faire, pour les deux journaux, avec la durée
    lue dans config.json (et non la valeur par défaut)."""

    @unittest.skipIf(cryptography_absente(),
                     "cryptography requis pour fabriquer les certificats")
    def test_archives_perimees_supprimees_au_demarrage(self):
        maintenant = datetime.datetime.now()

        def poser(dossier):
            def ecrire(nom, jours):
                date = (maintenant - datetime.timedelta(days=jours)).isoformat(
                    timespec="seconds")
                with open(os.path.join(dossier, nom), "w",
                          encoding="utf-8") as f:
                    f.write(date + " REPONSE methode=GET route=sante code=200\n")
            ecrire("journal.log.1", 40)
            ecrire("journal.log.2", 10)
            ecrire("technique.log.1", 40)
            ecrire("technique.log.2", 10)

        # Un mois : 40 jours dépassent 30 jours, 10 jours non. Avec la durée
        # par défaut (6 mois), rien ne serait supprimé : le test échoue donc
        # si le serveur ignore le paramètre de configuration.
        dossier, port, processus = demarrer_sandbox_court(
            {"conservation_journaux_mois": 1},
            attendre_demarrage_technique=True, avant_demarrage=poser)
        try:
            processus.terminate()
            processus.communicate(timeout=10)
        finally:
            presents = set(os.listdir(dossier))
            shutil.rmtree(dossier, ignore_errors=True)

        self.assertNotIn("journal.log.1", presents)
        self.assertNotIn("technique.log.1", presents)
        self.assertIn("journal.log.2", presents)
        self.assertIn("technique.log.2", presents)


class AvertissementIdentiteCabinet(unittest.TestCase):
    """Étape 4 du contrat C2-T1 : un bloc "cabinet" absent ou incomplet
    avertit sur la sortie standard, sans jamais refuser de démarrer — le
    risque réel (§12) est un cabinet mis à jour sans relancer --config."""

    @unittest.skipIf(cryptography_absente(),
                     "cryptography requis pour fabriquer les certificats")
    def test_demarrage_avertit_si_identite_absente(self):
        dossier, port, processus = demarrer_sandbox_court()
        try:
            # Le serveur tourne (serve_forever) : lire jusqu'à l'EOF
            # bloquerait indéfiniment sans l'arrêter d'abord. Même
            # exposition que ServeurArret (tube de sortie non drainé).
            processus.terminate()
            sortie, _ = processus.communicate(timeout=10)
        finally:
            shutil.rmtree(dossier, ignore_errors=True)

        self.assertIn("AVERTISSEMENT", sortie)
        self.assertIn("--config", sortie)

    @unittest.skipIf(cryptography_absente(),
                     "cryptography requis pour fabriquer les certificats")
    def test_demarrage_silencieux_si_identite_renseignee(self):
        dossier, port, processus = demarrer_sandbox_court(
            {"cabinet": {"praticien": "Dr Témoin"}})
        try:
            processus.terminate()
            sortie, _ = processus.communicate(timeout=10)
        finally:
            shutil.rmtree(dossier, ignore_errors=True)

        self.assertNotIn("AVERTISSEMENT", sortie)


class RefusDeDemarrer(unittest.TestCase):

    def test_sans_certificat_le_serveur_refuse(self):
        # Le repli silencieux en HTTP ferait circuler données de santé et mot
        # de passe en clair sur le réseau du cabinet.
        dossier = tempfile.mkdtemp(prefix="bilan-test-")
        self.addCleanup(shutil.rmtree, dossier, ignore_errors=True)
        os.mkdir(os.path.join(dossier, "serveur"))
        shutil.copy(os.path.join(PROJET, "serveur", "serveur.py"),
                    os.path.join(dossier, "serveur"))
        with open(os.path.join(dossier, "config.json"), "w") as f:
            json.dump({"port": port_libre(), "dossier_pdf": "bilans",
                       "utilisateur": "cabinet",
                       "mot_de_passe": serveur.hacher(MOT_DE_PASSE),
                       "certificat": "absent.pem",
                       "cle_privee": "absent-cle.pem"}, f)

        sortie = subprocess.run(
            [sys.executable, os.path.join("serveur", "serveur.py")],
            cwd=dossier, capture_output=True, text=True, timeout=30)
        self.assertEqual(sortie.returncode, 1)
        self.assertIn("Refus de démarrer", sortie.stdout)


if __name__ == "__main__":
    unittest.main()
