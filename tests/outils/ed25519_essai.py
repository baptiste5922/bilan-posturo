"""Signataire Ed25519 de test, en Python pur (C5-T1).

RFC 8032, §5.1.5 (génération de la clé publique) et §5.1.6 (signature).

NE PART JAMAIS AU CABINET. Il vit sous `tests/`, que `faire-paquet.sh` ne copie
pas. Le code livré (`serveur/`) ne sait que VÉRIFIER : un module de signature
en Python, avec des entiers de taille variable, fuirait la clé par le temps de
calcul. Ici, les clés sont des graines jetables tirées pour un test.

Il emprunte l'arithmétique de `serveur/signature_ed25519.py`. Cela ne rend pas
les tests circulaires : les cinq vecteurs de la RFC 8032 exigent que ce signataire
reproduise la clé publique et la signature à l'octet, et le croisement avec
`cryptography` (tests/test_signature_ed25519.py) confronte les deux sens.
"""

import hashlib
import os
import sys

_SERVEUR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "serveur")
if _SERVEUR not in sys.path:
    sys.path.insert(0, _SERVEUR)

import signature_ed25519 as _ed  # noqa: E402


def _developper(graine):
    """(scalaire secret, préfixe de nonce) d'après la graine (RFC 8032, §5.1.5)."""
    condensat = hashlib.sha512(graine).digest()
    scalaire = int.from_bytes(condensat[:32], "little")
    scalaire &= (1 << 254) - 8
    scalaire |= 1 << 254
    return scalaire, condensat[32:]


def cle_publique(graine):
    """Les 32 octets de la clé publique de la graine de 32 octets."""
    scalaire, _ = _developper(graine)
    return _ed._encoder(_ed._multiplier(scalaire, _ed._BASE))


def _signer(graine, message, s_force):
    scalaire, prefixe = _developper(graine)
    publique = cle_publique(graine)
    r = int.from_bytes(hashlib.sha512(prefixe + message).digest(), "little") % _ed._L
    octets_r = _ed._encoder(_ed._multiplier(r, _ed._BASE))
    k = int.from_bytes(
        hashlib.sha512(octets_r + publique + message).digest(), "little") % _ed._L
    s = (r + k * scalaire) % _ed._L if s_force is None else s_force
    return octets_r + s.to_bytes(32, "little")


def signer(graine, message):
    """Signature de 64 octets (R ‖ S) de `message` par la graine."""
    return _signer(graine, message, None)


def signer_avec_s(graine, message, s_force):
    """Comme `signer`, mais avec S imposé (entier < 2^256).

    Sert à fabriquer S >= L : par exemple S + L, que l'équation de vérification
    accepte (L·B est le neutre) et que le vérificateur doit pourtant refuser.
    """
    return _signer(graine, message, s_force)


def graine_aleatoire():
    return os.urandom(32)
