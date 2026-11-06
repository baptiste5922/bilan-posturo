# Revue C1-T4a — Écrire le schéma du cabinet dans le dépôt

**Date :** 2026-11-06  **Verdict :** À CORRIGER
**Tests :** exécutés par moi sur `2cbafa3` (aucun fichier suivi modifié).
- `python3 -W error::ResourceWarning -m unittest discover -s tests` : 318 tests, OK (2 sautés).
- `python3 -O -m unittest discover -s tests`, premier plan : 318 tests, OK (2 sautés).
- Les 13 suites Node, une à une (`npm test` dépasse le délai) : code 0 pour chacune, dont `test_schema_client.js` (8 cas) et `test_comparaison_dom.js`.
- `python3 -m pyflakes serveur/ tests/` : code 0.
- Au passage : lancée en arrière-plan, la suite Python échoue sur `ServeurArret.test_arret_journalise` (SIGINT ignoré, piège connu de `CLAUDE.md`) ; au premier plan, elle est verte.

Aucun défaut de code ne bloque. Le verdict tient à des **conclusions du constat plus fortes que ce qui est consigné**, à une consigne de retour arrière incomplète, et à un piège que la tâche pose à C1-T4b (G4). Tout se corrige en texte ou en quelques lignes.

## Critères d'acceptation

| N° | Vérifié par | Résultat |
|---|---|---|
| 1 | `cmp formulaire/schema.json clients/cabinet-01/schema.json` | OK (0) |
| 2 | `git ls-files clients` | OK : exactement `clients/LISEZMOI.md` et `clients/cabinet-01/schema.json` |
| 3 | `node tests/test_schema_client.js` | OK ; la sortie nomme G1 à G4 (8 cas) |
| 4 | Comparaison des lignes 55-149 de `0f33cc0:tests/test_comparaison_dom.js` avec `tests/outils/analyseur-html.js:14-106` ; suite rejouée | OK : le texte est identique, sauf un titre de section qui n'a pas suivi ; sortie de la suite verte |
| 5 | Journal `C1-T4a-mises-en-echec.md` ; rejeu de M4 (clé retirée dans les deux copies), M9 (`CLE_BROUILLON`) et de deux mutations ajoutées par moi | OK, voir « Qualité des tests » |
| 6 | Clone jetable sans `origin` : sans argument, `../formulaire`, `cabinet-01`, `unzip -p … \| cmp`, `grep -c '/clients/'` | OK : 2, 2, 0, `cmp` 0, `0` |
| 7 | 318 tests, aussi sous `-O` | OK |
| 8 | `grep -c` sur `package.json` et `tests.yml` ; 13 suites | OK : 1 et 1 |
| 9 | CI 42212161381 à `0b95515`, citée dans le journal des mutations ; les commits suivants n'ajoutent que de l'audit | OK, 7 jobs sur 7 (non rejoué par moi) |
| 10 | Constat §2 ; sorties de la session (`mesure760.out`) | **Satisfait par sa seconde branche, avec réserves** : pages égales, `comparer-pdf.js` à 0, noms d'origine égaux, `"traits":4`. `empreintes-pages.js` rend 1 sur P rempli ↔ M ; la comparaison qui rend 0 est faite contre « P restauré ». Voir Important 1 |
| 11 | Constat §3 | **Satisfait pour une paire choisie** : code 0 quand les deux exports tombent sur la même variante, 1 sinon. Le constat le dit ; ce n'est pas une propriété stable |
| 12 | Constat §6 : E1 à E7, N1 et la consigne F9. Lignes de `script.js` relues une à une | OK en lettre : chaque ligne a une source exacte et un document. F9 est incomplète, voir Important 2 |
| 13 | `git ls-files -z docs/references-visuelles` filtré ; pas CI rejoué par l'audit et dans le journal (M7) | OK |
| 14 | `python3 -m unittest tests.test_identite_absente` | OK |
| 15 | Relevés `stat` avant/après, refaits par l'audit | Non rejoué par moi (je n'ouvre pas ces fichiers) ; je m'en remets à l'audit, qui l'a refait sans rien lire |
| 16 | `git diff 0f33cc0 --stat -- formulaire/ serveur/ docs/production/` ; `git rev-parse` | OK : vide ; `d43350a0…` deux fois. Contre `main`, la commande liste `docs/production/cabinet-01.md`, ajouté avant la tâche : écart de lettre, consigné et exact |
| 17 | `git grep -c "clients/morlaix"` ; C3-T3a | OK |
| 18 | `docs/ROADMAP.md` | OK : livrée, renvoi depuis C1-T4b, `theme.json` amendé |

Périmètre : rien n'est entré hors liste. Les deux modifications de `produire.js` (lecture de `zonesDessin`, nom d'origine imprimé en mode `moteur`) sont de l'outillage et sont déclarées. L'ajout du corps de `cleChamp()` à G4 (M9 à M11) sert le même but, et il est déclaré.

## Remarques

### Important — le constat affirme la cause de la « variante B » plus fort que ses mesures
**Où :** `docs/references-visuelles/CONSTAT-2026-11-06-C1-T4a.md`, « Réponse courte », §3 (« Ce que cela prouve »), §4.
**Problème :**
- Le constat écrit que la variante B « apparaît sur … `d43350a` servi par `serveur.py`, **jamais** sur `http.server` : elle tient au couple serveur + HTTPS », puis « l'écart appartient au serveur, pas à la page ».
- Les décomptes consignés sont : `d43350a` sous `http.server` 0 B sur 7 ; `d43350a` sous `serveur.py` 2 B sur 6. Un test exact de Fisher sur ces deux séries donne p ≈ 0,19 : ce n'est pas une différence établie. Les 760 px (0 sur 3 contre 1 sur 3 et 1 sur 1) n'ajoutent presque rien. En cumulant tout, p ≈ 0,03 : un indice, pas une preuve.
- La même signature (une bande de 8 lignes, 3/255 au plus, soit une rangée de blocs JPEG) est attribuée, **à la page 1**, à l'état « rempli » contre « restauré », deux exports de `d43350a` servis par `http.server`. Une même signature a donc deux explications dans le même document. L'hypothèse la plus économique est un seul phénomène, un moment de décodage d'image non déterministe, indépendant du serveur. Le constat n'en parle pas.
- La conclusion utile **reste solide sans cette causalité** : Q montre B sur `d43350a` lui-même (2 sur 6), et les deux variantes de M-moteur sont celles de Q. B n'est donc pas une régression du moteur ni du schéma.

**Attendu :** retirer « jamais », « tient au couple serveur + HTTPS » et « l'écart appartient au serveur » de la réponse courte et du §3. Écrire : B existe aussi sur `d43350a` (Q) ; la cause n'est pas établie ; les effectifs (0/7 contre 2/6) ne séparent pas `http.server` de `serveur.py` ; la bande de la page 1 a la même signature. Faire de même dans `docs/audits/C1-T4a-mises-en-echec.md`, section « Mesure du déterminisme » (« vraie sous `http.server` et fausse sous `serveur.py` »). La consigne pour C1-T4b (comparer des ensembles de variantes) reste juste.

### Important — la consigne de retour arrière (F9) omet ce qui casse vraiment sur `d43350a`
**Où :** constat §6, « Consigne pour le retour arrière » ; contrat F9. Code : `d43350a:formulaire/script.js:775-847` contre `script.js:1396-1440`.
**Problème :**
- Sur une base IndexedDB passée en version 2, `d43350a` appelle `indexedDB.open("bilan-posturo", 1)`. L'appel échoue, et `lireReglage` **et** `ecrireReglage` échouent avec lui.
- Le constat ne retient que le premier effet : `dossierMemorise()` renvoie `null`, les PDF vont en téléchargement. « Rien ne se bloque » est vrai pour le PDF.
- Il manque le second effet : le bouton « Choisir le dossier… » ne peut plus enregistrer son choix. `choisirDossierBilans` affiche alors « Le dossier n'a pas pu être enregistré ». Après un aller-retour, la praticienne perd donc le dossier d'enregistrement de la tablette, **sans pouvoir le rétablir** tant qu'elle reste sur `d43350a`.
- Le retour arrière est le garde-fou central de C1-T4b. Sa consigne doit dire tout ce que la praticienne verra, pas seulement le sort de la file.

**Attendu :** compléter F9 avec cet effet. Écrire aussi dans la consigne si le dossier choisi se retrouve au retour sur `main` : la base v2 conserve le magasin `reglages`, mais cela n'est pas vérifié. Reporter cette phrase dans `docs/ROADMAP.md` sous C1-T4b, avec « écouler la file ».

### Important — G4 deviendra rouge à la livraison de C1-T4b, et rien ne le dit
**Où :** `tests/test_schema_client.js:244-249` (extraction de `<div id="form-bilan">` dans le blob de l'étiquette) ; `docs/production/cabinet-01.md:63` (« déplacer `production-cabinet-01` sur le nouveau commit ») ; `docs/ROADMAP.md`, section C1-T4b.
**Problème :**
- G4 lit `production-cabinet-01:formulaire/index.html` et cherche le texte `<div id="form-bilan">`. Après C1-T4b, la fiche de production demande de déplacer l'étiquette sur le commit livré, dont `index.html` est la coquille (`formulaire/index.html:85` : `<div id="form-bilan" data-moteur>`).
- Le motif n'existe plus dans ce blob : le cas G4 échoue (« fragment introuvable »), donc `npm test` et la CI rougissent sur `main`.
- La panne est bruyante (donc non mortelle), mais personne n'en est prévenu : ni `clients/LISEZMOI.md`, ni C1-T4b, ni la fiche de production. Un agent pressé réglerait la CI en affaiblissant G4.
- La sémantique de G4 est « compatible avec **ce qui est installé** ». Une fois le moteur installé, il n'y a plus de HTML écrit à la main à comparer. Ce qui reste utile est : la clé de brouillon de `d43350a` se rouvre sur la suite.

**Attendu :**
- Inscrire sous C1-T4b : « au déplacement de l'étiquette, réécrire G4 ». Deux voies : lire `d43350a` par son SHA, objet atteignable par `maintenance-cabinet-01` ; ou une seconde étiquette immobile, par exemple `production-cabinet-01-v1`, que la fiche de production ne déplace jamais. Dans les deux cas, dire que G4 ne doit pas être assoupli.
- Une ligne dans `clients/LISEZMOI.md` au même effet.
- Option : épingler dès maintenant le SHA dans le test, avec un message qui nomme l'étiquette ; le comportement d'aujourd'hui est inchangé.

### Important — la barrière D4 est détective, et deux documents disent encore de verser des images dans `docs/references-visuelles/`
**Où :** `outils/reference-visuelle/produire.js:36` (`SORTIE`, défaut `outils/reference-visuelle/sortie`) et `.gitignore` ; `docs/references-visuelles/LISEZMOI.md:30-42` et `:88-90` ; `docs/references-visuelles/MARCHE-A-SUIVRE.md:87,98,163`.
**Problème :**
- Constat 1 de l'audit, que je confirme : la sortie par défaut est dans l'arbre, aucune règle `.gitignore` ne la couvre, et la barrière CI ne lit que `docs/references-visuelles/`. Un `git add -A` après un essai sans `ESSAI_SORTIE` indexe des PNG et un PDF.
- S'ajoute une contradiction **dans le même fichier** : le §4 réécrit dit que seuls `.md` et `.json` sont versionnés, mais « Les quatre fichiers attendus » (l. 30-42) et l'étape 1 (l. 88-90) prescrivent d'enregistrer `V1-reference.pdf` et les deux PNG **dans `docs/references-visuelles/`**. `MARCHE-A-SUIVRE.md` fait de même.
- Un agent qui suit la procédure puis pousse sa branche **publie** l'image avant que la CI échoue. Le dépôt est public : le pas CI avertit, il n'empêche pas.

**Attendu :**
- Ajouter à `.gitignore` `outils/reference-visuelle/sortie/` et `docs/references-visuelles/*.png` ainsi que `*.pdf`. La barrière devient préventive ; `git add -f` reste possible, et la CI le voit.
- Corriger les deux listes et les étapes pour que la procédure écrive dans un dossier de travail hors dépôt.
- Si on préfère ne pas toucher aux procédures historiques, y ajouter un encadré « périmé depuis C1-T4a, voir §4 ».

### Mineur — `empreintes-pages.js` : en-tête périmé, et fichier absent confondu avec « différent »
**Où :** `outils/reference-visuelle/empreintes-pages.js:9-14` ; `:96` (`process.exitCode = main(…)`).
**Problème :**
- L'en-tête dit que le déterminisme « est mesuré, pas supposé : un PDF contre un second export du même brouillon doit rendre 0 ». La mesure de la tâche a montré le contraire sous `serveur.py` HTTPS (le journal le dit : « écart au contrat »). Le commentaire décrit une propriété que son auteur a infirmée.
- Un chemin de PDF inexistant lève une exception non rattrapée : code 1 et trace. C'est le code de « DIFFÈRENT ». Un `if ! node empreintes-pages.js a b; then …différent` prend une faute de frappe pour un écart de rendu. Je l'ai vérifié : `a.pdf nope.pdf` rend 1.
- Ni l'un ni l'autre n'est grave : l'outil sert au diagnostic, pas à une garde automatique.

**Attendu :** réécrire le paragraphe en « l'export n'est pas toujours déterministe (voir le constat C1-T4a §3) : comparer des ensembles ». Rattraper `ENOENT` et rendre 2, comme pour l'usage.

### Mineur — `faire-paquet.sh` laisse une archive nommée comme un paquet valide quand une pièce obligatoire manque
**Où :** `outils/faire-paquet.sh:116-125`, face à `:129-134`.
**Problème :**
- Constat 2 de l'audit, que j'ai reproduit dans un clone jetable : avec `formulaire/version.json` retiré, le script sort en 1 mais laisse `BilanPosturo-2026-11-06.zip` sur le disque.
- Le contrôle d'égalité ajouté par la tâche efface l'archive en échec. Le contrôle des pièces obligatoires voisin ne le fait pas.

**Attendu :** `rm -f "$PAQUET.zip"` avant le `exit 1` de la boucle. Un test dans `tests/test_paquet.py` peut retirer `LICENSE` de la copie et exiger l'absence de `.zip`.

### Mineur — G1 ne voit que les sous-dossiers de `clients/`
**Où :** `tests/test_schema_client.js:57-61`.
**Problème :**
- Constat 3 de l'audit. Un fichier à plat (`clients/<ville>.json`) ou un lien symbolique `clients/cabinet-02` passe G1 et G2. `faire-paquet.sh` suivrait le lien et livrerait un schéma que ni G1 ni G2 n'ont vu.
- Le `LISEZMOI` dit que le test « refuse un dossier mal nommé » : c'est exact à la lettre. La garde réelle est plus étroite que ce que laisse croire la règle « jamais d'après une ville ».

**Attendu :** lire toutes les entrées de `clients/` ; n'admettre que `LISEZMOI.md` en fichier, et exiger des vrais dossiers (`isDirectory() && !isSymbolicLink()`), avec un cas qui rougit sous mutation.

### Mineur — `outils/partager-paquet.sh:9` conseille `faire-paquet.sh` sans argument
**Où :** `outils/partager-paquet.sh:9` (« Lancez d'abord ./outils/faire-paquet.sh »).
**Problème :** quand aucune archive n'existe, le message envoie vers une commande qui sort désormais en 2. Le refus liste les clients : on s'en sort, mais l'instruction est périmée.
**Attendu :** « Lancez d'abord `./outils/faire-paquet.sh cabinet-01` ».

### Mineur — le nom d'une ville sert d'entrée refusée dans un test
**Où :** `tests/test_paquet.py:131` (`"morlaix"`) ; `docs/audits/C1-T4a-mises-en-echec.md:50` (M1).
**Problème :** la ville est déjà publique, donc aucune fuite. Mais la règle D8 (« jamais d'après une ville ») s'applique mieux avec un nom fictif, et le nom réel d'un cabinet dont le dossier existe dans l'historique n'a pas à vivre dans un test.
**Attendu :** `"ville-fictive"` ; faire de même pour M1 en rejouant ou en réécrivant la ligne du journal.

### Mineur — le constat écarte un écart d'écran par « bruit de capture » sans le chiffrer
**Où :** constat §5, « Écran 1 ».
**Problème :**
- 18 pixels d'au plus 2/255 aux coins des boutons séparent M-moteur de P restauré, et zéro sépare M-secours de P restauré. La raison avancée est qu'« un même clip, répété sur la même page, change d'empreinte d'une exécution à l'autre ».
- La raison est plausible (transition des boutons après le clic sur « Restaurer »), et l'argument des « seuls boutons identiques » la renforce. Mais le contrôle de répétition n'est donné **ni en nombre de pixels ni en écart**. C'est la forme exacte du piège « le bruit invoqué pour excuser un écart » de `CLAUDE.md` : ici, l'écart est sans effet sur le PDF et la décision n'en dépend pas.
- En revanche, la phrase « Bruit de capture, pas de changement de rendu » est une conclusion ferme sans chiffre.

**Attendu :** donner le chiffre du contrôle (pixels différents entre deux clips identiques sur la même page) ou reformuler en « non élucidé, sans effet sur le PDF ».

### Mineur — « Ce que la praticienne verra changer » ne couvre que le formulaire
**Où :** constat §6.
**Problème :**
- Le tableau est exact sur ce qu'il couvre (je l'ai vérifié ligne par ligne, voir plus bas), et utilisable par C1-T4b.
- Mais il ne dit pas que la livraison remplace aussi `serveur.py` : le bloc `cabinet` de `config.json` devient obligatoire (E3 le mentionne comme *effet*), les journaux sont purgés à six mois, `/etat` et `/sante` existent. La fiche de production liste ces points « à préparer », sans lien avec ce tableau.
- Un lecteur de C1-T4b pourrait croire que le tableau est la liste complète de ce qui change.

**Attendu :** une phrase en tête du §6 : « côté formulaire seulement ; côté PC, voir `docs/production/cabinet-01.md`, section “La prochaine livraison” ».

## Ce qui est bien fait

- **L'honnêteté méthodologique de la mesure.** Le contrat prévoyait un ordre de comparaison que le terrain a démenti. L'implémentation l'a dit, a ajouté un témoin (P restauré, puis Q), et a publié les décomptes par configuration au lieu d'un seul « identique ». Elle a refusé de réintroduire une tolérance : `empreintes-pages.js` n'a aucun seuil, et le constat rend 1 là où c'est 1. Sans le témoin Q, la variante B aurait été imputée au moteur. Les défauts que je relève plus haut portent sur la force d'une phrase, pas sur le procédé.
- **Un bogue d'outillage trouvé par la mesure.** `window.zonesDessin` n'existait pas : le rapport de restauration rendait toujours `traits: -1`, et le critère 10 était invérifiable. La correction est minimale, avec un commentaire qui explique le piège du gabarit de chaîne.
- **G4 ne cite que des clés.** Les erreurs de `git` et de l'analyseur sont remplacées par des messages sans contenu du blob, et chaque message d'échec est explicite : la CI est publique, le blob porte l'identité réelle. L'étiquette absente est un échec avec remède, jamais un saut.
- **Les gardes mordent.** J'ai rejoué des mutations dans un clone jetable sans `origin` : une clé retirée dans les deux copies fait rougir « mêmes clés » avec le nom de la clé ; `CLE_BROUILLON` modifiée fait rougir le cas dédié ; une profondeur fausse dans l'analyseur extrait fait rougir les trois cas G4. Le témoin est vert avant chaque mutation. Les cas sont chaînés pour ne pas passer à vide (`noms.length >= 1`, au moins 40 champs, quatre images, motifs uniques).
- **M4 et M6 sont les bonnes mutations.** Seul G4 les voit pendant que G3 reste vert : elles justifient l'existence de G4.
- **L'extraction de l'analyseur est fidèle.** `diff` du corps avant/après : identique au caractère près (le titre de section suivant n'a pas suivi, c'est tout).
- **`faire-paquet.sh <client>`.** Les contrôles précèdent toute copie. Le `case` juge la chaîne entière, saut de ligne compris, que `grep` seul laisserait passer. Le script relit le contenu de l'archive (`unzip -p | cmp`) au lieu de croire la copie. Rien de `clients/` ne voyage, et le test Python rend son préalable explicite (schéma du client volontairement différent du miroir).
- **Le pas CI de la barrière** : `-z`, `core.quotePath=false`, code de `grep` supérieur à 1 traité en erreur, patron du pas « palette ». Éprouvé sur un nom accentué.
- **Les numéros de ligne du tableau §6 sont exacts**, tous vérifiés : `script.js:283, 433, 460, 703, 989-1025, 1032, 1401, 1403` et, côté `d43350a`, `219`, `775` (début de `ouvrirBase`) et `835-847`. Chaque ligne distingue « mesuré » de « lu » et cite un document.
- **Un journal des mises en échec propre**, avec témoin, code du test lui-même et écarts au contrat consignés (critère 16 en lettre, prémisse du déterminisme, ajouts à G4).
- **Périmètre tenu** : `formulaire/`, `serveur/` et `docs/production/` intacts, étiquette et branche de maintenance au même SHA, aucune identité réelle dans les fichiers de la plage (`test_identite_absente` vert).

## Documentation à mettre à jour

- **`CLAUDE.md`** (je ne le modifie pas ; pour `/cloture-projet`) devient faux ou incomplet sur :
  - `tests/` : « 314 tests Python + 12 suites Node (branche `c4-t3-etat`) » devient 318 tests Python et 13 suites Node ; même chiffre à la section « Tests » (« 314 Python … 12 suites Node ») ;
  - « V2 — 17 tâches livrées » devient 18 ;
  - tableau V2 : C1 « T4 bloqué par le favori » devient « **T4a livrée**, T4b bloquée par le favori » ; la section « Reste un seul geste… C1-T4 ne peut pas commencer » vise désormais C1-T4b ;
  - `main` : « `a9b3676` » n'est plus le dernier commit ; `main` est à `48e3c43`, et `c4-t3-etat` n'est plus en attente d'y être fusionnée ;
  - architecture : `clients/` (un dossier par client, miroir de `formulaire/schema.json`), `outils/faire-paquet.sh <client>` à argument obligatoire, `tests/test_schema_client.js` ;
  - « Jalon / Architecture » : **la tâche C1-T4b doit prévenir que G4 lit l'étiquette `production-cabinet-01` et casse quand elle bouge** ;
  - pièges à ajouter : (1) la sortie de `produire.js` est dans l'arbre ; (2) une bande de 8 lignes d'au plus 3/255 sur une page de PDF est un phénomène connu et non élucidé, à comparer par ensembles de variantes ; (3) `typeof zonesDessin` et non `window.zonesDessin`.
- **`docs/references-visuelles/LISEZMOI.md` (§« Les quatre fichiers attendus », étape 1) et `MARCHE-A-SUIVRE.md`** : contradictoires avec le §4 (voir Important 4).
- **`docs/schema-formulaire.md:846,868`** : « relèvent de `theme.json` ». D3 a décidé qu'il n'existe pas et n'existera qu'avec son premier consommateur. Une note « futur » suffit ; sans conséquence tant qu'on ne cherche pas le fichier.
- **`docs/ROADMAP.md`**, sous C1-T4b : ajouter la réécriture de G4 (Important 3), l'effet « dossier » de F9 (Important 2), et corriger « Aucune décision bloquante » seulement si l'on retient une décision nouvelle ; sinon la phrase reste exacte.
- **`README.md`**, **`clients/LISEZMOI.md`**, **`docs/essais/C3-T3a-windows.md`** : à jour, rien à changer. Un point de forme : `clients/LISEZMOI.md` pourrait signaler que G4 dépend de l'étiquette (voir Important 3).
- **`docs/production/cabinet-01.md:62`** (« Fabriquer le paquet depuis cette branche ») reste exact pour `maintenance-cabinet-01`, où le script n'a pas d'argument. À préciser à la prochaine installation, pas ici.

## Suites — 6 novembre 2026

Les quatre remarques importantes et les mineures retenues sont corrigées dans
`f907c6d` (G4 lit le SHA complet de `d43350a`, F9 complétée, barrière D4
préventive par `.gitignore` et pas CI étendu, constat reformulé « cause non
établie »). La mineure sur le « bruit de capture » est consignée comme non
chiffrée, sans nouvelle mesure. Réaudit ciblé : **CONFORME**, aucun constat
(`docs/audits/C1-T4a.md`, « Réaudit après revue »). 319 tests Python et
13 suites Node verts ; CI 42236920584 verte sur 7 jobs.

**Verdict après corrections : À LIVRER.**
