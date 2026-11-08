# C5-T1 — Mises en échec

**Contrat :** `docs/contrats/C5-T1.md` (étape 10, A23)
**Date :** 8 novembre 2026
**Branche :** `c5-t1-signature`

Ce fichier consigne les mises en échec jouées par l'implémenteur. Le rapport
d'audit de sécurité, `docs/audits/C5-T1.md`, est écrit par l'auditeur : il ne
partage pas ce fichier (même découpage que C6-T5 et C6-T7).

## 1. Méthode

- **Jamais dans le dépôt.** Chaque jeu de mutations s'est joué dans une copie
  fabriquée par `git ls-files -z`, puis `git init` : un dépôt jetable **sans
  `origin`**. Aucun fichier du cabinet (`config.json`, `*.pem`, journaux,
  `bilans/`) n'y est entré (vérifié : `ls` de la copie).
- **Un harnais, un motif exact.** Pour chaque mutation, le harnais (hors dépôt)
  exige que le motif à remplacer apparaisse **exactement une fois** dans le fichier
  d'origine, écrit la version mutée dans la copie, lance les suites visées,
  restaure par `cp` depuis le dépôt, vérifie par empreinte SHA-256 que la copie est
  redevenue identique, puis relance les mêmes suites : le **témoin** (code intact,
  suites vertes). Une mutation qui ne change rien, ou dont le motif est ambigu,
  arrête le harnais.
- **Trois configurations** (les deux premières sur les 55 mutations, la troisième sur M1 à M19 et leurs variantes) :
  `python3` (3.14.3, avec `cryptography`) ; `python3 -O` (les `assert` disparaissent) ;
  `/usr/bin/python3 -O` (3.9.6, **sans** `cryptography`, M1 à M19) — la configuration
  de A4.
- **Suites jouées** : `tests.test_signature_ed25519` pour la primitive,
  `tests.test_paquet_signe` pour le format (et `tests.test_signer_paquet` pour
  l'outil, M12, M20 et X17 à X27).
- Les exécutions `-O` ont été lancées depuis le premier plan ; l'outil de
  commande les a basculées en arrière-plan après 180 s. Cela ne change rien ici :
  ces suites ne contiennent aucun test qui dépende d'un signal (le piège de
  `SIGINT` concerne `test_integration.test_arret_journalise`, joué séparément, au
  premier plan, dans la suite complète sous `-O`).

## 2. Résultat

**55 mutations, 55 concluantes sous `python3` et sous `python3 -O` ; 26 sur 26 (M1 à M19 et leurs variantes) sous `/usr/bin/python3 -O` sans `cryptography`.** Chacune fait rougir au
moins un test nommé ; chaque témoin est vert ; chaque fichier est restauré à
l'octet. Les vingt du contrat (M1 à M20) le sont **sans** `cryptography` (sauf M20,
qui est une garde de l'outil de signature et exige `cryptography`).

Ce chiffre n'est pas celui du premier passage (section 4).

## 3. Détail

### M1 à M20 (tableau du contrat)

| # | Mutation | Fichier | Visé | Tests rouges | Tests nommés (deux premiers) | python3 | python3 -O | 3.9.6 -O, sans cryptography |
|---|---|---|---|---|---|---|---|---|
| M1 | supprimer le refus S >= L | `serveur/signature_ed25519.py` | A2 | 2 | `CroisementCryptography.test_s_plus_l_refuse_ici_et_par_cryptography`<br>`RefusDesSignaturesMalleables.test_s_valide_plus_l_est_refuse_alors_que_l_equation_tient` | rouge | rouge | rouge |
| M2 | supprimer le refus y >= p | `serveur/signature_ed25519.py` | A2 | 1 | `RefusDesSignaturesMalleables.test_le_decodeur_refuse_y_au_dela_de_p` | rouge | rouge | rouge |
| M3 | supprimer le refus x = 0 avec signe 1 | `serveur/signature_ed25519.py` | A2 | 1 | `RefusDesSignaturesMalleables.test_x_nul_avec_bit_de_signe_a_un_est_refuse` | rouge | rouge | rouge |
| M4 | supprimer le refus d'ordre faible (A et R) | `serveur/signature_ed25519.py` | A2 | 2 | `PointsDOrdreFaible.test_forgerie_universelle_avec_une_cle_d_ordre_faible_refusee`<br>`PointsDOrdreFaible.test_r_neutre_avec_cle_honnete_refuse_alors_que_l_equation_tient` | rouge | rouge | rouge |
| M5 | verifier rend True si la longueur est fausse | `serveur/signature_ed25519.py` | A2 | 2 | `RefusDesSignaturesMalleables.test_longueurs_fausses_refusees`<br>`RefusDesSignaturesMalleables.test_signature_trop_longue_dont_le_debut_est_valide_est_refusee` | rouge | rouge | rouge |
| M6 | ne plus comparer R | `serveur/signature_ed25519.py` | A1, A7 | 9 | `LectureDuManifeste.test_aucune_cle_fournie_refuse`<br>`CroisementCryptography.test_c_alterations_memes_verdicts_et_toujours_un_refus` | rouge | rouge | rouge |
| M7 | analyser le manifeste avant la signature | `serveur/paquet_signe.py` | test d'ordre | 2 | `LectureDuManifeste.test_l_ordre_la_signature_avant_toute_analyse`<br>`ConfianceEtAlterations.test_un_octet_modifie_a_soixante_quatre_positions` | rouge | rouge | rouge |
| M8 | accepter si aucune clé n'est fournie | `serveur/paquet_signe.py` | A8 | 1 | `LectureDuManifeste.test_aucune_cle_fournie_refuse` | rouge | rouge | rouge |
| M9 | comparer les versions comme chaînes | `serveur/paquet_signe.py` | A9 | 3 | `AnalyseDesVersions.test_formes_valides`<br>`AnalyseDesVersions.test_l_ordre_est_numerique_pas_alphabetique` | rouge | rouge | rouge |
| M10 | >= au lieu de > sur la version installée | `serveur/paquet_signe.py` | A9 | 2 | `Versions.test_minimale_egale_a_la_version_est_inutilisable`<br>`Versions.test_version_egale_refusee` | rouge | rouge | rouge |
| M11 | retirer le contrôle de version minimale | `serveur/paquet_signe.py` | A9 | 2 | `Versions.test_minimale_egale_a_la_version_est_inutilisable`<br>`Versions.test_minimale_non_atteinte` | rouge | rouge | rouge |
| M12 | retirer le contrôle d'empreinte d'archive | `serveur/paquet_signe.py` | A7 | 5 | `PaquetSigne.test_a7_un_octet_modifie_est_refuse_partout`<br>`ContenuDeLArchive.test_archive_modifiee_apres_signature` | rouge | rouge | rouge |
| M13 | retirer FICHIER_EN_TROP (fichier) | `serveur/paquet_signe.py` | A10 | 1 | `ContenuDeLArchive.test_fichier_en_trop` | rouge | rouge | rouge |
| M14 | retirer FICHIER_MANQUANT | `serveur/paquet_signe.py` | A10 | 2 | `ContenuDeLArchive.test_fichier_en_moins`<br>`ConfianceEtAlterations.test_fuzz_de_trois_cents_archives_resignees` | rouge | rouge | rouge |
| M15 | valider filename au lieu de orig_filename | `serveur/paquet_signe.py` | A11 | 2 | `Chemins.test_la_garde_juge_le_nom_brut_et_non_le_nom_corrige`<br>`Chemins.test_nom_avec_nul_dans_le_zip` | rouge | rouge | rouge |
| M16 | retirer le refus des noms réservés Windows | `serveur/paquet_signe.py` | A11 | 3 | `Chemins.test_chemin_dangereux_comme_nom_d_entree_du_zip`<br>`Chemins.test_chemin_dangereux_dans_le_manifeste` | rouge | rouge | rouge |
| M17 | retirer le doublon à la casse près (manifeste et zip) | `serveur/paquet_signe.py` | A11 | 5 | `Chemins.test_deux_entrees_de_meme_nom_dans_le_zip`<br>`Chemins.test_doublon_a_la_casse_pres_dans_le_manifeste` | rouge | rouge | rouge |
| M18 | retirer le refus des liens symboliques | `serveur/paquet_signe.py` | A12 | 1 | `ContenuDeLArchive.test_lien_symbolique_refuse` | rouge | rouge | rouge |
| M19 | lecture non bornée d'une entrée | `serveur/paquet_signe.py` | A12 | 1 | `ContenuDeLArchive.test_lecture_bornee_a_taille_plus_un` | rouge | rouge | rouge |
| M20 | signer n'exige plus que la clé figure dans la liste | `outils/signer-paquet.py` | A15 | 1 | `PaquetSigne.test_a15_cle_absente_de_la_liste_du_paquet` | rouge | rouge | n/a |

### Variantes isolées (M4a, M4b, M4c, M12b, M13b, M17a, M17b)

| # | Mutation | Fichier | Visé | Tests rouges | Tests nommés (deux premiers) | python3 | python3 -O | 3.9.6 -O, sans cryptography |
|---|---|---|---|---|---|---|---|---|
| M4a | ordre faible : seulement la clé A | `serveur/signature_ed25519.py` | A2 | 1 | `PointsDOrdreFaible.test_forgerie_universelle_avec_une_cle_d_ordre_faible_refusee` | rouge | rouge | rouge |
| M4b | ordre faible : seulement R | `serveur/signature_ed25519.py` | A2 | 1 | `PointsDOrdreFaible.test_r_neutre_avec_cle_honnete_refuse_alors_que_l_equation_tient` | rouge | rouge | rouge |
| M4c | ordre faible : clés de confiance (_point_acceptable) | `serveur/signature_ed25519.py` | clés de confiance | 1 | `ClesDeConfiance.test_refus_de_cle` | rouge | rouge | rouge |
| M12b | retirer le contrôle de taille d'archive | `serveur/paquet_signe.py` | A7 (taille) | 2 | `ContenuDeLArchive.test_archive_plus_longue_ou_plus_courte`<br>`ContenuDeLArchive.test_empreinte_d_archive_fausse_dans_le_manifeste_signe` | rouge | rouge | rouge |
| M13b | retirer FICHIER_EN_TROP (dossier orphelin) | `serveur/paquet_signe.py` | A10 | 2 | `ContenuDeLArchive.test_dossier_a_la_racine_orphelin`<br>`ContenuDeLArchive.test_entree_de_dossier_orpheline` | rouge | rouge | rouge |
| M17a | doublon à la casse près : manifeste seul | `serveur/paquet_signe.py` | A11 | 1 | `Chemins.test_doublon_du_manifeste_refuse_avant_de_lire_l_archive` | rouge | rouge | rouge |
| M17b | doublon à la casse près : zip seul | `serveur/paquet_signe.py` | A11 | 3 | `Chemins.test_deux_entrees_de_meme_nom_dans_le_zip`<br>`Chemins.test_doublon_a_la_casse_pres_dans_le_zip` | rouge | rouge | rouge |

### Gardes hors tableau du contrat (X1 à X27)

| # | Mutation | Fichier | Visé | Tests rouges | Tests nommés (deux premiers) | python3 | python3 -O | 3.9.6 -O, sans cryptography |
|---|---|---|---|---|---|---|---|---|
| X1 | chemin : point final admis | `serveur/paquet_signe.py` | A11 | 3 | `Chemins.test_chemin_dangereux_comme_nom_d_entree_du_zip`<br>`Chemins.test_chemin_dangereux_dans_le_manifeste` | rouge | rouge | n/a |
| X2 | client : plus comparé | `serveur/paquet_signe.py` | A10 | 1 | `Versions.test_autre_client` | rouge | rouge | n/a |
| X3 | version.json : plus comparé au manifeste | `serveur/paquet_signe.py` | A10 | 2 | `ContenuDeLArchive.test_version_divergente_entre_manifeste_et_version_json`<br>`ContenuDeLArchive.test_version_json_illisible_ou_sans_version` | rouge | rouge | n/a |
| X4 | JSON : clés en double admises | `serveur/paquet_signe.py` | A13 | 1 | `ContenuDeLArchive.test_version_json_illisible_ou_sans_version` | rouge | rouge | n/a |
| X5 | JSON : NaN admis | `serveur/paquet_signe.py` | A13 | 1 | `ContenuDeLArchive.test_version_json_illisible_ou_sans_version` | rouge | rouge | n/a |
| X6 | JSON : BOM admis | `serveur/paquet_signe.py` | A13 | 1 | `LectureDuManifeste.test_le_bom_est_refuse_par_notre_garde_et_non_par_json` | rouge | rouge | n/a |
| X7 | taille : bool admis comme entier | `serveur/paquet_signe.py` | A13 | 1 | `LectureDuManifeste.test_refus_signes_de_forme` | rouge | rouge | n/a |
| X8 | entrée chiffrée admise | `serveur/paquet_signe.py` | A12 | 1 | `ContenuDeLArchive.test_entree_chiffree_refusee` | rouge | rouge | n/a |
| X9 | compression bzip2 admise | `serveur/paquet_signe.py` | A12 | 1 | `ContenuDeLArchive.test_compression_bzip2_refusee` | rouge | rouge | n/a |
| X10 | dossiers racine multiples admis | `serveur/paquet_signe.py` | ajout | 1 | `Chemins.test_plusieurs_dossiers_racine_refuses` | rouge | rouge | n/a |
| X11 | version : match au lieu de fullmatch | `serveur/paquet_signe.py` | A9 | 3 | `AnalyseDesVersions.test_formes_invalides`<br>`Versions.test_installee_inconnue_ou_illisible` | rouge | rouge | n/a |
| X12 | format inconnu admis | `serveur/paquet_signe.py` | A13 | 2 | `LectureDuManifeste.test_format_futur_reconnu_comme_inconnu_meme_avec_d_autres_cles`<br>`LectureDuManifeste.test_type_et_format_inconnus` | rouge | rouge | n/a |
| X13 | type inconnu admis | `serveur/paquet_signe.py` | A13 | 2 | `LectureDuManifeste.test_type_et_format_inconnus`<br>`LectureDuManifeste.test_un_manifeste_de_licence_n_est_pas_un_manifeste_de_mise_a_jour` | rouge | rouge | n/a |
| X14 | plafond de 1 Mio du manifeste retiré | `serveur/paquet_signe.py` | A13 | 1 | `LectureDuManifeste.test_trop_grand_avant_tout_calcul` | rouge | rouge | n/a |
| X15 | taille de fichier du zip non comparée au manifeste | `serveur/paquet_signe.py` | A12 | 1 | `ContenuDeLArchive.test_taille_declaree_dans_le_zip_differente_de_celle_du_manifeste` | rouge | rouge | n/a |
| X16 | contrôle de nombre de fichiers retiré | `serveur/paquet_signe.py` | plafond | 1 | `Chemins.test_plafond_du_nombre_de_fichiers` | rouge | rouge | n/a |
| X17 | la signature de l'outil n'est plus revérifiée | `outils/signer-paquet.py` | revérification | 1 | `PaquetSigne.test_a15_la_reverification_efface_ce_qu_elle_refuse` | rouge | rouge | n/a |
| X18 | generer-cle : plus de refus sous la racine du dépôt | `outils/signer-paquet.py` | A14 | 2 | `PaquetSigne.test_a14_generer_cle_refuse_un_dossier_sous_la_racine_du_depot`<br>`PaquetSigne.test_a14_un_lien_vers_le_depot_est_resolu_avant_la_comparaison` | rouge | rouge | n/a |
| X19 | generer-cle : phrase courte admise | `outils/signer-paquet.py` | A14 | 1 | `PaquetSigne.test_a14_phrase_trop_courte_refusee_sans_rien_ecrire` | rouge | rouge | n/a |
| X20 | signer : plus de refus de clé sous la racine | `outils/signer-paquet.py` | A15 | 1 | `PaquetSigne.test_a15_cle_sous_la_racine_du_depot` | rouge | rouge | n/a |
| X21 | signer : schéma du client non comparé | `outils/signer-paquet.py` | A15 | 1 | `PaquetSigne.test_a15_schema_different_de_celui_du_client` | rouge | rouge | n/a |
| X22 | signer : écrase un manifeste existant | `outils/signer-paquet.py` | A15 | 1 | `PaquetSigne.test_a15_manifeste_deja_present_n_est_jamais_ecrase` | rouge | rouge | n/a |
| X23 | generer-cle : écriture sans O_EXCL | `outils/signer-paquet.py` | A14 | 2 | `EcritureExclusive.test_ne_remplace_jamais_un_fichier_existant`<br>`EcritureExclusive.test_un_lien_symbolique_pendant_n_est_pas_suivi` | rouge | rouge | n/a |
| X24 | generer-cle : mode 0644 | `outils/signer-paquet.py` | A14 | 1 | `PaquetSigne.test_a14_la_cle_est_ecrite_en_0600` | rouge | rouge | n/a |
| X25 | generer-cle : clé non chiffrée | `outils/signer-paquet.py` | A14 | 1 | `test_signer_paquet.PaquetSigne` | rouge | rouge | n/a |
| X16b | plafond de la somme des tailles retiré | `serveur/paquet_signe.py` | plafond | 1 | `Chemins.test_plafond_de_la_somme_des_tailles` | rouge | rouge | n/a |
| X26 | version.json démesuré chargé en mémoire | `serveur/paquet_signe.py` | durcissement | 1 | `ContenuDeLArchive.test_version_json_demesure_refuse_sans_etre_charge_en_memoire` | rouge | rouge | n/a |
| X27 | signer : revérification sans effacement | `outils/signer-paquet.py` | A15 | 1 | `PaquetSigne.test_a15_la_reverification_efface_ce_qu_elle_refuse` | rouge | rouge | n/a |


Lecture : « rouge » = au moins un test échoue avec la mutation **et** les mêmes
tests passent une fois le fichier restauré. « n/a » = non jouée dans cette
configuration. Les mutations X1 à X27 sont des gardes que le contrat ne numérote
pas (plafonds, JSON strict, durcissements, outil) : elles ont été jouées parce
qu'une garde non mise en échec ne garde rien.

## 4. Premier passage : ce que les mutations ont révélé

Au premier passage, **44 mutations sur 52 étaient concluantes** ; huit
**survivaient**, c'est-à-dire que le code muté passait tous les tests. Chacune a
donné lieu à un test, puis a été rejouée. Aucune ne tenait à un défaut du code
livré ; toutes révélaient un test absent ou trop large.

| Survivante | Pourquoi elle survivait | Correction |
|---|---|---|
| M17a (doublon à la casse près du **manifeste**) | le zip de test contenait les deux graphies, et la garde du **zip** (même code) arrêtait avant | `test_doublon_du_manifeste_refuse_avant_de_lire_l_archive` : le zip n'a qu'une graphie, seul l'étape 4 peut dire `CHEMIN_EN_DOUBLE` |
| X5 (NaN admis dans le JSON) | tout champ du manifeste est typé : un `NaN` y est refusé par le schéma, la garde `parse_constant` était masquée | `version.json` du paquet porte `{"version": "1.2.0", "x": NaN}` : seul le JSON strict le refuse |
| X6 (BOM admis) | `json.loads` refuse déjà un BOM dans une chaîne | `test_le_bom_est_refuse_par_notre_garde_et_non_par_json` vérifie que c'est le message de **notre** garde qui parle |
| X15 (taille du zip non comparée au manifeste) | la lecture bornée constatait ensuite le même écart | les tests exigent le détail « taille déclarée » (refus **avant** toute lecture) ; le test de bombe exige « lecture impossible » |
| X16 (plafond de 10 000 fichiers) | aucun test | `test_plafond_du_nombre_de_fichiers`, aux deux bornes |
| X17 (revérification de l'outil retirée) | aucun test ne signait une archive que le cabinet refuserait | `test_a15_la_reverification_efface_ce_qu_elle_refuse` (lien symbolique) |
| X22 (refus d'un manifeste existant) | `O_EXCL` refusait de toute façon, avec le même mot | le test exige le message de la **première** garde (avant la phrase de passe) |
| X23 (`O_EXCL` retiré de l'écriture de la clé) | un `lexists` en amont refusait avant | `EcritureExclusive` : test direct de `_ecrire_exclusif` sur un fichier existant et sur un lien |

Trois mutations ont ensuite été ajoutées pour les gardes introduites ou
précisées pendant ce passage : X16b (plafond de la somme des tailles), X26
(`version.json` démesuré, qui ne doit pas être chargé en mémoire) et X27
(l'outil n'efface plus ce que la revérification refuse).

## 5. Constats de conception relevés en jouant les mutations

- **Plafonds jamais atteints par l'outil.** Le manifeste que l'outil écrit
  (`indent=2`) pèse environ 190 octets par fichier : le plafond de 1 Mio du
  manifeste est atteint vers 5 500 fichiers, bien avant le plafond de 10 000
  fichiers du contrat. Les deux gardes sont indépendantes et testées chacune ;
  le test du plafond de fichiers fabrique un manifeste compact (~1 000 000
  octets pour 10 000 entrées). Rien à corriger à l'échelle d'un paquet de
  28 fichiers.
- **Gardes redondantes par construction.** Comparer `file_size` au manifeste
  (X15), `O_EXCL` derrière le `lexists` (X22, X23), le BOM derrière
  `json.loads` (X6) : chacune double une autre. Elles sont gardées (la première
  épargne une lecture, la seconde ferme une fenêtre de concurrence, la dernière ne
  dépend pas d'un comportement de bibliothèque) et chacune a désormais son test.
- **Pas de mutation équivalente restante.**

## 6. A19 — la garde « stdlib seule » étendue

Copie jetable (`mutF`) ; l'import ajouté en tête de `serveur/paquet_signe.py` :

```
(témoin, copie intacte)           python3 -m unittest tests.test_serveur  ->  OK (104 tests)
(mutation : import cryptography)  python3 -m unittest tests.test_serveur  ->  FAILED (failures=1)
    FAIL: test_aucun_import_hors_bibliotheque_standard_ajoute (…) (module='paquet_signe.py')
(restauré)                        python3 -m unittest tests.test_serveur  ->  OK (104 tests)
```

Joué sous Python 3.14.3 (aucun 3.13 sur ce poste) ; la CI le rejoue sous 3.13.
`generer_autorite.py`, qui importe `cryptography`, reste exempté **par son nom**, et
`test_la_garde_stdlib_mord_et_l_exemption_est_justifiee` vérifie que l'exemption
est justifiée (le module importe bien `cryptography`) et que la garde voit un
import tiers sous ses quatre formes (`import x`, `import a, x.y`, `from x import y`,
import dans une fonction).

## 7. Ce que ces mises en échec ne couvrent pas

- Les **gardes qui dépendent du système** : `orig_filename` modifié par `zipfile`
  sous Windows (`a\b` réécrit `a/b`). M15 est mise en échec sur n'importe quel
  système par une entrée simulée dont `orig_filename` et `filename` diffèrent, et
  par un vrai nom à NUL ; la CI Windows en joue le cas réel.
- La **correction cryptographique** du vérificateur n'est pas prouvée par des
  mutations mais par les cinq vecteurs de la RFC 8032, le croisement avec
  `cryptography` (600 cas aléatoires par exécution) et les falsifications
  fabriquées pour que l'équation tienne (S + L, clé et R d'ordre faible).
