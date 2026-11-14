#!/usr/bin/env python3
"""
Client de mise à jour du serveur du bilan posturologique (C5-T2a).

Applique un paquet signé posé sur le PC du cabinet, le défait seul s'il ne tient
pas, et laisse une trace lisible par le support. Aucun accès réseau : C5-T2b y
ajoutera le téléchargement.

    python serveur\\maj.py appliquer <archive>   installe un paquet signé
    python serveur\\maj.py revenir               défait la dernière mise à jour
    python serveur\\maj.py reprendre             termine ou défait une mise à jour interrompue
    python serveur\\maj.py etat                  dit où en est la mise à jour
    python serveur\\maj.py auto-controle         contrôle que ce client se charge

C'est le code le plus dangereux du produit : il remplace, sous le compte SYSTEM,
le code qui reçoit les bilans. La règle qui le structure : tout ce qui peut
échouer échoue AVANT d'avoir touché un fichier du cabinet, et tout ce qui a été
touché se défait. Les clés qui jugent le paquet sont celles DÉJÀ installées,
jamais celles du paquet.

Bibliothèque standard seule. Contrat : docs/contrats/C5-T2.md.
Codes de sortie : 0 succès, 1 refus ou échec, 2 usage ou dépôt de développement,
3 reporté (à retenter plus tard).
"""

import argparse
import contextlib
import datetime
import hashlib
import http.client
import json
import os
import re
import secrets
import shutil
import socket
import ssl
import stat
import subprocess
import sys
import time
import zipfile

if os.name == "nt":
    import msvcrt
else:
    import fcntl

# Le dossier du script en tête de sys.path, explicitement : les modules voisins
# (le serveur, le vérificateur) se chargent d'ici, quel que soit le dossier
# courant, et TOUS au niveau du module. Après la bascule, ce processus ne doit
# plus rien charger : ses fichiers ont été remplacés sous ses pieds (D12).
DOSSIER_SCRIPT = os.path.dirname(os.path.abspath(__file__))
if not sys.path or sys.path[0] != DOSSIER_SCRIPT:
    sys.path.insert(0, DOSSIER_SCRIPT)

import paquet_signe  # noqa: E402
import serveur  # noqa: E402
import signature_ed25519  # noqa: E402

# Comme serveur.py : la racine est le parent du dossier du script.
RACINE = os.path.dirname(DOSSIER_SCRIPT)

# --------------------------------------------------------------------------
# Vocabulaire
# --------------------------------------------------------------------------

# Codes fermés (D8) : seuls ceux-ci, et ceux de paquet_signe.CODES, atteignent
# technique.log, qui circule. ETAT_ILLISIBLE s'ajoute à la liste du contrat
# (erratum 2 du contrat C5-T2).
CODES_MAJ = (
    "DEJA_EN_COURS", "DOSSIER_NON_PROTEGE", "CLIENT_NON_CONFIGURE",
    "CLES_ABSENTES", "VERSION_ECARTEE", "PAQUET_INCOMPLET", "CHEMIN_PROTEGE",
    "DESTINATION_INVALIDE", "CHEMIN_TROP_LONG", "SCHEMA_MODIFIE_LOCALEMENT",
    "ESPACE_INSUFFISANT", "ECRITURE_IMPOSSIBLE", "EXTRACTION_ALTEREE",
    "SAUVEGARDE_ALTEREE", "TACHE_ABSENTE", "SERVEUR_ABSENT", "ARRET_REFUSE",
    "ARRET_SANS_REPONSE", "SANTE_MUETTE", "AUTO_CONTROLE_ECHOUE", "INTERROMPUE",
    "RETOUR_MANUEL", "RETOUR_IMPOSSIBLE", "CODE_INCONNU", "ETAT_ILLISIBLE",
)
# Les refus qui donnent MAJ_REPORTEE (on retentera) plutôt que MAJ_REFUSEE.
CODES_REPORT = frozenset((
    "DEJA_EN_COURS", "TACHE_ABSENTE", "SERVEUR_ABSENT", "ARRET_REFUSE",
    "ARRET_SANS_REPONSE"))
# Les causes de retour qui écartent la version : un défaut du paquet, pas une
# coupure de courant (D10).
CAUSES_ECARTEES = ("SANTE_MUETTE", "AUTO_CONTROLE_ECHOUE", "RETOUR_MANUEL")
VERSIONS_ECARTEES_MAX = 10

# Champs que technique.log peut recevoir, dans cet ordre.
CHAMPS_TRACE = ("code", "cause", "resultat", "de", "vers", "cles")

NOM_TACHE_SERVEUR = "BilanPosturo"

# Durées de production. Les fonctions les reçoivent en PARAMÈTRE : un test les
# réduit, et un autre lit ces constantes pour garantir qu'elles n'ont pas bougé.
DELAI_SANTE_SECONDES = 60
INTERVALLE_SANTE_SECONDES = 2
DELAI_AUTO_CONTROLE_SECONDES = 60
DELAI_REPONSE_ARRET_SECONDES = 30
DELAI_ARRET_SECONDES = 90
# Temps laissé à un serveur pour répondre à /sante AVANT toute demande d'arrêt.
DELAI_SERVEUR_PRESENT_SECONDES = 5
# Après l'arrêt concerté, le processus finit de quitter : un court répit avant de
# toucher aux fichiers et de relancer la tâche, qui ignore un /Run tant que
# l'instance précédente existe encore.
PAUSE_APRES_ARRET_SECONDES = 1
INTERVALLE_RELANCE_SECONDES = 5
CALME_SECONDES_DEFAUT = 120
TENTATIVES_RETOUR = 3
TENTATIVES_REMPLACEMENT = 5
PAUSE_REMPLACEMENT_SECONDES = 0.5

TAILLE_MAX_ARCHIVE = 64 * 1024 * 1024
TAILLE_MAX_SIGNATURE = 65
TAILLE_MAX_ETAT = 16 * 1024
TAILLE_MAX_REPONSE_ARRET = 1024
MARGE_ESPACE_OCTETS = 50 * 1024 * 1024
LONGUEUR_MAX_CHEMIN_ABSOLU = 259
TAILLE_BLOC = 1024 * 1024

# Noms internes du dossier réservé (le dossier lui-même est nommé dans serveur.py).
NOM_TELECHARGEMENT = "telechargement"
NOM_PREPARE = "prepare"
NOM_SAUVEGARDE = "sauvegarde"
NOM_SAUVEGARDE_NEUVE = "sauvegarde-neuve"
# Même longueur que « sauvegarde-neuve » : ses chemins comptent pour D7 au même titre.
NOM_SAUVEGARDE_AVANT = "sauvegarde-avant"
NOM_VERROU = "verrou"
NOM_INSTALLE = "installe.json"
NOM_INVENTAIRE = "inventaire.json"
# Suffixe du temporaire posé À CÔTÉ de sa destination (erratum 1 du contrat) :
# sous Windows, un fichier déplacé garde ses droits, et un temporaire né dans le
# dossier réservé arriverait sur serveur\ réservé à SYSTEM et aux administrateurs.
SUFFIXE_TEMPORAIRE = ".maj-tmp"

# Liste blanche des destinations (D6) : la barrière. Les exclusions plus bas sont
# la seconde.
PREFIXES_ADMIS = ("serveur/", "formulaire/", "docs/")
FICHIERS_RACINE_ADMIS = (
    "LICENSE", "TIERS.md", "LISEZMOI.txt", "READ-ME-FIRST.txt",
    "demarrer-serveur.bat", "installer-demarrage.ps1", "desinstaller-demarrage.ps1")
EXTENSIONS_REFUSEES = (".pem", ".key", ".crt", ".log")
CHEMINS_REFUSES = ("formulaire/images/cabinet", serveur.NOM_DOSSIER_MAJ)
PIECES_INDISPENSABLES = (
    "serveur/serveur.py", "serveur/maj.py", "serveur/paquet_signe.py",
    "serveur/signature_ed25519.py", "serveur/cles_publication.json",
    "formulaire/version.json", "formulaire/index.html", "formulaire/index-v1.html")
CHEMIN_CLES = "serveur/cles_publication.json"
CHEMIN_SCHEMA = "formulaire/schema.json"
CHEMIN_VERSION = paquet_signe.CHEMIN_VERSION

_CLIENT = re.compile(r"cabinet-[0-9]{2,}")
_HEXA64 = re.compile(r"[0-9a-f]{64}")


class Refus(Exception):
    """Refus motivé. `code` appartient à CODES_MAJ ou à paquet_signe.CODES ;
    `detail` est libre (il peut nommer un chemin) et ne va QUE dans journal.log
    et sur la console, jamais dans technique.log."""

    def __init__(self, code, detail=""):
        if code not in CODES_MAJ and code not in paquet_signe.CODES:
            raise ValueError("code de refus inconnu : %r" % (code,))
        Exception.__init__(self, "%s : %s" % (code, detail) if detail else code)
        self.code = code
        self.detail = detail


def _depuis_paquet(erreur):
    return Refus(erreur.code, erreur.detail)


# --------------------------------------------------------------------------
# Traces
# --------------------------------------------------------------------------

def _code_connu(code):
    if code in CODES_MAJ or code in paquet_signe.CODES:
        return code
    return "CODE_INCONNU"


def _version_pour_trace(version):
    try:
        paquet_signe.analyser_version(version)
    except paquet_signe.PaquetRefuse:
        return "inconnue"
    return version


def detail_maj(**champs):
    """Compose la ligne de technique.log : des champs fermés, rien d'autre.

    Refuse (ValueError) tout champ hors de CHAMPS_TRACE. Un code hors vocabulaire
    devient CODE_INCONNU, une version qui ne passe pas analyser_version devient
    « inconnue » : ni un chemin, ni une adresse, ni un texte d'erreur ne peut
    traverser cette fonction. Un champ valant None est omis."""
    inconnus = sorted(set(champs) - set(CHAMPS_TRACE))
    if inconnus:
        raise ValueError("champ de trace interdit : %s" % ", ".join(inconnus))
    morceaux = []
    for nom in CHAMPS_TRACE:
        valeur = champs.get(nom)
        if valeur is None:
            continue
        if nom in ("code", "cause"):
            valeur = _code_connu(valeur)
        elif nom in ("de", "vers"):
            valeur = _version_pour_trace(valeur)
        elif nom == "resultat":
            if valeur not in ("ok", "echec"):
                raise ValueError("resultat de trace interdit : %r" % (valeur,))
        elif nom == "cles":
            if valeur != "changees":
                raise ValueError("cles de trace interdit : %r" % (valeur,))
        morceaux.append("%s=%s" % (nom, valeur))
    return " ".join(morceaux)


def tracer(evenement, libre=None, **champs):
    """Écrit l'événement dans technique.log (champs fermés) et dans journal.log
    (même ligne, plus le détail libre en `!r`, pour le support sur place)."""
    serveur.journaliser_technique(evenement, detail_maj(**champs))
    ligne = "{} {} {}".format(
        datetime.datetime.now().isoformat(timespec="seconds"), evenement,
        detail_maj(**champs))
    if libre:
        ligne += " detail={!r}".format(libre)
    serveur.journaliser(ligne + "\n")


_GLOBALES_SERVEUR = ("CONFIG", "JOURNAL", "TECHNIQUE", "JOURNAL_TECHNIQUE_ACTIF",
                     "CONSERVATION_JOURNAUX_MOIS")


@contextlib.contextmanager
def contexte_serveur(racine):
    """Oriente les fonctions de journal et de configuration de serveur.py vers
    `racine`, puis restaure.

    serveur.py calcule ses chemins depuis son propre emplacement : sans cela, un
    essai sur un bac à sable écrirait dans les journaux du dépôt réel. Au cabinet
    les deux coïncident. Les deux interrupteurs sont posés comme demarrer()."""
    anciennes = dict((nom, getattr(serveur, nom)) for nom in _GLOBALES_SERVEUR)
    serveur.CONFIG = os.path.join(racine, "config.json")
    serveur.JOURNAL = os.path.join(racine, "journal.log")
    serveur.TECHNIQUE = os.path.join(racine, "technique.log")
    try:
        config = _config_brute()
        if config is not None:
            serveur.JOURNAL_TECHNIQUE_ACTIF = config["journal_technique"]
            serveur.CONSERVATION_JOURNAUX_MOIS = config["conservation_journaux_mois"]
        yield
    finally:
        for nom, valeur in anciennes.items():
            setattr(serveur, nom, valeur)


def _config_brute():
    try:
        return serveur.charger_config()
    except (OSError, ValueError, AttributeError):
        return None


# --------------------------------------------------------------------------
# Fichiers
# --------------------------------------------------------------------------

def dossier_maj(racine):
    return os.path.join(racine, serveur.NOM_DOSSIER_MAJ)


def chemin_maj(racine, *noms):
    return os.path.join(dossier_maj(racine), *noms)


def empreinte_fichier(chemin):
    """(taille, sha256 hexadécimal) du fichier, lu par blocs."""
    condensat = hashlib.sha256()
    taille = 0
    with open(chemin, "rb") as f:
        while True:
            bloc = f.read(TAILLE_BLOC)
            if not bloc:
                break
            condensat.update(bloc)
            taille += len(bloc)
    return taille, condensat.hexdigest()


def empreinte_si_present(chemin):
    """sha256 du fichier ordinaire, ou None s'il n'existe pas.

    Un lien, un dossier ou un tube à cet endroit lèvent Refus : ce n'est pas un
    fichier que l'on peut comparer, encore moins remplacer."""
    try:
        info = os.lstat(chemin)
    except FileNotFoundError:
        return None
    except OSError as erreur:
        raise Refus("DESTINATION_INVALIDE", "illisible : %r" % (erreur,))
    if not stat.S_ISREG(info.st_mode):
        raise Refus("DESTINATION_INVALIDE", "ni absent ni fichier ordinaire : %r" % (chemin,))
    return empreinte_fichier(chemin)[1]


def lire_borne(chemin, limite, code):
    """Les octets d'un fichier ORDINAIRE d'au plus `limite` octets.

    `lstat` avant `open` : ouvrir un tube nommé bloquerait. O_NONBLOCK pour la
    fenêtre entre les deux, et `fstat` sur le descripteur ouvert."""
    try:
        if not stat.S_ISREG(os.lstat(chemin).st_mode):
            raise Refus(code, "pas un fichier ordinaire : %r" % (chemin,))
        drapeaux = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
        descripteur = os.open(chemin, drapeaux)
    except OSError as erreur:
        raise Refus(code, "ouverture impossible : %r (%r)" % (chemin, erreur))
    with os.fdopen(descripteur, "rb") as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
            raise Refus(code, "pas un fichier ordinaire : %r" % (chemin,))
        octets = f.read(limite + 1)
    if len(octets) > limite:
        raise Refus(code, "plus de %d octets : %r" % (limite, chemin))
    return octets


def ecrire_exclusif(chemin, octets, mode=0o600):
    """Crée `chemin` sans jamais écraser (O_EXCL), contenu sur le disque."""
    drapeaux = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descripteur = os.open(chemin, drapeaux, mode)
    with os.fdopen(descripteur, "wb") as f:
        f.write(octets)
        f.flush()
        os.fsync(f.fileno())


def ecrire_json(chemin, objet):
    """Écriture atomique : temporaire, fsync, remplacement, repris si le
    remplacement est refusé. Le serveur relit etat.json (page /etat) : sous Windows,
    un remplacement pendant cette lecture échoue momentanément, et sans reprise une
    consultation de la page au mauvais instant ferait défaire une version saine."""
    corps = (json.dumps(objet, ensure_ascii=True, sort_keys=True, indent=2)
             + "\n").encode("utf-8")
    serveur.ecrire_atomiquement_patient(chemin, corps)


def lire_json(chemin, limite, code):
    octets = lire_borne(chemin, limite, code)
    try:
        return paquet_signe.lire_json_strict(octets, "MANIFESTE_MALFORME")
    except paquet_signe.PaquetRefuse as erreur:
        raise Refus(code, erreur.detail)


def vider_dossier(chemin):
    """Dossier existant et vide. Aucun lien n'est suivi (rmtree)."""
    try:
        if os.path.lexists(chemin):
            if os.path.islink(chemin) or not os.path.isdir(chemin):
                os.remove(chemin)
            else:
                shutil.rmtree(chemin)
        os.makedirs(chemin)
    except OSError as erreur:
        raise Refus("ECRITURE_IMPOSSIBLE", "dossier non vidable : %r" % (erreur,))


def creer_parents(base, relatif):
    """Crée les dossiers parents de `relatif` sous `base`, un segment à la fois,
    sans jamais traverser un lien."""
    courant = base
    for segment in relatif.split("/")[:-1]:
        courant = os.path.join(courant, segment)
        try:
            info = os.lstat(courant)
        except FileNotFoundError:
            os.mkdir(courant)
            continue
        if not stat.S_ISDIR(info.st_mode):
            raise Refus("DESTINATION_INVALIDE", "parent qui n'est pas un dossier : %r" % (courant,))


def effacer_pycache(racine):
    shutil.rmtree(os.path.join(racine, "serveur", "__pycache__"), ignore_errors=True)


def maintenant_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Dossier réservé et verrou
# --------------------------------------------------------------------------

# La lecture et l'analyse des droits sont écrites dans serveur.py, qui les utilise
# aussi pour décider d'obéir à une demande d'arrêt : une seule règle, deux usages.
# Les noms restent disponibles ici pour les tests et pour les lecteurs de ce module.
sddl_est_protege = serveur.sddl_est_protege
sids_en_trop = serveur.sids_en_trop
decoder_sortie_icacls = serveur.decoder_sortie_icacls
_systeme32 = serveur.chemin_systeme32
SID_SYSTEME = serveur.SID_SYSTEME
SID_ADMINISTRATEURS = serveur.SID_ADMINISTRATEURS


def _lancer_windows(arguments, delai=60):
    """Exécute un outil Windows par son chemin absolu, arguments en liste, jamais
    par un shell ; rend son code de sortie (la sortie est traduite selon la
    langue de Windows : seul le code compte)."""
    resultat = subprocess.run(
        arguments, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, timeout=delai,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return resultat.returncode


# SID absolus des abréviations SDDL que l'on retrouve sur un dossier neuf. Les
# autres abréviations (LA, LG…) dépendent de la machine : on retire alors le SID du
# compte qui exécute le client (_sid_de_l_utilisateur).
SID_DES_ABREVIATIONS = {
    "OW": "S-1-3-4", "CO": "S-1-3-0", "WD": "S-1-1-0", "BU": "S-1-5-32-545",
    "AU": "S-1-5-11", "IU": "S-1-5-4", "AN": "S-1-5-7", "NU": "S-1-5-2",
    "PU": "S-1-5-32-547", "RC": "S-1-5-12", "BG": "S-1-5-32-546",
}


def _sortie_windows(arguments, delai=60):
    """(code, sortie standard) d'un outil Windows lancé par son chemin absolu."""
    resultat = subprocess.run(
        arguments, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, timeout=delai,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return resultat.returncode, resultat.stdout


def _sid_de_l_utilisateur():
    """Le SID du compte qui exécute le client, par whoami (CSV : indépendant de la
    langue de Windows)."""
    code, sortie = _sortie_windows(
        [_systeme32("whoami.exe"), "/user", "/fo", "csv", "/nh"])
    correspondance = re.search(r"S-1-[0-9-]+", sortie.decode("utf-8", "replace"))
    if code != 0 or correspondance is None:
        raise Refus("DOSSIER_NON_PROTEGE", "compte courant introuvable")
    return correspondance.group(0)


def _lire_droits_windows(dossier):
    try:
        return serveur.lire_sddl_windows(dossier)
    except OSError as erreur:
        raise Refus("DOSSIER_NON_PROTEGE", "droits illisibles : %r" % (erreur,))


def _proteger_windows(dossier):
    """Réserve le dossier à SYSTEM et aux administrateurs, puis RELIT les droits.

    Dans l'ordre : propriétaire = Administrateurs (un dossier posé à l'avance par un
    utilisateur resterait à lui, et un propriétaire règle ses droits à sa guise) ;
    héritage coupé et deux entrées ; retrait de toute autre entrée (celle
    du créateur) ; relecture, qui exige exactement SY et BA."""
    icacls = _systeme32("icacls.exe")
    etapes = (
        [icacls, dossier, "/setowner", "*" + SID_ADMINISTRATEURS],
        # SID plutôt que des noms : « Système » et « Administrateurs » se traduisent.
        [icacls, dossier, "/inheritance:r", "/grant:r",
         "*%s:(OI)(CI)F" % SID_SYSTEME, "*%s:(OI)(CI)F" % SID_ADMINISTRATEURS],
    )
    for arguments in etapes:
        code = _lancer_windows(arguments)
        if code != 0:
            raise Refus("DOSSIER_NON_PROTEGE", "icacls a refusé %s (code %d)"
                        % (arguments[2], code))
    texte = _lire_droits_windows(dossier)
    for compte in sids_en_trop(texte):
        sid = SID_DES_ABREVIATIONS.get(compte)
        if sid is None:
            sid = compte if compte.startswith("S-1-") else _sid_de_l_utilisateur()
        code = _lancer_windows([icacls, dossier, "/remove:g", "*" + sid])
        if code != 0:
            raise Refus("DOSSIER_NON_PROTEGE", "retrait d'une entrée refusé (code %d)" % code)
        texte = _lire_droits_windows(dossier)
    protege, motif = sddl_est_protege(texte)
    if not protege:
        # Le début de ce qui a été lu aide le support à comprendre un format
        # inattendu ; il ne va que dans journal.log et sur la console.
        raise Refus("DOSSIER_NON_PROTEGE", "%s (lu : %r)" % (motif, texte[:160]))


def _proteger_posix(dossier):
    try:
        os.chmod(dossier, 0o700)
        info = os.stat(dossier)
    except OSError as erreur:
        raise Refus("DOSSIER_NON_PROTEGE", "droits non posés : %r" % (erreur,))
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise Refus("DOSSIER_NON_PROTEGE", "droits trop larges")
    if hasattr(os, "geteuid") and info.st_uid != os.geteuid():
        raise Refus("DOSSIER_NON_PROTEGE", "le dossier appartient à un autre compte")


def vider_contenu(dossier):
    """Efface tout ce que contient `dossier`, sans suivre de lien (un lien est
    retiré, jamais sa cible). Le dossier lui-même reste."""
    for nom in os.listdir(dossier):
        chemin = os.path.join(dossier, nom)
        info = os.lstat(chemin)
        if stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode):
            shutil.rmtree(chemin)
        else:
            os.remove(chemin)


def preparer_dossier_prive(racine):
    """Crée au besoin le dossier réservé, en contrôle les droits et le contenu (D4).

    Refuse un lien ou une jonction (le chemin résolu doit être celui attendu), et
    ce AVANT toute écriture ou tout effacement : vider un dossier atteint par une
    jonction détruirait ce qui se trouve ailleurs. Un dossier qui existe déjà sans
    être de confiance (propriétaire ou droits : `serveur.dossier_reserve_de_confiance`)
    a pu être rempli par n'importe qui avant la première protection : son contenu
    (un état « bascule », une sauvegarde de son choix) serait « restauré » par
    SYSTEM. Il est donc VIDÉ, puis protégé. Un dossier déjà de confiance garde son
    contenu : c'est l'état, la sauvegarde et le verrou des mises à jour précédentes.
    Enfin les droits sont posés et RELUS : un dossier hérité de l'utilisateur du
    cabinet laisserait n'importe quel programme de sa session déposer un paquet que
    SYSTEM installerait."""
    dossier = dossier_maj(racine)
    existait = True
    try:
        info = os.lstat(dossier)
    except FileNotFoundError:
        existait = False
        try:
            os.mkdir(dossier, 0o700)
        except OSError as erreur:
            raise Refus("ECRITURE_IMPOSSIBLE", "dossier non créé : %r" % (erreur,))
    except OSError as erreur:
        raise Refus("DOSSIER_NON_PROTEGE", "illisible : %r" % (erreur,))
    else:
        if not stat.S_ISDIR(info.st_mode):
            raise Refus("DOSSIER_NON_PROTEGE", "pas un dossier ordinaire")
    try:
        # L'attendu n'est pas résolu : le résoudre comme `reel` le détournerait de
        # la même façon qu'une jonction, et rien ne différerait jamais.
        attendu = serveur.forme_non_resolue(os.path.join(
            os.path.realpath(racine), serveur.NOM_DOSSIER_MAJ))
        reel = serveur.forme_comparable(dossier)
    except (OSError, ValueError) as erreur:
        raise Refus("DOSSIER_NON_PROTEGE", "illisible : %r" % (erreur,))
    if attendu != reel:
        raise Refus("DOSSIER_NON_PROTEGE", "lien ou jonction vers un autre dossier")
    if existait and not serveur.dossier_reserve_de_confiance(dossier):
        try:
            vider_contenu(dossier)
        except OSError as erreur:
            raise Refus("DOSSIER_NON_PROTEGE", "contenu non vidable : %r" % (erreur,))
    if os.name == "nt":
        _proteger_windows(dossier)
    else:
        _proteger_posix(dossier)
    if not serveur.dossier_reserve_de_confiance(dossier):
        raise Refus("DOSSIER_NON_PROTEGE", "le dossier n'est pas de confiance après protection")


@contextlib.contextmanager
def verrou(racine):
    """Verrou inter-processus, non bloquant, relâché par le système à la mort du
    processus (un verrou-fichier qu'il faudrait effacer resterait après une
    coupure). Verrou pris : DEJA_EN_COURS."""
    drapeaux = os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0)
    try:
        descripteur = os.open(chemin_maj(racine, NOM_VERROU), drapeaux, 0o600)
    except OSError as erreur:
        raise Refus("ECRITURE_IMPOSSIBLE", "verrou non ouvert : %r" % (erreur,))
    try:
        try:
            if os.name == "nt":
                os.lseek(descripteur, 0, 0)
                msvcrt.locking(descripteur, msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(descripteur, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise Refus("DEJA_EN_COURS", "une autre mise à jour est en cours")
        yield
    finally:
        os.close(descripteur)


# --------------------------------------------------------------------------
# État sur disque
# --------------------------------------------------------------------------

def etat_par_defaut():
    return {"format": 1, "etape": "repos", "resultat": None, "code": None,
            "le": None, "version": None, "de": None, "vers": None, "ecartees": []}


def _version_ou_none(valeur):
    return valeur is None or (isinstance(valeur, str)
                              and paquet_signe.MOTIF_VERSION.fullmatch(valeur) is not None)


def lire_etat(racine):
    """L'état de la mise à jour ; `repos` s'il n'a jamais été écrit.

    Strict : un état qu'on ne sait pas lire n'est jamais deviné (il pourrait dire
    « bascule » et commander un retour). ETAT_ILLISIBLE arrête alors tout."""
    chemin = chemin_maj(racine, serveur.ETAT_MAJ)
    if not os.path.lexists(chemin):
        return etat_par_defaut()
    contenu = lire_json(chemin, TAILLE_MAX_ETAT, "ETAT_ILLISIBLE")
    valide = (
        isinstance(contenu, dict)
        and contenu.get("etape") in serveur.ETAPES_MAJ
        and (contenu.get("resultat") is None or contenu["resultat"] in serveur.RESULTATS_MAJ)
        and (contenu.get("code") is None or (
            isinstance(contenu["code"], str)
            and serveur.MOTIF_CODE_MAJ.fullmatch(contenu["code"]) is not None))
        and (contenu.get("le") is None or (
            isinstance(contenu["le"], str)
            and serveur.MOTIF_HORODATAGE_MAJ.fullmatch(contenu["le"]) is not None))
        and all(_version_ou_none(contenu.get(cle)) for cle in ("version", "de", "vers"))
        and isinstance(contenu.get("ecartees", []), list)
        and len(contenu.get("ecartees", [])) <= VERSIONS_ECARTEES_MAX
        and all(_version_ou_none(v) and v is not None for v in contenu.get("ecartees", [])))
    if not valide:
        raise Refus("ETAT_ILLISIBLE", "etat.json hors de la forme attendue")
    etat = etat_par_defaut()
    for cle in etat:
        if cle in contenu:
            etat[cle] = contenu[cle]
    return etat


def ecrire_etat(racine, **champs):
    """Fusionne `champs` dans l'état et l'écrit atomiquement."""
    etat = lire_etat(racine)
    etat.update(champs)
    etat["le"] = maintenant_iso()
    ecrire_json(chemin_maj(racine, serveur.ETAT_MAJ), etat)
    return etat


def lire_installe(racine):
    """{"version", "fichiers": {relatif: sha256}} de la dernière mise à jour
    appliquée, ou None : la première version est posée à la main, et la première
    mise à jour n'efface donc rien."""
    chemin = chemin_maj(racine, NOM_INSTALLE)
    if not os.path.lexists(chemin):
        return None
    contenu = lire_json(chemin, 4 * 1024 * 1024, "ETAT_ILLISIBLE")
    if (not isinstance(contenu, dict) or set(contenu) != {"version", "fichiers"}
            or not isinstance(contenu["fichiers"], dict)):
        raise Refus("ETAT_ILLISIBLE", "installe.json hors de la forme attendue")
    for relatif, empreinte in contenu["fichiers"].items():
        if (not isinstance(empreinte, str) or _HEXA64.fullmatch(empreinte) is None
                or not chemin_admis(relatif)):
            raise Refus("ETAT_ILLISIBLE", "installe.json : entrée invalide")
    return contenu


# --------------------------------------------------------------------------
# Destinations
# --------------------------------------------------------------------------

def chemin_admis(relatif):
    """Vrai si le chemin (racine du paquet ôtée) est dans la liste blanche ET hors
    des exclusions. Sans accès au disque."""
    try:
        paquet_signe.valider_chemin(relatif)
    except paquet_signe.PaquetRefuse:
        return False
    if not (relatif.startswith(PREFIXES_ADMIS) or relatif in FICHIERS_RACINE_ADMIS):
        return False
    return not chemin_exclu(relatif)


def chemin_exclu(relatif):
    """Les exclusions, casse ignorée (D6) : seconde barrière derrière la liste
    blanche, qui est sensible à la casse."""
    bas = relatif.casefold()
    segments = bas.split("/")
    if "__pycache__" in segments or segments[-1] == "config.json":
        return True
    if bas.endswith(EXTENSIONS_REFUSEES) or bas.endswith(SUFFIXE_TEMPORAIRE):
        return True
    for refuse in CHEMINS_REFUSES:
        if bas == refuse or bas.startswith(refuse + "/"):
            return True
    return False


def formes_absolues(racine, relatif):
    """Les formes absolues d'un chemin que l'opération écrira (D7) : sa
    destination, son temporaire, sa copie extraite et sa copie sauvegardée."""
    segments = relatif.split("/")
    destination = os.path.join(racine, *segments)
    return [destination, destination + SUFFIXE_TEMPORAIRE,
            os.path.join(dossier_maj(racine), NOM_PREPARE, *segments),
            os.path.join(dossier_maj(racine), NOM_SAUVEGARDE_NEUVE, *segments)]


def controler_longueurs(racine, relatifs):
    """CHEMIN_TROP_LONG si une forme absolue dépasse 259 caractères, sur tous les
    systèmes : un paquet ne doit pas s'installer ici et échouer au cabinet.
    Pas de préfixe `\\\\?\\` : il change la sémantique des chemins."""
    for relatif in sorted(relatifs):
        for forme in formes_absolues(racine, relatif):
            if len(forme) > LONGUEUR_MAX_CHEMIN_ABSOLU:
                raise Refus("CHEMIN_TROP_LONG",
                            "%d caractères pour %r" % (len(forme), relatif))


def controler_destinations(racine, relatifs, dossier_pdf):
    """Liste blanche, exclusions, dossier des bilans, liens (D6)."""
    for relatif in sorted(relatifs):
        if not (relatif.startswith(PREFIXES_ADMIS) or relatif in FICHIERS_RACINE_ADMIS) \
                or chemin_exclu(relatif):
            raise Refus("CHEMIN_PROTEGE", "destination interdite : %r" % (relatif,))
    try:
        bilans = serveur.forme_comparable(dossier_pdf)
    except (OSError, ValueError) as erreur:
        raise Refus("CHEMIN_PROTEGE", "dossier des bilans illisible : %r" % (erreur,))
    for relatif in sorted(relatifs):
        destination = os.path.join(racine, *relatif.split("/"))
        try:
            sous_bilans = serveur.chemin_contient(
                bilans, serveur.forme_comparable(destination))
        except (OSError, ValueError):
            sous_bilans = True
        if sous_bilans:
            raise Refus("CHEMIN_PROTEGE", "sous le dossier des bilans : %r" % (relatif,))
        _, motif = serveur.confiner_sous_racine(relatif, racine)
        if motif is not None:
            raise Refus("DESTINATION_INVALIDE", "%s : %r" % (motif, relatif))
        empreinte_si_present(destination)


# --------------------------------------------------------------------------
# Configuration, clés, version installée
# --------------------------------------------------------------------------

def lire_reglages(racine):
    """(client, port, dossier des bilans absolu) d'après config.json."""
    config = _config_brute()
    bloc = config.get("mise_a_jour") if isinstance(config, dict) else None
    client = bloc.get("client") if isinstance(bloc, dict) else None
    if not isinstance(client, str) or _CLIENT.fullmatch(client) is None:
        raise Refus("CLIENT_NON_CONFIGURE",
                    "mise_a_jour.client absent ou invalide dans config.json")
    port = config.get("port")
    if type(port) is not int or not 1 <= port <= 65535:
        port = None
    dossier_pdf = config.get("dossier_pdf")
    if not isinstance(dossier_pdf, str) or not dossier_pdf:
        dossier_pdf = "bilans"
    if not os.path.isabs(dossier_pdf):
        dossier_pdf = os.path.join(racine, dossier_pdf)
    return client, port, dossier_pdf


def lire_cles_installees(racine):
    """Les clés de confiance DÉJÀ installées. Jamais un fichier de telechargement/
    ni de prepare/ : un paquet ne se donne pas confiance à lui-même (D5)."""
    chemin = os.path.join(racine, *CHEMIN_CLES.split("/"))
    if not os.path.lexists(chemin):
        raise Refus("CLES_ABSENTES", "serveur/cles_publication.json n'est pas installé")
    octets = lire_borne(chemin, paquet_signe.TAILLE_MAX_CLES, "CLES_ABSENTES")
    try:
        return paquet_signe.charger_cles_de_confiance(octets), octets
    except paquet_signe.PaquetRefuse as erreur:
        raise _depuis_paquet(erreur)


def lire_version_installee(racine):
    chemin = os.path.join(racine, *CHEMIN_VERSION.split("/"))
    try:
        contenu = lire_json(chemin, paquet_signe.TAILLE_MAX_VERSION,
                            "VERSION_INSTALLEE_ILLISIBLE")
        version = contenu.get("version") if isinstance(contenu, dict) else None
        paquet_signe.analyser_version(version)
    except paquet_signe.PaquetRefuse as erreur:
        raise Refus("VERSION_INSTALLEE_ILLISIBLE", erreur.detail)
    return version


# --------------------------------------------------------------------------
# Contrôles préalables, extraction, sauvegarde
# --------------------------------------------------------------------------

class Plan(object):
    """Ce qu'un paquet vérifié permet de faire : rien n'a encore été touché."""

    def __init__(self, racine, manifeste, installee, fichiers, client, port,
                 empreinte_cles):
        self.racine = racine
        self.manifeste = manifeste
        self.version = manifeste.version
        self.installee = installee
        # relatif -> (taille, sha256, nom dans l'archive)
        self.fichiers = fichiers
        self.client = client
        self.port = port
        self.empreinte_cles = empreinte_cles


def copier_le_trio(racine, chemin_archive):
    """Copie privée de l'archive, du manifeste et de la signature (étape 6.1).

    Tout ce qui suit lit la copie : l'archive d'origine peut changer sous nos
    pieds, la copie est dans un dossier que seuls SYSTEM et les administrateurs
    écrivent. Lecture bornée, fichiers ordinaires seulement."""
    origine = os.path.abspath(chemin_archive)
    dossier = chemin_maj(racine, NOM_TELECHARGEMENT)
    vider_dossier(dossier)
    sources = ((origine, "archive.zip", TAILLE_MAX_ARCHIVE, "ARCHIVE_ILLISIBLE"),
               (origine + paquet_signe.SUFFIXE_MANIFESTE, "manifeste.json",
                paquet_signe.TAILLE_MAX_MANIFESTE, "MANIFESTE_MALFORME"),
               (origine + paquet_signe.SUFFIXE_SIGNATURE, "signature.sig",
                TAILLE_MAX_SIGNATURE, "SIGNATURE_INVALIDE"))
    copies = {}
    for source, nom, limite, code in sources:
        octets = lire_borne(source, limite, code)
        try:
            ecrire_exclusif(os.path.join(dossier, nom), octets)
        except OSError as erreur:
            raise Refus("ECRITURE_IMPOSSIBLE", "copie impossible : %r" % (erreur,))
        copies[nom] = octets if nom != "archive.zip" else None
    return (os.path.join(dossier, "archive.zip"), copies["manifeste.json"],
            copies["signature.sig"])


def espace_libre(racine):
    return shutil.disk_usage(racine).free


def controler(racine, chemin_archive):
    """Les contrôles préalables, dans l'ordre du contrat (étape 6). N'écrit rien
    hors de mise-a-jour/. Rend un Plan ou lève Refus."""
    copie, manifeste_octets, signature = copier_le_trio(racine, chemin_archive)
    client, port, dossier_pdf = lire_reglages(racine)
    cles, octets_cles = lire_cles_installees(racine)
    installee = lire_version_installee(racine)
    try:
        manifeste = paquet_signe.verifier_paquet(
            copie, manifeste_octets, signature, cles, installee, client)
    except paquet_signe.PaquetRefuse as erreur:
        raise _depuis_paquet(erreur)

    etat = lire_etat(racine)
    if manifeste.version in etat["ecartees"]:
        raise Refus("VERSION_ECARTEE", "cette version est revenue en arrière une fois")

    fichiers = {}
    for nom, (taille, empreinte) in manifeste.fichiers.items():
        if "/" not in nom:
            raise Refus("DESTINATION_INVALIDE", "fichier hors du dossier du paquet")
        fichiers[nom.split("/", 1)[1]] = (taille, empreinte, nom)
    manquantes = [p for p in PIECES_INDISPENSABLES if p not in fichiers]
    if manquantes:
        raise Refus("PAQUET_INCOMPLET", "pièce manquante : %s" % manquantes[0])

    controler_destinations(racine, fichiers, dossier_pdf)
    controler_longueurs(racine, fichiers)

    installe = lire_installe(racine)
    if installe is not None and CHEMIN_SCHEMA in fichiers \
            and CHEMIN_SCHEMA in installe["fichiers"]:
        sur_disque = empreinte_si_present(os.path.join(racine, *CHEMIN_SCHEMA.split("/")))
        if sur_disque is not None and sur_disque != installe["fichiers"][CHEMIN_SCHEMA]:
            raise Refus("SCHEMA_MODIFIE_LOCALEMENT",
                        "formulaire/schema.json a été retouché sur place")

    besoin = 3 * sum(taille for taille, _, _ in fichiers.values()) + MARGE_ESPACE_OCTETS
    if espace_libre(racine) < besoin:
        raise Refus("ESPACE_INSUFFISANT", "%d octets nécessaires" % besoin)
    return Plan(racine, manifeste, installee, fichiers, client, port,
                hashlib.sha256(octets_cles).hexdigest())


def extraire(plan):
    """Extrait dans mise-a-jour/prepare/, tout ou rien (étape 7).

    Jamais extract ni extractall : le chemin de destination est reconstruit
    segment par segment depuis un nom déjà validé, le fichier est créé en O_EXCL,
    lu à taille + 1 octets au plus, puis RELU sur le disque et comparé au
    manifeste. En cas d'erreur, prepare/ est vidé : rien d'autre n'a été touché."""
    prepare = chemin_maj(plan.racine, NOM_PREPARE)
    vider_dossier(prepare)
    try:
        with zipfile.ZipFile(chemin_maj(plan.racine, NOM_TELECHARGEMENT, "archive.zip")) as archive:
            for relatif in sorted(plan.fichiers):
                taille, empreinte, nom = plan.fichiers[relatif]
                paquet_signe.valider_chemin(nom)
                info = archive.getinfo(nom)
                if info.orig_filename != nom:
                    raise Refus("EXTRACTION_ALTEREE", "nom d'entrée modifié")
                creer_parents(prepare, relatif)
                destination = os.path.join(prepare, *relatif.split("/"))
                drapeaux = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
                with archive.open(info) as flux, \
                        os.fdopen(os.open(destination, drapeaux, 0o600), "wb") as sortie:
                    lus = 0
                    while lus < taille + 1:
                        bloc = flux.read(min(TAILLE_BLOC, taille + 1 - lus))
                        if not bloc:
                            break
                        sortie.write(bloc)
                        lus += len(bloc)
                    sortie.flush()
                    os.fsync(sortie.fileno())
                if lus != taille:
                    raise Refus("EXTRACTION_ALTEREE", "taille écrite différente : %r" % (relatif,))
                # La relecture est ce qui compte : ce qui est sur le disque, pas
                # ce qui est passé dans le flux.
                if empreinte_fichier(destination) != (taille, empreinte):
                    raise Refus("EXTRACTION_ALTEREE", "contenu écrit différent : %r" % (relatif,))
    except (Refus, paquet_signe.PaquetRefuse, KeyError, OSError) as erreur:
        shutil.rmtree(prepare, ignore_errors=True)
        os.makedirs(prepare, exist_ok=True)
        if isinstance(erreur, Refus):
            raise
        raise Refus("EXTRACTION_ALTEREE", "extraction impossible : %r" % (erreur,))
    except paquet_signe.ERREURS_ZIP as erreur:
        shutil.rmtree(prepare, ignore_errors=True)
        os.makedirs(prepare, exist_ok=True)
        raise Refus("EXTRACTION_ALTEREE", "archive illisible : %r" % (erreur,))
    ecrire_etat(plan.racine, etape="preparee", de=plan.installee, vers=plan.version)


def copier_verifie(source, destination, empreinte_attendue, code, mode=0o600):
    """Copie `source` vers `destination` (créée, jamais écrasée) en calculant
    l'empreinte de ce qui est écrit ; écart : Refus(code), destination effacée."""
    condensat = hashlib.sha256()
    drapeaux = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        with open(source, "rb") as entree, \
                os.fdopen(os.open(destination, drapeaux, mode), "wb") as sortie:
            while True:
                bloc = entree.read(TAILLE_BLOC)
                if not bloc:
                    break
                condensat.update(bloc)
                sortie.write(bloc)
            sortie.flush()
            os.fsync(sortie.fileno())
    except OSError as erreur:
        _effacer_si_present(destination)
        raise Refus("ECRITURE_IMPOSSIBLE", "copie impossible : %r" % (erreur,))
    if condensat.hexdigest() != empreinte_attendue:
        _effacer_si_present(destination)
        raise Refus(code, "empreinte différente de celle attendue : %r" % (source,))


def _effacer_si_present(chemin):
    try:
        os.remove(chemin)
    except OSError:
        pass


def preparer_sauvegarde(plan):
    """Bâtit et vérifie la sauvegarde de ce que la mise à jour va toucher (étape 8),
    dans `sauvegarde-neuve/`, SANS toucher à la sauvegarde existante.

    Ensemble : les chemins du nouveau manifeste, réunis à ceux d'installe.json.
    Chaque fichier présent est COPIÉ (jamais déplacé), relu et haché. Un défaut se
    dit ici, avant tout arrêt du serveur. La substitution est `adopter_sauvegarde`,
    qui n'a lieu qu'une fois l'arrêt accepté."""
    racine = plan.racine
    installe = lire_installe(racine)
    ensemble = set(plan.fichiers)
    if installe is not None:
        ensemble.update(installe["fichiers"])
    neuve = chemin_maj(racine, NOM_SAUVEGARDE_NEUVE)
    vider_dossier(neuve)
    presents, absents = {}, []
    try:
        for relatif in sorted(ensemble):
            source = os.path.join(racine, *relatif.split("/"))
            empreinte = empreinte_si_present(source)
            if empreinte is None:
                if relatif in plan.fichiers:
                    absents.append(relatif)
                continue
            creer_parents(neuve, relatif)
            copier_verifie(source, os.path.join(neuve, *relatif.split("/")),
                           empreinte, "SAUVEGARDE_ALTEREE")
            presents[relatif] = empreinte
        a_un_installe = installe is not None
        if a_un_installe:
            octets = lire_borne(chemin_maj(racine, NOM_INSTALLE), 4 * 1024 * 1024, "ETAT_ILLISIBLE")
            ecrire_exclusif(os.path.join(neuve, NOM_INSTALLE), octets)
        ecrire_json(os.path.join(neuve, NOM_INVENTAIRE), {
            "format": 1, "de": plan.installee, "vers": plan.version,
            "installe": a_un_installe, "presents": presents, "absents": absents})
        # Relecture de ce qui vient d'être sauvegardé, avant tout arrêt du serveur.
        for relatif, empreinte in presents.items():
            if empreinte_fichier(os.path.join(neuve, *relatif.split("/")))[1] != empreinte:
                raise Refus("SAUVEGARDE_ALTEREE", "copie différente : %r" % (relatif,))
    except OSError as erreur:
        shutil.rmtree(neuve, ignore_errors=True)
        raise Refus("ECRITURE_IMPOSSIBLE", "sauvegarde impossible : %r" % (erreur,))
    except Refus:
        shutil.rmtree(neuve, ignore_errors=True)
        raise


def adopter_sauvegarde(racine):
    """Substitue la sauvegarde bâtie à la sauvegarde courante.

    Appelée une fois l'arrêt ACCEPTÉ, jamais avant : la sauvegarde courante est ce
    qui permet de revenir de la version installée, et une tentative refusée ou
    reportée ne doit pas la détruire. Une seule sauvegarde est gardée. L'ancienne
    est écartée par un renommage (et non effacée d'abord) : si la substitution
    échoue, elle est remise en place."""
    neuve = chemin_maj(racine, NOM_SAUVEGARDE_NEUVE)
    courante = chemin_maj(racine, NOM_SAUVEGARDE)
    avant = chemin_maj(racine, NOM_SAUVEGARDE_AVANT)
    try:
        shutil.rmtree(avant, ignore_errors=True)
        if os.path.lexists(courante):
            os.replace(courante, avant)
        try:
            os.replace(neuve, courante)
        except OSError:
            if os.path.lexists(avant) and not os.path.lexists(courante):
                os.replace(avant, courante)
            raise
    except OSError as erreur:
        raise Refus("ECRITURE_IMPOSSIBLE", "sauvegarde non substituée : %r" % (erreur,))
    shutil.rmtree(avant, ignore_errors=True)


def sauvegarder(plan):
    """Bâtit puis adopte la sauvegarde : les deux temps d'un seul geste, pour les
    appelants qui n'ont pas d'arrêt à attendre (essais)."""
    preparer_sauvegarde(plan)
    adopter_sauvegarde(plan.racine)


def lire_inventaire(racine):
    chemin = chemin_maj(racine, NOM_SAUVEGARDE, NOM_INVENTAIRE)
    if not os.path.lexists(chemin):
        raise Refus("RETOUR_IMPOSSIBLE", "aucune sauvegarde")
    contenu = lire_json(chemin, 4 * 1024 * 1024, "SAUVEGARDE_ALTEREE")
    valide = (isinstance(contenu, dict)
              and set(contenu) == {"format", "de", "vers", "installe", "presents", "absents"}
              and isinstance(contenu["presents"], dict)
              and isinstance(contenu["absents"], list)
              and isinstance(contenu["installe"], bool)
              and all(chemin_admis(r) and isinstance(e, str) and _HEXA64.fullmatch(e)
                      for r, e in contenu["presents"].items())
              and all(isinstance(r, str) and chemin_admis(r) for r in contenu["absents"]))
    if not valide:
        raise Refus("SAUVEGARDE_ALTEREE", "inventaire hors de la forme attendue")
    return contenu


# --------------------------------------------------------------------------
# Pose des fichiers (bascule et retour)
# --------------------------------------------------------------------------

def remplacer(source, destination):
    """os.replace avec cinq tentatives : un antivirus tient parfois le fichier
    quelques centaines de millisecondes sous Windows."""
    for essai in range(TENTATIVES_REMPLACEMENT):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if essai == TENTATIVES_REMPLACEMENT - 1:
                raise
            time.sleep(PAUSE_REMPLACEMENT_SECONDES)


def poser_fichiers(racine, source, attendus, code):
    """Pose chaque fichier de `attendus` (relatif -> sha256) depuis `source`.

    IDEMPOTENT : un fichier déjà à la bonne empreinte n'est pas touché, si bien
    que rejouer l'opération depuis n'importe quel point converge, et qu'une
    reprise ne refait que ce qui reste. Le temporaire naît À CÔTÉ de sa
    destination (même volume, mêmes droits héritables), puis os.replace. Rend le
    nombre de fichiers remplacés."""
    remplaces = 0
    for relatif in sorted(attendus):
        destination = os.path.join(racine, *relatif.split("/"))
        if empreinte_si_present(destination) == attendus[relatif]:
            continue
        creer_parents(racine, relatif)
        temporaire = destination + SUFFIXE_TEMPORAIRE
        _effacer_si_present(temporaire)
        mode = 0o644
        if os.path.lexists(destination):
            mode = stat.S_IMODE(os.lstat(destination).st_mode)
        copier_verifie(os.path.join(source, *relatif.split("/")), temporaire,
                       attendus[relatif], code, mode=mode)
        try:
            os.chmod(temporaire, mode)
        except OSError:
            pass
        remplacer(temporaire, destination)
        remplaces += 1
    return remplaces


def effacer_temporaires(racine, relatifs):
    for relatif in relatifs:
        _effacer_si_present(os.path.join(racine, *relatif.split("/")) + SUFFIXE_TEMPORAIRE)


# --------------------------------------------------------------------------
# Pilote du serveur
# --------------------------------------------------------------------------

class PiloteTachePlanifiee(object):
    """Démarre et arrête le serveur par sa tâche planifiée Windows.

    schtasks.exe par son chemin absolu, jugé par son CODE DE SORTIE seul (sa sortie
    est traduite selon la langue de Windows). Interface minimale : existe(),
    demarrer(), arreter_de_force(), partagée avec le pilote d'essai des tests."""

    def __init__(self, nom=NOM_TACHE_SERVEUR):
        self.nom = nom

    def _schtasks(self, *arguments):
        return _lancer_windows([_systeme32("schtasks.exe")] + list(arguments))

    def existe(self):
        return self._schtasks("/Query", "/TN", self.nom) == 0

    def demarrer(self):
        if self._schtasks("/Run", "/TN", self.nom) != 0:
            raise Refus("TACHE_ABSENTE", "la tâche du serveur ne démarre pas")

    def arreter_de_force(self):
        """Seul usage de l'arrêt forcé : la version en place est celle qui vient
        d'échouer, ou la reprise suit une coupure. Un code non nul (rien à
        arrêter) n'est pas une erreur."""
        return self._schtasks("/End", "/TN", self.nom) == 0


def _pilote_requis(pilote):
    if pilote is None or not pilote.existe():
        raise Refus("TACHE_ABSENTE", "pas de tâche planifiée du serveur sur ce poste")
    return pilote


# --------------------------------------------------------------------------
# Santé
# --------------------------------------------------------------------------

def sante_repond(port, delai_connexion=3):
    """Vrai si GET /sante répond 200 avec EXACTEMENT {"etat":"ok"}.

    Par la boucle locale, en TLS sans vérification du certificat (D14) : le
    certificat du cabinet couvre son adresse sur le réseau, pas 127.0.0.1. La
    sonde n'envoie aucun identifiant et ne lit qu'un corps fixe.

    Elle ne prouve pas QUI répond : pendant que le serveur est arrêté (la bascule),
    n'importe quel processus local peut écouter sur ce port, sans être
    administrateur. L'effet se limite à tromper ce verdict de santé (l'auto-contrôle
    tourne quand même, et rien ne sort) ; le contrat le dit à l'erratum 12."""
    if port is None:
        return False
    contexte = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    contexte.check_hostname = False
    contexte.verify_mode = ssl.CERT_NONE
    contexte.minimum_version = ssl.TLSVersion.TLSv1_2
    connexion = http.client.HTTPSConnection(
        "127.0.0.1", port, timeout=delai_connexion, context=contexte)
    try:
        connexion.request("GET", "/sante", headers={"Connection": "close"})
        reponse = connexion.getresponse()
        corps = reponse.read(64)
        return reponse.status == 200 and corps == b'{"etat":"ok"}'
    except (OSError, http.client.HTTPException):
        return False
    finally:
        connexion.close()


def attendre_sante(port, delai, intervalle=INTERVALLE_SANTE_SECONDES, relancer=None,
                   intervalle_relance=INTERVALLE_RELANCE_SECONDES):
    """Attend que /sante réponde, au plus `delai` secondes.

    `relancer` : une fonction rappelée toutes les `intervalle_relance` secondes
    tant que la sonde reste muette. La tâche du serveur est en « IgnoreNew » : un
    /Run lancé alors que l'instance précédente finit de quitter est ignoré SANS
    erreur. Relancer à intervalle est inoffensif (une instance qui tourne ignore
    la demande) et rattrape ce cas ; un serveur qui ne démarre vraiment pas reste
    muet jusqu'au bout.

    Le filet n'interrompt JAMAIS l'attente : le verdict reste celui de la sonde. Un
    /Run sur une tâche déjà en marche (un serveur lent à démarrer : antivirus,
    premier import de Python) peut rendre un code non nul, que `demarrer` traduit en
    TACHE_ABSENTE ; laissé s'échapper, il ferait défaire une version saine, et userait
    les trois tentatives d'un retour. Toute erreur de `relancer` est donc avalée."""
    debut = time.monotonic()
    limite = debut + delai
    prochaine_relance = debut + intervalle_relance
    while True:
        if sante_repond(port):
            return True
        maintenant = time.monotonic()
        if maintenant >= limite:
            return False
        if relancer is not None and maintenant >= prochaine_relance:
            try:
                relancer()
            except Exception:
                pass
            prochaine_relance = maintenant + intervalle_relance
        time.sleep(min(intervalle, max(0.0, limite - time.monotonic())))


def port_ferme(port):
    """Vrai si plus rien n'écoute sur 127.0.0.1:port (connexion refusée)."""
    try:
        socket.create_connection(("127.0.0.1", port), 1).close()
    except OSError:
        return True
    return False


# --------------------------------------------------------------------------
# Arrêt concerté
# --------------------------------------------------------------------------

def _lire_reponse_arret(racine, jeton):
    chemin = chemin_maj(racine, serveur.REPONSE_ARRET)
    try:
        contenu = lire_json(chemin, TAILLE_MAX_REPONSE_ARRET, "ARRET_SANS_REPONSE")
    except Refus:
        return None
    if (isinstance(contenu, dict) and contenu.get("jeton") == jeton
            and isinstance(contenu.get("verdict"), str)
            and isinstance(contenu.get("motif"), str)):
        return contenu
    return None


def demander_arret(racine, port, calme_secondes, demarrage,
                   delai_reponse=DELAI_REPONSE_ARRET_SECONDES,
                   delai_arret=DELAI_ARRET_SECONDES, acceptation=None):
    """Demande au serveur de s'arrêter ; c'est LUI qui décide (D9).

    Aucun arrêt forcé ici (D16). Refus du serveur : ARRET_REFUSE. Pas de réponse :
    ARRET_SANS_REPONSE, et le serveur tourne peut-être encore : on n'y touche pas.

    `acceptation` (un dict) reçoit `accepte = True` dès que le serveur a accepté :
    à partir de là il quitte avec le code 0, que la tâche planifiée ne relance pas,
    et TOUTE sortie de l'appelant doit passer par `assurer_serveur`."""
    jeton = secrets.token_hex(16)
    demande = chemin_maj(racine, serveur.DEMANDE_ARRET)
    _effacer_si_present(chemin_maj(racine, serveur.REPONSE_ARRET))
    ecrire_json(demande, {"jeton": jeton, "calme_secondes": int(calme_secondes),
                          "demarrage": bool(demarrage)})
    limite = time.monotonic() + delai_reponse
    reponse = None
    while reponse is None and time.monotonic() < limite:
        reponse = _lire_reponse_arret(racine, jeton)
        if reponse is None:
            time.sleep(0.05)
    if reponse is None:
        _effacer_si_present(demande)
        raise Refus("ARRET_SANS_REPONSE", "le serveur n'a pas répondu")
    if reponse["verdict"] == "refuse":
        raise Refus("ARRET_REFUSE", "motif : %s" % reponse["motif"][:40])
    if acceptation is not None:
        acceptation["accepte"] = True
    limite = time.monotonic() + delai_arret
    while time.monotonic() < limite:
        reponse = _lire_reponse_arret(racine, jeton)
        if reponse is not None and reponse["verdict"] == "arrete" and port_ferme(port):
            time.sleep(PAUSE_APRES_ARRET_SECONDES)
            return
        time.sleep(0.05)
    raise Refus("ARRET_SANS_REPONSE", "le serveur ne s'est pas arrêté à temps")


def assurer_serveur(pilote, port, delai_sante, delai_fermeture=10):
    """Relance le serveur qui a accepté l'arrêt, et vérifie /sante. Rend le verdict.

    Le serveur est sorti en code 0 : la tâche planifiée (`-RestartCount`) ne relance
    que sur échec. Si le client abandonne après l'acceptation (arrêt jamais
    confirmé, exception, console fermée), personne d'autre ne le fera. On attend
    d'abord que le port soit fermé : un serveur qui finit de quitter répondrait
    encore une fois à /sante et ferait croire à tort qu'il tourne. `/Run` d'une
    tâche déjà en marche est sans effet. Aucune levée : c'est un filet."""
    try:
        limite = time.monotonic() + delai_fermeture
        while not port_ferme(port) and time.monotonic() < limite:
            time.sleep(0.2)
        pilote.demarrer()
        sain = attendre_sante(port, delai_sante, relancer=pilote.demarrer)
    except Exception:
        sain = False
    try:
        serveur.journaliser("{} relance du serveur après abandon de la mise à jour : {}\n"
                            .format(maintenant_iso(), "sante ok" if sain else "SANTE MUETTE"))
    except Exception:
        pass
    return sain


# --------------------------------------------------------------------------
# Retour arrière
# --------------------------------------------------------------------------

def _restaurer(racine, pilote, port, delai_sante):
    """Une tentative de retour. Idempotente : rejouée depuis n'importe quel point."""
    inventaire = lire_inventaire(racine)
    pilote.arreter_de_force()
    sauvegarde = chemin_maj(racine, NOM_SAUVEGARDE)
    poser_fichiers(racine, sauvegarde, inventaire["presents"], "SAUVEGARDE_ALTEREE")
    for relatif in inventaire["absents"]:
        destination = os.path.join(racine, *relatif.split("/"))
        if os.path.lexists(destination):
            os.remove(destination)
    effacer_temporaires(racine, list(inventaire["presents"]) + list(inventaire["absents"]))
    installe = chemin_maj(racine, NOM_INSTALLE)
    if inventaire["installe"]:
        octets = lire_borne(os.path.join(sauvegarde, NOM_INSTALLE), 4 * 1024 * 1024,
                            "SAUVEGARDE_ALTEREE")
        serveur.ecrire_atomiquement_patient(installe, octets)
    else:
        _effacer_si_present(installe)
    effacer_pycache(racine)
    # La tâche a pu relancer la version cassée entre-temps.
    pilote.arreter_de_force()
    pilote.demarrer()
    if not attendre_sante(port, delai_sante, relancer=pilote.demarrer):
        raise Refus("SANTE_MUETTE", "le serveur restauré ne répond pas")


def revenir_a_la_sauvegarde(racine, pilote, port, cause, delai_sante=DELAI_SANTE_SECONDES,
                            tentatives=TENTATIVES_RETOUR):
    """Remet l'installation dans l'état de la sauvegarde. Rend True si le retour a
    abouti.

    Après `tentatives` échecs dans le même passage : etat « echec-retour »,
    démarrage du serveur tenté quand même, trace resultat=echec."""
    etat = lire_etat(racine)
    de, vers = etat["de"], etat["vers"]
    champs = {"etape": "retour", "code": cause}
    if cause in CAUSES_ECARTEES and vers is not None:
        ecartees = [v for v in etat["ecartees"] if v != vers] + [vers]
        champs["ecartees"] = ecartees[-VERSIONS_ECARTEES_MAX:]
    ecrire_etat(racine, **champs)
    derniere = None
    for _ in range(tentatives):
        try:
            _restaurer(racine, pilote, port, delai_sante)
            derniere = None
            break
        except Exception as erreur:
            derniere = erreur
    if derniere is not None:
        ecrire_etat(racine, etape="echec-retour", resultat=None, code=cause)
        try:
            pilote.demarrer()
        except Exception:
            pass
        tracer("MAJ_RETOUR", libre=repr(derniere), cause=cause, resultat="echec",
               de=de, vers=vers)
        return False
    ecrire_etat(racine, etape="repos", resultat="revenue", code=cause, version=vers)
    tracer("MAJ_RETOUR", cause=cause, resultat="ok", de=de, vers=vers)
    return True


def reprendre(racine, pilote, port, delai_sante=DELAI_SANTE_SECONDES):
    """Termine ce qu'une coupure a laissé : bascule, vérification, retour ou
    échec de retour reviennent à la sauvegarde (cause INTERROMPUE). La version
    n'est PAS écartée : une coupure n'est pas un défaut du paquet. Rend False si
    le retour échoue encore."""
    etat = lire_etat(racine)
    if etat["etape"] in ("repos", "preparee"):
        return True
    _pilote_requis(pilote)
    return revenir_a_la_sauvegarde(racine, pilote, port, "INTERROMPUE", delai_sante)


# --------------------------------------------------------------------------
# Application
# --------------------------------------------------------------------------

def lancer_auto_controle(racine, delai):
    """Lance le client NEUF sur la version neuve (D11) : un client cassé ne
    pourrait plus jamais installer de correctif, et ne se répare pas par une mise
    à jour. Code 0 exigé."""
    try:
        resultat = subprocess.run(
            [sys.executable, "-B", os.path.join(racine, "serveur", "maj.py"),
             "auto-controle"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=delai, cwd=racine,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired):
        raise Refus("AUTO_CONTROLE_ECHOUE", "le nouveau client ne s'exécute pas")
    if resultat.returncode != 0:
        raise Refus("AUTO_CONTROLE_ECHOUE", "code de sortie %d" % resultat.returncode)


def ecrire_installe(plan):
    ecrire_json(chemin_maj(plan.racine, NOM_INSTALLE), {
        "version": plan.version,
        "fichiers": dict((r, v[1]) for r, v in plan.fichiers.items())})


def empreinte_des_cles(racine):
    try:
        return empreinte_fichier(os.path.join(racine, *CHEMIN_CLES.split("/")))[1]
    except OSError:
        return None


def basculer(plan, pilote, delai_sante, delai_auto_controle):
    """Étape 11 : remplace les fichiers, relance, juge. Tout échec défait."""
    racine = plan.racine
    prepare = chemin_maj(racine, NOM_PREPARE)
    try:
        # Dans le try : un état qui ne s'écrit pas ne doit pas laisser le serveur
        # arrêté (il l'est déjà, et la tâche ne le relancera pas).
        ecrire_etat(racine, etape="bascule", de=plan.installee, vers=plan.version)
        poser_fichiers(racine, prepare,
                       dict((r, v[1]) for r, v in plan.fichiers.items()),
                       "EXTRACTION_ALTEREE")
        installe = lire_installe(racine)
        if installe is not None:
            for relatif in sorted(set(installe["fichiers"]) - set(plan.fichiers)):
                destination = os.path.join(racine, *relatif.split("/"))
                if chemin_admis(relatif) and os.path.lexists(destination):
                    os.remove(destination)
        effacer_pycache(racine)
        ecrire_etat(racine, etape="verification")
        pilote.demarrer()
        if not attendre_sante(plan.port, delai_sante, relancer=pilote.demarrer):
            raise Refus("SANTE_MUETTE", "/sante ne répond pas après la bascule")
        lancer_auto_controle(racine, delai_auto_controle)
        cles = ("changees" if empreinte_des_cles(racine) != plan.empreinte_cles else None)
        ecrire_installe(plan)
        vider_dossier(prepare)
        vider_dossier(chemin_maj(racine, NOM_TELECHARGEMENT))
        ecrire_etat(racine, etape="repos", resultat="appliquee", code=None,
                    version=plan.version)
        tracer("MAJ_APPLIQUEE", de=plan.installee, vers=plan.version, cles=cles)
        return 0
    except KeyboardInterrupt:
        revenir_a_la_sauvegarde(racine, pilote, plan.port, "INTERROMPUE", delai_sante)
        raise
    except Exception as erreur:
        if isinstance(erreur, Refus):
            cause, libre = erreur.code, erreur.detail
        elif isinstance(erreur, OSError):
            cause, libre = "ECRITURE_IMPOSSIBLE", repr(erreur)
        else:
            cause, libre = "CODE_INCONNU", repr(erreur)
        tracer("MAJ_REFUSEE", libre=libre, code=cause)
        revenir_a_la_sauvegarde(racine, pilote, plan.port, cause, delai_sante)
        return 1


def _signaler_refus(racine, erreur, ecrire):
    evenement = "MAJ_REPORTEE" if erreur.code in CODES_REPORT else "MAJ_REFUSEE"
    tracer(evenement, libre=erreur.detail, code=erreur.code)
    if ecrire:
        try:
            ecrire_etat(racine,
                        resultat="reportee" if erreur.code in CODES_REPORT else "refusee",
                        code=erreur.code)
        except (Refus, OSError):
            pass
    print("%s : %s" % (erreur.code, erreur.detail))
    return 3 if erreur.code in CODES_REPORT else 1


def executer(racine, travail):
    """Dossier réservé, verrou, puis `travail()` ; tout Refus devient une trace
    et un code de sortie."""
    try:
        preparer_dossier_prive(racine)
        with verrou(racine):
            try:
                return travail()
            except Refus as erreur:
                return _signaler_refus(racine, erreur, True)
    except Refus as erreur:
        return _signaler_refus(racine, erreur, False)


def appliquer_trio(racine, chemin_archive, pilote, port, calme_secondes, demarrage,
                   delai_sante, delai_auto_controle, delai_reponse, delai_arret):
    """Contrôles, extraction, sauvegarde, arrêt concerté, bascule : tout ce qui suit
    la reprise, pour un trio (archive, manifeste, signature) posé à côté de
    `chemin_archive`. Rend le code de sortie ; lève Refus.

    Appelée verrou pris, dossier réservé protégé et reprise faite : par `appliquer`
    (archive posée à la main) et par `verifier` (archive téléchargée). Le verrou
    n'est pas réentrant, d'où cette fonction plutôt qu'un second appel d'`appliquer`.
    `port` est celui que l'appelant a lu pour la reprise ; le plan relit le sien."""
    plan = controler(racine, chemin_archive)
    acceptation = {"accepte": False}
    try:
        extraire(plan)
        preparer_sauvegarde(plan)
        _pilote_requis(pilote)
        if not attendre_sante(plan.port, DELAI_SERVEUR_PRESENT_SECONDES, 0.5):
            raise Refus("SERVEUR_ABSENT", "le serveur ne répond pas : rien n'est mis à jour")
        demander_arret(racine, plan.port, calme_secondes, demarrage,
                       delai_reponse, delai_arret, acceptation)
        # Seulement maintenant : la sauvegarde courante est celle qui permet de
        # revenir de la version installée.
        adopter_sauvegarde(racine)
        return basculer(plan, pilote, delai_sante, delai_auto_controle)
    except BaseException:
        # Toute sortie postérieure à une acceptation relance le serveur : il a
        # quitté en code 0, la tâche planifiée ne le fera pas. (basculer relance
        # lui-même dans tous ses chemins ; ce filet couvre ce qui l'entoure.)
        if acceptation["accepte"]:
            assurer_serveur(pilote, plan.port, delai_sante)
        raise
    finally:
        shutil.rmtree(chemin_maj(racine, NOM_SAUVEGARDE_NEUVE), ignore_errors=True)


def appliquer(racine, chemin_archive, pilote, calme_secondes=CALME_SECONDES_DEFAUT,
              demarrage=False, delai_sante=DELAI_SANTE_SECONDES,
              delai_auto_controle=DELAI_AUTO_CONTROLE_SECONDES,
              delai_reponse=DELAI_REPONSE_ARRET_SECONDES,
              delai_arret=DELAI_ARRET_SECONDES):
    """Installe un paquet signé. Rend le code de sortie."""
    racine = os.path.realpath(racine)

    def travail():
        port = _port_configure(racine)
        if not reprendre(racine, pilote, port, delai_sante):
            raise Refus("RETOUR_IMPOSSIBLE", "le retour arrière précédent a échoué")
        return appliquer_trio(racine, chemin_archive, pilote, port, calme_secondes,
                              demarrage, delai_sante, delai_auto_controle,
                              delai_reponse, delai_arret)

    with contexte_serveur(racine):
        return executer(racine, travail)


def _port_configure(racine):
    config = _config_brute()
    port = config.get("port") if isinstance(config, dict) else None
    return port if type(port) is int and 1 <= port <= 65535 else None


def revenir(racine, pilote, delai_sante=DELAI_SANTE_SECONDES):
    """Défait la dernière mise à jour appliquée (séance d'assistance). La version
    quittée est écartée."""
    racine = os.path.realpath(racine)

    def travail():
        port = _port_configure(racine)
        if not reprendre(racine, pilote, port, delai_sante):
            raise Refus("RETOUR_IMPOSSIBLE", "le retour arrière précédent a échoué")
        inventaire = lire_inventaire(racine)
        # Une tentative abandonnée après avoir bâti sa sauvegarde ne doit pas
        # faire « revenir » à ce qui est déjà installé.
        if lire_version_installee(racine) != inventaire["vers"]:
            raise Refus("RETOUR_IMPOSSIBLE",
                        "la sauvegarde ne correspond pas à la version installée")
        _pilote_requis(pilote)
        ecrire_etat(racine, de=inventaire["de"], vers=inventaire["vers"])
        if revenir_a_la_sauvegarde(racine, pilote, port, "RETOUR_MANUEL", delai_sante):
            shutil.rmtree(chemin_maj(racine, NOM_SAUVEGARDE), ignore_errors=True)
            print("Version %s remise en place." % inventaire["de"])
            return 0
        return 1

    with contexte_serveur(racine):
        return executer(racine, travail)


def reprendre_commande(racine, pilote, delai_sante=DELAI_SANTE_SECONDES):
    racine = os.path.realpath(racine)

    def travail():
        if not reprendre(racine, pilote, _port_configure(racine), delai_sante):
            raise Refus("RETOUR_IMPOSSIBLE", "le retour arrière a échoué")
        print("Rien à reprendre." if lire_etat(racine)["resultat"] != "revenue"
              else "Mise à jour défaite.")
        return 0

    with contexte_serveur(racine):
        return executer(racine, travail)


def etat_commande(racine):
    """Imprime l'étape, le dernier résultat, le code, les versions. Lecture seule :
    ni verrou, ni reprise, ni écriture."""
    racine = os.path.realpath(racine)
    try:
        etat = lire_etat(racine)
    except Refus as erreur:
        print("%s : %s" % (erreur.code, erreur.detail))
        return 1
    try:
        installee = lire_version_installee(racine)
    except Refus:
        installee = "inconnue"
    print("Étape : %s" % etat["etape"])
    print("Dernier résultat : %s" % (etat["resultat"] or "aucun"))
    print("Code : %s" % (etat["code"] or "aucun"))
    print("Version installée : %s" % installee)
    print("Versions écartées : %s" % (", ".join(etat["ecartees"]) or "aucune"))
    return 0


def auto_controle(racine):
    """Le client se charge et ses entrées se lisent : configuration, clés
    installées, version installée. Ne touche à rien, n'écrit aucun journal.

    Lancé par le client qui vient d'appliquer le paquet, PENDANT que celui-ci
    tient le verrou : il ne le prend donc pas, et ne reprend rien."""
    racine = os.path.realpath(racine)
    with contexte_serveur(racine):
        try:
            lire_reglages(racine)
            lire_cles_installees(racine)
            lire_version_installee(racine)
        except Refus as erreur:
            print("Auto-contrôle échoué : %s" % erreur.code)
            return 1
    if not callable(signature_ed25519.verifier) \
            or set(CODES_MAJ) & set(paquet_signe.CODES):
        print("Auto-contrôle échoué : vocabulaire incohérent")
        return 1
    print("Auto-contrôle réussi.")
    return 0


# --------------------------------------------------------------------------
# Ligne de commande
# --------------------------------------------------------------------------

def construire_analyseur():
    analyseur = argparse.ArgumentParser(
        prog="maj.py", description="Client de mise à jour du serveur du bilan posturologique.")
    sous = analyseur.add_subparsers(dest="commande")
    sous.required = True
    appliquer_ = sous.add_parser(
        "appliquer", help="installe un paquet signé (archive + manifeste + signature)")
    appliquer_.add_argument("archive", help="l'archive .zip ; son manifeste et sa signature sont à côté")
    appliquer_.add_argument("--calme-minutes", type=int, default=CALME_SECONDES_DEFAUT // 60,
                            help="minutes sans requête exigées du serveur avant l'arrêt (défaut : 2)")
    sous.add_parser("revenir", help="défait la dernière mise à jour appliquée")
    sous.add_parser("reprendre", help="termine ou défait une mise à jour interrompue")
    sous.add_parser("etat", help="dit où en est la mise à jour")
    sous.add_parser("auto-controle", help="contrôle que ce client se charge (usage interne)")
    return analyseur


def main(argv=None, racine=None, pilote=None):
    analyseur = construire_analyseur()
    arguments = analyseur.parse_args(argv)
    racine = os.path.realpath(RACINE if racine is None else racine)
    # Garde-fou de développement, avant tout autre geste : sur un dépôt Git, ce
    # client agirait sur les fichiers réels du cabinet présents à la racine.
    if os.path.lexists(os.path.join(racine, ".git")):
        print("Refus : %s contient un dossier .git. Ce client ne s'exécute que "
              "dans une installation, jamais dans un dépôt de développement."
              % racine)
        return 2
    if pilote is None and os.name == "nt":
        pilote = PiloteTachePlanifiee()
    if arguments.commande == "appliquer":
        if not 0 <= arguments.calme_minutes <= 1440:
            print("--calme-minutes : entre 0 et 1440.")
            return 2
        return appliquer(racine, arguments.archive, pilote,
                         calme_secondes=arguments.calme_minutes * 60)
    if arguments.commande == "revenir":
        return revenir(racine, pilote)
    if arguments.commande == "reprendre":
        return reprendre_commande(racine, pilote)
    if arguments.commande == "etat":
        return etat_commande(racine)
    return auto_controle(racine)


if __name__ == "__main__":
    sys.exit(main())
