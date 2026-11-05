# Session du 5 novembre 2026 (2) — Fiabiliser l'outillage et les gardes de la grille

**Durée approximative :** une demi-journée.
**Tâche concernée :** C1-T6b.
**Branche :** `c1-t6b-outillage`, tirée de `c1-t6-grille`. **Commits :** de
`4e44302` à `7027743`, quatorze en tout ; tous poussés sauf `4156217` et
`7027743` (rapports d'audit et de revue). **Ni `c1-t6-grille` ni
`c1-t6b-outillage` ne sont fusionnées** : `main` est toujours à `1ec796c`.

## Ce qui a été fait

**C1-T6b — les suites de C1-T6, fermées avant le premier schéma client à grille.**
Contrat, implémentation, audit, correction, réaudit, revue, correction,
réaudit : **À LIVRER**, critères 1 à 27 et 21b vérifiés.

- **`cdp.js` ne pilote plus qu'un Chrome qu'il a lancé.** Tout port qui ne
  refuse pas la connexion est déclaré occupé, y compris un service qui accepte
  sans jamais répondre (constat de l'audit). La sonde passe en tête, avant la
  vérification de Chrome et la création du profil : le refus se teste sous
  Linux et Windows (`tests/test_cdp.js`, 5 cas). Le bilan témoin ne peut plus
  sortir en 6 pages au lieu de 3 sans que personne ne le voie.
- **La CI joue le cas qu'elle sautait.** Le job `test` clone tout l'historique
  (`fetch-depth: 0`), et `test_export_grille.js` **échoue** si le commit de
  repère manque alors que `CI` est posé. Effet de bord bienvenu : deux
  vérifications de `test_licence.py` jouent pour la première fois en CI, vertes
  partout.
- **La garde de confidentialité regarde tout ce qui part sur GitHub.** Outre
  l'état final des fichiers : les messages de commit, les noms de branche et
  d'étiquette, les `src`/`href` de la fiche (365 marqueurs au lieu de 352), et
  — ajouté après l'audit — **chaque blob introduit dans la plage**, y compris
  un fichier commité puis retiré avant la poussée. Deux exemptions seulement,
  ancrées sur (SHA, ligne), toutes deux sur le même marqueur fortuit de
  8 caractères ; un test fait échouer celle qui deviendrait sans objet. Les
  échecs ne nomment jamais un marqueur. Gardes anti-vacuité : décompte
  confronté à un second comptage, tout `git` en échec lève.
- **La hauteur d'une grille est mesurée.** `essai-grille.js`, mode `mesure`,
  compare chaque grille à la hauteur de page, constantes lues dans la page. Sur
  la donnée fictive, **une grille de 20 lignes tient sur une page à partir de
  735 px de fenêtre**. La condition 2 de livraison se joue désormais aussi à la
  largeur de la tablette du client. Constat :
  `docs/references-visuelles/CONSTAT-2026-11-05-C1-T6b.md`.

`formulaire/`, `serveur/` et `CLAUDE.md` intacts pendant toute la tâche :
rien ne change au cabinet.

## Décisions prises

| Décision | Raison | Conséquence |
|---|---|---|
| **Pas de crochet Git** pour les messages de commit (DB1-A) | Un crochet ne s'active pas tout seul ; un seul développeur ; la garde ne joue que sur le poste à la fiche | La garde vit dans `npm test` ; un message fautif non poussé se corrige par `--amend` |
| **Grille plus haute qu'une page : documenter et borner en atelier** (DB2-A) | La hauteur admissible dépend de la tablette ; toucher `calculerPages()` engage la fiche de secours ; refuser l'export bloquerait une consultation | `script.js` intact ; épreuve à la largeur du client |
| **Process monté à Allégé + audit** | Garde d'un dépôt public : une fuite poussée est irréversible | Audit, deux réaudits |
| **Corriger dans la tâche la garde aveugle à l'historique** | Un texte commité puis retiré resterait public | Lecture de tous les blobs, seconde exemption autorisée par Baptiste |
| **Garder les résidus hors dépôt** (copie du 3 novembre, script d'audit du 4) | Dossiers temporaires, rien de public | Notés comme acceptés |
| **Enchaîner la chaîne sans proposer l'étape suivante** | Demande de Baptiste | Mémoire `enchainer-chaine-taches` |
| **Écarter une remarque mineure de revue** (double lecture dans `essai-grille.js`) | Pas de bug ; y toucher oblige à refaire les mesures dans Chrome | Laissée |

## État des tests

**Avant :** 226 tests Python et 11 suites Node (sur `c1-t6-grille`).
**Après :** **241 tests Python** (2 sautés), verts sous `python3` et `-O` ;
**12 suites Node** (compte fait dans `package.json`), dont `test_cdp.js`
(5 cas). Les comptes rendus de l'implémenteur et du réviseur disaient 11 :
ils reprenaient l'ancien chiffre.
- `ReperageHorsFichiers` : fonctions pures de la garde, jouées **en CI** sans
  la fiche.
- Mutations a à o consignées dans `docs/audits/C1-T6b-mises-en-echec.md`, dont
  une vingtaine de clones jetables sans `origin`, tous supprimés.

**CI :** 42103090760, 42108356730 et 42111426184, vertes sur 7 jobs sur 7,
macOS compris.

**Durée de la garde :** 25 s après l'ajout des blobs, 3,6 s après la revue
(la normalisation du texte était refaite pour chacun des 365 marqueurs).

## Constats de sécurité

- **Audit initial : CONFORME SOUS RÉSERVE.** Moyenne : la garde ne voyait pas
  l'historique (un blob déjà poussé portait le marqueur fortuit, rien de
  nouveau n'avait fui). Faible : un port muet déclaré libre. Faible : résidus
  hors dépôt.
- **Réaudit : CONFORME.** Les 71 blobs de la plage recomptés par un autre
  chemin ; aucune trace des mutations dans le dépôt ni sur `origin`.
- **Réaudit après revue : CONFORME.** L'optimisation rend exactement les mêmes
  résultats, cas factices compris (ligne à cheval, Unicode).
- **Hors garde, à surveiller :** les messages d'étiquettes annotées ; une image
  de la fiche commitée en binaire (aucune ne l'est aujourd'hui, vérifié par
  empreinte).

## Ce qui reste en suspens

- **Fusion de `c1-t6-grille` puis `c1-t6b-outillage` sur `main`**, et poussée
  des deux derniers commits : décision de Baptiste. **Une fusion qui réécrit
  l'historique** (squash, rebase) rendrait les deux exemptions sans objet :
  `test_exemptions_toujours_justifiees` le dira, il faudra alors les retirer.
- **Le schéma du prospect :** ses grilles hautes devront être scindées en
  plusieurs blocs, ou les tablettes sous ~735 px de fenêtre écartées.
- **Hérité :** favori de secours au cabinet pilote (bloque C1-T4), essai de
  C3-T3a sur VM Windows, questions au formateur, annonce de la purge de
  `journal.log`.

## Prochaine étape recommandée

Décider la fusion des deux branches sur `main`. Ensuite, le schéma du
prospect peut être écrit.

## À savoir pour la prochaine session

- **`python3 -O` lancé en arrière-plan par `(… &)` dans un shell non
  interactif ignore SIGINT** : `ServeurArret.test_arret_journalise` y échoue à
  chaque fois. Ce n'est pas un défaut du serveur : jouer la suite `-O` au
  premier plan. L'implémenteur l'avait d'abord pris pour un test instable.
- **Une garde peut être juste et lente.** La normalisation recalculée dans un
  `any(...)` coûtait 15 s ; un réaudit a prouvé que la sortir de la boucle ne
  changeait aucun résultat, ce qui est le seul moyen honnête d'optimiser une
  garde.
- **Un clone `file://` a pour `origin` le dépôt réel** : une poussée depuis un
  clone jetable y déposerait la mutation. `git remote remove origin`, puis
  `remote | wc -l` → 0, avant toute mutation.
- **L'ancien `cdp.js`, rejoué en mutation, lance de vrais Chrome qui
  survivent au test** : les chercher par `pgrep -fl profil-chrome-` après coup.
  Environ 119 profils `profil-chrome-*` traînent dans `$TMPDIR`.
- **Mesurer avant de trancher a payé** : la largeur seuil de 735 px a donné à
  DB2 un fondement chiffré, et dit tout de suite ce que le schéma du prospect
  devra faire.
