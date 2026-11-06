# C1-T4a — journal des mises en échec

**Date :** 6 novembre 2026
**Branche :** `c1-t4a-schema-cabinet`, depuis `0f33cc0`
**Règle :** un garde-fou non mis en échec ne garde rien (`CLAUDE.md`). Chaque
mutation a son **témoin** (la même commande sur l'arbre sain) et le **code de
retour du test lui-même**, lu dans la sortie du test (`code du test : N`), jamais
un `$?` lu après autre chose.

## Méthode

- Chaque mutation se joue dans un **clone jetable** du dépôt
  (`git clone --no-hardlinks`), puis `git remote remove origin`, avec contrôle
  `git remote | wc -l` → `0` : un clone qui garde son `origin` pourrait pousser
  dans le dépôt réel. Aucune mutation n'a touché l'arbre de travail réel, ni son
  index ; le dépôt réel est vérifié en fin de journal.
- Un clone ne contient que des objets commités : ni `config.json`, ni clé, ni
  journal. Le clone sain porte l'étiquette `production-cabinet-01`, dont G4 a
  besoin.
- Le script de mutation est hors dépôt (dossier de travail de la session) ; la
  sortie intégrale est reproduite ici en résumé, cas par cas.

## Départ

| Mesure | Avant (`0f33cc0`) | Après |
|---|---|---|
| `python3 -m unittest discover -s tests` | 314 tests, 2 sautés | **318** tests, 2 sautés, OK |
| `python3 -O -m unittest discover -s tests`, premier plan | — | 318 tests, OK |
| Suites Node | 12 | **13** (`test_schema_client.js`, 8 cas), toutes à 0 |
| `npm test` | — | code 0 |
| `python3 -m pyflakes serveur/ tests/` | — | code 0 |
| `python3 -W error::ResourceWarning -m unittest tests.test_paquet tests.test_scripts_installation` | — | 20 tests, OK |

Au départ, `ServeurArret.test_arret_journalise` échouait quand la suite était
lancée en arrière-plan (`SIGINT` ignoré, piège connu de `CLAUDE.md`) et passait
au premier plan : ce n'est pas un test instable.

## Extraction de l'analyseur HTML (critère 4)

`node tests/test_comparaison_dom.js` joué **avant** puis **après** l'extraction
de `analyserAttributs`, `analyserHtml` et `extraireElement` dans
`tests/outils/analyseur-html.js` : sortie enregistrée hors dépôt dans les deux
cas, `diff avant.txt apres.txt` vide et `cmp` à 0 (10 lignes, « Tout est vert. »).

## Mutations

| N° | Mutation (clone jetable sans `origin`) | Cas qui rougissent | Code du test | Témoin |
|---|---|---|---|---|
| M0 | Les quatre nouveaux tests de `test_paquet.py` rejoués contre le `faire-paquet.sh` de `main` (le code d'avant) | 8 échecs (sans argument, chemins, client inconnu, schéma du client) | 1 | arbre sain : 7 tests, OK, code 0 |
| M1 | `clients/cabinet-01` renommé d'après une ville (le journal d'origine employait le nom réel ; il est remplacé ici par un nom fictif) | **G1** (nom), puis G3 et G4 par ricochet | 1 | `node tests/test_schema_client.js` : « Tout est vert », code 0 |
| M2 | `"type": "inconnu"` dans `clients/cabinet-01/schema.json` seulement | **G2**, aussi G3 (comme prévu au contrat) | 1 | idem |
| M3 | une espace de plus dans `formulaire/schema.json` seulement | **G3** seul ; G2 et G4 restent verts | 1 | idem |
| M4 | `familliaux` → `famillaux` dans les **deux** copies | **G4** « mêmes clés » seul ; **G3 reste vert** ; le message nomme la clé `familliaux` | 1 | idem |
| M5 | clone `--no-tags` : étiquette absente | **G4**, quatre cas, avec le remède `git fetch --tags` (cité deux fois) : échec bruyant, **jamais un saut** | 1 | idem |
| M6 | `squelette_gauche.png` ↔ `squelette_droite.png` permutés dans les **deux** copies | **G4** « mêmes images annotables » seul ; G3 reste vert | 1 | idem |
| M7 | `docs/references-visuelles/x.png` indexé (`git add -f`), pas de la CI joué par `bash -e` sur le texte extrait de `tests.yml` | le pas sort **1** et nomme le fichier. Avec `capture-écran.pdf` (nom accentué) indexé : sort 1 aussi. | 1 | arbre sain : « Aucune image ni PDF… », code 0 |
| M8 | la ligne `cp "clients/$CLIENT/schema.json" …` commentée dans `faire-paquet.sh` | `test_le_schema_du_paquet_est_celui_du_client_et_aucune_entree_clients` | 1 | `tests.test_paquet` sain : 7 tests, OK |
| M8b | idem **et** contrôle `cmp` final du script neutralisé : le test seul doit rougir | le même test, sur le contenu de l'archive | 1 | idem |
| M9 | *(ajout)* `CLE_BROUILLON` changée dans `script.js` | **G4** « même clé de stockage… » | 1 | idem M1 |
| M10 | *(ajout)* `cleChamp()` modifiée dans `script.js` | **G4** « …même cleChamp() » (le cas « mêmes clés » reste vert : il appelle la même fonction mutée des deux côtés, d'où la garde sur le corps de la fonction) | 1 | idem M1 |
| M11 | *(ajout)* `clients/cabinet-01` supprimé : `clients/` sans aucun dossier | **G1** « au moins un dossier » : un test vert à vide ne garderait rien | 1 | idem M1 |

Observations :

- **M4 et M6 sont les mutations qui comptent** : G3 reste vert, seul G4 les voit.
  Sans lui, une clé renommée ou deux planches permutées dans les deux copies
  perdraient le bilan d'une consultation en cours ou décaleraient les traits, et
  rien ne rougirait.
- **M5** : la suite échoue avec le remède, y compris pour le cas de
  `CLE_BROUILLON`. `tests.yml` la joue après un `checkout` en `fetch-depth: 0`.
- **M7** : le pas de CI lui-même ne se joue pas à la main ; son texte est extrait
  de `.github/workflows/tests.yml` du clone mué et exécuté par `bash -e`, ce qui
  éprouve la logique (`-z`, `core.quotePath=false`, code de `grep` > 1 traité en
  erreur), pas le lanceur GitHub.
- **M8 / M8b** : le contrôle `cmp` du script et le test Python se couvrent l'un
  l'autre ; M8b prouve que le test seul suffit.

## Outil : `empreintes-pages.js`

Éprouvé sur les PDF de la mesure (`docs/references-visuelles/CONSTAT-2026-11-06-C1-T4a.md`),
1 280 px :

| Essai | Code |
|---|---|
| un PDF contre lui-même | 0 |
| un export contre un second export du même brouillon (`d43350a`, `http.server`) | 0 — 3 pages égales |
| **témoin négatif** : même bilan, un trait de plus (5 traits restaurés au lieu de 4) | **1 — page 2** |
| un seul PDF | une ligne `page N  <sha256>  <octets>` par page |
| sans argument | 2 (usage) |

**Mesure du déterminisme.** Il n'est pas total : une page varie entre deux états
(M-moteur 2 exports sur 7, M-secours 3 sur 7, `d43350a` sous `serveur.py` 2 sur 6,
`d43350a` sous `http.server` 0 sur 7). Ces effectifs ne séparent pas les deux
serveurs (p ≈ 0,19) : la cause n'est **pas établie** ; ce qui l'est, c'est que la
variante existe sur `d43350a` lui-même, donc qu'elle n'est pas due au moteur. Le
détail est au constat, section 3. La prémisse du contrat (« un export contre un
second export du même brouillon rend 0 ») n'est donc pas une propriété stable :
écart au contrat, consigné.

## Vérifications de fin

| Critère | Commande | Résultat |
|---|---|---|
| 15 | `stat -f '%m %z %N'` sur les fichiers réels de la racine (8 entrées : `autorite-cle.pem`, `autorite.crt`, `bilans/`, `certificat.pem`, `cle.pem`, `config.json`, `journal.log`, `technique.log`), avant et après, `diff` | vide |
| 16 | `git diff 0f33cc0 --stat -- formulaire/ serveur/ docs/production/` | vide (voir l'écart ci-dessous) |
| 16 | `git rev-parse production-cabinet-01^{commit} maintenance-cabinet-01` | `d43350a0cf20fef5672eadc7bcb6f67e156dc977` deux fois |

## Écarts au contrat, consignés

1. **Critère 16, lettre.** `git diff main --stat -- formulaire/ serveur/ docs/production/`
   liste `docs/production/cabinet-01.md` : cette fiche a été ajoutée par `0f33cc0`
   (« Archive la version du cabinet »), avant la tâche, et `main` ne l'a pas.
   Contre `0f33cc0`, le départ de la branche, la commande ne rend rien : aucun
   fichier de `formulaire/`, `serveur/` ou `docs/production/` n'a été touché.
2. **Critère 10, `"traits":4`.** `produire.js` lisait `window.zonesDessin`, qui
   n'existe pas (`const` de `script.js`) : le rapport rendait toujours `-1`. Lecture
   corrigée (outillage seulement) ; le mode `moteur` imprime aussi le nom produit par
   le formulaire.
3. **Étape 6, prémisse du déterminisme** : voir plus haut. Le critère 10 est
   satisfait par sa seconde branche (« chaque page différente localisée »), et le
   critère 11 sur une paire d'exports tombés sur la même variante.
4. **Ajouts à G4** (hors liste du contrat, même but) : égalité du corps de
   `cleChamp()` entre le blob et l'arbre, et mutations M9 à M11.
5. **Étape 7.2** : le contrôle `diff … | head -1` rend `65,68c65,68` ; un second
   décompte (8 lignes de diff, pas un octet de plus) a confirmé que seuls les
   quatre `<p>` diffèrent, sans rien afficher.

## Reprise après la revue (corrections retenues par le coordinateur)

Mêmes règles (clone jetable sans `origin`, l'état courant de l'arbre recopié par
`git ls-files -z`, témoin avant, code du test lui-même). Le journal d'origine
ci-dessus est conservé ; la mutation M5 y portait sur l'**étiquette** : G4 lit
désormais le **SHA complet** `d43350a0cf20…` (l'étiquette est déplacée à chaque
installation, `docs/production/cabinet-01.md`), M5 est donc rejouée en M5'.

| N° | Mutation | Résultat | Code | Témoin |
|---|---|---|---|---|
| M5' | commit de référence absent : clone `--depth 1 --no-tags` (objet vérifié absent) | **G4**, quatre cas, avec le remède `git fetch` (cité deux fois) : échec bruyant, **jamais un saut** | 1 | clone sain : « Tout est vert », 0 |
| M5'b | étiquette `production-cabinet-01` **déplacée** sur `HEAD` | G4 **reste vert** : c'est le but du SHA | 0 | — |
| M12 | lien symbolique `clients/cabinet-02` → `cabinet-01` | **G1** | 1 | idem |
| M13 | fichier à plat `clients/ville-fictive.json` | **G1** | 1 | idem |
| M14 | un `.pdf` indexé de force (`git add -f`) dans `outils/reference-visuelle/sortie/` (le `.gitignore` le couvre : `check-ignore` oui) | le pas CI sort **1** et nomme le fichier | 1 | arbre sain : code 0 |
| M14b | un `.json` indexé de force dans `sortie/` (rien n'y est admis) | pas CI **1** | 1 | idem |
| M7 rejoué | un `.png` indexé sous `docs/references-visuelles/` | pas CI **1** | 1 | idem |
| M15 | `rm -f "$PAQUET.zip"` retiré de la boucle des pièces obligatoires de `faire-paquet.sh` | `test_piece_absente_de_l_archive_efface_l_archive` | 1 | `tests.test_paquet` sain : 8 tests, OK |
| M4 rejoué | `familliaux` → `famillaux` dans les deux copies, avec le SHA épinglé | **G4** « mêmes clés » seul, G3 reste vert | 1 | idem |
| M16 | `empreintes-pages.js` sur deux fichiers absents | code **2** (et non 1, « différent ») | 2 | — |

Tests après reprise : 319 tests Python (le nouveau : pièce obligatoire absente de
l'archive) ; 13 suites Node ; les chiffres de fin sont ci-dessous.

## Intégration continue

`env -u GITHUB_TOKEN gh workflow run tests.yml --ref c1-t4a-schema-cabinet`, sur
`0b95515` : **7 jobs sur 7 verts** (5 combinaisons du job `test`, `lint`,
`scripts-windows`), dont le pas « Run client schema tests » (Linux, Python 3.9)
et le pas « Check that no image or PDF is versioned… » (lint).
Run : https://github.com/baptiste5922/bilan-posturo/actions/runs/42212161381

**Après la reprise de la revue** : run
https://github.com/baptiste5922/bilan-posturo/actions/runs/42236920584, sur
`f907c6d` : **7 jobs sur 7 verts** (le job macOS est resté en file d'attente
quelques minutes faute de machine, puis a réussi).
