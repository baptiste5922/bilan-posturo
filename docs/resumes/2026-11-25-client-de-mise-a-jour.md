# Session du 25 novembre 2026 — Un client de mise à jour, et un serveur qu'une connexion muette ne fige plus

**Durée approximative :** du 12 au 18 novembre 2026, clôture le 25 ; une longue
session, coupée trois fois par la limite d'API et une fois compactée.
**Tâches concernées :** C5-T2a, C5-T2b (C5-T2), C6-T8
**Branche :** `main` (branches de tâche fusionnées en avance rapide, toutes poussées)
**Commits :** 51 depuis la clôture du 9 novembre (`3c97705`), de `C5-T2a` à
`cff8210` (C6-T8) ; plus le commit de cette clôture.

## Ce qui a été fait

**C5-T2a — le client de mise à jour, en local.** `serveur/maj.py` sait appliquer
un paquet signé déjà présent sur le PC : contrôles préalables (signature,
version, liste blanche des destinations), sauvegarde, **arrêt concerté** du
serveur (`decider_arret` : le serveur refuse tant qu'un dépôt est en cours ou
que la plage n'est pas calme), bascule des fichiers, auto-contrôle par `/sante`
et **retour arrière sur tout échec**. `assurer_serveur` relance le serveur après
toute sortie qui suit l'acceptation de l'arrêt. Le dossier `mise-a-jour/` est
réservé à SYSTEM et aux administrateurs, vérifié sous Windows par le SDDL et le
propriétaire lus en `ctypes`. `Gestionnaire.timeout = 120` borne l'inactivité de
chaque connexion ; une expiration est muette, un dépôt interrompu donne
`DEPOT refus motif=transfert-interrompu`. Audit CONFORME SOUS RÉSERVE puis
CONFORME au réaudit ; revue À CORRIGER (fiche d'essai, un test, trois
documents) puis À LIVRER.

**C5-T2b — le téléchargement et la politique horaire.** `maj.py verifier`, lancé
par une seconde tâche planifiée `BilanPosturo-MiseAJour`, va chercher le paquet
du cabinet sur l'hébergement statique (D-M1, voie (d)), sur `http.client` avec
le contexte TLS par défaut, redirections vers https seules et cinq au plus,
proxy lu dans la seule configuration, échéance totale coupée par un
`threading.Timer`. Il n'applique qu'**entre 20 h et 7 h**, ou dans le quart
d'heure qui suit le démarrage du système (`au_demarrage`, `GetTickCount64`,
plafond 900 s), contrôle toutes les 6 h, rejuge la plage et le temps restant
juste avant la demande d'arrêt (`TEMPS_INSUFFISANT`), espace les nouvelles
tentatives (6 h après un transfert commencé, 1 h sans un octet), limite à une
ligne par jour et par clé ce qu'il écrit dans `technique.log`, et ne connaît que
36 codes fermés. `/etat` montre `maj_controle_le`. `verifier --forcer` sert aux
séances d'assistance et à la fiche d'essai. L'adresse de publication identifie
un client : elle est gardée hors du dépôt (`.gitignore`, motif de la CI, test
`tests/test_confidentialite_publication.py` qui ne nomme jamais ce qu'il
trouve). Audit CONFORME SOUS RÉSERVE (un constat moyen : un hébergement
compromis pouvait faire arrêter le serveur pendant les consultations du matin)
puis CONFORME au réaudit ; revue À LIVRER après corrections.

**Effet au cabinet : aucun.** Sans adresse de publication dans `config.json`, le
client est désactivé et le serveur se comporte comme avant. C5-T2 reste **non
cochée** : les fiches A et B de `docs/essais/C5-T2-windows.md` attendent une VM
Windows.

**C6-T8 — la négociation TLS a un délai.** Le réaudit de C5-T2a avait trouvé un
défaut présent en production (`d43350a`) : la négociation TLS avait lieu dans
`accept()`, sur le fil de `serve_forever()`, sans délai. Une seule connexion TCP
muette, sans identifiant, figeait tout le serveur — plus de dépôt, `/sante`
muette. La socket d'écoute est désormais enveloppée avec
`do_handshake_on_connect=False`, et `ServeurBilan.finish_request` négocie dans
le fil de chaque connexion, avec une **échéance totale de 10 s**
(`DELAI_NEGOCIATION_TLS_SECONDES`). `get_request()` est retirée. L'expiration
est journalisée `TLS_REFUSE raison=delai-depasse`, sans adresse ; une garde
`version() is None` interdit tout gestionnaire sur un canal non chiffré. Audit
CONFORME (1 000 connexions muettes en bac : `/sante` répond en moins de 10 ms,
toutes fermées en 12 s ; volume de journal inchangé pour une sonde de port) ;
revue À LIVRER. Contrat, implémentation, audit et revue en une journée.

## Décisions prises

| Décision | Raison | Conséquence |
|---|---|---|
| **D-M1 : hébergement statique** (voie (d)), tranchée par Baptiste le 14 novembre | Aucun serveur à tenir, aucun secret au cabinet ; l'adresse imprévisible par client suffit à cloisonner | Paquets par client, au format 1 ; hébergeur à choisir (C5-T3) ; adresse gardée hors du dépôt |
| Pas de découpe en C5-T2c | L'installateur et la fiche B étaient conformes ; le constat moyen se corrigeait entièrement dans `maj.py` | T2b livrée d'un bloc |
| Démarrage rapide de Windows : **mesurer avant de refondre** | Le processus du serveur survit peut-être à la veille prolongée ; une refonte à l'aveugle risquait d'aggraver | Variante 4 de B-5 dans la fiche ; précondition à l'activation (D-M3) |
| Pas de nouvel audit après la revue de T2b | Diff de 69 lignes de `maj.py`, relu, sans toucher au réseau ni au signal de démarrage | — |
| **C6-T8, voie (a)** : négocier dans le fil de la connexion | Un délai posé sur le fil principal (voie (b)) borne le gel sans le supprimer | `get_request()` retirée ; `finish_request` est le seul passage vers le gestionnaire |
| Expiration de négociation **journalisée**, contrairement à l'expiration d'inactivité | Une connexion qui ne présente jamais de TLS est l'anomalie que la tâche neutralise ; le support doit la voir | À mesurer à la visite : si la tablette en produit en usage normal, tâche de suivi |
| Pas de borne du nombre de fils (C6-T8, D4) | La surface existait déjà (négocier puis se taire 120 s) ; la tâche la réduit | À rouvrir seulement si un besoin se montre |
| Précondition 1 de D-M3 **ouverte jusqu'à l'installation** de C6-T8 au cabinet | Constat faible de l'audit : la fusion ne protège pas le cabinet, qui tourne sur `d43350a` | Ne pas activer le client avant la visite C1-T4b |
| CI épinglée sur `ubuntu-24.04` | `ubuntu-latest` est passé en 26.04, sans Python 3.9 | Le plancher reste testé sous Linux ; le job `lint` reste sur `ubuntu-latest` |
| Raisons de `TLS_REFUSE` non documentées dans les guides | En décrire une seule donnerait une liste incomplète | À faire avec une page de support qui les décrira toutes |

## État des tests

Avant : 671 tests Python et 16 suites Node (9 novembre). Après : **1 130 tests
Python** (23 sautés sur le Mac) et 16 suites Node, verts ; aussi sous
`python3 -O` au premier plan. CI de `main` verte sur les sept travaux (Linux
3.9 et 3.13, Windows 3.9 et 3.13, macOS, lint, scripts Windows).

Nouveau : `tests/test_maj_reseau.py` (faux hébergement `tests/outils/faux_hebergement.py`),
`tests/test_maj_politique.py`, `tests/test_confidentialite_publication.py`,
`tests/test_negociation_tls.py`. Mises en échec consignées : M1-M20 et R1-R22
(C5-T2a), N1-N51 (C5-T2b), M1-M7 (C6-T8), toutes rouges sur leur test, le témoin vert.

## Constats de sécurité

- **C5-T2a** : CONFORME au réaudit ; R1, O1, O2 refermés par C5-T2b. Le réaudit a
  trouvé le défaut d'acceptation TLS, devenu C6-T8.
- **C5-T2b** : constat moyen (arrêt pendant les consultations sur un hébergement
  compromis) et deux faibles corrigés ; CONFORME au réaudit.
- **C6-T8** : CONFORME ; un constat faible (ROADMAP disant la précondition levée
  à la fusion), corrigé.
- **Reporté** : borne du nombre de fils (C6-T8 D4) ; droits du dossier
  d'installation (C6) ; paquet en attente retéléchargé (erratum 43 de C5-T2).

## Ce qui reste en suspens

- **Fiches C5-T2 A et B sur une VM Windows**, dont B-5 variante 4 (Démarrage
  rapide) : il faut la VM. C5-T2 se coche ensuite.
- **Activation du client au cabinet (D-M3)** : C6-T8 installée (visite C1-T4b,
  janvier 2027) **et** mesure du Démarrage rapide.
- **Clé de publication réelle** à générer et sauvegarder par Baptiste
  (`docs/cle-publication.md`) ; **hébergeur** à choisir (C5-T3) ; **D9** à trancher.
- **Mesures** A13 (C1-T5), M-A et M-B (C9-T2) ; **D-O1, D-O2** avant le premier
  client hors pilote ; **C3-T3a** sur VM avant d'envoyer le paquet au prospect.
- **À verser dans la ROADMAP (C7)** : l'échec intermittent `TimeoutExpired` de
  120 s sur l'appel PowerShell `-Verifier` de `test_lance_d_un_sous_dossier_s_arrete`
  (CI de `main` `43465630699`, windows 3.13, exécuteur lent, vert à la relance ;
  journal capturé hors dépôt) ; l'unification du comptage des lignes de
  `technique.log` entre `test_negociation_tls.py` et `test_integration.py`.
- **Travail hors session, non commité** : à la clôture, l'arbre de travail
  portait un index de sections ajouté aux docstrings de `serveur/serveur.py` et
  `serveur/maj.py`, et une carte `docs/architecture-serveur.md` (non suivie),
  datés du 24 novembre. Ils ne viennent pas de cette session (documentation
  seule, aucune instruction modifiée) ; laissés tels quels, non commités.

## Prochaine étape recommandée

Dérouler les fiches d'essai C5-T2 A et B (`docs/essais/C5-T2-windows.md`) sur une
VM Windows propre, B-5 variante 4 comprise : c'est ce qui coche C5-T2 et lève la
seconde précondition de l'activation. Côté code, la prochaine tâche prête se
choisit par `/lancer-tache` sans argument.

## À savoir pour la prochaine session

- **Négociation TLS** : elle vit dans `ServeurBilan.finish_request`, plus dans
  `get_request()`. Une ligne `TLS_REFUSE` est donc écrite **par le fil de la
  connexion**, après le retour du client : un test la compte avant, puis attend
  une ligne de plus (`compter_lignes_technique`, `attendre_lignes_technique`).
  Attendre « une ligne » tout court passe sur une ligne antérieure et ne garde rien.
- **Ne jamais lancer `maj.py` depuis le dépôt, pas même `--help`** : un
  implémenteur l'a fait ; l'audit a dû prouver qu'il n'y avait eu ni lecture ni
  écriture. Même règle que `serveur.py`.
- **CI** : `ubuntu-latest` n'a plus Python 3.9 (épinglé `ubuntu-24.04`) ; un job
  macOS « not acquired by Runner » est un manque de capacité chez GitHub, pas
  un échec : relancer ce seul job.
- **Agents coupés par la limite d'API** (trois fois) : avant de les relancer,
  `git status` et `git diff` pour vérifier qu'aucune mutation ne reste.
- **Le 3.9.6 du Mac n'a pas `cryptography`** : les tests en bac y sont sautés. Pour
  éprouver 3.9, fabriquer l'autorité avec le Python récent et lancer le seul
  serveur sous `/usr/bin/python3` ; la CI 3.9 reste le juge.
- **Trois `BilanPosturo_video*.mp4` non suivis** dorment à la racine : ils ne sont
  pas au dépôt. Ajouter les fichiers par leur nom, jamais `git add -A`.
