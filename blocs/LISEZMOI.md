# blocs/ — la bibliothèque de fragments

Chaque fichier de ce dossier est un **fragment** : un ou plusieurs **blocs
entiers** du format de schéma (`docs/schema-formulaire.md` §5.2), tranchés dans
le schéma du cabinet pilote. Une recette de `templates/` en assemble plusieurs ;
`outils/composer-schema.js` en tire un `schema.json` complet.

**Outil d'atelier.** Ce dossier n'est jamais servi par le serveur (la racine web
est `formulaire/`) ni livré : `outils/faire-paquet.sh` copie une liste fermée,
et `tests/test_paquet.py` vérifie qu'aucune entrée `blocs/` n'entre dans
l'archive. Le moteur n'inclut rien à l'exécution : le client reçoit un
`schema.json` complet.

## Forme d'un fragment

`blocs/<nom>.json`, avec `<nom>` en minuscules, chiffres et tirets (`anamnese`,
`examen-statique`). Un objet à clés **fermées**, dans cet ordre :

```json
{
  "version_fragment": 1,
  "description": "Une phrase française.",
  "blocs": [ { "cle": "…", "champs": [ … ] } ]
}
```

- Un fragment porte des **blocs entiers**, jamais un champ isolé : le bloc est
  l'unité de pagination et de rendu.
- Le fichier est sous forme canonique : `JSON.stringify(objet, null, 2)` suivi
  d'un saut de ligne, indentation de deux espaces, fins de ligne LF.
- Vocabulaire : un *fragment* (fichier de `blocs/`) contient des *blocs* (au sens
  du schéma).

## Les neuf fragments

| Fragment | Contenu |
|---|---|
| `anamnese` | Informations Patient, Consultation, Orienté par, Déjà SO, Spécialistes, ATCD |
| `examen-statique` | Statique (trois images annotables), Appui, Podo |
| `examen-dynamique` | Rotation tête, Posturo dynamique, Spin test |
| `examen-bilans` | éléments testés, bilans algique, morphologique, définitif |
| `examen-complementaire` | pouls, enregistrement sur plateforme |
| `empreintes` | empreinte à l'encre |
| `chaussage` | chaussures de ville et de sport |
| `ortheses` | plan d'appareillage, pointures, base, recouvrement |
| `conclusion` | conseils, orientation |

Les neuf, dans cet ordre, redonnent **à l'octet** `clients/cabinet-01/schema.json`
(garde B4 de `tests/test_blocs.js`).

## Règles

- **Clés gelées.** Les blocs viennent du pilote **octet pour octet**. Les clés
  des champs sont celles du brouillon (`cleChamp()`), y compris les
  orthographes fautives (`familliaux`, `spécialistes`, `symétrique`, `pédieux`) ;
  les `id` des blocs (`patient_infos`, `section_squelettes`…) portent le style.
  Ne rien « corriger » ici : une clé renommée fait perdre à un praticien le
  bilan de sa consultation en cours. La garde B5 compare chaque bloc au pilote.
- **Aucune identité.** Ni nom, ni adresse, ni courriel, ni téléphone, ni texte
  propre à un cabinet : le dépôt est public (`tests/test_identite_absente.py`).
- **Aucune grille.** Le type `grille` (format version 2) ne se livre qu'à un
  client précis, après les trois conditions de `docs/schema-formulaire.md`, dont
  un export d'essai sur sa tablette. Un fragment de bibliothèque partirait sans
  épreuve : la garde B6 le refuse.
- **Un bloc dans un seul fragment.** Un même bloc dans deux fragments
  doublerait des clés de brouillon dans une composition.
- **Images.** Chaque `fichier` d'un champ `image-annotable` existe sous
  `formulaire/images/` (le moteur n'en contrôle que la forme).

## Modifier le pilote, ou un fragment

Le bloc d'un fragment est la copie d'un bloc du pilote. Si le pilote change, la
modification se fait dans **trois** endroits : `clients/cabinet-01/schema.json`,
son miroir `formulaire/schema.json`, et le fragment. Si un jour le pilote
diverge pour une raison propre à son cabinet, la tâche qui le fait diverger
décide par écrit de propager ou de figer la garde B4 sur le dernier état commun ;
elle ne s'assouplit pas en silence.

## Composer et vérifier

```
node outils/composer-schema.js templates/podologue-complet.json | cmp - clients/cabinet-01/schema.json
node tests/test_blocs.js
```

Un avertissement du moteur (attribut inconnu, que l'exécution ignorerait en
silence) est ici un refus : à l'atelier, c'est une faute de frappe.
