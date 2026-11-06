# Production — cabinet-01

Ce qui tourne au cabinet pilote, et comment y toucher sans rien casser.
Fiche tenue à la main : la mettre à jour **à chaque installation au cabinet**,
et seulement à ce moment-là.

## La version installée

| | |
|---|---|
| **Commit** | `d43350a` (26 août 2026) |
| **Étiquette** | `production-cabinet-01` |
| **Branche de maintenance** | `maintenance-cabinet-01` |
| **Installée** | fin août 2026, par paquet `outils/faire-paquet.sh` |
| **Constaté le** | 6 novembre 2026, sur la déclaration de Baptiste |

**Ce qu'elle contient :** le formulaire écrit à la main
(`formulaire/index.html`), le PDF fabriqué dans le navigateur, le serveur
HTTPS de dépôt et son journal, l'autorité de certification locale.

**Ce qu'elle ne contient pas**, alors que `main` l'a depuis :
- ni file d'attente des dépôts (un dépôt échoué se refait à la main) ;
- ni démarrage automatique par tâche planifiée ;
- ni fiche de secours `index-v1.html`, ni moteur à schéma ;
- ni `technique.log`, ni `/cabinet`, ni `/etat`, ni la purge à six mois ;
- ni la licence BUSL : cette version est sous **MIT** (antérieure à
  `frontiere-mit`).

L'identité du cabinet y est écrite dans le HTML, pas dans `config.json`.

## Vérifier que c'est bien elle

Pendant une séance à distance, dans PowerShell, depuis le dossier de
l'installation :

```
Get-FileHash serveur\serveur.py, formulaire\index.html, formulaire\script.js, formulaire\style.css -Algorithm SHA256
```

Empreintes attendues pour `d43350a` :

| Fichier | SHA-256 |
|---|---|
| `serveur/serveur.py` | `61c2ffbf2159c88ef5b177ed1de63e46e1f8ac191f98f8a3dfe20d5462422824` |
| `formulaire/index.html` | `9f1d04575394eaa476f3a78a4b51e3320badf65b0fee78bc8f81f0a3e6a461d9` |
| `formulaire/script.js` | `c383037803304134f40ad1c6b3910033b88bd51e8eb4f08376b1cdb980550ca6` |
| `formulaire/style.css` | `0a5e3e9d927bbb174b4a317a45078482e537324cfa58c2004036ea513c6af196` |

Le paquet est fabriqué sur le Mac : les fins de ligne sont celles du dépôt.
Une empreinte différente veut dire un autre fichier, **ou** un fichier
réenregistré avec des fins de ligne Windows : comparer alors le contenu avant
de conclure. Si les quatre diffèrent, la version installée n'est pas
`d43350a` : corriger cette fiche et déplacer l'étiquette.

## Un correctif d'urgence

Si la production casse avant la prochaine livraison, on ne livre **pas** la
V2 pour la réparer :

1. Partir de `maintenance-cabinet-01`, jamais de `main`.
2. Corriger le seul défaut, le tester sur cette branche.
3. Fabriquer le paquet depuis cette branche (`outils/faire-paquet.sh`).
4. Installer, puis déplacer `production-cabinet-01` sur le nouveau commit
   et mettre à jour cette fiche.

Les données du cabinet (`config.json`, clés, certificats, journaux, dossier
des bilans) ne sont jamais dans le paquet et ne se remplacent pas.

## La prochaine livraison

Elle franchira d'un coup tout ce qui sépare `d43350a` de `main`. Elle ne se
fait **qu'en présence de l'appareil**, pas avant janvier 2027 environ :
favori de secours posé et ouvert sur la tablette, puis une semaine de bilans
réels (C1-T4b, `docs/ROADMAP.md`). Points à préparer d'ici là :
- le bloc `cabinet` de `config.json` (sans lui, l'export est **refusé**) ;
- l'installation du démarrage automatique (`installer-demarrage.ps1 -Verifier`) ;
- l'annonce à la praticienne de la purge des journaux à six mois.
