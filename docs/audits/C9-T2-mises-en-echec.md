# C9-T2 — journal des mises en échec

**Date :** 7 novembre 2026
**Branche :** `c9-t2-atelier`, depuis `6cfe897` (contrat commité)
**Règle :** un garde-fou non mis en échec ne garde rien (`CLAUDE.md`). Chaque
mutation a son **témoin** (la même commande sur l'arbre sain) et le **code de
retour du test lui-même**, lu sur la dernière ligne de sa sortie.

## Méthode

- Chaque mutation se joue dans un **clone jetable** du dépôt, hors du dépôt
  (`git clone`, puis `git remote remove origin` : un clone qui garde son `origin`
  pousserait dans le dépôt réel). Un clone ne contient que les fichiers suivis
  et commités : ni `config.json`, ni clé, ni journal, ni dossier des bilans.
  L'arbre de travail réel n'a reçu aucune mutation ; la restauration est le
  `git checkout`/réécriture du fichier d'origine dans le clone, puis un rejeu.
- Le script de mutation (`mutations.py`) est **hors dépôt**. Il refuse une
  mutation sans effet (le motif doit se trouver le nombre de fois attendu, une
  fois, deux pour M9), joue `node tests/test_atelier.js`, relève les lignes
  `ECHEC -`, puis **réécrit le fichier d'origine** avant la suivante. Il joue le
  témoin avant la première mutation et rejoue la suite saine après la dernière.
- Le test se juge sur son **code de sortie** (0 / 1) et sur les noms de cas en
  échec, jamais sur un `$?` lu après autre chose.
- **Avant le code** : les cas T1 à T9 échouent trivialement sur le dépôt d'avant
  la tâche (`outils/atelier/atelier.js` n'existe pas : `require` lève). Les
  mutations ci-dessous prouvent que chaque cas **mord** une fois l'outil écrit.
- Les cas de confinement (M1) se jouent dans des **racines jetables** passées par
  `options.racineDepot` : aucune garde d'écriture n'est éprouvée dans le dépôt
  réel (un `finally` ne protège pas d'une interruption). La racine réelle n'est
  éprouvée qu'en lecture, par `refusConfinement`, et à la main par la commande A6.

## Mutations

Témoin : `node tests/test_atelier.js` dans le clone sain → code 0,
« Tout est vert. » (32 cas). Chaque mutation → code 1. Après restauration → code 0.

| N° | Garde visée | Mutation (clone jetable) | Cas qui rougissent | Retour au vert |
|---|---|---|---|---|
| M1 | Confinement hors du dépôt | `refusConfinement` : `if (composerSchema.estSousFormulaire(…))` devient `if (false && …)` | **T2** « sous la racine, égal à elle, ou atteint par un lien », **T2** « un lien vers la racine ne contourne pas la garde », **T2** « la racine réelle est reconnue par défaut » | code 0 |
| M2 | Création exclusive | `{ flag: "wx" }` devient `{ flag: "w" }` dans `ecrireDansTravail` | **T3** « composer refuse d'écraser `schema.json` », **T4** (le second `ecrireDansTravail` d'un nom de la liste réussit) | code 0 |
| M3 | Liste fermée des noms | `NOMS_ECRITS.indexOf(nom) === -1` retiré du test d'entrée | **T4** « aucun nom hors de la liste fermée n'est écrit » seul | code 0 |
| M4 | Motif de refus du logo | `if (motifLogo) {` devient `if (false) {` dans `verifierTravail` | **T6** « signature fausse, trop gros, lien, absent, mauvais emplacement… » seul | code 0 |
| M5 | Échappement de `<` | `.replace(/</g, "\\u003c")` retiré du JSON embarqué | **T8** « le JSON embarqué se relit égal… un libellé `</script><script>` n'apparaît jamais tel quel » seul | code 0 |
| M6 | Démarrage normal du moteur retiré | `document.removeEventListener("DOMContentLoaded", demarrerMoteur);` remplacé par `void 0;` dans le script de la page | **T9** « l'aperçu exécuté ne fait aucun fetch et retire `demarrerMoteur` » seul | code 0 |
| M7 | Refus d'un lien à la place de l'aperçu | `if (!infos.isFile()) {` devient `if (false) {` dans le chemin `remplacer` | **T3** « `apercu` remplace son fichier mais refuse… un lien » seul | code 0 |
| M8 | Marqueurs lus « exactement une fois » | `lignes.length !== 1` devient `lignes.length < 1` | **T5** « la liste des marqueurs est lue dans `script.js` ; une ligne absente ou en double → source illisible » seul | code 0 |
| M9 | `-B` : pas de `__pycache__` sous `serveur/` | `"-I", "-B", ` devient `"-I", ` aux deux appels de l'auxiliaire | **T1** « l'auxiliaire n'écrit rien sous `serveur/` » seul | code 0 |

M1 à M6 sont ceux du contrat (§9) ; M7 à M9 sont ajoutés : ils éprouvent des
gardes que le contrat exige (refus des liens, source illisible, `-I -B`) sans
leur donner de numéro.

## Limites connues des cas

- **M9 ne mord que sur un clone frais.** Dans le dépôt réel, `serveur/__pycache__/`
  existe déjà et à jour (ignoré par Git) : un import sans `-B` n'y écrit rien de
  neuf. Le cas capture l'état de `serveur/` avant le tout premier appel de
  l'auxiliaire, et la mutation se joue donc dans le clone, où le dossier n'existe
  pas. La commande de recoupement du contrat reste utile :
  `git status --porcelain --ignored serveur/` avant et après.
- **Le confinement de la racine réelle n'est pas éprouvé par écriture.** T2
  éprouve la garde sur une racine jetable ; `refusConfinement(RACINE)` prouve en
  lecture que la racine par défaut est bien reconnue ; A6 (`ouvrir ./essai-atelier`
  depuis la racine) le joue de bout en bout à la main.
- **Course (TOCTOU).** La garde contrôle le dossier puis écrit : un lien posé
  entre les deux par un tiers contourne le contrôle de dossier. `wx` ne suit pas
  un lien au dernier maillon du chemin, et l'opérateur seul écrit dans son
  dossier de travail ; le risque est jugé hors de portée de l'atelier, mais il
  est consigné pour l'audit.
