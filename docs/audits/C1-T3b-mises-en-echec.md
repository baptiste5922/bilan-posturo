# Vérifications C1-T3b — Basculer le formulaire de production sur le moteur

**Date :** 15 octobre 2026
**Auteur :** implémenteur.
**Nature de ce document :** le journal des mises en échec délibérées exigées
par la section 6, étape 11, et les constats humains des étapes 0, 3 et 12 du
contrat `docs/contrats/C1-T3b.md`. **Ce n'est pas l'audit de sécurité
formel** — celui-ci est un document distinct, produit par l'agent
`auditeur-securite` dans une passe séparée, dans `docs/audits/C1-T3b.md`.

## 0. Préalable bloquant (étape 0, critère 1) — NON LEVÉ

Le jeu de référence visuelle de la V1 n'existe pas :
`docs/references-visuelles/` ne contient que `LISEZMOI.md`. Les quatre
fichiers attendus (`bilan-reference.json`, `V1-reference.pdf`,
`V1-reference-ecran-1.png`, `V1-reference-ecran-2.png`) n'ont pas été
produits — aucun navigateur (Chrome, Playwright, Puppeteer) n'existe dans cet
environnement de développement assisté, et cette étape ne s'obtient qu'au
navigateur, par Baptiste, sur la tablette ou un poste équivalent.

**Conséquence, assumée par Baptiste :** la bascule a été implémentée malgré
cela, sur instruction explicite. La ligne à trous de la section 6 du contrat
(« Nombre de pages du PDF de référence V1 = `____` ») reste donc **en
l'état**, volontairement : c'est la trace visible de ce préalable non levé.

## 1. Repli éprouvé avant la bascule (étape 3, critère 2) — HUMAIN, NON FAIT ICI

**Non réalisé par l'implémenteur.** Ce critère exige une tablette physique,
un favori posé sur Chrome et sur l'écran d'accueil, une saisie réelle et un
PDF constaté dans le dossier des bilans du PC du cabinet — aucune de ces
actions n'est possible dans cet environnement. Il revient à Baptiste de :

1. ouvrir `https://<adresse-du-PC>:<port>/index-v1.html` sur la tablette ;
2. l'enregistrer en favori sous le nom exact « Formulaire — secours V1 »,
   sur la barre de favoris et sur l'écran d'accueil ;
3. saisir deux champs, tracer un trait, générer un PDF, et vérifier son
   arrivée dans le dossier des bilans ;
4. consigner ici la date et le constat.

*(Date, constat — à compléter par Baptiste.)*

## 2. Les six mises en échec de l'étape 11

Toutes rejouées puis annulées, chacune vérifiée par une relecture du `diff`
(ou de l'empreinte SHA-256 pour `formulaire/index-v1.html`) avant de passer à
la suivante. Les fichiers neufs (`formulaire/index-v1.html`,
`tests/test_coquille.py`) étaient déjà dans l'index Git (`git add`) avant ces
essais — condition nécessaire pour que les contrôles qui lisent l'index
(garde d'identité, `git ls-files`) les voient réellement (défaut du
14 octobre, rappelé par la consigne de cette tâche).

### 2.1 Scénario 1 — Le groupe 6 réancré ne peut plus être vert à vide

**Geste :** retirer le bloc `section_squelettes` de `formulaire/schema.json`
(sauvegarde préalable du fichier).

**Commande :** `node tests/test_inventaire_formulaire.js`

**Résultat :**
```
1. bijection clés HTML (index-v1.html) <-> inventaire (53 clés, 45 champs) ; 29 blocs et 4 images recomptés dans le HTML, ordre des images vérifié
2. version du format dans l'en-tête
3. un exemple JSON valide par type (8 blocs analysés)
4. aucun type écarté employé dans un exemple
5. les trois retraits sont justifiés (au moins 40 caractères chacun)
ÉCHEC : id gelé(s) déclaré(s) dans la liste « Clés gelées » mais plus émis ni par la coquille (formulaire/index.html) ni par formulaire/schema.json : section_squelettes
```
Code de sortie : 1. L'`id` manquant est nommé, le test échoue bruyamment —
pas de passage « vert à vide ».

**Annulation :** fichier restauré depuis la copie de sauvegarde ; `git diff
formulaire/schema.json` vide ; `node tests/test_inventaire_formulaire.js`
revenu à 8 groupes verts.

### 2.2 Scénario 2 — Les clés gelées restent protégées (bijection V1 ↔ schéma)

**Geste :** renommer `"familliaux"` en `"familiaux"` dans
`formulaire/schema.json` (sauvegarde préalable).

**Commande :** `node tests/test_inventaire_formulaire.js`

**Résultat :**
```
6. clés gelées exhaustives (7 id attendus, conteneur #form-bilan compris)
ÉCHEC : clé(s) du formulaire absente(s) de formulaire/schema.json : familliaux
```
Code de sortie : 1. Le groupe 7 (bijection HTML `index-v1.html` ↔
`schema.json`) nomme la clé disparue.

**Annulation :** fichier restauré ; `git diff formulaire/schema.json` vide ;
suite revenue au vert.

### 2.3 Scénario 3 — Le paquet ne peut plus partir sans moteur

**Geste :** réinsertion de `rm -rf "$PAQUET/formulaire/moteur"` juste après
`cp -R formulaire serveur "$PAQUET/"` dans `outils/faire-paquet.sh`
(sauvegarde préalable du script).

**Commande :** `python3 -m unittest tests.test_paquet -v`

**Résultat (extrait) :**
```
FAIL: test_le_script_reussit
AssertionError: 1 != 0 : ERREUR : BilanPosturo-2026-10-15/formulaire/moteur/rendu.js manque dans l'archive.
Le paquet ne doit pas partir incomplet : ni sans licence, ni sans moteur de rendu ni schéma.

FAIL: test_moteur_present_dans_le_paquet
AssertionError: False is not true : le moteur de rendu manque dans le paquet : (...)

Ran 3 tests in 0.205s
FAILED (failures=2)
```
Deux échecs réels : le script lui-même refuse de produire une archive
incomplète (son propre contrôle `obligatoire`), et le test Python le
confirme indépendamment.

**Annulation :** script restauré depuis la copie de sauvegarde ; `diff`
avec la sauvegarde vide ; `python3 -m unittest tests.test_paquet` revenu à
3 tests verts.

### 2.4 Scénario 4 — `IDS_RESERVES_COQUILLE` est tenue à jour, dans les deux sens

**Geste A — ajout d'un `id` non réservé à la coquille :** insertion de
`<span id="essai"></span>` dans `formulaire/index.html`, juste après le
bouton « Choisir le dossier… » (hors de `#form-bilan`, sauvegarde préalable).

**Commande :** `python3 -m unittest tests.test_coquille.IdsReservesCoquille -v`

**Résultat :**
```
FAIL: test_ensembles_egaux_dans_les_deux_sens
AssertionError: id de la coquille non réservé(s) dans IDS_RESERVES_COQUILLE : essai

FAIL: test_vingt_et_un_ids
AssertionError: 22 != 21 : la coquille émet 22 id unique(s), 21 attendus : (...)
```
Code de sortie : 1 (deux échecs), l'`id` ajouté est nommé.

**Annulation A :** `formulaire/index.html` restauré depuis la copie de
sauvegarde ; `diff` vide.

**Geste B — retrait d'une entrée côté moteur :** suppression de
`"apercu-trait"` de la liste `IDS_RESERVES_COQUILLE` dans
`formulaire/moteur/rendu.js` (sauvegarde préalable).

**Commande :** `python3 -m unittest tests.test_coquille.IdsReservesCoquille -v`

**Résultat :**
```
FAIL: test_ensembles_egaux_dans_les_deux_sens
AssertionError: id de la coquille non réservé(s) dans IDS_RESERVES_COQUILLE : apercu-trait
```
Code de sortie : 1, l'`id` retiré est nommé dans l'autre sens.

**Annulation B :** `formulaire/moteur/rendu.js` restauré depuis la copie de
sauvegarde ; `diff` vide ; `python3 -m unittest tests.test_coquille` revenu
à 6 tests verts.

### 2.5 Scénario 5 — La fiche de secours est gelée

**Geste :** ajout d'un espace en fin de fichier `formulaire/index-v1.html`
(sauvegarde préalable).

**Commande :** `python3 -m unittest tests.test_coquille.EmpreinteDeLaFicheDeSecours -v`

**Résultat :**
```
AssertionError: '43a5f3c0f40384e42e41f6138634fab7c636b7286a6c23a06ab38cd9f6decca2' != '589eee333e68bdbde9e46c1343392e767baa5cfa6b1abfee02026d9431958a6e'
 : formulaire/index-v1.html a été modifié : ce n'est plus la V1 gelée. Le modifier n'est pas un retour arrière, c'est créer une seconde implémentation à maintenir.
```
Code de sortie : 1.

**Annulation :** fichier restauré depuis la copie de sauvegarde ;
`shasum -a 256 formulaire/index-v1.html` redonne
`589eee333e68bdbde9e46c1343392e767baa5cfa6b1abfee02026d9431958a6e` ; `diff`
vide.

### 2.6 Scénario 6 — La garde d'identité mord encore après la bascule

Le pas CI « Check that cabinet identity is not copied into the schema
documents » (`.github/workflows/tests.yml`) a été extrait dans un script
shell autonome et rejoué localement (`sh`), avec `formulaire/index.html`
(la coquille, désormais la source de la garde) comme fichier d'ancrage.
Trois sous-cas, chacun annulé avant le suivant.

**Base (avant mise en échec) :** `Aucune coordonnée du cabinet recopiée.`
— sortie 0.

**Sous-cas A — ancre renommée :** `<section id="infos_podo">` →
`<section id="infos_podo_renomme">` dans `formulaire/index.html`
(sauvegarde préalable).
```
::error::Ancre <section id="infos_podo"> introuvable dans formulaire/index.html : la garde ne peut plus localiser le bloc d'identité.
```
Code de sortie : 1. Annulé ; `diff` vide.

**Sous-cas B — ancre trouvée, contenu vidé :** le contenu de
`<section id="infos_podo">…</section>` remplacé par une section vide
(sauvegarde préalable).
```
::error::Aucune ligne de texte non vide extraite de l'ancre <section id="infos_podo"> (formulaire/index.html, lignes 90-90) : la garde n'a plus rien à contrôler.
```
Code de sortie : 1. Annulé ; `diff` vide.

**Sous-cas C — une coordonnée réelle recopiée dans le schéma :** ajout d'une
clé `"_essai_fuite": "<l'adresse postale du cabinet, ligne 73 de formulaire/index-v1.html — non recopiée ici : ce fichier part dans un dépôt public>"` à
`formulaire/schema.json` (sauvegarde préalable).
```
::error::Coordonnée du cabinet recopiée, voir formulaire/index.html ligne(s) 90-96, dans : formulaire/schema.json
```
Code de sortie : 1. **Aucune coordonnée n'apparaît dans le message** — seul
le fichier source et la plage de lignes sont nommés, comme l'exige le
contrat (le journal d'actions GitHub est public). Annulé ; `diff` vide.

**Vérification finale de ce scénario :** après les trois annulations,
`sh` sur le script extrait redonne `Aucune coordonnée du cabinet
recopiée.` (sortie 0), et `git diff --stat formulaire/schema.json` est
vide.

## 3. Vérification de clôture de l'étape 11

- Six scénarios, six échecs réels, six annulations vérifiées par `diff`
  (ou par l'empreinte SHA-256 pour `formulaire/index-v1.html`).
- `shasum -a 256 formulaire/index-v1.html` =
  `589eee333e68bdbde9e46c1343392e767baa5cfa6b1abfee02026d9431958a6e`,
  inchangée du début à la fin de ces essais.
- Suite complète rejouée après le dernier scénario : `npm test` et
  `python3 -m pyflakes serveur/ tests/` verts (voir le compte rendu de
  l'implémenteur pour le détail).

## 4. Contrôle visuel et commit unique (étape 12, critère 11) — HUMAIN, NON FAIT ICI

**Non réalisé par l'implémenteur.** Ce critère exige de rejouer
`docs/references-visuelles/bilan-reference.json` dans le formulaire rendu
par le moteur, de générer `C1-T3b-moteur.pdf` et ses deux captures, et de
les comparer à `V1-reference.pdf` — lui-même absent (section 0 ci-dessus).
Sans ce préalable, cette comparaison est **structurellement impossible** ici
et doit être faite par Baptiste, au navigateur, en particulier sur le bloc
« Empreinte encre » (tolérance (g) du comparateur) et le bloc 20, signalés
par l'audit de C1-T3 comme porteurs d'une divergence visuelle possible non
couverte par les tests automatisés.

*(Verdict, date — à compléter par Baptiste.)*

## 5. Corrections apportées après l'audit (`docs/audits/C1-T3b.md`, NON CONFORME) et la revue (`docs/revues/C1-T3b.md`, À LIVRER)

Six constats à corriger : 1 élevé, 2 moyens, 3 faibles (un quatrième faible
était hors de portée ici, voir ci-dessous), plus une remarque importante de
revue. Chaque correction est rejouée en mise en échec, puis annulée.

### 5.1 Élevée — le filet se retirait avant que l'application ait démarré

**Correctif, `formulaire/moteur/rendu.js`** : dans `demarrerMoteur()`, le
retrait de `#attente-moteur` n'a plus lieu qu'**après** vérification que
`demarrerApplication` existe ; sinon, `afficherErreurMoteur()` est appelée
comme pour tout autre échec. `afficherErreurMoteur()` elle-même ne dépend
plus uniquement d'`annoncer()` (définie par `formulaire/script.js`, le
fichier qui peut précisément manquer) : elle écrit aussi le message
directement dans `#attente-moteur` par manipulation DOM, qui ne dépend
d'aucun autre fichier.

**Nouveau test, `tests/test_demarrage_moteur.js` (création)** : double de
DOM dédié (`getElementById`, `querySelector`, `remove()`, `hidden`, absents
de `tests/outils/dom-minimal.js` par construction). Trois scénarios :

1. Nominal (schéma valide, `formulaire/script.js` présent) :
   `#attente-moteur` retiré, `demarrerApplication()` appelée.
2. **Le constat lui-même** : schéma valide, rendu réussi, mais
   `demarrerApplication`/`annoncer` indéfinies (script.js absent). Avant
   correctif : `#attente-moteur` retiré, aucun message — reproduit et
   confirmé en remettant temporairement l'ancien code en place :
   ```
   ÉCHEC : formulaire/script.js absent : #attente-moteur a été retiré alors que l'application n'a jamais démarré (régression du constat élevé, audit C1-T3b)
   ```
   (code 1). Avec le correctif : `#attente-moteur` reste présent, visible
   (`hidden === false`), et nomme le favori et l'adresse.
3. Schéma refusé (`version_schema` inconnue), `script.js` présent : le
   message annoncé par `afficherErreurMoteur()` nomme le favori et
   l'adresse.

```
node tests/test_demarrage_moteur.js
1. scénario nominal : #attente-moteur retiré, demarrerApplication() appelée
2. formulaire/script.js absent : #attente-moteur reste affiché, favori et adresse nommés
3. schéma refusé : le message annoncé nomme le favori « secours V1 » et l'adresse index-v1.html

Tout est vert.
```

Ajouté à `npm test` (`package.json`) et à `.github/workflows/tests.yml`
(« Run engine start-up safety-net tests »).

### 5.2 Moyenne n°1 — `tests/test_coquille.py` pouvait publier les coordonnées du cabinet

**Correctif** : `test_en_tete_identique_hors_espaces` compare désormais deux
empreintes SHA-256 des en-têtes normalisés, jamais les chaînes elles-mêmes.

**Mise en échec rejouée** : divergence introduite dans l'en-tête de
`formulaire/index.html` (sauvegarde préalable).
```
AssertionError: '88daaa29…' != 'e442f370…'
 : l'en-tête de la coquille a dérivé de celui de la fiche de secours (formulaire/index-v1.html) — empreintes différentes, contenu non affiché pour ne pas publier l'identité du cabinet dans ce journal
```
Seules des empreintes apparaissent dans la sortie, jamais le texte. Annulé ;
`diff` vide.

### 5.3 Moyenne n°2 — la garde d'identité était une liste fermée de cinq cibles

**Correctif, `.github/workflows/tests.yml`** : la garde scanne désormais
**tous** les fichiers suivis par git (`git ls-files -z`), à l'exception de
`formulaire/index.html` (la source) et `formulaire/index-v1.html` (sa copie
gelée, explicitement justifiée — empreinte sous garde de
`tests/test_coquille.py`). `tests/test_coquille.py` n'est plus exclu : il ne
l'a jamais eu besoin, puisqu'il ne recopie aucune coordonnée — c'est
désormais prouvé plutôt que supposé.

**Mises en échec rejouées** (fichiers indexés via `git add` au préalable,
`formulaire/index-v1.html` et `tests/test_coquille.py` compris) :

1. Les trois sous-cas d'origine (ancre renommée, contenu vidé, coordonnée
   recopiée dans `formulaire/schema.json`), tous relus avec la garde
   réécrite — identiques à la section 2.6, reconfirmés :
   ```
   ::error::Ancre <section id="infos_podo"> introuvable dans formulaire/index.html : la garde ne peut plus localiser le bloc d'identité.
   ::error::Aucune ligne de texte non vide extraite de l'ancre <section id="infos_podo"> (formulaire/index.html, lignes 90-90) : la garde n'a plus rien à contrôler.
   ::error::Coordonnée du cabinet recopiée, voir formulaire/index.html ligne(s) 90-96, dans : formulaire/schema.json
   ```
2. **La preuve que l'ancienne garde ne pouvait pas voir** : une coordonnée
   réelle insérée en commentaire dans `tests/test_coquille.py` (fichier
   jamais couvert par la liste fermée). Avec la garde réécrite :
   ```
   ::error::Coordonnée du cabinet recopiée, voir formulaire/index.html ligne(s) 90-96, dans : tests/test_coquille.py
   ```
   La garde d'avant cette correction n'aurait rien dit : `tests/test_coquille.py`
   n'était pas dans ses cinq cibles.

Les trois fichiers mutés (`formulaire/index.html`, `formulaire/schema.json`,
`tests/test_coquille.py`) ont chacun été restaurés depuis leur sauvegarde ;
`diff` vide dans les trois cas. Aucune coordonnée réelle n'a été écrite dans
ce journal : la sortie ci-dessus ne nomme que des fichiers et des lignes
sources.

### 5.4 Les quatre faibles

1. **Adresse de repli non testée** — `tests/test_comparaison_dom.js` exige
   désormais « secours V1 » **et** « index-v1.html » dans le message
   statique (pas seulement le premier) ; `tests/test_demarrage_moteur.js`
   (scénario 3) vérifie la même propriété sur le message produit par
   `afficherErreurMoteur()`. Rejoué en retirant l'adresse du message
   statique : `ÉCHEC : formulaire/index.html : le message statique
   #attente-moteur ne dirige plus vers « secours V1 » ET l'adresse
   index-v1.html…` (code 1). Annulé, `diff` vide.
2. **`docs/Mode_emploi.md`/`docs/USER-GUIDE.md` ne donnaient pas
   l'adresse** — l'encadré et la ligne d'aide-mémoire des deux documents
   nomment désormais le favori **et** `index-v1.html`.
3. **La garde de palette prétendait lire des fichiers HTML qu'elle ne lit
   jamais** — les deux fichiers HTML sont retirés de sa boucle d'existence,
   et le commentaire ne revendique plus une couverture absente ; le point
   non couvert (la pastille « Vert » du stylet, qui recopie en dur la
   couleur du token `--titre`) est nommé explicitement comme non réglé par
   cette garde, plutôt que silencieusement.
4. **Rien ne protégeait le dépôt des futures captures du jeu de
   référence** — un pas d'intégration continue non bloquant (« Remind about
   the visual reference set's confidentiality ») émet un avertissement
   GitHub si `docs/references-visuelles/` contient autre chose que
   `LISEZMOI.md`, pour rappeler la relecture du §4 avant toute fusion. Un
   refus pur et simple aurait été prématuré (ces fichiers doivent un jour
   être versionnés) : testé en ajoutant un fichier factice
   (`git add -N`) — avertissement émis, sortie 0 (non bloquant) — puis
   retiré.

### 5.5 Remarque importante de revue — commentaire périmé dans `formulaire/script.js`

Le commentaire de `demarrerApplication()` affirmait encore que
« `formulaire/index.html` porte toujours son `onclick=` » : c'est
`formulaire/index-v1.html` qui le porte depuis la bascule. Corrigé pour
nommer le bon fichier ; aucun changement de comportement.

### 5.6 Vérification finale

- Les six scénarios originaux de la section 2 ont été rejoués une seconde
  fois après toutes ces corrections, pour s'assurer qu'aucune n'a affaibli
  les gardes existantes : six échecs réels, six annulations, `diff` vide à
  chaque fois.
- `npm test` : 81 tests Python + 7 (file) + 8 (palette) + 8 (inventaire) +
  8 (comparaison DOM) + 3 (démarrage du moteur) — tous verts.
- `python3 -m pyflakes serveur/ tests/` : aucune sortie.
- `shasum -a 256 formulaire/index-v1.html` =
  `589eee333e68bdbde9e46c1343392e767baa5cfa6b1abfee02026d9431958a6e`,
  inchangée.
- `git status --short` : aucun fichier résiduel de mise en échec, aucune
  coordonnée du cabinet écrite dans ce journal.
