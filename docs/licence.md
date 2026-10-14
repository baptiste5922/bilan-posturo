# La licence, expliquée

Ce document est une explication en français, écrite pour le praticien et pour
l'auditeur. **Il n'a aucune valeur contractuelle : seul `LICENSE` fait foi.**
En cas de doute ou de désaccord entre les deux, c'est le texte anglais de
`LICENSE` qui s'applique.

## Pourquoi le dépôt reste public

Le code du formulaire et du serveur reste lisible par tous, sans compte ni
inscription, **pour que le cabinet puisse vérifier lui-même qu'aucune donnée
de santé ne quitte son réseau local**. C'est l'argument central du
local-first : rien ne se démontre mieux qu'en se lisant.

## Ce que dit la licence, en clair

Depuis le 14 octobre 2026, les développements sont publiés sous
**Business Source License 1.1 (BUSL 1.1)**, et non plus sous MIT. BUSL n'est
pas une licence open source au sens strict, mais ce n'est pas non plus une
fermeture du dépôt :

- **Lire, auditer, cloner, modifier, expérimenter, et même republier** : libre,
  pour n'importe qui, sans rien demander à personne, **tant qu'il n'y a pas
  d'usage en production**. La licence accorde explicitement le droit de copier,
  modifier, créer des œuvres dérivées et redistribuer hors production
  (`LICENSE`, section `Terms`). C'est voulu : un cabinet ne peut vérifier que
  rien ne sort de son réseau que s'il peut lire le code, et un auditeur doit
  pouvoir en garder une copie.
- **Utiliser le logiciel en production, pour les patients de ses propres
  praticiens, dans un seul cabinet** : autorisé directement par la licence
  (clause `Additional Use Grant` de `LICENSE`), sans signature préalable.
- **Fournir le logiciel à un tiers pour qu'il s'en serve en production** —
  l'héberger pour un autre cabinet, le revendre, l'intégrer dans une offre
  commerciale, ou l'exploiter pour le compte d'un cabinet qui n'est pas le
  sien — **n'est pas autorisé**. C'est le point que la licence vient
  précisément fermer : un concurrent ne peut pas reprendre ce dépôt pour le
  vendre à d'autres cabinets de pédicurie-podologie. Ce qui est interdit est
  l'usage *en production* hors du cadre ci-dessus, pas la lecture ni la
  republication du code.
- **Chaque version redevient MIT au plus tard quatre ans après sa
  publication** (champ `Change Date` de `LICENSE`). Ce n'est pas une
  promesse vague : c'est une clause de la licence elle-même, qui s'applique
  automatiquement à la date indiquée.

## Et l'historique MIT ?

Tout ce qui a été publié jusqu'au commit `9339ee9` inclus (étiqueté
`frontiere-mit`, le 14 octobre 2026) **reste sous MIT pour toujours**. Un
droit déjà accordé publiquement ne se retire pas : le texte MIT exact de cette
période est conservé, inchangé, dans
[`LICENSE-MIT-HISTORIQUE`](../LICENSE-MIT-HISTORIQUE). Seuls les
développements postérieurs à cette frontière passent sous BUSL 1.1.

## Ce que cela change pour un cabinet déjà installé

Rien à son échelle : la copie installée chez lui a été livrée sous MIT, à
titre perpétuel. Les mises à jour postérieures à la bascule sont couvertes par
l'`Additional Use Grant` décrit plus haut — le cabinet reste en règle le jour
même, sans avoir à signer quoi que ce soit.

## Ce que la licence n'est pas

La licence ne fixe ni prix, ni durée, ni modalités de résiliation : ce sujet
relève d'un **contrat d'abonnement séparé**, propre à chaque cabinet. La
licence dit ce que le code autorise ; le contrat organise la relation
commerciale. Les deux documents ne se substituent pas l'un à l'autre.

## Composants tiers

Le formulaire embarque deux bibliothèques JavaScript sous licence MIT
(jsPDF et html2canvas), listées avec leur attribution complète dans
[`TIERS.md`](../TIERS.md). Leur licence MIT propre n'est pas affectée par le
passage du code du dépôt à BUSL 1.1.
