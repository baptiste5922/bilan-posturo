"""Client de mise à jour (C5-T2a) : `serveur/maj.py`, sans serveur en marche.

Chaque refus de l'étape 6 du contrat est éprouvé DERRIÈRE une signature valide
(décision D8 de C5-T1) : un paquet dont un seul point est faux, signé par une clé
jetable, pour que le refus ne puisse venir que de la garde visée. Après chaque
refus, l'arbre d'installation hors de `mise-a-jour/` est identique, fichier par
fichier, et le serveur n'a reçu aucune demande d'arrêt.

Rien ici n'exige `cryptography` : le signataire est en Python pur
(tests/outils/ed25519_essai.py), et le serveur n'est jamais lancé (le bout en bout
est dans tests/test_maj_bout_en_bout.py).

    python3 -m unittest tests.test_maj -v
"""

import ast
import contextlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
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
import serveur  # noqa: E402

SOURCE_MAJ = os.path.join(PROJET, "serveur", "maj.py")
# Les tests d'Installation remplacent maj.demander_arret par un espion ; ceux de
# l'arrêt concerté côté client veulent la vraie.
DEMANDER_ARRET_REEL = maj.demander_arret


class PiloteFactice(object):
    """Un pilote qui note ce qu'on lui demande et ne lance rien."""

    def __init__(self, tache_existe=True):
        self.tache_existe = tache_existe
        self.appels = []

    def existe(self):
        self.appels.append("existe")
        return self.tache_existe

    def demarrer(self):
        self.appels.append("demarrer")

    def arreter_de_force(self):
        self.appels.append("arreter_de_force")
        return True


class Installation(unittest.TestCase):
    """Une installation d'essai (sans certificats ni serveur) et de quoi y poser
    des paquets signés."""

    def setUp(self):
        self.base = pe.fichiers_de_base("1.1.0")
        self.racine = pe.fabriquer_installation(self.base, avec_certificats=False)
        self.paquets = tempfile.mkdtemp(prefix="bilan-maj-paquets-")
        for dossier in (self.racine, self.paquets):
            self.addCleanup(shutil.rmtree, dossier, True)
        self.pilote = PiloteFactice()
        self.demandes = []

        def demander_arret(*args, **kwargs):
            self.demandes.append(args)
            raise maj.Refus("ARRET_REFUSE", "refus d'essai")

        self.patch(maj, "demander_arret", demander_arret)
        # serveur.journaliser double chaque ligne sur la sortie d'erreur : sans
        # intérêt ici, et bruyant dans la sortie de la suite.
        self.patch(serveur, "ecrire_stderr", lambda ligne: None)
        if os.name == "nt":
            # Les droits Windows sont éprouvés pour de vrai par test_maj_windows ;
            # ici, deux processus icacls par essai ralentiraient la suite pour rien.
            self.patch(maj, "_proteger_windows", lambda dossier: None)

    def patch(self, objet, nom, valeur):
        p = unittest.mock.patch.object(objet, nom, valeur)
        p.start()
        self.addCleanup(p.stop)

    # --- fabrication -----------------------------------------------------------

    def trio(self, version="1.2.0", modifs=None, graine=pe.GRAINE_A, base=None, **kw):
        contenu = dict(self.base if base is None else base)
        for relatif, octets in (modifs or {}).items():
            if octets is None:
                contenu.pop(relatif, None)
            else:
                contenu[relatif] = octets
        contenu = pe.avec_version(contenu, version)
        return pe.fabriquer_trio(self.paquets, contenu, version, graine=graine, **kw)

    def appliquer(self, archive, **kw):
        sortie = io.StringIO()
        options = dict(calme_secondes=0, delai_sante=1)
        options.update(kw)
        pilote = options.pop("pilote", self.pilote)
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(io.StringIO()):
            return maj.appliquer(self.racine, archive, pilote, **options)

    def technique(self):
        try:
            with open(os.path.join(self.racine, "technique.log"), encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""

    def arbre(self):
        """Tout ce qui existe hors de mise-a-jour/ : noms et empreintes."""
        noms = []
        for dossier, sous, fichiers in os.walk(self.racine):
            sous[:] = [d for d in sous if d != "__pycache__"]
            for nom in fichiers + sous:
                noms.append(os.path.relpath(os.path.join(dossier, nom), self.racine))
        noms = sorted(n for n in noms if not n.startswith(
            (serveur.NOM_DOSSIER_MAJ, "journal.log", "technique.log")))
        return noms, pe.instantane(self.racine)

    def etat(self):
        return maj.lire_etat(self.racine)

    def refus(self, archive, code, attendu_pilote=(), **kw):
        """Un refus propre : code attendu, arbre inchangé, aucune demande d'arrêt."""
        avant = self.arbre()
        retour = self.appliquer(archive, **kw)
        report = code in maj.CODES_REPORT
        self.assertEqual(retour, 3 if report else 1)
        evenement = "MAJ_REPORTEE" if report else "MAJ_REFUSEE"
        self.assertIn("%s code=%s" % (evenement, code), self.technique())
        self.assertEqual(self.arbre(), avant)
        self.assertEqual(self.demandes, [])
        self.assertFalse(os.path.exists(os.path.join(
            self.racine, "mise-a-jour", serveur.DEMANDE_ARRET)))
        self.assertEqual(self.pilote.appels, list(attendu_pilote))

    def ecrire_config(self, **changements):
        chemin = os.path.join(self.racine, "config.json")
        with open(chemin) as f:
            config = json.load(f)
        config.update(changements)
        with open(chemin, "w") as f:
            json.dump(config, f)


# ==============================================================================
# A6 — rien n'est écrit hors de mise-a-jour/ avant la bascule
# ==============================================================================

class RefusSansEcriture(Installation):

    def test_client_non_configure(self):
        self.ecrire_config(mise_a_jour={})
        self.refus(self.trio(), "CLIENT_NON_CONFIGURE")

    def test_client_au_mauvais_format(self):
        self.ecrire_config(mise_a_jour={"client": "../cabinet-01"})
        self.refus(self.trio(), "CLIENT_NON_CONFIGURE")

    def test_cles_absentes(self):
        os.remove(os.path.join(self.racine, "serveur", "cles_publication.json"))
        self.refus(self.trio(), "CLES_ABSENTES")

    def test_cles_illisibles(self):
        with open(os.path.join(self.racine, "serveur", "cles_publication.json"), "w") as f:
            f.write("{pas du json")
        self.refus(self.trio(), "CLES_DE_CONFIANCE_INVALIDES")

    def test_version_ecartee(self):
        maj.preparer_dossier_prive(self.racine)
        maj.ecrire_etat(self.racine, ecartees=["1.2.0"])
        self.refus(self.trio("1.2.0"), "VERSION_ECARTEE")
        # Une version supérieure, elle, n'est pas écartée.
        self.assertEqual(self.etat()["ecartees"], ["1.2.0"])

    def test_paquet_incomplet(self):
        # formulaire/version.json est exigé AVANT, par le vérificateur lui-même
        # (VERSION_INCOHERENTE) : trio() la remet d'ailleurs toujours.
        for relatif in maj.PIECES_INDISPENSABLES:
            if relatif == "formulaire/version.json":
                continue
            with self.subTest(piece=relatif):
                self.refus(self.trio(modifs={relatif: None}), "PAQUET_INCOMPLET")

    def test_signature_invalide_cle_inconnue(self):
        self.refus(self.trio(graine=pe.GRAINE_C), "SIGNATURE_INVALIDE")

    def test_version_non_superieure(self):
        self.refus(self.trio("1.1.0"), "VERSION_NON_SUPERIEURE")

    def test_client_different(self):
        self.refus(self.trio(client="cabinet-02"), "CLIENT_DIFFERENT")

    def test_archive_absente(self):
        self.refus(os.path.join(self.paquets, "absente.zip"), "ARCHIVE_ILLISIBLE")

    def test_manifeste_absent(self):
        archive = self.trio()
        os.remove(archive + paquet_signe.SUFFIXE_MANIFESTE)
        self.refus(archive, "MANIFESTE_MALFORME")

    def test_signature_absente_ou_trop_longue(self):
        archive = self.trio()
        chemin = archive + paquet_signe.SUFFIXE_SIGNATURE
        with open(chemin, "ab") as f:
            f.write(b"x" * 2)
        self.refus(archive, "SIGNATURE_INVALIDE")
        os.remove(chemin)
        self.refus(archive, "SIGNATURE_INVALIDE")

    def test_archive_qui_est_un_tube_nomme(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("pas de tube nommé sur ce système")
        archive = os.path.join(self.paquets, "tube.zip")
        os.mkfifo(archive)
        self.refus(archive, "ARCHIVE_ILLISIBLE")

    def test_destination_qui_est_un_dossier(self):
        chemin = os.path.join(self.racine, "docs", "Mode_emploi.md")
        os.remove(chemin)
        os.mkdir(chemin)
        self.refus(self.trio(), "DESTINATION_INVALIDE")

    def test_parent_de_destination_qui_est_un_lien(self):
        cible = tempfile.mkdtemp(prefix="bilan-maj-cible-")
        self.addCleanup(shutil.rmtree, cible, True)
        try:
            os.symlink(cible, os.path.join(self.racine, "docs", "lien"),
                       target_is_directory=True)
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("lien symbolique impossible sur ce poste")
        self.refus(self.trio(modifs={"docs/lien/x.md": b"x"}), "DESTINATION_INVALIDE")
        self.assertEqual(os.listdir(cible), [])

    def test_destination_qui_est_un_lien(self):
        cible = os.path.join(self.paquets, "cible.txt")
        with open(cible, "w") as f:
            f.write("c")
        try:
            os.symlink(cible, os.path.join(self.racine, "docs", "lien.md"))
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("lien symbolique impossible sur ce poste")
        self.refus(self.trio(modifs={"docs/lien.md": b"x"}), "DESTINATION_INVALIDE")

    def test_espace_insuffisant(self):
        self.patch(maj, "espace_libre", lambda racine: 1024)
        self.refus(self.trio(), "ESPACE_INSUFFISANT")

    def test_espace_exige_trois_fois_la_taille_plus_cinquante_mio(self):
        archive = self.trio()
        with maj.contexte_serveur(self.racine):
            maj.preparer_dossier_prive(self.racine)
            plan = maj.controler(self.racine, archive)
        total = sum(t for t, _, _ in plan.fichiers.values())
        besoin = 3 * total + 50 * 1024 * 1024
        self.patch(maj, "espace_libre", lambda racine: besoin - 1)
        self.refus(archive, "ESPACE_INSUFFISANT")
        self.patch(maj, "espace_libre", lambda racine: besoin)
        with maj.contexte_serveur(self.racine):
            self.assertEqual(maj.controler(self.racine, archive).version, "1.2.0")

    def test_extraction_alteree_laisse_prepare_vide(self):
        reel = maj.empreinte_fichier

        def altere(chemin):
            if os.sep + "prepare" + os.sep in chemin:
                with open(chemin, "r+b") as f:
                    premier = f.read(1)
                    f.seek(0)
                    f.write(bytes([premier[0] ^ 1]) if premier else b"x")
            return reel(chemin)

        self.patch(maj, "empreinte_fichier", altere)
        self.refus(self.trio(), "EXTRACTION_ALTEREE")
        prepare = os.path.join(self.racine, "mise-a-jour", "prepare")
        self.assertEqual(os.listdir(prepare), [])

    def test_sauvegarde_alteree_avant_tout_arret(self):
        reel = maj.empreinte_fichier

        def altere(chemin):
            octets, empreinte = reel(chemin)
            if maj.NOM_SAUVEGARDE_NEUVE in chemin and chemin.endswith(".py"):
                return octets, "0" * 64
            return octets, empreinte

        self.patch(maj, "empreinte_fichier", altere)
        self.refus(self.trio(), "SAUVEGARDE_ALTEREE")

    def test_dossier_non_protege_quand_ce_n_est_pas_un_dossier(self):
        chemin = os.path.join(self.racine, serveur.NOM_DOSSIER_MAJ)
        with open(chemin, "w") as f:
            f.write("je ne suis pas un dossier")
        avant = pe.instantane(self.racine, sans=())
        self.assertEqual(self.appliquer(self.trio()), 1)
        self.assertIn("MAJ_REFUSEE code=DOSSIER_NON_PROTEGE", self.technique())
        self.assertEqual(pe.instantane(self.racine, sans=()), avant)

    def test_dossier_qui_est_un_lien_refuse(self):
        cible = tempfile.mkdtemp(prefix="bilan-maj-cible-")
        self.addCleanup(shutil.rmtree, cible, True)
        try:
            os.symlink(cible, os.path.join(self.racine, serveur.NOM_DOSSIER_MAJ),
                       target_is_directory=True)
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("lien symbolique impossible sur ce poste")
        self.assertEqual(self.appliquer(self.trio()), 1)
        self.assertIn("MAJ_REFUSEE code=DOSSIER_NON_PROTEGE", self.technique())
        self.assertEqual(os.listdir(cible), [])

    @unittest.skipIf(os.name == "nt", "les droits POSIX n'existent pas sous Windows")
    def test_dossier_trop_ouvert_est_resserre_a_0700(self):
        dossier = os.path.join(self.racine, serveur.NOM_DOSSIER_MAJ)
        os.mkdir(dossier)
        os.chmod(dossier, 0o777)
        maj.preparer_dossier_prive(self.racine)
        self.assertEqual(stat.S_IMODE(os.stat(dossier).st_mode), 0o700)

    def test_tache_absente(self):
        self.pilote = PiloteFactice(tache_existe=False)
        self.refus(self.trio(), "TACHE_ABSENTE", attendu_pilote=("existe",))

    def test_pas_de_pilote_hors_windows(self):
        avant = self.arbre()
        self.assertEqual(self.appliquer(self.trio(), pilote=None), 3)
        self.assertIn("MAJ_REPORTEE code=TACHE_ABSENTE", self.technique())
        self.assertEqual(self.arbre(), avant)

    def test_serveur_absent(self):
        self.patch(maj, "DELAI_SERVEUR_PRESENT_SECONDES", 0.2)
        self.refus(self.trio(), "SERVEUR_ABSENT", attendu_pilote=("existe",))

    def test_etat_illisible_arrete_tout(self):
        maj.preparer_dossier_prive(self.racine)
        with open(os.path.join(self.racine, "mise-a-jour", "etat.json"), "w") as f:
            f.write('{"etape": "bascule", "etape": "repos"}')
        self.refus(self.trio(), "ETAT_ILLISIBLE")

    def test_aucun_refus_n_ecrit_hors_du_dossier_reserve_meme_vers_etat(self):
        # Le refus consigne son résultat DANS mise-a-jour/etat.json, nulle part ailleurs.
        self.refus(self.trio("1.1.0"), "VERSION_NON_SUPERIEURE")
        etat = self.etat()
        self.assertEqual((etat["etape"], etat["resultat"], etat["code"]),
                         ("repos", "refusee", "VERSION_NON_SUPERIEURE"))


# ==============================================================================
# A9 — les clés installées jugent, jamais celles du paquet
# ==============================================================================

class ClesInstallees(Installation):

    def test_paquet_signe_par_b_dont_la_liste_embarquee_contient_b(self):
        hostile = self.trio(modifs={"serveur/cles_publication.json":
                                    pe.liste_de_cles(pe.CLE_A, pe.CLE_B)},
                            graine=pe.GRAINE_B)
        self.refus(hostile, "SIGNATURE_INVALIDE")

    def test_un_reste_de_prepare_ne_donne_pas_confiance(self):
        # Un prepare/ laissé par une tentative précédente porte une liste {A, B} :
        # il ne doit jamais être lu pour juger un paquet (D5).
        liste = os.path.join(self.racine, "mise-a-jour", "prepare", "serveur")
        os.makedirs(liste)
        with open(os.path.join(liste, "cles_publication.json"), "wb") as f:
            f.write(pe.liste_de_cles(pe.CLE_A, pe.CLE_B))
        os.makedirs(os.path.join(self.racine, "mise-a-jour", "telechargement"))
        hostile = self.trio(modifs={"serveur/cles_publication.json":
                                    pe.liste_de_cles(pe.CLE_A, pe.CLE_B)},
                            graine=pe.GRAINE_B)
        self.refus(hostile, "SIGNATURE_INVALIDE")

    def test_la_cle_du_paquet_sert_au_paquet_suivant_seulement(self):
        # Rotation : N+1 signé par A porte {A, B}. Tant qu'il n'est pas posé, B
        # ne juge rien ; une fois posé (simulé ici), N+2 signé par B passe.
        n2 = self.trio("1.3.0", graine=pe.GRAINE_B)
        self.refus(n2, "SIGNATURE_INVALIDE")
        with open(os.path.join(self.racine, "serveur", "cles_publication.json"), "wb") as f:
            f.write(pe.liste_de_cles(pe.CLE_A, pe.CLE_B))
        with maj.contexte_serveur(self.racine):
            self.assertEqual(maj.controler(self.racine, n2).version, "1.3.0")

    def test_n_plus_2_signe_par_b_avant_n_plus_1_est_refuse(self):
        self.refus(self.trio("1.3.0", graine=pe.GRAINE_B,
                             modifs={"serveur/cles_publication.json":
                                     pe.liste_de_cles(pe.CLE_B)}), "SIGNATURE_INVALIDE")


# ==============================================================================
# A7, A8 — liste blanche
# ==============================================================================

CHEMINS_PROTEGES = (
    "config.json", "cle.pem", "autorite.crt", "journal.log", "technique.log.1",
    "bilans/x.pdf", "formulaire/images/cabinet/logo.png",
    "Formulaire/Images/Cabinet/x.png", "mise-a-jour/etat.json",
    "serveur/__pycache__/x.pyc", "outils/x.py", "serveur/x.pem",
    "docs/bilans/x.pdf",
    # Sous un préfixe admis, seule l'exclusion (casse ignorée) protège ceux-ci :
    "formulaire/Images/Cabinet/x.png", "docs/Config.JSON", "serveur/Y.KEY",
    "docs/y.CRT", "docs/Journal.LOG", "serveur/__PYCACHE__/x.py",
    "serveur/serveur.py.maj-tmp",
)


class ListeBlanche(Installation):

    def test_chemins_proteges_refuses_derriere_une_signature_valide(self):
        self.ecrire_config(dossier_pdf="docs/bilans")
        for relatif in CHEMINS_PROTEGES:
            with self.subTest(chemin=relatif):
                self.refus(self.trio(modifs={relatif: b"pirate"}), "CHEMIN_PROTEGE")

    def test_un_chemin_admis_n_est_pas_refuse(self):
        for relatif in ("docs/nouveau.md", "serveur/nouveau.py", "formulaire/nouveau.js",
                        "LISEZMOI.txt", "demarrer-serveur.bat"):
            with self.subTest(chemin=relatif):
                self.assertTrue(maj.chemin_admis(relatif))
        for relatif in ("serveur", "autre/x.md", "lisezmoi.txt", "Serveur/x.py",
                        "docs\\x.md", "../x", "/etc/passwd"):
            with self.subTest(chemin=relatif):
                self.assertFalse(maj.chemin_admis(relatif))


@unittest.skipUnless(
    all(shutil.which(n) for n in ("sh", "zip", "unzip", "git")),
    "sh, zip, unzip et git requis pour fabriquer le paquet réel")
class ListeDerivee(unittest.TestCase):
    """La liste blanche contre le paquet RÉEL de faire-paquet.sh, dans les deux sens."""

    @classmethod
    def setUpClass(cls):
        from test_scripts_installation import fabriquer_paquet_extrait
        cls.travail, cls.extrait = fabriquer_paquet_extrait()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.travail, ignore_errors=True)

    def chemins_du_paquet(self):
        resultat = []
        for dossier, _, fichiers in os.walk(str(self.extrait)):
            for nom in fichiers:
                resultat.append(os.path.relpath(
                    os.path.join(dossier, nom), str(self.extrait)).replace(os.sep, "/"))
        return sorted(resultat)

    def test_chaque_chemin_du_paquet_est_admis(self):
        chemins = self.chemins_du_paquet()
        self.assertGreater(len(chemins), 20)
        refuses = [c for c in chemins if not maj.chemin_admis(c)]
        self.assertEqual(refuses, [])

    def test_chaque_entree_de_la_liste_blanche_apparait_dans_le_paquet(self):
        chemins = self.chemins_du_paquet()
        for prefixe in maj.PREFIXES_ADMIS:
            with self.subTest(prefixe=prefixe):
                self.assertTrue([c for c in chemins if c.startswith(prefixe)])
        for nom in maj.FICHIERS_RACINE_ADMIS:
            with self.subTest(fichier=nom):
                self.assertIn(nom, chemins)

    def test_maj_py_est_dans_le_paquet(self):
        self.assertIn("serveur/maj.py", self.chemins_du_paquet())

    def test_les_pieces_indispensables_sont_dans_le_paquet(self):
        # Le schéma du client est ajouté par faire-paquet.sh ; cles_publication.json
        # est l'exception : le dépôt ne le porte pas tant que la clé n'est pas faite.
        chemins = self.chemins_du_paquet()
        manquantes = [p for p in maj.PIECES_INDISPENSABLES
                      if p not in chemins and p != "serveur/cles_publication.json"]
        self.assertEqual(manquantes, [])


# ==============================================================================
# A10, A11 — schéma modifié sur place, MAX_PATH
# ==============================================================================

class SchemaModifie(Installation):

    def poser_installe(self):
        maj.preparer_dossier_prive(self.racine)
        schema = self.base["formulaire/schema.json"]
        maj.ecrire_json(os.path.join(self.racine, "mise-a-jour", "installe.json"), {
            "version": "1.1.0", "fichiers": {"formulaire/schema.json": pe.sha(schema)}})

    def retoucher(self):
        with open(os.path.join(self.racine, "formulaire", "schema.json"), "ab") as f:
            f.write(b"\n")

    def test_schema_retouche_sur_place_est_refuse(self):
        self.poser_installe()
        self.retoucher()
        self.refus(self.trio(), "SCHEMA_MODIFIE_LOCALEMENT")

    def test_schema_intact_est_remplace(self):
        self.poser_installe()
        archive = self.trio(modifs={"formulaire/schema.json": b'{"version": 9}\n'})
        with maj.contexte_serveur(self.racine):
            self.assertEqual(maj.controler(self.racine, archive).version, "1.2.0")

    def test_sans_installe_json_la_meme_retouche_est_remplacee(self):
        self.retoucher()
        archive = self.trio()
        with maj.contexte_serveur(self.racine):
            maj.preparer_dossier_prive(self.racine)
            self.assertEqual(maj.controler(self.racine, archive).version, "1.2.0")

    def test_schema_absent_du_nouveau_paquet_reste_en_place(self):
        self.poser_installe()
        self.retoucher()
        archive = self.trio(modifs={"formulaire/schema.json": None})
        with maj.contexte_serveur(self.racine):
            self.assertEqual(maj.controler(self.racine, archive).version, "1.2.0")


class MaxPath(Installation):

    def test_formes_absolues_comptent_le_temporaire_et_les_deux_copies(self):
        formes = maj.formes_absolues(self.racine, "docs/a.md")
        self.assertEqual(len(formes), 4)
        self.assertEqual(max(len(f) for f in formes),
                         len(os.path.join(self.racine, "mise-a-jour",
                                          maj.NOM_SAUVEGARDE_NEUVE, "docs", "a.md")))

    def test_frontiere_259_260(self):
        relatif = "docs/" + "a" * 100 + ".md"
        longueur = max(len(f) for f in maj.formes_absolues(self.racine, relatif))
        # Une racine plus courte ou plus longue d'exactement ce qu'il faut.
        decalage = maj.LONGUEUR_MAX_CHEMIN_ABSOLU - longueur
        racine_ok = self.racine + "x" * max(decalage, 0)
        racine_trop = self.racine + "x" * (decalage + 1)
        maj.controler_longueurs(racine_ok, [relatif])
        with self.assertRaises(maj.Refus) as contexte:
            maj.controler_longueurs(racine_trop, [relatif])
        self.assertEqual(contexte.exception.code, "CHEMIN_TROP_LONG")

    def test_racine_trop_longue_pour_la_sauvegarde_seulement(self):
        # Le plus long chemin du paquet : sa copie sauvegardée dépasse 259, sa
        # destination et son extraction non.
        relatif = "docs/" + "b" * 100 + ".md"
        base = dict(self.base)
        base[relatif] = b"long"
        formes = maj.formes_absolues(self.racine, relatif)
        pas = maj.LONGUEUR_MAX_CHEMIN_ABSOLU + 1 - max(len(f) for f in formes)
        self.assertGreater(pas, 0, "la racine d'essai est déjà trop longue")
        # Un sous-dossier de la racine fait le décalage : tout le reste du bac est
        # recréé dedans, copié par noms.
        profonde = os.path.join(self.racine, "p" * (pas - 1))
        os.makedirs(profonde, exist_ok=True)
        racine = os.path.realpath(profonde)
        for rel, octets in base.items():
            chemin = os.path.join(racine, *rel.split("/"))
            os.makedirs(os.path.dirname(chemin), exist_ok=True)
            with open(chemin, "wb") as f:
                f.write(octets)
        shutil.copy(os.path.join(self.racine, "config.json"), racine)
        self.racine_logique = racine
        self.assertEqual(max(len(f) for f in maj.formes_absolues(racine, relatif)),
                         maj.LONGUEUR_MAX_CHEMIN_ABSOLU + 1)
        archive = pe.fabriquer_trio(
            self.paquets, pe.avec_version(base, "1.2.0"), "1.2.0")
        self.racine = racine
        self.refus(archive, "CHEMIN_TROP_LONG")
        # Sans la sauvegarde, la destination et l'extraction tiennent en 259.
        self.assertLessEqual(len(maj.formes_absolues(racine, relatif)[0]), 259)
        self.assertLessEqual(len(maj.formes_absolues(racine, relatif)[2]), 259)


# ==============================================================================
# Pose idempotente, reprise, retour
# ==============================================================================

class PoseEtRetour(Installation):

    def preparer(self, version="1.2.0", modifs=None):
        """Contrôle, extrait et sauvegarde un paquet : prêt à basculer."""
        archive = self.trio(version, modifs)
        with maj.contexte_serveur(self.racine):
            maj.preparer_dossier_prive(self.racine)
            plan = maj.controler(self.racine, archive)
            maj.extraire(plan)
            maj.sauvegarder(plan)
        return plan

    def attendus(self, plan):
        return dict((r, v[1]) for r, v in plan.fichiers.items())

    def test_pose_idempotente(self):
        plan = self.preparer()
        prepare = os.path.join(self.racine, "mise-a-jour", "prepare")
        premiere = maj.poser_fichiers(self.racine, prepare, self.attendus(plan), "EXTRACTION_ALTEREE")
        self.assertGreaterEqual(premiere, 2)
        self.assertEqual(maj.poser_fichiers(
            self.racine, prepare, self.attendus(plan), "EXTRACTION_ALTEREE"), 0)
        # Un seul fichier abîmé : un seul remplacement, rien d'autre.
        with open(os.path.join(self.racine, "docs", "Mode_emploi.md"), "ab") as f:
            f.write(b"x")
        self.assertEqual(maj.poser_fichiers(
            self.racine, prepare, self.attendus(plan), "EXTRACTION_ALTEREE"), 1)

    def test_aucun_temporaire_ne_reste_apres_la_pose(self):
        plan = self.preparer()
        prepare = os.path.join(self.racine, "mise-a-jour", "prepare")
        maj.poser_fichiers(self.racine, prepare, self.attendus(plan), "EXTRACTION_ALTEREE")
        restes = [n for _, _, noms in os.walk(self.racine) for n in noms
                  if n.endswith(maj.SUFFIXE_TEMPORAIRE)]
        self.assertEqual(restes, [])

    def test_pose_refuse_une_source_alteree(self):
        plan = self.preparer()
        prepare = os.path.join(self.racine, "mise-a-jour", "prepare")
        with open(os.path.join(prepare, "docs", "Mode_emploi.md"), "ab") as f:
            f.write(b"abime")
        avant = self.arbre()
        with self.assertRaises(maj.Refus) as contexte:
            maj.poser_fichiers(self.racine, prepare, self.attendus(plan), "EXTRACTION_ALTEREE")
        self.assertEqual(contexte.exception.code, "EXTRACTION_ALTEREE")
        # Le fichier fautif n'a pas été remplacé ; son temporaire a été effacé.
        noms, _ = self.arbre()
        self.assertEqual([n for n in noms if n.endswith(maj.SUFFIXE_TEMPORAIRE)], [])
        self.assertEqual(self.arbre()[1]["docs/Mode_emploi.md"], avant[1]["docs/Mode_emploi.md"])

    def test_sauvegarde_conforme_a_l_inventaire(self):
        plan = self.preparer(modifs={"docs/nouveau.md": b"neuf"})
        inventaire = maj.lire_inventaire(self.racine)
        self.assertEqual(inventaire["de"], "1.1.0")
        self.assertEqual(inventaire["vers"], "1.2.0")
        self.assertEqual(inventaire["absents"], ["docs/nouveau.md"])
        self.assertFalse(inventaire["installe"])
        for relatif, empreinte in inventaire["presents"].items():
            self.assertEqual(empreinte, pe.sha(self.base[relatif]))
            copie = os.path.join(self.racine, "mise-a-jour", "sauvegarde", *relatif.split("/"))
            with open(copie, "rb") as f:
                self.assertEqual(pe.sha(f.read()), empreinte)
        self.assertEqual(set(inventaire["presents"]) | set(inventaire["absents"]),
                         set(plan.fichiers))
        # Copiée, jamais déplacée.
        self.assertTrue(os.path.exists(os.path.join(self.racine, "docs", "Mode_emploi.md")))

    def test_une_seule_sauvegarde_est_gardee_et_remplacee_apres_reussite(self):
        self.preparer("1.2.0")
        premiere = maj.lire_inventaire(self.racine)
        self.assertEqual(premiere["vers"], "1.2.0")
        self.preparer("1.3.0")
        self.assertEqual(maj.lire_inventaire(self.racine)["vers"], "1.3.0")
        self.assertFalse(os.path.exists(os.path.join(
            self.racine, "mise-a-jour", maj.NOM_SAUVEGARDE_NEUVE)))

    def basculer_a_moitie(self, plan, nombre):
        """Pose `nombre` fichiers du paquet puis simule la coupure."""
        prepare = os.path.join(self.racine, "mise-a-jour", "prepare")
        attendus = self.attendus(plan)
        choisis = dict((r, attendus[r]) for r in sorted(attendus)[:nombre])
        maj.ecrire_etat(self.racine, etape="bascule", de=plan.installee, vers=plan.version)
        maj.poser_fichiers(self.racine, prepare, choisis, "EXTRACTION_ALTEREE")

    def test_reprise_depuis_une_bascule_interrompue(self):
        # M10 : « bascule » ne doit jamais être tenue pour achevée.
        avant = self.arbre()
        plan = self.preparer(modifs={"docs/nouveau.md": b"neuf"})
        self.basculer_a_moitie(plan, 4)
        self.assertNotEqual(self.arbre(), avant)
        self.patch(maj, "attendre_sante", lambda *a, **k: True)
        with maj.contexte_serveur(self.racine):
            self.assertTrue(maj.reprendre(self.racine, self.pilote, 8000, delai_sante=1))
        self.assertEqual(self.arbre(), avant)
        etat = self.etat()
        self.assertEqual((etat["etape"], etat["resultat"], etat["code"]),
                         ("repos", "revenue", "INTERROMPUE"))
        self.assertEqual(etat["ecartees"], [])
        self.assertEqual(self.pilote.appels.count("demarrer"), 1)
        self.assertEqual(self.pilote.appels.count("arreter_de_force"), 2)

    def test_reprise_rejouee_converge_et_ne_refait_que_le_reste(self):
        avant = self.arbre()
        plan = self.preparer()
        self.basculer_a_moitie(plan, 4)
        self.patch(maj, "attendre_sante", lambda *a, **k: True)
        compteur = []
        reel = maj.poser_fichiers

        def espion(*args, **kwargs):
            compteur.append(reel(*args, **kwargs))
            return compteur[-1]

        self.patch(maj, "poser_fichiers", espion)
        with maj.contexte_serveur(self.racine):
            maj.reprendre(self.racine, self.pilote, 8000, delai_sante=1)
            premier = list(compteur)
            maj.ecrire_etat(self.racine, etape="retour")
            maj.reprendre(self.racine, self.pilote, 8000, delai_sante=1)
        self.assertGreaterEqual(premier[0], 1)
        self.assertEqual(compteur[1], 0)
        self.assertEqual(self.arbre(), avant)

    def test_reprise_sans_rien_a_faire(self):
        with maj.contexte_serveur(self.racine):
            maj.preparer_dossier_prive(self.racine)
            self.assertTrue(maj.reprendre(self.racine, self.pilote, 8000))
            maj.ecrire_etat(self.racine, etape="preparee")
            self.assertTrue(maj.reprendre(self.racine, self.pilote, 8000))
        self.assertEqual(self.pilote.appels, [])

    def test_retour_qui_echoue_trois_fois_laisse_echec_retour(self):
        plan = self.preparer()
        self.basculer_a_moitie(plan, 3)
        copie = os.path.join(self.racine, "mise-a-jour", "sauvegarde", "docs", "Mode_emploi.md")
        with open(copie, "wb") as f:
            f.write(b"abime")
        self.patch(maj, "attendre_sante", lambda *a, **k: True)
        with maj.contexte_serveur(self.racine):
            self.assertFalse(maj.revenir_a_la_sauvegarde(
                self.racine, self.pilote, 8000, "SANTE_MUETTE", delai_sante=1))
        etat = self.etat()
        self.assertEqual(etat["etape"], "echec-retour")
        self.assertIn("1.2.0", etat["ecartees"])
        self.assertIn("MAJ_RETOUR cause=SANTE_MUETTE resultat=echec de=1.1.0 vers=1.2.0",
                      self.technique())
        # Le démarrage est tenté quand même, après les trois tentatives.
        self.assertEqual(self.pilote.appels[-1], "demarrer")
        self.assertEqual(self.pilote.appels.count("arreter_de_force"), 3)

    def test_une_version_interrompue_n_est_pas_ecartee_mais_une_cassee_oui(self):
        for cause, ecartee in (("INTERROMPUE", False), ("SANTE_MUETTE", True),
                               ("AUTO_CONTROLE_ECHOUE", True), ("RETOUR_MANUEL", True),
                               ("ECRITURE_IMPOSSIBLE", False)):
            with self.subTest(cause=cause):
                self.setUp()
                plan = self.preparer()
                self.basculer_a_moitie(plan, 2)
                self.patch(maj, "attendre_sante", lambda *a, **k: True)
                with maj.contexte_serveur(self.racine):
                    self.assertTrue(maj.revenir_a_la_sauvegarde(
                        self.racine, self.pilote, 8000, cause, delai_sante=1))
                self.assertEqual("1.2.0" in self.etat()["ecartees"], ecartee)

    def test_ecartees_bornees_a_dix(self):
        maj.preparer_dossier_prive(self.racine)
        versions = ["1.%d.0" % n for n in range(2, 14)]
        maj.ecrire_etat(self.racine, ecartees=versions[:10])
        plan = self.preparer("1.20.0")
        self.basculer_a_moitie(plan, 1)
        self.patch(maj, "attendre_sante", lambda *a, **k: True)
        with maj.contexte_serveur(self.racine):
            maj.revenir_a_la_sauvegarde(self.racine, self.pilote, 8000, "SANTE_MUETTE",
                                        delai_sante=1)
        ecartees = self.etat()["ecartees"]
        self.assertEqual(len(ecartees), 10)
        self.assertEqual(ecartees[-1], "1.20.0")
        self.assertNotIn("1.2.0", ecartees)

    def test_revenir_refuse_une_sauvegarde_qui_n_est_pas_celle_de_la_version(self):
        # Une tentative abandonnée après sa sauvegarde ne doit pas faire « revenir »
        # à ce qui est déjà installé.
        self.preparer()
        self.assertEqual(maj.lire_version_installee(self.racine), "1.1.0")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(maj.revenir(self.racine, self.pilote), 1)
        self.assertIn("MAJ_REFUSEE code=RETOUR_IMPOSSIBLE", self.technique())


class ArretCoteClient(Installation):
    """`demander_arret` : la demande que le client écrit, ce qu'il attend, ce qu'il
    ne fait jamais (tuer le serveur)."""

    def setUp(self):
        Installation.setUp(self)
        with maj.contexte_serveur(self.racine):
            maj.preparer_dossier_prive(self.racine)
        self.dossier = os.path.join(self.racine, "mise-a-jour")

    def repondre(self, verdict, motif="aucun", delai_avant=0.05):
        """Un faux serveur : lit la demande, répond au jeton lu."""
        import threading
        import time

        def serveur_factice():
            chemin = os.path.join(self.dossier, "arret.demande")
            limite = time.monotonic() + 5
            while time.monotonic() < limite and not os.path.exists(chemin):
                time.sleep(0.01)
            with open(chemin) as f:
                demande = json.load(f)
            os.remove(chemin)
            self.demande_lue = demande
            time.sleep(delai_avant)
            for v in (verdict, "arrete") if verdict == "accepte" else (verdict,):
                serveur.ecrire_atomiquement(
                    os.path.join(self.dossier, "arret.reponse"),
                    json.dumps({"jeton": demande["jeton"], "verdict": v,
                                "motif": motif}).encode())
                time.sleep(0.1)

        fil = threading.Thread(target=serveur_factice)
        fil.start()
        self.addCleanup(fil.join, 10)

    def test_demande_ecrite_au_format_attendu_et_refus_rapporte(self):
        self.repondre("refuse", "depot-en-cours")
        with self.assertRaises(maj.Refus) as contexte:
            DEMANDER_ARRET_REEL(self.racine, 1, 120, False, delai_reponse=5, delai_arret=1)
        self.assertEqual(contexte.exception.code, "ARRET_REFUSE")
        self.assertIn("depot-en-cours", contexte.exception.detail)
        demande = self.demande_lue
        self.assertEqual(sorted(demande), ["calme_secondes", "demarrage", "jeton"])
        self.assertEqual((demande["calme_secondes"], demande["demarrage"]), (120, False))
        self.assertTrue(serveur.demande_arret_valide(demande))

    def test_acceptation_attend_arrete_puis_le_port_ferme(self):
        self.patch(maj, "PAUSE_APRES_ARRET_SECONDES", 0)
        self.patch(maj, "port_ferme", lambda port: True)
        self.repondre("accepte")
        DEMANDER_ARRET_REEL(self.racine, 1, 0, True, delai_reponse=5, delai_arret=5)
        self.assertTrue(self.demande_lue["demarrage"])

    def test_serveur_qui_ne_repond_pas(self):
        with self.assertRaises(maj.Refus) as contexte:
            DEMANDER_ARRET_REEL(self.racine, 1, 0, False, delai_reponse=0.3, delai_arret=1)
        self.assertEqual(contexte.exception.code, "ARRET_SANS_REPONSE")
        self.assertFalse(os.path.exists(os.path.join(self.dossier, "arret.demande")))

    def test_acceptation_sans_port_ferme_ne_force_rien(self):
        self.patch(maj, "PAUSE_APRES_ARRET_SECONDES", 0)
        self.patch(maj, "port_ferme", lambda port: False)
        self.repondre("accepte")
        with self.assertRaises(maj.Refus) as contexte:
            DEMANDER_ARRET_REEL(self.racine, 1, 0, False, delai_reponse=5, delai_arret=0.4)
        self.assertEqual(contexte.exception.code, "ARRET_SANS_REPONSE")
        self.assertEqual(self.pilote.appels, [])

    def test_reponse_d_un_autre_jeton_est_ignoree(self):
        serveur.ecrire_atomiquement(os.path.join(self.dossier, "arret.reponse"),
                                    json.dumps({"jeton": "cd" * 16, "verdict": "arrete",
                                                "motif": "aucun"}).encode())
        with self.assertRaises(maj.Refus) as contexte:
            DEMANDER_ARRET_REEL(self.racine, 1, 0, False, delai_reponse=0.3, delai_arret=0.3)
        self.assertEqual(contexte.exception.code, "ARRET_SANS_REPONSE")

    def test_port_ferme(self):
        import socket
        with socket.socket() as ecoute:
            ecoute.bind(("127.0.0.1", 0))
            ecoute.listen(1)
            port = ecoute.getsockname()[1]
            self.assertFalse(maj.port_ferme(port))
        self.assertTrue(maj.port_ferme(port))

    def test_attente_de_sante_relance_la_tache_tant_que_muette(self):
        self.patch(maj, "sante_repond", lambda port, delai_connexion=3: False)
        relances = []
        self.assertFalse(maj.attendre_sante(
            1, 0.45, intervalle=0.02, relancer=lambda: relances.append(1),
            intervalle_relance=0.1))
        self.assertGreaterEqual(len(relances), 2)
        self.patch(maj, "sante_repond", lambda port, delai_connexion=3: True)
        relances.clear()
        self.assertTrue(maj.attendre_sante(1, 5, relancer=lambda: relances.append(1)))
        self.assertEqual(relances, [])

    def test_sante_sans_serveur(self):
        import socket
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        self.assertFalse(maj.sante_repond(port, delai_connexion=1))
        self.assertFalse(maj.sante_repond(None))


# ==============================================================================
# A15, A16 — verrou, dépôt de développement
# ==============================================================================

SCRIPT_VERROU = '''
import sys
sys.path.insert(0, sys.argv[1])
import maj
with maj.verrou(sys.argv[2]):
    print("pret", flush=True)
    sys.stdin.readline()
'''


class Verrou(Installation):

    def test_verrou_tenu_par_un_autre_processus(self):
        with maj.contexte_serveur(self.racine):
            maj.preparer_dossier_prive(self.racine)
        detenteur = subprocess.Popen(
            [sys.executable, "-B", "-c", SCRIPT_VERROU, os.path.join(PROJET, "serveur"),
             self.racine], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            universal_newlines=True)
        try:
            self.assertEqual(detenteur.stdout.readline().strip(), "pret")
            avant = self.arbre()
            self.assertEqual(self.appliquer(self.trio()), 3)
            self.assertEqual(self.arbre(), avant)
            lignes = [l for l in self.technique().splitlines() if " MAJ_" in l]
            self.assertEqual(len(lignes), 1)
            self.assertTrue(lignes[0].endswith("MAJ_REPORTEE code=DEJA_EN_COURS"), lignes)
            self.assertFalse(os.path.exists(os.path.join(
                self.racine, "mise-a-jour", "etat.json")))
            self.assertEqual(self.pilote.appels, [])
        finally:
            detenteur.stdin.close()
            detenteur.wait(timeout=15)
            detenteur.stdout.close()
        # Relâché à la fin du processus : le verrou suivant passe.
        with maj.verrou(self.racine):
            pass

    def test_verrou_pris_deux_fois_dans_un_processus(self):
        with maj.contexte_serveur(self.racine):
            maj.preparer_dossier_prive(self.racine)
        with maj.verrou(self.racine):
            with self.assertRaises(maj.Refus) as contexte:
                with maj.verrou(self.racine):
                    pass
            self.assertEqual(contexte.exception.code, "DEJA_EN_COURS")


class DepotDeDeveloppement(Installation):

    def test_racine_avec_git_sort_en_code_2_sans_rien_creer(self):
        os.mkdir(os.path.join(self.racine, ".git"))
        archive = self.trio()
        avant = self.arbre()
        noms_avant = sorted(os.listdir(self.racine))
        for commande in (["appliquer", archive], ["etat"], ["revenir"], ["reprendre"],
                         ["auto-controle"]):
            with self.subTest(commande=commande[0]):
                resultat = subprocess.run(
                    [sys.executable, "-B", os.path.join(self.racine, "serveur", "maj.py")]
                    + commande, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                    timeout=60)
                self.assertEqual(resultat.returncode, 2, resultat.stderr)
                self.assertIn(".git", resultat.stdout)
                self.assertEqual(sorted(os.listdir(self.racine)), noms_avant)
                self.assertEqual(self.arbre(), avant)

    def test_la_garde_passe_par_main(self):
        os.mkdir(os.path.join(self.racine, ".git"))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(maj.main(["etat"], racine=self.racine), 2)


# ==============================================================================
# Commandes de lecture
# ==============================================================================

class Commandes(Installation):

    def test_etat_imprime_l_essentiel_sans_rien_ecrire(self):
        maj.preparer_dossier_prive(self.racine)
        maj.ecrire_etat(self.racine, resultat="refusee", code="CHEMIN_PROTEGE",
                        ecartees=["1.9.0"])
        avant = self.arbre()
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            self.assertEqual(maj.main(["etat"], racine=self.racine), 0)
        texte = sortie.getvalue()
        for attendu in ("repos", "refusee", "CHEMIN_PROTEGE", "1.1.0", "1.9.0"):
            self.assertIn(attendu, texte)
        self.assertEqual(self.arbre(), avant)
        self.assertFalse(os.path.exists(os.path.join(self.racine, "mise-a-jour", "verrou")))

    def test_auto_controle_reussit_sur_une_installation_saine(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(maj.main(["auto-controle"], racine=self.racine), 0)
        self.assertFalse(os.path.exists(os.path.join(self.racine, "mise-a-jour")))

    def test_auto_controle_echoue_quand_une_entree_manque(self):
        os.remove(os.path.join(self.racine, "serveur", "cles_publication.json"))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(maj.main(["auto-controle"], racine=self.racine), 1)

    def test_auto_controle_dans_un_processus_separe(self):
        resultat = subprocess.run(
            [sys.executable, "-B", os.path.join(self.racine, "serveur", "maj.py"),
             "auto-controle"], stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=60)
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)

    def test_aide_liste_les_cinq_sous_commandes(self):
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie), self.assertRaises(SystemExit) as contexte:
            maj.main(["--help"], racine=self.racine)
        self.assertEqual(contexte.exception.code, 0)
        for commande in ("appliquer", "revenir", "reprendre", "etat", "auto-controle"):
            self.assertIn(commande, sortie.getvalue())

    def test_commande_inconnue_ou_absente_refusee(self):
        for argv in ([], ["detruire"]):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as contexte:
                    maj.main(argv, racine=self.racine)
                self.assertEqual(contexte.exception.code, 2)


# ==============================================================================
# Traces
# ==============================================================================

class Traces(Installation):

    def test_detail_maj_compose_des_champs_fermes(self):
        self.assertEqual(
            maj.detail_maj(cause="SANTE_MUETTE", resultat="ok", de="1.1.0", vers="1.2.0"),
            "cause=SANTE_MUETTE resultat=ok de=1.1.0 vers=1.2.0")
        self.assertEqual(maj.detail_maj(code="SIGNATURE_INVALIDE"), "code=SIGNATURE_INVALIDE")
        self.assertEqual(maj.detail_maj(de="1.1.0", vers="1.2.0", cles="changees"),
                         "de=1.1.0 vers=1.2.0 cles=changees")
        self.assertEqual(maj.detail_maj(code="SIGNATURE_INVALIDE", de=None), "code=SIGNATURE_INVALIDE")

    def test_detail_maj_refuse_tout_autre_champ(self):
        for champs in ({"chemin": "x"}, {"detail": "x"}, {"code": "SANTE_MUETTE", "url": "x"},
                       {"erreur": "x"}):
            with self.subTest(champs=champs):
                with self.assertRaises(ValueError):
                    maj.detail_maj(**champs)
        with self.assertRaises(ValueError):
            maj.detail_maj(resultat="peut-etre")
        with self.assertRaises(ValueError):
            maj.detail_maj(cles="autres")

    def test_detail_maj_ne_laisse_passer_ni_chemin_ni_texte(self):
        piege = os.path.join(self.racine, "secret", "Dupont.pdf")
        self.assertEqual(maj.detail_maj(code=piege), "code=CODE_INCONNU")
        self.assertEqual(maj.detail_maj(cause="C:\\Users\\Léa"), "cause=CODE_INCONNU")
        self.assertEqual(maj.detail_maj(de=piege, vers="1.2.0-beta"), "de=inconnue vers=inconnue")
        self.assertNotIn("Dupont", maj.detail_maj(code=piege, de=piege, vers=piege))

    def test_un_refus_ecrit_le_detail_dans_le_journal_nominatif_seulement(self):
        archive = os.path.join(self.paquets, "absente-Dupont.zip")
        with maj.contexte_serveur(self.racine):
            pass
        self.assertEqual(self.appliquer(archive), 1)
        with open(os.path.join(self.racine, "journal.log"), encoding="utf-8") as f:
            nominatif = f.read()
        self.assertIn("absente-Dupont.zip", nominatif)
        self.assertIn("MAJ_REFUSEE code=ARCHIVE_ILLISIBLE detail=", nominatif)
        self.assertNotIn("Dupont", self.technique())
        self.assertNotIn(self.paquets, self.technique())
        self.assertIn("MAJ_REFUSEE code=ARCHIVE_ILLISIBLE", self.technique())

    def test_le_contexte_ne_laisse_aucune_trace_dans_les_journaux_du_depot(self):
        reels = (serveur.JOURNAL, serveur.TECHNIQUE, serveur.CONFIG)
        avant = [os.path.getsize(c) if os.path.exists(c) else None for c in reels[:2]]
        self.appliquer(os.path.join(self.paquets, "absente.zip"))
        self.assertEqual(
            [os.path.getsize(c) if os.path.exists(c) else None for c in reels[:2]], avant)
        self.assertEqual((serveur.JOURNAL, serveur.TECHNIQUE, serveur.CONFIG), reels)

    def test_l_interrupteur_du_journal_technique_est_respecte(self):
        self.ecrire_config(journal_technique=False)
        self.appliquer(os.path.join(self.paquets, "absente.zip"))
        self.assertNotIn("MAJ_REFUSEE", self.technique())
        with open(os.path.join(self.racine, "journal.log"), encoding="utf-8") as f:
            self.assertIn("MAJ_REFUSEE", f.read())


# ==============================================================================
# Constantes, pilote Windows, droits
# ==============================================================================

class Constantes(unittest.TestCase):

    def test_constantes_de_production(self):
        self.assertEqual(maj.DELAI_SANTE_SECONDES, 60)
        self.assertEqual(maj.DELAI_AUTO_CONTROLE_SECONDES, 60)
        self.assertEqual(maj.DELAI_REPONSE_ARRET_SECONDES, 30)
        self.assertEqual(maj.DELAI_ARRET_SECONDES, 90)
        self.assertEqual(maj.CALME_SECONDES_DEFAUT, 120)
        self.assertEqual(maj.TAILLE_MAX_ARCHIVE, 64 * 1024 * 1024)
        self.assertEqual(maj.TAILLE_MAX_SIGNATURE, 65)
        self.assertEqual(maj.TENTATIVES_RETOUR, 3)
        self.assertEqual(maj.TENTATIVES_REMPLACEMENT, 5)
        self.assertEqual(maj.PAUSE_REMPLACEMENT_SECONDES, 0.5)
        self.assertEqual(maj.LONGUEUR_MAX_CHEMIN_ABSOLU, 259)
        self.assertEqual(maj.VERSIONS_ECARTEES_MAX, 10)
        self.assertEqual(maj.MARGE_ESPACE_OCTETS, 50 * 1024 * 1024)
        self.assertEqual(serveur.DELAI_DEMARRAGE_MAX_SECONDES, 900)

    def test_codes_fermes_et_disjoints_de_ceux_du_verificateur(self):
        self.assertEqual(len(set(maj.CODES_MAJ)), len(maj.CODES_MAJ))
        self.assertEqual(set(maj.CODES_MAJ) & set(paquet_signe.CODES), set())
        self.assertTrue(maj.CODES_REPORT <= set(maj.CODES_MAJ))
        self.assertTrue(set(maj.CAUSES_ECARTEES) <= set(maj.CODES_MAJ))
        for code in maj.CODES_MAJ:
            self.assertRegex(code, r"^[A-Z_]{1,40}$")
        with self.assertRaises(ValueError):
            maj.Refus("PAS_UN_CODE")

    def test_les_suffixes_sont_ceux_du_verificateur(self):
        self.assertEqual(paquet_signe.SUFFIXE_MANIFESTE, ".manifeste.json")
        self.assertEqual(paquet_signe.SUFFIXE_SIGNATURE, ".manifeste.sig")
        with open(os.path.join(PROJET, "outils", "signer-paquet.py"), encoding="utf-8") as f:
            source = f.read()
        self.assertIn("SUFFIXE_MANIFESTE = paquet_signe.SUFFIXE_MANIFESTE", source)
        self.assertIn("SUFFIXE_SIGNATURE = paquet_signe.SUFFIXE_SIGNATURE", source)
        self.assertNotIn('".manifeste.json"', source)

    def test_nom_de_la_tache_egal_a_celui_du_script_d_installation(self):
        with open(os.path.join(PROJET, "installer-demarrage.ps1"), encoding="utf-8-sig") as f:
            correspondance = re.search(r'^\$NOM_TACHE\s*=\s*"([^"]+)"', f.read(), re.MULTILINE)
        self.assertIsNotNone(correspondance)
        self.assertEqual(maj.NOM_TACHE_SERVEUR, correspondance.group(1))
        self.assertEqual(maj.PiloteTachePlanifiee().nom, correspondance.group(1))

    def test_le_dossier_reserve_est_nomme_une_fois(self):
        self.assertEqual(os.path.basename(serveur.DOSSIER_MAJ), "mise-a-jour")
        self.assertEqual(serveur.NOM_DOSSIER_MAJ, "mise-a-jour")
        self.assertEqual(maj.dossier_maj("/r"), os.path.join("/r", "mise-a-jour"))


class PiloteTache(unittest.TestCase):
    """PiloteTachePlanifiee jugé par le code de sortie seul, schtasks par son
    chemin absolu, sans shell. Le vrai schtasks est éprouvé par test_maj_windows."""

    def pilote(self, code):
        appels = []

        def faux(arguments, delai=60):
            appels.append(arguments)
            return code

        patch = unittest.mock.patch.object(maj, "_lancer_windows", faux)
        patch.start()
        self.addCleanup(patch.stop)
        return maj.PiloteTachePlanifiee("BilanPosturo-essai"), appels

    def test_existe_demarrer_arreter(self):
        pilote, appels = self.pilote(0)
        self.assertTrue(pilote.existe())
        pilote.demarrer()
        self.assertTrue(pilote.arreter_de_force())
        self.assertEqual([a[1:] for a in appels], [
            ["/Query", "/TN", "BilanPosturo-essai"], ["/Run", "/TN", "BilanPosturo-essai"],
            ["/End", "/TN", "BilanPosturo-essai"]])
        for appel in appels:
            self.assertTrue(os.path.isabs(appel[0]) or appel[0].startswith("C:"))
            self.assertTrue(appel[0].lower().endswith("schtasks.exe"))
            self.assertIn("system32", appel[0].lower())

    def test_code_non_nul(self):
        pilote, _ = self.pilote(1)
        self.assertFalse(pilote.existe())
        self.assertFalse(pilote.arreter_de_force())
        with self.assertRaises(maj.Refus) as contexte:
            pilote.demarrer()
        self.assertEqual(contexte.exception.code, "TACHE_ABSENTE")


class DroitsWindows(unittest.TestCase):
    """L'analyse du SDDL que icacls /save écrit : pure, donc jouée partout."""

    def test_table(self):
        cas = (
            ("D:PAI(A;OICI;FA;;;BA)(A;OICI;FA;;;SY)", True),
            ("D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)", True),
            ("dossier\nD:PAI(A;OICI;FA;;;BA)(A;OICI;FA;;;SY)\n", True),
            ("D:AI(A;OICI;FA;;;BA)(A;OICI;FA;;;SY)", False),
            ("D:PAI(A;OICI;FA;;;BA)", False),
            ("D:PAI(A;OICI;FA;;;SY)", False),
            ("D:PAI(A;OICI;FA;;;BA)(A;OICI;FA;;;SY)(A;OICI;0x1200a9;;;BU)", False),
            ("D:PAI(A;OICI;FA;;;BA)(A;OICI;FA;;;SY)(A;OICI;FA;;;S-1-5-21-1-2-3-1001)", False),
            ("D:PAI(D;OICI;FA;;;BA)(A;OICI;FA;;;SY)", False),
            ("D:PAI(A;OICI;FA;;;BA)(A;OICI;FA;;;SY)(A;OICI;FA;;;WD)", False),
            ("", False),
        )
        for texte, attendu in cas:
            with self.subTest(texte=texte):
                self.assertEqual(maj.sddl_est_protege(texte)[0], attendu)


# ==============================================================================
# A18, A19 — gardes statiques sur maj.py (avec leur mise en échec)
# ==============================================================================

def lire_source():
    with open(SOURCE_MAJ, encoding="utf-8") as f:
        return f.read()


def imports_hors_module(source):
    """Les imports qui ne sont pas au niveau du module (dans une fonction, une
    classe ou une lambda)."""
    fautes = []
    for noeud in ast.walk(ast.parse(source)):
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                              ast.Lambda)):
            for interne in ast.walk(noeud):
                if isinstance(interne, (ast.Import, ast.ImportFrom)):
                    fautes.append("import ligne %d dans %s" % (
                        interne.lineno, getattr(noeud, "name", "lambda")))
    return fautes


def appels_interdits(source):
    fautes = []
    for noeud in ast.walk(ast.parse(source)):
        if isinstance(noeud, ast.Call):
            fonction = noeud.func
            nom = fonction.attr if isinstance(fonction, ast.Attribute) else getattr(fonction, "id", None)
            if nom in ("extract", "extractall"):
                fautes.append("appel à %s (ligne %d)" % (nom, noeud.lineno))
            for mot in noeud.keywords:
                if mot.arg == "shell":
                    fautes.append("shell= (ligne %d)" % noeud.lineno)
        if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
            for interdit in ("Expand-Archive", "7z"):
                if interdit in noeud.value:
                    fautes.append("chaîne %r (ligne %d)" % (interdit, noeud.lineno))
    return fautes


def fautes_de_trace(source):
    """Tout appel à journaliser_technique doit recevoir en 2e argument un appel à
    detail_maj, et rien dans detail_maj(...) ne doit être un texte d'erreur formaté."""
    fautes = []
    arbre = ast.parse(source)
    sites = 0
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call):
            continue
        fonction = noeud.func
        nom = fonction.attr if isinstance(fonction, ast.Attribute) else getattr(fonction, "id", None)
        if nom == "journaliser_technique":
            sites += 1
            if (len(noeud.args) != 2 or not isinstance(noeud.args[1], ast.Call)
                    or getattr(noeud.args[1].func, "id", None) != "detail_maj"):
                fautes.append("journaliser_technique non composé par detail_maj "
                              "(ligne %d)" % noeud.lineno)
        if nom == "detail_maj":
            for argument in list(noeud.args) + [k.value for k in noeud.keywords]:
                for interne in ast.walk(argument):
                    if isinstance(interne, ast.Call) and getattr(interne.func, "id", None) in (
                            "str", "repr", "format"):
                        fautes.append("%s(...) dans detail_maj (ligne %d)" % (
                            interne.func.id, noeud.lineno))
                    if isinstance(interne, (ast.JoinedStr, ast.BinOp)):
                        fautes.append("texte composé dans detail_maj (ligne %d)" % noeud.lineno)
                    if isinstance(interne, ast.Attribute) and interne.attr in ("detail", "args"):
                        fautes.append("détail d'erreur dans detail_maj (ligne %d)" % noeud.lineno)
    if sites == 0:
        fautes.append("aucun appel à journaliser_technique trouvé : garde à vide")
    return fautes


def evenements_non_declares(source):
    """Les événements passés à tracer() avec un littéral hors du vocabulaire."""
    hors, vus = [], 0
    for noeud in ast.walk(ast.parse(source)):
        if (isinstance(noeud, ast.Call) and getattr(noeud.func, "id", None) == "tracer"
                and noeud.args and isinstance(noeud.args[0], ast.Constant)):
            vus += 1
            if noeud.args[0].value not in serveur.EVENEMENTS_TECHNIQUES:
                hors.append(noeud.args[0].value)
    if vus == 0:
        hors.append("aucun appel à tracer() trouvé : garde à vide")
    return hors


class GardesStatiques(unittest.TestCase):

    def test_maj_py_est_soumis_a_la_garde_stdlib(self):
        # La garde de tests/test_serveur.py couvre TOUS les serveur/*.py sauf
        # generer_autorite.py : maj.py y est soumis d'office, mais seulement
        # si le fichier existe et n'importe rien d'extérieur.
        standard = getattr(sys, "stdlib_module_names", None)
        if standard is None:
            self.skipTest("sys.stdlib_module_names absent avant Python 3.10")
        from test_serveur import imports_hors_bibliotheque_standard
        voisins = {os.path.splitext(n)[0] for n in os.listdir(os.path.dirname(SOURCE_MAJ))
                   if n.endswith(".py")}
        self.assertIn("maj", voisins)
        self.assertEqual(
            imports_hors_bibliotheque_standard(lire_source(), standard, voisins), [])

    def test_aucun_import_hors_du_niveau_module(self):
        self.assertEqual(imports_hors_module(lire_source()), [])

    def test_modules_voisins_importes_au_niveau_du_module(self):
        modules = set()
        for noeud in ast.parse(lire_source()).body:
            if isinstance(noeud, ast.Import):
                modules.update(a.name for a in noeud.names)
        for nom in ("paquet_signe", "serveur", "signature_ed25519"):
            self.assertIn(nom, modules)

    def test_la_garde_des_imports_mord(self):
        source = lire_source()
        ancre = "def effacer_pycache(racine):\n"
        self.assertEqual(source.count(ancre), 1)
        for ligne in ("    import paquet_signe\n", "    from serveur import journaliser\n"):
            with self.subTest(ligne=ligne):
                self.assertTrue(imports_hors_module(source.replace(ancre, ancre + ligne)))
        self.assertTrue(imports_hors_module("class A:\n    def f(self):\n        import os\n"))
        self.assertTrue(imports_hors_module("x = lambda: __import__('os')\nf = lambda: 1\n"
                                            "def g():\n    import os\n"))

    def test_ni_extract_ni_shell_ni_outil_d_extraction(self):
        self.assertEqual(appels_interdits(lire_source()), [])

    def test_la_garde_des_appels_mord(self):
        for source in ("archive.extractall(d)\n", "a.extract(n)\n",
                       "subprocess.run(c, shell=True)\n", "x = 'Expand-Archive -Path'\n",
                       "x = ['7z', 'x']\n"):
            with self.subTest(source=source):
                self.assertTrue(appels_interdits(source))

    def test_technique_log_ne_recoit_que_detail_maj(self):
        self.assertEqual(fautes_de_trace(lire_source()), [])
        self.assertEqual(evenements_non_declares(lire_source()), [])

    def test_la_garde_des_traces_mord(self):
        source = lire_source()
        ancre = "    serveur.journaliser_technique(evenement, detail_maj(**champs))\n"
        self.assertEqual(source.count(ancre), 1)
        for remplacement in (
                "    serveur.journaliser_technique(evenement, str(libre))\n",
                "    serveur.journaliser_technique(evenement, '%s' % libre)\n",
                "    serveur.journaliser_technique(evenement, 'x {}'.format(libre))\n",
                "    serveur.journaliser_technique(evenement)\n"):
            with self.subTest(remplacement=remplacement):
                self.assertTrue(fautes_de_trace(source.replace(ancre, remplacement)))
        self.assertTrue(fautes_de_trace("detail_maj(code=str(erreur))\n"
                                        "serveur.journaliser_technique(e, detail_maj())\n"))
        self.assertTrue(fautes_de_trace("detail_maj(code=erreur.detail)\n"
                                        "serveur.journaliser_technique(e, detail_maj())\n"))
        self.assertTrue(evenements_non_declares("tracer('MAJ_INVENTEE', code=1)\n"))

    def test_aucun_assert_nu(self):
        # Sous python -O un assert disparaît : une garde qui s'y appuie ne garde plus rien.
        self.assertEqual(
            [n.lineno for n in ast.walk(ast.parse(lire_source())) if isinstance(n, ast.Assert)], [])
        self.assertIsNone(re.search(r"^\s*assert ", lire_source(), re.MULTILINE))

    def test_aucun_acces_reseau_en_t2a(self):
        # Le téléchargement est C5-T2b : ici, seule la sonde de santé locale parle
        # sur un socket, vers 127.0.0.1.
        source = lire_source()
        self.assertNotIn("urllib", source)
        for noeud in ast.walk(ast.parse(source)):
            if isinstance(noeud, ast.Call) and getattr(noeud.func, "attr", None) in (
                    "HTTPSConnection", "HTTPConnection"):
                self.assertEqual(noeud.args[0].value, "127.0.0.1")
            if isinstance(noeud, ast.Call) and getattr(noeud.func, "attr", None) == "create_connection":
                self.assertEqual(noeud.args[0].elts[0].value, "127.0.0.1")


class ExtractionSansExtract(Installation):
    """Aucune entrée ne s'écrit ailleurs que sous prepare/, quel que soit son nom."""

    def test_extraction_ecrit_uniquement_sous_prepare(self):
        archive = self.trio(modifs={"docs/a/b/c/d.md": b"profond"})
        with maj.contexte_serveur(self.racine):
            maj.preparer_dossier_prive(self.racine)
            plan = maj.controler(self.racine, archive)
            avant = self.arbre()
            maj.extraire(plan)
        self.assertEqual(self.arbre(), avant)
        prepare = os.path.join(self.racine, "mise-a-jour", "prepare")
        extraits = sorted(os.path.relpath(os.path.join(d, n), prepare).replace(os.sep, "/")
                          for d, _, noms in os.walk(prepare) for n in noms)
        self.assertEqual(extraits, sorted(plan.fichiers))
        self.assertEqual(self.etat()["etape"], "preparee")

    def test_une_entree_dont_le_nom_a_change_est_refusee(self):
        archive = self.trio()
        with maj.contexte_serveur(self.racine):
            maj.preparer_dossier_prive(self.racine)
            plan = maj.controler(self.racine, archive)
            reel = maj.zipfile.ZipFile.getinfo

            def getinfo(zf, nom):
                info = reel(zf, nom)
                info.orig_filename = "autre/" + nom
                return info

            with unittest.mock.patch.object(maj.zipfile.ZipFile, "getinfo", getinfo):
                with self.assertRaises(maj.Refus) as contexte:
                    maj.extraire(plan)
        self.assertEqual(contexte.exception.code, "EXTRACTION_ALTEREE")
        self.assertEqual(os.listdir(os.path.join(self.racine, "mise-a-jour", "prepare")), [])


class Documentation(unittest.TestCase):
    """Les fiches existent et ne citent que des sous-commandes qui existent (A22)."""

    def lire(self, *chemin):
        with open(os.path.join(PROJET, *chemin), encoding="utf-8") as f:
            return f.read()

    def test_fiche_d_exploitation_et_fiche_d_essai_existent(self):
        for chemin in (("docs", "mise-a-jour.md"), ("docs", "essais", "C5-T2-windows.md")):
            with self.subTest(chemin=chemin):
                self.assertGreater(len(self.lire(*chemin)), 1000)

    def test_chaque_sous_commande_citee_figure_dans_l_aide(self):
        aide = io.StringIO()
        with contextlib.redirect_stdout(aide), self.assertRaises(SystemExit):
            maj.main(["--help"], racine=PROJET)
        citees = set()
        for chemin in (("docs", "mise-a-jour.md"), ("docs", "essais", "C5-T2-windows.md")):
            citees.update(re.findall(r"maj\.py (?!--)([a-z-]+)", self.lire(*chemin)))
        self.assertTrue(citees, "aucune commande trouvée : la garde ne garderait rien")
        for commande in sorted(citees):
            with self.subTest(commande=commande):
                self.assertIn(commande, aide.getvalue())
        self.assertTrue(citees >= {"appliquer", "revenir", "reprendre", "etat"})

    def test_la_fiche_de_configuration_ne_dit_plus_qu_une_mise_a_jour_efface_le_logo(self):
        texte = self.lire("docs", "configuration.md")
        self.assertNotIn("efface ce dossier", texte)
        self.assertNotIn("point à traiter", texte)
        self.assertIn("mise_a_jour", texte)
        self.assertIn("ne touche jamais ce dossier", texte)


if __name__ == "__main__":
    unittest.main()
