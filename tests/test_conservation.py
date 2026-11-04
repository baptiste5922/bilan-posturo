"""Tests de la durée de conservation des journaux (C4-T2).

Bibliothèque standard uniquement. L'horloge s'injecte (paramètre
`maintenant`) : aucun test n'attend, aucun ne dépend de la date du jour.
Chaque journal est créé dans un dossier temporaire : ni journal.log ni
technique.log du dépôt, qui sont les données réelles d'un cabinet, ne sont
jamais lus ni touchés.

    python3 -m unittest tests.test_conservation
"""

import ast
import datetime
import inspect
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import unittest.mock

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "serveur"))

import serveur

# Instant de référence unique : tous les âges se calculent à partir de lui.
MAINTENANT = datetime.datetime(2026, 11, 3, 12, 0, 0)
SECONDE = datetime.timedelta(seconds=1)
JOUR = datetime.timedelta(days=1)


def duree_mois(mois):
    """Dérivée de la constante du serveur : jamais « 180 » transcrit."""
    return datetime.timedelta(days=serveur.JOURS_PAR_MOIS * mois)


def seuil_purge(mois=6):
    """Seuil de purge d'une archive : N mois moins un jour (D3 bis)."""
    return duree_mois(mois) - JOUR


def ligne_datee(date, texte="REPONSE methode=GET route=sante code=200"):
    return "{} {}\n".format(date.isoformat(timespec="seconds"), texte)


class BacADossier(unittest.TestCase):
    """Un dossier temporaire par test, et un journal par nom de base."""

    def setUp(self):
        self.dossier = tempfile.mkdtemp(prefix="bilan-conservation-")
        self.addCleanup(shutil.rmtree, self.dossier, ignore_errors=True)
        # Durée explicite, indépendante du défaut : un test qui ne la fixe pas
        # ne doit pas changer de sens si le défaut change.
        patch = unittest.mock.patch.object(
            serveur, "CONSERVATION_JOURNAUX_MOIS", 6)
        patch.start()
        self.addCleanup(patch.stop)

    def chemin(self, nom):
        return os.path.join(self.dossier, nom)

    def ecrire(self, nom, contenu, modification=None):
        chemin = self.chemin(nom)
        with open(chemin, "w", encoding="utf-8", newline="") as f:
            f.write(contenu)
        if modification is not None:
            horodatage = modification.timestamp()
            os.utime(chemin, (horodatage, horodatage))
        return chemin

    def existe(self, nom):
        return os.path.lexists(self.chemin(nom))


# --------------------------------------------------------------------------
# Paramètre de configuration (D5)
# --------------------------------------------------------------------------

class ParametreDeConfiguration(unittest.TestCase):

    def test_defaut_de_six_mois(self):
        self.assertEqual(serveur.CONSERVATION_MOIS_DEFAUT, 6)
        self.assertEqual(
            serveur.CONFIG_DEFAUT["conservation_journaux_mois"], 6)

    def test_valeurs_valides_conservees(self):
        for valeur in (1, 6, 12, serveur.CONSERVATION_MOIS_MAX):
            with self.subTest(valeur=valeur):
                self.assertEqual(
                    serveur.normaliser_conservation_mois(valeur), valeur)

    def test_valeurs_invalides_retombent_sur_le_defaut(self):
        invalides = (
            0, -1, serveur.CONSERVATION_MOIS_MAX + 1, 10 ** 30,
            True, False,            # bool est un int en Python
            6.0, 5.5, "6", "six", "", None, [], [6], {}, {"mois": 6},
            float("nan"), float("inf"),
        )
        for valeur in invalides:
            with self.subTest(valeur=valeur):
                self.assertEqual(
                    serveur.normaliser_conservation_mois(valeur),
                    serveur.CONSERVATION_MOIS_DEFAUT)

    def test_charger_config_normalise_la_valeur_ecrite(self):
        dossier = tempfile.mkdtemp(prefix="bilan-conservation-config-")
        self.addCleanup(shutil.rmtree, dossier, ignore_errors=True)
        chemin = os.path.join(dossier, "config.json")
        cas = [
            ({}, 6),                                       # clé absente
            ({"conservation_journaux_mois": 12}, 12),
            ({"conservation_journaux_mois": 0}, 6),
            ({"conservation_journaux_mois": 121}, 6),
            ({"conservation_journaux_mois": "12"}, 6),
            ({"conservation_journaux_mois": None}, 6),
            ({"conservation_journaux_mois": True}, 6),
            ({"conservation_journaux_mois": 2.5}, 6),
        ]
        for contenu, attendu in cas:
            with self.subTest(contenu=contenu):
                with open(chemin, "w", encoding="utf-8") as f:
                    json.dump(contenu, f)
                with unittest.mock.patch.object(serveur, "CONFIG", chemin):
                    config = serveur.charger_config()
                self.assertEqual(config["conservation_journaux_mois"], attendu)

    def test_la_duree_en_vigueur_se_revalide(self):
        # Un global corrompu (test, ou code futur) ne doit jamais lever
        # dans le chemin d'écriture d'un journal.
        for valeur in ("x", None, -5, True):
            with self.subTest(valeur=valeur):
                with unittest.mock.patch.object(
                        serveur, "CONSERVATION_JOURNAUX_MOIS", valeur):
                    self.assertEqual(serveur.conservation_mois(), 6)

    def test_aucun_assert_nu_dans_le_serveur(self):
        # Piège du dépôt : un `assert` nu s'évapore sous python -O et la
        # garde qu'il portait cesse d'exister sans bruit. Aucun ne doit
        # entrer dans serveur.py (les gardes sont des `if` / `raise`).
        with open(serveur.__file__, encoding="utf-8") as f:
            arbre = ast.parse(f.read())
        nus = [n.lineno for n in ast.walk(arbre) if isinstance(n, ast.Assert)]
        self.assertEqual(nus, [], "assert nu à la ligne(s) {}".format(nus))


class Documentation(unittest.TestCase):
    """Les trois documents disent la durée, et plus « pas en durée »."""

    RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def lire(self, *chemin):
        with open(os.path.join(self.RACINE, *chemin), encoding="utf-8") as f:
            return f.read()

    def test_la_cle_est_documentee_partout(self):
        for chemin in (("README.md",), ("docs", "Mode_emploi.md"),
                       ("docs", "USER-GUIDE.md")):
            with self.subTest(document=chemin[-1]):
                self.assertIn("conservation_journaux_mois", self.lire(*chemin))

    def test_plus_de_pas_en_duree(self):
        for chemin in (("docs", "Mode_emploi.md"), ("docs", "USER-GUIDE.md")):
            texte = self.lire(*chemin)
            with self.subTest(document=chemin[-1]):
                self.assertNotIn("pas en durée", texte)
                self.assertNotIn("not by age", texte)

    def test_les_aide_memoire_du_paquet_disent_six_mois(self):
        # Copiés tels quels dans le paquet (outils/faire-paquet.sh) : ils ne
        # doivent plus annoncer trois générations d'archives.
        self.assertIn("six mois", self.lire("docs", "LISEZMOI.txt"))
        self.assertIn("six months", self.lire("docs", "READ-ME-FIRST.txt"))
        for nom in ("LISEZMOI.txt", "READ-ME-FIRST.txt"):
            with self.subTest(document=nom):
                self.assertNotIn("journal.log.3", self.lire("docs", nom))

    def test_les_reserves_sont_dites(self):
        # Serveur arrêté : rien n'est purgé. Première archive après la mise à
        # jour : elle part en bloc, donc plus tôt qu'un mois d'avance.
        self.assertIn("Serveur arrêté", self.lire("docs", "LISEZMOI.txt"))
        self.assertIn("is stopped", self.lire("docs", "READ-ME-FIRST.txt"))
        self.assertIn("Exception, la première fois",
                      self.lire("docs", "Mode_emploi.md"))
        self.assertIn("Exception, the first time",
                      self.lire("docs", "USER-GUIDE.md"))

    def test_la_duree_documentee_est_celle_du_defaut(self):
        self.assertIn("{} par défaut".format(serveur.CONSERVATION_MOIS_DEFAUT),
                      self.lire("docs", "Mode_emploi.md"))
        self.assertIn("{} by default".format(serveur.CONSERVATION_MOIS_DEFAUT),
                      self.lire("docs", "USER-GUIDE.md"))


# --------------------------------------------------------------------------
# Borne du nombre d'archives (D4)
# --------------------------------------------------------------------------

class BorneDesGenerations(BacADossier):

    def test_sept_generations_avec_six_mois(self):
        self.assertEqual(serveur.generations_maximales(), 7)

    def test_le_compte_ne_borne_pas_la_duree(self):
        for mois, attendu in ((1, 3), (2, 3), (6, 7), (12, 13),
                              (serveur.CONSERVATION_MOIS_MAX, 121)):
            with self.subTest(mois=mois):
                with unittest.mock.patch.object(
                        serveur, "CONSERVATION_JOURNAUX_MOIS", mois):
                    self.assertEqual(serveur.generations_maximales(), attendu)

    def test_sept_archives_coexistent_puis_la_huitieme_est_ecartee(self):
        journal = self.chemin("journal.log")
        with unittest.mock.patch.object(serveur, "JOURNAL_TAILLE_MAX", 100):
            for rang in range(1, 8):
                # Première ligne récente : l'âge ne purge rien, seul le
                # compte peut supprimer.
                self.ecrire("journal.log", ligne_datee(MAINTENANT) + "x" * 100)
                self.assertTrue(
                    serveur.faire_tourner_journal(journal, MAINTENANT))
                for n in range(1, rang + 1):
                    self.assertTrue(self.existe("journal.log.%d" % n),
                                    "journal.log.%d manque après %d rotations"
                                    % (n, rang))
            self.assertFalse(self.existe("journal.log.8"))

            self.ecrire("journal.log", ligne_datee(MAINTENANT) + "x" * 100)
            serveur.faire_tourner_journal(journal, MAINTENANT)
            self.assertTrue(self.existe("journal.log.7"))
            self.assertFalse(self.existe("journal.log.8"))


# --------------------------------------------------------------------------
# Rotation mensuelle (D2)
# --------------------------------------------------------------------------

class RotationMensuelle(BacADossier):

    def verifier_bascule(self, nom):
        """Un journal dont la première ligne a exactement un mois reste ;
        une seconde de plus, il est archivé. Sous 5 Mo dans les deux cas."""
        chemin = self.chemin(nom)
        un_mois = duree_mois(1)

        self.ecrire(nom, ligne_datee(MAINTENANT - un_mois))
        self.assertFalse(serveur.faire_tourner_journal(chemin, MAINTENANT))
        self.assertTrue(self.existe(nom))
        self.assertFalse(self.existe(nom + ".1"))

        self.ecrire(nom, ligne_datee(MAINTENANT - un_mois - SECONDE))
        self.assertLess(os.path.getsize(chemin), serveur.JOURNAL_TAILLE_MAX)
        self.assertTrue(serveur.faire_tourner_journal(chemin, MAINTENANT))
        self.assertFalse(self.existe(nom))
        self.assertTrue(self.existe(nom + ".1"))

    def test_bascule_a_un_mois_journal(self):
        self.verifier_bascule("journal.log")

    def test_bascule_a_un_mois_technique(self):
        self.verifier_bascule("technique.log")

    def test_la_premiere_ligne_decide_pas_la_derniere(self):
        # Ancienne en tête, récente en queue : c'est la tête qui compte,
        # sans quoi un journal actif ne tournerait jamais.
        contenu = (ligne_datee(MAINTENANT - duree_mois(2))
                   + ligne_datee(MAINTENANT - SECONDE))
        self.ecrire("journal.log", contenu)
        self.assertTrue(serveur.faire_tourner_journal(
            self.chemin("journal.log"), MAINTENANT))

    def test_journal_vide_ne_tourne_pas(self):
        # Rien à archiver, même avec une date de modification ancienne.
        self.ecrire("journal.log", "", MAINTENANT - duree_mois(3))
        self.assertFalse(serveur.faire_tourner_journal(
            self.chemin("journal.log"), MAINTENANT))
        self.assertTrue(self.existe("journal.log"))

    def test_horodatage_illisible_se_replie_sur_la_modification(self):
        chemin = self.chemin("journal.log")
        self.ecrire("journal.log", "n'importe quoi\n",
                    MAINTENANT - duree_mois(1) - SECONDE)
        self.assertTrue(serveur.faire_tourner_journal(chemin, MAINTENANT))

        self.ecrire("journal.log", "n'importe quoi\n", MAINTENANT)
        self.assertFalse(serveur.faire_tourner_journal(chemin, MAINTENANT))

    def test_seuil_de_taille_inchange(self):
        # La rotation par taille subsiste : première ligne toute fraîche,
        # mais au plafond.
        chemin = self.chemin("journal.log")
        with unittest.mock.patch.object(serveur, "JOURNAL_TAILLE_MAX", 100):
            self.ecrire("journal.log", ligne_datee(MAINTENANT) + "x" * 100)
            self.assertTrue(serveur.faire_tourner_journal(chemin, MAINTENANT))
            self.ecrire("journal.log", ligne_datee(MAINTENANT))
            self.assertFalse(serveur.faire_tourner_journal(chemin, MAINTENANT))

    def test_prochaine_ecriture_du_journal_nominatif(self):
        # Bout en bout, horloge réelle : une première ligne vieille de deux
        # mois, très en dessous de 5 Mo.
        ancien = datetime.datetime.now() - duree_mois(2)
        self.ecrire("journal.log", ligne_datee(ancien, "ancienne"))
        with unittest.mock.patch.object(
                serveur, "JOURNAL", self.chemin("journal.log")), \
                unittest.mock.patch.object(serveur, "ecrire_stderr"):
            serveur.journaliser("2026-11-03T12:00:01 neuve\n")
        self.assertIn("ancienne", self.lire("journal.log.1"))
        self.assertEqual(self.lire("journal.log"),
                         "2026-11-03T12:00:01 neuve\n")

    def test_prochaine_ecriture_du_journal_technique(self):
        ancien = datetime.datetime.now() - duree_mois(2)
        self.ecrire("technique.log", ligne_datee(ancien, "DEPOT ok 1 octets"))
        resultat = []

        def ecrire():
            with unittest.mock.patch.object(
                    serveur, "TECHNIQUE", self.chemin("technique.log")), \
                    unittest.mock.patch.object(
                        serveur, "JOURNAL_TECHNIQUE_ACTIF", True):
                serveur.journaliser_technique("DEPOT", "ok 2 octets")
            resultat.append(True)

        # Un fil avec échéance : un interblocage (verrou non réentrant)
        # serait un échec, pas un test qui se fige.
        fil = threading.Thread(target=ecrire, daemon=True)
        fil.start()
        fil.join(10)
        self.assertFalse(fil.is_alive(), "interblocage du verrou du journal")
        self.assertEqual(resultat, [True])

        self.assertIn("DEPOT ok 1 octets", self.lire("technique.log.1"))
        courant = self.lire("technique.log").splitlines()
        self.assertEqual(len(courant), 2)
        self.assertIn(serveur.EVENEMENT_ROTATION, courant[0])
        self.assertIn("DEPOT ok 2 octets", courant[1])
        for ligne in courant:       # forme inchangée : horodatage ISO en tête
            self.assertRegex(ligne, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2} ")

    def lire(self, nom):
        with open(self.chemin(nom), encoding="utf-8") as f:
            return f.read()


# --------------------------------------------------------------------------
# Purge (D3)
# --------------------------------------------------------------------------

class PurgeDesArchives(BacADossier):

    def verifier_bascule_purge(self, nom, purge):
        """Juste avant et juste après N mois, première ligne d'une archive.
        `purge` est la voie testée (directe, rotation ou démarrage)."""
        limite = seuil_purge(6)

        self.ecrire(nom + ".1", ligne_datee(MAINTENANT - limite))
        purge()
        self.assertTrue(self.existe(nom + ".1"),
                        "supprimée au seuil exact (N mois moins un jour)")

        self.ecrire(nom + ".1", ligne_datee(MAINTENANT - limite - SECONDE))
        purge()
        self.assertFalse(self.existe(nom + ".1"),
                         "survit au-delà de N mois")

        self.ecrire(nom + ".1", ligne_datee(MAINTENANT - limite + SECONDE))
        purge()
        self.assertTrue(self.existe(nom + ".1"))

    def test_bascule_purge_directe_pour_les_deux_journaux(self):
        for nom in ("journal.log", "technique.log"):
            with self.subTest(journal=nom):
                chemin = self.chemin(nom)
                self.verifier_bascule_purge(
                    nom, lambda: serveur.purger_archives(chemin, MAINTENANT))

    def test_bascule_purge_a_chaque_rotation_pour_les_deux_journaux(self):
        for nom in ("journal.log", "technique.log"):
            with self.subTest(journal=nom):
                self.verifier_bascule_purge_rotation(nom)

    def verifier_bascule_purge_rotation(self, nom):
        """Comme verifier_bascule_purge, mais la purge est celle qui suit une
        rotation réelle. L'archive d'essai est posée au rang 1 ; la rotation,
        déclenchée par la taille, la décale au rang 2 puis la juge."""
        chemin = self.chemin(nom)
        limite = seuil_purge(6)
        cas = ((datetime.timedelta(0), True),     # au seuil exact : reste
               (SECONDE, False),                  # une seconde de plus : part
               (-SECONDE, True))                  # une seconde de moins : reste
        with unittest.mock.patch.object(serveur, "JOURNAL_TAILLE_MAX", 100):
            for depassement, doit_survivre in cas:
                for entree in os.listdir(self.dossier):
                    os.remove(self.chemin(entree))
                self.ecrire(nom + ".1",
                            ligne_datee(MAINTENANT - limite - depassement))
                self.ecrire(nom, ligne_datee(MAINTENANT) + "x" * 100)
                self.assertTrue(
                    serveur.faire_tourner_journal(chemin, MAINTENANT))
                self.assertTrue(self.existe(nom + ".1"))   # le courant archivé
                self.assertEqual(
                    self.existe(nom + ".2"), doit_survivre,
                    "dépassement de {} : survie attendue {}".format(
                        depassement, doit_survivre))

    def test_purge_au_demarrage_pour_les_deux_journaux(self):
        journal = self.chemin("journal.log")
        technique = self.chemin("technique.log")
        # purger_au_demarrage() lit l'horloge réelle : les archives se datent
        # donc par rapport à elle, pas à MAINTENANT.
        reel = datetime.datetime.now()
        for nom in ("journal.log", "technique.log"):
            self.ecrire(nom + ".1", ligne_datee(reel - duree_mois(7)))
            self.ecrire(nom + ".2", ligne_datee(reel - duree_mois(5)))
        with unittest.mock.patch.object(serveur, "JOURNAL", journal), \
                unittest.mock.patch.object(serveur, "TECHNIQUE", technique):
            serveur.purger_au_demarrage()
        for nom in ("journal.log", "technique.log"):
            self.assertFalse(self.existe(nom + ".1"), nom)
            self.assertTrue(self.existe(nom + ".2"), nom)

    def test_un_mois_vaut_trente_jours(self):
        # Décision D5 : la seule constante écrite en dur, donc la seule qui
        # ne se dérive pas du code. Les autres tests s'en servent ; celui-ci
        # l'épingle en jours littéraux, pour qu'un changement de la
        # constante ne passe pas inaperçu.
        self.assertEqual(serveur.JOURS_PAR_MOIS, 30)
        jour = datetime.timedelta(days=1)

        self.ecrire("journal.log", ligne_datee(MAINTENANT - 30 * jour))
        self.assertFalse(serveur.faire_tourner_journal(
            self.chemin("journal.log"), MAINTENANT))
        self.ecrire("journal.log", ligne_datee(MAINTENANT - 31 * jour))
        self.assertTrue(serveur.faire_tourner_journal(
            self.chemin("journal.log"), MAINTENANT))

        # Seuil de purge : 180 jours moins un jour (D3 bis).
        self.ecrire("technique.log.1", ligne_datee(MAINTENANT - 179 * jour))
        serveur.purger_archives(self.chemin("technique.log"), MAINTENANT)
        self.assertTrue(self.existe("technique.log.1"))
        self.ecrire("technique.log.1",
                    ligne_datee(MAINTENANT - 179 * jour - SECONDE))
        serveur.purger_archives(self.chemin("technique.log"), MAINTENANT)
        self.assertFalse(self.existe("technique.log.1"))

    def test_journal_courant_jamais_supprime_par_la_purge(self):
        self.ecrire("journal.log", ligne_datee(MAINTENANT - duree_mois(40)))
        serveur.purger_archives(self.chemin("journal.log"), MAINTENANT)
        self.assertTrue(self.existe("journal.log"))

    def test_courant_oublie_depuis_plus_de_n_mois(self):
        # Rotation puis purge dans le même passage : aucune ligne de plus de
        # N mois ne survit à l'écriture qui la découvre.
        self.ecrire("journal.log", ligne_datee(MAINTENANT - duree_mois(7)))
        self.assertTrue(serveur.faire_tourner_journal(
            self.chemin("journal.log"), MAINTENANT))
        self.assertFalse(self.existe("journal.log"))
        self.assertFalse(self.existe("journal.log.1"))

    def test_n_depend_du_parametre(self):
        archive = ligne_datee(MAINTENANT - duree_mois(2))
        # 60 jours : au-delà du seuil de 1 mois (29 j) et de 2 mois (59 j),
        # en deçà de celui de 3 mois (89 j).
        for mois, survit in ((1, False), (2, False), (3, True)):
            with self.subTest(mois=mois):
                self.ecrire("journal.log.1", archive)
                with unittest.mock.patch.object(
                        serveur, "CONSERVATION_JOURNAUX_MOIS", mois):
                    serveur.purger_archives(
                        self.chemin("journal.log"), MAINTENANT)
                self.assertEqual(self.existe("journal.log.1"), survit)

    def test_chaque_archive_est_jugee_sur_sa_propre_premiere_ligne(self):
        limite = duree_mois(6)
        for rang, jours in ((1, 1), (2, 10), (3, 200), (4, 400)):
            self.ecrire("journal.log.%d" % rang,
                        ligne_datee(MAINTENANT - datetime.timedelta(days=jours)))
        self.assertEqual(
            serveur.purger_archives(self.chemin("journal.log"), MAINTENANT), 2)
        self.assertEqual(
            [self.existe("journal.log.%d" % r) for r in (1, 2, 3, 4)],
            [True, True, False, False])
        self.assertLess(datetime.timedelta(days=10), limite)

    def test_la_purge_d_un_journal_ne_touche_pas_l_autre(self):
        ancien = ligne_datee(MAINTENANT - duree_mois(12))
        self.ecrire("journal.log.1", ancien)
        self.ecrire("technique.log.1", ancien)
        serveur.purger_archives(self.chemin("journal.log"), MAINTENANT)
        self.assertFalse(self.existe("journal.log.1"))
        self.assertTrue(self.existe("technique.log.1"))


# --------------------------------------------------------------------------
# Purge à l'écriture, une fois par jour (D3 bis)
# --------------------------------------------------------------------------

class PurgeALEcriture(BacADossier):

    def test_une_archive_perimee_part_sans_rotation(self):
        chemin = self.chemin("journal.log")
        self.ecrire("journal.log", ligne_datee(MAINTENANT))
        self.ecrire("journal.log.1", ligne_datee(MAINTENANT - duree_mois(7)))
        self.assertFalse(serveur.faire_tourner_journal(chemin, MAINTENANT))
        self.assertFalse(self.existe("journal.log.1"))
        self.assertTrue(self.existe("journal.log"))

    def test_au_plus_une_purge_par_jour_et_par_journal(self):
        chemin = self.chemin("journal.log")
        self.ecrire("journal.log", ligne_datee(MAINTENANT))
        serveur.faire_tourner_journal(chemin, MAINTENANT)       # purge

        ancien = ligne_datee(MAINTENANT - duree_mois(7))
        self.ecrire("journal.log.1", ancien)
        presque = MAINTENANT + JOUR - SECONDE
        serveur.faire_tourner_journal(chemin, presque)
        self.assertTrue(self.existe("journal.log.1"),
                        "purge refaite moins d'un jour après la précédente")

        serveur.faire_tourner_journal(chemin, MAINTENANT + JOUR)
        self.assertFalse(self.existe("journal.log.1"))

    def test_chaque_journal_a_sa_propre_echeance(self):
        self.ecrire("journal.log", ligne_datee(MAINTENANT))
        self.ecrire("technique.log", ligne_datee(MAINTENANT))
        serveur.faire_tourner_journal(self.chemin("journal.log"), MAINTENANT)
        self.ecrire("technique.log.1", ligne_datee(MAINTENANT - duree_mois(7)))
        # Le journal nominatif vient d'être purgé, pas le technique.
        serveur.faire_tourner_journal(self.chemin("technique.log"), MAINTENANT)
        self.assertFalse(self.existe("technique.log.1"))

    def test_horloge_reculee_compte_comme_due(self):
        chemin = self.chemin("journal.log")
        self.ecrire("journal.log", ligne_datee(MAINTENANT))
        serveur.faire_tourner_journal(chemin, MAINTENANT)
        self.ecrire("journal.log.1", ligne_datee(MAINTENANT - duree_mois(7)))
        serveur.faire_tourner_journal(chemin, MAINTENANT - 3 * JOUR)
        self.assertFalse(self.existe("journal.log.1"))

    def test_journal_courant_absent_les_archives_sont_quand_meme_jugees(self):
        self.ecrire("journal.log.1", ligne_datee(MAINTENANT - duree_mois(7)))
        self.assertFalse(serveur.faire_tourner_journal(
            self.chemin("journal.log"), MAINTENANT))
        self.assertFalse(self.existe("journal.log.1"))

    def test_ecriture_reelle_des_deux_journaux(self):
        reel = datetime.datetime.now()
        self.ecrire("journal.log", ligne_datee(reel))
        self.ecrire("technique.log", ligne_datee(reel))
        for nom in ("journal.log.1", "technique.log.1"):
            self.ecrire(nom, ligne_datee(reel - duree_mois(7)))
        resultat = []

        def ecrire():
            with unittest.mock.patch.object(
                    serveur, "JOURNAL", self.chemin("journal.log")), \
                    unittest.mock.patch.object(
                        serveur, "TECHNIQUE", self.chemin("technique.log")), \
                    unittest.mock.patch.object(serveur, "ecrire_stderr"), \
                    unittest.mock.patch.object(
                        serveur, "JOURNAL_TECHNIQUE_ACTIF", True):
                serveur.journaliser(ligne_datee(reel))
                serveur.journaliser_technique("DEPOT", "ok 1 octets")
            resultat.append(True)

        fil = threading.Thread(target=ecrire, daemon=True)
        fil.start()
        fil.join(10)
        self.assertEqual(resultat, [True], "interblocage du verrou du journal")
        self.assertFalse(self.existe("journal.log.1"))
        self.assertFalse(self.existe("technique.log.1"))

    def mesurer(self, ecart, jours=900):
        """Simule `jours` jours d'écritures espacées de `ecart` : à chaque
        écriture, appelle faire_tourner_journal() puis ajoute une ligne, et
        rend l'âge de la plus vieille ligne présente (journal et archives)
        relevé à chaque écriture, juste après la purge."""
        chemin = self.chemin("journal.log")
        t = datetime.datetime(2024, 1, 1, 8, 0, 0)
        fin = t + datetime.timedelta(days=jours)
        pire = datetime.timedelta(0)
        while t < fin:
            serveur.faire_tourner_journal(chemin, t)
            with open(chemin, "a", encoding="utf-8") as f:
                f.write(ligne_datee(t))
            for rang in range(0, serveur.generations_maximales() + 1):
                fichier = chemin if rang == 0 else "{}.{}".format(chemin, rang)
                if os.path.exists(fichier):
                    with open(fichier, encoding="utf-8") as f:
                        premiere = datetime.datetime.fromisoformat(
                            f.readline().split()[0])
                    pire = max(pire, t - premiere)
            t += ecart
        return pire

    def test_aucune_ligne_ne_depasse_n_mois(self):
        # D1, tenue : écritures toutes les 12 h, quotidiennes, hebdomadaires.
        # Sans la purge à l'écriture, la même simulation donne 182 j 12 h,
        # 185 j et 203 j.
        for heures in (12, 24, 7 * 24):
            with self.subTest(heures=heures):
                for entree in os.listdir(self.dossier):
                    os.remove(self.chemin(entree))
                pire = self.mesurer(datetime.timedelta(hours=heures))
                self.assertLessEqual(pire, duree_mois(6))


# --------------------------------------------------------------------------
# Fil de purge périodique
# --------------------------------------------------------------------------

class EvenementSimule:
    """Remplace threading.Event : wait() ne dort jamais. `tours` fait
    rendre False aux `tours` premiers appels (la boucle tourne), puis True
    (l'événement est « levé »). `avant` est appelé à chaque attente, avec la
    durée demandée ; s'il rend True, la boucle s'arrête."""

    def __init__(self, tours=0, avant=None):
        self.tours = tours
        self.avant = avant
        self.attentes = []

    def is_set(self):
        return False

    def wait(self, delai=None):
        self.attentes.append(delai)
        if self.avant is not None:
            return bool(self.avant(delai))
        if len(self.attentes) > self.tours:
            return True
        return False


class FilDePurgePeriodique(BacADossier):

    def test_la_boucle_purge_a_chaque_tour_et_s_arrete_sur_l_evenement(self):
        arret = EvenementSimule(tours=3)
        with unittest.mock.patch.object(
                serveur, "entretenir_journaux") as entretien:
            serveur.boucle_purge_periodique(arret, attente=123)
        self.assertEqual(entretien.call_count, 3)
        # Une attente par tour plus celle qui rend True : l'attente injectée
        # est bien celle qui est demandée.
        self.assertEqual(arret.attentes, [123, 123, 123, 123])

    def test_un_evenement_deja_leve_n_entretient_rien(self):
        class Garde(BaseException):
            """Échappe à `except Exception` de la boucle : une boucle qui
            tournerait malgré l'événement lève ici au lieu de tourner sans
            fin."""

        arret = threading.Event()
        arret.set()
        with unittest.mock.patch.object(
                serveur, "entretenir_journaux", side_effect=Garde) as entretien:
            serveur.boucle_purge_periodique(arret, attente=3600)
        entretien.assert_not_called()

    def test_une_exception_n_arrete_pas_la_boucle(self):
        arret = EvenementSimule(tours=4)
        with unittest.mock.patch.object(
                serveur, "entretenir_journaux",
                side_effect=[OSError("disque"), RuntimeError("x"),
                             ValueError("y"), None]) as entretien:
            serveur.boucle_purge_periodique(arret, attente=1)
        self.assertEqual(entretien.call_count, 4)

    def test_une_horloge_defaillante_n_arrete_pas_la_boucle(self):
        arret = EvenementSimule(tours=2)

        def horloge():
            raise RuntimeError("horloge")
        with unittest.mock.patch.object(
                serveur, "entretenir_journaux") as entretien:
            serveur.boucle_purge_periodique(arret, attente=1, horloge=horloge)
        entretien.assert_not_called()
        self.assertEqual(len(arret.attentes), 3)

    def test_l_horloge_injectee_arrive_jusqu_a_l_entretien(self):
        arret = EvenementSimule(tours=1)
        with unittest.mock.patch.object(
                serveur, "entretenir_journaux") as entretien:
            serveur.boucle_purge_periodique(
                arret, attente=1, horloge=lambda: MAINTENANT)
        entretien.assert_called_once_with(MAINTENANT)

    def test_le_fil_est_un_demon_et_s_arrete_sur_l_evenement(self):
        lancee = threading.Event()

        def boucle(arret, *args, **kwargs):
            lancee.set()
            arret.wait()           # bloque jusqu'à arret.set(), sans délai

        with unittest.mock.patch.object(
                serveur, "boucle_purge_periodique", boucle):
            fil, arret = serveur.demarrer_purge_periodique()
        # Même si une assertion échoue, le fil doit pouvoir finir : un fil
        # non démon figerait la sortie de la suite entière.
        self.addCleanup(arret.set)
        self.assertTrue(lancee.wait(10))
        self.assertTrue(fil.daemon)
        self.assertTrue(fil.is_alive())
        arret.set()
        fil.join(10)
        self.assertFalse(fil.is_alive())

    def test_demarrer_lance_le_fil_apres_la_purge_de_demarrage(self):
        # Le démarrage complet exige un certificat et un port : on lit donc
        # l'arbre syntaxique de demarrer(), comme pour les garde-fous de
        # source du dépôt. L'ordre compte : purge, puis fil, puis premier
        # événement du journal technique.
        with open(serveur.__file__, encoding="utf-8") as f:
            arbre = ast.parse(f.read())
        demarrer = next(n for n in ast.walk(arbre)
                        if isinstance(n, ast.FunctionDef) and n.name == "demarrer")
        lignes = {}
        for noeud in ast.walk(demarrer):
            if isinstance(noeud, ast.Call):
                f = noeud.func
                nom = f.id if isinstance(f, ast.Name) else getattr(f, "attr", "")
                lignes.setdefault(nom, noeud.lineno)
        self.assertIn("demarrer_purge_periodique", lignes)
        self.assertLess(lignes["purger_au_demarrage"],
                        lignes["demarrer_purge_periodique"])
        self.assertLess(lignes["demarrer_purge_periodique"],
                        lignes["journaliser_technique"])

    def test_l_intervalle_tient_dans_l_avance_d_un_jour(self):
        self.assertEqual(serveur.PURGE_PERIODIQUE_SECONDES, 6 * 3600)
        self.assertLessEqual(
            datetime.timedelta(seconds=serveur.PURGE_PERIODIQUE_SECONDES),
            serveur.PURGE_INTERVALLE)

    def test_l_entretien_range_un_journal_courant_oublie(self):
        # Aucune écriture : seul le fil peut archiver puis purger.
        self.ecrire("journal.log", ligne_datee(MAINTENANT - duree_mois(7)))
        self.ecrire("technique.log", ligne_datee(MAINTENANT - duree_mois(2)))
        self.ecrire("technique.log.1", ligne_datee(MAINTENANT - duree_mois(7)))
        with unittest.mock.patch.object(
                serveur, "JOURNAL", self.chemin("journal.log")), \
                unittest.mock.patch.object(
                    serveur, "TECHNIQUE", self.chemin("technique.log")):
            serveur.entretenir_journaux(MAINTENANT)
        self.assertFalse(self.existe("journal.log"))
        self.assertFalse(self.existe("journal.log.1"))
        # Le technique, vieux de deux mois, est archivé mais pas purgé ; la
        # vieille archive, elle, est purgée.
        self.assertFalse(self.existe("technique.log"))
        self.assertTrue(self.existe("technique.log.1"))
        with open(self.chemin("technique.log.1"), encoding="utf-8") as f:
            self.assertIn(
                (MAINTENANT - duree_mois(2)).isoformat(timespec="seconds"),
                f.read())

    def test_l_entretien_tient_le_verrou_du_journal(self):
        # Le fil concurrence les écritures des requêtes : sans le verrou,
        # il pourrait renommer un journal pendant qu'on y écrit.
        etats = []

        def observer(*args, **kwargs):
            etats.append(serveur._verrou_journal.locked())
            return 0

        with unittest.mock.patch.object(serveur, "purger_archives", observer), \
                unittest.mock.patch.object(
                    serveur, "faire_tourner_journal", observer):
            serveur.entretenir_journaux(MAINTENANT)
        self.assertEqual(len(etats), 4)
        self.assertTrue(all(etats))
        self.assertFalse(serveur._verrou_journal.locked())

    def test_l_entretien_ne_journalise_pas_et_ne_bloque_pas(self):
        self.ecrire("journal.log", ligne_datee(MAINTENANT - duree_mois(2)))
        fini = []

        def entretenir():
            with unittest.mock.patch.object(
                    serveur, "JOURNAL", self.chemin("journal.log")), \
                    unittest.mock.patch.object(
                        serveur, "TECHNIQUE", self.chemin("technique.log")), \
                    unittest.mock.patch.object(serveur, "journaliser") as j, \
                    unittest.mock.patch.object(
                        serveur, "journaliser_technique") as t, \
                    unittest.mock.patch.object(serveur, "ecrire_stderr") as e:
                serveur.entretenir_journaux(MAINTENANT)
                j.assert_not_called()
                t.assert_not_called()
                e.assert_not_called()
            fini.append(True)

        fil = threading.Thread(target=entretenir, daemon=True)
        fil.start()
        fil.join(10)
        self.assertEqual(fini, [True], "interblocage ou échec de l'entretien")
        self.assertTrue(self.existe("journal.log.1"))
        for fonction in (serveur.entretenir_journaux,
                         serveur.boucle_purge_periodique,
                         serveur.demarrer_purge_periodique):
            with self.subTest(fonction=fonction.__name__):
                self.assertEqual(
                    LaPurgeResteDansLesArchives.identifiants(fonction)
                    & {"journaliser", "journaliser_technique",
                       "ecrire_stderr", "_ajouter_ligne_technique",
                       "glob", "listdir", "scandir", "walk", "rmtree"},
                    set())

    def simuler(self, ecart, jours=450):
        """Simule `jours` jours avec la vraie boucle de purge, une horloge
        virtuelle et un événement qui n'attend jamais : à chaque attente de
        la boucle, l'horloge avance de PURGE_PERIODIQUE_SECONDES et les
        écritures prévues dans l'intervalle ont lieu (`ecart` est leur
        espacement ; None : une seule écriture, au début).

        Rend l'âge maximal d'une ligne présente à TOUT instant. L'âge ne
        fait que croître entre deux événements : le maximum se lit donc
        juste avant chaque événement (écriture ou tour de purge).
        """
        chemin = self.chemin("journal.log")
        debut = datetime.datetime(2024, 1, 1, 8, 0, 0)
        fin = debut + datetime.timedelta(days=jours)
        etat = {"t": debut, "ecriture": debut, "pire": datetime.timedelta(0)}

        def releve():
            for rang in range(0, serveur.CONSERVATION_MOIS_MAX + 2):
                fichier = chemin if rang == 0 else "{}.{}".format(chemin, rang)
                if os.path.exists(fichier):
                    with open(fichier, encoding="utf-8") as f:
                        premiere = datetime.datetime.fromisoformat(
                            f.readline().split()[0])
                    etat["pire"] = max(etat["pire"], etat["t"] - premiere)

        def ecrire():
            releve()
            serveur.faire_tourner_journal(chemin, etat["t"])
            with open(chemin, "a", encoding="utf-8") as f:
                f.write(ligne_datee(etat["t"]))
            etat["ecriture"] = (None if ecart is None
                                else etat["ecriture"] + ecart)

        def avant(delai):
            arrivee = etat["t"] + datetime.timedelta(seconds=delai)
            while (etat["ecriture"] is not None
                   and etat["ecriture"] <= arrivee):
                etat["t"] = etat["ecriture"]
                ecrire()
            etat["t"] = arrivee
            releve()               # juste avant le tour de purge
            return arrivee >= fin

        with unittest.mock.patch.object(
                serveur, "JOURNAL", chemin), \
                unittest.mock.patch.object(
                    serveur, "TECHNIQUE", self.chemin("technique.log")):
            serveur.boucle_purge_periodique(
                EvenementSimule(avant=avant),
                attente=serveur.PURGE_PERIODIQUE_SECONDES,
                horloge=lambda: etat["t"])
        return etat["pire"]

    def test_aucune_ligne_ne_depasse_n_mois_a_aucun_instant(self):
        # D1 sans réserve : toutes les 12 h, quotidiennes, hebdomadaires,
        # une seule par mois, et aucune écriture après la première.
        cadences = (("12 h", datetime.timedelta(hours=12)),
                    ("1 jour", datetime.timedelta(days=1)),
                    ("7 jours", datetime.timedelta(days=7)),
                    ("30 jours", datetime.timedelta(days=30)),
                    ("aucune", None))
        for nom, ecart in cadences:
            with self.subTest(cadence=nom):
                for entree in os.listdir(self.dossier):
                    os.remove(self.chemin(entree))
                pire = self.simuler(ecart)
                self.assertLessEqual(pire, duree_mois(6),
                                     "{} : {}".format(nom, pire))

    def test_sans_le_fil_la_promesse_ne_tient_pas(self):
        # Preuve que la simulation mord : sans tour de purge, un journal où
        # plus rien ne s'écrit garde sa première ligne bien au-delà de six
        # mois (la purge à l'écriture ne s'exécute qu'à une écriture).
        with unittest.mock.patch.object(
                serveur, "entretenir_journaux", lambda maintenant=None: None):
            pire = self.simuler(None)
        self.assertGreater(pire, duree_mois(6))


# --------------------------------------------------------------------------
# Rotation atomique (constats de l'audit C4-T2)
# --------------------------------------------------------------------------

class RotationAtomique(BacADossier):

    def lire(self, nom):
        with open(self.chemin(nom), encoding="utf-8") as f:
            return f.read()

    def poser_archives(self, ages_en_jours):
        """Une archive par âge, du rang 1 vers le haut ; rend {nom: contenu}."""
        attendu = {}
        for rang, jours in enumerate(ages_en_jours, start=1):
            nom = "journal.log.%d" % rang
            contenu = (ligne_datee(MAINTENANT - datetime.timedelta(days=jours))
                       + "archive-%d\n" % rang)
            self.ecrire(nom, contenu)
            attendu[nom] = contenu
        return attendu

    def echouer_sur(self, source):
        """os.replace qui échoue pour une source donnée : l'échec s'injecte,
        il ne dépend pas de la plateforme (Windows, fichier tenu ouvert)."""
        reel = os.replace
        appels = []

        def remplacer(src, dst, *args, **kwargs):
            appels.append((src, dst))
            if src == source:
                raise PermissionError(13, "fichier utilisé par un autre processus")
            return reel(src, dst, *args, **kwargs)
        return remplacer, appels

    def test_echec_du_renommage_du_courant_ne_touche_aucune_archive(self):
        # Scénario de l'audit : archives de 35 à 140 jours, courant de plus
        # de 30 jours, renommage du courant qui échoue.
        attendu = self.poser_archives([35, 60, 100, 140])
        courant = self.chemin("journal.log")
        contenu = ligne_datee(MAINTENANT - 40 * JOUR) + "courant\n"
        self.ecrire("journal.log", contenu)
        remplacer, appels = self.echouer_sur(courant)

        with unittest.mock.patch.object(os, "replace", remplacer):
            for jour in range(6):          # six écritures, une par jour
                maintenant = MAINTENANT + jour * JOUR
                self.assertFalse(
                    serveur.faire_tourner_journal(courant, maintenant))
                self.assertEqual(self.lire("journal.log"), contenu)
                for nom, texte in attendu.items():
                    self.assertEqual(self.lire(nom), texte, nom)
                self.assertFalse(self.existe("journal.log.5"))
        # Rien d'autre que le renommage du courant n'a été tenté.
        self.assertEqual({src for src, _ in appels}, {courant})

        # Le verrou levé, la rotation aboutit et décale proprement.
        self.assertTrue(serveur.faire_tourner_journal(
            courant, MAINTENANT + 7 * JOUR))
        self.assertEqual(self.lire("journal.log.1"), contenu)
        for rang in range(1, 5):
            self.assertEqual(self.lire("journal.log.%d" % (rang + 1)),
                             attendu["journal.log.%d" % rang])

    def test_pas_de_nouvel_essai_dans_la_journee(self):
        self.poser_archives([35])
        courant = self.chemin("journal.log")
        self.ecrire("journal.log", ligne_datee(MAINTENANT - 40 * JOUR))
        remplacer, appels = self.echouer_sur(courant)
        with unittest.mock.patch.object(os, "replace", remplacer):
            for _ in range(6):
                serveur.faire_tourner_journal(courant, MAINTENANT)
            self.assertEqual(len(appels), 1)
            serveur.faire_tourner_journal(courant, MAINTENANT + JOUR - SECONDE)
            self.assertEqual(len(appels), 1)
            serveur.faire_tourner_journal(courant, MAINTENANT + JOUR)
            self.assertEqual(len(appels), 2)

    def test_decalage_interrompu_puis_repris_ne_perd_rien(self):
        attendu = self.poser_archives([10, 20, 30, 40, 50])
        courant = self.chemin("journal.log")
        contenu = ligne_datee(MAINTENANT - 40 * JOUR) + "courant\n"
        self.ecrire("journal.log", contenu)
        # Le décalage échoue à mi-chemin : .3 ne peut pas monter en .4.
        remplacer, _ = self.echouer_sur(self.chemin("journal.log.3"))
        with unittest.mock.patch.object(os, "replace", remplacer):
            self.assertFalse(serveur.faire_tourner_journal(courant, MAINTENANT))
        # Le courant attend sous son nom provisoire ; rien n'a disparu.
        presents = {self.lire(n) for n in os.listdir(self.dossier)
                    if n != "journal.log.rotation"}
        self.assertEqual(presents, set(attendu.values()))
        self.assertEqual(self.lire("journal.log.rotation"), contenu)

        # Une écriture plus tard (le lendemain), tout est replacé.
        serveur.faire_tourner_journal(courant, MAINTENANT + JOUR)
        self.assertFalse(self.existe("journal.log.rotation"))
        self.assertEqual(self.lire("journal.log.1"), contenu)
        for rang in range(1, 6):
            self.assertEqual(self.lire("journal.log.%d" % (rang + 1)),
                             attendu["journal.log.%d" % rang])

    def test_temporaire_laisse_par_une_interruption_est_replace_d_abord(self):
        attendu = self.poser_archives([10, 20])
        contenu = ligne_datee(MAINTENANT - 40 * JOUR) + "interrompu\n"
        self.ecrire("journal.log.rotation", contenu)
        # Un journal neuf, créé depuis : il ne doit pas être touché.
        neuf = ligne_datee(MAINTENANT)
        self.ecrire("journal.log", neuf)
        serveur.faire_tourner_journal(self.chemin("journal.log"), MAINTENANT)
        self.assertFalse(self.existe("journal.log.rotation"))
        self.assertEqual(self.lire("journal.log.1"), contenu)
        self.assertEqual(self.lire("journal.log.2"), attendu["journal.log.1"])
        self.assertEqual(self.lire("journal.log.3"), attendu["journal.log.2"])
        self.assertEqual(self.lire("journal.log"), neuf)

    def test_temporaire_replace_meme_sans_journal_courant(self):
        contenu = ligne_datee(MAINTENANT) + "interrompu\n"
        self.ecrire("journal.log.rotation", contenu)
        serveur.faire_tourner_journal(self.chemin("journal.log"), MAINTENANT)
        self.assertEqual(self.lire("journal.log.1"), contenu)

    def test_temporaire_jamais_ecrase_ni_purge(self):
        # Rang 1 occupé par un dossier : le temporaire ne peut pas être
        # placé. Un courant à archiver ne doit pas l'écraser.
        os.mkdir(self.chemin("journal.log.1"))
        provisoire = ligne_datee(MAINTENANT - duree_mois(8)) + "provisoire\n"
        self.ecrire("journal.log.rotation", provisoire)
        courant = ligne_datee(MAINTENANT - 40 * JOUR) + "courant\n"
        self.ecrire("journal.log", courant)
        self.assertFalse(serveur.faire_tourner_journal(
            self.chemin("journal.log"), MAINTENANT))
        serveur.purger_archives(self.chemin("journal.log"), MAINTENANT)
        self.assertEqual(self.lire("journal.log.rotation"), provisoire)
        self.assertEqual(self.lire("journal.log"), courant)

    def test_temporaire_non_replace_n_est_jamais_ecrase(self):
        # Le placement du temporaire échoue (injecté) : un courant à
        # archiver ne doit pas être renommé par-dessus.
        provisoire = ligne_datee(MAINTENANT - 40 * JOUR) + "provisoire\n"
        self.ecrire("journal.log.rotation", provisoire)
        courant = ligne_datee(MAINTENANT - 40 * JOUR) + "courant\n"
        self.ecrire("journal.log", courant)
        remplacer, appels = self.echouer_sur(self.chemin("journal.log.rotation"))
        with unittest.mock.patch.object(os, "replace", remplacer):
            for _ in range(3):
                self.assertFalse(serveur.faire_tourner_journal(
                    self.chemin("journal.log"), MAINTENANT))
        self.assertEqual(self.lire("journal.log.rotation"), provisoire)
        self.assertEqual(self.lire("journal.log"), courant)
        self.assertNotIn((self.chemin("journal.log"),
                          self.chemin("journal.log.rotation")), appels)

    def test_barriere_au_rang_un_ne_laisse_pas_toucher_au_rang_zero(self):
        # Avec un dossier au rang 1, aucun rang n'est libérable : la
        # suppression par compte ne doit surtout pas viser « .0 ».
        os.mkdir(self.chemin("journal.log.1"))
        zero = ligne_datee(MAINTENANT - duree_mois(8)) + "zero\n"
        self.ecrire("journal.log.0", zero)
        self.ecrire("journal.log.rotation", ligne_datee(MAINTENANT) + "p\n")
        serveur.faire_tourner_journal(self.chemin("journal.log"), MAINTENANT)
        self.assertEqual(self.lire("journal.log.0"), zero)
        self.assertTrue(self.existe("journal.log.rotation"))

    def remplir_et_tourner(self, rangs_fichiers, rang_barriere):
        """Pose les fichiers des rangs donnés et un dossier-barrière, puis
        fait tourner un courant trop vieux. Rend le résultat de la rotation."""
        os.mkdir(self.chemin("journal.log.%d" % rang_barriere))
        with open(os.path.join(self.chemin("journal.log.%d" % rang_barriere),
                               "dedans.txt"), "w", encoding="utf-8") as f:
            f.write("intouchable")
        for rang in rangs_fichiers:
            self.ecrire("journal.log.%d" % rang,
                        ligne_datee(MAINTENANT - JOUR) + "rang-%d\n" % rang)
        self.ecrire("journal.log", ligne_datee(MAINTENANT - 40 * JOUR) + "courant\n")
        return serveur.faire_tourner_journal(self.chemin("journal.log"), MAINTENANT)

    def verifier_barriere_intacte(self, rang):
        chemin = self.chemin("journal.log.%d" % rang)
        self.assertTrue(os.path.isdir(chemin))
        with open(os.path.join(chemin, "dedans.txt"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "intouchable")

    def test_dossier_au_rang_le_plus_haut_ne_bloque_pas_la_rotation(self):
        borne = serveur.generations_maximales()
        resultat = self.remplir_et_tourner(range(1, borne), borne)
        self.assertTrue(resultat)
        self.verifier_barriere_intacte(borne)
        self.assertIn("courant", self.lire("journal.log.1"))
        # Le décalage s'est arrêté sous la barrière : l'archive du rang
        # borne - 1 est partie par le compte, l'avant-dernière l'a remplacée.
        self.assertIn("rang-%d" % (borne - 2),
                      self.lire("journal.log.%d" % (borne - 1)))
        self.assertFalse(self.existe("journal.log"))

    def test_dossier_au_milieu_de_la_chaine_est_une_barriere(self):
        resultat = self.remplir_et_tourner([1, 2, 4, 5], 3)
        self.assertTrue(resultat)
        self.verifier_barriere_intacte(3)
        self.assertIn("courant", self.lire("journal.log.1"))
        self.assertIn("rang-1", self.lire("journal.log.2"))
        # Au-delà de la barrière, rien n'a bougé.
        self.assertIn("rang-4", self.lire("journal.log.4"))
        self.assertIn("rang-5", self.lire("journal.log.5"))

    def test_dossier_au_rang_un_interdit_la_rotation_sans_rien_casser(self):
        courant = ligne_datee(MAINTENANT - 40 * JOUR) + "courant\n"
        os.mkdir(self.chemin("journal.log.1"))
        self.ecrire("journal.log", courant)
        self.assertFalse(serveur.faire_tourner_journal(
            self.chemin("journal.log"), MAINTENANT))
        self.assertEqual(self.lire("journal.log"), courant)
        self.assertTrue(os.path.isdir(self.chemin("journal.log.1")))
        self.assertFalse(self.existe("journal.log.rotation"))


class HorodatageIllisible(BacADossier):
    """D3 : un horodatage illisible se replie sur la date de modification,
    et rien ne lève."""

    def purger(self):
        return serveur.purger_archives(self.chemin("journal.log"), MAINTENANT)

    def test_illisible_ancien_purge_recent_conserve(self):
        illisibles = {
            "texte": "n'importe quoi\n",
            "vide": "",
            "date_seule": "2020-01-01 REPONSE\n",
            "compact": "20200101T000000 REPONSE\n",   # accepté en 3.11+ seulement
            "fuseau": "2020-01-01T00:00:00+02:00 REPONSE\n",
            "mois_impossible": "2020-13-45T99:99:99 REPONSE\n",
        }
        for cle, contenu in illisibles.items():
            with self.subTest(cas=cle, modification="ancienne"):
                self.ecrire("journal.log.1", contenu,
                            MAINTENANT - duree_mois(6) - SECONDE)
                self.assertEqual(self.purger(), 1)
                self.assertFalse(self.existe("journal.log.1"))
            with self.subTest(cas=cle, modification="recente"):
                self.ecrire("journal.log.1", contenu, MAINTENANT)
                self.assertEqual(self.purger(), 0)
                self.assertTrue(self.existe("journal.log.1"))

    def test_octets_non_utf8_ne_levent_pas(self):
        chemin = self.chemin("journal.log.1")
        with open(chemin, "wb") as f:
            f.write(b"\xff\xfe\x00 \xe9\xe8 REPONSE\n")
        horodatage = (MAINTENANT - duree_mois(7)).timestamp()
        os.utime(chemin, (horodatage, horodatage))
        self.assertEqual(self.purger(), 1)

    def test_horodatage_futur_se_replie_sur_la_modification(self):
        # Une tête datée de 2999 rendrait le fichier immortel.
        self.ecrire("journal.log.1", "2999-01-01T00:00:00 REPONSE\n",
                    MAINTENANT - duree_mois(7))
        self.assertEqual(self.purger(), 1)

    @unittest.skipIf(os.name == "nt",
                     "chmod ne restreint pas la lecture sous Windows")
    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0,
                     "root lit tout fichier")
    def test_archive_illisible_ne_leve_pas(self):
        chemin = self.ecrire("journal.log.1", ligne_datee(MAINTENANT),
                             MAINTENANT - duree_mois(7))
        os.chmod(chemin, 0)
        try:
            self.assertEqual(self.purger(), 1)     # repli sur la modification
        finally:
            if os.path.exists(chemin):
                os.chmod(chemin, 0o600)

    @unittest.skipIf(os.name == "nt",
                     "chmod ne restreint pas la suppression sous Windows")
    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0,
                     "root supprime dans tout dossier")
    def test_suppression_impossible_ne_leve_pas(self):
        # Le dossier n'autorise pas la suppression : os.remove lève
        # PermissionError, que la purge doit absorber (un journal ne coûte
        # jamais une requête), puis continuer avec les rangs suivants.
        self.ecrire("journal.log.1", ligne_datee(MAINTENANT - duree_mois(7)))
        os.chmod(self.dossier, 0o500)
        try:
            self.assertEqual(self.purger(), 0)
            self.assertTrue(self.existe("journal.log.1"))
        finally:
            os.chmod(self.dossier, 0o700)

    def test_horloge_aberrante_ne_leve_pas(self):
        self.ecrire("journal.log.1", ligne_datee(MAINTENANT), MAINTENANT)
        serveur.purger_archives(self.chemin("journal.log"),
                                datetime.datetime.min + SECONDE)
        self.assertTrue(self.existe("journal.log.1"))

    def test_rotation_avec_horodatage_illisible_ne_leve_pas(self):
        self.ecrire("journal.log", "\xff\xfe\n")
        self.ecrire("journal.log.1", "\x00\n")
        serveur.faire_tourner_journal(self.chemin("journal.log"), MAINTENANT)


# --------------------------------------------------------------------------
# Point nommé de l'audit (D6)
# --------------------------------------------------------------------------

class LaPurgeResteDansLesArchives(BacADossier):
    """La purge ne supprime que « <journal>.<entier> », entier de 1 à
    CONSERVATION_MOIS_MAX + 1. Tout le reste du dossier survit, même vieux de dix ans."""

    def test_leurres_intacts(self):
        ancien = ligne_datee(MAINTENANT - duree_mois(120))
        vieux = MAINTENANT - duree_mois(120)

        fichiers = [
            "journal.log.bak", "journal.log.1.x", "journal.log.1.bak",
            "journal.log.0", "journal.log.%d" % (serveur.CONSERVATION_MOIS_MAX + 2),
            "journal.log.rotation",
            "journal.log.01", "journal.log.-1",
            "journal.logX1", "xjournal.log.1", "journal.log.1~",
            "config.json", "config.json.1", "technique.log.1",
            "autorite.crt", "cle.pem",
        ]
        for nom in fichiers:
            self.ecrire(nom, ancien, vieux)

        # Un dossier du nom d'une archive, avec un contenu vieux dedans.
        os.mkdir(self.chemin("journal.log.4"))
        self.ecrire(os.path.join("journal.log.4", "dedans.txt"), ancien, vieux)

        # Un lien symbolique du nom d'une archive, vers un fichier vieux
        # situé hors du dossier : ni lui ni sa cible ne doivent disparaître.
        dehors = tempfile.mkdtemp(prefix="bilan-conservation-dehors-")
        self.addCleanup(shutil.rmtree, dehors, ignore_errors=True)
        cible = os.path.join(dehors, "cible.log")
        with open(cible, "w", encoding="utf-8") as f:
            f.write(ancien)
        lien_pose = True
        try:
            os.symlink(cible, self.chemin("journal.log.5"))
        except (OSError, NotImplementedError, AttributeError):
            lien_pose = False       # Windows sans privilège : permis par le contrat

        # La vraie archive périmée : preuve que la purge a bien travaillé.
        self.ecrire("journal.log.1", ancien, vieux)
        self.ecrire("journal.log.2", ancien, vieux)

        supprimees = serveur.purger_archives(
            self.chemin("journal.log"), MAINTENANT)

        self.assertEqual(supprimees, 2)
        self.assertFalse(self.existe("journal.log.1"))
        self.assertFalse(self.existe("journal.log.2"))
        for nom in fichiers:
            self.assertTrue(self.existe(nom), nom + " a été supprimé")
        self.assertTrue(os.path.isdir(self.chemin("journal.log.4")))
        self.assertTrue(os.path.exists(
            self.chemin(os.path.join("journal.log.4", "dedans.txt"))))
        if lien_pose:
            self.assertTrue(os.path.islink(self.chemin("journal.log.5")))
            self.assertTrue(os.path.exists(cible))

    def test_n_baisse_de_12_a_6_les_orphelines_sont_purgees(self):
        # Avec N = 12 les archives vont jusqu'à .13 ; N repassé à 6, la borne
        # de rotation tombe à 7 : les rangs 8 à 13 ne doivent pas rester
        # hors d'atteinte, sinon leurs lignes vivraient indéfiniment.
        for rang in range(9, 14):
            self.ecrire("journal.log.%d" % rang,
                        ligne_datee(MAINTENANT - duree_mois(8)))
        self.ecrire("journal.log.1", ligne_datee(MAINTENANT - JOUR))
        with unittest.mock.patch.object(
                serveur, "CONSERVATION_JOURNAUX_MOIS", 6):
            self.assertLess(serveur.generations_maximales(), 9)
            supprimees = serveur.purger_archives(
                self.chemin("journal.log"), MAINTENANT)
        self.assertEqual(supprimees, 5)
        for rang in range(9, 14):
            self.assertFalse(self.existe("journal.log.%d" % rang))
        self.assertTrue(self.existe("journal.log.1"))

    def test_la_sonde_va_jusqu_a_la_borne_maximale_et_pas_au_dela(self):
        dernier = serveur.CONSERVATION_MOIS_MAX + 1
        for rang in (dernier, dernier + 1):
            self.ecrire("journal.log.%d" % rang,
                        ligne_datee(MAINTENANT - duree_mois(130)))
        serveur.purger_archives(self.chemin("journal.log"), MAINTENANT)
        self.assertFalse(self.existe("journal.log.%d" % dernier))
        self.assertTrue(self.existe("journal.log.%d" % (dernier + 1)))

    def test_la_rotation_ne_supprime_pas_un_lien_du_rang_le_plus_ancien(self):
        borne = serveur.generations_maximales()
        dehors = tempfile.mkdtemp(prefix="bilan-conservation-dehors-")
        self.addCleanup(shutil.rmtree, dehors, ignore_errors=True)
        cible = os.path.join(dehors, "cible.log")
        with open(cible, "w", encoding="utf-8") as f:
            f.write("contenu hors des archives\n")
        lien = self.chemin("journal.log.%d" % borne)
        try:
            os.symlink(cible, lien)
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("liens symboliques non permis ici")
        with unittest.mock.patch.object(serveur, "JOURNAL_TAILLE_MAX", 100):
            self.ecrire("journal.log", ligne_datee(MAINTENANT) + "x" * 100)
            self.assertTrue(serveur.faire_tourner_journal(
                self.chemin("journal.log"), MAINTENANT))
        self.assertTrue(os.path.islink(lien))
        self.assertTrue(os.path.exists(cible))
        self.assertTrue(self.existe("journal.log.1"))

    def test_la_rotation_supprime_la_plus_ancienne_quand_la_chaine_est_pleine(self):
        borne = serveur.generations_maximales()
        for rang in range(1, borne + 1):
            self.ecrire("journal.log.%d" % rang,
                        ligne_datee(MAINTENANT) + "rang-%d\n" % rang)
        with unittest.mock.patch.object(serveur, "JOURNAL_TAILLE_MAX", 100):
            self.ecrire("journal.log", ligne_datee(MAINTENANT) + "x" * 100)
            serveur.faire_tourner_journal(self.chemin("journal.log"), MAINTENANT)
        # L'ancien dernier rang est parti ; l'avant-dernier l'a remplacé.
        with open(self.chemin("journal.log.%d" % borne), encoding="utf-8") as f:
            self.assertIn("rang-%d" % (borne - 1), f.read())
        self.assertFalse(self.existe("journal.log.%d" % (borne + 1)))

    def test_la_rotation_ne_supprime_rien_tant_qu_un_rang_est_libre(self):
        # Une seule archive, au rang le plus haut : la chaîne a des trous, le
        # décalage ne doit rien supprimer par le compte.
        borne = serveur.generations_maximales()
        self.ecrire("journal.log.%d" % borne, ligne_datee(MAINTENANT) + "seule\n")
        with unittest.mock.patch.object(serveur, "JOURNAL_TAILLE_MAX", 100):
            self.ecrire("journal.log", ligne_datee(MAINTENANT) + "x" * 100)
            serveur.faire_tourner_journal(self.chemin("journal.log"), MAINTENANT)
        with open(self.chemin("journal.log.%d" % borne), encoding="utf-8") as f:
            self.assertIn("seule", f.read())
        self.assertTrue(self.existe("journal.log.1"))

    def test_un_lien_du_nom_d_une_archive_n_est_pas_lu(self):
        # Le lien pointe vers un fichier daté de maintenant : s'il était
        # suivi, il serait épargné pour la mauvaise raison. On le pointe vers
        # un fichier vieux, et c'est le lien qui doit survivre.
        dehors = tempfile.mkdtemp(prefix="bilan-conservation-dehors-")
        self.addCleanup(shutil.rmtree, dehors, ignore_errors=True)
        cible = os.path.join(dehors, "cible.log")
        with open(cible, "w", encoding="utf-8") as f:
            f.write(ligne_datee(MAINTENANT - duree_mois(40)))
        try:
            os.symlink(cible, self.chemin("journal.log.1"))
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("liens symboliques non permis ici")
        self.assertEqual(serveur.purger_archives(
            self.chemin("journal.log"), MAINTENANT), 0)
        self.assertTrue(os.path.islink(self.chemin("journal.log.1")))
        self.assertTrue(os.path.exists(cible))

    # Points d'entrée de la purge et de la rotation : tout ce qu'ils appellent,
    # de proche en proche, est dérivé de l'arbre syntaxique de serveur.py —
    # jamais une liste tenue à la main, qui avait oublié les deux fonctions
    # ajoutées après l'audit (_liberer_le_rang_un, _replacer_le_temporaire).
    POINTS_D_ENTREE = ("faire_tourner_journal", "purger_archives",
                       "purger_au_demarrage", "entretenir_journaux")

    @classmethod
    def chaine_de_purge(cls):
        """Les fonctions de serveur.py atteignables depuis POINTS_D_ENTREE."""
        module = ast.parse(inspect.getsource(serveur))
        fonctions = {n.name: n for n in module.body
                     if isinstance(n, ast.FunctionDef)}
        a_voir, vues = list(cls.POINTS_D_ENTREE), set()
        while a_voir:
            nom = a_voir.pop()
            if nom in vues or nom not in fonctions:
                continue
            vues.add(nom)
            for noeud in ast.walk(fonctions[nom]):
                if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name):
                    a_voir.append(noeud.func.id)
        return [getattr(serveur, nom) for nom in sorted(vues)]

    def test_la_chaine_derivee_couvre_les_fonctions_connues(self):
        # Garde anti-vide : une dérivation cassée rendrait les deux gardes
        # de source vertes sans rien examiner.
        noms = {f.__name__ for f in self.chaine_de_purge()}
        for attendu in ("faire_tourner_journal", "purger_archives",
                        "_liberer_le_rang_un", "_replacer_le_temporaire",
                        "_est_fichier_ordinaire", "_age_premiere_ligne"):
            with self.subTest(fonction=attendu):
                self.assertIn(attendu, noms)

    def test_un_temporaire_qui_n_est_pas_un_fichier_reste_en_place(self):
        # Un dossier du nom provisoire n'est ni déplacé en « .1 » ni ne fait
        # décaler la chaîne : seul un fichier ordinaire est un journal laissé
        # par une rotation interrompue.
        os.mkdir(self.chemin("journal.log.rotation"))
        self.ecrire("journal.log.1", ligne_datee(MAINTENANT - duree_mois(1)))
        serveur._replacer_le_temporaire(self.chemin("journal.log"))
        self.assertTrue(os.path.isdir(self.chemin("journal.log.rotation")))
        self.assertTrue(os.path.isfile(self.chemin("journal.log.1")))
        self.assertFalse(self.existe("journal.log.2"))

    @staticmethod
    def identifiants(fonction):
        """Noms et attributs réellement employés par une fonction : lus dans
        l'arbre syntaxique, pour ne pas confondre le code avec sa docstring
        (qui nomme justement ce qu'elle s'interdit)."""
        arbre = ast.parse(inspect.getsource(fonction))
        noms = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Name):
                noms.add(noeud.id)
            elif isinstance(noeud, ast.Attribute):
                noms.add(noeud.attr)
            elif isinstance(noeud, (ast.Import, ast.ImportFrom)):
                noms.update(a.name.split(".")[0] for a in noeud.names)
        return noms

    def test_aucune_recherche_par_motif(self):
        # Garde de source, dérivée du code : ni glob, ni listdir, ni scandir,
        # ni walk dans la chaîne de purge. Une recherche par motif pourrait
        # désigner autre chose qu'une archive.
        interdits = {"glob", "iglob", "listdir", "scandir", "walk", "fnmatch",
                     "rmtree", "shutil", "pathlib", "Path", "rmdir",
                     "removedirs"}
        for fonction in self.chaine_de_purge():
            with self.subTest(fonction=fonction.__name__):
                self.assertEqual(
                    self.identifiants(fonction) & interdits, set())

    def test_la_purge_ne_journalise_pas(self):
        # Appelée sous _verrou_journal, non réentrant : une écriture de
        # journal depuis la purge est un interblocage garanti.
        self.ecrire("journal.log.1", ligne_datee(MAINTENANT - duree_mois(12)))
        with unittest.mock.patch.object(serveur, "journaliser") as j, \
                unittest.mock.patch.object(
                    serveur, "journaliser_technique") as t, \
                unittest.mock.patch.object(serveur, "ecrire_stderr") as e, \
                unittest.mock.patch.object(
                    serveur, "JOURNAL", self.chemin("journal.log")), \
                unittest.mock.patch.object(
                    serveur, "TECHNIQUE", self.chemin("technique.log")):
            serveur.purger_archives(self.chemin("journal.log"), MAINTENANT)
            serveur.purger_au_demarrage()
            self.ecrire("journal.log", ligne_datee(MAINTENANT - duree_mois(2)))
            serveur.faire_tourner_journal(self.chemin("journal.log"), MAINTENANT)
        j.assert_not_called()
        t.assert_not_called()
        e.assert_not_called()

        # Et dans le code lui-même : aucune fonction de la chaîne ne nomme
        # une fonction d'écriture de journal.
        for fonction in self.chaine_de_purge():
            with self.subTest(fonction=fonction.__name__):
                self.assertEqual(
                    self.identifiants(fonction)
                    & {"journaliser", "journaliser_technique",
                       "ecrire_stderr", "_ajouter_ligne_technique"}, set())

    def test_la_purge_au_demarrage_ne_bloque_pas(self):
        # Elle prend _verrou_journal : si elle appelait journaliser(), le
        # verrou non réentrant la figerait. Fil à échéance.
        self.ecrire("journal.log.1", ligne_datee(MAINTENANT - duree_mois(12)))
        fini = []

        def purger():
            with unittest.mock.patch.object(
                    serveur, "JOURNAL", self.chemin("journal.log")), \
                    unittest.mock.patch.object(
                        serveur, "TECHNIQUE", self.chemin("technique.log")):
                serveur.purger_au_demarrage()
            fini.append(True)

        fil = threading.Thread(target=purger, daemon=True)
        fil.start()
        fil.join(10)
        self.assertEqual(fini, [True])
        self.assertFalse(self.existe("journal.log.1"))


if __name__ == "__main__":
    unittest.main()
