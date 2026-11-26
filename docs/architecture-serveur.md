# Carte des deux gros fichiers du serveur

> **Objet.** Dire **où regarder** dans `serveur/serveur.py` (~3 060 l.) et
> `serveur/maj.py` (~2 600 l.) : ce que fait chaque section, quel état elle
> partage avec les autres, et quelles gardes de tests la couvrent.
>
> Ce document ne remplace ni le code, ni les contrats de `docs/contrats/`, qui
> font foi sur le *pourquoi* de chaque règle. Il répond à une seule question,
> celle qu'un relecteur se pose en ouvrant un fichier de 3 000 lignes :
> **« par quel bout le prendre ? »**

**Dernière mise à jour :** 24 novembre 2026
**Process :** Direct — documentation, aucun octet de code modifié hors les
index de sections ajoutés aux deux docstrings.

---

## 1. La convention de navigation

Les deux fichiers sont découpés par **bannières encadrées** :

```python
# --------------------------------------------------------------------------
# Journal technique (C4-T1) — non identifiant, conçu pour circuler
# --------------------------------------------------------------------------
```

Trois gestes suffisent donc :

| Pour | Chercher |
|---|---|
| Enchaîner les sections | `# ---` |
| Aller à une section | son titre, repris mot pour mot dans l'index du docstring |
| Savoir ce qu'il y a dedans | l'index en tête de fichier, ou ce document |

**Aucun numéro de ligne n'est écrit nulle part**, ni dans les index ni ici :
ils vieillissent à chaque commit, et un index faux coûte plus cher qu'un index
absent. Les tailles ci-dessous sont des ordres de grandeur, pour situer
l'effort de lecture, pas des mesures à maintenir.

---

## 2. `serveur/serveur.py` — les dix sections

| Section | Rôle | Tâche | Taille |
|---|---|---|---|
| En-tête et constantes | Chemins (`RACINE`, `FORMULAIRE`), **vocabulaires fermés** des journaux, bornes, `CONFIG_DEFAUT` | — | ~390 l. |
| Configuration et mots de passe | `charger_config`, PBKDF2, comparaison à temps constant | — | ~80 l. |
| Logo du cabinet (C2-T2) | Le logo, **le confinement des chemins**, **le refus de racine web**, et la saisie `--config` | C2-T2, C6-T6, C6-T7 | ~330 l. |
| Nom de fichier | `assainir_nom`, `chemin_libre`, écriture atomique | — | ~80 l. |
| Journal | `journal.log` nominatif : rotation, purge, fil périodique | C4-T2 | ~390 l. |
| Journal technique | `technique.log`, conçu pour circuler | C4-T1 | ~160 l. |
| Page d'état | `GET /etat`, et l'analyseur DER du certificat | C4-T3 | ~470 l. |
| Arrêt concerté | Compteurs de dépôts, demande d'arrêt, protection Windows du dossier réservé | C5-T2a | ~410 l. |
| Serveur | `ServeurBilan` (écoute, TLS) et `Gestionnaire` (auth, routes, dépôt) | C6-T5, C6-T8 | ~550 l. |
| Démarrage | `demarrer()` : **l'ordre des refus**, puis `serve_forever` | C6-T7 | ~200 l. |

### 2.1 Une bannière qui dit moins que son contenu

**Point à connaître avant toute relecture :** la section
**« Logo du cabinet (C2-T2) »** porte en réalité **quatre** sujets, parce
qu'elle a grossi au fil de trois tâches sans que son titre bouge :

1. **le logo** (C2-T2) — `forme_logo`, `valider_logo`, `FORME_CHEMIN_LOGO`,
   `FORME_LOGO_CLIENT` ;
2. **le confinement générique des chemins** (C6-T6) — `confiner_sous_racine`
   (dont `confiner_logo` est un **alias du même objet**),
   `confiner_fichier_servi`, `forme_comparable`, `forme_non_resolue`,
   `chemin_contient` ;
3. **le refus d'une racine web dangereuse** (C6-T7) —
   `motif_refus_racine_web` ;
4. **la saisie interactive** `--config` — `saisir_cabinet`,
   `definir_mot_de_passe`.

C'est la seule section du fichier dont le titre induit en erreur. Elle est
aussi la plus sensible : **trois des quatre sujets sont des barrières de
sécurité**. Chercher « confinement » n'y mène pas ; chercher
`confiner_sous_racine` si.

> Correction possible, non faite ici : ajouter trois sous-bannières
> (`# --- Confinement des chemins (C6-T6) ---`, etc.). C'est un changement de
> commentaires seul, sans risque — mais il sort du périmètre de ce document,
> qui ne touche pas au corps des fichiers.

### 2.2 Ce qu'il faut savoir d'autre, section par section

**En-tête et constantes.** C'est la section la plus importante du fichier pour
qui veut comprendre le reste, parce que **les tests s'en dérivent au lieu de
recopier des listes** : `EVENEMENTS_TECHNIQUES`, `ROUTES_TECHNIQUES`,
`MOTIFS_REFUS_DEPOT`, `MOTIFS_REFUS_LOGO`, `MOTIFS_REFUS_DEMARRAGE`,
`CLES_ETAT`, `ETAPES_MAJ`, `RESULTATS_MAJ`, `EXTENSIONS_SERVIES`. Modifier un
de ces ensembles modifie du même geste ce que les tests exigent.

On y trouve aussi deux `raise AssertionError` **explicites** au niveau du
module (cohérence de `EVENEMENT_ROTATION` et de `CHAMPS_ETAT_HORODATES`) :
jamais des `assert`, qui disparaîtraient sous `python -O`.

**Journal.** La section la plus longue du fichier après `Serveur`, et la plus
indépendante : rotation (5 Mo × 3), purge d'archive à la conservation
configurée, et un **fil de purge périodique** (6 h) dont la raison est écrite
dans les constantes — la promesse « au plus N mois » doit tenir même quand
plus rien ne s'écrit. `ROTATION` échappe de nécessité à `journaliser_technique`
(le verrou n'est pas réentrant : interblocage certain), d'où la constante
`EVENEMENT_ROTATION` dérivée une seule fois.

**Page d'état.** Contient un corps étranger : **l'analyseur DER de
certificat** (`_element_der` → `lire_certificat`, ~150 l.), écrit à la main
pour lire une date d'expiration et un `subjectAltName` sans `cryptography`.
C'est du code pur, sans entrée-sortie ni globale — et donc le meilleur
candidat à une extraction si l'on en venait là (§6).

**Arrêt concerté.** Contient elle aussi un corps étranger, sous sa propre
sous-bannière `# --- Protection du dossier réservé ---` : la lecture des
droits Windows (SDDL, `icacls`, SID). Ce bloc est **partagé avec `maj.py`**,
qui en importe quatre fonctions.

**Serveur.** Les deux classes, et rien d'autre. `ServeurBilan` porte l'écoute
(double pile IPv6, `SO_REUSEADDR` conditionné à `os.name`, `server_bind` qui
saute `getfqdn()`) et surtout `finish_request`, où la négociation TLS a lieu
**dans le fil de la connexion**, bornée par `DELAI_NEGOCIATION_TLS_SECONDES`
(C6-T8). `Gestionnaire` porte l'authentification, les cinq routes et le dépôt.

**Démarrage.** À lire **comme une séquence**, pas comme une fonction : l'ordre
des contrôles est lui-même une règle. Les interrupteurs de journal sont posés
*avant* tout refus possible (pour que la ligne de refus les respecte), le
refus de racine web est jugé *avant* `makedirs` et *avant* toute ouverture de
socket, et la ligne `ARRET` du `finally` s'écrit *après* `server_close()` —
« un journal ne doit jamais coûter autre chose que lui-même, et surtout pas la
disponibilité du port pour une relance ».

---

## 3. L'état global : le couplage réel du fichier

Dix globales de module sont **lues par plusieurs sections à la fois** : sept
sont posées au démarrage, les trois autres pendant le service. C'est elles, et
non la longueur, qui rendent le fichier difficile à couper.

| Globale | Posée par | Lue par |
|---|---|---|
| `VERSION_EN_COURS` | Démarrage | Page d'état |
| `DEMARRE_LE` | Démarrage | Page d'état |
| `DEMARRE_MONOTONIC` | Démarrage | Arrêt concerté |
| `DERNIER_DEPOT` | Serveur (`traiter_post`) | Page d'état |
| `DEPOTS_EN_COURS` | Arrêt concerté (`entrer_depot`/`sortir_depot`, appelés par `do_POST`) | Arrêt concerté |
| `DERNIERE_ACTIVITE` | Arrêt concerté (`marquer_activite`, appelée par les routes) | Arrêt concerté |
| `CERTIFICAT_CHARGE` | Démarrage | Page d'état |
| `JOURNAL_TECHNIQUE_ACTIF` | Démarrage | Journal technique, Page d'état |
| `CONSERVATION_JOURNAUX_MOIS` | Démarrage | Journal |
| `_PROTECTION_SIGNALEE` | Arrêt concerté | Arrêt concerté |

Lecture de ce tableau : **« Démarrage » écrit, « Page d'état » lit.** Six des
dix globales relient ces deux sections, qui sont aux deux extrémités du
fichier. Et trois relient « Serveur » à « Arrêt concerté ».

Conséquence pratique, pour toute modification : **changer une de ces valeurs
ailleurs qu'au démarrage touche la page d'état sans qu'aucun appel ne le
montre.** C'est pourquoi les tests de `PageEtat` remplacent ces globales par
`unittest.mock.patch.object` plutôt que de lancer un serveur.

---

## 4. `serveur/maj.py` — les dix-neuf sections

Fichier plus long, mais **plus facile à lire** : presque pas d'état global, des
sections courtes, et un enchaînement unique.

### 4.1 L'enchaînement, à lire de bas en haut du fichier

```
verifier  →  _controler_en_ligne   (manifeste, signature, puis archive)
          →  _appliquer_recu  →  appliquer_trio
                 →  controler, extraire, preparer_sauvegarde
                 →  demander_arret, adopter_sauvegarde
                 →  basculer  →  poser_fichiers, auto-contrôle
                              →  revenir_a_la_sauvegarde sur TOUT échec
```

`appliquer <archive>` (paquet posé à la main) entre au **même**
`appliquer_trio`, sans la partie réseau. C'est voulu : un seul chemin
d'application, donc un seul chemin à éprouver.

Deux endroits portent l'essentiel du soin :

- **`appliquer_trio`** — son `except BaseException` relance le serveur dès
  qu'une demande d'arrêt est **partie sans refus lu** (et pas seulement
  « acceptée » : les deux réponses peuvent se perdre). Sans ce filet, le
  serveur resterait arrêté, puisqu'il a quitté en code 0 et que la tâche
  planifiée ne le relancera pas.
- **`basculer`** — tout échec, `KeyboardInterrupt` compris, passe par
  `revenir_a_la_sauvegarde`. C'est la promesse « tout ce qui a été touché se
  défait », et elle tient en un seul endroit.

### 4.2 Les sections

| Section | Rôle | Taille |
|---|---|---|
| En-tête et constantes | Racine, imports des trois voisins, délais, tailles | ~70 l. |
| Vocabulaire | `CODES_MAJ` et les ensembles fermés ; exception `Refus` | ~170 l. |
| Traces | `detail_maj`, `tracer` — **les deux seules portes vers un journal** | ~90 l. |
| Fichiers | Lectures bornées, écritures exclusives, JSON | ~130 l. |
| Dossier réservé et verrou | `mise-a-jour/` réservé à SYSTEM ; exécution unique | ~200 l. |
| État sur disque | `etat.json`, lu aussi par `GET /etat` | ~100 l. |
| Destinations | Liste blanche des chemins qu'un paquet peut écrire (D6) | ~80 l. |
| Configuration, clés, version installée | Ce que le PC sait de lui-même | ~50 l. |
| Politique (C5-T2b) | Adresse, plage, calme, démarrage, proxy — **échec fermé** | ~170 l. |
| Contrôles préalables, extraction, sauvegarde | Tout ce qui peut refuser **avant** de toucher un fichier | ~270 l. |
| Pose des fichiers | La bascule, et le même code pour le retour | ~50 l. |
| Pilote du serveur | `schtasks` : arrêter, relancer, lire | ~40 l. |
| Santé | Attendre `/sante` après la relance | ~80 l. |
| Client HTTPS (C5-T2b) | `_telecharger` : trois GET, TLS vérifié, redirections `https` seules | ~220 l. |
| Arrêt concerté | Demander l'arrêt, et l'attendre | ~120 l. |
| Retour arrière | `revenir_a_la_sauvegarde`, `reprendre` | ~100 l. |
| Application | `basculer`, `appliquer_trio`, auto-contrôle | ~300 l. |
| Vérifier (C5-T2b) | Le point d'entrée de la tâche planifiée | ~260 l. |
| Ligne de commande | Les sept sous-commandes | ~60 l. |

### 4.3 Ce que `maj.py` emprunte à `serveur.py`

**Trente noms**, par `import serveur` (compte dérivé de l'AST, pas tenu à la
main : `ast.Attribute` dont la base est le nom `serveur`). Les principaux :

| Emprunt | Pourquoi |
|---|---|
| `journaliser`, `journaliser_technique`, `TECHNIQUE` | Écrire dans les mêmes journaux, avec les mêmes règles |
| `charger_config` | **Lire la configuration comme le serveur la lit**, jamais autrement |
| `ecrire_atomiquement_patient` | La même écriture, reprises comprises |
| `confiner_sous_racine`, `chemin_contient`, `forme_comparable`, `forme_non_resolue` | Le même confinement de chemins |
| `sddl_est_protege`, `sids_en_trop`, `lire_sddl_windows`, `decoder_sortie_icacls`, `dossier_reserve_de_confiance`, `SID_SYSTEME`, `SID_ADMINISTRATEURS` | Les mêmes droits Windows |
| `NOM_DOSSIER_MAJ`, `ETAT_MAJ`, `REPONSE_ARRET`, `MOTIF_HORODATAGE_MAJ`, `RESULTATS_MAJ` | Le dossier et le protocole d'arrêt, **nommés une seule fois** |

C'est la même règle que pour l'atelier : **dériver du code, jamais
transcrire.** Et c'est une dépendance **à sens unique** — `serveur.py`
n'importe de `maj.py` rien du tout ; il importe seulement `paquet_signe`, pour
emprunter la forme d'un numéro de version et la lecture JSON stricte.

**Mais cinq de ces trente emprunts sont des globales mutables** du serveur :
`CONFIG`, `JOURNAL`, `TECHNIQUE`, `JOURNAL_TECHNIQUE_ACTIF` et
`CONSERVATION_JOURNAUX_MOIS`. Le gestionnaire de contexte
`contexte_serveur(racine)` les **réécrit le temps d'une opération**, puis les
restaure dans un `finally`.

C'est délibéré, et c'est la seule façon d'obtenir ce qu'on veut — que `maj.py`
écrive dans les journaux du cabinet avec exactement les règles du serveur,
interrupteur et durée de conservation compris, **sans recopier une ligne de
leur logique**. Mais cela veut dire que **l'état global du §3 est partagé
entre deux modules**, et qu'il franchit déjà une frontière de fichier. À
retenir pour le §6 : le découpage ne buterait pas sur un couplage interne à
`serveur.py`, mais sur un couplage qui sort déjà de lui.

---

## 5. Les gardes de tests, par section

C'est la partie que ce document ajoute vraiment : savoir **ce qui tombe** si
l'on touche à une section.

### 5.1 `serveur.py`

| Section | Gardes principales |
|---|---|
| En-tête / vocabulaires | `test_serveur.py::VocabulaireDeLaMiseAJour` (dont **aucun jeton n'est préfixe d'un autre**), `JournalTechnique` |
| Configuration, mots de passe | `test_serveur.py::MotDePasse`, `ConfigurationCabinet` ; `test_identite_absente.py` |
| Logo (et confinement) | `test_logo.py` (forme, confinement, casse Windows, défaut fermé, logo au démarrage) ; `test_liens_servis.py::ConfinementServi`, `ToleranceDeLaCasse`, `LiensServis`, `JonctionsReelles` ; `test_racine_web.py` (motif de refus, formes Unicode, signalement, jonctions) |
| Nom de fichier | `test_serveur.py::AssainirNom`, `CheminLibre`, `EcritureAtomique`, `EcrituresPatientes`, `PortabiliteWindows` |
| Journal | `test_serveur.py::RotationDuJournal` ; `test_conservation.py` (rotation mensuelle, purge des archives, purge à l'écriture, fil périodique, rotation atomique) |
| Journal technique | `test_serveur.py::JournalTechnique`, `DepotEchecEcritureSansFuite` |
| Page d'état | `test_serveur.py::PageEtat`, `LecteurCertificat`, `VerdictAdresse`, `EtatDeLaMiseAJour` ; `test_integration.py::InterrupteurPageEtat` |
| Arrêt concerté | `test_serveur.py::DeciderArret`, `SurveillanceDeLArret`, `CompteursDeDepots`, `ObeissanceALaDemandeDArret` ; `test_maj_bout_en_bout.py::ArretConcerte`, `DepotEnCours`, `DepotFige` |
| Serveur | `test_integration.py::ServeurEnMarche` (bout en bout, vrai TLS) ; `test_requetes_malformees.py` (requêtes malformées, version neutre, forme invalide, filet et index, journalisation) ; `test_negociation_tls.py::FinishRequest`, `NegociationEnBac` ; `test_serveur.py::ExpirationDuDelaiDInactivite` |
| Démarrage | `test_integration.py::RefusDeDemarrer`, `PurgeAuDemarrage`, `AvertissementIdentiteCabinet` ; `test_racine_web.py::RefusDeDemarrer`, `SignalementDuRefus`, `RefusSousJonction` |

### 5.2 `maj.py`

| Section | Gardes principales |
|---|---|
| Vocabulaire, Traces | `test_maj.py::Traces`, `Constantes`, `ChampsDeLEtat` ; `test_maj_bout_en_bout.py::GardeDesTraces` |
| Dossier réservé, verrou | `test_maj.py::DossierReserve`, `Verrou`, `ProtegerAvantDeVider`, `DroitsWindows` ; `test_maj_windows.py::WindowsReel` |
| Destinations | `test_maj.py::ListeBlanche`, `ListeDerivee` (**la liste blanche contre le paquet réel de `faire-paquet.sh`, dans les deux sens**), `MaxPath`, `SchemaModifie` |
| Politique | `test_maj_politique.py` (plage, lecture de la politique, désactivation, fréquence, éligibilité, filet de la tâche) |
| Contrôles, extraction, sauvegarde | `test_maj.py::RefusSansEcriture`, `ExtractionSansExtract`, `SauvegardeCourante` |
| Pose, Application, Retour | `test_maj.py::PoseEtRetour`, `GardeApresAcceptation` ; `test_maj_bout_en_bout.py` (montées successives, interruption, retour impossible, retour manuel, pilote corrupteur) |
| Client HTTPS | `test_maj_reseau.py` (dont **`DonneesEnvoyees`** : ce qui sort du cabinet, octet par octet ; puis TLS, redirections, tailles et délais, proxy, en-tête) contre un faux hébergement local |
| Signature et paquet | `test_signature_ed25519.py` (vecteurs RFC 8032, malléabilité, ordre faible, croisement `cryptography`) ; `test_paquet_signe.py` (versions, chemins, clés de confiance, contenu de l'archive, altérations, codes de refus) ; `test_signer_paquet.py` |

### 5.3 Les gardes **structurelles** — à connaître absolument

Celles-ci ne testent pas un comportement : elles **lisent l'arbre syntaxique**
du fichier et exigent une propriété de sa forme.

| Garde | Fichier | Ce qu'elle exige |
|---|---|---|
| `GardesStatiques::test_maj_py_est_soumis_a_la_garde_stdlib` | `test_maj.py` | Aucun import hors bibliothèque standard |
| `…::test_aucun_import_hors_du_niveau_module` | `test_maj.py` | Tous les imports au niveau du module (D12 : après la bascule, plus rien ne se charge) |
| `…::test_ni_extract_ni_shell_ni_outil_d_extraction` | `test_maj.py` | Jamais `extract`/`extractall` ni shell |
| `…::test_technique_log_ne_recoit_que_detail_maj` | `test_maj.py` | Rien n'entre dans `technique.log` hors `detail_maj` |
| `…::test_aucun_assert_nu` | `test_maj.py`, `test_signer_paquet.py` | Aucun `assert` : il s'évaporerait sous `python -O` |
| `…::test_les_acces_reseau_ne_passent_que_par_les_trois_fonctions_prevues` | `test_maj.py` | Le réseau est circonscrit |
| `…::test_ctypes_ne_sert_qu_a_lire_l_horloge_du_systeme` | `test_maj.py` | `ctypes` cantonné |
| `GardesStructurelles::test_g1_toute_lecture_passe_par_autorise_lecture` | `test_liens_servis.py` | Aucune route statique ne contourne le filtre |
| `…::test_g2_une_seule_forme_du_chemin_et_chaque_etape_a_sa_place` | `test_liens_servis.py` | Le filtre juge **la chaîne que le disque ouvrira** |
| `Gardes::test_g2_le_controle_precede_l_ecriture_et_le_socket` | `test_racine_web.py` | L'ordre des refus au démarrage |
| `VocabulaireDeLaMiseAJour::test_serveur_py_n_importe_ni_urllib_ni_http_client` | `test_serveur.py` | **Le serveur n'a aucun client réseau** |
| `adresse_jamais_dans_la_page_etat` (parcours d'appels) | `test_serveur.py` | Aucune adresse n'atteint `/etat`, **en suivant les appels de proche en proche** |

Et chacune de ces gardes possède **sa propre garde** : `test_la_garde_des_imports_mord`,
`test_la_garde_des_appels_mord`, `test_la_garde_des_traces_mord`,
`test_la_garde_du_reseau_mord`. C'est la règle du dépôt : *un garde-fou non
mis en échec ne garde rien.*

---

## 6. Si l'on voulait découper ces fichiers un jour

La question se pose légitimement, vu les tailles. Elle a été instruite le
24 novembre 2026 et **reportée**, pour une raison mécanique précise.

### 6.1 Pourquoi pas maintenant

**Les gardes structurelles du §5.3 sont mono-fichier.** Elles font
`ast.parse(un seul source)`, construisent la table des fonctions depuis
`arbre.body`, puis suivent les appels **quand le nœud est un `ast.Name`
présent dans cette table** :

```python
if isinstance(noeud, ast.Name) and noeud.id in modulaires:
    a_voir.append(modulaires[noeud.id])
```

Déplacer `construire_etat` dans un `serveur/etat.py` change l'appel en
`etat.construire_etat(...)`, soit un `ast.Attribute`. La condition ne se
déclenche plus, le parcours s'arrête, et la garde « aucune adresse n'atteint
`/etat` » **continue de passer au vert en ne couvrant plus rien**. Aucun test
ne rougit : c'est exactement le piège « détection non ancrée » de `CLAUDE.md`.

S'y ajoutent trois raisons de calendrier et de coût :

1. **L'état global** (§3) est le vrai couplage, et il **sort déjà du
   fichier** : `maj.py` réécrit cinq de ces globales le temps d'une opération
   (§4.3). Un découpage qui ne le traite pas produit des imports circulaires
   ou un module `etat_global` partagé — la même boule, répartie sur six
   fichiers, et une lisibilité **moindre** puisqu'il faudrait sauter de
   fichier en fichier pour suivre une requête.
2. **La fenêtre est mauvaise.** La production tourne sur `d43350a`
   (26 août) ; la prochaine étape est **C1-T4b**, la livraison au cabinet, où
   il faut pouvoir lire le diff production ↔ `main` ligne par ligne. Un
   refactoring qui touche chaque ligne rend ce diff illisible au moment où il
   doit l'être le moins.
3. **Ce serait du niveau Complet** (serveur, authentification,
   journalisation, code installé chez un client) : contrat, audit, journal des
   mises en échec, revue — pour **zéro gain fonctionnel**.

### 6.2 Dans quel ordre, le jour où

1. **D'abord, rendre les gardes structurelles multi-fichiers** : une tâche à
   part entière, avec ses propres mises en échec. Le parcours doit suivre
   `module.fonction` à travers les fichiers, et un test doit **rougir** si une
   fonction couverte sort du périmètre. Sans ce préalable, le découpage est
   une régression du filet, quel que soit le gain de lisibilité.
2. **Puis extraire les sections réellement indépendantes**, un commit chacune,
   de la moins risquée à la plus :
   - **l'analyseur DER** (`_element_der` → `lire_certificat`) : pur, sans
     entrée-sortie, sans globale. Le candidat idéal ;
   - **le SDDL/icacls Windows** : déjà isolé, déjà partagé avec `maj.py` ;
   - **le client HTTPS de `maj.py`** (`_telecharger` et ses auxiliaires) :
     frontière nette, et déjà couvert par un fichier de tests dédié.
3. **Ne jamais extraire** : la classe `Gestionnaire`, l'authentification,
   `/depot`, les journaux. Trop de gardes y sont ancrées, et c'est le chemin
   de production.
4. **À vérifier à chaque étape** : `PIECES_INDISPENSABLES` de `maj.py`, la
   liste explicite de `outils/faire-paquet.sh`, et le manifeste signé. Plus de
   fichiers, c'est plus de pièces qui doivent **toutes** atterrir ensemble sur
   le chemin de code le plus dangereux du produit — celui qui remplace ses
   propres fichiers sous ses pieds.

---

## 7. Pour aller plus loin

| Sujet | Document |
|---|---|
| Le *pourquoi* de chaque règle | `docs/contrats/<ID>.md` |
| Ce qui a été éprouvé, et par quelle mutation | `docs/audits/<ID>-mises-en-echec.md` |
| Le format du schéma de formulaire | `docs/schema-formulaire.md` |
| La configuration d'un cabinet | `docs/configuration.md` |
| La mise à jour, côté opérateur | `docs/mise-a-jour.md` |
| L'état du projet et les pièges connus | `CLAUDE.md` |
