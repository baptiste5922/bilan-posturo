# Session du 7 novembre 2026 (2) — Un serveur qui refuse de démarrer sur une racine web dangereuse

**Durée approximative :** une demi-journée, à la suite de la session du matin
(`2026-11-07-atelier-et-liens-servis.md`).
**Tâches concernées :** C6-T7.
**Branche :** `c6-t7-racine`, fusionnée en avance rapide sur `main` et poussée.
**Commits :** `efb13f6..1b771bd`. `main` est à `1b771bd`. La CI de la branche
(run `42416314295`) puis celle de `main` (run `42416813258`) sont vertes sur
les 7 jobs.

## Ce qui a été fait

**Mode de travail.** Inchangé : Baptiste a demandé de commiter et de pousser
sans demander. C6-T7 a enchaîné contrat, implémentation, audit, réaudit, revue,
fusion et poussée.

**C6-T7 — La racine web ne peut plus contenir celle du cabinet. Livrée.**

- **Ce qui est refusé.** Au démarrage, avant de créer le dossier des bilans et
  avant d'ouvrir le port, le serveur compare trois chemins résolus : la racine
  web (`formulaire/`), la racine du cabinet et `dossier_pdf`. Il refuse de
  démarrer, code de sortie 1, dans trois cas :
  - `racine-cabinet` : `formulaire` est un lien ou une jonction qui mène au
    dossier d'installation ou au-dessus. Avant la tâche, `GET /config.json`
    rendait 200 dans cette configuration, le constat faible laissé par l'audit
    de C6-T6 ;
  - `dossier-pdf` : le dossier des bilans se trouve sous `formulaire` ;
  - `indetermine` : un chemin ne se résout pas. Échec fermé.
- **Comment.** `motif_refus_racine_web` compare par `os.path.commonpath` les
  formes `NFC(normcase(realpath(…)))`. Le motif appartient à un vocabulaire
  fermé (`MOTIFS_REFUS_DEMARRAGE`), et deux gardes AST vérifient que
  `demarrer()` appelle le contrôle avant `os.makedirs` et avant le socket.
- **Ce que voit chacun.**
  - `journal.log`, nominatif, reçoit les chemins résolus entre `repr()` ;
  - `technique.log` reçoit `DEMARRAGE_REFUSE refus motif=<motif>`, sans aucun
    chemin. C'est le dixième événement technique ;
  - la console affiche le geste à faire.
- **La note de C6-T6 est traitée.** Dans la boucle `lstat` du service statique,
  un préfixe absent (`FileNotFoundError`, `NotADirectoryError`) est ignoré au
  lieu d'être journalisé `illisible`. La réponse reste la même 404.
- **Documentation.**
  - Le mode d'emploi et sa traduction gagnent deux lignes dans le tableau des
    messages, et une sous-section de Maintenance, « Le serveur refuse de
    démarrer » : motif, cause, geste, puis relance de la tâche planifiée ;
  - le README a une phrase dans « Exposed surface » ;
  - le bloc de C6-T7 dans `docs/ROADMAP.md` porte l'état, les mutations et les
    limites.

## Décisions prises

| Décision | Raison | Conséquence |
|---|---|---|
| Refuser de démarrer plutôt que servir en mode dégradé | Une racine web qui englobe `config.json` expose l'empreinte du mot de passe et les clés ; aucun mode dégradé n'est sûr | Un matin de consultation, le serveur peut ne pas démarrer : d'où la procédure de Maintenance et le contrôle à la visite |
| Amendement A1 au contrat : « aucun import » devient « seul `unicodedata` », déjà présent | La normalisation NFC était nécessaire pour fermer le contournement par les accents sous macOS | Toujours la seule bibliothèque standard |
| `verdict_certificat` lit le jeton exact `DEMARRAGE` | Le nouvel événement `DEMARRAGE_REFUSE` contenait la sous-chaîne et trompait la détection d'un changement de certificat | Test `VerdictApresUnRefus` dans les deux sens |
| Chemins `\\?\` et sous-dossier du cabinet désigné comme racine web : consignés, non traités | Aucun appareil du cabinet ni l'installateur ne les produisent | Inscrits comme limites dans le bloc de C6-T7 |
| Pas de test pour la branche `web = cible = "?"` de `signaler_refus_racine_web` | Elle ne touche que le journal nominatif, jamais `technique.log` ni le code de sortie | Écarté dans la revue, avec sa raison |

## État des tests

**Avant :** 405 tests Python (6 sautés sur le Mac) et 16 suites Node.
**Après :** **448 tests Python** (7 sautés sur le Mac), verts aussi sous
`python3 -O`, et 16 suites Node.
- `tests/test_racine_web.py` est nouveau (U1 à U9, G1, G2, I1 à I3, I6, W1,
  `FormesUnicode`, `VerdictApresUnRefus`) ;
- U13a et U13b sont ajoutés dans `tests/test_liens_servis.py` ;
- `preparer_sandbox()` est extraite de `demarrer_sandbox_court`, et son `assert`
  est devenu une exception explicite.

En CI Windows, W1 joue une vraie jonction `mklink /J`, et U9 (formes Unicode)
passe. Chaque garde a été mise en échec : M1 à M14 sont consignées dans
`docs/audits/C6-T7-mises-en-echec.md`, et l'auditeur comme le réviseur en ont
rejoué d'autres.

## Constats de sécurité

- **Audit : CONFORME SOUS RÉSERVE au premier passage, CONFORME au réaudit.**
  Deux constats faibles ont été levés, puis corrigés :
  - `verdict_certificat` cherchait une sous-chaîne, et `DEMARRAGE_REFUSE` le
    trompait ;
  - sous macOS, écrire les accents du chemin du lien en forme décomposée
    contournait la comparaison. Corrigé par la normalisation NFC.
- **Revue : À LIVRER.** La remarque importante était la procédure de retour en
  service, absente des guides. Elle est ajoutée.

## Ce qui reste en suspens

- **À la visite de janvier (C1-T4b) :** lancer une fois `demarrer-serveur.bat`
  et lire la sortie. Le réglage `dossier_pdf` de la praticienne n'est pas
  connu ; s'il pointait sous `formulaire`, le serveur refuserait désormais de
  démarrer.
- **Mesures de Baptiste :** A13 de C1-T5, M-A et M-B de C9-T2.
- **D-O1 et D-O2** : à trancher avant le premier client hors pilote.
- **Les deux courses de l'outillage de test sous macOS** (signal avant le
  `try:`, port libre pris entre recherche et usage) : une tâche C7 à ouvrir.
- **Serveur `http.server` du port 8777 (PID 77897)** : toujours à arrêter.
- **Hérité :** C6-T5 (en-tête `Server`, `/x%00.json`), essai de C3-T3a sur une
  VM Windows.

## Prochaine étape recommandée

Faire les deux mesures qui attendent, en commençant par celle de C9-T2, qui
débloque la fabrication du premier client hors pilote :
`docs/essais/C9-T2-fabrication.md`. Côté code, la tâche prête suivante est
C6-T5 : `/lancer-tache C6-T5`.

## À savoir pour la prochaine session

- **En CI Windows, le dossier temporaire passe par un nom court 8.3**
  (`RUNNER~1`). Un test qui compare un chemin construit à un chemin résolu doit
  partir de `os.path.realpath(tmp)`. La première correction de U9, un saut sous
  Windows, reposait sur une explication fausse : c'est le réaudit qui l'a
  relevé. Ne pas sauter un test qu'on ne comprend pas.
- **Un nouvel événement journalisé peut tromper un lecteur existant.** Tout
  lecteur de journal doit chercher un jeton exact, jamais une sous-chaîne :
  `DEMARRAGE` est un préfixe de `DEMARRAGE_REFUSE`.
- **Sous macOS, un même chemin a deux écritures Unicode.** `realpath` ne
  normalise pas : toute comparaison de chemins passe par NFC.
- **Un refus de démarrer doit passer avant tout effet de bord.** Les globales
  de journalisation (`JOURNAL_TECHNIQUE_ACTIF`, `CONSERVATION_JOURNAUX_MOIS`)
  ont dû être lues avant le contrôle, sinon la ligne `DEMARRAGE_REFUSE` partait
  avec des réglages par défaut.
- **Sous zsh, `^{commit}` doit être entre guillemets** :
  `git rev-parse "production-cabinet-01^{commit}"`.
