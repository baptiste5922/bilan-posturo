# Marche à suivre — les trois vérifications de C1-T3b

Cette fiche couvre **les trois seules choses** que la bascule du formulaire sur
le moteur ne peut pas vérifier toute seule, parce qu'elles demandent un
navigateur et un œil. Tant qu'elles ne sont pas faites, C1-T3b n'est pas livrée
et **aucun paquet ne doit partir au cabinet**.

Compter **une heure**, dont l'essentiel en saisie. À faire d'une traite : les
trois manips s'enchaînent et la deuxième réutilise ce que produit la première.

| # | Manip | Critère du contrat | Pourquoi maintenant |
|---|---|---|---|
| A | Produire le jeu de référence de la V1 | 1 | Le rendu de la V1 se dégrade dès que `style.css` ou `script.js` bougent |
| B | Éprouver la fiche de secours | 2 | On ne découvre pas un repli le jour où on en a besoin |
| C | Superposer les deux PDF | 11 | C'est la seule preuve que le moteur rend à l'identique |

## Avant de commencer

- Démarrer le serveur sur le PC du cabinet (`demarrer-serveur.bat`), et ouvrir
  le formulaire depuis la tablette, ou depuis Chrome à la taille de la tablette.
  L'adresse est celle habituelle, port **8000** par défaut, en **https**.
- Avoir les identifiants sous la main : l'authentification est demandée une
  fois par session de navigateur.
- **Partir d'un formulaire vide.** Si le bouton « Restaurer » apparaît au
  chargement, un brouillon traîne : cliquer « Restaurer », puis
  « Nouveau bilan » pour le vider.

Deux adresses à distinguer, et c'est tout l'enjeu de la soirée :

| Adresse | Ce qui s'ouvre |
|---|---|
| `…/index-v1.html` | **la V1**, le formulaire écrit à la main, gelé. C'est la fiche de secours. |
| `…/` ou `…/index.html` | **le moteur**, la coquille remplie depuis `schema.json`. |

---

## A. Produire le jeu de référence de la V1

**Sur `…/index-v1.html`** — insistons : pas sur l'adresse habituelle, qui est
désormais le moteur.

### A.1 Remplir le bilan témoin

**Aucune donnée patient réelle.** Nom **« Témoin Référence »**, date de
naissance fictive, par exemple 01/01/1980.

Le bilan doit exercer tout ce que le moteur devra savoir rendre. Remplir au
moins :

- un **champ texte** — nom, prénom, métier, sport ;
- le **champ date** en tête du formulaire ;
- une **case à cocher** — par exemple dans le bloc Pouls ou Podo ;
- un **radio simple** — Appui, ou Spin test ;
- un **radio de tableau** — Rotation tête, ou Posturo dynamique. À ne pas
  oublier : ce sont les seuls champs dont la clé de brouillon a une autre forme,
  donc le chemin le plus fragile de la restauration ;
- **plusieurs zones de texte remplies longuement**, assez pour obtenir **au
  moins trois pages** de PDF — sans quoi la pagination et le numéro de page
  n'entrent pas dans la comparaison ;
- **un trait de stylet sur chacun des quatre schémas** : squelette gauche,
  squelette droite, squelette dos, empreintes plantaires. Les traits sont
  enregistrés **par position**, donc les quatre comptent.

### A.2 Copier le brouillon

**Sans recharger la page** : F12 → onglet **Application** (ou Stockage) →
**Local Storage** → l'origine du formulaire → clé **`bilan-posturo-brouillon`**.

Copier la valeur — une longue chaîne JSON — et l'enregistrer telle quelle dans :

```
docs/references-visuelles/bilan-reference.json
```

C'est ce fichier qui permettra, en manip C, de rejouer **exactement** le même
bilan dans le formulaire du moteur. Sans lui, les deux PDF ne sont pas
comparables.

### A.3 Générer le PDF et les captures

1. Cliquer **« Générer le PDF »**, enregistrer sous
   `docs/references-visuelles/V1-reference.pdf`.
2. **Noter le nombre de pages obtenu : ______** — c'est la première chose que la
   comparaison vérifiera, et il est à reporter dans
   `docs/contrats/C1-T3b.md`, étape 0.
3. Deux captures d'écran du formulaire rempli, haut puis bas de page :
   `V1-reference-ecran-1.png` et `V1-reference-ecran-2.png`. Le bouton
   « Générer le PDF » doit être visible sur au moins l'une des deux.

### A.4 Relire avant de verser dans Git

**C'est le seul chemin par lequel une donnée de santé réelle pourrait entrer
dans ce dépôt, qui est public.**

- Rouvrir `bilan-reference.json` et `V1-reference.pdf` : le nom doit être
  « Témoin Référence », la date de naissance fictive, et aucune annotation ne
  doit évoquer un patient réel.
- **Ouvrir les deux PNG et les regarder vraiment.** Une capture montre les
  onglets du navigateur, la barre de favoris, une notification arrivée au
  mauvais moment, une fenêtre en arrière-plan.

En cas de doute sur un seul des quatre fichiers, recommencer plutôt que de
verser le fichier douteux : l'historique Git conserve ce qui y entre, même
supprimé ensuite.

---

## B. Éprouver la fiche de secours

C'est le geste qui doit fonctionner le jour où rien ne fonctionne. Il n'a de
valeur que **vérifié à froid**, pas le jour de la panne.

### B.1 Poser le favori

Sur la tablette, dans Chrome, ouvrir `…/index-v1.html` et l'enregistrer en
favori sous le nom exact :

```
Formulaire — secours V1
```

Ce nom est repris **mot pour mot** par les messages d'erreur du moteur : si
vous le changez, le message désignera un favori qui n'existe pas. Le poser aussi
sur l'écran d'accueil de la tablette, à côté du raccourci habituel.

### B.2 L'essayer pour de vrai

Depuis le favori, sur la V1 :

1. Saisir deux champs — un texte et une case suffisent.
2. Cliquer **« Générer le PDF »**.
3. **Vérifier que le PDF est bien arrivé** dans le dossier des bilans sur le PC
   du cabinet.

Si le PDF n'arrive pas, s'arrêter là et le signaler : le repli ne marche pas, et
c'est plus grave que tout le reste.

### B.3 Vérifier la reprise d'un bilan en cours

C'est la propriété qui permet de ne pas perdre une consultation :

1. Commencer un bilan **sur le moteur** (adresse habituelle), remplir deux ou
   trois champs, **ne pas** générer de PDF.
2. Toucher le favori « Formulaire — secours V1 ».
3. Cliquer **« Restaurer »** si proposé.
4. La saisie doit réapparaître — les deux pages partagent le même brouillon.

---

## C. Superposer les deux PDF

**Sur l'adresse habituelle**, celle du moteur.

1. F12 → Application → Local Storage → coller le contenu de
   `bilan-reference.json` dans la clé **`bilan-posturo-brouillon`**.
2. Recharger la page, cliquer **« Restaurer »**.
3. Vérifier d'abord que **le formulaire réaffiche la même saisie** qu'en A.1 :
   textes, cases, radios, et **les traits de stylet sur les quatre schémas, dans
   le bon ordre**. Un trait qui apparaît sur la mauvaise planche est un défaut à
   signaler immédiatement.
4. Cliquer « Générer le PDF », enregistrer sous
   `docs/references-visuelles/C1-T3-moteur.pdf`, plus deux captures
   `C1-T3-moteur-ecran-1.png` et `-2.png`.
5. Ouvrir `V1-reference.pdf` et `C1-T3-moteur.pdf` **côte à côte, page par
   page**.

### Ce qui doit être identique

- le **nombre de pages** — celui noté en A.3 ;
- les **couleurs** : fond, texte, titres, bordures ;
- les **marges** et le **positionnement** de chaque bloc ;
- le **numéro de page** ;
- les **traits de stylet**, sur la bonne planche et au bon endroit.

### Ce qui est admis

Le bruit de compression JPEG, et lui seul : l'export passe par une image
compressée à 92 %, qui diffère à chaque génération — y compris entre deux
exports du même formulaire.

### Si un écart apparaît

Ne rien corriger à la main dans le formulaire. Noter **page, zone et nature**
de l'écart, et le signaler : cela se corrige dans le schéma ou dans le moteur,
donc une fois pour tous les cabinets, pas dans un fichier HTML.

---

## Quand les trois manips sont faites

Consigner dans `docs/audits/C1-T3b.md` : la date, le nombre de pages, le
verdict de la comparaison, et le fait que le favori a été éprouvé avec un PDF
réellement arrivé. Les critères 1, 2 et 11 du contrat peuvent alors être cochés
— et **seulement alors** un paquet peut être fabriqué pour le cabinet.
