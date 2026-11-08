# La clé de publication : le geste de Baptiste

**Contrat :** `docs/contrats/C5-T1.md`
**Outil :** `outils/signer-paquet.py`
**Date :** 8 novembre 2026

Cette fiche décrit le seul geste que personne d'autre ne peut faire à la place de
l'éditeur : fabriquer, garder et utiliser la clé qui signe les mises à jour.
**Aucun agent ne génère, ne lit ni ne manipule cette clé.** Tant que le geste n'a
pas été fait, le dépôt ne porte aucune clé publique de publication
(`serveur/cles_publication.json` n'existe pas) et aucun paquet ne peut être signé.

Toutes les commandes se lancent depuis la racine du dépôt, sur le **poste de
l'éditeur**, jamais sur un PC de cabinet ni en intégration continue.

## 1. À quoi sert la clé, et ce qu'elle permet si elle fuit

Le PC du cabinet **tire** ses mises à jour (décision du 3 novembre 2026) et
n'installe **qu'un paquet signé**. La signature est une signature Ed25519 posée
sur un manifeste qui liste, avec leur empreinte SHA-256, chaque fichier du
paquet. Le PC du cabinet ne connaît que la partie **publique** de la clé : elle
suffit à vérifier, elle ne permet pas de signer.

La partie **privée** est donc la clé de tout le parc. Celui qui la détient peut
faire exécuter du code, sous le compte SYSTEM, sur chaque PC où se trouvent les
bilans. Il n'y a **pas de révocation** : une clé qui a fuité ne se « désactive »
pas à distance (section 8). C'est pourquoi elle :

- n'est **jamais** dans le dépôt, ni dans la CI, ni dans un nuage synchronisé ;
- est chiffrée par une phrase de passe ;
- est distincte de l'autorité de certification de chaque cabinet : ces deux
  rôles ne se confondent pas, sans quoi un PC de cabinet compromis deviendrait
  un éditeur.

## 2. Générer la clé

Sur le poste de l'éditeur, dans un dossier **hors du dépôt** (l'outil refuse
tout dossier sous la racine du dépôt, liens compris, et ne remplace jamais une
clé existante) :

```bash
mkdir -p ~/cles-editeur
python3 outils/signer-paquet.py generer-cle --dossier ~/cles-editeur --nom publication-2026
```

L'outil demande deux fois une **phrase de passe d'au moins 12 caractères**, puis
écrit `~/cles-editeur/publication-2026-privee.pem` (chiffré, droits `0600`). Le
nom suit le motif `publication-AAAA`, éventuellement suivi de `[a-z0-9-]`. Le
module `cryptography` est requis pour cette commande
(`python3 -m pip install cryptography`).

La **sortie standard** ne contient que l'objet JSON de la clé publique, à copier
tel quel à la section 4 ; la clé privée et la phrase n'y apparaissent jamais.

## 3. Sauvegarder

Faites-le **tout de suite**, avant la première signature :

1. **Deux copies** du fichier chiffré `publication-2026-privee.pem`, sur **deux
   supports hors ligne** (clé USB, disque externe), rangés dans **deux lieux**
   différents.
2. La **phrase de passe** dans le gestionnaire de mots de passe, séparément du
   fichier.
3. Jamais dans un courriel, jamais dans un nuage synchronisé, jamais dans le
   dépôt. Le nom `*-privee.pem` est de toute façon refusé par le contrôle « aucun
   secret versionné » de la CI.

Sans la clé ni la phrase, plus aucune mise à jour ne peut être signée (section 7).

## 4. Publier la clé publique

La clé publique est embarquée dans chaque paquet : c'est elle que le PC du
cabinet utilise pour juger la mise à jour **suivante**. Une fois commitée, ce
n'est pas un secret.

1. Créez `serveur/cles_publication.json` avec la sortie de `generer-cle` :

   ```json
   {
     "format": 1,
     "cles": [
       {"nom": "publication-2026", "publique": "<64 chiffres hexadécimaux minuscules>"}
     ]
   }
   ```

2. Un **commit dédié**, qui ne contient que ce fichier. Relisez la clé publique
   dans le diff avant de commiter : c'est la valeur qui sera de confiance sur tout
   le parc.
3. Le fichier part ensuite dans le paquet avec `serveur/` (`faire-paquet.sh`
   copie tout ce dossier).

Au plus **quatre clés** par liste. Cette liste est celle que le PC lit pour juger
un paquet : c'est toujours la liste **déjà installée** qui juge, jamais celle du
paquet entrant.

## 5. Signer un paquet

1. Fabriquer le paquet, comme aujourd'hui :

   ```bash
   sh outils/faire-paquet.sh cabinet-01
   ```

2. Le signer. La version minimale est la plus ancienne version installée qui a le
   droit d'y monter ; elle doit être **strictement inférieure** à la version du
   paquet :

   ```bash
   python3 outils/signer-paquet.py signer --cle ~/cles-editeur/publication-2026-privee.pem --client cabinet-01 --version-minimale 1.1.0 BilanPosturo-2026-11-08.zip
   ```

   L'outil refuse de signer si la clé n'est pas dans la liste embarquée du paquet
   (le cabinet ne pourrait pas vérifier la mise à jour suivante), si le schéma
   n'est pas celui du client, ou si un nom de fichier sort de la liste blanche.
   Il pose à côté de l'archive `….zip.manifeste.json` et `….zip.manifeste.sig`,
   puis **revérifie** le trio avec le code qui tournera au cabinet.

3. **Relire la liste des fichiers signés** que l'outil imprime. Tout fichier que
   `cp -R` a emporté sans être suivi par Git est signé fidèlement et part chez
   tous les clients : un fichier inattendu dans cette liste est un arrêt.

4. Contrôler comme le fera le cabinet :

   ```bash
   python3 outils/signer-paquet.py verifier --cles serveur/cles_publication.json --version-installee 1.1.0 --client cabinet-01 BilanPosturo-2026-11-08.zip
   ```

   Sortie attendue : `PAQUET ACCEPTÉ <version>`. Sinon : `PAQUET REFUSÉ <code>`.

Le paquet de `cabinet-02` n'est pas celui de `cabinet-01` : le manifeste nomme le
client, et un PC refuse le paquet d'un autre.

## 6. Changer de clé

La rotation se fait **en deux versions**, sans jamais laisser un PC sans clé
valide :

1. Générer la nouvelle clé (section 2, un autre `--nom`) et la sauvegarder
   (section 3).
2. Publier une version **signée par l'ancienne clé** dont
   `serveur/cles_publication.json` contient **l'ancienne et la nouvelle**.
3. Une fois cette version installée partout, publier une version **signée par la
   nouvelle clé** dont la liste ne contient que la nouvelle.

À aucun moment la clé qui signe n'est absente de la liste du paquet : l'outil le
refuse.

## 7. Perte de la clé

Si le fichier **ou** la phrase est perdu et que les sauvegardes sont perdues
aussi, aucun paquet ne peut plus être signé par cette clé, donc **aucune mise à
jour ne peut plus être acceptée** par les PC qui ne connaissent que cette clé.
La seule issue est une intervention sur chaque PC pour y poser une nouvelle liste
de clés. C'est la raison des deux sauvegardes hors ligne de la section 3.

## 8. Compromission

Si la clé privée a pu être copiée (poste volé ou infecté, fichier dans un nuage,
phrase divulguée) :

- **Il n'y a pas de révocation.** Une clé compromise permet de pousser une liste
  qui l'exclut… ou qui garde la clé de l'attaquant ; le PC ne fait confiance qu'à
  la liste déjà installée.
- **Cessez immédiatement toute publication** et retirez les versions en ligne.
- La seule parade sûre est une **intervention sur chaque PC** : poser une
  nouvelle liste de clés, à la main, et réinstaller une version saine.
- Prévenez les cabinets concernés. Les bilans n'ont pas quitté les PC, mais le
  code qui les traite a pu être remplacé.

La limite est connue et consignée (contrat C5-T1, D6) : on la réduit en gardant la
clé hors ligne, chiffrée, et en ne signant jamais depuis un poste partagé.
