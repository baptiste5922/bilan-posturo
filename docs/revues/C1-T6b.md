# Revue C1-T6b — Fiabiliser l'outillage et les gardes de la grille

**Date :** 2026-11-05  **Verdict :** À LIVRER
**Tests :** `npm test` exécuté par moi, code 0 (241 tests Python, 2 sautés hors Windows ; les 11 suites Node vertes, dont `test_cdp.js` à 5 cas). `python3 -O -m unittest discover -s tests` au premier plan : 241 tests, OK (skipped=2). `python3 -m pyflakes serveur/ tests/` : aucune sortie, code 0. CI 42108356730 : `success` sur 7 jobs à `fb12203` (relu avec `gh`) ; son journal compte 0 « saut - options de capture » et 5 « ok - sans grille… ».

Aucun texte de la fiche du prospect n'a été lu ni n'est reproduit ici : je n'ai ouvert `fiche_presentation.html` ni directement ni par sonde, et les seuls chiffres cités sont des durées et des nombres de blobs.

## Critères d'acceptation

| Critère | Vérifié par | Résultat |
|---|---|---|
| 1. Rien sous `formulaire/` ni `serveur/` | `git diff --quiet ccd75d5 -- formulaire serveur` → 0 | OK |
| 2. `npm test` et `python3 -O` verts | exécutés (voir ci-dessus) | OK |
| 3. pyflakes propre | exécuté, code 0 | OK |
| 4. Aucun `assert` nu | `grep -nE '^\s*assert '` → code 1 | OK |
| 5. `CLAUDE.md` intact | `git diff --quiet` → 0 | OK |
| 6. `dejaLa` absent | `grep -c` → 0 | OK |
| 7. `test_cdp.js` vert | exécuté : 5 `ok` (le contrat disait 3 ; les deux autres viennent du correctif de l'audit) | OK |
| 8. Test branché dans `package.json` et la CI | `grep -c` → 1 et 1 | OK |
| 9. Mutations a et b | journal lignes a, b ; le cas « aucun profil » est le seul à rougir pour b | OK (consigné, non rejoué : elles lancent un vrai Chrome) |
| 10. Plus de « réutilis » ni « déjà en écoute » | `grep -c` → 0 sur les deux fichiers | OK |
| 11. SHA complet et `cat-file` | `grep -c` → 1 et 2 | OK |
| 12. `fetch-depth: 0` une seule fois, dans `test` | `awk` + `grep -c` → 1 ; total → 1 | OK |
| 13. Clone superficiel | rejoué : sans `CI`, ligne `saut - …`, code 0 ; avec `CI=true`, cas nommé en échec avec `fetch-depth: 0`, code 1 ; `CI=` vide → 0 | OK |
| 14. Cas joué dans le dépôt avec `CI=true` | `grep -c` → 1 | OK |
| 15. CI verte, 0 saut, 5 cas | `gh run view 42108356730` | OK |
| 16. `test_licence` joué sous Windows | CI verte sur les 3 systèmes avec historique complet ; le journal d'audit relève 5 `ok` | OK |
| 17. Garde : les méthodes en « ok » | `unittest -v` : messages, noms, exemptions, **blobs** tous « ok » (4 au lieu de 3, ajout post-audit) | OK |
| 18. Sans fiche, `ReperageHorsFichiers` et `ExtractionDeLaFiche` jouent | clone `--depth 1` rejoué : 0 « skipped » pour ces deux classes (6 sauts au total, les autres sont de l'infrastructure) | OK |
| 19. Exemptions fermées | `1 1 1` (messages, blobs, jetons) | OK |
| 20. Mutations d à j | journal : code 1 sous les deux modes, témoin 0, « marqueur absent de la sortie : True » pour f, g, h, j | OK (consigné) |
| 21 / 21b. Aucune trace dans le dépôt réel ni sur `origin` | `ls-remote origin` relu : aucune branche ni étiquette inattendue ; `git log --format=%s ccd75d5..HEAD \| grep -vc '^C1-T6b'` → 0 ; l'audit a relevé avant/après et les objets | OK |
| 22. La fiche n'a pas bougé | `git ls-files … \| grep -c fiche_presentation` → 0 ; `check-ignore` → 0 | OK |
| 23. Constat complet | relu : douze largeurs (les dix demandées, plus 734 et 735), `innerWidth`, `#form-bilan`, `P`, `H` des trois grilles, verdict, ligne « Largeur seuil : 735 px » | OK |
| 24. Hauteur de page non transcrite | `grep -nE "273\|186\|1\.46"` sur `essai-grille.js` → code 1 | OK |
| 25. Mutation k | journal ligne k (734 px : témoin 1, muté 0 ; 1 280 px : 8 lignes OK) | OK (consigné) |
| 26. Spécification | trois `grep -c` → 1, 1, 1 | OK |
| 27. `VocabulaireFictif` | dans la suite, vert | OK |
| B1-B2 | sans objet (DB1 = A) | — |

**Les deux ajouts post-audit.** (1) Lecture de tous les blobs de `repère..HEAD`, avec la seconde exemption `(81f06a97…, 620)`. Le texte du réaudit tient : le blob est ancré par couple (SHA, ligne), la mutation n prouve que la garde de l'état final seule laissait passer un texte commité puis retiré, et `test_exemptions_toujours_justifiees` couvre aussi les blobs. (2) `portEstOccupe` : conclusion « libre » uniquement sur `ECONNREFUSED` (seul ou en agrégat), tout le reste vaut « occupé ». Je confirme à la lecture que `AbortSignal.timeout` lève une `DOMException` sans `cause`, donc `estRefusDeConnexion` rend `false` et le port est déclaré occupé : le cas du serveur `net` muet est bien celui-là, et la mutation o le fait rougir seul.

## Remarques

### Important — La garde des blobs coûte 15 s à chaque `npm test` sur le poste qui détient la fiche, par une normalisation répétée dans un générateur
**Où :** `tests/test_confidentialite_prospect.py:368` (`localiser_dans_blobs`) ; même motif en `:348` (messages) et `:328` (fichiers), mais ces deux-là ne le paient que sur le chemin « marqueur à cheval », donc rarement.
**Problème :** `any(m in normaliser(texte) for m in marqueurs)` réévalue `normaliser(texte)` à chaque marqueur : 365 expressions régulières sur chaque blob, au lieu d'une. Mesuré ici : `localiser_dans_blobs` sur les 72 blobs de la plage met **15,0 s** ; avec la normalisation sortie de la boucle, **0,28 s** pour le même résultat (1 blob porteur, celui de l'exemption). La classe entière dure 25 s sur 45 s de suite Python. Le commentaire de la fonction (« évite de normaliser chaque ligne des blobs qui ne portent rien ») annonce justement l'économie inverse. Le coût croît avec la plage (elle ne se referme jamais : `repère..HEAD` ne fait que grandir, et la tâche suivante, le schéma du prospect, y ajoute des blobs) et se multiplie par le nombre de marqueurs.
**Attendu :** `normalise = normaliser(texte)` une fois avant le `any`. Une garde de 15 s que l'on finit par sauter pour aller vite est une garde qui ne garde plus (premier piège de `CLAUDE.md`). À corriger avant la tâche du schéma du prospect ; sans effet sur la CI, qui n'a pas la fiche.

### Mineur — Les deux exemptions ne survivront pas à une fusion qui réécrit les SHA
**Où :** `tests/test_confidentialite_prospect.py:78` et `:88`.
**Problème :** les exemptions sont ancrées sur le SHA complet d'un commit et d'un blob de `c1-t6-grille`. Si cette branche est fusionnée dans `main` par « Squash and merge » ou par rebasage, ni le commit ni le blob n'existent plus dans `repère..HEAD` : `test_exemptions_toujours_justifiees` échoue, sur le poste à la fiche seulement, avec « exemption sans objet ». C'est le comportement voulu, mais la panne tombera au moment de la fusion, sans mode d'emploi.
**Attendu :** une phrase dans le commentaire de `MESSAGES_EXEMPTES` (ou dans la note de fusion) : après une fusion qui réécrit l'historique, retirer les deux exemptions ; après une fusion simple, rien à faire.

### Mineur — Trois lignes hors gabarit de 80 colonnes
**Où :** `outils/reference-visuelle/cdp.js:62` (la première ligne du commentaire de refus déborde, les suivantes sont à 80) ; `tests/test_confidentialite_prospect.py:20` (la docstring, une ligne de ~170 caractères) ; `docs/schema-formulaire.md`, condition 2, la ligne qui contient « colonne entière et aucune ligne de grille n'est coupée… Un changement de tablette… » (~130 caractères alors que le reste du paragraphe est replié à 80).
**Problème :** reflux manuel resté de l'insertion d'une phrase ; le contrat demandait de « garder la mise en forme » du paragraphe. Sans conséquence fonctionnelle ; les prochains diffs de ces lignes seront bruyants.
**Attendu :** replier à la largeur du voisinage (le `grep` du critère 26 cherche la phrase seule, elle tient sur une ligne repliée).

### Mineur — `essai-grille.js` interroge deux fois `#form-bilan` et deux fois la liste des blocs
**Où :** `outils/reference-visuelle/essai-grille.js:214-227`.
**Problème :** `getBoundingClientRect().width` de `#form-bilan` est lu pour `formulaire` puis relu pour `page`, et la liste `JSON.stringify(grilles.map(g => g.bloc))` est recopiée pour `largeurs` et `hauteurs`. Les deux lectures se suivent dans la même évaluation, donc elles concordent : pas de bug, seulement une divergence possible le jour où l'une des deux est modifiée.
**Attendu :** `const form = …; const ids = …;` en tête de l'évaluation, comme `verification9` le fait déjà pour `form`.

## Ce qui est bien fait

- **La mesure de hauteur est exacte, et sa source est la bonne.** Je l'ai relue contre `calculerPages()` : une coupure franche n'a lieu que si le bloc dépasse seul une page, c'est-à-dire si `bas − haut > hauteurPagePx`, et `hauteurPagePx` vaut la largeur CSS de `#form-bilan` × (`PDF_HAUTEUR − 2·MARGE_MM`)/(`PDF_LARGEUR − 2·MARGE_MM`) (`script.js:348-358`). Les constantes sont lues dans la page (globales du `script.js` servi), jamais recopiées (critère 24 vérifié). Un `PDF_HAUTEUR` disparu lèverait une `ReferenceError` dans la page : l'outil échoue fort, il ne ment pas. Le seuil de 735 px est cohérent avec les chiffres du constat (963 px contre 962,84 px à 734 px).
- **Le cas de repère ne peut plus se vider en silence.** `cat-file -e <sha>^{commit}` sur le SHA complet, nom du cas conservé, message d'échec qui dit quoi corriger (`fetch-depth: 0`). J'ai rejoué le triplet clone superficiel / sans `CI` / `CI=true` : saut, puis échec nommé, code 1.
- **La lecture `cat-file --batch` est défensive à la bonne place.** `rev-list` ou `cat-file` en échec, objet `missing`, entête inattendu, nombre d'objets rendu différent du nombre demandé, tous lèvent ; un objet qui n'est pas un blob est compté mais pas lu ; les binaires sont écartés selon la règle déjà en usage dans `corpus_public`. Le décompte des messages est confronté à `git rev-list --count`, indépendant. Aucune `assert` nue.
- **Les échecs ne nomment jamais un marqueur** : SHA abrégé, chemin, ligne ou rang. Les fonctions de repérage sont pures, donc testables sans fiche ni Git, donc jouées en CI (`ReperageHorsFichiers`, 11 cas, dont l'exemption qui ne couvre ni une autre ligne ni un autre commit).
- **`portEstOccupe` ne tire pas une conclusion de libre d'un silence.** Seul un refus de connexion libère le port ; la sonde passe avant tout (même `/Applications`, même `mkdtempSync`), ce qui rend le refus testable sous Linux et Windows. Le cas du serveur muet comble le trou exact de l'ancienne conclusion.
- **Le journal des mises en échec** est complet (a à o), avec témoin, codes sous les deux modes, et une section « ce que les mutations ont appris » honnête, qui relève entre autres que l'ancien `cdp.js` laisse un vrai Chrome en vie sur le port d'un autre service.
- **Périmètre tenu.** `formulaire/`, `serveur/` et `CLAUDE.md` intacts ; les trois commentaires et les deux messages devenus faux sont corrigés sans toucher à la logique de relecture de largeur ; la CI ne reçoit que `fetch-depth: 0` sur le job `test` et un pas.

## Documentation à mettre à jour

- **`README.md` : rien.** Il ne mentionne ni `outils/reference-visuelle/` ni `cdp.js` ; le refus de port occupé s'explique de lui-même (le message nomme la commande `lsof -ti tcp:<port>`). Aucun guide praticien de `docs/` n'est concerné : rien n'est installé au cabinet.
- **`docs/schema-formulaire.md` et le constat `CONSTAT-2026-11-05-C1-T6b.md` : conformes** au contrat (paragraphe « Hauteur d'une grille », condition 2 à deux largeurs, phrase exacte sur les lignes de grille coupées). Les nombres du constat (seuil 735 px, 963 px) concordent entre eux et avec la spécification. Seule réserve : la mise en forme, voir le Mineur ci-dessus.
- **`CLAUDE.md` devient faux sur cinq points** (à traiter par `/cloture-projet`, non modifié ici) :
  1. Piège « Piloter Chrome… » : « `cdp.js` réutilise sans le dire un Chrome déjà en écoute sur le port 9222 » est faux depuis cette tâche ; `cdp.js` refuse tout port qui ne refuse pas la connexion, y compris un serveur muet.
  2. Piège « Le dépôt est public… » : « **rien ne garde les messages de commit ni les noms de branche** » est faux ; la garde lit désormais messages de `repère..HEAD`, noms de branches et d'étiquettes locales, valeurs `src`/`href` de la fiche et tous les blobs introduits dans la plage. Reste non couvert : les messages d'étiquettes annotées, et une image de la fiche commitée en binaire.
  3. Piège « `actions/checkout` clone à la profondeur 1 » : le job `test` clone désormais tout l'historique (`fetch-depth: 0`) ; les jobs `lint` et `scripts-windows` restent superficiels. Le piège vaut encore pour ces deux-là.
  4. Tableau d'architecture et section « Tests » : « 219 tests Python + 10 suites Node » devient **241 tests Python + 11 suites Node** (ajout de `test_cdp.js`).
  5. Tableau V2, ligne C1 : C1-T6b livrée ; `docs/ROADMAP.md` : la tâche peut être cochée (l. 485-500, trois points et la hauteur d'une grille).
- **À la fusion :** voir le Mineur sur les exemptions, qui sautent si l'historique est réécrit.

---

**Verdict : À LIVRER.** 0 Bloquant, 1 Important, 3 Mineur.
**Remarque principale :** `localiser_dans_blobs` normalise le blob 365 fois au lieu d'une (15 s mesurés contre 0,28 s une fois la normalisation sortie du générateur), ce qui alourdit chaque `npm test` du poste détenant la fiche et empirera à mesure que la plage grandit.
