# C6-T7 — Journal des mises en échec

Rédigé par l'implémenteur, le 7 novembre 2026. L'audit de sécurité de la tâche
(`docs/audits/C6-T7.md`) est écrit à part, par l'auditeur.

## Protocole

- **Copie jetable** hors du dépôt, faite par
  `git ls-files -z --cached --others --exclude-standard`, fichier par fichier,
  puis initialisée en dépôt Git **sans origine** pour que U12 (`git ls-files`)
  et les tests de dossiers ignorés disposent d'un index. 191 fichiers ; ni
  `config.json`, ni clé, ni certificat, ni journal ni `bilans/` n'y figurent.
  Deux copies, l'une pour le mode normal, l'autre pour `-O`, afin de pouvoir les
  jouer en même temps sans qu'elles se marchent dessus.
- **Sauvegarde** de `serveur/serveur.py` hors du dépôt avant toute mutation
  (`scratchpad/serveur.final.py`). Le dépôt n'a jamais été muté : chaque
  mutation est un remplacement de texte **exact** sur la copie, et le harnais
  refuse de jouer une mutation qui ne change pas le texte (assertion sur le
  nombre d'occurrences).
- **Témoin non muté avant chaque mutation**, dans le même mode, puis un témoin
  final : `rc=0` chaque fois. `serveur.py` de la copie est réécrit depuis la
  sauvegarde avant chaque série (le harnais affiche « serveur identique au
  témoin » pour le témoin).
- **Tests joués** : `python3 [-O] -m unittest tests.test_racine_web
  tests.test_liens_servis tests.test_logo tests.test_serveur` (221 tests, dont
  5 sautés : W1 hors Windows et quatre jonctions réelles). `test_logo` garde le
  relevé des motifs de `confiner_logo` ; `test_serveur` dérive la couverture des
  événements de `EVENEMENTS_TECHNIQUES`.
- **Mode normal** : lancé en arrière-plan sur la copie 1 (sans incidence en
  mode normal). **Mode `-O`** : lancé au **premier plan**, sur la copie 2, pour
  ne pas rencontrer le piège de `ServeurArret.test_arret_journalise` (SIGINT
  ignoré par un `-O` lancé en arrière-plan). Le témoin `-O` est vert, ce test
  compris.
- **Disque** : macOS, insensible à la casse ; la simulation de Windows
  (`windows_simule`, `realpath_casse_des_parents`) est donc exercée sur un
  disque qui n'impose pas la casse. Interpréteur : Python 3.14.3. Un essai de
  non-régression sous le Python 3.9.6 de macOS est décrit plus bas.
- **Une mutation qui fige** (M1, M3, M5 : le serveur démarre au lieu de
  refuser) ne fige pas la suite : `lancer_et_sonder` borne chaque lancement à
  30 s (`subprocess.run(timeout=30)`, qui tue le fils), d'où des durées de 75 à
  165 s au lieu de 15 s. Les tests d'intégration se terminent en **erreur**
  (`TimeoutExpired`), pas en échec : c'est le même signal, un test rouge.

## Résultats

Tous les témoins rendent `rc=0` ; toutes les mutations rendent `rc=1`. Les
listes rouges sont **identiques en mode normal et sous `-O`**, test pour test.

| Id | Mutation | Tests rouges | Attendu par le contrat |
|---|---|---|---|
| M1 | appel de `motif_refus_racine_web` supprimé de `demarrer()` (`motif = None`) | `test_i1_formulaire_lie_a_la_racine_du_bac`, `test_i1_le_lien_peut_aussi_etre_absolu`, `test_i2_dossier_des_bilans_sous_la_racine_web`, `test_i2_le_dossier_des_bilans_absolu_est_refuse_aussi`, `test_i3_refus_sans_journal_technique` (erreurs de délai), `test_g2_le_controle_precede_l_ecriture_et_le_socket` | I1, I2, G2 : conforme |
| M2 | `realpath` retiré côté cabinet | `test_u2_…` (2 tests), `test_u3_…`, `test_u4_…` (les deux côtés), `test_u5_la_racine_du_cabinet_l_emporte…`, `test_u7_…` | U4 : conforme |
| M3 | `realpath` retiré côté racine web | U2 (2), U3, U4 (2), U5 (5 sous-cas), U7, et I1, I1 absolu, I3 (le serveur démarre : délai) | U2, U4 : conforme |
| M4 | `normcase` retiré aux trois endroits | `test_u7_windows_la_casse_est_ignoree` | U7 : conforme |
| M5 | test de `dossier_pdf` retiré (`if False:`) | `test_u5_…` (4 formes + le lien), `test_i2_dossier_des_bilans_sous_la_racine_web`, `test_i2_le_dossier_des_bilans_absolu_est_refuse_aussi` | U5, I2 : conforme |
| M6 | `startswith` à la place de `commonpath` | `test_u6_voisin_par_prefixe_de_chaine` | U6 : conforme, voir note 1 |
| M7 | la racine web ajoutée au détail de `technique.log` | `test_i1_formulaire_lie_a_la_racine_du_bac`, `test_i1_le_lien_peut_aussi_etre_absolu`, `test_i2_dossier_des_bilans_sous_la_racine_web`, `test_aucun_chemin_dans_le_journal_technique`, `test_chaque_motif_a_son_message_et_ses_deux_lignes` (3 motifs), `test_g1_le_signalement_n_ecrit_au_technique_que_le_detail_ferme` | I1 : conforme |
| M8 | `return 0` à la place de `return 1` | `test_i1_…` (2), `test_i2_…` (2), `test_i3_…`, `test_g2_le_refus_sort_avec_le_code_1` | I1 : conforme |
| M9 | contrôle déplacé après `os.makedirs` | `test_i1_formulaire_lie_a_la_racine_du_bac`, `test_i2_dossier_des_bilans_sous_la_racine_web`, `test_i2_le_dossier_des_bilans_absolu_est_refuse_aussi`, `test_g2_le_controle_precede_l_ecriture_et_le_socket` | I2, G2 : conforme |
| M10 | `return reel, None` à la place de `continue` dans la boucle `lstat` | `test_u13b_parent_en_point_de_reparse_reste_refuse_si_le_fichier_est_absent` | U13b : conforme |

## Notes

1. **U6 du contrat ne mord pas M6 dans le sens où il est écrit.** Le contrat
   donne « `web = tmp/cab-web`, cabinet `tmp/cab` ». Or le prédicat est
   « la racine web contient X » : avec `startswith`, il teste
   `cabinet.startswith(web)`, soit `"tmp/cab".startswith("tmp/cab-web")`, faux
   dans les deux implémentations. Le piège réel est l'inverse : une racine web
   `tmp/cab` et un cabinet voisin `tmp/cab-x`. Le test U6 joue les deux sens
   (celui du contrat, gardé, et le sens qui mord) plus le même piège pour
   `dossier_pdf`. M6 ne rougit que grâce à ce second sens ; c'est constaté, pas
   supposé.
2. **M2 ne rougit aucun test d'intégration sous macOS, et c'est normal.** Un
   serveur lancé par un chemin relatif dans un bac calcule sa racine depuis
   `os.getcwd()`, déjà résolu (`/private/var/…`) : `RACINE` est donc la forme
   résolue, et retirer `realpath` n'y change rien. C'est la raison de la
   consigne du contrat pour U4 (« ne pas partir de `os.getcwd()` ») : seul U4,
   qui fabrique une racine non résolue avec `acces → reel`, mord M2.
3. **M3 : I2 ne rougit pas.** Dans I2, `formulaire` est un vrai dossier, pas un
   lien : sans `realpath`, la racine web reste lisible telle quelle et
   `formulaire/bilans` est encore détecté. Ce n'est pas un trou : le contrat
   n'attend de M3 que U2 et U4.
4. **U4 mord deux côtés.** La première version du test ne mordait que M2 ; une
   mutation M3 laissait U4 vert, parce que la racine web donnée y était déjà
   résolue. Le test joue maintenant les deux orientations (cabinet non résolu
   contre web résolu, et l'inverse), vérifié par M2 **et** M3 ci-dessus.
5. **Fragilité de test corrigée en cours de série.** Le premier U2 bouclait sur
   deux cibles avec un nettoyage à l'intérieur du sous-test : un premier échec
   sautait le nettoyage et le second sous-test se terminait en erreur
   parasite (`cible='.'`). U2 est maintenant deux tests séparés. Toute la série
   a été rejouée après ce changement ; les chiffres ci-dessus sont ceux de la
   seconde passe.
6. **W1 (jonction NTFS réelle)** ne peut pas être joué ici ; il est écrit pour
   la CI Windows. Il n'a donc été éprouvé par aucune mutation : sa première
   exécution sera celle de la CI. `defaire_la_jonction` fait un `rmdir` avant
   `rmtree`, pour que `shutil.rmtree` ne suive jamais une jonction qui remonte
   vers son propre parent.
7. **Ce que les mutations ne couvrent pas** : l'ordre « racine du cabinet
   d'abord, puis `dossier_pdf` ». Une permutation ferait rendre `dossier-pdf`
   quand `formulaire` englobe le cabinet ; elle est gardée par
   `test_u5_la_racine_du_cabinet_l_emporte_sur_les_bilans` et par le motif
   exact de I1, mais n'est pas listée au contrat et n'a pas été jouée.

## Essais complémentaires

- **Avant correctif** (`serveur.py` de `efb13f6` replacé dans le dépôt, puis
  restauré) : U13a rend `'illisible'` au lieu de `None`, U13b rend `'illisible'`
  au lieu de `'lien-symbolique'`. Constaté avant d'écrire la correction définitive.
- **Python 3.9.6 (macOS, sans `cryptography`)** : `tests.test_racine_web`,
  `tests.test_liens_servis` et `tests.test_logo` donnent deux échecs, les deux
  tests de jonction simulée (`test_u8_jonction_simulee_invisible_a_islink`,
  `test_jonction_invisible_a_islink`). Ils échouent **de la même façon à
  `efb13f6`, avant toute modification de la tâche** (essai dans un arbre de
  travail jetable, 82 tests, 2 échecs) : défaut connu de 3.9.6 sous macOS. Les
  tests d'intégration, dont I1 à I6, sont sautés faute de `cryptography`.
- **Nombre de tests** : `tests.test_integration` + `tests.test_liens_servis`
  rendent 100 tests et 4 sautés à `efb13f6`, 102 tests et 4 sautés après la
  tâche (les deux de plus sont U13a et U13b) : l'extraction de
  `preparer_sandbox` ne change aucun test existant.
- **Fuite de processus** : une série interrompue à la main a laissé un serveur
  de bac à sable en marche (I6, nettoyage sauté par le `pkill` de la série, pas
  par le test). Retrouvé par son répertoire courant, arrêté, bac supprimé. Aucun
  serveur ne tourne plus.
