# C1-T5 — journal des mises en échec

**Date :** 6 novembre 2026
**Branche :** `c1-t5-blocs`, depuis `8ba4e06` (contrat commité)
**Règle :** un garde-fou non mis en échec ne garde rien (`CLAUDE.md`). Chaque
mutation a son **témoin** (la même commande sur l'arbre sain) et le **code de
retour du test lui-même**, lu dans la sortie du test, jamais un `$?` lu après
autre chose.

## Méthode

- Chaque mutation se joue dans une **copie jetable** construite par
  `git ls-files -z --cached --others --exclude-standard` (fichiers suivis et
  fichiers neufs non ignorés ; ni `config.json`, ni clé, ni journal, ni dossier
  des bilans : ils sont ignorés par Git), copiée fichier par fichier. Aucune
  mutation n'a touché l'arbre de travail réel : la restauration est la
  suppression de la copie.
- Le script de mutation (`mutations.py`) est **hors dépôt**, dans le dossier de
  session ; il refuse une mutation sans effet (motif absent du fichier).
- Le témoin est joué dans une copie saine avant les mutations : `node tests/test_blocs.js`
  rend 0 (« Tout est vert »), `python3 -m unittest tests.test_paquet` rend 0,
  `python3 -O -m unittest tests.test_paquet` rend 0.
- La copie est rejouée après les dernières retouches du dépôt (descriptions des
  fragments, voir « Confidentialité » plus bas) : le tableau ci-dessous est celui
  de la **seconde exécution complète**, identique à la première pour tous les cas
  qui rougissent.

## Mutations

« Cas qui rougissent » : le groupe de garde (B1 à B9) du ou des cas de
`tests/test_blocs.js` en échec. Code du test : 1 partout, témoin : 0.

| N° | Garde visée | Mutation (copie jetable) | Cas qui rougissent | Remarque |
|---|---|---|---|---|
| M1 | B4, B5 | libellé altéré dans `blocs/anamnese.json` (`Nom:` devient `Nom :`) | **B4**, **B5** (identité au pilote) ; B8 (sortie standard) par ricochet | B3 reste vert : la composition est valide, seule sa fidélité est atteinte |
| M2 | B4 | `examen-statique` et `examen-dynamique` permutés dans `podologue-complet` | **B4** ; B8 (sortie standard) par ricochet | B3, B5 restent verts : chaque fragment est intact et valide |
| M3 | B3 | `version_schema: 3` dans `podologue-court` | **B3**, **B6** (version 1 exigée) ; B8 par ricochet (le cas « attribut inconnu » compose le court) | Écart avec le contrat, qui écrit « B3 seul » : B6 exige aussi la version 1 (voir M3b) |
| M3b | B3 seul | fragment d'essai à `type` inconnu, recette d'essai qui l'utilise | **B3** seul | aucun bloc du pilote (B5 vert), structure valide (B1, B2 verts) |
| M4 | B5 | fragment orphelin portant `atcd_bloc` avec `familliaux` renommé `familiaux` | **B5** (identité : « diffère du pilote à `.champs[1].cle` »), **B5** (bloc dans deux fragments) | B1, B3, B4 restent verts : le fragment n'est dans aucune recette. Écart de lettre : le contrat place `familliaux` dans `patient_infos`, il est dans `atcd_bloc` |
| M5 | B6 | fragment d'essai portant un champ de type `grille`, orphelin | **B6** seul | |
| M6 | B1 | clé `auteur` ajoutée dans `blocs/conclusion.json` | **B1** ; B3, B4 et trois cas B8 par ricochet (l'outil refuse le fragment) | |
| M7a | B1 | `blocs/notes.txt` | **B1** (entrées de `blocs/`) seul | |
| M7b | B1 | lien symbolique `blocs/lien.json` | **B1** (entrées de `blocs/`) seul | |
| M8 | B2 | fragment inexistant dans `podologue-court` | **B2** ; B3 et deux cas B8 par ricochet | |
| M9 | B7 | `cp -R blocs templates "$PAQUET/"` ajouté dans la copie de `faire-paquet.sh` | `test_ni_blocs_ni_templates_dans_l_archive` (`FAIL`, un seul test) | **Joué aussi sous `python3 -O`** : même échec, même test |
| M10 | B8 | drapeau `wx` remplacé par `w` dans `composer-schema.js` | **B8** « `--sortie` crée… refuse d'écraser » seul | |
| M11 | B9 | `images/inexistante.png` dans un fragment orphelin | **B9** « chaque image des fragments existe » seul | |
| M11b | B9 | `images/inexistante.png` dans `blocs/ortheses.json` | **B9**, plus B3, B4, B5 et trois cas B8 par ricochet | l'outil lui-même refuse l'image |
| M12 | B1 | `blocs/chaussage.json` réindenté à 4 espaces | **B1** (forme canonique) seul | B4 reste vert : il compare le JSON composé, pas la mise en page des fragments |
| M13 | B8 | garde `formulaire/` neutralisée (`if (false)`) | **B8** « `--sortie` sous `formulaire/` », sous-cas **chemin direct** | les sous-cas se jouent dans une **racine temporaire** (script, moteur et fragments copiés) : plus aucun cas de test n'écrit dans le dépôt ; témoin vert (une sortie hors de `formulaire/` est acceptée dans la même racine) |
| M13b | B8 | garde réduite à une comparaison de chaînes de chemins | **B8**, sous-cas **lien symbolique** (« écrit sous formulaire/ ») | le dossier temporaire est passé par `realpath` pour que ce soit le lien, et non `/var` -> `/private/var` de macOS, qui trahisse la garde |
| M13c | B8 | garde sans remontée des ancêtres (seul le dossier exact est comparé) | **B8**, sous-cas **`formulaire/moteur/`** | |
| M13d | B8 | garde réduite à une comparaison de `realpath` (chaînes) | **B8**, sous-cas **autre casse** (`FORMULAIRE/`), joué sur disque insensible à la casse | sur un disque sensible à la casse le sous-cas s'annonce `SAUTÉ`, jamais en silence |
| M14a | A7 | attribut inconnu dans un fragment (`blocs/chaussage.json`) | **B3**, **B4**, **B5** ; B8 par ricochet | |
| M14b | A7, B8 | avertissement du moteur toléré dans `composer-schema.js` | **B8** « un attribut inconnu dans un fragment est un refus » et **B8** « `--verifier` rend 1 sur un attribut inconnu » | l'avertissement n'est un refus que par cette ligne |
| M15 | B8 | motif des noms de fragment neutralisé (`/^.+$/`) | **B8** « nom de fragment avec chemin » seul | le cas exige que le refus vienne du motif, pas de la lecture du fichier visé |
| M16 | B8 | `lstat` remplacé par `stat` (liens suivis) | **B8** « un fragment qui est un lien symbolique est refusé » seul | |
| M17 | B8, B9 | contrôle d'existence des images neutralisé dans l'outil | **B9** « l'outil refuse une image absente » seul | |
| M18 | B4 | une espace ajoutée à un libellé de `clients/cabinet-01/schema.json` seul | **B4**, **B5** ; B8 (sortie standard) | D9 en acte : modifier le pilote seul rougit, la décision est écrite ; B4 ne s'assouplit pas |

## Constats de la séquence

- **Mutation sans témoin sain** : les trois témoins (`node tests/test_blocs.js`,
  `tests.test_paquet`, même sous `-O`) rendent 0 dans une copie fraîche avant la
  première mutation.
- **B7 sous `python3 -O`** : le test est écrit en `self.assertEqual` /
  `self.assertTrue` (aucun `assert` nu), donc il mord sous `-O` (M9).
- **Rien n'est écrit dans le dépôt par B8** (revue de l'audit) : après chacune des
  mutations M13 à M13d, jouées dans une copie, aucun fichier `zz-*` n'existe sous
  le `formulaire/` de la copie, ni sous celui du dépôt réel
  (`ls formulaire | grep -c zz` rend 0).
- **Le préalable de B7** (« la copie du dépôt contient `blocs/` et `templates/` »)
  est un `assertTrue` sur des fichiers réellement présents : sans lui, un
  `_copier_le_depot()` qui oublierait les deux dossiers rendrait le test vert à
  vide. Le préalable a été vérifié en retirant `"blocs", "templates"` de la liste
  de copie : le test échoue au préalable, avec le message « test vert à vide ».
  (Mutation jouée à la main sur `tests/test_paquet.py` dans une copie jetable,
  hors tableau ci-dessus.)

## Confidentialité (A14), constaté en cours de route

Avant les mutations, `tests.test_confidentialite_prospect` (`AucunMarqueurDeLaFiche`)
a refusé quatre lignes d'un premier jet de **descriptions** de fragments et de
`blocs/LISEZMOI.md` (« texte de la fiche retrouvé dans… », sans l'afficher) : des
tournures de vocabulaire médical générique qui recoupaient la fiche du prospect.
La fiche n'a pas été lue : les descriptions ont été reformulées à partir des
titres de blocs du **pilote** (déjà publics : « Informations Patient »,
« Statique », « Appui », « Podo »…), et la garde est repassée au vert, sans saut.
Rien n'avait été commité ni poussé avant.

## Fin de séquence

`git status --short` ne montre que les fichiers du §5 du contrat ; les deux
schémas du pilote ont toujours le SHA d'origine
`5e7a56821e6730fdbd802553c2c6730a04626d51724d13e8064f74eb22ea0706`.
