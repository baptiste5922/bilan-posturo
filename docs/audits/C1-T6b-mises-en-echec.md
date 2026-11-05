# C1-T6b — mises en échec

Journal des mutations volontaires de l'étape 13 du contrat
(`docs/contrats/C1-T6b.md`). Une garde qui n'a jamais été mise en échec ne garde
rien (`CLAUDE.md`, premier piège) : chaque ligne ci-dessous a été jouée, avec un
**témoin sans mutation** et le **code de retour du test lui-même**.

**Aucun texte de la fiche du prospect n'est consigné ici**, ni aucun marqueur :
seuls figurent des nombres, des booleens, des codes de retour, des noms de tests
et les numéros de ligne que les échecs nomment eux-mêmes.

## Méthode

- **a, b, c, k, o** (outillage Node) : mutation faite sur une copie
  `git ls-files -z --cached --others --exclude-standard` du dépôt (125 fichiers ;
  aucun `*.pem`, `config.json`, journal, `autorite.crt` ni `fiche_presentation*`
  dans la copie : `find … | wc -l` → 0), le fichier étant sauvegardé hors du dépôt
  avant la mutation et restauré par `cp`, puis comparé au dépôt par `cmp`. Pour c,
  un clone superficiel (`--depth 1`) du dépôt, sans remote.
- **d, e, m** (Python, sans historique) et **f, g, h, i, j, l, n** (Python, avec la fiche
  et un historique modifié) : un **pilote** Python hors dépôt (bloc-notes de la
  session). À chaque lancement, il fait un **clone jetable** complet du dépôt
  (`git clone file://…`), retire aussitôt `origin` et vérifie
  `git -C <clone> remote | wc -l` → **0** avant toute mutation (consigné pour
  chaque lancement ci-dessous), importe le module de garde **du clone**, pose
  `module.FICHE` au chemin absolu de la fiche d'origine (lue sur place, jamais
  copiée), joue un témoin, applique la mutation, rejoue, et supprime le clone.
- Le marqueur n'existe que dans la mémoire du pilote et dans le clone, le temps
  d'un lancement : message de commit passé à `git commit -F -` par l'**entrée
  standard** (`--cleanup=verbatim`), nom de branche créé par
  `git update-ref --stdin` (commande lue sur l'entrée standard), fichier de j
  écrit par le pilote dans le clone. Jamais dans l'environnement, jamais sur une
  ligne de commande, jamais affiché. Le pilote capture la sortie des tests dans
  un tampon et vérifie qu'aucun marqueur n'y figure.
- Chaque mutation est jouée deux fois, sous `python3` puis `python3 -O`.
- Après la dernière mutation : `test -d <clone>` → 1 (le clone n'existe plus),
  `git status` du dépôt réel vide, aucune référence nouvelle (critère 21).

## Résultats

| # | Mutation | Fichier muté | Témoin | `python3` | `python3 -O` | Ce que l'échec nomme |
|---|---|---|---|---|---|---|
| a | `cdp.js` de `ccd75d5` restauré | copie de `outils/reference-visuelle/cdp.js` | `test_cdp.js` : 3 `ok`, code 0 | code 1 (3 cas sur 3 en échec) | sans objet (Node) | les trois cas : message inattendu (`onglets.find is not a function`) et « aucun refus en 5 s : cdp.js a continué sur un port occupé » |
| b | `mkdtempSync` replacé avant la sonde | copie de `cdp.js` | idem, code 0 | code 1 (1 cas sur 3) | sans objet | le seul cas « aucun profil temporaire créé avant le refus » : `un profil profil-chrome-* a été créé avant le refus` (119 !== 118) |
| c | clause `CI` retirée du cas de repère | clone superficiel, `tests/test_export_grille.js` | sans `CI` : code 0 ; `CI=true` : code **1** (message `fetch-depth: 0`) | `CI=true` avec la mutation : code **0** au lieu de 1, ligne `saut - …` | sans objet | aucune garde ne rougit : c'est la mutation qui passe, d'où le code 0 attendu et obtenu. Restauré : `CI=true` → code 1 |
| d | `src`/`href` retirés de la récolte (`ATTRIBUTS_DE_REFERENCE` vidé) | clone, `tests/test_confidentialite_prospect.py` | `ExtractionDeLaFiche` code 0 | code 1 | code 1 | `test_valeurs_d_attributs_et_litteraux` : `'#une-ancre' not found` dans les valeurs récoltées |
| e | exemption élargie au commit entier (ligne ignorée) | clone, idem | `ReperageHorsFichiers` (7 cas) code 0 | code 1 | code 1 | `test_l_exemption_ne_couvre_que_sa_ligne` (le couple de la ligne 3 disparaît à tort) |
| f | commit jetable dont le message porte un marqueur (le plus court, 8 caractères) | clone (historique), message par entrée standard | `…messages_de_commit` code 0 | code 1 | code 1 | `texte de la fiche retrouvé dans les messages de : <sha 12>:1` ; marqueur absent de la sortie : **True** |
| g | branche jetable dont le nom porte un marqueur (motif `^[a-z0-9-]+$` ; 51 candidats, le plus court retenu, 8 caractères) | clone, `update-ref --stdin` | `…noms_de_reference` code 0 | code 1 | code 1 | `…le nom des références de rang : 2` ; marqueur absent de la sortie : **True** |
| h | `MESSAGES_EXEMPTES` vidé | clone, `tests/test_confidentialite_prospect.py` | `…messages_de_commit` code 0 | code 1 | code 1 | `…dans les messages de : fbf905a144ab:1` |
| i | exemption pointant un autre commit de la plage (celui de `HEAD`) | clone, idem | `…exemptions_toujours_justifiees` code 0 | code 1 | code 1 | `exemption sans objet (commit absent de la plage ou ligne sans marqueur) : <sha 12>:1` |
| j | fichier non suivi du clone portant la charge utile **entière et la plus courte** des 5 `src` (9 356 caractères, retenue comme marqueur : True) | clone, `mutation-j.txt` écrit par le pilote | `…fichiers_changes` code 0 | code 1 | code 1 | `texte de la fiche retrouvé dans : mutation-j.txt:2` ; marqueur absent de la sortie : **True** |
| k | comparaison de hauteur neutralisée (`hauteur <= etat.page` → `hauteur !== null`) | copie de `essai-grille.js` | à 734 px, copie non mutée : code **1** (ligne de hauteur de la grille 3 : RATÉ, 963 px pour 962,84) | à 734 px, copie mutée : code **0** au lieu de 1 (la même ligne passe « OK ») | sans objet | rien : la ligne RATÉ du témoin devient OK ; à 1 280 px (non muté), huit lignes OK, code 0 |
| l | `BLOBS_EXEMPTES` vidé | clone, `tests/test_confidentialite_prospect.py` | `…blobs_de_la_plage` code 0 | code 1 | code 1 | `texte de la fiche retrouvé dans les blobs : 81f06a971edc (formulaire/style.css):620` ; marqueur absent de la sortie : **True** |
| m | exemption de blob élargie au blob entier (ligne ignorée) | clone, idem | `ReperageHorsFichiers` (11 cas) code 0 | code 1 | code 1 | `test_l_exemption_de_blob_ne_couvre_que_sa_ligne_et_son_blob`, seul cas en échec |
| n | deux commits jetables : l'un ajoute un fichier portant un marqueur (le plus court, 8 caractères), le suivant le retire | clone (historique), fichier écrit par le pilote, commits aux messages neutres | blobs + fichiers changés : code 0 | blobs : code **1** ; garde de l'état final (`…fichiers_changes`) : code **0**, le fichier n'étant plus dans l'arbre | blobs : code 1 ; état final : code 0 | `texte de la fiche retrouvé dans les blobs : <sha 12> (mutation-n.txt):2` ; marqueur absent de la sortie : **True**. C'est la preuve que la garde de l'état final seule laissait passer le cas. |
| o | ancienne conclusion de la sonde restaurée (`portEstOccupe` rend `false` pour toute erreur) | copie de `outils/reference-visuelle/cdp.js` | `test_cdp.js` : 5 `ok`, code 0 | code 1 (1 cas sur 5) | sans objet (Node) | le seul cas « un port qui accepte la connexion sans jamais répondre est refusé, en moins de 5 s » : `aucun refus en 5 s : cdp.js a continué sur un port occupé` |

`git -C <clone> remote | wc -l` relevé **avant la première mutation** de chaque
clone : **0** pour d, e, f, g, h, i, j sous `python3` et sous `python3 -O` (14
clones), **0** pour les six clones de l, m, n (sous `python3` puis `-O`), et **0** pour le clone superficiel de c. Chaque pilote a affiché
`clone supprime : True`.

## Ce que les mutations ont appris

- **Mutation a sous macOS : l'ancien `cdp.js` lance un Chrome sur le port d'un
  autre serveur.** Avec un port qui répond 404, `dejaLa` valait `false` et Chrome
  était lancé (en vain : le port est pris) ; il restait en vie après la fin du test.
  Les processus `profil-chrome-` restants (11 lignes de `ps`) ont dû être arrêtés à la main
  (`pkill -f "user-data-dir=.*profil-chrome-"`), ce qui n'aurait pas été
  nécessaire sur le code livré (le refus précède `spawn`).
- **Le témoin des mutations d à j est lui-même un test** : chaque lancement joue
  d'abord la garde sans mutation (code 0), de sorte que le code 1 suivant est bien
  imputable à la mutation seule.
- **Mutation e** : sur les sept cas de `ReperageHorsFichiers`, un seul rougit
  (`test_l_exemption_ne_couvre_que_sa_ligne`) : c'est lui, et lui seul, qui
  empêche d'élargir l'exemption au commit entier.
- **Mutation j** : la charge utile la plus courte fait 9 356 caractères. Un
  fragment ne ferait rien rougir (la garde cherche chaque marqueur en entier) :
  c'est pourquoi la mutation prend la charge utile entière.
- **Mutations l à o (correctifs de l'audit)** : le blob exempté de la mutation l
  est le seul que la garde des blobs nomme quand l'exemption disparaît ; aucun
  autre blob de la plage ne porte de marqueur. La mutation n joue le scénario que
  l'audit avait relevé : un texte commité puis retiré avant la poussée.
- **Mutation o** : sans le cas du serveur muet, l'ancienne conclusion (« toute
  erreur de `fetch` vaut libre ») passerait les quatre autres cas ; l'ancien code,
  sur macOS, lance alors un vrai Chrome sur un port tenu par un autre service. Les
  processus `profil-chrome-` restants ont été arrêtés (0 après).
