# Session du 7 novembre 2026 — L'atelier de composition, et un serveur qui ne suit plus les liens

**Durée approximative :** une journée.
**Tâches concernées :** C9-T2 ; C6-T6 ; C6-T7 ouverte.
**Branches :** `c9-t2-atelier`, puis la branche de C6-T6, fusionnées en avance
rapide sur `main` et poussées.
**Commits :** `6cfe897..423b629` (C9-T2), `d144645..fd0f163` (C6-T6). `main`
est à `fd0f163`. La CI de `main` est verte sur les 7 jobs après chaque
fusion ; la dernière est le run `42390561578`.

## Ce qui a été fait

**Mode de travail.** Comme la veille, Baptiste a demandé de commiter et de
pousser sans demander. Chaque tâche a donc enchaîné contrat, implémentation,
audit, revue, fusion et poussée, sans arrêt intermédiaire.

**C9-T2 — Outil d'atelier de composition. Implémentée et fusionnée, pas encore
livrée.**
- **L'outil.** `outils/atelier/atelier.js`, en Node nu, conduit la fabrication
  d'un client en quatre gestes : `ouvrir`, `composer`, `verifier`, `apercu`.
  Il travaille dans un dossier de travail **hors de tout dépôt Git**, puisque
  le dépôt est public et que l'identité d'un client ne doit jamais y entrer.
- **Une seule voie d'écriture.** `ecrireDansTravail` n'écrit que des noms d'une
  liste fermée, sans jamais écraser, et refuse les liens. Le confinement a deux
  couches :
  - tout dossier qui a un ancêtre `.git` est refusé, quel que soit le dépôt ;
  - le dossier est comparé à la racine du dépôt par identité de fichier
    (périphérique et inode).
- **Rien n'est recopié du serveur.** La vérification de l'identité et du logo
  s'appuie sur les vraies fonctions de `serveur.py`, lues par un auxiliaire
  Python (`lire_serveur.py`) qui l'importe isolé (`-I -B`). Les marqueurs de la
  convention de nommage sont lus dans `script.js`. Ainsi, une règle qui change
  au serveur change aussi à l'atelier.
- **L'aperçu** est une page statique ouverte en `file://`. Elle charge le seul
  moteur de rendu, sans démarrer l'application, et embarque le schéma avec `<`
  échappé.
- **Barrières de confidentialité.**
  - `identite-cabinet.json` et `apercu-atelier.html` sont ignorés par Git.
  - Le contrôle « aucun secret versionné » de la CI connaît désormais
    `identite-cabinet.json`.
- **Ce qui manque : la mesure.** Il faut deux fabrications chronométrées par
  Baptiste, sous trois heures chacune (M-A et M-B), en suivant
  `docs/essais/C9-T2-fabrication.md`.

**C6-T6 — Le service statique ne suit plus les liens symboliques. Livrée.**
- **Liens refusés.** Le serveur ne sert plus aucun lien symbolique ni jonction
  placé sous `formulaire/`, même s'il pointe vers l'intérieur. La réponse est
  une 404 identique à l'octet près, et en temps, à celle d'un fichier absent.
  Le refus et son motif vont dans `journal.log` seul.
- **Comment.** Le contrôle `confiner_fichier_servi` s'insère dans
  `autorise_lecture`, après l'authentification et le filtre d'extensions. Il
  porte sur le chemin même que `send_head` ouvrira. Il réutilise le confinement
  du logo de C2-T2, rebaptisé `confiner_sous_racine`.
- **Casse sous Windows.** Une adresse qui ne diffère que par la casse
  (`/Index.html`) reste servie. Le serveur vérifie d'abord, élément par
  élément, qu'aucun maillon du chemin n'est un lien ou un point d'analyse.
  Pour le logo, la même différence est refusée avec le motif `absent`, au lieu
  de `lien-symbolique`.
- **Effet de bord voulu.** `/x%00.json` répond désormais 404 au lieu d'une
  erreur 500 de la bibliothèque. Une note est versée sous C6-T5.

## Décisions prises

| Décision | Raison | Conséquence |
|---|---|---|
| Commits et poussées sans demander, pour cette session | Demande de Baptiste | Deux tâches complètes, de bout en bout |
| L'atelier refuse tout dossier situé dans un dépôt Git, pas seulement celui-ci (constat moyen de l'audit C9-T2) | Un clone ou une copie du dépôt aurait accueilli l'identité d'un client sans garde | Le dossier de travail vit ailleurs, par construction |
| L'atelier lit les règles dans `serveur.py` et `script.js`, sans les recopier | Ne jamais transcrire une garde | `serveur/` doit rester importable sans effet de bord ; la contrainte est vérifiée par capture avant le premier appel |
| D-O1 (où vit le schéma d'un client hors pilote) et D-O2 (palette par client) restent ouvertes | Ce sont des décisions métier, pas de l'implémentation | `templates/LISEZMOI.md` interdit de verser un client hors pilote dans le dépôt tant que D-O1 n'est pas tranchée |
| Casse tolérée au service statique sous Windows, contre l'avis du planificateur (404) | Une correction de sécurité ne doit pas donner une page blanche un matin de consultation | Vérification `lstat` de chaque élément du chemin avant d'accepter |
| Noms courts 8.3 de Windows → 404 (R8), course entre contrôle et ouverture acceptée (D6) | Aucun appareil du cabinet n'en produit ; il faut déjà écrire dans la racine pour exploiter la course | Inscrit dans le contrat, sans tâche |
| Le motif `illisible` au lieu de `None` (fichier absent, dossier de casse différente) n'est pas corrigé à chaud | La réponse est la même 404 ; le correctif toucherait la boucle de sécurité sans nouvel audit | Versé dans les notes de C6-T7 |
| L'historique poussé n'est pas réécrit pour un message de commit imprécis (`65ace88`) | Pas de poussée forcée | Consigné dans la revue de C9-T2 |

## État des tests

**Avant :** 368 tests Python et 15 suites Node.
**Après :** **405 tests Python** (6 sautés sur le Mac), verts aussi sous
`python3 -O`, et **16 suites Node** (`test_atelier.js`, 36 cas). Les nouveaux
tests Python sont `tests/test_liens_servis.py` (37) et `CasseWindows` dans
`test_logo.py`. Sous Windows, la CI a joué des jonctions réelles. Chaque garde
a été mise en échec par mutation sur une copie jetable :
- M1 à M13 pour C9-T2 ;
- la série de `docs/audits/C6-T6-mises-en-echec.md`.

## Constats de sécurité

- **C9-T2 — CONFORME SOUS RÉSERVE, puis CONFORME au réaudit.** Trois constats
  ont été levés :
  - **moyen :** la garde ne connaissait que le dépôt de l'atelier ;
  - **faible :** une recette était copiée avant d'être validée, et un extrait
    en était cité à l'écran ;
  - **faible :** le refus d'une convention de nommage citait le texte entre
    accolades.
- **Restent deux observations :**
  - `generer_autorite.py` est cité comme geste au cabinet, sans le rappel
    « jamais depuis le dépôt » ;
  - sous Windows, l'interpréteur Python est cherché d'abord dans le dossier
    courant. C'est sans portée tant que l'atelier tourne sur le Mac.
- **C6-T6 — CONFORME au premier passage.** Une centaine de requêtes piégées
  n'ont fait sortir aucun fichier. Le seul constat faible, antérieur à la
  tâche et non aggravé, devient **C6-T7** : si le dossier `formulaire` est
  lui-même un lien vers la racine du cabinet, `GET /config.json` rend 200. Ni
  le paquet ni l'installateur ne produisent cette configuration.
- **Revues.**
  - **C9-T2 :** le code était bon, deux pages d'aide non. Corrigées (une
    fonction au lieu d'une variable de commande, pour zsh, et les deux gestes
    du logo), le verdict est devenu « à livrer ».
  - **C6-T6 :** à livrer. Ses remarques d'une ligne ont été appliquées.

## Ce qui reste en suspens

- **Mesures M-A et M-B de C9-T2.** À faire par Baptiste, en suivant
  `docs/essais/C9-T2-fabrication.md`. Elles seules font passer C9-T2 à
  « livrée ».
- **Mesure A13 de C1-T5.** Toujours à faire par Baptiste.
- **D-O1 et D-O2.** À trancher avant le premier client hors pilote.
- **C6-T7.** Courte (effort S), prête à partir.
- **Les deux courses de l'outillage de test sous macOS**, consignées sous
  C7-T5 :
  - le signal d'arrêt arrive avant le `try:` ;
  - un port libre est pris entre sa recherche et son usage. Correctif suggéré :
    le port 0.
- **Serveur `http.server` du port 8777 (PID 77897).** Toujours à arrêter par
  Baptiste.
- **Hérité :**
  - C1-T4b à la visite de janvier ;
  - essai de C3-T3a sur une VM Windows ;
  - en-tête `Server` (C6-T5).

## Prochaine étape recommandée

C6-T7 : courte, déjà cadrée par l'audit de C6-T6, et elle ferme le dernier
chemin connu vers `config.json`. Commande : `/lancer-tache C6-T7`.

## À savoir pour la prochaine session

- **Une commande rangée dans une variable ne marche pas sous zsh.** Avec
  `A="node outils/atelier/atelier.js"`, `$A ouvrir …` rend 127. Ce piège était
  déjà connu dans les harnais de mutation, et il est revenu dans un protocole
  destiné à Baptiste. Écrire une fonction : `A() { node … "$@"; }`.
- **Pour simuler Windows dans un test, `lstat` aussi doit ignorer la casse.**
  Il faut en plus isoler `realpath` du faux `lstat` sous Python 3.9 et Linux.
  Les deux défauts n'ont été vus qu'en CI.
- **Sous macOS, `os.getcwd()` rend le chemin résolu.** Un bac à sable lancé
  depuis son dossier ne passe donc jamais par `/var` et ne prouve rien sur une
  racine atteinte par un lien. Seul un test qui part d'une racine non résolue
  le prouve.
- **Deux tests de jonction échouent sous le Python 3.9.6 de macOS**
  (`test_u8`, `test_jonction_invisible_a_islink`). Le défaut vient de cet
  interpréteur, pas du code ; la CI joue 3.9 sous Linux et Windows.
- **Le fil lecteur de `stderr` n'est pas dans `demarrer_sandbox_court`.**
  Seuls `ServeurEnMarche` et `LiensServis` en ont un, et `ServeurArret` lit
  son tube par `communicate()`. Attendre la ligne `DEMARRAGE` ne garantit pas
  non plus que le `try:` est franchi.
- **La garde de confidentialité a mordu sur une adresse électronique complète**
  écrite dans un rapport d'audit. Il a fallu en décrire la forme, sans la
  recopier.
