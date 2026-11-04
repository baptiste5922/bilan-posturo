# C1-T6 — journal des mises en échec

**Date :** 4 novembre 2026
**Branche :** `c1-t6-grille`, depuis `1ec796c`
**Règle :** un garde-fou non mis en échec ne garde rien (`CLAUDE.md`). Chaque
mutation ci-dessous a un **témoin sans mutation** (même commande, vert) et le
**code de retour du test lui-même**, lu en Python (`subprocess.run(...).returncode`),
jamais un `$?` lu après autre chose.

## Étape 0 — témoin de départ, sur `1ec796c`

| Suite | Résultat |
|---|---|
| `python3 -m unittest discover -s tests` | 219 tests, OK (2 sautés hors Windows) |
| `python3 -O -m unittest discover -s tests` | 219 tests, OK (2 sautés) |
| Suites Node de la CI (9 : `file_depots`, `pagination`, `version`, `palette`, `inventaire_formulaire`, `comparaison_dom`, `demarrage_moteur`, `nommage`, `concurrence_export`) | code 0 chacune |

Le contrat et `CLAUDE.md` parlent de « dix suites Node » : la CI et
`package.json` n'en comptaient que **neuf** à `1ec796c` ; la dixième est
`test_grille.js`, ajoutée par cette tâche.

## Fin de tâche

| Suite | Résultat |
|---|---|
| `python3 -m unittest discover -s tests` | **225** tests, OK (2 sautés) — 219 + 6 de `test_confidentialite_prospect` |
| `python3 -O -m unittest discover -s tests` | **225** tests, OK (2 sautés) |
| 10 suites Node, dont `test_grille.js` (88 cas) | code 0 chacune |
| `python3 -m pyflakes serveur/ tests/` | code 0 |

## Mutations de `formulaire/moteur/rendu.js` et de la spécification

Méthode : copie de travail par `git ls-files -z --cached --others
--exclude-standard` (ni `config.json`, ni clé, ni journal, ni la fiche du
prospect n'y figurent), fichier sauvegardé hors de la copie avant chaque mutation
et restauré par `cp`, **témoin sans mutation** relancé avant et après (les dix
suites Node, toutes à 0). Les dix suites sont rejouées à chaque mutation ; seules
celles qui rougissent sont listées (code 1 chacune).

| # | Mutation | Suites rouges | Premier cas qui rougit dans `test_grille.js` |
|---|---|---|---|
| a | `grille` accepté en version 1 (`version < 2` devient `version < 1`) | `grille` | une grille dans un document de version 1 est refusée, nommée « règle 16 » |
| b | séparateur de clé de cellule `__` changé en `_` | `grille` | règle 18 : une clé de cellule égale à la clé d'un champ qui la précède est refusée |
| c | clés de cellule hors de `clesChampVues` (un `Set` vide à la place) | `grille` | règle 18 : une clé de cellule égale à la clé d'un champ qui la précède est refusée |
| d | croisement avec les `cle` de bloc retiré (`false &&`) | `grille` | règle 18 : une clé de cellule égale à la clé d'un bloc est refusée |
| e | contrôle émis dans une cellule neutralisée | `grille` | DOM : les id des contrôles sont exactement les clés dérivées |
| f | `":"` ajouté au libellé du coin | `grille` | DOM : en-tête avec groupes (texte exact) |
| g1 | `maxlength` retiré | `grille` | DOM : natures de cellule |
| g2 | `autocomplete` retiré | `grille` | DOM : natures de cellule |
| h | borne de colonnes portée à 13 | `grille` | règle 17 : 13 colonnes refusé(e) |
| i | une classe ajoutée dans `creerTable()` | `comparaison_dom`, `grille` | v1 : le rendu de `formulaire/schema.json` est identique à l'instantané du commit 1ec796c |
| j | `VERSIONS_CONNUES` étendu à `[1, 2, 3]` | `comparaison_dom`, `demarrage_moteur`, `grille` | la version max de la spécification, celle du moteur et celle de la donnée concordent |
| k | l'exemple `grille` retiré de la spécification | `inventaire_formulaire`, `grille` | la spécification annonce les règles 15 à 20 et porte un exemple de grille valide |

Témoin sans mutation, relancé en tête et en fin de série :
`file_depots 0, pagination 0, version 0, palette 0, inventaire_formulaire 0,
comparaison_dom 0, demarrage_moteur 0, nommage 0, concurrence_export 0, grille 0`.

Lecture des cas (i) et (j) : (i) est attrapée à la fois par l'instantané de
`test_grille.js` et par `test_comparaison_dom.js` ; (j) l'est par trois suites
parce que « version max + 1 » y est dérivée de l'en-tête de la spécification et
que 3 devient connue du moteur.

## Mutations de l'étape 9 — les trois gardes de confidentialité

Faites **en place** (les gardes lisent l'index Git), arbre commité au préalable,
sauvegardes hors du dépôt (`.gitignore`, donnée fictive), restauration par `cp`.
**Aucun `git add` ni `git commit`** tant qu'une mutation était active. Après
chaque mutation : `git status --short` vide, `tests/donnees/_mutation.txt`
absent, `cmp .gitignore <sauvegarde>` à 0 — contrôlés par le script lui-même
(« état propre : True »). Le contenu du marqueur n'est jamais écrit ici : seule
la classe qui rougit est consignée.

Témoins sans mutation (code 0, avec et sans `-O`) : `FicheNonSuivie`,
`VocabulaireFictif`, `AucunMarqueurDeLaFiche` — cette dernière **exécutée**,
non sautée.

| # | Mutation | Classe qui rougit | `python3` | `python3 -O` | Ce que l'échec nomme |
|---|---|---|---|---|---|
| 1 | ligne 44 du `.gitignore` retirée | `FicheNonSuivie` | code 1 | code 1 | « la fiche n'est plus ignorée par Git (code 1) » |
| 2 | un `libelle` de la donnée fictive remplacé par un mot hors vocabulaire | `VocabulaireFictif` | code 1 | code 1 | un chemin JSON, jamais la valeur |
| 3 | fichier non suivi `tests/donnees/_mutation.txt` portant un marqueur choisi par le script | `AucunMarqueurDeLaFiche` | code 1 | code 1 | `tests/donnees/_mutation.txt:1`, jamais le marqueur |

### Un vrai positif, trouvé en cours de route

Avant la mutation 3, la garde `AucunMarqueurDeLaFiche` avait déjà échoué deux
fois **sur du texte écrit par cette tâche** :

- elle signalait des tokens techniques (`aria-label`, une clé de grille), parce
  que D9 impose des clés `grille-N` que la fiche emploie aussi et que D12 nomme un
  attribut WAI-ARIA absent jusque-là du dépôt. Écart assumé et signalé :
  deux exemptions écrites dans la garde (vocabulaire fictif de D9 ; liste fermée
  d'un seul attribut standard) ;
- elle signalait un commentaire CSS de cette tâche, dont une expression courante
  de huit caractères figurait aussi dans un nœud de texte de la fiche. Le
  commentaire a été reformulé ; le seul remède légitime d'un vrai positif est de
  ne pas écrire ce texte. La garde mord donc sur du texte réel, pas seulement
  sous la mutation.

Son extraction des littéraux de script confondait aussi la prose des
commentaires français (apostrophes) avec des chaînes : remplacée par un petit
parcours qui saute `//` et `/* */` (`litteraux_js`).

## Mutations de l'essai de rendu réel (en plus de ce que le contrat demandait)

Faites sur la copie du formulaire du **bac à sable**, jamais sur le dépôt ;
témoin « 7 lignes OK, code 0 » avant chaque série, restauration par `cp` et
`cmp` contre le dépôt.

| Mutation du bac | Vérification qui devient « RATÉ » | Code de l'essai |
|---|---|---|
| `display: table-cell` retiré de `table.grille th.titre_section` (le défaut d'en-tête du constat) | 3 (en-têtes alignés sur leurs colonnes) | 1 |
| `.grille-texte { width: 9em }` ramené à `5em` | 4 (`WWWWWWWW` coupé) | 1 |
| grille 3 dont 5, 6 puis 12 colonnes sur 12 sont du texte court | 3 (débordement : 1260, 1350, 1891 px) | 1 |

## Étape 12 — absence de mutation résiduelle

- `git diff 1ec796c -- formulaire/moteur/rendu.js` relu en entier : seules
  figurent les modifications de l'implémentation (constantes de version et de
  grille, `validerGrille`, `cleCellule`, exemption de bloc, `creerGrille`), aucune
  mutation ci-dessus.
- `git status --short` : aucun fichier inattendu ; `fiche_presentation.html` y
  est absente (ignorée), `tests/donnees/_mutation.txt` n'existe pas.
- `git diff --quiet 1ec796c -- .gitignore` : code 0.

## Critère 12 — `AucunMarqueurDeLaFiche` exécuté sur le poste de l'implémenteur

```
$ python3 -m unittest -v tests.test_confidentialite_prospect
test_aucun_marqueur_dans_les_fichiers_changes (...AucunMarqueurDeLaFiche...) ... ok
test_absente_de_l_index (...FicheNonSuivie...) ... ok
test_toujours_ignoree (...FicheNonSuivie...) ... ok
test_donnees_de_test (...VocabulaireFictif...) ... ok
test_exemples_de_grille_de_la_specification (...VocabulaireFictif...) ... ok
test_le_verificateur_mord (...VocabulaireFictif...) ... ok

Ran 6 tests in 3.4s
OK
```

(Aucun « skipped » : la fiche est présente, le commit de repère aussi.)

## Critère 14 — intégration continue

Exécution `workflow_dispatch` sur la branche, au commit « Écarte la prose des
commentaires de la garde de marqueurs » : identifiant
**41809865962**, succès sur les sept tâches — `test` (ubuntu 3.9 et 3.13,
windows 3.9 et 3.13, macos 3.13), `scripts-windows` et `lint`.
