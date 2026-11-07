# C6-T6 — Journal des mises en échec

Rédigé par l'implémenteur, le 7 novembre 2026. L'audit de sécurité de la tâche
(`docs/audits/C6-T6.md`) est écrit à part, par l'auditeur.

## Protocole

- **Copie jetable** hors du dépôt, faite par
  `git ls-files -z --cached --others --exclude-standard`, fichier par fichier
  (Python, `shutil.copy2`), puis initialisée en dépôt Git **sans origine** pour
  que U12 dispose d'un index. Le harnais refuse de continuer si `config.json`,
  une clé, `journal.log` ou `technique.log` se retrouve dans la copie. Aucun
  fichier réel du cabinet n'y figure.
- **Une mutation = un remplacement de texte exact** dans `serveur/serveur.py` de
  la copie. Le harnais refuse de jouer une mutation qui ne change rien
  (`MUTATION NON APPLIQUÉE`). La copie est refaite à neuf avant chaque
  témoin, puis mutée.
- **Témoin sans mutation** joué avant chaque mutation, dans le même mode : `rc=0`
  partout. Code de sortie lu sur le processus de test lui-même.
- **Tests joués** : `python3 [-O] -m unittest tests.test_liens_servis tests.test_logo`
  (81 tests lors des séries, 82 depuis l'ajout de I10) ; pour M6,
  `+ tests.test_integration` (145 tests).
- **Sous `-O`, au premier plan** : M5a, M5b, M5c, M5d, M6. Un lancement en
  arrière-plan par `( … &)` ignore SIGINT et fait échouer
  `ServeurArret.test_arret_journalise` y compris sans mutation (piège connu de
  `CLAUDE.md`) : le premier essai de M6 en arrière-plan l'a montré, il a été
  rejoué au premier plan. Les listes rouges sont identiques en mode normal et
  sous `-O`, test pour test.
- **Disques** : les séries ont été jouées sur le disque ordinaire de macOS
  (insensible à la casse) ; la suite des tests a en plus été jouée sur un volume
  APFS **sensible à la casse** (`TMPDIR`), qui reproduit le comportement de
  Linux et a révélé un défaut de la simulation de Windows (voir plus bas).
- Interpréteur : Python 3.14 (macOS) ; Python 3.9.6 pour un essai de
  non-régression (voir « Observations »). La CI joue 3.9 et 3.13 sur trois
  systèmes.
- **État final** : `git status` propre sur `serveur/` ; aucune mutation dans le
  dépôt (le seul fichier modifié au moment de l'écriture est ce journal, plus
  `tests/test_liens_servis.py` avec l'ajout de I10, commités ensuite).

## Résultats

Tous les témoins rendent `rc=0` ; toutes les mutations rendent `rc=1`.

| Id | Mutation | Tests rouges | Attendu par le contrat |
|---|---|---|---|
| M1 | bloc de refus supprimé de `autorise_lecture` | `test_g2_…`, `test_i1_…`, `test_i2_…`, `test_i3_…`, `test_i4_…`, `test_i7_journaux` | I1 à I4, I7, G2 : conforme |
| M2 | `confiner_fichier_servi(chemin, …)` au lieu de `self.translate_path(chemin)` | `test_g2_…`, `test_i5_le_service_ordinaire_est_intact`, `test_i7_journaux`, `test_logo_valide_propose_et_servi` | I4 et G2 attendus : **I4 ne rougit pas**, voir note 1 |
| M2b *(ajoutée)* | chemin brut non décodé, joint à la racine | `test_g2_…`, `test_i4_nom_du_lien_encode_refuse` | — : celle qui éprouve I4 |
| M3 | `FORBIDDEN` au lieu de `NOT_FOUND` | `test_i1_…`, `test_i2_…`, `test_i3_…`, `test_i4_…`, `test_i7_journaux` | I1 : conforme |
| M4 | message français au lieu de `File not found` | `test_i1_le_lien_vers_config_rend_la_meme_404_qu_un_absent` | I1 : conforme |
| M5a | `tolerer_casse=True` → `False` dans `confiner_fichier_servi` | `test_g3_…`, `test_u9_casse_seule_est_servie`, `test_u9b_a_…`, `test_u9b_b_…` | U9, G3, I9 sur Windows : **I9 non éprouvée**, voir note 2 |
| M5b | défaut `tolerer_casse=True` | `test_casse_seule_est_absente_et_non_lien` (CasseWindows), `test_g3_…`, `test_u9_le_defaut_est_le_refus`, `test_u9c_le_logo_garde_le_refus` | CasseWindows, U9c, G3 : conforme |
| M5c | boucle `lstat` retirée de la branche de tolérance | `test_u9b_a_lstat_voit_un_lien_que_islink_ne_voit_pas`, `test_u9b_b_point_de_reparse_sur_un_dossier_parent` | U9b (a) et (b) : conforme |
| M5d | `if True:` à la place de la comparaison `normcase` | `test_casse_seule_est_absente_et_non_lien`, `test_u9_casse_seule_est_servie`, `test_u9_le_defaut_est_le_refus`, `test_u9c_le_logo_garde_le_refus` | CasseWindows, U9c, U9 : conforme |
| M6 | `base = os.path.abspath(racine_web)` | 27 rouges, dont `test_u7_racine_elle_meme_atteinte_par_un_lien`, `test_racine_elle_meme_atteinte_par_un_lien` (test_logo), `test_u1_…`, `test_u2_…`, `test_u8_…`, `test_u9*`, `test_fichier_sous_la_racine_accepte`, `test_jonction_invisible_a_islink` | U7, I5, intégration, `test_racine_elle_meme…` : **I5 et l'intégration ne rougissent pas sous macOS**, voir note 3 |
| M7 | `self.log_message(…)` au lieu de `journaliser(…)` | `test_i7_journaux` (échec), `test_i4_nom_du_lien_encode_refuse` (erreur) | I7 : conforme |
| M8 | `super().do_GET()` hors du `if self.autorise_lecture()` | `test_g1_toute_lecture_passe_par_autorise_lecture`, `test_i7_journaux` | G1 : conforme |
| M9 *(ajoutée)* | garde explicite de l'octet nul retirée | `test_u10_l_octet_nul_est_refuse_meme_si_realpath_le_laisse_passer` | — : éprouve l'ajout hors contrat |

## Notes

1. **M2 et I4.** Avec le chemin brut (`/images/fuite.png`, absolu), `relpath` par
   rapport à `formulaire/` sort de la racine : tout est refusé en `hors-racine`,
   y compris `GET /` (I5 rougit) et le logo servi. I4 reste donc vert, puisqu'il
   attend déjà une 404. La mutation qui éprouve I4 est le contrôle d'un chemin
   brut **relatif à la racine** : c'est M2b, ajoutée, qui fait rougir I4 et G2
   sans toucher I5.
2. **M5a et I9.** I9 (`GET /INDEX.HTML` → 200) ne se joue que sous Windows.
   M5a ne l'a donc pas fait rougir ici : seule la CI Windows peut le montrer, et
   il aurait fallu pousser une branche portant la mutation. Cela n'a **pas** été
   fait (une branche à serveur volontairement cassé n'était pas dans le mandat).
   Ce qui est établi : I9 est **joué** et vert sur les deux jobs Windows
   (journal du job), U9 et G3 rougissent par M5a localement. Ce qui ne l'est
   pas : que I9 rougisse effectivement par M5a.
3. **M6 et l'intégration sous macOS.** Le contrat attend que toute l'intégration
   rougisse sous macOS, la racine passant par `/var` → `/private/var`. Ce n'est
   pas le cas : le serveur du bac à sable calcule `RACINE` par
   `abspath(__file__)` à partir d'un chemin **relatif** (`serveur/serveur.py`,
   `cwd=dossier`) ; `os.getcwd()` rend déjà le chemin résolu
   (`/private/var/…`), si bien que sa racine ne passe par aucun lien. Vérifié :
   `cd $(mktemp -d); python3 -c "import os; print(os.getcwd())"` rend
   `/private/var/…` alors que `pwd` rend `/var/…`. M6 est néanmoins tuée par
   U7 (`acces` → racine, que j'ai écrit pour cela), par
   `test_racine_elle_meme_atteinte_par_un_lien` de `test_logo.py` et par les 25
   autres tests qui passent une racine temporaire non résolue.

## Écart découvert en CI, corrigé dans les tests

Les deux premiers essais en CI étaient rouges, et la cause tenait aux **tests**,
pas au serveur :

- sur Linux, `lstat("…/INDEX.HTML")` échoue (disque sensible à la casse) alors
  que sous Windows il réussit : la simulation de Windows de U9 doit donc aussi
  rendre `lstat` insensible à la casse. Le contrat prévoyait un « lstat réel » ;
  il est faux sur un disque sensible à la casse. Rejoué ensuite sur un volume
  APFS sensible à la casse ;
- sous Python 3.9 sur Linux, `realpath` appelle `os.lstat` : le faux lien posé
  par U9b (a) lui faisait lire un lien inexistant (`illisible`). `realpath` est
  maintenant isolé du faux `lstat` ;
- sous Windows, `commonpath` ignore la casse : U9b (c) place donc la cible dans
  un autre parent (`…-ailleurs/WEB`) pour être hors racine sur tous les systèmes.

## Observations

- Python 3.9.6 (macOS) : `test_logo.ConfinementLogo.test_jonction_invisible_a_islink`
  échoue **déjà sur le dépôt avant la tâche**. Sur ces versions, `realpath`
  consulte `os.path.islink` : le patch de l'aveuglement le rend aveugle aussi.
  `test_u8_jonction_simulee_invisible_a_islink` est de la même famille et
  échoue pareillement sur 3.9.6 ; il passe sur les 3.9 de la CI (Linux et
  Windows). À surveiller si l'on rejoue 3.9 en local sous macOS.
- Octet nul : selon la version de Python et le système, `realpath` lève
  `ValueError` ou laisse passer. Sans garde, `/x%00.json` sous Python 3.9 sur
  Linux serait « autorisé » par `confiner_fichier_servi`, puis `open()` lèverait
  une `ValueError` non rattrapée par `send_head` (connexion fermée, le symptôme
  de C6-T5). D'où une garde explicite dans `confiner_fichier_servi` (M9).
- M7 fait aussi échouer I4 en erreur : `log_message` applique `format % args`,
  et le chemin `fu%69te.png` contient un `%`. Ce n'est pas un défaut du code
  livré (qui utilise `journaliser`), mais cela illustre pourquoi `log_message`
  est la mauvaise voie pour une saisie contrôlée par le client.
