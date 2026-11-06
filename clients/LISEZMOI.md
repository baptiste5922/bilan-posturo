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
  dossier mal nommé, un dossier sans schéma, un schéma que le moteur refuse, et
  tout fichier à plat ou lien symbolique dans `clients/` autre que ce
  `LISEZMOI.md`.
- **Aucune identité, aucune configuration.** Ni nom, ni adresse, ni courriel, ni
  téléphone, ni mot de passe : l'identité d'un cabinet vit dans son `config.json`,
  sur son PC, jamais dans le dépôt. Cela vaut pour tout fichier de ce dossier,
  documentation comprise.
- **Pas de logo ici** : il identifie le cabinet ; il se pose sur son PC, sous
  `formulaire/images/cabinet/`.
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
formulaire écrit à la main installé au cabinet en août 2026, lu **par le SHA
complet de son commit** (`d43350a0cf20fef5672eadc7bcb6f67e156dc977`, constante
`REFERENCE_PRODUCTION`), et non par l'étiquette `production-cabinet-01` : la
fiche de production déplace cette étiquette à chaque installation, et après la
livraison du moteur elle ne désignerait plus aucun HTML à comparer. Renommer une
clé, même mal orthographiée, ferait perdre le bilan d'une consultation en cours.

- **La garde ne s'assouplit pas.** Une nouvelle version livrée s'ajoute comme
  seconde référence ; elle ne remplace pas celle-ci : un brouillon commencé sur
  `d43350a` doit toujours se rouvrir.
- Si ce commit manque (clone peu profond), le test échoue en donnant le remède
  (`git fetch --all --tags`, ou `--unshallow`) : il ne se saute jamais.

## Créer un client

On ne part pas d'une page blanche : `templates/` porte deux recettes de départ,
assemblées à partir de `blocs/` par `outils/composer-schema.js`. La procédure
pas à pas est dans `templates/LISEZMOI.md`. Le résultat se verse ici, dans un
nouveau dossier `cabinet-NN` (jamais d'après une ville), sous réserve que
`node tests/test_schema_client.js` reste vert.

## Fabriquer le paquet d'un client

```
sh outils/faire-paquet.sh cabinet-01
```

L'argument est obligatoire, sans valeur par défaut : on ne livre pas par mégarde
le formulaire d'un cabinet à un autre. Le schéma de ce dossier remplace
`formulaire/schema.json` dans l'archive, qui ne contient **aucune** entrée
`clients/`.
