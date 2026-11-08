"""Vérification de signatures Ed25519, en Python pur (C5-T1).

Référence : RFC 8032 (EdDSA : Ed25519 et Ed448), §5.1.3 pour le décodage d'un
point et §5.1.7 pour la vérification. Le code du §6 de la RFC est un « Code
Component » publié sous la licence BSD simplifiée de l'IETF Trust ; ce module
suit l'algorithme du §5.1, écrit en français, et la mention figure dans
`TIERS.md` pour ne laisser aucun doute sur la copie livrée chez un client.

Pourquoi en Python pur : la bibliothèque standard n'a pas Ed25519, et le serveur
du cabinet n'a le droit à aucune dépendance (`cryptography` est une extension
compilée, une roue par plateforme et par version de Python).

AUCUN SECRET N'EST MANIPULÉ ICI, donc aucune exigence de temps constant : la clé
publique, le message et la signature sont des données publiques. Ce module ne
doit JAMAIS servir à signer, ni recevoir une graine : une arithmétique en
Python sur des entiers de taille variable fuit le secret par le temps de calcul.

La seule surface publique est `verifier`. Les noms préfixés d'un tiret bas sont
partagés avec `paquet_signe.py` (qui vérifie que ses clés de confiance se
décodent) et avec le signataire de test de `tests/outils/` ; ils ne sont pas une
interface pour le reste du code.

Ce vérificateur est plus strict qu'OpenSSL, jamais plus laxiste : équation sans
cofacteur, refus de S >= L, de tout encodage non canonique, de x = 0 avec le bit
de signe à 1 et des points d'ordre faible. Une signature honnête passe des deux
façons.
"""

import hashlib

# Le corps premier 2^255 - 19, l'ordre L du sous-groupe premier, et la constante
# d de la courbe -x² + y² = 1 + d·x²·y² (RFC 8032, §5.1).
_P = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _P - 2, _P)) % _P
# Racine carrée de -1 : sert à corriger la racine candidate au décodage.
_RACINE_DE_MOINS_UN = pow(2, (_P - 1) // 4, _P)

# Coordonnées étendues (X, Y, Z, T) avec x = X/Z, y = Y/Z et T = X·Y/Z : l'addition
# n'exige alors aucune inversion modulaire, coûteuse. Le neutre est (0, 1).
_NEUTRE = (0, 1, 1, 0)


def _ajouter(p, q):
    """Addition de deux points (RFC 8032, §5.1.4).

    La formule est unifiée et complète pour cette courbe : elle sert aussi au
    doublement, sans cas particulier à oublier.
    """
    a = (p[1] - p[0]) * (q[1] - q[0]) % _P
    b = (p[1] + p[0]) * (q[1] + q[0]) % _P
    c = p[3] * 2 * _D * q[3] % _P
    d = p[2] * 2 * q[2] % _P
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _multiplier(scalaire, point):
    """[scalaire]·point par doublements et additions successifs.

    Pas de fenêtre ni d'échelle de Montgomery : sans secret, la simplicité
    l'emporte, et 3 à 4 ms par vérification suffisent largement.
    """
    resultat = _NEUTRE
    while scalaire > 0:
        if scalaire & 1:
            resultat = _ajouter(resultat, point)
        point = _ajouter(point, point)
        scalaire >>= 1
    return resultat


def _encoder(point):
    """Encode un point en 32 octets : y petit-boutiste, bit de poids fort = parité de x."""
    inverse = pow(point[2], _P - 2, _P)
    x = point[0] * inverse % _P
    y = point[1] * inverse % _P
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _decoder_point(octets):
    """Décode 32 octets en point (RFC 8032, §5.1.3), ou rend None.

    Refus : y >= p (encodage non canonique), x non récupérable (le point n'est
    pas sur la courbe), et x = 0 avec le bit de signe à 1 (deux encodages pour
    un même point).
    """
    entier = int.from_bytes(octets, "little")
    signe = entier >> 255
    y = entier & ((1 << 255) - 1)
    if y >= _P:
        return None
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _RACINE_DE_MOINS_UN % _P
    if (x * x - x2) % _P != 0:
        return None
    if x == 0 and signe == 1:
        return None
    if (x & 1) != signe:
        x = _P - x
    return (x, y, 1, x * y % _P)


def _ordre_faible(point):
    """Vrai si [8]·point est le neutre : le point est dans le sous-groupe d'ordre 8.

    Calculé et non listé : une liste de huit encodages oublierait leurs variantes.
    """
    for _ in range(3):
        point = _ajouter(point, point)
    return point[0] % _P == 0 and (point[1] - point[2]) % _P == 0


def _point_acceptable(octets):
    """Vrai si les 32 octets se décodent en un point d'ordre non faible.

    C'est le contrôle que `verifier` applique à A : `paquet_signe` s'en sert pour
    refuser, dès le chargement, une clé de confiance qui ne pourrait jamais
    vérifier quoi que ce soit.
    """
    if type(octets) is not bytes or len(octets) != 32:
        return False
    point = _decoder_point(octets)
    return point is not None and not _ordre_faible(point)


# Point de base B : y = 4/5 et x pair (RFC 8032, §5.1).
_BASE = _decoder_point((4 * pow(5, _P - 2, _P) % _P).to_bytes(32, "little"))


def verifier(cle_publique, message, signature):
    """Vrai si `signature` est une signature Ed25519 valide de `message`.

    Rend False pour tout refus et ne lève jamais : un argument qui n'est pas de
    type `bytes` est un refus comme un autre. Les règles, dans l'ordre :

    1. clé de 32 octets, signature de 64 octets ;
    2. A (clé) et R (première moitié de la signature) se décodent en points
       canoniques ;
    3. ni A ni R n'est d'ordre faible ;
    4. S (seconde moitié, petit-boutiste) est strictement inférieur à L ;
    5. [S]·B − [k]·A, avec k = SHA-512(R ‖ A ‖ M) mod L, s'encode exactement en R.

    La comparaison porte sur les encodages : elle refuse d'office un R non
    canonique, sans règle supplémentaire.
    """
    for argument in (cle_publique, message, signature):
        if type(argument) is not bytes:
            return False
    if len(cle_publique) != 32 or len(signature) != 64:
        return False

    a = _decoder_point(cle_publique)
    if a is None or _ordre_faible(a):
        return False
    octets_r = signature[:32]
    r = _decoder_point(octets_r)
    if r is None or _ordre_faible(r):
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= _L:
        return False

    k = int.from_bytes(
        hashlib.sha512(octets_r + cle_publique + message).digest(), "little") % _L
    moins_a = ((-a[0]) % _P, a[1], a[2], (-a[3]) % _P)
    obtenu = _ajouter(_multiplier(s, _BASE), _multiplier(k, moins_a))
    return _encoder(obtenu) == octets_r
