# Vérifications C1-T3 — Moteur de rendu du schéma (étapes 1 à 8)

**Date :** 15 octobre 2026
**Auteur :** implémenteur (passe étapes 1 à 8 seulement — l'étape 0 et
l'étape 9 ne sont pas levées, voir le compte rendu transmis en fin de tâche).
**Nature de ce document :** le journal des mises en échec délibérées exigées
par la section 6, étape 8 et la section 8 (critère 8) du contrat. **Ce n'est
pas l'audit de sécurité formel** — celui-ci est un document distinct, produit
par l'agent `auditeur-securite` dans une passe séparée.

## 1. Les quatre gardes de CI, mises en échec une par une, sur des fichiers indexés

Les quatre fichiers nouveaux ou modifiés par cette tâche ont été ajoutés à
l'index (`git add -N`) avant chaque essai, pour éviter le défaut du 14
octobre (un contrôle qui lit l'index Git ne voit rien sur des fichiers non
suivis).

### 1.1 Garde d'identité du cabinet (R3)

Trois scénarios, chacun rejoué puis annulé :

| Scénario | Commande | Résultat |
|---|---|---|
| Ancre `<section id="infos_podo">` renommée dans `formulaire/index.html` | `sed -i 's/id="infos_podo"/id="infos_podo_renomme"/' …` puis le pas | `::error::Ancre <section id="infos_podo"> introuvable dans formulaire/index.html : la garde ne peut plus localiser le bloc d'identité.` — code 1 |
| Ancre trouvée, mais contenu vidé (aucune ligne de texte) | contenu de la section remplacé par une section vide | `::error::Aucune ligne de texte non vide extraite de l'ancre … : la garde n'a plus rien à contrôler.` — code 1 |
| Une coordonnée réelle recopiée dans `formulaire/schema.json` | `"libelle": "Nom"` → `"libelle": "Nom: <le courriel du cabinet, ligne 74 de formulaire/index-v1.html — non recopié ici : ce dépôt est public>"` | `::error::Coordonnée du cabinet recopiée, voir formulaire/index.html ligne(s) 71-77, dans : formulaire/schema.json` — code 1, **aucune coordonnée n'apparaît dans le message** |

Dans les trois cas, les fichiers ont été restaurés immédiatement après
(`diff` vérifié identique) et `formulaire/index.html` n'a jamais été modifié
de façon persistante — son empreinte SHA-256 reste
`589eee333e68bdbde9e46c1343392e767baa5cfa6b1abfee02026d9431958a6e` tout au
long de la tâche (`shasum -a 256 formulaire/index.html`).

Ceci referme le point R3 de l'audit de C1-T1 : l'ancienne garde, ancrée sur
les numéros de ligne 72-75, devenait **verte à vide** dès qu'une ligne était
insérée au-dessus du bloc d'identité — exactement ce que l'ajout de
`formulaire/index-moteur.html` ne fait pas directement (il ne modifie pas
`index.html`), mais que l'étape 9 (bascule) ferait. La nouvelle garde échoue
plutôt que de se taire si l'ancre disparaît.

### 1.2 Garde de palette (couleurs dupliquées hors des tokens)

Fichiers lus désormais : `formulaire/style.css`, `formulaire/script.js`,
`formulaire/index.html`, **`formulaire/moteur/rendu.js`**,
**`formulaire/index-moteur.html`**.

| Scénario | Résultat |
|---|---|
| Ajout d'un commentaire `// test "#cec1a3"` dans `formulaire/moteur/rendu.js` | `714:// test "#cec1a3"` puis `::error::Couleur de palette écrite en dur hors des tokens de :root.` — code 1 |
| Ajout de `style="color:red"` sur le `<main>` de `formulaire/index-moteur.html` | ligne citée, puis `::error::Style en ligne dans formulaire/index-moteur.html : incompatible avec la CSP (C6-T1).` — code 1 |

Les deux fichiers ont été restaurés aussitôt (`diff` vérifié identique).

### 1.3 Garde des clés gelées (`tests/test_inventaire_formulaire.js`)

| Scénario | Résultat |
|---|---|
| `"familliaux"` → `"familiaux"` dans `formulaire/schema.json` (critère 4 du contrat) | `ÉCHEC : clé(s) du formulaire absente(s) de formulaire/schema.json : familliaux` — code 1 |
| Ajout de `document.getElementById('spin')` (apostrophes) dans `formulaire/script.js` (R1) | `ÉCHEC : id gelé(s) référencé(s) par script.js ou style.css mais absent(s) de la liste « Clés gelées » : spin` — code 1 |
| `<input type="text" id="nom">` → `<input type=text value="DUPOND Marie" id=>` dans une copie de `formulaire/index.html` (R2) | `ÉCHEC : attribut « id » de forme non reconnue (ni "...", ni '...', ni sans guillemet), occurrence numéro 2 de lireAttribut()` — code 1, **le texte « DUPOND Marie » n'apparaît pas dans le message** |

Les trois mutations ont été faites sur des copies ou défaites immédiatement ;
`formulaire/script.js` et `formulaire/schema.json` ont été comparés
octet pour octet à leur état d'avant mutation après restauration.

### 1.4 Garde de comparaison de DOM (`tests/test_comparaison_dom.js`)

| Scénario | Résultat |
|---|---|
| Tolérance (f) (`patient_infos` en `<section>`) désactivée dans le test | `ÉCHEC : divergence(s) hors tolérance :\n  - bloc 1 : balise « section » (V1) vs « div » (moteur)` |
| `"familliaux"` → `"familiaux"` dans `formulaire/schema.json` | `ÉCHEC : divergence(s) hors tolérance :\n  - bloc 6, champ 1 (familliaux) : id « familliaux » (V1) vs « familiaux » (moteur)` |

La garde elle-même (le test) a été restaurée et revérifiée verte après
chaque essai.

## 2. Critère 5 (champ ajouté sans JavaScript) et critère 6 (schéma cassé)

Vérifiés par `tests/test_comparaison_dom.js`, intégralement en mémoire :
`formulaire/schema.json` n'est jamais modifié pour ce test (`git diff --stat`
ne montre aucun changement sur ce fichier, ni sur aucun `.js`, à l'issue de
l'exécution de la suite complète).

```
$ node tests/test_comparaison_dom.js
1. comparaison V1 <-> moteur : 29 blocs, champs et images identiques (hors tolérances déclarées)
2. trois schémas cassés (clé racine en trop, version inconnue, type « liste ») : refusés en nommant la règle, aucun nœud inséré
3. un bloc et un champ ajoutés à schema.json (en mémoire) apparaissent dans le rendu, sans qu'aucun fichier .js ne soit modifié

Tout est vert.
```

## 3. Critère 7 (serveur et surface)

```
$ python3 -m unittest discover -s tests -v   # 70 tests, OK
$ git diff serveur/serveur.py
```
Le `diff` ne montre qu'une ligne de liste (`EXTENSIONS_SERVIES`, ajout de
`.json`) et un commentaire de trois lignes : aucun `import` ajouté.

Démontré en plus (hors liste du contrat, pour couvrir la régression que le
contrat annonce) : avec `.json` retiré de `EXTENSIONS_SERVIES`,
`test_json_du_formulaire_servi` échoue (`403 != 200`) ; avec l'ancienne
assertion stricte `403` sur `/config.json` rejouée contre le serveur corrigé,
elle échoue aussi (`404 != 403`), confirmant exactement l'effet de bord
annoncé par le contrat (section 3).

## 4. Critère 10 (non-régression)

```
$ git diff --stat tests/test_file_depots.js tests/test_palette.js
(vide)
$ node tests/test_file_depots.js   # 7 scénarios, vert
$ node tests/test_palette.js       # 8 groupes, vert
```

## 5. Ce que ce document ne couvre pas

Les critères 1 (préalable, étape 0), 3 (PDF superposable) et 9 (retour
arrière éprouvé) sont hors de portée de cette passe — voir le compte rendu
transmis à l'issue de la tâche, qui liste précisément ce qui reste à faire en
étape 9 (C1-T3b).

---

## 6. Corrections consécutives à l'audit de sécurité (`docs/audits/C1-T3.md`)

**Verdict de l'audit :** CONFORME SOUS RÉSERVE, 0 critique, 0 élevé, 6
moyens, 5 faibles. Chaque constat est corrigé ci-dessous, avec la mise en
échec déjà consignée dans la section 1 reprise ou étendue, et de nouvelles
mises en échec pour les constats 1, 2, 3 et 4, comme demandé.

### Moyen n°1 — Les blocs n'atterrissent pas dans `<main>` — **corrigé**

`rendre(schema, document, conteneur)` prend désormais l'élément qui doit
recevoir directement les blocs — en production, le `<main>` de la coquille
(résolu par `demarrerMoteur()` via `querySelector`), jamais `#form-bilan`
lui-même. `tests/test_comparaison_dom.js` construit maintenant un vrai
`<main>` côté moteur et compare la **chaîne des ancêtres** de chaque bloc
(`collecterBlocsAvecAncetres()`), pas seulement la suite plate.

Mise en échec, en revenant à l'ancien appel
(`rendre(schemaProduction, contexteMoteur.document, conteneurMoteur)` au
lieu de `mainMoteur`) :

```
$ node tests/test_comparaison_dom_mutant1.js
ÉCHEC : divergence(s) hors tolérance :
  - bloc 1 (patient_infos) : ancêtres différents — V1=[…,{"balise":"main",…}] moteur=[{"balise":"div","id":"form-bilan",…}]
  - bloc 2 … (26 lignes similaires, une par bloc du schéma)
```

Restauré, `node tests/test_comparaison_dom.js` repasse vert (8 étapes).

### Moyen n°2 — Les blocs `<table>` échappent à la comparaison des champs — **corrigé**

`extraireDetailsTable()` compare désormais le titre de la première colonne
d'en-tête, le texte des autres en-têtes, et le nom de chaque ligne, pour les
deux blocs `<table>`.

Mise en échec, rejouant exactement le scénario de l'audit (« Rotation tête »
→ « Rotation du cou », en-têtes → `["XXX","YYY"]`, « Positif » →
« POSITIF ??? ») :

```
ÉCHEC : divergence(s) hors tolérance :
  - bloc 10 (tableau) : titre « Rotation tête » (V1) vs « Rotation du cou » (moteur)
  - bloc 10 (tableau) : en-têtes de colonnes différents — V1=["Gauche(G)","Droite (D)"] moteur=["XXX","YYY"]
  - bloc 10 (tableau) : noms de ligne différents — V1=["Positif","Plus court"] moteur=["POSITIF ???","Plus court"]
```

`formulaire/schema.json` restauré, `diff` vérifié identique.

### Moyen n°3 — Champ sans `cle` rendu avec `id="undefined"` — **corrigé**

`verifierCompatibiliteBloc()` (nouvelle fonction) referme la combinatoire
type × disposition à ce que les fonctions de rendu savent construire : le
type `tableau` n'est accepté que comme unique champ de son bloc, et chaque
disposition (`en-ligne`, `atcd`, `chaussures`, `en-ligne-bas`) n'accepte que
les types dont son rendu connaît la forme.

Mise en échec, en désactivant l'appel à `verifierCompatibiliteBloc()` dans
`validerSchema()` :

```
ÉCHEC : un type « tableau » combiné à un autre champ dans le même bloc doit être refusé
```

`formulaire/moteur/rendu.js` restauré, `diff` vérifié identique.

### Moyen n°4 — Les `id` de la coquille ne sont pas réservés — **corrigé**

`IDS_RESERVES_COQUILLE` (`form-bilan`, `date-bilan`, `maintitle`, `logo`,
`infos_podo`) est désormais un jeu fermé, refusé comme `cle` de bloc, `cle`
de champ/option, ou `titre_cle`. **Écart volontaire et documenté** par
rapport à la lettre du constat : les six autres clés gelées
(`patient_infos`, `patient_info_title`, `section_squelettes`,
`section_enregistrement_plateforme`, `image_empreintes`) n'y sont **pas**
incluses — ce sont des clés que `formulaire/schema.json` doit légitimement
émettre (D2), les interdire casserait la production livrée sans rien
protéger de plus. Signalé dans le compte rendu de la tâche pour arbitrage.

Mise en échec, en vidant `IDS_RESERVES_COQUILLE` :

```
ÉCHEC : une « cle » de bloc réservée à la coquille doit être refusée
```

`formulaire/moteur/rendu.js` restauré, `diff` vérifié identique.

### Moyen n°5 — `validerSchema()` accepte ce que `rendre()` fait lever — **corrigé**

Deux corrections : (a) la règle 10 exige désormais `entetes` (tableau non
vide de chaînes non vides) pour tout champ `tableau`, fermant le
`TypeError` de `creerTable()` ; (b) `rendre()` encadre maintenant toute la
construction dans un `try/catch` et retourne `{ ok: false, erreurs }` au
lieu de laisser remonter une exception, quelle qu'en soit la cause — un
filet de sécurité au-delà des deux cas déjà connus.

Mise en échec (désactivation du contrôle `entetes`) :

```
ÉCHEC : un « tableau » sans « entetes » doit être refusé
```

Les deux schémas démontrés par l'audit (`texte` en disposition `en-ligne`,
`tableau` sans `entetes`) sont désormais vérifiés par
`tests/test_comparaison_dom.js` : `validerSchema()` les refuse, et
`rendre()` ne lève jamais (`try { rendre(...) } catch { leve = true; }`,
`leve` reste `false` dans les deux cas).

### Moyen n°6 — D8 non implémenté — **corrigé**

`avertirAttributsInconnus()` émet un `console.warn` pour toute clé
facultative inconnue d'un bloc ou d'un champ (jamais au niveau racine, où la
règle 1 reste fermée). `titre_apparence`/`titre_cle` portés par un champ
sont désormais explicitement refusés (règle 14 étendue), pas seulement
avertis.

Deux mises en échec :

```
=== avertirAttributsInconnus désactivée ===
ÉCHEC : D8 : avertissement attendu pour l'attribut de bloc inconnu « couleur »

=== refus règle 14 (champ) désactivé ===
ÉCHEC : titre_apparence porté par un champ : règle 14 attendue
```

`formulaire/moteur/rendu.js` restauré après chaque essai, `diff` vérifié
identique.

### Faible n°7 — La page provisoire voyagerait dans le paquet — **corrigé**

`outils/faire-paquet.sh` exclut désormais explicitement
`formulaire/index-moteur.html`, `formulaire/moteur/` et
`formulaire/schema.json`, et vérifie leur absence dans l'archive produite
(même patron que le contrôle `LICENSE`/`TIERS.md` déjà présent). Un
nouveau test (`tests/test_paquet.py`, 3 cas, sauté si `sh`/`zip`/`unzip`
sont indisponibles) rejoue le script sur une copie du dépôt.

Mise en échec, en retirant les trois `rm` ajoutés :

```
$ sh outils/faire-paquet.sh
ERREUR : BilanPosturo-2026-10-15/formulaire/index-moteur.html est présent dans l'archive.
La page provisoire du moteur de rendu (C1-T3) ne doit jamais partir au cabinet.
$ echo $?
1
```

### Faible n°8 — `fichier` d'une image-annotable non contraint — **corrigé**

`cheminImageAutorise()` exige un chemin relatif sous `images/`, sans `..`,
sans antislash, sans schéma d'URL ni protocole relatif. Six formes refusées
et une acceptée, vérifiées par `tests/test_comparaison_dom.js` (étape 5) :
`https://…`, `//…`, `../../../etc/passwd.png`, `/etc/passwd.png`,
`images\..\x.png`, `data:image/png;base64,…` sont toutes refusées ;
`images/essai.png` reste accepté.

### Faible n°9 — Silence si `rendu.js` ne se charge pas — **corrigé**

`formulaire/index-moteur.html` porte désormais un message statique
(`#attente-moteur`, dans `<main>`) qui ne dépend d'aucun fichier JavaScript
pour exister : il survit même si `formulaire/moteur/rendu.js` ne se charge
jamais. `demarrerMoteur()` le retire une fois le rendu réellement réussi, et
appelle `afficherErreurMoteur()` dans tous les chemins d'échec, y compris
quand `#form-bilan`/`<main>` sont introuvables.

Mise en échec (retrait du message statique) :

```
ÉCHEC : formulaire/index-moteur.html : aucun message statique #attente-moteur dirigeant vers « secours V1 » (constat n°9, audit C1-T3) — un échec de chargement de rendu.js resterait silencieux.
```

### Faible n°10 — Identité dupliquée et `onclick=` en ligne — **corrigé**

Le `onclick="exporterBilanPDF()"` de `index-moteur.html` est retiré ; le
bouton est câblé par `demarrerApplication()` (`script.js`), conditionné à
la présence de `data-moteur` pour ne jamais déclencher l'export deux fois
sur `index.html`. L'exemption de la garde d'identité pour
`index-moteur.html` est désormais écrite explicitement dans
`.github/workflows/tests.yml`, avec sa raison (c'est la source elle-même,
répétée, sous surveillance par `tests/test_comparaison_dom.js`, pas un lieu
de fuite).

Mise en échec (réintroduction de l'`onclick=`) :

```
ÉCHEC : formulaire/index-moteur.html : onclick= en ligne sur #btn-export (constat n°10, audit C1-T3).
```

### Observation n°11 — Deux messages mal rédigés — **corrigé**

`formulaire/moteur/rendu.js` : guillemet français fermé par une apostrophe
→ fermé par un guillemet français. `tests/test_comparaison_dom.js` :
« 30ᵉ bloc attendu » → « 29ᵉ bloc attendu » (28 blocs du schéma + le bloc
« essai », sans en-tête dans ce conteneur de test).

### Suite complète rejouée après toutes les corrections

```
$ npm test
… (73 Python, 7 Node file, 8 Node palette, 7 Node inventaire, 8 Node comparaison)
Ran 73 tests in …s
OK
Tout est vert.   (×4)

$ python3 -m pyflakes serveur/ tests/
(rien)

$ shasum -a 256 formulaire/index.html
589eee333e68bdbde9e46c1343392e767baa5cfa6b1abfee02026d9431958a6e  formulaire/index.html
```

`formulaire/index.html` reste intact, octet pour octet, après l'ensemble de
ces corrections.
