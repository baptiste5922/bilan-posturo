"""La politique du client de mise à jour (C5-T2b) : adresse, plage horaire,
fréquence, éligibilité, limitation des lignes. Sans réseau et sans `cryptography`.

Le téléchargement est remplacé par un faux qui sert les fichiers d'un trio signé
(la vraie porte de sortie, `maj._telecharger`, est éprouvée contre un faux
hébergement HTTPS par `tests/test_maj_reseau.py`). Ce qu'on éprouve ici est ce que
`verifier` DÉCIDE : se connecter ou non, appliquer ou non, écrire une ligne ou non.

    python3 -m unittest tests.test_maj_politique -v
"""

import contextlib
import datetime
import io
import json
import os
import sys
import unittest

DOSSIER_TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DOSSIER_TESTS)
sys.path.insert(0, os.path.join(DOSSIER_TESTS, "outils"))

import ed25519_essai  # noqa: E402
import maj  # noqa: E402
import paquet_essai as pe  # noqa: E402
import paquet_signe  # noqa: E402
import serveur  # noqa: E402
import test_maj  # noqa: E402

ADRESSE = "https://127.0.0.1:4443/essai/stable.zip"
ABSENTE = object()      # une clé du bloc `mise_a_jour` qui n'est pas écrite du tout
# Un identifiant dans une adresse ressemble à un courriel : la garde d'identité du
# dépôt (tests/test_identite_absente.py) refuse ce motif écrit en clair, elle ne voit
# pas celui qu'on assemble ici.
ARO = "@"
LUNDI_MIDI = datetime.datetime(2026, 11, 16, 12, 0, 0)
LUNDI_NUIT = datetime.datetime(2026, 11, 16, 23, 0, 0)


def a(heure, minute=0, jour=16):
    return datetime.datetime(2026, 11, jour, heure, minute, 0)


# ==============================================================================
# B7 — dans_la_plage, en table
# ==============================================================================

class DansLaPlage(unittest.TestCase):

    def test_la_nuit_traverse_minuit(self):
        for heure, minute, attendu in (
                (19, 59, False), (20, 0, True), (23, 59, True), (0, 0, True),
                (6, 59, True), (7, 0, False), (12, 0, False)):
            with self.subTest(heure="%02d:%02d" % (heure, minute)):
                self.assertIs(maj.dans_la_plage("20:00-07:00", a(heure, minute)), attendu)

    def test_la_journee_est_le_complementaire(self):
        for heure, minute, attendu in (
                (6, 59, False), (7, 0, True), (12, 0, True), (19, 59, True),
                (20, 0, False), (23, 59, False), (0, 0, False)):
            with self.subTest(heure="%02d:%02d" % (heure, minute)):
                self.assertIs(maj.dans_la_plage("07:00-20:00", a(heure, minute)), attendu)

    def test_les_secondes_ne_comptent_pas(self):
        # 06:59:59 est encore dans la plage, 07:00:00 n'y est plus.
        self.assertTrue(maj.dans_la_plage("20:00-07:00", datetime.datetime(2026, 11, 16, 6, 59, 59)))
        self.assertFalse(maj.dans_la_plage("20:00-07:00", datetime.datetime(2026, 11, 16, 7, 0, 0)))

    def test_un_objet_time_convient_aussi(self):
        self.assertTrue(maj.dans_la_plage("20:00-07:00", datetime.time(23, 0)))

    def test_formes_invalides(self):
        for texte in ("00:00-00:00", "24:00-07:00", "7:00-20:00", "20:00-07:60", "", "20:00",
                      "20:00-07:00 ", " 20:00-07:00", "20:00-07:00\n", "20h00-07h00",
                      "20:00–07:00", "20:00-7:00", "20:00-07:00-08:00", "12:30-12:30",
                      "١٢:٠٠-١٣:٠٠", None, 2000, ["20:00-07:00"]):
            with self.subTest(texte=texte):
                with self.assertRaises(maj.Refus) as contexte:
                    maj.dans_la_plage(texte, a(12))
                self.assertEqual(contexte.exception.code, "PLAGE_INVALIDE")


# ==============================================================================
# B12 — la configuration, forme par forme
# ==============================================================================

class LirePolitique(unittest.TestCase):

    def test_sans_adresse_le_client_est_desactive(self):
        for bloc in (None, {}, [], "x", 5, {"client": "cabinet-01"}, {"adresse": ""},
                     {"adresse": "", "plage": "n'importe quoi", "proxy": 3}):
            with self.subTest(bloc=bloc):
                self.assertEqual(maj.lire_politique(bloc).adresse, "")

    def test_les_defauts(self):
        politique = maj.lire_politique({"adresse": ADRESSE})
        self.assertEqual(politique, maj.Politique(ADRESSE, "", "20:00-07:00", 30, True))

    def test_une_configuration_complete(self):
        politique = maj.lire_politique({
            "adresse": ADRESSE, "proxy": "http://proxy.local:3128", "plage": "22:30-05:15",
            "calme_minutes": 240, "au_demarrage": False})
        self.assertEqual(politique, maj.Politique(
            ADRESSE, "http://proxy.local:3128", "22:30-05:15", 240, False))
        for proxy in ("http://proxy.local:3128/", "http://10.0.0.2:8080"):
            self.assertEqual(
                maj.lire_politique({"adresse": ADRESSE, "proxy": proxy}).proxy, proxy)

    def test_chaque_forme_refusee_rend_son_code(self):
        base = {"adresse": ADRESSE}
        table = (
            # adresse
            ("ADRESSE_INVALIDE", {"adresse": "http://127.0.0.1/essai/stable.zip"}),
            ("ADRESSE_INVALIDE", {"adresse": "127.0.0.1/essai/stable.zip"}),
            ("ADRESSE_INVALIDE", {"adresse": "ftp://127.0.0.1/essai/stable.zip"}),
            ("ADRESSE_INVALIDE", {"adresse": "file:///essai/stable.zip"}),
            ("ADRESSE_INVALIDE", {"adresse": "https:///essai/stable.zip"}),
            ("ADRESSE_INVALIDE", {"adresse": "https://u:p@127.0.0.1/essai/stable.zip"}),
            ("ADRESSE_INVALIDE", {"adresse": "https://u@127.0.0.1/essai/stable.zip"}),
            ("ADRESSE_INVALIDE", {"adresse": ADRESSE + "?a=1"}),
            ("ADRESSE_INVALIDE", {"adresse": ADRESSE + "#x"}),
            ("ADRESSE_INVALIDE", {"adresse": ADRESSE + "?"}),
            ("ADRESSE_INVALIDE", {"adresse": "https://127.0.0.1/essai/stable"}),
            ("ADRESSE_INVALIDE", {"adresse": "https://127.0.0.1/essai/stable.zip/"}),
            ("ADRESSE_INVALIDE", {"adresse": "https://127.0.0.1:99999/stable.zip"}),
            ("ADRESSE_INVALIDE", {"adresse": "https://127.0.0.1:abc/stable.zip"}),
            ("ADRESSE_INVALIDE", {"adresse": "https://exemple .fr/stable.zip"}),
            ("ADRESSE_INVALIDE", {"adresse": "https://exemple.fr/a b/stable.zip"}),
            ("ADRESSE_INVALIDE", {"adresse": "https://exemple.fr/stable.zip\n"}),
            ("ADRESSE_INVALIDE", {"adresse": "https://exemple.fr/é/stable.zip"}),
            ("ADRESSE_INVALIDE", {"adresse": "https://exemple.fr\\stable.zip"}),
            ("ADRESSE_INVALIDE", {"adresse": "https://exemple.fr/" + "a" * 1100 + ".zip"}),
            ("ADRESSE_INVALIDE", {"adresse": None}),
            ("ADRESSE_INVALIDE", {"adresse": 5}),
            ("ADRESSE_INVALIDE", {"adresse": ["https://exemple.fr/stable.zip"]}),
            ("ADRESSE_INVALIDE", {"adresse": True}),
            # proxy
            ("ADRESSE_INVALIDE", {"proxy": "https://proxy.local:3128"}),
            ("ADRESSE_INVALIDE", {"proxy": "proxy.local:3128"}),
            ("ADRESSE_INVALIDE", {"proxy": "http://proxy.local"}),
            ("ADRESSE_INVALIDE", {"proxy": "http://u:p" + ARO + "proxy.local:3128"}),
            ("ADRESSE_INVALIDE", {"proxy": "http://proxy.local:3128/x"}),
            ("ADRESSE_INVALIDE", {"proxy": "http://proxy.local:3128?a=1"}),
            ("ADRESSE_INVALIDE", {"proxy": None}),
            ("ADRESSE_INVALIDE", {"proxy": 3128}),
            # plage et le reste
            ("PLAGE_INVALIDE", {"plage": "20:00-20:00"}),
            ("PLAGE_INVALIDE", {"plage": "24:00-07:00"}),
            ("PLAGE_INVALIDE", {"plage": ""}),
            ("PLAGE_INVALIDE", {"plage": None}),
            ("PLAGE_INVALIDE", {"plage": 2000}),
            ("PLAGE_INVALIDE", {"calme_minutes": 0}),
            ("PLAGE_INVALIDE", {"calme_minutes": 241}),
            ("PLAGE_INVALIDE", {"calme_minutes": -5}),
            ("PLAGE_INVALIDE", {"calme_minutes": True}),
            ("PLAGE_INVALIDE", {"calme_minutes": False}),
            ("PLAGE_INVALIDE", {"calme_minutes": "30"}),
            ("PLAGE_INVALIDE", {"calme_minutes": 30.0}),
            ("PLAGE_INVALIDE", {"calme_minutes": None}),
            ("PLAGE_INVALIDE", {"au_demarrage": "true"}),
            ("PLAGE_INVALIDE", {"au_demarrage": 1}),
            ("PLAGE_INVALIDE", {"au_demarrage": 0}),
            ("PLAGE_INVALIDE", {"au_demarrage": None}),
        )
        for code, changement in table:
            with self.subTest(code=code, changement=repr(changement)[:80]):
                bloc = dict(base, **changement)
                with self.assertRaises(maj.Refus) as contexte:
                    maj.lire_politique(bloc)
                self.assertEqual(contexte.exception.code, code)

    def test_un_message_de_refus_ne_reprend_jamais_l_adresse(self):
        for adresse in ("https://sentinelle" + ARO + "hote-secret.invalid/0123/stable.zip",
                        "http://hote-secret.invalid/0123/stable.zip",
                        "https://hote-secret.invalid/0123/stable.zip?jeton=sentinelle"):
            with self.subTest():
                with self.assertRaises(maj.Refus) as contexte:
                    maj.lire_politique({"adresse": adresse})
                for texte in (contexte.exception.detail, str(contexte.exception)):
                    self.assertNotIn("sentinelle", texte)
                    self.assertNotIn("hote-secret", texte)
                    self.assertNotIn("0123", texte)

    def test_une_valeur_ecrite_n_est_jamais_remplacee_par_son_defaut(self):
        # Une plage fausse ne devient pas 20:00-07:00 : elle refuse.
        with self.assertRaises(maj.Refus):
            maj.lire_politique({"adresse": ADRESSE, "plage": "demain"})

    def test_analyse_des_adresses_et_des_redirections(self):
        self.assertEqual(maj.analyser_adresse(ADRESSE), ("127.0.0.1", 4443, "/essai/stable.zip"))
        self.assertEqual(maj.analyser_adresse("https://Exemple.FR/a/b.zip"),
                         ("exemple.fr", 443, "/a/b.zip"))
        # Une cible de redirection suit les mêmes règles hors le suffixe .zip.
        self.assertEqual(maj.analyser_adresse("https://exemple.fr/x", exiger_zip=False),
                         ("exemple.fr", 443, "/x"))
        for cible in ("http://exemple.fr/x", "file:///x", "https://u" + ARO + "exemple.fr/x",
                      "https://exemple.fr/x?a=1", "//exemple.fr/x", "/x"):
            with self.subTest(cible=cible):
                with self.assertRaises(ValueError):
                    maj.analyser_adresse(cible, exiger_zip=False)


# ==============================================================================
# Les passages de `verifier`
# ==============================================================================

class Passage(test_maj.Installation):
    """Une installation d'essai, un faux hébergement et des passages de `verifier`
    à des heures choisies."""

    def setUp(self):
        test_maj.Installation.setUp(self)
        self.requetes = []
        self.panne = None
        self.panne_archive = None       # seule l'archive échoue (manifeste et signature passent)
        self.fichiers = {}
        self.patch(maj, "_telecharger", self.telecharger)
        self.patch(maj, "attendre_sante", lambda *a, **k: True)
        self.configurer()
        # B21 : quoi qu'un test ait provoqué, le chemin de l'adresse n'est dans aucun
        # des deux journaux. Enregistré après l'effacement du dossier : joué avant.
        self.addCleanup(self.aucune_adresse_dans_les_journaux, self.racine)

    @staticmethod
    def aucune_adresse_dans_les_journaux(racine):
        # La racine est celle de CE setUp : un test qui rejoue setUp (une installation
        # par cas d'une table) a plusieurs racines, effacées dans l'ordre inverse.
        for nom in ("technique.log", "journal.log"):
            chemin = os.path.join(racine, nom)
            if not os.path.exists(chemin):
                continue
            with open(chemin, encoding="utf-8") as f:
                texte = f.read()
            for interdit in ("/essai/", "stable.zip"):
                if interdit in texte:
                    raise AssertionError("%s porte une partie de l'adresse de publication" % nom)

    # --- faux hébergement ---------------------------------------------------

    def telecharger(self, url, destination, limite, delai_total, contexte=None, proxy="",
                    delai_operation=30):
        self.requetes.append(url)
        if self.panne is not None:
            raise maj.Refus(self.panne, "panne d'essai")
        if url.endswith(paquet_signe.SUFFIXE_MANIFESTE):
            nature = "manifeste"
        elif url.endswith(paquet_signe.SUFFIXE_SIGNATURE):
            nature = "signature"
        else:
            nature = "archive"
        if nature == "archive" and self.panne_archive is not None:
            raise maj.Refus(self.panne_archive, "panne d'essai sur l'archive")
        with open(self.fichiers[nature], "rb") as f:
            octets = f.read()
        if len(octets) > limite:
            raise maj.Refus("REPONSE_TROP_GRANDE", "trop grand")
        with open(destination, "xb") as f:
            f.write(octets)
        return len(octets)

    def publier(self, archive):
        self.fichiers = {"archive": archive,
                         "manifeste": archive + paquet_signe.SUFFIXE_MANIFESTE,
                         "signature": archive + paquet_signe.SUFFIXE_SIGNATURE}

    def configurer(self, **bloc):
        reglage = {"client": "cabinet-01", "adresse": ADRESSE}
        reglage.update(bloc)
        self.ecrire_config(mise_a_jour=dict(
            (k, v) for k, v in reglage.items() if v is not ABSENTE))

    def passer(self, maintenant=LUNDI_MIDI, depuis_demarrage=100000, **delais):
        sortie = io.StringIO()
        options = {"sante": 1, "auto_controle": 5, "reponse": 1, "arret": 1, "operation": 1}
        options.update(delais)
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(io.StringIO()):
            return maj.verifier(self.racine, self.pilote, maintenant=maintenant,
                                depuis_demarrage=lambda: depuis_demarrage, delais=options)

    def journal(self):
        with open(os.path.join(self.racine, "journal.log"), encoding="utf-8") as f:
            return f.read()

    def lignes(self, jeton, texte=None):
        return [l for l in (self.technique() if texte is None else texte).splitlines()
                if " %s" % jeton in l]

    def dossier_maj(self, *noms):
        return os.path.join(self.racine, "mise-a-jour", *noms)

    # --- modifier un trio déjà signé ----------------------------------------

    def retoucher_le_manifeste(self, archive, **archive_champs):
        chemin = archive + paquet_signe.SUFFIXE_MANIFESTE
        with open(chemin, "rb") as f:
            manifeste = json.load(f)
        manifeste["archive"].update(archive_champs)
        octets = pe.serialiser(manifeste)
        with open(chemin, "wb") as f:
            f.write(octets)
        with open(archive + paquet_signe.SUFFIXE_SIGNATURE, "wb") as f:
            f.write(ed25519_essai.signer(pe.GRAINE_A, octets))


class Desactive(Passage):
    """B11 : sans adresse, aucune connexion, une ligne par jour."""

    def desactiver(self, forme):
        if forme == "pas de bloc":
            with open(os.path.join(self.racine, "config.json")) as f:
                config = json.load(f)
            del config["mise_a_jour"]
            with open(os.path.join(self.racine, "config.json"), "w") as f:
                json.dump(config, f)
        elif forme == "bloc qui n'est pas un objet":
            self.ecrire_config(mise_a_jour="oui")
        elif forme == "adresse absente":
            self.configurer(adresse=ABSENTE)
        else:
            self.configurer(adresse="")

    FORMES = ("pas de bloc", "bloc qui n'est pas un objet", "adresse absente", "adresse vide")

    def test_aucune_connexion_et_une_ligne_par_jour(self):
        for forme in self.FORMES:
            with self.subTest(forme=forme):
                self.setUp()
                self.desactiver(forme)
                self.assertEqual(self.passer(a(9)), 3)
                self.assertEqual(self.passer(a(10)), 3)
                self.assertEqual(self.requetes, [])
                self.assertEqual(len(self.lignes("MAJ_REPORTEE code=DESACTIVEE")), 1)
                self.assertEqual(self.passer(a(9, jour=17)), 3)
                self.assertEqual(len(self.lignes("MAJ_REPORTEE code=DESACTIVEE")), 2)
                # Dans le journal nominatif aussi, et avec la même limite.
                self.assertEqual(len(self.lignes("MAJ_REPORTEE", self.journal())), 2)
                etat = self.etat()
                self.assertEqual((etat["resultat"], etat["code"]), ("reportee", "DESACTIVEE"))
                self.assertIsNone(etat["controle_le"])

    def test_un_etat_a_la_bascule_est_defait_meme_desactive(self):
        with maj.contexte_serveur(self.racine):
            maj.preparer_dossier_prive(self.racine)
            archive = self.trio("1.2.0", {"docs/nouveau.md": b"neuf"})
            paquet = maj.controler(self.racine, archive)
            maj.extraire(paquet)
            maj.sauvegarder(paquet)
            prepare = self.dossier_maj("prepare")
            attendus = dict((r, v[1]) for r, v in paquet.fichiers.items())
            maj.ecrire_etat(self.racine, etape="bascule", de=paquet.installee,
                            vers=paquet.version)
            maj.poser_fichiers(self.racine, prepare,
                               dict((r, attendus[r]) for r in sorted(attendus)[:4]),
                               "EXTRACTION_ALTEREE")
        self.configurer(adresse="")
        self.assertEqual(self.passer(), 3)
        self.assertIn("MAJ_RETOUR cause=INTERROMPUE resultat=ok de=1.1.0 vers=1.2.0",
                      self.technique())
        self.assertEqual(self.etat()["etape"], "repos")
        self.assertEqual(self.requetes, [])
        self.assertEqual(self.etat()["ecartees"], [])


class ConfigurationFausse(Passage):
    """B12 : une forme refusée rend son code, sans connexion ni valeur par défaut."""

    def test_chaque_forme_refusee_arrete_tout_avant_la_connexion(self):
        for code, changement in (
                ("ADRESSE_INVALIDE", {"adresse": "http://127.0.0.1:4443/essai/stable.zip"}),
                ("ADRESSE_INVALIDE", {"proxy": "proxy.local"}),
                ("PLAGE_INVALIDE", {"plage": "demain"}),
                ("PLAGE_INVALIDE", {"calme_minutes": 0}),
                ("PLAGE_INVALIDE", {"au_demarrage": "oui"})):
            with self.subTest(code=code, changement=changement):
                self.setUp()
                self.configurer(**changement)
                self.assertEqual(self.passer(), 1)
                self.assertEqual(self.requetes, [])
                self.assertIn("MAJ_REFUSEE code=%s" % code, self.technique())
                self.assertFalse(os.path.lexists(self.dossier_maj("reception")))
                self.assertEqual(self.demandes, [])

    def test_une_ligne_par_jour_pour_une_configuration_fausse(self):
        self.configurer(plage="demain")
        for heure in (9, 10, 11):
            self.assertEqual(self.passer(a(heure)), 1)
        self.assertEqual(len(self.lignes("MAJ_REFUSEE code=PLAGE_INVALIDE")), 1)
        self.assertEqual(self.passer(a(9, jour=17)), 1)
        self.assertEqual(len(self.lignes("MAJ_REFUSEE code=PLAGE_INVALIDE")), 2)

    def test_une_plage_fausse_n_applique_pas_la_plage_par_defaut(self):
        # 23:00 est dans 20:00-07:00 : si la valeur écrite était remplacée par le
        # défaut, ce passage irait jusqu'au téléchargement.
        self.configurer(plage="25:00-07:00")
        self.publier(self.trio("1.2.0"))
        self.assertEqual(self.passer(LUNDI_NUIT), 1)
        self.assertEqual(self.requetes, [])

    def test_le_client_reste_obligatoire(self):
        self.ecrire_config(mise_a_jour={"adresse": ADRESSE})
        self.assertEqual(self.passer(), 1)
        self.assertIn("MAJ_REFUSEE code=CLIENT_NON_CONFIGURE", self.technique())
        self.assertEqual(self.requetes, [])

    def test_sans_cles_installees_rien_ne_sort(self):
        os.remove(os.path.join(self.racine, "serveur", "cles_publication.json"))
        self.assertEqual(self.passer(), 1)
        self.assertIn("MAJ_REFUSEE code=CLES_ABSENTES", self.technique())
        self.assertEqual(self.requetes, [])


class Frequence(Passage):
    """B10 : un contrôle réseau toutes les six heures au plus, sauf horloge reculée."""

    def setUp(self):
        Passage.setUp(self)
        # La même version que l'installée : « à jour ».
        self.publier(self.trio("1.1.0"))

    def test_une_minute_plus_tard_aucune_requete_six_heures_plus_tard_deux(self):
        self.assertEqual(self.passer(a(9, 0)), 0)
        self.assertEqual(len(self.requetes), 2)
        self.requetes.clear()
        self.assertEqual(self.passer(a(9, 1)), 0)
        self.assertEqual(self.requetes, [])
        self.assertEqual(self.passer(a(14, 59)), 0)
        self.assertEqual(self.requetes, [], "5 h 59 : pas encore dû")
        self.assertEqual(self.passer(a(15, 0)), 0)
        self.assertEqual(len(self.requetes), 2, "6 h pile : dû")

    def test_une_horloge_reculee_ne_gele_pas_les_controles(self):
        self.assertEqual(self.passer(a(10, 0)), 0)
        self.requetes.clear()
        self.assertEqual(self.passer(a(9, 0)), 0)
        self.assertEqual(len(self.requetes), 2)

    def test_un_controle_d_une_forme_illisible_est_du(self):
        self.assertEqual(self.passer(a(9, 0)), 0)
        etat_chemin = self.dossier_maj("etat.json")
        with open(etat_chemin) as f:
            contenu = json.load(f)
        self.assertEqual(contenu["controle_le"], "2026-11-16T09:00:00")
        # Une date impossible (31 novembre) passe la forme du serveur mais pas strptime.
        contenu["controle_le"] = "2026-11-31T09:00:00"
        with open(etat_chemin, "w") as f:
            json.dump(contenu, f)
        self.requetes.clear()
        self.assertEqual(self.passer(a(9, 5)), 0)
        self.assertEqual(len(self.requetes), 2)

    def test_apres_un_echec_reseau_le_controle_reste_du(self):
        self.panne = "RESEAU_INJOIGNABLE"
        self.assertEqual(self.passer(a(9, 0)), 3)
        self.assertIsNone(self.etat()["controle_le"])
        self.assertIn("MAJ_REPORTEE code=RESEAU_INJOIGNABLE", self.technique())
        self.panne = None
        self.requetes.clear()
        self.assertEqual(self.passer(a(9, 1)), 0)
        self.assertEqual(len(self.requetes), 2, "le passage suivant réessaie")
        self.assertEqual(self.etat()["controle_le"], "2026-11-16T09:01:00")

    def test_un_echec_de_l_archive_laisse_le_controle_du(self):
        # Le manifeste est jugé et bon, mais l'archive n'arrive pas (Wi-Fi tombé, ou
        # hébergeur qui a publié le manifeste avant elle) : le même échec réseau que
        # sur le manifeste, la même parade, une heure et non six (erratum 24).
        self.publier(self.trio("1.2.0"))
        self.panne_archive = "HTTP_STATUT"
        self.assertEqual(self.passer(a(9, 0)), 3)
        self.assertIn("MAJ_REPORTEE code=HTTP_STATUT", self.technique())
        etat = self.etat()
        self.assertIsNone(etat["controle_le"])
        self.assertIsNone(etat["attente"])
        self.panne_archive = None
        self.requetes.clear()
        self.assertEqual(self.passer(a(10, 0)), 3)          # hors plage : reçue, elle attend
        self.assertEqual(len(self.requetes), 3, "le contrôle suivant est du, une heure plus tard")
        self.assertEqual(self.etat()["attente"], "1.2.0")
        self.assertEqual(self.etat()["controle_le"], "2026-11-16T10:00:00")

    def test_un_echec_reseau_ne_change_pas_un_controle_deja_fait(self):
        self.assertEqual(self.passer(a(9, 0)), 0)
        avant = self.etat()["controle_le"]
        self.panne = "TLS_INVALIDE"
        self.assertEqual(self.passer(a(16, 0)), 3)
        self.assertEqual(self.etat()["controle_le"], avant)

    def test_le_resultat_a_jour_est_ecrit_une_fois_par_jour(self):
        self.assertEqual(self.passer(a(9, 0)), 0)
        self.assertEqual(self.passer(a(15, 0)), 0)
        self.assertEqual(self.passer(a(21, 0)), 0)
        self.assertEqual(len(self.lignes("MAJ_CONTROLE resultat=a-jour de=1.1.0")), 1)
        self.assertEqual(self.passer(a(9, 0, jour=17)), 0)
        self.assertEqual(len(self.lignes("MAJ_CONTROLE resultat=a-jour de=1.1.0")), 2)
        self.assertEqual(len(self.lignes("MAJ_CONTROLE", self.journal())), 2)

    def test_un_controle_n_est_pas_un_resultat(self):
        self.assertEqual(self.passer(a(9, 0)), 0)
        etat = self.etat()
        self.assertEqual(etat["controle_le"], "2026-11-16T09:00:00")
        self.assertIsNone(etat["le"], "`le` est la date du dernier résultat")
        self.assertIsNone(etat["attente"])

    def test_deux_requetes_seulement_manifeste_puis_signature(self):
        self.assertEqual(self.passer(a(9, 0)), 0)
        self.assertEqual(self.requetes, [
            ADRESSE + paquet_signe.SUFFIXE_MANIFESTE, ADRESSE + paquet_signe.SUFFIXE_SIGNATURE])


class ArchiveJamaisDemandeeAvantLEntete(Passage):
    """B2, côté décision : le manifeste est jugé AVANT que l'archive soit demandée."""

    def verifier_sans_archive(self, archive, version_ecartee=None):
        self.publier(archive)
        if version_ecartee is not None:
            with maj.contexte_serveur(self.racine):
                maj.preparer_dossier_prive(self.racine)
                maj.ecrire_etat(self.racine, ecartees=[version_ecartee])
        retour = self.passer()
        self.assertEqual(self.requetes, [
            ADRESSE + paquet_signe.SUFFIXE_MANIFESTE, ADRESSE + paquet_signe.SUFFIXE_SIGNATURE])
        self.assertFalse(os.path.lexists(self.dossier_maj("reception", "archive.zip")))
        self.assertEqual(os.listdir(self.dossier_maj("reception")), [])
        etat = self.etat()
        self.assertIsNone(etat["attente"])
        self.assertIsNotNone(etat["controle_le"], "un refus d'en-tête est un verdict : contrôle fait")
        return retour

    def test_signature_invalide(self):
        retour = self.verifier_sans_archive(self.trio("1.2.0", graine=pe.GRAINE_B))
        self.assertEqual(retour, 1)
        self.assertIn("MAJ_REFUSEE code=SIGNATURE_INVALIDE", self.technique())

    def test_version_non_superieure(self):
        self.assertEqual(self.verifier_sans_archive(self.trio("1.1.0")), 0)
        self.assertIn("MAJ_CONTROLE resultat=a-jour de=1.1.0", self.technique())

    def test_version_minimale_non_atteinte(self):
        retour = self.verifier_sans_archive(self.trio("1.3.0", version_minimale="1.2.0"))
        self.assertEqual(retour, 1)
        self.assertIn("MAJ_REFUSEE code=VERSION_MINIMALE_NON_ATTEINTE", self.technique())

    def test_client_different(self):
        retour = self.verifier_sans_archive(self.trio("1.2.0", client="cabinet-02"))
        self.assertEqual(retour, 1)
        self.assertIn("MAJ_REFUSEE code=CLIENT_DIFFERENT", self.technique())

    def test_version_ecartee(self):
        retour = self.verifier_sans_archive(self.trio("1.2.0"), version_ecartee="1.2.0")
        self.assertEqual(retour, 0)
        self.assertIn("MAJ_CONTROLE resultat=a-jour de=1.1.0", self.technique())
        self.assertNotIn("disponible", self.technique())

    def test_archive_annoncee_trop_grande_n_est_jamais_demandee(self):
        archive = self.trio("1.2.0")
        self.retoucher_le_manifeste(archive, taille=maj.TAILLE_MAX_ARCHIVE + 1)
        self.publier(archive)
        self.assertEqual(self.passer(), 3)
        self.assertEqual(len(self.requetes), 2)
        self.assertIn("MAJ_REPORTEE code=REPONSE_TROP_GRANDE", self.technique())
        self.assertIsNone(self.etat()["attente"])
        self.assertIsNotNone(self.etat()["controle_le"])


class Eligibilite(Passage):
    """B8, B9 : dans la plage, hors plage, juste après le démarrage. Le serveur reste
    juge (ici, un faux refuse toujours) : on regarde ce que le client lui demande."""

    def setUp(self):
        Passage.setUp(self)
        self.publier(self.trio("1.2.0"))

    def demande_ecrite(self):
        self.assertEqual(len(self.demandes), 1)
        racine, port, calme, demarrage = self.demandes[0][:4]
        return calme, demarrage

    def test_dans_la_plage_le_calme_configure(self):
        self.configurer(calme_minutes=45)
        self.assertEqual(self.passer(LUNDI_NUIT), 3)
        self.assertEqual(self.demande_ecrite(), (45 * 60, False))
        self.assertIn("MAJ_CONTROLE resultat=disponible de=1.1.0 vers=1.2.0", self.technique())
        self.assertIn("MAJ_REPORTEE code=ARRET_REFUSE", self.technique())

    def test_le_calme_par_defaut_est_une_demi_heure(self):
        self.assertEqual(self.passer(LUNDI_NUIT), 3)
        self.assertEqual(self.demande_ecrite(), (1800, False))

    def test_hors_plage_sans_demarrage_rien_n_est_extrait_ni_demande(self):
        self.configurer(au_demarrage=False)
        avant = self.arbre()
        self.assertEqual(self.passer(LUNDI_MIDI, depuis_demarrage=60), 3)
        self.assertEqual(self.demandes, [])
        self.assertFalse(os.path.lexists(self.dossier_maj("prepare")))
        self.assertFalse(os.path.lexists(self.dossier_maj(serveur.DEMANDE_ARRET)))
        self.assertIn("MAJ_REPORTEE code=HORS_PLAGE", self.technique())
        etat = self.etat()
        self.assertEqual((etat["etape"], etat["resultat"], etat["code"], etat["attente"]),
                         ("repos", "reportee", "HORS_PLAGE", "1.2.0"))
        self.assertTrue(os.path.isfile(self.dossier_maj("reception", "archive.zip")),
                        "la version reçue attend son heure")
        self.assertEqual(self.arbre(), avant)

    def test_hors_plage_et_demarrage_depasse_c_est_le_meme_resultat(self):
        self.assertEqual(self.passer(LUNDI_MIDI, depuis_demarrage=901), 3)
        self.assertEqual(self.demandes, [])
        self.assertFalse(os.path.lexists(self.dossier_maj("prepare")))
        self.assertIn("MAJ_REPORTEE code=HORS_PLAGE", self.technique())

    def test_la_frontiere_des_quinze_minutes(self):
        self.assertEqual(self.passer(LUNDI_MIDI, depuis_demarrage=900), 3)
        self.assertEqual(self.demande_ecrite(), (0, True))

    def test_hors_plage_apres_le_demarrage_calme_zero_et_demarrage_vrai(self):
        self.assertEqual(self.passer(LUNDI_MIDI, depuis_demarrage=120), 3)
        self.assertEqual(self.demande_ecrite(), (0, True))

    def test_la_version_en_attente_est_appliquee_au_passage_de_la_nuit(self):
        self.configurer(au_demarrage=False)
        self.assertEqual(self.passer(a(19, 0)), 3)
        self.assertEqual(self.demandes, [])
        requetes = len(self.requetes)
        self.assertEqual(self.passer(a(20, 0)), 3)
        self.assertEqual(len(self.requetes), requetes, "pas de nouveau contrôle : attente")
        self.assertEqual(self.demande_ecrite(), (1800, False))

    def test_une_ligne_hors_plage_par_jour(self):
        self.configurer(au_demarrage=False)
        for heure in (9, 10, 11, 12):
            self.assertEqual(self.passer(a(heure)), 3)
        self.assertEqual(len(self.lignes("MAJ_REPORTEE code=HORS_PLAGE")), 1)
        self.assertEqual(self.passer(a(9, jour=17)), 3)
        self.assertEqual(len(self.lignes("MAJ_REPORTEE code=HORS_PLAGE")), 2)

    def test_une_ligne_disponible_par_version_vue(self):
        self.configurer(au_demarrage=False)
        self.assertEqual(self.passer(a(9, 0)), 3)
        self.assertEqual(self.passer(a(15, 0)), 3)      # nouveau contrôle, même version
        self.assertEqual(len(self.lignes("MAJ_CONTROLE resultat=disponible")), 1)

    def test_un_refus_d_arret_garde_la_version_en_attente(self):
        # ARRET_REFUSE est un report : la version reçue reste, le prochain passage
        # (une heure plus tard, sans nouveau téléchargement) retentera.
        self.assertEqual(self.passer(LUNDI_NUIT), 3)
        self.assertEqual(self.etat()["attente"], "1.2.0")
        self.assertTrue(os.path.isfile(self.dossier_maj("reception", "archive.zip")))
        requetes = len(self.requetes)
        self.assertEqual(self.passer(a(0, 0, jour=17)), 3)
        self.assertEqual(len(self.requetes), requetes)
        self.assertEqual(len(self.demandes), 2)

    def test_un_autre_refus_consomme_la_version(self):
        # SCHEMA_MODIFIE_LOCALEMENT, ESPACE_INSUFFISANT… : une cause locale, qui se
        # répare. Rien ne reste en attente, la version sera retéléchargée au
        # contrôle suivant, jamais écartée.
        self.patch(maj, "espace_libre", lambda racine: 0)
        self.assertEqual(self.passer(LUNDI_NUIT), 1)
        self.assertIn("MAJ_REFUSEE code=ESPACE_INSUFFISANT", self.technique())
        self.assertIsNone(self.etat()["attente"])
        self.assertEqual(os.listdir(self.dossier_maj("reception")), [])
        self.assertEqual(self.etat()["ecartees"], [])
        self.assertEqual(self.demandes, [])


class SansConsole(Passage):
    """B22 : sous pythonw.exe, `sys.stdout` et `sys.stderr` valent None."""

    def sans_console(self, travail):
        sortie, erreur = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = None
        try:
            return travail()
        finally:
            sys.stdout, sys.stderr = sortie, erreur

    def passer_sans_console(self, maintenant=LUNDI_MIDI):
        return self.sans_console(lambda: maj.verifier(
            self.racine, self.pilote, maintenant=maintenant,
            depuis_demarrage=lambda: 100000,
            delais={"sante": 1, "auto_controle": 5, "reponse": 1, "arret": 1,
                    "operation": 1}))

    def test_desactive(self):
        self.configurer(adresse="")
        self.assertEqual(self.passer_sans_console(), 3)

    def test_a_jour(self):
        self.publier(self.trio("1.1.0"))
        self.assertEqual(self.passer_sans_console(), 0)

    def test_refus(self):
        self.publier(self.trio("1.2.0", graine=pe.GRAINE_B))
        self.assertEqual(self.passer_sans_console(), 1)

    def test_configuration_fausse(self):
        self.configurer(plage="demain")
        self.assertEqual(self.passer_sans_console(), 1)

    def test_report_reseau(self):
        self.panne = "RESEAU_INJOIGNABLE"
        self.assertEqual(self.passer_sans_console(), 3)

    def test_etat_aide_et_proteger_ne_levent_pas_non_plus(self):
        self.assertEqual(self.sans_console(lambda: maj.proteger(self.racine)), 0)
        self.assertEqual(self.sans_console(lambda: maj.etat_commande(self.racine)), 0)


class Verrou(Passage):

    def test_un_verrou_pris_est_un_report_silencieux_pour_l_etat(self):
        with maj.contexte_serveur(self.racine):
            maj.preparer_dossier_prive(self.racine)
            with maj.verrou(self.racine):
                # Même processus : le verrou n'est pas réentrant, comme pour un
                # second passage de la tâche qui chevaucherait le premier.
                code = self.passer()
        self.assertEqual(code, 3)
        self.assertEqual(self.requetes, [])
        self.assertIn("MAJ_REPORTEE code=DEJA_EN_COURS", self.technique())


class PointDEntree(Passage):
    """`main` aiguille `verifier` et applique la garde du dépôt de développement."""

    def test_main_aiguille_verifier(self):
        self.configurer(adresse="")
        with contextlib.redirect_stdout(io.StringIO()):
            code = maj.main(["verifier"], racine=self.racine, pilote=self.pilote)
        self.assertEqual(code, 3)
        self.assertIn("MAJ_REPORTEE code=DESACTIVEE", self.technique())
        self.assertEqual(self.requetes, [])

    def test_verifier_refuse_de_s_executer_dans_un_depot(self):
        os.mkdir(os.path.join(self.racine, ".git"))
        with contextlib.redirect_stdout(io.StringIO()):
            code = maj.main(["verifier"], racine=self.racine, pilote=self.pilote)
        self.assertEqual(code, 2)
        self.assertFalse(os.path.lexists(self.dossier_maj()))
        self.assertEqual(self.requetes, [])

    def test_une_commande_inconnue_est_refusee_par_l_usage(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as contexte:
                maj.main(["telecharger"], racine=self.racine)
        self.assertEqual(contexte.exception.code, 2)


class Proteger(Passage):

    def test_proteger_cree_le_dossier_et_ne_fait_que_cela(self):
        avant = self.arbre()
        self.assertFalse(os.path.lexists(self.dossier_maj()))
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            self.assertEqual(maj.proteger(self.racine), 0)
        self.assertTrue(os.path.isdir(self.dossier_maj()))
        self.assertEqual(os.listdir(self.dossier_maj()), [])
        self.assertEqual(self.arbre(), avant)
        self.assertEqual(self.pilote.appels, [])
        self.assertEqual(self.requetes, [])

    def test_proteger_refuse_un_lien(self):
        cible = os.path.join(self.paquets, "ailleurs")
        os.mkdir(cible)
        try:
            os.symlink(cible, self.dossier_maj(), target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("lien symbolique impossible sur ce poste")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(maj.proteger(self.racine), 1)
        self.assertEqual(os.listdir(cible), [])

    def test_la_sous_commande_est_dans_l_aide_et_dans_main(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(maj.main(["proteger"], racine=self.racine), 0)
        aide = maj.construire_analyseur().format_help()
        for commande in ("verifier", "proteger"):
            self.assertIn(commande, aide)


if __name__ == "__main__":
    unittest.main()
