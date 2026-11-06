# outils/atelier/ — fabriquer un client

Un opérateur d'atelier fabrique un client dans **un dossier de travail hors du
dépôt**, une commande par étape. L'outil ne voit aucune donnée de santé : il
manipule l'**identité professionnelle** et le **logo** d'un client, qui ne
doivent jamais entrer dans un dépôt public. D'où la règle qui commande tout le
reste :

> **L'atelier n'écrit jamais dans un dépôt Git.** Il refuse tout dossier de
> travail dont le chemin résolu (`realpath`), ou l'un des ancêtres, porte une
> entrée `.git` — dossier, ou fichier d'un worktree ou d'un sous-module : cela
> vaut pour **tout** arbre de travail Git, y compris un second clone de ce
> dépôt, pas seulement celui qui contient l'atelier. En seconde couche, il
> compare l'identité (périphérique + inœud) des ancêtres à la racine du dépôt de
> l'atelier, ce qui tient aussi sans `.git` (un lien, une casse différente, un
> `..` ne la contournent pas). Il n'écrit qu'une liste fermée de noms, en
> création exclusive, et ne suit aucun lien. Le refus dit « dossier situé dans un
> dépôt Git ». Aucun port n'est ouvert, aucune dépendance npm n'est ajoutée.

Ni le serveur ni le formulaire ne sont modifiés. Rien de ce dossier ne part dans
un paquet (`outils/faire-paquet.sh` copie une liste fermée).

## Prérequis

Node (le même que celui des tests) et un Python 3 (3.9 ou plus) : l'atelier
**lit** dans `serveur/serveur.py` les clés du bloc `cabinet`, la règle du logo et
le critère « praticien renseigné » au lieu de les recopier
(`outils/atelier/lire_serveur.py`, qui importe le serveur sans jamais le lancer).
L'interpréteur est cherché dans l'ordre : variable `ATELIER_PYTHON`, `python3`,
`python` ; le premier qui répond gagne. Sous Windows, `python3` peut n'être que
l'amorce du Store : elle est sautée.

## Disposition du dossier de travail

```
<travail>/
  recette.json            copie de la recette de départ, éditable
  schema.json             écrit par `composer`, puis retouché à la main
  identite-cabinet.json   les sept clés du bloc cabinet, valeurs par défaut du serveur
  images/cabinet/         le logo du client, s'il en a un
  apercu-atelier.html     réécrit à chaque `apercu`
```

`<travail>` est **obligatoire, sans défaut**, et **hors du dépôt**. Un nom de
code, jamais le nom du client. Il doit être neuf pour `ouvrir`.

## Les quatre commandes

```
A="node outils/atelier/atelier.js"
$A ouvrir   <travail> --recette templates/podologue-court.json
$A composer <travail>
$A verifier <travail>
$A apercu   <travail>
```

| Commande | Fait | Refuse |
|---|---|---|
| `ouvrir` | crée le dossier, copie la recette à l'octet, écrit l'identité vierge, crée `images/cabinet/` | un dossier existant ; un parent absent ; un dossier dans un dépôt Git ; une recette qui n'est pas du JSON ou dont les clés ne sont pas celles de la recette (rien n'est créé, le message ne cite rien du contenu) |
| `composer` | compose `recette.json` et écrit `schema.json` | d'écraser un `schema.json` : le retoucher, ou l'effacer à la main pour recomposer |
| `verifier` | schéma, identité, logo, convention de nommage ; rappels `À FAIRE` | voir ci-dessous |
| `apercu` | écrit `apercu-atelier.html` | un schéma que le moteur refuse |

Codes de sortie : **0** (rien à refuser), **1** (au moins un refus, ligne
`REFUS :` sur l'erreur standard), **2** (usage). Les lignes `À FAIRE :` ne
changent pas le code.

### Ce que `verifier` refuse

- le schéma, **par le vrai moteur** (`formulaire/moteur/rendu.js`), avertissements
  compris, et l'existence de chaque image annotable sous `formulaire/` ;
- une identité qui n'a pas **exactement** les clés du serveur, ou une valeur qui
  n'est pas une chaîne ;
- un `praticien` vide : l'export serait refusé au cabinet ;
- un logo que le serveur refuserait au démarrage, avec son motif (`absent`,
  `illisible`, `trop-volumineux`, `lien-symbolique`, `forme-invalide`…) : un logo
  se pose sous `images/cabinet/` du dossier de travail, un seul niveau ;
- une `convention_nommage` dont un `{marqueur}` est inconnu du formulaire (le
  refus dit **combien** de marqueurs sont inconnus, jamais lesquels : le texte
  des accolades est une saisie de l'opérateur). La
  liste des marqueurs est **lue dans `formulaire/script.js`** à chaque exécution ;
  si la ligne qui la définit n'est pas retrouvée exactement une fois, `verifier`
  refuse (« source illisible ») au lieu de deviner.

Les messages nomment une clé ou un motif, **jamais une valeur** d'identité : la
sortie de l'outil peut être copiée dans un échange sans exposer un courriel ou un
téléphone.

### Ce que `À FAIRE` rappelle

- **une grille** dans le schéma : l'outil ne l'éprouve pas. Trois conditions
  (`docs/schema-formulaire.md`), dont un export d'essai **sur la tablette du
  client**, à sa largeur ;
- **le logo du pilote** conservé : le confirmer avec la feuille de route du client
  (section 1) ;
- **la palette** : c'est celle du pilote (`formulaire/style.css`) ; aucun
  mécanisme ne livre la palette d'un client (décision D-O2, ouverte).

## L'aperçu n'est pas le PDF

`apercu-atelier.html` se double-clique ou s'ouvre dans Chrome (`file://`) : aucun
serveur. Il charge le **vrai moteur** et la **vraie feuille de style** du dépôt en
lecture, et rend le corps du formulaire. **Limites**, écrites aussi dans la
bannière de la page :

- pas d'en-tête du cabinet (il vient de `GET /cabinet`), pas de stylet, pas de
  PDF, pas de pagination ;
- **la largeur compte** : la bannière l'affiche. Au-delà de 1 192 px, un export
  de grille est refusé ; sous ~735 px de fenêtre, une grille de 20 lignes est
  coupée entre deux pages. Ouvrir l'aperçu à la largeur relevée sur la tablette du
  client (`window.innerWidth` sur l'appareil, en portrait) ;
- la palette est celle du pilote.

Relire l'aperçu **bloc par bloc** contre la feuille de route du client fait
partie de la fabrication (D1 du contrat C9-T2).

## Un client complet, à la sortie de l'atelier

Un dossier où `verifier` rend 0, avec : `schema.json` validé ; `identite-cabinet.json`
aux sept clés, praticien renseigné, convention valide ; le logo sous
`images/cabinet/`, ou `logo` vide, ou celui du pilote en connaissance de cause ;
un aperçu relu.

Restent des **gestes de mise en service, hors de l'atelier** : reporter l'identité
au cabinet par `python3 serveur/serveur.py --config` — **à lancer UNIQUEMENT dans le dossier d'installation du cabinet, jamais depuis le dépôt** (depuis la racine du dépôt, la commande réécrit le `config.json` réel) (`docs/configuration.md`
§2) ; poser le logo sous `formulaire/images/cabinet/` (§7) ; l'export d'essai sur
la tablette ; la palette ; le paquet (`outils/faire-paquet.sh`).

## Ce que l'atelier ne fait pas

- **Verser** un schéma dans `clients/cabinet-NN/` : le dépôt est public, et la
  question de l'endroit où vit le schéma d'un client hors pilote (D-O1) n'est pas
  tranchée. L'atelier n'a pas de commande `verser` et ne rend pas la question plus
  urgente.
- Fabriquer le paquet, installer chez un client, livrer une palette.
- Lire la feuille de route du client : c'est un document lu par l'opérateur,
  conservé **hors du dépôt**.

## Si un fichier d'identité atterrit dans le dépôt malgré tout

Ces fichiers ne peuvent y atterrir que par un geste manuel, puisque l'atelier
refuse d'y écrire. `.gitignore` ignore `identite-cabinet.json` et `apercu-atelier.html` à toute
profondeur, et le contrôle « aucun secret versionné » de la CI refuse
`identite-cabinet.json` dans l'index. `tests/test_identite_absente.py` refuse en
outre tout courriel ou téléphone dans l'arbre suivi. Ce sont des filets : la
barrière est le refus d'écrire dans le dépôt.

Essai de mesure : `docs/essais/C9-T2-fabrication.md`. Tests : `tests/test_atelier.js`.
