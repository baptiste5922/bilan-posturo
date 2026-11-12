#!/usr/bin/env python3
"""
Serveur du bilan posturologique.

Trois rôles :
  1. servir le formulaire, qui vit dans formulaire/ ;
  2. recevoir les PDF générés sur la tablette et les écrire dans le dossier
     patient du PC (route POST /depot) ;
  3. protéger l'ensemble par un mot de passe et par TLS, tous deux
     obligatoires : sans certificat, le serveur refuse de démarrer.

N'utilise que la bibliothèque standard : rien à installer au cabinet.
Le certificat, lui, se fabrique avec generer_autorite.py.

    python3 serveur/generer_autorite.py 192.168.1.13   # certificat, une fois
    python3 serveur/serveur.py --config                # identifiant, mot de passe
    python3 serveur/serveur.py                         # démarrage
"""

import argparse
import base64
import binascii
import datetime
import getpass
import hashlib
import hmac
import html
import ipaddress
import json
import os
import re
import secrets
import shutil
import socket
import socketserver
import ssl
import stat
import sys
import tempfile
import threading
import time
import unicodedata
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

# Module voisin, bibliothèque standard seule : le serveur lui emprunte la forme
# d'un numéro de version et la lecture JSON stricte (C5-T2a), pour que ni la page
# d'état ni la demande d'arrêt ne lisent autrement que le client de mise à jour.
import paquet_signe

# Le script vit dans serveur/ : la racine du projet est le dossier parent.
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(RACINE, "config.json")
JOURNAL = os.path.join(RACINE, "journal.log")
# Journal technique : non identifiant par construction (C4-T1). Il coexiste
# avec JOURNAL, qui reste nominatif et ne quitte jamais le cabinet.
TECHNIQUE = os.path.join(RACINE, "technique.log")

# Racine web : elle ne contient que le formulaire. Ni config.json, ni les
# clés privées, ni le code Python n'y figurent, si bien qu'aucune requête ne
# peut les atteindre même si le filtre d'extensions venait à être contourné.
FORMULAIRE = os.path.join(RACINE, "formulaire")

# Source unique du numéro de version (C4-T4) : le formulaire la lit par la
# même route que schema.json, le serveur la lit ici au démarrage, et
# tests/test_version.py échoue si package.json en diverge.
FICHIER_VERSION = os.path.join(FORMULAIRE, "version.json")
VERSION_INCONNUE = "inconnue"


def lire_version(chemin=FICHIER_VERSION):
    """Le numéro de version, ou "inconnue" — jamais une levée.

    Un fichier absent, illisible ou malformé ne doit pas empêcher le cabinet
    de démarrer. Le numéro est restreint à [0-9A-Za-z.+-] : il part dans
    technique.log, le journal qui circule, et rien d'autre qu'un numéro ne
    doit pouvoir y entrer par ce chemin.
    """
    try:
        with open(chemin, encoding="utf-8") as f:
            version = json.load(f).get("version")
    except (OSError, ValueError, AttributeError):
        return VERSION_INCONNUE
    if isinstance(version, str) and re.fullmatch(r"[0-9A-Za-z.+-]{1,32}", version):
        return version
    return VERSION_INCONNUE

TAILLE_MAX = 30 * 1024 * 1024      # 30 Mo : un bilan pèse ~1 à 3 Mo
ITERATIONS = 240_000               # coût du hachage PBKDF2

# Le serveur tourne désormais en service, donc en continu : sans rotation, le
# journal croîtrait indéfiniment. 5 Mo représentent environ 40 000 requêtes.
JOURNAL_TAILLE_MAX = 5 * 1024 * 1024
JOURNAL_ARCHIVES = 3

# Durée de conservation des deux journaux (C4-T2). Un cabinet qui fait une
# cinquantaine de requêtes par jour met plus de deux ans à remplir 5 Mo : la
# taille seule ne borne donc pas la durée. Un mois vaut 30 jours, écrit ici
# une seule fois : la rotation mensuelle et la purge s'en dérivent toutes
# deux, jamais d'un calendrier (un mois de calendrier varie de 28 à 31 jours).
JOURS_PAR_MOIS = 30
CONSERVATION_MOIS_DEFAUT = 6
CONSERVATION_MOIS_MAX = 120
# Une archive est purgée quand sa première ligne a plus de N mois MOINS ce
# délai, et la purge est revérifiée à l'écriture au plus à cet intervalle
# (D3 bis). Les deux sont liés : la première ligne était, à la vérification
# précédente, plus jeune que le seuil ; elle ne peut donc pas avoir dépassé N
# mois à la suivante. Une constante, pour ne pas les désaccorder.
PURGE_INTERVALLE = datetime.timedelta(days=1)
# Fil de purge périodique (voir boucle_purge_periodique) : il tient la promesse
# « au plus N mois » même quand plus rien ne s'écrit. Son intervalle doit rester
# inférieur à PURGE_INTERVALLE, sans quoi l'avance d'un jour ne couvre plus
# l'attente entre deux tours (un test le vérifie).
PURGE_PERIODIQUE_SECONDES = 6 * 3600
# Positionné depuis la configuration dans demarrer(). Toujours relu via
# conservation_mois(), qui le revalide : une valeur absurde ne lève jamais.
CONSERVATION_JOURNAUX_MOIS = CONSERVATION_MOIS_DEFAUT

# Vocabulaire fermé du journal technique : la source dont les tests se
# dérivent, jamais recopiée. Un nom d'événement hors de cet ensemble devient
# "EVENEMENT_INCONNU" plutôt que de lever (journaliser_technique).
EVENEMENTS_TECHNIQUES = frozenset({
    "DEMARRAGE", "ARRET", "TLS_REFUSE", "AUTH_REFUSEE",
    "REPONSE", "DEPOT", "ECHEC_ECRITURE", "ROTATION", "LOGO",
    "DEMARRAGE_REFUSE",
    # Mise à jour (C5-T2a). MAJ_CONTROLE ne sert qu'en C5-T2b : déclaré ici pour
    # ne toucher le vocabulaire qu'une fois. Aucun n'est préfixe d'un autre.
    "MAJ_REFUSEE", "MAJ_REPORTEE", "MAJ_APPLIQUEE", "MAJ_RETOUR", "MAJ_CONTROLE",
})

# ROTATION échappe de nécessité à journaliser_technique() (interblocage
# certain : le verrou n'est pas réentrant), donc à la garde qui ne relève
# que les appels littéraux à cette fonction. Le libellé se dérive ici une
# seule fois, jamais retranscrit au site d'écriture
# (_ajouter_ligne_technique, plus bas) : constat d'audit C4-T1.
EVENEMENT_ROTATION = "ROTATION"
if EVENEMENT_ROTATION not in EVENEMENTS_TECHNIQUES:
    # Levée explicite, jamais `assert` : sous python -O, un `assert` nu au
    # niveau du module disparaîtrait aussi silencieusement qu'ailleurs, et
    # ce lien ne serait plus vérifié du tout (constat d'audit C4-T1).
    raise AssertionError(
        "EVENEMENT_ROTATION ({!r}) doit appartenir à EVENEMENTS_TECHNIQUES"
        .format(EVENEMENT_ROTATION))

# Classes de route fermées : jamais un chemin brut, contrôlé par le client,
# n'atteint le journal technique (décision D3). "cabinet" (C2-T1, décision
# D5) permet de distinguer, à distance, « la tablette n'a jamais demandé
# l'identité » de « elle l'a demandée et a reçu 401 ». "etat" (C4-T3) fait de
# même pour la page de diagnostic.
ROUTES_TECHNIQUES = frozenset({"depot", "sante", "formulaire", "cabinet", "etat", "autre"})

# Caractères de contrôle échappés dans les journaux : C0, DEL et C1, la table
# de CPython 3.12 sans la barre oblique inverse. Échappée, elle doublerait chaque
# séparateur des chemins Windows de la ligne ECHEC ecriture et rendrait le
# journal illisible pour le support (C6-T5, D9).
ECHAPPEMENT_CONTROLE = str.maketrans({
    c: "\\x{:02x}".format(c) for c in list(range(0x20)) + list(range(0x7f, 0xa0))})

# Motifs de refus de dépôt, fermés eux aussi : un motif hors de cet ensemble
# devient "motif-inconnu" (detail_refus_depot).
MOTIFS_REFUS_DEPOT = frozenset({
    "content-length-invalide", "corps-vide", "trop-volumineux",
    "transfert-interrompu", "non-pdf",
})

# Interrupteur de retour arrière (étape 8) : à False, le journal technique
# n'est jamais écrit. Positionné depuis la configuration dans demarrer().
JOURNAL_TECHNIQUE_ACTIF = True

# Page d'état (C4-T3) : la liste fermée des informations, dans l'ordre où
# la page les présente. Source dont les tests se dérivent, jamais recopiée ;
# C3-T2 y ajoutera son champ le jour venu.
CLES_ETAT = (
    "version", "demarre_le", "dernier_depot", "disque_libre_octets",
    "certificat_expire_le", "certificat_empreinte", "certificat_adresse",
    "identite_cabinet",
    "maj_etape", "maj_resultat", "maj_code", "maj_le", "maj_version",
    "journal_technique",
)
# Les seuls champs dont la valeur est un horodatage : les tests anti-adresse
# en font l'exception exprimable, car « 12:34:56 » ressemble à une adresse
# IPv6 pour le motif laxiste.
CHAMPS_ETAT_HORODATES = frozenset({
    "demarre_le", "dernier_depot", "certificat_expire_le", "maj_le"})
if not CHAMPS_ETAT_HORODATES <= set(CLES_ETAT):
    # Levée explicite, jamais `assert` (voir EVENEMENT_ROTATION plus haut).
    raise AssertionError(
        "CHAMPS_ETAT_HORODATES doit être inclus dans CLES_ETAT")
# Verdict de concordance entre le certificat chargé et les adresses du PC :
# jamais une adresse, seulement un de ces trois mots (décision n°1, voie A).
VERDICTS_ADRESSE = frozenset({"conforme", "adresse changée", "indéterminé"})
# Bornes de la lecture de technique.log par la page : une page qui circule
# n'a pas besoin de plus, et la lecture reste de durée constante.
LIGNES_ETAT = 30
QUEUE_ETAT_OCTETS = 64 * 1024
# Sous ce nombre de jours restants, la page ajoute « à renouveler ».
JOURS_CERTIFICAT_A_RENOUVELER = 30

# Mise à jour (C5-T2a). Le dossier est nommé UNE fois ici : maj.py le reprend
# par import, et le serveur n'y crée jamais rien (il est réservé à SYSTEM et aux
# administrateurs par maj.py ; un serveur qui le créerait en hériterait les droits
# de la racine). Il y lit l'état de la mise à jour et y répond à une demande
# d'arrêt.
NOM_DOSSIER_MAJ = "mise-a-jour"
DOSSIER_MAJ = os.path.join(RACINE, NOM_DOSSIER_MAJ)
ETAT_MAJ = "etat.json"
DEMANDE_ARRET = "arret.demande"
REPONSE_ARRET = "arret.reponse"
# Vocabulaire fermé de l'état de la mise à jour, dont les tests se dérivent.
ETAPES_MAJ = ("repos", "preparee", "bascule", "verification", "retour",
              "echec-retour")
RESULTATS_MAJ = ("appliquee", "revenue", "refusee", "reportee")
# Ce que /etat dit quand le fichier manque ou ne se lit pas : jamais une valeur
# recopiée du fichier.
ETAPE_MAJ_ABSENTE = "absente"
ETAPE_MAJ_ILLISIBLE = "illisible"
TAILLE_MAX_ETAT_MAJ = 16 * 1024
TAILLE_MAX_DEMANDE_ARRET = 1024
# Au-delà, la demande d'arrêt « au démarrage » est refusée (D9 du contrat C5-T2).
DELAI_DEMARRAGE_MAX_SECONDES = 900
CALME_MAX_SECONDES = 86400
# Le serveur sonde le dossier toutes les secondes ; attend au plus 30 s qu'un
# dépôt déjà commencé s'achève avant de quitter.
INTERVALLE_SURVEILLANCE_SECONDES = 1.0
DELAI_FIN_DEPOTS_SECONDES = 30
MOTIFS_ARRET = ("aucun", "depot-en-cours", "activite", "demarrage-depasse",
                "demande-invalide")
_JETON_ARRET = re.compile(r"[0-9a-f]{32}")
_CODE_MAJ = re.compile(r"[A-Z_]{1,40}")
_HORODATAGE_MAJ = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}")

# État du processus lu par la page d'état. Posés dans demarrer() ; None tant
# qu'il n'a pas tourné (tests unitaires).
VERSION_EN_COURS = None
DEMARRE_LE = None
# En mémoire seulement (D7) : perdu au redémarrage, sans fichier d'état.
DERNIER_DEPOT = None
# Ce que le serveur a CHARGÉ au démarrage (D6) : un fichier remplacé sans
# redémarrage ne doit pas faire mentir la page sur ce qui est servi.
CERTIFICAT_CHARGE = None

# Ce que la demande d'arrêt concerté lit (C5-T2a) : un compte de dépôts en cours
# et l'heure de la dernière requête qui n'est pas la sonde de santé. Sous un
# verrou PROPRE : _verrou_journal n'est valable que pour les journaux, et la
# fonction qui incrémente ne doit jamais attendre une rotation.
_verrou_compteurs = threading.Lock()
DEPOTS_EN_COURS = 0
DERNIERE_ACTIVITE = None      # time.monotonic() de la dernière requête, ou None
DEMARRE_MONOTONIC = None      # time.monotonic() du démarrage, posé dans demarrer()

# Seuls ces fichiers sont servis. Le filtre double la séparation des dossiers :
# même si la racine web venait à contenir autre chose, rien d'autre ne sortirait.
# .json y figure pour schema.json (moteur de rendu, C1-T3) : la racine web ne
# contient que le formulaire, et config.json vit un niveau au-dessus (RACINE,
# pas FORMULAIRE) — inatteignable même maintenant que l'extension est servie.
EXTENSIONS_SERVIES = {".html", ".css", ".js", ".json", ".png", ".jpg", ".jpeg", ".svg", ".ico"}

# Logo du cabinet (C2-T2). PNG et JPEG seulement : le SVG est un contenu actif
# et html2canvas le rend mal, l'ICO n'est pas un logo. Un sous-ensemble de
# EXTENSIONS_SERVIES, jamais un élargissement du filtre : le logo est servi par
# le gestionnaire statique, sous ses deux barrières habituelles.
EXTENSIONS_LOGO = frozenset({".png", ".jpg", ".jpeg"})
if not EXTENSIONS_LOGO <= EXTENSIONS_SERVIES:
    # Levée explicite, jamais `assert` (voir EVENEMENT_ROTATION plus haut).
    raise AssertionError(
        "EXTENSIONS_LOGO doit être incluse dans EXTENSIONS_SERVIES")
# Les huit premiers octets d'un vrai fichier de cette extension : un fichier
# renommé en .png (page HTML, archive) n'est pas proposé à la tablette.
SIGNATURES_LOGO = {
    ".png": b"\x89PNG\r\n\x1a\n",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
}
if set(SIGNATURES_LOGO) != EXTENSIONS_LOGO:
    raise AssertionError(
        "SIGNATURES_LOGO doit couvrir exactement EXTENSIONS_LOGO")
# Le logo s'affiche en 130 x 130 px : au-delà, c'est une photo mal exportée qui
# ralentit html2canvas sur la tablette.
LOGO_TAILLE_MAX = 512 * 1024
# Motifs de refus du logo, fermés comme MOTIFS_REFUS_DEPOT : ce sont les seules
# valeurs qui atteignent technique.log (le chemin, lui, est une saisie libre).
MOTIFS_REFUS_LOGO = frozenset({
    "hors-racine", "forme-invalide", "extension-non-servie", "lien-symbolique",
    "absent", "trop-volumineux", "illisible",
})

# Motifs de refus de démarrer quand la racine web englobe le cabinet (C6-T7),
# fermés comme MOTIFS_REFUS_LOGO : seules valeurs qui atteignent technique.log,
# les chemins de l'installation n'y entrent jamais.
MOTIFS_REFUS_DEMARRAGE = frozenset({
    "racine-cabinet", "dossier-pdf", "indetermine",
})

CONFIG_DEFAUT = {
    "port": 8000,
    "dossier_pdf": "bilans",
    "utilisateur": "cabinet",
    "mot_de_passe": "",
    "certificat": "certificat.pem",
    "cle_privee": "cle.pem",
    "journal_technique": True,
    # Page de diagnostic GET /etat (C4-T3). Retour arrière niveau 1 : à false,
    # la route retombe exactement dans le comportement d'avant la tâche (401
    # sans identifiants, 403 avec). Seul `true` l'active : une fonction
    # facultative échoue fermée.
    "page_etat": True,
    # Durée de conservation des deux journaux, en mois de 30 jours (C4-T2).
    "conservation_journaux_mois": CONSERVATION_MOIS_DEFAUT,
    # Identité du cabinet (C2-T1) : chaînes vides par défaut, jamais un
    # exemple générique — un exemple finit tôt ou tard imprimé sur un bilan
    # réel (décision D3 du contrat). Sert à remplir l'en-tête du formulaire
    # via GET /cabinet, et à nommer le fichier PDF (convention_nommage).
    "cabinet": {
        "nom": "",
        "praticien": "",
        "adresse": "",
        "courriel": "",
        "telephone": "",
        "logo": "images/favicon.jpeg",
        "convention_nommage": "Bilan_{date}_{patient}",
    },
}

# Dérivée de CONFIG_DEFAUT, jamais retranscrite : la route /cabinet, la
# saisie de --config et les tests s'appuient tous sur cette même liste
# (piège « une liste normative recopiée finit fausse »).
CLES_CABINET = tuple(CONFIG_DEFAUT["cabinet"])


# --------------------------------------------------------------------------
# Configuration et mots de passe
# --------------------------------------------------------------------------

def normaliser_conservation_mois(valeur):
    """Rend la durée de conservation si c'est un entier de 1 à
    CONSERVATION_MOIS_MAX, sinon la valeur par défaut, sans jamais lever.

    Un booléen est écarté explicitement : en Python, True est un entier, et
    `"conservation_journaux_mois": true` donnerait un mois de conservation.
    Des `if` plutôt que des `assert`, qui s'évaporeraient sous python -O.
    """
    if isinstance(valeur, bool) or not isinstance(valeur, int):
        return CONSERVATION_MOIS_DEFAUT
    if valeur < 1 or valeur > CONSERVATION_MOIS_MAX:
        return CONSERVATION_MOIS_DEFAUT
    return valeur


def charger_config():
    if not os.path.exists(CONFIG):
        return None
    with open(CONFIG, encoding="utf-8") as f:
        config = json.load(f)
    complet = dict(CONFIG_DEFAUT)
    complet.update(config)

    # Fusion à deux niveaux pour la seule clé "cabinet" : une fusion de
    # surface écraserait un bloc partiel au lieu de le compléter clé à clé,
    # ce qui romprait tout config.json d'un cabinet déjà installé avant
    # cette version. Aucune levée : un "cabinet" absent, null, ou qui n'est
    # pas un dictionnaire retombe simplement sur les défauts. Une sous-clé
    # qui n'est pas une chaîne (null, nombre, objet, écrits à la main) y
    # retombe aussi : sinon demarrer() lève sur .strip() et le cabinet ne
    # redémarre plus après la réparation manuelle que la doc conseille.
    cabinet = dict(CONFIG_DEFAUT["cabinet"])
    brut = config.get("cabinet")
    if isinstance(brut, dict):
        for cle in CLES_CABINET:
            if isinstance(brut.get(cle), str):
                cabinet[cle] = brut[cle]
    complet["cabinet"] = cabinet

    # Même tolérance que pour « cabinet » : une valeur écrite à la main qui
    # n'est pas un entier de 1 à 120 retombe sur 6 au lieu d'empêcher le
    # démarrage.
    complet["conservation_journaux_mois"] = normaliser_conservation_mois(
        complet.get("conservation_journaux_mois"))

    return complet


def hacher(mot_de_passe, sel=None, iterations=ITERATIONS):
    """Hachage PBKDF2-SHA256. Le mot de passe n'est jamais stocké en clair."""
    if sel is None:
        sel = secrets.token_bytes(16)
    empreinte = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode("utf-8"),
                                    sel, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations, sel.hex(), empreinte.hex())


def verifier_mot_de_passe(mot_de_passe, stocke):
    """Comparaison à temps constant : ne renseigne pas sur le nombre de
    caractères corrects, contrairement à un == classique."""
    try:
        algo, iterations, sel_hex, attendu_hex = stocke.split("$")
        if algo != "pbkdf2_sha256":
            return False
        candidat = hashlib.pbkdf2_hmac(
            "sha256", mot_de_passe.encode("utf-8"),
            bytes.fromhex(sel_hex), int(iterations))
        return hmac.compare_digest(candidat.hex(), attendu_hex)
    except (ValueError, binascii.Error):
        return False


# --------------------------------------------------------------------------
# Logo du cabinet (C2-T2)
# --------------------------------------------------------------------------

# Alphabet admis d'un chemin de logo : segments de lettres, chiffres, « _ », « - »
# et « . » (jamais en tête), séparés par « / ». Tout le reste est refusé d'un
# bloc : schéma d'URL (« : »), « //hôte », « % », « ? », « # », « \ » (donc
# aussi les flux alternatifs NTFS et les noms courts), espaces, accents et
# caractères de contrôle. Une liste blanche, parce que ce chemin finit dans un
# attribut `src` côté tablette.
FORME_CHEMIN_LOGO = re.compile(
    r"(?:[A-Za-z0-9_-][A-Za-z0-9._-]*/)*[A-Za-z0-9_-][A-Za-z0-9._-]*")

# Emplacement admis d'un logo (constat d'audit C2-T2) : un seul niveau sous
# images/cabinet/, le dossier que Git ignore et que faire-paquet.sh refuse
# d'emballer — ou exactement le logo par défaut, dérivé de CONFIG_DEFAUT et
# jamais recopié. Un logo client posé ailleurs sous formulaire/ serait servi,
# non ignoré, et emballé pour le client suivant.
LOGO_PAR_DEFAUT = CONFIG_DEFAUT["cabinet"]["logo"]
FORME_LOGO_CLIENT = re.compile(
    r"images/cabinet/[A-Za-z0-9_-][A-Za-z0-9._-]*")


def forme_logo(chemin):
    """Rend le motif de refus d'un chemin de logo d'après sa seule forme, ou
    None. Purement textuelle : aucun accès au système de fichiers.

    Première des deux couches (la seconde est confiner_logo, qui tient même si
    celle-ci était un jour assouplie). Une chaîne et pas autre chose : les deux
    séparateurs sont examinés, que le chemin ait été saisi sous Windows ou non.
    """
    if not isinstance(chemin, str):
        return "forme-invalide"
    if (".." in chemin.replace("\\", "/").split("/")
            or chemin.startswith(("/", "\\"))
            or re.match(r"[A-Za-z]:", chemin)
            or os.path.isabs(chemin)):
        return "hors-racine"
    if not FORME_CHEMIN_LOGO.fullmatch(chemin):
        return "forme-invalide"
    if os.path.splitext(chemin)[1].lower() not in EXTENSIONS_LOGO:
        return "extension-non-servie"
    if chemin != LOGO_PAR_DEFAUT and not FORME_LOGO_CLIENT.fullmatch(chemin):
        return "forme-invalide"
    return None


def confiner_sous_racine(chemin, racine_web, tolerer_casse=False):
    """Rend (chemin_absolu, None) si le chemin, résolu pour de bon, reste sous
    racine_web sans passer par aucun lien, sinon ("", motif).

    Sert au logo (C2-T2) et au gestionnaire statique (C6-T6). Suppose la forme
    déjà validée mais ne s'y fie pas : c'est la seconde couche, qui regarde le
    disque. Tout lien symbolique est refusé, même vers l'intérieur (décision
    D5) ; la comparaison des chemins résolus tient aussi contre une jonction
    Windows, que islink() ne voit pas avant Python 3.12. Aucune exception ne
    sort.

    tolerer_casse : sous Windows, realpath rend la casse du disque. Une casse
    seule n'est pas un lien : par défaut (le logo, geste d'installation qui se
    corrige à froid) le chemin est refusé comme « absent ». Le service statique
    la tolère, parce que Windows sert aujourd'hui /Index.html et qu'une page
    blanche en consultation n'achète aucune sécurité ; chaque composante est
    alors relue par lstat avant d'accepter (C6-T6, amendement A1).
    """
    try:
        base = os.path.realpath(racine_web)
        attendu = os.path.normpath(os.path.join(base, *chemin.split("/")))

        # Préfixes de `attendu` strictement sous `base`, du plus profond au
        # plus haut. Un chemin qui sort de `base` n'en a aucun : c'est la
        # comparaison de résolution, plus bas, qui le refuse.
        prefixes = []
        courant = attendu
        while courant != base:
            parent = os.path.dirname(courant)
            if parent == courant:
                prefixes = []
                break
            prefixes.append(courant)
            courant = parent
        for prefixe in prefixes:
            if os.path.islink(prefixe):
                return "", "lien-symbolique"

        reel = os.path.realpath(attendu)
        if os.path.commonpath([base, reel]) != base:
            return "", "hors-racine"
        if reel != attendu:
            if os.path.normcase(reel) != os.path.normcase(attendu):
                return "", "lien-symbolique"
            # Windows : realpath rend la casse du disque. Une casse seule
            # n'est pas un lien : aucun fichier ne porte exactement ce nom.
            if not tolerer_casse:
                return "", "absent"
            # Tolérance du service statique. Elle ne doit laisser passer aucun
            # détour : chaque composante sous la racine est relue par lstat,
            # qui voit le lien même quand islink est aveugle, et le point de
            # reparse (jonction) par ses attributs Windows.
            for prefixe in prefixes:
                try:
                    infos = os.lstat(prefixe)
                except (FileNotFoundError, NotADirectoryError):
                    # Un préfixe absent (le fichier demandé lui-même, le plus
                    # souvent) n'est pas un lien : la 404 de la bibliothèque
                    # répond. `continue` et non `return` : ses parents restent
                    # à examiner, l'un d'eux peut être une jonction (C6-T7).
                    continue
                if (stat.S_ISLNK(infos.st_mode)
                        or (getattr(infos, "st_file_attributes", 0)
                            & stat.FILE_ATTRIBUTE_REPARSE_POINT)):
                    return "", "lien-symbolique"
            return reel, None
    except ValueError:
        # commonpath : lecteurs différents sous Windows, donc hors racine.
        return "", "hors-racine"
    except OSError:
        return "", "illisible"
    return attendu, None


# Nom historique de C2-T2, gardé pour valider_logo et tests/test_logo.py. Un
# alias et non une enveloppe : c'est le même objet, donc les simulations de
# serveur.os.path et la garde AST des motifs portent sur le code réel.
confiner_logo = confiner_sous_racine


def confiner_fichier_servi(chemin_traduit, racine_web):
    """Rend le motif de refus d'un fichier statique, ou None s'il peut être
    ouvert. Un fichier absent rend None : c'est la 404 de la bibliothèque qui
    répond, comme avant (C6-T6).

    chemin_traduit est celui que send_head ouvrira (translate_path), décodé.
    Seul appelant à tolérer la casse : voir confiner_sous_racine. Aucune
    exception ne sort.

    Un chemin que le système de fichiers ne sait pas nommer (octet nul, demi-
    paire de substitution isolée sous POSIX) rend « forme-invalide » : la
    réponse reste la 404 d'un absent, seul le journal nominatif le distingue
    (C6-T5).
    """
    # Refus explicite : selon la version de Python et le système, realpath lève
    # ou laisse passer un octet nul, et open() lèverait alors une ValueError
    # que send_head ne rattrape pas.
    if "\0" in chemin_traduit:
        return "forme-invalide"
    # Même famille de défaut : open() lève UnicodeEncodeError, une ValueError
    # elle aussi, sur un nom que le système n'encode pas. Le test suit
    # l'encodage réel du système (sous Windows, PEP 529, la demi-paire s'encode
    # et la 404 d'un absent répond) au lieu de transcrire une liste.
    try:
        os.fsencode(chemin_traduit)
    except UnicodeEncodeError:
        return "forme-invalide"
    try:
        relatif = os.path.relpath(chemin_traduit, racine_web)
    except ValueError:   # lecteurs différents sous Windows
        return "hors-racine"
    _, motif = confiner_sous_racine(relatif.replace(os.sep, "/"), racine_web,
                                    tolerer_casse=True)
    return motif


def chemin_contient(englobant, contenu):
    """Vrai si `contenu` est `englobant` ou se trouve dessous ; deux formes
    déjà résolues et normalisées. commonpath et non startswith : /cab-x n'est
    pas sous /cab."""
    try:
        return os.path.commonpath([englobant, contenu]) == englobant
    except ValueError:   # lecteurs différents sous Windows
        return False


def forme_comparable(chemin):
    """Forme résolue, normalisée en casse puis en NFC, d'un chemin à comparer.

    Sous macOS, un lien écrit en NFC vers un dossier stocké en NFD désigne le
    même dossier, mais realpath rend chaque forme telle qu'écrite : sans la
    normalisation, commonpath ne verrait aucune contenance. L'erreur ne peut
    aller que dans le sens du refus (deux noms que seule la normalisation
    distingue sont confondus). Lève OSError ou ValueError comme realpath."""
    return unicodedata.normalize(
        "NFC", os.path.normcase(os.path.realpath(chemin)))


def motif_refus_racine_web(racine_web, racine_cabinet, dossier_pdf):
    """None si la racine web résolue ne contient ni la racine du cabinet ni le
    dossier des bilans ; sinon un motif de MOTIFS_REFUS_DEMARRAGE. Jamais de
    levée.

    Le confinement des fichiers servis (D2 de C6-T6) accepte une racine web
    atteinte par un lien, indispensable sous macOS et sous une jonction. Il ne
    distingue pas un lien qui déplace la racine web d'un lien qui lui fait
    englober le cabinet : config.json (extension servie) ne serait plus
    protégé par la séparation des dossiers. Ce contrôle porte donc sur la
    contenance, des formes résolues des deux côtés, jamais sur l'existence
    d'un lien.
    """
    try:
        web = forme_comparable(racine_web)
        cabinet = forme_comparable(racine_cabinet)
        bilans = forme_comparable(dossier_pdf)
    except (OSError, ValueError):
        # Échec fermé : mieux vaut un refus visible qu'un serveur qui paraît
        # marcher, comme pour l'absence de TLS.
        return "indetermine"

    # Le motif le plus général d'abord : quand formulaire englobe le cabinet,
    # il englobe aussi les bilans.
    if chemin_contient(web, cabinet):
        return "racine-cabinet"
    if chemin_contient(web, bilans):
        return "dossier-pdf"
    return None


def valider_logo(chemin, racine_web=None):
    """Valide le chemin du logo configuré. Rend (chemin_servi, motif) :
    (chemin tel que validé, None) s'il peut être proposé à la tablette,
    ("", None) quand le cabinet n'a pas de logo (un choix, pas une anomalie),
    ("", motif) pour tout refus. Jamais de levée.

    Un logo refusé donne « pas de logo », jamais le logo par défaut
    (décision D7) : l'emblème d'une autre profession n'a rien à faire sur le
    bilan d'un autre cabinet. Validé une fois, au démarrage (décision D3).
    """
    if racine_web is None:
        racine_web = FORMULAIRE
    if not isinstance(chemin, str):
        return "", "forme-invalide"
    if chemin.strip() == "":
        return "", None

    motif = forme_logo(chemin)
    if motif:
        return "", motif
    absolu, motif = confiner_logo(chemin, racine_web)
    if motif:
        return "", motif

    try:
        infos = os.lstat(absolu)
    except (FileNotFoundError, NotADirectoryError):
        return "", "absent"
    except OSError:
        return "", "illisible"
    if not stat.S_ISREG(infos.st_mode):
        return "", "absent"
    if infos.st_size > LOGO_TAILLE_MAX:
        return "", "trop-volumineux"
    if infos.st_size == 0:
        return "", "illisible"

    signature = SIGNATURES_LOGO[os.path.splitext(chemin)[1].lower()]
    try:
        with open(absolu, "rb") as f:
            debut = f.read(8)
    except OSError:
        return "", "illisible"
    if not debut.startswith(signature):
        return "", "illisible"
    return chemin, None


def saisir_cabinet(config):
    """Demande chaque champ de l'identité du cabinet, valeur courante entre
    crochets ; une saisie vide la conserve. Ne fait aucune entrée-sortie
    fichier : travaille uniquement sur le dictionnaire reçu.

    Dérivée de CLES_CABINET, jamais retranscrite : un champ ajouté au bloc
    "cabinet" de CONFIG_DEFAUT est saisi ici sans modification de cette
    fonction.
    """
    # Copie défensive : config["cabinet"] peut être le dictionnaire partagé
    # de CONFIG_DEFAUT (repli de definir_mot_de_passe sur un config.json
    # absent) — le modifier en place altérerait les défauts pour le reste
    # du processus.
    cabinet = dict(config.get("cabinet") or CONFIG_DEFAUT["cabinet"])

    print("\nIdentité du cabinet, affichée sur chaque bilan généré.")
    for cle in CLES_CABINET:
        saisie = input("{} [{}] : ".format(cle, cabinet.get(cle, ""))).strip()
        if saisie:
            cabinet[cle] = saisie

    config["cabinet"] = cabinet
    return config


def definir_mot_de_passe():
    config = charger_config() or dict(CONFIG_DEFAUT)

    utilisateur = input("Identifiant [{}] : ".format(config["utilisateur"])).strip()
    if utilisateur:
        config["utilisateur"] = utilisateur

    premier = getpass.getpass("Mot de passe : ")
    if len(premier) < 8:
        print("Refusé : 8 caractères minimum.")
        return 1
    if premier != getpass.getpass("Confirmation : "):
        print("Refusé : les deux saisies diffèrent.")
        return 1

    config = saisir_cabinet(config)

    # On avertit sans empêcher (décision D11) : l'installateur peut poser le
    # fichier après avoir saisi la configuration.
    _, motif_logo = valider_logo(config["cabinet"]["logo"])
    if motif_logo:
        print("AVERTISSEMENT : ce logo sera refusé au démarrage ({}). "
              "Placez le fichier sous formulaire/images/cabinet/ et indiquez "
              "images/cabinet/<nom>.png.".format(motif_logo))

    config["mot_de_passe"] = hacher(premier)
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    os.chmod(CONFIG, 0o600)      # lisible par le seul propriétaire

    print("\nConfiguration écrite dans config.json (permissions 600).")
    print("Identifiant : {}".format(config["utilisateur"]))
    return 0


# --------------------------------------------------------------------------
# Nom de fichier
# --------------------------------------------------------------------------

def assainir_nom(nom):
    """Réduit un nom fourni par le client à une forme sûre.

    Neutralise la traversée de répertoire (../), les séparateurs de chemin et
    les caractères spéciaux. Le résultat ne peut désigner qu'un fichier du
    dossier de dépôt.
    """
    nom = os.path.basename(nom.replace("\\", "/"))
    nom = unicodedata.normalize("NFKD", nom)
    nom = nom.encode("ascii", "ignore").decode("ascii")
    nom = re.sub(r"[^A-Za-z0-9 ._-]", "_", nom).strip(" .")
    nom = re.sub(r"_{2,}", "_", nom)

    if nom.lower().endswith(".pdf"):
        nom = nom[:-4]
    if not nom:
        nom = "bilan"
    # Tronquer AVANT de remettre l'extension, sinon un nom très long
    # ressortirait sans ".pdf"
    return nom[:116] + ".pdf"


def chemin_libre(dossier, nom):
    """Ajoute un suffixe numérique plutôt que d'écraser un bilan existant."""
    base, ext = os.path.splitext(nom)
    candidat = os.path.join(dossier, nom)
    n = 2
    while os.path.exists(candidat):
        candidat = os.path.join(dossier, "{}-{}{}".format(base, n, ext))
        n += 1
    return candidat


def ecrire_atomiquement(destination, contenu):
    """Écrit le PDF sans jamais laisser de fichier partiel dans le dossier.

    Le contenu part dans un fichier temporaire du même dossier — donc du même
    système de fichiers, sans quoi le renommage ne serait pas atomique — puis
    est renommé. Le logiciel du cabinet qui surveille le dossier ne peut donc
    ouvrir qu'un bilan complet : un transfert interrompu ne laisse rien.
    """
    dossier = os.path.dirname(destination)
    descripteur, temporaire = tempfile.mkstemp(dir=dossier, suffix=".part")
    try:
        with open(descripteur, "wb") as f:
            f.write(contenu)
            f.flush()
            os.fsync(f.fileno())     # sinon un arrêt brutal perd le contenu
        os.chmod(temporaire, 0o600)
        os.replace(temporaire, destination)
    except BaseException:
        # Ne pas laisser traîner de .part si l'écriture échoue.
        try:
            os.unlink(temporaire)
        except OSError:
            pass
        raise


# --------------------------------------------------------------------------
# Journal
# --------------------------------------------------------------------------

# Le serveur est multithreadé : deux requêtes simultanées peuvent vouloir
# écrire, et surtout faire tourner le journal, au même instant.
_verrou_journal = threading.Lock()


def ecrire_stderr(ligne):
    """Écrit sur la sortie d'erreur quand il y en a une.

    Lancé par le service Windows, le serveur tourne sous `pythonw.exe`, qui
    n'ouvre pas de console : `sys.stderr` vaut alors None. Un write direct
    lèverait AttributeError au milieu d'une requête, et le thread mourrait
    sans réponse — un dépôt perdu pour une ligne de journal.
    """
    if sys.stderr is None:
        return
    try:
        sys.stderr.write(ligne)
    except (ValueError, OSError):
        pass


def conservation_mois():
    """Durée de conservation en vigueur, toujours valide."""
    return normaliser_conservation_mois(CONSERVATION_JOURNAUX_MOIS)


def seuil_purge():
    """Âge au-delà duquel la première ligne d'une archive la condamne :
    N mois moins PURGE_INTERVALLE (D3 bis). L'avance garantit qu'aucune ligne
    ne dépasse N mois entre deux vérifications ; elle coûte au plus un jour
    de conservation."""
    return (datetime.timedelta(days=JOURS_PAR_MOIS * conservation_mois())
            - PURGE_INTERVALLE)


def generations_maximales():
    """Nombre maximal d'archives d'un journal (décision D4).

    Avec une rotation mensuelle, JOURNAL_ARCHIVES = 3 couperait la
    conservation à trois mois : le compte ne doit jamais être la borne de
    durée. N + 1 générations laissent l'âge, et lui seul, décider ; la borne
    disque reste finie (au plus JOURNAL_TAILLE_MAX par génération).
    """
    return max(JOURNAL_ARCHIVES, conservation_mois() + 1)


def _horodatage_de_tete(chemin):
    """Date de la première ligne du fichier, ou None si elle est illisible.

    Les deux journaux commencent chaque ligne par
    datetime.now().isoformat(timespec="seconds"), naïf et sans espace. Le
    motif est strict à dessein : fromisoformat() accepte plus de formes
    depuis Python 3.11 qu'en 3.9 (« 20261019 », fuseaux), et un même fichier
    ne doit pas être daté différemment selon l'interpréteur.
    """
    try:
        with open(chemin, "rb") as f:
            tete = f.readline(64)
    except OSError:
        return None
    mots = tete.decode("utf-8", errors="replace").split()
    if not mots or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", mots[0]):
        return None
    try:
        return datetime.datetime.fromisoformat(mots[0])
    except ValueError:
        return None


def _age_premiere_ligne(chemin, maintenant):
    """Âge de la première ligne du fichier, ou None si rien ne permet de le
    dire.

    Horodatage illisible, ou postérieur à l'horloge (corrompu, ou horloge
    reculée : sinon il rendrait le fichier immortel) : repli sur la date de
    modification, plus prudente. La décision D1 n'est pas tenue sur un
    fichier corrompu, mais rien ne lève.
    """
    horodatage = _horodatage_de_tete(chemin)
    if horodatage is not None and horodatage <= maintenant:
        return maintenant - horodatage
    try:
        modification = datetime.datetime.fromtimestamp(os.lstat(chemin).st_mtime)
    except (OSError, OverflowError, ValueError):
        return None
    return maintenant - modification


# Instant de la dernière purge de chaque journal, pour la limiter à une par
# intervalle. Lu et écrit sous _verrou_journal (ou hors de tout fil concurrent,
# au démarrage et dans les tests).
_derniere_purge = {}


def _est_fichier_ordinaire(chemin):
    """Vrai pour un fichier ordinaire, faux pour un lien symbolique, un
    dossier, un chemin absent ou illisible. lstat, jamais stat : un lien n'est
    pas suivi."""
    try:
        return stat.S_ISREG(os.lstat(chemin).st_mode)
    except OSError:
        return False


def purger_archives(chemin=None, maintenant=None):
    """Supprime les archives dont la première ligne a plus de N mois.

    Point nommé de l'audit (décision D6) : ne supprime que des chemins de la
    forme exacte « <journal>.<entier> », entier de 1 à CONSERVATION_MOIS_MAX + 1
    (D6 bis : baisser N ne laisse pas d'archives orphelines hors d'atteinte),
    construits un à un — jamais de recherche par motif (glob) : un
    « journal.log.bak », un « journal.log.1.x » ou un autre fichier du
    dossier ne peuvent pas être désignés. Un lien symbolique ou un dossier de
    ce nom est laissé tel quel (lstat, jamais stat). Ne lève pas, et ne
    journalise rien : elle est appelée sous _verrou_journal, non réentrant,
    et journaliser_technique() le reprendrait (interblocage).

    Mémorise l'instant de la purge (_derniere_purge) pour que l'écriture ne la
    refasse pas plus d'une fois par PURGE_INTERVALLE.

    Rend le nombre d'archives supprimées. Le défaut de chemin et d'horloge se
    résout dans le corps, comme dans faire_tourner_journal().
    """
    if chemin is None:
        chemin = JOURNAL
    if maintenant is None:
        maintenant = datetime.datetime.now()

    _derniere_purge[chemin] = maintenant
    limite = seuil_purge()
    supprimees = 0
    for rang in range(1, CONSERVATION_MOIS_MAX + 2):
        archive = "{}.{}".format(chemin, rang)
        try:
            if not _est_fichier_ordinaire(archive):
                continue
            age = _age_premiere_ligne(archive, maintenant)
            if age is not None and age > limite:
                os.remove(archive)
                supprimees += 1
        except OSError:
            continue
    return supprimees


def purger_au_demarrage():
    """Purge les archives des deux journaux avant la première écriture.

    Un serveur arrêté plusieurs mois ne tourne pas et ne purge donc rien :
    sans ce passage, les archives périmées survivraient jusqu'à la prochaine
    rotation. Les deux journaux, même si journal_technique est désactivé : la
    promesse vaut pour les fichiers déjà là.
    """
    with _verrou_journal:
        for chemin in (JOURNAL, TECHNIQUE):
            purger_archives(chemin)


def entretenir_journaux(maintenant=None):
    """Passe d'entretien des deux journaux, hors de toute écriture : rotation
    si le courant a plus d'un mois ou dépasse la taille, puis purge
    inconditionnelle des archives (le plafond d'un jour de purge_due ne
    s'applique pas ici : le fil appelle déjà à intervalle fixe).

    Sans écriture, le journal courant vieillirait seul et ses lignes
    passeraient N mois. La rotation d'un technique.log par ce chemin
    n'inscrit pas de ligne ROTATION : l'écrire créerait le fichier même
    quand journal_technique est désactivé.

    Prend _verrou_journal et ne journalise rien dessous (interblocage).
    """
    if maintenant is None:
        maintenant = datetime.datetime.now()
    with _verrou_journal:
        for chemin in (JOURNAL, TECHNIQUE):
            faire_tourner_journal(chemin, maintenant)
            purger_archives(chemin, maintenant)


def boucle_purge_periodique(arret, attente=PURGE_PERIODIQUE_SECONDES,
                            horloge=None):
    """Corps du fil de purge : toutes les `attente` secondes, entretient les
    deux journaux, jusqu'à ce que `arret` (un threading.Event) soit levé.

    Attente et événement d'arrêt s'injectent : un test passe un événement
    simulé et n'attend jamais. `arret.wait()` rend True quand l'événement est
    levé, ce qui arrête la boucle sans attendre le délai. Aucune exception
    n'arrête la boucle (un journal ne doit jamais coûter autre chose que
    lui-même), et rien n'est journalisé : une erreur de purge se retrouvera
    à l'écriture suivante, qui repasse par les mêmes fonctions.
    """
    while not arret.wait(attente):
        try:
            entretenir_journaux(horloge() if horloge is not None else None)
        except Exception:
            pass


def demarrer_purge_periodique():
    """Lance le fil de purge, en démon : il meurt avec le processus. Rend le
    fil et son événement d'arrêt."""
    arret = threading.Event()
    fil = threading.Thread(target=boucle_purge_periodique, args=(arret,),
                           name="purge-journaux", daemon=True)
    fil.start()
    return fil, arret


# Nom provisoire du journal courant pendant une rotation. Hors de la forme
# « <journal>.<entier> » : la purge ne le voit pas, et il ne se confond avec
# aucune archive.
SUFFIXE_ROTATION = ".rotation"

# Dernier échec de rotation de chaque journal : on ne retente pas à chaque
# écriture un renommage qui échoue (journal tenu ouvert sous Windows), une
# fois par PURGE_INTERVALLE suffit. Même verrou que _derniere_purge.
_rotation_ratee = {}


def _rang(chemin, rang):
    return "{}.{}".format(chemin, rang)


def _liberer_le_rang_un(chemin):
    """Décale les archives pour que « <journal>.1 » soit libre. Lève OSError.

    Chaque archive monte d'un rang seulement jusqu'au premier trou : une
    archive n'est supprimée par le compte que si la chaîne est pleine. Un
    décalage interrompu à mi-chemin, relancé, ne perd donc rien (la boucle
    d'origine supprimait « la plus ancienne » avant de savoir si le courant
    pourrait être archivé : audit C4-T2).

    Une entrée qui n'est pas un fichier ordinaire (dossier, lien) à un rang
    est une barrière : on ne la touche jamais, et le décalage s'arrête sous
    elle. Une archive part alors un peu plus tôt, ce que D1 tolère ; le
    journal courant, lui, continue de tourner. Seule une barrière au rang 1
    interdit toute rotation.
    """
    borne = generations_maximales()
    plafond = borne
    for rang in range(1, borne + 1):
        nom = _rang(chemin, rang)
        if os.path.lexists(nom) and not _est_fichier_ordinaire(nom):
            plafond = rang - 1
            break
    if plafond < 1:
        raise OSError("le rang 1 des archives est occupé par autre chose "
                      "qu'un fichier")

    libre = None
    for rang in range(1, plafond + 1):
        if not os.path.lexists(_rang(chemin, rang)):
            libre = rang
            break
    if libre is None:
        # Chaîne pleine : la plus ancienne part par le compte.
        os.remove(_rang(chemin, plafond))
        libre = plafond
    for rang in range(libre - 1, 0, -1):
        os.replace(_rang(chemin, rang), _rang(chemin, rang + 1))


def _replacer_le_temporaire(chemin):
    """Place en « .1 » le journal laissé sous son nom provisoire par une
    rotation interrompue. Sans effet s'il n'y en a pas. Ne lève pas."""
    temporaire = chemin + SUFFIXE_ROTATION
    if not _est_fichier_ordinaire(temporaire):
        return
    try:
        _liberer_le_rang_un(chemin)
        os.replace(temporaire, _rang(chemin, 1))
    except OSError:
        pass


def purge_due(chemin, maintenant):
    """Vrai si la dernière purge de ce journal remonte à PURGE_INTERVALLE ou
    plus, ou n'a jamais eu lieu. Une horloge reculée (écart négatif) compte
    comme due : mieux vaut purger trop que laisser vieillir."""
    derniere = _derniere_purge.get(chemin)
    if derniere is None:
        return True
    ecart = maintenant - derniere
    return ecart < datetime.timedelta(0) or ecart >= PURGE_INTERVALLE


def faire_tourner_journal(chemin=None, maintenant=None):
    """Archive le journal au-delà de JOURNAL_TAILLE_MAX, ou dès que sa
    première ligne a plus d'un mois (décision D2), puis purge les archives
    périmées (D3). Sans rotation, la purge est quand même revérifiée, au plus
    une fois par jour (D3 bis) : sans cela, une archive devenue éligible
    attendrait la rotation suivante et ses lignes dépasseraient N mois.

    Partagée par les deux journaux : le défaut se résout ici, dans le corps,
    et non dans la signature — sinon il serait figé à l'import, et les tests
    qui remplacent le global JOURNAL (RotationDuJournal) cesseraient d'agir
    sur cette fonction. L'horloge (`maintenant`, un datetime naïf local) suit
    la même règle et s'injecte dans les tests : jamais de sleep.

    Conserve generations_maximales() générations. Toute erreur est ignorée :
    un journal qu'on ne peut pas faire tourner ne doit pas empêcher le
    serveur de répondre. Rend True si une rotation a eu lieu, pour que
    l'appelant (déjà sous verrou dans journaliser_technique) puisse noter
    l'événement sans ré-acquérir ce verrou.
    """
    if chemin is None:
        chemin = JOURNAL
    if maintenant is None:
        maintenant = datetime.datetime.now()

    # D'abord, une rotation interrompue : ses lignes ne sont dans aucune
    # archive reconnue tant qu'elles restent sous le nom provisoire.
    _replacer_le_temporaire(chemin)

    try:
        taille = os.path.getsize(chemin)
        a_tourner = taille >= JOURNAL_TAILLE_MAX
        # Un fichier vide n'a rien à archiver, quelle que soit sa date.
        if not a_tourner and taille > 0:
            age = _age_premiere_ligne(chemin, maintenant)
            a_tourner = (age is not None
                         and age > datetime.timedelta(days=JOURS_PAR_MOIS))
    except OSError:
        # Journal absent : pas de rotation, mais des archives peuvent
        # attendre leur purge.
        a_tourner = False
    if a_tourner:
        derniere = _rotation_ratee.get(chemin)
        if (derniere is not None
                and datetime.timedelta(0) <= maintenant - derniere
                < PURGE_INTERVALLE):
            a_tourner = False
    # Un nom provisoire encore là écraserait des lignes non archivées.
    if a_tourner and os.path.lexists(chemin + SUFFIXE_ROTATION):
        a_tourner = False
    # Un non-fichier au rang 1 interdit toute rotation : on ne déplace pas le
    # courant sous son nom provisoire pour ne pas pouvoir le replacer.
    rang_un = _rang(chemin, 1)
    if a_tourner and os.path.lexists(rang_un) and not _est_fichier_ordinaire(rang_un):
        a_tourner = False
    if not a_tourner:
        if purge_due(chemin, maintenant):
            purger_archives(chemin, maintenant)
        return False

    # Le courant passe d'abord sous son nom provisoire : si ce renommage
    # échoue (journal tenu ouvert sous Windows), aucune archive n'a bougé ni
    # disparu. Le décalage ne vient qu'ensuite (audit C4-T2).
    temporaire = chemin + SUFFIXE_ROTATION
    try:
        os.replace(chemin, temporaire)
    except OSError:
        _rotation_ratee[chemin] = maintenant
        if purge_due(chemin, maintenant):
            purger_archives(chemin, maintenant)
        return False
    try:
        _liberer_le_rang_un(chemin)
        os.replace(temporaire, _rang(chemin, 1))
    except OSError:
        # Le courant reste sous son nom provisoire ; _replacer_le_temporaire
        # le placera à l'écriture suivante (et tant qu'il est là, aucune
        # nouvelle rotation ne part : pas besoin de la limite quotidienne).
        return False
    _rotation_ratee.pop(chemin, None)

    # Après le décalage, pour que l'archive qui vient d'être créée soit jugée
    # elle aussi : un journal courant resté plus de N mois sans écriture
    # s'archive puis disparaît dans le même passage.
    purger_archives(chemin, maintenant)
    return True


def journaliser(ligne):
    """Trace une ligne sur la sortie d'erreur et dans le journal."""
    ecrire_stderr(ligne)
    with _verrou_journal:
        faire_tourner_journal()
        try:
            with open(JOURNAL, "a", encoding="utf-8") as f:
                f.write(ligne)
        except OSError:
            pass


# --------------------------------------------------------------------------
# Journal technique (C4-T1) — non identifiant, conçu pour circuler
# --------------------------------------------------------------------------

def empreinte_certificat(chemin):
    """Seize premiers chiffres hexadécimaux du SHA-256 du certificat.

    Substitut d'adresse (décision D2) : le certificat porte l'adresse en
    subjectAltName, donc toute réémission pour une nouvelle adresse change
    l'empreinte, sans que celle-ci ne soit elle-même une adresse ni ne
    s'inverse. Bibliothèque standard seule ; aucune clé privée n'est lue.
    """
    try:
        with open(chemin, encoding="ascii") as f:
            pem = f.read()
        der = ssl.PEM_cert_to_DER_cert(pem)
        return hashlib.sha256(der).hexdigest()[:16]
    except (OSError, ValueError, ssl.SSLError):
        return "indisponible"


def verdict_certificat(empreinte):
    """Compare l'empreinte courante à celle inscrite au dernier démarrage.

    Relit la dernière ligne DEMARRAGE de technique.log, sans lire d'archive
    ni tenir d'état séparé (étape 7) : si rien n'est trouvé, ou en cas
    d'erreur de lecture, le verdict est "premier démarrage observé". Un
    fichier non décodable (réenregistré en ANSI par un correspondant, ou
    tronqué en plein caractère multi-octets par un disque plein) lève
    UnicodeDecodeError, qui dérive de ValueError et non d'OSError : sans ce
    second type, l'exception remonte et empêche le serveur de démarrer —
    exactement ce que le §11 du contrat interdit à ce journal de faire.
    """
    try:
        with open(TECHNIQUE, encoding="utf-8") as f:
            lignes = f.readlines()
    except (OSError, ValueError):
        return "premier démarrage observé"

    precedente = None
    for ligne in reversed(lignes):
        # Le jeton exact après l'horodatage, pas une sous-chaîne : sans cela,
        # DEMARRAGE_REFUSE (C6-T7) passait pour un démarrage sans empreinte et
        # le verdict suivant annonçait à tort « premier démarrage observé ».
        if re.match(r"\S+ DEMARRAGE(?:\s|$)", ligne):
            correspondance = re.search(r"certificat=([0-9a-f]+)", ligne)
            if correspondance:
                precedente = correspondance.group(1)
            break

    if precedente is None:
        return "premier démarrage observé"
    if precedente == empreinte:
        return "certificat identique au démarrage précédent"
    return "certificat différent du démarrage précédent"


def classe_route(chemin):
    """Classe un chemin canonique en une des catégories fermées.

    Jamais un chemin brut, contrôlé par le client, n'atteint le journal
    technique (décision D3) : une tentative de traversée ou un nom de
    fichier ne traverse jamais cette fonction, qui ne rend que des membres
    de ROUTES_TECHNIQUES.
    """
    if chemin == "/depot":
        return "depot"
    if chemin == "/sante":
        return "sante"
    if chemin == "/cabinet":
        return "cabinet"
    if chemin == "/etat":
        return "etat"
    if chemin in ("/", ""):
        return "formulaire"
    extension = os.path.splitext(chemin)[1].lower()
    if extension in EXTENSIONS_SERVIES:
        return "formulaire"
    return "autre"


def detail_refus_depot(motif):
    """Compose le détail d'un dépôt refusé, sur un vocabulaire fermé : une
    valeur hors de MOTIFS_REFUS_DEPOT devient "motif-inconnu" plutôt que
    d'être recopiée telle quelle."""
    if motif not in MOTIFS_REFUS_DEPOT:
        motif = "motif-inconnu"
    return "refus motif={}".format(motif)


def detail_refus_logo(motif):
    """Compose le détail d'un logo refusé, sur un vocabulaire fermé : jamais
    le chemin, qui est une saisie libre (enseigne, nom de session Windows) et
    n'a pas sa place dans technique.log (décision D8)."""
    if motif not in MOTIFS_REFUS_LOGO:
        motif = "motif-inconnu"
    return "refus motif={}".format(motif)


def detail_refus_demarrage(motif):
    """Compose le détail d'un démarrage refusé, sur un vocabulaire fermé :
    jamais un chemin, qui peut porter un nom de session Windows et n'a pas sa
    place dans technique.log."""
    if motif not in MOTIFS_REFUS_DEMARRAGE:
        motif = "motif-inconnu"
    return "refus motif={}".format(motif)


def detail_depot_ok(octets):
    """Compose le détail d'un dépôt réussi : une taille, jamais un nom."""
    return "ok {} octets".format(octets)


def detail_echec_ecriture(erreur):
    """Compose le détail d'un échec d'écriture à partir d'errno et de
    strerror seuls : str(OSError) inclurait le chemin complet, donc le nom
    du patient (décision D4). C'est le point le plus facile à rater de tout
    le contrat — d'où une fonction dédiée, plutôt qu'un formatage recopié à
    chaque site."""
    return "errno={} {}".format(erreur.errno, erreur.strerror)


def _ajouter_ligne_technique(ligne):
    try:
        with open(TECHNIQUE, "a", encoding="utf-8") as f:
            f.write(ligne)
    except OSError:
        pass


def journaliser_technique(evenement, detail=""):
    """Trace une ligne dans technique.log, sans jamais rien écrire sur
    stderr (décision D5, pour ne pas doubler chaque ligne), ni lever sur un
    nom d'événement fautif : un journal ne doit jamais coûter un dépôt.
    """
    if not JOURNAL_TECHNIQUE_ACTIF:
        return
    if evenement not in EVENEMENTS_TECHNIQUES:
        evenement = "EVENEMENT_INCONNU"

    # L'horodatage est sans espace (isoformat, timespec="seconds") : le
    # premier mot de chaque ligne en est un, et le test anti-fuite s'appuie
    # sur ce fait pour appliquer le motif IPv6 à la ligne privée de son
    # premier mot.
    horodatage = datetime.datetime.now().isoformat(timespec="seconds")

    with _verrou_journal:
        # faire_tourner_journal() est appelée ici, sous le verrou déjà
        # acquis : surtout ne jamais rappeler journaliser_technique() depuis
        # l'intérieur de ce bloc, ce serait un interblocage (verrou non
        # réentrant). L'événement ROTATION s'écrit donc directement.
        if faire_tourner_journal(TECHNIQUE):
            _ajouter_ligne_technique("{} {} archive\n".format(
                datetime.datetime.now().isoformat(timespec="seconds"),
                EVENEMENT_ROTATION))
        _ajouter_ligne_technique("{} {} {}\n".format(
            horodatage, evenement, detail))


# --------------------------------------------------------------------------
# Page d'état (C4-T3) — lecture seule, conçue pour circuler comme technique.log
# --------------------------------------------------------------------------

# Rien de ce qui suit ne reçoit le gestionnaire de requête : ces fonctions
# n'ont structurellement pas accès à l'adresse du client (une garde statique
# de tests/test_serveur.py le vérifie sur l'arbre syntaxique).

def identite_renseignee(config):
    """Vrai quand le praticien est nommé dans la configuration.

    Même critère que le formulaire (formulaire/script.js) : sans lui l'export
    est refusé. Isolé ici pour que le démarrage et la page d'état ne
    puissent pas diverger.
    """
    return bool(config["cabinet"]["praticien"].strip())


# Étiquettes de l'ASN.1 DER utilisées par lire_certificat.
_DER_SEQUENCE = 0x30
_DER_UTCTIME = 0x17
_DER_GENERALIZEDTIME = 0x18
_DER_VERSION = 0xA0
_DER_EXTENSIONS = 0xA3
_DER_ADRESSE_IP = 0x87
_DER_OCTETS = 0x04
# 2.5.29.17, subjectAltName.
_OID_NOMS_ALTERNATIFS = bytes((0x55, 0x1D, 0x11))


def _element_der(donnees, debut, fin):
    """(étiquette, début du contenu, fin du contenu) de l'élément DER qui
    commence à `debut`. Lève ValueError si l'élément dépasse `fin`.

    Toute longueur lue est confrontée à la borne avant d'être suivie, et
    chaque appel avance d'au moins deux octets : aucune boucle de l'appelant
    ne peut tourner sans fin sur un fichier abîmé.
    """
    if fin - debut < 2:
        raise ValueError("élément DER tronqué")
    etiquette = donnees[debut]
    if etiquette & 0x1F == 0x1F:
        raise ValueError("étiquette DER à plusieurs octets non gérée")
    longueur = donnees[debut + 1]
    position = debut + 2
    if longueur & 0x80:
        nombre = longueur & 0x7F
        # 0x80 (longueur indéfinie) est interdite en DER ; plus de quatre
        # octets de longueur dépasse de loin un certificat.
        if nombre == 0 or nombre > 4 or position + nombre > fin:
            raise ValueError("longueur DER invalide")
        longueur = int.from_bytes(donnees[position:position + nombre], "big")
        position += nombre
    if position + longueur > fin:
        raise ValueError("élément DER plus long que son conteneur")
    return etiquette, position, position + longueur


def _enfants_der(donnees, debut, fin):
    """Les éléments successifs de donnees[debut:fin], en triplets."""
    enfants = []
    while debut < fin:
        element = _element_der(donnees, debut, fin)
        enfants.append(element)
        debut = element[2]
    return enfants


def _temps_der(etiquette, contenu):
    """Un UTCTime (AAMMJJhhmmssZ) ou un GeneralizedTime (AAAAMMJJhhmmssZ).

    Pour l'UTCTime, une année inférieure à 50 est en 20AA, sinon en 19AA
    (RFC 5280, 4.1.2.5.1). Les formes sans secondes ou avec décalage, que la
    RFC interdit, sont refusées plutôt que devinées.
    """
    texte = contenu.decode("ascii")
    if etiquette == _DER_UTCTIME:
        modele = r"([0-9]{2})([0-9]{2})([0-9]{2})([0-9]{2})([0-9]{2})([0-9]{2})Z"
    elif etiquette == _DER_GENERALIZEDTIME:
        modele = r"([0-9]{4})([0-9]{2})([0-9]{2})([0-9]{2})([0-9]{2})([0-9]{2})Z"
    else:
        raise ValueError("étiquette de date inattendue")
    trouve = re.fullmatch(modele, texte)
    if trouve is None:
        raise ValueError("date DER mal formée")
    nombres = [int(n) for n in trouve.groups()]
    if etiquette == _DER_UTCTIME:
        nombres[0] += 2000 if nombres[0] < 50 else 1900
    return datetime.datetime(*nombres, tzinfo=datetime.timezone.utc)


def _adresses_alternatives(der, debut, fin):
    """Adresses IP du subjectAltName, parmi les extensions de [3]."""
    etiquette, debut, fin = _element_der(der, debut, fin)
    if etiquette != _DER_SEQUENCE:
        raise ValueError("extensions : séquence attendue")
    adresses = []
    for etiquette, debut, fin in _enfants_der(der, debut, fin):
        if etiquette != _DER_SEQUENCE:
            continue
        # Extension : OID, criticité facultative, valeur en OCTET STRING.
        parties = _enfants_der(der, debut, fin)
        _, debut_oid, fin_oid = parties[0]
        if der[debut_oid:fin_oid] != _OID_NOMS_ALTERNATIFS:
            continue
        etiquette, debut, fin = parties[-1]
        if etiquette != _DER_OCTETS:
            raise ValueError("subjectAltName : octets attendus")
        etiquette, debut, fin = _element_der(der, debut, fin)
        if etiquette != _DER_SEQUENCE:
            raise ValueError("subjectAltName : séquence attendue")
        for etiquette, debut, fin in _enfants_der(der, debut, fin):
            if etiquette == _DER_ADRESSE_IP:
                adresses.append(ipaddress.ip_address(der[debut:fin]))
    return tuple(adresses)


def _analyser_certificat(der):
    """(expiration, adresses IP) du certificat DER ; lève sur tout défaut."""
    etiquette, debut, fin = _element_der(der, 0, len(der))
    if etiquette != _DER_SEQUENCE:
        raise ValueError("certificat : séquence attendue")
    etiquette, debut, fin = _element_der(der, debut, fin)
    if etiquette != _DER_SEQUENCE:
        raise ValueError("tbsCertificate : séquence attendue")
    champs = _enfants_der(der, debut, fin)

    # version [0] facultative, puis serialNumber, signature, issuer, validity,
    # subject, subjectPublicKeyInfo ; ensuite les facultatifs, dont [3].
    rang = 1 if champs[0][0] == _DER_VERSION else 0
    etiquette, debut, fin = champs[rang + 3]
    if etiquette != _DER_SEQUENCE:
        raise ValueError("validity : séquence attendue")
    dates = _enfants_der(der, debut, fin)
    etiquette, debut, fin = dates[1]
    expire_le = _temps_der(etiquette, der[debut:fin])

    adresses = ()
    for etiquette, debut, fin in champs[rang + 6:]:
        if etiquette == _DER_EXTENSIONS:
            adresses = _adresses_alternatives(der, debut, fin)
    return expire_le, adresses


def lire_certificat(chemin):
    """Date d'expiration (UTC) et adresses IP du subjectAltName du certificat.

    Rend {"expire_le": datetime | None, "adresses": tuple d'ipaddress} et ne
    lève jamais : un fichier absent, tronqué ou qui n'est pas un certificat
    donne une réponse vide, que la page d'état affiche comme « inconnue ».

    Parseur DER minimal plutôt que ssl._ssl._test_decode_cert : celle-ci est
    privée et préfixée « _test », donc retirable sans dépréciation (D4). La
    bibliothèque standard n'expose rien de public pour lire ces champs.
    """
    vide = {"expire_le": None, "adresses": ()}
    try:
        with open(chemin, encoding="ascii") as f:
            pem = f.read()
        der = ssl.PEM_cert_to_DER_cert(pem)
        expire_le, adresses = _analyser_certificat(der)
    except (OSError, ValueError, IndexError, ssl.SSLError):
        return vide
    return {"expire_le": expire_le, "adresses": adresses}


def adresse_portee(adresse):
    """Vrai si cette adresse est portée par une interface de ce PC.

    Demande au système plutôt que de deviner (D5) : un bind sur le port 0
    réussit si et seulement si l'adresse est locale. Aucun paquet n'est émis,
    aucune résolution de nom n'a lieu (voir le piège getfqdn de
    ServeurBilan.server_bind), la socket n'écoute pas et se ferme aussitôt.
    """
    try:
        adresse = ipaddress.ip_address(adresse)
        famille = socket.AF_INET6 if adresse.version == 6 else socket.AF_INET
        with socket.socket(famille, socket.SOCK_STREAM) as essai:
            essai.bind((str(adresse), 0))
    except (OSError, ValueError):
        return False
    return True


def verdict_adresse(adresses, est_portee=adresse_portee):
    """Le certificat couvre-t-il encore une adresse de ce PC ?

    Rend toujours un membre de VERDICTS_ADRESSE, jamais une adresse. Les
    adresses de boucle sont ignorées : le PC les porte toujours, elles ne
    disent rien d'un changement de box. Recalculé à chaque requête, car
    l'incident survient serveur en marche.
    """
    candidates = [a for a in adresses if not a.is_loopback]
    if not candidates:
        return "indéterminé"
    if any(est_portee(a) for a in candidates):
        return "conforme"
    return "adresse changée"


def dernieres_lignes_techniques():
    """Au plus LIGNES_ETAT dernières lignes de technique.log courant, ou None
    quand le journal technique est désactivé.

    Jamais d'archive, jamais journal.log : seul le fichier conçu pour
    circuler. Lue sous le verrou des journaux pour ne pas tenir le fichier
    ouvert pendant une rotation, qui le renomme. Ce verrou n'est pas
    réentrant : surtout ne pas appeler cette fonction d'un point qui le tient.
    """
    if not JOURNAL_TECHNIQUE_ACTIF:
        return None
    try:
        with _verrou_journal:
            with open(TECHNIQUE, "rb") as f:
                taille = f.seek(0, os.SEEK_END)
                debut = max(0, taille - QUEUE_ETAT_OCTETS)
                f.seek(debut)
                brut = f.read(QUEUE_ETAT_OCTETS)
    except OSError:
        return []
    # Seul le saut de ligne sépare les lignes : splitlines() couperait aussi
    # sur des caractères que le texte d'une erreur TLS peut porter.
    lignes = [l.rstrip("\r") for l in brut.decode("utf-8", errors="replace").split("\n")]
    if lignes and lignes[-1] == "":
        lignes.pop()
    # La lecture a pu commencer au milieu d'une ligne.
    if debut > 0 and lignes:
        lignes = lignes[1:]
    return lignes[-LIGNES_ETAT:]


def _json_strict(octets):
    """Le JSON strict de `octets` (clé en double, NaN, BOM refusés), ou ValueError.

    La lecture est celle de paquet_signe : ce que le client de mise à jour a écrit
    se relit exactement comme il le relit lui-même."""
    try:
        return paquet_signe._lire_json_strict(octets, "MANIFESTE_MALFORME")
    except paquet_signe.PaquetRefuse as erreur:
        raise ValueError(erreur.detail)


_ETAT_MAJ_ILLISIBLE = {
    "maj_etape": ETAPE_MAJ_ILLISIBLE, "maj_resultat": None, "maj_code": None,
    "maj_le": None, "maj_version": None}
_ETAT_MAJ_ABSENT = dict(_ETAT_MAJ_ILLISIBLE, maj_etape=ETAPE_MAJ_ABSENTE)


def lire_etat_maj(dossier=None):
    """Les cinq informations `maj_*` de /etat, lues dans `etat.json`.

    Le fichier est écrit par UN AUTRE processus (maj.py) : rien n'en est recopié
    tel quel. Chaque valeur est confrontée à un vocabulaire ou à une forme
    fermés, et une seule valeur hors forme rend `illisible` partout (un état à
    moitié cru serait pire qu'un état inconnu). Un chemin, une adresse, un nom
    de fichier ne passent pas ces formes, par construction. Aucune levée : une
    page d'état ne doit jamais coûter un diagnostic.
    """
    chemin = os.path.join(DOSSIER_MAJ if dossier is None else dossier, ETAT_MAJ)
    try:
        info = os.lstat(chemin)
    except FileNotFoundError:
        return dict(_ETAT_MAJ_ABSENT)
    except OSError:
        return dict(_ETAT_MAJ_ILLISIBLE)
    # Fichier ordinaire exigé : un lien ou un tube nommé n'est pas lu.
    if not stat.S_ISREG(info.st_mode):
        return dict(_ETAT_MAJ_ILLISIBLE)
    try:
        with open(chemin, "rb") as f:
            brut = f.read(TAILLE_MAX_ETAT_MAJ + 1)
        if len(brut) > TAILLE_MAX_ETAT_MAJ:
            return dict(_ETAT_MAJ_ILLISIBLE)
        contenu = _json_strict(brut)
    except (OSError, ValueError):
        return dict(_ETAT_MAJ_ILLISIBLE)
    if not isinstance(contenu, dict):
        return dict(_ETAT_MAJ_ILLISIBLE)

    def valeur(cle, valide):
        brute = contenu.get(cle)
        if brute is None:
            return None
        if not isinstance(brute, str) or not valide(brute):
            raise ValueError(cle)
        return brute

    try:
        etape = contenu.get("etape")
        if etape not in ETAPES_MAJ:
            raise ValueError("etape")
        return {
            "maj_etape": etape,
            "maj_resultat": valeur("resultat", lambda v: v in RESULTATS_MAJ),
            "maj_code": valeur("code", lambda v: _CODE_MAJ.fullmatch(v) is not None),
            "maj_le": valeur(
                "le", lambda v: _HORODATAGE_MAJ.fullmatch(v) is not None),
            "maj_version": valeur(
                "version", lambda v: paquet_signe._VERSION.fullmatch(v) is not None),
        }
    except ValueError:
        return dict(_ETAT_MAJ_ILLISIBLE)


def construire_etat(config, dossier_pdf):
    """Les informations de CLES_ETAT, et rien d'autre.

    Dictionnaire écrit en clair, clé par clé : ni la configuration, ni le
    dossier des PDF ne s'y sérialisent. Le chemin du dossier peut porter le
    nom de session du praticien et str(OSError) porte un chemin complet
    (décision D4 de C4-T1) : seul l'espace libre en sort, ou None.
    """
    charge = CERTIFICAT_CHARGE or {}
    expire_le = charge.get("expire_le")
    try:
        libre = shutil.disk_usage(dossier_pdf).free
    except (OSError, ValueError):
        libre = None
    return {
        "version": VERSION_EN_COURS or VERSION_INCONNUE,
        "demarre_le": DEMARRE_LE,
        "dernier_depot": DERNIER_DEPOT,
        "disque_libre_octets": libre,
        "certificat_expire_le": (
            expire_le.strftime("%Y-%m-%dT%H:%M:%SZ") if expire_le else None),
        "certificat_empreinte": charge.get("empreinte", "indisponible"),
        "certificat_adresse": verdict_adresse(charge.get("adresses", ())),
        "identite_cabinet": identite_renseignee(config),
        **lire_etat_maj(),
        "journal_technique": dernieres_lignes_techniques(),
    }


def rendre_etat_json(etat):
    return json.dumps(etat, ensure_ascii=False)


# Phrase affichée par verdict : le mot seul ne dit pas quoi faire. Les clés
# se dérivent de VERDICTS_ADRESSE (un test le vérifie), sans adresse.
EXPLICATIONS_ADRESSE = {
    "conforme": "le certificat couvre une adresse portée par ce PC.",
    "adresse changée": (
        "le certificat ne couvre aucune adresse que ce PC porte en ce moment. "
        "Soit l'adresse a changé : réémettre le certificat (mode d'emploi, "
        "« L'adresse du PC a changé »). Soit une interface réseau est "
        "débranchée (Wi-Fi coupé, câble) : la rebrancher et recharger la page."),
    "indéterminé": (
        "rien à comparer : le certificat ne porte que des adresses de boucle "
        "(localhost), ou il n'a pas pu être lu."),
}


def _go(octets):
    """Octets en Go (1 Go = 2^30 octets, comme l'Explorateur), une décimale,
    virgule française."""
    return "{:.1f} Go".format(octets / 1024 ** 3).replace(".", ",")


def _texte_certificat(etat, maintenant):
    expire = etat["certificat_expire_le"]
    if expire is None:
        return "inconnue"
    texte = expire.replace("T", " ").replace("Z", " UTC")
    try:
        fin = datetime.datetime.strptime(
            expire, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        return texte
    jours = (fin - maintenant).days
    if jours < 0:
        return "{} — expiré".format(texte)
    reste = "dans {} jour{}".format(jours, "s" if jours > 1 else "")
    if jours < JOURS_CERTIFICAT_A_RENOUVELER:
        return "{} — {}, à renouveler".format(texte, reste)
    return "{} — {}".format(texte, reste)


def _texte_mise_a_jour(etat):
    """La ligne « Mise à jour » : l'étape, puis ce que l'on sait du dernier
    résultat. Les valeurs ont déjà passé lire_etat_maj ; html.escape reste
    appliqué par l'appelant, comme pour toute autre ligne."""
    etape = etat["maj_etape"]
    if etape == ETAPE_MAJ_ABSENTE:
        return "aucune mise à jour enregistrée"
    if etape == ETAPE_MAJ_ILLISIBLE:
        return "état illisible : à signaler au support"
    morceaux = ["étape « {} »".format(etape)]
    if etat["maj_resultat"] is not None:
        morceaux.append("dernier résultat : {}".format(etat["maj_resultat"]))
    if etat["maj_code"] is not None:
        morceaux.append("code : {}".format(etat["maj_code"]))
    if etat["maj_version"] is not None:
        morceaux.append("version : {}".format(etat["maj_version"]))
    if etat["maj_le"] is not None:
        morceaux.append("le {}".format(etat["maj_le"].replace("T", " ")))
    return " — ".join(morceaux)


def rendre_etat_html(etat, maintenant=None):
    """Page autonome : aucun script, aucune ressource externe. Chaque valeur
    passe par html.escape — les lignes de technique.log portent des chaînes
    d'origine externe (TLS_REFUSE raison=...). Le dossier des PDF n'est
    nommé que par son rôle, jamais par son chemin."""
    if maintenant is None:
        maintenant = datetime.datetime.now(datetime.timezone.utc)

    def date(valeur):
        return "aucun depuis le démarrage" if valeur is None else valeur.replace("T", " ")

    verdict = etat["certificat_adresse"]
    explication = EXPLICATIONS_ADRESSE.get(verdict, "")
    lignes_journal = etat["journal_technique"]
    if lignes_journal is None:
        journal = "<p>Désactivé (réglage <code>journal_technique</code>).</p>"
    elif not lignes_journal:
        journal = "<p>Aucune ligne.</p>"
    else:
        journal = "<pre>{}</pre>".format(
            html.escape("\n".join(lignes_journal)))

    lignes = [
        ("Version", etat["version"]),
        ("Serveur démarré le", "inconnu" if etat["demarre_le"] is None
         else etat["demarre_le"].replace("T", " ")),
        ("Dernier bilan reçu", date(etat["dernier_depot"])),
        ("Espace libre (dossier des PDF)", "inconnu"
         if etat["disque_libre_octets"] is None
         else _go(etat["disque_libre_octets"])),
        ("Certificat valable jusqu'au", _texte_certificat(etat, maintenant)),
        ("Empreinte du certificat", etat["certificat_empreinte"]),
        ("Adresse du PC et certificat", "{} — {}".format(verdict, explication)),
        ("Identité du cabinet", "renseignée" if etat["identite_cabinet"]
         else "non renseignée : l'export des bilans est refusé"),
        ("Mise à jour", _texte_mise_a_jour(etat)),
    ]
    rangees = "\n".join(
        "<tr><th>{}</th><td>{}</td></tr>".format(
            html.escape(str(libelle)), html.escape(str(valeur)))
        for libelle, valeur in lignes)
    return """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>État du serveur — bilan posturologique</title>
<style>
body {{ font-family: sans-serif; margin: 1.5em; color: #222; }}
table {{ border-collapse: collapse; }}
th, td {{ text-align: left; padding: .4em .8em; border-bottom: 1px solid #ccc; vertical-align: top; }}
pre {{ background: #f4f4f4; padding: .8em; overflow-x: auto; white-space: pre-wrap; }}
</style>
</head>
<body>
<h1>État du serveur</h1>
<table>
{rangees}
</table>
<h2>Dernières lignes du journal technique</h2>
{journal}
</body>
</html>
""".format(rangees=rangees, journal=journal)


# --------------------------------------------------------------------------
# Arrêt concerté pour une mise à jour (C5-T2a)
# --------------------------------------------------------------------------

# Le client de mise à jour (maj.py, un AUTRE processus) ne tue jamais le serveur :
# il dépose une demande dans DOSSIER_MAJ, et c'est le serveur, seul à savoir s'il
# reçoit un bilan, qui accepte ou refuse. Aucune route, aucun port : le dossier
# est réservé à SYSTEM et aux administrateurs.

def marquer_activite():
    """Note l'heure de la dernière requête autre que la sonde de santé."""
    global DERNIERE_ACTIVITE
    with _verrou_compteurs:
        DERNIERE_ACTIVITE = time.monotonic()


def entrer_depot():
    global DEPOTS_EN_COURS
    with _verrou_compteurs:
        DEPOTS_EN_COURS += 1


def sortir_depot():
    """Fin d'un dépôt. L'activité est notée AUSSI à la sortie : un bilan de 30 Mo
    peut durer une minute, et le calme se mesure depuis sa fin, pas son début."""
    global DEPOTS_EN_COURS, DERNIERE_ACTIVITE
    with _verrou_compteurs:
        DEPOTS_EN_COURS -= 1
        DERNIERE_ACTIVITE = time.monotonic()


def lire_compteurs():
    """(dépôts en cours, dernière activité) d'un même instant."""
    with _verrou_compteurs:
        return DEPOTS_EN_COURS, DERNIERE_ACTIVITE


def demande_arret_valide(demande):
    """Vrai pour une demande exactement de la forme
    {"jeton": <32 hex>, "calme_secondes": <entier 0..86400>, "demarrage": <bool>}.

    `type() is` et non isinstance : True est un entier pour Python."""
    return (isinstance(demande, dict)
            and set(demande) == {"jeton", "calme_secondes", "demarrage"}
            and isinstance(demande["jeton"], str)
            and _JETON_ARRET.fullmatch(demande["jeton"]) is not None
            and type(demande["calme_secondes"]) is int
            and 0 <= demande["calme_secondes"] <= CALME_MAX_SECONDES
            and type(demande["demarrage"]) is bool)


def decider_arret(demande, depots_en_cours, derniere_activite, demarre_depuis_s,
                  maintenant):
    """(verdict, motif) d'une demande d'arrêt : fonction pure, sans serveur.

    verdict : "accepte" ou "refuse" ; motif : un membre de MOTIFS_ARRET.
    Aucun bilan n'est lu : seuls comptent un dépôt déjà commencé et l'heure de la
    dernière requête (horloge monotone, injectée).

    - un dépôt en cours refuse toujours ;
    - « au démarrage » (PC éteint la nuit) n'accepte que dans les 900 premières
      secondes ET si le serveur n'a reçu AUCUNE requête depuis ;
    - sinon, le serveur doit être calme depuis `calme_secondes` (borne incluse),
      ou n'avoir reçu aucune requête.
    """
    if not demande_arret_valide(demande):
        return "refuse", "demande-invalide"
    if depots_en_cours > 0:
        return "refuse", "depot-en-cours"
    if demande["demarrage"]:
        if demarre_depuis_s > DELAI_DEMARRAGE_MAX_SECONDES:
            return "refuse", "demarrage-depasse"
        if derniere_activite is not None:
            return "refuse", "activite"
        return "accepte", "aucun"
    if derniere_activite is None:
        return "accepte", "aucun"
    if maintenant - derniere_activite >= demande["calme_secondes"]:
        return "accepte", "aucun"
    return "refuse", "activite"


def _effacer_fichier_de_demande(chemin):
    """Efface ce qui occupe le nom d'une demande : fichier, lien (jamais sa
    cible) ou dossier vide. Ce qui ne s'efface pas reste, et sera de nouveau
    ignoré : une surveillance ne doit pas boucler sur une erreur."""
    try:
        os.remove(chemin)
        return
    except OSError:
        pass
    try:
        os.rmdir(chemin)
    except OSError:
        pass


def lire_demande_arret(chemin):
    """(statut, demande) du fichier de demande : "absente", "invalide" ou "ok".

    `lstat` d'abord : un fichier ordinaire est exigé, et un tube nommé ne doit
    jamais être ouvert (l'ouverture bloquerait). Au plus 1 024 octets, JSON
    strict. Pour "invalide", `demande` porte l'objet lu quand il l'a été, afin de
    répondre au jeton s'il est lisible ; None sinon."""
    try:
        info = os.lstat(chemin)
    except FileNotFoundError:
        return "absente", None
    except OSError:
        return "invalide", None
    if not stat.S_ISREG(info.st_mode):
        return "invalide", None
    try:
        with open(chemin, "rb") as f:
            brut = f.read(TAILLE_MAX_DEMANDE_ARRET + 1)
    except OSError:
        return "invalide", None
    if len(brut) > TAILLE_MAX_DEMANDE_ARRET:
        return "invalide", None
    try:
        demande = _json_strict(brut)
    except ValueError:
        return "invalide", None
    if demande_arret_valide(demande):
        return "ok", demande
    return "invalide", demande


def ecrire_reponse_arret(dossier, jeton, verdict, motif):
    """Écrit `arret.reponse` atomiquement ; sans effet si le dossier manque (le
    serveur ne le crée jamais)."""
    corps = json.dumps({"jeton": jeton, "verdict": verdict, "motif": motif},
                       sort_keys=True).encode("utf-8")
    try:
        ecrire_atomiquement(os.path.join(dossier, REPONSE_ARRET), corps)
    except OSError:
        pass


class ArretConcerte(object):
    """Ce que le fil de surveillance transmet à demarrer() : l'événement posé
    quand une demande est acceptée, et le jeton auquel répondre « arrete »."""

    def __init__(self):
        self.evenement = threading.Event()
        self.jeton = None


def traiter_demande_arret(dossier, arret, demarre_depuis_s, maintenant=None):
    """Un passage de la surveillance : lit la demande, répond, l'efface.

    Rend True si l'arrêt est accepté (`arret.jeton` est alors posé). Une demande
    malformée, d'un jeton illisible ou qui n'est pas un fichier est effacée sans
    réponse ; d'un jeton lisible mais de forme invalide, effacée avec la réponse
    « demande-invalide »."""
    chemin = os.path.join(dossier, DEMANDE_ARRET)
    statut, demande = lire_demande_arret(chemin)
    if statut == "absente":
        return False
    if maintenant is None:
        maintenant = time.monotonic()
    depots, activite = lire_compteurs()
    verdict, motif = decider_arret(demande, depots, activite, demarre_depuis_s,
                                   maintenant)
    jeton = demande.get("jeton") if isinstance(demande, dict) else None
    if isinstance(jeton, str) and _JETON_ARRET.fullmatch(jeton):
        ecrire_reponse_arret(dossier, jeton, verdict, motif)
    _effacer_fichier_de_demande(chemin)
    if verdict == "accepte":
        arret.jeton = jeton
        return True
    return False


def effacer_demandes_perimees(dossier):
    """Au démarrage : une demande ou une réponse laissées par un processus
    précédent ne valent rien. Sans cela, une demande oubliée arrêterait le
    serveur dès sa relance."""
    for nom in (DEMANDE_ARRET, REPONSE_ARRET):
        _effacer_fichier_de_demande(os.path.join(dossier, nom))


def surveiller_demande_arret(serveur, arret, fin, dossier=None):
    """Corps du fil de surveillance : sonde le dossier toutes les secondes.

    Sur acceptation : pose l'événement puis `serveur.shutdown()` — appelé depuis
    CE fil, jamais depuis celui de serve_forever(), qu'il attendrait en vain.
    Toute exception est avalée : la surveillance ne doit jamais coûter un dépôt."""
    dossier = DOSSIER_MAJ if dossier is None else dossier
    while not fin.is_set():
        try:
            demarre_depuis = (0 if DEMARRE_MONOTONIC is None
                              else time.monotonic() - DEMARRE_MONOTONIC)
            if traiter_demande_arret(dossier, arret, demarre_depuis):
                arret.evenement.set()
                serveur.shutdown()
                return
        except Exception:
            pass
        fin.wait(INTERVALLE_SURVEILLANCE_SECONDES)


def demarrer_surveillance_arret(serveur, arret):
    """Efface les restes d'un processus précédent, puis lance le fil (démon).
    Rend l'événement qui l'arrête."""
    effacer_demandes_perimees(DOSSIER_MAJ)
    fin = threading.Event()
    fil = threading.Thread(target=surveiller_demande_arret,
                           args=(serveur, arret, fin),
                           name="surveillance-arret", daemon=True)
    fil.start()
    return fin


def attendre_fin_depots(delai, pas=0.05):
    """Attend que plus aucun dépôt ne soit en cours, au plus `delai` secondes.
    Rend True si le compte est revenu à 0."""
    limite = time.monotonic() + delai
    while True:
        if lire_compteurs()[0] <= 0:
            return True
        if time.monotonic() >= limite:
            return False
        time.sleep(pas)


# --------------------------------------------------------------------------
# Serveur
# --------------------------------------------------------------------------

class ServeurBilan(ThreadingHTTPServer):
    """Serveur d'écoute, en double pile quand la machine le permet.

    `localhost` se résout d'abord en ::1 : un serveur lié au seul 0.0.0.0 y
    est injoignable, et le praticien qui ouvre le formulaire sur le PC lui-même
    obtient un refus de connexion. On écoute donc en IPv6 avec IPV6_V6ONLY
    désactivé, ce qui couvre aussi l'IPv4.

    Si la pile IPv6 est absente, ou si IPV6_V6ONLY ne peut pas être désactivé,
    on retombe entièrement en IPv4 : mieux vaut perdre l'accès par ::1 que
    d'écouter en IPv6 pur, ce qui rendrait la tablette incapable de se
    connecter tout en laissant croire que le serveur tourne.
    """

    address_family = socket.AF_INET6
    daemon_threads = True

    # Sous Windows, SO_REUSEADDR n'a pas la sémantique POSIX : il laisse deux
    # processus se lier au même port, l'ancien continuant de répondre pendant
    # que le nouveau annonce un démarrage réussi. Un port déjà pris doit
    # échouer franchement.
    allow_reuse_address = (os.name != "nt")

    def __init__(self, adresse, gestionnaire):
        try:
            super().__init__(adresse, gestionnaire)
        except OSError:
            if self.address_family != socket.AF_INET6:
                raise
            self.address_family = socket.AF_INET
            super().__init__(adresse, gestionnaire)

    def server_bind(self):
        if self.address_family == socket.AF_INET6:
            # Si IPV6_V6ONLY ne peut pas être désactivé, l'écoute resterait
            # purement IPv6. La tablette se connecte en 192.168.1.x : elle
            # serait injoignable, et le serveur paraîtrait pourtant démarré.
            # L'erreur est donc laissée remonter, pour que __init__ retombe
            # franchement en IPv4.
            self.socket.setsockopt(socket.IPPROTO_IPV6,
                                   socket.IPV6_V6ONLY, 0)

        # HTTPServer.server_bind() appelle socket.getfqdn(), c'est-à-dire une
        # résolution DNS inverse, entre le bind() et le listen(). Sur un
        # réseau sans DNS joignable — celui du cabinet comme celui d'un
        # runner d'intégration continue — elle peut bloquer plusieurs
        # dizaines de secondes, pendant lesquelles le serveur semble démarré
        # mais refuse toute connexion. On saute donc l'appel : server_name ne
        # sert qu'aux en-têtes CGI, que ce serveur n'émet pas.
        socketserver.TCPServer.server_bind(self)
        self.server_name = "bilan-posturo"
        self.server_port = self.server_address[1]

    def get_request(self):
        """Remonte les échecs de négociation TLS.

        Quand la socket d'écoute est chiffrée, le handshake a lieu ici, et
        socketserver avale les OSError sans rien journaliser : le navigateur
        affiche une erreur pendant que le serveur reste parfaitement muet.
        """
        try:
            return super().get_request()
        except ssl.SSLError as erreur:
            journaliser("{} TLS refusé : {}\n".format(
                datetime.datetime.now().isoformat(timespec="seconds"), erreur))
            # self.client_address n'est pas disponible à ce stade, et ne
            # doit pas y être cherché : aucune adresse dans technique.log
            # (décision D1).
            journaliser_technique("TLS_REFUSE", "raison={}".format(erreur))
            raise


class Gestionnaire(SimpleHTTPRequestHandler):
    config = None
    dossier_pdf = None
    # Interrupteur de la page d'état (C4-T3), posé dans demarrer(). Fermé par
    # défaut : une page facultative échoue fermée.
    page_etat = False
    # Le logo validé au démarrage (C2-T2), seul chemin que /cabinet rend. Vide
    # par défaut : sans demarrer(), aucun logo n'est proposé (échoue fermé).
    logo = ""
    # L'en-tête Server (C6-T5, D1) : le nom du produit, sans numéro. Celui de la
    # bibliothèque donnait la version exacte de Python à qui scanne le port,
    # /sante et la 401 comprises, sans qu'il ait à s'authentifier.
    server_version = "bilan-posturo"
    sys_version = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=FORMULAIRE, **kwargs)

    def version_string(self):
        # La bibliothèque rend server_version + " " + sys_version : même vide,
        # sys_version laisserait une espace finale.
        return self.server_version

    # --- journalisation ----------------------------------------------------

    def handle_one_request(self):
        # Une connexion persistante sert plusieurs requêtes avec la même
        # instance : sans remise à zéro, une sonde de santé rendrait muettes
        # toutes les requêtes suivantes de la même connexion, et un code de
        # réponse laissé en place ferait porter à cette requête le code
        # d'une précédente.
        self.silencieux = False
        self._code_reponse_technique = 0
        super().handle_one_request()

    def log_request(self, code="-", size="-"):
        # Capture le code AVANT qu'il ne soit mis en forme dans la chaîne de
        # log_message() : log_message() est aussi appelée par log_error()
        # avec une tout autre forme d'arguments (vu par exemple à l'étape 4,
        # évaluation de la fuite), et reconstruire le code à partir du
        # format interne de BaseHTTPRequestHandler serait fragile — une
        # version de Python qui modifie cette chaîne romprait
        # silencieusement l'extraction, sans rien faire échouer d'autre.
        if isinstance(code, HTTPStatus):
            code = code.value
        self._code_reponse_technique = code
        super().log_request(code, size)

    def log_message(self, format, *args):
        # La sonde de santé est interrogée toutes les quelques dizaines de
        # secondes par chaque tablette allumée : la journaliser noierait les
        # dépôts et les erreurs sous des milliers de lignes par jour.
        if getattr(self, "silencieux", False):
            return
        # Les caractères de contrôle venus du client (la ligne de requête est
        # journalisée avant la 401) sont échappés : bruts, ils s'exécuteraient
        # dans la console de qui lit le journal. CPython l'a corrigé dans son
        # log_message en 3.12 ; celui-ci le remplace entièrement (C6-T5, D9).
        journaliser("{} {} {}\n".format(
            datetime.datetime.now().isoformat(timespec="seconds"),
            self.address_string(),
            (format % args).translate(ECHAPPEMENT_CONTROLE)))

        # Voie technique : ni adresse (self.address_string() n'y est jamais
        # passé), ni chemin brut — route est une classe fermée. Le code de
        # réponse n'est fiable que lorsque log_request() a déjà tourné pour
        # cette requête (remis à 0 par handle_one_request sinon) : un appel
        # ad hoc à log_message(), comme ceux de DEPOT ou ECHEC_ECRITURE, n'a
        # pas encore de code de réponse à cet instant.
        commande = getattr(self, "command", None)
        methode = commande if commande in ("GET", "HEAD", "POST") else "autre"
        if commande:
            chemin = getattr(self, "path", "") or ""
            route = classe_route(chemin.split("?", 1)[0].split("#", 1)[0])
        else:
            # Ligne de requête non analysée (414, 505, 400 de syntaxe) : le
            # chemin est vide et classe_route("") rendrait « formulaire », ce
            # qui est faux (C6-T5, D8).
            route = "autre"
        code = getattr(self, "_code_reponse_technique", 0)
        journaliser_technique("REPONSE", "methode={} route={} code={}".format(
            methode, route, code))

    # --- authentification --------------------------------------------------

    def authentifie(self):
        entete = self.headers.get("Authorization", "")
        if not entete.startswith("Basic "):
            return False
        try:
            decode = base64.b64decode(entete[6:]).decode("utf-8")
            utilisateur, _, mot_de_passe = decode.partition(":")
        except (ValueError, binascii.Error, UnicodeDecodeError):
            return False

        # La comparaison porte sur les octets UTF-8 : compare_digest lève
        # TypeError sur une chaîne contenant un caractère non-ASCII, et un
        # identifiant accentué tuerait le thread sans qu'aucune réponse ne
        # parte.
        identifiant_ok = hmac.compare_digest(
            utilisateur.encode("utf-8"),
            self.config["utilisateur"].encode("utf-8"))
        mot_de_passe_ok = verifier_mot_de_passe(mot_de_passe,
                                                self.config["mot_de_passe"])
        # Les deux vérifications sont toujours exécutées : le temps de réponse
        # ne révèle pas si c'est l'identifiant ou le mot de passe qui est faux.
        return identifiant_ok and mot_de_passe_ok

    def exiger_authentification(self):
        # Ni identifiant, ni mot de passe, ni adresse : seule la classe de
        # route, fermée (décision D3). Un compteur d'échecs par identité
        # relève de C6, pas d'ici.
        journaliser_technique("AUTH_REFUSEE", "route={}".format(
            classe_route(self.chemin_demande())))
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("WWW-Authenticate", 'Basic realm="Bilan posturologique"')
        self.send_header("Content-Length", "0")
        self.end_headers()

    # --- en-têtes de sécurité ---------------------------------------------

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        super().end_headers()

    # --- GET ---------------------------------------------------------------

    def chemin_demande(self):
        """Chemin seul, sans chaîne de requête ni fragment."""
        return self.path.split("?", 1)[0].split("#", 1)[0]

    def autorise_lecture(self):
        """Filtre commun à GET et HEAD.

        Normalise le chemin et refuse tout ce qui n'est pas une ressource du
        formulaire. Appliqué aussi à HEAD : sans cela, un HEAD sur
        config.json confirmerait son existence et sa taille.

        Retourne False si la réponse a déjà été envoyée.
        """
        if not self.authentifie():
            self.exiger_authentification()
            return False

        chemin = self.chemin_demande()
        # Seule la forme d'origine (RFC 9112 §3.2.1) est celle d'un navigateur :
        # la forme absolue est réservée aux mandataires, « * » à OPTIONS. Après
        # l'authentification, pour qu'un client sans identifiants reçoive la
        # même 401 vide quel que soit son chemin (C6-T5, D3 et D4). Le message
        # est en ASCII : il voyage dans la ligne d'état, encodée en latin-1.
        if not chemin.startswith("/"):
            self.send_error(HTTPStatus.BAD_REQUEST, "Chemin invalide")
            return False
        if chemin == "/":
            chemin = "/index.html"

        # Le fichier que send_head ouvrira, décodé et normalisé comme lui. Le
        # filtre d'extension et le contrôle portent sur cette seule chaîne :
        # une seconde forme serait un endroit où le filtre juge une chose et
        # le disque en ouvre une autre (C6-T5, D2).
        fichier = self.translate_path(chemin)
        extension = os.path.splitext(fichier)[1].lower()
        if extension not in EXTENSIONS_SERVIES:
            self.send_error(HTTPStatus.FORBIDDEN, "Type de fichier non servi")
            return False

        motif = confiner_fichier_servi(fichier, FORMULAIRE)
        if motif:
            journaliser("{} {} lecture refusée motif={} chemin={!r}\n".format(
                datetime.datetime.now().isoformat(timespec="seconds"),
                self.address_string(), motif, chemin))
            # Libellé anglais repris à l'identique de send_head : le refus doit
            # être indiscernable d'un fichier absent (404, même corps).
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return False

        self.path = chemin
        return True

    def noter_activite(self):
        """Note la requête pour l'arrêt concerté, sauf la sonde de santé : la
        tablette l'interroge en tâche de fond, et la compter interdirait à
        jamais une mise à jour."""
        if self.chemin_demande() != "/sante":
            marquer_activite()

    def do_GET(self):
        self.noter_activite()
        if self.chemin_demande() == "/sante":
            self.repondre_sante(avec_corps=True)
            return
        if self.chemin_demande() == "/cabinet":
            self.repondre_cabinet(avec_corps=True)
            return
        if self.chemin_demande() == "/etat" and self.page_etat:
            self.repondre_etat(avec_corps=True)
            return
        if self.autorise_lecture():
            super().do_GET()

    def do_HEAD(self):
        self.noter_activite()
        if self.chemin_demande() == "/sante":
            self.repondre_sante(avec_corps=False)
            return
        if self.chemin_demande() == "/cabinet":
            self.repondre_cabinet(avec_corps=False)
            return
        if self.chemin_demande() == "/etat" and self.page_etat:
            self.repondre_etat(avec_corps=False)
            return
        if self.autorise_lecture():
            super().do_HEAD()

    def send_head(self):
        # Filet (C6-T5, D6), qui double confiner_fichier_servi : la
        # bibliothèque n'attrape que OSError à l'open(), et une ValueError
        # (octet nul, UnicodeEncodeError) fermait la connexion sans un octet.
        # Elle ne se lève qu'à l'open(), avant tout send_response. Rien d'autre
        # n'est attrapé : une autre exception doit rester visible.
        try:
            return super().send_head()
        except ValueError:
            journaliser("{} {} lecture refusée motif=forme-invalide "
                        "chemin={!r}\n".format(
                            datetime.datetime.now().isoformat(timespec="seconds"),
                            self.address_string(), self.path))
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return None

    def list_directory(self, path):
        # Le formulaire ne sert aucun index de dossier (C6-T5, D7). Il est déjà
        # fermé par le filtre d'extension, mais ce filtre dépend de détails de
        # la bibliothèque qui ont changé entre versions (redirection d'un
        # dossier demandé en %2f, moment où la barre finale est calculée) :
        # cette surcharge le ferme quelle que soit la version.
        self.send_error(HTTPStatus.NOT_FOUND, "File not found")
        return None

    # --- sonde de santé ----------------------------------------------------

    def repondre_sante(self, avec_corps):
        """Répond « je suis là », sans authentification.

        La tablette interroge cette route en tâche de fond pour distinguer les
        pannes, que le navigateur confond toutes en une erreur de connexion :
        serveur arrêté, mauvaise adresse, mot de passe refusé. Elle est donc
        volontairement hors authentification — un 401 ne dirait pas si le
        serveur tourne.

        Elle ne révèle rien de plus que le port ouvert, qui répond déjà 401 à
        qui le sollicite : ni version, ni chemins, ni nombre de bilans.
        """
        self.silencieux = True
        corps = b'{"etat":"ok"}'
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        if avec_corps:
            self.wfile.write(corps)

    # --- identité du cabinet (C2-T1) ----------------------------------------

    def repondre_cabinet(self, avec_corps):
        """Répond l'identité du cabinet, authentifiée contrairement à
        /sante : des coordonnées professionnelles ne sont pas un secret,
        mais rien n'oblige à les offrir à qui scanne le port (décision D2).

        Construit par itération sur CLES_CABINET, jamais par sérialisation
        du sous-dictionnaire lu dans le fichier (décision D4) : un
        config.json bricolé pourrait porter n'importe quoi sous "cabinet",
        la réponse ne rend que ce qu'elle a promis.
        """
        if not self.authentifie():
            self.exiger_authentification()
            return

        cabinet = self.config.get("cabinet") or {}
        donnees = {cle: cabinet.get(cle, "") for cle in CLES_CABINET}
        # Jamais la valeur brute du fichier : seul le chemin validé au
        # démarrage (ou "") est proposé à la tablette.
        donnees["logo"] = self.logo
        corps = json.dumps(donnees, ensure_ascii=False).encode("utf-8")

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        # Pas de Cache-Control ici : end_headers() l'émet déjà, un second
        # appel produirait l'en-tête en double.
        self.end_headers()
        if avec_corps:
            self.wfile.write(corps)

    # --- page d'état (C4-T3) -------------------------------------------------

    def repondre_etat(self, avec_corps):
        """Répond l'état de l'installation, en HTML ou, sur demande, en JSON.

        Authentifiée comme /cabinet, sans l'exception de /sante (D1). Tout
        l'état et le corps sont construits AVANT send_response() : celle-ci
        journalise donc prend le verrou des journaux, que
        dernieres_lignes_techniques() prend aussi, et qui n'est pas réentrant.
        """
        if not self.authentifie():
            self.exiger_authentification()
            return

        etat = construire_etat(self.config, self.dossier_pdf)
        if "application/json" in self.headers.get("Accept", "").lower():
            type_contenu = "application/json; charset=utf-8"
            corps = rendre_etat_json(etat).encode("utf-8")
        else:
            type_contenu = "text/html; charset=utf-8"
            corps = rendre_etat_html(etat).encode("utf-8")

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", type_contenu)
        if type_contenu.startswith("text/html"):
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; style-src 'unsafe-inline'")
        self.send_header("Content-Length", str(len(corps)))
        # Pas de Cache-Control ici : end_headers() l'émet déjà.
        self.end_headers()
        if avec_corps:
            self.wfile.write(corps)

    # --- POST /depot -------------------------------------------------------

    def do_POST(self):
        # Le compte couvre TOUT le traitement, lecture du corps comprise : c'est
        # elle qui dure quand la tablette envoie un bilan par un Wi-Fi faible. Le
        # décrément est dans un finally, que la requête échoue ou non.
        self.noter_activite()
        entrer_depot()
        try:
            self.traiter_post()
        finally:
            sortir_depot()

    def traiter_post(self):
        if not self.authentifie():
            self.exiger_authentification()
            return

        if self.path.split("?", 1)[0] != "/depot":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        try:
            taille = int(self.headers.get("Content-Length", 0))
        except ValueError:
            journaliser_technique("DEPOT",
                                  detail_refus_depot("content-length-invalide"))
            self.repondre_json(HTTPStatus.BAD_REQUEST,
                               {"erreur": "Content-Length invalide"})
            return

        if taille <= 0:
            journaliser_technique("DEPOT", detail_refus_depot("corps-vide"))
            self.repondre_json(HTTPStatus.BAD_REQUEST,
                               {"erreur": "Corps de requête vide"})
            return
        if taille > TAILLE_MAX:
            journaliser_technique("DEPOT", detail_refus_depot("trop-volumineux"))
            self.repondre_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                               {"erreur": "Fichier trop volumineux"})
            return

        contenu = self.rfile.read(taille)
        if len(contenu) != taille:
            # Connexion coupée en cours d'envoi : le PDF serait tronqué.
            journaliser_technique("DEPOT",
                                  detail_refus_depot("transfert-interrompu"))
            self.repondre_json(HTTPStatus.BAD_REQUEST,
                               {"erreur": "Transfert interrompu"})
            return

        # Le nom voyage en base64 : un en-tête HTTP ne transporte pas
        # fiablement les accents.
        nom_brut = "bilan.pdf"
        entete_nom = self.headers.get("X-Fichier")
        if entete_nom:
            try:
                nom_brut = base64.b64decode(entete_nom).decode("utf-8")
            except (ValueError, binascii.Error, UnicodeDecodeError):
                pass

        if not contenu.startswith(b"%PDF"):
            journaliser_technique("DEPOT", detail_refus_depot("non-pdf"))
            self.repondre_json(HTTPStatus.BAD_REQUEST,
                               {"erreur": "Le fichier reçu n'est pas un PDF"})
            return

        nom = assainir_nom(nom_brut)
        destination = chemin_libre(self.dossier_pdf, nom)

        try:
            ecrire_atomiquement(destination, contenu)
        except OSError as erreur:
            self.log_message("ECHEC ecriture %s : %s", destination, erreur)
            # errno/strerror seuls, jamais str(erreur) : il contient le
            # chemin complet, donc le nom du patient (décision D4).
            journaliser_technique("ECHEC_ECRITURE", detail_echec_ecriture(erreur))
            self.repondre_json(HTTPStatus.INTERNAL_SERVER_ERROR,
                               {"erreur": "Écriture impossible sur le PC"})
            return

        self.log_message("DEPOT %s (%d octets)",
                         os.path.basename(destination), len(contenu))
        journaliser_technique("DEPOT", detail_depot_ok(len(contenu)))
        # Indépendant de l'interrupteur du journal technique (D7).
        global DERNIER_DEPOT
        DERNIER_DEPOT = datetime.datetime.now().isoformat(timespec="seconds")
        self.repondre_json(HTTPStatus.OK, {
            "ok": True,
            "fichier": os.path.basename(destination),
            "octets": len(contenu),
        })

    def repondre_json(self, statut, donnees):
        corps = json.dumps(donnees, ensure_ascii=False).encode("utf-8")
        self.send_response(statut)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)


# --------------------------------------------------------------------------
# Démarrage
# --------------------------------------------------------------------------

def signaler_refus_racine_web(motif, dossier_pdf):
    """Trace le refus de démarrer : journal nominatif (chemins résolus),
    journal technique (motif seul) et console. Écrit avant toute ouverture de
    socket ; ne crée rien sous la racine web."""
    try:
        web = os.path.realpath(FORMULAIRE)
        cible = os.path.realpath(RACINE if motif == "racine-cabinet"
                                 else dossier_pdf)
    except (OSError, ValueError):
        web = cible = "?"
    # !r : un chemin peut porter un retour à la ligne ou un caractère de
    # contrôle qui forgerait une ligne du journal nominatif.
    journaliser("{} DEMARRAGE refusé motif={} racine_web={!r} cible={!r}\n"
                .format(datetime.datetime.now().isoformat(timespec="seconds"),
                        motif, web, cible))
    journaliser_technique("DEMARRAGE_REFUSE", detail_refus_demarrage(motif))
    if motif == "racine-cabinet":
        print("Refus de démarrer : le dossier formulaire mène à la racine du "
              "cabinet ou au-dessus ; config.json et les journaux seraient "
              "servis à la tablette.")
        print("Remettez à sa place le dossier formulaire du paquet : un vrai "
              "dossier, ni raccourci ni jonction.")
    elif motif == "dossier-pdf":
        print("Refus de démarrer : le dossier des bilans (dossier_pdf) se "
              "trouve dans le dossier formulaire, servi à la tablette.")
        print("Choisissez dans config.json un dossier_pdf hors du dossier "
              "formulaire.")
    else:
        print("Refus de démarrer : impossible de vérifier l'emplacement du "
              "dossier formulaire.")
        print("Vérifiez les droits sur le dossier d'installation.")


def demarrer():
    config = charger_config()
    if config is None or not config.get("mot_de_passe"):
        print("Aucun mot de passe défini.")
        print("Lancez d'abord :  python3 serveur/serveur.py --config")
        return 1

    # Posés avant tout refus : l'interrupteur journal_technique et la durée de
    # conservation s'appliquent aussi à la ligne de refus (C6-T7).
    global JOURNAL_TECHNIQUE_ACTIF
    JOURNAL_TECHNIQUE_ACTIF = config["journal_technique"]
    global CONSERVATION_JOURNAUX_MOIS
    CONSERVATION_JOURNAUX_MOIS = config["conservation_journaux_mois"]

    # Un cabinet mis à jour sans relancer --config n'a pas encore saisi son
    # identité : ce n'est pas un refus de démarrer (le formulaire reste
    # utile pour tout sauf l'export), mais un bilan ne pourra pas sortir
    # (D7) tant que l'identité manque. L'avertissement nomme le geste.
    identite_absente = not identite_renseignee(config)

    dossier_pdf = config["dossier_pdf"]
    if not os.path.isabs(dossier_pdf):
        dossier_pdf = os.path.join(RACINE, dossier_pdf)
    # Avant makedirs : un refus ne crée rien sous la racine web (C6-T7), et
    # avant toute ouverture de socket.
    motif = motif_refus_racine_web(FORMULAIRE, RACINE, dossier_pdf)
    if motif:
        signaler_refus_racine_web(motif, dossier_pdf)
        return 1
    os.makedirs(dossier_pdf, exist_ok=True)

    Gestionnaire.config = config
    Gestionnaire.dossier_pdf = dossier_pdf
    Gestionnaire.page_etat = config.get("page_etat") is True
    # Posé avant serve_forever() : /cabinet ne rend jamais le chemin brut.
    logo_servi, motif_logo = valider_logo(config["cabinet"]["logo"])
    Gestionnaire.logo = logo_servi

    certificat = os.path.join(RACINE, config["certificat"])
    cle = os.path.join(RACINE, config["cle_privee"])

    # Pas de repli silencieux en clair : le formulaire transporte des données
    # de santé et le mot de passe voyage en HTTP Basic, donc en base64
    # réversible. Sans TLS, les deux circulent en clair sur le réseau du
    # cabinet. Mieux vaut un refus visible qu'un serveur qui paraît marcher.
    manquants = [os.path.basename(c) for c in (certificat, cle)
                 if not os.path.exists(c)]
    if manquants:
        print("Refus de démarrer : {} introuvable.".format(
            " et ".join(manquants)))
        print("Générez le certificat :  python3 serveur/generer_autorite.py <ip>")
        return 1

    contexte = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexte.minimum_version = ssl.TLSVersion.TLSv1_2
    # Sans ALPN, Chrome ferme la connexion sans envoyer un octet là où curl
    # bascule sans bruit en HTTP/1.1 : un ERR_EMPTY_RESPONSE sans la moindre
    # trace côté serveur.
    contexte.set_alpn_protocols(["http/1.1"])
    try:
        contexte.load_cert_chain(certificat, cle)
    except (ssl.SSLError, OSError) as erreur:
        print("Certificat inutilisable : {}".format(erreur))
        print("Regénérez-le :  python3 serveur/generer_autorite.py <ip>")
        return 1

    try:
        serveur = ServeurBilan(("", config["port"]), Gestionnaire)
    except OSError as erreur:
        print("Port {} indisponible : {}".format(config["port"], erreur))
        print("Une autre instance du serveur tourne probablement déjà.")
        return 1

    serveur.socket = contexte.wrap_socket(serveur.socket, server_side=True)

    global VERSION_EN_COURS
    VERSION_EN_COURS = lire_version()

    print("Bilan posturologique — serveur démarré")
    print("  sur ce PC     : https://localhost:{}".format(config["port"]))
    print("  tablette      : https://<ip-du-pc>:{}".format(config["port"]))
    print("  version       : {}".format(VERSION_EN_COURS))
    print("  identifiant   : {}".format(config["utilisateur"]))
    print("  dépôt des PDF : {}".format(dossier_pdf))
    print("  journal       : {}".format(JOURNAL))
    if identite_absente:
        print("\nAVERTISSEMENT : identité du cabinet non configurée — les "
              "bilans ne pourront pas être exportés.")
        print("Lancez :  python3 serveur/serveur.py --config")
    if motif_logo:
        print("\nAVERTISSEMENT : logo refusé ({}) — l'en-tête sortira sans "
              "logo.".format(motif_logo))
    print("\nCtrl+C pour arrêter.\n")

    purger_au_demarrage()
    _, arret_purge = demarrer_purge_periodique()

    empreinte = empreinte_certificat(certificat)
    global CERTIFICAT_CHARGE
    CERTIFICAT_CHARGE = dict(lire_certificat(certificat), empreinte=empreinte)
    journaliser_technique("DEMARRAGE", "version={} port={} certificat={} {}".format(
        VERSION_EN_COURS, config["port"], empreinte, verdict_certificat(empreinte)))
    if motif_logo:
        # !r : le chemin est une saisie libre, qu'un retour à la ligne ou un
        # caractère de contrôle ne doit pas laisser forger une ligne du
        # journal nominatif. Il n'entre jamais dans technique.log (D8).
        journaliser("{} LOGO refusé motif={} chemin={!r}\n".format(
            datetime.datetime.now().isoformat(timespec="seconds"),
            motif_logo, config["cabinet"]["logo"]))
        journaliser_technique("LOGO", detail_refus_logo(motif_logo))

    global DEMARRE_LE, DEMARRE_MONOTONIC
    DEMARRE_LE = datetime.datetime.now().isoformat(timespec="seconds")
    DEMARRE_MONOTONIC = time.monotonic()
    motif_arret = "autre"
    arret_concerte = ArretConcerte()
    fin_surveillance = None
    try:
        # Dans le try : la surveillance est lancée là où le finally qui écrit
        # ARRET la couvre, et jamais avant que serve_forever() soit atteint.
        fin_surveillance = demarrer_surveillance_arret(serveur, arret_concerte)
        serveur.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du serveur.")
        motif_arret = "interruption"
    finally:
        if fin_surveillance is not None:
            fin_surveillance.set()
        if arret_concerte.evenement.is_set():
            # Arrêt demandé par maj.py et accepté : un dépôt qui aurait commencé
            # entre la décision et l'arrêt de la boucle est attendu avant de
            # quitter, sans quoi la fin du processus le tuerait.
            motif_arret = "mise-a-jour"
            attendre_fin_depots(DELAI_FIN_DEPOTS_SECONDES)
        # Le port se libère d'abord, sans dépendre d'une écriture de
        # journal : un journal ne doit jamais coûter autre chose que
        # lui-même (§10 du contrat), et surtout pas la disponibilité du
        # port pour une relance.
        serveur.server_close()
        arret_purge.set()
        journaliser_technique("ARRET", "motif={}".format(motif_arret))
    if arret_concerte.evenement.is_set():
        # DERNIÈRE instruction avant la sortie : « arrete » ne se lit qu'une fois
        # la ligne ARRET écrite et le port libéré, c'est ce que maj.py attend.
        ecrire_reponse_arret(DOSSIER_MAJ, arret_concerte.jeton, "arrete", "aucun")
    return 0


def main():
    analyseur = argparse.ArgumentParser(
        description="Serveur du bilan posturologique.")
    analyseur.add_argument("--config", action="store_true",
                           help="configure l'identifiant et le mot de passe")
    arguments = analyseur.parse_args()

    if arguments.config:
        return definir_mot_de_passe()
    return demarrer()


if __name__ == "__main__":
    sys.exit(main())
