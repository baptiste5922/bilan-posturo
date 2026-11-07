# templates/ — les recettes de départ

Une **recette** liste, dans l'ordre, les fragments de `blocs/` qui forment un
formulaire. Un nouveau client part d'une recette, pas d'une page blanche.

**Une recette n'est pas un schéma.** Un schéma complet n'existe que dans
`clients/<client>/schema.json`, ou en sortie de `outils/composer-schema.js` :
chaque bloc n'a ainsi qu'une source. Rien de ce dossier n'est servi, ni livré
(`tests/test_paquet.py`).

## Forme d'une recette

`templates/<nom>.json`, clés fermées, dans cet ordre :

```json
{
  "version_recette": 1,
  "description": "Une phrase française.",
  "version_schema": 1,
  "fragments": ["anamnese", "examen-statique"]
}
```

Les noms de fragment sont ceux de `blocs/` (minuscules, chiffres, tirets : aucun
chemin), sans doublon.

| Recette | Contenu |
|---|---|
| `podologue-complet` | les neuf fragments : les 28 blocs du cabinet pilote, à l'octet |
| `podologue-court` | `anamnese`, `examen-statique`, `ortheses`, `conclusion` : 16 blocs |

## Créer un client

Tout se passe dans un dossier de travail **hors du dépôt** (`$TRAVAIL`) jusqu'à
la dernière étape. L'outil d'atelier `outils/atelier/atelier.js` enchaîne les
étapes 1 à 4 ci-dessous et y ajoute l'identité, le logo et un aperçu : voir
`outils/atelier/LISEZMOI.md`.

1. Copier la recette la plus proche : `cp templates/podologue-court.json "$TRAVAIL/recette.json"`.
   Ajouter ou retirer des fragments dans la copie (jamais dans `templates/`).
2. Composer : `node outils/composer-schema.js "$TRAVAIL/recette.json" --sortie "$TRAVAIL/schema.json"`.
   L'outil refuse d'écraser un fichier existant et d'écrire sous `formulaire/`.
3. Retoucher `"$TRAVAIL/schema.json"` à la main (retirer un bloc ou un champ,
   changer un libellé, ajouter un bloc). Il n'y a pas de langage de surcharge :
   le schéma du client est un fichier à lui. Respecter `docs/schema-formulaire.md`.
   Ne jamais renommer une clé existante d'un bloc repris de la bibliothèque : elle
   porte le style et, pour le pilote, le brouillon des praticiens.
4. Vérifier : `node outils/composer-schema.js --verifier "$TRAVAIL/schema.json"`
   rend 0. Le moteur est le vrai ; un avertissement vaut refus.
5. Verser le résultat dans `clients/cabinet-NN/schema.json` (numéro suivant,
   jamais d'après une ville ni un nom : le dépôt est public), puis
   `node tests/test_schema_client.js`. **Un client hors pilote n'est pas versé
   tant que la décision D-O1 (où vit son schéma ?) n'est pas tranchée** : le
   dépôt est public. Pour un client réel, travailler avec l'atelier
   (`outils/atelier/LISEZMOI.md`), qui ne verse rien.
6. Fabriquer le paquet : `sh outils/faire-paquet.sh cabinet-NN`.

Aucune **grille** n'entre dans une recette ni dans un fragment. Elle se pose à
la main dans le schéma d'un client précis, en version 2, après les trois
conditions de `docs/schema-formulaire.md`, dont un export d'essai sur sa tablette.

La mesure du temps de fabrication d'un client à partir d'un template :
`docs/essais/C1-T5-client-fictif.md`.
