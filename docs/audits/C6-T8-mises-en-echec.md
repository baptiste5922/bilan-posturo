# C6-T8 — journal des mises en échec

**Date :** 18 novembre 2026
**Branche :** `c6-t8-negociation-tls`, depuis `d1d22b4` (contrat commité)
**Règle :** un garde-fou non mis en échec ne garde rien (`CLAUDE.md`). Chaque
série a son **témoin** (l'arbre sain, avant et après) ; chaque résultat est lu
sur la sortie du test lui-même (`OK` ou `FAILED`), jamais sur un `$?` lu après
autre chose.

## Méthode

- Clone jetable du dépôt, hors du dépôt (`git clone --no-hardlinks`, puis
  `git remote remove origin` : un clone qui garde son `origin` pousserait dans
  le dépôt réel). Un clone ne contient que les fichiers suivis : ni
  `config.json`, ni clé, ni journal, ni bilans. L'arbre de travail réel n'a reçu
  aucune mutation (`git diff` vide à la fin, relevé ci-dessous).
- `serveur/serveur.py` du clone est **sauvegardé hors du clone** avant la série ;
  chaque mutation réécrit le fichier d'origine par `cp` à la fin de son tour.
  Le script de mutation refuse une mutation sans effet : le motif doit se
  trouver **exactement une fois**.
- Les deux séries (`python3` puis `python3 -O`, au premier plan) jouent
  `tests.test_negociation_tls` : un témoin, M1 à M6, un témoin.

## Avant le code (témoin rouge, étape 1 du plan)

Sur l'arbre d'avant la tâche, la constante étant posée seule (l'ancre du bac à
sable doit exister) : `test_connexion_muette_ne_bloque_ni_depot_ni_sante`
(`TimeoutError: The handshake operation timed out` côté client, le serveur étant
figé dans `accept()`), `test_connexion_muette_fermee_au_delai` et
`test_goutte_a_goutte_ferme_au_delai` rougissent ; `test_requete_en_clair_refusee`
et `test_alpn_http11` passent (gardes de non-régression, comme prévu). Les tests
unitaires de `finish_request` rougissent : la méthode n'est pas surchargée (le
gestionnaire est créé) et la constante est absente avant son ajout.

## Mutations

| N° | Garde visée | Mutation | Tests qui rougissent |
|---|---|---|---|
| M1 | Négociation hors du fil principal | `do_handshake_on_connect=False` retiré de `wrap_socket` | `test_connexion_muette_ne_bloque_ni_depot_ni_sante` (erreur : délai client), `test_connexion_muette_fermee_au_delai`, `test_goutte_a_goutte_ferme_au_delai`, `test_requete_en_clair_refusee` |
| M2 | Délai posé sur la socket | `request.settimeout(...)` retiré | `test_connexion_muette_fermee_au_delai`, `test_goutte_a_goutte_ferme_au_delai`, `test_expiration_journalisee_sans_adresse`, `test_canal_negocie_cree_le_gestionnaire` |
| M3 | Négociation explicite | `request.do_handshake()` retiré | `test_connexion_muette_fermee_au_delai`, `test_goutte_a_goutte_ferme_au_delai`, `test_requete_en_clair_refusee`, `test_alpn_http11`, `test_connexion_muette_ne_bloque_ni_depot_ni_sante` et les quatre unitaires de `finish_request` qui attendent l'appel |
| M4 | Garde du canal chiffré | `if request.version() is None: return` retiré | `test_canal_sans_version_ferme` **seul** |
| M5 | Jeton fermé de l'expiration | `raison=delai-depasse` devient `raison=timed out` | `test_expiration_journalisee_sans_adresse`, `test_connexion_muette_fermee_au_delai` |
| M6 | Aucune adresse dans technique.log | `client_address[0]` ajouté au détail de l'expiration | `test_expiration_journalisee_sans_adresse`, `test_connexion_muette_fermee_au_delai` |

Résultats relevés (`python3`) : témoin `Ran 12 tests … OK` ; M1 `FAILED
(failures=3, errors=1)` ; M2 `FAILED (failures=4)` ; M3 `FAILED (failures=7,
errors=2)` ; M4 `FAILED (failures=1)` ; M5 `FAILED (failures=2)` ; M6 `FAILED
(failures=2)` ; témoin après la série `OK`.

Série `python3 -O` : témoin `OK` ; M1 `FAILED (failures=3, errors=1)` ; M2
`FAILED (failures=4)` ; M3 `FAILED (failures=7, errors=2)` ; M4 `FAILED
(failures=1)` ; M5 `FAILED (failures=2)` ; M6 `FAILED (failures=2)` ; témoin
`OK`.

Remarques :

- **M3** : le contrat attendait « fermeture à 120 s » pour la muette. Sans
  `do_handshake()`, `request.version()` rend `None` sur une socket jamais
  négociée : la garde de M4 ferme aussitôt la connexion. La muette est donc
  fermée **trop tôt** (avant 0,8 × délai) au lieu de trop tard : le test rougit
  quand même, par sa borne basse. Les deux gardes se couvrent l'une l'autre
  contre un clair non négocié ; M4 seule prouve que la deuxième tient.
- **M4** n'est vue que par `test_canal_sans_version_ferme` : en production, le
  canal sans version n'arrive jamais après un `do_handshake()` réussi. La garde
  est une ceinture, dont ce test est la seule preuve.
- **M1** rougit aussi `test_requete_en_clair_refusee`, par deux chemins : la
  négociation se fait de nouveau dans `accept()`, où `get_request()` n'existe
  plus pour journaliser le refus (aucune ligne `TLS_REFUSE`), et un serveur figé
  par une connexion muette ne répond plus du tout. Ce second effet est mon
  hypothèse, non isolée.

## Mutation résiduelle

Après la série, `git status --short` et `git diff --stat` dans le **dépôt réel**
et dans le clone : vides.
