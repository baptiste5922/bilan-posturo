# Mettre à jour le serveur d'un cabinet

**Contrat :** `docs/contrats/C5-T2.md` (parties C5-T2a et C5-T2b ; le §14 fait foi pour la seconde)
**Client :** `serveur/maj.py` — bibliothèque standard seule
**Public :** la personne qui assiste un cabinet (séance d'assistance ou visite),
jamais la praticienne.

Le client installe un **paquet signé**. Deux façons de le lui donner :

- **à la main** (C5-T2a, §1 à §6) : un paquet posé sur le PC, appliqué par
  `python serveur\maj.py appliquer`, en séance d'assistance, sans déplacement ;
- **tout seul** (C5-T2b, §7 et §8) : une seconde tâche planifiée, chaque heure, va
  chercher le paquet à l'adresse configurée, le vérifie, et l'applique dans la
  plage de nuit. **Inactive tant qu'aucune adresse n'est écrite dans
  `config.json`.**

Ce client est le code le plus sensible du produit : il remplace, sous le compte
SYSTEM, le code qui reçoit les bilans. Il ne fait confiance qu'aux clés de
signature **déjà installées** sur le PC, jamais à celles du paquet.

## 1. Amorçage (à la visite, une fois)

Le client ne sait rien appliquer tant que trois choses ne sont pas en place.
D-M3 du contrat recommande de les poser **à la visite de C1-T4b**, puis de ne
rien appliquer avant la fin de la semaine de bilans réels : deux nouveautés le
même matin, c'est deux causes possibles pour une seule panne.

1. **La clé publique de publication**, dans `serveur\cles_publication.json`
   (format et geste : `docs/cle-publication.md`). Sans ce fichier, tout est refusé
   (`CLES_ABSENTES`). C'est la partie *publique* de la clé : elle ne permet que de
   vérifier.
2. **Le client du cabinet**, dans `config.json` :
   `"mise_a_jour": { "client": "cabinet-01" }` (`docs/configuration.md`, §8).
3. **La tâche planifiée du serveur** (`BilanPosturo`), installée par
   `installer-demarrage.ps1` : c'est elle que le client arrête et relance. Sans
   elle, `appliquer` refuse (`TACHE_ABSENTE`) et ne touche à rien.

Le serveur n'obéit à une demande d'arrêt que si ce dossier est réservé (droits
relus, propriétaire Administrateurs ou SYSTEM). Un dossier qui existait déjà sans
l'être est **vidé** avant d'être protégé : son contenu n'est pas cru.

Le dossier `mise-a-jour\` (à côté de `config.json`) est créé et protégé par le
client lui-même au premier appel : seuls SYSTEM et les administrateurs y ont des
droits. Leur propriétaire devient le groupe Administrateurs, et toute autre
entrée de droits est retirée puis **relue** ; si un lien ou une jonction occupe le
nom, ou si les droits relus ne sont pas exactement ceux-là, c'est un refus
(`DOSSIER_NON_PROTEGE`, dont le détail dans `journal.log` cite le début de ce qui
a été lu).

## 2. Appliquer un paquet

En console **administrateur**, depuis le dossier d'installation :

```powershell
cd C:\BilanPosturo
python serveur\maj.py appliquer C:\chemin\BilanPosturo-AAAA-MM-JJ.zip
```

Les deux fichiers qui accompagnent l'archive (`….zip.manifeste.json` et
`….zip.manifeste.sig`) doivent être **à côté** : c'est le trio que l'éditeur signe
(`docs/cle-publication.md`). Option : `--calme-minutes N` (défaut 2) — le nombre
de minutes sans requête que le serveur doit constater avant d'accepter de
s'arrêter.

Ce que fait la commande, dans l'ordre :

1. **Contrôles**, sans rien écrire hors de `mise-a-jour\` : copie privée du trio,
   signature, version, client, liste des destinations, longueur des chemins,
   schéma non retouché, espace disque. Tout échoue ici avant d'avoir touché un
   fichier du cabinet.
2. **Extraction** dans `mise-a-jour\prepare\`, tout ou rien, chaque fichier relu
   et comparé à l'empreinte signée.
3. **Sauvegarde** de tout ce qui va être remplacé : bâtie et relue dans
   `mise-a-jour\sauvegarde-neuve\`, mais elle ne remplace la sauvegarde courante
   (`mise-a-jour\sauvegarde\`) qu'**une fois l'arrêt accepté** : un refus ou un
   report laisse intacte celle qui permet de revenir de la version installée.
4. **Arrêt concerté** : le client *demande* au serveur de s'arrêter, et c'est le
   serveur qui décide. Il refuse pendant un dépôt, et tant qu'une requête (hors
   sonde de santé) date de moins de `--calme-minutes`. Refus : code de sortie 3,
   rien n'a changé, on recommence plus tard. Un dépôt qui ne progresse plus depuis
   deux minutes (tablette éteinte en pleine émission) ne compte plus comme « en
   cours » ; un dépôt lent mais qui avance, si. **Dès que le serveur a accepté**,
   il quitte (code 0) et la tâche ne le relance pas : quoi qu'il arrive ensuite, le
   client le relance et vérifie `/sante` avant de rendre la main.
5. **Bascule** : les fichiers sont remplacés un par un, jamais le dossier entier.
6. **Contrôle** : la tâche relance le serveur, `/sante` doit répondre dans la
   minute, puis le nouveau client se contrôle lui-même.
7. **Retour arrière automatique** si l'une des deux étapes échoue : les fichiers
   d'avant sont remis, le serveur relancé, et la version est **écartée** (elle ne
   sera plus jamais appliquée ; une version supérieure, si).

Rien de ce que le cabinet possède n'est touché : `config.json`, clés et
certificats, bilans, journaux, logo (`formulaire\images\cabinet\`). Un paquet qui
les nommerait est refusé même signé (`CHEMIN_PROTEGE`).

Codes de sortie : `0` appliquée ; `1` refus ou échec ; `2` usage, ou dossier de
développement (`.git`) ; `3` reportée (à retenter : serveur occupé, tâche absente,
mise à jour déjà en cours).

## 3. Lire où l'on en est

```powershell
python serveur\maj.py etat
```

Imprime l'étape (`repos`, `preparee`, `bascule`, `verification`, `retour`,
`echec-retour`), le dernier résultat (`appliquee`, `revenue`, `refusee`,
`reportee`), le code, la version installée et les versions écartées. Lecture
seule.

La page `/etat` du serveur (authentifiée, comme tout le reste) montre la même
chose sur la ligne « Mise à jour », ainsi que les dernières lignes de
`technique.log`. Cette page circule en capture : elle ne montre ni adresse ni
chemin.

**Où lire un échec :**

| Où | Quoi |
|---|---|
| `technique.log` (peut circuler) | `MAJ_APPLIQUEE`, `MAJ_REFUSEE`, `MAJ_REPORTEE`, `MAJ_RETOUR` avec des **codes seulement** (`code=`, `cause=`, `resultat=ok\|echec`, `de=`, `vers=`) |
| `journal.log` (reste au cabinet) | la même ligne, plus le détail libre (`detail='…'`), qui peut nommer un chemin |
| console | le code et le détail |

Codes de refus (`code=`) : `DEJA_EN_COURS`, `DOSSIER_NON_PROTEGE`,
`CLIENT_NON_CONFIGURE`, `CLES_ABSENTES`, `VERSION_ECARTEE`, `PAQUET_INCOMPLET`,
`CHEMIN_PROTEGE`, `DESTINATION_INVALIDE`, `CHEMIN_TROP_LONG`,
`SCHEMA_MODIFIE_LOCALEMENT`, `ESPACE_INSUFFISANT`, `ECRITURE_IMPOSSIBLE`,
`EXTRACTION_ALTEREE`, `SAUVEGARDE_ALTEREE`, `TACHE_ABSENTE`, `SERVEUR_ABSENT`,
`ARRET_REFUSE`, `ARRET_SANS_REPONSE`, `SANTE_MUETTE`, `AUTO_CONTROLE_ECHOUE`,
`INTERROMPUE`, `RETOUR_MANUEL`, `RETOUR_IMPOSSIBLE`, `ETAT_ILLISIBLE`,
`CODE_INCONNU`, auxquels s'ajoutent les codes du vérificateur
(`SIGNATURE_INVALIDE`, `VERSION_NON_SUPERIEURE`, `CLIENT_DIFFERENT`,
`ARCHIVE_DIFFERENTE`, …, définis dans `serveur\paquet_signe.py`).

`SCHEMA_MODIFIE_LOCALEMENT` : `formulaire\schema.json` a été retouché sur place
depuis la dernière mise à jour. Le schéma qui fait foi est celui de l'atelier
(`clients/<client>/schema.json`) : le reprendre à l'atelier, republier, puis
appliquer. Le client ne l'écrase jamais.

## 4. Coupure de courant, mise à jour interrompue

L'état est écrit sur le disque avant chaque étape. Si le PC s'éteint pendant la
bascule :

```powershell
python serveur\maj.py reprendre
```

défait ce qui a été commencé (cause `INTERROMPUE`) et relance le serveur. Le même
travail est fait au début de **chaque** `appliquer` et `revenir` : un cabinet qui
ne ferait rien se retrouve donc avec son ancienne version à la prochaine
tentative. Une coupure n'est pas un défaut du paquet : la version n'est pas
écartée.

`MAJ_RETOUR … resultat=echec` et l'étape `echec-retour` sur `/etat` : le retour
n'a pas abouti (sauvegarde abîmée, disque plein…). Le serveur est relancé quand
même. **Tant que l'étape n'est pas revenue à `repos`, `appliquer` refuse.**
Relancer `python serveur\maj.py reprendre` ; sinon, retour manuel (§6).

## 5. Défaire la dernière mise à jour

Si une version appliquée pose problème au formulaire (la santé du serveur ne le
voit pas) :

```powershell
python serveur\maj.py revenir
```

Environ deux minutes. La version quittée est écartée. Elle ne marche que si la
sauvegarde correspond à la version installée ; sinon `RETOUR_IMPOSSIBLE`. Pour
la tablette, le favori « Formulaire — secours V1 » reste le premier recours.

## 6. Retour manuel, si tout le reste a échoué

Arrêter la tâche `BilanPosturo`, puis recopier à la main le contenu de
`mise-a-jour\sauvegarde\` sur la racine d'installation (mêmes sous-dossiers :
`serveur\`, `formulaire\`, `docs\`), **sauf** `inventaire.json` et `installe.json`,
qui ne se recopient pas sur la racine mais se traitent à part :

- les fichiers listés dans `absents` de `inventaire.json` sont ceux que la mise à
  jour avait *ajoutés* : les supprimer ;
- `installe.json` (la liste des fichiers que la dernière mise à jour a posés) doit
  redire ce qui est maintenant sur le disque. Si `inventaire.json` porte
  `"installe": true`, recopier `mise-a-jour\sauvegarde\installe.json` sur
  `mise-a-jour\installe.json`. S'il porte `"installe": false` (il n'y en avait pas
  avant cette mise à jour), **effacer** `mise-a-jour\installe.json`. Oublier ce
  geste ferait juger, à la montée suivante, `SCHEMA_MODIFIE_LOCALEMENT` sur un
  schéma que personne n'a retouché, et effacer les fichiers d'une liste périmée ;
- laisser `etat.json` à `repos` (ou lancer `python serveur\maj.py reprendre`, qui
  n'a alors rien à faire).

Effacer ensuite `serveur\__pycache__`, redémarrer la tâche, et vérifier `/sante`
puis `/etat`.

## 7. La mise à jour automatique (C5-T2b)

La tâche planifiée **`BilanPosturo-MiseAJour`** (SYSTEM, installée par
`installer-demarrage.ps1` à côté de celle du serveur) lance `python serveur\maj.py
verifier` **au démarrage du PC (après trois minutes) puis toutes les heures**, une
heure d'exécution au plus. Chaque passage :

1. **défait ce qu'une coupure a laissé**, toujours, même désactivé (`reprendre`) ;
2. lit la configuration (`docs/configuration.md`, §8) : sans adresse, il s'arrête là
   (`MAJ_REPORTEE code=DESACTIVEE`, **aucune connexion**) ;
3. si le dernier contrôle date de six heures ou plus : demande le **manifeste** puis
   la **signature**, et les juge avec les clés **déjà installées** (signature,
   version, client, version minimale). **L'archive n'est demandée qu'après**, et
   seulement si la version est supérieure et pas écartée. Trois `GET`, aucun corps,
   quatre en-têtes, rien du cabinet : ni version, ni nom, ni donnée de santé ;
4. si une version attend et que l'heure s'y prête, l'applique par le chemin de
   `appliquer` (§2) : **dans la plage** (`20:00-07:00` par défaut) si le serveur est
   calme depuis `calme_minutes` ; **hors plage** seulement dans le quart d'heure qui
   suit le démarrage du PC, et si le serveur n'a reçu aucune requête (`au_demarrage`).
   Le serveur reste juge : il refuse pendant un dépôt, quoi qu'on lui demande.

Rien d'extrait, de sauvegardé ni demandé au serveur avant que l'heure s'y prête :
hors plage, le passage s'arrête à `MAJ_REPORTEE code=HORS_PLAGE`, version reçue
gardée dans `mise-a-jour\reception\`.

**Activer** (séance d'assistance, **après** la semaine de bilans réels qui suit la
visite : D-M3) : écrire l'adresse dans `config.json`, rien d'autre. Pas de
redémarrage du serveur ; effet au passage suivant, une heure au plus.

```json
"mise_a_jour": { "client": "cabinet-01", "adresse": "<adresse>" }
```

**Désactiver** : retirer la clé `adresse` ou la mettre à `""` ; ou, sans toucher à la
configuration, `schtasks /Change /TN BilanPosturo-MiseAJour /Disable`.

**Ne pas activer** sur un serveur qui ne porte pas encore C6-T8 (une connexion TCP
muette peut figer l'acceptation du serveur ; contrat C5-T2, §14.16).

**Lire où l'on en est.** `/etat` (page authentifiée, qui circule en capture) porte
`maj_controle_le` : la date du dernier contrôle réseau qui a rendu un verdict. C'est
le seul signe qui distingue « la tâche tourne et rien n'est publié » de « la tâche ne
tourne plus ». Elle ne bouge pas quand le réseau est tombé : le passage suivant (une
heure) réessaie, sans attendre six heures. `python serveur\maj.py etat` montre
l'étape et le dernier résultat.

`technique.log` ne reçoit que des codes. **Une ligne par jour au plus** pour
`DESACTIVEE`, `HORS_PLAGE`, un code réseau, `ADRESSE_INVALIDE`, `PLAGE_INVALIDE` et
`MAJ_CONTROLE resultat=a-jour` ; `MAJ_CONTROLE resultat=disponible` une fois par
version vue. **L'adresse n'est dans aucun journal** : `journal.log` peut nommer
l'hôte, jamais le chemin.

Codes ajoutés par C5-T2b : `DESACTIVEE`, `ADRESSE_INVALIDE`, `PLAGE_INVALIDE`,
`HORS_PLAGE` ; réseau : `RESEAU_INJOIGNABLE` (pas de réponse, port fermé, proxy
refusé), `TLS_INVALIDE` (certificat non reconnu : voir la racine de l'hébergeur dans
le magasin de Windows), `HTTP_STATUT` (404 : rien n'est publié à cette adresse),
`REPONSE_TROP_GRANDE` (plus de 64 Mio), `DELAI_DEPASSE` (une minute pour le
manifeste, un quart d'heure pour l'archive), `REDIRECTION_REFUSEE` (cinq au plus,
`https` seulement, sans identifiant).

**`python serveur\maj.py proteger`** crée et protège `mise-a-jour\` (SYSTEM et
administrateurs), sans rien faire d'autre ; l'installateur le lance avant
d'enregistrer la seconde tâche, et **n'enregistre pas** la tâche s'il échoue (le
serveur, lui, reste installé : relancer la commande en console administrateur pour
lire le motif).

**Désinstaller pendant une mise à jour.** `desinstaller-demarrage.ps1` retire la tâche
de mise à jour **d'abord**, et **refuse** si elle tourne : l'arrêter en pleine
bascule laisserait des fichiers mêlés que plus aucune tâche ne reprendrait. Réessayer
dans quelques minutes ; si `python serveur\maj.py etat` montre longtemps une étape
autre que `repos`, lancer `python serveur\maj.py reprendre`.

**Limites connues.** Un appareil du réseau qui interroge le serveur toutes les
trente minutes empêche tout arrêt concerté, donc toute mise à jour (le sens de
l'échec est le bon : jamais un bilan coupé ; `/etat` montre `reportee`,
`ARRET_REFUSE`). L'hébergeur doit servir l'archive **avant** son manifeste et sa
signature : un manifeste neuf servi avec l'archive ancienne donne
`ARCHIVE_DIFFERENTE`, refus propre, nouvel essai au contrôle suivant.

## 8. Ce que le client ne fait pas

- Il n'envoie rien : trois `GET` anonymes, aucune statistique d'usage, aucune donnée
  du cabinet.
- Il ne s'authentifie pas auprès de l'hébergeur (D-M1, voie (d) : l'adresse, qui
  ouvre le paquet d'un client, est le seul secret, et elle ne protège que du code et
  un schéma). Aucun jeton n'est posé sur le PC.
- Il ne lit aucun proxy dans l'environnement ni dans le registre : seulement la clé
  `proxy` de `config.json`.
- Il ne révoque pas une clé : une clé qui a fuité ne se désactive pas à distance
  (`docs/cle-publication.md`, §8).
- Il refuse de s'exécuter dans un dépôt de développement (dossier `.git`) : il
  agirait sur les fichiers réels du cabinet présents à la racine.
- Il ne choisit ni l'hébergeur, ni le nom de canal, ni ne retire une version : c'est
  C5-T3.
