# Contrat C1-T4a — Écrire le schéma du cabinet dans le dépôt

**Chantier :** C1  **Effort estimé :** M  **Date :** 2026-11-06
**Process :** Complet (fixé par `docs/ROADMAP.md`, section C1-T4)
**Décisions bloquantes :** aucune pour commencer. La mesure de l'étape 7 peut
en faire naître pour **C1-T4b** (et pour elle seule) : la règle qui les déclare
est au §7, D6.

> **Rien ne part au cabinet.** Aucune ligne de cette tâche ne modifie ce qui y
> tourne (`d43350a`, étiquette `production-cabinet-01`, branche
> `maintenance-cabinet-01`). Elle prépare C1-T4b, qui attend la visite.

## 1. Objectif

Après cette tâche, le schéma du cabinet pilote existe à l'emplacement prévu
pour chaque client, `clients/cabinet-01/schema.json`, et c'est lui qui part
dans le paquet : `outils/faire-paquet.sh cabinet-01`. Surtout, la
fidélité au pixel est mesurée **contre ce qui tourne vraiment au cabinet**
(`d43350a`) et non plus seulement contre la fiche de secours. Un constat daté
dresse la liste exacte de ce que la praticienne verra changer le jour de
C1-T4b. Avant, cette liste n'existait pas, et la seule preuve au pixel visait
`index-v1.html`, qui n'est pas la version installée.

## 2. Pourquoi

- **Verrou n°2 de la projection** (`docs/projection.md`, « Le piège du template
  unique », §5) : un moteur unique, N descriptions. `clients/<client>/` est la
  place de ces descriptions ; C1-T5 (blocs) et C9-T2 (atelier) partent de
  `clients/cabinet-01/` (dépendance « C1-T4a » dans `docs/ROADMAP.md`).
- **Un seul utilisateur en production.** C1-T4b franchira d'un coup l'écart
  `d43350a` → `main`, soit +3256/−389 lignes sous `formulaire/`. Or la preuve
  au pixel du 19 octobre portait sur moteur ↔ `index-v1.html`. Et
  `index-v1.html` **diffère** de l'`index.html` installé, sur trois points
  (§3, F2). La pagination n'a plus été comparée depuis C2-T1
  (`docs/references-visuelles/CONSTAT-2026-11-03-C2-T1.md:43`). Sans mesure
  contre `d43350a`, C1-T4b livrerait sur une foi transitive, celle-là même
  qu'a démentie le 19 octobre (cinq écarts sous 115 tests verts).
- **Le brouillon gelé** (`CLAUDE.md`, pièges) : la mise à jour aura lieu un
  jour de consultation. Un brouillon commencé sur `d43350a` doit se rouvrir
  sur la version livrée.
- **D8 de C2-T1** (`docs/contrats/C2-T1.md:602-613`) : le dossier client
  s'appelle `cabinet-01`, jamais d'après une ville. Aucune donnée
  d'identité dans le dépôt, qui est public.

## 3. État actuel

Faits vérifiés le 6 novembre 2026 sur `c1-t4a-schema-cabinet` (`0f33cc0`,
arbre propre, `main` = `48e3c43` poussé).

**Ce qui est déjà fait, et qui réduit la tâche :**
- `formulaire/schema.json` porte déjà les 28 blocs du cabinet, au format v1
  (`"version_schema": 1`, ligne 2), et le moteur les rend depuis C1-T3b
  (`formulaire/moteur/rendu.js:1386`, `fetch("schema.json")`). Le « travail 1 »
  de la feuille de route (écrire le schéma) est **fait** : il reste à le placer,
  à le livrer par client et à le mesurer contre la production.
- La fidélité moteur ↔ `index-v1.html` est prouvée au pixel (CONSTAT du
  19 octobre) et gardée par `tests/test_comparaison_dom.js` et
  `tests/test_inventaire_formulaire.js` (bijection des clés, groupe 7).

**Ce qui manque :**
- F1. Aucun dossier `clients/`. Aucun fichier du dépôt ne cite
  `clients/cabinet-01` hors `docs/ROADMAP.md` et des traces datées.
  `docs/schema-formulaire.md`, document vivant (D8), cite encore
  `clients/morlaix/` aux lignes 150, 221, 867 et 873.
- F2. `index-v1.html` ≠ `index.html` de `d43350a`. Trois différences, toutes
  lues par `diff` :
  (a) le style en ligne de `#btn-export` (`d43350a:formulaire/index.html:26`)
  est passé dans `style.css`, aux mêmes valeurs, par C1-T2 ;
  (b) `#barre-attente` a été ajoutée (`index-v1.html:40-46`, file d'attente,
  commit `ba1f5de`) ;
  (c) les quatre `<p>` d'identité de `#infos_podo`
  (`d43350a:formulaire/index.html:64-68`) ont été retirés par C2-T1. Leur
  texte est désormais injecté par `appliquerCabinet()` (`script.js:1000`)
  depuis `GET /cabinet`.
  Le corps de `#form-bilan` est inchangé, donc les champs aussi.
- F3. Les **clés de brouillon sont compatibles par lecture du code**, sans
  preuve mécanique :
  - même clé de stockage (`CLE_BROUILLON`, `d43350a:script.js:539` et
    `script.js:1172`) ;
  - même `cleChamp()` (`d43350a:549`, `script.js:1182`) ;
  - même format (`version: 1`, `script.js:1210`) ;
  - même jeu de champs (F2).
  Le blob `d43350a` est atteignable en CI : étiquette poussée
  (`git ls-remote` : `production-cabinet-01^{}` = `d43350a…`), et le job
  `test` clone en `fetch-depth: 0` (`.github/workflows/tests.yml:30`).
- F4. `outils/faire-paquet.sh` ne connaît pas de client. Il copie
  `formulaire/` tel quel (ligne 30) et vérifie la présence de
  `formulaire/schema.json` (lignes 68-77). Il est appelé sans argument par
  `tests/test_paquet.py:55`, par `tests/test_scripts_installation.py:276` et
  par `docs/essais/C3-T3a-windows.md:22`.
- F5. Le serveur ne sert **que** `formulaire/` (`serveur/serveur.py:56`),
  avec un filtre d'extensions (`serveur.py:195`). Un schéma qui vivrait dans
  `clients/` lui est inatteignable, et doit le rester.
- F6. Aucun consommateur de `theme.json` n'existe, et aucun n'est prévu à
  court terme :
  - C1-T3 l'a écarté, sur décision de Baptiste : le moteur ne charge que
    `schema.json` (`docs/contrats/C1-T3.md:155-162`) ;
  - C1-T2 a fait des cinq tokens de `:root` la source unique de la palette
    (`docs/contrats/C1-T2.md:365-400`).
- F7. Outillage de mesure en place (`outils/reference-visuelle/`) :
  - `produire.js` remplit un bilan en mode `v1`, mais seulement sur
    `/index-v1.html`, écrit en dur à la ligne 273 ;
  - `comparer-pdf.js` lit la structure ;
  - `comparer-pixels.js` rend son verdict à un **écart moyen < 3/255**
    (ligne 50), une tolérance. La lecture stricte (maximum 0) se fait ligne
    à ligne.
  Le décodage des pages passait jusqu'ici par un `extraire.js` **hors
  dépôt** (`CONSTAT-2026-11-04-C1-T6.md:132-137`).
- F8. Écarts d'exécution entre `d43350a` et `main`, lus dans le code. Ils
  forment la liste attendue que l'étape 7 confirme ou complète :
  - E1. Pied de page de version, hors PDF : `afficherVersion()`,
    `script.js:1032` (C4-T4).
  - E2. Bandeau « bilans en attente » et bouton « Réessayer maintenant » :
    `majBarreAttente()`, `script.js:703` (file d'attente, commit `ba1f5de`,
    documentée dans `docs/Mode_emploi.md:83-90`).
  - E3. En-tête du cabinet lu sur le PC. S'il manque : en-tête vide,
    bandeau d'avertissement et export refusé (`script.js:989-1025`, C2-T1).
  - E4. Message de repli du moteur et favori de secours (coquille
    `index.html`, `#attente-moteur`, C1-T3b).
  - E5. Nouveaux libellés après l'export : « Envoi au PC différé… »
    (`script.js:433-442`) au lieu de « Dépôt sur le PC impossible… »
    (`d43350a:script.js:219`).
  - E6. Un second appui sur « Générer le PDF » pendant un export est ignoré
    (`exportEnCours`, `script.js:283`, C2-T1).
  - E7. Nom du PDF inchangé par défaut (`GABARIT_NOMMAGE_DEFAUT`,
    `script.js:460`, C2-T1).
  - N1, invisible : la base IndexedDB passe en version 2
    (`VERSION_BASE`, `script.js:1403`), avec le magasin `file-depots`
    (`script.js:1401`).
- F9. **Conséquence de N1 pour le retour arrière de C1-T4b**, lue dans le
  code de `d43350a` :
  - après un passage par `main`, `indexedDB.open("bilan-posturo", 1)`
    (`d43350a:script.js:775`) échoue sur une base en version 2 ;
  - `dossierMemorise()` (`d43350a:835-847`) avale l'erreur et retombe sur
    le téléchargement : pas de blocage ;
  - en revanche, les bilans restés **dans la file** ne partent plus tant
    qu'on reste sur `d43350a`. Ils ne sont pas perdus pour autant :
    ils restent dans IndexedDB.

## 4. Périmètre

### Dans le périmètre
1. `clients/cabinet-01/schema.json`, copie octet pour octet de
   `formulaire/schema.json`, et `clients/LISEZMOI.md` (convention).
2. Une suite Node `tests/test_schema_client.js` : convention de nommage,
   validité de chaque schéma client, égalité des deux copies, et
   **compatibilité des clés de brouillon avec `production-cabinet-01`**.
3. `outils/faire-paquet.sh <client>` : argument obligatoire, schéma pris
   dans `clients/<client>/`, contrôle dans l'archive. Mise à jour des deux
   tests Python qui l'appellent.
4. Mesure en navigateur réel `d43350a` ↔ paquet `cabinet-01`, aux largeurs
   1 280 et 760 px : PDF, brouillon repris d'une version à l'autre, captures
   d'écran. Puis le constat
   `docs/references-visuelles/CONSTAT-2026-11-xx-C1-T4a.md`, qui porte la
   section « Ce que la praticienne verra changer ».
5. Deux ajouts d'outillage : `ESSAI_PAGE` honoré par `produire.js v1` (défaut
   inchangé), et `outils/reference-visuelle/empreintes-pages.js`.
6. La barrière CI promise à C1-T4 par le réaudit de C1-T3b
   (`docs/ROADMAP.md`, section C1-T3b) : aucun fichier autre que `.md` ou
   `.json` dans `docs/references-visuelles/`.
7. Les documents vivants : `docs/schema-formulaire.md` (`morlaix` →
   `cabinet-01`), `README.md` (arborescence et usage du paquet),
   `docs/essais/C3-T3a-windows.md:22` (commande du paquet),
   `docs/references-visuelles/LISEZMOI.md` §4, et `docs/ROADMAP.md` (état de
   C1-T4a, renvoi au constat depuis C1-T4b, amendement du périmètre
   `theme.json`).

### Hors périmètre
- **Toute livraison, toute action au cabinet**, ainsi que le favori de secours
  et la semaine de bilans : C1-T4b.
- **`docs/production/cabinet-01.md`** : cette fiche ne se met à jour qu'à une
  installation (sa propre règle, ligne 4). Le constat de C1-T4a en sera la
  pièce jointe, sans y être recopié.
- **`theme.json`** et le logo : aucun consommateur (F6). Voir D3 ; C2-T2 pour
  le logo.
- Supprimer `index-v1.html` ou tout HTML écrit à la main : C1-T4b.
- Renommer une clé de brouillon, même mal orthographiée (`familliaux`…).
- Corriger un écart dont la cause est dans `script.js` ou `style.css`
  (règle D6).
- Créer le dossier d'un autre client, en particulier celui du prospect, dont la
  fiche est confidentielle et hors dépôt.
- Nommer l'archive d'après le client, identifier le client dans `/etat` ou
  `technique.log`, distribuer le schéma par les mises à jour (C5).
- Éprouver la file d'attente panne comprise sur la tablette : C7-T3.
- La bibliothèque de blocs : C1-T5.

## 5. Fichiers touchés

| Fichier | Nature | Remarque |
|---|---|---|
| `clients/cabinet-01/schema.json` | création | `cp formulaire/schema.json`, jamais réécrit à la main |
| `clients/LISEZMOI.md` | création | convention D8, règle du miroir, ce qui n'y entre jamais |
| `tests/test_schema_client.js` | création | quatre groupes, §6 étape 2 |
| `tests/outils/analyseur-html.js` | création | mini-analyseur **extrait** de `tests/test_comparaison_dom.js:55-149`, sans copie |
| `tests/test_comparaison_dom.js` | modification | importe l'analyseur extrait ; sorties inchangées |
| `outils/faire-paquet.sh` | modification | argument `<client>`, copie, contrôle |
| `tests/test_paquet.py` | modification | copie `clients/`, passe `cabinet-01`, quatre nouveaux cas |
| `tests/test_scripts_installation.py` | modification | ligne 276 : `cabinet-01` |
| `outils/reference-visuelle/produire.js` | modification | `ESSAI_PAGE` en mode `v1`, défaut `index-v1.html` |
| `outils/reference-visuelle/empreintes-pages.js` | création | SHA-256 de chaque flux `/DCTDecode`, comparaison stricte |
| `.github/workflows/tests.yml` | modification | pas Node `test_schema_client.js` ; avertissement l. 118-131 → barrière |
| `package.json` | modification | `npm test` : treizième suite |
| `docs/references-visuelles/CONSTAT-2026-11-xx-C1-T4a.md` | création | mesures et liste des changements |
| `docs/references-visuelles/LISEZMOI.md` | modification | §4 : images et PDF jamais versionnés |
| `docs/schema-formulaire.md` | modification | quatre `clients/morlaix/` |
| `README.md` | modification | `clients/` dans l'arborescence ; `faire-paquet.sh cabinet-01` |
| `docs/essais/C3-T3a-windows.md` | modification | ligne 22 seulement |
| `docs/ROADMAP.md` | modification | état C1-T4a, renvoi depuis C1-T4b, périmètre `theme.json` |
| `docs/audits/C1-T4a-mises-en-echec.md` | création | journal des mutations (précédents : C1-T3, C1-T6) |

**Ne sont pas touchés :**
- `formulaire/` en entier (`script.js`, `style.css`, `index.html`,
  `index-v1.html`, `moteur/rendu.js`, `schema.json`), sauf l'exception de D6 ;
- `serveur/` ;
- `docs/production/cabinet-01.md` ;
- la branche `maintenance-cabinet-01` et l'étiquette.

## 6. Plan d'implémentation

**Étape 0 — Préalables.**
- Sur `c1-t4a-schema-cabinet`, `git status` propre, puis
  `python3 -m unittest discover -s tests` : 314 tests, 2 sautés. Lancer
  `npm test` en arrière-plan : 12 suites vertes.
- Relever **l'empreinte de métadonnées** des fichiers réels de la racine, sans
  les ouvrir :
  `git status --ignored --porcelain | sed -n 's/^!! //p'` donne les noms,
  puis `stat -f '%m %z %N'` sur chacun. Le relevé est écrit hors dépôt.
  Il se compare en fin de tâche (critère 15).
- *Bonne si* les deux suites sont vertes et le relevé existe.

**Étape 1 — Le dossier client.**
- `mkdir -p clients/cabinet-01 && cp formulaire/schema.json clients/cabinet-01/schema.json`.
- `clients/LISEZMOI.md`, une page au plus :
  - un dossier par client, nommé `cabinet-NN` (D8), jamais d'après une ville ;
  - aucun fichier d'identité ni de configuration (l'identité vit dans
    `config.json`, au cabinet) ;
  - `formulaire/schema.json` est le miroir de `clients/cabinet-01/schema.json`,
    gardé égal par le test ; toute modification se fait **dans les deux**,
    puis `node tests/test_schema_client.js` ;
  - le paquet se fabrique par `sh outils/faire-paquet.sh <client>` ;
  - le dépôt est public : le schéma d'un client y est publié (§12).
- *Bonne si* `cmp formulaire/schema.json clients/cabinet-01/schema.json` sort
  en 0.

**Étape 2 — `tests/test_schema_client.js`.** Bibliothèque standard de Node,
format `cas()` comme `tests/test_grille.js:150`, code de sortie non nul au
premier échec.
- D'abord, **extraire** le mini-analyseur HTML de
  `tests/test_comparaison_dom.js` (`analyserAttributs`, `analyserHtml`,
  `extraireElement`, l. 55-149) dans `tests/outils/analyseur-html.js`, et
  l'importer depuis les deux tests. Contrôle : `node tests/test_comparaison_dom.js`
  produit la même sortie qu'avant, à l'octet près. On compare par un `diff`
  des sorties, enregistrées hors dépôt avant et après.
- **G1 — Dossiers.**
  - `clients/` existe et contient au moins un dossier (sinon échec : un test
    vert à vide ne garde rien) ;
  - chaque sous-dossier correspond à `^cabinet-[0-9]{2,}$` et contient
    `schema.json`.
  - Les noms se lisent par `fs.readdirSync`, jamais dans une liste écrite.
- **G2 — Validité.** Chaque `clients/*/schema.json` est accepté par
  `validerSchema()` (`rendu.js:252`), le moteur étant chargé en `vm` comme
  dans `tests/test_comparaison_dom.js:546`.
- **G3 — Miroir.** `formulaire/schema.json` et
  `clients/cabinet-01/schema.json` sont égaux **octet pour octet**
  (`Buffer.equals`, sans normalisation ; `.gitattributes` fige `*.json` en LF).
- **G4 — Brouillon de production.**
  - Lire `production-cabinet-01:formulaire/index.html` par
    `execFileSync("git", ["cat-file", "-p", …])`, sans shell. Si l'étiquette
    est absente, échouer avec un message qui donne le remède
    (`git fetch --tags`), et **ne jamais sauter**.
  - Côté production : construire `#form-bilan` dans `tests/outils/dom-minimal.js`
    par l'analyseur extrait.
  - Côté moteur : prendre l'en-tête de la coquille `formulaire/index.html` et
    le rendu de `clients/cabinet-01/schema.json` par `rendre()` (`rendu.js:863`).
  - Sur chaque `input`, `textarea` et `select`, pris dans l'ordre du document,
    appliquer la **vraie** `cleChamp()` de `formulaire/script.js`, chargée en
    `vm` (patron de `tests/test_nommage.js:30-73`). Elle n'est jamais
    réécrite dans le test.
  - Exiger l'égalité des deux ensembles de clés, dans les deux sens, et
    l'égalité de la **liste ordonnée** des `src` des images annotables.
    Les traits sont indexés par position (`script.js`, `restaurerBilan`).
  - Exiger que la valeur de `CLE_BROUILLON` soit la même dans les deux
    `script.js` (blob et arbre). La lire par un motif ancré
    `^const CLE_BROUILLON = "([^"]+)";$` (drapeau `m`), présent **une seule
    fois** dans chaque fichier.
  - En cas d'échec, ne citer **que des clés**, jamais un texte du blob : il
    porte l'identité réelle, et le journal de CI est public.
- *Bonne si* `node tests/test_schema_client.js` sort en 0 et que chaque garde
  rougit sous sa mutation (étape 9).

**Étape 3 — `outils/faire-paquet.sh <client>`.**
- Avant toute copie :
  - un seul argument, sinon code 2 et un message en français qui liste les
    clients disponibles, dérivés de `clients/*/schema.json` ;
  - l'argument doit correspondre à `^cabinet-[0-9]{2,}$` (sinon code 2) :
    aucun `/`, aucun `..` ;
  - `clients/$CLIENT/schema.json` doit exister.
- Après `cp -R formulaire serveur` (ligne 30) :
  `cp "clients/$CLIENT/schema.json" "$PAQUET/formulaire/schema.json"`.
- Après le zip, dans la boucle des obligatoires ou juste après :
  `unzip -p "$PAQUET.zip" "$PAQUET/formulaire/schema.json" | cmp -s - "clients/$CLIENT/schema.json"`.
  En cas d'échec, effacer l'archive et sortir en 1.
- Le message final nomme le client.
- Le nom de l'archive ne change pas (D5).
- *Bonne si* les commandes du critère 6 donnent les résultats annoncés.

**Étape 4 — Tests Python du paquet.**
- `tests/test_paquet.py` :
  - ajouter `"clients"` à la liste copiée (l. 45) et passer `cabinet-01` ;
  - nouveaux cas, chacun dans sa propre copie temporaire :
    - sans argument : code ≠ 0 et aucune archive ;
    - `../formulaire` : refusé ;
    - `cabinet-99` (inexistant) : refusé ;
    - avec `cabinet-01` : `formulaire/schema.json` de l'archive égal en octets
      à `clients/cabinet-01/schema.json`, et **aucune entrée** de l'archive
      ne contient `/clients/`.
- `tests/test_scripts_installation.py:276` : ajouter `"cabinet-01"`. Sa copie
  par `git ls-files -z` emporte déjà `clients/`, une fois le dossier indexé.
- Aucune `assert` nue : les méthodes `self.assert*` uniquement.
- *Bonne si* `python3 -m unittest tests.test_paquet tests.test_scripts_installation`
  est vert, puis sous `python3 -O`, joué au premier plan.

**Étape 5 — Intégration continue.**
- Ajouter le pas « Run client schema tests »
  (`node tests/test_schema_client.js`) au job `test`, et la même suite à la
  fin de `npm test` dans `package.json`.
- Remplacer l'avertissement des lignes 118-131 par une **erreur** :
  - tout fichier suivi sous `docs/references-visuelles/` dont l'extension
    n'est ni `.md` ni `.json` fait échouer le pas ;
  - la liste se lit par `git -c core.quotePath=false ls-files -z`, et un
    code de `grep` supérieur à 1 se traite comme une erreur, sur le patron du
    pas « palette ».
- *Bonne si* le pas passe sur l'arbre actuel et échoue dans un clone jetable
  où l'on a indexé un `.png` (étape 9, M7).

**Étape 6 — Outillage de mesure.**
- `produire.js`, mode `v1` : remplacer `"/index-v1.html"` (l. 273) par
  `"/" + (process.env.ESSAI_PAGE || "index-v1.html")`, et mettre à jour
  l'en-tête. Le mode `moteur` est inchangé ; sans variable, le comportement
  aussi.
- `empreintes-pages.js` :
  - avec un PDF : une ligne par flux `/DCTDecode`, sous la forme
    `page N  <sha256>  <octets>` ;
  - avec deux PDF : même nombre de pages exigé et même empreinte page à page.
    Sortie 0 si tout est égal, 1 sinon, en nommant les pages qui diffèrent ;
  - **aucun seuil**, aucune dépendance.
- *Bonne si*, avec deux PDF :
  - `V1-reference.pdf` contre lui-même rend 0 ;
  - un PDF contre un second export du même brouillon (mesure du
    déterminisme) rend 0 ;
  - un témoin négatif (même bilan, un trait de plus) rend 1.

**Étape 7 — La mesure.** Tout se fait **hors du dépôt**, dans un dossier de
travail que l'on supprime à la fin. On ne lance jamais `serveur.py` ni
`generer_autorite.py` depuis le dépôt.

1. *Identité fictive.* Écrire hors dépôt un seul fichier JSON `cabinet`, avec
   `praticien`, `adresse`, `courriel` en `.invalid` et `telephone` hors du
   motif `0[1-9]…`. C'est la source unique des deux côtés. Elle n'est
   recopiée dans aucun fichier suivi.
2. *Côté P (production).*
   - Extraire le formulaire sans la page :
     `git archive production-cabinet-01 -- formulaire ':(exclude)formulaire/index.html' | tar -x -C <bacP>`
     (vérifié : la syntaxe d'exclusion fonctionne avec git 2.39).
   - Écrire `<bacP>/formulaire/index.html` à partir de
     `git show production-cabinet-01:formulaire/index.html`, après avoir
     remplacé, dans l'ordre, le texte des quatre `<p>` de `#infos_podo` par
     `praticien`, `adresse`, `"mail: " + courriel` et `"tel: " + telephone`
     (même forme que `appliquerCabinet()`, `script.js:1000-1025`). L'identité
     réelle n'est **jamais écrite sur disque**.
   - Contrôle sans affichage :
     `diff <(git show production-cabinet-01:formulaire/index.html) <bacP>/formulaire/index.html | head -1`
     doit rendre `65,68c65,68`, et rien d'autre ne doit différer.
   - Servir par `python3 -m http.server <portP> --bind 127.0.0.1 --directory <bacP>/formulaire`.
     Ce n'est pas `serveur.py` : le dépôt de `d43350a` y échoue aussitôt, et le
     PDF tombe en téléchargement (`d43350a:script.js:208-209`).
3. *Côté M (livrable).*
   - Copier le dépôt par `git ls-files -z` dans `<copie>` (patron de
     `tests/test_scripts_installation.py:245-268`), puis
     `sh outils/faire-paquet.sh cabinet-01` dans `<copie>`.
   - Dézipper dans `<bacM>`, puis, **dans `<bacM>`** :
     `python3 serveur/generer_autorite.py 127.0.0.1`.
   - Écrire `config.json` sur le patron de
     `tests/test_integration.py:118-160`, avec le bloc `cabinet` du point 1 et
     sans `convention_nommage`.
   - Lancer `serveur.py` depuis `<bacM>`, en lisant sa sortie : un tube non
     lu fige le serveur (`CLAUDE.md`).
4. *Pour chaque largeur L ∈ {1280, 760},* avec des dossiers de sortie
   distincts. `cdp.js` refuse un port occupé : en choisir un libre.
   - (a) Remplir sur P :
     `ESSAI_BASE=http://127.0.0.1:<portP> ESSAI_PAGE=index.html ESSAI_LARGEUR=L ESSAI_SORTIE=<sortie>/P-L node outils/reference-visuelle/produire.js v1`.
     Cela produit le PDF de P, ses deux captures et **le brouillon écrit par
     `d43350a`**.
   - (b) Copier ce brouillon dans `<sortie>/M-L/bilan-reference.json`, puis
     le reprendre sur le moteur :
     `ESSAI_BASE=https://127.0.0.1:<portM> ESSAI_IDENTIFIANTS=… ESSAI_PAGE=index.html ESSAI_PREFIXE=M-moteur ESSAI_LARGEUR=L ESSAI_SORTIE=<sortie>/M-L node outils/reference-visuelle/produire.js moteur`.
   - (c) Même chose sur la fiche de secours servie par M :
     `ESSAI_PAGE=index-v1.html ESSAI_PREFIXE=M-secours`.
   - (d) Comparer P ↔ M-moteur et M-secours ↔ M-moteur, d'abord par
     `comparer-pdf.js` (structure), puis par `empreintes-pages.js`.
     Si une empreinte diffère : extraction et vignettes
     (`CONSTAT-2026-11-04-C1-T6.md:132-134`), lecture de `comparer-pixels.js`
     page par page (le **maximum**, pas le verdict), puis l'œil.
   - (e) Relever le nom d'origine des deux PDF (ligne `nom produit par le
     formulaire` de `produire.js`, et `nomOrigine`) et le rapport
     `restauration :` de M.
   - (f) Comparer les captures P ↔ M-moteur, à l'œil et par paire, en
     notant chaque différence visible.
5. Arrêter les serveurs, puis supprimer `<bacP>`, `<bacM>` et `<copie>`. Les
   PDF et captures restent hors dépôt (D4) : ils peuvent montrer l'identité
   fictive et le logo du cabinet.
- *Bonne si* chaque commande a rendu, et que tout écart d'empreinte est
  localisé (page, zone) avant d'écrire le constat.

**Étape 8 — Le constat.**
`docs/references-visuelles/CONSTAT-2026-11-xx-C1-T4a.md` contient :
- le **montage**, avec les versions de Chrome, Node et Python ;
- un tableau par largeur : pages, `comparer-pdf.js`, `empreintes-pages.js`,
  noms d'origine, rapport de restauration ;
- le résultat M-secours ↔ M-moteur ;
- la section **« Ce que la praticienne verra changer »**, un tableau dont les
  colonnes sont : écart, où (écran / PDF / comportement / invisible), source
  (*mesuré* ou *lu dans le code*, avec `fichier:ligne`), document qui
  l'établit voulu (chemin). On part de E1-E7 et N1 (F8), qu'on complète de
  tout écart mesuré, et l'on y ajoute F9 comme **consigne pour le retour
  arrière de C1-T4b** : écouler la file avant de revenir à `d43350a` ;
- la section « Ce que ce constat ne couvre pas » : la tablette réelle, Safari,
  la panne de dépôt sur IndexedDB réel (C7-T3).

Il n'y figure ni courriel, ni téléphone, ni coordonnée réelle ou fictive, et
aucune image. Le constat peut **citer** des noms et des clés.
Enfin, dans `docs/ROADMAP.md`, ajouter sous C1-T4b un renvoi vers ce constat,
et y lister comme **décision bloquante** chaque écart sans document (D6).
- *Bonne si* `python3 -m unittest tests.test_identite_absente` reste vert.

**Étape 9 — Mutations, consignées dans `docs/audits/C1-T4a-mises-en-echec.md`.**
- Chaque mutation se fait sur une copie `git ls-files -z --cached --others
  --exclude-standard`, ou dans un clone jetable **sans `origin`**.
- Chacune est jouée avec un témoin, c'est-à-dire la même commande sur l'arbre
  sain, et l'on note le code de sortie **du test lui-même**.
- Les mutations à jouer sont listées au §9.

**Étape 10 — Documents, puis tout le filet.**
- Documents : §4, point 7.
- Filet :
  - `python3 -m unittest discover -s tests` puis `python3 -O -m unittest discover -s tests`, au
    premier plan ;
  - `npm test` en arrière-plan ;
  - pousser la branche, puis
    `env -u GITHUB_TOKEN gh workflow run tests.yml --ref c1-t4a-schema-cabinet`,
    et attendre 7 jobs sur 7 verts (5 combinaisons du job `test`, `lint`, `scripts-windows`).

## 7. Décisions de conception

**Tranchées par ce contrat :**

- **D1 — Le schéma du client fait foi ; `formulaire/schema.json` en est le
  miroir gardé.** Il reste en place parce que :
  - le serveur ne peut servir que `formulaire/` (F5) ;
  - six suites de tests, le bac à sable `demarrer_sandbox_court` et la fiche
    de secours le lisent à cet endroit.
  Le supprimer ou le générer casserait tout cela pour un gain nul tant qu'un
  seul client existe. La duplication est tenue par G3, à l'octet.
- **D2 — Le client se choisit à la fabrication du paquet, jamais au serveur.**
  Une route ou un chemin vers `clients/` élargirait la racine web,
  contrainte permanente. L'argument est **obligatoire**, sans défaut, pour ne
  jamais livrer par mégarde le formulaire de `cabinet-01` à un autre cabinet.
- **D3 — Pas de `theme.json` dans cette tâche,** malgré le périmètre de
  C1-T4 dans la feuille de route. Raisons :
  - aucun code ne le lirait (F6, décision de Baptiste consignée à C1-T3) ;
  - il recopierait les cinq tokens de `:root`, source unique depuis C1-T2 :
    une seconde source de palette, c'est exactement le défaut que C1-T2
    a fermé.
  Il naîtra avec son premier consommateur (thème d'un deuxième cabinet, ou
  C2-T2 pour le logo). L'amendement est écrit dans `docs/ROADMAP.md`.
- **D4 — Les images et PDF de mesure ne sont jamais versionnés.** C'est la
  décision que le réaudit de C1-T3b renvoyait à C1-T4. Trois précédents
  (19 octobre, C2-T1, C1-T6) les ont gardés hors dépôt. Une image échappe à
  `tests/test_identite_absente.py`, et une donnée publiée ne se reprend pas.
  La barrière CI (étape 5) remplace un avertissement que personne ne lisait.
- **D5 — Le nom de l'archive ne change pas** (`BilanPosturo-AAAA-MM-JJ`).
  `docs/essais/C3-T3a-windows.md:174` lit ce motif, et la question du nommage
  par client appartient au premier paquet d'un autre client.
- **D6 — Référence du « identique au pixel » : `d43350a`, à titre principal.**
  `index-v1.html` reste référence de non-régression (M-secours ↔ M-moteur).
  Règle de traitement d'un écart P ↔ M :
  - **cause dans le moteur ou le schéma** : corrigé dans C1-T4a. La
    correction porte alors aussi sur `formulaire/schema.json`, puisque G3
    l'exige, et la preuve du 19 octobre est rejouée ;
  - **cause dans `script.js` ou `style.css`** et caractère voulu établi par un
    document du dépôt : consigné, rien à faire ;
  - **cause dans `script.js` ou `style.css`** sans document : consigné, **non
    corrigé ici** (toucher `script.js`, c'est toucher la fiche de secours),
    et inscrit comme **décision bloquante de C1-T4b** dans `docs/ROADMAP.md`.
    C1-T4a peut se clore.
- **D7 — Le brouillon de `d43350a` doit se reprendre sur la version livrée.**
  Tranché, parce que le code le permet déjà (F3) : la tâche le rend
  **mécanique** (G4) et le **mesure** (étape 7, b). Toute clé qui divergerait
  est un défaut bloquant pour C1-T4a lui-même, pas un écart à consigner.
- **D8 — Identité fictive, la même des deux côtés.** La mesure porte sur la
  différence de code, et le texte de l'en-tête en est une variable. Prendre
  l'identité réelle forcerait à la manipuler hors du cabinet, sans rien
  apporter de plus.

**Laissés à l'implémenteur :**
- la structure interne de `test_schema_client.js` et le libellé de ses cas ;
- le texte de `clients/LISEZMOI.md` ;
- les ports et les noms des dossiers de travail ;
- le format exact de sortie d'`empreintes-pages.js` ;
- la date du nom du constat.

## 8. Critères d'acceptation

1. [ ] `cmp formulaire/schema.json clients/cabinet-01/schema.json` sort en 0.
2. [ ] `git ls-files clients` rend exactement `clients/LISEZMOI.md` et
   `clients/cabinet-01/schema.json`.
3. [ ] `node tests/test_schema_client.js` sort en 0, et sa sortie nomme les
   quatre groupes G1 à G4.
4. [ ] La sortie de `node tests/test_comparaison_dom.js` est identique à
   l'octet avant et après l'extraction de l'analyseur
   (`diff avant.txt apres.txt` vide).
5. [ ] Chaque mutation M1 à M8 du §9 est consignée dans
   `docs/audits/C1-T4a-mises-en-echec.md`, avec son témoin. Le test visé y
   rend un code ≠ 0, et 0 sur l'arbre sain.
6. [ ] Dans une copie par `git ls-files -z` :
   - `sh outils/faire-paquet.sh` → code ≠ 0, aucun `BilanPosturo-*.zip` ;
   - `sh outils/faire-paquet.sh ../formulaire` → code ≠ 0 ;
   - `sh outils/faire-paquet.sh cabinet-01` → code 0 ;
   - puis `unzip -p BilanPosturo-*.zip '*/formulaire/schema.json' | cmp - clients/cabinet-01/schema.json`
     → 0, et `unzip -l BilanPosturo-*.zip | grep -c '/clients/'` → `0`.
7. [ ] `python3 -m unittest discover -s tests` : 0 échec, au moins 318 tests
   (314 + 4 nouveaux) ; idem sous `python3 -O`, joué au premier plan.
8. [ ] `npm test` vert, 13 suites ; `grep -c "test_schema_client.js"
   package.json .github/workflows/tests.yml` rend 1 pour chacun.
9. [ ] CI sur `c1-t4a-schema-cabinet` (`gh workflow run`) : 7 jobs sur 7 verts
   (5 combinaisons du job `test`, `lint`, `scripts-windows`) (lien du run dans le constat ou l'audit).
10. [ ] Le constat existe, et pour **chaque** largeur (1 280 et 760 px) il
    donne :
    - le nombre de pages de P et de M-moteur, égal ;
    - `comparer-pdf.js` P ↔ M-moteur : code 0 ;
    - `empreintes-pages.js` P ↔ M-moteur : code 0, **ou** chaque page
      différente localisée et traitée selon D6 ;
    - le même nom d'origine pour les deux PDF ;
    - un rapport de restauration M avec `"restaure":"cliqué"`,
      `"nom":"Témoin"`, `"tableau":true` et `"traits":4`.
11. [ ] `empreintes-pages.js` M-secours ↔ M-moteur à 1 280 px : code 0.
12. [ ] La section « Ce que la praticienne verra changer » compte au moins
    les huit entrées E1 à E7 et N1, plus la consigne F9. Chaque ligne porte
    une source et soit un chemin de document, soit la mention « décision
    bloquante C1-T4b » ; dans ce dernier cas, l'écart figure sous C1-T4b dans
    `docs/ROADMAP.md`.
13. [ ] `git ls-files -z docs/references-visuelles | tr '\0' '\n' | grep -vE '\.(md|json)$'`
    ne rend rien, et le pas CI correspondant échoue dans un clone où un
    `.png` est indexé (M7).
14. [ ] `python3 -m unittest tests.test_identite_absente` vert, constat et
    `clients/LISEZMOI.md` compris.
15. [ ] Le relevé `stat` des fichiers réels de la racine est identique avant
    et après (`diff` vide).
16. [ ] `git diff main --stat -- formulaire/ serveur/ docs/production/` ne
    liste rien (exception D6 : seuls `formulaire/schema.json` et
    `formulaire/moteur/rendu.js`, avec la preuve rejouée).
    `git rev-parse production-cabinet-01^{commit} maintenance-cabinet-01`
    rend deux fois `d43350a0cf20fef5672eadc7bcb6f67e156dc977`.
17. [ ] `git grep -c "clients/morlaix" -- docs/schema-formulaire.md README.md`
    ne rend rien. `docs/essais/C3-T3a-windows.md` donne
    `sh outils/faire-paquet.sh cabinet-01`.
18. [ ] `docs/ROADMAP.md` : C1-T4a marquée livrée, C1-T4b renvoie au
    constat, et le périmètre `theme.json` est amendé (D3).

## 9. Tests à écrire

| Test | Fichier | Ce qu'il doit échouer à faire passer aujourd'hui |
|---|---|---|
| G1 dossiers clients | `tests/test_schema_client.js` | Aujourd'hui, `clients/` est absent : échec. M1 : renommer `cabinet-01` en un nom de ville, dans une copie → échec. |
| G2 validité | idem | M2 : un `type` inconnu dans `clients/cabinet-01/schema.json` → échec (aussi par G3). |
| G3 miroir | idem | M3 : un octet changé (une espace) dans l'une des deux copies seulement → échec. |
| G4 clés de production | idem | M4 : renommer une `cle` (ex. `familliaux`) **dans les deux** copies → échec, G3 restant vert. M5 : étiquette absente (clone jetable sans étiquettes) → échec bruyant, pas de saut. M6 : permuter deux `image-annotable` dans les deux copies → échec. |
| refus sans argument, chemin, inconnu | `tests/test_paquet.py` | Aujourd'hui le script réussit sans argument : échec. |
| schéma du paquet = schéma client, aucun `clients/` | `tests/test_paquet.py` | M8 : commenter la ligne `cp clients/…` en remplaçant le schéma client par un autre (copie modifiée de `formulaire/schema.json`) → échec. |
| barrière d'images | `.github/workflows/tests.yml` (pas joué à la main) | M7 : indexer `docs/references-visuelles/x.png` dans un clone jetable → le pas sort ≠ 0 (aujourd'hui : simple avertissement). |
| `empreintes-pages.js` | outil, éprouvé à l'étape 6 | Témoin négatif : un trait de plus rend 1. |

## 10. Points de sécurité à l'attention de l'auditeur

- **Identité réelle dans l'historique** : le blob
  `production-cabinet-01:formulaire/index.html` la porte. G4 le lit, mais ne
  doit jamais l'afficher, même en échec (CI publique).
- **Identité pendant la mesure** : la substitution a lieu avant toute
  écriture, et l'exclusion de `git archive` garantit qu'aucune copie réelle
  ne touche le disque.
- **Artefacts de mesure** : images et PDF restent hors dépôt (D4). Une
  barrière CI le garantit désormais, et `test_identite_absente` couvre le
  texte du constat.
- **Fichiers réels du cabinet** à la racine : ni lus, ni copiés. Les bacs se
  font par `git archive` (objets commités) et `git ls-files -z`, et le relevé
  `stat` de métadonnées le prouve (critère 15).
- **Exécution du serveur** : uniquement dans `<bacM>`, issu du paquet,
  jamais dans le dépôt. Les certificats sont produits dans le bac.
- **Argument du script de paquet** : il entre dans un chemin. Le motif ancré
  `^cabinet-[0-9]{2,}$` interdit la remontée de répertoire.
- **Fuite entre clients** : une archive ne doit contenir aucune entrée
  `clients/`, sans quoi le schéma d'un client partirait chez un autre
  (critère 6).
- **Surface exposée** : inchangée. `/schema.json` reste servi sous
  authentification (`tests/test_integration.py:505-512`), et la racine web
  ne bouge pas.
- **Données de santé** : aucune. Le bilan témoin est fictif
  (`produire.js`, « Témoin Référence »).
- **Dépôt public** : `clients/cabinet-01/schema.json` publie une structure de
  formulaire déjà publique (`formulaire/schema.json`), sans rien de plus.

## 11. Retour arrière

Au cabinet : **rien à défaire**. Rien n'y est livré, et ni la branche
`maintenance-cabinet-01` ni l'étiquette ne bougent. La praticienne ne voit
aucune différence.

Dans le dépôt, en moins de cinq minutes :
- tant que la branche n'est pas fusionnée, ne pas la fusionner ;
- après fusion, `git revert -m 1 <commit de fusion>` sur `main`, puis
  `python3 -m unittest discover -s tests`. Le revert remet
  `faire-paquet.sh` sans argument : les docs et les tests reviennent avec lui.

Le seul effet hors dépôt est la suppression des bacs de mesure, déjà prévue
par l'étape 7.5.

## 12. Risques

| Risque | Probabilité | Conséquence | Parade |
|---|---|---|---|
| La mesure révèle un écart P ↔ M venu de `script.js` ou `style.css` | moyenne | C1-T4b ne peut pas livrer en l'état | D6 : consigné, inscrit comme bloquant pour C1-T4b ; C1-T4a se clôt sur un constat honnête |
| L'identité réelle passe dans un journal de CI ou un fichier versionné | faible | publication irréversible | G4 ne cite que des clés ; substitution avant écriture ; barrière D4 ; `test_identite_absente` |
| Le miroir est corrigé d'un seul côté par un futur agent | moyenne | le paquet et le développement divergent | G3 rougit immédiatement ; règle écrite dans `clients/LISEZMOI.md` |
| L'étiquette `production-cabinet-01` manque en CI ou dans un clone local | faible | G4 rouge | échec bruyant avec le remède `git fetch --tags`, jamais un saut silencieux (piège C1-T6b) |
| Un appel ancien sans argument (`docs/essais/C3-T3a-windows.md`, habitude) | moyenne | paquet refusé | refus clair, qui liste les clients ; fiche C3-T3a mise à jour |
| L'extraction de l'analyseur modifie `test_comparaison_dom.js` | faible | garde affaiblie sans bruit | critère 4 : sortie identique à l'octet |
| Tolérance réintroduite pour faire passer la comparaison (verdict `< 3` de `comparer-pixels.js`) | moyenne | un écart réel déclaré « bruit » | `empreintes-pages.js` sans seuil fait foi ; `comparer-pixels.js` ne sert qu'au diagnostic, par son maximum |
| Le serveur de test du bac se fige (tube non lu) | faible | mesure bloquée, cause invisible | lire la sortie dans un fil, comme `demarrer_sandbox_court` |
| Retour arrière de C1-T4b vers `d43350a` avec des bilans en file | moyenne (plus tard) | bilans bloqués sur la tablette | F9 consigné dans le constat : écouler la file avant tout retour |
| Le schéma d'un futur client publié dans un dépôt public | certaine au deuxième client | structure de formulaire concurrente visible | hors périmètre ; à trancher avant de créer `cabinet-02` (C9) ; le dossier du prospect n'est pas créé ici |
