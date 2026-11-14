# Le bloc `cabinet` de `config.json`

**Contrat :** `docs/contrats/C2-T1.md`
**Date :** 21 octobre 2026

---

## 1. Pourquoi ce bloc existe

Avant cette tâche, le nom, l'adresse, le courriel et le téléphone de la
praticienne étaient écrits en dur dans `formulaire/index.html` et
`formulaire/index-v1.html` — deux fichiers du dépôt, qui est public. Cette
identité vit désormais dans `config.json`, à la racine, **hors suivi Git**, et
le formulaire la lit au chargement par la route authentifiée `GET /cabinet`.

Un bilan PDF produit sans en-tête n'est pas versable au dossier patient : le
serveur refuse donc l'export plutôt que de laisser sortir un document de
santé non identifiable (décision D7 du contrat). C'est pourquoi la marche à
suivre ci-dessous n'est pas optionnelle au premier démarrage.

## 2. Marche à suivre au cabinet déjà installé

Un cabinet mis à jour depuis une version antérieure à C2-T1 a un
`config.json` **sans** bloc `cabinet` — ce n'est pas une erreur, et le serveur
démarre quand même, en l'écrivant sur sa sortie standard :

```
AVERTISSEMENT : identité du cabinet non configurée — les bilans ne pourront
pas être exportés.
Lancez :  python3 serveur/serveur.py --config
```

La marche à suivre est donc, dans le même passage que la mise à jour, jamais
à distance :

```bash
python3 serveur/serveur.py --config
```

Cette commande demande d'abord l'identifiant et le mot de passe (inchangé
depuis la V1), puis les sept champs du bloc `cabinet`, un par un, la valeur
courante affichée entre crochets. **Une saisie vide conserve la valeur
courante** pour l'identifiant et les sept champs du bloc `cabinet` : relancer
`--config` pour changer le mot de passe ne touche pas à l'identité déjà
saisie.

**Le mot de passe, lui, est toujours redemandé** (huit caractères au moins)
et son empreinte réécrite. Au cabinet déjà installé, qui ne vient que saisir
son identité, **retaper le mot de passe actuel** : en choisir un autre ferait
perdre l'accès à la tablette dès la consultation suivante, jusqu'à ce que le
nouveau y soit saisi.

`config.json` est réécrit en entier à la fin de la saisie (permissions
`600`) : c'est le seul moment où ce fichier est modifié, et c'est toujours un
geste volontaire sur la machine du cabinet.

## 3. Les sept champs

| Champ | Rôle | Défaut |
|---|---|---|
| `nom` | Raison sociale ou nom du cabinet, à usage interne (pas affiché aujourd'hui dans l'en-tête, réservé à un usage futur) | `""` |
| `praticien` | Nom et qualité de la praticienne, première ligne de l'en-tête. **Champ pivot** : tant qu'il est vide, l'export est refusé (voir §4) | `""` |
| `adresse` | Adresse postale, deuxième ligne de l'en-tête | `""` |
| `courriel` | Affiché précédé de `mail: ` | `""` |
| `telephone` | Affiché précédé de `tel: ` | `""` |
| `logo` | Chemin du logo, relatif à `formulaire/` ; **servi depuis C2-T2**, voir §7. `""` = pas de logo. Validé une fois, au démarrage du serveur | `"images/favicon.jpeg"` |
| `convention_nommage` | Gabarit du nom de fichier PDF, voir §5 | `"Bilan_{date}_{patient}"` |

**Les cinq champs d'identité ont une valeur par défaut vide, jamais un
exemple générique** (décision D3) : un « Cabinet de podologie, 1 rue de
l'Exemple » écrit par défaut finirait, un jour ou l'autre, imprimé sur un
bilan réel. Mieux vaut un en-tête absent — et l'export refusé qui va avec —
qu'un en-tête faux.

## 4. Ce que le formulaire en fait

Au chargement de la page, `formulaire/script.js` interroge `GET /cabinet`
(authentifiée, comme le reste du formulaire) et remplit l'ancre
`<section id="infos_podo">` avec un `<p>` par champ non vide, dans l'ordre
`praticien`, `adresse`, `courriel` (préfixé `mail: `), `telephone` (préfixé
`tel: `). Ce chargement est **asynchrone** : le formulaire s'affiche et reste
saisissable sans attendre, le brouillon continue d'être sauvegardé que la
route réponde ou non.

L'export, lui, est **refusé** — pas dégradé — tant que `praticien` est vide ou
que la route ne répond pas (401, injoignable, JSON invalide), après une
seconde tentative : la saisie n'est jamais perdue (brouillon `localStorage`),
mais aucun PDF n'est produit, aucune entrée n'entre dans la file de dépôt. Le
niveau 0 du retour arrière (`docs/contrats/C2-T1.md`, §11) est : corriger
`config.json`, redémarrer le serveur, recharger la page sur la tablette.

## 5. `convention_nommage` et ses quatre marqueurs

Le nom de fichier PDF est construit par substitution de gabarit, quatre
marqueurs disponibles :

| Marqueur | Valeur |
|---|---|
| `{date}` | Le champ « Réalisé le » du bilan, ou la date du jour s'il est vide |
| `{nom}` | Le champ « Nom » du patient |
| `{prenom}` | Le champ « Prénom » du patient |
| `{patient}` | `{nom}-{prenom}` si l'un des deux est renseigné, sinon `sans-nom` — c'est exactement la valeur que composait le code avant cette tâche |

Avec le gabarit par défaut `"Bilan_{date}_{patient}"`, la sortie est
**identique, caractère pour caractère**, à celle produite avant C2-T1 : c'est
la condition qui protège la production, vérifiée par
`tests/test_nommage.js`.

Un marqueur inconnu (`{autre_chose}`) est remplacé par la chaîne vide. Un
gabarit vide, ou qui ne rend qu'une chaîne vide après substitution, retombe
sur le gabarit par défaut plutôt que de produire un nom réduit à `.pdf`.
L'extension `.pdf` est toujours ajoutée par le code, **jamais par le
gabarit** : un gabarit fautif ne doit pas pouvoir produire un nom que le
serveur refuse.

Le serveur assainit ce nom de son côté (`assainir_nom()`,
`serveur/serveur.py`) avant de l'écrire sur le disque : un gabarit contenant
`../` ne permet toujours aucune écriture hors du dossier des PDF. Ce n'est
pas parce que le nom est désormais déclaré en configuration qu'il devient une
source de confiance — il traverse toujours la même barrière.

## 6. Ce que la route `GET /cabinet` renvoie, et ce qu'elle ne renvoie jamais

La réponse est un JSON construit par itération sur les sept clés ci-dessus,
jamais par sérialisation directe du fichier : un `config.json` qui porterait
une clé supplémentaire sous `cabinet` ne la verrait jamais ressortir. Pour
`logo`, la réponse ne rend pas la valeur du fichier mais le chemin **validé au
démarrage** (§7), ou `""`. Aucune
autre clé de la configuration (`mot_de_passe`, `utilisateur`, `certificat`,
`cle_privee`, `dossier_pdf`, `port`) n'apparaît jamais dans cette réponse, à
quelque titre que ce soit.

La route est authentifiée, à la différence de `/sante` : des coordonnées
professionnelles ne sont pas un secret au sens strict, mais rien n'oblige à
les offrir à qui scanne le port.

## 7. Le logo (C2-T2)

L'image `#logo` de l'en-tête, et donc le logo qui figure en première page du
PDF, est celle que déclare `cabinet.logo`. Au démarrage, le serveur valide ce
chemin **une fois** ; un chemin refusé n'est jamais proposé à la tablette.

**Les règles** :

- relatif à `formulaire/`, avec des `/` : lettres sans accent, chiffres,
  `_`, `-` et `.` (jamais en tête de nom), pas d'espace ;
- **sous `images/cabinet/`, sur un seul niveau** (`images/cabinet/<nom>.png`),
  **ou exactement** le logo par défaut `images/favicon.jpeg`. Tout autre chemin
  sous `formulaire/` est refusé (`forme-invalide`) : seul ce dossier est ignoré
  par Git et refusé par `outils/faire-paquet.sh`, un logo posé ailleurs serait
  emballé pour le client suivant ;
- PNG ou JPEG (`.png`, `.jpg`, `.jpeg`), dont le contenu est bien celui d'une
  telle image ;
- 512 Kio au plus : le logo s'affiche en 130 × 130 px ;
- ni remontée (`..`), ni chemin absolu, ni lecteur (`C:`), ni adresse
  (`https://…`) ;
- aucun lien symbolique ni jonction, ni sur le fichier ni sur un dossier du
  chemin, même vers l'intérieur de `formulaire/` ;
- `""` : **pas de logo**, c'est un choix et non une anomalie (la case « pas de
  logo » de la feuille de route client).

À l'ouverture de la page, la tablette affiche d'abord le logo par défaut, le
temps de recevoir l'identité du cabinet ; puis elle le remplace ou le masque.
Ce bref affichage ne touche jamais le PDF, qui attend le logo configuré.

**Un logo refusé donne pas de logo**, jamais le logo par défaut : l'emblème de
la podologie n'a rien à faire sur le bilan d'un autre métier. L'export reste
possible, sans logo (seul `praticien` est pivot, §4).

**Installer le logo d'un cabinet** : il porte en général le nom ou l'enseigne du
cabinet, donc il l'identifie, et **il ne vit jamais dans le dépôt** (public). Il
est conservé à l'atelier hors dépôt, puis posé **sur le PC du cabinet** :

1. copier le fichier sous `formulaire/images/cabinet/` (dossier à créer ; il est
   ignoré par Git, et `outils/faire-paquet.sh` refuse d'emballer un atelier qui
   le contient) ; nom sans accent ni espace, par exemple `logo.png` ;
2. lancer `python3 serveur/serveur.py --config` et répondre
   `images/cabinet/logo.png` à l'invite `logo` (ou éditer `config.json`) ;
   `--config` avertit si le chemin serait refusé, et écrit quand même ;
3. redémarrer le serveur, recharger la page sur la tablette, exporter un bilan
   d'essai et regarder la première page.

Une mise à jour ne touche jamais ce dossier (C5-T2a) : le client de mise à jour
refuse tout chemin sous `formulaire/images/cabinet/`, quelle que soit la casse,
même dans un paquet signé, et remplace les fichiers un par un au lieu de
remplacer `formulaire/`. Après une réinstallation **à la main** (dossier
recopié), en revanche, reposer le fichier.

**Où lire un refus** :

- `journal.log` (reste au cabinet) : la ligne
  `LOGO refusé motif=<motif> chemin='<chemin>'`, le chemin entre `repr()` ;
- `technique.log` (peut circuler) : `LOGO refus motif=<motif>`, **sans le
  chemin** ; c'est aussi ce que la page `/etat` montre parmi les dernières
  lignes ;
- la console du serveur : `AVERTISSEMENT : logo refusé (<motif>)`.

Les motifs : `hors-racine`, `forme-invalide`, `extension-non-servie`,
`lien-symbolique`, `absent`, `trop-volumineux`, `illisible`.

`absent` : aucun fichier ne porte exactement ce nom. Sous Windows, vérifier
aussi la casse : `Logo.png` n'est pas `logo.png`.

**Le service statique ne suit aucun lien** (C6-T6). Un lien symbolique ou une
jonction posés sous `formulaire/` ne sont jamais servis : le serveur répond 404,
comme pour un fichier absent, et note `lecture refusée motif=lien-symbolique`
dans `journal.log` (jamais dans `technique.log`). Cela vaut pour tout fichier,
pas seulement le logo. Sous Windows, une différence de casse seule dans l'URL
(`/INDEX.HTML`) reste servie ; le logo, lui, refuse une casse différente.

**Retour arrière** : mettre `"logo": "images/favicon.jpeg"` (ou `""`) dans
`config.json` et relancer le serveur.

## 8. Le bloc `mise_a_jour` (C5-T2a, C5-T2b)

```json
"mise_a_jour": {
  "client": "cabinet-01",
  "adresse": "<adresse>",
  "plage": "20:00-07:00",
  "calme_minutes": 30,
  "au_demarrage": true,
  "proxy": ""
}
```

Toutes les clés sont facultatives, **sauf `client` pour appliquer un paquet**. Le
serveur ignore ce bloc : un `config.json` qui le porte reste lisible par une version
plus ancienne.

| Clé | Défaut | Forme admise | Si elle est fausse |
|---|---|---|---|
| `client` | — | `cabinet-NN` (au moins deux chiffres) : le client auquel ce PC appartient. Un paquet signé pour un autre client est refusé (`CLIENT_DIFFERENT`). | `CLIENT_NON_CONFIGURE` |
| `adresse` | absente : **désactivé** | `""` (désactivé) ou une adresse `https://…` sans identifiant (`@`), sans `?` ni `#`, sans espace, ASCII, 1 024 caractères au plus, et **terminée par `.zip`**. Le manifeste et la signature se déduisent de cette adresse en y ajoutant `.manifeste.json` et `.manifeste.sig`. | `ADRESSE_INVALIDE` |
| `plage` | `"20:00-07:00"` | `HH:MM-HH:MM` sur 24 heures, début ≠ fin, début inclus et fin exclue ; traverse minuit quand le début est postérieur à la fin. | `PLAGE_INVALIDE` |
| `calme_minutes` | `30` | un entier de 1 à 240 (pas un booléen, pas un texte). Dans la plage, le serveur doit n'avoir reçu aucune requête depuis ce délai. | `PLAGE_INVALIDE` |
| `au_demarrage` | `true` | `true` ou `false`. Vrai : hors plage, la mise à jour reste possible dans le quart d'heure qui suit le démarrage du PC, si le serveur n'a reçu aucune requête (un PC éteint la nuit ne se mettrait sinon jamais à jour). | `PLAGE_INVALIDE` |
| `proxy` | `""` | `""` ou `http://<hôte>:<port>` (port obligatoire, pas d'identifiant). Seule source de proxy : l'environnement et le registre ne sont jamais lus. | `ADRESSE_INVALIDE` |

**Une clé présente et fausse n'est jamais remplacée par son défaut** : la mise à jour
ne s'applique pas (échec fermé), une ligne `MAJ_REFUSEE` dit laquelle (au plus une par
jour), et rien n'est téléchargé. Une plage fausse n'applique donc pas `20:00-07:00`.

**Désactiver** : retirer `adresse` ou l'écrire `""` ; effet au passage suivant de la
tâche (une heure au plus), sans relancer le serveur. **Activer**, c'est l'écrire : en
séance d'assistance, après la semaine de bilans réels qui suit la visite.

**L'adresse identifie un client** et ouvre son paquet (code public et schéma, aucune
donnée de santé). Elle ne figure ni dans `technique.log`, ni dans `/etat`, ni sur la
console, et `journal.log` n'en nomme que l'hôte. Elle ne se commite jamais : côté
éditeur, elle est notée dans `adresse-publication.json`, dans le dossier de travail du
client à l'atelier (hors dépôt, ignoré par Git et refusé par la CI), et ce fichier se
sauvegarde comme `identite-cabinet.json`.

Sans la clé `client`, `python serveur\maj.py appliquer` refuse (`CLIENT_NON_CONFIGURE`)
et **rien d'autre ne change**.

La marche à suivre complète (amorçage à la visite, application à la main, mise à jour
automatique, lecture de l'état, retour arrière) est dans `docs/mise-a-jour.md`.
