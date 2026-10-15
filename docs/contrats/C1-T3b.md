# Contrat C1-T3b — Basculer le formulaire de production sur le moteur

**Chantier :** C1  **Effort estimé :** M  **Date :** 2026-10-15
**Décisions bloquantes :** **deux, bloquantes avant la première modification de
fichier** — (1) le jeu de référence visuelle de la V1 n'existe pas ; (2) le
nombre de pages du PDF de référence n'est pas renseigné (section 6, étape 0).
Tant que les deux ne sont pas levées, **aucune étape de ce contrat ne commence**.

---

## 1. Objectif

Après cette tâche, `formulaire/index.html` — le fichier que la tablette ouvre
chaque matin — n'est plus le formulaire écrit à la main : c'est une coquille
(en-tête du cabinet en dur, barre d'outils, `<div id="form-bilan" data-moteur>`
contenant un `<main>` vide), et les 28 blocs du corps du bilan sont rendus au
chargement par `formulaire/moteur/rendu.js` à partir de
`formulaire/schema.json`. La V1 survit en un seul exemplaire gelé,
`formulaire/index-v1.html`, servi à la même adresse, qui est le repli de
consultation.

Avant : le moteur n'était atteignable que par une page provisoire
(`formulaire/index-moteur.html`) explicitement retirée du paquet livré au
cabinet — la production restait la V1. Après : la production **est** le moteur,
`index-moteur.html` n'existe plus, et le paquet emporte `moteur/`,
`schema.json` et `index-v1.html`.

C'est le point de non-retour du chantier C1 : à partir de là, aucun PDF de la V1
ne peut plus être fabriqué.

## 2. Pourquoi

C1 existe pour lever le verrou n°2 de `docs/projection.md` (§5, « Le piège du
template unique ») : un HTML par cabinet rend impossible la propagation du
premier correctif de pagination. Les étapes 1 à 8 de C1-T3 ont construit le
moteur, mais elles n'ont rien changé pour personne : tant que `index.html` reste
la V1, le dépôt porte **deux** implémentations du même formulaire, et la seconde
n'est validée que par comparaison de DOM. C'est exactement l'état que C1 doit
supprimer, et le coût de sa prolongation est double — deux fichiers à maintenir,
et un moteur dont personne ne sait s'il tient en vraie consultation.

L'autre face est le risque : la praticienne de Morlaix fait **la totalité** de
ses bilans avec cet outil, tous les matins. Une régression de rendu ne se
découvre pas en test, elle se découvre un mardi matin avec un patient assis en
face. D'où la forme de ce contrat : un préalable irréversible (section 6, étape
0), un repli que la praticienne exécute seule en moins d'une minute et qui est
**éprouvé avant** la bascule (section 11), et un commit unique pour que
l'annulation soit un geste et non une reconstruction.

## 3. État actuel

Faits vérifiés le 15 octobre 2026.

**Le dépôt n'est pas dans l'état habituel.** Branche
`c1-t3-moteur-rendu-schema`, `HEAD` = `90ac62d`. Les étapes 1 à 8 de C1-T3 sont
livrées, auditées **CONFORME** (`docs/audits/C1-T3.md`) et revues **À LIVRER**
(`docs/revues/C1-T3.md`), mais **non commitées** : elles vivent dans l'arbre de
travail (11 fichiers modifiés, 8 chemins non suivis, `git status`). Cette tâche
se greffe donc sur un travail non fusionné : elle commence par le geler dans un
commit (étape 1), faute de quoi le retour arrière de niveau 3 n'a rien à
annuler.

**Le formulaire de production**

- `formulaire/index.html` : 388 lignes, SHA-256
  `589eee333e68bdbde9e46c1343392e767baa5cfa6b1abfee02026d9431958a6e`
  (`shasum -a 256`, vérifié à l'instant). C'est la V1, intacte octet pour octet
  depuis le début de C1-T3. C'est elle qui sert les consultations aujourd'hui.
- `formulaire/index.html:26` : `<button id="btn-export" onclick="exporterBilanPDF()">`.
  La V1 câble l'export par attribut HTML.
- `formulaire/script.js:788-826` : `demarrerApplication()` (idempotente) et le
  gestionnaire `DOMContentLoaded` qui ne l'appelle **que si** `#form-bilan` ne
  porte pas `data-moteur`. `script.js:800-801` : l'écouteur `click` sur
  `#btn-export` n'est posé **que** sous `data-moteur` — précisément pour ne pas
  déclencher `exporterBilanPDF()` deux fois sur la V1, qui garde son `onclick=`.
  La coexistence des deux pages est donc déjà prévue par le code.
- `formulaire/script.js:234` : la pagination collecte `.bloc` par
  `querySelectorAll` et nomme chaque bloc `b.id || b.className`
  (`calculerPages()`, `script.js:173`). Le PDF est sensible au DOM émis.

**La page provisoire, qui disparaît ici**

- `formulaire/index-moteur.html` : 116 lignes. C'est **déjà** la coquille
  cible : `<div id="form-bilan" data-moteur>` (l. 82), en-tête recopié octet
  pour octet (l. 83-96), `<main>` (l. 97) contenant le seul message statique
  `#attente-moteur` (l. 106), `btn-export` **sans** `onclick=`, et
  `<script src="moteur/rendu.js">` après `script.js`. Son en-tête de fichier
  (l. 26-42) est un commentaire qui explique sa nature provisoire : il doit être
  réécrit, pas recopié.
- Elle est nommée dans **sept** endroits, tous à réancrer :
  `.github/workflows/tests.yml:93` (garde de palette), `:147` (garde
  `style=`), `:219` et `:225-236` (commentaire de la garde d'identité),
  `outils/faire-paquet.sh:39` et `:81`, `tests/test_paquet.py:4` et `:78`,
  `tests/test_comparaison_dom.js:33, 532-562`, `formulaire/moteur/rendu.js:133,
  510, 907, 927` (commentaires).
- `outils/faire-paquet.sh:39-41` retire du paquet **trois** chemins :
  `index-moteur.html`, `moteur/` et `schema.json` ; `:81-87` vérifie leur
  absence dans l'archive, et `tests/test_paquet.py:74-80` le revérifie. **Après
  la bascule, cette exclusion livrerait au cabinet une coquille sans moteur et
  sans schéma : un formulaire vide.** C'est le piège principal de cette tâche,
  et il ne ferait rougir aucun test actuel.

**Le moteur**

- `formulaire/moteur/rendu.js:150` :
  `IDS_RESERVES_COQUILLE = new Set(["form-bilan", "date-bilan", "maintitle", "logo", "infos_podo"])`,
  consultée par `verifierCleUnique()` (`:418`) et par la validation des `cle`
  et `titre_cle` de bloc (`:214`, `:242`).
- La coquille émet **21** `id` (comptés : `grep -o 'id="[^"]*"'`). Cinq sont
  réservés. L'audit affirme que les seize autres sont tous **avant**
  `#form-bilan` dans le document, donc protégés par l'ordre
  (`docs/audits/C1-T3.md`, Observation « Les 16 `id` … »). **C'est inexact pour
  l'un d'eux** : `attente-moteur` (`index-moteur.html:106`) vit **dans**
  `#form-bilan > main`. L'invariant d'ordre ne le couvre pas. Vérifié aussi :
  aucune des 82 clés de `formulaire/schema.json` ne collisionne avec aucun des
  21 `id` de la coquille (contrôlé par script).
- `formulaire/moteur/rendu.js:933-941` : `afficherErreurMoteur()` affiche déjà,
  via `annoncer(…, "erreur", true)`, « Le formulaire n'a pas pu être chargé.
  Utilisez le favori « Formulaire — secours V1 » pour continuer la
  consultation. » Le favori est donc déjà nommé par le code — mais **le favori
  n'existe pas encore sur la tablette**, et aucun message ne donne l'adresse de
  repli si le favori a disparu.
- `formulaire/moteur/rendu.js:876-931` : `demarrerMoteur()` résout `<main>` par
  `querySelector` **dans** `#form-bilan`, charge `schema.json` par `fetch(…,
  {credentials: "same-origin"})`, retire `#attente-moteur` après succès, puis
  appelle `demarrerApplication()`.

**Les tests, et ce qui va s'éteindre**

- 103 tests verts : 73 Python, 7 Node (file), 8 (palette), 7 (inventaire),
  8 (comparaison de DOM) — `npm test`, `docs/revues/C1-T3.md`.
- `tests/test_inventaire_formulaire.js:27` lit `formulaire/index.html` et en
  dérive **tout** : `corpsFormulaire()` (l. 43-49) coupe au littéral
  `<div id="form-bilan">`, puis `clesDuFormulaire()` (l. 100), `blocsHtml()`
  (l. 117), `imagesHtml()` (l. 137), `idsPresentsDansLeFormulaire()` (l. 202).
  Après la bascule :
  - le littéral `<div id="form-bilan">` ne correspond plus (la coquille porte
    `data-moteur`) → `corpsFormulaire()` **lève**, et le test échoue
    bruyamment. C'est le seul mode de défaillance franc du lot ;
  - le groupe 1 (l. 380-443) recompterait 1 bloc au lieu de 29 et 0 image au
    lieu de 4 ;
  - le groupe 6 (l. 489-496) deviendrait **vert à vide** :
    `idsGelesAttendus()` (l. 221-228) intersecte les `id` référencés par
    `style.css`/`script.js` avec ceux **présents dans le formulaire** ; la
    coquille n'en porte plus que cinq, donc la liste des clés gelées exigées se
    vide. La protection des clés de brouillon s'éteindrait sans bruit, juste au
    moment où elle sert ;
  - le groupe 7 (l. 498-519) deviendrait **tautologique** : il compare les clés
    du HTML à celles de `schema.json` ; si les clés du HTML sont dérivées du
    schéma, il ne compare plus rien.
- `tests/test_comparaison_dom.js:32-33` lit la V1 dans `formulaire/index.html`
  et l'en-tête du moteur dans `formulaire/index-moteur.html` ; `:536-562`
  vérifie que les deux en-têtes sont identiques (espaces mis à part), que le
  message statique `#attente-moteur` dirige vers « secours V1 », et qu'aucun
  `onclick=` ne traîne sur `#btn-export`. Ces trois contrôles doivent changer de
  cible, sinon ils lisent un fichier supprimé.
- `tests/test_integration.py:61-63` copie `formulaire/index.html`,
  `style.css`, `script.js`, `schema.json` dans la racine web d'essai ;
  `:226-230` vérifie que `/`, `/index.html`, `/style.css`, `/script.js`
  répondent 200. `index-v1.html` n'y est pas.
- `tests/test_coquille.py` **n'existe pas**. `formulaire/index-v1.html`
  **n'existe pas**.

**La garde d'identité du cabinet**

`.github/workflows/tests.yml:238-287`. Source = `formulaire/index.html`, ancre
= `<section id="infos_podo">` … `</section>`, cibles =
`docs/schema-formulaire.md`, `tests/test_inventaire_formulaire.js`,
`formulaire/schema.json`, `formulaire/moteur/rendu.js`,
`tests/test_comparaison_dom.js`. Échoue si l'ancre est introuvable ou si aucune
ligne de texte n'en est extraite. **Vérifié sur la coquille que ce contrat
spécifie :** `index-moteur.html` porte `<section id="infos_podo">` (l. 88) avec
ses quatre lignes de texte, donc l'ancre tient après la bascule. Le message
d'échec ne nomme que le fichier cible et la plage de lignes **source** — jamais
le contenu ; le journal d'actions GitHub est public et le dépôt l'est aussi.

**La tolérance (i) du comparateur**

`tests/test_comparaison_dom.js:186-199` filtre l'ancêtre
`<section id="consultation">` du côté V1 seulement. Sa condition de validité,
posée par l'audit : aucun sélecteur enfant `>` ni adjacent `+` dans
`style.css`, et rien qui cible `#consultation`. **La bascule ne change rien à
cette condition** : elle ne touche pas `style.css`, et l'enveloppe
`#consultation` ne quitte pas `index-v1.html`, qui devient le côté V1 de la
comparaison. La tolérance reste donc valide à l'identique ; elle devra tomber le
jour où un sélecteur enfant apparaîtra dans `style.css` (hors de cette tâche).

**Le jeu de référence visuelle**

`docs/references-visuelles/` ne contient que `LISEZMOI.md` (réécrit le 15
octobre pour cette cible). Les quatre fichiers attendus — `bilan-reference.json`,
`V1-reference.pdf`, `V1-reference-ecran-1.png`, `V1-reference-ecran-2.png` —
**n'existent pas**. Aucune règle de `.gitignore` ne les couvre : ils entreront
dans un dépôt public.

## 4. Périmètre

### Dans le périmètre

1. `formulaire/index-v1.html` : copie gelée, octet pour octet, de l'actuel
   `formulaire/index.html`.
2. `formulaire/index.html` réduit à la coquille.
3. Suppression de `formulaire/index-moteur.html` et réancrage de ses sept
   références.
4. Inversion du paquet : `moteur/`, `schema.json` et `index-v1.html` deviennent
   **obligatoires** dans l'archive livrée au cabinet.
5. `tests/test_coquille.py` : création. Empreinte d'`index-v1.html`, intégrité
   de la coquille, cohérence d'`IDS_RESERVES_COQUILLE`, absence
   d'`index-moteur.html`.
6. Réancrage de `tests/test_inventaire_formulaire.js` (groupes 1, 6, 7 ;
   nouveau groupe 8) et de `tests/test_comparaison_dom.js`.
7. `tests/test_integration.py` : `index-v1.html` servi, authentifié.
8. Extension d'`IDS_RESERVES_COQUILLE` aux 21 `id` de la coquille, vérifiée
   mécaniquement.
9. Le favori « Formulaire — secours V1 » sur la tablette, posé **et éprouvé**
   avant la bascule, et l'adresse de repli ajoutée aux deux messages d'erreur.
10. `docs/Mode_emploi.md` et `docs/USER-GUIDE.md` : le geste de repli, côté
    praticienne. `README.md` : l'arborescence.
11. Les mises en échec délibérées de l'étape 11, consignées dans
    `docs/audits/C1-T3b-mises-en-echec.md`.

### Hors périmètre

- **Toute modification de `formulaire/moteur/rendu.js` autre que
  `IDS_RESERVES_COQUILLE`, le texte de `afficherErreurMoteur()` et les
  commentaires qui nomment `index-moteur.html`.** Le moteur est audité et revu :
  on ne le retouche pas ici.
- **Toute modification de `formulaire/schema.json`.** Le schéma est la référence
  du comparateur ; le changer dans la même tâche que la bascule rendrait un
  échec indiagnosticable.
- `date-bilan` dans le schéma via `en_tete`, et le retrait de la tolérance du
  groupe 7 : l'en-tête sort en configuration avec **C2-T1**, pas ici.
- La suppression de `formulaire/index-v1.html` : **C1-T4**, après la campagne de
  bilans réels.
- Le déplacement du schéma vers `clients/morlaix/` : C1-T4.
- Un test par type et par disposition : C7-T2.
- CSP, en-têtes de sécurité : C6-T1. La coquille n'a pas d'`onclick=` ni de
  `style=`, c'est un effet de bord heureux, pas l'objet de la tâche.
- `cheminImageAutorise()` et son refus des noms accentués et des sous-dossiers :
  observation pour **C9**. Ici, on vérifie seulement que les quatre images
  réelles passent toujours (critère 8).
- Toute correction d'anomalie du HTML V1 (A1 à A6).

## 5. Fichiers touchés

| Fichier | Nature | Remarque |
|---|---|---|
| `formulaire/index-v1.html` | création | Copie de l'actuel `index.html`, **octet pour octet**. Gelé à jamais. |
| `formulaire/index.html` | réécriture | Coquille. Contenu dérivé d'`index-moteur.html`, commentaire de tête réécrit. |
| `formulaire/index-moteur.html` | **suppression** | Sa raison d'être était de ne pas toucher `index.html`. |
| `formulaire/moteur/rendu.js` | modification étroite | `IDS_RESERVES_COQUILLE` (21 `id`), texte d'erreur, commentaires. Rien d'autre. |
| `outils/faire-paquet.sh` | modification | Exclusion → inclusion obligatoire. |
| `tests/test_paquet.py` | modification | Le moteur doit être **présent**, et `index-v1.html` aussi. |
| `tests/test_coquille.py` | création | Empreinte, intégrité, `IDS_RESERVES_COQUILLE`, absence d'`index-moteur.html`. |
| `tests/test_inventaire_formulaire.js` | modification | Source V1 = `index-v1.html` ; groupe 6 réancré sur coquille + schéma ; groupe 8 nouveau. |
| `tests/test_comparaison_dom.js` | modification | V1 ← `index-v1.html`, coquille ← `index.html`. |
| `tests/test_integration.py` | modification | `index-v1.html` copié et servi. |
| `.github/workflows/tests.yml` | modification | Trois réancrages de nom de fichier, un pas Python de plus si besoin. |
| `docs/Mode_emploi.md`, `docs/USER-GUIDE.md` | ajout d'une section courte | Le geste de repli. |
| `README.md` | 3 lignes | Arborescence : `index-v1.html`, `moteur/`, `schema.json`. |
| `docs/references-visuelles/*` | ajout (Baptiste) | Étape 0, puis les homologues du moteur. |
| `docs/audits/C1-T3b-mises-en-echec.md` | création | Journal des mises en échec. |
| `docs/contrats/C1-T3b.md` | ce fichier | Le nombre de pages du PDF de référence s'écrit **ici**, étape 0. |

## 6. Plan d'implémentation

### Étape 0 — Préalable bloquant et irréversible (Baptiste, au navigateur)

**Rien ne commence avant.** Produire les quatre fichiers décrits par
`docs/references-visuelles/LISEZMOI.md`, sur la V1 encore en place :

```
docs/references-visuelles/bilan-reference.json
docs/references-visuelles/V1-reference.pdf
docs/references-visuelles/V1-reference-ecran-1.png
docs/references-visuelles/V1-reference-ecran-2.png
```

Puis **reporter ici, dans ce fichier, avant toute modification de code** :

> **Nombre de pages du PDF de référence V1 = `____`** (à compléter par Baptiste
> à l'étape 0 ; au moins trois pages attendues, cf. LISEZMOI §1).

**Conséquence si l'on passe outre, écrite noir sur blanc.** Cette tâche rend la
V1 **inobservable**. Une fois `index.html` devenu coquille, plus aucun PDF de la
V1 ne peut être fabriqué, et le critère « PDF superposable » n'a plus de
référence : un défaut de marge, de police ou de pagination se découvrirait chez
la praticienne, sans rien à quoi le comparer, et sans moyen de savoir si c'est
le moteur ou le souvenir qui a tort. Aucun agent ne peut rattraper cela : ni
Chrome, ni Playwright, ni Puppeteer n'existent dans l'environnement de
développement assisté. `formulaire/index-v1.html` conserve le *fichier*, pas le
*rendu* : il faudrait réinstaller un navigateur, une tablette et une session
authentifiée pour en refaire un PDF, c'est-à-dire refaire l'étape 0 — mais sans
jamais savoir si la V1 de ce jour-là est encore celle d'aujourd'hui.

*Vérification de l'étape :* `ls docs/references-visuelles/` montre les quatre
fichiers ; la relecture de confidentialité du §4 du LISEZMOI est faite (nom
« Témoin Référence », captures **regardées à l'œil**, onglets et notifications
comprises) ; le nombre de pages est écrit ci-dessus.

### Étape 1 — Geler les étapes 1 à 8 dans un commit

Sur la branche `c1-t3-moteur-rendu-schema`, commiter l'intégralité du travail
non commité de C1-T3 (11 modifications, 8 créations, `git status`) **sans y
mêler aucune modification de cette tâche**. Message en français, préfixé
`C1-T3`.

Raison : le retour arrière de niveau 3 (section 11) est un `git revert` du
commit de bascule. Si les étapes 1 à 8 et la bascule sont dans le même commit,
le revert détruit le moteur avec elle, et il n'y a plus rien à réessayer.

*Vérification :* `git status --short` vide ; `git log --oneline -1` montre le
commit ; `npm test` toujours vert (103 tests) ; `shasum -a 256
formulaire/index.html` inchangé.

### Étape 2 — Créer la fiche de secours, et la geler

1. `cp formulaire/index.html formulaire/index-v1.html` — **aucune
   modification**, pas même un espace, pas même une fin de ligne.
2. Écrire `tests/test_coquille.py`, en français, avec quatre classes de
   vérifications (détail en section 9). La première, immédiatement
   exécutable : `formulaire/index-v1.html` a le SHA-256
   `589eee333e68bdbde9e46c1343392e767baa5cfa6b1abfee02026d9431958a6e`.

*Vérification :* `shasum -a 256 formulaire/index-v1.html` rend l'empreinte
attendue ; `python3 -m unittest tests.test_coquille` vert.

### Étape 3 — Poser et éprouver le favori de secours (Baptiste, **avant** la bascule)

`formulaire/index.html` est **encore la V1** à cette étape : `index-v1.html` est
servi à côté d'elle, par le même serveur, derrière la même authentification. Le
repli est donc testable sans avoir rien cassé.

1. Sur la tablette, ouvrir `https://<adresse-du-PC>:<port>/index-v1.html`.
2. Enregistrer la page en favori sous le nom exact **« Formulaire — secours
   V1 »**, sur la barre de favoris **et** sur l'écran d'accueil.
3. Saisir deux champs, tracer un trait sur un schéma, générer un PDF, et
   constater qu'il arrive dans le dossier des bilans du PC.
4. Consigner la date et le constat dans `docs/audits/C1-T3b-mises-en-echec.md`.

Si cette étape échoue, **on ne bascule pas.** Le repli est la condition de la
bascule, pas sa conséquence.

*Vérification :* critère 2 (humain, Baptiste).

### Étape 4 — Basculer `index.html` en coquille

Remplacer le contenu de `formulaire/index.html` par celui de
`formulaire/index-moteur.html`, avec **trois** différences et aucune autre :

1. Le commentaire de tête (`index-moteur.html:26-42`), qui décrit une page
   provisoire, est remplacé par un commentaire qui décrit la coquille : d'où
   vient le corps du bilan (`schema.json` par `moteur/rendu.js`), pourquoi
   l'en-tête reste en dur (C2-T1), pourquoi `index-v1.html` existe et qu'il est
   gelé, et pourquoi `#btn-export` n'a pas d'`onclick=` (il est câblé par
   `demarrerApplication()` sous `data-moteur`, `script.js:800-801` ; le remettre
   déclencherait l'export deux fois par clic).
2. Le message statique `#attente-moteur` nomme **le favori et l'adresse de
   repli** : « … utilisez le favori « Formulaire — secours V1 » (adresse :
   `index-v1.html`) pour continuer la consultation. »
3. Rien d'autre. En particulier l'en-tête `<header class="bloc">` reste **octet
   pour octet** celui de la V1, et la barre d'outils reste **avant**
   `#form-bilan` dans le document (invariant, voir section 7).

Appliquer la même addition d'adresse au texte de `afficherErreurMoteur()`
(`formulaire/moteur/rendu.js:933-941`).

*Vérification :* `diff <(sed -n '/<header class="bloc">/,/<\/header>/p'
formulaire/index-v1.html) <(sed -n '/<header class="bloc">/,/<\/header>/p'
formulaire/index.html)` est vide ; `grep -c 'style="' formulaire/index.html`
rend 0 ; `grep 'id="btn-export"' formulaire/index.html` ne contient pas
`onclick`.

### Étape 5 — Supprimer la page provisoire et réancrer ses sept références

`rm formulaire/index-moteur.html`, puis, dans cet ordre :

- `tests/test_comparaison_dom.js:32-33` : `CHEMIN_HTML` →
  `formulaire/index-v1.html` (le côté V1 de la comparaison),
  `CHEMIN_INDEX_MOTEUR` → `formulaire/index.html`, renommée `CHEMIN_COQUILLE`.
  Les trois contrôles de `:536-562` (en-tête identique, `#attente-moteur` vers
  « secours V1 », pas d'`onclick=`) portent désormais sur la coquille de
  production. Le commentaire de tête du fichier (l. 6-14), qui déclare la passe
  partielle, est réécrit.
- `.github/workflows/tests.yml:92-93` (garde de palette) et `:147` (garde
  `style=`) : `formulaire/index-moteur.html` → `formulaire/index-v1.html`.
- `.github/workflows/tests.yml:219` et `:225-236` : le commentaire de la garde
  d'identité est réécrit pour dire que **`formulaire/index-v1.html`** est
  délibérément hors des cibles — c'est la copie gelée de la source elle-même,
  sous surveillance d'empreinte (`tests/test_coquille.py`) et de comparaison
  (`tests/test_comparaison_dom.js`), pas un endroit où l'identité pourrait
  fuiter sans bruit. La source de la garde reste `formulaire/index.html`.
- `formulaire/moteur/rendu.js:133, 510, 907, 927` : les commentaires nomment
  `formulaire/index.html` (la coquille) au lieu d'`index-moteur.html`.

*Vérification :* `grep -rn "index-moteur" . --exclude-dir=.git
--exclude-dir=node_modules --exclude-dir=docs` ne rend plus rien ; `npm test`
vert.

### Étape 6 — Inverser le paquet

`outils/faire-paquet.sh` : supprimer les trois `rm` de `:39-41` et la boucle
`interdit` de `:81-87` ; ajouter `formulaire/moteur/rendu.js`,
`formulaire/schema.json`, `formulaire/index.html` et `formulaire/index-v1.html`
à la boucle `obligatoire` de `:65-71`, avec un commentaire d'une ligne : depuis
C1-T3b, le formulaire de production **est** le moteur, et un paquet sans schéma
livrerait un formulaire vide.

`tests/test_paquet.py` : `test_moteur_exclu_du_paquet` devient
`test_moteur_present_dans_le_paquet` (`formulaire/moteur/rendu.js`,
`formulaire/schema.json`), `test_formulaire_de_production_present` gagne
`formulaire/index-v1.html`, et l'en-tête du module est réécrit.

*Vérification :* `python3 -m unittest tests.test_paquet` vert ; mise en échec de
l'étape 11, scénario 3.

### Étape 7 — Réancrer `tests/test_inventaire_formulaire.js`

Deux sources distinctes, nommées comme telles :

- `CHEMIN_V1 = formulaire/index-v1.html` — la V1 gelée. C'est le **témoin
  indépendant** des 29 blocs, des 45 champs et des 4 images. Les groupes 1 et 7
  s'y ancrent. Commentaire obligatoire : son intégrité est garantie par
  l'empreinte SHA-256 de `tests/test_coquille.py`, sans quoi on pourrait un jour
  l'éditer pour la faire coller à un schéma qui a dérivé.
- `CHEMIN_COQUILLE = formulaire/index.html` — la production.

Modifications précises :

1. `corpsFormulaire()` accepte un texte en argument et localise le conteneur par
   `/<div\s+id="form-bilan"[^>]*>/` (et non par le littéral `<div
   id="form-bilan">`) : la coquille porte `data-moteur`. Elle **lève** toujours
   si le motif est introuvable.
2. Groupe 1 : inchangé dans sa substance, lu sur `CHEMIN_V1`. Il doit continuer
   à rendre 29 blocs, 45 champs, 4 images dans l'ordre.
3. Groupe 6 : `idsPresentsDansLeFormulaire()` devient l'**union** des `id` émis
   par la coquille à l'intérieur de `#form-bilan` **et** des `id` émis par le
   schéma — `bloc.cle`, `bloc.titre_cle`, `champ.cle` (tous types sauf les
   `lignes` de `tableau`, qui ne reçoivent jamais d'`id`), `option.cle` des
   `radio`. Nouvelle fonction `idsEmisParLeSchema()`, distincte de
   `clesDuSchemaJson()` (qui dérive des clés de **brouillon**, forme
   `ligne.cle + "#" + valeur`). La liste des clés gelées exigées doit retrouver
   ses 7 entrées.
4. Groupe 7 : inchangé — bijection `CHEMIN_V1` ↔ `schema.json`, exception
   `date-bilan`. Ajouter une assertion qui rend l'exception non vacante :
   `date-bilan` doit être **présent dans la coquille**. Sans elle, l'exception
   devient un laissez-passer.
5. Groupe 8, nouveau : **la coquille ne contient que l'en-tête.** Dans
   `#form-bilan` de `formulaire/index.html` : exactement 1 élément de classe
   `bloc`, exactement 0 `img`, exactement 1 champ de saisie dont la clé est
   `date-bilan`, et un `<main>` dont le seul contenu est le paragraphe
   `#attente-moteur`. Raison : la coquille est le seul fichier HTML de
   production, et rien d'autre ne surveille qu'un bloc n'y soit pas recopié à la
   main — ce qui réintroduirait exactement le verrou que C1 lève.

*Vérification :* `node tests/test_inventaire_formulaire.js` rend 8 groupes
verts ; mises en échec de l'étape 11, scénarios 1 et 2.

### Étape 8 — Réserver les 21 `id` de la coquille

`formulaire/moteur/rendu.js:150` : `IDS_RESERVES_COQUILLE` passe de 5 à **21**
entrées — les 21 `id` que la coquille émet (`grep -o 'id="[^"]*"'
formulaire/index.html`). Le commentaire de `:131-149` est réécrit en
conséquence : l'argument « l'ordre du document protège les seize autres » est
**faux pour `attente-moteur`**, qui vit dans `#form-bilan > main` (section 3), et
il est de toute façon un argument de hasard — `label for=` pointerait sur le
mauvais contrôle, et un futur déplacement de la barre d'outils rendrait inerte
le bouton d'export.

Vérification mécanique, dans `tests/test_coquille.py` : l'ensemble des `id`
extraits de `formulaire/index.html` est **exactement égal** à l'ensemble lu dans
la ligne `IDS_RESERVES_COQUILLE` de `formulaire/moteur/rendu.js`. Un `id` ajouté
à la coquille sans être réservé fait rougir la CI ; une entrée réservée sans
`id` correspondant aussi.

Contrôle de non-régression : aucune des 82 clés de `formulaire/schema.json` ne
figure parmi les 21 (vérifié à la rédaction de ce contrat) ; `validerSchema()`
doit continuer à rendre `[]` sur le schéma de production.

*Vérification :* `node tests/test_comparaison_dom.js` vert (il rend le schéma de
production) ; `python3 -m unittest tests.test_coquille` vert ; mise en échec de
l'étape 11, scénario 4.

### Étape 9 — Le serveur et la surface

`tests/test_integration.py:61-63` : ajouter `formulaire/index-v1.html` aux
fichiers copiés dans la racine web d'essai. `:226-230` : ajouter
`/index-v1.html` à la liste des ressources servies (200 après
authentification). Ajouter une assertion : `/index-v1.html` sans identifiants
répond **401**, comme le reste — le repli est derrière la même porte.

Aucune modification de `serveur/serveur.py` : `.html` est déjà dans
`EXTENSIONS_SERVIES` (`serveur.py:64`), et `index-v1.html` vit dans la racine
web. `git diff serveur/` doit rester **vide**.

*Vérification :* `python3 -m unittest discover -s tests` vert ; `git diff
--stat serveur/` vide.

### Étape 10 — La documentation de la praticienne

- `docs/Mode_emploi.md`, dans la section « 2. Pendant la consultation » : un
  encadré de quatre lignes maximum — *si le formulaire ne s'affiche pas ou
  qu'un message rouge le dit, toucher le favori « Formulaire — secours V1 » :
  c'est le même formulaire, le même brouillon, le même dépôt ; la saisie en
  cours est reprise.* Et dans l'« Aide-mémoire », une ligne : « Secours |
  favori *Formulaire — secours V1* ».
- `docs/USER-GUIDE.md` : le même ajout, en anglais.
- `README.md`, arborescence (l. 225-231) : `index-v1.html`, `moteur/`,
  `schema.json`.

*Vérification :* lecture ; les deux guides partent dans le paquet
(`outils/faire-paquet.sh:52`), donc l'ajout arrive au cabinet.

### Étape 11 — Mettre les gardes en échec, exprès

Un garde-fou qu'on n'a pas mis en échec exprès ne garde rien : c'est le défaut
qui s'est répété deux fois le 15 octobre. Six scénarios, chacun rejoué **puis
annulé**, consignés dans `docs/audits/C1-T3b-mises-en-echec.md` avec la commande
et la sortie. Les fichiers concernés sont **ajoutés à l'index** (`git add -N` au
minimum) avant chaque essai : un contrôle qui lit l'index Git ne voit rien sur
un fichier non suivi.

1. **Groupe 6 réancré ne peut plus être vert à vide** — retirer
   `section_squelettes` de `formulaire/schema.json` : le groupe 6 doit échouer
   en nommant l'`id` gelé manquant (et non passer en silence).
2. **Clés gelées toujours protégées** — renommer `familliaux` en `familiaux`
   dans `schema.json` : le groupe 7 échoue en nommant la clé.
3. **Le paquet ne peut plus partir sans moteur** — remettre `rm -rf
   "$PAQUET/formulaire/moteur"` dans `outils/faire-paquet.sh` :
   `tests/test_paquet.py` échoue.
4. **`IDS_RESERVES_COQUILLE` est tenue à jour** — ajouter `id="essai"` à la
   coquille : `tests/test_coquille.py` échoue en nommant l'`id` non réservé. Et
   dans l'autre sens : retirer une entrée de la liste du moteur.
5. **La fiche de secours est gelée** — ajouter un espace à
   `formulaire/index-v1.html` : `tests/test_coquille.py` échoue sur
   l'empreinte.
6. **La garde d'identité mord encore après la bascule** — trois sous-cas :
   ancre `<section id="infos_podo">` renommée dans la coquille (échec
   `::error::Ancre … introuvable`) ; contenu de la section vidé (échec
   « plus rien à contrôler ») ; une coordonnée réelle recopiée dans
   `formulaire/schema.json` (échec nommant **le fichier et la plage de lignes
   source uniquement**, aucune coordonnée dans le journal).

*Vérification :* six scénarios, six échecs réels, six annulations vérifiées par
`git diff` vide ; `shasum -a 256 formulaire/index-v1.html` inchangé à la fin.

### Étape 12 — Le contrôle visuel, et le commit unique (Baptiste)

1. Rejouer `docs/references-visuelles/bilan-reference.json` dans le formulaire
   rendu par le moteur : coller la valeur dans la clé `bilan-posturo-brouillon`
   du stockage local, recharger, cliquer « Restaurer ».
2. Générer `docs/references-visuelles/C1-T3b-moteur.pdf` et les deux captures
   `C1-T3b-moteur-ecran-1.png`, `-2.png`.
3. Comparer à `V1-reference.pdf` : **nombre de pages identique** à celui de
   l'étape 0, aucune différence de couleur, de marge ni de positionnement. Seul
   le bruit de compression JPEG est admis (`toDataURL("image/jpeg", 0.92)`,
   `script.js:276`). Regarder en particulier le bloc « Empreinte encre »
   (tolérance (g) du comparateur) et le bloc 20, dont l'audit signale une
   divergence visuelle possible non couverte par les tests.
4. Consigner le verdict dans `docs/audits/C1-T3b-mises-en-echec.md`.
5. **Un seul commit, isolé et le dernier**, pour toute la bascule (étapes 2,
   4 à 10) — c'est la condition du niveau 3 de la section 11.

*Vérification :* critères 1 à 12 de la section 8 tous cochés ; `git log
--oneline -2` montre le commit de bascule seul au-dessus du commit de l'étape 1.

## 7. Décisions de conception

### Déjà tranché — ne pas rouvrir

**La coquille est le contenu d'`index-moteur.html`, pas une réécriture.** Ce
fichier a été écrit, audité et revu pour être exactement la coquille cible. Le
réécrire de mémoire reviendrait à rejouer les constats n°1, 9 et 10 de l'audit
(blocs hors de `<main>`, silence si `rendu.js` ne se charge pas, `onclick=` en
double). On déplace du contenu ; on ne le réinvente pas.

**La barre d'outils reste avant `#form-bilan` dans le document.** Invariant, pas
habitude. Deux raisons : `#zone-messages`, `#outils-globaux` et les barres
doivent rester **hors** de `#form-bilan` pour ne jamais être capturés dans le
PDF (`index.html:32`, commentaire d'origine), et l'ordre du document est la
seconde ligne de défense sur les `id` de la barre d'outils, derrière
`IDS_RESERVES_COQUILLE`.

**Les seize `id` hors `#form-bilan` entrent dans `IDS_RESERVES_COQUILLE`,
plutôt que de rester protégés par l'ordre du document.** La question était
posée par la feuille de route et laissée ouverte par l'audit. Trois raisons de
trancher ainsi : l'argument d'ordre est **faux** pour `attente-moteur`, qui vit
dans `#form-bilan` (section 3) ; l'ordre protège `getElementById()` mais pas
`label for=`, qui pointerait sur le mauvais contrôle ; et la liste est gratuite
à maintenir dès lors qu'un test vérifie son égalité avec les `id` réellement
émis par la coquille — ce qui est la différence entre une liste et une liste qui
ment. Vérifié : aucune des 82 clés du schéma de production n'y collisionne, donc
la production ne change pas de comportement.

**`formulaire/index-v1.html` est gelé, et son empreinte est vérifiée.** Le
modifier n'est pas un retour arrière : c'est la création d'une seconde
implémentation à maintenir, c'est-à-dire exactement le verrou que C1 existe pour
lever et que C1-T4 doit clore. Si la V1 doit changer, c'est que la bascule a
échoué et qu'il faut la refaire, pas la contourner.

**Le témoin des 45 champs devient `index-v1.html`, pas le schéma.** Un test qui
dérive sa source de vérité du fichier qu'il contrôle ne contrôle rien. Les
groupes 1 et 7 gardent donc un témoin indépendant — la V1 gelée, dont
l'empreinte est sous garde. Conséquence assumée, à inscrire au contrat de
**C1-T4** : le jour où `index-v1.html` disparaît, les groupes 1 et 7 perdent
leur témoin, et l'inventaire de `docs/schema-formulaire.md` §3 (écrit à la main,
45 lignes) devient la seule référence.

**Les deux messages de repli nomment le favori *et* l'adresse.** Un favori
s'efface, se perd au changement de tablette, ou n'a jamais été posé sur le bon
profil Chrome. Le message ne coûte rien de plus et il est la seule chose que la
praticienne ait sous les yeux à ce moment-là.

**La tolérance (i) du comparateur reste en place, inchangée.** La bascule ne
touche pas `style.css` et ne déplace pas `#consultation`, qui reste dans
`index-v1.html` — le côté V1 de la comparaison. Sa condition de validité
(aucun sélecteur `>` ni `+` dans `style.css`, rien qui cible `#consultation`)
est donc intacte. Rien à faire ; à ne pas refaire non plus.

**`date-bilan` n'entre pas dans le schéma.** L'audit posait la question ; la
réponse est C2-T1, où l'en-tête entier sort en configuration. Le faire ici
ajouterait une clé racine `en_tete` au schéma, donc une incrémentation de
`version_schema` (D8), dans la même tâche que la bascule. Un échec deviendrait
indiagnosticable.

**Aucune modification de `formulaire/schema.json` ni du corps du moteur.** Même
raison : le schéma et le moteur sont la référence du comparateur. Si la
superposition des PDF échoue à l'étape 12, on veut pouvoir affirmer que seule la
coquille a changé.

**Le commit de bascule est unique, isolé et le dernier.** Reprise explicite de
la section 11 du contrat de C1-T3. Sans cela, le niveau 3 du retour arrière
n'existe pas.

### Laissé à l'implémenteur

- L'organisation interne de `tests/test_coquille.py` (nombre de classes, noms
  des méthodes), pourvu que les quatre vérifications de la section 9 y soient et
  qu'il tourne sous Python 3.9.
- La forme exacte de l'analyse des `id` de la coquille et de la ligne
  `IDS_RESERVES_COQUILLE` dans `tests/test_coquille.py` (expression régulière,
  tolérance aux espaces), pourvu qu'elle échoue bruyamment si la ligne du moteur
  change de forme plutôt que de passer au vert à vide.
- Le libellé exact du commentaire de tête de la coquille, pourvu qu'il couvre
  les quatre points de l'étape 4.
- La rédaction de l'encadré de `docs/Mode_emploi.md`, pourvu qu'elle tienne en
  quatre lignes et nomme le favori mot pour mot.

## 8. Critères d'acceptation

Deux critères sont **humains et attribués à Baptiste** : le 2 et le 11. Ils ne
sont pas automatisables — aucun navigateur n'existe en développement assisté.
Un critère humain non nommé comme tel est un critère qu'on coche sans le
vérifier.

- [ ] **1. Préalable levé.** `ls docs/references-visuelles/` montre
  `bilan-reference.json`, `V1-reference.pdf`, `V1-reference-ecran-1.png`,
  `V1-reference-ecran-2.png`, et le nombre de pages est inscrit à l'étape 0 de
  ce contrat (`grep -n "Nombre de pages du PDF de référence V1" docs/contrats/C1-T3b.md`
  ne montre plus `____`).
- [ ] **2. Repli éprouvé AVANT la bascule — critère humain, Baptiste.** Le
  favori « Formulaire — secours V1 » existe sur la barre de favoris **et** sur
  l'écran d'accueil de la tablette ; il a été ouvert une fois alors que
  `index.html` était encore la V1 ; deux champs saisis, un trait tracé, un PDF
  généré, et le PDF constaté dans le dossier des bilans du PC. Date et constat
  dans `docs/audits/C1-T3b-mises-en-echec.md`.
- [ ] **3. La V1 est conservée octet pour octet.**
  `shasum -a 256 formulaire/index-v1.html` rend
  `589eee333e68bdbde9e46c1343392e767baa5cfa6b1abfee02026d9431958a6e`.
- [ ] **4. La coquille ne contient que l'en-tête.**
  `node tests/test_inventaire_formulaire.js` sort 0 avec **8** groupes verts,
  dont le groupe 8 : dans `#form-bilan` de `formulaire/index.html`, 1 `.bloc`,
  0 `img`, 1 champ (`date-bilan`), et un `<main>` réduit à `#attente-moteur`.
  `diff` de l'en-tête entre `index-v1.html` et `index.html` est vide (commande à
  l'étape 4).
- [ ] **5. La protection des clés gelées ne s'est pas éteinte.** Le groupe 6
  exige **7** `id` gelés (et non 5 ni 0) ; la mise en échec n°1 de l'étape 11
  (retrait de `section_squelettes` du schéma) produit un échec réel, code 1, qui
  nomme l'`id` manquant. Consigné.
- [ ] **6. Les 21 `id` de la coquille sont réservés, et la liste ne mente pas.**
  `python3 -m unittest tests.test_coquille` sort 0 ; les mises en échec n°4
  (ajout d'un `id` à la coquille, retrait d'une entrée du moteur) produisent
  deux échecs réels. `validerSchema(formulaire/schema.json)` rend toujours `[]`
  (vérifié par `node tests/test_comparaison_dom.js`, sortie 0).
- [ ] **7. Le paquet livré au cabinet contient le moteur.**
  `python3 -m unittest tests.test_paquet` sort 0 ; l'archive contient
  `formulaire/index.html`, `formulaire/index-v1.html`,
  `formulaire/moteur/rendu.js`, `formulaire/schema.json`, `LICENSE`, `TIERS.md`
  et **ne contient pas** `index-moteur.html` ; la mise en échec n°3 (réinsertion
  d'un `rm`) fait échouer le test.
- [ ] **8. Le DOM de production est toujours équivalent à la V1.**
  `node tests/test_comparaison_dom.js` sort 0, le côté V1 étant désormais lu
  dans `formulaire/index-v1.html` et la coquille dans `formulaire/index.html`,
  29 blocs comparés, 9 tolérances déclarées inchangées. Les quatre `fichier`
  d'image du schéma passent toujours `cheminImageAutorise()` (couvert par la
  sortie 0 : un refus empêcherait le rendu).
- [ ] **9. La page provisoire a disparu sans laisser de référence morte.**
  `test ! -f formulaire/index-moteur.html` et
  `grep -rn "index-moteur" . --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=docs`
  ne rend rien. `tests/test_coquille.py` échoue si le fichier réapparaît.
- [ ] **10. Serveur, surface et gardes.** `python3 -m unittest discover -s
  tests` sort 0 sur Python 3.9 et 3.13 ; `/index-v1.html` répond 200 après
  authentification et 401 sans ; `/config.json`, `/cle.pem`, `/journal.log`,
  `/serveur.py` restent inatteignables ; `/sante` reste la seule route non
  authentifiée ; `git diff --stat serveur/` est **vide**. La garde d'identité
  est mise en échec selon les trois sous-cas de l'étape 11 et **aucune
  coordonnée n'apparaît dans sa sortie**.
- [ ] **11. PDF superposable — critère humain, Baptiste.**
  `bilan-reference.json` rejoué dans le formulaire rendu par le moteur,
  `C1-T3b-moteur.pdf` produit : **même nombre de pages** qu'à l'étape 0, aucune
  différence de couleur, de marge ni de positionnement, seul le bruit JPEG
  admis. Les deux captures sont versées à côté de celles de la V1. Verdict écrit
  et daté.
- [ ] **12. Aucune régression, et un seul commit.** `npm test` sort 0 ;
  `node tests/test_file_depots.js` (7 scénarios) et `node tests/test_palette.js`
  (8 groupes) sortent 0 **sans avoir été modifiés**
  (`git diff --stat HEAD~1 -- tests/test_file_depots.js tests/test_palette.js`
  vide) ; `git log --oneline -2` montre la bascule en un commit unique, isolé et
  dernier.

## 9. Tests à écrire

| Test | Fichier | Ce qu'il doit échouer à faire passer aujourd'hui |
|---|---|---|
| Empreinte SHA-256 d'`index-v1.html` = `589eee33…958a6e` | `tests/test_coquille.py` (création) | Le fichier n'existe pas ; rien ne garantira ensuite que la fiche de secours n'a pas été retouchée « juste un peu ». |
| Intégrité de l'en-tête : le `<header class="bloc">` de la coquille est identique à celui d'`index-v1.html`, et l'ancre `<section id="infos_podo">` y est présente avec ses lignes de texte | `tests/test_coquille.py` | Rien ne lie les deux fichiers côté Python ; et la garde d'identité de la CI deviendrait muette si l'ancre partait. |
| `IDS_RESERVES_COQUILLE` du moteur == ensemble des `id` de la coquille (21, les deux sens) | `tests/test_coquille.py` | Aujourd'hui 5 entrées sur 21 ; une `cle` de schéma valant `btn-export` passe, et un `id` ajouté à la coquille n'est jamais réservé. |
| `formulaire/index-moteur.html` n'existe pas | `tests/test_coquille.py` | Le fichier existe ; après suppression, rien n'empêche sa résurrection par un `git checkout` malheureux. |
| Groupe 6 réancré : l'union coquille + schéma rend bien 7 `id` gelés exigés | `tests/test_inventaire_formulaire.js` (modification) | Tel quel, le groupe deviendrait **vert à vide** dès la coquille : il n'exigerait plus aucun `id`. |
| Groupe 8 : la coquille ne contient que l'en-tête (1 `.bloc`, 0 `img`, 1 champ, `<main>` vide hors `#attente-moteur`) | `tests/test_inventaire_formulaire.js` | N'existe pas : rien n'empêche de recopier un bloc à la main dans la coquille, ce qui réintroduit le verrou de C1. |
| Groupe 7 : l'exception `date-bilan` est conditionnée à sa présence dans la coquille | `tests/test_inventaire_formulaire.js` | Aujourd'hui l'exception est inconditionnelle : si `date-bilan` disparaissait de la coquille, elle resterait un laissez-passer. |
| Comparaison V1 ↔ moteur réancrée sur `index-v1.html` / `index.html` | `tests/test_comparaison_dom.js` (modification) | Tel quel, le test lirait `index-moteur.html`, supprimé : il échouerait à l'ouverture du fichier — bruyamment, mais pour la mauvaise raison. |
| Le moteur et le schéma sont **présents** dans l'archive, `index-v1.html` aussi | `tests/test_paquet.py` (modification) | Le test actuel exige exactement le contraire : il passerait au vert sur un paquet qui livre un formulaire vide. |
| `/index-v1.html` servi 200 authentifié, 401 sans identifiants | `tests/test_integration.py` (modification) | Le fichier n'est pas copié dans la racine web d'essai : le repli de consultation n'est couvert par aucun test de surface. |

**Renvoyé, sans trou :** un cas de rendu par type et par disposition → C7-T2 ;
la stabilité du harnais `ServeurEnMarche` sous Windows/Python 3.9 → C7-T5 ; la
tolérance de `cheminImageAutorise()` aux noms accentués → C9.

## 10. Points de sécurité à l'attention de l'auditeur

- **Disponibilité du formulaire de production.** C'est la tâche qui fait du
  chargement de `schema.json` un point de défaillance unique en consultation.
  Trois chemins d'échec à réexaminer : fichier absent du paquet (étape 6), 401
  sur le `fetch`, schéma refusé par le validateur. Dans les trois cas, le
  message statique `#attente-moteur` — qui ne dépend d'aucun JavaScript — doit
  rester visible et nommer le favori **et** l'adresse de repli.
- **Deux formulaires servis à la même adresse, derrière la même
  authentification.** `index-v1.html` entre dans la racine web : il est lisible
  par tout client authentifié, comme `index.html`. Aucune nouvelle extension
  n'entre dans `EXTENSIONS_SERVIES` et `serveur/serveur.py` n'est pas modifié.
- **Brouillon partagé entre les deux pages.** Clé `bilan-posturo-brouillon`,
  mêmes clés de champ : un bilan commencé sur le moteur se reprend sur la fiche
  de secours. C'est voulu et c'est ce qui rend le repli utilisable en pleine
  consultation — c'est aussi le chemin par lequel une divergence de clé
  perdrait silencieusement une saisie. Couvert par les groupes 6 et 7.
- **Identité du cabinet dupliquée dans un dépôt public.**
  `formulaire/index-v1.html` recopie l'en-tête, coordonnées comprises. C'est la
  copie gelée de la source elle-même, délibérément hors des cibles de la garde
  d'identité, sous surveillance d'empreinte et de comparaison. À purger en
  C2-T1 — deux fichiers, pas un.
- **Journalisation publique.** Les mises en échec de l'étape 11 touchent la
  garde d'identité : sa sortie ne doit nommer qu'un fichier et une plage de
  lignes source, jamais une coordonnée. Le journal d'actions GitHub est public.
- **Le jeu de référence visuelle est le seul chemin par lequel une donnée de
  santé réelle pourrait entrer dans ce dépôt public** : `bilan-reference.json`,
  le PDF et surtout les **deux captures PNG**, qui montrent les onglets, la
  barre de favoris et les notifications. Aucune règle de `.gitignore` ne les
  couvre. La relecture du §4 de
  `docs/references-visuelles/LISEZMOI.md` est une étape, pas une
  recommandation : une donnée publiée ne se reprend pas, l'historique Git la
  conserve.
- **Écriture de fichiers.** Aucune nouvelle écriture côté serveur ; le dépôt des
  PDF ne change pas de chemin.
- **Élargissement de la liste des `id` réservés.** Vérifier qu'aucune des 82
  clés du schéma de production n'est refusée après l'étape 8 : un refus
  rendrait le formulaire vide au cabinet, ce qui est le défaut le plus grave que
  cette tâche puisse produire.

## 11. Retour arrière

**C'est la section la plus importante de ce contrat.** Trois niveaux. Le
premier est le seul qui compte un mardi matin, et il est éprouvé **avant** la
bascule (étape 3, critère 2).

### Niveau 1 — par la praticienne, seule, en moins d'une minute, sans ligne de commande

**Le geste :** toucher le favori **« Formulaire — secours V1 »**, sur la barre
de favoris de Chrome et sur l'écran d'accueil de la tablette. C'est tout. Pas de
`git`, pas de fenêtre noire, pas d'appel à Baptiste pour continuer la journée.

Ce qui s'ouvre est `formulaire/index-v1.html` : le formulaire V1 **intact**,
servi par le **même** serveur, à la **même** adresse, derrière la **même**
authentification — la session est déjà ouverte, rien à ressaisir. Il charge
`script.js` et `style.css` inchangés et **ne porte pas** l'attribut
`data-moteur` : `script.js` y démarre comme avant (`script.js:810-826`), stylet,
brouillon, PDF et dépôt compris, et son `onclick=` d'origine câble le bouton
d'export.

**La saisie en cours n'est pas perdue.** Le brouillon est le **même**
(`bilan-posturo-brouillon`, mêmes clés de champ, mêmes traits indexés par
position) : un bilan commencé sur le moteur se reprend sur la fiche de secours,
et inversement. La praticienne touche le favori, clique « Restaurer », et
continue la consultation.

**Ce qui le rend fiable :**

- le favori est posé et ouvert une fois **avant** la bascule, pendant que
  `index.html` est encore la V1 (étape 3) — on ne découvre pas un repli le jour
  où on en a besoin ;
- un PDF en est réellement sorti et est arrivé sur le PC (critère 2) ;
- les deux messages d'erreur du moteur — le statique `#attente-moteur`, qui
  survit même si `rendu.js` ne se charge pas du tout, et
  `afficherErreurMoteur()` — nomment le favori **mot pour mot** et donnent
  l'adresse `index-v1.html` au cas où le favori aurait disparu ;
- `docs/Mode_emploi.md` le dit en quatre lignes, et ce guide part dans le
  paquet ;
- `tests/test_integration.py` vérifie que l'adresse répond 200 authentifiée, et
  `tests/test_coquille.py` que le fichier n'a pas bougé d'un octet.

**Ce qui ne constitue pas un retour arrière :** modifier
`formulaire/index-v1.html`. Son empreinte est vérifiée ; le modifier, c'est
créer une seconde implémentation à maintenir — ce que C1 existe pour supprimer
et C1-T4 pour clore.

### Niveau 2 — Baptiste, à distance ou sur place, en deux minutes

Sur le PC du cabinet, dans `formulaire/` : renommer `index.html` en
`index-coquille.html`, puis `index-v1.html` en `index.html`. Recharger la page
sur la tablette. L'adresse habituelle redevient la V1 ; le favori de la tablette
n'a pas à changer, et le raccourci « Bilan posturo » de l'écran d'accueil non
plus. **Aucun redémarrage du serveur n'est nécessaire** :
`SimpleHTTPRequestHandler` lit le fichier à chaque requête.

### Niveau 3 — annulation du commit

`git revert` du commit de bascule, qui est **unique, isolé et le dernier**
(étapes 1 et 12). À noter : ce revert restaure `index.html` dans sa version V1
**et supprime `index-v1.html`** — l'adresse habituelle redevient donc la V1, et
le favori de secours cesse de répondre. C'est cohérent (il n'y a plus de moteur
à secourir), mais il faut le dire à la praticienne, sinon elle découvre un
favori mort. Ce niveau exige Baptiste, un dépôt et un nouveau paquet : il n'est
jamais sur le chemin critique d'une consultation.

## 12. Risques

| Risque | Probabilité | Conséquence | Parade |
|---|---|---|---|
| Étape 0 sautée « parce qu'on est pressé » | moyenne | Le critère 11 devient **définitivement** invérifiable : la V1 n'est plus observable, un défaut de marge se découvre au cabinet sans référence | Décision bloquante en tête de contrat ; critère 1 ; conséquence écrite à l'étape 0 ; nombre de pages à inscrire avant la première modification |
| Le paquet part au cabinet sans `moteur/` ni `schema.json` (les trois `rm` d'`outils/faire-paquet.sh` sont encore là) | **forte si l'étape 6 est oubliée** | Formulaire **vide** au cabinet, le lendemain de l'installation. Aucun test actuel ne le voit | Étape 6 ; critère 7 ; mise en échec n°3 ; `tests/test_paquet.py` inversé |
| Le groupe 6 de l'inventaire devient vert à vide | **certaine si non traitée** | La protection des clés de brouillon s'éteint sans bruit, juste au moment où elle sert : un `id` renommé perd un bilan en cours | Étape 7 ; critère 5 ; mise en échec n°1 (retrait de `section_squelettes`) |
| Divergence visuelle sur les blocs à forme locale (18, 20, 21, 22, « Empreinte encre ») | moyenne | Formulaire qui « n'a plus la même tête » ; perte de confiance immédiate | Jeu de référence visuelle ; critère 11 attribué à Baptiste, avec ces blocs nommés à l'étape 12 ; niveau 1 du retour arrière |
| Le favori n'est pas posé, ou posé sur le mauvais profil Chrome | moyenne | La seule parade d'une minute n'existe pas le jour où elle sert | Étape 3 **avant** la bascule ; critère 2 humain ; adresse `index-v1.html` écrite dans les deux messages d'erreur et dans `docs/Mode_emploi.md` |
| La bascule et les étapes 1 à 8 dans le même commit | moyenne | Le niveau 3 du retour arrière détruit le moteur avec la bascule | Étape 1 (commit de gel) ; étape 12 point 5 ; critère 12 |
| `index-v1.html` retouché « juste un peu » pour corriger un détail | moyenne | Deux implémentations à maintenir, et la fiche de secours cesse d'être la V1 éprouvée | Empreinte SHA-256 dans `tests/test_coquille.py` ; mise en échec n°5 ; décision de conception explicite |
| L'extension d'`IDS_RESERVES_COQUILLE` refuse une clé légitime du schéma | faible | `validerSchema()` refuse le schéma de production → formulaire vide | Vérifié à la rédaction : aucune collision sur les 82 clés ; critères 6 et 8 ; `node tests/test_comparaison_dom.js` rend le schéma réel |
| La garde d'identité devient muette après le déplacement de l'en-tête | faible | Une coordonnée recopiée dans un fichier public passe sans bruit | Ancre `<section id="infos_podo">` vérifiée présente dans la coquille (section 3) ; `tests/test_coquille.py` ; mise en échec n°6 |
| Un échec du moteur laisse `#attente-moteur` dans `#form-bilan`, et la praticienne clique « Générer le PDF » | faible | Un PDF d'une page contenant l'en-tête et le message d'attente part au dépôt | Le message dirige vers le repli avant qu'on y arrive ; aucune donnée patient n'y figure ; `calculerPages()` ne collecte que `.bloc` |
| Les captures PNG de l'étape 0 publient autre chose que le formulaire | faible | Donnée réelle dans un dépôt public, irrécupérable | §4 du LISEZMOI : ouvrir et **regarder** les deux captures ; recommencer en cas de doute |
