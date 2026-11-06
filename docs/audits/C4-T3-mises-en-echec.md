# C4-T3 — Journal des mises en échec

Rédigé par l'implémenteur, le 6 novembre 2026. L'audit de sécurité de la tâche
(`docs/audits/C4-T3.md`) est écrit à part, par l'auditeur.

## Protocole

- **Copie de travail** hors du dépôt, faite par
  `git ls-files -z --cached --others --exclude-standard | rsync -a --from0 --files-from=- ./ <copie>/`.
  Aucun fichier réel du cabinet (`config.json`, clés, certificats, journaux,
  `bilans/`) n'y figure : la liste de fichiers du dépôt ne les contient pas.
- **Sauvegarde** de `serveur/serveur.py` hors de la copie avant toute mutation ;
  **restauration par `cp`** après chacune, puis comparaison `cmp` à la sauvegarde
  en fin de série. Rien n'a été muté dans le dépôt ; rien n'était indexé pendant
  les mutations (`git status` propre).
- **Harnais** : une mutation = un remplacement de texte exact, dont le nombre
  d'occurrences est vérifié avant écriture (une mutation qui ne change rien
  fait échouer le harnais, pas passer le test). Les tests joués :
  `python3 [-O] -W error::ResourceWarning -m unittest tests.test_serveur tests.test_integration tests.test_conservation`
  (246 tests), depuis la copie, au premier plan. Code de retour lu sur le
  processus de test lui-même, pas sur un tube.
- **Témoin sans mutation** joué dans chaque série : `rc=0`, 246 tests OK,
  en mode normal et sous `-O`.
- Interpréteur : Python 3.14.3 (macOS). Le contrat parle de 3.13 pour le
  critère 16 seulement ; la CI joue 3.9 et 3.13.

## Résultats

Les mutations a à h sont celles du critère 12 du contrat ; g est jouée sous
deux formes. Les lignes i à p sont ajoutées : elles éprouvent les risques du §12
(parseur DER, interrupteur, verrou) que le critère 12 ne couvre pas.
« Rouges » = nombre de tests distincts en échec, mode normal / sous `-O`
(les deux listes sont identiques, test pour test). Toutes les mutations
rendent `rc=1` dans les deux modes ; le témoin rend `rc=0`.

| Id | Critère 12 | Mutation | Éprouve | Rouges | Tests rouges notables |
|---|---|---|---|---|---|
| a | 12 a | `etat["client"] = self.client_address[0]` dans `repondre_etat` | critère 8 et garde statique | 3 / 3 | `test_etat_json_liste_blanche`, `test_etat_sans_adresse`, `test_garde_statique_sans_adresse_client` |
| b | 12 b | `authentifie()` retiré de `repondre_etat` | critère 1 | 5 / 5 | `test_etat_construit_avant_send_response`, `test_etat_head_sans_authentification_401`, `test_etat_mauvais_mot_de_passe_401`, `test_etat_sans_authentification_401`, `test_seule_sante_sans_authentification` |
| c | 12 c | clé `"dossier": dossier_pdf` ajoutée à `construire_etat` | critères 2 et 9 | 5 / 5 | `test_aucune_valeur_de_configuration`, `test_cles_exactes`, `test_disque_indisponible_ne_divulgue_rien`, `test_etat_json_liste_blanche`, `test_etat_sans_nom_de_fichier` |
| d | 12 d | `open(JOURNAL, ...)` à la place de `open(TECHNIQUE, ...)` | critère 10 | 11 / 11 | `test_etat_lignes_du_journal_technique`, `test_etat_sans_adresse`, `test_queue_bornee` |
| e | 12 e | `VERSION_EN_COURS = "9.9.9"` à la place de `lire_version()` | critère 4 | 3 / 3 | `test_etat_html`, `test_etat_version_source_unique`, `test_scenario_complet_reconstituable` |
| f | 12 f | `html.escape(` remplacé par `str(` (3 sites) | échappement HTML | 1 / 1 | `test_html_echappe` |
| g1 | 12 g | `/etat` servi par `repondre_sante` en tête de `do_GET` | critère 11 | 14 / 14 | `test_etat_mauvais_mot_de_passe_401`, `test_etat_sans_authentification_401`, `test_seule_sante_sans_authentification` |
| g2 | 12 g (variante) | `/etat` ajouté au tuple de la branche `/sante` de `do_GET` | critère 11 | 15 / 15 | `test_etat_desactivee_retrouve_l_existant`, `test_etat_sans_authentification_401`, `test_seule_sante_sans_authentification` |
| h | 12 h | `"etat"` retiré de `ROUTES_TECHNIQUES` | `test_classe_route_etat` | 1 / 1 | `test_classe_route_etat` |
| i | — | début de validité lu à la place de la fin (`dates[0]`) | risque §12 (parseur DER) | 8 / 8 | `test_conforme_a_cryptography`, `test_etat_certificat`, `test_la_fin_est_la_seconde_date` |
| j | — | `dernieres_lignes_techniques` sans le verrou des journaux | étape 5 | 1 / 1 | `test_queue_prend_le_verrou_des_journaux` |
| k | — | `Gestionnaire.page_etat = True` (interrupteur ignoré) | critère 13 | 1 / 1 | `test_etat_desactivee_retrouve_l_existant` |
| l | — | pivot UTCTime supprimé (toujours 20AA) | risque §12 (parseur DER) | 2 / 2 | `test_utctime_et_generalizedtime`, `test_utctime_et_generalizedtime_de_cryptography` |
| m | — | `DERNIER_DEPOT` jamais posé | critère 5 | 1 / 1 | `test_etat_dernier_depot` |
| n | — | verdict inversé (`conforme` / `adresse changée`) | critère 7 | 2 / 2 | `test_trois_issues`, `test_une_seule_adresse_portee_suffit` |
| p | — | première ligne partielle conservée dans la queue | étape 5 | 1 / 1 | `test_queue_ecarte_la_ligne_coupee` |
| témoin | — | aucune | — | 0 / 0 | `rc=0`, 246 tests OK |

## Les tests de la tâche sur l'ancien code

Les tests ajoutés, joués contre `serveur/serveur.py` de `a9b3676` (copie,
sans la tâche) : 165 tests chargés, 13 échecs et 225 erreurs (sous-tests
compris). Les tests qui passent déjà sur l'ancien code sont ceux que le
contrat annonçait (les trois 401 et `test_etat_cache_control_unique`), plus
`test_etat_content_length_exact` et `test_etat_desactivee_retrouve_l_existant`
(`/etat` répondait déjà 403/401 : l'interrupteur n'a rien à changer là, et
c'est la mutation k qui l'éprouve — contrairement à ce que dit la table du §9
du contrat). `test_seule_sante_sans_authentification` échoue sur l'ancien code :
il exige au moins deux chemins protégés dérivés de l'arbre, et il n'y en avait
qu'un (`/cabinet`).

## Constats

- La garde statique `problemes_adresse_client` a elle-même été mise en échec
  (`PageEtat.test_garde_statique_mise_en_echec`) : une adresse glissée dans
  chacune des quatre fonctions, ou dans une aide qu'elles appellent, la fait
  rougir, et une fonction introuvable aussi.
- Aucune mutation résiduelle : en fin de série, la copie est identique à la
  sauvegarde (`cmp`), et le dépôt n'a jamais été touché.

## CI

Run `42198008294` (`workflow_dispatch` sur `c4-t3-etat`, commit `9de935e`) :
7 jobs sur 7 verts (lint, scripts-windows, et `test` sur ubuntu, macOS et
Windows en 3.13, ubuntu et Windows en 3.9).
https://github.com/baptiste5922/bilan-posturo/actions/runs/42198008294
