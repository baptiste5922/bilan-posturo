# Audit C1-T4a — Écrire le schéma du cabinet dans le dépôt

**Date :** 2026-11-06  **Périmètre audité :** `git diff 0f33cc0..28a75c6` sur
`c1-t4a-schema-cabinet` (5 commits, 20 fichiers), lu dans le contexte des
fichiers entiers : `outils/faire-paquet.sh`, `tests/test_schema_client.js`,
`tests/outils/analyseur-html.js`, `tests/test_paquet.py`,
`.github/workflows/tests.yml`, `outils/reference-visuelle/produire.js` et
`empreintes-pages.js`, le constat `CONSTAT-2026-11-06-C1-T4a.md`, le journal
`C1-T4a-mises-en-echec.md`, ainsi que le dossier de travail de la session.
**Verdict :** CONFORME

Aucune des six questions prioritaires ne fait apparaître de défaut. Les trois
constats sont **faibles** : deux portent sur ce que les barrières ne couvrent
pas, le troisième est un défaut antérieur du script de paquet que la tâche a
corrigé pour son propre contrôle sans l'étendre aux autres.

## Constats

### Faible — la sortie par défaut de `produire.js` est dans l'arbre, non ignorée, et hors de la barrière D4
**Où :** `outils/reference-visuelle/produire.js:35` (`SORTIE` vaut par défaut
`outils/reference-visuelle/sortie`) ; `.gitignore` (aucune règle pour ce
dossier) ; `.github/workflows/tests.yml:122-152` (la barrière ne lit que
`docs/references-visuelles`).
**Scénario :** quelqu'un lance `node outils/reference-visuelle/produire.js v1`
sans `ESSAI_SORTIE`, comme l'en-tête du script le permet (« défaut ./sortie »).
Le PDF, les deux captures PNG et le brouillon s'écrivent dans
`outils/reference-visuelle/sortie/`. Un `git add -A` les indexe ensuite. Je l'ai
rejoué dans un clone jetable sans `origin` : `git status` montre
`A outils/reference-visuelle/sortie/V1.pdf`, et le pas « Check that no image or
PDF is versioned… », extrait de `tests.yml` et lancé par `bash -e`, **sort 0**.
Aucun autre contrôle ne refuse un PDF ou une image hors de ce dossier : le pas
« aucun secret versionné » n'a pas de motif `.pdf`, et
`test_identite_absente` ne lit que le texte. Ces captures contiennent ce que le
`LISEZMOI` §4 décrit lui-même (onglets, favoris, notifications, en-tête et logo
du cabinet). Si `ESSAI_BASE` vise un serveur qui renvoie la vraie identité par
`GET /cabinet`, l'en-tête réel y figure aussi. Le bilan témoin reste fictif.
**Propriété à rétablir :** D4 (« images et PDF de mesure jamais versionnés »)
et le §10 du contrat (« une barrière CI le garantit désormais ») doivent tenir
pour **tout** emplacement où l'outillage du dépôt écrit ses mesures par
défaut. Aujourd'hui, ils ne tiennent que pour le dossier où l'on range les
constats.

### Faible — une archive incomplète reste sur le disque après l'échec du contrôle des pièces obligatoires (antérieur à la tâche)
**Où :** `outils/faire-paquet.sh:116-125` (boucle `obligatoire`, `exit 1` sans
effacement) ; à comparer avec `:128-134`, le contrôle ajouté par la tâche, qui
efface bien l'archive.
**Scénario :** une pièce obligatoire manque, par exemple
`formulaire/version.json` (essai dans une copie `git ls-files`). Le script
affiche l'erreur et sort en 1, mais `BilanPosturo-2026-11-06.zip` **reste dans
le dossier**, avec le nom exact d'un paquet valide. Quelqu'un qui ne lit pas la
sortie, ou une relance qui échoue avant d'atteindre `rm -rf`, peut envoyer au
cabinet un paquet sans licence ou sans moteur. La tâche n'aggrave pas ce
défaut, mais elle traite les deux contrôles différemment.
**Propriété à rétablir :** tout contrôle en échec, quel qu'il soit, ne laisse
aucune archive portant le nom d'un paquet livrable.

### Faible — G1 ne voit que les dossiers de `clients/`
**Où :** `tests/test_schema_client.js:57-61` (`isDirectory()` filtre les
entrées) ; `clients/LISEZMOI.md` affirme que le test « refuse un dossier mal
nommé ».
**Scénario :** un fichier déposé à plat dans `clients/` passe G1 sans un mot.
Il peut s'agir d'un fichier nommé d'après une ville, d'une fiche de
configuration ou d'une identité. Un lien symbolique `clients/cabinet-02` le
passe aussi : `Dirent.isDirectory()` est faux pour un lien. Or
`faire-paquet.sh cabinet-02` suit ce lien (`cp "clients/$CLIENT/schema.json"`),
si bien que le schéma livré n'aurait été ni validé par G2 ni vu par G1. Ce
défaut n'est pas exploitable sans un commit fautif. Mais le LISEZMOI promet
plus que ce que le test vérifie.
**Propriété à rétablir :** `clients/` ne contient que des dossiers
`cabinet-NN` réels, chacun avec son `schema.json`. Toute autre entrée, lien
compris, fait rougir le test.

## Vérifications prioritaires demandées

1. **Identité réelle du cabinet.** Le texte des quatre `<p>` de `#infos_podo`
   a été lu en mémoire depuis `production-cabinet-01:formulaire/index.html`,
   puis cherché sous trois formes : valeur entière, jetons de 5 caractères ou
   plus, suite de chiffres du téléphone. Aucune valeur n'a été affichée. Le
   détecteur a d'abord été éprouvé sur le blob lui-même : 17 correspondances.
   Les endroits fouillés sont :
   - les **22 blobs** créés par la plage et les **5 messages de commit** ;
   - les fichiers du bloc-notes de session, dont `prep.sh`, `mesurer.sh`,
     `mutations.sh` et `.out`, `npm-test*.txt` et les relevés ;
   - les **254 fichiers** créés aujourd'hui sous `/private/tmp/claude-501`,
     sorties des tâches comprises ;
   - les sorties d'échec de `test_schema_client.js` sous trois mutations :
     étiquette absente, clé renommée, `cleChamp()` mutée.

   Résultat : **aucune** valeur entière, aucun courriel, aucun téléphone.
   Seul un jeton de 7 caractères ressort, le nom de la ville. Il apparaît dans
   `tests/test_paquet.py:131` (entrée refusée), dans
   `docs/audits/C1-T4a-mises-en-echec.md:50` (M1) et dans le contrat. Cette
   ville est déjà publique : `CLAUDE.md:6` et des contrats antérieurs la
   citent.

   `prep.sh` substitue bien l'identité en mémoire avant toute écriture, et
   exclut `index.html` de `git archive`. `prod-index.html` n'existe plus.

   `tests/test_identite_absente.py` **couvre les nouveaux fichiers** : sa
   liste est dérivée de `git ls-files -z --cached --others --exclude-standard`,
   sans liste fermée, donc elle inclut `clients/` et le constat. Le test est
   vert, aussi sous `-O`. Il ne couvre pas les images (constat 1).
2. **`faire-paquet.sh <client>`.** 18 arguments essayés dans une copie
   `git ls-files`, avec le code lu directement :
   - vide et deux arguments : code 2 ;
   - formes de remontée : `../formulaire`, `cabinet-01/..`, `cabinet-01\n../x`,
     `../x\ncabinet-01`, `%2f`, séparateurs `\` ;
   - espaces de tête et de fin, tiret initial, majuscules, `cabinet-001` ;
   - chiffres pleine chasse et exposants, accent, sous `C`, `fr_FR.UTF-8` et
     `en_US.UTF-8` ;
   - tentatives d'injection `;touch` et `$(touch …)`.

   Tous rendent **2**, sans archive ni dossier, et aucun fichier témoin n'est
   créé. Seul `cabinet-01` rend 0. `"$CLIENT"` est toujours entre guillemets.
   L'archive est relue par `unzip -p | cmp`. Elle ne contient aucune entrée
   `/clients/` (`test_paquet` le vérifie). L'archive laissée après échec relève
   du constat 2.
3. **Barrière CI.** Rejouée dans un clone jetable : arbre sain 0 ;
   `capture-écran.png` (accentué) 1 ; `a.PDF` 1 ; un nom contenant un saut de
   ligne (`b.png⏎c.md`) 1 ; un `.jpg` en sous-dossier 1. Un code de `grep`
   supérieur à 1 est traité comme une erreur. Limites : un PNG renommé `.md`
   passe, car le filtre porte sur l'extension et non sur le contenu ; et le
   dossier de sortie par défaut n'est pas couvert (constat 1).
4. **G4.**
   - Contre le passage à vide : au moins 40 champs de chaque côté, 4 images
     annotables exigées, motifs `CLE_BROUILLON` et `cleChamp()` présents une
     seule fois.
   - Étiquette absente (clone `--no-tags`, sans `origin`) : code 1, quatre cas
     en échec avec le remède, **aucun saut**.
   - Les messages d'échec ne citent que des clés (`id`, `name#value` de champs),
     des `src` d'images, des décomptes et la valeur de `CLE_BROUILLON`.
     `deepStrictEqual` et `strictEqual` reçoivent toujours un message
     explicite, donc pas de diff du contenu.
   - Les erreurs de `git` et de `extraireElement` sont remplacées par des
     messages sans contenu du blob.
   - Les `<p>` d'identité ne sont que des nœuds de texte, jamais des champs.
5. **Fichiers réels.**
   - `releve-reel-avant.txt` et `releve-reel-apres.txt` sont identiques
     (8 entrées). Un relevé `stat` refait par l'audit, sans rien ouvrir, est
     identique aux deux.
   - Aucun `serveur.py`, `generer_autorite.py` ni Chrome piloté ne reste en
     cours d'exécution.
   - Une copie par `rsync`/`git ls-files` n'emporte aucun fichier ignoré.
   - Le dossier `mesure/` a été supprimé.
6. **Production.**
   - `git diff 0f33cc0..28a75c6 -- formulaire serveur docs/production` est
     vide.
   - Localement **et sur `origin`** (`git ls-remote`), l'étiquette
     `production-cabinet-01^{}` et `maintenance-cabinet-01` valent `d43350a0…`.
   - `cmp formulaire/schema.json clients/cabinet-01/schema.json` rend 0.

## Rubriques sans constat

1. **Données de santé** : aucun chemin nouveau vers l'extérieur.
   - `serveur/` est intact : journaux, `/sante` et `/etat` inchangés.
   - Le bilan de mesure est fictif.
   - Rien n'est écrit sous `formulaire/`.
   - `produire.js` affiche désormais le nom d'origine du PDF : celui du témoin,
     dans un outil de développement.
2. **Surface exposée** : inchangée.
   - La racine web reste `formulaire/` (`serveur.py` intact). `clients/`
     n'y est pas atteignable, conformément à D2.
   - Aucune route ajoutée.
   - La remontée de chemin par l'argument du paquet a été éprouvée
     (point 2 ci-dessus).
3. **Authentification et cryptographie** : sans objet, aucun code
   d'authentification touché.
   - `ESSAI_IDENTIFIANTS` passe par l'environnement, pas par la ligne de
     commande.
   - Les identifiants présents dans `mesurer.sh` sont ceux d'un bac à sable
     détruit.
   - Les certificats de mesure ont été produits dans le bac.
4. **Écriture de fichiers** : côté serveur, sans objet. Côté paquet, voir le
   constat 2. L'arbre de travail du paquet est ignoré par Git
   (`BilanPosturo-*/`).
5. **Robustesse de service** : sans objet pour le serveur. G4 dépend de
   l'étiquette publiée. Si elle disparaît, la CI rougit bruyamment ; c'est
   voulu.
6. **Côté navigateur** : aucun fichier de `formulaire/` modifié, donc ni
   `innerHTML`, ni CSP, ni `localStorage` touchés. La compatibilité du
   brouillon de `d43350a` est désormais gardée mécaniquement : clés,
   `CLE_BROUILLON`, corps de `cleChamp()`, ordre des images.
7. **Chaîne d'approvisionnement** : le paquet relit son propre contenu (`cmp`
   sur l'archive) et n'emporte aucun autre client. C5 n'est pas concerné.
8. **Conformité** :
   - aucun stockage chez l'éditeur, aucun sous-traitant ;
   - aucune aide à la décision ;
   - `clients/cabinet-01/schema.json` publie une structure déjà publique,
     identique à l'octet à `formulaire/schema.json`.

## Observations

- **Un `python3 -m http.server 8777 --bind 127.0.0.1` tourne depuis le
  19 octobre** (PID 77897), avec `formulaire/` du dépôt réel comme répertoire
  courant. Il est antérieur à la tâche et n'écoute que la boucle locale. C'est
  aussi la cible par défaut de `produire.js` (`ESSAI_BASE`). À arrêter par son
  propriétaire : l'audit ne l'a pas touché.
- La « variante B » (73 px, au plus 3/255, sous `serveur.py` en HTTPS) n'a
  aucune portée de sécurité. Le constat la rattache au serveur par le témoin Q.
- Le nom de la ville sert d'entrée refusée dans `tests/test_paquet.py:131`.
  Il est déjà public. Pour la règle D8, un nom générique de ville fictive
  aurait suffi.

## Points à surveiller plus tard

- **Fuite entre clients au deuxième paquet.** « Aucune entrée `clients/` »
  n'empêche pas un autre cabinet de recevoir ce qui est propre à `cabinet-01`
  hors du schéma. `cp -R formulaire` livre notamment `images/favicon.jpeg`,
  affiché comme logo du cabinet (`formulaire/index.html:88`). C'est à trancher
  avec C2-T2, avant `cabinet-02`.
- **Dossier du prospect.** Un `clients/cabinet-02/` créé localement, non
  ignoré, partirait au premier `git add -A`. Seule
  `test_confidentialite_prospect` le garde, sur un seul poste. Ce risque est
  déjà inscrit au §12 du contrat.
- Des répertoires `bilan-conservation-*` et `tmp*/bilan.pdf` (fictifs, vides)
  traînent dans `$TMPDIR` depuis les 3 et 4 novembre : un test antérieur ne
  nettoie pas derrière lui. Ils ne viennent pas de cette tâche.

## Réaudit après revue

**Date :** 2026-11-06  **Plage :** `2cbafa3..b3c6a3e` (2 commits, 13 fichiers ;
CI 42236920584 annoncée verte sur 7 jobs à `f907c6d`)
**Verdict : CONFORME.** Les trois constats faibles sont levés, sans constat
nouveau. Deux observations s'ajoutent, sans correction exigée.

Chaque garde a été éprouvée dans un clone jetable sans `origin`
(`git remote | wc -l` → 0). Le code de sortie relevé est toujours celui du
test lui-même, et chaque mutation a son témoin sur l'arbre sain.

### Constat 1 (sortie de `produire.js`) : levé

`.gitignore` et la barrière fonctionnent ensemble :
- **`.gitignore`.** Un `git add -A` n'indexe **rien** sous
  `outils/reference-visuelle/sortie/`, ni de `.png` posé directement dans
  `docs/references-visuelles/` (0 fichier indexé).
- **Barrière CI.** Le pas extrait de `tests.yml` et lancé par `bash -e` sort
  **0** sur l'arbre sain, et **1** dans chacun des cas suivants :
  - `sortie/V1.pdf` forcé par `git add -f` ;
  - `sortie/note.md` forcé : rien n'est admis dans `sortie/`, même un `.md` ;
  - `x.png` forcé dans `docs/references-visuelles/` ;
  - un `.DS_Store` forcé dans le même dossier ;
  - un `PNG` en majuscules dans un sous-dossier ;
  - un `.pdf` au nom accentué ;
  - un nom qui contient un saut de ligne pour se faire passer pour un `.md`
    de `docs/`.

Le motif est désormais ancré sur `^docs/references-visuelles/`, si bien
qu'un `.md` ou un `.json` ne passe que dans ce dossier. Le `.gitignore` ne
couvre que `*.png` et `*.pdf` en minuscules à la racine du dossier. Ce n'est
pas un trou : la barrière CI rattrape tout le reste, comme le montre le cas
du sous-dossier, qu'un `git add -A` indexe et que la barrière refuse.

Limite inchangée : la barrière juge l'extension, pas le contenu (un PNG
renommé `.md` passerait).

### Constat 2 (archive incomplète) : levé

Le `rm -f "$PAQUET.zip"` ajouté à `outils/faire-paquet.sh` vise un nom fixe,
`BilanPosturo-<date du jour>.zip`, dans la racine où le script s'est placé.
Aucune entrée utilisateur n'y entre.

Essai : sans `formulaire/version.json`, le script rend **1** et efface
l'archive du jour. Un `BilanPosturo-2020-01-01.zip` et un `autre.zip` posés à
côté restent **intacts**.

`tests.test_paquet` est vert, aussi sous `python3 -O`, avec le nouveau cas
`test_piece_absente_de_l_archive_efface_l_archive`.

### Constat 3 (G1) : levé

Essais de mutation, chacun avec son témoin sain (0) :

| Mutation | Code | Cas en échec |
|---|---|---|
| fichier à plat `clients/notes.txt` | 1 | G1 |
| lien `clients/cabinet-02 → ../formulaire` | 1 | G1 |
| lien `clients/cabinet-03 → cabinet-01` | 1 | G1 |
| `clients/LISEZMOI.md` remplacé par un dossier | 1 | G1 et G2 |

**L'exemption `.DS_Store` ne crée pas de trou exploitable.** Elle porte sur le
nom seul : un **dossier** ou un **lien** nommé `.DS_Store` passe aussi G1
(code 0, essayé). Il reste pourtant sans effet :
- `faire-paquet.sh` refuse `.DS_Store` comme client, car le motif est ancré ;
- `.gitignore` l'exclut ;
- rien ne le lit.

Voir l'observation ci-dessous.

### G4 lit un SHA complet : correct, et échoue toujours bruyamment

`REFERENCE_PRODUCTION` est le SHA complet `d43350a0cf20fef5672eadc7bcb6f67e156dc977`.
Un SHA ne se déplace pas, contrairement à l'étiquette que
`docs/production/cabinet-01.md` prévoit de déplacer. Ce commit est un ancêtre
de `main` et de la branche (`git merge-base --is-ancestor`), donc atteignable
en CI avec `fetch-depth: 0`.

Essai dans un clone `--depth 1 --no-tags` où le commit est absent : code
**1**, quatre cas G4 en échec avec le remède, quatre verts (G1 à G3),
**aucun saut**. La sortie d'échec, passée au détecteur d'identité, ne contient
rien.

### Identité réelle : rien de nouveau

Le détecteur est le même qu'au premier audit, déjà éprouvé sur le blob, et
n'affiche jamais les valeurs. Résultat :
- **0** occurrence dans les 14 blobs de la plage et dans les 2 messages de
  commit ;
- **0** dans les fichiers temporaires de la session postérieurs au premier
  audit ;
- **0** dans les sorties d'échec des mutations ci-dessus.

Le nom de la ville a disparu de `tests/test_paquet.py` et du journal des
mutations (`git grep` → 0). `tests.test_identite_absente` est vert.

### Production inchangée

- `git diff --stat 0f33cc0..b3c6a3e -- formulaire serveur docs/production`
  est vide.
- L'étiquette `production-cabinet-01^{}` et `maintenance-cabinet-01` valent
  `d43350a0…`, en local comme sur `origin` (`git ls-remote`).
- Aucun `serveur.py`, `generer_autorite.py` ni Chrome piloté ne reste en
  cours d'exécution.

Les autres changements ne relèvent pas de la sécurité :
- `empreintes-pages.js` rend 2 sur un fichier illisible ;
- `partager-paquet.sh` n'a changé que dans son message ;
- le constat a été reformulé, et F9 complétée.

### Observations du réaudit

- **Exemption `.DS_Store` plus large que son besoin.** Elle exempte le nom,
  quel que soit le type d'entrée. La réserver aux fichiers ordinaires suffirait
  à garder la promesse « ni lien ni fichier à plat » sans exception. Aucun
  effet aujourd'hui.
- **G1 ne regarde pas l'intérieur d'un dossier client.** Un fichier
  supplémentaire dans `clients/cabinet-01/`, lien compris, passe (code 0,
  essayé). Il ne part pas dans le paquet, qui ne copie que `schema.json`, et
  `test_identite_absente` lit son texte s'il est suivi. Ce n'est donc qu'un
  écart avec « son `schema.json`, rien d'autre » de `clients/LISEZMOI.md`.
- **La revue non suivie cite deux fois la ville.**
  `docs/revues/C1-T4a.md`, lignes 33 et 116, en dehors de la plage : c'est
  une information déjà publique. À garder en tête avant de l'indexer.
