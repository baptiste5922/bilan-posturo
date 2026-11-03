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
| `logo` | Chemin du logo, relatif à `formulaire/`. **Déclaré et renvoyé par la route dès C2-T1, mais le formulaire ne s'en sert pas encore** — `formulaire/index.html` continue d'afficher `images/favicon.jpeg` en dur ; servir ce chemin est C2-T2 | `"images/favicon.jpeg"` |
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
une clé supplémentaire sous `cabinet` ne la verrait jamais ressortir. Aucune
autre clé de la configuration (`mot_de_passe`, `utilisateur`, `certificat`,
`cle_privee`, `dossier_pdf`, `port`) n'apparaît jamais dans cette réponse, à
quelque titre que ce soit.

La route est authentifiée, à la différence de `/sante` : des coordonnées
professionnelles ne sont pas un secret au sens strict, mais rien n'oblige à
les offrir à qui scanne le port.
