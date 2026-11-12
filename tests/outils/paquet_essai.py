"""Installations et paquets signés jetables pour les tests de mise à jour (C5-T2a).

Python pur : rien ici n'exige `cryptography`, sauf `certificats()` (qui fait
fabriquer les certificats du bac à sable par `generer_autorite.py`, comme les
tests d'intégration). Le zip n'est PAS fabriqué par `faire-paquet.sh` : les tests
qui s'en servent tournent donc aussi sous Windows.

Les fichiers d'une installation d'essai sont les fichiers SUIVIS par Git de
`serveur/` et de `formulaire/` (liste par `git ls-files -z`, jamais par copie
d'arborescence : la racine du dépôt porte les données réelles d'un cabinet).

NE PART JAMAIS AU CABINET : il vit sous `tests/`. Les clés sont des graines
jetables, tirées pour un test.
"""

import atexit
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

RACINE_DEPOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RACINE_DEPOT, "serveur"))
sys.path.insert(0, os.path.join(RACINE_DEPOT, "tests", "outils"))

import paquet_signe  # noqa: E402
import ed25519_essai  # noqa: E402

GRAINE_A = bytes(range(32))
GRAINE_B = bytes(range(100, 132))
GRAINE_C = bytes(range(200, 232))
CLE_A = ed25519_essai.cle_publique(GRAINE_A)
CLE_B = ed25519_essai.cle_publique(GRAINE_B)
CLE_C = ed25519_essai.cle_publique(GRAINE_C)

DOSSIER_RACINE_PAQUET = "BilanPosturo-2026-11-12"
DATE_FIXE = (2026, 11, 12, 8, 0, 0)
MOT_DE_PASSE = "motdepasse123"
UTILISATEUR = "cabinet"

# Les fichiers suivis qu'une installation d'essai reçoit : de quoi démarrer le
# serveur, plus les pièces que la mise à jour exige (PIECES_INDISPENSABLES).
FICHIERS_FORMULAIRE = (
    "formulaire/index.html", "formulaire/index-v1.html", "formulaire/schema.json",
    "formulaire/version.json", "formulaire/style.css", "formulaire/script.js",
    "formulaire/images/favicon.jpeg")
FICHIERS_RACINE = ("LICENSE", "docs/Mode_emploi.md")

_suivis = None
_hash_mot_de_passe = None
_certificats = None


def fichiers_suivis():
    """Les chemins suivis par Git (`git ls-files -z`, jamais sans -z)."""
    global _suivis
    if _suivis is None:
        sortie = subprocess.run(["git", "ls-files", "-z"], cwd=RACINE_DEPOT,
                                capture_output=True)
        if sortie.returncode != 0:
            raise RuntimeError("git ls-files a échoué")
        _suivis = [os.fsdecode(b) for b in sortie.stdout.split(b"\0") if b]
    return _suivis


def contenu_depot(relatif):
    with open(os.path.join(RACINE_DEPOT, *relatif.split("/")), "rb") as f:
        return f.read()


def liste_de_cles(*cles):
    """Le contenu d'un cles_publication.json pour ces clés publiques."""
    return (json.dumps({"format": 1, "cles": [
        {"nom": "publication-essai-%d" % i, "publique": cle.hex()}
        for i, cle in enumerate(cles)]}, indent=2) + "\n").encode("utf-8")


def fichiers_de_base(version="1.1.0", cles=(CLE_A,)):
    """Le contenu (relatif -> octets) d'une version complète du produit."""
    suivis = set(fichiers_suivis())
    base = {}
    for relatif in sorted(suivis):
        if relatif.startswith("serveur/") and relatif.endswith(".py"):
            base[relatif] = contenu_depot(relatif)
    for relatif in FICHIERS_FORMULAIRE + FICHIERS_RACINE:
        if relatif not in suivis:
            raise RuntimeError("fichier suivi attendu : " + relatif)
        base[relatif] = contenu_depot(relatif)
    base["serveur/cles_publication.json"] = liste_de_cles(*cles)
    return avec_version(base, version)


def avec_version(base, version):
    """Copie de `base` portant ce numéro : version.json et une ligne de la
    documentation, pour que deux versions diffèrent aussi par un fichier de plus."""
    base = dict(base)
    base["formulaire/version.json"] = (
        json.dumps({"version": version}, indent=2) + "\n").encode("utf-8")
    base["docs/Mode_emploi.md"] = (
        contenu_depot("docs/Mode_emploi.md") + ("\nversion d'essai %s\n" % version).encode("utf-8"))
    return base


def certificats():
    """(dossier, noms) des quatre fichiers de certificats d'un bac à sable,
    fabriqués une fois par processus par `generer_autorite.py` pour 127.0.0.1."""
    global _certificats
    if _certificats is None:
        dossier = tempfile.mkdtemp(prefix="bilan-maj-certs-")
        atexit.register(shutil.rmtree, dossier, True)
        os.mkdir(os.path.join(dossier, "serveur"))
        shutil.copy(os.path.join(RACINE_DEPOT, "serveur", "generer_autorite.py"),
                    os.path.join(dossier, "serveur"))
        sortie = subprocess.run(
            [sys.executable, os.path.join("serveur", "generer_autorite.py"), "127.0.0.1"],
            cwd=dossier, capture_output=True, text=True)
        if sortie.returncode != 0:
            raise RuntimeError("generer_autorite.py a échoué : " + sortie.stderr)
        _certificats = dossier
    return _certificats


NOMS_CERTIFICATS = ("certificat.pem", "cle.pem", "autorite.crt", "autorite-cle.pem")


def port_libre():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def fabriquer_installation(base, avec_certificats=True, client="cabinet-01", port=None,
                           dossier_pdf="bilans", config_extra=None):
    """Installe `base` dans un dossier jetable (réel, résolu) et rend sa racine.

    Autour des fichiers du produit, tout ce qui appartient au cabinet et qu'aucune
    mise à jour ne doit toucher : configuration, certificats et clés, logo, un
    bilan fictif, des lignes de journaux, un fichier inconnu posé à la racine."""
    global _hash_mot_de_passe
    racine = os.path.realpath(tempfile.mkdtemp(prefix="bilan-maj-"))
    for relatif, octets in base.items():
        chemin = os.path.join(racine, *relatif.split("/"))
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        with open(chemin, "wb") as f:
            f.write(octets)
    if _hash_mot_de_passe is None:
        sys.path.insert(0, os.path.join(RACINE_DEPOT, "serveur"))
        import serveur
        _hash_mot_de_passe = serveur.hacher(MOT_DE_PASSE)
    config = {"port": port or port_libre(), "dossier_pdf": dossier_pdf,
              "utilisateur": UTILISATEUR, "mot_de_passe": _hash_mot_de_passe,
              "certificat": "certificat.pem", "cle_privee": "cle.pem",
              "mise_a_jour": {"client": client}}
    config.update(config_extra or {})
    with open(os.path.join(racine, "config.json"), "w") as f:
        json.dump(config, f)
    if avec_certificats:
        for nom in NOMS_CERTIFICATS:
            shutil.copy(os.path.join(certificats(), nom), os.path.join(racine, nom))
    os.makedirs(os.path.join(racine, "formulaire", "images", "cabinet"))
    with open(os.path.join(racine, "formulaire", "images", "cabinet", "logo.png"), "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\nlogo d'essai")
    os.makedirs(os.path.join(racine, dossier_pdf), exist_ok=True)
    with open(os.path.join(racine, dossier_pdf, "Bilan_fictif.pdf"), "wb") as f:
        f.write(b"%PDF-1.4\nbilan fictif\n%%EOF\n")
    with open(os.path.join(racine, "journal.log"), "w", encoding="utf-8") as f:
        f.write("2026-11-01T08:00:00 ligne ancienne du journal nominatif\n")
    with open(os.path.join(racine, "technique.log"), "w", encoding="utf-8") as f:
        f.write("2026-11-01T08:00:00 DEMARRAGE version=1.0.0\n")
    with open(os.path.join(racine, "fichier-inconnu.txt"), "w") as f:
        f.write("posé à la main par le cabinet\n")
    return racine


def instantane(racine, sans=("mise-a-jour",), journaux=False):
    """{relatif: sha256} de tout fichier de l'arbre, hors dossiers `sans`, hors
    __pycache__ (créés par n'importe quel Python qui importe), et hors journaux
    sauf demande : les journaux ne font que s'allonger (voir `debuts_de_journaux`)."""
    resultat = {}
    for dossier, sous_dossiers, noms in os.walk(racine):
        relatif_dossier = os.path.relpath(dossier, racine).replace(os.sep, "/")
        sous_dossiers[:] = [d for d in sous_dossiers if d != "__pycache__"
                            and not (relatif_dossier == "." and d in sans)]
        for nom in noms:
            relatif = nom if relatif_dossier == "." else relatif_dossier + "/" + nom
            if not journaux and (nom.startswith("journal.log") or nom.startswith("technique.log")):
                continue
            with open(os.path.join(dossier, nom), "rb") as f:
                resultat[relatif] = hashlib.sha256(f.read()).hexdigest()
    return resultat


def contenu_des_journaux(racine):
    resultat = {}
    for nom in sorted(os.listdir(racine)):
        if nom.startswith("journal.log") or nom.startswith("technique.log"):
            with open(os.path.join(racine, nom), "rb") as f:
                resultat[nom] = f.read()
    return resultat


def serialiser(manifeste):
    return (json.dumps(manifeste, ensure_ascii=True, indent=2, sort_keys=True)
            + "\n").encode("utf-8")


def sha(octets):
    return hashlib.sha256(octets).hexdigest()


def ecrire_zip(chemin, contenus, racine_zip=DOSSIER_RACINE_PAQUET):
    with zipfile.ZipFile(chemin, "w") as archive:
        for relatif, octets in sorted(contenus.items()):
            info = zipfile.ZipInfo(racine_zip + "/" + relatif, DATE_FIXE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, octets)


def fabriquer_trio(dossier, base, version, graine=GRAINE_A, client="cabinet-01",
                   version_minimale="1.1.0", nom=None, declarer=None):
    """Fabrique archive + manifeste + signature de la version `version` du contenu
    `base` (un paquet de plus par appel) et rend le chemin de l'archive.

    `base` est le contenu COMPLET du paquet (relatif -> octets) ; sa version.json
    doit déjà porter `version` (voir `avec_version`). `declarer` remplace ce que
    le manifeste annonce pour certains fichiers, pour fabriquer un manifeste
    signé dont un seul point est faux."""
    nom = nom or "BilanPosturo-%s" % version.replace(".", "-")
    archive = os.path.join(dossier, nom + ".zip")
    ecrire_zip(archive, base)
    with open(archive, "rb") as f:
        octets_archive = f.read()
    fichiers = {DOSSIER_RACINE_PAQUET + "/" + relatif: {"sha256": sha(o), "taille": len(o)}
                for relatif, o in base.items()}
    fichiers.update(declarer or {})
    manifeste = {
        "archive": {"sha256": sha(octets_archive), "taille": len(octets_archive)},
        "client": client, "date": "2026-11-12T08:00:00Z", "fichiers": fichiers,
        "format": 1, "produit": "bilan-posturo", "type": "manifeste-mise-a-jour",
        "version": version, "version_minimale": version_minimale,
    }
    octets_manifeste = serialiser(manifeste)
    with open(archive + paquet_signe.SUFFIXE_MANIFESTE, "wb") as f:
        f.write(octets_manifeste)
    with open(archive + paquet_signe.SUFFIXE_SIGNATURE, "wb") as f:
        f.write(ed25519_essai.signer(graine, octets_manifeste))
    return archive


# --- variantes cassées du serveur et du client ---------------------------------

SERVEUR_QUI_SORT_EN_1 = b"import sys\nsys.exit(1)\n"
SERVEUR_QUI_NE_LIE_JAMAIS = b"import time\ntime.sleep(3600)\n"


def serveur_a_racine_web_indeterminee(source):
    """Le vrai serveur.py, dont motif_refus_racine_web rend « indetermine » : il
    refuse de démarrer (C6-T7), /sante reste muette."""
    marque = b'if __name__ == "__main__":'
    if source.count(marque) != 1:
        raise RuntimeError("ancre introuvable dans serveur.py")
    return source.replace(
        marque, b'motif_refus_racine_web = lambda *a, **k: "indetermine"\n' + marque)


def maj_a_auto_controle_en_echec(source):
    """Le vrai maj.py, dont l'auto-contrôle sort en 1."""
    marque = b'if __name__ == "__main__":'
    if source.count(marque) != 1:
        raise RuntimeError("ancre introuvable dans maj.py")
    return source.replace(marque, b"auto_controle = lambda racine: 1\n" + marque)
