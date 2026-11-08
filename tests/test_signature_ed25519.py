"""Vérification Ed25519 en Python pur (C5-T1) : `serveur/signature_ed25519.py`.

Ce module décidera, au cabinet, quel code a le droit de s'installer. Un
vérificateur trop laxiste ne se corrige pas par une mise à jour qu'il laisserait
passer : chaque règle est donc éprouvée ici séparément, et une règle qui n'est
pas atteinte par un test précis est une règle qui ne garde rien.

Quatre sources de vérité indépendantes :
  - les cinq vecteurs du §7.1 de la RFC 8032, recopiés dans
    tests/donnees/rfc8032-ed25519.json ;
  - un signataire de test en Python pur (tests/outils/ed25519_essai.py), qui doit
    reproduire ces vecteurs à l'octet ;
  - des falsifications fabriquées pour que l'ÉQUATION de vérification tienne : le
    seul motif de refus est alors la règle visée ;
  - `cryptography` (sautée si absente, présente en CI), dans les deux sens.

    python3 -m unittest tests.test_signature_ed25519
"""

import hashlib
import importlib.util
import json
import os
import random
import statistics
import sys
import time
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "serveur"))
sys.path.insert(0, os.path.join(RACINE, "tests", "outils"))

import signature_ed25519 as ed  # noqa: E402
import ed25519_essai as essai  # noqa: E402


def cryptography_absente():
    """cryptography ne sert qu'aux tests de croisement, jamais au serveur."""
    return importlib.util.find_spec("cryptography") is None


def _vecteurs():
    # Dans externes/ et non à plat dans donnees/ : le contrôle de vocabulaire de
    # tests/test_confidentialite_prospect.py lit TOUT .json de donnees/ comme un
    # schéma de formulaire. Ces vecteurs viennent de la RFC, pas du projet.
    chemin = os.path.join(RACINE, "tests", "donnees", "externes", "rfc8032-ed25519.json")
    with open(chemin, encoding="utf-8") as f:
        brut = json.load(f)["vecteurs"]
    return [
        {"nom": v["nom"], "secret": bytes.fromhex(v["secret"]),
         "publique": bytes.fromhex(v["publique"]),
         "message": bytes.fromhex(v["message"]),
         "signature": bytes.fromhex(v["signature"])}
        for v in brut
    ]


VECTEURS = _vecteurs()


def encoder_y(y, signe=0):
    """32 octets de l'encodage d'une ordonnée donnée, sans rien décoder."""
    return (y | (signe << 255)).to_bytes(32, "little")


def equation_tient(cle, message, signature):
    """Vrai si [S]B − [k]A encode exactement R, SANS aucune des gardes du module.

    Sert à prouver qu'une falsification fabriquée est « bonne » au sens de
    l'équation : si le vérificateur la refuse, c'est alors la garde visée, et
    elle seule, qui l'a refusée.
    """
    a = ed._decoder_point(cle)
    if a is None:
        return False
    s = int.from_bytes(signature[32:], "little")
    k = int.from_bytes(
        hashlib.sha512(signature[:32] + cle + message).digest(),
        "little") % ed._L
    moins_a = ((-a[0]) % ed._P, a[1], a[2], (-a[3]) % ed._P)
    obtenu = ed._ajouter(ed._multiplier(s, ed._BASE),
                         ed._multiplier(k, moins_a))
    return ed._encoder(obtenu) == signature[:32]


def points_d_ordre_faible():
    """Les huit points de [L]·P, P tiré au hasard sur la courbe.

    Obtenus par le calcul et non par la fonction `_ordre_faible` testée : P est
    d'ordre 8·L en général, donc [L]·P tombe dans le sous-groupe d'ordre 8, et
    sur chacun de ses huit éléments à tour de rôle.
    """
    graine = random.Random(8032)
    trouves = {}
    while len(trouves) < 8:
        y = graine.randrange(2, ed._P)
        point = ed._decoder_point(encoder_y(y))
        if point is None:
            continue
        faible = ed._multiplier(ed._L, point)
        trouves[ed._encoder(faible)] = faible
    return trouves


class VecteursRfc8032(unittest.TestCase):

    def test_les_cinq_vecteurs_sont_charges(self):
        self.assertEqual([v["nom"] for v in VECTEURS],
                         ["TEST 1", "TEST 2", "TEST 3", "TEST 1024", "TEST SHA(abc)"])
        self.assertEqual([len(v["message"]) for v in VECTEURS], [0, 1, 2, 1023, 64])

    def test_les_vecteurs_sont_acceptes(self):
        for v in VECTEURS:
            with self.subTest(vecteur=v["nom"]):
                self.assertTrue(
                    ed.verifier(v["publique"], v["message"], v["signature"]))

    def test_le_signataire_de_test_reproduit_cle_et_signature_a_l_octet(self):
        # Une faute de recopie d'un vecteur fait échouer ce test au lieu de
        # passer inaperçue : clé publique ET signature sont recalculées.
        for v in VECTEURS:
            with self.subTest(vecteur=v["nom"]):
                self.assertEqual(essai.cle_publique(v["secret"]), v["publique"])
                self.assertEqual(essai.signer(v["secret"], v["message"]),
                                 v["signature"])

    def test_un_bit_change_dans_le_message_ou_la_signature_est_refuse(self):
        for v in VECTEURS:
            with self.subTest(vecteur=v["nom"]):
                for position in range(0, 64, 7):
                    alteree = bytearray(v["signature"])
                    alteree[position] ^= 0x01
                    self.assertFalse(
                        ed.verifier(v["publique"], v["message"], bytes(alteree)),
                        "octet %d" % position)
                self.assertFalse(
                    ed.verifier(v["publique"], v["message"] + b"\0",
                                v["signature"]))

    def test_la_cle_d_un_autre_vecteur_est_refusee(self):
        premier, second = VECTEURS[0], VECTEURS[1]
        self.assertFalse(ed.verifier(second["publique"], premier["message"],
                                     premier["signature"]))


class RefusDesSignaturesMalleables(unittest.TestCase):
    """Une règle par test, chacune derrière une signature dont l'ÉQUATION tient."""

    def setUp(self):
        self.graine = bytes(range(32))
        self.cle = essai.cle_publique(self.graine)
        self.message = b"mise a jour 1.2.0"
        self.signature = essai.signer(self.graine, self.message)
        self.s_valide = int.from_bytes(self.signature[32:], "little")

    def test_la_signature_honnete_passe(self):
        self.assertTrue(ed.verifier(self.cle, self.message, self.signature))

    def test_s_egal_a_l_est_refuse(self):
        faux = self.signature[:32] + ed._L.to_bytes(32, "little")
        self.assertFalse(ed.verifier(self.cle, self.message, faux))

    def test_s_valide_plus_l_est_refuse_alors_que_l_equation_tient(self):
        # La malléabilité de S : S + L donne la même équation, car L·B est le
        # neutre. Seule la règle S < L la refuse.
        faux = essai.signer_avec_s(self.graine, self.message, self.s_valide + ed._L)
        self.assertTrue(equation_tient(self.cle, self.message, faux),
                        "la falsification doit tenir l'équation")
        self.assertFalse(ed.verifier(self.cle, self.message, faux))

    def test_s_tres_grand_est_refuse(self):
        faux = self.signature[:32] + b"\xff" * 32
        self.assertFalse(ed.verifier(self.cle, self.message, faux))

    def test_r_non_decodable_est_refuse(self):
        y = 2
        while ed._decoder_point(encoder_y(y)) is not None:
            y += 1
        faux = encoder_y(y) + self.signature[32:]
        self.assertFalse(ed.verifier(self.cle, self.message, faux))

    def test_a_non_decodable_est_refuse(self):
        y = 2
        while ed._decoder_point(encoder_y(y)) is not None:
            y += 1
        self.assertFalse(ed.verifier(encoder_y(y), self.message, self.signature))

    def test_y_egal_p_ou_au_dela_est_refuse_en_a_et_en_r(self):
        for decalage in range(0, 19):
            for signe in (0, 1):
                encodage = encoder_y(ed._P + decalage, signe)
                with self.subTest(y="p+%d" % decalage, signe=signe):
                    self.assertFalse(
                        ed.verifier(encodage, self.message, self.signature))
                    self.assertFalse(
                        ed.verifier(self.cle, self.message,
                                    encodage + self.signature[32:]))

    def test_le_decodeur_refuse_y_au_dela_de_p(self):
        # Au niveau du décodeur lui-même : sans lui, c'est la règle d'ordre faible
        # qui refuserait y = p et y = p + 1, et la règle y < p ne serait jamais
        # éprouvée. y = p + 3 à p + 18 (ordonnées de vrais points) la distinguent.
        decodables = [d for d in range(0, 19)
                      if ed._decoder_point(encoder_y(d)) is not None]
        self.assertGreater(len(decodables), 4, "il faut des cas non faibles")
        for d in decodables:
            with self.subTest(y="p+%d" % d):
                self.assertIsNone(ed._decoder_point(encoder_y(ed._P + d)))
                self.assertIsNone(ed._decoder_point(encoder_y(ed._P + d, 1)))

    def test_x_nul_avec_bit_de_signe_a_un_est_refuse(self):
        # x = 0 pour y = 1 (le neutre) et y = p - 1 : deux encodages pour un même
        # point si on tolère le bit de signe. Niveau décodeur (ces points sont
        # aussi d'ordre faible, que la règle suivante refuserait seule sinon).
        for y in (1, ed._P - 1):
            with self.subTest(y=y):
                self.assertIsNotNone(ed._decoder_point(encoder_y(y, 0)))
                self.assertIsNone(ed._decoder_point(encoder_y(y, 1)))
                self.assertFalse(
                    ed.verifier(encoder_y(y, 1), self.message, self.signature))
                self.assertFalse(
                    ed.verifier(self.cle, self.message,
                                encoder_y(y, 1) + self.signature[32:]))

    def test_longueurs_fausses_refusees(self):
        for longueur in (0, 31, 33):
            with self.subTest(cle=longueur):
                faux = (self.cle + b"\0" * 40)[:longueur]
                self.assertFalse(ed.verifier(faux, self.message, self.signature))
        for longueur in (0, 63, 65):
            with self.subTest(signature=longueur):
                faux = (self.signature + b"\0" * 40)[:longueur]
                self.assertFalse(ed.verifier(self.cle, self.message, faux))

    def test_signature_trop_longue_dont_le_debut_est_valide_est_refusee(self):
        # M5 : rendre True quand la longueur est fausse accepterait ceci.
        self.assertFalse(
            ed.verifier(self.cle, self.message, self.signature + b"\0"))
        self.assertFalse(
            ed.verifier(self.cle + b"\0", self.message, self.signature))
        self.assertFalse(
            ed.verifier(self.cle, self.message, self.signature[:63]))

    def test_aucun_argument_de_type_faux_ne_leve(self):
        faux = [None, "texte", 12, 1.5, bytearray(b"x" * 32), memoryview(b"x" * 32),
                [1, 2], object()]
        for position in range(3):
            for valeur in faux:
                arguments = [self.cle, self.message, self.signature]
                arguments[position] = valeur
                with self.subTest(position=position, type=type(valeur).__name__):
                    self.assertIs(ed.verifier(*arguments), False)

    def test_un_bytearray_n_est_pas_un_bytes(self):
        self.assertIs(ed.verifier(bytearray(self.cle), self.message,
                                  self.signature), False)


class PointsDOrdreFaible(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.faibles = points_d_ordre_faible()

    def test_les_huit_points_sont_obtenus(self):
        self.assertEqual(len(self.faibles), 8)
        for encodage, point in self.faibles.items():
            huit = ed._multiplier(8, point)
            self.assertEqual(ed._encoder(huit), encoder_y(1), encodage.hex())

    def test_les_huit_sont_reconnus_d_ordre_faible_et_les_autres_non(self):
        for point in self.faibles.values():
            self.assertTrue(ed._ordre_faible(point))
        self.assertFalse(ed._ordre_faible(ed._BASE))
        self.assertFalse(ed._ordre_faible(ed._multiplier(12345, ed._BASE)))

    def test_chacun_des_huit_est_refuse_comme_cle_a(self):
        message, graine = b"m", bytes(range(32))
        signature = essai.signer(graine, message)
        for encodage in self.faibles:
            with self.subTest(cle=encodage.hex()):
                self.assertFalse(ed.verifier(encodage, message, signature))

    def test_chacun_des_huit_est_refuse_comme_r(self):
        cle = essai.cle_publique(bytes(range(32)))
        for encodage in self.faibles:
            with self.subTest(r=encodage.hex()):
                self.assertFalse(
                    ed.verifier(cle, b"m", encodage + (1).to_bytes(32, "little")))

    def test_forgerie_universelle_avec_une_cle_d_ordre_faible_refusee(self):
        # Avec A d'ordre faible, (R = [s]B, S = s) tient l'équation pour tout
        # message dès que k est multiple de l'ordre de A : on cherche un tel s.
        # La règle d'ordre faible est alors la SEULE à refuser (M4).
        for encodage in self.faibles:
            with self.subTest(cle=encodage.hex()):
                for s in range(1, 400):
                    signature = (ed._encoder(ed._multiplier(s, ed._BASE))
                                 + s.to_bytes(32, "little"))
                    if equation_tient(encodage, b"universel", signature):
                        break
                else:
                    self.fail("aucune falsification trouvée en 400 essais")
                self.assertFalse(ed.verifier(encodage, b"universel", signature))

    def test_r_neutre_avec_cle_honnete_refuse_alors_que_l_equation_tient(self):
        graine = bytes(range(32))
        cle = essai.cle_publique(graine)
        message = b"r neutre"
        neutre = encoder_y(1)
        k = int.from_bytes(
            hashlib.sha512(neutre + cle + message).digest(),
            "little") % ed._L
        a, _ = essai._developper(graine)
        faux = neutre + ((k * a) % ed._L).to_bytes(32, "little")
        self.assertTrue(equation_tient(cle, message, faux))
        self.assertFalse(ed.verifier(cle, message, faux))

    def test_la_liste_connue_des_huit_encodages_concorde(self):
        # Témoin indépendant du calcul : les huit encodages publiés (libsodium,
        # « Ed25519 low order points ») doivent être exactement ceux calculés.
        connus = {
            "0100000000000000000000000000000000000000000000000000000000000000",
            "ecffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f",
            "0000000000000000000000000000000000000000000000000000000000000000",
            "0000000000000000000000000000000000000000000000000000000000000080",
            "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac037a",
            "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac03fa",
            "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05",
            "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc85",
        }
        self.assertEqual({e.hex() for e in self.faibles}, connus)


@unittest.skipIf(cryptography_absente(), "cryptography absente : croisement sauté")
class CroisementCryptography(unittest.TestCase):
    """Les deux sens, contre une implémentation indépendante (OpenSSL).

    Les graines aléatoires sont imprimées en cas d'échec : un désaccord rare doit
    pouvoir se rejouer.
    """

    NOMBRE = 200

    def setUp(self):
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.hazmat.primitives import serialization
        self.ed25519 = ed25519
        self.serialization = serialization
        self.graine = int.from_bytes(os.urandom(8), "big")
        self.hasard = random.Random(self.graine)

    def _octets(self, n):
        return bytes(self.hasard.getrandbits(8) for _ in range(n))

    def _brute(self, publique):
        return publique.public_bytes(self.serialization.Encoding.Raw,
                                     self.serialization.PublicFormat.Raw)

    def _cryptography_accepte(self, cle, message, signature):
        try:
            self.ed25519.Ed25519PublicKey.from_public_bytes(cle).verify(
                signature, message)
        except Exception:  # InvalidSignature, ValueError : un refus dans les deux cas
            return False
        return True

    def test_a_signatures_de_cryptography_acceptees(self):
        for i in range(self.NOMBRE):
            privee = self.ed25519.Ed25519PrivateKey.generate()
            message = self._octets(self.hasard.randrange(0, 300))
            signature = privee.sign(message)
            self.assertTrue(
                ed.verifier(self._brute(privee.public_key()), message, signature),
                "graine %d, essai %d" % (self.graine, i))

    def test_b_signatures_du_signataire_de_test_acceptees_par_cryptography(self):
        for i in range(self.NOMBRE):
            graine_cle = self._octets(32)
            message = self._octets(self.hasard.randrange(0, 300))
            cle = essai.cle_publique(graine_cle)
            signature = essai.signer(graine_cle, message)
            self.assertTrue(self._cryptography_accepte(cle, message, signature),
                            "graine %d, essai %d" % (self.graine, i))
            self.assertTrue(ed.verifier(cle, message, signature),
                            "graine %d, essai %d" % (self.graine, i))

    def test_c_alterations_memes_verdicts_et_toujours_un_refus(self):
        for i in range(self.NOMBRE):
            privee = self.ed25519.Ed25519PrivateKey.generate()
            cle = self._brute(privee.public_key())
            message = self._octets(self.hasard.randrange(1, 200))
            signature = privee.sign(message)
            cible = self.hasard.choice(("signature", "message", "cle"))
            if cible == "signature":
                morceau = bytearray(signature)
            elif cible == "message":
                morceau = bytearray(message)
            else:
                morceau = bytearray(cle)
            position = self.hasard.randrange(len(morceau))
            morceau[position] ^= 1 << self.hasard.randrange(8)
            if cible == "signature":
                signature = bytes(morceau)
            elif cible == "message":
                message = bytes(morceau)
            else:
                cle = bytes(morceau)
            contexte = "graine %d, essai %d, %s" % (self.graine, i, cible)
            mien = ed.verifier(cle, message, signature)
            autre = self._cryptography_accepte(cle, message, signature)
            self.assertEqual(mien, autre, contexte)
            self.assertFalse(mien, contexte)

    def test_s_plus_l_refuse_ici_et_par_cryptography(self):
        # Le vérificateur est plus strict qu'OpenSSL sur certains points, jamais
        # plus laxiste : pour S + L, les deux refusent.
        graine = bytes(range(32))
        cle, message = essai.cle_publique(graine), b"x"
        s = int.from_bytes(essai.signer(graine, message)[32:], "little")
        faux = essai.signer_avec_s(graine, message, s + ed._L)
        self.assertFalse(ed.verifier(cle, message, faux))
        self.assertFalse(self._cryptography_accepte(cle, message, faux))


class Temps(unittest.TestCase):

    def test_mediane_de_vingt_verifications_sous_cinquante_millisecondes(self):
        v = VECTEURS[4]
        durees = []
        for _ in range(20):
            debut = time.perf_counter()
            accepte = ed.verifier(v["publique"], v["message"], v["signature"])
            durees.append(time.perf_counter() - debut)
            self.assertTrue(accepte)
        mediane = statistics.median(durees) * 1000
        print("\n[C5-T1] médiane de 20 vérifications Ed25519 : %.2f ms "
              "(Python %s)" % (mediane, sys.version.split()[0]))
        self.assertLess(mediane, 50.0)


if __name__ == "__main__":
    unittest.main()
