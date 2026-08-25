#!/usr/bin/env python3
"""
Autorité de certification locale du cabinet, et certificat serveur qu'elle
signe.

Un certificat auto-signé oblige à réinstaller un certificat sur la tablette
chaque fois que l'adresse IP du PC change. En passant par une autorité, seule
l'autorité est installée sur les appareils, une fois pour toutes : changer
d'adresse ne demande plus qu'à regénérer le certificat serveur côté PC.

    python3 generer_autorite.py 192.168.1.13
    python3 generer_autorite.py 192.168.1.11 192.168.1.13

Produit dans le dossier du projet :
    autorite.crt        à installer sur la tablette et sur le PC
    autorite-cle.pem    clé privée de l'autorité — ne doit jamais sortir du PC
    certificat.pem      certificat serveur, signé par l'autorité
    cle.pem             clé privée du serveur

L'autorité n'est créée qu'à la première exécution. Les fois suivantes, elle
est relue et réutilisée, sans quoi les appareils cesseraient de reconnaître
le serveur.
"""

import datetime
import ipaddress
import os
import sys

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
except ImportError:
    sys.exit("Module manquant.  Installez-le :  python3 -m pip install cryptography")


def sortie_tolerante():
    """Empêche un caractère non affichable de faire planter le script.

    La console Windows travaille en cp1252 : imprimer un caractère absent de
    ce jeu lève UnicodeEncodeError et interrompt la génération, au moment
    précis où le praticien installe le logiciel.
    """
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


RACINE = os.path.dirname(os.path.abspath(__file__))
AUTORITE_CERT = os.path.join(RACINE, "autorite.crt")
AUTORITE_CLE = os.path.join(RACINE, "autorite-cle.pem")
SERVEUR_CERT = os.path.join(RACINE, "certificat.pem")
SERVEUR_CLE = os.path.join(RACINE, "cle.pem")

JOURS_AUTORITE = 3650      # 10 ans : l'autorité est installée à la main
JOURS_SERVEUR = 825        # limite acceptée par les navigateurs récents


def ecrire_cle(chemin, cle):
    """Écrit une clé privée en PEM, lisible par le seul propriétaire.

    Les permissions sont posées à la création et non après coup : entre un
    open() et un chmod(), la clé serait brièvement lisible par tous.
    """
    descripteur = os.open(chemin, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with open(descripteur, "wb") as f:
        f.write(cle.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()))


def ecrire_certificat(chemin, certificat):
    with open(chemin, "wb") as f:
        f.write(certificat.public_bytes(serialization.Encoding.PEM))


def creer_autorite():
    """Crée l'autorité de certification du cabinet."""
    cle = rsa.generate_private_key(public_exponent=65537, key_size=4096)

    nom = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Cabinet"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Autorite Bilan Posturologique"),
    ])
    debut = datetime.datetime.now(datetime.timezone.utc)

    certificat = (
        x509.CertificateBuilder()
        .subject_name(nom)
        .issuer_name(nom)                      # auto-signée : c'est la racine
        .public_key(cle.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(debut - datetime.timedelta(minutes=5))
        .not_valid_after(debut + datetime.timedelta(days=JOURS_AUTORITE))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0),
                       critical=True)
        # Une autorité ne sert qu'à signer : lui interdire tout autre usage
        # limite les dégâts si sa clé fuite.
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False,
            key_encipherment=False, data_encipherment=False,
            key_agreement=False, key_cert_sign=True, crl_sign=True,
            encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(cle.public_key()),
                       critical=False)
        .sign(cle, hashes.SHA256())
    )

    ecrire_cle(AUTORITE_CLE, cle)
    ecrire_certificat(AUTORITE_CERT, certificat)
    return cle, certificat


def charger_autorite():
    """Relit l'autorité existante, ou la crée si c'est la première exécution.

    Retourne (clé, certificat, créée_maintenant).
    """
    if os.path.exists(AUTORITE_CERT) and os.path.exists(AUTORITE_CLE):
        with open(AUTORITE_CLE, "rb") as f:
            cle = serialization.load_pem_private_key(f.read(), password=None)
        with open(AUTORITE_CERT, "rb") as f:
            certificat = x509.load_pem_x509_certificate(f.read())
        return cle, certificat, False

    # Une autorité sans sa clé ne peut plus rien signer : la regénérer
    # invaliderait silencieusement celle déjà installée sur les appareils.
    if os.path.exists(AUTORITE_CERT) != os.path.exists(AUTORITE_CLE):
        sys.exit(
            "Autorité incomplète : {} et {} doivent coexister.\n"
            "Supprimez celui qui reste pour repartir d'une autorité neuve — "
            "il faudra alors la réinstaller sur tous les appareils.".format(
                os.path.basename(AUTORITE_CERT), os.path.basename(AUTORITE_CLE)))

    return (*creer_autorite(), True)


def noms_alternatifs(adresses):
    """Construit le subjectAltName.

    Un navigateur ne regarde plus le CN : une adresse absente d'ici produit un
    ERR_CERT_COMMON_NAME_INVALID, quelle que soit la validité du certificat.
    """
    entrees = [x509.DNSName("localhost")]
    vues = set()

    for brute in adresses:
        try:
            adresse = ipaddress.ip_address(brute)
        except ValueError:
            sys.exit("Adresse IP invalide : {}".format(brute))
        if adresse not in vues:
            vues.add(adresse)
            entrees.append(x509.IPAddress(adresse))

    # Le PC lui-même accède au formulaire par localhost, qui se résout en ::1
    # avant 127.0.0.1 sur une pile double.
    for boucle in ("127.0.0.1", "::1"):
        adresse = ipaddress.ip_address(boucle)
        if adresse not in vues:
            vues.add(adresse)
            entrees.append(x509.IPAddress(adresse))

    return x509.SubjectAlternativeName(entrees)


def creer_certificat_serveur(cle_autorite, cert_autorite, adresses):
    cle = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    debut = datetime.datetime.now(datetime.timezone.utc)

    certificat = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Cabinet"),
            x509.NameAttribute(NameOID.COMMON_NAME, "Bilan Posturologique"),
        ]))
        .issuer_name(cert_autorite.subject)
        .public_key(cle.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(debut - datetime.timedelta(minutes=5))
        .not_valid_after(debut + datetime.timedelta(days=JOURS_SERVEUR))
        .add_extension(noms_alternatifs(adresses), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None),
                       critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False,
            key_encipherment=True, data_encipherment=False,
            key_agreement=False, key_cert_sign=False, crl_sign=False,
            encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),
                       critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(
                cert_autorite.public_key()), critical=False)
        .sign(cle_autorite, hashes.SHA256())
    )

    ecrire_cle(SERVEUR_CLE, cle)
    ecrire_certificat(SERVEUR_CERT, certificat)
    return certificat


def main():
    sortie_tolerante()
    adresses = sys.argv[1:]
    if not adresses or adresses[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0 if adresses else 1

    cle_autorite, cert_autorite, creee = charger_autorite()
    certificat = creer_certificat_serveur(cle_autorite, cert_autorite, adresses)

    if creee:
        print("Autorité créée      : {}  (valable {} ans)".format(
            os.path.basename(AUTORITE_CERT), JOURS_AUTORITE // 365))
    else:
        print("Autorité réutilisée : {}  (expire le {})".format(
            os.path.basename(AUTORITE_CERT),
            cert_autorite.not_valid_after_utc.date()))

    print("Certificat serveur  : {}  (expire le {})".format(
        os.path.basename(SERVEUR_CERT), certificat.not_valid_after_utc.date()))
    print("Adresses déclarées  : {}".format(", ".join(adresses)))

    if creee:
        print("\nInstallez {} sur la tablette et sur le PC :".format(
            os.path.basename(AUTORITE_CERT)))
        print("  Android - Reglages, Securite, Chiffrement et identifiants,")
        print("            Installer depuis la memoire, Certificat CA")
        print("  Windows — Import-Certificate -FilePath autorite.crt "
              "-CertStoreLocation Cert:\\CurrentUser\\Root")
    else:
        print("\nL'autorité étant inchangée, rien à réinstaller sur la tablette.")

    print("\n{} est la clé de l'autorité : elle ne doit jamais quitter ce PC.".format(
        os.path.basename(AUTORITE_CLE)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
