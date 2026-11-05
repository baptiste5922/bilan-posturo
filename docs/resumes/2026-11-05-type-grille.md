# Session des 4 et 5 novembre 2026 — Le type `grille`, et la grille qu'on ne voyait pas rognée

**Durée approximative :** une longue session, coupée une fois par la limite
d'usage.
**Tâche concernée :** C1-T6 (et C1-T6b, ouverte pour ses suites).
**Branche :** `c1-t6-grille`, poussée. **Commits :** de `e6ed95a` à `22fda9c`,
quinze en tout. Le dernier (`22fda9c`) n'est pas poussé. **`main` n'a pas
bougé** (`1ec796c`) : la fusion attend la décision de Baptiste.

## Ce qui a été fait

**C1-T6 — le type `grille`, de bout en bout de la chaîne.** Contrat,
implémentation, audit, amendement, réaudit, revue : la tâche est
**À LIVRER**, 24 critères d'acceptation vérifiés.

- **Le format de schéma passe en version 2.** Il gagne un huitième type,
  `grille` : un tableau dont chaque colonne a une nature fixe, `case` ou
  `texte-court` (8 caractères au plus). Il admet des en-têtes de colonnes
  groupés et des cellules neutralisées, jusqu'à 12 colonnes et 20 lignes. La
  clé de brouillon de chaque cellule se dérive de la grille, de la ligne et de
  la colonne. Six règles de validation nouvelles (15 à 20) dans
  `docs/schema-formulaire.md`.
- **La version 1 se rend toujours à l'identique.** Un instantané de
  sérialisation du schéma de production le garde en test, et la comparaison au
  pixel dans Chrome l'a confirmé.
- **Trois gardes de confidentialité.** La fiche de démonstration du prospect
  reprend son protocole ; le dépôt est public. `tests/test_confidentialite_prospect.py`
  vérifie qu'elle reste ignorée par Git, que les données de test n'emploient
  qu'un vocabulaire fictif (`Grille 1`, `colonne-4`…), et qu'aucun fichier du
  dépôt ne reprend un marqueur de la fiche — y compris dans les valeurs
  d'attributs, depuis l'audit. Une garde en échec nomme le fichier et la ligne,
  jamais le marqueur.
- **Amendement A1 : aucune grille rognée dans le PDF.** L'audit a trouvé
  qu'une grille valide mais large sortait du cadre de la capture et perdait ses
  dernières colonnes dans le PDF, sans un mot. Désormais `script.js` mesure
  chaque grille à l'export, réduit dans la copie capturée celle qui déborde,
  et **refuse l'export** au-delà de 1 192 px (`LARGEUR_GRILLE_REFERENCE_PX`) :
  la saisie est conservée et un message dit de prévenir le support. Tout ce
  code est inerte sans grille. La fiche de secours, qui charge le même
  `script.js`, produit toujours un PDF identique au pixel.
- **Livrer une grille chez un client est encadré.** Trois conditions, client
  par client, dans `docs/schema-formulaire.md` : la réduction livrée, un essai
  en atelier (`essai-grille.js`, mode `ESSAI_MODE=mesure`) **et** un export
  d'essai sur la tablette du client, avec ses réglages d'affichage ; enfin le
  favori de secours posé.
- **Outillage de rendu réel.** `essai-grille.js` (modes complet, refus,
  mesure) ; `produire.js` et `comparer-pixels.js` paramétrés, et `produire.js`
  vérifie désormais la largeur réelle de la fenêtre. Constat :
  `docs/references-visuelles/CONSTAT-2026-11-04-C1-T6.md`.

**Rien n'est parti au cabinet.** Le schéma de la praticienne reste en
version 1.

## Décisions prises

| Décision | Raison | Conséquence |
|---|---|---|
| **Cellules à trois états (vide, +, −) hors version 2** | La fiche s'en passe ; un état de plus touche le brouillon et le PDF | Natures `case` et `texte-court` seulement |
| **Élargir C1-T6 à `script.js`** plutôt que d'ouvrir une sous-tâche | Une grille rognée en silence est un bilan faux : la livrer sans correctif n'avait pas de sens | Amendement A1, contrat réaudité |
| **Réduire, puis refuser au-delà de 1 192 px** | Une grille réduite au-delà devient illisible ; un refus visible vaut mieux qu'un PDF faux | Message de refus, saisie conservée |
| **Une grille chez un client sous trois conditions**, dont un essai sur sa tablette | Le réaudit (R1) a montré qu'un schéma validé en atelier peut être refusé en consultation : taille du texte, zoom, largeur d'écran | Condition rejouée à chaque changement de tablette, de navigateur ou de taille de texte |
| **Garder l'ancienne copie de la fiche** dans le dossier de travail de la session du 3 novembre | Hors dépôt, sans risque de publication | Rien à faire |
| **Écarter deux remarques mineures de revue** (assistant de test écrit trois fois, deux règles CSS consécutives) | Confort sans conséquence ; fusionner les règles CSS oblige à rejouer toute la comparaison au pixel | Laissées en l'état |
| **Ouvrir C1-T6b** | Quatre suites hors périmètre : `cdp.js` qui réutilise un Chrome inconnu, un test sauté en CI faute d'historique, des messages de commit hors garde, une ligne de grille coupée entre deux pages sous ~680 px | À faire avant le premier schéma client à grille |

## État des tests

**Avant :** 219 tests Python (2 sautés hors Windows) et 10 suites Node.

**Après :** 226 tests Python, verts en mode normal et sous `-O`, et 11 suites
Node, vertes.
- `tests/test_grille.js` : 88 cas (validation, rendu, brouillon).
- `tests/test_export_grille.js` : 14 cas (mesure, réduction, refus, ordre des
  gardes de l'export, fiche de secours intacte). Un cas est sauté dans le clone
  superficiel de la CI.
- Gardes de confidentialité : 7 cas Python.

**CI :** verte sur 7 jobs sur 7 à `d84b443`. Sur 6 jobs sur 7 à `5765906` : le
job macOS 3.13 a été annulé deux fois, faute de machine chez GitHub. Ce n'est
pas un échec de test.

Chaque garde nouvelle a été mise en échec par mutation, sur copie, avec un
témoin : journal dans `docs/audits/C1-T6-mises-en-echec.md`.

## Constats de sécurité

**Audit initial : CONFORME SOUS RÉSERVE.**
- **Élevé — grille rognée dans le PDF :** fermé par l'amendement A1.
- **Moyen — la garde de marqueurs ignorait les valeurs d'attributs :** fermé
  (294 marqueurs vus, puis 352).
- **Faible — messages de commit et noms de branche hors de toute garde :**
  ouvert, reporté dans C1-T6b. Contrôle manuel : aucun marqueur.

**Réaudit : CONFORME SOUS RÉSERVE.**
- **R1, moyen — refus possible en consultation sur un schéma validé en
  atelier :** levé par la condition d'essai sur la tablette du client.
- **R2, faible — l'outillage peut mesurer à une largeur qu'il n'annonce pas :**
  `produire.js` corrigé pendant la revue ; `cdp.js` reporté dans C1-T6b.

**Revue : À LIVRER.** Aucun bloquant ; deux remarques importantes corrigées
(`ESSAI_MODE=mesure`, largeur vérifiée par `produire.js`) ; quatre mineures
corrigées sur sept.

## Ce qui reste en suspens

- **Fusion de `c1-t6-grille` sur `main`** et poussée de `22fda9c` : décision
  de Baptiste. `main` local n'est toujours pas poussé non plus.
- **C1-T6b**, avant le premier schéma client contenant une grille.
- **Le schéma du prospect lui-même** n'est pas écrit : il demande les trois
  conditions de livraison, dont un essai sur sa tablette.
- **Hérité et toujours ouvert :** le favori de secours sur la tablette du
  cabinet pilote (bloque C1-T4) ; l'essai de C3-T3a sur une VM Windows propre ;
  les questions au formateur ; l'annonce de la purge de `journal.log`.

## Prochaine étape recommandée

Fusionner la branche, une fois la décision prise, puis fermer les suites de la
grille avant d'écrire le schéma du prospect :

```
/lancer-tache C1-T6b
```

## À savoir pour la prochaine session

- **Des tests verts n'avaient pas vu la grille rognée.** Encore une fois, c'est
  la lecture du rendu réel, ici par l'auditeur, qui a trouvé le défaut. Une
  spécification affirmait même que le cas ne pouvait pas arriver.
- **Le nombre de pages du bilan témoin dépend de la largeur de fenêtre :**
  3 pages à 1 280 px, 6 vers 760 px. Les « 3 au lieu de 6 » qui ont inquiété
  l'audit venaient d'un **Chrome du 19 octobre resté ouvert sur le port 9222**,
  que `cdp.js` réutilise sans le dire. Avant tout essai de rendu, vérifier
  qu'aucun Chrome n'écoute déjà sur ce port.
- **La fiche de secours charge `script.js`.** Toute modification de
  `script.js` doit prouver que le PDF de la fiche V1 reste identique au pixel.
- **`npm test` dépasse le délai de deux minutes d'une commande** (181 s pour la
  seule partie Python au 5 novembre) : la lancer en arrière-plan. La garde de
  confidentialité a pris une fois 442 s, puis 7,6 s le lendemain, avec la garde
  d'identité : cause non élucidée, sans doute la charge de la machine à ce
  moment-là.
- **La garde a mordu sur le code de l'implémenteur** : clés fictives et
  `aria-label` y ressemblaient à des marqueurs. Deux exemptions ancrées, jugées
  saines par l'audit et la revue ; une collision fortuite connue subsiste.
- **Le dépôt est public, et rien ne garde encore les messages de commit.** Ne
  jamais nommer un élément de la fiche du prospect dans un commit, une branche,
  un audit ou une revue.
- **Le planificateur, coupé par la limite d'usage, a repris par `SendMessage`**
  sans perte, contrat vérifié inchangé avant la reprise.
