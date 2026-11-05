# Audit C1-T6b — Fiabiliser l'outillage et les gardes de la grille

**Date :** 2026-11-05  **Périmètre audité :** `ccd75d5..eaf9711` (7 commits, branche
`c1-t6b-outillage`) : `outils/reference-visuelle/{cdp,essai-grille,produire}.js`,
`tests/test_cdp.js`, `tests/test_export_grille.js`,
`tests/test_confidentialite_prospect.py`, `.github/workflows/tests.yml`,
`package.json`, `docs/schema-formulaire.md`, le constat
`docs/references-visuelles/CONSTAT-2026-11-05-C1-T6b.md`, le journal
`docs/audits/C1-T6b-mises-en-echec.md` ; le pilote et les sorties de mutation du
bloc-notes de session ; les références locales et distantes et tous les objets
du dépôt réel.
**Verdict :** CONFORME SOUS RÉSERVE

Aucun texte de la fiche du prospect ne figure dans ce rapport : seuls des
chemins, des empreintes, des numéros de ligne, des longueurs et des rangs.

## Ce qui a été vérifié pour les quatre demandes prioritaires

**1. Aucune fuite de la fiche.** Une sonde hors dépôt a calculé les 365
marqueurs par `marqueurs_de_la_fiche()` (fiche lue sur place), puis a cherché
chacun, sans jamais l'imprimer :
- dans le contenu à `eaf9711` des 12 fichiers changés de la plage, et dans
  toutes les lignes ajoutées du diff : **0** ;
- dans les 7 messages de `ccd75d5..eaf9711` : **0** ; dans les 23 de
  `1ec796c..eaf9711` : **1**, `fbf905a144ab:1`, la collision fortuite exemptée
  (le message entier n'en porte pas d'autre, ni à cheval sur deux lignes) ;
- dans le message de l'étiquette annotée `frontiere-mit` : **0** ;
- dans les 24 noms de référence locaux (branches, étiquettes, distantes) et les
  14 noms de `git ls-remote origin` : **0** ;
- dans les 826 fichiers du bloc-notes de session : **1**, `audit-pages.js`
  (daté du 4 novembre, session d'audit de C1-T6, antérieur à la tâche : voir le
  constat Faible ci-dessous) ; **0** dans le pilote, les sorties `pil/*.txt`,
  le journal, les relevés de références ;
- aucun fichier `fiche_presentation*` dans le bloc-notes de session ;
  `git ls-files` n'en suit aucun ; `git check-ignore` → 0.

Le constat et le journal des mutations ont été relus en entier : chiffres,
codes, noms de tests, SHA abrégés et numéros de ligne seulement.

**2. La garde mord.** `python3 -m unittest -v tests.test_confidentialite_prospect`
et la même sous `-O` : 17 cas, OK, les trois nouvelles méthodes « ok » et non
« skipped ». Aucune `assert` nue (`grep` → 1). `MESSAGES_EXEMPTES` : 1 entrée,
`JETONS_TECHNIQUES_PUBLICS` : 1. L'exemption est soustraite comme couple
(`trouves - set(exemptions)`, `tests/test_confidentialite_prospect.py:326`) : ni
autre ligne, ni autre commit (cas de `ReperageHorsFichiers`, mutations e et i,
relues dans `pil/e.txt` et `pil/i.txt`). Les messages d'échec ne rendent que
`sha[:12]:ligne` ou des rangs ; le message standard d'`assertEqual` y ajoute le
SHA complet, jamais un texte. Garde anti-vacuité : le décompte des messages est
confronté à `git rev-list --count` (`:531-534`), les trois lectures `git`
nouvelles lèvent `RuntimeError` sur un code non nul (`:343-368`), `noms` vide
fait échouer (`:548`). Une plage vide passe — c'est correct, il n'y a alors rien
à publier. Dans un clone superficiel sans fiche : `ReperageHorsFichiers` et
`ExtractionDeLaFiche` jouent (aucun saut), seules les 4 méthodes de
`AucunMarqueurDeLaFiche` sautent, comme prévu.

**3. Aucune trace des mutations.** `refs-avant.txt` / `refs-apres.txt` ne
diffèrent que par `refs/remotes/origin/c1-t6b-outillage` ; l'état actuel est
identique à `refs-apres.txt`. `remote-avant/apres` ne diffèrent que par
`refs/heads/c1-t6b-outillage`, et `git ls-remote origin` ne porte aucun nom
porteur. Parmi les 814 objets du dépôt réel (accessibles ou non), aucun commit
de l'auteur « Pilote » ; les 12 commits inaccessibles ne portent aucun
marqueur. `git log --format=%s ccd75d5..HEAD | grep -vc '^C1-T6b'` → 0. Aucun
remise (`stash`), un seul arbre de travail. Le pilote (`pilote.py`) clone par
`file://`, retire `origin` et s'arrête si un remote subsiste, passe le message
par `git commit -F -` et la branche par `git update-ref --stdin`, jamais en
argument ni en variable d'environnement, et supprime le clone dans un `finally`.
Les 14 sorties consignent `remote | wc -l -> 0`, `clone supprime : True`,
`marqueur absent de la sortie : True`. j a bien pris la plus courte des 5
charges utiles (9 356 caractères).

**4. Fichiers réels du cabinet.** Non lus par moi (métadonnées seules). Leurs
dates d'accès sont toutes antérieures au 5 novembre ; aucun n'est suivi par Git ;
les bacs du bloc-notes portent des `config.json` de 396 octets générés sur place
le 4 novembre (le réel en fait 274), des bilans fictifs, et le montage de la
tâche (`monter_bac.py`) copie par `git ls-files -z -- serveur formulaire`.
`formulaire/`, `serveur/` et `CLAUDE.md` intacts depuis `ccd75d5`.

**Contrôles rejoués.** `node tests/test_cdp.js` → 0, trois `ok`.
`CI=true node tests/test_export_grille.js` → cas « sans grille » joué, 0. Clone
superficiel : sans `CI` → `saut -`, code 0 ; avec `CI=true` → échec nommant
`fetch-depth: 0`, code 1. CI 42103090760 : `success` sur `eaf9711`, 7 jobs ;
journal : 0 « saut - options de capture », 5 « ok - sans grille… »,
`test_mit_historique_identique_au_commit_frontiere` 5 fois `ok`.

## Constats

### Moyenne — La garde des fichiers ne voit que l'état final, pas l'historique qui part sur GitHub
**Où :** `tests/test_confidentialite_prospect.py:285-291`
(`fichiers_modifies_ou_ajoutes`, inchangée par la tâche) et `:300-306`
(`localiser_marqueurs`), à rapprocher de la docstring `:11-14` qui annonce
désormais « tout cela part sur GitHub ».
**Scénario :** pendant le schéma du prospect, un texte de la fiche est collé
dans un fichier, commité, puis retiré par un commit suivant. `npm test` lit
`git diff 1ec796c` contre l'arbre de travail : le texte n'y est plus, la garde
est verte. `git push` publie les deux commits, et le blob intermédiaire reste
lisible pour toujours sur GitHub. Ce chemin n'est pas théorique : le blob
`81f06a971edc` (`formulaire/style.css`, introduit par `fbf905a`, remplacé par
`729ec2c`), présent sur `origin/c1-t6-grille` et `origin/c1-t6b-outillage`,
porte à sa ligne 620 un marqueur de 8 caractères que la garde n'a jamais vu.
Vérification faite, c'est **le même** marqueur que la collision fortuite de
`fbf905a:1` (même rang dans l'ensemble trié, même longueur) : rien de nouveau
n'a fui. Mais la garde n'aurait pas mieux réagi à un vrai texte de la fiche.
**Propriété à rétablir :** tout blob introduit par un commit de
`repère..HEAD` est soumis aux marqueurs, pas seulement l'état final de l'arbre ;
le blob `81f06a971edc` devra alors faire l'objet d'une décision de l'architecte
(même collision que l'exemption existante), ancrée comme elle sans recopier de
texte. À fermer avant le premier schéma client à grille, qui est la tâche où ce
scénario a le plus de chances de se produire.

### Faible — La sonde de `cdp.js` tient pour libre un port qui accepte la connexion sans répondre en 3 s
**Où :** `outils/reference-visuelle/cdp.js:43-48`
**Scénario :** un processus tient le port de débogage mais ne répond pas à
`/json/version` en 3 s (un Chrome laissé par un essai précédent, machine
chargée, ou un service muet). `AbortSignal.timeout(3000)` rejette, le `catch`
pose `occupe = false`, et un nouveau Chrome est lancé ; il ne peut pas se lier
au port. `lireJson` (`:18-27`, sans délai par requête) attend alors le premier
qui répond : soit indéfiniment, soit l'**ancien** processus, piloté à une fenêtre
inconnue — exactement R2. `essai-grille.js` est protégé par sa relecture de
largeur ; `produire.js` ne l'est que si `ESSAI_LARGEUR` est posé. Rien ne touche
une consultation : c'est la valeur d'un verdict « au pixel » qui est en jeu. Le
délai en lui-même est raisonnable (une sonde ne doit pas figer l'outil) ; c'est
la **conclusion** tirée de son expiration qui contredit D2.
**Propriété à rétablir :** un port sur lequel une connexion TCP est acceptée est
occupé, qu'il réponde ou non ; seul un refus de connexion le déclare libre.

### Faible — Copies et fragments de la fiche hors racine, antérieurs à la tâche
**Où :** `/private/tmp/claude-501/-Users-baptiste--claude-spares-spare-k7z19D/907680dc-bff9-40f5-8f36-94f0bfd8f0b9/scratchpad/servi/fiche_presentation.html`
(créée le 2026-11-03 à 22:45, 133 634 octets, version voisine de la fiche
actuelle), avec dans le même bloc-notes un `fiche-impression.pdf` non ouvert ;
et `audit-pages.js:31` du bloc-notes de cette session (2026-11-04 15:35, un
marqueur de 12 caractères).
**Scénario :** la règle « aucune copie de la fiche, nulle part » est enfreinte
depuis le 3 novembre par une session précédente, hors de tout contrôle : un
`tar`, une copie de bac à sable ou un envoi de ce dossier temporaire emporterait
le document confidentiel. Aucun lien avec C1-T6b, dont le bloc-notes est
propre sur ce point ; rien n'est public.
**Propriété à rétablir :** aucune copie ni fragment de la fiche hors de la
racine du dépôt ; les deux résidus sont à purger par Baptiste.

## Rubriques sans constat

1. **Données de santé** — sans objet : `formulaire/` et `serveur/` intacts
   (`git diff --quiet` → 0) ; les seules requêtes ajoutées visent `127.0.0.1`
   dans l'outillage ; aucun journal du serveur touché.
2. **Surface exposée** — sans objet : aucune route, aucun changement de la
   racine web ni d'`EXTENSIONS_SERVIES`. `cdp.js` ne pilote plus un Chrome
   qu'il n'a pas lancé (sous la réserve du constat Faible).
3. **Authentification et cryptographie** — sans objet. `fetch-depth: 0`
   n'apporte à la CI que l'historique déjà public ; le contrôle « aucun secret
   versionné » est inchangé et vert.
4. **Écriture de fichiers** — sans objet côté serveur. Outillage : aucun profil
   créé avant le refus (cas dédié, mutation b) ; les ~121 `profil-chrome-*` de
   `$TMPDIR` sont hors périmètre, déjà connus.
5. **Robustesse de service** — sans objet : aucun code du serveur ni du
   formulaire. L'échec intermittent `ServeurArret.test_arret_journalise` signalé
   par l'implémenteur porte sur un serveur inchangé : non lié.
6. **Côté navigateur** — sans objet : `formulaire/` intact ; `essai-grille.js`
   lit les constantes de la page servie, ne les recopie pas (critère 24).
7. **Chaîne d'approvisionnement** — aucune dépendance ajoutée ; `test_cdp.js`
   n'utilise que Node ; `actions/checkout@v4` inchangé, seul `fetch-depth`
   ajouté au job `test`, et seul.
8. **Conformité** — sans objet pour HDS et dispositif médical. Confidentialité
   contractuelle du prospect : traitée ci-dessus ; aucune donnée ne quitte le
   poste, la CI ne voit pas la fiche (limite assumée, §10 du contrat).

## Points à surveiller plus tard

- `fichiers_modifies_ou_ajoutes` et `corpus_public` (inchangées) ignorent le
  code de retour de `git` : un `git diff` en échec rendrait la garde des
  fichiers vacante, alors que les nouvelles lectures lèvent. À aligner en même
  temps que le constat Moyen.
- Le repère de la garde Python reste abrégé (`COMMIT_DE_REPERE = "1ec796c"`,
  `:34`) alors que `test_export_grille.js` est passé au SHA complet : une
  ambiguïté future ferait lever les messages mais taire les fichiers.
- Messages d'étiquettes annotées non scannés (seuls les noms) ; aujourd'hui une
  seule, propre.
- Dans un message qui porte déjà un marqueur sur une ligne, un marqueur à cheval
  sur deux lignes n'est pas signalé (`:321-325`) ; sans effet tant que la seule
  exemption, immuable, n'en porte pas (vérifié).
- Le piège « `cdp.js` réutilise… » de `CLAUDE.md` est devenu faux :
  `/cloture-projet`.

---

## Réaudit

**Date :** 2026-11-05  **Périmètre :** `eaf9711..fb12203` (3 commits, poussés),
soit `tests/test_confidentialite_prospect.py`, `outils/reference-visuelle/cdp.js`,
`tests/test_cdp.js`, `docs/audits/C1-T6b-mises-en-echec.md` ; les sorties
`pil/l*`, `pil/m*`, `pil/n*` et le pilote du bloc-notes. CI 42108356730 :
`success` sur `fb12203`.
**Verdict :** CONFORME

### Sort des constats du premier passage

- **Moyenne — historique non lu : levée.** `blobs_de_la_plage()`
  (`:416-463`) lit tout objet de `git rev-list --objects <repère>..HEAD` et garde
  les blobs ; `localiser_dans_blobs()` (`:353-379`) est pure. J'ai vérifié la
  couverture indépendamment : les 71 blobs qu'introduisent, commit par commit,
  les diffs de la plage (`git log --raw -m`) sont exactement les 71 que lit la
  garde, et aucun blob introduit n'y échappe hors de l'arbre du repère (déjà
  public). Un blob remplacé avant la poussée est vu : mutation n, dans les deux
  modes, garde de l'état final verte et garde des blobs rouge, avec deux SHA de
  blob jetable différents (`pil/n.txt`, `pil/n-O.txt`). **Pas de passage à vide :**
  `rev-list`, `cat-file` en échec, objet `missing`, entête inattendu ou nombre
  d'objets rendus différent du nombre demandé lèvent ; le test confronte le
  décompte à un second comptage (`rev-list` + `--batch-check`). Une plage vide
  donne 0 = 0 et passe, ce qui est correct. **Exemption :** une seule,
  `(81f06a971edc…, 620)`, retirée comme couple (sha, ligne) (`:378`). Ce blob
  ne porte qu'un marqueur, sur la seule ligne 620, et aucun à cheval entre deux
  lignes : l'angle mort de la ligne 0 ne cache rien. Mutation l (exemption vidée)
  la nomme seule ; mutation m (exemption élargie au blob) fait rougir le cas
  dédié ; `test_exemptions_toujours_justifiees` couvre aussi les blobs. Ce blob
  est bien celui de la collision fortuite déjà jugée : même marqueur que
  `fbf905a:1`.
- **Faible — sonde de `cdp.js` : levée.** `portEstOccupe()` (`cdp.js:44-52`)
  ne déclare libre qu'un refus de connexion (`ECONNREFUSED`, seul ou en
  agrégat) ; une réponse, un délai écoulé ou toute autre erreur le disent
  occupé. Les 5 cas de `test_cdp.js` sont verts, dont le serveur `net` muet,
  refusé en moins de 5 s ; mutation o (ancienne conclusion) le fait rougir seul.
- **Faible — résidus hors dépôt (copie du 3 novembre, `audit-pages.js`) :
  acceptés par Baptiste**, conservés en l'état ; ils ne sont plus un constat
  ouvert de cette tâche. Toujours présents, et toujours seuls porteurs de
  marqueurs dans le bloc-notes.
- **Points à surveiller du premier passage :** `fichiers_modifies_ou_ajoutes`
  et `corpus_public` lèvent désormais si `git` échoue (`:271-280`, `:300-306`) ;
  `COMMIT_DE_REPERE` est au SHA complet (`:37`). Clos.

### Contrôles rejoués

- Garde : 22 cas, OK sous `python3` et `python3 -O` ;
  `test_aucun_marqueur_dans_les_blobs_de_la_plage` et
  `test_exemptions_toujours_justifiees` « ok » ; aucune `assert` nue ;
  `MESSAGES_EXEMPTES`, `BLOBS_EXEMPTES`, `JETONS_TECHNIQUES_PUBLICS` : 1, 1, 1.
- Rien de la fiche dans les 4 fichiers de la plage, ses lignes ajoutées, ses 3
  messages, les 24 références locales, les 14 de `git ls-remote origin`, les
  sorties `pil/l*`, `pil/m*`, `pil/n*` ni le pilote. Les messages des commits
  jetables de n sont neutres, le marqueur n'est passé que par un fichier écrit
  par le pilote dans le clone.
- Six nouveaux clones : `remote | wc -l -> 0` et `clone supprime : True` dans
  chaque sortie ; aucun dossier `clone` dans le bloc-notes. Dépôt réel : 830
  objets, aucun commit « Pilote », seuls porteurs les deux objets déjà connus
  (`fbf905a`, `81f06a971edc`), références locales et distantes inchangées hors
  branche de la tâche.
- `formulaire/`, `serveur/` et `CLAUDE.md` intacts depuis `ccd75d5`.

### Points à surveiller plus tard

- **Une image de la fiche commitée en binaire échapperait à la garde.** Les
  marqueurs portent les charges utiles en base64. Or les blobs binaires sont
  ignorés (`:458-459`), comme les fichiers binaires (`:315`). Les 5 images
  embarquées de la fiche sont des PNG. Aucune n'est aujourd'hui identique,
  octet pour octet, à un blob du dépôt (vérifié par empreinte). Le schéma du
  prospect est pourtant la tâche où l'on pourrait vouloir déposer des images
  dans `formulaire/`. Il faudrait alors refuser au moins un blob identique à
  une image décodée de la fiche, en sachant qu'une image recompressée resterait
  invisible.
- Messages d'étiquettes annotées non scannés ; le piège « `cdp.js`
  réutilise… » de `CLAUDE.md`, pour `/cloture-projet`.

---

## Réaudit après revue

**Date :** 2026-11-05  **Périmètre :** `4156217..2e289fd` (2 commits, poussés) ;
CI 42111426184 : `success` sur `2e289fd`.
**Verdict :** CONFORME

- **L'optimisation ne change aucun résultat.** J'ai chargé côte à côte la garde
  de `4156217` et celle de `2e289fd`, sur le dépôt réel et avec les mêmes 365
  marqueurs (l'ensemble est identique d'une version à l'autre). Les résultats
  sont identiques sur la plage réelle :
  - sans exemptions : `localiser_dans_messages` rend 1 couple dans les deux
    versions (`fbf905a:1`), et `localiser_dans_blobs` 1 triplet
    (`81f06a971edc`, `formulaire/style.css`, 620) ;
  - avec exemptions : 0 dans les deux ;
  - `localiser_marqueurs` (fichiers) : 0 dans les deux.

  Sur des cas factices, les deux versions rendent aussi la même ligne :
  marqueur à cheval sur deux lignes (ligne 0), espaces et tabulations
  multiples, casse, formes Unicode décomposées et composées, sigma final grec,
  et un texte portant à la fois un marqueur sur une ligne et un autre à cheval.
- **Pas de normalisation divergente.** Le code de `normaliser` est identique
  à l'octet entre les deux versions. Le texte entier est normalisé une fois,
  hors du générateur, par la même fonction que les lignes et les marqueurs. Le
  chemin « à cheval » n'est emprunté, comme avant, que si aucune ligne ne porte
  de marqueur. Le préfiltre sur le blob entier, déjà présent au réaudit
  précédent, reste un sur-ensemble des lignes.
- **`cdp.js` : seul un commentaire est re-coupé.** Le source, privé de ses
  commentaires et de ses blancs, est identique entre `4156217` et `2e289fd`.
  `test_cdp.js` : 5 cas sur 5 verts.
- **Le reste.** Le commentaire sur la fragilité des deux exemptions face à une
  fusion qui réécrit l'historique dit juste : `test_exemptions_toujours_justifiees`
  échouerait alors. La docstring et la condition 2 de `docs/schema-formulaire.md`
  sont seulement re-coupées : la phrase exigée par le critère 26 y figure
  toujours une fois, et `VocabulaireFictif` passe.
- **Contrôles rejoués.** La garde passe sous `python3` (3,6 s) et sous
  `python3 -O`, sans `assert` nue. Rien de la fiche dans les deux messages ni
  dans les lignes ajoutées. Le rejeu de l, m et n est consigné avec des
  nombres, des SHA et des numéros de ligne seulement. Aucun commit « Pilote »
  parmi les objets du dépôt réel, aucun clone restant. Les références (24
  locales, 14 distantes) sont inchangées. `formulaire/`, `serveur/` et
  `CLAUDE.md` sont intacts.

Les points à surveiller du réaudit précédent demeurent : images de la fiche
commitées en binaire, messages d'étiquettes annotées.
