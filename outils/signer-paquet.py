#!/usr/bin/env python3
"""Signe et vérifie un paquet de mise à jour (C5-T1). Poste de l'éditeur.

Trois sous-commandes :

    generer-cle   fabrique la clé de publication, chiffrée par une phrase de passe
    signer        pose à côté d'un paquet son manifeste et sa signature Ed25519
    verifier      rejoue la vérification que fera le PC du cabinet (stdlib seule)

La signature est l'étape SUIVANTE et séparée de `outils/faire-paquet.sh`, qui ne
signe jamais et n'exige aucune clé : la CI fabrique et teste l'archive sans
détenir la clé de publication. Cette clé, elle, vit hors du dépôt et ne signe
jamais en CI. Voir docs/cle-publication.md pour le geste complet.

Seules `generer-cle` et `signer` importent `cryptography` (à l'intérieur de leur
fonction). `verifier` n'utilise que la bibliothèque standard, comme le PC du
cabinet : il tourne là où `cryptography` est absente.

Codes de sortie : 0 succès, 1 refus ou échec, 2 usage.
"""

import argparse
import datetime
import getpass
import hashlib
import json
import os
import re
import sys
import unicodedata
import zipfile

RACINE_DEPOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE_DEPOT, "serveur"))

import paquet_signe  # noqa: E402

SUFFIXE_CLE_PRIVEE = "-privee.pem"
NOM_CLES_DE_CONFIANCE = "serveur/cles_publication.json"
SUFFIXE_MANIFESTE = paquet_signe.SUFFIXE_MANIFESTE
SUFFIXE_SIGNATURE = paquet_signe.SUFFIXE_SIGNATURE

_NOM_DE_CLE = re.compile(r"publication-[0-9]{4}[a-z0-9-]*")
_CLIENT = re.compile(r"cabinet-[0-9]{2,}")
# Le fichier de clé n'est chiffré que par 2 048 tours de PBKDF2 : la phrase est sa
# seule défense, d'où un minimum aligné sur docs/cle-publication.md.
LONGUEUR_MIN_PHRASE = 20


class Echec(Exception):
    """Un refus ou un échec expliqué en français ; `code` est le code de sortie."""

    def __init__(self, message, code=1):
        Exception.__init__(self, message)
        self.code = code


# --------------------------------------------------------------------------
# Garde-fous communs
# --------------------------------------------------------------------------

def _normaliser(chemin):
    # NFC : sous macOS, un même nom a deux écritures Unicode (C6-T7).
    return os.path.normcase(unicodedata.normalize("NFC", os.path.realpath(chemin)))


def est_sous_la_racine_du_depot(chemin):
    """Vrai si `chemin`, résolu, est le dépôt ou se trouve dessous.

    On remonte les ancêtres en comparant à la fois les chaînes normalisées et
    l'identité du fichier (`samefile`) : la seconde voie attrape une racine écrite
    avec une autre casse sur un disque qui l'ignore, la première un dossier qui
    n'existe pas encore.
    """
    racine = _normaliser(RACINE_DEPOT)
    courant = _normaliser(chemin)
    while True:
        if courant == racine:
            return True
        try:
            if os.path.samefile(courant, RACINE_DEPOT):
                return True
        except OSError:
            pass
        parent = os.path.dirname(courant)
        if parent == courant:
            return False
        courant = parent


def _lire_phrase(args, confirmer):
    """La phrase de passe : sur l'entrée standard (tests) ou saisie sans écho."""
    if args.phrase_stdin:
        ligne = sys.stdin.readline()
        if not ligne:
            raise Echec("aucune phrase de passe sur l'entrée standard")
        return ligne.rstrip("\r\n")
    phrase = getpass.getpass("Phrase de passe de la clé : ")
    if confirmer and getpass.getpass("Confirmez la phrase de passe : ") != phrase:
        raise Echec("les deux phrases de passe diffèrent")
    return phrase


def _importer_cryptography():
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError:
        raise Echec("le module « cryptography » est requis par cette commande "
                    "(python -m pip install cryptography)")
    return serialization, ed25519


def _ecrire_exclusif(chemin, octets, mode):
    """Crée `chemin` sans jamais écraser un fichier existant."""
    drapeaux = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        descripteur = os.open(chemin, drapeaux, mode)
    except FileExistsError:
        raise Echec("le fichier existe déjà et ne sera pas écrasé : %s" % chemin)
    except OSError as erreur:
        raise Echec("écriture impossible de %s : %s" % (chemin, erreur))
    # Le fichier existe depuis l'instant précédent, et c'est CETTE exécution qui
    # l'a créé : s'il reste à moitié écrit, il est effacé, quelle que soit la cause
    # de l'échec (disque plein, interruption). Un manifeste ou une signature tronqués
    # ressemblent à un vrai trio, et une clé tronquée bloquerait la génération
    # suivante (« existe déjà »).
    try:
        with os.fdopen(descripteur, "wb") as fichier:
            fichier.write(octets)
    except BaseException as erreur:
        _supprimer([chemin])
        if isinstance(erreur, OSError):
            raise Echec("écriture impossible de %s : %s" % (chemin, erreur))
        raise


def _supprimer(chemins):
    for chemin in chemins:
        try:
            os.remove(chemin)
        except OSError:
            pass


# --------------------------------------------------------------------------
# generer-cle
# --------------------------------------------------------------------------

def generer_cle(args):
    if _NOM_DE_CLE.fullmatch(args.nom) is None:
        raise Echec("nom de clé invalide : attendu « publication-AAAA » suivi "
                    "éventuellement de [a-z0-9-] (par exemple publication-2026)", 2)
    if not os.path.isdir(args.dossier):
        raise Echec("le dossier n'existe pas : %s" % args.dossier)
    if est_sous_la_racine_du_depot(args.dossier):
        raise Echec("refus : la clé privée ne se range jamais dans le dépôt "
                    "(%s). Choisissez un dossier HORS du dépôt." % args.dossier)
    chemin = os.path.join(args.dossier, args.nom + SUFFIXE_CLE_PRIVEE)
    if os.path.lexists(chemin):
        raise Echec("la clé existe déjà et ne sera jamais écrasée : %s" % chemin)
    phrase = _lire_phrase(args, confirmer=True)
    if len(phrase) < LONGUEUR_MIN_PHRASE:
        raise Echec("phrase de passe trop courte : %d caractères au minimum"
                    % LONGUEUR_MIN_PHRASE)

    serialization, ed25519 = _importer_cryptography()
    privee = ed25519.Ed25519PrivateKey.generate()
    pem = privee.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(
            phrase.encode("utf-8")))
    publique = privee.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    _ecrire_exclusif(chemin, pem, 0o600)

    # Sur la sortie standard : UNIQUEMENT la clé publique, à placer telle quelle
    # dans serveur/cles_publication.json. Ni la graine ni le PEM n'y passent.
    print(json.dumps({"format": 1, "cles": [
        {"nom": args.nom, "publique": publique.hex()}]}, indent=2))
    print("Clé privée chiffrée écrite : %s" % chemin, file=sys.stderr)
    print("Sauvegardez-la maintenant (docs/cle-publication.md, section 3).",
          file=sys.stderr)


# --------------------------------------------------------------------------
# signer
# --------------------------------------------------------------------------

def _inspecter_archive(chemin):
    """(dossier racine, {chemin: (taille, sha256)}, contenus lus) d'une archive."""
    fichiers, contenus, racines = {}, {}, set()
    try:
        archive = zipfile.ZipFile(chemin)
    except (OSError, zipfile.BadZipFile) as erreur:
        raise Echec("archive illisible : %s" % erreur)
    with archive:
        for entree in archive.infolist():
            if entree.orig_filename.endswith("/"):
                continue
            nom = entree.orig_filename
            try:
                paquet_signe.valider_chemin(nom)
            except paquet_signe.PaquetRefuse as erreur:
                raise Echec("entrée refusée, rien n'est signé : %s" % erreur.detail)
            racines.add(nom.split("/")[0])
            condensat, taille = hashlib.sha256(), 0
            with archive.open(entree) as flux:
                while True:
                    bloc = flux.read(paquet_signe.TAILLE_BLOC)
                    if not bloc:
                        break
                    condensat.update(bloc)
                    taille += len(bloc)
                    # Les trois pièces dont la signature a besoin se gardent en
                    # mémoire ; le reste n'est que haché.
                    if nom.endswith(("/formulaire/version.json",
                                     "/formulaire/schema.json", "/" + NOM_CLES_DE_CONFIANCE)):
                        contenus[nom] = contenus.get(nom, b"") + bloc
            fichiers[nom] = (taille, condensat.hexdigest())
    if len(racines) != 1:
        raise Echec("l'archive doit contenir un seul dossier racine, trouvé : %s"
                    % (", ".join(sorted(racines)) or "aucun"))
    return next(iter(racines)), fichiers, contenus


def signer(args):
    if _CLIENT.fullmatch(args.client) is None:
        raise Echec("client invalide : attendu cabinet-NN", 2)
    if est_sous_la_racine_du_depot(args.cle):
        raise Echec("refus : la clé privée est dans le dépôt (%s). Une clé de "
                    "publication ne vit jamais dans le dépôt." % args.cle)
    archive = args.archive
    chemin_manifeste = archive + SUFFIXE_MANIFESTE
    chemin_signature = archive + SUFFIXE_SIGNATURE
    for chemin in (chemin_manifeste, chemin_signature):
        if os.path.lexists(chemin):
            raise Echec("%s existe déjà : supprimez-le délibérément pour re-signer"
                        % chemin)
    try:
        version_minimale = paquet_signe.analyser_version(args.version_minimale)
    except paquet_signe.PaquetRefuse as erreur:
        raise Echec("version minimale invalide : %s" % erreur.detail, 2)

    racine, fichiers, contenus = _inspecter_archive(archive)

    # Version du paquet : celle de formulaire/version.json, forme stricte.
    brut_version = contenus.get(racine + "/formulaire/version.json")
    if brut_version is None:
        raise Echec("formulaire/version.json manque dans l'archive")
    try:
        version = json.loads(brut_version.decode("utf-8")).get("version")
        version_analysee = paquet_signe.analyser_version(version)
    except (ValueError, AttributeError, paquet_signe.PaquetRefuse):
        raise Echec("formulaire/version.json ne porte pas un numéro X.Y.Z strict")
    if not version_minimale < version_analysee:
        raise Echec("la version minimale (%s) doit être strictement inférieure à "
                    "la version du paquet (%s) : sinon aucun PC ne pourrait "
                    "l'installer" % (args.version_minimale, version))

    # Le schéma du paquet est celui du client, octet pour octet (comme
    # faire-paquet.sh) : on ne signe pas le formulaire d'un autre.
    schema_client = os.path.join(RACINE_DEPOT, "clients", args.client, "schema.json")
    try:
        with open(schema_client, "rb") as f:
            attendu = f.read()
    except OSError:
        raise Echec("le client %s n'existe pas (clients/%s/schema.json manque)"
                    % (args.client, args.client))
    if contenus.get(racine + "/formulaire/schema.json") != attendu:
        raise Echec("formulaire/schema.json de l'archive n'est pas celui de "
                    "clients/%s/schema.json" % args.client)

    # Sans clé de confiance dans le paquet, le cabinet ne pourrait pas vérifier
    # la mise à jour SUIVANTE.
    brut_cles = contenus.get(racine + "/" + NOM_CLES_DE_CONFIANCE)
    if brut_cles is None:
        raise Echec("aucune clé de confiance dans le paquet : générez la clé de "
                    "publication (docs/cle-publication.md)")
    try:
        cles = paquet_signe.charger_cles_de_confiance(brut_cles)
    except paquet_signe.PaquetRefuse as erreur:
        raise Echec("liste de clés de confiance du paquet invalide : %s" % erreur.detail)

    serialization, ed25519 = _importer_cryptography()
    phrase = _lire_phrase(args, confirmer=False)
    try:
        with open(args.cle, "rb") as f:
            privee = serialization.load_pem_private_key(
                f.read(), password=phrase.encode("utf-8"))
    except (OSError, ValueError, TypeError):
        raise Echec("clé illisible ou phrase de passe incorrecte : %s" % args.cle)
    if not isinstance(privee, ed25519.Ed25519PrivateKey):
        raise Echec("ce n'est pas une clé Ed25519 : %s" % args.cle)
    publique = privee.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    if publique not in cles:
        raise Echec("refus : la clé publique de cette clé ne figure pas dans "
                    "%s du paquet. Le cabinet ne pourrait pas vérifier la mise à "
                    "jour suivante." % NOM_CLES_DE_CONFIANCE)

    with open(archive, "rb") as f:
        octets_archive = f.read()
    manifeste = {
        "archive": {"sha256": hashlib.sha256(octets_archive).hexdigest(),
                    "taille": len(octets_archive)},
        "client": args.client,
        "date": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "fichiers": {nom: {"sha256": sha, "taille": taille}
                     for nom, (taille, sha) in fichiers.items()},
        "format": paquet_signe.FORMAT_MANIFESTE,
        "produit": paquet_signe.PRODUIT,
        "type": paquet_signe.TYPE_MANIFESTE,
        "version": version,
        "version_minimale": args.version_minimale,
    }
    octets = (json.dumps(manifeste, ensure_ascii=True, indent=2, sort_keys=True)
              + "\n").encode("utf-8")
    signature = privee.sign(octets)

    # On ne supprime que ce que CETTE exécution a créé.
    crees = []
    try:
        _ecrire_exclusif(chemin_manifeste, octets, 0o644)
        crees.append(chemin_manifeste)
        _ecrire_exclusif(chemin_signature, signature, 0o644)
        crees.append(chemin_signature)
        # Revérification par le code de Python pur qui tournera au cabinet : une
        # signature que le cabinet refuserait ne doit jamais sortir d'ici.
        paquet_signe.verifier_paquet(archive, octets, signature, cles,
                                     args.version_minimale, args.client)
    except paquet_signe.PaquetRefuse as erreur:
        _supprimer(crees)
        raise Echec("le paquet signé ne passerait pas la vérification du cabinet "
                    "(%s), fichiers effacés : %s" % (erreur.code, erreur.detail))
    except BaseException:
        _supprimer(crees)
        raise

    print("Paquet signé : %s (version %s, client %s)"
          % (os.path.basename(archive), version, args.client))
    print("Relisez la liste ci-dessous : tout fichier inattendu part chez tous "
          "les clients.")
    for nom in sorted(fichiers):
        print("  %9d  %s" % (fichiers[nom][0], nom))
    print("%d fichiers signés." % len(fichiers))
    print("Posés à côté de l'archive :\n  %s\n  %s"
          % (os.path.basename(chemin_manifeste), os.path.basename(chemin_signature)))


# --------------------------------------------------------------------------
# verifier
# --------------------------------------------------------------------------

def _lire_borne(chemin, limite):
    with open(chemin, "rb") as f:
        return f.read(limite + 1)


def verifier(args):
    archive = args.archive
    try:
        cles = paquet_signe.charger_cles_de_confiance(
            _lire_borne(args.cles, paquet_signe.TAILLE_MAX_CLES))
    except OSError as erreur:
        raise Echec("liste de clés illisible : %s" % erreur)
    except paquet_signe.PaquetRefuse as erreur:
        print("PAQUET REFUSÉ %s : %s" % (erreur.code, erreur.detail))
        return 1
    try:
        octets = _lire_borne(archive + SUFFIXE_MANIFESTE,
                             paquet_signe.TAILLE_MAX_MANIFESTE)
        signature = _lire_borne(archive + SUFFIXE_SIGNATURE, 65)
    except OSError as erreur:
        print("PAQUET REFUSÉ SIGNATURE_INVALIDE : manifeste ou signature "
              "introuvable (%s)" % erreur)
        return 1
    try:
        verifie = paquet_signe.verifier_paquet(
            archive, octets, signature, cles, args.version_installee, args.client)
    except paquet_signe.PaquetRefuse as erreur:
        print("PAQUET REFUSÉ %s : %s" % (erreur.code, erreur.detail))
        return 1
    print("PAQUET ACCEPTÉ %s" % verifie.version)
    return 0


# --------------------------------------------------------------------------
# Ligne de commande
# --------------------------------------------------------------------------

class AnalyseurFrancais(argparse.ArgumentParser):
    """argparse, avec ses refus d'usage en français et le code de sortie 2."""

    def __init__(self, *args, **kwargs):
        argparse.ArgumentParser.__init__(self, *args, **kwargs)
        # Titres des sections de l'aide : argparse les écrit en anglais et n'offre
        # aucune option publique pour les changer.
        self._positionals.title = "arguments"
        self._optionals.title = "options"

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("%s : erreur d'usage : %s\n" % (self.prog, message))
        raise SystemExit(2)


def construire_analyseur():
    analyseur = AnalyseurFrancais(
        prog="signer-paquet.py", add_help=False,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Signe et vérifie un paquet de mise à jour (C5-T1).")
    analyseur.add_argument("-h", "--help", action="help",
                           help="affiche cette aide et quitte")
    sous = analyseur.add_subparsers(dest="commande", metavar="COMMANDE",
                                    parser_class=AnalyseurFrancais)

    def sous_commande(nom, aide):
        parseur = sous.add_parser(nom, help=aide, description=aide, add_help=False)
        parseur.add_argument("-h", "--help", action="help",
                             help="affiche cette aide et quitte")
        return parseur

    gc = sous_commande("generer-cle",
                       "fabrique la clé de publication, chiffrée par une phrase de passe")
    gc.add_argument("--dossier", required=True,
                    help="dossier HORS du dépôt où écrire <nom>-privee.pem")
    gc.add_argument("--nom", required=True,
                    help="nom de la clé, par exemple publication-2026")
    gc.add_argument("--phrase-stdin", action="store_true",
                    help="lit la phrase de passe sur l'entrée standard (tests)")
    gc.set_defaults(fonction=generer_cle)

    si = sous_commande("signer", "signe un paquet fabriqué par faire-paquet.sh")
    si.add_argument("--cle", required=True, help="fichier <nom>-privee.pem")
    si.add_argument("--client", required=True, help="client du paquet, cabinet-NN")
    si.add_argument("--version-minimale", required=True,
                    help="plus ancienne version installée acceptée, X.Y.Z")
    si.add_argument("--phrase-stdin", action="store_true",
                    help="lit la phrase de passe sur l'entrée standard (tests)")
    si.add_argument("archive", help="le paquet .zip à signer")
    si.set_defaults(fonction=signer)

    ve = sous_commande("verifier",
                       "rejoue la vérification du cabinet (bibliothèque standard seule)")
    ve.add_argument("--cles", required=True,
                    help="serveur/cles_publication.json DÉJÀ INSTALLÉ, jamais celui du paquet")
    ve.add_argument("--version-installee", required=True, help="version installée, X.Y.Z")
    ve.add_argument("--client", required=True, help="client attendu, cabinet-NN")
    ve.add_argument("archive", help="le paquet .zip à vérifier")
    ve.set_defaults(fonction=verifier)

    # Le résumé des options est DÉRIVÉ des sous-commandes, jamais recopié.
    analyseur.epilog = "Usage de chaque commande :\n" + "\n".join(
        "  " + p.format_usage().replace("usage: ", "", 1).strip()
        for p in sous.choices.values())
    return analyseur


def main(argv=None):
    analyseur = construire_analyseur()
    args = analyseur.parse_args(argv)
    if getattr(args, "fonction", None) is None:
        analyseur.print_help(sys.stderr)
        return 2
    try:
        resultat = args.fonction(args)
    except Echec as erreur:
        print("ERREUR : %s" % erreur, file=sys.stderr)
        return erreur.code
    return resultat or 0


if __name__ == "__main__":
    sys.exit(main())
