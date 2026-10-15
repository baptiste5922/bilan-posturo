# Jeu de référence visuelle de la V1 — à produire avant C1-T3

> **Pourquoi ce dossier existe.** Un critère d'acceptation de C1-T3 exige
> qu'« un PDF généré depuis le moteur soit superposable à un PDF de la V1 ».
> Ce PDF de la V1 ne peut être fabriqué que **tant que la V1 tourne encore** :
> C1-T3 réduit `formulaire/index.html` à une coquille, et après cette bascule
> il n'existe plus aucun moyen de l'obtenir. Produire ce jeu de référence est
> donc la dernière chose à faire avant d'attaquer le moteur, et la seule qui
> ne peut pas être rattrapée ensuite.

**À faire par Baptiste**, sur la tablette de développement ou dans Chrome à la
taille de la tablette. Compter vingt minutes, l'essentiel du temps étant la
saisie du bilan de référence. Aucun navigateur n'est disponible pendant le
développement assisté — ni Chrome, ni Playwright, ni Puppeteer — donc rien de
tout ceci ne peut être automatisé ici.

## Historique : le contrôle de C1-T2 est derrière nous

La version précédente de ce document décrivait une comparaison *avant / après*
l'extraction des couleurs en tokens (C1-T2), destinée à prouver qu'aucune
teinte n'avait bougé. **Cette comparaison n'a plus d'objet** et ne doit pas
être exécutée : le contrôle de thème du 14 octobre 2026 l'a rendue inutile.
Forcer `--fond` rend magenta le fond du formulaire à l'écran *et* la marge du
PDF ; forcer `--texte` rend rouge le texte des champs, numéro de page compris.
Les deux chemins — html2canvas pour le fond, `setTextColor` pour le texte —
sont donc validés, ce qui était le seul point de C1-T2 que rien ne permettait
de vérifier sans navigateur. Résultats détaillés dans `docs/audits/C1-T2.md`.

Il ne reste donc **qu'un seul jeu de fichiers à produire**, sur `main` tel
qu'il est aujourd'hui, sans aucun changement de branche.

## Les quatre fichiers attendus

```
docs/references-visuelles/bilan-reference.json       le bilan, rejouable
docs/references-visuelles/V1-reference.pdf           le PDF de la V1
docs/references-visuelles/V1-reference-ecran-1.png   formulaire, haut de page
docs/references-visuelles/V1-reference-ecran-2.png   formulaire, bas de page
```

C1-T3 produira plus tard ses homologues (`C1-T3-moteur.pdf`,
`C1-T3-moteur-ecran-*.png`) pour la comparaison ; ne pas s'en occuper
maintenant.

## 0. Partir d'un formulaire vide

Si le bouton « Restaurer » est visible au chargement, un brouillon traîne
d'une saisie précédente : cliquer « Restaurer », puis « Nouveau bilan » pour le
vider. Si rien ne s'affiche, il n'y a rien à faire.

## 1. Remplir le bilan de référence

**Aucune donnée patient réelle.** Nom « Témoin Référence », date de naissance
fictive — par exemple 01/01/1980. Ce dépôt est public : voir la section 4.

Le bilan doit exercer tout ce que le moteur devra savoir rendre. Remplir donc
au moins :

- un champ **texte** (nom, métier, sport…) ;
- le champ **date** (`date-bilan`, en tête du formulaire) ;
- une **case à cocher** (par exemple dans le bloc Pouls ou Podo) ;
- un **bouton radio** simple (Appui, Spin test) ;
- un radio **de tableau** (Rotation tête, Posturo dynamique) — ce sont les
  seuls champs dont la clé a une autre forme, il faut qu'ils soient couverts ;
- plusieurs **zones de texte** remplies longuement — assez pour obtenir **au
  moins trois pages** de PDF, afin que la pagination et le numéro de page
  soient dans la comparaison ;
- un **trait de stylet sur chacun des quatre schémas** : squelette gauche,
  squelette droite, squelette dos, empreintes plantaires. L'ordre compte : les
  traits sont enregistrés par position, pas par nom.

Il n'y a **aucune liste déroulante** dans ce formulaire : l'ancienne version de
ce document en demandait une, c'était une erreur.

## 2. Enregistrer le bilan saisi

Sans recharger la page, ouvrir les outils de développement (F12), onglet
Application ou Stockage → Local Storage → l'origine du formulaire. Copier la
valeur de la clé `bilan-posturo-brouillon` — une chaîne JSON — et l'enregistrer
telle quelle dans `bilan-reference.json`.

C'est ce fichier qui permettra, en C1-T3, de rejouer exactement le même bilan
dans le formulaire rendu par le moteur : on le recolle dans la même clé, puis
on clique « Restaurer ». Sans lui, les deux PDF ne sont pas comparables.

## 3. Produire le PDF et les captures

1. Cliquer « Générer le PDF », enregistrer sous `V1-reference.pdf`.
2. Capturer le formulaire rempli en deux morceaux, haut puis bas de page :
   `V1-reference-ecran-1.png` et `V1-reference-ecran-2.png`. Le bouton
   « Générer le PDF » doit être visible sur au moins l'une des deux.

Noter au passage, dans `docs/contrats/C1-T3.md` quand il existera, le nombre de
pages obtenu : c'est la première chose que la comparaison vérifiera.

## 4. Avant de verser les fichiers dans Git

**C'est le seul chemin par lequel une donnée de santé réelle pourrait entrer
dans ce dépôt**, et le dépôt est désormais public sur GitHub, sous BUSL.

- Relire `bilan-reference.json` et ouvrir `V1-reference.pdf` : le nom doit être
  « Témoin Référence », la date de naissance fictive, et aucune annotation ne
  doit évoquer un patient réel.
- **Ouvrir les deux captures PNG et les regarder.** Une capture d'écran montre
  bien plus que le formulaire : onglets du navigateur, barre de favoris,
  notification, fenêtre en arrière-plan. C'est le fichier le plus susceptible
  de contenir ce qu'on n'y cherchait pas.

En cas de doute sur un seul des quatre fichiers, recommencer la procédure
plutôt que de verser le fichier douteux. Une donnée de santé publiée ne se
reprend pas : l'historique Git la conserve même après suppression.

## Tolérance, pour mémoire

Lors de la comparaison en C1-T3 : **aucune** différence admise sur les
couleurs, les marges ou le positionnement. Seul le bruit de compression JPEG
est admis, l'export passant par `toDataURL("image/jpeg", 0.92)`
(`formulaire/script.js:276`) — il diffère à chaque génération, y compris entre
deux exports du même formulaire.
