# Revue C5-T2b — Client de mise à jour : téléchargement HTTPS, politique horaire, seconde tâche planifiée

**Date :** 2026-11-17  **Verdict :** À CORRIGER (aucun bloquant ; une fiche d'essai qui ne se déroule pas jusqu'au bout, trois documents de présentation, et une hypothèse Windows à mesurer avant toute activation. Le code livré est bon et n'appelle pas de nouvel audit, sauf si la source de `depuis_demarrage` change.)
**Tests :** `python3 -m unittest discover -s tests` exécuté par moi (Python 3.14.3, macOS, clone jetable de `c626d76` sans `origin`, sortie redirigée vers un fichier) : **1108 tests en 429 s, 1 échec, 28 sautés**. L'échec est `test_integration.ServeurArret.test_arret_journalise`, l'artefact déjà consigné dans `CLAUDE.md` (processus lancé par `(… &)` d'un shell non interactif : SIGINT ignoré) ; rejoué seul au premier plan : `OK` en 0,5 s. Les classes réseau et bout en bout ne sont pas sautées (`cryptography` 49.0.0 présente). `python3 -m pyflakes serveur/ tests/` muet. Sous `python3 -O -W error::ResourceWarning` : `test_maj_reseau`, `test_maj_politique`, `test_maj`, `test_scripts_installation`, `test_confidentialite_publication`, `test_paquet_signe`, `test_serveur` : 595 tests OK. Sous Python 3.9.6 (venv du poste, sans `cryptography`) : `test_maj_politique`, `test_scripts_installation`, `test_confidentialite_publication`, `test_maj_reseau` (160 tests, 2 sautés) puis `test_maj`, `test_paquet_signe` (271 tests, 1 sauté), `-W error::ResourceWarning` : OK ; syntaxe de tous les fichiers touchés relue par `ast.parse` sous 3.9 : valide. `git diff main -- formulaire/` : vide, donc `npm test` non rejoué. `grep -nE "^\s*assert "` dans `serveur/maj.py` et `serveur/paquet_signe.py` : vide. CI : run `44089891029` sur `a7308f5`, lu sur le run : 7 jobs verts, `workflow_dispatch` sur `c5-t2b-telechargement` ; les commits suivants ne touchent que `docs/`. Neuf mutations de ma main, voir plus bas. Aucun `serveur.py`, `maj.py` ni `generer_autorite.py` lancé depuis le dépôt ; aucun fichier réel du cabinet lu ; fiche du prospect non ouverte ; les trois `BilanPosturo_video*.mp4` non touchés ; `git status` du dépôt inchangé avant et après (hors ce rapport).

## Critères d'acceptation

| Critère | Vérifié par | Résultat |
|---|---|---|
| B1 trois `GET`, ordre, quatre en-têtes lus à l'arrivée | `test_maj_reseau.DonneesEnvoyees` (8) et `test_maj_bout_en_bout.VerifierMontee`, exécutés ; N5/M9 (mutation de l'agent utilisateur) rouge | OK |
| B2 archive jamais demandée avant le jugement de l'en-tête | `test_maj_reseau.Entete` (8), `test_maj_politique.ArchiveJamaisDemandeeAvantLEntete`, `test_paquet_signe.EnteteSeul` ; mutation d'ordre rejouée par l'auditeur | OK |
| B3 TLS exigé | `test_maj_reseau.Tls` (5) : contexte par défaut contre un certificat inconnu, `CERT_REQUIRED`, `check_hostname`, TLS 1.2 ; mutation `keylog_filename` (M10) rouge | OK |
| B4 redirections | `Redirections` (12) ; mutation « 6e acceptée » (M5) rouge | OK |
| B5 tailles et délais, constantes de production | `TaillesEtDelais` (12), dont les trois cas de goutte-à-goutte et `test_les_constantes_de_production` | OK |
| B6 proxy seulement par la configuration | `Proxy` (5) : l'environnement n'est jamais lu, `CONNECT` reçu par le faux mandataire | OK |
| B7 `dans_la_plage` en table | `DansLaPlage` (5) ; plages invalides, chiffres non ASCII et `\n` final compris | OK |
| B8 éligibilité hors plage | `Eligibilite` (11, sans réseau) et `VerifierEligibilite` (5, serveur réel, `/cabinet` puis refus `activite`) ; mutation `< 900` (M2) rouge | OK |
| B9 calme et démarrage dans la demande | `Eligibilite.test_dans_la_plage_le_calme_configure`, `test_hors_plage_apres_le_demarrage_calme_zero_et_demarrage_vrai` | OK |
| B10 fréquence | `Frequence` (9) ; horloge reculée (M1) rouge | OK |
| B11 désactivé, une ligne par jour, `reprendre` même désactivé | `Desactive` (4 formes), `VerifierDesactiveEtCoupure` ; mutation « reprendre après la politique » (M4) rouge | OK |
| B12 configuration invalide, jamais le défaut | `LirePolitique`, `ConfigurationFausse` | OK |
| B13 installateur par lecture | `SecondeTache` (garde d'ordre, 11 mutations de texte qui la font rougir) ; lu aussi à la main | OK |
| B14 désinstallateur par lecture | `SecondeTache.test_le_desinstallateur_est_conforme` et sa garde (5 mutations) | OK |
| B15 gardes statiques de `maj.py` | `GardesStatiques` (12) ; la garde du réseau mord sur 14 cas | OK |
| B16 aucun accès à `bilans/` | `VerifierMontee.test_le_client_n_ouvre_jamais_le_dossier_des_bilans` (mode `000`), exécuté ici (POSIX, hors root) | OK |
| B17 R1 | `VerifierMortApresAcceptation`, `ArretEnCours` | OK |
| B18 O1 | `VerifierReponsesPerdues` | OK |
| B19 O2 | `ProtegerAvantDeVider` (3) | OK |
| B20 état et `/etat` | `ChampsDeLEtat`, `EtatDeLaMiseAJour`, `PageEtat`, `test_integration` (15 clés) | OK |
| B21 adresse hors du dépôt | `test_confidentialite_publication` (12) ; contrôle des journaux **après chaque test** des bacs (plus fort que le critère) ; motif de CI et `.gitignore` lus | OK |
| B22 sans console, dans l'heure | `SansConsole` (6) ; `budget_application` + `TEMPS_INSUFFISANT` jugé à l'exécution (M6 rouge) | OK |
| B23 Windows réel | `test_maj_windows` : **sauté ici (Mac)** ; vert en CI `windows-latest`, 3.9 et 3.13 (run `43606954657`, lu par l'implémenteur et l'auditeur) | OK en CI seulement |
| B24 fiche partie B déroulable | fiche lue ligne à ligne ; bloc de préparation exécuté en entier dans une copie jetable (cinq dossiers de paquets produits) | **Non satisfait tel quel** : B-5 et B-6 ne se déroulent pas (Important 2) ; rien n'a été joué sur Windows, comme prévu |
| B25 mises en échec, `-O`, `assert`, `formulaire/`, CI | `docs/audits/C5-T2b-mises-en-echec.md` (N1 à N42, mutation + témoin) ; mes mutations ; `grep` vide ; suites normale et `-O` ; `formulaire/` vide ; CI verte | OK |

Mes neuf mutations (clone `git clone --no-hardlinks`, `origin` retiré, restauration par `git checkout`, témoin rejoué vert) sur `test_maj_politique` et `test_maj_reseau` : horloge reculée sans effet (M1), démarrage `< 900` (M2), reprise après la politique (M4), sixième redirection acceptée (M5), `TEMPS_INSUFFISANT` jamais levé (M6), version non retenue après un refus local (M7), en-tête `User-Agent` changé (M9), `keylog_filename` laissé (M10) : **tous rouges**. M3 (décision d'entrée jugée sur l'heure figée) : **verte, mutant survivant**, comme l'a vu l'audit (Mineur 1).

## Remarques

### Important — `au_demarrage` repose sur `GetTickCount64`, que le Démarrage rapide de Windows ne remet pas à zéro
**Où :** `serveur/maj.py:1038-1049` (`depuis_demarrage_systeme`), `maj.py:1019` (`decider_moment`), `docs/configuration.md:237`, `docs/mise-a-jour.md:212`, `docs/essais/C5-T2-windows.md:378-394` (B-5).
**Problème :** `au_demarrage` existe pour le PC **éteint la nuit** (D-M2). Le client juge « moins de 900 s depuis le démarrage » avec le temps écoulé depuis le démarrage du *système*. Sous Windows 10 et 11 le Démarrage rapide (hibernation hybride) est actif par défaut, et « Arrêter » puis rallumer ne fait pas un démarrage à froid : le compteur de disponibilité du noyau, et donc `GetTickCount64`, continue de courir (seul « Redémarrer » le remet à zéro). Je n'ai pas de Windows ici et la documentation de `GetTickCount64` dit seulement « depuis le démarrage du système » : c'est le comportement connu du Démarrage rapide, **à mesurer, pas à croire**. S'il se confirme : le PC du matin rend des heures ou des jours, le filtre répond `HORS_PLAGE` à chaque démarrage, et un cabinet qui éteint son PC chaque soir et le rallume à 8 h ne se met jamais à jour, sans autre signe qu'une ligne `HORS_PLAGE` par jour. Le serveur, lui, juge sa propre durée de vie (`serveur.py:2092`, `demarre_depuis_s` depuis le démarrage du processus, qui repart bien de zéro) : les deux références divergent précisément dans ce cas. La fiche B-5 ne le verrait pas : elle dit « redémarrer la VM », ce qui contourne le Démarrage rapide.
**Attendu :** (1) ajouter à B-5 une variante « Arrêter » puis rallumer la VM avec le Démarrage rapide actif, en relevant ce que rend `depuis_demarrage_systeme()` au premier passage ; (2) si l'écart se confirme, prendre pour référence le démarrage du serveur (ce que `decider_arret` juge) plutôt que celui du système, et corriger les trois textes qui disent « le démarrage du PC ». Rien n'est cassé tant que l'adresse est vide ; à trancher avant D-M3.

### Important — La fiche B ne peut pas être jouée jusqu'au bout : B-5 et B-6 n'obtiennent jamais la version suivante
**Où :** `docs/essais/C5-T2-windows.md:378-410` (B-5, B-6), `serveur/maj.py:1024-1035` (`controle_du`), `maj.py:2330-2331`.
**Problème :** `controle_le` n'est posé que par un contrôle réseau et n'est jamais remis à zéro par une application. B-3 fait un contrôle, B-4 applique N+1 sans nouveau contrôle, puis B-5 « publie N+2 » et redémarre la VM quelques minutes plus tard : le dernier contrôle date de moins de six heures, rien n'est en attente, le passage sort sans une ligne (14.4 étape 3). N+2 n'est jamais téléchargée, la case « appliquée dans le quart d'heure » reste vide ou est cochée « échec » à tort, et B-6 (N+3 à publier pendant qu'une mise à jour tourne) ne peut pas non plus démarrer. Rien dans la fiche ni dans `docs/mise-a-jour.md` ne dit comment provoquer un contrôle. Le contrat B24 est coché alors que la fiche n'est pas déroulable.
**Attendu :** ajouter avant B-5 et B-6 un geste explicite et sûr (par exemple, en administrateur, retirer la clé `controle_le` de `mise-a-jour\etat.json` ; ou attendre six heures, à dire), le nommer dans `docs/mise-a-jour.md` §7 comme « forcer un contrôle en séance d'assistance », et rejouer B-5 et B-6 avec lui.

### Important — README, Mode d'emploi et USER-GUIDE décrivent encore un installateur à une tâche et un client sans réseau
**Où :** `README.md:18`, `:134-136`, `:160`, `:243`, `:278`, `:291` ; `docs/Mode_emploi.md:147-153` et `:326-331` ; `docs/USER-GUIDE.md:143-148` et `:309-312`.
**Problème :** aucun de ces fichiers n'est dans le diff.
- `README.md` : la table des clés ne connaît que `{"client": …}` ; `adresse`, `plage`, `calme_minutes`, `au_demarrage`, `proxy` y manquent. `adresse-publication.json`, fichier à ne jamais versionner, n'est pas dans la liste des fichiers ignorés. L'installateur est décrit comme enregistrant « la tâche `BilanPosturo` » ; la seconde tâche n'apparaît nulle part, ni son retrait par `desinstaller-demarrage.ps1`.
- Surtout, **« No data leaves the local network. No cloud, no third-party service »** (ligne 18), l'argument commercial du produit, devient inexact dès qu'une adresse est configurée : un `GET` HTTPS part vers un hébergeur tiers, sans donnée du cabinet. À dire explicitement (un appel sortant facultatif, trois `GET`, rien du cabinet), sans quoi un lecteur qui lit le code verra l'écart avec le texte.
- `Mode_emploi.md` et `USER-GUIDE.md` : la section sur le démarrage automatique ne cite que la tâche `BilanPosturo`. La ligne « Mise à jour » de la page d'état dit « aucune mise à jour enregistrée tant qu'aucune n'a été tentée » : faux dès que la seconde tâche a tourné une fois, puisque `etat.json` porte alors `reportee` / `DESACTIVEE` (vérifié). La page affiche aussi « dernier contrôle le … », non décrit.
**Attendu :** mettre à jour ces trois fichiers (français d'abord, anglais ensuite) : clés, seconde tâche et son retrait, fichier ignoré, phrase sur le flux sortant, valeurs normales de la ligne « Mise à jour » (`DESACTIVEE` n'est pas une panne), « dernier contrôle ».

### Mineur — La décision d'entrée de `verifier` n'est gardée par aucun test (mutant survivant de l'audit)
**Où :** `serveur/maj.py:2408` (`heure_courante()`), tests `tests/test_maj_politique.py:694-745`.
**Problème :** remplacer `heure_courante()` par `maintenant` à cet endroit laisse `test_maj_politique` et `test_maj_reseau` verts (M3, confirmé). La sécurité tient, car `reevaluer` rejuge juste avant la demande d'arrêt, mais un passage qui franchit la fin de la plage pendant le contrôle réseau extrairait 64 Mio et bâtirait une sauvegarde pour rien, et aucun test ne le dirait.
**Attendu :** un cas où l'heure d'entrée est dans la plage, le contrôle (faux téléchargement qui avance l'horloge monotone) la fait sortir, et l'on s'attend à `HORS_PLAGE` avec `prepare/` absent.

### Mineur — Après une activation, `/etat` garde `maj_resultat=reportee` et `maj_code=DESACTIVEE`
**Où :** `serveur/maj.py:2303-2308` (verdict `a-jour`), `maj.py:2405-2406` (sortie silencieuse).
**Problème :** reproduit : un passage désactivé, puis l'adresse écrite et un passage à jour (code de sortie 0) ; `etat.json` garde `resultat=reportee`, `code=DESACTIVEE` et porte un `controle_le` frais. Même chose après une coupure réseau résorbée : `RESEAU_INJOIGNABLE` reste affiché des jours. En séance d'activation (D-M3), le support lit « code : DESACTIVEE » à côté d'un contrôle du jour. Le `maj_controle_le` règle le doute, mais il faut le savoir.
**Attendu :** soit effacer `resultat`/`code` quand ils décrivent un report ou un refus plus ancien que le contrôle réussi, soit le dire dans `docs/mise-a-jour.md` §7 (« lire `maj_controle_le` d'abord »).

### Mineur — Un disque plein pendant la réception est rapporté comme une panne réseau
**Où :** `serveur/maj.py:1673-1688` (le `except Exception` générique de `_telecharger`), `maj.py:2325` (`octets_recus > 0`).
**Problème :** reproduit (`write` qui lève `ENOSPC` après 16 Kio) : `RESEAU_INJOIGNABLE`, `octets_recus=16384`. `technique.log`, qui circule, dit « réseau » ; le détail du `journal.log` dit `errno=28` mais seulement sur place ; et le contrôle compte pour fait, donc six heures d'attente avant le prochain essai, alors que le code `ECRITURE_IMPOSSIBLE` existe et sert déjà à l'ouverture de la destination.
**Attendu :** traduire un `OSError` levé par `write`/`flush` en `ECRITURE_IMPOSSIBLE` (sans changer ce qui est compté comme transfert).

### Mineur — `TEMPS_INSUFFISANT` n'est pas limité à une ligne par jour
**Où :** `serveur/maj.py:118-121` (`LIGNES_LIMITEES`). Déjà noté par l'audit.
**Problème :** après un contrôle réseau très lent, chaque passage horaire suivant de la plage peut rejouer le cas et écrire une ligne dans les deux journaux. Rare, mais c'est le seul report de la phase d'application hors de la limitation, avec `ARRET_REFUSE`, qui, lui, est voulu.
**Attendu :** l'ajouter à `LIGNES_LIMITEES` (une ligne, et le dictionnaire `lignes` reste borné par construction).

### Mineur — Un client désactivé sort en code 3, que le Planificateur de tâches affiche comme `0x3`
**Où :** `serveur/maj.py:2026` (`return 3 if erreur.code in CODES_REPORT`).
**Problème :** `DESACTIVEE` et `HORS_PLAGE` sont des reports. Chaque heure, « Résultat de la dernière exécution » de `BilanPosturo-MiseAJour` montre `0x3` (« chemin introuvable » pour qui ne connaît pas le code). Un support qui ouvre le Planificateur voit une panne là où il n'y en a pas. La fiche B-4 demande déjà de relever ce résultat.
**Attendu :** décider si un passage « désactivé » ou « hors plage » doit sortir en 0 ; sinon, le dire dans `docs/mise-a-jour.md` et dans la fiche (« 0x3 est normal »).

### Mineur — Un paquet en attente est retéléchargé à chaque contrôle, soit trois ou quatre fois par jour avant la nuit
**Où :** `serveur/maj.py:2275` (`vider_dossier(reception)` inconditionnel), `maj.py:2316-2331`.
**Problème :** quand `attente` porte déjà la version vue (publiée à 9 h, plage à 20 h), les contrôles de 15 h et 21 h effacent `reception/` et redemandent l'archive. Le contrat l'accepte (14.4), le coût est de quelques Mio sur un lien ordinaire ; sur une box 4G de secours à forfait, ce sont des Mio inutiles.
**Attendu :** si `attente == manifeste["version"]` et que `reception/archive.zip` est présente, ne pas la redemander. À peser avec C5-T3, sans urgence.

### Mineur — Un test dépend de la résolution DNS réelle
**Où :** `tests/test_maj_reseau.py:465-470` (`test_un_hote_qui_n_existe_pas`).
**Problème :** `hote-qui-n-existe-pas.invalid` est résolu par le résolveur de la machine. Sur un résolveur qui redirige les noms inconnus (portail captif, FAI) ou sans réseau (délai de plusieurs secondes, que `delai_total=10` ne borne pas, `getaddrinfo` ne rendant pas la main), le code attendu peut changer ou le test traîner. Le reste de la suite n'emploie que `127.0.0.1`.
**Attendu :** substituer `socket.getaddrinfo` par une `socket.gaierror`.

### Mineur — Deux lignes de commentaire cassent la largeur du dépôt ; `ROADMAP.md` dit encore « En attente : audit »
**Où :** `serveur/maj.py:587` (126 caractères) et `:2036` (153) ; `docs/ROADMAP.md`, bloc « C5-T2b implémentée le 14 novembre ».
**Problème :** deux docstrings reflowées par un ajout de phrase ; la ROADMAP annonce l'audit en attente alors qu'il est CONFORME au réaudit (la clôture la mettra à jour, mais la case de la tâche ne peut être cochée qu'après la fiche B).
**Attendu :** recouper les deux lignes ; mettre la ligne d'état de la ROADMAP à jour à la clôture.

### Mineur — Les faux serveurs de test posent `SO_REUSEADDR` sans condition
**Où :** `tests/outils/faux_hebergement.py:46` (`allow_reuse_address = True`) et `:292`.
**Problème :** le dépôt conditionne `SO_REUSEADDR` à `os.name` (piège connu, sous Windows il permet à un second processus de se lier au même port). Ici le port est éphémère (`0`), donc aucun effet constaté : la CI Windows est verte. C'est une dérogation à une règle écrite, sans commentaire qui la justifie.
**Attendu :** retirer l'option (un port `0` n'en a pas besoin) ou dire pourquoi elle est inoffensive ici.

## Ce qui est bien fait

- **Extractions pures isolées.** `55fd384` ne touche aucun fichier de `tests/` et ne déplace que du code (`verifier_entete`, `appliquer_trio`) : le diff se relit en cinq minutes, et la règle de jugement du manifeste n'est écrite qu'une fois, `verifier_paquet` l'appelle en premier (et un test le montre par substitution).
- **Horloge, démarrage système et contexte TLS injectables.** Toute la politique (plage, fréquence, éligibilité, rejugement avant l'arrêt, `TEMPS_INSUFFISANT`) se joue sans réseau, sans horloge réelle et en dixièmes de seconde ; le réseau est éprouvé séparément contre un vrai serveur TLS local. Aucun test de politique ne dort.
- **Le faux hébergement note ce qui arrive, pas ce que le client dit envoyer** (en-têtes lus côté serveur), et ses comportements couvrent les vrais modes de défaillance (goutte-à-goutte d'en-têtes, corps coupé par RST, annonce sans corps).
- **Échec fermé et vocabulaire fermé.** `lire_politique` ne remplace jamais une clé fausse par son défaut ; `Refus` refuse un code inconnu ; `detail_maj` n'accepte que des champs fermés ; la classe seule d'une exception imprévue est tracée, jamais son texte.
- **Le minuteur de `_telecharger`** : drapeau posé *avant* la coupure, toute issue après l'échéance convertie en `DELAI_DEPASSE`, jamais un corps coupé pris pour complet ; la course est éprouvée en forçant le minuteur à gagner.
- **Gardes dérivées du code, et éprouvées.** B15 est une garde AST (où le module parle au réseau, ce qu'il envoie) avec 14 mutations qui la font rougir ; la garde de l'installateur a ses 11 textes fautifs. `lire_motif_des_secrets` lit maintenant toutes les lignes du motif de CI (erratum 29), ce qui aurait laissé `adresse-publication.json` invisible.
- **Une seule règle pour les droits du dossier**, écrite dans `maj.py`, que l'installateur appelle par `proteger` : aucune ACL recopiée en PowerShell, et un test qui interdit au script de connaître `icacls` ou `plage`.
- **L'adresse de publication ne sort nulle part**, et le test des journaux tourne après *chaque* test des bacs, plus exigeant que le critère.
- **Ordre de l'installateur** : la seconde tâche est enregistrée avant la section pare-feu (dont `exit 1` ne doit pas la sauter), après le code de sortie de `proteger`, et rien ne s'exécute avant la sortie de `-Verifier` ; `maj.py` absent laisse l'installation exactement ce qu'elle était.
- **Honnêteté du contrat §15** : la durée de répétition de 7 300 jours est annoncée comme non vérifiée et renvoyée à la fiche B-1 ; l'unique exécution de `maj.py --help` depuis le dépôt est déclarée.
- **L'épinglage `ubuntu-24.04`** (erratum 39) est justifié (`ubuntu-latest` n'a plus de Python 3.9), borné à la matrice `test`, commenté avec sa condition de réouverture, et sans effet de bord : la branche n'est pas protégée (`gh api` : « Branch not protected »), aucun nom de job requis ne change. Le plancher 3.9 reste testé sous Linux.

## Documentation à mettre à jour

| Fichier | État |
|---|---|
| `docs/configuration.md` §8 | À jour : les six clés, leurs formes, l'échec fermé, l'activation. À corriger seulement si Important 1 se confirme (« le démarrage du PC »). |
| `docs/mise-a-jour.md` §7, §8 | À jour et fidèle au code. À compléter : comment forcer un contrôle (Important 2), `0x3` normal et résultat obsolète dans `/etat` (Mineurs), « démarrage du PC » si Important 1 se confirme. |
| `docs/essais/C5-T2-windows.md` partie B | À reprendre : B-5 (variante « Arrêter » à froid, geste de contrôle forcé) et B-6 (geste de contrôle forcé). Le bloc de préparation (poste de développement) s'exécute tel quel. |
| `README.md` | **À faire** : clés `mise_a_jour`, `adresse-publication.json` dans les fichiers ignorés, seconde tâche et son retrait, ligne 278 (« applies a signed package » : il le télécharge aussi), et la phrase « No data leaves the local network » (Important 3). |
| `docs/Mode_emploi.md`, `docs/USER-GUIDE.md` | **À faire** : section « démarrage automatique » (deux tâches), ligne « Mise à jour » de la page d'état (`DESACTIVEE` normal, « dernier contrôle le … »). Français d'abord, anglais ensuite. |
| `docs/ROADMAP.md` | À la clôture : retirer « En attente : audit », cocher C5-T2b seulement après la fiche B jouée sur Windows. |
| `CLAUDE.md` | Maintenu par `/cloture-projet` : rien à faire ici. |
