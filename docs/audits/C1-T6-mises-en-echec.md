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

Le contrat et `CLAUDE.md` parlent de « dix suites Node » (onze depuis A1, avec
`test_export_grille.js`) : la CI et
`package.json` n'en comptaient que **neuf** à `1ec796c` ; la dixième est
`test_grille.js`, ajoutée par cette tâche.

## Fin de tâche

| Suite | Résultat |
|---|---|
| `python3 -m unittest discover -s tests` | **226** tests, OK (2 sautés) — 219 + 7 de `test_confidentialite_prospect` |
| `python3 -O -m unittest discover -s tests` | **226** tests, OK (2 sautés) |
| 10 suites Node, dont `test_grille.js` (88 cas) ; `npm test` | code 0 chacune ; `npm test` à 0 |
| **Après A1** : 11 suites Node, dont `test_export_grille.js` (14 cas) ; Python inchangé à 226 (aussi sous `-O`) | code 0 chacune ; `npm test` à 0 |
| `python3 -m pyflakes serveur/ tests/` | code 0 |

## Mutations de `formulaire/moteur/rendu.js` et de la spécification

Méthode : copie de travail par `git ls-files -z --cached --others
--exclude-standard` (ni `config.json`, ni clé, ni journal, ni la fiche du
prospect n'y figurent), fichier sauvegardé hors de la copie avant chaque mutation
et restauré par `cp`, **témoin sans mutation** relancé avant et après (les dix
suites Node, toutes à 0). Les dix suites alors existantes (onze depuis A1) sont rejouées à chaque mutation ; seules
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

## Reprise après l'audit de sécurité

### La garde lit désormais les valeurs d'attributs

`AucunMarqueurDeLaFiche` ignorait les valeurs d'attributs HTML (`id`, `name`,
`aria-*`, `data-*`…), où vivent les identifiants. L'extraction recueille
maintenant `id`, `class` (découpée en jetons), `name`, `for`, `placeholder`,
`title`, `alt`, `value`, `label` et tout `aria-*` / `data-*`, avec les mêmes
règles : normalisation, seuil de huit caractères, retrait de ce qui est déjà
public à `1ec796c`, exemptions D9 et d'un attribut standard, échecs qui ne
nomment que fichier et ligne. Aucune exemption nouvelle ; les fichiers de la
tâche n'ont déclenché aucun faux positif. Un test sans fiche ni git
(`ExtractionDeLaFiche`) éprouve l'extraction sur un HTML synthétique.

Mutation : un fichier non suivi `tests/donnees/_mutation.txt` portant **une valeur
d'attribut propre à la fiche** (choisie par le script parmi les marqueurs que
l'extension a ajoutés, ni écrite à la main ni affichée). Hygiène de l'étape 9 :
arbre commité au préalable, rien d'indexé pendant la mutation, fichier supprimé
ensuite.

| Contrôle | Résultat |
|---|---|
| Marqueurs avant / après l'extension | 294 / 352, dont 58 propres aux attributs |
| Témoin sans mutation, `AucunMarqueurDeLaFiche` | code 0 ; sous `-O` code 0 |
| Garde d'**avant** l'extension, sur le fichier de mutation | ne trouve rien (aveugle : c'est ce que l'extension corrige) |
| Mutation, garde étendue | code 1 (`tests/donnees/_mutation.txt:1`, jamais la valeur) |
| Mutation rejouée sous `python3 -O` | code 1 |
| Après nettoyage | fichier absent ; `git status --short` ne montre que `docs/audits/C1-T6.md`, non suivi, rapport de l'auditeur |
| Témoin final | code 0 ; sous `-O` code 0 |

### Intitulés de ligne

Le `white-space: nowrap` des intitulés de ligne est retiré (le coin le garde). Un
intitulé de 200 caractères ne dépasse plus la page (1182 px au lieu de 1590) ;
le correctif d'en-tête a été rejoué : essai réel à sept « OK » et PDF contrôlé à
l'œil. Détail et mesures de largeur : `CONSTAT-2026-11-04-C1-T6.md`.

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

Ran 7 tests in 5.6s
OK
```

(Aucun « skipped » : la fiche est présente, le commit de repère aussi.)

## Critère 14 — intégration continue

Exécution `workflow_dispatch` sur la branche, au commit « Écarte la prose des
commentaires de la garde de marqueurs » : identifiant
**41809865962**, succès sur les sept tâches — `test` (ubuntu 3.9 et 3.13,
windows 3.9 et 3.13, macos 3.13), `scripts-windows` et `lint`.

Après l'amendement A1 : exécution **41847917207**, sur le commit `d84b443`, succès
sur les mêmes sept tâches.

## Amendement A1 — mutations (m) à (s), sur une copie passée par `SCRIPT_A_TESTER`

`formulaire/script.js` n'est jamais muté en place : le mutant vit dans un fichier
hors du dépôt, passé par `SCRIPT_A_TESTER` aux suites qui l'acceptent
(`export_grille`, `concurrence_export`, `pagination`, `version`) ; pour celles qui
lisent un chemin fixe (`file_depots`, `palette`, `nommage`), une copie du dépôt
par `git ls-files -z --cached --others --exclude-standard` dont `script.js` est
le mutant. Chaque mutation est précédée du **témoin sans mutation** (les sept
suites à 0) ; le code de retour est celui du test lui-même, lu en Python. A1 ne
pose aucune garde Python : rien à rejouer sous `-O`.

Témoin sans mutation : `export_grille 0, concurrence_export 0, pagination 0,
version 0, file_depots 0, palette 0, nommage 0` — en tête et en fin de série ;
`git diff --quiet HEAD -- formulaire/script.js` à 0 après la série.

| # | Mutation | Suite rouge (code 1) | Premier cas rouge |
|---|---|---|---|
| m | `table.grille` devient `table` dans la réduction (`preparerClone`) | `export_grille` | preparerClone : une grille qui dépasse (sous la référence) est réduite, elle seule |
| n | refus supprimé (`if (false)`) | `export_grille` | export : une grille qui dépasse avec une largeur de référence + 1 est refusée |
| o | refus déplacé après `mettreEnFile()` | `export_grille` | idem (html2canvas appelé) |
| p | `>` devient `>=` | `export_grille` | export : une grille qui dépasse mais dont la largeur égale la référence est acceptée |
| q1 | `transformOrigin` retiré | `export_grille` | preparerClone : une grille qui dépasse … est réduite, elle seule, origine en haut à gauche |
| q2 | facteur forcé à 1 (`scale(1)`) | `export_grille` | idem |
| r | constante portée de 1192 à 1100 | **aucune suite unitaire** (elles lisent la constante dans le source) ; **essai réel : vérification 9 « RATÉ »** (disponible 1192, constante 1100), code 1 ; témoin : « OK », code 0 | — |
| s | `document.querySelectorAll(".sans-pdf")` au niveau module | `export_grille` | A1-D6 : script.js se charge sans toucher au DOM |

Précisions honnêtes :

- **(m)** : le cas rouge est celui de la table de la V1, touchée à la place de la
  grille de même rang. Rejouée au pixel (critère 19), la mutation resterait
  **invisible** sur `index-v1.html` et sur le schéma pilote : sans grille à
  réduire, `preparerClone()` n'interroge pas la copie (A1-D3). Seul un schéma qui
  mêle un tableau de la V1 et une grille réduite la révélerait, et c'est ce que
  couvre `test_export_grille.js`.
- **(s)** : `test_file_depots.js` et `test_concurrence_export.js` restent verts,
  car leurs doubles fournissent un `document.querySelectorAll` qui ne lève rien. La
  garde est donc le cas A1-D6 de `test_export_grille.js`, dont le `document` lève
  à tout accès sauf `addEventListener`.
- **(r)** : la constante est lue dans le source par les tests unitaires, qui
  suivent donc toute valeur ; seule la mesure au rendu réel (critère 22) détecte
  une constante fausse, c'est sa raison d'être.

Mutations de l'essai réel, en plus (copie du bac, jamais le dépôt) :

| Mutation du bac | Scénario | Vérifications « RATÉ » | Code |
|---|---|---|---|
| refus supprimé | refus, 1280 px | 1 (message) et 2 (un PDF est déposé) | 1 |
| réduction neutralisée (`transform = ""`) | complet, 1024 px | 8 (grille 3 : bord droit à 1159,2 px pour 996,0) | 1 |

## Reprise après la revue — mode `mesure`, largeur de `produire.js`, égalité stricte

Faites sur des copies de bac hors du dépôt, avec témoin et code de retour.

**`ESSAI_MODE=mesure`** (épreuve d'atelier d'un schéma client, spécification
§5.3, condition 2) : ne saisit rien, une ligne « OK » / « RATÉ » par grille (largeur
au plus égale à `LARGEUR_GRILLE_REFERENCE_PX`, lue dans le source servi), puis la
vérification de la constante à 1280 px.

| Schéma | Résultat | Code |
|---|---|---|
| `schema-v2-grilles-fictives.json` | « OK » pour le rendu, les trois grilles (1182 px chacune pour 1192) et la constante (disponible 1192, 1192, 1192 ; source 1192) | 0 |
| `schema-v2-grille-trop-large.json` (témoin négatif) | « RATÉ » pour la grille 1 : 1911 px contre 1192 ; constante « OK » | 1 |

Les modes d'origine sont inchangés : complet à 1280 et 820 px, et refus, rejoués
tous « OK », code 0.

**Vérification de la constante, désormais stricte** (`disponible === constante`, au
lieu de 0,5 px près). Mutation du bac : constante servie à 1192,4, que l'ancienne
tolérance aurait laissée passer — vérification « RATÉ », code 1 ; témoin à 1192,
« OK », code 0.

**`produire.js` relit `window.innerWidth`** et l'imprime à chaque production
(« fenêtre : 1280 px » par défaut ; « fenêtre : 1024 px (demandé : 1024) » avec
`ESSAI_LARGEUR=1024`). Témoin négatif : copie de `produire.js` hors du dépôt dont
l'imposition de largeur est neutralisée, `ESSAI_LARGEUR=1000` — elle imprime
« fenêtre : 1280 px (demandé : 1000) », « ÉCHEC : largeur de fenêtre 1280 au lieu
de 1000… », code 1. (Les essais de `produire.js` ont tourné sur un port de débogage
autre que 9222, par une copie ; le refus d'un Chrome que `cdp.js` n'a pas lancé
reste hors du contrat.)
