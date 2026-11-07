# bilan-posturo — état du projet

Application de bilan posturologique sur tablette : le praticien remplit le
formulaire et annote les schémas au stylet, le PDF est fabriqué dans le
navigateur et déposé sur le PC du cabinet. Utilisée quotidiennement depuis
août 2026 par une pédicure-podologue à Morlaix, pour la totalité de ses bilans.

**Dernière mise à jour :** 7 novembre 2026, par `/cloture-projet`
**Version :** V1 en production au cabinet ; `main` porte la 1.1.0
(`formulaire/version.json`), sous **BUSL 1.1** depuis le 14 octobre 2026
**Jalon en cours :** V2 — 21 tâches livrées, C1-T5 et C9-T2 fusionnées en
attente de leur mesure ; rien de la V2 n'est au cabinet, qui tourne sur
**`d43350a` (26 août)**, étiquette `production-cabinet-01`, fiche
`docs/production/cabinet-01.md`. **`main` est poussé** (`1b771bd`), CI verte.
**Premier prospect hors pilote :** un formateur en posturologie (fiche hors dépôt).

## Architecture en bref

```
    Tablette                        PC du cabinet
┌──────────────┐                 ┌──────────────────┐
│  formulaire  │                 │    serveur.py    │
│  + stylet    │ ──── HTTPS ───► │ (stdlib seule)   │
│  → jsPDF     │   POST /depot   │        ↓         │
│  → file      │ ◄─── GET ────── │ dossier des PDF  │
│  (IndexedDB) │     /sante      │ (tâche planifiée)│
└──────────────┘                 └──────────────────┘
```

| Composant | Rôle |
|---|---|
| `serveur/serveur.py` (~2 250 l.) | HTTPS, dépôt, authentification, `/sante`, `/cabinet`, `/etat`, deux journaux purgés à six mois |
| `serveur/generer_autorite.py` | Autorité de certification locale + certificat serveur |
| `formulaire/script.js` | PDF, stylet, brouillon, dépôt, file d'attente, tokens de couleur |
| `formulaire/index.html` | Coquille de 118 l. que le moteur remplit ; V1 gelée dans `index-v1.html` |
| `formulaire/moteur/rendu.js` | Valide un schéma et construit le DOM du formulaire |
| `formulaire/schema.json` | Les 28 blocs du corps du bilan, en données |
| `formulaire/style.css` | La palette du cabinet : cinq tokens sur `:root`, **source unique** |
| `formulaire/version.json` | Numéro de version, **source unique** (serveur, pied de page, `technique.log`) |
| `installer-demarrage.ps1` | Tâche planifiée SYSTEM + pare-feu ; `-Verifier` contrôle sans rien modifier |
| `clients/cabinet-01/schema.json` | Schéma du client, **fait foi** ; `formulaire/schema.json` en est le miroir gardé à l'octet |
| `outils/faire-paquet.sh <client>` | Paquet d'un client, argument obligatoire ; le serveur ne voit jamais `clients/` |
| `blocs/`, `templates/`, `outils/composer-schema.js` | Neuf fragments du pilote, recettes de départ, composition validée par le moteur (atelier, hors paquet) |
| `outils/atelier/` | Fabrication d'un client hors de tout dépôt Git ; règles lues dans `serveur.py` et `script.js`, jamais recopiées ; `identite-cabinet.json` et `apercu-atelier.html` ignorés par Git |
| `tests/` | 448 tests Python + 16 suites Node |

Le PDF est produit **côté navigateur** : le serveur ne reçoit qu'un fichier déjà
assemblé, et n'a aucune dépendance Python.

**Deux journaux à la racine du cabinet.** `journal.log` est nominatif — noms de
fichiers et adresses — et **ne quitte jamais le cabinet**. `technique.log` ne
contient ni adresse, ni nom de fichier, ni rien d'un patient : c'est le fichier
conçu pour **circuler**, celui que le support peut lire. L'interrupteur
`journal_technique` du `config.json` le désactive sans rien casser (C4-T1).
**Aucune ligne n'est conservée plus de six mois**, serveur en marche (C4-T2 :
rotation mensuelle, purge à l'écriture et toutes les 6 h, clé
`conservation_journaux_mois`). L'identité du cabinet vit dans `config.json`,
jamais dans le dépôt, servie par `GET /cabinet` ; sans elle, l'export est refusé.
Son logo, seule exception, vit dans `formulaire/images/cabinet/`, hors dépôt et
hors paquet, validé au démarrage (C2-T2, `docs/configuration.md` §7).

## Contraintes non négociables

- **Local-first.** Aucune donnée de santé ne quitte le PC du cabinet. C'est
  l'argument commercial principal *et* ce qui écarte l'obligation HDS.
- **Le serveur n'utilise que la bibliothèque standard Python.** `cryptography`
  ne sert qu'à fabriquer les certificats, hors du chemin d'exécution.
- **Python 3.9 est le plancher** (CI : 3.9 et 3.13 × Linux, Windows, macOS).
- **TLS obligatoire**, jamais de repli en clair.
- **La racine web est `formulaire/`** et ne contient que le formulaire. Clés,
  configuration, journaux et code Python vivent un niveau au-dessus. Le filtre
  d'extensions et le refus de tout lien sous la racine (C6-T6, 404 identique à
  un absent) sont les deux autres barrières : les trois se conservent. Le
  serveur **refuse de démarrer** si la racine web résolue contient le cabinet
  ou `dossier_pdf` (C6-T7, événement `DEMARRAGE_REFUSE`).
- **`/sante` est la seule route non authentifiée** (garde dérivée de l'AST
  depuis C4-T3). Elle ne divulgue que l'existence du port, muette dans les
  **deux** journaux. **`/etat` ne montre aucune adresse ni nom de fichier** :
  la page circule en capture, comme `technique.log`.
- **Code, commentaires et messages en français**, accents compris.
- **Un seul utilisateur en production** : toute modification du formulaire peut
  casser une consultation le lendemain matin. Prévoir le retour arrière.

## Avancement V2

Trois hypothèses implicites structurent la V1, et ce sont celles que le passage
à plusieurs cabinets casse : un seul cabinet, un seul installateur, le bilan est
une image et non une donnée.

| Chantier | Intitulé | État |
|---|---|---|
| C0 | Cadre juridique et licence | T1 **livré** ; T2 (contrat RGPD, modèles génériques) à faire |
| C1 | Moteur de formulaire à schéma | T1, T2, T3, T3b, T4a, T6, T6b **livrés** ; **T5 fusionnée**, mesure A13 à faire ; T4b à la visite |
| C2 | Identité du cabinet en configuration | T1, **T2 (logo) livrés** |
| C3 | Adressage, certificat et installateur | T1, **T3a livrés** (T3a : VM Windows à faire) ; T2, T3, T4 |
| C4 | Observabilité et support | T1, T2, **T3 (`/etat`)**, T4 **livrés** ; T5 **sortie de la V2** ; T6 |
| C5 | Mises à jour signées | à faire (tirées par le PC, signées : décidé) |
| C6 | Durcissement de sécurité | **T4, T6 (liens), T7 (racine web) livrés** ; T1, T2, T3, T5 |
| C7 | Filet de tests | **T1, T5 livrés** ; T2, T3, T4 |
| C8 | Mécanisme de licence d'abonnement | à faire (grâce de 30 j puis export bloqué : décidé) |
| C9 | Atelier de fabrication d'un client | **T1 livré** ; **T2 fusionnée**, mesures M-A et M-B à faire ; T3 décidé (révision annuelle) |

**Décisions métier du 3 novembre**, dans `docs/ROADMAP.md` en tête : pas de
tunnel de support, mises à jour tirées et signées, grâce puis export bloqué,
révision annuelle incluse, journaux conservés six mois.

Détail par tâche, critères d'acceptation et ordre d'exécution :
`docs/ROADMAP.md`. Analyse produit, prix et cadre juridique :
`docs/projection.md` (document interne, ne pas diffuser).

## Trois décisions à ne pas rouvrir

**Licence.** Les développements depuis le commit `9339ee9` (étiqueté
`frontiere-mit`) sont sous **BUSL 1.1** : lecture, fork et modification libres,
usage en production réservé à un cabinet pour ses propres patients, bascule en
MIT au bout de quatre ans. L'historique antérieur reste MIT à jamais.
Explication : `docs/licence.md` ; seul `LICENSE` fait foi.

**Vocabulaire du schéma**, fixé par C1-T1 : `docs/schema-formulaire.md` est la
source de vérité du format — types fermés (huit depuis la version 2 et C1-T6),
clés reprises à l'identique des `id` du formulaire, version en première clé.

**Adressage**, tranché par C3-T1 le 19 octobre : **IP privée fixe + autorité
locale**, l'existant, conservé délibérément (0 €/cabinet/an, aucun geste du
praticien). « Sous-domaine public + Let's Encrypt » est écarté : panne
intermittente chez Free (IPv4 refuse, IPv6 accepte), dépendance à Internet,
liste des cabinets publiée dans *Certificate Transparency*, certificats à
47 jours en 2029. Réserve documentée, avec protocole d'essai : `docs/adressage.md`.

## L'état réel du moteur, et le geste qui manque

`formulaire/index.html` est une coquille que le moteur remplit depuis
`formulaire/schema.json`. La V1 est conservée octet pour octet dans
`formulaire/index-v1.html`, servie : c'est le **retour arrière de niveau 1**, le
favori « Formulaire — secours V1 », et le témoin qui garde les clés de brouillon
dans les tests.

Le 19 octobre, moteur et fiche de secours ont été comparés au pixel dans Chrome
piloté, repli éprouvé contre un vrai serveur (`CONSTAT-2026-10-19.md`, outillage
`outils/reference-visuelle/`).

**Mais la fiche de secours n'est pas la production** : le cabinet tourne sur
`d43350a`. C1-T4a a mesuré le moteur contre elle (brouillon repris sans perte,
pages identiques une fois restaurées) et listé ce que la praticienne verra
changer : `docs/references-visuelles/CONSTAT-2026-11-06-C1-T4a.md`.

**Livrer au cabinet, c'est C1-T4b** : poser le favori de secours, l'ouvrir, puis
une semaine de bilans réels. Il faut l'appareil, **pas avant janvier 2027**.
D'ici là rien ne part au cabinet ; un correctif d'urgence part de
`maintenance-cabinet-01`, jamais de `main`.

**Tests :** 448 Python (7 sautés sur le Mac) et 16 suites Node, tous verts
au 7 novembre 2026, aussi sous `python3 -O`, et en CI sur Linux, Windows et
macOS, Python 3.9 et 3.13, sur les branches de tâche comme sur `main`.
`npm test` dépasse le délai de 2 min d'une commande : le lancer en arrière-plan.

**Deux mesures de Baptiste attendent** : C1-T5 (`docs/essais/C1-T5-client-fictif.md`)
et C9-T2 (`docs/essais/C9-T2-fabrication.md`). Avant le premier client hors
pilote, trancher D-O1 (où vit son schéma) et D-O2 (sa palette), bloc C9-T2.

**Une grille n'entre dans un schéma client** qu'aux trois conditions de
`docs/schema-formulaire.md`, dont un export d'essai **sur la tablette du
client**, à sa largeur : au-delà de 1 192 px, l'export est refusé ; sous
~735 px de fenêtre, une grille de 20 lignes est coupée entre deux pages.

**Avant d'envoyer le paquet au prospect** : essai de C3-T3a sur une VM Windows
propre, fiche `docs/essais/C3-T3a-windows.md`. Et annoncer à la praticienne
pilote que l'historique de `journal.log` partira en bloc vers février 2027.
À la visite, lancer une fois `demarrer-serveur.bat` et lire la sortie : un
`dossier_pdf` sous `formulaire` ferait désormais refuser le démarrage.

## Dernières sessions

- [2026-11-07 (2) — Un serveur qui refuse de démarrer sur une racine web dangereuse](docs/resumes/2026-11-07-racine-web-refusee.md) :
  C6-T7 livrée ; audit CONFORME au réaudit.
- [2026-11-07 — L'atelier de composition, et un serveur qui ne suit plus les liens](docs/resumes/2026-11-07-atelier-et-liens-servis.md) :
  C9-T2 fusionnée (mesure à faire) ; C6-T6 livrée ; C6-T7 ouverte.
- [2026-11-06 (3) — Une bibliothèque de blocs, et le logo du client](docs/resumes/2026-11-06-blocs-templates-et-logo.md) :
  C1-T4a et C1-T5 fusionnées ; C2-T2 livrée ; C6-T6 ouverte.
- [2026-11-06 (2) — La production archivée, et le schéma du cabinet mesuré contre elle](docs/resumes/2026-11-06-production-archivee-et-schema-cabinet.md) :
  production nommée (`d43350a`) ; C1-T4 scindée ; C1-T4a livrée.
- [2026-11-06 — `main` publié, et une page d'état qui peut circuler](docs/resumes/2026-11-06-page-etat.md) :
  C1-T6 et C1-T6b fusionnées et poussées ; C4-T3 livrée (voie A, neuf clés).

## Comment on travaille ici

| Étape | Commande | Produit |
|---|---|---|
| 1. Contrat | `/lancer-tache <ID>` | `docs/contrats/<ID>.md` |
| 2. Implémentation + audit | `/implementer-tache <ID>` | code, tests, `docs/audits/<ID>.md` |
| 3. Revue | `/revue-code <ID>` | `docs/revues/<ID>.md` |
| 4. Clôture | `/cloture-projet` | ce fichier, et `docs/resumes/<date>.md` |

On n'implémente jamais sans contrat, et le contrat se relit à froid. Les agents
vivent dans `.claude/agents/`. Chaque tâche porte un **niveau de process**
(Direct, Allégé, Allégé + audit, Complet) fixé dans `docs/ROADMAP.md` : il se
monte en cours de route, jamais ne se descend.

**Ce fichier est maintenu exclusivement par `/cloture-projet`**, et doit rester
sous 300 lignes. Il oriente ; il ne recopie pas `docs/ROADMAP.md`.

## Pièges connus

Ils ont déjà coûté du temps ; ils le recoûteront.

- **Un garde-fou non mis en échec ne garde rien.** Le piège le plus coûteux du
  dépôt, quatre fois sur la seule C4-T1 : test qui ne mordait pas, détection non
  ancrée, **`assert` nus qui s'évaporent sous `python -O`**, liste de noms tenue
  à la main. **Dériver du code, jamais transcrire ; éprouver chaque garde par
  une mutation volontaire ; la jouer sous `-O`.** Une tolérance ajoutée pendant
  l'implémentation est le moyen le plus simple de faire taire un comparateur.
- **Le rendu réel voit ce qu'aucun test ne voit.** Le 19 octobre, cinq écarts
  de rendu sous 115 tests verts ; le 4 novembre, une grille rognée sans un mot
  dans le PDF. **Le moteur n'invente ni ponctuation ni structure** : le schéma
  porte le texte exact qui s'affiche. Se méfier de ses propres tolérances : le
  bruit JPEG invoqué pour excuser un écart était **nul**, mesure faite.
- **Ne jamais lancer `serveur.py` ni `generer_autorite.py` depuis le dépôt.**
  Ils calculent leur racine depuis leur emplacement et **écraseraient** les
  fichiers réels du cabinet. Tout essai se fait en bac à sable — patron
  `demarrer_sandbox_court` dans `tests/test_integration.py`.
- **Une copie de bac à sable par `tar` ou `cp -r` emporte les données réelles du
  cabinet** (clés, `config.json`, journal, un bilan réel : arrivé le 20 octobre).
  Aucun garde-fou mécanique ne l'empêche : copier par `git ls-files -z`, toujours.
- **Un agent interrompu laisse son chantier ouvert** : une fois, une **fuite
  d'adresse IP est restée active dans le code**. Sauvegarder hors du dépôt avant
  toute mutation, restaurer par `cp` ; au retour d'un agent interrompu, vérifier
  l'absence de mutation résiduelle **avant** toute autre question.
- **Serveur** — sans `set_alpn_protocols`, Chrome ferme sans un octet, et
  `get_request()` est surchargée pour ne pas avaler l'`OSError` TLS ;
  `SO_REUSEADDR` conditionné à `os.name` (Windows) ; `compare_digest` sur des
  octets (accents) ; double pile IPv6 avec `IPV6_V6ONLY` désactivé.
- **Palette** — cinq couleurs sur `:root` ; le PDF les lit par
  `getComputedStyle` **dans** la génération, jamais au niveau module.
- **Une garde d'écriture s'éprouve dans une racine jetable**, jamais dans le
  dépôt : un `finally` ne protège pas d'une interruption (C1-T5).
- **Les clés de brouillon sont gelées.** Les `id` du formulaire *sont* les clés
  du brouillon `localStorage` (`cleChamp()`). Les renommer — même pour corriger
  `familliaux`, `spécialistes`, `symétrique`, `pédieux` — perd le bilan d'une
  consultation en cours. La tentation de « nettoyer » est le risque de C1-T4.
- **`initDessin()` exige les quatre images dans le DOM** : `demarrerApplication()`
  est appelée **par le moteur, après rendu**, jamais sur `DOMContentLoaded`.
- **`dossier_pdf` et le compte SYSTEM** — un lecteur réseau de la session du
  praticien n'existe pas pour la tâche planifiée : chemin local ou UNC. Et
  `TerminateProcess` saute le `finally` : pas de ligne `ARRET` au cabinet.
- **`actions/checkout` clone à la profondeur 1** (sauf le job `test`) : un test
  qui a besoin d'un autre commit vérifie **l'objet** (`git cat-file -e`).
- **`git ls-files` sans `-z`** échappe les chemins accentués ; `xargs -0 grep`
  rend 123 pour « rien » comme pour une erreur. Un contrôle qui lit l'index Git
  s'éprouve sur des fichiers **indexés**.
- **Un tube `stdout=PIPE` jamais lu fige le serveur de test sous Windows** :
  seule `/sante` répond. Fil lecteur dans `ServeurEnMarche` et `LiensServis`,
  **pas** dans `demarrer_sandbox_court`. Attendre `DEMARRAGE` ne garantit pas
  que le `try:` est franchi. Ne jamais relancer un échec intermittent : le capturer.
- **La CI ne part que sur `main`, une pull request ou à la main.** Une branche
  poussée ne lance rien : `env -u GITHUB_TOKEN gh workflow run tests.yml --ref
  <branche>`. Un `GITHUB_TOKEN` invalide dans l'environnement masque le
  trousseau de `gh`. Des commits jamais passés en CI ont caché deux semaines une
  régression Windows : ne pas laisser `main` local longtemps sans CI.
- **Un harnais de mutation peut mentir** (`$?` après un `printf` ; commande en
  variable sous zsh, rendue 127 : écrire `A() { … "$@"; }`) : toujours un témoin.
  Muter une copie `git ls-files -z`, ou un clone jetable **sans `origin`**.
- **Une mutation qui interbloque fige la suite** : garde statique AST (C4-T2).
- **Piloter Chrome** : défiler avant `Input.dispatchMouseEvent` ; sans
  `Network.setCacheDisabled`, un PDF régénéré ressort identique ; le nombre de
  pages dépend de la fenêtre (3 à 1 280 px, 6 vers 760 px).
- **Simuler Windows dans un test** : `lstat` aussi doit ignorer la casse, et
  `realpath` être isolé du faux `lstat` sous 3.9 (vu en CI seulement). Sous
  macOS, `os.getcwd()` rend le chemin résolu : un bac à sable ne passe jamais
  par `/var`. Deux tests de jonction échouent sous le Python 3.9.6 de macOS.
- **Chemins comparés** : en CI Windows, le dossier temporaire passe par un nom
  court 8.3 (`RUNNER~1`) — partir de `realpath(tmp)`, ne pas sauter le test ;
  sous macOS, un chemin a deux écritures Unicode — comparer en NFC (C6-T7).
- **Un lecteur de journal cherche un jeton exact**, jamais une sous-chaîne :
  `DEMARRAGE` est un préfixe de `DEMARRAGE_REFUSE` (`verdict_certificat`).
- **`python3 -O` lancé par `(… &)` d'un shell non interactif ignore SIGINT** :
  `test_arret_journalise` y échoue toujours. Jouer `-O` au premier plan.
- **La fiche de secours charge `script.js`.** Toute modification de ce fichier
  doit prouver que le PDF de `index-v1.html` reste identique au pixel.
- **Un export n'est pas déterministe sous `serveur.py`** : comparer des
  ensembles d'exports, jamais un contre un. **G4 lit le SHA `d43350a`**, pas
  l'étiquette `production-cabinet-01`, qui bouge à chaque installation.
- **Le dépôt est public, la fiche du prospect ne l'est pas.** Ignorée par Git,
  elle est gardée par `tests/test_confidentialite_prospect.py` : fichiers,
  messages de commit, noms de référence et **tout blob de la plage** — sur le
  seul poste qui détient la fiche. Restent hors garde : messages d'étiquettes
  annotées, image commitée en binaire. Elle mord aussi sur du vocabulaire
  médical ordinaire : reformuler, et **effacer le brouillon refusé** du bloc-notes.

## Fichiers à ne jamais toucher

Ce sont les données réelles d'un cabinet en exercice, présentes à la racine et
exclues du suivi Git : la configuration (empreinte du mot de passe), les clés
privées du serveur et de l'autorité, le certificat de l'autorité, les deux
journaux et leurs archives, et le dossier des bilans produits.

Ne jamais les lire, les modifier ni les versionner — ni les emporter dans une
copie de travail. Le contrôle « aucun secret versionné » de
`.github/workflows/tests.yml` fait échouer la CI si l'un d'eux entre dans le
dépôt.
