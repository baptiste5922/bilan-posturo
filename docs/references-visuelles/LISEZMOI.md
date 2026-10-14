# Contrôle visuel manuel — C1-T2

> **Tant que la section 4 de cette procédure n'a pas été exécutée, pas de
> déploiement de cette tâche sur la tablette du cabinet.** Rien ne prouve
> encore que html2canvas résout `var(--fond)` dans l'iframe qu'il construit
> pour la capture : c'est la seule partie de C1-T2 qui touche réellement au
> rendu du PDF, et elle n'a pas pu être vérifiée faute de navigateur pendant
> l'implémentation.

Cette procédure vérifie ce qu'aucun test automatisé ne peut vérifier ici :
que le rendu à l'écran et le PDF produit sont **identiques au pixel** avant
et après l'extraction des couleurs en tokens CSS.

Aucun navigateur n'était disponible pendant l'implémentation (ni Chrome, ni
Playwright, ni Puppeteer) : cette procédure n'a **pas** été exécutée, et les
six fichiers qu'elle produit n'existent **pas encore**. À faire par Baptiste,
sur la tablette de développement ou dans Chrome à la taille de la tablette —
compter une dizaine de minutes.

## 0. Avant de commencer

Partir d'un formulaire vide, sans brouillon résiduel d'une saisie
précédente : si le bouton « Restaurer » est visible au chargement, cliquer
d'abord « Restaurer » puis « Nouveau bilan » pour vider ce brouillon avant de
continuer. Si rien ne s'affiche, il n'y a rien à faire.

## 1. Avant la bascule — sur le code d'avant C1-T2

Se placer sur le commit **avant** les modifications de cette tâche (avant
`68845a0`.. les commits de la branche `c1-t2-tokens-couleur`), ou sur
`main`, selon ce qui est déployé sur la tablette au moment du contrôle.

### 1.1 Remplir le bilan de référence

Un seul bilan sert de référence aux deux passages. **Aucune donnée patient
réelle** : utiliser le nom « Témoin Référence » et une date de naissance
fictive (par exemple 01/01/1980).

Remplir au moins :

- un champ texte (ex. nom, profession) ;
- un champ date (date de naissance) ;
- une case à cocher ;
- un bouton radio ;
- un champ liste déroulante, s'il y en a un dans le bloc rempli ;
- une zone de texte (`textarea`), avec assez de contenu sur plusieurs blocs
  pour obtenir **au moins trois pages** de PDF (remplir plusieurs zones de
  texte longuement, par exemple « Antécédents », « Plaintes », « Examen
  clinique ») ;
- un trait de stylet sur **chacun des quatre schémas** : squelette gauche,
  squelette droite, squelette dos, empreintes plantaires.

### 1.2 Enregistrer le bilan saisi

Sans recharger la page, ouvrir les outils de développement du navigateur
(F12), onglet Application/Stockage → Local Storage → l'origine du
formulaire. Copier la valeur de la clé `bilan-posturo-brouillon` (une chaîne
JSON) et l'enregistrer telle quelle dans :

```
docs/references-visuelles/bilan-reference.json
```

Ce fichier doit permettre de rejouer le même bilan après la bascule, en le
recollant dans la même clé avant de cliquer « Restaurer ».

### 1.3 Générer le PDF « avant »

Cliquer « Générer le PDF ». Enregistrer le fichier produit sous :

```
docs/references-visuelles/C1-T2-avant.pdf
```

### 1.4 Capturer l'écran

Capture plein écran du formulaire rempli, en deux morceaux (haut puis bas de
la page, défilement entre les deux) :

```
docs/references-visuelles/C1-T2-avant-ecran-1.png   (haut de page)
docs/references-visuelles/C1-T2-avant-ecran-2.png   (bas de page)
```

Le bouton « Générer le PDF » doit être visible sur au moins l'une des deux.

## 2. Après la bascule — sur le code de C1-T2

Basculer sur la branche `c1-t2-tokens-couleur` (ou le commit qui porte les
modifications de l'étape 6 du contrat). Vider le cache du navigateur
(Ctrl+Maj+R, ou « Actualiser » maintenu → « Vider le cache et actualiser ») :
`style.css` et `script.js` sont servis sans mise en cache par le serveur,
mais le navigateur peut avoir gardé son propre cache.

### 2.1 Rejouer le même bilan

Ouvrir les outils de développement, recoller le contenu de
`bilan-reference.json` dans la clé `bilan-posturo-brouillon` du Local
Storage, recharger la page, cliquer « Restaurer » si proposé. Le formulaire
doit réafficher exactement la même saisie qu'à l'étape 1.1 (textes, cases,
traits de stylet compris).

### 2.2 Générer le PDF « après »

Cliquer « Générer le PDF ». Enregistrer sous :

```
docs/references-visuelles/C1-T2-apres.pdf
```

### 2.3 Capturer l'écran

```
docs/references-visuelles/C1-T2-apres-ecran-1.png   (haut de page)
docs/references-visuelles/C1-T2-apres-ecran-2.png   (bas de page)
```

## 3. Comparer et consigner le verdict

Ouvrir `C1-T2-avant.pdf` et `C1-T2-apres.pdf` côte à côte, page par page.
Comparer aussi les deux paires de captures d'écran.

Tolérance : **aucune** différence sur les couleurs, les marges ou le
positionnement. Seul le bruit de compression JPEG (propre à chaque export,
`toDataURL("image/jpeg", 0.92)`) est admis.

Remplir le tableau ci-dessous, une ligne par page du PDF, puis le recopier
dans `docs/audits/C1-T2.md` avec le verdict global :

| Page | Fond identique | Texte identique | Titres identiques | Bordures identiques | Numéro de page identique | Écart constaté |
|---|---|---|---|---|---|---|
| 1 | | | | | | |
| 2 | | | | | | |
| 3 | | | | | | |

Vérifier en particulier :

- le bouton « Générer le PDF » est visuellement identique entre
  `C1-T2-avant-ecran-1.png` et `C1-T2-apres-ecran-1.png` (couleur, taille,
  position, marge de 20 px sur les quatre côtés) ;
- aucune zone du formulaire ou du PDF n'a gardé une ancienne teinte isolée
  (effet d'un littéral oublié dans le CSS).

## 4. Contrôle du changement de thème (critères d'acceptation dédiés)

Ces deux manipulations se font sur le code **après** la bascule :

1. Dans les outils de développement, éditer temporairement `formulaire/style.css`
   (ou utiliser l'inspecteur pour forcer la règle `:root`) : remplacer
   `--fond: #cec1a3` par `--fond: #ff00ff`. Recharger la page : le fond du
   formulaire **à l'écran** doit devenir magenta. Cliquer « Générer le PDF » :
   la marge du PDF généré doit aussi être magenta, sur le même document.
   Rétablir `--fond: #cec1a3` ensuite.
2. Même manipulation sur `--texte` (remplacer par une couleur vive) :
   le numéro de page du PDF généré doit changer de couleur. Rétablir
   `--texte: #3B4133` ensuite.

Consigner le résultat de ces deux manipulations dans `docs/audits/C1-T2.md`.

## 5. Avant de verser les fichiers dans Git

Cette section est le seul chemin par lequel une donnée de santé réelle
pourrait entrer dans ce dépôt public : elle porte sur les **six** fichiers
produits, pas seulement sur le JSON et les PDF.

- Relire `bilan-reference.json` et les deux PDF (`C1-T2-avant.pdf`,
  `C1-T2-apres.pdf`) ligne à ligne.
- **Ouvrir chacune des quatre captures PNG** (`C1-T2-avant-ecran-1.png`,
  `-2.png`, `C1-T2-apres-ecran-1.png`, `-2.png`) et vérifier à l'œil qu'aucun
  nom, date de naissance ou annotation réelle n'y figure — une capture
  d'écran peut montrer un onglet de navigateur, une barre de favoris ou une
  fenêtre arrière-plan qui n'apparaîtrait dans aucun des deux autres
  fichiers.

Dans tous les cas, le nom doit rester « Témoin Référence » et la date de
naissance fictive. En cas de doute sur un seul des six fichiers, recommencer
la procédure plutôt que de verser le fichier douteux.
