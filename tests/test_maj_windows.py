"""Le client de mise à jour contre le vrai Windows (C5-T2a, critère A17).

Windows seulement. `schtasks.exe` et `icacls.exe` ne se simulent pas : ce que
`maj.PiloteTachePlanifiee` et le dossier réservé font de ces deux outils ne
s'éprouve que sur le vrai système. En intégration continue (`windows-latest`),
le lanceur est administrateur ; s'il ne l'est pas, le test ÉCHOUE au lieu de se
sauter, comme `ExecutionReelleSousWindows` : un saut ferait croire à une
couverture que l'on n'a pas.

    python -m unittest tests.test_maj_windows -v
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

DOSSIER_TESTS = os.path.dirname(os.path.abspath(__file__))
PROJET = os.path.dirname(DOSSIER_TESTS)
sys.path.insert(0, os.path.join(PROJET, "serveur"))
sys.path.insert(0, DOSSIER_TESTS)
sys.path.insert(0, os.path.join(DOSSIER_TESTS, "outils"))

import maj  # noqa: E402
import paquet_essai as pe  # noqa: E402
import serveur  # noqa: E402

SCRIPT_BATTEMENT = '''
import os, sys, time
dossier = sys.argv[1]
with open(os.path.join(dossier, "demarre.txt"), "w") as f:
    f.write("ok")
n = 0
while True:
    n += 1
    with open(os.path.join(dossier, "battement.txt"), "w") as f:
        f.write(str(n))
    time.sleep(0.2)
'''


def est_administrateur():
    import ctypes
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def lancer(*arguments):
    return subprocess.run(list(arguments), stdin=subprocess.DEVNULL, capture_output=True,
                          text=True, errors="replace", timeout=120)


@unittest.skipUnless(os.name == "nt", "Windows seulement")
class WindowsReel(unittest.TestCase):

    def test_le_lanceur_est_administrateur(self):
        # Échec, et non saut : sans droits, ni la tâche jetable ni les droits du
        # dossier ne s'éprouvent, et le critère A17 ne serait pas tenu.
        if not est_administrateur():
            self.fail("le lanceur n'est pas administrateur : A17 exige l'exécution "
                      "réelle de schtasks et d'icacls. Ce test ne se saute pas.")

    def test_nom_de_la_tache_egal_a_celui_du_script_d_installation(self):
        with open(os.path.join(PROJET, "installer-demarrage.ps1"), encoding="utf-8-sig") as f:
            correspondance = re.search(r'^\$NOM_TACHE\s*=\s*"([^"]+)"', f.read(), re.MULTILINE)
        self.assertIsNotNone(correspondance)
        self.assertEqual(maj.NOM_TACHE_SERVEUR, correspondance.group(1))

    def test_pilote_de_tache_planifiee_sur_une_tache_jetable(self):
        if not est_administrateur():
            self.fail("le lanceur n'est pas administrateur")
        nom = "BilanPosturo-essai-" + uuid.uuid4().hex[:8]
        dossier = tempfile.mkdtemp(prefix="bilan-maj-tache-",
                                   dir=os.path.join(os.environ["SystemRoot"], "Temp"))
        self.addCleanup(shutil.rmtree, dossier, True)
        script = os.path.join(dossier, "battement.py")
        with open(script, "w") as f:
            f.write(SCRIPT_BATTEMENT)
        pilote = maj.PiloteTachePlanifiee(nom)
        self.assertFalse(pilote.existe())

        action = '"%s" "%s" "%s"' % (sys.executable, script, dossier)
        creation = lancer(maj._systeme32("schtasks.exe"), "/Create", "/TN", nom, "/TR", action,
                          "/SC", "ONCE", "/ST", "23:59", "/RU", "SYSTEM", "/RL", "HIGHEST", "/F")
        # Nettoyage dans tous les cas, y compris si la création échoue à moitié.
        self.addCleanup(lancer, maj._systeme32("schtasks.exe"), "/Delete", "/TN", nom, "/F")
        self.addCleanup(lancer, maj._systeme32("schtasks.exe"), "/End", "/TN", nom)
        self.assertEqual(creation.returncode, 0, creation.stdout + creation.stderr)

        self.assertTrue(pilote.existe())
        pilote.demarrer()
        marque = os.path.join(dossier, "demarre.txt")
        limite = time.monotonic() + 30
        while not os.path.exists(marque) and time.monotonic() < limite:
            time.sleep(0.2)
        self.assertTrue(os.path.exists(marque), "la tâche n'a pas démarré")

        self.assertTrue(pilote.arreter_de_force())
        time.sleep(1.5)
        battement = os.path.join(dossier, "battement.txt")
        with open(battement) as f:
            avant = f.read()
        time.sleep(1.5)
        with open(battement) as f:
            self.assertEqual(f.read(), avant, "la tâche tourne encore après /End")
        # Rien à arrêter : un code non nul, qui n'est pas une erreur.
        self.assertFalse(pilote.arreter_de_force())

        lancer(maj._systeme32("schtasks.exe"), "/Delete", "/TN", nom, "/F")
        self.assertFalse(pilote.existe())

    def test_tache_inexistante(self):
        pilote = maj.PiloteTachePlanifiee("BilanPosturo-absente-" + uuid.uuid4().hex)
        self.assertFalse(pilote.existe())
        with self.assertRaises(maj.Refus) as contexte:
            pilote.demarrer()
        self.assertEqual(contexte.exception.code, "TACHE_ABSENTE")

    def test_droits_du_dossier_reserve_relus_apres_icacls(self):
        if not est_administrateur():
            self.fail("le lanceur n'est pas administrateur")
        racine = os.path.realpath(tempfile.mkdtemp(prefix="bilan-maj-droits-"))
        self.addCleanup(shutil.rmtree, racine, True)
        maj.preparer_dossier_prive(racine)
        dossier = os.path.join(racine, serveur.NOM_DOSSIER_MAJ)
        # Un fichier créé dedans hérite des mêmes droits.
        fichier = os.path.join(dossier, "essai.txt")
        with open(fichier, "w") as f:
            f.write("x")
        for cible in (dossier, fichier):
            with self.subTest(cible=os.path.basename(cible)):
                enregistrement = os.path.join(racine, "droits-" + os.path.basename(cible) + ".txt")
                resultat = lancer(maj._systeme32("icacls.exe"), cible, "/save", enregistrement)
                self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
                with open(enregistrement, "rb") as f:
                    brut = f.read()
                texte = brut.decode("utf-16") if brut[:2] in (b"\xff\xfe", b"\xfe\xff") \
                    else brut.decode("utf-8", "replace")
                # Lecture INDÉPENDANTE de maj.sddl_est_protege : deux lecteurs qui
                # s'accordent valent mieux qu'un seul qui se juge lui-même.
                self.assertEqual(set(re.findall(r";;;([A-Z0-9-]+)\)", texte)), {"SY", "BA"}, texte)
                if cible == dossier:
                    # Le dossier est protégé ; le fichier, lui, HÉRITE (D:AI).
                    self.assertRegex(texte, r"D:P")
                    self.assertTrue(maj.sddl_est_protege(texte)[0], texte)
                else:
                    self.assertRegex(texte, r"D:AI")

    def test_dossier_reserve_relu_a_chaque_fois(self):
        racine = os.path.realpath(tempfile.mkdtemp(prefix="bilan-maj-droits-"))
        self.addCleanup(shutil.rmtree, racine, True)
        maj.preparer_dossier_prive(racine)
        maj.preparer_dossier_prive(racine)
        self.assertEqual(os.listdir(os.path.join(racine, serveur.NOM_DOSSIER_MAJ)), [])

    def test_icacls_refuse_est_un_dossier_non_protege(self):
        racine = os.path.realpath(tempfile.mkdtemp(prefix="bilan-maj-droits-"))
        self.addCleanup(shutil.rmtree, racine, True)
        os.mkdir(os.path.join(racine, serveur.NOM_DOSSIER_MAJ))
        reel = maj._lancer_windows
        maj._lancer_windows = lambda arguments, delai=60: 5
        try:
            with self.assertRaises(maj.Refus) as contexte:
                maj.preparer_dossier_prive(racine)
        finally:
            maj._lancer_windows = reel
        self.assertEqual(contexte.exception.code, "DOSSIER_NON_PROTEGE")

    def test_paquet_essai_est_importable_sous_windows(self):
        # Le bout en bout fabrique ses paquets sans sh ni zip : il tourne ici aussi.
        self.assertTrue(callable(pe.fabriquer_trio))


if __name__ == "__main__":
    unittest.main()
