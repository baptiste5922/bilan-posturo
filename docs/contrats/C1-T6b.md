# Contrat C1-T6b — Fiabiliser l'outillage et les gardes de la grille

**Chantier :** C1  **Effort estimé :** M (annoncé S par la feuille de route ; voir §7, D0)  **Date :** 2026-11-05
**Décisions bloquantes :** aucune. **DB1 et DB2 tranchées par Baptiste le
5 novembre 2026 : voie A pour chacune** (pas de crochet Git ; documenter et
borner en atelier, `script.js` intact). L'étape 9b et les critères B1-B2 ne
s'appliquent pas ; les étapes 11 et 12 se font. Les encadrés ci-dessous sont
conservés pour la trace du choix.

> **DB1 — Crochet Git pour les messages de commit (bloque l'étape 9b seulement).**
> La garde du point 3 lit les messages déjà commités : elle attrape une copie
> **avant la poussée** si les tests sont joués avant de pousser, pas avant le
> commit. Deux voies :
> - **A (recommandée)** : aucun crochet. La garde vit dans
>   `tests/test_confidentialite_prospect.py`, jouée par `npm test` ; un message
>   fautif non encore poussé se corrige par `git commit --amend`. Raison : un
>   crochet versionné ne s'active pas tout seul (`core.hooksPath` à poser dans
>   chaque clone), il y a un seul développeur, et la garde ne joue de toute façon
>   que sur le poste qui détient la fiche.
> - **B** : `outils/crochets/pre-push`, versionné, qui lance
>   `python3 -m unittest tests.test_confidentialite_prospect` et refuse la poussée
>   en cas d'échec ; activé par `git config core.hooksPath outils/crochets`,
>   documenté dans `README.md`. Coût : une étape de plus (9b) et deux critères.
>
> Le contrat est écrit pour **A**. Si Baptiste choisit B, l'étape 9b et les
> critères B1-B2 du §8 s'ajoutent ; rien d'autre ne change.
>
> **DB2 — Ce qu'on fait d'une grille plus haute qu'une page (bloque les étapes 11 et 12 seulement).**
> - **A (recommandée)** : **documenter et borner en atelier**. `essai-grille.js`
>   en `ESSAI_MODE=mesure` vérifie aussi la hauteur de chaque grille contre la
>   hauteur de page, et la condition 2 de livraison se joue en plus **à la largeur
>   de fenêtre de la tablette du client**. `formulaire/script.js` n'est pas touché.
>   Raison : la hauteur admissible dépend de la largeur de la tablette, qu'aucune
>   borne statique du schéma ne connaît, et la fiche de secours charge
>   `script.js` (risque nul en consultation avec A).
> - **B** : couper entre deux lignes de grille dans `calculerPages()`. Touche
>   `script.js`, donc la fiche de secours : contrat séparé, process Complet,
>   preuve au pixel des quatre PDF. Hors de cette tâche.
> - **C** : refuser l'export d'une grille plus haute qu'une page. **Déconseillée** :
>   c'est le scénario R1 de l'audit de C1-T6 (consultation bloquée devant le
>   patient) pour un défaut qui ne perd aucune donnée — l'image reste continue.
>
> L'étape 10 (mesure) ne dépend pas de DB2 et se fait d'abord : ses chiffres
> sont la pièce que Baptiste regarde pour trancher.

**Niveau de process :** la feuille de route dit **Allégé**. Ce contrat
recommande de le **monter à Allégé + audit**, point nommé : *la garde de
confidentialité du dépôt public* (point 3). Une fuite poussée est irréversible.
Monter est permis, descendre ne l'est pas ; non bloquant.

**Branche :** `c1-t6b-outillage`, tirée de `c1-t6-grille` (sommet `ccd75d5`).
`c1-t6-grille` est **À LIVRER** mais **non fusionnée** : `main` est à `1ec796c`.
Si elle a été fusionnée avant le début, tirer de `main` : c'est équivalent.

---

## 1. Objectif

Après cette tâche : aucun outil de rendu réel ne mesure dans un Chrome qu'il n'a
pas lancé ; le cas « options de capture identiques à `1ec796c` » est joué en CI,
et son absence y est un échec, plus un saut ; les messages de commit, les noms de
branche et d'étiquette, et les valeurs `src`/`href` de la fiche du prospect
passent sous la garde de marqueurs ; et une grille trop haute pour une page à la
largeur de la tablette du client est vue **en atelier**, mesures à l'appui.

## 2. Pourquoi

C1-T6 a ouvert le type `grille` pour le premier prospect hors pilote. Sa fiche
est faite de grilles, et son schéma sera la première tâche qui manipulera de
près un document confidentiel dans un dépôt **public** (projection : la BUSL
publie le code, pas les données d'un client). Avant ce schéma, quatre trous
laissés par l'audit et la revue de C1-T6 doivent être fermés :

1. **R2 (audit)** : un verdict « au pixel » produit dans un Chrome réutilisé à
   une largeur inconnue a déjà donné 6 pages au lieu de 3. Un verdict de rendu
   qui dépend d'un processus oublié ne prouve rien — et c'est sur ces verdicts
   que repose la promesse « la fiche de secours reste identique au pixel ».
2. **Revue, remarque 4** : le seul test qui compare l'export au vrai code
   d'avant (`1ec796c`) ne joue pas en CI. C'est le piège « clone superficiel »
   de `CLAUDE.md`, sous sa forme la plus silencieuse : un `saut -` vert.
3. **Audit, constat faible** : les messages de commit et les noms de branche
   partent sur GitHub sans garde. Une copie de la fiche dans un message serait
   publique et irréversible. Les valeurs `src`/`href` de la fiche (images
   embarquées, ancres) ne sont pas récoltées non plus.
4. **Réaudit** : sous une certaine largeur de fenêtre, une grille de 20 lignes
   dépasse une page et `calculerPages()` la coupe au milieu d'une ligne. Rien
   n'est perdu (l'image est continue), mais un bilan imprimé avec une ligne de
   tableau à cheval sur deux pages est un bilan mal présenté chez un client
   payant. Des tablettes 8 pouces ont environ 600 px de large en portrait.

Aucun de ces points ne part au cabinet. Ils conditionnent la **livraison d'une
grille chez un client**, d'où « à faire avant le premier schéma client à grille ».

## 3. État actuel

Vérifié sur `c1-t6-grille` à `ccd75d5`, arbre propre.

**Point 1 — `cdp.js` et ses appelants**
- `outils/reference-visuelle/cdp.js:40-47` : sonde `GET /json/version` ; si le
  port répond `ok`, `dejaLa = true`. `cdp.js:60` : aucun Chrome lancé dans ce
  cas, et `--window-size` (l. 55) est ignoré. **Rien n'est signalé**, et l'objet
  rendu (l. 152-153) ne dit pas si Chrome a été réutilisé.
- `cdp.js:49` crée un profil temporaire **avant** de savoir s'il servira, et
  `cdp.js:37-39` vérifie la présence de Chrome sous `/Applications` **avant** la
  sonde : sous Linux ou Windows, `ouvrirChrome` lève toujours « pas installé ».
- `cdp.js:147-150` : `fermer()` ne tue que le processus lancé (correct).
- Appelants (`grep require("./cdp.js")`) : quatre.

| Appelant | Port | Largeur imposée ? | Relue ? | Ce qui reste ouvert |
|---|---|---|---|---|
| `produire.js:257` | 9222 (défaut de `cdp.js`) | seulement si `ESSAI_LARGEUR` (l. 267-270) | oui, `relireLargeur()` l. 204-211 ; **échec seulement si `ESSAI_LARGEUR` est posé** | sans `ESSAI_LARGEUR`, un Chrome réutilisé produit à une largeur que l'outil imprime mais ne refuse pas |
| `essai-grille.js:312` | 9335 (`ESSAI_PORT_CHROME`, l. 66) | toujours (l. 322-323) | oui, échec si différente (l. 330-334) | fermé pour la largeur ; reste l'état hérité (cache, `localStorage` d'un autre profil) |
| `essai-identite.js:101` | 9334 | non | non | verdict non dépendant de la largeur, mais même réutilisation silencieuse |
| `essai-repli.js:30` | 9333 | non | non | idem ; passe en outre `ignorerCertificat: true`, option que `cdp.js` ignore (sans effet : l. 33-34 le font à la main) |

- Les commentaires `produire.js:199-200` et `essai-grille.js:40-41, 319-321`,
  et les messages d'erreur `produire.js:208-209` et `essai-grille.js:332-333`,
  décrivent la réutilisation comme un fait : ils deviendront faux.

**Point 2 — cas sauté en CI**
- `tests/test_export_grille.js:35` : `COMMIT_DE_REPERE = "1ec796c"` (abrégé).
- `tests/test_export_grille.js:409-418` : `git show` échoue → `scriptReference
  = null` → ligne `saut - …` et le cas n'est pas déclaré : il n'entre ni dans
  `nbCas`, ni dans `echecs`. Code de sortie 0.
- `.github/workflows/tests.yml:24` : `actions/checkout@v4` sans `fetch-depth`
  (profondeur 1), job `test`.
- **Effet de bord à prévoir** : `tests/test_licence.py:56-69` saute deux
  vérifications dans un clone superficiel (`COMMIT_FRONTIERE_DISPONIBLE`,
  `HISTORIQUE_COMPLET`). Avec l'historique complet, elles se mettent à jouer en
  CI, sur trois systèmes, pour la première fois. Elles passent en local (10 cas,
  vérifié le 5 novembre) ; `Path.read_text` et `text=True` normalisent les fins
  de ligne, donc la sortie CRLF de Windows ne devrait pas les gêner — à
  confirmer par la CI.
- Taille du dépôt : 70 commits, 5,1 Mio (`git count-objects -vH`) : un clone
  complet ne coûte rien. `1ec796c` est sur `origin/main` et `origin/c1-t6-grille`.

**Point 3 — garde de confidentialité**
- `tests/test_confidentialite_prospect.py:255-261` (`fichiers_modifies_ou_ajoutes`)
  ne lit que l'arbre de travail : ni messages, ni noms de référence.
- `:50-52` et `:181-193` : attributs récoltés : `id`, `class` (en jetons), `name`,
  `for`, `placeholder`, `title`, `alt`, `value`, `label`, `aria-*`, `data-*`.
  **`src` et `href` ne le sont pas**, et le cas `ExtractionDeLaFiche` l'exige
  aujourd'hui (`:357`, `:365-366` : `href="pas-recolte"` doit rester non récolté).
- Structure de la fiche, sondée sans rien en extraire que des nombres : les
  `src` sont **5 URI `data:`** (images embarquées, jusqu'à 21 874 caractères) ;
  les `href` sont **9 ancres `#…`**. Aucun lien externe.
- Sonde des messages `1ec796c..HEAD` (16 commits) contre les 352 marqueurs :
  **une** correspondance, `fbf905a144aba6895a0835c9ecc396225c2473cb`, ligne 1 —
  la collision fortuite déjà jugée par l'audit (« Faible — messages de commit »).
  Ce commit est **poussé** (`origin/c1-t6-grille`) : l'historique ne se récrit
  pas. Noms de référence (22, locaux et distants) : aucune correspondance.
- `:53-61` : la liste d'exemptions est fermée, un nouveau faux positif est
  « une décision de l'architecte, pas un réglage ».
- `:373-379` : toute la classe `AucunMarqueurDeLaFiche` saute sans la fiche,
  donc **en CI** ; elle ne joue que sur le poste qui détient la fiche.

**Point 4 — hauteur d'une grille**
- `formulaire/script.js:241-269` (`calculerPages`) : un bloc plus haut qu'une
  page est coupé net à `debut + hauteurPagePx` (l. 255-260, `console.warn`).
- `formulaire/script.js:348-368` : `hauteurPagePx = canvas.width ×
  (PDF_HAUTEUR − 2·MARGE_MM) / (PDF_LARGEUR − 2·MARGE_MM)` (constantes l. 9-11),
  soit, en px CSS, **largeur de `#form-bilan` × 273/186**. La hauteur de page
  baisse donc avec la largeur de la tablette ; la hauteur d'une grille, elle,
  ne baisse pas.
- `formulaire/moteur/rendu.js:1262-1267` : une grille **est** son bloc
  (`table#<cle du bloc>.bloc.grille`) : sa boîte est celle que lit `calculerPages`.
- Mesures du réaudit (non rejouées par ce contrat) : une grille de 20 lignes de
  texte court mesure 893 px ; la page fait 913 px à 700 px de fenêtre et passe
  sous 893 vers 680 px. Le constat C1-T6 donne 963 px pour la grille 3 de la
  donnée fictive, à 1 280 px.
- `essai-grille.js:198-228` (`scenarioMesure`) ne mesure que la largeur.
- `docs/schema-formulaire.md:437-439` évoque la coupure (« trop de lignes la
  couperait au milieu d'une ligne ») ; les conditions de livraison (l. 465-480)
  ne la vérifient pas, et l'épreuve d'atelier se joue à 1 280 px seulement
  (l. 470-473).

## 4. Périmètre

### Dans le périmètre
- `cdp.js` refuse tout port déjà occupé ; test Node qui joue partout.
- Commentaires devenus faux dans `produire.js` et `essai-grille.js`.
- `test_export_grille.js` : commit de repère complet, présence vérifiée par
  `git cat-file -e`, échec (et non saut) quand `CI` est posé.
- `fetch-depth: 0` sur le job `test` de la CI.
- `test_confidentialite_prospect.py` : récolte de `src`/`href` ; garde des
  messages `repère..HEAD` et des noms de `refs/heads` et `refs/tags` ; une
  exemption ancrée sur (commit, ligne) ; fonctions pures testées sans fiche.
- `essai-grille.js`, mode `mesure` : vérification de hauteur par grille.
- Mesure de la largeur de fenêtre seuil, consignée dans un constat.
- `docs/schema-formulaire.md` : hauteur d'une grille et condition 2 (sous DB2-A).
- Journal des mises en échec.

### Hors périmètre
- `formulaire/` tout entier, dont `script.js` et `calculerPages()` (DB2-B serait
  un autre contrat), et `serveur/`. Rien ne part au cabinet.
- Imposer ou relire la largeur dans `essai-identite.js` et `essai-repli.js`
  (verdicts non dépendants de la largeur ; le refus de `cdp.js` suffit).
- L'option fantôme `ignorerCertificat` de `essai-repli.js:30`, et le nettoyage
  des profils temporaires que `cdp.js` ne supprime jamais.
- Abaisser le seuil de 8 caractères ou élargir la liste d'exemptions des
  **fichiers** (`JETONS_TECHNIQUES_PUBLICS`).
- Scanner les messages des branches autres que `HEAD`, les notes Git, les
  descriptions de pull request et les journaux de CI.
- Le crochet Git (sauf DB1-B).
- La remarque « Important » de la revue sur la condition 2 (déjà corrigée par
  `ESSAI_MODE=mesure`, commit `5765906`), les remarques mineures 5 à 8 de la
  revue, et la tolérance de 0,5 px (déjà retirée).
- `CLAUDE.md` et la ligne d'état de C1-T6b dans `docs/ROADMAP.md` :
  `/cloture-projet` s'en charge (le piège « `cdp.js` réutilise… » y deviendra faux).
- Le schéma du prospect.

## 5. Fichiers touchés

| Fichier | Nature | Remarque |
|---|---|---|
| `outils/reference-visuelle/cdp.js` | modification | sonde déplacée en tête, refus, plus de branche de réutilisation |
| `tests/test_cdp.js` | création | Node, sans Chrome, joue sous Linux, Windows, macOS |
| `package.json` | modification | ajoute `node tests/test_cdp.js` au script `test` |
| `.github/workflows/tests.yml` | modification | `fetch-depth: 0` (job `test`) ; un pas `node tests/test_cdp.js` |
| `outils/reference-visuelle/produire.js` | modification | commentaire l. 196-203 et message l. 208-209 seulement |
| `outils/reference-visuelle/essai-grille.js` | modification | commentaires l. 39-41, 319-321 et message l. 332-333 ; vérification de hauteur en mode `mesure` |
| `tests/test_export_grille.js` | modification | l. 22-24, 35, 409-418 |
| `tests/test_confidentialite_prospect.py` | modification | voir étape 7-9 |
| `docs/schema-formulaire.md` | modification | sous DB2-A seulement |
| `docs/references-visuelles/CONSTAT-<date>-C1-T6b.md` | création | mesures de hauteur, chiffres seuls, donnée fictive |
| `docs/audits/C1-T6b-mises-en-echec.md` | création | journal des mutations, témoins, codes |

## 6. Plan d'implémentation

Règles valables à chaque étape :
- **Jamais** `serveur.py` ni `generer_autorite.py` depuis le dépôt ; bac à sable
  hors dépôt peuplé par `git ls-files -z -- serveur formulaire` (montage :
  `docs/references-visuelles/CONSTAT-2026-11-04-C1-T6.md`, « Montage »).
- **Jamais** de copie de `fiche_presentation.html`, ni d'un de ses textes, nulle
  part — avec **une seule** exception, bornée : les mutations f, g et j de
  l'étape 13 écrivent un marqueur **transitoirement** et **uniquement dans le
  clone jetable**, et seulement si ce marqueur est écrit par le pilote lui-même :
  jamais saisi à la main, jamais affiché, jamais placé dans une variable
  d'environnement ni sur une ligne de commande (visible dans `ps`) — le pilote
  le passe à `git` par l'entrée standard (`git commit -F -`) ou par un fichier
  qu'il écrit dans le clone, et crée la branche par `git update-ref` depuis
  Python avec le nom construit en mémoire. Le clone est supprimé à la fin de
  chaque mutation, au plus tard à la fin de l'étape 13. Partout ailleurs, la
  règle « nulle part » tient sans exception. Toute sonde n'imprime que des
  nombres, des empreintes de commit et des numéros de ligne.
- Mutations sur une copie `git ls-files -z --cached --others --exclude-standard`
  (ou sur le clone jetable de l'étape 9), fichier sauvegardé hors du dépôt avant
  toute mutation, restauré par `cp`. Un témoin sans mutation à chaque fois, et le
  code de retour **du test lui-même**.

**Étape 0 — Départ.** `git switch -c c1-t6b-outillage c1-t6-grille`. Vérifier
`git status --short` vide et `git diff --stat ccd75d5` vide. Relever les
compteurs : `npm test` (code 0) et `python3 -O -m unittest discover -s tests`.

**Étape 1 — `cdp.js` refuse un port occupé.** Dans `ouvrirChrome` :
1. En **tout premier**, avant la vérification de `/Applications` et avant
   `mkdtempSync` : sonder `http://127.0.0.1:<port>/json/version`. Si `fetch`
   **résout** (quel que soit le statut HTTP), lever une `Error` dont le message
   commence exactement par `Le port <port> est déjà occupé` et poursuit :
   ` (un Chrome laissé par un essai précédent ?) : cdp.js ne pilote qu'un Chrome
   qu'il a lancé lui-même, à une fenêtre connue. Fermez ce processus
   (lsof -ti tcp:<port>) ou choisissez un autre port.`
2. Supprimer `dejaLa` : `spawn` est inconditionnel.
3. Remplacer le commentaire l. 40-42 par la raison du refus (R2 de l'audit C1-T6 :
   6 pages au lieu de 3).

Bonne étape si : `grep -c "dejaLa" outils/reference-visuelle/cdp.js` → 0, et un
essai manuel avec un serveur quelconque sur le port lève le message.

**Étape 2 — `tests/test_cdp.js`.** Même harnais que `test_export_grille.js`
(`cas()`, `ok - `/`ECHEC - `, code 1 si un échec). Trois cas :
- « un port qui répond 200 sur /json/version est refusé » : serveur `http` sur
  `127.0.0.1`, port 0 ; `ouvrirChrome({ port })` rejette, message qui contient
  `Le port <port> est déjà occupé`, en moins de 5 s.
- « un port qui répond 404 est refusé aussi ».
- « aucun profil temporaire créé avant le refus » : nombre d'entrées
  `profil-chrome-*` de `os.tmpdir()` identique avant et après.
Ajouter `node tests/test_cdp.js` en fin du script `test` de `package.json`, et
un pas `Run Chrome driver refusal tests` dans le job `test` de `tests.yml`.
Bonne étape si `node tests/test_cdp.js` → 0 sous macOS, et si le test, joué sur
le `cdp.js` de `ccd75d5`, échoue (étape 13, mutation a).

**Étape 3 — Commentaires et messages devenus faux.** `produire.js:196-203` et
`essai-grille.js:39-41, 319-321` : remplacer « cdp.js réutilise… » par « cdp.js
refuse un port occupé (C1-T6b) ; la relecture reste, elle vérifie que
l'émulation de largeur a pris ». Les deux messages d'erreur qui invoquent un
Chrome réutilisé (`produire.js:208-209`, `essai-grille.js:332-333`) disent
désormais : `l'émulation de largeur n'a pas pris`. Aucune autre ligne de code
de ces deux fichiers ne change à cette étape ; la logique de relecture reste.
Bonne étape si `grep -c "réutilis"` et `grep -c "déjà en écoute"` rendent `0`
sur chacun des deux fichiers.

**Étape 4 — `test_export_grille.js`.**
1. `COMMIT_DE_REPERE = "1ec796c172bf1dcc9129bd0331fa6368edddb8c0"`.
2. Présence par `git cat-file -e <sha>^{commit}` (`execFileSync`, `stdio`
   ignoré) ; la lecture par `git show` ne se fait que si l'objet est là.
3. Objet absent **et** `process.env.CI` non vide : déclarer le cas par `cas()` et
   le faire échouer avec `commit de repère <sha court> absent alors que CI est
   posé : le clone de la CI doit porter l'historique (fetch-depth: 0)`. Objet
   absent sans `CI` : la ligne `saut - …` actuelle, inchangée.
4. En-tête l. 22-24 mis à jour.
Bonne étape si `node tests/test_export_grille.js` → 0 et affiche
`ok - sans grille : html2canvas reçoit les mêmes options`.

**Étape 5 — CI.** Dans le job `test`, `actions/checkout@v4` reçoit
`with: fetch-depth: 0`, avec un commentaire qui cite le cas et `test_licence.py`.
Les jobs `lint` et `scripts-windows` ne changent pas.

**Étape 6 — Épreuve du clone superficiel (local).**
```
D=<bloc-notes>/peu-profond
git clone --depth 1 --branch c1-t6b-outillage "file://$PWD" "$D"
(cd "$D" && node tests/test_export_grille.js); echo $?          # 0, ligne « saut - »
(cd "$D" && CI=true node tests/test_export_grille.js); echo $?  # 1, message « fetch-depth: 0 »
```
(La branche doit avoir un commit portant l'étape 4.) Et dans le dépôt :
`CI=true node tests/test_export_grille.js` → 0, cas joué.

**Étape 7 — Récolte de `src` et `href`.** Dans `_ExtracteurDeFiche.handle_starttag` :
- `src` et `href` sont récoltés **en entier** ;
- une valeur de `href` commençant par `#` est récoltée aussi **sans** le `#` ;
- une valeur commençant par `data:` est récoltée aussi pour sa partie après la
  première virgule (la charge utile seule) ;
- `style` reste non récolté.
Mettre à jour `ExtractionDeLaFiche` : `href="#une-ancre"` doit donner
`#une-ancre` et `une-ancre` ; `src="data:image/png;base64,UNECHARGE"` doit
donner la valeur entière et `UNECHARGE` ; `style="pas-recolte-non-plus"` reste
absent. Puis jouer `AucunMarqueurDeLaFiche` sur le poste : s'il rougit, c'est une
**vraie** collision à examiner (§7, D6), pas un réglage.

**Étape 8 — Fonctions pures, testables sans fiche ni Git.**
- `localiser_dans_messages(messages, marqueurs, exemptions)` : `messages` est
  une liste de `(sha_complet, texte)` ; rend la liste triée des `(sha_complet,
  numéro_de_ligne)` dont la ligne normalisée contient un marqueur, **moins** les
  couples présents dans `exemptions`. Un marqueur à cheval sur deux lignes donne
  la ligne 0 (même règle que `localiser_marqueurs`, `:279-280`).
- `localiser_dans_noms(noms, marqueurs)` : rend les **rangs** (à partir de 1)
  des noms qui contiennent un marqueur, jamais les noms.
- Nouvelle classe `ReperageHorsFichiers`, sans fiche ni Git (donc jouée en CI),
  avec au moins : un message porteur d'un marqueur est trouvé à la bonne ligne ;
  le même commit à une **autre** ligne n'est pas couvert par l'exemption d'une
  ligne ; un marqueur coupé par un saut de ligne donne la ligne 0 ; aucun élément
  rendu ne contient le marqueur (`assertNotIn` sur `repr` du résultat) ; un nom
  de branche porteur est rendu par son rang.

**Étape 9 — Messages, références et exemption.**
- `messages_de_commit()` : `git log -z --format=%H%x00%B <repère>..HEAD`,
  décodé en UTF-8 avec `errors="replace"`, découpé en `(sha, texte)`.
- `noms_de_reference()` : `git for-each-ref --format=%(refname:short)
  refs/heads refs/tags`.
- `MESSAGES_EXEMPTES = frozenset([("fbf905a144aba6895a0835c9ecc396225c2473cb", 1)])`,
  commenté : collision fortuite jugée par l'audit de C1-T6 (constat « Faible »),
  commit déjà poussé ; liste fermée, une entrée nouvelle est une décision de
  l'architecte ; le texte en cause n'est **jamais** recopié.
- Trois méthodes dans `AucunMarqueurDeLaFiche` :
  `test_aucun_marqueur_dans_les_messages_de_commit` (échec : `sha[:12]:ligne`
  seulement), `test_aucun_marqueur_dans_les_noms_de_reference` (échec : rangs
  seulement), `test_exemptions_toujours_justifiees` (chaque exemption désigne un
  commit présent dans la plage **et** une ligne qui porte encore un marqueur ;
  sinon échec « exemption sans objet », pour qu'une exemption ne survive pas à
  sa raison).
Bonne étape si `python3 -m unittest -v tests.test_confidentialite_prospect` et
la même commande sous `-O` sont vertes, nouvelles méthodes « ok » et non « skipped ».

**Étape 9b — (DB1-B seulement)** crochet `pre-push` versionné, voir l'encadré.

**Étape 10 — Mesurer (indépendante de DB2).** Dans `essai-grille.js`,
`scenarioMesure` : pour chaque grille, relever `hauteur` (boîte de
`table#<bloc>`) et `page` = largeur de `#form-bilan` × `(PDF_HAUTEUR − 2 ×
MARGE_MM) / (PDF_LARGEUR − 2 × MARGE_MM)`, constantes **lues dans la page**
(globales du `script.js` servi, comme la vérification 6 le fait déjà l. 507-511),
jamais recopiées. Ajouter, après les vérifications de largeur, une ligne par
grille : `grille k (…) : hauteur H px au plus égale à la hauteur de page P px
à cette largeur`, OK si `H <= P`. La vérification 9 garde son rang (dernière).
Puis jouer `ESSAI_MODE=mesure` sur `tests/donnees/schema-v2-grilles-fictives.json`,
bac à sable, aux largeurs **600, 640, 680, 700, 720, 768, 800, 820, 1024, 1280**,
et consigner pour chacune `innerWidth`, largeur de `#form-bilan`, `P`, `H` de
chaque grille et le verdict, dans `docs/references-visuelles/CONSTAT-<date>-C1-T6b.md`,
avec la **largeur seuil** (plus petite largeur où toutes les grilles passent).

**Étape 11 — (DB2-A) Spécification.** Dans `docs/schema-formulaire.md`, après
« **Largeur d'une grille.** », un paragraphe qui commence par
`**Hauteur d'une grille.**` : la pagination ne coupe jamais à l'intérieur d'un
bloc sauf si le bloc dépasse une page ; la hauteur de page vaut la largeur de
`#form-bilan` × 273/186 et baisse avec la largeur de la tablette ; la largeur
seuil mesurée pour la donnée fictive (étape 10) ; conséquence : une grille haute
se scinde en plusieurs blocs. Dans la condition 2 :
- épreuve d'atelier : « joué à 1 280 px **puis à la largeur de fenêtre de la
  tablette du client** (`ESSAI_LARGEUR`, relevée par `window.innerWidth` sur
  l'appareil, en portrait) » ; OK exigé pour la largeur **et la hauteur** de
  chaque grille ;
- épreuve sur la tablette : ajouter, après « montre la dernière colonne
  entière », la phrase exacte `et aucune ligne de grille n'est coupée entre deux pages`.
Garder la mise en forme : un paragraphe par rubrique (remarque 7 de la revue).

**Étape 12 — (DB2-A) Épreuve.** Rejouer `ESSAI_MODE=mesure` à 1 280 px (tout OK,
code 0) et à une largeur **sous le seuil** mesuré (au moins une ligne de hauteur
RATÉ, code 1). Consigner les deux dans le constat.

**Étape 13 — Mises en échec**, consignées dans `docs/audits/C1-T6b-mises-en-echec.md`
(mutation, fichier, témoin, code `python3`, code `python3 -O`, ce que l'échec nomme) :

| # | Mutation | Doit rougir |
|---|---|---|
| a | `cdp.js` de `ccd75d5` restauré dans une copie | `test_cdp.js`, code 1 |
| b | `mkdtempSync` replacé avant la sonde | `test_cdp.js`, cas « aucun profil » |
| c | clause `CI` retirée de `test_export_grille.js` | clone superficiel + `CI=true` → code 0 au lieu de 1 |
| d | `src`/`href` retirés de la récolte | `ExtractionDeLaFiche` |
| e | exemption élargie au commit entier (ligne ignorée) | `ReperageHorsFichiers` |
| f | commit jetable dont le message porte un marqueur | `…messages_de_commit` |
| g | branche jetable dont le nom porte un marqueur | `…noms_de_reference` |
| h | `MESSAGES_EXEMPTES` vidé | `…messages_de_commit` (sur `fbf905a…:1`) |
| i | exemption pointant un autre commit de la plage | `…exemptions_toujours_justifiees` |
| j | fichier non suivi du clone portant la charge utile **la plus courte** des `src` de la fiche | `…fichiers_changes` |
| k | comparaison de hauteur neutralisée dans une copie d'`essai-grille.js` | sous le seuil : code 0 au lieu de 1 |

Méthode pour f à j, qui exigent la fiche **et** un historique modifié : un
**clone jetable** du dépôt dans le bloc-notes (`git clone "file://$PWD" <bloc-notes>/clone`,
qui n'emporte que l'historique et les fichiers suivis), où l'on commite et crée
les branches. **Juste après le clone**, avant toute mutation :
`git -C <bloc-notes>/clone remote remove origin`, puis
`git -C <bloc-notes>/clone remote | wc -l` → `0` — sans quoi l'`origin` du
clone **est** le dépôt réel, et une poussée (manuelle ou d'un outil) y
déposerait une branche porteuse de marqueur, prête à partir sur GitHub. Ensuite ; un **pilote** Python hors dépôt qui importe le module du clone,
pose `module.FICHE` au **chemin absolu** de la fiche d'origine (`os.path.join`
rend alors ce chemin : la fiche est lue sur place, jamais copiée), lance la
classe, et vérifie par programme que la sortie ne contient pas le marqueur
choisi, en n'imprimant que `True`/`False`. Le marqueur est choisi par le pilote
(pour g : un marqueur qui satisfait `^[a-z0-9-]+$`), jamais affiché. Le clone est
supprimé à la fin de chaque mutation ; **aucun** commit, branche ni étiquette
de mutation dans le dépôt réel.

Pour j, **un fragment de la charge utile ne suffit pas** : la garde cherche
chaque marqueur **en entier** (`m in ligne`), et la charge utile d'un `src` est
récoltée comme un seul marqueur (étape 7). Un fragment ne ferait rien rougir, et
la mutation ne prouverait rien. Récolter des fragments pour l'occasion
multiplierait les collisions fortuites dans la prose (seuil de 8, audit C1-T6).
Le pilote prend donc la charge utile **entière**, mais la **plus courte** des
cinq : c'est le moins de contenu de la fiche qu'une mutation probante puisse
écrire, et il ne vit que dans le clone, le temps d'un lancement.

**Étape 14 — CI.** Pousser la branche, `env -u GITHUB_TOKEN gh workflow run
tests.yml --ref c1-t6b-outillage`, attendre la fin, relever l'identifiant.

## 7. Décisions de conception

Tranchées :
- **D0 — Effort M.** Quatre points, dont deux à mutations sur clone jetable et
  un à mesures en Chrome réel. Pas de découpage : chaque point est petit, et
  tous partagent la même condition de sortie (avant le premier schéma à grille).
- **D1 — Refuser plutôt que signaler.** La feuille de route laissait le choix.
  Un signal s'ignore ; un refus coûte une commande (`lsof -ti tcp:<port> |
  xargs kill`). La raison d'origine de la réutilisation (premier démarrage lent)
  est couverte par l'attente de 60 s de `cdp.js:62-63`.
- **D2 — Tout port qui répond est refusé**, pas seulement un Chrome : un autre
  service sur le port ferait échouer plus loin, et plus obscurément.
- **D3 — Sonde avant tout le reste** dans `ouvrirChrome` : c'est ce qui rend le
  refus testable hors macOS, donc en CI.
- **D4 — `fetch-depth: 0` plutôt qu'une récupération ciblée** : le dépôt pèse
  5 Mio ; une récupération ciblée exige un SHA complet répété dans le YAML et ne
  servirait qu'un test, alors que `test_licence.py` profite aussi de l'historique.
- **D5 — En CI, un commit de repère absent est un échec.** Sinon une
  régression de `fetch-depth` repasserait au vert en silence. Signal : la
  variable `CI`, posée par GitHub Actions sur les trois systèmes.
- **D6 — Exemption de message ancrée sur (SHA complet, ligne)**, jamais sur un
  texte : elle ne peut couvrir qu'une ligne d'un commit immuable, ne recopie
  rien, et `test_exemptions_toujours_justifiees` l'empêche de survivre à sa
  raison. Une nouvelle collision trouvée à l'étape 7 ou 9 **n'est pas exemptée
  par l'implémenteur** : il s'arrête et la remonte (fichier:ligne ou sha:ligne).
- **D7 — Plage des messages : `<repère>..HEAD`**, comme celle des fichiers.
  Noms : `refs/heads` et `refs/tags` locaux, ce qui peut être poussé.
- **D8 — Les échecs ne nomment jamais un marqueur** : fichier et ligne, SHA
  abrégé et ligne, ou rang d'une référence. Les journaux de CI sont publics.
- **D9 — Hauteur mesurée sur la boîte non réduite**, comme `calculerPages()` la
  lit (`script.js:352-357`) : c'est elle qui déclenche la coupure.
- **D10 — Rien sous `formulaire/`.** Aucun risque en consultation.

Laissés à l'implémenteur :
- La forme exacte du pilote de mutation et des noms de variables.
- Le libellé anglais du pas de CI (les autres le sont).
- Le jeu de largeurs mesurées, pourvu qu'il contienne les dix de l'étape 10.
- Factoriser ou non l'appel `git` des nouvelles fonctions avec `git()` (`:65-69`).

## 8. Critères d'acceptation

Toutes les commandes depuis la racine du dépôt, sur la branche `c1-t6b-outillage`.

**Général**
- [ ] 1. Rien sous `formulaire/` ni `serveur/` : `git diff --quiet ccd75d5 -- formulaire serveur; echo $?` → `0`.
- [ ] 2. `npm test` → code 0 ; `python3 -O -m unittest discover -s tests` → code 0.
- [ ] 3. `python3 -m pyflakes serveur/ tests/` → aucune sortie, code 0.
- [ ] 4. Aucun `assert` nu : `grep -nE '^\s*assert ' tests/test_confidentialite_prospect.py; echo $?` → `1`.
- [ ] 5. `CLAUDE.md` intact : `git diff --quiet ccd75d5 -- CLAUDE.md; echo $?` → `0`.

**Point 1**
- [ ] 6. `grep -c dejaLa outils/reference-visuelle/cdp.js` → `0`.
- [ ] 7. `node tests/test_cdp.js` → code 0, trois lignes `ok - `.
- [ ] 8. `grep -c "node tests/test_cdp.js" package.json` → `1` ; `grep -c "node tests/test_cdp.js" .github/workflows/tests.yml` → `1`.
- [ ] 9. Mutations a et b consignées, chacune code 1, témoin code 0.
- [ ] 10. `grep -c "réutilis" outils/reference-visuelle/produire.js outils/reference-visuelle/essai-grille.js` → `:0` pour chacun ; même chose avec `"déjà en écoute"`.

**Point 2**
- [ ] 11. `grep -c 1ec796c172bf1dcc9129bd0331fa6368edddb8c0 tests/test_export_grille.js` → au moins `1`, et `grep -c 'cat-file' tests/test_export_grille.js` → au moins `1`.
- [ ] 12. `awk '/^  test:/,/^  lint:/' .github/workflows/tests.yml | grep -c "fetch-depth: 0"` → `1` ; `grep -c "fetch-depth" .github/workflows/tests.yml` → `1`.
- [ ] 13. Clone superficiel (étape 6) : sans `CI`, code 0 et une ligne `saut - ` ; avec `CI=true`, code 1 et `fetch-depth: 0` dans la sortie.
- [ ] 14. Dans le dépôt : `CI=true node tests/test_export_grille.js | grep -c "^ok - sans grille : html2canvas reçoit les mêmes options"` → `1`.
- [ ] 15. CI de l'étape 14 en `success` ; `gh run view <id> --log | grep -c "saut - options de capture"` → `0` et `gh run view <id> --log | grep -c "ok - sans grille : html2canvas reçoit les mêmes options"` → `5` (une par combinaison de la matrice).
- [ ] 16. Dans le même journal, `test_mit_historique_identique_au_commit_frontiere` est `ok` et non `skipped` sous Windows.

**Point 3**
- [ ] 17. `python3 -m unittest -v tests.test_confidentialite_prospect 2>&1 | grep -cE "(messages_de_commit|noms_de_reference|exemptions_toujours_justifiees).* \.\.\. ok$"` → `3`, sur le poste qui a la fiche ; même résultat sous `python3 -O`.
- [ ] 18. `ReperageHorsFichiers` et `ExtractionDeLaFiche` jouent sans la fiche : dans le clone superficiel de l'étape 6, `python3 -m unittest -v tests.test_confidentialite_prospect 2>&1 | grep -E "(ReperageHorsFichiers|ExtractionDeLaFiche)" | grep -c skipped` → `0`.
- [ ] 19. Une seule exemption de message : `python3 -c "import sys; sys.path.insert(0, 'tests'); import test_confidentialite_prospect as t; print(len(t.MESSAGES_EXEMPTES), len(t.JETONS_TECHNIQUES_PUBLICS))"` → `1 1`.
- [ ] 20. Mutations d à j consignées : chacune code 1 sous `python3` **et** `python3 -O`, témoin code 0, et pour f, g, h, j la vérification « marqueur absent de la sortie » → `True`.
- [ ] 21. Aucune trace de mutation dans le dépôt réel : `git for-each-ref --format='%(refname)'` relevé à l'étape 0 et à la fin ne diffère que par `refs/heads/c1-t6b-outillage` (et `refs/remotes/origin/c1-t6b-outillage` après l'étape 14) — `diff <(…avant) <(…après)` ne montre aucune autre ligne, étiquettes comprises ; `git log --format=%s ccd75d5..HEAD | grep -vc '^C1-T6b'` → `0` ; le clone jetable n'existe plus (`test -d <bloc-notes>/clone; echo $?` → `1`).
- [ ] 21b. Le clone jetable n'a jamais eu de remote pendant une mutation : le journal des mises en échec consigne, pour chaque clone créé, `git -C <clone> remote | wc -l` → `0` relevé **avant** la première mutation ; et `git ls-remote origin | cut -f2`, relevé à l'étape 0 et à la fin, ne diffère que par `refs/heads/c1-t6b-outillage` (aucune autre branche ni étiquette poussée par la tâche).
- [ ] 22. La fiche n'a pas bougé : `git ls-files -z | tr '\0' '\n' | grep -c fiche_presentation` → `0` ; `git check-ignore -q fiche_presentation.html; echo $?` → `0` ; aucun fichier nommé `fiche_presentation*` hors de la racine du dépôt créé par la tâche (`find <bloc-notes> -name 'fiche_presentation*'` → vide).

**Point 4**
- [ ] 23. Le constat existe et donne, pour chacune des dix largeurs, `innerWidth`, largeur de `#form-bilan`, `P`, `H` par grille et verdict, plus une ligne « largeur seuil : N px ».
- [ ] 24. La hauteur de page n'est pas transcrite : `grep -nE "273|186|1\.46" outils/reference-visuelle/essai-grille.js; echo $?` → `1`.
- [ ] 25. Mutation k consignée : code 0 sous le seuil, témoin code 1 au même seuil ; et à 1 280 px, code 0, toutes lignes OK.
- [ ] 26. (DB2-A) `grep -c "^\*\*Hauteur d'une grille\.\*\*" docs/schema-formulaire.md` → `1` ; `grep -c "aucune ligne de grille n'est coupée entre deux pages" docs/schema-formulaire.md` → `1` ; `grep -c "largeur de fenêtre de la tablette du client" docs/schema-formulaire.md` → au moins `1`.
- [ ] 27. `python3 -m unittest tests.test_confidentialite_prospect.VocabulaireFictif` → OK (les exemples JSON de la spécification restent fictifs).

**DB1-B seulement**
- [ ] B1. `test -x outils/crochets/pre-push; echo $?` → `0`.
- [ ] B2. Dans le clone jetable, `git config core.hooksPath outils/crochets`, commit porteur d'un marqueur, `git push` vers un dépôt nu local → refusé, code ≠ 0.

## 9. Tests à écrire

| Test | Fichier | Ce qu'il doit échouer à faire passer aujourd'hui |
|---|---|---|
| port qui répond 200 refusé | `tests/test_cdp.js` | `cdp.js` de `ccd75d5` réutilise le port (macOS : expire sur `/json/list` avec un autre message ; Linux : « pas installé ») |
| port qui répond 404 refusé | `tests/test_cdp.js` | aujourd'hui `dejaLa = false`, Chrome est lancé |
| aucun profil créé avant le refus | `tests/test_cdp.js` | `mkdtempSync` l. 49 précède tout refus |
| commit de repère absent avec `CI` → échec | `tests/test_export_grille.js` | aujourd'hui `saut -`, code 0 |
| `src` et `href` récoltés | `ExtractionDeLaFiche` | `:365-366` exige l'inverse |
| repérage dans les messages, exemption ancrée à la ligne | `ReperageHorsFichiers` | fonctions absentes (`AttributeError`) |
| repérage dans les noms, rendu par rang | `ReperageHorsFichiers` | fonction absente |
| messages de commit sans marqueur | `AucunMarqueurDeLaFiche` | méthode absente ; sans exemption, rougirait sur `fbf905a…:1` |
| noms de référence sans marqueur | `AucunMarqueurDeLaFiche` | méthode absente |
| exemptions toujours justifiées | `AucunMarqueurDeLaFiche` | méthode absente |
| hauteur ≤ page (essai réel, pas en CI) | `essai-grille.js`, mode `mesure` | vérification absente : une grille coupée passe « OK » |

## 10. Points de sécurité à l'attention de l'auditeur

- **Dépôt public, document confidentiel** : la garde étendue lit la fiche du
  prospect ; vérifier qu'aucun message d'échec, aucune sonde, aucun constat ni
  journal de mutations n'en porte un texte, un intitulé ou un marqueur.
- **Exemption de message** : une seule, ancrée (SHA complet, ligne) ; vérifier
  qu'elle ne couvre ni une autre ligne ni un autre commit (mutations e, i).
- **Mutations sur historique** : faites dans un clone jetable **sans remote**
  (`origin` retiré juste après le clone, critère 21b) ; vérifier qu'aucun commit,
  branche ni étiquette porteur de marqueur n'existe dans le dépôt réel
  (`git for-each-ref`) ni sur `origin` (`git ls-remote origin`).
- **Marqueurs écrits par les mutations f, g, j** : seule exception à la règle
  « nulle part » (§6). Vérifier qu'ils n'ont existé que dans le clone, écrits par
  le pilote (entrée standard ou fichier, `update-ref`), jamais dans l'environnement,
  sur une ligne de commande, un journal, une sortie ou le bloc-notes hors du
  clone ; que le clone a été supprimé ; et que j n'a écrit que la plus courte
  des charges utiles `src`.
- **Lecture de la fiche par le pilote** : sur place, par chemin absolu ;
  vérifier qu'aucune copie de la fiche n'existe dans le bloc-notes ni dans le clone.
- **Couverture de la garde en CI** : nulle pour les marqueurs (fiche absente) ;
  c'est une limite assumée, la garde ne protège que le poste qui détient la fiche.
- **`fetch-depth: 0`** : le clone de la CI porte tout l'historique public ; aucun
  secret n'y est (contrôle « aucun secret versionné » inchangé).
- **Outillage Chrome** : `cdp.js` ne pilote plus un navigateur qu'il n'a pas
  lancé, ce qui retire aussi le risque de piloter un onglet d'un Chrome de
  travail ouvert en débogage.
- **Fichiers réels du cabinet** : jamais lus ; bacs peuplés par `git ls-files -z`.
- Données de santé, authentification, journaux du serveur, surface exposée :
  **non touchés** (critère 1).

## 11. Retour arrière

Rien de cette tâche n'est installé au cabinet : la praticienne n'a rien à faire
et aucune consultation n'est exposée (`formulaire/` et `serveur/` intacts,
critère 1). Retour arrière côté dépôt, en moins de cinq minutes :
- tout : ne pas fusionner `c1-t6b-outillage`, ou `git revert` de ses commits ;
- la CI seule (si les cas de `test_licence.py` désormais joués échouent sous un
  système) : retirer les deux lignes `with: fetch-depth: 0` ; le cas de
  `test_export_grille.js` échouera alors en CI **par construction** (D5) — c'est
  voulu ; poser `CI=` sur ce seul pas en attendant le correctif ;
- `cdp.js` : restaurer `git show ccd75d5:outils/reference-visuelle/cdp.js`.

## 12. Risques

| Risque | Probabilité | Conséquence | Parade |
|---|---|---|---|
| Les cas de `test_licence.py` débloqués par l'historique échouent sous Windows | faible | CI rouge sans régression du produit | critère 16 ; correctif minimal dans `test_licence.py` (fins de ligne) accepté dans le périmètre, ou retour arrière ciblé §11 |
| La récolte de `src`/`href` révèle une collision avec un fichier déjà changé | faible | garde rouge | D6 : s'arrêter et remonter, jamais exempter seul |
| Une mutation laisse un commit porteur de marqueur dans le dépôt réel | faible si le clone jetable est respecté | fuite publique au prochain `push` | méthode de l'étape 13 ; critère 21 ; `git ls-remote` avant toute poussée |
| Agent interrompu en pleine mutation | moyenne | `cdp.js` ou la garde laissée mutée | sauvegarde hors dépôt avant chaque mutation ; au retour, `git diff` et `git status` avant toute chose |
| `essai-grille.js` à une largeur étroite échoue sur la largeur avant la hauteur | faible | mesure illisible | la vérification de largeur compare à 1 192 px, non au conteneur : une grille réduite passe ; les deux lignes sont indépendantes |
| Un futur port fixe d'un essai entre en collision avec un autre essai lancé en parallèle | faible | refus franc au lieu d'une mesure fausse | c'est le comportement voulu (D1) |
| `CI` posé par un outil local dans un clone superficiel | très faible | échec local inattendu | message explicite ; ôter `CI` |
| Collision fortuite dans un futur message (seuil de 8) | moyenne | garde rouge sur un message non poussé | `git commit --amend` avant poussée ; une exemption reste une décision de l'architecte |
