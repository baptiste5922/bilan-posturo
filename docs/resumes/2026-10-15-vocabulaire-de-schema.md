# Session du 15 octobre 2026 — Le vocabulaire du schéma de formulaire

**Durée approximative :** une journée de travail
**Tâches concernées :** C1-T1 (livrée)
**Branche :** `c1-t1-inventaire-formulaire`  **Commits :** aucun — le travail
est dans l'arbre, non commité

## Ce qui a été fait

C1-T1 est livrée, du contrat à la revue. La tâche demandait d'inventorier le
formulaire de production et d'en déduire le vocabulaire minimal qui permettra,
en C1-T3, de le décrire par un fichier plutôt que par du HTML écrit à la main.
Le livrable est `docs/schema-formulaire.md`, 625 lignes : l'inventaire des
29 blocs, 45 champs logiques et 4 images annotables de `#form-bilan`, le jeu
fermé des types, la structure du format avec son numéro de version, ses règles
de validation, et la règle de stabilité des clés.

Trois choses ont changé en cours de route par rapport à ce que la feuille de
route annonçait. D'abord les décomptes : elle parlait de « 17 blocs, ~78
champs », qui étaient une estimation ; le relevé réel donne 29 blocs et
45 champs, et la feuille de route est corrigée. Ensuite le jeu de types : la
feuille de route en proposait dix à titre indicatif, le document n'en retient
que **sept**, et justifie nommément le retrait des trois autres — aucun
`<select>` dans le fichier, aucun contrôle numérique à l'intérieur du
formulaire, et les seuls textes statiques relèvent du thème, donc de C2-T1.
Enfin les clés, qui étaient la vraie décision cachée de cette tâche.

Un garde-fou mécanique accompagne le document : `tests/test_inventaire_formulaire.js`,
six groupes, sans dépendance, qui établit la bijection entre les clés dérivables
du HTML et celles de l'inventaire, recompte les blocs et les images dans le HTML
à chaque exécution, et vérifie l'exhaustivité de la liste des `id` gelés. Un
second pas d'intégration continue vérifie qu'aucune coordonnée du cabinet n'est
recopiée dans les documents de la tâche.

Aucun octet de `formulaire/` ni de `serveur/` n'a été modifié. Le formulaire en
production est intact, et le retour arrière de cette tâche ne peut affecter
aucune consultation.

## Décisions prises

| Décision | Raison | Conséquence |
|---|---|---|
| Sept types et non dix : `texte`, `zone-texte`, `date`, `case`, `radio`, `tableau`, `image-annotable` | Chaque type devra être rendu, testé, documenté et maintenu chez N cabinets pendant des années. Un type ajouté « au cas où » est une dette signée pour dix clients | `nombre`, `liste` et `paragraphe` sont écartés avec justification vérifiée. Les ajouter plus tard relève d'une révision du format |
| Les clés du schéma reprennent **à l'identique** les `id` actuels, fautes et accents compris (`familliaux`, `spécialistes`, `symétrique`, `pédieux`, `MDC`, `Isthme`) | Ces chaînes sont déjà les clés du brouillon `localStorage` d'une praticienne en exercice. Les renommer perd le bilan d'une consultation en cours | Aucune table de correspondance — elle créerait deux noms pour une même chose, à maintenir à vie. Un renommage, s'il devient souhaitable, se fera plus tard avec une migration explicite |
| Le titre d'un bloc est une donnée du **schéma**, jamais du thème | Faire venir un titre de bloc du thème obligerait C2-T1 à connaître la structure du formulaire, et recréerait la seconde source de vérité que C1-T2 vient de refermer | Le tableau des 29 blocs porte une colonne `Titre`, remplie pour dix blocs |
| Les largeurs restent dans le CSS ; le schéma n'en porte aucune | C'est la leçon de C1-T2 : une valeur écrite à deux endroits ressort tôt ou tard en défaut visible chez le client | Le schéma porte une `disposition` à valeurs fermées, reprises des classes existantes. Les largeurs ne figurent dans l'inventaire qu'à titre documentaire |
| Un seul niveau de regroupement : une liste **plate** de 29 blocs | `.bloc` est la notion sur laquelle repose la pagination du PDF ; une hiérarchie imbriquée n'aurait aucun répondant dans le code existant | L'ordre de la liste est l'ordre de rendu *et* l'ordre de pagination |
| **Ne pas corriger** les anomalies du HTML relevées en passant | Corriger un `id` fautif casse le brouillon de la praticienne pour rien. Les quatre `nom=` au lieu de `name=`, les `name` dupliqués entre les deux blocs chaussures, `date_naissance` en `type=text` : tous consignés, aucun réparé | Le document les énumère comme volontairement conservés, pour que personne ne les « nettoie » en C1-T3 |
| **Ne pas trancher** ici la contradiction entre la règle 1 de la section 7 et la règle d'évolution de la section 5.1 | Elle ne se manifeste qu'au moment d'écrire le validateur ; la trancher maintenant serait décider sans son contexte d'implémentation | Reportée sur C1-T3 dans la feuille de route |

## État des tests

Avant : 67 Python, 7 Node (file d'attente), 8 groupes (palette).
Après : les mêmes, plus **6 groupes (inventaire)**. Tout est vert, vérifié
après chacune des trois boucles de correction de la journée.

Ce qui est couvert de nouveau : un champ ajouté au formulaire sans être porté à
l'inventaire fait rougir l'intégration continue en nommant sa clé ; une image
annotable ajoutée, retirée ou déplacée aussi ; un bloc ajouté ou retiré aussi ;
un `id` dont `script.js` ou `style.css` dépend mais qui manque à la liste des
clés gelées aussi ; et une coordonnée du cabinet recopiée dans un des documents
de la tâche aussi.

## Constats de sécurité

Audit : **CONFORME SOUS RÉSERVE** au premier passage — 0 critique, 0 élevé,
3 moyens, 4 faibles — puis **CONFORME** après correction des sept constats,
chacun rejoué par l'auditeur sur des mutations de son choix.

Le constat qui justifiait la boucle : la spécification énumérait les `id` que le
futur moteur devra émettre à l'identique, mais **omettait `form-bilan`**, celui
du conteneur, dont dépendent à la fois la génération du PDF (`script.js:208`) et
la collecte du brouillon (`script.js:871`). Un moteur C1-T3 fidèle à la lettre
du document aurait pu renommer ce conteneur : plus de PDF, et un brouillon
enregistré vide, sans aucune erreur visible, en pleine consultation. La liste
est désormais dérivée mécaniquement de `script.js` et `style.css` au lieu d'être
recopiée à la main.

Deuxième correction utile : les 29 blocs et les 4 images étaient des
**constantes du test**, qui restait vert sur une cinquième image insérée. Or les
traits de stylet sont stockés par index : une image insérée en amont décale
toutes les annotations d'un brouillon existant. Ils sont maintenant recomptés
dans le HTML, avec contrôle de leur ordre.

Trois faibles résiduelles, reportées sur C1-T3 dans la feuille de route : la
garde d'identité du cabinet est ancrée sur les *numéros* de ligne 72-75 de
`index.html` et deviendra silencieusement verte quand C1-T3 réduira ce fichier
à une coquille ; `getElementById` n'est reconnu qu'en guillemets doubles ; et un
chemin de refus recopie des attributs dans le journal public de CI.

Revue : **À corriger** puis À livrer — 1 important, 3 mineures. L'important
était une contradiction interne du document sur le titre du bloc 2, qui aurait
fait disparaître « Informations Patient » du bilan rendu par le moteur.

## Ce qui reste en suspens

- **Le travail n'est pas commité.** Il vit sur la branche
  `c1-t1-inventaire-formulaire`, dans l'arbre de travail. Pour le débloquer :
  un commit sur cette branche, puis la fusion dans `main`.
- **Les coordonnées réelles du cabinet sont en dur dans `formulaire/index.html`
  (lignes 72-75)**, donc publiées de fait dans un dépôt lisible sous BUSL. La
  garde ajoutée aujourd'hui empêche seulement qu'elles se *propagent* aux
  nouveaux documents. Pour le débloquer : **C2-T1**, qui sort l'identité du
  cabinet du HTML pour la mettre en configuration.
- **Les six fichiers de référence visuelle** de `docs/references-visuelles/`,
  restés en suspens depuis C1-T2, serviront de point de comparaison à C1-T3.
  Pour le débloquer : les produire avant d'attaquer le moteur, sinon il n'y aura
  rien à quoi comparer le PDF rendu.

## Prochaine étape recommandée

`/lancer-tache C1-T3` — le moteur de rendu du schéma. Ses deux dépendances,
C1-T1 et C1-T2, sont maintenant livrées. C'est la tâche la plus lourde du
chantier et son point de non-retour : le contrat mérite d'être relu à froid
avant d'être implémenté, et les références visuelles d'être produites d'abord.

## À savoir pour la prochaine session

**Le contrat a tenu.** Les trois boucles de la journée (audit, réaudit, revue)
n'ont trouvé aucune erreur dans le contrat lui-même : ses références
`fichier:ligne` étaient exactes, ses décomptes reproductibles, ses critères
mécaniquement vérifiables. Ce qu'elles ont trouvé, ce sont des défauts du
livrable — et toujours le même genre de défaut, qui vaut d'être retenu pour
C1-T3.

**Le défaut récurrent : une liste normative recopiée à la main.** Les trois
constats sérieux de la journée sont la même erreur sous trois formes. Une liste
de clés gelées recopiée, donc incomplète (`form-bilan` manquant). Un décompte
figé en constante dans le test, donc insensible à la réalité (la cinquième
image). Une liste de « 9 blocs sans `id` » qui en contenait 10, dont un qui en
avait un. Chaque fois, le correctif a été le même : **dériver du code au lieu de
recopier**. En C1-T3, toute liste que le moteur consulte doit être dérivée, pas
transcrite.

**Une garde peut mentir en silence.** La garde d'intégration continue ajoutée
aujourd'hui vérifie les lignes 72 à 75 de `index.html` — par leur numéro. Elle
restera verte le jour où ces lignes bougeront, c'est-à-dire précisément en
C1-T3. Une garde muette est pire qu'une garde absente, parce qu'on cesse d'y
penser : c'est le premier point à traiter dans cette tâche.

**Ce qui a coûté du temps, et ce qui en a fait gagner.** Les mises en échec
délibérées — retirer une ligne de l'inventaire, tronquer une justification,
insérer une image surnuméraire — sont ce qui a réellement prouvé que le test
servait à quelque chose, et elles ont été rejouées à chaque boucle. À l'inverse,
le premier jet du test *passait* sur un formulaire modifié : sans ces mutations,
on aurait livré un garde-fou décoratif.

**Un piège du dépôt confirmé une fois de plus.** Le contrôle « aucun secret
versionné » lit `git ls-files`, qui ne voit pas les fichiers non suivis : les
cinq fichiers nouveaux de cette session lui étaient invisibles. Le contrôle de
clôture a donc été rejoué en y ajoutant explicitement les fichiers non suivis.
C'est exactement le piège qui avait fait échouer six travaux d'intégration
continue le 14 octobre.
