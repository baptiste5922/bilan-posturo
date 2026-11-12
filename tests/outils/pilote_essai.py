"""Pilote de serveur pour les tests de mise à jour (C5-T2a).

Même interface que `maj.PiloteTachePlanifiee` (`existe`, `demarrer`,
`arreter_de_force`), mais le « serveur » est le `serveur.py` du bac à sable, lancé
en sous-processus. Sa sortie va dans un FICHIER, jamais dans un tube : un tube
`stdout=PIPE` que personne ne lit finit plein, et sous Windows le serveur se
fige alors (seule /sante répond ; piège de C7-T5).

Le numéro du processus est écrit dans un fichier : un second pilote, ou un autre
processus (celui d'un `maj.py` tué en pleine bascule), peut ainsi arrêter un
serveur qu'il n'a pas lancé, comme `schtasks /End` le fait pour la tâche.

NE PART JAMAIS AU CABINET : il vit sous `tests/`.
"""

import os
import signal
import subprocess
import sys
import time


class PiloteProcessus(object):
    """Lance et arrête le serveur d'un bac à sable.

    `racine` est la racine d'installation (celle qui contient `serveur/`) ;
    `sortie` un dossier HORS de cette racine, pour que l'arbre à comparer ne
    reçoive ni journal de console ni fichier de pid."""

    def __init__(self, racine, sortie, tache_existe=True):
        self.racine = racine
        self.sortie = sortie
        self.tache_existe = tache_existe
        self.appels = []
        self.processus = None
        self.fichier_pid = os.path.join(sortie, "serveur.pid")
        self.fichier_console = os.path.join(sortie, "console.txt")

    # --- interface commune au pilote de production -------------------------

    def existe(self):
        self.appels.append("existe")
        return self.tache_existe

    def demarrer(self):
        """Comme `schtasks /Run` d'une tâche en IgnoreNew : sans effet si une
        instance tourne déjà."""
        self.appels.append("demarrer")
        if self._vivant():
            return
        with open(self.fichier_console, "ab") as console:
            # -B : le serveur n'écrit aucun __pycache__ dans l'arbre comparé.
            self.processus = subprocess.Popen(
                [sys.executable, "-B", "-u", os.path.join("serveur", "serveur.py")],
                cwd=self.racine, stdin=subprocess.DEVNULL, stdout=console,
                stderr=subprocess.STDOUT)
        with open(self.fichier_pid, "w") as f:
            f.write(str(self.processus.pid))

    def arreter_de_force(self):
        self.appels.append("arreter_de_force")
        pid = self._pid()
        if pid is None:
            return False
        tue = self._tuer(pid)
        if self.processus is not None and self.processus.pid == pid:
            try:
                self.processus.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
            self.processus = None
        else:
            self._attendre_la_mort(pid)
        try:
            os.remove(self.fichier_pid)
        except OSError:
            pass
        return tue

    # --- aides des tests ----------------------------------------------------

    def arreter(self):
        """Nettoyage de fin de test : n'importe quel serveur lancé par ce pilote
        ou par un processus qui l'a utilisé est arrêté."""
        pid = self._pid()
        if pid is not None:
            self._tuer(pid)
            if self.processus is not None:
                try:
                    self.processus.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
                self.processus = None
            else:
                self._attendre_la_mort(pid)
            try:
                os.remove(self.fichier_pid)
            except OSError:
                pass

    def attendre_la_sortie(self, delai=30):
        """Code de sortie du serveur lancé par CE pilote, ou None après `delai`."""
        if self.processus is None:
            return None
        try:
            code = self.processus.wait(timeout=delai)
        except subprocess.TimeoutExpired:
            return None
        self.processus = None
        return code

    def console(self):
        try:
            with open(self.fichier_console, encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return ""

    # --- interne ---------------------------------------------------------------

    def _pid(self):
        try:
            with open(self.fichier_pid) as f:
                return int(f.read().strip())
        except (OSError, ValueError):
            return None

    def _vivant(self):
        if self.processus is not None:
            return self.processus.poll() is None
        pid = self._pid()
        if pid is None or os.name == "nt":
            return False
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    @staticmethod
    def _tuer(pid):
        if os.name == "nt":
            return subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)], stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            return False
        return True

    @staticmethod
    def _attendre_la_mort(pid, delai=10):
        if os.name == "nt":
            time.sleep(0.5)
            return
        limite = time.monotonic() + delai
        while time.monotonic() < limite:
            try:
                os.kill(pid, 0)
            except OSError:
                return
            time.sleep(0.05)
