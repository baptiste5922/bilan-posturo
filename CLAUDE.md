# bilan-posturo — état du projet

Application de bilan posturologique sur tablette : le praticien remplit le
formulaire et annote les schémas au stylet, le PDF est fabriqué dans le
navigateur et déposé sur le PC du cabinet. Utilisée quotidiennement depuis
août 2026 par une pédicure-podologue à Morlaix, pour la totalité de ses bilans.

**Dernière mise à jour :** 1er octobre 2026, par `/cloture-projet`
**Version :** V1 en production  **Jalon en cours :** V2 (voir `docs/ROADMAP.md`)

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
| `formulaire/script.js` (1135 l.) | PDF, stylet, brouillon, dépôt, file d'attente persistante |
| `formulaire/index.html` (388 l.) | Le formulaire, 17 blocs, ~78 champs — **écrit à la main** |
| `tests/` | 57 tests Python + 7 scénarios Node sur la file d'attente |
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
| C0 | Cadre juridique et licence | à faire — **décision en amont de tout** |
| C1 | Moteur de formulaire à schéma | à faire — le cœur du produit |
| C2 | Identité du cabinet en configuration | à faire |
| C3 | Adressage, certificat et installateur | à faire — verrou n°1, bloquant |
| C4 | Observabilité et support à distance | à faire |
| C5 | Mises à jour signées | à faire |
| C6 | Durcissement de sécurité (CSP, tentatives) | à faire |
| C7 | Filet de tests (pagination, moteur) | à faire |
| C8 | Mécanisme de licence d'abonnement | à faire |
| C9 | Atelier de fabrication d'un client | à faire |

Détail par tâche, critères d'acceptation et ordre d'exécution :
`docs/ROADMAP.md`. Analyse produit, prix et cadre juridique :
`docs/projection.md` (document interne, ne pas diffuser).

**Tests :** 57 Python + 7 Node, tous verts au 1er octobre 2026.

## Dernières sessions

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
- **Palette dupliquée** — les couleurs sont écrites à trois endroits :
  `style.css`, `script.js` (`FOND`, `FOND_RGB`, `TEXTE_RGB`) et un style en
  ligne dans `index.html:26`. Changer de palette sans les unifier fait sortir un
  PDF aux couleurs du cabinet précédent. C'est la tâche C1-T2.
- **`dossier_pdf` et le compte SYSTEM** — la tâche planifiée tourne en SYSTEM :
  un lecteur réseau monté dans la session du praticien n'existe pas pour elle.
  Chemin local absolu ou chemin UNC.
- **La file d'attente des dépôts n'a jamais tourné sur un vrai IndexedDB** :
  elle est validée sur un double simulé (tâche C7-T3).
- **Les scripts PowerShell n'ont jamais été exécutés hors du cabinet** : seule
  leur syntaxe est contrôlée en intégration continue.

## Fichiers à ne jamais toucher

Ce sont les données réelles d'un cabinet en exercice, présentes à la racine et
exclues du suivi Git : la configuration (empreinte du mot de passe), les clés
privées du serveur et de l'autorité, le certificat de l'autorité, le journal et
ses archives, et le dossier des bilans produits.

Ne jamais les lire, les modifier ni les versionner. Le contrôle « aucun secret
versionné » de `.github/workflows/tests.yml` fait échouer la CI si l'un d'eux
entre dans le dépôt.
