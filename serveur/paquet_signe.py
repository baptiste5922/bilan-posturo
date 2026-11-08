"""Paquet de mise à jour signé : format du manifeste et vérification (C5-T1).

Un paquet signé, c'est trois fichiers posés côte à côte :

    BilanPosturo-2026-11-08.zip                  l'archive, telle que la fabrique la CI
    BilanPosturo-2026-11-08.zip.manifeste.json   ce qu'elle doit contenir, empreintes comprises
    BilanPosturo-2026-11-08.zip.manifeste.sig    64 octets : signature Ed25519 du manifeste

Le manifeste porte l'empreinte de l'archive ENTIÈRE. Rien de ce qui n'est pas
authentifié n'est analysé : on vérifie d'abord 64 octets de signature sur au plus
1 Mio de manifeste, puis l'empreinte de l'archive, et seulement ensuite on
confie l'archive à `zipfile`. Un manifeste rangé DANS le zip obligerait à lire le
répertoire central d'une archive hostile avant toute preuve.

Ce module ne décompresse jamais rien sur le disque. Il décide si un paquet peut
être installé ; c'est C5-T2 qui l'installera, et ce qui s'exécutera ensuite aura
les droits du compte SYSTEM, sur le PC où se trouvent les bilans. Une erreur ici
est une exécution de code à distance sur tout le parc : toute règle est donc
fermée (liste blanche, schéma exact, formats inconnus refusés), et le vérificateur
installé est celui qui jugera la mise à jour SUIVANTE.

Les clés de confiance se passent EN ARGUMENT. L'appelant doit leur donner celles
déjà installées sur le PC, JAMAIS celles du paquet entrant : sinon l'attaquant
fournirait sa clé avec son paquet.

Bibliothèque standard seule. Documentation : docs/contrats/C5-T1.md.
"""

import hashlib
import json
import os
import re
import stat
import struct
import types
import zipfile
import zlib
from collections import namedtuple

import signature_ed25519

# Codes de refus : fermés, et sans chemin, pour pouvoir entrer un jour dans
# technique.log (qui circule). Le détail, lui, peut nommer un chemin du paquet :
# il n'est fait que pour la console de l'éditeur et pour journal.log.
CODES = (
    "MANIFESTE_TROP_GRAND",
    "SIGNATURE_INVALIDE",
    "MANIFESTE_MALFORME",
    "TYPE_INCONNU",
    "FORMAT_INCONNU",
    "CLES_DE_CONFIANCE_INVALIDES",
    "VERSION_MALFORMEE",
    "VERSION_INSTALLEE_ILLISIBLE",
    "VERSION_NON_SUPERIEURE",
    "VERSION_MINIMALE_NON_ATTEINTE",
    "CLIENT_DIFFERENT",
    "CHEMIN_DANGEREUX",
    "CHEMIN_EN_DOUBLE",
    "ARCHIVE_DIFFERENTE",
    "ARCHIVE_ILLISIBLE",
    "ENTREE_INTERDITE",
    "FICHIER_EN_TROP",
    "FICHIER_MANQUANT",
    "FICHIER_ALTERE",
    "VERSION_INCOHERENTE",
)

TAILLE_MAX_MANIFESTE = 1024 * 1024
TAILLE_MAX_CLES = 64 * 1024
NOMBRE_MAX_CLES = 4
NOMBRE_MAX_FICHIERS = 10000
OCTETS_MAX_TOTAL = 256 * 1024 * 1024
LONGUEUR_MAX_CHEMIN = 240
TAILLE_BLOC = 1024 * 1024
# formulaire/version.json est lu en mémoire pour être comparé au manifeste : il
# tient en quelques dizaines d'octets, et rien ne justifie d'en charger davantage.
TAILLE_MAX_VERSION = 4096

FORMAT_MANIFESTE = 1
TYPE_MANIFESTE = "manifeste-mise-a-jour"
PRODUIT = "bilan-posturo"
CHEMIN_VERSION = "formulaire/version.json"

ManifesteVerifie = namedtuple(
    "ManifesteVerifie", ("version", "version_minimale", "date", "client", "fichiers"))
ManifesteVerifie.__doc__ = (
    "Ce qu'un paquet vérifié a le droit de dire. `fichiers` associe chaque chemin "
    "à (taille, sha256) ; le tout est en lecture seule.")


class PaquetRefuse(Exception):
    """Refus motivé. `code` est l'un de CODES, `detail` un texte pour l'éditeur."""

    def __init__(self, code, detail=""):
        if code not in CODES:
            raise ValueError("code de refus inconnu : %r" % (code,))
        Exception.__init__(self, "%s : %s" % (code, detail) if detail else code)
        self.code = code
        self.detail = detail


# Erreurs que `zipfile` et `zlib` lèvent sur une archive abîmée ou hostile. Une
# archive qui ne se lit pas est un refus, jamais une exception qui remonte.
_ERREURS_ZIP = (zipfile.BadZipFile, zipfile.LargeZipFile, NotImplementedError,
                RuntimeError, EOFError, OSError, zlib.error, ValueError,
                struct.error, OverflowError)


# --------------------------------------------------------------------------
# Versions et chemins
# --------------------------------------------------------------------------

# `re.fullmatch` et des classes ASCII explicites : `$` accepterait un saut de ligne
# final, et `\d` des chiffres d'autres écritures.
_VERSION = re.compile(r"(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})")
_SEGMENT = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]*")
_RESERVES_WINDOWS = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + ["COM%d" % n for n in range(10)] + ["LPT%d" % n for n in range(10)])


def analyser_version(texte):
    """(majeur, mineur, correctif) d'un numéro `X.Y.Z`, ou PaquetRefuse.

    Ni zéro de tête ni suffixe : `1.10.0` doit se comparer comme un nombre à
    `1.9.0` (comme des chaînes, il lui serait inférieur), et `1.2.0-beta` n'a pas
    d'ordre défini.
    """
    if not isinstance(texte, str):
        raise PaquetRefuse("VERSION_MALFORMEE", "version absente ou de mauvais type")
    correspondance = _VERSION.fullmatch(texte)
    if correspondance is None:
        raise PaquetRefuse("VERSION_MALFORMEE",
                           "forme attendue X.Y.Z, reçu %r" % (texte[:40],))
    return tuple(int(partie) for partie in correspondance.groups())


def valider_chemin(nom):
    """Lève PaquetRefuse("CHEMIN_DANGEREUX") si `nom` n'est pas un chemin admis.

    Liste blanche plutôt que motifs interdits, toujours incomplets (flux NTFS
    `a:b`, noms réservés, points finaux, normalisation Unicode) : un alphabet
    fermé [A-Za-z0-9._-] et `/`. Elle refuse d'office `\\`, `:`, la lettre de
    lecteur, le chemin absolu, NUL, l'espace et tout caractère non ASCII.
    """
    if not isinstance(nom, str) or nom == "":
        raise PaquetRefuse("CHEMIN_DANGEREUX", "chemin vide ou de mauvais type")
    if len(nom) > LONGUEUR_MAX_CHEMIN:
        raise PaquetRefuse("CHEMIN_DANGEREUX",
                           "chemin de plus de %d caractères" % LONGUEUR_MAX_CHEMIN)
    for segment in nom.split("/"):
        # Pas de point initial : ni `.`, ni `..`, ni fichier caché.
        if _SEGMENT.fullmatch(segment) is None:
            raise PaquetRefuse("CHEMIN_DANGEREUX", "chemin refusé : %r" % (nom,))
        # Windows retire les points finaux : `a.` désignerait `a`.
        if segment.endswith("."):
            raise PaquetRefuse("CHEMIN_DANGEREUX", "point final : %r" % (nom,))
        # `CON.txt` est le périphérique CON : l'extension ne protège pas.
        if segment.split(".", 1)[0].upper() in _RESERVES_WINDOWS:
            raise PaquetRefuse("CHEMIN_DANGEREUX",
                               "nom réservé de Windows : %r" % (nom,))


# --------------------------------------------------------------------------
# JSON strict
# --------------------------------------------------------------------------

def _objet_sans_doublon(paires):
    objet = {}
    for cle, valeur in paires:
        if cle in objet:
            raise ValueError("clé en double : %r" % (cle,))
        objet[cle] = valeur
    return objet


def _refuser_constante(nom):
    raise ValueError("constante JSON interdite : %s" % nom)


def _lire_json_strict(octets, code):
    """Décode et analyse du JSON, en refusant tout ce qui prête à deux lectures.

    UTF-8 strict sans BOM, aucune clé en double (deux lecteurs retiendraient l'une
    ou l'autre), ni NaN ni Infinity. Toute faute devient PaquetRefuse(`code`).
    """
    try:
        if octets.startswith(b"\xef\xbb\xbf"):
            raise ValueError("marque d'ordre des octets (BOM) interdite")
        return json.loads(octets.decode("utf-8"),
                          object_pairs_hook=_objet_sans_doublon,
                          parse_constant=_refuser_constante)
    except (ValueError, RecursionError) as erreur:
        raise PaquetRefuse(code, "JSON refusé : %s" % (str(erreur)[:120],))


def _entier_positif(valeur):
    # type() et non isinstance() : True est un int pour Python.
    return type(valeur) is int and valeur >= 0


def _empreinte_valide(valeur):
    return isinstance(valeur, str) and re.fullmatch(r"[0-9a-f]{64}", valeur) is not None


# --------------------------------------------------------------------------
# Clés de confiance
# --------------------------------------------------------------------------

_NOM_DE_CLE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


def charger_cles_de_confiance(octets):
    """Les clés publiques (tuple de 32 octets) d'un `cles_publication.json`.

    Format fermé : {"format": 1, "cles": [{"nom": "...", "publique": "<64 hex>"}]}.
    Une clé qui ne se décode pas, ou d'ordre faible, ne pourrait jamais rien
    vérifier : elle est refusée ici plutôt que de dormir dans la liste.
    """
    def refuser(detail):
        raise PaquetRefuse("CLES_DE_CONFIANCE_INVALIDES", detail)

    if type(octets) is not bytes or len(octets) > TAILLE_MAX_CLES:
        refuser("fichier absent, de mauvais type ou trop grand")
    contenu = _lire_json_strict(octets, "CLES_DE_CONFIANCE_INVALIDES")
    if not isinstance(contenu, dict) or set(contenu) != {"format", "cles"}:
        refuser("clés attendues : format, cles")
    if type(contenu["format"]) is not int or contenu["format"] != 1:
        refuser("format de liste inconnu")
    liste = contenu["cles"]
    if not isinstance(liste, list) or not 1 <= len(liste) <= NOMBRE_MAX_CLES:
        refuser("entre 1 et %d clés attendues" % NOMBRE_MAX_CLES)
    cles = []
    for entree in liste:
        if not isinstance(entree, dict) or set(entree) != {"nom", "publique"}:
            refuser("chaque clé porte exactement : nom, publique")
        nom, publique = entree["nom"], entree["publique"]
        if not isinstance(nom, str) or _NOM_DE_CLE.fullmatch(nom) is None:
            refuser("nom de clé invalide")
        if not _empreinte_valide(publique):
            refuser("clé publique : 64 chiffres hexadécimaux minuscules attendus")
        brute = bytes.fromhex(publique)
        if brute in cles:
            refuser("clé publique en double")
        if not signature_ed25519._point_acceptable(brute):
            refuser("clé qui ne se décode pas en un point utilisable")
        cles.append(brute)
    return tuple(cles)


# --------------------------------------------------------------------------
# Manifeste
# --------------------------------------------------------------------------

_CLES_MANIFESTE = frozenset((
    "archive", "client", "date", "fichiers", "format", "produit", "type",
    "version", "version_minimale"))
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
_CLIENT = re.compile(r"cabinet-[0-9]{2,}")


def _valider_taille_et_empreinte(objet, nom):
    if not isinstance(objet, dict) or set(objet) != {"sha256", "taille"}:
        raise PaquetRefuse("MANIFESTE_MALFORME",
                           "%s : exactement sha256 et taille attendus" % nom)
    if not _empreinte_valide(objet["sha256"]) or not _entier_positif(objet["taille"]):
        raise PaquetRefuse("MANIFESTE_MALFORME",
                           "%s : empreinte ou taille invalide" % nom)


def lire_manifeste(octets, signature, cles):
    """Le manifeste (dict) des `octets` signés par l'une des `cles`, ou PaquetRefuse.

    L'ORDRE est la règle : taille, puis signature sur les octets exacts, et
    seulement alors décodage et schéma. Un manifeste malformé mais non signé doit
    donc donner SIGNATURE_INVALIDE, jamais un code qui révèle comment il est lu.
    Le manifeste n'est jamais resérialisé : ce qui a été signé est ce qui a été lu.
    """
    if type(octets) is not bytes:
        raise PaquetRefuse("MANIFESTE_MALFORME", "le manifeste doit être en octets")
    if len(octets) > TAILLE_MAX_MANIFESTE:
        raise PaquetRefuse("MANIFESTE_TROP_GRAND",
                           "plus de %d octets" % TAILLE_MAX_MANIFESTE)
    try:
        cles = tuple(cles)
    except TypeError:
        cles = ()
    # Aucune clé : aucune signature ne peut être valide (any() de rien est faux).
    if not any(signature_ed25519.verifier(cle, octets, signature) for cle in cles):
        raise PaquetRefuse("SIGNATURE_INVALIDE",
                           "aucune clé de confiance ne valide cette signature")

    manifeste = _lire_json_strict(octets, "MANIFESTE_MALFORME")
    if not isinstance(manifeste, dict):
        raise PaquetRefuse("MANIFESTE_MALFORME", "objet JSON attendu")
    # Type et format d'abord : un format futur aura d'autres clés, et doit être
    # nommé comme inconnu plutôt que comme malformé.
    if "type" in manifeste and manifeste["type"] != TYPE_MANIFESTE:
        raise PaquetRefuse("TYPE_INCONNU", "type de document non pris en charge")
    if "format" in manifeste and (type(manifeste["format"]) is not int
                                  or manifeste["format"] != FORMAT_MANIFESTE):
        raise PaquetRefuse("FORMAT_INCONNU", "format de manifeste non pris en charge")
    if set(manifeste) != _CLES_MANIFESTE:
        raise PaquetRefuse("MANIFESTE_MALFORME", "clés du manifeste inattendues")

    if manifeste["produit"] != PRODUIT:
        raise PaquetRefuse("MANIFESTE_MALFORME", "produit inconnu")
    for nom, motif in (("client", _CLIENT), ("date", _DATE)):
        valeur = manifeste[nom]
        if not isinstance(valeur, str) or motif.fullmatch(valeur) is None:
            raise PaquetRefuse("MANIFESTE_MALFORME", "%s invalide" % nom)
    for nom in ("version", "version_minimale"):
        if not isinstance(manifeste[nom], str):
            raise PaquetRefuse("MANIFESTE_MALFORME", "%s invalide" % nom)
    _valider_taille_et_empreinte(manifeste["archive"], "archive")
    fichiers = manifeste["fichiers"]
    if not isinstance(fichiers, dict):
        raise PaquetRefuse("MANIFESTE_MALFORME", "fichiers : objet attendu")
    for chemin, description in fichiers.items():
        _valider_taille_et_empreinte(description, "fichier")
    return manifeste


# --------------------------------------------------------------------------
# Vérification d'un paquet
# --------------------------------------------------------------------------

def _lire_borne(flux, taille, garder=False):
    """(sha256 hexadécimal, octets lus, contenu ou None), en lisant AU PLUS taille + 1.

    Un octet de plus que la taille annoncée suffit à constater qu'une entrée
    déborde ; en lire davantage ferait d'une bombe de décompression un déni de
    service.
    """
    condensat = hashlib.sha256()
    morceaux = [] if garder else None
    lus = 0
    limite = taille + 1
    while lus < limite:
        bloc = flux.read(min(TAILLE_BLOC, limite - lus))
        if not bloc:
            break
        condensat.update(bloc)
        if garder:
            morceaux.append(bloc)
        lus += len(bloc)
    return condensat.hexdigest(), lus, (b"".join(morceaux) if garder else None)


def _verifier_empreinte_archive(fichier, archive):
    """Taille puis SHA-256 de l'archive ouverte, avant tout `zipfile`."""
    try:
        etat = os.fstat(fichier.fileno())
        if not stat.S_ISREG(etat.st_mode):
            raise PaquetRefuse("ARCHIVE_ILLISIBLE", "l'archive n'est pas un fichier")
        if etat.st_size != archive["taille"]:
            raise PaquetRefuse("ARCHIVE_DIFFERENTE", "taille différente de celle signée")
        condensat = hashlib.sha256()
        while True:
            bloc = fichier.read(TAILLE_BLOC)
            if not bloc:
                break
            condensat.update(bloc)
    except OSError as erreur:
        raise PaquetRefuse("ARCHIVE_ILLISIBLE", "lecture impossible : %s" % erreur)
    if condensat.hexdigest() != archive["sha256"]:
        raise PaquetRefuse("ARCHIVE_DIFFERENTE", "empreinte différente de celle signée")


# Champ supplémentaire « Unicode Path » d'Info-ZIP : un second nom, que
# `zipfile` applique à partir de Python 3.12 et ignore avant.
CHAMP_NOM_UNICODE = 0x7075


def _porte_un_champ_de_nom(extra):
    """Vrai si le champ supplémentaire d'une entrée contient un champ de nom.

    Parcours des blocs (type, longueur, données) sans rien interpréter d'autre ;
    un bloc tronqué arrête la lecture, `zipfile` refusant de toute façon l'archive.
    """
    i = 0
    while i + 4 <= len(extra):
        type_champ, longueur = struct.unpack_from("<HH", extra, i)
        if type_champ == CHAMP_NOM_UNICODE:
            return True
        i += 4 + longueur
    return False


def _controler_entrees(entrees):
    """Gardes de l'étape 6 sur chaque entrée de l'archive ; rend (fichiers, dossiers).

    Le nom jugé est le nom BRUT (`orig_filename`) : `zipfile` y remplace `\\` par
    `/` sous Windows seulement, et tronque au premier NUL ; juger le nom corrigé
    laisserait passer sur un système ce que l'autre extrairait ailleurs.

    Deux barrières contre un nom qui change selon la version de Python. La première
    refuse tout champ de nom supplémentaire, en lisant `extra` : le verdict est le
    même sous 3.9 (qui l'ignore) et sous 3.12 et plus (qui l'applique). La seconde,
    la comparaison du nom brut au nom corrigé, rattrape ce que la première n'aurait
    pas prévu.
    """
    fichiers, dossiers, vus = {}, set(), set()
    for entree in entrees:
        brut = entree.orig_filename
        if _porte_un_champ_de_nom(entree.extra):
            raise PaquetRefuse("CHEMIN_DANGEREUX",
                               "entrée à champ de nom supplémentaire : %r" % (brut,))
        if brut != entree.filename:
            raise PaquetRefuse("CHEMIN_DANGEREUX",
                               "nom d'entrée modifié par zipfile : %r" % (brut,))
        est_dossier = brut.endswith("/")
        nom = brut[:-1] if est_dossier else brut
        valider_chemin(nom)
        if est_dossier and entree.file_size != 0:
            raise PaquetRefuse("CHEMIN_DANGEREUX",
                               "entrée à nom de dossier qui porte des données : %r" % (brut,))
        if nom.casefold() in vus:
            raise PaquetRefuse("CHEMIN_EN_DOUBLE", "entrée en double : %r" % (nom,))
        vus.add(nom.casefold())
        if (entree.external_attr >> 16) & 0o170000 == 0o120000:
            raise PaquetRefuse("ENTREE_INTERDITE", "lien symbolique : %r" % (nom,))
        if entree.flag_bits & 0x1:
            raise PaquetRefuse("ENTREE_INTERDITE", "entrée chiffrée : %r" % (nom,))
        if entree.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise PaquetRefuse("ENTREE_INTERDITE", "compression non admise : %r" % (nom,))
        if est_dossier:
            dossiers.add(nom)
        else:
            fichiers[nom] = entree
    return fichiers, dossiers


def _parents_stricts(chemins):
    parents = set()
    for chemin in chemins:
        morceaux = chemin.split("/")
        for i in range(1, len(morceaux)):
            parents.add("/".join(morceaux[:i]))
    return parents


def _refuser_fichier_et_dossier_de_meme_nom(fichiers, dossiers=()):
    """Refuse un nom qui serait à la fois un fichier et un dossier.

    `…/x` et `…/x/y` ne s'extraient pas sous Windows (ni ailleurs) : le même nom
    ne peut désigner les deux. Le code est CHEMIN_EN_DOUBLE, celui d'un même nom
    pris deux fois : il n'y a pas de motif nouveau, seulement une autre manière
    d'en avoir deux. La casse est ignorée, comme pour les doublons.
    """
    noms = {nom.casefold() for nom in fichiers}
    dossiers_pris = {p.casefold() for p in _parents_stricts(fichiers)}
    dossiers_pris.update(d.casefold() for d in dossiers)
    communs = sorted(noms & dossiers_pris)
    if communs:
        raise PaquetRefuse("CHEMIN_EN_DOUBLE",
                           "nom à la fois fichier et dossier : %r" % (communs[0],))


def verifier_paquet(chemin_archive, octets_manifeste, signature, cles,
                    version_installee, client_attendu):
    """Vérifie un trio (archive, manifeste, signature) ; rend un ManifesteVerifie.

    `cles` : les clés de confiance DÉJÀ INSTALLÉES (jamais celles du paquet).
    Toute autre issue qu'un ManifesteVerifie est une PaquetRefuse à code fermé ;
    aucune autre exception ne sort. Rien n'est extrait sur le disque.
    """
    # 1. Authentifier le manifeste.
    manifeste = lire_manifeste(octets_manifeste, signature, cles)

    # 2. Versions : strictement supérieure à l'installée, jamais d'horloge.
    version = analyser_version(manifeste["version"])
    minimale = analyser_version(manifeste["version_minimale"])
    try:
        installee = analyser_version(version_installee)
    except PaquetRefuse as erreur:
        raise PaquetRefuse("VERSION_INSTALLEE_ILLISIBLE", erreur.detail)
    if minimale > version:
        raise PaquetRefuse("MANIFESTE_MALFORME",
                           "version minimale supérieure à la version du paquet")
    if not version > installee:
        raise PaquetRefuse("VERSION_NON_SUPERIEURE",
                           "le paquet %s n'est pas postérieur à la version installée %s"
                           % (manifeste["version"], version_installee))
    if not installee >= minimale:
        raise PaquetRefuse("VERSION_MINIMALE_NON_ATTEINTE",
                           "la version installée %s est antérieure à la minimale %s"
                           % (version_installee, manifeste["version_minimale"]))

    # 3. Le formulaire d'un autre cabinet n'est pas le sien.
    if manifeste["client"] != client_attendu:
        raise PaquetRefuse("CLIENT_DIFFERENT",
                           "paquet de %s, attendu %s"
                           % (manifeste["client"], client_attendu))

    # 4. Chemins du manifeste, doublons à la casse près, plafonds.
    fichiers = manifeste["fichiers"]
    casses = set()
    for chemin in fichiers:
        valider_chemin(chemin)
        if chemin.casefold() in casses:
            raise PaquetRefuse("CHEMIN_EN_DOUBLE", "chemin en double : %r" % (chemin,))
        casses.add(chemin.casefold())
    _refuser_fichier_et_dossier_de_meme_nom(fichiers)
    if len(fichiers) > NOMBRE_MAX_FICHIERS:
        raise PaquetRefuse("MANIFESTE_MALFORME",
                           "plus de %d fichiers" % NOMBRE_MAX_FICHIERS)
    if sum(d["taille"] for d in fichiers.values()) > OCTETS_MAX_TOTAL:
        raise PaquetRefuse("MANIFESTE_MALFORME",
                           "plus de %d octets au total" % OCTETS_MAX_TOTAL)

    # 5. L'archive est authentifiée avant d'être lue. On la garde ouverte : la lire
    # ensuite par son chemin laisserait une fenêtre pour l'échanger.
    try:
        fichier = open(os.fspath(chemin_archive), "rb")
    except (OSError, TypeError, ValueError) as erreur:
        raise PaquetRefuse("ARCHIVE_ILLISIBLE", "ouverture impossible : %s" % erreur)
    with fichier:
        _verifier_empreinte_archive(fichier, manifeste["archive"])
        fichier.seek(0)
        _verifier_contenu(fichier, manifeste, fichiers)

    return ManifesteVerifie(
        manifeste["version"], manifeste["version_minimale"], manifeste["date"],
        manifeste["client"],
        types.MappingProxyType(
            {chemin: (d["taille"], d["sha256"]) for chemin, d in fichiers.items()}))


def _verifier_contenu(fichier, manifeste, fichiers):
    """Étapes 6 à 9 : l'archive, déjà authentifiée, dit bien ce que le manifeste dit."""
    racines = {chemin.split("/")[0] for chemin in fichiers}
    if len(racines) > 1:
        raise PaquetRefuse("MANIFESTE_MALFORME", "plusieurs dossiers racine")
    chemin_version = None if not racines else "%s/%s" % (next(iter(racines)), CHEMIN_VERSION)

    # 6. Ouverture et gardes par entrée.
    try:
        archive = zipfile.ZipFile(fichier)
    except _ERREURS_ZIP as erreur:
        raise PaquetRefuse("ARCHIVE_ILLISIBLE", "archive illisible : %s" % (erreur,))
    with archive:
        try:
            entrees = archive.infolist()
        except _ERREURS_ZIP as erreur:
            raise PaquetRefuse("ARCHIVE_ILLISIBLE", "archive illisible : %s" % (erreur,))
        presents, dossiers = _controler_entrees(entrees)
        _refuser_fichier_et_dossier_de_meme_nom(presents, dossiers)

        # 7. Égalité des ensembles. Un dossier n'est admis que s'il abrite un
        # fichier du manifeste : un dossier vide n'a rien à faire dans un paquet.
        parents = _parents_stricts(fichiers)
        for dossier in sorted(dossiers):
            if dossier not in parents:
                raise PaquetRefuse("FICHIER_EN_TROP",
                                   "dossier sans fichier du manifeste : %r" % (dossier,))
        for nom in sorted(presents):
            if nom not in fichiers:
                raise PaquetRefuse("FICHIER_EN_TROP",
                                   "fichier absent du manifeste : %r" % (nom,))
        for nom in sorted(fichiers):
            if nom not in presents:
                raise PaquetRefuse("FICHIER_MANQUANT",
                                   "fichier du manifeste absent de l'archive : %r" % (nom,))

        # 8. Chaque fichier, à la taille et à l'empreinte signées.
        contenu_version = None
        for nom in sorted(fichiers):
            attendu = fichiers[nom]
            entree = presents[nom]
            if nom == chemin_version and attendu["taille"] > TAILLE_MAX_VERSION:
                raise PaquetRefuse("VERSION_INCOHERENTE",
                                   "%s démesuré : %d octets" % (CHEMIN_VERSION, attendu["taille"]))
            if entree.file_size != attendu["taille"]:
                raise PaquetRefuse("FICHIER_ALTERE",
                                   "taille déclarée différente du manifeste : %r" % (nom,))
            try:
                with archive.open(entree, "r") as flux:
                    empreinte, lus, donnees = _lire_borne(
                        flux, attendu["taille"], garder=(nom == chemin_version))
            except _ERREURS_ZIP as erreur:
                raise PaquetRefuse("FICHIER_ALTERE",
                                   "lecture impossible de %r : %s" % (nom, erreur))
            if lus != attendu["taille"] or empreinte != attendu["sha256"]:
                raise PaquetRefuse("FICHIER_ALTERE",
                                   "contenu différent du manifeste : %r" % (nom,))
            if nom == chemin_version:
                contenu_version = donnees

    # 9. Le numéro que le formulaire affichera est celui que le manifeste a signé.
    if contenu_version is None:
        raise PaquetRefuse("VERSION_INCOHERENTE",
                           "%s absent du manifeste" % (CHEMIN_VERSION,))
    contenu = _lire_json_strict(contenu_version, "VERSION_INCOHERENTE")
    if not isinstance(contenu, dict) or contenu.get("version") != manifeste["version"]:
        raise PaquetRefuse("VERSION_INCOHERENTE",
                           "%s ne porte pas la version du manifeste" % (CHEMIN_VERSION,))
