# C1-T5 — Fabriquer un client fictif à partir d'un template

**Question posée** (`docs/projection.md` §12, « temps réel de fabrication d'un
template ») : combien de temps faut-il à un opérateur d'atelier pour passer d'un
template de départ à un `schema.json` de client, huit modifications faites,
validé par le vrai moteur ? **Seuil du contrat : strictement moins de 60 minutes.**

Ce qui est mesuré : la durée murale entre l'ouverture de la feuille de route
ci-dessous et le premier `--verifier` qui rend 0 sur le schéma final, **outil
compris**. Pas d'aperçu dans un navigateur (C9-T2). Seule la mesure de
l'**opérateur humain** compte (critère A13) : la répétition de l'implémenteur,
plus bas, ne compte pas.

Tout texte neuf n'emploie que le vocabulaire fictif « Bloc N / Texte N ». Le
schéma produit reste ici (`docs/essais/`), **jamais** dans `clients/` : G1 y
exige un `cabinet-NN`, et un client fictif pourrait partir dans un paquet.

## Protocole pas à pas

Tout se passe dans un dossier de travail **hors du dépôt**, depuis la racine du
dépôt. **N'ouvrir ni copier `docs/essais/C1-T5-client-fictif.schema.json`**
pendant la mesure : c'est la référence à laquelle le résultat sera comparé.

```
cd <racine du dépôt>
TRAVAIL=$(mktemp -d)
date '+%Y-%m-%d %H:%M:%S'      # DÉBUT : à lancer en ouvrant la feuille de route
```

### Feuille de route (huit modifications)

1. Partir de `podologue-court` :
   `cp templates/podologue-court.json "$TRAVAIL/recette.json"`.
2. Ajouter le fragment `examen-dynamique` **après** `examen-statique` dans
   `"$TRAVAIL/recette.json"` (copie de la recette), puis composer :
   `node outils/composer-schema.js "$TRAVAIL/recette.json" --sortie "$TRAVAIL/schema.json"`.
   Les modifications 3 à 8 se font à la main dans `"$TRAVAIL/schema.json"`.
3. Retirer le bloc `oriente_par_bloc`.
4. Retirer le champ `niveau_scolaire` du bloc `patient_infos`.
5. Remplacer le libellé `Sport:` par `Texte 1 :` (la clé `sport` ne change pas).
6. Remplacer le titre `Consultation` par `Bloc 1` (bloc `consultation_bloc`).
7. Ajouter, **juste après** le bloc `atcd_bloc`, ce bloc exactement :

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

8. Ajouter **à la fin** des `champs` du bloc `section_conseils` ce champ exactement :

   ```json
   { "cle": "texte-4", "type": "zone-texte", "libelle": "Texte 4 :" }
   ```

   Les libellés s'écrivent avec une espace ordinaire avant les deux-points
   (`Texte 1 :`, `Texte 4 :`).

### Fin de la mesure

```
node outils/composer-schema.js --verifier "$TRAVAIL/schema.json"; echo "code $?"
date '+%Y-%m-%d %H:%M:%S'      # FIN : dès que --verifier rend 0 (le premier qui rend 0)
```

Puis, **hors chronomètre** :

```
shasum -a 256 "$TRAVAIL/schema.json"
node -e 'const a=require("assert"),f=require("fs");a.deepStrictEqual(JSON.parse(f.readFileSync(process.argv[1],"utf8")),JSON.parse(f.readFileSync(process.argv[2],"utf8")));console.log("MÊME CONTENU")' "$TRAVAIL/schema.json" docs/essais/C1-T5-client-fictif.schema.json
```

Une indentation retouchée à la main n'est pas un écart : la comparaison porte sur
le contenu JSON, pas sur les octets. Les résultats s'inscrivent dans la section
« Mesure officielle » ci-dessous.

## Répétition de l'implémenteur — non comptée

Jouée par l'agent qui a implémenté C1-T5, **par script** (les modifications 3 à 8
sont faites par un court programme Python, non versionné), le 6 novembre 2026.
Elle prouve que le protocole se déroule sans accroc et produit le schéma de
référence ; sa durée (moins d'une seconde) n'a aucune valeur de mesure.

| Élément | Valeur |
|---|---|
| Opérateur | agent implémenteur (répétition, **non comptée**) |
| Template de départ | `podologue-court` |
| Début / fin | `2026-11-06 17:45:04` / `2026-11-06 17:45:04` |
| Modifications faites | 8 sur 8 |
| `--verifier` | `Schéma valide (19 blocs, 30 champs).`, code 0 |
| `shasum -a 256` du schéma produit | `b557761161c4fff42fabd30c489166501701845b9e4f768937282ba2c3e21d24` |

Le schéma produit est versionné : `docs/essais/C1-T5-client-fictif.schema.json`
(19 blocs : 16 du template court, plus `examen-dynamique` (3), moins
`oriente_par_bloc`, plus `bloc-1`).

## Mesure officielle (Baptiste) — à remplir

À consigner par l'opérateur, après avoir joué le protocole ci-dessus. Seuil :
**strictement moins de 60 minutes**.

| Élément | Valeur |
|---|---|
| Opérateur | |
| Template de départ | `podologue-court` |
| Début (`date '+%Y-%m-%d %H:%M:%S'`) | |
| Fin (premier `--verifier` rendant 0) | |
| Durée | |
| Modifications faites (8 attendues) | |
| Sortie de `--verifier` | |
| `shasum -a 256` du schéma produit | |
| Comparaison au schéma de référence (`MÊME CONTENU` ?) | |
| Verdict (durée < 60 min, 8 modifications, même contenu, `--verifier` à 0) | |

Remarques de l'opérateur (ce qui a coincé, ce que l'outil ne dit pas) :

