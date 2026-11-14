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
