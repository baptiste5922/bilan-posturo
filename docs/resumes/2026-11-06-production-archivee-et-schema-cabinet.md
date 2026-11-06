# Session du 6 novembre 2026 (2) — La production archivée, et le schéma du cabinet mesuré contre elle

**Durée approximative :** une demi-journée.
**Tâches concernées :** C1-T4 (scindée), C1-T4a ; fusion de C4-T3.
**Branche :** `c1-t4a-schema-cabinet`, tirée de `main` à `48e3c43`.
**Commits :** de `0f33cc0` à `f70f948`, tous poussés sauf le dernier ;
**branche non fusionnée**. `main` est à `48e3c43`, poussé, CI verte
(`42203299148`).

## Ce qui a été fait

**C4-T3 fusionnée et publiée.** `c4-t3-etat` a été fusionnée en avance rapide
sur `main`, puis poussée.

**La production du cabinet est archivée.** Baptiste ne pourra pas poser le
favori de secours sur la tablette avant deux mois environ. Plutôt que
d'attendre, la version qui tourne au cabinet est désormais nommée et
gardée :
- **Version :** `d43350a` du 26 août, d'après Baptiste. Le dépôt ne la notait
  nulle part.
- **Étiquette :** `production-cabinet-01`.
- **Branche :** `maintenance-cabinet-01`, pour un correctif d'urgence sans la V2.
- **Fiche :** `docs/production/cabinet-01.md`. Elle donne ce que contient
  cette version et ce qui lui manque, la commande PowerShell et les quatre
  empreintes SHA-256 pour la vérifier à distance, et le geste d'urgence.

**C1-T4 est scindée.**
- **C1-T4a** se développe dans le dépôt, sans rien livrer.
- **C1-T4b**, la livraison, attend la visite : favori posé, une semaine de
  bilans réels, puis suppression du HTML écrit à la main.

C1-T5 et C9-T2 ne dépendent plus que de C1-T4a.

**C1-T4a — le schéma du cabinet, mesuré contre la production réelle.**
**À LIVRER**, 18 critères vérifiés.
- **Ce qui restait à faire.** Le schéma existait déjà : `formulaire/schema.json`
  porte les 28 blocs depuis C1-T3b. La tâche l'a placé dans
  `clients/cabinet-01/schema.json`, qui fait foi. `formulaire/schema.json` en
  est le miroir, gardé égal à l'octet par un test.
- **Un paquet par client.** `outils/faire-paquet.sh <client>` exige
  l'argument et le filtre (18 arguments hostiles refusés). Il relit l'archive
  pour la comparer au schéma du client et l'efface si une pièce manque. Le
  serveur, lui, ne voit jamais `clients/`.
- **La mesure, dans un vrai Chrome, contre `d43350a`** et non plus contre la
  fiche de secours. Le fait de départ : `index-v1.html` **n'est pas** la
  version installée.
  - Un bilan rempli sur `d43350a` se rouvre sur le moteur sans perdre une clé
    (nom, texte de 477 caractères, ligne de tableau, 4 traits). Un test le
    garde désormais : G4, dans `tests/test_schema_client.js`, applique la
    vraie `cleChamp()` aux deux versions.
  - « `d43350a` restauré » est identique au moteur, page à page, à 1 280 et
    à 760 px.
  - Une variante d'une bande de 8 lignes (≤ 3/255) existe sur `d43350a`
    lui-même. Ce n'est donc pas le moteur, mais sa cause n'est pas établie.
- **Ce que la praticienne verra changer**, dans
  `docs/references-visuelles/CONSTAT-2026-11-06-C1-T4a.md` :
  - le pied de page de version ;
  - le bandeau des bilans en attente ;
  - l'en-tête lu sur le PC (sans lui, l'export est refusé) ;
  - le message de repli et le favori de secours ;
  - de nouveaux libellés après un dépôt échoué ;
  - le double appui sur « Générer le PDF » ignoré ;
  - la base IndexedDB en version 2.
- **La barrière des images devient préventive.** Les sorties de mesure sont
  ignorées par Git, et la CI refuse toute image ou tout PDF suivi dans
  `docs/references-visuelles/` ou dans `outils/reference-visuelle/sortie/`.

**Ménage.**
- **Une copie du `index.html` de production**, laissée dans le bloc-notes de
  session par un agent, portait l'identité réelle du cabinet. Elle a été
  vérifiée identique au blob déjà public, puis supprimée.
- **Un serveur d'essai `http.server` oublié depuis le 19 octobre** (port 8777)
  a été trouvé. Son arrêt a été refusé par le système de permissions et
  laissé à Baptiste.

## Décisions prises

| Décision | Raison | Conséquence |
|---|---|---|
| **Archiver la production plutôt qu'attendre le favori** | Pas de visite au cabinet avant deux mois environ | Étiquette, branche de maintenance, fiche ; mémoire `production-cabinet-01-et-visite` |
| **La production est `d43350a` (26 août)** | Déclaration de Baptiste ; vérifiable par empreintes | La prochaine livraison franchira tout l'écart jusqu'à `main` |
| **Scinder C1-T4 en C1-T4a et C1-T4b** | Le développement n'a pas besoin de l'appareil, la livraison si | C1-T5 et C9-T2 débloquées |
| **Pas de `theme.json`** (D3) | Aucun code ne le lirait ; il dupliquerait la palette de `:root` | Périmètre de la feuille de route amendé |
| **Le client se choisit au paquet, jamais au serveur** (D2) | La racine web reste `formulaire/` | Argument obligatoire, sans valeur par défaut |
| **G4 lit le SHA de `d43350a`, pas l'étiquette** | L'étiquette se déplace à chaque installation | Une version livrée s'ajoute comme seconde référence, la garde ne s'assouplit pas |
| **Images et PDF de mesure jamais versionnés** (D4) | Une image échappe à la garde d'identité | `.gitignore` et barrière CI |

## État des tests

**Avant :** 314 tests Python et 12 suites Node.
**Après :** **319 tests Python** (2 sautés), verts sous `-W
error::ResourceWarning` et sous `-O` ; **13 suites Node** (`test_schema_client.js`).
Mutations M0 à M16 consignées dans `docs/audits/C1-T4a-mises-en-echec.md`.
**CI :** `42212161381` puis `42236920584`, vertes sur 7 jobs sur 7.

## Constats de sécurité

- **Audit : CONFORME**, avec trois faibles :
  - la sortie par défaut de `produire.js` dans l'arbre, non ignorée ;
  - une archive laissée par `faire-paquet.sh` après un échec, défaut antérieur ;
  - G1 aveugle aux fichiers à plat et aux liens symboliques.

  Les trois sont corrigés.
- **Réaudit après revue : CONFORME**, aucun constat. Aucune nouvelle copie de
  l'identité réelle n'a été trouvée, ni dans les blobs, ni dans les messages de
  commit, ni dans les fichiers temporaires. La production n'a pas bougé.
- **Revue :** quatre points à reprendre, puis feu vert (À LIVRER).

## Ce qui reste en suspens

- **Fusion de `c1-t4a-schema-cabinet`** sur `main` et poussée : décision de
  Baptiste.
- **Serveur `http.server` sur le port 8777 (PID 77897)** : à arrêter par
  Baptiste (`kill 77897`).
- **C1-T4b, à la visite**, avec ce qu'il faudra trancher pour le retour
  arrière : sur une base IndexedDB passée en version 2, `d43350a` ne vide plus
  la file et ne peut plus enregistrer le dossier des bilans. Faut-il supprimer
  la base de la tablette, ou la ramener en version 1 ?
- **Vérifier par empreintes** que le cabinet tourne bien sur `d43350a`, lors
  d'une séance à distance (commande dans la fiche de production).
- **Hérité :**
  - essai de C3-T3a sur une VM Windows ;
  - schéma du prospect ;
  - documents qui citent encore le tunnel (`docs/adressage.md`,
    `docs/projection.md`) ;
  - en-tête `Server` (C6-T5).

## Prochaine étape recommandée

Fusionner `c1-t4a-schema-cabinet`. Puis C1-T5 (bibliothèque de blocs) ou
C2-T2 (logo du client), toutes deux débloquées.

## À savoir pour la prochaine session

- **La fiche de secours n'était pas la production.** Toutes les preuves au
  pixel depuis octobre visaient `index-v1.html`, figée en octobre, et non ce
  qui tourne au cabinet depuis août. Avant de dire « identique à la V1 », il
  faut nommer la V1.
- **`window.zonesDessin` n'existe pas** : c'est une `const` de `script.js`.
  `produire.js` rendait toujours `traits: -1`, et personne ne l'avait vu.
- **Un export n'est pas déterministe sous `serveur.py`.** Comparer des
  ensembles d'exports (au moins 3 par côté, même serveur), jamais un export
  contre un export.
- **Une garde liée à une étiquette mobile rougit le jour où l'étiquette
  bouge.** Épingler un SHA dès qu'une référence doit rester fixe.
- **Les agents laissent des copies dans le bloc-notes.** Une copie du blob de
  production y est restée sans que l'implémenteur l'ait écrite. Les auditeurs
  ont fouillé le bloc-notes ; il faut continuer.
