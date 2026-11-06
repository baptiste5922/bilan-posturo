# clients/ — un dossier par client

Ce dossier porte la **description du formulaire de chaque client** : pour
l'instant, son `schema.json`, rien d'autre. Le moteur (`formulaire/moteur/`) est
unique ; ce qui change d'un client à l'autre vit ici.

## Convention

- **Un dossier par client, nommé `cabinet-NN`** (`cabinet-01`, `cabinet-02`…),
  jamais d'après une ville, un nom de praticien ou une enseigne : le dépôt est
  public.
- **Chaque dossier contient un `schema.json`**, au format décrit par
  `docs/schema-formulaire.md`. Le test `tests/test_schema_client.js` refuse un
  dossier mal nommé, un dossier sans schéma, et un schéma que le moteur refuse.
- **Aucune identité, aucune configuration.** Ni nom, ni adresse, ni courriel, ni
  téléphone, ni mot de passe : l'identité d'un cabinet vit dans son `config.json`,
  sur son PC, jamais dans le dépôt. Cela vaut pour tout fichier de ce dossier,
  documentation comprise.
- **Le dépôt est public** : le schéma d'un client y est publié. Un client dont la
  structure de formulaire ne doit pas l'être n'a pas sa place ici avant que la
  question soit tranchée (C9).

## `formulaire/schema.json` est le miroir de `clients/cabinet-01/schema.json`

Le serveur ne sert que `formulaire/` : il ne peut pas lire ce dossier, et ne
doit jamais le pouvoir. Le schéma du cabinet pilote reste donc **aussi** à
`formulaire/schema.json`, où le lisent le moteur en développement, la fiche de
secours et plusieurs suites de tests.

Les deux copies sont égales **octet pour octet**, et le test le garde. Toute
modification se fait **dans les deux**, puis :

```
node tests/test_schema_client.js
```

Le même test compare aussi les clés de brouillon du schéma à celles du
formulaire installé au cabinet (étiquette `production-cabinet-01`) : renommer
une clé, même mal orthographiée, ferait perdre le bilan d'une consultation en
cours. Si l'étiquette manque, le test échoue en donnant le remède
(`git fetch --tags`) : il ne se saute jamais.

## Fabriquer le paquet d'un client

```
sh outils/faire-paquet.sh cabinet-01
```

L'argument est obligatoire, sans valeur par défaut : on ne livre pas par mégarde
le formulaire d'un cabinet à un autre. Le schéma de ce dossier remplace
`formulaire/schema.json` dans l'archive, qui ne contient **aucune** entrée
`clients/`.
