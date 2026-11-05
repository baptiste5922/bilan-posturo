# bilan-posturo — état du projet

Application de bilan posturologique sur tablette : le praticien remplit le
formulaire et annote les schémas au stylet, le PDF est fabriqué dans le
navigateur et déposé sur le PC du cabinet. Utilisée quotidiennement depuis
août 2026 par une pédicure-podologue à Morlaix, pour la totalité de ses bilans.

**Dernière mise à jour :** 5 novembre 2026, par `/cloture-projet`
**Version :** V1 en production au cabinet ; `main` porte la 1.1.0
(`formulaire/version.json`), sous **BUSL 1.1** depuis le 14 octobre 2026
**Jalon en cours :** V2 — 15 tâches livrées ; rien de la V2 n'est au cabinet.
**`main` local n'est pas poussé**, et **`c1-t6-grille` n'y est pas fusionnée**.
**Premier prospect hors pilote :** un formateur en posturologie, à installer à
distance. Sa fiche, hors dépôt, demande le type `grille` (C1-T6, puis C1-T6b).

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
| `serveur/serveur.py` (~1 300 l.) | HTTPS, dépôt, authentification, `/sante`, `/cabinet`, deux journaux purgés à six mois |
| `serveur/generer_autorite.py` | Autorité de certification locale + certificat serveur |
| `formulaire/script.js` | PDF, stylet, brouillon, dépôt, file d'attente, tokens de couleur |
| `formulaire/index.html` | Coquille de 118 l. que le moteur remplit ; V1 gelée dans `index-v1.html` |
| `formulaire/moteur/rendu.js` | Valide un schéma et construit le DOM du formulaire |
| `formulaire/schema.json` | Les 28 blocs du corps du bilan, en données |
| `formulaire/style.css` | La palette du cabinet : cinq tokens sur `:root`, **source unique** |
| `formulaire/version.json` | Numéro de version, **source unique** (serveur, pied de page, `technique.log`) |
| `installer-demarrage.ps1` | Tâche planifiée SYSTEM + pare-feu ; `-Verifier` contrôle sans rien modifier |
| `tests/` | 226 tests Python + 11 suites Node (branche `c1-t6-grille`) |

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

## Contraintes non négociables

- **Local-first.** Aucune donnée de santé ne quitte le PC du cabinet. C'est
  l'argument commercial principal *et* ce qui écarte l'obligation HDS.
- **Le serveur n'utilise que la bibliothèque standard Python.** `cryptography`
  ne sert qu'à fabriquer les certificats, hors du chemin d'exécution.
- **Python 3.9 est le plancher** (CI : 3.9 et 3.13 × Linux, Windows, macOS).
- **TLS obligatoire**, jamais de repli en clair.
- **La racine web est `formulaire/`** et ne contient que le formulaire. Clés,
  configuration, journaux et code Python vivent un niveau au-dessus. Le filtre
  d'extensions est la seconde barrière : les deux se conservent.
- **`/sante` est la seule route non authentifiée.** Elle ne divulgue rien de
  plus que l'existence du port, et reste muette dans les **deux** journaux.
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
| C1 | Moteur de formulaire à schéma | T1, T2, T3, T3b, **T6 (`grille`) livrés** ; T6b ; T4 bloqué par le favori ; T5 |
| C2 | Identité du cabinet en configuration | T1 **livré** ; T2 (logo) à faire |
| C3 | Adressage, certificat et installateur | T1, **T3a livrés** (T3a : VM Windows à faire) ; T2, T3, T4 |
| C4 | Observabilité et support | T1, **T2, T4 livrés** ; T5 **sortie de la V2** ; T3, T6 |
| C5 | Mises à jour signées | à faire (tirées par le PC, signées : décidé) |
| C6 | Durcissement de sécurité | **T4 livré** ; T1, T2, T3, T5 |
| C7 | Filet de tests | **T1, T5 livrés** ; T2, T3, T4 |
| C8 | Mécanisme de licence d'abonnement | à faire (grâce de 30 j puis export bloqué : décidé) |
| C9 | Atelier de fabrication d'un client | **T1 livré** ; T3 décidé (révision annuelle) ; T2 |

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
locale**, soit l'existant, conservé délibérément. 0 €/cabinet/an, aucun geste à
la charge du praticien. La voie « sous-domaine public + Let's Encrypt » a été
écartée sur trois constats : un nom public résolvant vers une adresse privée est
refusé par les résolveurs IPv4 de Free et accepté par leurs IPv6, donc la panne
est intermittente ; elle rendait un usage local dépendant d'Internet ; elle
publiait la liste des cabinets dans *Certificate Transparency*. Et les
certificats publics tombent à 47 jours en 2029, dont une autorité locale est
exemptée. Elle reste en **réserve documentée** pour un client dont les appareils
n'admettent pas l'installation d'une autorité, avec son protocole d'essai :
`docs/adressage.md`.

## L'état réel du moteur, et le geste qui manque

`formulaire/index.html` est une coquille que le moteur remplit depuis
`formulaire/schema.json`. La V1 est conservée octet pour octet dans
`formulaire/index-v1.html`, servie : c'est le **retour arrière de niveau 1**, le
favori « Formulaire — secours V1 », et le témoin qui garde les clés de brouillon
dans les tests.

Le rendu a été comparé page à page dans Chrome piloté et le repli éprouvé contre
un vrai serveur en bac à sable le 19 octobre : six pages identiques au pixel
près, une saisie commencée sur le moteur se reprend sur la fiche de secours, PDF
déposé compris. Cinq écarts de rendu avaient été trouvés et corrigés à cette
occasion — aucun n'était visible des 115 tests d'alors. Détail :
`docs/references-visuelles/CONSTAT-2026-10-19.md` ; outillage rejouable :
`outils/reference-visuelle/`.

**Reste un seul geste avant de livrer au cabinet** : poser le favori de secours
sur la tablette et l'ouvrir une fois. Il demande l'appareil ; le chemin qu'il
emprunte est éprouvé. **Tant qu'il n'est pas fait, rien ne part au cabinet et
C1-T4 ne peut pas commencer** — son critère d'acceptation est une semaine de
bilans réels sans régression.

**Tests :** 226 Python (2 sautés hors Windows) et 11 suites Node, tous verts
au 5 novembre 2026, aussi sous `python3 -O`, et en CI sur Linux, Windows et
macOS, Python 3.9 et 3.13 — CI jouée sur les branches de tâche, pas sur `main`.
`npm test` dépasse le délai de 2 min d'une commande : le lancer en arrière-plan.

**Une grille n'entre dans un schéma client** qu'aux trois conditions de
`docs/schema-formulaire.md`, dont un export d'essai **sur la tablette du
client** : au-delà de 1 192 px, l'export est refusé en consultation.

**Avant d'envoyer le paquet au prospect** : essai de C3-T3a sur une VM Windows
propre, fiche `docs/essais/C3-T3a-windows.md`. Et annoncer à la praticienne
pilote que l'historique de `journal.log` partira en bloc vers février 2027.

## Dernières sessions

- [2026-11-05 — Le type `grille`, et la grille qu'on ne voyait pas rognée](docs/resumes/2026-11-05-type-grille.md) :
  C1-T6 livrée (format v2, amendement A1 : réduire puis refuser). C1-T6b ouverte.
- [2026-11-04 — Un premier prospect, et huit tâches livrées](docs/resumes/2026-11-04-premier-prospect-et-huit-taches.md) :
  C2-T1, C6-T4, C9-T1, C7-T1, C4-T4, C7-T5, C3-T3a, C4-T2. Décisions métier.
- [2026-10-20 — L'adressage tranché, et un journal que l'éditeur peut lire](docs/resumes/2026-10-20-adressage-et-journal-technique.md) :
  C3-T1 et C4-T1 livrées. Le garde-fou qui ne garde rien, quatre fois.
- [2026-10-19 — La bascule, et ce que le rendu réel a révélé](docs/resumes/2026-10-19-bascule-et-fidelite.md) :
  C1-T3b livrée. Cinq écarts de rendu trouvés dans un vrai navigateur.
- [2026-10-15 (2) — Le moteur de rendu, sans la bascule](docs/resumes/2026-10-15-moteur-de-rendu.md) :
  C1-T3 étapes 1 à 8. Moteur, schéma, comparateur V1 ↔ moteur.

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
  cabinet.** C'est arrivé le 20 octobre : clés privées, `config.json`,
  `journal.log` et un PDF de bilan réel dans le dossier de travail d'un agent.
  Purgé, originaux intacts, mais **aucun garde-fou mécanique ne l'empêche** :
  copier par `git ls-files -z`, toujours.
- **Un agent interrompu laisse son chantier ouvert** : une fois, une **fuite
  d'adresse IP est restée active dans le code**. Sauvegarder hors du dépôt avant
  toute mutation, restaurer par `cp` ; au retour d'un agent interrompu, vérifier
  l'absence de mutation résiduelle **avant** toute autre question.
- **ALPN** — sans `set_alpn_protocols`, Chrome ferme la connexion sans envoyer
  un octet, là où curl retombe sur HTTP/1.1. Symptôme : `ERR_EMPTY_RESPONSE`
  sans aucune trace serveur.
- **Erreurs TLS invisibles** — la négociation a lieu dans `get_request()`, et
  `socketserver` y avale l'`OSError` sans rien journaliser. La méthode est
  surchargée pour les faire remonter.
- **`SO_REUSEADDR`** — sous Windows, laisse deux processus se lier au même port,
  l'ancien répondant encore pendant que le nouveau annonce un démarrage réussi.
  Le drapeau est conditionné à `os.name`.
- **`hmac.compare_digest`** lève `TypeError` sur une chaîne non ASCII : un
  identifiant accentué tuait le fil d'exécution. Comparaison sur des octets.
- **Double pile** — `localhost` résout d'abord en `::1` : un serveur lié au seul
  `0.0.0.0` y est injoignable. On écoute en IPv6 avec `IPV6_V6ONLY` désactivé,
  avec repli IPv4.
- **Palette — piège refermé par C1-T2.** Les cinq couleurs vivent **uniquement**
  sur `:root` dans `style.css` ; le PDF les lit par `getComputedStyle` à chaque
  génération, et la lecture doit rester **dans** la génération — au niveau module
  elle casse les tests de la file d'attente, dont le contexte `vm` n'a pas
  `getComputedStyle`.
- **Les clés de brouillon sont gelées.** Les `id` du formulaire *sont* les clés
  du brouillon `localStorage` (`cleChamp()`). Les renommer — même pour corriger
  `familliaux`, `spécialistes`, `symétrique`, `pédieux` — perd le bilan d'une
  consultation en cours. La tentation de « nettoyer » est le risque de C1-T4.
- **Le rendu ne doit pas démarrer après `DOMContentLoaded`.** `initDessin()`
  exige que les quatre images soient déjà dans le DOM ; sinon le stylet ne
  répond plus et les traits d'un brouillon restauré tombent dans le vide. D'où
  `demarrerApplication()`, appelée **par le moteur, après rendu**.
- **`dossier_pdf` et le compte SYSTEM** — la tâche planifiée tourne en SYSTEM :
  un lecteur réseau monté dans la session du praticien n'existe pas pour elle.
  Chemin local absolu ou chemin UNC. Corollaire : `TerminateProcess` n'exécute
  pas le `finally`, donc la ligne `ARRET` du journal technique n'existera presque
  jamais au cabinet.
- **`actions/checkout` clone à la profondeur 1.** Un test qui a besoin d'un autre
  commit doit vérifier **l'objet** (`git cat-file -e`), pas le dossier ; et
  `git log -1 -- <fichier>` y rend la date de `HEAD`, donc toute mesure de date
  tirée de l'historique y est silencieusement fausse.
- **`git ls-files` sans `-z`** échappe les chemins non ASCII à la façon du C.
  Tous les documents de ce dépôt portent des noms français. Et `xargs -0 grep`
  rend 123 aussi bien pour « rien trouvé » que pour une erreur réelle : il faut
  une boucle. Un contrôle qui lit l'index Git doit être éprouvé sur des fichiers
  **indexés** — validé sur des fichiers non suivis, il ne voit rien.
- **Un tube `stdout=PIPE` jamais lu fige le serveur de test sous Windows**
  (tampon minuscule) : toute requête qui journalise se bloque, `/sante` seule
  répond. C'était le « délai TLS » de C7-T5 ; un fil lecteur le règle (même
  mécanisme dans `demarrer_sandbox_court`). Ne jamais relancer un échec
  intermittent : le capturer.
- **La CI ne part que sur `main`, une pull request ou à la main.** Une branche
  poussée ne lance rien : `env -u GITHUB_TOKEN gh workflow run tests.yml --ref
  <branche>`. Un `GITHUB_TOKEN` invalide dans l'environnement masque le
  trousseau de `gh`. Des commits jamais passés en CI ont caché deux semaines une
  régression Windows : ne pas laisser `main` local longtemps sans CI.
- **Un harnais de mutation peut mentir** : `$?` lu après un `printf`, une
  commande rangée dans une variable sous zsh, une mutation placée là où elle ne
  change rien. Toujours un témoin sans mutation, et le code de retour du test
  lui-même. Les mutations se font sur une copie `git ls-files -z --cached
  --others --exclude-standard` : le classificateur refuse de muter `serveur.py`
  en place, et une poussée forcée (pousser sous un nouveau nom de branche).
- **Une mutation qui provoque un interblocage fige la suite** au lieu d'échouer :
  préférer une garde statique dérivée de l'arbre syntaxique (C4-T2).
- **Piloter Chrome ne demande rien à installer** (Node 24 expose `WebSocket`),
  mais les coordonnées de `Input.dispatchMouseEvent` sont relatives à la zone
  affichée — il faut défiler jusqu'à l'élément — et sans
  `Network.setCacheDisabled`, un PDF régénéré ressort identique à l'octet près.
  **`cdp.js` réutilise sans le dire un Chrome déjà en écoute sur le port 9222**,
  à une largeur inconnue : le bilan témoin fait 3 pages à 1 280 px, 6 vers
  760 px. Vérifier le port avant tout essai de rendu (C1-T6b).
- **La fiche de secours charge `script.js`.** Toute modification de ce fichier
  doit prouver que le PDF de `index-v1.html` reste identique au pixel.
- **Le dépôt est public, la fiche du prospect ne l'est pas.** Elle est ignorée
  par Git et gardée par `tests/test_confidentialite_prospect.py`, mais **rien
  ne garde les messages de commit ni les noms de branche** : n'y nommer aucun
  élément de sa fiche. Les données de test n'emploient qu'un vocabulaire fictif.

## Fichiers à ne jamais toucher

Ce sont les données réelles d'un cabinet en exercice, présentes à la racine et
exclues du suivi Git : la configuration (empreinte du mot de passe), les clés
privées du serveur et de l'autorité, le certificat de l'autorité, les deux
journaux et leurs archives, et le dossier des bilans produits.

Ne jamais les lire, les modifier ni les versionner — ni les emporter dans une
copie de travail. Le contrôle « aucun secret versionné » de
`.github/workflows/tests.yml` fait échouer la CI si l'un d'eux entre dans le
dépôt.
