# Mettre à jour le serveur d'un cabinet

**Contrat :** `docs/contrats/C5-T2.md` (partie C5-T2a)
**Client :** `serveur/maj.py` — bibliothèque standard seule
**Public :** la personne qui assiste un cabinet (séance d'assistance ou visite),
jamais la praticienne.

C5-T2a installe un **paquet signé posé sur le PC du cabinet**. Le téléchargement
automatique est C5-T2b : tant qu'il n'est pas livré, rien ne se met à jour tout
seul, et cette fiche décrit l'application **à la main**, en séance d'assistance
(à distance, sans déplacement).

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

Le dossier `mise-a-jour\` (à côté de `config.json`) est créé et protégé par le
client lui-même au premier appel : seuls SYSTEM et les administrateurs y ont des
droits. S'il existe déjà avec d'autres droits, ils sont resserrés ; si un lien ou
une jonction l'occupe, c'est un refus (`DOSSIER_NON_PROTEGE`).

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
3. **Sauvegarde** de tout ce qui va être remplacé, dans `mise-a-jour\sauvegarde\`.
4. **Arrêt concerté** : le client *demande* au serveur de s'arrêter, et c'est le
   serveur qui décide. Il refuse pendant un dépôt, et tant qu'une requête (hors
   sonde de santé) date de moins de `--calme-minutes`. Refus : code de sortie 3,
   rien n'a changé, on recommence plus tard.
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
`serveur\`, `formulaire\`, `docs\`), **sauf** `inventaire.json` et `installe.json`
(propres au client). Effacer ensuite `serveur\__pycache__`, redémarrer la tâche,
et vérifier `/sante` puis `/etat`. Les fichiers listés dans `absents` de
`inventaire.json` sont ceux que la mise à jour avait *ajoutés* : les supprimer.

## 7. Ce que le client ne fait pas (encore)

- Il ne télécharge rien : c'est C5-T2b (un appel sortant HTTPS, trois `GET`, aucune
  donnée du cabinet).
- Il n'a pas de tâche planifiée à lui : aucune mise à jour ne part toute seule.
- Il ne révoque pas une clé : une clé qui a fuité ne se désactive pas à distance
  (`docs/cle-publication.md`, §8).
- Il refuse de s'exécuter dans un dépôt de développement (dossier `.git`) : il
  agirait sur les fichiers réels du cabinet présents à la racine.
