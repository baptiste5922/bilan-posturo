# Audit C5-T2a — Client de mise à jour : application locale, retour arrière, traces

**Date :** 2026-11-12  **Périmètre audité :** `git diff 1a84caf..30ffd4d` (branche
`c5-t2a-application`, 8 commits) : `serveur/maj.py` (nouveau, 1 610 l.),
`serveur/serveur.py` (+423), `serveur/paquet_signe.py`, `outils/faire-paquet.sh`,
`outils/signer-paquet.py`, `.gitignore`, tests et documentation. Lu dans son
contexte : `confiner_sous_racine`, `forme_comparable`, `ecrire_atomiquement`,
`journaliser*`, `faire_tourner_journal`, `do_POST`, `demarrer()`,
`installer-demarrage.ps1`, `formulaire/script.js` (sondes de la tablette).
Contrat `docs/contrats/C5-T2.md`, §10 et errata §13.
**Verdict :** CONFORME SOUS RÉSERVE

**Réserve.** Le constat de gravité Moyenne (serveur arrêté et jamais relancé
quand le client abandonne après l'acceptation de l'arrêt) est à corriger
**avant que le client soit installé au cabinet**, et en tout cas avant C5-T2b,
qui rendra la séquence automatique et nocturne.

## Ce qui a été rejoué

- **Témoin** sur une copie `git ls-files -z` sans `origin` :
  `tests.test_maj`, `tests.test_maj_bout_en_bout`, `tests.test_maj_windows`
  (Python 3.14 avec `cryptography` : 130 tests, 8 sautés, tous Windows) ;
  `tests.test_maj`, `tests.test_serveur`, `tests.test_paquet_signe` sous
  `/usr/bin/python3 -O` (3.9.6) : verts. Aucun `assert` nu dans `maj.py`.
- **CI `43240323698`** relue : tête `30ffd4d`, 7 jobs verts ; sous
  `windows-latest` 3.9 et 3.13, les huit tests de `test_maj_windows.WindowsReel`
  sont **exécutés** (`... ok`), et 30 tests bout en bout passent sous Windows.
- **Mises en échec de l'implémenteur** : M1 à M20 relues ; les classes qu'elles
  font rougir existent et passent au témoin. Non rejouées une à une : mes propres
  mutations recoupent M4 (X12), M11 (X11), M20 (X10).
- **Mes mises en échec** (harnais hors dépôt, ancre unique exigée, témoin vert,
  restauration par copie vérifiée par SHA-256, `python3` et `python3 -O`) :

| # | Mutation | Résultat |
|---|---|---|
| X1 | `.maj-tmp` retiré des exclusions | rouge (`ListeBlanche`) |
| X2 | `/sante` comptée comme activité | rouge (`CompteursDeDepots`) |
| X3 | `calme_secondes` accepte `True` | rouge (`DeciderArret`) |
| X4 | `revenir` sans comparaison `vers` / version installée | rouge (`PoseEtRetour`) |
| X5 | le retour n'efface plus les `.maj-tmp` | survit à `test_maj`, **rouge** au bout en bout (`Interruption`) |
| X6 | le retour ne restaure plus `installe.json` (erratum 7) | **survit**, unitaires et bout en bout (`Interruption`, `Retour*`) |
| X7 | dossier réservé : comparaison `realpath` retirée | **survit** (sous POSIX, le `lstat` la double ; sous Windows elle est seule contre une jonction, et rien ne l'éprouve) |
| X8 | `empreinte_si_present` retiré de `controler_destinations` | survit : redondant, `sauvegarder` refuse au même endroit, avant l'arrêt |
| X9 | `attendre_fin_depots` retiré de `demarrer()` | **survit**, unitaires et bout en bout (`DepotEnCours`, `ArretConcerte`) |
| X10 | `maj_code` recopié sans forme | rouge (`EtatDeLaMiseAJour`) |
| X11 | borne du calme exclue (`>`) | rouge (`DeciderArret`) |
| X12 | exclusions sensibles à la casse | rouge (`ListeBlanche`) |
| X13 | `dossier_pdf` ignoré | rouge (`ListeBlanche`) |
| X14 | demande non effacée après traitement | rouge (`SurveillanceDeLArret`) |
| X15 | demandes périmées non effacées au démarrage | **survit**, unitaires et bout en bout |
| X16 | `lstat` retiré de `lire_borne` | survit : `O_NONBLOCK` + `fstat` le doublent |
| X17 | état `bascule` écrit après la pose | survit à `test_maj`, **rouge** au bout en bout (`Interruption`) |

- **Sondes de scénario** (bac à sable bout en bout, serveur réel, fichier de test
  hors dépôt) : S1b, S2, S3 décrites dans les constats ci-dessous, toutes trois
  **démontrées**.

## Constats

### Moyenne — Un serveur arrêté sur demande n'est pas relancé quand le client abandonne

**Où :** `serveur/maj.py:1249-1256` (`demander_arret`, après `accepte`),
`serveur/maj.py:1461-1463` et `:1374` (étape `bascule` écrite hors du `try` de
`basculer`), `serveur/serveur.py:1934` (`ecrire_reponse_arret` avale toute
`OSError`, sans nouvelle tentative), `serveur/maj.py:1213-1223` (lecture de
`arret.reponse` toutes les 50 ms), `installer-demarrage.ps1:86`
(`-RestartCount` : relance sur échec seulement).

**Scénario :** une fois `accepte` décidé, le serveur appelle `shutdown()`, quitte
avec le code 0 et écrit `arrete` en dernière instruction (`serveur.py:2721`). Si
`maj.py` ne lit pas `arrete` dans les 90 s, il sort en
`ARRET_SANS_REPONSE` (code 3, « report ») **sans `pilote.demarrer()`**, en
affichant « le serveur ne s'est pas arrêté à temps ». Or le serveur, lui, est bel
et bien arrêté, avec le code 0 : la tâche planifiée ne le relance pas. Plus aucun
dépôt possible avant un redémarrage du PC ou un geste humain.

Le déclencheur réaliste est une écriture de `arret.reponse` ratée sous Windows.
CPython ouvre ses fichiers sans `FILE_SHARE_DELETE` (`_wopen`). Pendant que
`maj.py` tient `arret.reponse` ouvert pour sa lecture périodique, l'`os.replace`
du serveur sur ce même nom est donc refusé (`PermissionError`), puis silencieusement
avalé. Le dépôt connaît déjà ce risque, puisque `remplacer()` (`maj.py:1061`)
retente cinq fois pour un antivirus, mais pas les fichiers d'échange. Ni la
fréquence ni le mécanisme n'ont été reproduits sur un Windows réel. Ce qui a été
**démontré en bac à sable** (sonde S1b), c'est la conséquence : en supprimant la
seule écriture `arrete`, `appliquer` rend 3 et `ARRET_SANS_REPONSE`, `/sante` est
muette, et le pilote n'est jamais rappelé.

La perte de l'écriture `accepte` seule se rattrape, car `arrete` porte le même
jeton (sonde S1, vérifiée). Il reste le cas où `arrete` arrive après les 30 s de
`delai_reponse`, par exemple un dépôt attendu jusqu'à 30 s par `attendre_fin_depots`.

Le même effet suit toute sortie entre l'acceptation et le `try` de `basculer` :
- `ecrire_etat(…, etape="bascule")` qui lève (`OSError`, ou
  `Refus("ETAT_ILLISIBLE")`) ;
- une console fermée pendant la pause d'une seconde.

Dans ces cas, l'état reste `preparee`, et `reprendre` n'y voit rien à faire.

Facette voisine, moins grave : les écritures d'`etat.json` n'ont pas non plus de
nouvelle tentative. Une consultation de `/etat` au moment précis du dernier
`ecrire_etat(repos, appliquee)` (`maj.py:1396`, serveur neuf en marche) lève
`OSError`, ce qui donne `ECRITURE_IMPOSSIBLE` et le **retour arrière d'une version
saine**.

**Propriété à rétablir :** dès que le serveur a accepté l'arrêt, **toute** sortie
du client, refus ou exception, laisse un serveur relancé (`/Run` est inoffensif
sur une tâche en `IgnoreNew`). Les fichiers d'échange entre les deux processus
doivent aussi supporter un remplacement momentanément refusé sous Windows. C'est
la règle du contrat : « tout ce qui a été touché se défait ».

### Faible — Une tentative reportée détruit la sauvegarde de la version installée

**Où :** `serveur/maj.py:1457` (`sauvegarder` avant `demander_arret`),
`:1031-1034` (l'ancienne sauvegarde est effacée dès que la nouvelle est prête),
`:1487` (`revenir` exige `vers` = version installée).

**Scénario (sonde S2, démontré) :**
1. 1.2.0 est appliquée avec succès.
2. Une **requête non authentifiée** (`GET /` → 401) est envoyée, puis
   `appliquer` 1.3.0 avec le calme par défaut. La sauvegarde est reconstruite :
   elle contient maintenant les fichiers de 1.2.0, avec `vers=1.3.0`. Puis
   l'arrêt est refusé (`ARRET_REFUSE`).
3. `maj.py revenir` rend `RETOUR_IMPOSSIBLE` (« la sauvegarde ne correspond pas
   à la version installée »).

Les fichiers de 1.1.0 n'existent plus nulle part sur le PC : même le retour
manuel de `docs/mise-a-jour.md` §6 recopierait 1.2.0. Le recours de niveau 1 du
§11 du contrat (« une version reçue pose problème au formulaire : `revenir` »)
est perdu dès qu'une version plus récente a été tentée sans être basculée. En
T2a, `appliquer` est un geste manuel et le cas est rare. En T2b, `verifier`
préparera et sera reporté, de jour, chaque fois qu'une version est publiée.

**Propriété à rétablir :** la sauvegarde qui permet de revenir de la version
installée survit jusqu'au début effectif d'une nouvelle bascule.

### Faible — Un dépôt figé bloque toute mise à jour jusqu'au redémarrage du serveur

**Où :** `serveur/serveur.py:2440-2449` (`entrer_depot` / `sortir_depot` autour
de tout `traiter_post`), `:2480` (`self.rfile.read(taille)`). Aucun délai n'est
posé sur les connexions (constat du §3 du contrat : `timeout` absent).

**Scénario (sonde S3, démontré) :**
1. Un `POST /depot` authentifié annonce 100 000 octets, en envoie 50, puis se tait
   sans fermer la connexion. C'est le cas d'une tablette mise en veille ou qui
   perd le Wi-Fi en plein envoi.
2. 40 s plus tard, `appliquer` rend toujours `ARRET_REFUSE`, motif
   `depot-en-cours`.

Sans délai côté serveur, le fil reste bloqué dans `read` jusqu'à ce que TCP
renonce, ce qui peut ne jamais arriver sans keepalive. `DEPOTS_EN_COURS` reste
alors à 1 et **toute** mise à jour est refusée jusqu'au redémarrage du serveur.
`--calme-minutes 0` n'y peut rien, car la règle du dépôt passe avant. Aucun
bilan n'est en jeu (la file de la tablette le renverra), mais un fil figé, jusque
là inoffensif, suffit désormais à geler les correctifs de ce PC. Le seul signal
est `reportee` / `ARRET_REFUSE` sur `/etat`.

**Propriété à rétablir :** un dépôt qui ne progresse plus cesse, au bout d'un
temps borné, de compter comme dépôt en cours.

### Faible — Le serveur obéit à un fichier d'arrêt dans un dossier dont il ne vérifie pas la protection

**Où :** `serveur/serveur.py:1988` (`surveiller_demande_arret`) et le
commentaire de `NOM_DOSSIER_MAJ` (« le serveur n'y crée jamais rien ») ;
`serveur/maj.py:556-587` (`preparer_dossier_prive` règle le propriétaire et la
DACL **du dossier**, mais ne vérifie ni ne vide un contenu préexistant).

**Précondition :** la racine d'installation est inscriptible par l'utilisateur du
cabinet. C'est le point du §10 du contrat, à relever sur VM (fiche A2). Un
dossier créé directement sous `C:\` hérite en général d'une entrée
« Utilisateurs authentifiés : modification ».

**Scénario :** en T2a, rien ne crée `mise-a-jour\` à l'installation, et c'est
l'état du cabinet après la visite tant qu'aucun `appliquer` n'a tourné. Un
programme de la session de la praticienne, **non administrateur**, crée alors
`C:\BilanPosturo\mise-a-jour\arret.demande` avec
`{"jeton": <32 hex>, "calme_secondes": 0, "demarrage": false}`. Le serveur SYSTEM
l'accepte s'il est au calme, quitte en code 0 et n'est pas relancé.

C'est une **primitive nouvelle**. Jusqu'ici, un non-administrateur pouvait au pire
modifier des fichiers, avec effet au prochain démarrage. Il ne pouvait pas arrêter
le processus SYSTEM.

Variante sans aggravation, mais à savoir : un `mise-a-jour\` pré-rempli
(`etat.json` à `bascule`, `sauvegarde\inventaire.json`,
`sauvegarde\serveur\serveur.py` de son choix) serait « restauré » par SYSTEM au
premier `appliquer`, car seul le dossier est re-protégé.

**Propriété à rétablir :** le serveur ne lit de demande que dans un dossier dont
la protection est établie. Et la première protection du dossier vaut aussi pour
ce qu'il contient, ou part d'un dossier vide. Le point de C6, « racine
inscriptible », devient une condition de déploiement du client sur le parc.

### Faible — Quatre gardes ne sont mises en échec par aucun test

**Où et effet si la garde tombait :**
- **X15** — `effacer_demandes_perimees` (`serveur.py:1980`). Une demande laissée
  par une coupure entre son écriture et sa lecture arrêterait le serveur
  relancé par la tâche dans la seconde, en code 0, sans relance, et sans
  personne pour l'attendre. C'est exactement ce que la garde évite, et rien ne
  la tient.
- **X6** — restauration d'`installe.json` au retour (erratum 7,
  `maj.py:1274-1280`). Une coupure entre `ecrire_installe` et `repos`
  laisserait des fichiers gérés de la version quittée. La montée suivante
  jugerait alors `SCHEMA_MODIFIE_LOCALEMENT` contre la mauvaise empreinte, et
  effacerait d'après la mauvaise liste.
- **X9** — `attendre_fin_depots` (`serveur.py:2710`). Un dépôt commencé entre la
  décision et la fin de `serve_forever` serait tué à la sortie du processus.
  Le PDF reste atomique et la tablette renvoie, mais c'est un aller-retour
  devant le patient.
- **X7** — la comparaison `realpath` de `preparer_dossier_prive`
  (`maj.py:576-583`) est, sous Windows, la **seule** barrière contre une
  jonction à la place de `mise-a-jour\`. `lstat` rend `S_IFDIR` pour une
  jonction, et CPython ne mappe en `S_IFLNK` que les liens symboliques. Le test
  existant n'éprouve qu'un lien POSIX, que le `lstat` arrête déjà.

**Propriété à rétablir :** chacune de ces gardes fait rougir un test nommé, sous
`python3` et `-O`. Pour X7, le test se joue là où la garde est seule, c'est-à-dire
sous Windows (CI administrateur disponible).

### Observation — Liens et jonctions posés pendant la bascule (point 3 de l'implémenteur)

**Où :** `serveur/maj.py:365-377` (`creer_parents`), `:1074-1101` (`poser_fichiers`),
`:1382-1385` et `:1269-1273` (effacements).

**Réponse à la question posée : oui, si la racine est inscriptible.** Le contrôle
`confiner_sous_racine` est fait avant la bascule. Pendant la bascule,
`creer_parents` ne regarde que `S_ISDIR(lstat)`, qui est **vrai pour une
jonction** sous Windows. Son commentaire, « sans jamais traverser un lien », est
donc inexact sous Windows.

Un programme de la session qui remplace `docs\` par une jonction entre le contrôle
et la pose redirige :
- les écritures SYSTEM (contenu : celui du paquet signé ; noms : ceux du
  manifeste) ;
- les effacements SYSTEM (fichiers retirés d'`installe.json`, `absents` au
  retour).

La même précondition permet aussi de réécrire un `.maj-tmp` entre son empreinte et
son `os.replace`.

**Ce n'est pas une aggravation.** La même précondition permet déjà de remplacer
`serveur\serveur.py`, exécuté en SYSTEM. Sur une racine réservée aux
administrateurs, aucun de ces chemins n'existe. L'erratum 1 lui-même est juste :
un fichier renommé sur le même volume garde son descripteur. Le temporaire posé à
côté de sa destination hérite des droits du dossier, et `.maj-tmp` n'est ni servi
(filtre d'extensions) ni admis comme destination (X1 rouge). Le nettoyage au retour
est éprouvé par le bout en bout (X5 rouge en `Interruption`).

### Observation — Sonde `/sante` en TLS non vérifié (point 2, D14)

Aucun identifiant n'est envoyé. La sonde s'adresse à `127.0.0.1` seulement, lit
64 octets et exige le corps exact. Elle est acceptable. La justification de D14,
« occuper le port, il faudrait être administrateur », est cependant inexacte pour
la fenêtre où le serveur est arrêté : n'importe quel processus local peut écouter
sur `127.0.0.1:<port>`. L'effet se limite à tromper le verdict (une version cassée
gardée ; l'auto-contrôle tourne quand même). Rien ne sort.

### Observation — Activité non authentifiée (point 6)

`noter_activite` est appelée avant l'authentification
(`serveur.py:2290`). **Empêcher :** oui. Une requête non authentifiée toutes les
`calme_secondes` suffit à refuser indéfiniment l'arrêt (S2 : un seul 401 fait
`ARRET_REFUSE`). **Déclencher :** non. L'arrêt ne part que d'un fichier, et un
`POST` non authentifié ne tient `DEPOTS_EN_COURS` que le temps du PBKDF2.
L'exception d'une `surveiller_demande_arret` qui avale tout ne fait que reprendre
la boucle. Ce déni de service est acceptable en T2a : il ne retarde qu'une mise
à jour, il est visible sur `/etat`, et l'opérateur dispose de `--calme-minutes 0`.
C5-T2b, sans opérateur, devra le peser : un appareil du réseau qui sonde la page
d'accueil suffirait à geler les mises à jour de ce PC.

### Observation — `serveur.py` importe `paquet_signe` (point 5, erratum 8)

**Nécessaire :** défendable, puisque c'est « dériver, ne pas transcrire » le
motif de version et la lecture JSON stricte. Mais le contrat entre modules repose
sur deux noms **privés** (`_lire_json_strict`, `_VERSION`, `serveur.py:1579`,
`:1640`). Un renommage dans `paquet_signe.py` empêcherait le serveur de
démarrer, et sous `pythonw` sans un mot. Une telle version reviendrait seule par
`SANTE_MUETTE`.

**Effet sur `maintenance-cabinet-01` :** nul pour un correctif fabriqué depuis
cette branche, qui embarque son propre `serveur.py` sans l'import. Le risque
n'existe que si un `serveur.py` de `main` est recopié **seul** au cabinet : le
serveur ne démarre plus.

### Observation — `revenir_a_la_sauvegarde` attrape `Exception` (point 4)

Acceptable. Trois tentatives, puis `echec-retour`, puis le serveur est relancé
quand même. `repr(erreur)` ne va qu'à `journal.log`, `technique.log` ne reçoit
que la cause fermée. `KeyboardInterrupt` et `SystemExit` passent et laissent
l'étape `retour`, que `reprendre` rejoue. Une erreur de programmation est absorbée
en `echec-retour`, mais reste visible. Le premier `ecrire_etat(etape="retour")`,
hors du `try`, ne fait que laisser l'étape précédente, elle aussi reprenable.

### Observation — Reprise et `installe.json` (point 7)

Les séquences de coupure examinées sont cohérentes :
- pendant la sauvegarde, l'étape `preparee` ne déclenche rien ;
- pendant la bascule, X17 est rouge au bout en bout ;
- entre `ecrire_installe` et `repos`, le retour restaure aussi `installe.json`
  (erratum 7), mais la garde n'est pas éprouvée (X6 ci-dessus).

À savoir : en T2a, « défait seul après une coupure » (§1) ne vaut qu'au **prochain
geste** (`appliquer`, `revenir`, `reprendre`). Jusque-là, la tâche du serveur
démarre sur des fichiers mêlés. `docs/mise-a-jour.md` §4 le dit. T2b le
fermera.

## Rubriques sans constat

1. **Données de santé.**
   - `maj.py` ne lit ni `bilans/` ni `dossier_pdf`. Il calcule seulement la forme
     résolue de `dossier_pdf` pour l'exclure, et ne lit pas `journal.log`.
   - `technique.log` ne reçoit que `detail_maj` : champs fermés, codes membres de
     `CODES_MAJ` ∪ `paquet_signe.CODES`, versions passées par `analyser_version`.
   - La garde de bout en bout (A12, `tearDownModule`) a passé sur tous mes bacs ;
     le détail libre va seulement dans `journal.log` et sur la console.
   - Aucun réseau en T2a (garde AST). Rien n'est écrit sous `formulaire/` hors
     des fichiers du paquet.
   - `/etat` : cinq champs validés un à un, illisible partout au moindre écart
     (X10 rouge) ; aucun chemin ni adresse.
2. **Surface exposée.**
   - Aucune route ajoutée ; `/sante` reste la seule exception (garde AST de C4-T3
     verte) et reste muette dans les deux journaux.
   - `noter_activite` n'écrit rien. Racine web et `EXTENSIONS_SERVIES` inchangés.
   - `.maj-tmp` n'est pas une extension servie. `git diff 1a84caf..HEAD --
     formulaire/` et `git diff main...HEAD -- formulaire/` sont vides.
3. **Authentification et cryptographie.**
   - Ce sont les clés **installées** qui jugent (`maj.py:787-797`, M1 rouge) ; la
     rotation ne prend effet qu'au paquet suivant ; auto-contrôle avant de garder
     une version.
   - L'anti-retour (`verifier_paquet`) et les versions écartées ont été relus.
   - Clé de publication distincte, absente du dépôt. Authentification du serveur
     inchangée.
4. **Écriture de fichiers.**
   - Extraction par `zipfile` seul, d'après les noms du manifeste, triés :
     `valider_chemin` rejoué, `orig_filename` comparé, `O_EXCL`, lecture bornée à
     `taille + 1`, puis **relecture et SHA-256** de chaque fichier écrit (M2).
   - Liste blanche, puis exclusions insensibles à la casse (X12 rouge), puis
     `dossier_pdf` (X13 rouge), puis `confiner_sous_racine`.
   - Les points finaux, espaces, `:` et noms réservés sont déjà refusés par
     `valider_chemin` : `formulaire/images/cabinet./logo.png` n'atteint pas le
     logo.
   - `config.json`, `*.pem`, `*.key`, `*.crt`, `*.log`, `bilans/`, `mise-a-jour/`
     et `__pycache__` ne peuvent être nommés par aucun paquet.
   - Temporaire dans le dossier de destination, `fsync`, puis `os.replace`.
   - Ordre : rien hors de `mise-a-jour/` avant l'étape `bascule`, hors traces
     (A6 ; X17 rouge au bout en bout).
5. **Robustesse de service.** Hors les constats ci-dessus :
   - lectures bornées partout (archive 64 Mio, manifeste, signature,
     `etat.json`, demande d'arrêt), `lstat` avant `open` ;
   - verrou inter-processus relâché à la mort du processus (M15, test
     multi-processus) ;
   - racine contenant `.git` refusée en code 2 avant tout geste ;
   - surveillance de l'arrêt démarrée dans le `try` de `serve_forever` ;
     `shutdown()` appelé avant que la boucle tourne sort quand même (sémantique
     de `socketserver`) ;
   - journaux écrits par deux processus : chaque ligne ouvre, ajoute, ferme. Une
     rotation concurrente ratée est tolérée (`_rotation_ratee`, renommage en
     deux temps) et la purge ne réécrit jamais le journal courant. Je n'ai pas
     trouvé de chemin de perte de ligne.
6. **Côté navigateur.** Sans objet : aucun changement sous `formulaire/`. La
   ligne « Mise à jour » de `/etat` passe par `html.escape`.
7. **Chaîne d'approvisionnement.**
   - Signature et empreinte de l'archive sont vérifiées **avant** toute
     extraction, sur une copie privée.
   - Le retour arrière est automatique (A1, A4, A5), à la réserve du constat
     Moyen. Une version antérieure est refusée.
   - `config.json`, certificats et clés, journaux, `bilans/`, `dossier_pdf` et
     logo restent hors d'atteinte (A3, A7). Un schéma retouché sur place n'est
     jamais écrasé (A10, M16).
   - Version publiée par `version.json` seul. `schtasks` et `icacls` sont appelés
     par chemin absolu, arguments en liste, sans shell.
   - SDDL relu et exigé exactement `D:P` + `SY` + `BA` : la logique a été relue,
     la CI Windows l'exécute.
8. **Conformité.** Rien ne sort du PC en T2a. Aucun stockage chez l'éditeur, aucun
   sous-traitant nouveau, aucune aide à la décision. Les journaux restent soumis à
   la purge de six mois : `maj.py` écrit par les fonctions du serveur, interrupteur
   et durée lus dans `config.json`.

## Points à surveiller plus tard

- **C5-T2b :**
  - corriger d'abord le constat Moyen, dont la séquence deviendra nocturne et
    sans témoin ;
  - peser le blocage par activité non authentifiée et par dépôt figé, qui
    seraient silencieux sans opérateur ;
  - faire créer `mise-a-jour\` protégé par l'installateur, qui ferme le Faible
    sur le fichier d'arrêt dès l'installation ;
  - la sauvegarde remplacée par une tentative reportée y deviendra fréquente.
- **Fiche `docs/essais/C5-T2-windows.md`, A2** : relever les droits de
  `C:\BilanPosturo`. S'ils sont ouverts aux utilisateurs, ouvrir le constat C6
  **avant** d'activer le client sur un poste, car c'est la précondition commune
  de trois points ci-dessus.
- Sur la VM, provoquer une consultation de `/etat` pendant `appliquer`, et
  observer `PermissionError` sur `arret.reponse` / `etat.json`.
- Rendre publics, ou tester comme contrat, `_lire_json_strict` et `_VERSION`,
  désormais lus par le serveur.
