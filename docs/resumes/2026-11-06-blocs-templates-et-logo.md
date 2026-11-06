# Session du 6 novembre 2026 (3) — Une bibliothèque de blocs, et le logo du client

**Durée approximative :** une demi-journée.
**Tâches concernées :** fusion de C1-T4a ; C1-T5 ; C2-T2.
**Branches :** `c1-t5-blocs`, `c2-t2-logo`, toutes deux fusionnées en avance
rapide sur `main` et poussées.
**Commits :** `7ea6a66` (C1-T4a sur `main`), `8ba4e06..715c0b1` (C1-T5),
`6ac2a1a..af6e7ee` (C2-T2). `main` est à `af6e7ee`. CI de `main` verte après
chaque fusion (`42252637104`, `42260090317`, puis celle de `af6e7ee`).

## Ce qui a été fait

**C1-T4a fusionnée et publiée.** La branche de la session précédente est
entrée sur `main` en avance rapide. La production n'a pas bougé :
`production-cabinet-01` et `maintenance-cabinet-01` restent sur `d43350a`.

**Mode de travail.** Baptiste a demandé, pour cette session, de commiter et de
pousser sans demander, et d'avancer au maximum. Chaque tâche a donc enchaîné
contrat, implémentation, audit, revue, fusion et poussée sans arrêt.

**C1-T5 — Bibliothèque de blocs et templates de départ. Implémentée et
fusionnée, pas encore livrée.**
- **Neuf fragments** (`blocs/*.json`), de l'anamnèse à la conclusion, forment
  une partition exacte des 28 blocs du pilote. Ils ont été extraits par
  script, jamais recopiés : les clés gelées (`familliaux`…) sont intactes.
- **Deux templates** (`templates/`) sont des **recettes**, pas des schémas :
  une liste de fragments, pour qu'un bloc n'ait qu'une source.
  `podologue-complet` redonne **à l'octet** `clients/cabinet-01/schema.json`,
  et une garde (B4) le vérifie. `podologue-court` prend quatre fragments.
- **`outils/composer-schema.js`**, en Node nu, compose une recette et valide le
  résultat par le vrai moteur. Un avertissement du moteur y vaut refus.
  L'outil refuse d'écraser un fichier et d'écrire sous `formulaire/`, par
  identité de dossier plutôt que par comparaison de chaînes.
- **Aucune grille dans la bibliothèque.** Une grille entre client par client,
  après ses trois conditions.
- **Ce qui manque : la mesure.** Le critère de la feuille de route,
  « un client fictif en moins d'une heure », se chronomètre par Baptiste.
  Le protocole, avec sa répétition non comptée, est dans
  `docs/essais/C1-T5-client-fictif.md`.

**C2-T2 — Logo propre au client. Livrée.**
- **Emplacement.** Le logo d'un client vit dans `formulaire/images/cabinet/`,
  posé sur le PC du cabinet, jamais dans le dépôt : un logo porte en général
  le nom du cabinet. Le dossier est ignoré par Git, et `faire-paquet.sh`
  refuse de fabriquer un paquet s'il le trouve.
- **Validation au démarrage.** Le serveur valide `cabinet.logo` une fois, en
  deux couches indépendantes (forme, puis `realpath` et `commonpath`). Il
  refuse tout lien symbolique, n'admet que PNG ou JPEG, au plus 512 Kio, et
  contrôle la signature du fichier.
- **Ce qui est accepté.** Seulement `images/cabinet/<nom>` ou exactement le
  défaut. `/cabinet` ne rend que le chemin validé.
- **Logo refusé.** Il donne « pas de logo », jamais l'emblème par défaut, et
  l'export reste possible. Le chemin va dans `journal.log` seul, échappé ;
  `technique.log` ne reçoit que le motif fermé.
- **Côté formulaire.** `script.js` applique le logo et attend son chargement
  avant la capture, 3 s au plus. La fiche de secours chargeant `script.js`,
  l'inertie au pixel a été prouvée par ensembles d'exports, sur
  `index-v1.html` comme sur `index.html`.

## Décisions prises

| Décision | Raison | Conséquence |
|---|---|---|
| Commits et poussées sans demander, pour cette session | Demande de Baptiste | Chaîne complète par tâche, arrêt seulement sur décision métier |
| Le moteur n'inclut aucun fichier à l'exécution (C1-T5, D4) | La tablette ne voit que `formulaire/` | La composition se fait à l'atelier, le client reçoit un `schema.json` complet |
| Un template est une recette, pas un schéma (D3) | Une seule source par bloc | Le pilote se recompose depuis les fragments ; B4 l'ancre |
| B4 ne s'assouplit pas quand le pilote divergera (D9) | Éviter la tolérance silencieuse | La tâche qui fait diverger tranche par écrit |
| A13 de C1-T5 compare le contenu JSON, pas l'empreinte | Une indentation retouchée à la main n'est pas un écart | Mesure robuste ; la fin du chronomètre est « après la modification 8 » |
| Logo client sous `formulaire/images/cabinet/`, hors dépôt | Un logo est identifiant ; pas de route hors racine | Ignoré par Git, refusé par le paquet ; à préserver par C5-T2 |
| Un logo refusé donne « pas de logo » | L'emblème des podologues ne doit pas s'imprimer chez un posturologue | Export jamais bloqué |
| Le serveur n'accepte que `images/cabinet/` ou le défaut exact (faible n° 2 de l'audit) | Un logo posé ailleurs partirait chez le client suivant | Contrat D2 amendé |

## État des tests

**Avant :** 319 tests Python et 13 suites Node.
**Après :** **368 tests Python** (2 sautés, PowerShell), verts aussi sous
`python3 -O`, et **15 suites Node** (`test_blocs.js`, `test_logo.js`). CI verte
sur 7 jobs à chaque étape. Mutations consignées dans
`docs/audits/C1-T5-mises-en-echec.md` (24 et plus) et en bas de
`docs/audits/C2-T2.md` (M1 à M32).

## Constats de sécurité

- **C1-T5 — CONFORME**, un faible : le test B8 de la garde « pas d'écriture
  sous `formulaire/` » visait le vrai `formulaire/` du dépôt. Interrompu au
  mauvais moment, il aurait pu y laisser un fichier, emballé ensuite par le
  paquet. Le cas se joue désormais dans une racine temporaire.
- **C2-T2 — CONFORME SOUS RÉSERVE, puis CONFORME au réaudit.** La réserve a été
  levée par une inscription en feuille de route. Le faible n° 2 (logo accepté
  hors de `images/cabinet/`) a été corrigé. 60 entrées hostiles ont été
  éprouvées contre le confinement, puis 43 contre la nouvelle couche.
- **Ouverte : C6-T6.** Le gestionnaire statique suit tout lien symbolique posé
  sous `formulaire/`. Le défaut est antérieur à C2-T2, et il faut déjà pouvoir
  écrire dans la racine pour l'exploiter. C2-T2 en fait cependant un dossier
  rempli à la main.
- **Revues.** C1-T5, À LIVRER : la consigne de fin du chronomètre est
  précisée. C2-T2, À LIVRER : le README et l'amendement du contrat sont
  corrigés.

## Ce qui reste en suspens

- **Mesure A13 de C1-T5** : à faire par Baptiste, en suivant
  `docs/essais/C1-T5-client-fictif.md`. Elle seule fait passer C1-T5 à
  « livrée ».
- **Serveur `http.server` du port 8777 (PID 77897)** : toujours à arrêter par
  Baptiste (`kill 77897`).
- **C1-T4b à la visite.** La fiche de production liste désormais le contrôle du
  logo et la preuve d'inertie à 760 px avec le vrai logo.
- **Hérité :**
  - essai de C3-T3a sur une VM Windows ;
  - schéma du prospect ;
  - documents qui citent le tunnel ;
  - en-tête `Server` (C6-T5) ;
  - vérification de la production par empreintes.

## Prochaine étape recommandée

C9-T2, l'outil d'atelier de composition. Il s'appuie sur les fonctions que
`composer-schema.js` exporte, et C9-T1 et C1-T5 sont en place. À défaut,
C6-T6 (liens symboliques), courte et ouverte par cette session :
`/lancer-tache C9-T2`.

## À savoir pour la prochaine session

- **La garde de confidentialité mord sur du vocabulaire générique.** Elle a
  refusé quatre lignes de description de blocs, du vocabulaire médical
  ordinaire qui recoupait la fiche du prospect. Il a fallu reformuler à partir
  des titres déjà publics du pilote. Les brouillons refusés étaient restés
  dans le bloc-notes de session et ont été supprimés : **un texte refusé par la
  garde ne doit pas survivre dans un fichier de travail**.
- **Un test qui éprouve une garde d'écriture doit écrire dans une racine
  jetable**, jamais dans le dépôt : un `finally` ne protège pas d'une
  interruption.
- **Sous macOS, `/var` est un lien vers `/private/var`** : une racine
  temporaire passe par `realpath`, sinon une garde par chaînes rougit pour une
  mauvaise raison.
- **Les agents signent leurs commits avec leur modèle réel** (Sonnet 5.5) :
  ce n'est pas un défaut.
- **Une fusion en avance rapide n'a pas de message** : ce qu'on voulait
  « signaler au message de fusion » se consigne dans la revue.
