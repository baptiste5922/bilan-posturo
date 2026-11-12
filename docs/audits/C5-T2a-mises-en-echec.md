# C5-T2a — Mises en échec M1 à M20

**Contrat :** `docs/contrats/C5-T2.md` §9 (« Mises en échec C5-T2a »), critère A21.
**Dépôt éprouvé :** `7fa6cd7` (tête de `c5-t2a-application`), rejoué en entier le
12 novembre 2026.

## Méthode

- **Copie jetable, jamais le dépôt.** `git ls-files -z` copie les seuls fichiers
  suivis (aucune donnée du cabinet : ni `config.json`, ni clés, ni journaux, ni
  `bilans/`), puis `git init` + un commit, **sans `origin`**. Une seconde copie
  intacte sert de source de restauration.
- **Un témoin par mutation et par mode.** Les mêmes tests sont d'abord joués sur la
  copie non mutée : ils doivent être **verts** (colonne « Témoin »). Puis la mutation
  est appliquée (une ancre qui n'apparaît pas exactement une fois arrête le
  harnais) et les mêmes tests doivent devenir **rouges**.
- **Restauration par `cp`**, puis vérification de l'empreinte SHA-256 du fichier muté
  contre celle d'avant : le harnais s'arrête sur une restauration infidèle.
- **Deux modes** : `python3` et `python3 -O` (où un `assert` nu disparaîtrait),
  avec `-W error::ResourceWarning` comme en intégration continue.
- Les tests rouges nommés ci-dessous sont ceux que la mutation fait échouer ; le
  contrat en exigeait au moins un par mutation.

Le harnais lui-même (`mutations.py`, hors dépôt) applique chaque mutation par
remplacement exact de texte ; les mutations sont décrites ci-dessous.

## Mutations

| # | Mutation | Où | Doit rougir (contrat) |
|---|---|---|---|
| M1 | `lire_cles_installees` lit `mise-a-jour/prepare/serveur/cles_publication.json` | `maj.py:lire_cles_installees` | A9 |
| M2 | relecture après extraction supprimée (`if False:` à la place de la comparaison) | `maj.py:extraire` | test d'altération injectée |
| M3 | liste blanche retirée (seule l'exclusion reste) | `maj.py:controler_destinations` | A7 |
| M4 | exclusion `formulaire/images/cabinet` retirée de `CHEMINS_REFUSES` | `maj.py` | A7 (deux casses) |
| M5 | `controler_longueurs` n'est plus appelé | `maj.py:controler` | A11 |
| M6 | extraction dans `<racine>/extrait-direct` au lieu de `mise-a-jour/prepare` | `maj.py:extraire` | A6 |
| M7 | `journaliser_technique(evenement, str(libre))` | `maj.py:tracer` | A12, A18 |
| M8 | `sante_repond` rend toujours vrai | `maj.py:sante_repond` | A1 |
| M9 | `poser_fichiers` ne compare plus l'empreinte avant de copier | `maj.py:poser_fichiers` | A4 |
| M10 | `reprendre` tient `bascule` pour achevée | `maj.py:reprendre` | A4 |
| M11 | `decider_arret` ignore `depots_en_cours` | `serveur.py:decider_arret` | A2, A14 |
| M12 | `ecartees` jamais consultée | `maj.py:controler` | A1 (second `appliquer`) |
| M13 | auto-contrôle supprimé de `basculer` | `maj.py:basculer` | A1 (variante `maj.py`) |
| M14 | `archive.extractall(prepare)` ajouté dans `extraire` | `maj.py:extraire` | A18 |
| M15 | verrou retiré (`flock`/`msvcrt.locking` supprimés) | `maj.py:verrou` | A15 |
| M16 | contrôle du schéma modifié sur place retiré (`if False and …`) | `maj.py:controler` | A10 |
| M17 | `pilote.arreter_de_force()` à la place de `demander_arret` dans `appliquer` | `maj.py:appliquer` | A3 (`ARRET motif=mise-a-jour` absent) |
| M18 | `PAQUET_INCOMPLET` retiré (`if False:`) | `maj.py:controler` | A6 (paquet sans pièce indispensable) |
| M19 | `import paquet_signe` dans le corps de `effacer_pycache` | `maj.py` | A18 |
| M20 | `lire_etat_maj` recopie `etat.json` sans valider | `serveur.py:lire_etat_maj` | A13 |

## Résultat

Quarante exécutions (20 mutations × 2 modes) : **témoin vert 40/40, mutation
rouge 40/40, aucune mutation survivante.**

| # | Mutation | Mode | Témoin (copie intacte) | Mutée | Tests rouges |
|---|---|---|---|---|---|
| M1 | clés lues dans prepare/serveur/cles_publication.json | python3 | vert | rouge | test_la_cle_du_paquet_sert_au_paquet_suivant_seulement (ClesInstallees)<br>test_n_plus_2_signe_par_b_avant_n_plus_1_est_refuse (ClesInstallees)<br>test_paquet_signe_par_b_dont_la_liste_embarquee_contient_b (ClesInstallees)<br>test_un_paquet_ne_se_donne_pas_confiance_a_lui_meme (Rotation)<br>test_un_reste_de_prepare_ne_donne_pas_confiance (ClesInstallees) |
| M1 | clés lues dans prepare/serveur/cles_publication.json | python3 -O | vert | rouge | test_la_cle_du_paquet_sert_au_paquet_suivant_seulement (ClesInstallees)<br>test_n_plus_2_signe_par_b_avant_n_plus_1_est_refuse (ClesInstallees)<br>test_paquet_signe_par_b_dont_la_liste_embarquee_contient_b (ClesInstallees)<br>test_un_paquet_ne_se_donne_pas_confiance_a_lui_meme (Rotation)<br>test_un_reste_de_prepare_ne_donne_pas_confiance (ClesInstallees) |
| M2 | relecture après extraction supprimée | python3 | vert | rouge | test_extraction_alteree_laisse_prepare_vide (RefusSansEcriture) |
| M2 | relecture après extraction supprimée | python3 -O | vert | rouge | test_extraction_alteree_laisse_prepare_vide (RefusSansEcriture) |
| M3 | liste blanche retirée | python3 | vert | rouge | test_chemins_proteges_refuses_derriere_une_signature_valide (ListeBlanche) |
| M3 | liste blanche retirée | python3 -O | vert | rouge | test_chemins_proteges_refuses_derriere_une_signature_valide (ListeBlanche) |
| M4 | exclusion formulaire/images/cabinet/ retirée | python3 | vert | rouge | test_chemins_proteges_refuses_derriere_une_signature_valide (ListeBlanche) |
| M4 | exclusion formulaire/images/cabinet/ retirée | python3 -O | vert | rouge | test_chemins_proteges_refuses_derriere_une_signature_valide (ListeBlanche) |
| M5 | contrôle MAX_PATH retiré | python3 | vert | rouge | test_racine_trop_longue_pour_la_sauvegarde_seulement (MaxPath) |
| M5 | contrôle MAX_PATH retiré | python3 -O | vert | rouge | test_racine_trop_longue_pour_la_sauvegarde_seulement (MaxPath) |
| M6 | extraction écrite directement sous la racine | python3 | vert | rouge | test_extraction_alteree_laisse_prepare_vide (RefusSansEcriture)<br>test_extraction_ecrit_uniquement_sous_prepare (ExtractionSansExtract)<br>test_une_entree_dont_le_nom_a_change_est_refusee (ExtractionSansExtract) |
| M6 | extraction écrite directement sous la racine | python3 -O | vert | rouge | test_extraction_alteree_laisse_prepare_vide (RefusSansEcriture)<br>test_extraction_ecrit_uniquement_sous_prepare (ExtractionSansExtract)<br>test_une_entree_dont_le_nom_a_change_est_refusee (ExtractionSansExtract) |
| M7 | str(erreur) passé à journaliser_technique | python3 | vert | rouge | test_la_garde_des_traces_mord (GardesStatiques)<br>test_technique_log_ne_recoit_que_detail_maj (GardesStatiques)<br>test_un_refus_ecrit_le_detail_dans_le_journal_nominatif_seulement (Traces) |
| M7 | str(erreur) passé à journaliser_technique | python3 -O | vert | rouge | test_la_garde_des_traces_mord (GardesStatiques)<br>test_technique_log_ne_recoit_que_detail_maj (GardesStatiques)<br>test_un_refus_ecrit_le_detail_dans_le_journal_nominatif_seulement (Traces) |
| M8 | sonde de santé qui rend toujours vrai | python3 | vert | rouge | test_quatre_variantes_cassees_reviennent_seules (Retour) |
| M8 | sonde de santé qui rend toujours vrai | python3 -O | vert | rouge | test_quatre_variantes_cassees_reviennent_seules (Retour) |
| M9 | bascule non idempotente (copie sans comparer l'empreinte) | python3 | vert | rouge | test_coupure_pendant_le_retour_puis_deux_reprises (Interruption)<br>test_pose_idempotente (PoseEtRetour)<br>test_reprise_rejouee_converge_et_ne_refait_que_le_reste (PoseEtRetour) |
| M9 | bascule non idempotente (copie sans comparer l'empreinte) | python3 -O | vert | rouge | test_coupure_pendant_le_retour_puis_deux_reprises (Interruption)<br>test_pose_idempotente (PoseEtRetour)<br>test_reprise_rejouee_converge_et_ne_refait_que_le_reste (PoseEtRetour) |
| M10 | reprendre tient bascule pour achevée | python3 | vert | rouge | test_coupure_pendant_la_bascule (Interruption)<br>test_reprise_depuis_une_bascule_interrompue (PoseEtRetour)<br>test_reprise_rejouee_converge_et_ne_refait_que_le_reste (PoseEtRetour) |
| M10 | reprendre tient bascule pour achevée | python3 -O | vert | rouge | test_coupure_pendant_la_bascule (Interruption)<br>test_reprise_depuis_une_bascule_interrompue (PoseEtRetour)<br>test_reprise_rejouee_converge_et_ne_refait_que_le_reste (PoseEtRetour) |
| M11 | decider_arret ignore depots_en_cours | python3 | vert | rouge | test_table (DeciderArret)<br>test_un_depot_commence_refuse_l_arret_et_aboutit (DepotEnCours) |
| M11 | decider_arret ignore depots_en_cours | python3 -O | vert | rouge | test_table (DeciderArret)<br>test_un_depot_commence_refuse_l_arret_et_aboutit (DepotEnCours) |
| M12 | ecartees jamais consultée | python3 | vert | rouge | test_quatre_variantes_cassees_reviennent_seules (Retour)<br>test_version_ecartee (RefusSansEcriture) |
| M12 | ecartees jamais consultée | python3 -O | vert | rouge | test_quatre_variantes_cassees_reviennent_seules (Retour)<br>test_version_ecartee (RefusSansEcriture) |
| M13 | auto-contrôle supprimé | python3 | vert | rouge | test_quatre_variantes_cassees_reviennent_seules (Retour) |
| M13 | auto-contrôle supprimé | python3 -O | vert | rouge | test_quatre_variantes_cassees_reviennent_seules (Retour) |
| M14 | extractall dans maj.py | python3 | vert | rouge | test_ni_extract_ni_shell_ni_outil_d_extraction (GardesStatiques) |
| M14 | extractall dans maj.py | python3 -O | vert | rouge | test_ni_extract_ni_shell_ni_outil_d_extraction (GardesStatiques) |
| M15 | verrou retiré | python3 | vert | rouge | test_verrou_pris_deux_fois_dans_un_processus (Verrou)<br>test_verrou_tenu_par_un_autre_processus (Verrou) |
| M15 | verrou retiré | python3 -O | vert | rouge | test_verrou_pris_deux_fois_dans_un_processus (Verrou)<br>test_verrou_tenu_par_un_autre_processus (Verrou) |
| M16 | contrôle du schéma modifié retiré | python3 | vert | rouge | test_schema_retouche_sur_place_est_refuse (SchemaModifie) |
| M16 | contrôle du schéma modifié retiré | python3 -O | vert | rouge | test_schema_retouche_sur_place_est_refuse (SchemaModifie) |
| M17 | arrêt forcé dans le chemin nominal | python3 | vert | rouge | test_le_cabinet_survit_a_trois_montees (TroisMontees) |
| M17 | arrêt forcé dans le chemin nominal | python3 -O | vert | rouge | test_le_cabinet_survit_a_trois_montees (TroisMontees) |
| M18 | PAQUET_INCOMPLET retiré | python3 | vert | rouge | test_paquet_incomplet (RefusSansEcriture) |
| M18 | PAQUET_INCOMPLET retiré | python3 -O | vert | rouge | test_paquet_incomplet (RefusSansEcriture) |
| M19 | import paresseux de paquet_signe dans une fonction | python3 | vert | rouge | test_aucun_import_hors_du_niveau_module (GardesStatiques) |
| M19 | import paresseux de paquet_signe dans une fonction | python3 -O | vert | rouge | test_aucun_import_hors_du_niveau_module (GardesStatiques) |
| M20 | /etat recopie etat.json sans valider | python3 | vert | rouge | test_construire_etat_ne_recopie_pas_un_fichier_hostile (EtatDeLaMiseAJour)<br>test_illisible_et_rien_ailleurs (EtatDeLaMiseAJour) |
| M20 | /etat recopie etat.json sans valider | python3 -O | vert | rouge | test_construire_etat_ne_recopie_pas_un_fichier_hostile (EtatDeLaMiseAJour)<br>test_illisible_et_rien_ailleurs (EtatDeLaMiseAJour) |

## Ce que ces mutations n'éprouvent pas

- **Windows.** Aucune mutation ne vise `_proteger_windows`, `PiloteTachePlanifiee` ni
  `icacls` : elles ne s'éprouvent que sur le vrai système, par
  `tests/test_maj_windows.py` (exécuté, non sauté, en intégration continue sous
  `windows-latest`) et par la fiche `docs/essais/C5-T2-windows.md`.
- **Mutations de la garde elle-même.** Chaque garde statique (imports, appels
  interdits, traces) est mise en échec par un test dédié sur des sources fautives
  (`GardesStatiques.test_la_garde_*_mord`), indépendamment des M7, M14 et M19.
- **Un défaut intermittent capturé, non relancé.** Les trois premiers essais du bout
  en bout ont montré un serveur non relancé après l'arrêt concerté (tâche en
  `IgnoreNew` et ancienne instance qui finit de quitter) ; la cause est comprise et
  corrigée (erratum 6 du contrat : répit de 1 s et relance toutes les 5 s tant que
  `/sante` est muette), pas masquée par un nouvel essai.
