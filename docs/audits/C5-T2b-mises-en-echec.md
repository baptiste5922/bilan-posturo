# C5-T2b — mises en échec

Date : 14 novembre 2026. Python 3.14.3 (macOS). Critère B25 du contrat (§14.12) ; mutations N1 à N18 du §14.13, plus
N19 à N28 que l'implémenteur a ajoutées pour les gardes qu'il a écrites, dont N27 (une adresse
à segment de 32 hexadécimaux versionnée : le test rougit sans que la sortie contienne le
segment, critère B21) et N28 (l'adresse écrite dans `journal.log`), et N3b (N3 rejouée sur le
seul test qu'elle visait).

**Méthode.** Une copie du dépôt par `git ls-files -z` (jamais `cp -r` ni `tar` : la
racine porte les données réelles d'un cabinet), `git init` sans `origin` dans la copie
(les tests lisent `git ls-files`), puis pour chaque mutation : le texte visé doit se
trouver **exactement une fois** ; le fichier muté doit avoir une empreinte différente ;
les tests visés se jouent **en `python3` puis en `python3 -O`**, au premier échec
(`unittest -f`) ; le fichier est **restauré par `cp` depuis l'original gardé hors de la
copie, empreinte SHA-256 vérifiée** ; les mêmes tests se rejouent en entier, dans les deux
modes, **sur le fichier restauré (le témoin)**. Un harnais qui ne dirait jamais « vert »
ne prouverait rien : le témoin est ce qui montre qu'un rouge vient de la mutation.
Le dépôt réel n'a jamais été muté : toutes les mutations ont lieu dans la copie.

| # | Mutation | Fichier | Tests visés | python3 | python3 -O | Témoin (fichier restauré) |
|---|---|---|---|---|---|---|
| N1 | contexte TLS par défaut en CERT_NONE sans check_hostname | `serveur/maj.py` | `test_maj_reseau.Tls` | rouge (test_le_contexte_par_defaut_exige_la_verification, 0.8 s) | rouge (test_le_contexte_par_defaut_exige_la_verification, 1.1 s) | vert dans les deux modes (5 tests in 0.919s) |
| N2 | redirection vers http suivie | `serveur/maj.py` | `test_maj_reseau.Redirections` | rouge (test_une_redirection_vers_http_est_refusee, 1.4 s) | rouge (test_une_redirection_vers_http_est_refusee, 1.8 s) | vert dans les deux modes (12 tests in 1.228s) |
| N3 | read1(n) remplacé par un read() sans borne | `serveur/maj.py` | `test_maj_reseau.TaillesEtDelais` | rouge (test_aucun_fichier_partiel_apres_un_depassement_du_delai, 21.2 s) | rouge (test_aucun_fichier_partiel_apres_un_depassement_du_delai, 21.3 s) | vert dans les deux modes (12 tests in 6.187s) |
| N4 | proxy repris de l'environnement (HTTPS_PROXY) | `serveur/maj.py` | `test_maj_reseau.Proxy`, `test_maj.GardesStatiques` | rouge (test_l_environnement_n_est_jamais_lu, 1.8 s) | rouge (test_l_environnement_n_est_jamais_lu, 1.2 s) | vert dans les deux modes (17 tests in 1.215s) |
| N5 | en-tête X-Version ajouté à la requête | `serveur/maj.py` | `test_maj_reseau.DonneesEnvoyees` | rouge (test_aucune_version_aucun_identifiant_aucun_cookie, 1.5 s) | rouge (test_aucune_version_aucun_identifiant_aucun_cookie, 2.3 s) | vert dans les deux modes (8 tests in 2.304s) |
| N6 | dans_la_plage rend toujours vrai | `serveur/maj.py` | `test_maj_politique.DansLaPlage`, `test_maj_politique.Eligibilite`, `test_maj_bout_en_bout.VerifierEligibilite` | rouge (test_la_journee_est_le_complementaire, 0.2 s) | rouge (test_la_journee_est_le_complementaire, 0.1 s) | vert dans les deux modes (21 tests in 18.087s) |
| N7 | fréquence ignorée : le contrôle est toujours dû | `serveur/maj.py` | `test_maj_politique.Frequence` | rouge (test_une_minute_plus_tard_aucune_requete_six_heures_plus_tard_deux, 0.4 s) | rouge (test_une_minute_plus_tard_aucune_requete_six_heures_plus_tard_deux, 0.4 s) | vert dans les deux modes (8 tests in 0.288s) |
| N8 | archive téléchargée avant verifier_entete | `serveur/maj.py` | `test_maj_reseau.Entete`, `test_maj_politique.ArchiveJamaisDemandeeAvantLEntete` | rouge (test_client_different, 0.8 s) | rouge (test_client_different, 0.7 s) | vert dans les deux modes (14 tests in 1.948s) |
| N9 | test DESACTIVEE retiré (adresse vide traitée comme une adresse) | `serveur/maj.py` | `test_maj_politique.Desactive`, `test_maj_politique.SansConsole` | rouge (test_aucune_connexion_et_une_ligne_par_jour, 0.2 s) | rouge (test_aucune_connexion_et_une_ligne_par_jour, 0.2 s) | vert dans les deux modes (8 tests in 0.210s) |
| N10 | hors plage, demande envoyée avec demarrage=False et calme_secondes=0 | `serveur/maj.py` | `test_maj_politique.Eligibilite`, `test_maj_bout_en_bout.VerifierEligibilite` | rouge (test_hors_plage_apres_le_demarrage_calme_zero_et_demarrage_vrai, 0.3 s) | rouge (test_hors_plage_apres_le_demarrage_calme_zero_et_demarrage_vrai, 0.3 s) | vert dans les deux modes (16 tests in 17.369s) |
| N11 | filtre depuis_demarrage <= 900 retiré | `serveur/maj.py` | `test_maj_politique.Eligibilite`, `test_maj_bout_en_bout.VerifierEligibilite` | rouge (test_hors_plage_et_demarrage_depasse_c_est_le_meme_resultat, 0.3 s) | rouge (test_hors_plage_et_demarrage_depasse_c_est_le_meme_resultat, 0.4 s) | vert dans les deux modes (16 tests in 17.369s) |
| N12 | reprendre ignore arret_en_cours | `serveur/maj.py` | `test_maj.ArretEnCours`, `test_maj_bout_en_bout.VerifierMortApresAcceptation` | rouge (test_reprendre_avec_le_drapeau_relance_le_serveur_et_note_l_interruption, 0.8 s) | rouge (test_reprendre_avec_le_drapeau_relance_le_serveur_et_note_l_interruption, 0.8 s) | vert dans les deux modes (14 tests in 25.916s) |
| N13 | arret_en_cours remis à faux même si la santé reste muette | `serveur/maj.py` | `test_maj.ArretEnCours`, `test_maj_bout_en_bout.VerifierMortApresAcceptation` | rouge (test_reprendre_avec_une_sante_muette_garde_le_drapeau, 0.8 s) | rouge (test_reprendre_avec_une_sante_muette_garde_le_drapeau, 0.8 s) | vert dans les deux modes (14 tests in 25.916s) |
| N14 | filet d'appliquer_trio conditionné à `accepte` seul (état de T2a) | `serveur/maj.py` | `test_maj.ArretEnCours`, `test_maj_bout_en_bout.VerifierReponsesPerdues` | rouge (test_le_filet_joue_sur_le_drapeau_meme_sans_acceptation_lue, 0.5 s) | rouge (test_le_filet_joue_sur_le_drapeau_meme_sans_acceptation_lue, 0.5 s) | vert dans les deux modes (12 tests in 9.254s) |
| N15 | vidage avant protection dans preparer_dossier_prive | `serveur/maj.py` | `test_maj.ProtegerAvantDeVider` | rouge (test_l_ordre_est_protection_puis_vidage_puis_relecture, 0.2 s) | rouge (test_l_ordre_est_protection_puis_vidage_puis_relecture, 0.2 s) | vert dans les deux modes (3 tests in 0.093s) |
| N16 | échéance totale sans réduire le délai de socket, et read1 remplacé par read(TAILLE_BLOC) | `serveur/maj.py` | `test_maj_reseau.TaillesEtDelais` | rouge (test_un_octet_toutes_les_deux_dixiemes_depasse_le_delai_total, 44.3 s) | rouge (test_un_octet_toutes_les_deux_dixiemes_depasse_le_delai_total, 45.2 s) | vert dans les deux modes (12 tests in 6.187s) |
| N17 | limitation quotidienne des lignes retirée | `serveur/maj.py` | `test_maj_politique.Desactive`, `test_maj_politique.ConfigurationFausse`, `test_maj_politique.Eligibilite` | rouge (test_aucune_connexion_et_une_ligne_par_jour, 0.3 s) | rouge (test_aucune_connexion_et_une_ligne_par_jour, 0.2 s) | vert dans les deux modes (18 tests in 0.635s) |
| N18 | motif de test_confidentialite_publication porté à 33 hexadécimaux | `tests/test_confidentialite_publication.py` | `test_confidentialite_publication` | rouge (test_un_fichier_suivi_porteur_fait_rougir_sans_nommer_l_adresse, 0.2 s) | rouge (test_un_fichier_suivi_porteur_fait_rougir_sans_nommer_l_adresse, 0.2 s) | vert dans les deux modes (12 tests in 0.144s) |
| N19 | Content-Length annoncé trop grand : plus refusé avant lecture | `serveur/maj.py` | `test_maj_reseau.TaillesEtDelais` | rouge (test_une_taille_annoncee_trop_grande_est_refusee_sans_lire_le_corps, 14.3 s) | rouge (test_une_taille_annoncee_trop_grande_est_refusee_sans_lire_le_corps, 14.2 s) | vert dans les deux modes (12 tests in 6.187s) |
| N20 | verifier ne reprend plus rien (même désactivé) | `serveur/maj.py` | `test_maj_bout_en_bout.VerifierDesactiveEtCoupure`, `test_maj_bout_en_bout.VerifierMortApresAcceptation` | rouge (test_un_etat_a_la_bascule_est_defait_meme_sans_adresse, 5.1 s) | rouge (test_un_etat_a_la_bascule_est_defait_meme_sans_adresse, 5.0 s) | vert dans les deux modes (4 tests in 31.679s) |
| N21 | controle_le posé avant les téléchargements (donc même après un échec réseau) | `serveur/maj.py` | `test_maj_politique.Frequence` | rouge (test_apres_un_echec_reseau_le_controle_reste_du, 0.2 s) | rouge (test_apres_un_echec_reseau_le_controle_reste_du, 0.2 s) | vert dans les deux modes (8 tests in 0.288s) |
| N22 | verifier_paquet n'appelle plus verifier_entete | `serveur/paquet_signe.py` | `test_paquet_signe.EnteteSeul` | rouge (test_verifier_paquet_appelle_verifier_entete_en_premier, 0.1 s) | rouge (test_verifier_paquet_appelle_verifier_entete_en_premier, 0.1 s) | vert dans les deux modes (5 tests in 0.076s) |
| N23 | sixième redirection suivie (REDIRECTIONS_MAX + 1) | `serveur/maj.py` | `test_maj_reseau.Redirections` | rouge (test_six_redirections_sont_refusees, 0.9 s) | rouge (test_six_redirections_sont_refusees, 1.0 s) | vert dans les deux modes (12 tests in 1.228s) |
| N24 | tunnel du proxy oublié (connexion directe malgré la configuration) | `serveur/maj.py` | `test_maj_reseau.Proxy` | rouge (test_le_proxy_configure_recoit_un_connect_vers_la_cible, 10.6 s) | rouge (test_le_proxy_configure_recoit_un_connect_vers_la_cible, 10.6 s) | vert dans les deux modes (5 tests in 0.722s) |
| N25 | calme_minutes admet un booléen | `serveur/maj.py` | `test_maj_politique.LirePolitique` | rouge (test_chaque_forme_refusee_rend_son_code, 0.1 s) | rouge (test_chaque_forme_refusee_rend_son_code, 0.1 s) | vert dans les deux modes (7 tests in 0.001s) |
| N26 | maj_controle_le absent de /etat | `serveur/serveur.py` | `test_serveur` | rouge (test_construire_etat_porte_les_six_cles_dans_l_ordre, 0.3 s) | rouge (test_construire_etat_porte_les_six_cles_dans_l_ordre, 0.3 s) | vert dans les deux modes (164 tests in 1.858s) |
| N3b | N3 jouée sur le seul test visé (corps sans longueur au-delà de la limite) | `serveur/maj.py` | `test_maj_reseau.TaillesEtDelais.test_un_corps_sans_longueur_au_dela_de_la_limite` | rouge (test_un_corps_sans_longueur_au_dela_de_la_limite, 21.3 s) | rouge (test_un_corps_sans_longueur_au_dela_de_la_limite, 21.2 s) | vert dans les deux modes (1 test in 0.473s) |
| N27 | une adresse à segment de 32 hexadécimaux versionnée dans un fichier suivi (B21) | `docs/mise-a-jour.md` | `test_confidentialite_publication` | rouge (test_aucun_fichier_suivi_ne_porte_une_adresse, 0.1 s, **le segment n'apparaît pas dans la sortie**) | rouge (test_aucun_fichier_suivi_ne_porte_une_adresse, 0.1 s, **le segment n'apparaît pas dans la sortie**) | vert dans les deux modes (12 tests in 0.142s) |
| N28 | l'adresse (chemin compris) écrite dans le détail d'un refus réseau, donc dans journal.log (B21) | `serveur/maj.py` | `test_maj_politique.Frequence`, `test_maj_reseau.Entete` | rouge (test_apres_un_echec_reseau_le_controle_reste_du, 0.3 s) | rouge (test_apres_un_echec_reseau_le_controle_reste_du, 0.3 s) | vert dans les deux modes (17 tests in 1.472s) |

**Bilan : 29 mutations jouées, 29 font rougir leurs tests dans les deux modes, 29 témoins
verts dans les deux modes.**


## Ce que ces mutations ont appris

- **N3 et N16 ne mordent que si le faux hébergement goutte après le corps.** Avec un corps
  fini de 10 Mio, un `read()` sans borne lit tout, constate le dépassement et rend le même
  code que la version bornée : le test serait resté vert sous N3. Le faux hébergement
  (`tests/outils/faux_hebergement.py`, `corps_sans_longueur`) envoie donc 300 000 octets puis
  **un octet toutes les demi-secondes sans fermer** ; la version bornée rend
  `REPONSE_TROP_GRANDE` en moins de trois secondes, un `read()` reste suspendu une vingtaine de
  secondes. Relevé en écrivant la mutation, avant de la jouer ; **N3b** rejoue N3 sur ce seul
  test (le premier échec de N3 sur la classe entière est un autre test, par ordre
  alphabétique : sans N3b, rien ne dirait que le test visé mord).
- **Aucune tolérance** n'a été ajoutée à un comparateur pour faire passer un test. Les
  délais des essais passent en paramètre et sont courts (une à deux secondes) ; les bornes
  hautes (« moins de 3 s », « moins de 4 s ») laissent un facteur d'au moins deux sur la durée
  mesurée sur le poste de développement, et la CI (trois systèmes, Python 3.9 et 3.13) les a tenues.
- **Les tests de PowerShell sont mutés dans la suite elle-même.** `SecondeTache.
  test_la_garde_de_l_installateur_mord` et `test_la_garde_du_desinstallateur_mord` fabriquent
  seize textes fautifs (un `Start-Process` avant `-Verifier`, une tâche enregistrée sans
  condition, une limite de trois heures, un second `-RestartCount`, un pare-feu avant la
  mise à jour, etc.) et exigent un défaut pour chacun ; aucun lancement de PowerShell.
  De même, `GardesStatiques.test_la_garde_du_reseau_mord` (quatorze cas) pour B15 et
  `GardeDesTraces` pour les lignes `MAJ_*`.
- **Un harnais qui ne dirait jamais « vert » ne prouverait rien.** Chaque ligne a son
  témoin, dans les deux modes, sur le fichier restauré par `cp` et vérifié par empreinte.
- **Limites de cet exercice.** Rien de Windows réel n'y figure (ni `icacls`, ni
  `GetTickCount64`, ni les tâches planifiées) : c'est `tests.test_maj_windows`, joué sous
  `windows-latest` en administrateur, et la fiche d'essai, partie B. N1 à N26 mutent le code ;
  aucune ne mute `desinstaller-demarrage.ps1` autrement que par les seize textes ci-dessus.

## Suites complètes, après les mutations

Toutes les mutations ont été jouées **dans la copie** ; le dépôt n'a jamais été muté (`git status`
propre avant et après chaque lot). Les suites ci-dessous portent sur le dépôt restauré.

| Commande | Résultat |
|---|---|
| `python3 -W error::ResourceWarning -m unittest discover -s tests` (lancée en arrière-plan : voir ci-dessous) | **Ran 1089 tests in 424.862s — OK (skipped=23)** |
| `python3 -O -W error::ResourceWarning -m unittest …` au premier plan, en cinq tronçons de moins de 3 min : fichiers `test_maj`, `test_maj_politique`, `test_maj_reseau`, `test_paquet_signe`, `test_scripts_installation`, `test_confidentialite_publication`, `test_maj_windows`, `test_serveur` et dix autres fichiers hors bout en bout (961 tests, 74 s) ; `test_integration` et `test_confidentialite_prospect` (86 tests, 21 s) ; `test_maj_bout_en_bout` en trois lots (10 tests 138 s, 18 tests 115 s, 14 tests `-k Verifier` 74 s) | **961 + 86 + 10 + 18 + 14 = 1089 tests, tous OK sous `-O`** (même total que la suite normale) |
| `grep -nE "^\s*assert " serveur/maj.py serveur/paquet_signe.py` | vide (code de sortie 1) |
| `python3 -m pyflakes serveur/ tests/ outils/atelier/ outils/signer-paquet.py` | vide |
| `git diff main -- formulaire/` | vide : `npm test` et la preuve au pixel ne sont pas dues |

Avant la tâche : 905 tests, 19 sautés (`discover`, à `c4e9873`). `test_arret_journalise` y échouait,
**sans rapport avec le code** : la suite avait été lancée par `( … &)` d'un shell non interactif,
qui laisse SIGINT ignoré (piège connu du dépôt) ; lancée comme tâche de fond de l'outil
(`run_in_background`), la même suite est verte. Après : 1089 tests (+184), 23 sautés (+4 : les
quatre tests de `test_maj_windows` qui n'ont de sens que sous Windows).

Sous Python 3.9.6 (macOS, sans `cryptography`) : 427 tests, 0 échec, 69 sautés ; avec
`cryptography` installée dans un environnement jetable : `tests.test_maj_reseau` et
`tests.test_maj_politique` (107 tests) verts, `-W error::ResourceWarning`. La CI les rejoue
sur Linux, macOS et Windows (Python 3.9 et 3.13).

## Corrections de l'audit : N29 à N42 (17 novembre 2026)

L'audit (`docs/audits/C5-T2b.md`, CONFORME SOUS RÉSERVE : un Moyen, deux Faibles) a été corrigé
(errata 33 à 38 du contrat). Même méthode que ci-dessus : copie `git ls-files -z`, `git init`
sans `origin`, mutation vérifiée par empreinte, `python3` puis `python3 -O` au premier échec,
restauration par `cp` et empreinte relue, témoin rejoué en entier dans les deux modes. Les
fichiers `BilanPosturo_video*.mp4` de la racine, non suivis et qui ne sont pas à nous, n'entrent
pas dans la copie.

| # | Mutation | Fichier | Tests visés | python3 | python3 -O | Témoin (fichier restauré) |
|---|---|---|---|---|---|---|
| N29 | audit (a) : le minuteur d'échéance totale n'est jamais démarré | `serveur/maj.py` | `test_maj_reseau.TaillesEtDelais.test_des_en_tetes_au_goutte_a_goutte_depassent_le_delai_total` | rouge (test_des_en_tetes_au_goutte_a_goutte_depassent_le_delai_total, 21.0 s) | rouge (test_des_en_tetes_au_goutte_a_goutte_depassent_le_delai_total, 21.0 s) | vert dans les deux modes (1 test in 3.447s) |
| N30 | audit (a) : une échéance totale dépassée qui coupe un corps sans longueur passe pour un succès (plus de mémoire de l'échéance) | `serveur/maj.py` | `test_maj_reseau.TaillesEtDelais.test_un_corps_sans_longueur_coupe_par_l_echeance_n_est_pas_un_succes` | rouge (test_un_corps_sans_longueur_coupe_par_l_echeance_n_est_pas_un_succes, 2.0 s) | rouge (test_un_corps_sans_longueur_coupe_par_l_echeance_n_est_pas_un_succes, 1.4 s) | vert dans les deux modes (1 test in 1.736s) |
| N31 | audit (b) : la plage est rejugée sur l'heure d'entrée, non sur l'heure courante, avant l'arrêt | `serveur/maj.py` | `test_maj_politique.Eligibilite` | rouge (test_la_plage_se_rejuge_sur_l_heure_courante_juste_avant_l_arret, 0.5 s) | rouge (test_la_plage_se_rejuge_sur_l_heure_courante_juste_avant_l_arret, 0.5 s) | vert dans les deux modes (16 tests in 0.725s) |
| N32 | audit (b) : plus aucun rejugement juste avant la demande d'arrêt | `serveur/maj.py` | `test_maj_politique.Eligibilite` | rouge (test_la_plage_se_rejuge_sur_l_heure_courante_juste_avant_l_arret, 0.5 s) | rouge (test_la_plage_se_rejuge_sur_l_heure_courante_juste_avant_l_arret, 0.5 s) | vert dans les deux modes (16 tests in 0.725s) |
| N33 | audit (c) : plus de contrôle du temps restant avant la mort de la tâche | `serveur/maj.py` | `test_maj_politique.Eligibilite` | rouge (test_pas_assez_de_temps_pour_tout_finir_avant_la_mort_de_la_tache, 0.7 s) | rouge (test_pas_assez_de_temps_pour_tout_finir_avant_la_mort_de_la_tache, 0.7 s) | vert dans les deux modes (16 tests in 0.725s) |
| N34 | audit (c) : borne du temps restant décalée d'une seconde (>= au lieu de >) | `serveur/maj.py` | `test_maj_politique.Eligibilite` | rouge (test_juste_assez_de_temps_l_arret_est_demande, 0.4 s) | rouge (test_juste_assez_de_temps_l_arret_est_demande, 0.4 s) | vert dans les deux modes (16 tests in 0.725s) |
| N35 | audit (c) : le budget oublie le retour arrière | `serveur/maj.py` | `test_maj.Constantes`, `test_maj_politique.Eligibilite` | rouge (test_un_passage_tient_dans_l_heure_de_la_tache, 0.1 s) | rouge (test_un_passage_tient_dans_l_heure_de_la_tache, 0.1 s) | vert dans les deux modes (26 tests in 0.704s) |
| N36 | audit Faible 2 : une Location illisible n'est plus convertie (ValueError d'urljoin) | `serveur/maj.py` | `test_maj_reseau.Redirections` | rouge (test_une_location_malformee_est_une_redirection_refusee, 2.2 s) | rouge (test_une_location_malformee_est_une_redirection_refusee, 1.1 s) | vert dans les deux modes (14 tests in 1.838s) |
| N37 | audit Faible 2 : toute exception imprévue du client traduite seulement si OSError/HTTPException | `serveur/maj.py` | `test_maj_reseau.Redirections.test_aucune_exception_imprevue_ne_sort_de_telecharger` | rouge (test_aucune_exception_imprevue_ne_sort_de_telecharger, 0.6 s) | rouge (test_aucune_exception_imprevue_ne_sort_de_telecharger, 1.3 s) | vert dans les deux modes (1 test in 0.676s) |
| N38 | audit Faible 2 : le filet de verifier laisse passer l'exception (muette sous SYSTEM) | `serveur/maj.py` | `test_maj_politique.FiletDeLaTache` | rouge (test_le_verrou_est_relache_apres_l_exception, 0.2 s) | rouge (test_le_verrou_est_relache_apres_l_exception, 0.2 s) | vert dans les deux modes (5 tests in 0.153s) |
| N39 | audit Faible 3 : un échec après transfert d'archive laisse le contrôle dû | `serveur/maj.py` | `test_maj_politique.Frequence` | rouge (test_un_echec_apres_un_transfert_de_l_archive_attend_six_heures, 0.4 s) | rouge (test_un_echec_apres_un_transfert_de_l_archive_attend_six_heures, 0.4 s) | vert dans les deux modes (11 tests in 0.622s) |
| N40 | audit Faible 3 : _telecharger ne dit plus combien d'octets étaient arrivés | `serveur/maj.py` | `test_maj_reseau.TaillesEtDelais` | rouge (test_un_echec_apres_un_transfert_dit_combien_d_octets_etaient_arrives, 7.6 s) | rouge (test_un_echec_apres_un_transfert_dit_combien_d_octets_etaient_arrives, 7.3 s) | vert dans les deux modes (16 tests in 10.642s) |
| N41 | audit : MAJ_REFUSEE CLES_ABSENTES retirée de la limitation quotidienne | `serveur/maj.py` | `test_maj_politique.FiletDeLaTache`, `test_maj.Constantes` | rouge (test_cles_absentes_ne_fait_qu_une_ligne_par_jour, 0.2 s) | rouge (test_cles_absentes_ne_fait_qu_une_ligne_par_jour, 0.2 s) | vert dans les deux modes (15 tests in 0.143s) |
| N42 | audit : SSLKEYLOGFILE honoré par le contexte du client | `serveur/maj.py` | `test_maj_reseau.Tls` | rouge (test_sslkeylogfile_n_ecrit_jamais_les_cles_de_session, 0.8 s) | rouge (test_sslkeylogfile_n_ecrit_jamais_les_cles_de_session, 0.8 s) | vert dans les deux modes (6 tests in 1.958s) |

**Bilan : 14 mutations jouées, 14 font rougir leurs tests dans les deux modes, 14 témoins
verts dans les deux modes.**

**Deux mutations qui n'ont pas mordu du premier coup, et ce qu'on en a fait.**
- **N30** (première version : le client ne traduisait plus une erreur de socket en `DELAI_DEPASSE`
  après l'échéance) était **équivalente** : la boucle de lecture rejuge l'échéance à chaque bloc,
  donc le résultat ne changeait pas. Le vrai trou, trouvé en l'analysant : le minuteur coupe la
  socket, `read1` rend alors `b""` comme à la fin d'un corps sans longueur, et **un corps coupé
  passait pour complet**. Ajout d'une vérification explicite (`echu.is_set()` avant de rendre
  le succès) et d'un test où le minuteur gagne à coup sûr (il part à la moitié du délai de la
  socket) ; N30 a été redéfinie sur cette vérification et rougit.
- **N40** (`octets_recus` n'est plus posé) ne rougissait pas : les tests ne passaient que par
  le chemin des `Refus` levés par la boucle, jamais par celui d'une exception de socket au
  milieu du corps. Ajout de `faux.coupure_brutale` (réinitialisation TCP) et d'une assertion ;
  N40 rougit.

**Ce que ces mutations ne disent pas.** N34 éprouve la borne du temps restant à la seconde près
sur une horloge monotone injectée ; elle ne dit rien de la précision de `time.monotonic()` sous
Windows (15 ms) ni d'une mise en veille du PC pendant un passage. La marge de 300 s est faite
pour cela.

### Suites complètes après les corrections de l'audit

| Commande | Résultat |
|---|---|
| `python3 -W error::ResourceWarning -m unittest discover -s tests` (tâche de fond de l'outil) | **Ran 1108 tests in 427.791s — OK (skipped=23)** |
| `python3 -O -W error::ResourceWarning -m unittest …` au premier plan, mêmes cinq tronçons qu'auparavant | 980 + 86 + 10 + 18 + 14 = **1108 tests, tous OK sous `-O`** |
| `python3 -m pyflakes serveur/ tests/ outils/atelier/ outils/signer-paquet.py` | vide |
| `git diff main -- formulaire/` | vide |

+19 tests depuis la livraison (1089 → 1108). Aucun `serveur.py` ni `maj.py` n'a été lancé depuis le dépôt
pendant ces corrections, pas même pour `--help`.

## Corrections de la revue : N43 à N51 (17 novembre 2026)

La revue (`docs/revues/C5-T2b.md`, À CORRIGER : trois importants) a été corrigée (errata 40 à 43 du
contrat). Même méthode : copie `git ls-files -z`, `git init` sans `origin`, mutation vérifiée par
empreinte, `python3` puis `python3 -O` au premier échec, restauration par `cp` et empreinte relue,
témoin rejoué en entier dans les deux modes.

| # | Mutation | Fichier | Tests visés | python3 | python3 -O | Témoin (fichier restauré) |
|---|---|---|---|---|---|---|
| N43 | revue : --forcer n'ignore plus la fréquence de six heures | `serveur/maj.py` | `test_maj_politique.Frequence`, `test_maj_bout_en_bout.VerifierMontee.test_la_fiche_b5_se_deroule_avec_forcer` | rouge (test_forcer_fait_le_controle_meme_a_une_minute_d_ecart, 0.3 s) | rouge (test_forcer_fait_le_controle_meme_a_une_minute_d_ecart, 0.3 s) | vert dans les deux modes (16 tests in 12.096s) |
| N44 | revue : --forcer outrepasse la plage horaire | `serveur/maj.py` | `test_maj_politique.Frequence` | rouge (test_forcer_ne_change_ni_la_plage_ni_le_desactive_ni_la_signature, 0.4 s) | rouge (test_forcer_ne_change_ni_la_plage_ni_le_desactive_ni_la_signature, 0.4 s) | vert dans les deux modes (15 tests in 0.790s) |
| N45 | revue : --forcer outrepasse le client désactivé | `serveur/maj.py` | `test_maj_politique.Frequence` | rouge (test_forcer_ne_change_ni_la_plage_ni_le_desactive_ni_la_signature, 0.3 s) | rouge (test_forcer_ne_change_ni_la_plage_ni_le_desactive_ni_la_signature, 0.3 s) | vert dans les deux modes (15 tests in 0.764s) |
| N46 | revue : un disque plein pendant la réception redevient une panne du réseau | `serveur/maj.py` | `test_maj_reseau.TaillesEtDelais` | rouge (test_un_disque_plein_pendant_la_reception_est_une_ecriture_impossible, 7.4 s) | rouge (test_un_disque_plein_pendant_la_reception_est_une_ecriture_impossible, 7.1 s) | vert dans les deux modes (17 tests in 10.842s) |
| N47 | revue : TEMPS_INSUFFISANT sorti de la limitation quotidienne | `serveur/maj.py` | `test_maj_politique.Eligibilite`, `test_maj.Constantes` | rouge (test_temps_insuffisant_ne_fait_qu_une_ligne_par_jour, 0.8 s) | rouge (test_temps_insuffisant_ne_fait_qu_une_ligne_par_jour, 0.8 s) | vert dans les deux modes (28 tests in 1.022s) |
| N48 | revue : le report périmé reste dans l'état après un contrôle réussi | `serveur/maj.py` | `test_maj_politique.Frequence` | rouge (test_un_controle_reussi_efface_le_report_perime_de_l_etat, 0.5 s) | rouge (test_un_controle_reussi_efface_le_report_perime_de_l_etat, 0.5 s) | vert dans les deux modes (15 tests in 0.764s) |
| N49 | revue : un contrôle efface aussi le résultat d'une application | `serveur/maj.py` | `test_maj_politique.Frequence` | rouge (test_un_resultat_d_application_n_est_pas_efface_par_un_controle, 0.8 s) | rouge (test_un_resultat_d_application_n_est_pas_efface_par_un_controle, 0.8 s) | vert dans les deux modes (15 tests in 0.764s) |
| N50 | revue : un client désactivé ou hors plage sort de nouveau en code 3 | `serveur/maj.py` | `test_maj_politique.Desactive`, `test_maj.ChampsDeLEtat` | rouge (test_aucune_connexion_et_une_ligne_par_jour, 0.2 s) | rouge (test_aucune_connexion_et_une_ligne_par_jour, 0.2 s) | vert dans les deux modes (9 tests in 0.194s) |
| N51 | revue (mutant survivant de l'audit) : la décision d'entrée jugée sur l'heure figée | `serveur/maj.py` | `test_maj_politique.Eligibilite` | rouge (test_la_decision_d_entree_se_juge_sur_l_heure_courante_elle_aussi, 0.4 s) | rouge (test_la_decision_d_entree_se_juge_sur_l_heure_courante_elle_aussi, 0.4 s) | vert dans les deux modes (18 tests in 0.793s) |

**Bilan : 9 mutations jouées, 9 font rougir leurs tests dans les deux modes, 9 témoins
verts dans les deux modes.**

**N44 n'a pas mordu du premier coup.** Un `--forcer` qui outrepasse la plage laissait pourtant le
résultat inchangé (`HORS_PLAGE`, aucune demande d'arrêt) : le rejugement fait juste avant la
demande d'arrêt (erratum 34) rattrapait la faute, **après** l'extraction et la sauvegarde. Le test
vérifie maintenant que `prepare/` et `sauvegarde-neuve/` n'existent pas : c'est la décision
d'entrée qui doit retenir le passage, le rejugement n'est que la seconde barrière.
