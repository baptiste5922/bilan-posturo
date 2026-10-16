# Audit C1-T3b — Basculer le formulaire de production sur le moteur

**Date :** 2026-10-15
**Périmètre audité :** arbre de travail contre `664f923` (`git diff HEAD` +
`git status --short`) — `formulaire/index.html` (coquille, 118 l.),
`formulaire/index-v1.html` (nouveau, non suivi), `formulaire/moteur/rendu.js`,
suppression stagée de `formulaire/index-moteur.html`, `outils/faire-paquet.sh`,
`.github/workflows/tests.yml`, `tests/test_coquille.py` (nouveau),
`tests/test_paquet.py`, `tests/test_integration.py`,
`tests/test_comparaison_dom.js`, `tests/test_inventaire_formulaire.js`,
`README.md`, `docs/Mode_emploi.md`, `docs/USER-GUIDE.md`,
`docs/audits/C1-T3b-mises-en-echec.md` (non suivi). Lus en entier autour des
changements : `serveur/serveur.py` (non modifié), `formulaire/script.js` (non
modifié), `formulaire/schema.json`, `formulaire/style.css`.
Contrat : `docs/contrats/C1-T3b.md`, §10, §11, §12.

**Date du réaudit :** 2026-10-16
**Verdict :** CONFORME SOUS RÉSERVE — réserve = les critères 1, 2 et 11,
humains, toujours non exécutés (voir « Risque résiduel » et « Réaudit »).

**Premier passage (2026-10-15) : NON CONFORME.** Un constat élevé — la perte
silencieuse d'une saisie — 2 moyens, 4 faibles. Les sept sont corrigés et
vérifiés au réaudit du 2026-10-16 ; les constats d'origine sont conservés
ci-dessous tels qu'écrits, et la section « Réaudit » en fin de document dit
pour chacun ce qui a été éprouvé. **Plus aucun constat élevé ni critique.** Il
reste un faible nouveau (chemin n°9), un faible seulement partiellement
refermé, et le risque résiduel des trois critères humains, qui est la seule
raison de la réserve.

---

## Constats

### Élevée — Le filet de secours se retire alors que l'application n'a pas démarré

**Où :** `formulaire/moteur/rendu.js:935-939` (retrait de `#attente-moteur`),
`formulaire/moteur/rendu.js:959-966` (`afficherErreurMoteur()`),
`formulaire/index.html:117-118` (les deux `<script>`),
`formulaire/script.js:1088-1093` (`annoncer`).

**Scénario :** la coquille charge **deux** fichiers JavaScript au lieu d'un, et
le serveur répond `Cache-Control: no-store` (`serveur/serveur.py:400`) : les
deux sont retéléchargés à chaque ouverture de la page, sur le Wi-Fi de la
tablette. Entrée : `formulaire/script.js` n'arrive pas ou arrive tronqué (perte
de connexion en cours de chargement, ou, demain, une erreur de syntaxe
introduite dans ce fichier de 1223 lignes), tandis que `moteur/rendu.js` et
`schema.json` arrivent normalement. État : `rendre()` réussit, donc
`rendu.js:935-936` **retire** `#attente-moteur` ; puis `typeof
demarrerApplication === "function"` est faux et la branche est sautée **en
silence** ; `afficherErreurMoteur()` est de toute façon muet, puisque `annoncer`
vient lui aussi de `script.js`. Effet : les 28 blocs s'affichent, le formulaire
a l'air parfaitement normal, et pourtant `initSauvegarde()` n'a jamais tourné
(aucun brouillon n'est écrit dans `localStorage`), `initDessin()` non plus
(`zonesDessin` vide, le stylet ne marque pas) et `#btn-export` n'est câblé par
personne — la coquille n'a plus d'`onclick=`, délibérément
(`formulaire/index.html:38-41`). La praticienne remplit un bilan entier, touche
« Générer le PDF », **rien ne se passe et aucun message ne le dit**. Au
rechargement, tout est perdu.

J'ai reproduit les huit chemins de `demarrerMoteur()` sur un double de DOM : les
sept chemins d'échec prévus (404, 401, schéma refusé, `fetch` rejeté, JSON
illisible, `#form-bilan` absent, `<main>` absent) conservent tous
`#attente-moteur` **et** émettent le message français nommant le favori et
l'adresse — le filet tient, et bien. Le huitième, celui-ci, est le seul qui
passe au travers, et c'est celui qui ne dit rien.

C'est pire qu'un écran blanc : un écran blanc envoie au favori de secours, un
formulaire muet laisse travailler une heure pour rien. L'absence de
`script.js` était déjà fatale en V1, mais la V1 n'avait pas de filet à retirer,
et n'exigeait qu'**un** téléchargement réussi au lieu de deux.

**Propriété à rétablir :** le message de repli ne se retire que si
l'application a réellement démarré ; et un échec du moteur doit rester visible
par un chemin qui ne dépend pas de `formulaire/script.js`, puisque c'est
précisément le fichier qui peut manquer. Aucun des trois chemins
(`demarrerMoteur`, `afficherErreurMoteur`, et l'enchaînement
rendu → `demarrerApplication`) n'est aujourd'hui couvert par un test : la
propriété doit être garantie par un test, pas par construction.

---

### Moyenne — Un échec de `tests/test_coquille.py` publie les coordonnées du cabinet dans un journal public

**Où :** `tests/test_coquille.py:132-136` (`test_en_tete_identique_hors_espaces`),
`formulaire/index.html:84-96` (le `<header>` comparé).

**Scénario :** entrée : quelqu'un modifie l'en-tête de la coquille — ce que
C2-T1 fera par construction, en sortant l'identité en configuration, et ce
qu'une faute de frappe fait aujourd'hui. État : l'en-tête de `index.html`
diverge de celui d'`index-v1.html`, gelé. Effet : `assertEqual` sur deux
chaînes déclenche `assertMultiLineEqual`, qui imprime le **diff des deux
en-têtes** — donc le nom de la praticienne, l'adresse postale, l'adresse de
courriel et le numéro de téléphone — dans la sortie de
`python -m unittest discover -s tests` exécutée par
`.github/workflows/tests.yml:36`. Le journal d'actions GitHub est public et
conservé ; une donnée publiée ne se reprend pas.

Le §10 du contrat nomme explicitement cette propriété, et la garde d'identité
de `tests.yml:281-284` a justement été écrite pour ne citer **qu'un fichier et
une plage de lignes**. Le nouveau test fait l'inverse.

**Propriété à rétablir :** aucun chemin d'échec de la suite de tests n'émet le
contenu du bloc d'identité ; une comparaison sur ce bloc rapporte un écart par
sa position, pas par son texte.

---

### Moyenne — La garde d'identité n'a pas été étendue aux fichiers que la tâche ajoute

**Où :** `.github/workflows/tests.yml:239` (liste `cibles`),
`docs/audits/C1-T3b-mises-en-echec.md:206`.

**Scénario :** la garde d'identité fonctionne sur une **liste fermée de cinq
cibles** (`docs/schema-formulaire.md`, `tests/test_inventaire_formulaire.js`,
`formulaire/schema.json`, `formulaire/moteur/rendu.js`,
`tests/test_comparaison_dom.js`). Tout fichier hors de cette liste est, par
défaut, hors de la garde. C1-T3b ajoute deux fichiers qui manipulent l'en-tête
— `formulaire/index-v1.html` (exclu avec un raisonnement explicite et
recevable : empreinte SHA-256 figée, toute dérive d'un octet échoue) et
`tests/test_coquille.py` (exclu **sans** raisonnement, alors qu'il lit et
compare le bloc d'identité) — et n'ajoute ni l'un ni l'autre. Effet démontré,
pas hypothétique : `docs/audits/C1-T3b-mises-en-echec.md:206` recopie en clair
l'adresse postale du cabinet (ligne 73 de `formulaire/index-v1.html`, non recopiée ici) ; ce fichier est non suivi aujourd'hui, et
destiné au dépôt, qui est public. Le pas « Check that no secret is committed »
(`tests.yml:70-78`) ne filtre que des **noms** de fichiers, pas leur contenu :
rien ne s'y opposerait.

**Propriété à rétablir :** la garde d'identité doit refuser la recopie d'une
coordonnée **partout** sauf aux endroits explicitement justifiés, et non
l'autoriser partout sauf en cinq points. Et le document de mises en échec ne
doit pas emporter dans le dépôt la coordonnée qu'il a servi à détecter.

---

### Faible — L'adresse de repli, exigée par le §11, n'est garantie par aucun test

**Où :** `tests/test_comparaison_dom.js:552` (seul contrôle du message
statique), `formulaire/moteur/rendu.js:961-964`.

**Scénario :** le §11 exige que les **deux** messages nomment le favori **et**
l'adresse `index-v1.html` — le second sert au cas où le favori aurait disparu,
c'est-à-dire exactement le cas où le critère 2 n'a pas été exécuté. Le seul
contrôle existant est
`/id="attente-moteur"[^>]*>[^<]*secours V1/`. Un `grep -rn "index-v1.html"
tests/` ne rend aucune assertion sur le contenu des messages, et
`afficherErreurMoteur()` n'est contrôlé par rien du tout. Effet : la mention de
l'adresse peut être supprimée des deux messages sans qu'aucun test ne rougisse.

**Propriété à rétablir :** le libellé du dernier filet — favori **et** adresse,
dans le message statique comme dans `afficherErreurMoteur()` — est une
propriété testée.

### Faible — `docs/Mode_emploi.md` nomme le favori mais pas l'adresse

**Où :** `docs/Mode_emploi.md:58-62` et `:229`, `docs/USER-GUIDE.md:58-61`.

**Scénario :** le guide papier est le recours quand l'écran ne dit rien. Il
nomme « Formulaire — secours V1 » et s'arrête là. Si le favori n'a pas été posé
— et le critère 2 n'est **pas** exécuté, donc personne ne sait s'il existe — ou
s'il l'a été sur le mauvais profil Chrome, le guide n'offre aucune porte de
sortie, là où les deux messages de l'écran, eux, donnent l'adresse.

**Propriété à rétablir :** le document qui part dans le paquet dit la même
chose que l'écran, adresse comprise.

### Faible — La garde de palette liste deux fichiers HTML qu'elle ne lit jamais

**Où :** `.github/workflows/tests.yml:93-94` (boucle d'existence),
`:102-144` (les `grep` réels), `formulaire/index.html:74`,
`formulaire/index-v1.html:55`, `formulaire/style.css:13`.

**Scénario :** la boucle `for fichier in … formulaire/index.html …
formulaire/index-v1.html` ne fait qu'un `test -f`. Les `grep` sur le motif de
palette ne portent ensuite que sur `style.css`, `script.js` et
`moteur/rendu.js` : **aucun fichier HTML n'est jamais lu**, contrairement à ce
qu'affirme le commentaire réécrit par cette tâche (« un nouveau fichier JS ou
HTML dans `formulaire/` qui écrirait une couleur de palette en dur ne serait
sinon couvert par aucune garde »). La preuve que la garde est muette est dans
le dépôt : `#3B523A` est la valeur du token `--titre`
(`formulaire/style.css:13`) et il est écrit en dur dans les deux fichiers HTML.
Effet : au changement de palette d'un cabinet, la pastille « Vert » du stylet
reste au vert du cabinet précédent, sans que rien ne le signale — exactement la forme du
piège que C1-T2 a refermé, sur un chemin que la garde ne couvre pas. La tâche
n'introduit pas le défaut, mais elle **double** la duplication (second fichier
public) et la rend non corrigible, puisqu'`index-v1.html` est gelé par
empreinte : C2-T1 devra casser le gel pour y toucher.

**Propriété à rétablir :** soit la garde lit les fichiers qu'elle énumère, soit
son commentaire cesse d'affirmer une couverture qu'elle n'a pas. Une garde
verte à vide est pire qu'une garde absente.

### Faible — Rien ne protège le dépôt public des captures du jeu de référence

**Où :** `.gitignore` (aucune règle), `docs/references-visuelles/LISEZMOI.md`.

**Scénario :** les critères 1, 2 et 11 restent à exécuter par Baptiste, et le
critère 1 consiste précisément à produire `bilan-reference.json`, un PDF et
**deux captures PNG d'écran entier** — onglets, barre de favoris,
notifications. `docs/references-visuelles/` ne contient aujourd'hui que son
LISEZMOI, et aucune règle de `.gitignore` ni aucun pas d'intégration continue
ne s'opposerait à un `git add -A` qui les verserait dans un dépôt public. La
seule barrière est un humain qui relit le §4 du LISEZMOI. Le contrat le dit
déjà en §10 ; je le reprends parce que l'exécution de ces critères est
maintenant sur le chemin de la livraison.

**Propriété à rétablir :** le jeu de référence visuelle est exclu du suivi Git
par une règle, pas par une consigne.

---

## Risque résiduel des trois critères non prononçables

Les critères 1, 2 et 11 ne sont pas des manquements de l'implémenteur — ils
exigent un navigateur, une tablette et un jeu de référence qui n'existe pas. Il
faut cependant nommer ce qui reste en l'air, parce que c'est substantiel :

1. **Le repli n'a jamais été essayé par un humain.** Le favori « Formulaire —
   secours V1 » n'est, à ma connaissance, posé sur aucune tablette. Le niveau 1
   du retour arrière — la seule parade d'une minute, celle qui compte un mardi
   matin — est à ce jour une intention documentée. Aucun PDF n'est sorti
   d'`index-v1.html` et n'est arrivé sur le PC. Si le moteur défaille en
   consultation, le message dirige vers un favori dont l'existence n'est pas
   établie ; il reste l'adresse écrite dans le message, ce qui suppose de la
   saisir à la main sur une tablette, en consultation.
2. **Aucun PDF n'a été comparé.** La fidélité du rendu n'est établie que par
   comparaison de DOM, et ce comparateur ne descend pas au niveau de la feuille
   partout : les quatre images annotables n'y sont comparées que par leur `alt`
   et leurs classes (`tests/test_comparaison_dom.js:325-334`), ni `src` ni `id`
   — l'`id` émis sur les trois images `squelette_*` est d'ailleurs une
   divergence réelle avec la V1, déclarée en tolérance (b) ligne 351. J'ai
   vérifié à la main que les quatre `src` et leur ordre sont exacts, donc
   `zonesDessin` restera correctement indexé ; mais une divergence de marge ou
   de police dans les blocs 18, 20, 21, 22 et « Empreinte encre » passerait
   toute la chaîne de tests sans un mot.
3. **Conséquence :** la bascule est faite dans le dépôt, et les deux
   vérifications qui protègent la praticienne le jour J sont les deux qui
   manquent. Je ne recommande pas de commiter la bascule avant qu'elles soient
   faites.

---

## Vérifications indépendantes conduites

- **Clés de brouillon, les 52.** Rendu du vrai `schema.json` par `rendu.js`
  dans le double de DOM, extraction des clés telles que `cleChamp()`
  (`formulaire/script.js:902-907`) les calcule, et comparaison avec celles
  extraites d'`index-v1.html` : **52 contre 52, ensembles identiques et ordre
  identique**, les 8 radios de tableau sans `id` comprises (forme
  `name#value`), `date-bilan` compris puisqu'il vit dans `#form-bilan`. Aucune
  clé nulle d'aucun côté. La barre d'outils (`couleur-libre`,
  `epaisseur-trait`) reste hors de `#form-bilan` dans les deux fichiers, donc
  hors du brouillon. Le brouillon partagé tiendra.
- **Ordre des quatre images annotables.** Identique des deux côtés,
  `src` compris : `squelette_gauche`, `squelette_droite`, `squelette_dos`,
  `empreintes_pieds`. `restaurerBilan()` indexe les traits par position
  (`script.js:987-993`) : la restauration après repli replacera les traits sur
  les bonnes images.
- **Les huit chemins du dernier filet**, exécutés sur un double de DOM (cf. le
  constat élevé). Sept tiennent, le huitième ne dit rien.
- **Atomicité du rendu.** `rendre()` construit dans un `createDocumentFragment`
  et n'insère qu'au bout (`formulaire/moteur/rendu.js:533-575`) : un schéma
  refusé ou une exception de construction ne laisse **aucun** nœud dans
  `<main>`. Pas de formulaire à moitié rendu dans lequel on pourrait saisir.
  Bien fait.
- **La liste des 21 `id` est vérifiée mécaniquement**, et dans les deux sens
  (`tests/test_coquille.py:152-180`) : un `id` ajouté à la coquille sans
  réservation échoue, une réservation sans `id` correspondant échoue aussi. La
  question posée — liste figée à la main ou contrôlée — a la bonne réponse. Et
  le rendu du schéma de production réussit avec la liste élargie
  (`npm test`, scénario 1), donc aucune des 82 clés ne collisionne.
- **Suites complètes** : `python -W error::ResourceWarning -m unittest discover
  -s tests` → 81 tests, OK ; `npm test` → 8 groupes d'inventaire + 8 scénarios
  de comparaison DOM, tout vert.
- **Inversion exclusion → inclusion dans `outils/faire-paquet.sh`.** Je n'y
  trouve pas de porte ouverte : `cp -R formulaire serveur` était déjà là, les
  trois `rm` supprimés ne portaient que sur les trois chemins du moteur, et
  `formulaire/` ne contient que `images/`, `lib/`, `moteur/`, `schema.json`,
  `script.js`, `style.css` et les deux HTML. Les quatre nouvelles pièces
  obligatoires sont vérifiées **dans l'archive**, pas dans le script
  (`faire-paquet.sh:65-73`). Un seul effet de bord à savoir : la boucle
  `interdit` disparaît entièrement, donc plus rien ne contrôle qu'un fichier
  **ne** part **pas** ; le retour d'`index-moteur.html` est désormais attrapé
  au niveau du dépôt (`tests/test_coquille.py:182-191`) et non de l'archive, ce
  qui est suffisant puisque `cp -R` ne peut copier que ce qui existe.

---

## Rubriques sans constat

- **1. Données de santé.** Aucune donnée de santé ne peut sortir. Pas de
  nouvelle requête sortante : `fetch("schema.json", { credentials:
  "same-origin" })` est la seule, même origine, chemin relatif, sans paramètre.
  Pas de télémétrie, pas de page de diagnostic. `serveur/serveur.py` n'est pas
  modifié, le journal technique n'est pas touché, aucune trace n'est écrite
  dans `formulaire/`. Les trois `console.error` de `rendu.js` restent dans la
  console de la tablette et ne journalisent que l'erreur du validateur, jamais
  une valeur saisie. Sur la journalisation publique, voir les deux constats
  moyens : il ne s'agit pas de donnée de santé mais des coordonnées
  professionnelles du cabinet.
- **2. Surface exposée.** Les deux barrières tiennent, inchangées : racine web
  limitée à `formulaire/` et `EXTENSIONS_SERVIES`
  (`serveur/serveur.py:64, 428-430`) appliqué par `autorise_lecture()`, appelé
  identiquement par `do_GET` et `do_HEAD` (`:435-447`). `index-v1.html` entre
  dans la racine web avec l'extension `.html`, déjà servie — aucune extension
  n'est ajoutée. Aucune nouvelle route ; `/sante` reste la seule exception et
  n'est pas touchée. L'authentification est vérifiée **avant** le filtre
  d'extensions, et `tests/test_integration.py:232-241` couvre les deux faces
  (200 authentifié, 401 sans). Pas de remontée de chemin nouvelle : aucun
  chemin ne vient d'une requête, et le `fichier` d'une image du schéma est déjà
  contraint (relatif, sous `images/`, sans `..`, sans antislash, sans schéma
  d'URL — `tests/test_comparaison_dom.js`, scénario 5). Aucune réponse ne
  divulgue version, chemin absolu, trace d'exception ni décompte.
- **3. Authentification et cryptographie.** Sans objet : `serveur/serveur.py`
  n'est pas dans le diff. J'ai relu `authentifie()` (`:380-387`) pour
  confirmer qu'elle est intacte — comparaison sur octets UTF-8, les deux
  vérifications toujours exécutées, pas de court-circuit. Aucun secret, aucune
  clé, aucun repli en clair concerné.
- **4. Écriture de fichiers.** Sans objet : aucune écriture côté serveur n'est
  modifiée, le dépôt des PDF ne change ni de chemin ni de code.
- **5. Robustesse de service.** C'est le cœur de cette tâche, et le travail est
  sérieux : `rendre()` est atomique, `validerSchema()` et le filet
  `try/catch` empêchent toute exception de remonter, et sept chemins d'échec
  sur huit conservent le message de repli (vérifié par exécution). Deux points
  mineurs, sans constat séparé : (a) quand le moteur échoue,
  `demarrerApplication()` n'est pas appelée, donc `initFileDepots()` ne tourne
  pas et la file IndexedDB n'est pas vidangée sur cette page — elle l'est sur
  `index-v1.html`, où le message envoie, donc aucun bilan n'est perdu ; (b) sur
  ces mêmes chemins, `#btn-export` n'est pas câblé, donc le bouton ne fait rien
  du tout, ce qui vaut mieux qu'un PDF contenant le message d'attente (lequel
  ne porte pas la classe `.bloc` et ne serait pas collecté par
  `calculerPages()`). Mémoire bornée, corps de requête inchangé. Le huitième
  chemin est le constat élevé.
- **6. Côté navigateur.** Aucun `innerHTML` : le double de DOM
  (`tests/outils/dom-minimal.js`) ne l'expose pas, donc son usage ferait échouer
  la suite par construction — bonne discipline. Aucun `style=` en ligne dans
  les deux fichiers HTML (vérifié par `grep`), et le pas CSP de
  `tests.yml:148-153` couvre désormais `index.html` et `index-v1.html`.
  `#btn-export` n'a plus d'`onclick=` dans la coquille et un test l'interdit
  (`test_comparaison_dom.js:562`) ; `index-v1.html` conserve le sien, ce qui
  est normal — c'est la V1 gelée, et aucune garde ne le lui reproche. Les
  données relues de `localStorage` sont réinjectées par `.value` et `.checked`,
  jamais par `innerHTML`, et `cleChamp()` ne lit que des clés existantes du
  DOM : une clé inconnue dans le brouillon est ignorée.
- **7. Chaîne d'approvisionnement et mises à jour.** Sans objet pour la
  signature (C5 n'existe pas encore). Pour le paquet : la correction est
  **réelle et nécessaire** — l'ancienne exclusion aurait livré un formulaire
  vide au cabinet, et le contrat l'avait vu. Les quatre pièces sont vérifiées
  dans l'archive et `tests/test_paquet.py` est inversé en conséquence. Un point
  à savoir plutôt qu'un constat : `formulaire/schema.json` devient un fichier
  **livré**, donc écrasé par le prochain paquet ; toute personnalisation locale
  au cabinet serait détruite. C'est l'objet de C1-T4 (`clients/<cabinet>/`), et
  c'est écrit au contrat.
- **8. Conformité.** L'exemption d'hébergement de données de santé n'est pas
  remise en cause : rien ne quitte le PC, aucun stockage durable chez l'éditeur,
  aucun nouveau sous-traitant. Aucune aide à la décision ni indice interprété :
  le moteur rend des champs, il ne calcule rien. Durées de conservation
  inchangées. Seule réserve, hors donnée de santé : les deux constats moyens
  portent sur l'identité professionnelle du cabinet dans un dépôt et un journal
  publics.

---

## Points à surveiller plus tard

- **`index-v1.html` est gelé par empreinte.** C'est la bonne décision, et elle
  a un coût daté : C2-T1 devra soit casser le gel pour purger l'identité des
  **deux** fichiers, soit l'assumer explicitement. Le contrat le dit ; qu'il ne
  se perde pas. Même remarque pour le `#3B523A` en dur.
- **Le comparateur de DOM a un plancher.** Il descend au champ mais pas à
  l'image (ni `src`, ni `id`, cf. tolérances (a)–(i),
  `tests/test_comparaison_dom.js:340-360`). C'est documenté et argumenté, mais
  cela veut dire que la fidélité des quatre images repose entièrement sur le
  critère 11 humain. À reconsidérer en C7 si le critère 11 reste longtemps
  non prononcé.
- **La coquille dépend désormais de trois ressources** (`script.js`,
  `moteur/rendu.js`, `schema.json`) là où la V1 en demandait une. Chaque
  ressource ajoutée au chemin critique multiplie les chargements partiels
  possibles sur un Wi-Fi de cabinet. Quand C6 arrivera, un contrôle d'intégrité
  à l'ouverture (« tout est là, ou on le dit ») vaudra mieux que trois gardes
  séparées.
- **La garde d'identité est une liste fermée.** Elle le restera fausse à chaque
  tâche qui ajoute un fichier. Le constat moyen en demande l'inversion ; si
  elle n'est pas inversée maintenant, inscrire la mise à jour de `cibles` comme
  point de passage obligé de toute tâche qui touche `formulaire/` ou `tests/`.
- **`docs/audits/C1-T3b-mises-en-echec.md`** est un document d'implémenteur
  déposé dans `docs/audits/`. Hors de mon périmètre d'audit technique, mais il
  brouille la convention de la chaîne contrat → audit → revue, et il porte une
  coordonnée (constat moyen n°2).

---

# Réaudit — 2026-10-16

**Périmètre du réaudit :** l'arbre de travail après les sept corrections, contre
`664f923`. Nouveaux fichiers depuis le premier passage :
`tests/test_demarrage_moteur.js`. Fichiers nouvellement modifiés :
`formulaire/moteur/rendu.js`, `formulaire/script.js`, `package.json`,
`.github/workflows/tests.yml`, `tests/test_coquille.py`,
`docs/Mode_emploi.md`, `docs/USER-GUIDE.md`.

**Note de méthode, et mea culpa.** Mon rapport du 15 recopiait en clair
l'adresse postale du cabinet — exactement le défaut que je reprochais à
`tests/test_coquille.py` et au journal de mises en échec. La ligne a été
corrigée. Règle appliquée partout ci-dessous : **une coordonnée se désigne par
son numéro de ligne dans `formulaire/index-v1.html`, jamais par sa valeur.**
Un auditeur qui s'exempte de sa propre règle n'a plus de règle.

## État des sept constats

| Constat | Gravité initiale | État | Éprouvé par |
|---|---|---|---|
| Filet retiré sans démarrage de l'application | Élevée | **Fermé** | 11 chemins rejoués sur double de DOM |
| En-tête imprimé dans le journal public | Moyenne | **Fermé** | lecture + exécution de la suite |
| Garde d'identité en liste fermée | Moyenne | **Fermé** | garde extraite et exécutée, à vide et en morsure |
| Adresse de repli non testée | Faible | **Fermé** | `tests/test_demarrage_moteur.js` scénario 3 |
| Guides sans l'adresse | Faible | **Fermé** | relecture des deux diffs |
| Garde de palette listant des fichiers non lus | Faible | **Fermé** autrement qu'attendu, et c'est mieux | lecture du diff |
| Captures du jeu de référence non protégées | Faible | **Partiellement** fermé | lecture du pas de CI |

### Le constat élevé est fermé, et fermé à la bonne place

`formulaire/moteur/rendu.js:955-961` : `rendre()` réussit, puis
`typeof demarrerApplication !== "function"` est traité **comme un chemin
d'échec comme un autre** — `afficherErreurMoteur()` puis `return` — et le
retrait de `#attente-moteur` ne vient qu'après, aux lignes 966-968, suivi de
l'appel. L'ordre est le bon : le filet ne tombe qu'une fois l'application
réellement démarrée.

`afficherErreurMoteur()` (`:994-1003`) a désormais **deux** canaux : `annoncer()`
si `script.js` a chargé, **et** une écriture directe dans `#attente-moteur`
(`textContent` + `hidden = false`) qui ne dépend d'aucun autre fichier. Le
texte est factorisé dans `MESSAGE_REPLI` (`:899-902`) : une seule chaîne à
tenir, pas deux qui divergeraient. C'est la bonne forme de correctif.

**J'ai rejoué mes huit chemins sur le nouveau code, plus trois nouveaux**
(double de DOM indépendant de celui du test de l'implémenteur, pour ne pas
valider un correctif avec l'outil qui l'accompagne) :

| Chemin | `#attente-moteur` | Texte final | Message nommant favori + adresse |
|---|---|---|---|
| a) `schema.json` 404 | présent, non masqué | `MESSAGE_REPLI` | oui (DOM + bandeau) |
| b) 401 | présent, non masqué | `MESSAGE_REPLI` | oui |
| c) schéma refusé | présent, non masqué | `MESSAGE_REPLI` | oui |
| d) `fetch` rejeté | présent, non masqué | `MESSAGE_REPLI` | oui |
| e) `#form-bilan` absent | présent, non masqué | `MESSAGE_REPLI` | oui |
| f) `<main>` absent | présent, non masqué | `MESSAGE_REPLI` | oui |
| g) JSON illisible | présent, non masqué | `MESSAGE_REPLI` | oui |
| **h) `script.js` absent, schéma valide** | **présent, non masqué** | **`MESSAGE_REPLI`** | **oui, par le DOM seul** |
| i) `script.js` absent **et** `#form-bilan` absent | inexistant | — | **non** |
| j) `script.js` absent **et** `<main>` absent | inexistant | — | **non** |
| k) `demarrerApplication()` lève | déjà retiré | — | oui, par le bandeau |

Le chemin (h) — celui du constat — est fermé, et il est fermé **sans**
`annoncer`, c'est-à-dire précisément dans le cas où `script.js` est le fichier
manquant. C'était la question posée : le correctif ne déplace pas le trou, il
le bouche.

### Réponses aux quatre questions du réaudit

**1. Le correctif a-t-il déplacé le problème ? Un neuvième chemin ?**
Oui, il en existe un — chemins (i) et (j) ci-dessus — et il fait l'objet du
seul constat nouveau, ci-dessous. Il n'est pas de la même nature que le
constat élevé : il ne produit pas un formulaire d'apparence normale, il
produit une page manifestement vide. Le chemin (k) mérite une ligne : si
`demarrerApplication()` lève après le retrait du filet (par exemple
`initDessin()` sur une tablette capricieuse), `#attente-moteur` a déjà disparu
et seul le bandeau `annoncer()` porte le message — ce qui est exactement
suffisant, puisque dans ce cas `script.js` a nécessairement chargé. Et
`applicationDemarree` est déjà passé à `true` (`formulaire/script.js:789-790`)
avant la levée : l'application reste à moitié démarrée, mais le bandeau est
persistant et dirige vers le repli. Rien à corriger.

**2. La garde d'identité élargie mord-elle, et sera-t-elle vivable ?**
Elle mord. J'ai extrait le pas de `.github/workflows/tests.yml` et je l'ai
exécuté deux fois :

- tel quel : `Aucune coordonnée du cabinet recopiée.`, sortie 0 — donc le
  journal de mises en échec a bien été purgé, et mon propre rapport aussi ;
- avec la seule exclusion neutralisée : sortie 1, et le message
  `::error::Coordonnée du cabinet recopiée, voir formulaire/index.html
  ligne(s) 90-96, dans : formulaire/index-v1.html formulaire/index.html`.
  Elle attrape bien la copie gelée dès qu'on cesse de l'excuser, **et son
  message ne cite qu'un fichier et une plage de lignes source** — jamais une
  valeur. C'est la propriété que le §10 exige, et elle est maintenant tenue des
  deux côtés : par la garde et par le test.

Elle balaie tous les fichiers suivis par `git ls-files -z`, avec `grep -I`
contre les binaires et un `break` dès la première correspondance ; la seule
exclusion est `^formulaire/index(-v1)?\.html$`, justifiée en commentaire et
adossée à l'empreinte SHA-256 d'`index-v1.html`. Le piège documenté dans
`CLAUDE.md` (`git ls-files` sans `-z`, et `xargs -0 grep` indistinguable d'une
erreur) est évité explicitement. Sur le bruit : elle est verte aujourd'hui, et
tout faux positif serait un document qui recopie réellement une coordonnée —
donc un vrai positif. Un seul cas la rendrait pénible : un document
d'intégration de client (C9) qui citerait légitimement l'identité du cabinet.
Le jour venu, il faudra une exclusion justifiée de plus, pas la désactivation
du pas. Noté ci-dessous.

**3. La comparaison par empreintes a-t-elle perdu en précision ?**
Un peu, et c'est acceptable. `tests/test_coquille.py:128-144` compare deux
SHA-256 de l'en-tête normalisé : en cas d'écart, `unittest` n'imprime que deux
condensats hexadécimaux, et le message explique pourquoi le contenu n'est pas
affiché. Ce qu'on perd : le développeur ne lit plus **où** l'en-tête a dérivé.
Ce que ça coûte : un `diff` local entre deux fichiers du même dépôt, long de
treize lignes. L'échange est bon. Si le test devenait pénible, la bonne
évolution serait de nommer les **numéros de ligne** divergents, pas de
revenir au texte.

**4. Dépendance nouvelle ? Contenu dans un journal public ?**
Aucune dépendance nouvelle : `tests/test_demarrage_moteur.js` n'utilise que
`fs`, `path`, `vm` et `assert`, pas de `jsdom`, et porte son propre double de
DOM — une duplication avec `tests/outils/dom-minimal.js`, assumée et expliquée
en tête de fichier par une raison juste (le double partagé n'expose
délibérément ni `getElementById`, ni `querySelector`, ni `remove()`, que
`demarrerMoteur()` a besoin d'utiliser et que `rendre()` n'a pas le droit
d'utiliser). `package.json` l'ajoute à `npm test`, et
`.github/workflows/tests.yml:56-57` en fait un pas de CI à part entière : le
test ne peut pas être oublié.

Sur les journaux publics, j'ai relu chaque chemin d'échec nouveau :
`test_demarrage_moteur.js` imprime au pire `MESSAGE_REPLI` (texte de
l'éditeur, aucune donnée du cabinet), `test_coquille.py` deux condensats et des
`id` d'interface, `test_paquet.py` des noms de membres d'archive, le pas
`references-visuelles` un simple rappel sans nom de fichier. **Aucun chemin ne
cite de contenu de fichier, de coordonnée ni de libellé clinique.**

## Constats du réaudit

### Faible (nouveau) — Aucun canal d'erreur quand l'ancre du filet manque elle-même

**Où :** `formulaire/moteur/rendu.js:994-1003` (`afficherErreurMoteur()`),
`formulaire/index.html:108-112` (`#attente-moteur` vit **dans**
`#form-bilan > main`).

**Scénario :** entrée — `formulaire/script.js` absent ou tronqué **et**
`#form-bilan` ou son `<main>` introuvable (coquille écrasée par une
installation partielle, fichier tronqué au déploiement, ou un futur
remaniement de la coquille). État : les deux canaux d'`afficherErreurMoteur()`
tombent en même temps — `annoncer` est indéfinie puisqu'elle vient de
`script.js`, et `#attente-moteur` n'existe pas puisqu'il vit à l'intérieur de
l'ancre manquante. Effet : chemins (i) et (j) de mon tableau, **silence
complet**, aucun message d'aucune sorte.

Pourquoi ce n'est que faible, et pourquoi je le consigne quand même : dans cet
état la page est manifestement vide — aucun bloc, aucun champ —, donc l'échec
est visible même sans message, et ce n'est pas le cas trompeur du constat
élevé. Mais le principe affiché en toutes lettres dans le fichier (« le silence
n'est jamais une réponse acceptable ») a ici une exception non écrite, et c'est
le seul endroit du dernier filet qui ne survit pas à la perte de son point
d'ancrage.

**Propriété à rétablir :** le dernier filet ne doit pas dépendre d'un nœud
situé à l'intérieur de ce qu'il surveille. Un point d'écriture hors de
`#form-bilan` — `#zone-messages` existe déjà et vit avant lui
(`formulaire/index.html:67`) — rendrait le canal indépendant des deux pannes à
la fois. Deux lignes ; pas urgent, mais à ne pas perdre.

### Faible (reclassé « partiellement fermé ») — Le rappel sur les captures arrive après le commit, pas avant

**Où :** `.github/workflows/tests.yml:83-95`.

Le pas est honnête sur ce qu'il est — « ce pas ne bloque rien, il rappelle fort
» — et le choix de ne pas refuser tout fichier image est juste, puisque ces
fichiers devront un jour être versionnés. Mais il repose sur
`git ls-files docs/references-visuelles` : une capture n'y apparaît qu'une fois
**indexée**, donc le rappel ne peut s'afficher qu'après le `commit`, et dans la
pratique après le `push` qui déclenche la CI. Or le risque nommé au §10 du
contrat est irréversible : « une donnée publiée ne se reprend pas, l'historique
Git la conserve ». Le pas transforme donc une fuite silencieuse en fuite
signalée — c'est un progrès réel, ce n'est pas une barrière.

**Propriété à rétablir :** la barrière doit précéder l'acte irréversible. Une
règle `.gitignore` sur `docs/references-visuelles/*.png` et `*.pdf`, levée
sciemment par `git add -f` le jour où les captures ont été relues, place la
décision avant le commit et non après. Le rappel de CI garde alors tout son
sens comme seconde ligne.

## Vérifications d'exécution du réaudit

- `python -W error::ResourceWarning -m unittest discover -s tests` → **81
  tests, OK**.
- `node tests/test_file_depots.js`, `test_palette.js`,
  `test_inventaire_formulaire.js`, `test_comparaison_dom.js`,
  `test_demarrage_moteur.js` → **les cinq verts**, le dernier sur ses trois
  scénarios (nominal, `script.js` absent, schéma refusé).
- Pas d'identité de `tests.yml` extrait et exécuté : vert à l'état réel,
  rouge avec la seule exclusion neutralisée, message sans coordonnée.
- Onze chemins d'échec de `demarrerMoteur()` rejoués sur mon propre double de
  DOM (tableau ci-dessus).
- `formulaire/script.js:792-799` : le commentaire périmé est corrigé et dit
  juste — c'est `index-v1.html` qui porte l'`onclick=`, et la coquille qui
  porte `data-moteur`. Le câblage conditionnel est inchangé : pas de double
  déclenchement de `exporterBilanPDF()`.
- Aucun des constats fermés ne l'a été au prix d'un autre : ni
  `serveur/serveur.py`, ni `EXTENSIONS_SERVIES`, ni le périmètre de la racine
  web, ni les clés de brouillon n'ont bougé depuis le premier passage. Les 52
  clés et l'ordre des quatre images annotables, vérifiés le 15, ne sont
  touchés par aucune des sept corrections.

## Risque résiduel — inchangé, et c'est la réserve

Je le redis mot pour mot, parce qu'il n'a pas bougé d'un pouce et qu'il est
maintenant la **seule** raison pour laquelle le verdict n'est pas « conforme »
tout court :

**La bascule est faite dans le dépôt, le favori « Formulaire — secours V1 »
n'a jamais été ouvert par un humain, et aucun PDF n'a été comparé.**

- Critère 2 : le niveau 1 du retour arrière — la seule parade d'une minute,
  celle qui compte un mardi matin — reste une intention documentée. Le code le
  secourt mieux qu'hier (les guides et les deux messages donnent désormais
  l'adresse à défaut du favori), mais personne n'a posé le favori, ouvert la
  fiche de secours, saisi un bilan et vérifié qu'un PDF arrive sur le PC.
- Critère 11 : la fidélité du rendu reste établie par comparaison de DOM
  seulement, et ce comparateur ne descend pas au niveau de la feuille pour les
  images. Une divergence de marge ou de police dans les blocs 18, 20, 21, 22 et
  « Empreinte encre » traverserait toute la chaîne sans un mot.
- Critère 1 : le jeu de référence visuelle n'existe pas, donc le critère 11 est
  structurellement non prononçable tant qu'il n'est pas produit — et sa
  production est elle-même le seul chemin par lequel une donnée réelle pourrait
  entrer dans ce dépôt public (voir le faible partiellement fermé ci-dessus).

**Ma recommandation est inchangée : ne pas commiter la bascule avant que les
critères 1, 2 et 11 soient prononcés.** Le travail d'implémentation, lui, n'a
plus rien qui s'y oppose.

## Points à surveiller plus tard (ajouts du réaudit)

- **La garde d'identité attrape des lignes entières.** Elle compare par
  `grep -F` les lignes de texte extraites de l'ancre. Une recopie **partielle**
  — le nom sans la qualification qui le suit sur la même ligne — passerait.
  C'est une limite du mécanisme, pas une régression ; à savoir avant de s'y
  fier comme à une preuve.
- **La première exclusion justifiée fera jurisprudence.** Le jour où un
  document d'intégration client (C9) devra citer l'identité d'un cabinet, la
  tentation sera de désactiver le pas plutôt que d'ajouter une exclusion
  motivée. Que la ligne `exclus=` reste une liste courte et commentée.
- **Deux doubles de DOM cohabitent** (`tests/outils/dom-minimal.js` et celui de
  `tests/test_demarrage_moteur.js`). La justification est bonne aujourd'hui ;
  elle deviendra fausse si le second se met à servir aussi à tester `rendre()`,
  puisqu'il expose ce que le premier interdit volontairement. À reprendre en
  C7 si un troisième apparaît.
- **La pastille « Vert » du stylet reste une couleur de palette en dur** dans
  les deux fichiers HTML, et la garde de palette ne le couvre pas — elle ne
  prétend plus le couvrir, ce qui est le vrai progrès. Il faudra une tâche
  dédiée, et elle devra toucher `index-v1.html`, donc casser le gel
  d'empreinte : à faire pendant C2-T1, pas après.
