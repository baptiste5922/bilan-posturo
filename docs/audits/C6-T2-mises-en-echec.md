# C6-T2 — journal des mises en échec

**Date :** 26 novembre 2026
**Branche :** `c6-t2-limitation-auth`, depuis `612c65e` (dernier commit de `main` :
la clôture `67fefd2` plus l'index des sections ; le contrat, commité en `918f2f7`,
nommait `cff8210` : **`612c65e` est substitué à `cff8210` dans toutes les
commandes de la §8**).
**Règle :** un garde-fou non mis en échec ne garde rien (`CLAUDE.md`). Chaque
série a son **témoin** (l'arbre sain, avant et après) ; chaque résultat est lu
sur le code de sortie de la commande elle-même (`0` vert, `1` rouge) et sur sa
dernière ligne (`OK` / `FAILED`).

## Méthode

- Copie jetable hors du dépôt, obtenue par `git ls-files -z | rsync -a --from0
  --files-from=-` : elle ne contient que les fichiers suivis (ni `config.json`,
  ni clé, ni journal, ni bilans). Le dépôt réel n'a reçu aucune mutation ;
  `git status` et `git diff` sont vides à la fin (relevé en dernière section).
- `serveur/serveur.py` de la copie est **sauvegardé hors de la copie** ;
  chaque mutation le réécrit depuis la sauvegarde à la fin de son tour (`finally`).
  Le script **refuse une mutation sans effet** : chaque motif remplacé doit se
  trouver **exactement une fois**.
- Commande jouée sur chaque arbre muté : `python3 -m unittest
  tests.test_limitation_auth` (22 tests), puis la même sous `python3 -O` pour
  M1, M2, M6 et M10, celles qu'un `assert` nu aurait laissées passer. Le script
  de la série est resté hors du dépôt (scratchpad de la session).

## Avant le code (témoin rouge)

Le fichier de tests joué contre `serveur.py` de `612c65e` : échec immédiat à
l'import, `AttributeError: module 'serveur' has no attribute 'attendre'`
(`ATTENDRE_REEL = serveur.attendre`, en tête de module). Aucun test ne peut donc
passer sans le mécanisme.

## Mutations

| N° | Garde visée | Mutation | Code | Tests qui rougissent (python3) |
|---|---|---|---|---|
| M1 | Fenêtre d'oubli | le bloc `if … > FENETRE_ECHECS_AUTH_SECONDES: ECHECS_AUTH = 0` supprimé | 1 | `test_u3_fenetre_d_oubli` |
| M2 | Remise à zéro sur succès | `reinitialiser_echecs_authentification()` retiré de la branche valide | 1 | `test_u4_succes_remet_a_zero`, `test_f1_identifiant_valide_jamais_retarde` |
| M3 | Aucun délai sur un succès (D2) | `attendre(...)` posé avant les deux vérifications, et retiré de la branche de refus | 1 | `test_f1_identifiant_valide_jamais_retarde` |
| M4 | Une requête sans identifiants n'est pas comptée (D3) | la branche « pas de `Basic ` » compte, attend et pose `refuses` | 1 | `test_f2_sans_entete_jamais_compte`, `test_f4_remise_a_zero_entre_requetes_d_une_meme_connexion`, `test_j1_forme_du_detail_derivee` |
| M5 | `/sante` hors du mécanisme | `attendre(3.0)` dans `repondre_sante` | 1 | `test_g1_le_sommeil_est_circonscrit`, `test_e2_sante_intacte_apres_quinze_echecs` |
| M6 | Plafond | `min(ATTENTE_AUTH_MAX_SECONDES, …)` retiré | 1 | `test_u2_progression_et_plafond`, `test_u3_fenetre_d_oubli` |
| M7 | Rien ne dort sous un verrou | `attendre(...)` déplacé dans le `with _verrou_auth` de `noter_echec_authentification` | 1 | `test_g2_rien_ne_dort_sous_le_verrou`, `test_f5_aucun_verrou_tenu_pendant_le_sommeil`, `test_g1_le_sommeil_est_circonscrit`, `test_e4_un_depot_legitime_aboutit_pendant_que_des_refus_dorment` |
| M8 | Aucune adresse dans le détail | `self.client_address[0]` ajouté à la route du détail d'`AUTH_REFUSEE` | 1 | `test_j2_aucune_fuite_dans_le_detail`, `test_j1_forme_du_detail_derivee`, `test_e1_le_onzieme_refus_dort_vraiment`, `test_f4_remise_a_zero_entre_requetes_d_une_meme_connexion` |
| M9 | Vocabulaire fermé non vide | `MOTIFS_AUTH_REFUSEE = frozenset()` | 1 | `test_j1_forme_du_detail_derivee` (ancrage ≥ 2 jetons), `test_e1_…`, `test_f2_…`, `test_f4_remise_a_zero_entre_requetes_…` |
| M10 | Seuil | `SEUIL_ECHECS_AUTH = 1` | 1 | `test_u1_seuil`, `test_u2_progression_et_plafond`, `test_e1_le_onzieme_refus_dort_vraiment` |

Résultats lus (`python3`) : témoin avant `Ran 22 tests … OK` (code 0) ; M1
`FAILED (failures=1)` ; M2 `FAILED (failures=2)` ; M3 `FAILED (failures=1)` ; M4
`FAILED (failures=3)` ; M5 `FAILED (failures=2)` ; M6 `FAILED (failures=2)` ; M7
`FAILED (failures=4)` ; M8 `FAILED (failures=15)` (sous-tests) ; M9 `FAILED
(failures=4)` ; M10 `FAILED (failures=12)` ; témoin après `OK` (code 0).

Série `python3 -O` : témoin avant `OK` (0) ; M1 `FAILED (failures=1)` (1) ; M2
`FAILED (failures=2)` (1) ; M6 `FAILED (failures=2)` (1) ; M10 `FAILED
(failures=12)` (1) ; témoin après `OK` (0). Mêmes tests rouges que sous `python3`.

Remarques :

- **Toutes les mutations attendues par le contrat rougissent les tests qu'il
  nomme**, et quelques-uns de plus : M5 et M7 rougissent G1 (un `attendre`
  appelé hors d'`authentifie`), M7 rougit aussi E4 (un fil endormi sous
  `_verrou_auth` retarde le dépôt légitime), M4, M8 et M9 rougissent
  `test_f4_remise_a_zero_entre_requetes_…` parce que son détail attendu est exact.
- **M3** n'est mordue que par `test_f1` : la preuve « un succès n'attend jamais »
  est l'espion, comme D9 le veut ; aucun essai de bout en bout ne la double, par
  prudence sur les bornes supérieures mesurées.
- **M6** coûte 25 s au lieu de 11 : sans plafond, les refus du bac à sable
  dorment 4, 8, 16 s… C'est le signe que le plafond protège aussi la suite.

## Écart de contrat relevé en route

La formule de l'étape 2, `min(MAX, BASE * 2 ** (echecs - SEUIL - 1))`, lève
`OverflowError: int too large to convert to float` dès que l'exposant dépasse
environ 1 023 : `min` ne protège pas, l'exposant est évalué avant. Le critère A2
(`attente_apres_echec(10**6)`) était donc impossible avec elle. L'exposant est
borné à 32 avant le calcul (`BASE * 2 ** 32` dépasse tout plafond raisonnable),
et `min(MAX, …)` reste la borne qui compte : M6 la mord.

## Arbre de travail à la fin

`git status --short` : seuls les trois `BilanPosturo_video*.mp4` non suivis,
étrangers à la tâche. `git diff` : vide.

## Run de CI

À faire après l'audit (`env -u GITHUB_TOKEN gh workflow run tests.yml --ref
c6-t2-limitation-auth`) : numéro du run à noter ici.
