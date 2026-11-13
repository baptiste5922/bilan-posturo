# Audit C5-T2a — Client de mise à jour : application locale, retour arrière, traces

**Date :** 2026-11-12  **Périmètre audité :** `git diff 1a84caf..30ffd4d` (branche
`c5-t2a-application`, 8 commits) : `serveur/maj.py` (nouveau, 1 610 l.),
`serveur/serveur.py` (+423), `serveur/paquet_signe.py`, `outils/faire-paquet.sh`,
`outils/signer-paquet.py`, `.gitignore`, tests et documentation. Lu dans son
contexte : `confiner_sous_racine`, `forme_comparable`, `ecrire_atomiquement`,
`journaliser*`, `faire_tourner_journal`, `do_POST`, `demarrer()`,
`installer-demarrage.ps1`, `formulaire/script.js` (sondes de la tablette).
Contrat `docs/contrats/C5-T2.md`, §10 et errata §13.
**Verdict :** CONFORME SOUS RÉSERVE (premier passage, `30ffd4d`) — **CONFORME au réaudit** (`1419493`, section « Réaudit » en fin de document)

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

---

# Réaudit

**Date :** 2026-11-12  **Périmètre :** `git diff 7b5ad54..1419493` : `serveur/maj.py`,
`serveur/serveur.py`, `serveur/paquet_signe.py`, tests, errata 12 à 18 du contrat.
Le reste de `serveur.py` a été relu pour les régressions : `get_request`,
`handle_one_request`, `log_message`, `do_POST`.
**Verdict :** CONFORME

## Ce qui a été rejoué

- **Témoin** sur une copie `git ls-files -z` de `1419493` sans `origin` :
  `test_maj`, `test_maj_bout_en_bout`, `test_maj_windows`, `test_serveur` et
  `test_integration` passent (387 tests, Python 3.14 avec `cryptography`, 12
  sautés). `test_maj` et `test_serveur` passent aussi sous `/usr/bin/python3 -O`
  (3.9.6). Aucun `assert` nu ni dans `maj.py` ni dans `serveur.py`.
- **CI `43263305981`** relue : tête `1419493`, succès. Sous `windows-latest`, ces
  tests sont **exécutés** (`... ok`) :
  `test_vraie_jonction_a_la_place_du_dossier_reserve` (une vraie jonction faite
  par `mklink /J`), `test_proprietaire_de_la_racine_jetable_se_lit` (ctypes),
  `test_jonction_simulee_*`, `test_demande_dans_un_dossier_qui_n_est_pas_de_confiance_est_ignoree`.
- **Mes sondes de scénario de l'audit, rejouées** sur un serveur réel en bac à
  sable :

| Sonde | Avant | Après |
|---|---|---|
| S1b : `arrete` jamais écrit | code 3, serveur **laissé arrêté** | code 3, **serveur relancé**, `/sante` répond |
| S2 : tentative reportée puis `revenir` | `RETOUR_IMPOSSIBLE` | code 0, « Version 1.1.0 remise en place » |
| S3 : dépôt figé, puis `appliquer` | `ARRET_REFUSE depot-en-cours` après 40 s | après 126 s : **code 0**, mise à jour appliquée |
| S5 (nouvelle) : dépôt lent mais actif, un morceau toutes les 28 s, 168 s au total | — | **200**, PDF identique octet pour octet |

- **Mes mises en échec** (ancre unique, témoin vert, restauration contrôlée par
  SHA-256, `python3` et `python3 -O`) : 9 mutations, toutes rouges.

| # | Mutation | Rougit |
|---|---|---|
| Y1 | confiance POSIX : écriture du groupe ou des autres admise | `DossierReserve`, `ObeissanceALaDemandeDArret.test_criteres_posix` |
| Y2 | confiance POSIX : propriétaire non vérifié | `test_proprietaire_etranger_ou_lien_ou_fichier_refuses` |
| Y3 | `vider_contenu` suit les liens (`stat` au lieu de `lstat`) | `test_contenu_pose_a_l_avance_est_vide_sans_suivre_de_lien` |
| Y4 | relecture de confiance après protection retirée | `test_dossier_qui_n_est_pas_de_confiance_apres_protection_est_refuse` |
| Y5 | ancienne sauvegarde non remise en place si la substitution échoue | `test_substitution_qui_echoue_remet_l_ancienne` |
| Y6 | drapeau d'acceptation jamais posé | survit aux unitaires, dont les tests simulent l'acceptation eux-mêmes ; **rouge** au bout en bout (`AbandonApresAcceptation`, deux tests) |
| Y7 | écriture patiente réduite à un essai | `EtatSousLecture`, `EcrituresPatientes` |
| Y8 | délai d'inactivité retiré | `test_delai_d_inactivite_des_connexions` |

  Le registre de l'implémenteur (R1 à R14) a été relu. Les gardes que j'avais
  trouvées non éprouvées (X15, X6, X9, X7) y sont reprises en R9 à R12, et je ne
  les ai pas rejouées une à une. Y1 à Y8 portent sur la nouvelle surface.

## Sort des constats

**Moyen, serveur accepté jamais relancé : corrigé.**
- Dès l'acceptation, `demander_arret` pose un drapeau. Toute sortie d'`appliquer`
  passe ensuite par le `except BaseException` qui appelle `assurer_serveur`
  (`maj.py`, fonction `appliquer`) : refus, exception ou `KeyboardInterrupt`.
- `assurer_serveur` n'est appelée qu'après une acceptation ; un refus ne relance
  rien.
- L'étape `bascule` est écrite dans le `try` de `basculer`.
- `arret.reponse` et `etat.json` s'écrivent avec 40 reprises de 50 ms sur
  `PermissionError`.
- Démontré par S1b, et Y6 et Y7 rougissent.
- Résidu en observation ci-dessous.

**Faible, sauvegarde détruite par une tentative reportée : corrigé.**
- La sauvegarde est bâtie et relue avant l'arrêt, mais n'est adoptée qu'après
  l'acceptation.
- L'ancienne passe par un renommage et revient si la substitution échoue (Y5
  rouge).
- `sauvegarde-neuve/` est effacée dans tous les cas (`finally`).
- Démontré par S2.

**Faible, dépôt figé : corrigé.** `Gestionnaire.timeout = 120` est posé par
`StreamRequestHandler.setup()` sur la socket acceptée. C'est un délai **par
opération**, pas une durée totale : S5 le montre, un envoi de 168 s qui avance
aboutit. Les effets vérifiés :
- **Dépôt en cours :** un délai dépassé lève `TimeoutError` dans `rfile.read`,
  que `BaseHTTPRequestHandler.handle_one_request` rattrape. `sortir_depot` passe
  par le `finally`, rien n'est écrit sous `bilans/`, et la ligne va dans
  `journal.log` par `log_error`. `technique.log` ne reçoit pas d'adresse
  (`log_message` inchangé).
- **File de la tablette :** aucun effet. La tablette abandonne d'elle-même un dépôt
  au bout de 20 s (`DELAI_DEPOT`, `script.js:13`) et le garde dans sa file. Le
  délai serveur de 120 s de silence ne coupe donc jamais un envoi que la tablette
  attendrait encore.
- **Réponses lentes à lire :** le délai s'applique de la même façon à l'écriture.
  Je n'ai pas trouvé de régression.

**Faible, fichier d'arrêt dans un dossier non vérifié : corrigé.**
- **Côté serveur :** il n'obéit qu'après `dossier_reserve_de_confiance`, sinon il
  efface la demande et l'écrit une seule fois dans `journal.log`.
- **Sous Windows :** le SDDL doit être exactement `D:P` + `SY` + `BA`, **et** le
  propriétaire doit être SYSTEM ou Administrateurs.
- **Ailleurs :** le propriétaire doit être le compte du serveur ou root, sans
  écriture pour le groupe ni les autres.
- **Correctif de l'erratum 17 (« comparaison vide »), vérifié de près :**
  - l'attendu est bâti à partir de `realpath(parent)` et du **nom non résolu**,
    puis comparé à `forme_comparable(dossier)` ;
  - une jonction ou un lien à la place du dossier lui-même fait donc différer
    les deux formes ;
  - un parent résolu (`/var` → `/private/var`, nom court 8.3) les laisse égales ;
  - j'avais écrit au premier audit que la logique était « correcte, simplement
    non éprouvée » : c'était faux, l'implémenteur a eu raison de le relever ;
  - c'est une vraie jonction qui est éprouvée sous Windows en CI.
- **La surface ctypes de `proprietaire_windows` est raisonnable :**
  - `argtypes` et `restype` sont déclarés pour les trois fonctions, et l'arité
    de `GetNamedSecurityInfoW` est conforme (8 paramètres) ;
  - les tampons sont libérés par `LocalFree` dans un `finally` ;
  - aucune donnée ne vient du réseau : le seul argument est un chemin construit
    par le serveur ;
  - toute `OSError` vaut « non » ;
  - l'appel n'a lieu, comme `icacls`, que si une demande existe, et pas à chaque
    sonde.
- **`vider_contenu` ne suit aucun lien :**
  - `lstat` d'abord ;
  - un lien est retiré, jamais sa cible ;
  - un sous-dossier passe par `shutil.rmtree`, qui depuis Python 3.8 retire une
    jonction **sans la parcourir** (bpo-37834) ;
  - il n'a lieu qu'après le refus d'une jonction à la place du dossier ;
  - Y3 rougit.

**Faible, quatre gardes non éprouvées : corrigé.** R9 à R12 du registre ; la
jonction est éprouvée pour de vrai sous Windows.

## Observations du réaudit

### Observation — Résidu : arrêt accepté mais aucune réponse lue

**Où :** `maj.py`, `demander_arret`, première boucle (`ARRET_SANS_REPONSE`
« le serveur n'a pas répondu »).

**Scénario (sonde S4, simulé) :** si **les deux** écritures `accepte` et
`arrete` échouent, `maj.py` sort avant d'avoir vu l'acceptation. Le serveur, lui,
a accepté et quitte : il reste arrêté (S4 : code 3, `/sante` muette).

Il faudrait deux refus de remplacement soutenus chacun plus de 2 s (40 × 50 ms).
Autre voie : un `accepte` perdu suivi d'un `arrete` qui arrive après les 30 s de
`delai_reponse`. Pour cela, il faut qu'un dépôt ait commencé dans la seconde qui
suit la décision et qu'il dure plus de 30 s, ce que la tablette elle-même
abandonne au bout de 20 s.

Improbable. Un `/Run` y serait inoffensif, puisque `assurer_serveur` est sans
effet sur un serveur qui tourne. À reprendre en C5-T2b, où personne ne
regardera la console.

### Observation — Ordre « vider puis protéger » dans `preparer_dossier_prive`

Sur un dossier existant qui n'est pas de confiance, le contenu est vidé
**avant** que `icacls` retire à l'utilisateur le droit d'y créer des fichiers.
Un programme qui reposerait en boucle `etat.json` (étape `bascule`) et une
`sauvegarde/` dans cet intervalle pourrait voir son contenu survivre.
`dossier_reserve_de_confiance` ne vérifie que le dossier, pas son contenu.

La précondition reste une racine inscriptible par l'utilisateur, qui permet déjà
de remplacer `serveur\serveur.py` directement : ce n'est **pas une aggravation**.
Mais la variante que le correctif voulait fermer ne l'est qu'en l'absence de
course. Protéger d'abord, puis vider, la fermerait aussi. À traiter avec le point
C6 de la racine inscriptible, ou en T2b, quand l'installateur créera le dossier
protégé.

### Observation — Ce que le serveur lit encore sans vérifier le dossier

- `effacer_demandes_perimees` (au démarrage) efface `arret.demande` et
  `arret.reponse` sans contrôle de confiance. Sur un `mise-a-jour` remplacé par une
  jonction (racine inscriptible), SYSTEM efferait deux fichiers **de ces noms
  exacts** dans le dossier cible. Les liens ne sont pas suivis : seule la jonction
  du dossier lui-même le permettrait.
- `/etat` lit `etat.json` sans contrôle de confiance. Les valeurs restent fermées
  (étape, code, version) : au pire un affichage trompeur, jamais une fuite.
- Le dossier temporaire de `lire_sddl_windows` naît dans le `%TEMP%` de SYSTEM,
  sous un nom aléatoire que les utilisateurs ne peuvent pas lister.

Sans conséquence au-delà de la précondition déjà connue.

### Observation — Poignée de main TLS sans délai (antérieure, erratum 15)

Hors périmètre : je n'en fais pas un constat de cette tâche, qui ne l'aggrave
pas. Je la signale parce qu'elle est plus grave que le dépôt figé corrigé
ici. La socket d'écoute est enveloppée (`serveur.py`, `contexte.wrap_socket`), donc
la poignée de main a lieu dans `accept()`, sur le fil de `serve_forever`, **sans
délai**. Une seule connexion TCP muette, ouverte depuis le réseau local **sans
identifiant**, fige l'acceptation de toutes les autres : plus de dépôt, plus de
`/sante`. Le délai de 120 s ne s'applique qu'après, dans `setup()`. **À ouvrir en
C6, avec une gravité élevée.**

## Rubriques sans constat (réaudit)

1. **Données de santé.**
   - La ligne « demande d'arrêt ignorée » va dans `journal.log` seulement, sans
     chemin.
   - `assurer_serveur` écrit « sante ok / SANTE MUETTE » dans `journal.log`.
   - `technique.log` reste fermé (A12 vert au bout en bout).
2. **Surface exposée.**
   - Aucune route ajoutée ; `/sante` reste la seule non authentifiée.
   - `ctypes` et `subprocess` sont importés par `serveur.py` mais ne servent que
     le contrôle du dossier réservé, sur un chemin interne.
   - Aucune entrée réseau n'y parvient.
3. **Authentification.** Inchangée. Ce sont toujours les clés installées qui
   jugent.
4. **Écriture de fichiers.**
   - `ecrire_atomiquement_patient` ne reprend que sur `PermissionError` et
     relève la dernière erreur.
   - Le temporaire `.part` est toujours effacé (`except BaseException` de
     `ecrire_atomiquement`).
5. **Robustesse.**
   - 40 × 50 ms, soit au plus 2 s de reprise sur le fil de surveillance : sans
     effet sur les dépôts.
   - Le délai de connexion est borné.
   - La sauvegarde reste unique, plus un renommage transitoire
     (`sauvegarde-avant`) compté pour D7.
6. **Navigateur.** Sans objet : `formulaire/` est inchangé.
7. **Mises à jour.**
   - L'ordre est conservé : rien hors de `mise-a-jour/` avant la bascule.
   - La sauvegarde n'est adoptée qu'une fois l'arrêt accepté.
   - Le retour arrière est éprouvé (A1, A4, A5, et S2).
8. **Conformité.** Rien ne sort du PC. Aucun sous-traitant ni stockage nouveau.

## Verdict du réaudit

**CONFORME.** Les cinq constats sont corrigés, démontrés par mes sondes S1b,
S2, S3 et S5, et tenus par des gardes qui rougissent (Y1 à Y8, R1 à R14).
Restent quatre observations. Deux sont à porter en C5-T2b ou en C6 : le résidu
« arrêt accepté jamais vu », et l'ordre « vider puis protéger ». La poignée de
main TLS sans délai, antérieure à la tâche, est à ouvrir en C6 avec une gravité
élevée.

---

# Contrôle des corrections de revue

**Date :** 2026-11-13  **Périmètre :** `git diff a085b59..8991a2f`, ciblé sur
`serveur/serveur.py` (`Gestionnaire.log_error`, `traiter_post`), `serveur/maj.py`
(`attendre_sante`) et `docs/essais/C5-T2-windows.md`. Le reste de la plage (noms
rendus publics, guides, documentation) a été parcouru sans constat.
**Verdict :** CONFORME

**CI `43276781553`** relue : tête `8991a2f`, 7 jobs verts.

## Ce qui a été éprouvé

Copie `git ls-files -z` de `8991a2f`, sans `origin`. Chaque mutation est jouée
avec témoin et restauration contrôlée par SHA-256, en `python3` et en `python3 -O`.

| # | Mutation | Rougit |
|---|---|---|
| Z1 | `log_error` muet pour **toute** erreur | `ExpirationDuDelaiDInactivite.test_les_autres_erreurs_restent_tracees` |
| Z2 | filtre retiré (l'expiration est journalisée comme avant) | `test_connexion_jamais_utilisee_est_muette_dans_les_deux_journaux` |
| Z3 | expiration du corps non rattrapée dans `traiter_post` | `test_expiration_pendant_le_corps_est_un_transfert_interrompu`, `test_expiration_puis_reponse_impossible_ne_leve_pas` |
| Z4 | une relance en erreur rend « sain » | `ArretCoteClient.test_une_relance_en_erreur_n_empeche_pas_le_verdict_negatif` |
| clé | `cles_publication.json` portant `publication-2026-essai` | test vert tant que le fichier n'est pas suivi ; **rouge** une fois `git add` fait, aussi sous `-O` (`Documentation.test_aucune_cle_d_essai_n_est_versionnee`) |

## 1. `log_error` et les journaux — sans constat

**Ce qui est rendu muet.** La surcharge ne retient que le **format** littéral de
la bibliothèque, `"Request timed out: %r"`. Ce texte fixe est écrit par
`BaseHTTPRequestHandler.handle_one_request`. Le contenu venu du client passe
dans `args`, jamais dans `format` : aucune requête ne peut se faire passer pour
une expiration.

**Ce qui reste journalisé.** Les autres appels passent par `send_error` (format
`"code %d, message %s"`) :
- les refus de C6-T5 (ligne de requête malformée, forme absolue, etc.) ;
- les 404 et 403 ;
- `TLS_REFUSE`, écrit dans `get_request`, hors de `log_error`.

Tout cela est tracé comme avant, et Z1 rougit.

**Rien de muet qui était tracé avant C5-T2a.** Une expiration n'existait pas
avant C5-T2a, puisque le délai de 120 s est apparu avec cette tâche. Est
désormais muette, en plus de la connexion jamais utilisée, une requête dont la
ligne ou les en-têtes s'arrêtent en route. L'interrompre ne produit aucun effet :
la requête n'a jamais été exécutée.

**Dépôt interrompu.**
- `rfile.read` qui lève une `OSError` (délai ou rupture ; `ssl.SSLError` en hérite)
  donne la même branche qu'un corps tronqué : `DEPOT refus motif=transfert-interrompu`.
- La réponse 400 est protégée contre une socket morte.
- Rien n'est écrit sous `bilans/`.
- `sortir_depot` passe toujours par le `finally`.

**Rien de nouveau dans `technique.log`.** Il reçoit :
- `detail_refus_depot` (vocabulaire fermé) ;
- la ligne `REPONSE` de `log_message`, inchangée (route en classe fermée, sans
  adresse).

L'adresse ne va qu'à `journal.log`.

## 2. Relance non fatale dans `attendre_sante` — sans constat

Seul l'appel à `relancer()` **pendant** l'attente est protégé, par
`except Exception` : `KeyboardInterrupt` passe.

Le verdict rendu est uniquement celui de `sante_repond` : `True` seulement
après un `200` dont le corps vaut exactement `{"etat":"ok"}`, `False` au délai
dépassé. Aucun chemin ne déclare sain un serveur muet (Z4 rougit).

Le premier `pilote.demarrer()` de `basculer` et de `_restaurer` reste hors de la
protection, et donc fatal. Une tâche réellement absente continue de produire un
refus et un retour.

## 3. Fiche d'essai et clé d'essai — sans constat

La séquence de `docs/essais/C5-T2-windows.md` part d'une copie
`git ls-files -z` dans `$ESSAI` (`mktemp -d`), hors du dépôt. Elle y écrit :
- `serveur/cles_publication.json` dans la copie ;
- la clé privée dans `$ESSAI/cles`.

La fiche interdit de copier la clé privée sur la VM et fait effacer `$ESSAI` à la
fin. Aucune instruction ne pose une clé d'essai dans le dépôt.

**Garde.** Elle lit l'index (`git ls-files -z`) et mord dès que la liste est
suivie avec un nom contenant `essai`.

Deux limites, sans conséquence aujourd'hui :
- elle relit le fichier **du disque**, pas le blob indexé ;
- elle ne reconnaît une clé d'essai qu'à son nom.

Le contrôle « aucun secret versionné » de la CI reste la barrière pour la clé
privée.

## Verdict

**CONFORME.** Les trois corrections sont justes et chacune est tenue par une
garde qui mord. Aucune adresse ni aucun chemin n'entre dans `technique.log`.
Aucune erreur journalisée avant C5-T2a n'est rendue muette.
