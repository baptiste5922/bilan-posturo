# C9-T2 — Fabriquer deux clients fictifs avec l'outil d'atelier

**Question posée** (`docs/projection.md` §3 et §8, `docs/ROADMAP.md` C9-T2) : un
opérateur d'atelier, avec l'outil `outils/atelier/atelier.js`, fabrique-t-il un
client complet — schéma, identité, logo, aperçu relu — en **strictement moins de
trois heures** ? Le temps de fabrication fixe le prix du setup et le plafond de
croissance : c'est ce seuil qu'on mesure.

**Seuil : strictement moins de trois heures, par cas.** Deux cas, A et B. Seule
la mesure de l'**opérateur humain** compte (critères M-A et M-B) : la
répétition de l'implémenteur, plus bas, ne compte pas.

Tout texte neuf n'emploie que le vocabulaire fictif « Bloc N / Texte N ». Le
dépôt est public : **aucun courriel ni téléphone n'est écrit en entier ici ni
dans aucun fichier versionné**. Pendant la mesure, ces deux champs se saisissent
depuis une valeur **dictée hors document** (une valeur fictive inventée sur le
moment, jamais celle d'un vrai cabinet). Rien de ce qui est fabriqué ne reste
dans le dépôt, et l'atelier refuse d'y écrire.

## Ce qui est mesuré, et ce qui ne l'est pas

- **Début** : l'ouverture de la feuille de route du cas (le texte ci-dessous),
  `date '+%Y-%m-%d %H:%M:%S'`.
- **Fin** : le **premier** `verifier` qui rend 0 *après* la dernière
  modification **et** l'aperçu relu **bloc par bloc** contre la feuille de route.
  Un `verifier` fait en cours de route n'arrête pas le chronomètre.
- **Exclus, et dits** : la **palette** (aucun mécanisme ne la livre : D-O2 du
  contrat, l'aperçu montre celle du pilote) ; l'**export d'essai sur la tablette**
  du client ; le **versement** du schéma dans `clients/` (D-O1 non tranchée) ;
  la fabrication du **paquet** (`outils/faire-paquet.sh`) ; le report de
  l'identité dans `config.json` (`python3 serveur/serveur.py --config`,
  voir l'avertissement ci-dessous) ; la pose du logo sous
  `formulaire/images/cabinet/`. Aucune de ces étapes n'est dans le chronomètre,
  et un temps plus long ne leur est pas imputé à l'atelier.
- **Le temps de l'outil compris** : chaque commande de l'atelier fait partie de
  la durée.

> **`python3 serveur/serveur.py --config` : à lancer UNIQUEMENT dans le dossier
> d'installation du cabinet, jamais depuis le dépôt.** Lancée depuis la racine
> du dépôt, la commande réécrit le `config.json` réel.

Un cas peut être **remplacé par une vraie feuille de route** de client : on ne
consigne alors que la **durée** et le **nombre de modifications**, rien de son
contenu (le dépôt est public).

## Préparation

Tout se passe depuis la racine du dépôt, dans un dossier de travail **hors du
dépôt** (l'atelier refuse tout autre emplacement). Choisir un nom de code, jamais
le nom du client.

```
cd <racine du dépôt>
T=$(cd "$(mktemp -d)" && pwd -P)
A() { node outils/atelier/atelier.js "$@"; }
```

`A` est une **fonction**, pas une variable : sous zsh (macOS), une variable
`A="node …"` n'est pas découpée en mots et la première commande rend 127.

## Cas A — départ `podologue-court`, logo, aperçu relu

```
date '+%Y-%m-%d %H:%M:%S'      # DÉBUT : à lancer en ouvrant cette feuille de route
A ouvrir "$T/a" --recette templates/podologue-court.json
```

Onze modifications du schéma :

1. Dans `"$T/a/recette.json"`, ajouter le fragment `examen-dynamique` **après**
   `examen-statique`, puis `A composer "$T/a"`. Les modifications 2 à 11 se
   font à la main dans `"$T/a/schema.json"`.
2. Retirer le bloc `oriente_par_bloc`.
3. Retirer le champ `niveau_scolaire` du bloc `patient_infos`.
4. Retirer le champ `metier` du bloc `patient_infos`.
5. Remplacer le libellé `Sport:` par `Texte 1 :` (la clé `sport` ne change pas).
6. Remplacer le titre `Consultation` par `Bloc 1` (bloc `consultation_bloc`).
7. Remplacer le titre `Appui:` par `Bloc 3` (bloc `appui`).
8. Retirer le bloc `specialistes_bloc`.
9. Ajouter, **juste après** le bloc `atcd_bloc`, ce bloc exactement :

   ```json
   {
     "cle": "bloc-1",
     "disposition": "en-ligne",
     "titre": "Bloc 2",
     "champs": [
       {
         "type": "radio",
         "valeurs": [
           { "cle": "texte-2", "valeur": "texte-2", "libelle": "Texte 2" },
           { "cle": "texte-3", "valeur": "texte-3", "libelle": "Texte 3" }
         ]
       }
     ]
   }
   ```

10. Ajouter **à la fin** des `champs` du bloc `section_conseils` ce champ
    exactement :

    ```json
    { "cle": "texte-4", "type": "zone-texte", "libelle": "Texte 4 :" }
    ```

11. Retirer le bloc `section_orientation`.

Les libellés s'écrivent avec une espace ordinaire avant les deux-points. Ne
jamais renommer une clé existante d'un bloc repris de la bibliothèque.

**Identité** (`"$T/a/identite-cabinet.json"`, sept clés, aucune en trop) :
`nom` = `Texte 5`, `praticien` = `Texte 6`, `adresse` = `Texte 7`, `courriel` et
`telephone` = valeurs fictives dictées hors document, `convention_nommage` =
`Bilan_{date}_{patient}`.

**Logo** : `cp formulaire/images/favicon.jpeg "$T/a/images/cabinet/logo.jpeg"`,
puis `"logo": "images/cabinet/logo.jpeg"` dans l'identité.

**Aperçu** : `A apercu "$T/a"`, puis ouvrir `"$T/a/apercu-atelier.html"` dans
Chrome, **à la largeur de la tablette** (l'aperçu l'affiche), et relire **chaque
bloc** contre les onze modifications : le bloc retiré n'y est plus, le libellé
neuf y est, le bloc neuf est après `ATCD:`. Ce n'est pas le PDF.

```
A verifier "$T/a"; echo "code $?"
date '+%Y-%m-%d %H:%M:%S'      # FIN : premier verifier à 0 APRÈS la dernière modification et l'aperçu relu
```

Attendu : code 0, `Dossier de travail valide (17 blocs).`, une seule ligne
`À FAIRE` (palette : le logo est posé, donc pas de rappel de logo).

## Cas B — départ `podologue-complet`, sans logo

```
date '+%Y-%m-%d %H:%M:%S'      # DÉBUT
A ouvrir "$T/b" --recette templates/podologue-complet.json
```

Onze rubriques, soit **treize gestes** (un retrait de fragment ou de champ
compte pour un) :

1. Dans `"$T/b/recette.json"`, **retirer** les fragments `examen-complementaire`
   et `chaussage`, puis `A composer "$T/b"`. Les rubriques 2 à 11 se font à
   la main dans `"$T/b/schema.json"`.
2. Retirer les champs `niveau_scolaire` puis `metier` du bloc `patient_infos`.
3. Remplacer le libellé `Sport:` par `Texte 1 :` (la clé `sport` ne change pas).
4. Remplacer le libellé `Conseils:` par `Texte 2 :` (champ `conseils`, bloc
   `section_conseils` ; la clé ne change pas).
5. Remplacer le titre `Consultation` par `Bloc 1`.
6. Retirer le bloc `specialistes_bloc`.
7. Retirer le bloc `section_empreinte_encre`.
8. Retirer le bloc `spin`.
9. Retirer le bloc `section_orientation`.
10. Ajouter, **juste après** `atcd_bloc`, le bloc `bloc-1` exactement comme au
    cas A (modification 9).
11. Ajouter **à la fin** des `champs` du bloc `section_conseils` le champ
    `texte-4` exactement comme au cas A (modification 10).

Les rubriques 1 et 2 comptent chacune pour deux gestes, les rubriques 6 à 9
ensemble pour quatre : 2 + 2 + 1 + 1 + 1 + 4 + 1 + 1 = 13.

**Identité** : comme au cas A, avec **`logo` laissé vide** (`""`) et
`convention_nommage` = `{nom}_{prenom}_{date}`. Pas de dossier `images/cabinet/`
garni.

**Aperçu** : `A apercu "$T/b"`, relu **bloc par bloc**.

```
A verifier "$T/b"; echo "code $?"
date '+%Y-%m-%d %H:%M:%S'      # FIN
```

Attendu : code 0, `Dossier de travail valide (21 blocs).`, un seul `À FAIRE`
(palette).

## Répétition de l'implémenteur — non comptée

Jouée par l'agent qui a implémenté C9-T2, le 7 novembre 2026, **par script**
(les modifications sont faites par un court programme Python, non versionné, qui
n'appelle que les commandes de l'atelier). Elle prouve que le protocole se
déroule sans accroc, que les cibles existent bien dans les schémas composés et
que les nombres de blocs attendus sont les bons ; sa durée n'a aucune valeur de
mesure (aucune relecture humaine, aucune saisie).

| Élément | Cas A | Cas B |
|---|---|---|
| Début / fin (durée) | `2026-11-07 00:40:55` / `2026-11-07 00:40:55` (0,3 s) | idem (0,3 s) |
| Modifications faites | 11 sur 11 | 13 gestes sur 13 |
| `verifier` | `Dossier de travail valide (17 blocs).`, code 0 | `Dossier de travail valide (21 blocs).`, code 0 |
| Aperçu écrit | oui | oui |

## Constat de rendu réel (critère A12)

Aucune capture n'est versionnée. Joué le 7 novembre 2026 avec Google Chrome
156.0.8078.80 piloté par `outils/reference-visuelle/cdp.js` (port 9333, fenêtre de
1 280 × 900 px, cache désactivé), sur l'aperçu de `podologue-complet` (identité :
praticien renseigné, logo par défaut). Un second client du protocole de débogage
écoutait `Network`, `Runtime` et `Log` pendant le chargement.

| Observation | Résultat |
|---|---|
| Zone d'erreurs de la bannière (`#erreurs-apercu`) | masquée, texte vide |
| Console (`Runtime.consoleAPICalled`, `exceptionThrown`, `Log.entryAdded`) | aucune entrée |
| Chargements en échec (`Network.loadingFailed`) | aucun |
| Blocs rendus dans `#form-bilan main` | 28 ; 52 champs de saisie |
| Images annotables : `naturalWidth` | `squelette_gauche` 887, `squelette_droite` 1024, `squelette_dos` 887, `image_empreintes` 1536 — toutes > 0 |
| Requêtes (`Network.requestWillBeSent`) | 7, **toutes `file://`** : la page, `style.css`, `moteur/rendu.js`, les quatre images ; **aucune** autre |
| Scripts chargés | `moteur/rendu.js` seul (ni `script.js`, ni jsPDF, ni html2canvas) |
| Largeur affichée par la bannière | `1280` à 1 280 px ; `900` après passage à 900 px (le redimensionnement est suivi) |

Le repli prévu au contrat (`--allow-file-access-from-files`) n'a pas été
nécessaire : Chrome applique `<base href>` en `file://` et exécute le script
inline.

## Mesure officielle (Baptiste) — à remplir

À consigner par l'opérateur, après avoir joué le protocole ci-dessus. Seuil :
**strictement moins de trois heures par cas**.

| Élément | Cas A | Cas B |
|---|---|---|
| Opérateur | | |
| Gabarit de départ | `podologue-court` | `podologue-complet` |
| Début (`date '+%Y-%m-%d %H:%M:%S'`) | | |
| Fin (premier `verifier` à 0, aperçu relu) | | |
| Durée | | |
| Modifications faites (11 / 13 gestes attendus) | | |
| Sortie de `verifier` | | |
| Aperçu relu bloc par bloc ? | | |
| Verdict (durée < 3 h, modifications faites, `verifier` à 0, aperçu relu) | | |

Remarques de l'opérateur (ce qui a coincé, ce que l'outil ne dit pas, ce que
l'aperçu ne montre pas) :
