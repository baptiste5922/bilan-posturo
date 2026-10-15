# Session du 15 octobre 2026 (seconde) — Le moteur de rendu, sans la bascule

**Durée approximative :** une journée de travail, enchaînée sur la session C1-T1
**Tâches concernées :** C1-T3 (étapes 1 à 8 livrées), C1-T3b et C6-T5 ouvertes
**Branche :** `c1-t3-moteur-rendu-schema`  **Commits :** aucun — le travail est
dans l'arbre, non commité

## Ce qui a été fait

Le moteur de rendu existe. `formulaire/moteur/rendu.js` valide un schéma puis
construit le DOM du formulaire ; `formulaire/schema.json` décrit les 28 blocs du
corps du bilan ; et `tests/test_comparaison_dom.js` compare ce que le moteur
produit à ce que contient le formulaire V1 — les 29 unités de pagination avec
leur chaîne d'ancêtres, les champs, les deux tableaux de radios et les quatre
images annotables, sous neuf tolérances écrites et motivées.

**Ce qui n'a pas été fait, délibérément : la bascule.** Le contrat posait un
préalable bloquant — produire le jeu de référence visuelle de la V1, quatre
fichiers qui ne s'obtiennent qu'au navigateur. Ce préalable n'a pas été levé, et
Baptiste a choisi la voie que le contrat prévoyait lui-même en parade : réaliser
les étapes 1 à 8 en laissant `formulaire/index.html` **intact, octet pour
octet**. Le moteur n'est donc atteignable que par une page provisoire,
`formulaire/index-moteur.html`, exclue du paquet livré au cabinet. La V1
continue de servir les consultations, et reste observable — c'est tout l'intérêt
de ce découpage : le jeu de référence est encore produisible demain.

Trois choses ont été découvertes dans le code existant et traitées au passage.
`/schema.json` aurait répondu 403 : `.json` n'était pas dans la liste blanche
d'extensions du serveur, et l'y ajouter cassait un test d'intégration qui
affirmait que `/config.json` répond 403 — hors racine web, il passe à 404. Le
rendu asynchrone aurait tué le stylet : `initDessin()` exige que les quatre
images soient déjà dans le DOM, et un moteur qui rend après `DOMContentLoaded`
aurait laissé `zonesDessin` vide, donc plus aucun dessin et les traits d'un
brouillon restauré tombant dans le vide ; d'où un point de couture explicite,
`demarrerApplication()`, appelé par le moteur après rendu. Enfin le HTML V1 rend
les titres de bloc sous trois formes différentes, ce qui a demandé quatre
attributs facultatifs à valeurs fermées (D9 à D11) plutôt que de laisser le
moteur deviner.

## Décisions prises

| Décision | Raison | Conséquence |
|---|---|---|
| Le thème reste **hors périmètre** : le moteur ne charge que `schema.json`, l'identité du cabinet reste en dur dans la page | C2-T1 n'est pas faite et le format du thème n'est pas spécifié. Empiler l'invention d'un format sur la tâche déjà la plus lourde aurait élargi le point de non-retour sans nécessité | Le travail n°1 du contrat (« appliquer le thème aux tokens CSS ») est réduit à néant par C1-T2 : les cinq tokens de `:root` sont la source unique, il n'y a rien à appliquer au chargement |
| **Ne pas basculer** : étapes 1 à 8 seulement, `index.html` intact | Le critère « PDF superposable » devient définitivement invérifiable après la bascule — la V1 n'est plus observable. Mieux vaut un moteur non branché qu'une preuve perdue | L'étape 9 devient **C1-T3b**, avec le jeu de référence comme dépendance déclarée |
| La contradiction entre la règle 1 (racine fermée) et la règle d'évolution de la section 5.1 est tranchée **en faveur de la règle 1** | Une racine ouverte rend indécidable la différence entre un attribut futur et une faute de frappe | Tout ajout d'attribut racine, même facultatif, exige désormais une nouvelle version du format |
| `IDS_RESERVES_COQUILLE` ne réserve que les `id` **émis par la coquille à l'intérieur de `#form-bilan`** — cinq, pas dix | Les autres clés gelées (`patient_infos`, `section_squelettes`, …) sont émises **par le schéma** : les réserver les aurait interdites et cassé le rendu. Le bon critère n'est pas « clé gelée » mais « qui l'émet » | L'audit avait sur-généralisé sur ce point et s'est rectifié après vérification fichier par fichier |
| **Ne pas corriger** l'octet nul dans les chemins du serveur | Défaut **pré-existant**, vérifié antérieur à cette tâche : `/index%00.html` produit le même silence. L'ajout de `.json` n'a fait qu'ajouter une orthographe au même défaut | Versé dans **C6-T5**, ouverte pour cela |

## État des tests

Avant : 67 Python, 7 Node (file), 8 groupes (palette), 6 (inventaire) — 88.
Après : **103**. 73 Python (+3 sur la surface du serveur, +3 sur la fabrication
du paquet), 7 (file, intact), 8 (palette, intact), 7 (inventaire, +1 sur la
bijection HTML ↔ schéma), 8 (comparaison de DOM, nouveau).

Ce qui est couvert de nouveau : une divergence entre le DOM du moteur et celui
de la V1 — y compris une divergence de **place dans l'arbre** —, un titre ou un
en-tête de tableau renommé, une clé de schéma qui collisionne avec la coquille,
un schéma cassé de trois façons, un champ ajouté au schéma sans toucher au
JavaScript, et le moteur qui tenterait de partir dans le paquet du cabinet.

## Constats de sécurité

Audit : **CONFORME SOUS RÉSERVE** au premier passage — 0 critique, 0 élevé,
6 moyens, 5 faibles — puis **CONFORME** après correction des onze constats,
chacun rejoué par l'auditeur sur des mutations de son choix.

Les deux constats qui comptaient vraiment portaient sur la même faiblesse : un
comparateur qui ne voit pas ce qu'il devrait voir. Les blocs atterrissaient
**après** `<main>` au lieu d'y entrer, perdant son `padding: 10px` — une marge
décalée sur un document de santé imprimé et archivé, exactement ce que le
critère 3 interdit, et le comparateur ne pouvait pas le détecter puisqu'il
aplatissait l'arbre. Et les deux blocs `<table>` échappaient entièrement à la
comparaison des champs : « Rotation tête » pouvait devenir « Rotation du cou »,
les en-têtes de colonnes n'importe quoi, sans qu'aucun test ne bronche. Les deux
sont refermés, et vérifiés en reproduisant chaque défaut.

Deux autres méritent d'être retenus : un champ sans clé était rendu avec
`id="undefined"`, si bien que deux champs de ce genre auraient partagé la même
clé de brouillon — un champ clinique rempli pouvant réapparaître avec le contenu
d'un autre ; et la page provisoire du moteur serait partie au cabinet avec le
prochain paquet, où elle aurait produit des bilans indiscernables des vrais, par
un chemin de rendu non validé.

Réaudit : un seul constat nouveau, faible, corrigé — la vérification intégrée au
script de paquet était **aveugle aux dossiers** (`unzip -l` liste
`moteur/rendu.js`, jamais `moteur` tout court), donc un paquet fabriqué à la
main pouvait emporter le moteur en s'annonçant conforme.

Revue de code : **À LIVRER**, 0 bloquant, 0 important, 2 mineures.

Reporté : C6-T5 (octet nul, pré-existant), une note sur C2-T1 (deux en-têtes à
purger, pas un), et sur C1-T3b les seize `id` de la barre d'outils qui ne sont
protégés que par l'ordre du document.

## Ce qui reste en suspens

- **Le travail n'est pas commité**, sur la branche `c1-t3-moteur-rendu-schema`.
  Pour le débloquer : un commit, puis la même voie que C1-T1 — une pull request
  qui fait tourner la CI sur les trois systèmes avant toute fusion.
- **Le jeu de référence visuelle de la V1** : quatre fichiers,
  `docs/references-visuelles/LISEZMOI.md`, une vingtaine de minutes au
  navigateur. C'est la dépendance de C1-T3b, et la seule étape que la bascule ne
  laisse pas rattraper.
- **C1-T3b, la bascule** : elle attend le point précédent. C'est le point de
  non-retour du chantier.
- **Les coordonnées du cabinet** sont maintenant en dur dans **deux** fichiers
  servis (`index.html` et `index-moteur.html`), dans un dépôt public. Pour le
  débloquer : C2-T1.

## Prochaine étape recommandée

Produire les quatre fichiers de référence visuelle, puis `/lancer-tache C1-T3b`.
Rien d'autre ne devrait passer devant : tant que la V1 tourne, ces fichiers sont
gratuits ; le jour de la bascule, ils sont impossibles.

## À savoir pour la prochaine session

**Le défaut récurrent de la journée, pour la deuxième fois : un garde-fou qui ne
garde rien.** En C1-T1, c'étaient trois listes normatives recopiées à la main.
En C1-T3, c'est un comparateur qui aplatissait l'arbre et sautait deux blocs sur
vingt-neuf. La leçon est la même et vaut pour C1-T3b : **un test qui n'a pas été
mis en échec exprès n'est pas un test**. Les quatre mutations qui ont servi ici —
un titre de tableau renommé, une clé collisionnant avec la coquille, un bloc
rendu hors de `<main>`, une exclusion de paquet neutralisée — sont ce qui a
transformé des affirmations en preuves.

**Une tolérance ajoutée pendant l'implémentation est le moyen le plus simple de
faire taire un comparateur.** Le contrat en déclarait cinq ; il y en a neuf. Les
quatre ajoutées ont été examinées une par une, et toutes tiennent — mais la
neuvième, qui filtre l'ancêtre `<section id="consultation">`, ne tient que parce
que `style.css` ne contient aujourd'hui **aucun** sélecteur enfant `>` ni
adjacent `+`. Le jour où une telle règle entre dans la feuille de style, cette
tolérance redevient un angle mort. C'est écrit dans l'audit ; il faudra y
revenir.

**Ce qui a coûté du temps.** La session a touché la limite de requêtes en
milieu de réaudit, ce qui a interrompu l'auditeur avant qu'il n'écrive son
rapport. Le réaudit a dû être relancé plus tard, en parallèle de la revue de
code, sur des fichiers de sortie disjoints pour qu'ils ne s'écrasent pas. À
retenir : sur une tâche de cette taille, lancer l'audit et la revue ensemble
fonctionne, à condition de leur interdire explicitement d'écrire ailleurs que
dans leur propre rapport.

**Un piège de nommage à ne pas répéter.** Le contrat demandait de consigner les
mises en échec dans `docs/audits/C1-T3.md` — le fichier même où l'auditeur écrit
son rapport. L'implémenteur l'a donc occupé, et il a fallu le déplacer en
`docs/audits/C1-T3-mises-en-echec.md` avant de lancer l'audit. Les futurs
contrats doivent nommer un autre fichier pour le journal de l'implémenteur.

**Un défaut du dépôt découvert en nettoyant.** `.gitignore` couvrait l'archive
`BilanPosturo-*.zip` mais pas le **dossier** du même nom : un `git add -A` après
fabrication d'un paquet aurait versé une copie complète de `formulaire/` et
`serveur/` dans le dépôt. Corrigé.
