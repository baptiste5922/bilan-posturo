# Session du 14 octobre 2026 — Licence BUSL et palette unifiée

**Durée approximative :** une longue séance
**Tâches concernées :** C0-T1 (livrée), C1-T2 (livrée sous réserve), C7-T5 (ouverte)
**Branche :** `main`  **Commits :** `ea17f75` → `c510195`, quatorze commits

## Ce qui a été fait

### D'abord, sauver ce qui n'existait que sur un disque

La session s'ouvre sur un constat qui n'était pas à l'ordre du jour : le dernier
commit datait du 26 août, et **la totalité de la V1 décrite par `CLAUDE.md`
n'était pas versionnée**. Huit cent cinquante lignes dans l'arbre de travail —
la file d'attente IndexedDB, la rotation du journal, la sonde `/sante`,
l'intégration continue multiplateforme, les quatre documents du cabinet
réécrits — et cinq fichiers non suivis, dont `CLAUDE.md` et `docs/ROADMAP.md`
eux-mêmes. Pour un logiciel utilisé chaque jour en consultation, dont la
contrainte affichée est de prévoir le retour arrière, c'était le risque le plus
grand du dépôt, très loin devant les suivants.

Sept commits thématiques régularisent l'ensemble, du `.gitignore` qui protège
`docs/projection.md` jusqu'à la feuille de route. La CI a tourné pour la
première fois sur ce code : verte sur les trois systèmes, Python 3.9 et 3.13,
plus les deux travaux qui n'avaient jamais été exercés — les sept scénarios
Node et l'analyse de syntaxe PowerShell sous Windows.

### C0-T1 — la licence

Le dépôt est public, et chaque semaine de développement sous MIT agrandissait la
base qu'un concurrent pouvait reprendre et revendre. La décision est prise :
**source-available non concurrentielle**, et l'arbitrage qui restait ouvert a été
instruit par le contrat. **BUSL 1.1** l'emporte sur PolyForm Noncommercial pour
une raison concrète : une pédicure-podologue libérale qui facture ses bilans fait
un usage *commercial*, donc la licence publique de PolyForm n'aurait accordé
aucun droit au marché cible, et le cabinet déjà installé n'aurait plus pu
recevoir de mise à jour avant la rédaction d'une licence commerciale séparée —
une tâche juridique non commencée. L'`Additional Use Grant` de BUSL le met en
règle le jour même, sans signature.

Le commit frontière `9339ee9` est étiqueté `frontiere-mit` et poussé : tout ce
qui le précède reste MIT à jamais. Les dix-sept critères d'acceptation sont
vérifiés.

Le cadrage a trouvé un défaut que personne ne cherchait : `outils/faire-paquet.sh`
**n'embarquait aucun texte de licence** dans l'archive livrée au cabinet.
Négligent sous MIT, c'est une non-conformité à sa propre licence sous BUSL, qui
exige son `Notice` sur chaque copie. Le script a été corrigé — et l'audit a
montré qu'il lui manquait aussi `set -e`, si bien qu'une copie en échec le
laissait zipper puis annoncer « Archive créée » sur un paquet amputé.

### C1-T2 — la palette

Les couleurs du cabinet étaient écrites à trois endroits : `style.css`, trois
constantes de `script.js`, et un style en ligne dans `index.html`. Cinq tokens
sur `:root` deviennent la source unique, trente-six littéraux passent en
`var()`, et le générateur de PDF lit les tokens **à chaque génération** plutôt
qu'au chargement du module.

Ce choix n'est pas esthétique, il est contraint : le contexte `vm` des tests de
la file d'attente ne fournit ni `getComputedStyle` ni `document`, donc un appel
au niveau module aurait cassé les sept scénarios existants ; et C1-T3 appliquera
le thème à un instant qui n'est pas garanti antérieur au chargement de
`script.js`.

Seules les couleurs qui varient d'un cabinet à l'autre sont des tokens. Les
couleurs d'état, les neutres, les ombres et les encres de stylet restent
littérales : un thème ne doit pas pouvoir rendre un message d'erreur illisible,
et chaque token est une ligne que C9 devra renseigner chez chaque client.
`#3B523A` servait à la fois de vert de titre et d'encre verte : seul le premier
usage est thématisé.

Quinze des dix-huit critères sont vérifiés, **dont les deux qui décidaient de la
tâche**, confirmés en navigateur en fin de séance.

## Décisions prises

| Décision | Raison | Conséquence |
|---|---|---|
| BUSL 1.1, `Change License` MIT, `Change Date` à quatre ans | Les deux candidates arrêtent le concurrent, mais seule BUSL laisse un cabinet payant en règle sans licence commerciale séparée | C0-T2 rédige l'abonnement, pas un préalable juridique bloquant |
| Dépôt maintenu **public** | L'auditabilité *est* l'argument local-first : un cabinet doit pouvoir vérifier lui-même que rien ne sort | Fermer le dépôt était écarté d'emblée |
| Commit frontière = `9339ee9` | C'est `HEAD` au moment de la bascule, déjà poussé donc déjà irrévocablement MIT | Étiquette `frontiere-mit` poussée, nommée dans trois fichiers |
| Aucun en-tête de licence par fichier | Le dépôt n'en a jamais eu, ni BUSL ni PolyForm ne l'exigent | Décision écrite pour ne pas être rouverte à chaque fichier du moteur C1 |
| Cinq tokens, pas trois ni vingt | Seules les couleurs qui varient d'un cabinet à l'autre méritent un token ; `#A39B8B` apparaît douze fois en bordures et est manifestement teinté | Deux tokens au-delà du critère littéral de la feuille de route |
| Fond de dernier recours **blanc** | Le blanc n'est pas une couleur de palette mais un neutre ; entre un bilan illisible et un bilan neutre, pour une pièce qui part dans un dossier patient, la lisibilité primait | Écart assumé à la lettre du contrat, documenté en commentaire |
| Références visuelles versionnées dans le dépôt | Hors Git, elles seraient introuvables quand C1-T3 en aura besoin | Six fichiers à produire, patient fictif obligatoire |
| Ne pas produire de captures sans navigateur | Un faux témoignage sur un contrôle visuel ferait croire la chose vérifiée pour toujours | Procédure écrite plutôt que verdict fabriqué |
| Ne pas diagnostiquer l'instabilité Windows | Hors sujet de la tâche, et un aléa TLS Windows ne se diagnostique pas depuis macOS en passant | C7-T5 ouverte avec le constat complet |

## État des tests

Avant la session : 57 tests Python et 7 scénarios Node, verts mais **non
versionnés**. Après : **67 tests Python** (dix nouveaux sur la licence),
**7 scénarios** sur la file d'attente, **8 groupes de cas** sur la conversion de
couleur. `npm test` enchaîne les trois et sort 0. `pyflakes` propre.

Trois garde-fous d'intégration continue sont nouveaux : les tests Node, la
syntaxe PowerShell sous Windows, et deux contrôles de contenu — « aucune mention
de licence contradictoire » et « palette non dupliquée », ce dernier refusant
aussi les styles en ligne dans `index.html`.

La couverture reste absente sur `calculerPages()` (C7-T1) et sur le rendu.

## Constats de sécurité

Les deux audits ont rendu **CONFORME SOUS RÉSERVE**, sans aucun constat critique
ni élevé. Deux trouvailles valaient à elles seules la séance.

**C0-T1 — le filet de tests serait tombé au rouge dès la pousse.** Un test
vérifiait l'existence du dossier `.git` et non celle de l'objet Git. Or
`actions/checkout` clone à la profondeur 1 : le dossier existe, l'objet
`9339ee9` disparaît dès que `main` avance. `check=True` en aurait fait une
exception sur les cinq combinaisons de la matrice, en permanence. Corrigé par un
garde sur la disponibilité de l'objet, et un second sur le caractère superficiel
du clone — où la date de commit est celle de `HEAD` et ne veut rien dire.

**C1-T2 — le repli pouvait remettre un bilan noir au patient.** Si `style.css`
n'est pas chargée, le repli lit le fond résolu du corps du document, et le
navigateur répond `rgba(0, 0, 0, 0)`. La garde empêchait bien le remplissage
jsPDF, mais la chaîne continuait vers html2canvas et `ctx.fillStyle` : canevas
transparent, aplati sur du noir par le JPEG, bilan illisible annoncé comme
réussi. **C'était une régression par rapport à la V1**, dont le littéral en dur
sortait un PDF lisible dans ce même état. Le contrat affirmait « conséquence :
aucune » pour ce chemin — il avait tort.

Autres constats corrigés : le contrôle anti-mention-MIT était aveugle aux noms
de fichiers accentués (`git ls-files` les échappe à la façon du C, et un
`|| true` avalait l'erreur) dans un dépôt dont tous les documents portent des
noms français ; l'exclusion `^TIERS\.md` non ancrée à droite laissait passer un
`TIERS.md.bak` ; le français de `docs/licence.md` interdisait la redistribution
que le texte anglais autorise hors production ; et la procédure de contrôle
visuel ne faisait relire que les PDF et le JSON, pas les quatre captures PNG —
le seul chemin par lequel une donnée de santé pourrait entrer dans ce dépôt
public.

Reporté hors périmètre : **C7-T5**. Rien n'a été écarté d'important.

## Ce qui reste en suspens

- **Les six fichiers de référence visuelle** (C1-T2, sections 1 à 3 et 5 du
  `LISEZMOI.md`). Ne conditionnent plus la validité de C1-T2. *Pour débloquer :*
  trente minutes dans un navigateur, sur un patient fictif. Autant les produire
  au moment de C1-T3, avec un bilan choisi pour éprouver la pagination.
- **La relecture juridique** de l'`Additional Use Grant` — notamment ce que
  recouvre « a single healthcare practice » pour un cabinet de groupe, qui est la
  frontière du palier V4. *Pour débloquer :* une séance de conseil en propriété
  intellectuelle, à grouper avec C0-T2. Ne bloque rien : une licence se corrige
  vers l'avant.
- **C7-T5**, l'instabilité de `ServeurEnMarche` sous Windows et Python 3.9.
  *Pour débloquer :* rendre déterministe l'attente de disponibilité du serveur
  de test — poignée de main TLS complète plutôt que connexion TCP.
- **`.claude/` n'est pas versionné** (`.gitignore:28`). Les quatre agents et les
  quatre compétences sur lesquels repose toute la méthode de travail n'existent
  que sur ce disque — le même risque que celui soldé en début de séance, un cran
  plus haut. *Pour débloquer :* une décision, puisque c'est un choix et non un
  oubli.

## Prochaine étape recommandée

`/lancer-tache C1-T1` — l'inventaire du formulaire et le vocabulaire de schéma.
C'est le chemin critique du produit : la fondation de C1-T3, la tâche la plus
lourde du projet, que la feuille de route interdit de démarrer avant que C1-T1
soit relu. Le contrat de C1-T2 a déjà repéré une dette qui l'attend : `.json`
n'est pas dans `EXTENSIONS_SERVIES` (`serveur/serveur.py:61`), donc
`schema.json` ne pourrait même pas être servi en l'état.

## À savoir pour la prochaine session

**Un contrôle qui lit l'index Git doit être éprouvé sur des fichiers indexés.**
Le contrôle anti-mention-MIT a été validé alors que les documents de la chaîne
n'étaient pas encore suivis : `git ls-files` ne les voyait pas. Commités au
commit suivant, ils ont fait échouer six travaux d'intégration continue. Deux
minutes de rouge sur `main`, et la leçon vaut pour tout contrôle bâti sur
`git ls-files`.

**`xargs -0 grep` ne permet pas de distinguer « rien trouvé » d'une erreur
réelle** : il rend 123 dans les deux cas. Toute tentative de différencier les
deux codes de sortie à travers `xargs` est perdue d'avance — il faut une boucle.

**`git ls-files` sans `-z` échappe les chemins non ASCII** et les entoure de
guillemets. Dans ce dépôt où tous les documents portent des noms français, c'est
un trou béant dans n'importe quel contrôle de contenu.

**Mesurer un code de sortie à travers un tube donne celui du dernier maillon.**
J'ai cru un garde-fou défaillant parce que je lisais le code de `tail` et non
celui du script. Mesuré correctement, il était juste.

**`actions/checkout` clone à la profondeur 1.** Tout test qui interroge un
commit autre que `HEAD` doit vérifier la disponibilité de l'objet, pas
l'existence de `.git`. Et dans un clone superficiel, `git log -1 -- <fichier>`
rend la date de `HEAD` : une mesure de date tirée de l'historique y est
silencieusement fausse.

**Forcer un token par la console est un meilleur test qu'éditer `style.css`.**
`document.documentElement.style.setProperty('--fond', '#ff00ff')` ne touche
aucun fichier, donc rien à rétablir ; et comme il n'y a pas de rechargement, le
test prouve en plus que les couleurs sont lues au moment de la génération et non
au chargement du module. C'est ainsi que les deux critères de thème ont été
validés.

**Un test instable est pire qu'un test absent.** Les dix tests de
`ServeurEnMarche` ont échoué sur la seule combinaison Windows et Python 3.9, et
une relance sans aucune modification de code est repassée au vert. On prend
l'habitude de relancer, et le jour où l'échec est réel, on relance aussi. D'où
C7-T5, ouverte plutôt que classée.

**Les relais perdent des constats.** L'audit de C1-T2 comptait cinq constats, je
n'en ai transmis que quatre à l'implémenteur ; c'est la revue indépendante qui a
rattrapé le cinquième — la lecture des couleurs hors du `try`, donc un échec
silencieux sans message à la praticienne. La séparation des trois rôles n'est
pas une formalité : elle a servi deux fois sur deux tâches.
