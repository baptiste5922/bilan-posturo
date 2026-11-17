# Audit C5-T2b — Client de mise à jour : téléchargement HTTPS, politique horaire, seconde tâche planifiée

**Date :** 2026-11-14  **Périmètre audité :** `main..c5-t2b-telechargement` (`c4e9873..3cf9e8b`, 12 commits, 24 fichiers) : `serveur/maj.py`, `serveur/paquet_signe.py`, `serveur/serveur.py`, `installer-demarrage.ps1`, `desinstaller-demarrage.ps1`, `.gitignore`, `.github/workflows/tests.yml`, `tests/outils/faux_hebergement.py`, `tests/test_confidentialite_publication.py`, `tests/test_maj*.py`, `tests/test_scripts_installation.py`, `tests/test_serveur.py`. Lus dans leur contexte : `serveur.traiter_demande_arret`, `surveiller_demande_arret`, `demander_arret`, `assurer_serveur`, `executer`, `preparer_dossier_prive`, `vider_dossier`. Contrat : `docs/contrats/C5-T2.md` §10, §14 (fait foi pour T2b) et §15 (errata 24 à 32, résultats).
**Verdict :** CONFORME SOUS RÉSERVE

Le cœur de la tâche tient. Le contexte TLS est vérifié. Seul HTTPS passe, redirections comprises. Aucun proxy n'est lu dans l'environnement. L'archive n'est demandée qu'après que l'en-tête signé a été jugé par les clés installées. R1, O1 et O2 sont corrects. L'adresse de publication ne sort ni dans les journaux ni dans `/etat`, et elle n'entre pas dans le dépôt. La réserve porte sur une propriété que le contrat tenait pour acquise, le passage horaire qui tient dans l'heure. Un hébergement compromis peut la casser à cause du trou déclaré à l'erratum 31, aggravé par une plage horaire jugée sur l'heure de début du passage.

## Constats

### Moyenne — Un passage peut ne pas tenir dans l'heure : l'arrêt est demandé hors plage, et la tâche peut être tuée au milieu de la bascule

**Où :**
- `serveur/maj.py:1550-1551` : en-têtes lus par `getresponse()`, chaque réception bornée, leur somme non bornée (erratum 31).
- `serveur/maj.py:2258` : `maintenant` est figé à l'entrée de `verifier`.
- `serveur/maj.py:2283` : `decider_moment(politique, maintenant, …)` juge la plage sur cette heure figée.
- `installer-demarrage.ps1:143` : `-ExecutionTimeLimit` d'une heure.
- `tests/test_maj.py:1226-1242` : le budget de 2 700 s ne compte la phase réseau que par ses délais totaux.

**Éprouvé :** une sonde (hors dépôt, sur une copie `git ls-files -z`) a servi la ligne de statut, puis un octet d'en-tête toutes les 0,5 s, chacun dans son propre enregistrement TLS. `_telecharger(…, delai_total=3, delai_operation=2)` a rendu `DELAI_DEPASSE` au bout de **20,3 s** au lieu de 3 s, et seulement parce que la sonde avait fini d'envoyer ses 40 octets. Avec 100 lignes de 64 Kio admises par `http.client`, rien ne borne cette phase en deçà de la limite de la tâche. Un réseau hostile sans la clé TLS ne peut pas en faire autant. La poignée de main TLS porte une échéance globale dans `_ssl`, et un intermédiaire ne peut pas découper des enregistrements qu'il ne sait pas fabriquer. L'acteur est donc **l'hébergement lui-même, ou un hôte vers lequel il redirige**. C'est précisément le cas « hébergement compromis sans la clé privée ».

**Scénario :**
1. Une version 1.2.0 légitimement signée est publiée, et le cabinet est encore en 1.1.0. Plage par défaut `20:00-07:00`.
2. À 06:59, le passage horaire démarre : `maintenant` vaut 06:59 et le contrôle est dû.
3. L'hébergement compromis égoutte les en-têtes du manifeste pendant 55 minutes, puis sert rapidement le trio légitime. `verifier_entete` l'accepte, et l'archive arrive.
4. À 07:55, `decider_moment` juge encore sur 06:59, donc « dans la plage ». La demande d'arrêt part avec `calme_secondes = 1800`. Le formulaire étant chargé une seule fois et le brouillon local, une tablette ouverte depuis la veille peut n'avoir rien demandé depuis 30 minutes : le serveur accepte.
5. L'attaquant a réglé la fin de son goutte-à-goutte pour que la bascule commence quelques secondes avant 07:59. Windows tue `python.exe` à la limite d'une heure, au milieu de `poser_fichiers`.
6. Le serveur est arrêté en code 0, ce qui ne déclenche pas `-RestartCount`, et ses fichiers sont mêlés. Rien ne le relance avant le passage suivant. Avec `IgnoreNew`, le déclenchement horaire qui tombe à l'instant de la mise à mort peut être ignoré : jusqu'à environ une heure plus tard, `reprendre` revient alors en arrière.
7. Effet : **serveur indisponible entre 08:00 et 09:00 environ, à l'heure des premières consultations**. Le formulaire ne se charge pas et les dépôts attendent dans la file. Aucun bilan n'est perdu, mais une consultation est bloquée.

Sans attaquant, la même plage figée laisse un hébergement légitime mais lent, ou une connexion ADSL lente, repousser la demande d'arrêt jusqu'à environ 17 minutes après la fin de la plage (60 + 60 + 900 s). Le calme de 30 minutes reste la seule barrière.

**Propriété à rétablir :**
- La demande d'arrêt ne part que si l'heure **courante** est dans la plage (ou le démarrage récent, déjà jugé en direct).
- Il faut aussi que le temps restant avant la limite de la tâche couvre le budget de la phase d'application.
- À défaut, la phase réseau doit avoir une échéance **totale** réelle, en-têtes compris.
- Le critère B22 doit le prouver, et non additionner des constantes que le code ne garantit pas.

**À noter :** §14.17 prévoit qu'un constat Moyen ou plus sur la partie réseau fasse passer les étapes 7 et 9 (installateur et fiche B) en C5-T2c. Ce constat touche la partie réseau. La décision revient à l'orchestrateur, mais le texte du contrat s'applique.

### Faible — Une `Location` malformée fait sortir `verifier` par une exception non capturée, sans aucune trace

**Où :**
- `serveur/maj.py:1559` : `urllib.parse.urljoin(courante, cible)` hors du `try`, ou plus exactement dans le `try` mais sans clause pour `ValueError`.
- `serveur/maj.py:1618` : seuls `OSError` et `HTTPException` sont convertis.
- `serveur/maj.py:1967-1969` : `executer` ne capture que `Refus`.

**Éprouvé :** `Location: https://[abc/x` et `Location: //[::1/x` donnent `ValueError('Invalid IPv6 URL')` hors de `_telecharger` (sonde, Python 3.14). Le fichier de destination n'est pas créé. Autres réponses malformées éprouvées, toutes en `Refus` propres : chunk illisible, `Content-Length` négatif ou doublé, statut illisible, redirection vers `http`, Location non ASCII.

**Scénario :** l'hébergement, ou un hôte de sa chaîne de redirection, renvoie un 302 dont la `Location` contient un crochet non fermé. `verifier` sort sur une trace de pile, perdue sous SYSTEM, avec le code 1. Aucune ligne n'est écrite dans `journal.log` ni dans `technique.log`, et `etat.json` n'est pas réécrit. Comme `controle_le` est inchangé, le cas se reproduit à chaque heure. Le serveur n'est pas touché, puisque cela se passe avant toute demande d'arrêt, et ni l'adresse ni le chemin n'apparaissent dans la trace. Seul signe pour le support : `maj_controle_le` qui n'avance plus.

**Propriété à rétablir :** « tout refus devient une trace ». `_telecharger`, porte d'entrée de données hostiles, ne doit lever que `Refus`, comme `paquet_signe.verifier_paquet` le garantit pour ses propres entrées.

### Faible — Un échec de l'archive est retenté chaque heure : jusqu'à 24 × 64 Mio par jour, au lieu des 4 × admis au §14.4

**Où :** `serveur/maj.py:2224-2227`. `controle_le` n'est posé qu'après réception complète de l'archive (erratum 24).

**Scénario :** un manifeste signé d'une version supérieure est servi avec une archive dont le transfert échoue après l'essentiel des octets :
- tronquée à `taille - 1` : `RESEAU_INJOIGNABLE` ;
- plus longue que la taille annoncée : `REPONSE_TROP_GRANDE` ;
- servie au goutte-à-goutte jusqu'aux 900 s : `DELAI_DEPASSE`.

Un hébergement compromis peut le provoquer, mais aussi, sans malveillance, une liaison qui coupe les longues connexions (box 4G de secours, équipement qui réinitialise vers 50 Mio). Chaque code réseau laisse le contrôle dû : à chaque heure, le passage retélécharge jusqu'à 64 Mio, soit environ 1,5 Gio par jour, avec au plus une ligne par jour. Pour un 404 sur l'archive (publication dans le désordre), la répétition horaire ne coûte presque rien, et c'est le cas que l'erratum visait. Rien ne touche le serveur ni les bilans : seuls la bande passante et la facture d'un forfait limité sont en jeu.

**Propriété à rétablir :** le coût réseau d'un paquet qui ne se télécharge pas doit rester borné comme le §14.4 l'a accepté. Il faut distinguer un échec sans octets (réessai horaire légitime) d'un échec après un transfert substantiel, ou limiter les tentatives d'archive par version et par jour.

## Rubriques sans constat

**1. Données de santé — conforme.**
- Le client ne lit ni `bilans/` ni `dossier_pdf` (B16, bac en mode `000`).
- Le flux sortant compte trois `GET`, sans corps, avec les en-têtes `User-Agent: bilan-posturo`, `Accept-Encoding: identity`, `Connection: close` et `Host` (`maj.py:1486-1487`, B1).
- `technique.log` ne reçoit que `detail_maj`, à champs fermés (`maj.py:269-278`).
- `journal.log` reçoit l'hôte seul : tous les `Refus` de `_telecharger` et de `analyser_adresse` sont composés sur `hote` ou sur des messages fixes, et `_cause_sans_adresse` (`maj.py:1500`) n'emploie jamais `str(erreur)`.
- Aucune écriture dans `formulaire/` : `git diff main -- formulaire/` est vide.

**2. Surface exposée — conforme.**
- Aucune route nouvelle. `/etat` gagne `maj_controle_le`, horodatage validé par `MOTIF_HORODATAGE_MAJ`, `illisible` partout sinon (`serveur.py:1690-1692`).
- `/sante` est inchangée. Les deux barrières de la racine web ne sont pas touchées.
- Les chemins de `reception/` sont des noms fixes dans le dossier réservé ; aucun chemin venu du réseau n'est écrit.
- Les redirections vers `http:`, `file:`, `user@`, un antislash ou des caractères non ASCII sont refusées (B4, sonde).

**3. Authentification et cryptographie — conforme.**
- `contexte_tls_par_defaut` : `CERT_REQUIRED`, `check_hostname`, TLS 1.2 au minimum, sans aucun repli (`maj.py:1494-1495`, N1).
- Proxy : `set_tunnel` vers la cible, dont le nom est vérifié par TLS.
- Aucun `os.environ`, `getenv`, `getproxies` ni `urllib.request` (B15, N4).
- La confiance repose sur les clés **installées** (`lire_cles_installees`, `maj.py:2179`), jamais sur celles du paquet. Aucun `Authorization`, aucun jeton.
- Clés séparées : rien ne mêle autorité, publication et licence.

**4. Écriture de fichiers — conforme.**
- Destination créée en `O_EXCL` en `0o600`, après un statut 200 et une taille admise. Elle est effacée sur toute erreur, et un fichier préexistant n'est jamais effacé (`maj.py:1571-1603`).
- Le plafond est appliqué **avant** d'écrire : `Content-Length` jugé d'abord, `recu > limite` testé avant `write`.
- `reception/` vit dans le même dossier réservé que la copie privée de T2a.

**5. Robustesse de service — conforme hors les constats.**
- R1 : le drapeau `arret_en_cours` est posé **avant** l'écriture de `arret.demande` (`maj.py:1663-1668`). Il retombe sur un `refuse` lu, dans la même écriture que `etape="bascule"`, au retour, ou après une santé vraie. `reprendre` le lit avant même la politique, client désactivé compris (`maj.py:1836`).
- O1 : le filet joue sur `accepte` **ou** le drapeau (`maj.py:2004`). Un état illisible compte pour « peut-être accepté » (`maj.py:1712-1719`), choix sûr.
- O2 : protéger, puis vider, puis relire. Un vidage impossible donne `DOSSIER_NON_PROTEGE`, en échec fermé.
- `lire_politique` échoue fermé : une clé hors forme n'est jamais remplacée par son défaut.
- État borné : `lignes` est un dictionnaire fermé.
- Lignes quotidiennes limitées aux cas du §14.11.

**6. Côté navigateur — sans objet** : aucun fichier de `formulaire/` modifié.

**7. Chaîne d'approvisionnement — conforme.**
- `verifier_entete` (signature, puis version, minimale, client, chemins) juge le manifeste avant la demande d'archive. Les versions écartées sont filtrées avant elle aussi (`maj.py:2198-2226`, B2, N8).
- L'archive reçue repasse par le `controler` complet de T2a.
- Le retour vers une version antérieure est refusé (`VERSION_NON_SUPERIEURE`).
- L'extraction pure (`55fd384`) ne change aucune règle, d'après la lecture du diff : étapes 1 à 4 déplacées telles quelles.
- Exclusions T2a (`config.json`, certificats, `bilans/`, schémas) non touchées.

**8. Conformité — conforme.**
- Aucun stockage chez l'éditeur ; l'hébergement ne reçoit que trois `GET` sans donnée du cabinet. L'exemption HDS n'est pas rouverte.
- Aucune aide à la décision.
- L'hébergeur choisi en C5-T3 verra l'adresse IP publique du cabinet et l'heure des contrôles. Le nommer comme sous-traitant en C0-T2, avec la phrase du §10.
- Conservation : purge de six mois inchangée.

**Installateur et désinstallateur — conformes.**
- `Start-Process … proteger -Wait -PassThru` est placé après la sortie de `-Verifier`, et son code de sortie commande l'enregistrement (`installer-demarrage.ps1:117-123`).
- Répétition sur 7 300 jours, aucun `-RestartCount` sur la seconde tâche, `IgnoreNew`, une heure au plus.
- Le désinstallateur retire la tâche de mise à jour d'abord et refuse `Running` (`desinstaller-demarrage.ps1:26-35`).

**Garde de l'adresse — conforme.**
- `.gitignore`, motif de la CI et `test_confidentialite_publication.py` sont en place. Le test ne rend que des rangs, des numéros de ligne et des SHA abrégés, jamais le texte.
- Copie sans le commit de repère : la plage est sautée proprement, les fichiers suivis sont contrôlés.

**`ctypes` — conforme** : un seul appel, `GetTickCount64`, sans argument (`maj.py:1032-1035`).

**Lancement de `maj.py --help` depuis le dépôt — rien lu ni écrit.**
- `parse_args` (`maj.py:2332`) précède `realpath(RACINE)` et tout geste.
- Les imports n'ont aucun effet d'E/S : constantes seulement.
- Aucun `.pyc` de `maj`, `paquet_signe` ni `signature_ed25519` dans `serveur/__pycache__`, et `serveur.cpython-314.pyc` date du 7 novembre.
- Aucun `mise-a-jour/` à la racine.

**Filtre `ResourceWarning`** (`tests/test_maj_reseau.py:454-457`) : il est confiné à un seul test, celui du `CONNECT` refusé. Il ne porte que sur `ResourceWarning`, dans `catch_warnings`. Le chemin du client y ferme bien `connexion` dans son `finally`, et le filtre ne masque rien d'autre.

**Mises en échec de l'auditeur.** Copie `git ls-files -z`, `git init` sans `origin`, chaque mutation jouée en `python3` puis en `python3 -O`. Le fichier est restauré par `cp`, l'empreinte vérifiée, et un témoin rejoué vert dans les deux modes.

| # | Mutation | Tests | python3 | -O | Témoin |
|---|---|---|---|---|---|
| A2 | `_telecharger` : contrôle `recu > limite` neutralisé | `test_maj_reseau.TaillesEtDelais` | rouge (`test_un_corps_sans_longueur_au_dela_de_la_limite`) | rouge | vert ×2 (12 tests) |
| A3 | `_telecharger` : fichier partiel non effacé sur erreur | idem | rouge (`test_aucun_fichier_partiel_apres_un_depassement_du_delai`) | rouge | vert ×2 |
| B | `_controler_en_ligne` : version écartée non filtrée avant l'archive | `test_maj_reseau.Entete` | rouge (`test_version_ecartee`) | rouge | vert ×2 (8 tests) |
| C | désinstallateur : refus `Running` neutralisé | `test_scripts_installation` | rouge (`test_la_garde_du_desinstallateur_mord`) | rouge | vert ×2 (21 tests) |
| D | `lire_politique` : adresse « fausse » (`None`) prise pour désactivée | `test_maj_politique` | rouge (`LirePolitique`, `{'adresse': None}`) | rouge | vert ×2 (58 tests) |
| E | état illisible compté « non accepté » | `test_maj.ArretEnCours`, `VerifierReponsesPerdues` | rouge | rouge | vert ×2 (12 tests) |
| F | drapeau `arret_en_cours` écrit **après** la demande | `test_maj.ArretEnCours` | rouge (`test_la_demande_pose_le_drapeau_avant_d_ecrire_le_fichier`) | rouge | (témoin de E) |

## Points à surveiller plus tard

- **C6-T8 avant toute activation.** `assurer_serveur` n'attend la fermeture du port que 10 s. Un `shutdown()` ralenti par une connexion figée peut laisser `/sante` répondre une dernière fois. Le drapeau retombe alors à tort, et le serveur qui finit de quitter n'est plus relancé par R1. Le sens de la recommandation du §14.16 est confirmé.
- **`MAJ_REFUSEE code=CLES_ABSENTES`, `CLIENT_NON_CONFIGURE`, version installée illisible** : 24 lignes par jour si une adresse est posée sur une installation incomplète, comme aujourd'hui, avant la génération de la vraie clé. Les lignes ne sont pas identifiantes et la purge à six mois les borne. À ranger dans `LIGNES_LIMITEES` à l'occasion.
- **Redirection vers le réseau local.** L'hébergement peut rediriger vers `https://192.168.x.y/` ou vers le port du serveur lui-même : un `GET` sans identifiant, dont rien ne revient à l'attaquant. Au pire une requête « d'activité » qui retarde la mise à jour. À peser en C5-T3 : refuser les redirections hors de l'hôte configuré ?
- **`ssl.create_default_context`** honore `SSL_CERT_FILE`, `SSL_CERT_DIR` et `SSLKEYLOGFILE` dans l'environnement du système. Il faut des droits administrateur pour les poser, donc il n'y a pas de chemin d'exploitation. « Jamais l'environnement » ne vaut cependant que pour le proxy.
- **Désinstallation hors `Running`** : un état `bascule` laissé par un passage tué n'est plus repris une fois la tâche retirée. Le message `reprendre` ne s'affiche que dans le cas du refus. Lire `maj.py etat` serait plus sûr (fiche B-6).
- **Motif de la garde d'adresse** : une URL échappée en JSON (`https:\/\/…`) ou un segment suivi d'un accent grave lui échappent. La forme réelle (`/<hex>/<canal>.zip`) est bien couverte.
- `analyser_adresse` rend `port or 443` : un `:0` explicite vise 443. Sans effet de sécurité.

## Réaudit — 2026-11-17

**Plage réauditée :** `3cf9e8b..bc24177` (`96e0b24`, `c63f035`, `dd697ef`, `d10ba25`, `d22acdc`, `a7308f5`, `bc24177`). Errata 33 à 39 (§15 du contrat), mises en échec N29 à N42.
**CI :** run `44089891029` sur `a7308f5`, lu sur le run : sept jobs verts, dont `lint`. Son pas « Check that no secret is committed » a bien tourné, en succès. `bc24177` ne touche que le contrat.
**Verdict du réaudit :** CONFORME

Les trois constats sont fermés, et aucun constat nouveau n'est ouvert.

### Moyen — passage hors de l'heure : fermé

**(a) Échéance totale, en-têtes compris.** Un `threading.Timer` est armé après la requête, sur l'échéance globale. Il pose d'abord le drapeau `echu`, puis coupe la socket (`serveur/maj.py:1545`).

Toute issue postérieure au déclenchement est convertie en `DELAI_DEPASSE` :
- `Refus` et `Exception` (`maj.py:1678-1686`) ;
- fin de corps sans longueur (`maj.py:1669`, N30).

Le minuteur est annulé dans le `finally` de chaque tour, redirections comprises (`maj.py:1691`).

Le drapeau est posé **avant** la coupure. Une lecture réveillée par la coupure voit donc toujours le drapeau. Un déclenchement entre le dernier test du drapeau et le `return` ne survient qu'après une lecture terminée sur une vraie fin de flux. La poignée de main et la connexion restent bornées par le délai de la socket, ramené à ce qui reste.

**Rejoué :**
- Goutte-à-goutte d'en-têtes, un octet par enregistrement TLS toutes les 0,5 s, `delai_total=3` : **`DELAI_DEPASSE` en 3,00 s**. L'audit avait mesuré 20,3 s. Avec `delai_total=1,5` : 1,51 s.
- Corps sans longueur au goutte-à-goutte : `DELAI_DEPASSE` en 3,00 s, `octets_recus=10`, destination absente.
- Course minuteur contre lecture, 150 téléchargements dont l'échéance tombe autour de la fin d'un corps sans longueur de 20 octets : 22 succès, tous complets, et 128 `DELAI_DEPASSE` sans fichier restant. **Aucun succès tronqué.** Aucun minuteur vivant à la fin.

**(b) Plage rejugée sur l'heure courante.** L'heure courante vaut l'heure d'entrée plus le temps monotone écoulé (`maj.py:2415`). La plage est jugée deux fois :
- à l'entrée de l'application (`maj.py:2408`) ;
- par `reevaluer`, juste avant `demander_arret` (`maj.py:2079`, `2418-2433`), après extraction, sauvegarde et contrôle de présence. La politique y est relue, et le démarrage est jugé en direct.

Un `Refus` levé là précède la demande d'arrêt : le filet d'O1 ne relance rien, puisque le drapeau n'est pas posé.

**(c) `TEMPS_INSUFFISANT`.** La demande d'arrêt est refusée si le temps écoulé plus `budget_application` (496 s en production) dépasse 3 600 − 300 s. Il reste donc au moins 796 s au moment de la demande. Ce qui suit l'arrêt sans figurer au budget se compte en secondes : adoption de la sauvegarde, pose des fichiers. La marge le couvre, avec le démarrage de Python. Le code est un report : la version attend le passage suivant.

### Faible — `Location` malformée : fermé

`urljoin` est converti en `REDIRECTION_REFUSEE`, et `_telecharger` ne laisse plus sortir que des `Refus`. Rejoué : `https://[abc/x` et `//[::1/x` donnent `REDIRECTION_REFUSEE`, détail « redirection illisible reçue de 127.0.0.1 », sans chemin.

En dernier filet, `executer(…, filet=True)` est réservé à `verifier` (`maj.py:2045-2050`, `2435`). Il écrit `MAJ_REFUSEE code=CODE_INCONNU` avec la seule classe de l'exception. Les commandes manuelles gardent la propagation.

### Faible — archive retentée chaque heure : fermé

`Refus.octets_recus` porte les octets de corps reçus. Après un transfert, le contrôle compte pour fait et la réception est vidée : six heures d'attente (`maj.py:2325`). Sans octet, il est retenté dans l'heure. Un hôte qui égoutte les en-têtes de l'archive coûte désormais au plus 900 s et quelques Mio d'en-têtes par heure, sans charge notable.

### Points courts

- `MAJ_REFUSEE:CLES_ABSENTES` limitée à une ligne par jour (`maj.py:121`).
- `keylog_filename = None` (`maj.py:1513`).
- `SSL_CERT_FILE` est laissé tel quel (erratum 38). Il faut des droits administrateur pour le poser : accepté.

**CI : épinglage `ubuntu-24.04`.** Il ne concerne que la matrice `test`. `lint`, qui porte le contrôle des secrets, reste sur `ubuntu-latest` avec Python 3.13. Aucune condition ne dépend du nom de l'exécuteur. Il n'y a pas de recul de couverture : Linux reste joué en 3.9 et 3.13.

### Mises en échec de l'auditeur (réaudit)

Méthode : copie `git ls-files -z` de `bc24177`, `git init` sans `origin`. Chaque mutation est jouée en `python3` puis `-O`, le fichier restauré par `cp` puis vérifié par empreinte (`82450c5a…`), et le témoin rejoué dans les deux modes.

| # | Mutation | Tests | python3 | -O | Témoin |
|---|---|---|---|---|---|
| R1 | filet de `verifier` : détail porté par le **texte** de l'exception, et non par sa classe | `test_maj_politique`, `test_maj_reseau` | rouge (`FiletDeLaTache.test_une_exception_imprevue_laisse_une_ligne_a_code_ferme_dans_les_deux_journaux`) | rouge | vert ×2 (127 tests) |
| R2 | minuteur : drapeau `echu` posé **après** la coupure (course) | `test_maj_reseau` | rouge (`test_un_corps_sans_longueur_coupe_par_l_echeance_n_est_pas_un_succes`) | rouge | vert ×2 (57 tests) |
| R3 | décision d'**entrée** (`maj.py:2408`) jugée sur l'heure figée | `test_maj_politique` | **vert** (mutant survivant) | vert | vert ×2 (70 tests) |

R3 survit, sans effet de sécurité. La propriété « aucune demande d'arrêt hors plage » est portée par `reevaluer`, que N31 et N32 éprouvent. La décision d'entrée ne fait qu'éviter une extraction inutile. Elle n'a pas de test qui la distingue : à couvrir à l'occasion.

Suites jouées dans la copie : `test_maj_reseau`, `test_maj_politique`, `test_maj`, `test_paquet_signe`, `test_confidentialite_publication` et `test_scripts_installation`, sous `-W error::ResourceWarning`, toutes OK. La suite complète n'a pas été relancée par l'auditeur ; la CI l'a jouée.

### Points à surveiller (ajouts)

- La décision d'entrée sur l'heure courante n'est pas gardée par un test (R3).
- `TEMPS_INSUFFISANT` n'est pas dans `LIGNES_LIMITEES`. Il ne survient qu'après un contrôle réseau anormalement long, donc il reste rare.
- Les points de l'audit initial restent valables : C6-T8 avant toute activation, redirection vers le réseau local, désinstallation hors `Running`, angles morts du motif d'adresse.
