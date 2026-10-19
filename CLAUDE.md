# bilan-posturo — état du projet

Application de bilan posturologique sur tablette : le praticien remplit le
formulaire et annote les schémas au stylet, le PDF est fabriqué dans le
navigateur et déposé sur le PC du cabinet. Utilisée quotidiennement depuis
août 2026 par une pédicure-podologue à Morlaix, pour la totalité de ses bilans.

**Dernière mise à jour :** 19 octobre 2026, par `/cloture-projet`
**Version :** V1 en production, sous **BUSL 1.1** depuis le 14 octobre 2026
**Jalon en cours :** V2 — 4 tâches livrées ; le formulaire tourne sur le moteur
à schéma dans le dépôt, pas encore au cabinet (voir `docs/ROADMAP.md`)

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
| `serveur/serveur.py` (632 l.) | HTTPS, dépôt des PDF, authentification, sonde `/sante`, journal |
| `serveur/generer_autorite.py` (248 l.) | Autorité de certification locale + certificat serveur |
| `formulaire/script.js` (1223 l.) | PDF, stylet, brouillon, dépôt, file d'attente, lecture des tokens de couleur |
| `formulaire/index.html` (388 l.) | Le formulaire, 17 blocs, ~78 champs — **écrit à la main** |
| `formulaire/style.css` | La palette du cabinet : cinq tokens sur `:root`, **source unique** |
| `formulaire/moteur/rendu.js` | Valide un schéma et construit le DOM du formulaire (C1-T3) |
| `formulaire/schema.json` | Les 28 blocs du corps du bilan, en données |
| `tests/` | 73 Python + Node : 7 (file), 8 (palette), 7 (inventaire), 8 (comparaison de DOM) |
| `installer-demarrage.ps1` | Tâche planifiée Windows, jamais exécuté hors du cabinet |

Le PDF est produit **côté navigateur** : le serveur ne reçoit qu'un fichier déjà
assemblé, et n'a aucune dépendance Python.

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
  plus que l'existence du port.
- **Code, commentaires et messages en français**, accents compris.
- **Un seul utilisateur en production** : toute modification du formulaire peut
  casser une consultation le lendemain matin. Prévoir le retour arrière.

## Avancement V2

Trois hypothèses implicites structurent la V1, et ce sont celles que le passage
à plusieurs cabinets casse : un seul cabinet, un seul installateur, le bilan est
une image et non une donnée.

| Chantier | Intitulé | État |
|---|---|---|
| C0 | Cadre juridique et licence | C0-T1 **livré** (BUSL 1.1) ; C0-T2 à faire |
| C1 | Moteur de formulaire à schéma | C1-T2, C1-T1, C1-T3 et C1-T3b **livrés** ; reste C1-T4 (schéma client) et C1-T5 (bibliothèque de blocs) |
| C2 | Identité du cabinet en configuration | à faire |
| C3 | Adressage, certificat et installateur | à faire — verrou n°1, bloquant |
| C4 | Observabilité et support à distance | à faire |
| C5 | Mises à jour signées | à faire |
| C6 | Durcissement de sécurité (CSP, tentatives) | à faire |
| C7 | Filet de tests (pagination, moteur) | à faire — C7-T5 ouverte le 14/10 |
| C8 | Mécanisme de licence d'abonnement | à faire |
| C9 | Atelier de fabrication d'un client | à faire |

**Licence.** Les développements depuis le commit `9339ee9` (étiqueté
`frontiere-mit`) sont sous **BUSL 1.1** : lecture, fork et modification libres,
usage en production réservé à un cabinet pour ses propres patients, bascule en
MIT au bout de quatre ans. L'historique antérieur reste MIT à jamais. Explication
en français : `docs/licence.md` ; seul `LICENSE` fait foi. **Ne pas rouvrir ce
choix** ; il se corrige vers l'avant si besoin.

Détail par tâche, critères d'acceptation et ordre d'exécution :
`docs/ROADMAP.md`. Analyse produit, prix et cadre juridique :
`docs/projection.md` (document interne, ne pas diffuser).

**Vocabulaire du schéma.** Fixé par C1-T1, le 15 octobre :
`docs/schema-formulaire.md` est la source de vérité du format — sept types
fermés, clés reprises à l'identique des `id` du formulaire, version du format
en première clé. C1-T3, C1-T4, C7-T2 et C9-T1 s'y règlent sans rouvrir le
débat.

**Le moteur est branché dans le dépôt, pas encore au cabinet.**
`formulaire/index.html` est une coquille de 118 lignes que le moteur remplit
depuis `formulaire/schema.json`. La V1 est conservée octet pour octet dans
`formulaire/index-v1.html`, servie : c'est le **retour arrière de niveau 1**, le
favori « Formulaire — secours V1 », et le témoin qui garde les clés de brouillon
dans les tests.

**Le rendu a été comparé page à page et le repli éprouvé** le 19 octobre, dans
Chrome piloté et contre un vrai serveur en bac à sable : les six pages sont
identiques au pixel près, et une saisie commencée sur le moteur se reprend sur
la fiche de secours, PDF déposé compris. Cinq écarts de rendu avaient été
trouvés et corrigés à cette occasion — aucun n'était visible des 115 tests.
Détail : `docs/references-visuelles/CONSTAT-2026-10-19.md` ; outillage
rejouable : `outils/reference-visuelle/`.

**Reste un seul geste avant de livrer au cabinet** : poser le favori de secours
sur la tablette et l'ouvrir une fois. Il demande l'appareil ; le chemin qu'il
emprunte est éprouvé.

**Tests :** 115 au total, tous verts au 19 octobre 2026, en intégration continue
sur Linux, Windows et macOS : 81 Python, 7 Node (file), 8 (palette),
8 (inventaire), 8 (comparaison de DOM), 4 (démarrage du moteur).

## Dernières sessions

- [2026-10-19 — La bascule, et ce que le rendu réel a révélé](docs/resumes/2026-10-19-bascule-et-fidelite.md) :
  C1-T3b livrée. Cinq écarts de rendu trouvés par comparaison dans un vrai
  navigateur, et corrigés ; repli éprouvé contre un vrai serveur.
- [2026-10-15 (2) — Le moteur de rendu, sans la bascule](docs/resumes/2026-10-15-moteur-de-rendu.md) :
  C1-T3 étapes 1 à 8. Moteur, schéma, comparateur V1 ↔ moteur. `index.html` intact.
  Non commité, branche `c1-t3-moteur-rendu-schema`.
- [2026-10-15 — Le vocabulaire du schéma de formulaire](docs/resumes/2026-10-15-vocabulaire-de-schema.md) :
  C1-T1 livrée. 29 blocs et 45 champs inventoriés, sept types fermés, clés gelées.
  Travail non commité, sur la branche `c1-t1-inventaire-formulaire`.
- [2026-10-14 — Licence BUSL et palette unifiée](docs/resumes/2026-10-14-licence-et-tokens.md) :
  V1 enfin versionnée (elle n'existait que sur un disque), C0-T1 et C1-T2 livrées.
- [2026-10-01 — Outillage de la V2](docs/resumes/2026-10-01-outillage-v2.md) :
  feuille de route V2, quatre agents, quatre compétences.

## Comment on travaille ici

Une tâche de la feuille de route suit toujours la même chaîne :

| Étape | Commande | Produit |
|---|---|---|
| 1. Contrat | `/lancer-tache <ID>` | `docs/contrats/<ID>.md` |
| 2. Implémentation + audit | `/implementer-tache <ID>` | code, tests, `docs/audits/<ID>.md` |
| 3. Revue | `/revue-code <ID>` | `docs/revues/<ID>.md` |
| 4. Clôture | `/cloture-projet` | ce fichier, et `docs/resumes/<date>.md` |

On n'implémente jamais sans contrat. Les agents correspondants vivent dans
`.claude/agents/` : `planificateur-tache`, `implementeur`, `auditeur-securite`,
`reviseur-code`.

**Ce fichier est maintenu exclusivement par `/cloture-projet`**, et doit rester
sous 300 lignes. Il oriente ; il ne recopie pas `docs/ROADMAP.md`.

## Pièges connus

Ils ont déjà coûté du temps ; ils le recoûteront.

- **ALPN** — sans `set_alpn_protocols`, Chrome ferme la connexion sans envoyer
  un octet, là où curl retombe silencieusement sur HTTP/1.1. Symptôme :
  `ERR_EMPTY_RESPONSE` sans aucune trace serveur.
- **Erreurs TLS invisibles** — la négociation a lieu dans `get_request()`, et
  `socketserver` y avale l'`OSError` sans rien journaliser. La méthode est
  surchargée pour les faire remonter.
- **`SO_REUSEADDR`** — sous Windows, laisse deux processus se lier au même port,
  l'ancien répondant encore pendant que le nouveau annonce un démarrage réussi.
  Le drapeau est donc conditionné à `os.name`.
- **`hmac.compare_digest`** — lève `TypeError` sur une chaîne contenant un
  caractère non ASCII. Un identifiant accentué tuait le fil d'exécution. La
  comparaison se fait sur des octets UTF-8.
- **Double pile** — `localhost` résout d'abord en `::1` : un serveur lié au seul
  `0.0.0.0` y est injoignable. On écoute en IPv6 avec `IPV6_V6ONLY` désactivé,
  avec repli IPv4.
- **Palette — piège refermé par C1-T2, à ne pas rouvrir.** Les cinq couleurs
  d'identité vivent **uniquement** sur `:root` dans `style.css` ; le PDF les lit
  par `getComputedStyle` à chaque génération. Réécrire une de ces valeurs
  ailleurs fait ressortir le défaut d'origine — un PDF aux couleurs du cabinet
  précédent — et un pas d'intégration continue le refuse. La lecture doit rester
  **dans** la génération : au niveau module, elle casse les tests de la file
  d'attente, dont le contexte `vm` n'a pas `getComputedStyle`.
- **`dossier_pdf` et le compte SYSTEM** — la tâche planifiée tourne en SYSTEM :
  un lecteur réseau monté dans la session du praticien n'existe pas pour elle.
  Chemin local absolu ou chemin UNC.
- **La file d'attente des dépôts n'a jamais tourné sur un vrai IndexedDB** :
  elle est validée sur un double simulé (tâche C7-T3).
- **Les scripts PowerShell n'ont jamais été exécutés hors du cabinet** : seule
  leur syntaxe est contrôlée en intégration continue.
- **`actions/checkout` clone à la profondeur 1.** `.git` existe donc en
  intégration continue, mais pas les commits antérieurs à `HEAD` : un test qui a
  besoin d'un autre commit doit vérifier **l'objet** (`git cat-file -e`), pas le
  dossier. Et `git log -1 -- <fichier>` y rend la date de `HEAD`, donc toute
  mesure de date tirée de l'historique y est silencieusement fausse.
- **`git ls-files` sans `-z`** échappe les chemins non ASCII à la façon du C et
  les entoure de guillemets. Tous les documents de ce dépôt portent des noms
  français : un contrôle de contenu bâti dessus les manque sans rien dire. Et
  `xargs -0 grep` rend 123 aussi bien pour « rien trouvé » que pour une erreur
  réelle — les deux cas y sont indistinguables, il faut une boucle.
- **Un contrôle qui lit l'index Git doit être éprouvé sur des fichiers indexés.**
  Validé sur des fichiers non suivis, il ne voit rien : `git ls-files` ne les
  liste pas. C'est ainsi que six travaux d'intégration continue ont échoué le
  14 octobre.
- **Le rendu réel voit ce qu'aucun test ne voit.** Le 19 octobre : 115 tests
  verts, audit CONFORME, revue À LIVRER — et **cinq** écarts de rendu quand
  même, dont un titre de bloc qui ne s'affichait pas du tout. Trois tenaient à
  des détails qu'on ne pense pas à tester : une espace entre deux balises, un
  `<label>` vide, un deux-points collé. **Le moteur n'invente ni ponctuation ni
  structure** : le schéma porte le texte exact qui s'affiche, et les formes qui
  ne s'en déduisent pas sont des attributs à valeurs fermées. Toute comparaison
  de rendu se rejoue avec `outils/reference-visuelle/`.
- **Se méfier de ses propres tolérances.** Le premier verdict de cette
  comparaison disait « identiques, le reste est du bruit JPEG ». Mesure faite,
  le bruit réel est **nul** : deux exports de la même page sont nombre pour
  nombre identiques. Une tolérance inventée pour expliquer un écart est ce qui
  fait passer un défaut pour du bruit.
- **Ne jamais lancer `serveur.py` ni `generer_autorite.py` depuis le dépôt.**
  Ils calculent leur racine depuis leur propre emplacement et **écraseraient**
  les fichiers réels du cabinet, qui vivent à la racine. Tout essai se fait sur
  une copie, dans un bac à sable — c'est ainsi que le repli a été éprouvé.
- **Piloter Chrome ne demande rien à installer** (Node 24 expose `WebSocket`),
  mais deux pièges : les coordonnées de `Input.dispatchMouseEvent` sont
  relatives à la **zone affichée**, donc il faut défiler jusqu'à l'élément ; et
  sans `Network.setCacheDisabled`, un PDF régénéré après correction ressort
  identique à l'octet près.
- **Un garde-fou non mis en échec ne garde rien.** Deux fois le 15 octobre, le
  même défaut : des listes normatives recopiées à la main (C1-T1), puis un
  comparateur qui aplatissait l'arbre et sautait deux blocs sur 29 (C1-T3). Les
  deux passaient au vert sur un formulaire modifié. **Dériver du code, jamais
  transcrire ; et éprouver chaque test par une mutation volontaire.** Corollaire :
  une tolérance ajoutée pendant l'implémentation est le moyen le plus simple de
  faire taire un comparateur — celui de C1-T3 en compte neuf, toutes motivées,
  mais la neuvième ne tient que parce qu'aucun sélecteur enfant `>` n'existe
  encore dans `style.css`.
- **Le rendu ne doit pas démarrer après `DOMContentLoaded`.** `initDessin()`
  exige que les quatre images soient déjà dans le DOM ; sinon `zonesDessin` est
  vide, le stylet ne répond plus et les traits d'un brouillon restauré tombent
  dans le vide. D'où `demarrerApplication()`, appelée **par le moteur, après
  rendu**.
- **Les clés de brouillon sont gelées — piège refermé par C1-T1.** Les `id` du
  formulaire *sont* les clés du brouillon `localStorage` (`cleChamp()`,
  `script.js:863-867`). Les renommer — même pour corriger `familliaux`,
  `spécialistes`, `symétrique`, `pédieux` — perd le bilan d'une consultation en
  cours. `docs/schema-formulaire.md` les documente comme volontairement
  conservés ; la tentation de « nettoyer » est le principal risque de C1-T3.
- **Une liste normative recopiée à la main finit fausse.** Les trois constats
  sérieux de C1-T1 étaient la même erreur : clés gelées recopiées donc
  incomplètes, décompte figé en constante dans un test, liste de « 9 blocs » qui
  en contenait 10. Dériver du code, jamais transcrire. Et toute garde ancrée sur
  des **numéros** de ligne devient silencieusement verte quand le fichier bouge :
  celle de l'identité du cabinet le fera en C1-T3.
- **`ServeurEnMarche` est instable sous Windows et Python 3.9** : ses dix tests
  ont expiré en lecture TLS une fois, puis sont repassés au vert sur simple
  relance, sans modification de code. C'est le harnais, pas le serveur (C7-T5).
  Ne pas prendre l'habitude de relancer : le jour où l'échec sera réel, on
  relancera aussi.

## Fichiers à ne jamais toucher

Ce sont les données réelles d'un cabinet en exercice, présentes à la racine et
exclues du suivi Git : la configuration (empreinte du mot de passe), les clés
privées du serveur et de l'autorité, le certificat de l'autorité, le journal et
ses archives, et le dossier des bilans produits.

Ne jamais les lire, les modifier ni les versionner. Le contrôle « aucun secret
versionné » de `.github/workflows/tests.yml` fait échouer la CI si l'un d'eux
entre dans le dépôt.
