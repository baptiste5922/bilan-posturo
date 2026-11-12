# Revue C5-T2a — Client de mise à jour : application locale, retour arrière, arrêt concerté

**Date :** 2026-11-12  **Verdict :** À CORRIGER (fiche d'essai, un test, trois documents ; le code livré est bon et n'appelle aucun nouvel audit)
**Tests :** `python3 -m unittest discover -s tests` exécuté par moi, redirigé vers un fichier (Python 3.14.3, macOS) : **892 tests en 328 s, 1 échec, 19 sautés**. L'échec est `test_integration.ServeurArret.test_arret_journalise`, l'artefact déjà consigné dans `CLAUDE.md` (processus lancé par `(… &)` d'un shell non interactif : SIGINT ignoré) ; rejoué seul au premier plan : `OK` en 1,6 s. Les classes de bout en bout ne sont pas sautées (`cryptography` présente). `python3 -m pyflakes serveur/ tests/` muet. `test_maj` et `test_paquet` sous `-W error::ResourceWarning` : 144 verts ; `test_maj` sous `python3 -O` : 127 verts. `git diff main -- formulaire/` vide. `grep` d'`assert` nu dans `serveur/maj.py` et `serveur/serveur.py` : rien. Syntaxe des 7 fichiers touchés relue avec `ast.parse(feature_version=(3, 9))` : valide. CI : run 43263305981 sur `1419493`, 7 jobs verts (3.9 et 3.13, Linux, Windows, macOS) ; `a085b59` ne touche que `docs/ROADMAP.md` et `docs/audits/C5-T2a.md`. `git status` propre avant et après. Aucun fichier du cabinet lu, aucun `serveur.py`/`maj.py` lancé depuis le dépôt (la copie de mutation est dans le dossier de travail, par `git ls-files -z`, avec son propre `git init` sans `origin`).

## Critères d'acceptation

| Critère | Vérifié par | Résultat |
|---|---|---|
| A1 retour seul, 4 variantes + second `appliquer` | `Retour` (bout en bout, serveur réel), exécuté | OK |
| A2 dépôt en cours non altéré | `DepotEnCours` (2 tests), exécuté | OK |
| A3 trois montées, config et journaux intacts | `TroisMontees`, exécuté | OK |
| A4 coupure à k ∈ {1, 3, 5}, et pendant le retour | `Interruption` (`os._exit` dans un sous-processus), exécuté | OK |
| A5 retour impossible | `RetourImpossible`, exécuté | OK |
| A6 rien hors `mise-a-jour/` avant la bascule | `RefusSansEcriture` (`test_maj`), exécuté | OK |
| A7 / A8 liste blanche, dérivée du paquet réel dans les deux sens | `ListeBlanche`, `ListeDerivee` (sautée sous Windows, jouée ici et en CI Linux/macOS) | OK |
| A9 clés installées seules, rotation | `ClesInstallees` + `Rotation` (bout en bout) | OK |
| A10 / A11 schéma retouché, `MAX_PATH` | `SchemaModifie`, `MaxPath` | OK |
| A12 traces | `Traces` + `tearDownModule` du bout en bout (garde qui mord : `GardeDesTraces`) | OK |
| A13 `/etat` | `EtatDeLaMiseAJour` (15 cas), `test_integration` (14 clés) | OK |
| A14 arrêt concerté, table de `decider_arret` | `DeciderArret`, `SurveillanceDeLArret`, `ArretConcerte` (serveur réel) | OK |
| A15 / A16 verrou, dépôt de développement | `Verrou`, `DepotDeDeveloppement` | OK |
| A17 Windows réel | `test_maj_windows` : **sauté ici (Mac)**, vert en CI `windows-latest` sur 3.9 et 3.13 (run 43263305981) | OK en CI seulement ; voir Important 3 sur ce qu'il ne touche pas |
| A18 gardes statiques | `GardesStatiques` ; la garde stdlib est sautée sous 3.9 (`stdlib_module_names`), jouée sous 3.13 en CI | OK |
| A19 pas d'`assert` nu, suites, `-O`, CI | commandes ci-dessus | OK |
| A20 `formulaire/` intact, `maj.py` dans l'archive | `git diff`, `test_paquet` (+ le test d'archive incomplète) | OK |
| A21 mises en échec M1 à M20 | consignées dans `docs/audits/C5-T2a-mises-en-echec.md` ; **rejouée par moi : une mutation de plus, qui n'est pas dans la liste, et que rien ne voit** (Important 2) | OK sur la liste du contrat |
| A22 fiches | fichiers présents, `Documentation` vert ; mais **la fiche d'essai ne se déroule pas dès sa première commande** (Important 1) | À CORRIGER |

Erratum du contrat : les 18 errata du §13 correspondent au code relu (temporaire à côté de la destination, `ETAT_ILLISIBLE`, `adopter_sauvegarde` après l'acceptation, `assurer_serveur`, `Gestionnaire.timeout`, `dossier_reserve_de_confiance`, `forme_non_resolue`, noms publics). Aucune étape du plan n'a été sautée en silence. Le périmètre n'est pas dépassé : pas de réseau, pas de seconde tâche.

## Remarques

### Important — La fiche d'essai Windows ne se déroule pas : la clé d'essai est refusée, puis `signer` refuse le paquet
**Où :** `docs/essais/C5-T2-windows.md:15-20` (« Clés d'essai »)
**Problème :** deux défauts, le premier vérifié par exécution.
1. `python3 outils/signer-paquet.py generer-cle --dossier <…> --nom publication-essai` rend `ERREUR : nom de clé invalide : attendu « publication-AAAA »…`, code 2 (`outils/signer-paquet.py:43` : `publication-[0-9]{4}[a-z0-9-]*`). Un nom comme `publication-2026-essai` passe.
2. Même avec une clé, `signer` exige que le paquet **porte** `serveur/cles_publication.json` avec la clé publique correspondante (`outils/signer-paquet.py:277-300`). La fiche ne parle que de poser la clé « de la VM ». Pour fabriquer N+1 et N+2 sur le poste de développement, il faut donc la poser dans `serveur/` avant `faire-paquet.sh`, dans un arbre où rien ne puisse être commité : ce fichier n'est pas ignoré par Git (`git check-ignore` : rien), et c'est la racine de confiance de tout le parc (`docs/cle-publication.md` §4 exige un commit dédié, relu).
**Conséquence :** Baptiste bute dès le début de l'essai qui conditionne la livraison au prospect, et le contournement naturel (écrire la clé jetable dans le dépôt) approche de l'erreur la plus grave possible du chantier.
**Attendu :** un nom de clé valide ; la séquence complète écrite (arbre jetable copié par `git ls-files -z` hors du dépôt, `serveur/cles_publication.json` d'essai posé *là*, `faire-paquet.sh`, `signer` avec ses trois options obligatoires, `--phrase-stdin` ou phrase de 20 caractères) ; une phrase interdisant de poser la clé d'essai dans le dépôt.

### Important — Rien ne protège l'effacement de `__pycache__` (D12) : le neutraliser laisse 153 tests verts
**Où :** `serveur/maj.py:385-386` (`effacer_pycache`), appelée à `:1322` (retour) et `:1429` (bascule)
**Problème :** mutation rejouée par moi sur une copie jetable : `effacer_pycache` réduit à `return`. `tests.test_maj` : 127 verts ; `tests.test_maj_bout_en_bout` : 26 verts (237 s). La raison est structurelle : le pilote d'essai lance le serveur en `-B` (`tests/outils/pilote_essai.py:52`) donc aucun `.pyc` n'existe jamais, et `pe.instantane` ignore `__pycache__` (`tests/outils/paquet_essai.py:187`). Les deux seules mentions de `effacer_pycache` dans les tests sont une ancre d'import (garde M19) et une exclusion de comparaison.
**Conséquence :** D12 est une exigence nommée du contrat (« une restauration dans la même seconde, à taille égale, ferait réutiliser un `.pyc` de la version quittée »). C'est le piège le plus coûteux du dépôt : une garde jamais mise en échec. Une réécriture qui retire l'appel passerait la CI.
**Attendu :** un test dans le bac de bout en bout (ou en unitaire sur `basculer` et `_restaurer`) qui pose un `serveur/__pycache__/x.pyc` avant la bascule, puis affirme son absence après une montée réussie et après un retour ; et la mutation ajoutée à la liste M.

### Important — `schtasks /Run` sur une tâche déjà en marche : l'hypothèse dont dépend la sonde de santé n'est éprouvée nulle part
**Où :** `serveur/maj.py:1134-1136` (`demarrer` lève `TACHE_ABSENTE` sur tout code non nul), `:1204-1206` (`relancer()` appelée dans `attendre_sante`), `tests/test_maj_windows.py:73-116`, `docs/essais/C5-T2-windows.md:109-120` (A5)
**Problème :** `attendre_sante` rappelle `pilote.demarrer` toutes les 5 s tant que `/sante` est muette. Sur un PC lent (antivirus, premier import de Python), le nouveau serveur est encore en train de démarrer à t + 5 s : la tâche est alors **en marche** et `-MultipleInstances IgnoreNew` ignore le `/Run`. Si Windows rend un code non nul dans ce cas, `Refus("TACHE_ABSENTE")` s'échappe de la boucle d'attente : `basculer` défait une version saine (`MAJ_REFUSEE`), et dans `_restaurer` cela use les trois tentatives du retour (`echec-retour`). Le pilote d'essai, lui, écrit en dur « sans effet si une instance tourne » (`pilote_essai.py:43`) : le bout en bout ne peut pas voir la différence. Le test Windows lance `/Run` une seule fois, jamais sur une tâche en marche, et la fiche A5 demande « une relance a-t-elle été nécessaire ? » sans demander le code de sortie du `/Run` inoffensif. Je crois que Windows rend 0, sans pouvoir le prouver d'ici.
**Conséquence :** le chemin « mise à jour saine, démarrage lent » est celui des PC de cabinet ; s'il échoue, la mise à jour d'un serveur sain est annulée à chaque fois. Une erreur sur le filet de relance ne doit pas défaire ce qu'elle protège.
**Attendu :** (a) dans `test_pilote_de_tache_planifiee_sur_une_tache_jetable`, un second `pilote.demarrer()` pendant que la tâche tourne, qui ne doit pas lever ; (b) une ligne à A5 : noter le code de `schtasks /Run` sur la tâche `BilanPosturo` en marche ; (c) par prudence, que l'appel `relancer()` d'`attendre_sante` n'interrompe jamais l'attente (le verdict reste celui de la sonde), avec son test.

### Mineur — README et guides non mis à jour
**Où :** `README.md` (arborescence « Layout », liste « Files that must never be committed », ligne `page_etat` du tableau de configuration) ; `docs/Mode_emploi.md:297-318` et `docs/USER-GUIDE.md:~282-303` (« La page d'état / The status page »)
**Problème :** `serveur/maj.py` manque dans l'arborescence alors que `signature_ed25519.py` et `paquet_signe.py` y figurent ; `mise-a-jour/` est ajouté à `.gitignore` mais pas à la liste « bundled `.gitignore` excludes them » ; la clé `mise_a_jour` n'a pas de ligne dans le tableau de configuration (elle n'est que dans `docs/configuration.md` §8) ; la page d'état gagne une ligne « Mise à jour » que ni le README ni les deux guides (qui disent « Elle dit, ligne à ligne : »), français et anglais, ne citent.
**Conséquence :** un lecteur du README ne sait pas que ce dossier existe ni qu'il ne doit pas être versionné ; l'assistant qui lit la page d'état y trouve une ligne que son guide ne décrit pas (et qui peut dire `illisible` ou `echec-retour`).
**Attendu :** les quatre ajouts, français d'abord puis anglais.

### Mineur — Le retour manuel écrit en §6 laisse un `installe.json` périmé
**Où :** `docs/mise-a-jour.md:169-176`
**Problème :** la procédure dit de recopier la sauvegarde « **sauf** `inventaire.json` et `installe.json` ». Or `_restaurer` (`maj.py:1315-1321`) remet `installe.json` depuis la sauvegarde (ou l'efface si l'inventaire dit `"installe": false`) : c'est ce qui garde la liste des fichiers gérés cohérente avec le disque.
**Conséquence :** après un retour manuel, `installe.json` décrit les fichiers de la version quittée. La montée suivante compare l'empreinte de `formulaire/schema.json` sur le disque à celle de cette liste et, si le schéma a changé entre les deux versions, rend `SCHEMA_MODIFIE_LOCALEMENT` pour un fichier que personne n'a retouché.
**Attendu :** ajouter la remise de `sauvegarde\installe.json` à `mise-a-jour\installe.json`, ou son effacement si `inventaire.json` porte `"installe": false` ; `etat.json` et `reprendre` restent à `repos`.

### Mineur — Fiche d'essai : `python` sous SYSTEM
**Où :** `docs/essais/C5-T2-windows.md:89`
**Problème :** la tâche de test lance `python …` sous SYSTEM ; une installation de Python « pour moi seulement » n'est pas dans le `PATH` de SYSTEM (l'installateur du produit prend pour cela le chemin absolu de `pythonw.exe`, `installer-demarrage.ps1:57`). **Attendu :** le chemin absolu de `python.exe`.

### Mineur — L'état de C5-T2a dans la feuille de route est périmé
**Où :** `docs/ROADMAP.md:1144`
**Problème :** « implémentée le 12 novembre 2026, en attente d'audit » ; l'audit est CONFORME au réaudit. **Attendu :** à la clôture, « auditée CONFORME, revue le 12 novembre ». La tâche C5-T2 reste non cochée (T2b à faire).

### Mineur — Un commentaire de test décrit un code qui n'existe pas
**Où :** `tests/test_maj_bout_en_bout.py:288-290`
**Problème :** « le test attend que le compte le dise plutôt que de dormir un temps fixe » ; la ligne suivante est `time.sleep(0.5)`. **Conséquence :** le lecteur croit à une synchronisation sur le compteur de dépôts ; sur un exécuteur très chargé, il n'y en a pas. En pratique le test est sûr (la demande d'arrêt part des secondes plus tard), mais il faut un commentaire vrai. **Attendu :** un commentaire vrai : « 0,5 s suffit, `appliquer` met bien plus longtemps à écrire sa demande d'arrêt » (le compteur du serveur n'est lisible d'aucun autre processus, il n'y a donc rien à attendre d'autre).

### Mineur — Un test de dépôt figé a une course avec la durée de `appliquer`
**Où :** `tests/test_maj_bout_en_bout.py:807-817` (`DepotFige`, inactivité réduite à 2 s)
**Problème :** le test envoie 20 octets, se tait, puis lance `appliquer` et attend le code 3. Si `trio` + `controler` + `extraire` + `preparer_sauvegarde` (une centaine de fichiers, un `fsync` chacun, deux fois) durent plus de 2 s avant la demande d'arrêt, le dépôt figé a déjà expiré et `appliquer` réussit (code 0). Sur un exécuteur Windows aux disques lents, cela peut arriver. Aujourd'hui vert partout (7 jobs).
**Attendu :** porter l'inactivité du bac à 6 ou 8 s et le silence attendu à 9 ou 10 s ; ne jamais relancer cet échec s'il survient : le capturer.

### Mineur — Des noms privés d'un module lus depuis un autre
**Où :** `serveur/maj.py:619-623` (`serveur._CODE_MAJ`, `serveur._HORODATAGE_MAJ`), `:926` (`paquet_signe._ERREURS_ZIP`, antérieur)
**Problème :** l'erratum 18 a rendu publics `lire_json_strict` et `MOTIF_VERSION` pour exactement cette raison ; ces deux motifs sont restés à tiroir. Un renommage « de confort » dans `serveur.py` casse `maj.py` au démarrage du client, donc la mise à jour suivante.
**Attendu :** les nommer sans souligné, comme leurs voisins `ETAPES_MAJ` et `RESULTATS_MAJ`.

### Mineur — Les effets du délai de 120 s sur les journaux ne sont ni vus ni dits
**Où :** `serveur/serveur.py:2347-2349` (`Gestionnaire.timeout`) ; `tests/test_serveur.py:2340-2343`
**Problème :** le test du délai ne relit que la constante. Le comportement (un dépôt lent qui avance aboutit, un figé lâche) est bien couvert par `DepotFige`. Mais ce qu'une expiration écrit ne l'est pas : d'après `handle_one_request` de la bibliothèque, une expiration passe par `log_error("Request timed out")`, donc `log_message`, donc une ligne nominative dans `journal.log` et une ligne `REPONSE methode=… route=… code=0` dans `technique.log`, y compris pour une connexion Chrome ouverte par anticipation et jamais utilisée (jusqu'ici muette). Je ne l'ai pas observé : je n'ai pas lancé de serveur sur le dépôt.
**Conséquence :** une ligne `code=0` nouvelle dans le fichier qui circule, dont le support ne connaît pas le sens.
**Attendu :** un test qui provoque une expiration dans un bac (délai réduit comme dans `DepotFige`) et fige ce qui est écrit ; une phrase dans `docs/Mode_emploi.md` si la ligne est conservée. À joindre à la déclaration du délai (« déclaré » dans la demande de revue, mais seulement comme borne).

### Mineur — Une coupure entre l'acceptation et `bascule` laisse le serveur arrêté sans que `reprendre` le voie
**Où :** `serveur/maj.py:1372-1373` (`reprendre`), `:1499-1511`
**Problème :** l'état reste `preparee` de l'extraction jusqu'à `ecrire_etat(etape="bascule")` ; `reprendre` tient `preparee` pour « rien à faire » et ne relance pas le serveur. `assurer_serveur` couvre toute sortie *Python* (exception, `KeyboardInterrupt`) mais pas la mort brutale du processus (console Windows fermée, `taskkill`) dans cette fenêtre d'une ou deux secondes ; le serveur a quitté en code 0, la tâche ne le relance pas. Un `appliquer` suivant répond `SERVEUR_ABSENT`.
**Conséquence :** très improbable en séance d'assistance ; plus visible en C5-T2b où personne ne regarde la console (l'auditeur l'a déjà consigné pour le cas voisin). **Attendu :** à traiter avec T2b : écrire l'étape `bascule` (ou un drapeau « arrêt accepté ») dès l'acceptation, ou faire relancer par `reprendre` un serveur muet.

### Mineur — Le serveur du quotidien porte désormais la mécanique d'ACL de Windows
**Où :** `serveur/serveur.py:327-479` (`sddl_est_protege`, `sids_en_trop`, `decoder_sortie_icacls`, `lire_sddl_windows`, `proprietaire_windows`), imports `ctypes`, `subprocess`, `paquet_signe`
**Problème :** 150 lignes qui ne servent que quand une demande d'arrêt existe, dans le processus qui reçoit les bilans chaque jour. Le choix est défendu (une règle écrite une fois, erratum 16) et je n'ai trouvé aucun défaut ; je le signale pour la taille (`maj.py` fait 1 667 lignes, le contrat en estimait 700 ; `serveur.py` gagne 651 lignes) et parce qu'un serveur sans client de mise à jour hérite de trois imports de plus à l'ouverture. Sans conséquence mesurable aujourd'hui.
**Attendu :** rien à faire maintenant ; à garder en tête si le démarrage du serveur devient un sujet (C6-T8).

## Ce qui est bien fait

- **Le dépôt de bilans est intact.** La diff de `do_POST` est un enrobage : `traiter_post` reprend le corps à l'identique, `sortir_depot` est dans un `finally`, `noter_activite` ne lève jamais (elle ne lit que `self.path`, déjà analysé). Le seul changement de comportement d'un serveur sans mise à jour en cours est le délai d'inactivité de 120 s, plus un `lstat` par seconde sur un chemin absent et un fil de plus. `demarrer()` : la surveillance est lancée *dans* le `try`, le `finally` qui écrit `ARRET` couvre tout, `attendre_fin_depots` borne l'attente à 30 s.
- **Le serveur décide de son propre arrêt**, sans route ni port, et la règle de confiance du dossier réservé est écrite une fois (`dossier_reserve_de_confiance`) puis partagée. La comparaison « chemin résolu » dont la partie résolue était vide (erratum 17) a été trouvée en écrivant le test, et corrigée au bon endroit.
- **Les abandons après l'acceptation** sont chacun un test de bout en bout (`AbandonApresAcceptation` : arrêt jamais confirmé, état qui ne s'écrit pas, exception imprévue, `KeyboardInterrupt` pendant le répit), vérifiés par « `/sante` répond à la fin ». C'est exactement la sonde de l'audit, jouée en continu.
- **`poser_fichiers` est idempotent par comparaison d'empreinte** et le test d'interruption pendant le retour compte les `os.replace` de la dernière reprise (3 : exactement ce qui restait). C'est un test qui prouve la convergence, pas seulement la fin.
- **Traces sous garde qui mord** : `detail_maj` refuse un champ inconnu, `GardeDesTraces` met sa propre garde en échec sur neuf lignes forgées, et le `tearDownModule` relit les journaux de *tous* les bacs. Pas de `assert` nu, y compris dans les gardes de tests, donc sous `-O`.
- **Les errata sont lisibles et honnêtes** : le contrat dit où il se trompait (jetons préfixes, `etat` sans verrou, D14 inexact pendant la bascule) au lieu de plier le code ou la phrase.
- **`EtatSousLecture` est un modèle à imiter** : il rend une panne propre à Windows (remplacement refusé pendant qu'un autre processus lit `etat.json`) reproductible sur un Mac par un `os.replace` simulé, et nomme ce qu'il protège (une version saine défaite à tort).

## Documentation à mettre à jour

- `docs/essais/C5-T2-windows.md` : nom de clé, séquence de fabrication des paquets d'essai, chemin absolu de Python, code de `schtasks /Run` en A5 (Important 1 et 3, Mineur).
- `README.md` : arborescence (`maj.py`), liste « never be committed » (`mise-a-jour/`), ligne `mise_a_jour` du tableau de configuration, description de `/etat`.
- `docs/Mode_emploi.md` et `docs/USER-GUIDE.md` : la ligne « Mise à jour / Update » de la page d'état (le français est la source).
- `docs/mise-a-jour.md` §6 : `installe.json` du retour manuel.
- `docs/ROADMAP.md:1144` : état de C5-T2a à la clôture ; la case de C5-T2 reste vide (T2b).
- `CLAUDE.md` (par `/cloture-projet`) : `serveur.py` (~2 330 l.) est devenu plus long, `tests/` compte 892 tests Python.
