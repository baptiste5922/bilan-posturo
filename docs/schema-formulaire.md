# Spécification du schéma de formulaire — bilan-posturo

**Version du format de schéma : 1**

Ce document fige le vocabulaire qui permettra de décrire un bilan
posturologique par un fichier `schema.json` plutôt que par du HTML écrit à la
main. Il est la traduction exhaustive de `formulaire/index.html` (sous-arbre
`#form-bilan`, lignes 65-385) en un inventaire, un jeu fermé de types, une
structure de fichier et une règle de stabilité des clés. Il ne modifie aucune
ligne de code de production : `formulaire/` et `serveur/` restent intacts.

Les décisions structurantes (D1 à D7) sont tranchées dans
`docs/contrats/C1-T1.md`, section 7, et reprises ici telles quelles, sans être
rouvertes.

## 1. Objet et méthode

Le formulaire capturé dans le PDF est le sous-arbre `#form-bilan`
(`formulaire/index.html:65-385`). Tout ce qui le précède — boutons, barre
d'état, outils de stylet, lignes 26-63 — est hors du formulaire et ne relève
pas de ce schéma.

La pagination du PDF repose sur la classe `.bloc` : `script.js:234-239`
collecte `element.querySelectorAll(".bloc")` et nomme chaque bloc par
`b.id || b.className`. `.bloc` est donc une notion fonctionnelle : le schéma a
exactement un niveau de regroupement qui lui correspond (D6).

Les clés du brouillon `localStorage` sont dérivées par `cleChamp()`
(`script.js:863-867`) : l'`id` du champ s'il existe, sinon `name + "#" +
value`, sinon le champ est ignoré. Les champs sont collectés par
`champsDuFormulaire()` (`script.js:869-872`) sur `#form-bilan input, textarea,
select`. Ce document reprend ces deux règles à l'identique : c'est l'objet
même de la décision D2.

Les décomptes ci-dessous sont ceux du `formulaire/index.html` en vigueur au
15 octobre 2026. Ils se reproduisent avec la commande de la section 8 du
contrat C1-T1 ; si elle rend un chiffre différent, c'est que le formulaire a
changé depuis et cette spécification doit être reprise, pas ajustée en
silence.

| Élément | Nombre |
|---|---|
| `.bloc` (unité de pagination) | **29**, dont 9 sans attribut `id` |
| `input[type=text]` | 15 |
| `textarea` | 14 |
| `input[type=radio]` | 16 (**8 groupes** de 2) |
| `input[type=checkbox]` | 7 |
| `input[type=date]` | 1 |
| `img.dessinable` | 4 |
| `select` | 0 |
| `input[type=number]` | 0 |

Soit **53 contrôles de saisie**, **45 champs logiques** (un groupe de 2 radios
compte pour 1) et **4 images annotables**.

## 2. Les 29 blocs, dans l'ordre du DOM

Ce tableau est la transcription du squelette vérifié en section 3 du contrat
C1-T1. Il sert de repère pour le détail champ par champ de la section 3.

| # | Lignes | `id` | Titre | Classes hors `bloc` | Disposition retenue |
|---|---|---|---|---|---|
| 1 | 66-80 | — | — (hors schéma : titre d'en-tête thématique, voir section 9) | — | — (bloc d'en-tête, `en_tete: true`, voir D6) |
| 2 | 81-100 | `patient_infos` | « Informations Patient » (`patient_info_title`, gelé — section 5.2) | — | empilée |
| 3 | 103-108 | — | « Consultation » (`consultation_title`, non gelé — section 5.2) | — | empilée |
| 4 | 109-112 | — | — | — | empilée |
| 5 | 113-126 | — | — | `form-group-inline` | **en-ligne** |
| 6 | 127-131 | — | — | — | empilée |
| 7 | 132-147 | — | « ATCD » (porté par le bloc, pas par un champ) | `form-group-atcd` | **atcd** |
| 8 | 148-154 | `section_squelettes` | « Statique » (porté par le bloc, pas par un champ) | — | empilée (images) |
| 9 | 155-167 | `appui` | « Appui » (porté par le bloc ; repris aussi dans le libellé du champ radio, voir note) | `form-group-inline` | **en-ligne** |
| 10 | 169-190 | `Podo` | « Podo » (porté par le bloc, pas par un champ) | `form-group-inline` | **en-ligne** |
| 11 | 192-220 | `rotation` | — | *(élément `<table>`)* | — (type `tableau`, disposition sans objet) |
| 12 | 222-250 | `Posturo` | — | *(élément `<table>`)* | — (type `tableau`, disposition sans objet) |
| 13 | 252-264 | `spin` | « Spin test » (porté par le bloc ; repris aussi dans le libellé du champ radio, voir note) | `form-group-inline` | **en-ligne** |
| 14 | 266-269 | `section_elements_testes` | — | — | empilée |
| 15 | 271-274 | `section_bilan_algique` | — | — | empilée |
| 16 | 276-279 | `section_bilan_morpho` | — | — | empilée |
| 17 | 281-284 | `section_bilan_def` | — | — | empilée |
| 18 | 286-298 | `Pouls` | « Pouls » (porté par le bloc, pas par un champ) | `form-group-inline` | **en-ligne** |
| 19 | 301-304 | `section_enregistrement_plateforme` | — | — | empilée |
| 20 | 306-311 | `section_empreinte_encre` | — | `form-group-inline` | **en-ligne** |
| 21 | 313-326 | `section_chaussures_ville` | — | `chaussures-inline-group` | **chaussures** |
| 22 | 328-341 | `section_chaussures_sport` | — | `chaussures-inline-group` | **chaussures** |
| 23 | 343-352 | `section_plan_appareillage` | « Plan appareillage proposé » (porté par le bloc, pas par un champ) | — | empilée |
| 24 | 354-357 | — | — | `form-group-inline-bottom` | **en-ligne-bas** |
| 25 | 359-362 | — | — | `form-group-inline-bottom` | **en-ligne-bas** |
| 26 | 364-367 | — | — | `form-group-inline-bottom` | **en-ligne-bas** |
| 27 | 369-372 | `section_recouvrement` | — | — | empilée |
| 28 | 374-377 | `section_conseils` | — | — | empilée |
| 29 | 379-382 | `section_orientation` | — | — | empilée |

### Titre de bloc

`titre` (section 5.2) est une donnée du **schéma**, pas du thème : c'est le
texte d'un `<label>` ou d'un `<h3>` qui introduit tout le bloc sans être lié
par `for` à un champ particulier. Dix blocs en portent un, listés dans la
colonne ci-dessus ; les dix-neuf autres n'en ont pas (`—`).

Deux cas à ne pas lire de travers :

- **Blocs 9 (Appui) et 13 (Spin test).** Chacun ne contient qu'un seul champ
  `radio` : par commodité de lecture, la section 3 reprend le même texte en
  tête de la colonne « Libellé visible » de ce champ (`« Appui: » /
  « Antérieur », « Postérieur »`). C'est une redondance strictement
  documentaire, propre à cet inventaire : dans le schéma, seul `bloc.titre`
  porte ce texte, et le champ `radio` n'a besoin que du libellé de ses
  options.
- **Blocs 11 (rotation) et 12 (Posturo).** Le texte de leur `<th>` d'en-tête
  (« Rotation tête: », « Posturo dynamique: ») est au contraire le `libelle`
  de leur unique champ `tableau` lui-même (section 5.4) : bloc et champ se
  confondant, aucun `bloc.titre` distinct ne lui correspond — d'où le `—` de
  ces deux lignes.

`consultation_title` (bloc 3, `index.html:104`) n'est ciblé par aucune règle
CSS (`grep -n "consultation_title" formulaire/style.css` ne rend rien) : ce
n'est donc pas une clé gelée, mais « Consultation » reste une donnée du
schéma (`bloc.titre`) au même titre que « Informations Patient » — seul son
`id` n'a pas à être reproduit à l'identique par un futur moteur.

### Clés gelées

Un `id` est **gelé** s'il est à la fois (a) présent dans `#form-bilan` et (b)
lu par un sélecteur `#id` de `formulaire/style.css`, ou par
`document.getElementById("id")` / un sélecteur `#id` dans
`formulaire/script.js`. Cette intersection est recalculée mécaniquement par
`tests/test_inventaire_formulaire.js` à chaque exécution — elle n'est jamais
recopiée à la main — et le test échoue en nommant tout `id` gelé absent de la
liste ci-dessous. Un moteur C1-T3 qui renommerait un de ces `id`, **conteneur
compris**, casse soit le CSS, soit le JavaScript qui le cible par cet `id`
littéral.

- `form-bilan` — conteneur de tout le formulaire. Le plus critique des sept :
  `script.js:208` (`document.getElementById("form-bilan")`, génération du
  PDF) et `script.js:871` (`champsDuFormulaire()`, sélecteur `#form-bilan
  input, …`, collecte du brouillon) y échouent silencieusement s'il disparaît
  — respectivement aucun PDF (`console.error`, sans message au praticien) et
  un brouillon qui s'enregistre **vide** sans erreur visible. Référencé aussi
  en `script.js:130-131, 234-239, 1023` et `style.css:28`. Il n'est ni un bloc
  ni un champ du schéma — celui-ci ne modélise pas le conteneur — mais il doit
  être émis à l'identique par tout moteur de rendu.
- `patient_infos` — bloc 2 (`style.css:157,173,182-183,196`).
- `patient_info_title` — porte le `titre` **du schéma** du bloc 2
  (`bloc.titre`, section 5.2 ; voir aussi « Titre de bloc » plus haut), pas un
  texte du thème : seul l'`id` est gelé, le texte qu'il affiche vient de
  `clients/morlaix/schema.json`, pas de `theme.json` (`style.css:166`).
- `section_squelettes` — bloc 8 (`style.css:203,211`).
- `section_enregistrement_plateforme` — bloc 19 (`style.css:304,310`).
- `image_empreintes` — champ du bloc 23, type `image-annotable`
  (`style.css:342`).
- `logo` — image d'identité du cabinet, hors schéma : voir section 9
  (`style.css:46`).

Aucun autre `id` référencé par `script.js` ou `style.css` n'est présent dans
`#form-bilan` : les autres (`btn-export`, `barre-brouillon`, `barre-attente`,
`texte-attente`, `texte-brouillon`, `couleur-libre`, `epaisseur-trait`,
`apercu-trait`, `zone-messages`, `btn-dossier`, `btn-nouveau`,
`btn-restaurer`, `btn-abandonner`, `btn-reessayer`) appartiennent à la barre
d'outils, lignes 26-63, hors du formulaire (section 1) : ils ne sont ni gelés
ni concernés par ce schéma.

### Blocs sans `id`

Recomptés mécaniquement sur les 29 blocs de la section précédente (un bloc
sans attribut `id` dans son tag d'ouverture), et non recopiés à la main : les
**9** blocs sans `id` sont les blocs numéros `1`, `3`, `4`, `5`, `6`, `7`,
`24`, `25`, `26`. Le bloc 13 (`spin`) **a** un `id` et n'en fait pas partie.

Ces 9 blocs reçoivent dans le schéma une `cle` obligatoire que le moteur
émettra comme `id` HTML. C'est sans effet sur le brouillon (les clés de
brouillon viennent des champs, jamais des blocs) et sans effet sur le CSS
(aucune règle ne cible ces 9 blocs par `id` aujourd'hui, `spin` compris :
`grep -n "#spin" formulaire/style.css` ne rend rien) : c'est la seule
divergence de DOM volontaire à tolérer dans la comparaison automatisée de
C1-T3. Au-delà de ces 9, tout autre bloc qui perdrait son `id` dans un futur
moteur sortirait de cette tolérance — en particulier `spin`, qui en a un
aujourd'hui.

## 3. Inventaire détaillé : 45 champs et 4 images

Une ligne par champ logique ou par image. C'est la table que
`tests/test_inventaire_formulaire.js` compare, clé par clé, aux clés dérivées
mécaniquement de `formulaire/index.html` : **toute clé retirée d'une ligne
ci-dessous fait échouer ce test en la nommant.** Le même test recompte aussi,
à chaque exécution, le nombre de `.bloc` et d'`img.dessinable` réellement
présents dans le HTML (29 et 4) : il ne s'agit pas de constantes du test, un
bloc ou une image ajoutée dans `formulaire/index.html` sans mise à jour de
cet inventaire fait rougir l'intégration continue en le nommant.

Les valeurs de la colonne « Clé » sont les clés de brouillon telles qu'elles
sortiraient de `cleChamp()` — identiques aux `id` HTML, accents et fautes
compris (D2), sauf pour les 4 lignes de tableau, sans `id`, dont la clé est
`nom + "#" + valeur`.

**Deux granularités, une équivalence arithmétique.** Les « 45 champs
logiques » de cette section comptent chacune des 4 lignes des deux tableaux
(`test_positif`, `membre_court`, `dorsal`, `lombaire`) comme un champ à part
entière — c'est la granularité qui permet de vérifier, ligne par ligne, la
bijection avec les clés de brouillon. La structure du schéma (section 5) les
regroupe au contraire par table : les 4 lignes de tableau deviennent les
`lignes` de seulement **2 objets** de type `tableau` (un pour `rotation`, un
pour `Posturo`), chacun portant un en-tête de colonnes partagé. Un schéma de
production conforme à la section 5 contient donc **43 objets champ** (45 − 4
lignes de tableau + 2 objets `tableau`) **plus 4 objets `image-annotable`**,
et non 45 objets plus 4 images : un décompte structurel de contrôle (C7-T2)
ou de production (C1-T4) qui viserait « 45 champs dans le schéma » échouerait
à tort sur un schéma pourtant conforme. C'est le nombre de **lignes de cet
inventaire** qui vaut 45, pas le nombre d'objets JSON du futur
`clients/morlaix/schema.json`.

| Bloc | Lignes | Clé | Type retenu | Libellé visible | Valeurs possibles | Largeur observée (CSS) | Groupement | Anomalie |
|---|---|---|---|---|---|---|---|---|
| 1 | 69-70 | `date-bilan` | date | « Réalisé le » | libre (date) | — | — (en-tête) | — |
| 2 | 83-84 | `nom` | texte | « Nom: » | libre | — | empilée | — |
| 2 | 86-87 | `prenom` | texte | « Prénom: » | libre | — | empilée | — |
| 2 | 89-90 | `date_naissance` | texte | « Date de naissance: » | libre | — | empilée | A4 : `input type="text"`, pas `type="date"` |
| 2 | 92-93 | `sport` | texte | « Sport: » | libre | — | empilée | — |
| 2 | 95-96 | `metier` | texte | « Métier: » | libre | — | empilée | — |
| 2 | 98-99 | `niveau_scolaire` | texte | « Niveau Scolaire: » | libre | — | empilée | — |
| 3 | 105-106 | `MDC` | zone-texte | « MDC: » | libre | — | empilée | A3 : `id` en majuscules conservé (D2) |
| 4 | 110-111 | `oriente_par` | zone-texte | « Orienté par: » | libre | — | empilée | — |
| 5 | 113-123 | `SO_oui`, `SO_non` | radio | « Déjà SO: » / « Oui », « Non » | `oui` / `non` (attribut `value`) | — | **en-ligne** | A3 : `name="semelle_orthopédique"` accentué conservé (D2) |
| 6 | 128-129 | `spécialistes` | zone-texte | « Spécialistes: » | libre | — | empilée | A3 : `id` accentué conservé (D2) |
| 7 | 136-137 | `perso` | zone-texte | « Perso: » | libre | `style.css:133-134` (`.atcd-row textarea`) | **atcd** | — |
| 7 | 141-142 | `familliaux` | zone-texte | « Familiaux: » | libre | `style.css:133-134` (`.atcd-row textarea`) | **atcd** | A3 : `id` fautif (deux « l ») conservé (D2) |
| 8 | 150 | `squelette_gauche` | image-annotable | alt « squelette gauche » | traits de stylet (coordonnées normalisées 0-1) | `style.css:216` (`.squelette`) | — (ordre normatif, D7) | sans `id` dans le HTML (D7) |
| 8 | 151 | `squelette_droite` | image-annotable | alt « squelette droite » | traits de stylet (coordonnées normalisées 0-1) | `style.css:216` (`.squelette`) | — (ordre normatif, D7) | sans `id` dans le HTML (D7) |
| 8 | 152 | `squelette_dos` | image-annotable | alt « squelette dos » | traits de stylet (coordonnées normalisées 0-1) | `style.css:216` (`.squelette`) | — (ordre normatif, D7) | sans `id` dans le HTML (D7) |
| 9 | 159-165 | `anterieur`, `posterieur` | radio | « Appui: » / « Antérieur », « Postérieur » | sélection exclusive, sans attribut `value` | — | **en-ligne** | — |
| 10 | 173 | `symétrique` | case | « Symétrique » | coché / décoché | — | **en-ligne** | A3 : `id` accentué conservé (D2) |
| 10 | 177 | `Isthme` | case | « Isthme » | coché / décoché | — | **en-ligne** | A3 : `id` en majuscules conservé (D2) |
| 10 | 182-187 | `isthme_g`, `isthme_d` | radio | *(pas de libellé de groupe propre, sous « Podo: »)* / « Gauche », « Droit » | sélection exclusive, sans attribut `value` | — | **en-ligne** | — |
| 11 | 202-208 | `test_positif#G`, `test_positif#D` | tableau | « Rotation tête: » / ligne « Positif » | `G` / `D` (colonnes « Gauche(G) », « Droite (D) ») | — | — (type `tableau`) | sans `id` ; clé `nom#valeur` (D2, exception) |
| 11 | 211-217 | `membre_court#G`, `membre_court#D` | tableau | « Rotation tête: » / ligne « Plus court » | `G` / `D` (colonnes « Gauche(G) », « Droite (D) ») | — | — (type `tableau`) | sans `id` ; clé `nom#valeur` (D2, exception) |
| 12 | 232-238 | `dorsal#G`, `dorsal#D` | tableau | « Posturo dynamique: » / ligne « Dorsal » | `G` / `D` (colonnes « Gauche(G) », « Droite (D) ») | — | — (type `tableau`) | sans `id` ; clé `nom#valeur` (D2, exception) |
| 12 | 241-247 | `lombaire#G`, `lombaire#D` | tableau | « Posturo dynamique: » / ligne « Lombaire » | `G` / `D` (colonnes « Gauche(G) », « Droite (D) ») | — | — (type `tableau`) | sans `id` ; clé `nom#valeur` (D2, exception) |
| 13 | 256-261 | `gauche`, `droit` | radio | « Spin test: » / « Gauche », « Droit » | sélection exclusive, sans attribut `value` | — | **en-ligne** | — |
| 14 | 267-268 | `elements_testes` | zone-texte | « Elements testés: » | libre | — | empilée | — |
| 15 | 272-273 | `bilan_algique` | zone-texte | « Bilan algique: » | libre | — | empilée | — |
| 16 | 277-278 | `bilan_morpho` | zone-texte | « Bilan morpho: » | libre | — | empilée | — |
| 17 | 282-283 | `bilan_def` | zone-texte | « Bilan def: » | libre | — | empilée | — |
| 18 | 290-291 | `pédieux` | case | « Pédieux » | coché / décoché | — | **en-ligne** | A3 : `id` accentué conservé (D2) |
| 18 | 294-295 | `tibial` | case | « Tibial » | coché / décoché | — | **en-ligne** | — |
| 19 | 302-303 | `enregistrement_plateforme` | zone-texte | « Enregistrement Plateforme: » | libre | — | empilée | — |
| 20 | 308-309 | `empreinte_encre` | case | « Empreinte encre: » | coché / décoché | — | **en-ligne** | A6 : `type=checkbox` sans guillemets, label imbriqué dans un label |
| 21 | 314-315 | `chaussures_ville` | texte | « Chaussures ville: » | libre | `style.css:287-290` (`.chaussures-inline-group input[type="text"]`) | **chaussures** | A2 : `name="chaussures_modele"` dupliqué avec le bloc 22 |
| 21 | 318 | `usee_ville` | case | « Usées » | coché / décoché | — | **chaussures** | A2 : `name="chaussures_usees"` dupliqué avec le bloc 22 |
| 21 | 321-322 | `marque_ville` | texte | « Marque : » | libre | `style.css:287-290` | **chaussures** | A2 : `name="chaussures_marque"` dupliqué avec le bloc 22 |
| 21 | 324-325 | `type_ville` | texte | « Type : » | libre | `style.css:287-290` | **chaussures** | A2 : `name="chaussures_type"` dupliqué avec le bloc 22 |
| 22 | 329-330 | `chaussures_sport` | texte | « Chaussures sport : » | libre | `style.css:287-290` | **chaussures** | A2 : `name="chaussures_modele"` dupliqué avec le bloc 21 |
| 22 | 333 | `usee_sport` | case | « Usées » | coché / décoché | — | **chaussures** | A2 : `name="chaussures_usees"` dupliqué avec le bloc 21 |
| 22 | 336-337 | `marque_sport` | texte | « Marque : » | libre | `style.css:287-290` | **chaussures** | A2 : `name="chaussures_marque"` dupliqué avec le bloc 21 |
| 22 | 339-340 | `type_sport` | texte | « Type : » | libre | `style.css:287-290` | **chaussures** | A2 : `name="chaussures_type"` dupliqué avec le bloc 21 |
| 23 | 348 | `image_empreintes` | image-annotable | alt « Empreintes plantaires » | traits de stylet (coordonnées normalisées 0-1) | `style.css:342` (`#image_empreintes`) | — (ordre normatif, D7) | `id` réel, ciblé par le CSS : **clé gelée** |
| 23 | 350 | `plan_texte` | zone-texte | « Plan appareillage proposé : » | libre | — | empilée | A1 : `nom="plan_appareillage_notes"` au lieu de `name=`, sans effet |
| 24 | 355-356 | `pointure_ville` | texte | « Pointure ville: » | libre | `style.css:363-365` (`.form-group-inline-bottom input[type="text"]`) | **en-ligne-bas** | A1 : `nom="pointure_ville"` au lieu de `name=`, sans effet |
| 25 | 360-361 | `pointure_sport` | texte | « Pointure sport: » | libre | `style.css:363-365` | **en-ligne-bas** | A1 : `nom="semelle_base"` au lieu de `name=`, sans effet ; valeur dupliquée avec le bloc 26, sans effet |
| 26 | 365-366 | `base` | texte | « Base : » | libre | `style.css:363-365` | **en-ligne-bas** | A1 : `nom="semelle_base"` au lieu de `name=`, sans effet ; valeur dupliquée avec le bloc 25, sans effet |
| 27 | 370-371 | `recouvrement` | zone-texte | « Recouvrement : » | libre | — | empilée | — |
| 28 | 375-376 | `conseils` | zone-texte | « Conseils: » | libre | — | empilée | — |
| 29 | 380-381 | `orientation` | zone-texte | « Orientation: » | libre | — | empilée | A5 : `<textarea type="text">`, sans effet |

Légende des anomalies, détaillées en section 8 :
**A1** `nom=` au lieu de `name=` · **A2** `name` dupliqué entre deux blocs ·
**A3** faute ou accent figé dans un `id`/`name`, conservé par D2 · **A4**
`date_naissance` en `type=text` · **A5** `<textarea type="text">` sans effet ·
**A6** `type=checkbox` sans guillemets.

## 4. Jeu de types retenu

### 4.1 Types retenus

Sept types, et pas un de plus (D1) :

1. **`texte`** — une ligne de saisie libre. 15 occurrences dans le formulaire
   actuel.
2. **`zone-texte`** — plusieurs lignes de saisie libre, agrandissement
   automatique. 14 occurrences.
3. **`date`** — une date. 1 occurrence (`date-bilan`), bien que portée
   aujourd'hui par un `input[type=text]` dans un seul autre cas
   (`date_naissance`, anomalie A4, non reclassée — voir section 8).
4. **`case`** — une case à cocher binaire. 7 occurrences.
5. **`radio`** — un choix exclusif entre plusieurs options, portées chacune
   par son propre `id`. 4 occurrences (8 options).
6. **`tableau`** — un en-tête de colonnes partagé par plusieurs lignes, chaque
   cellule étant un bouton radio sans `id`. 2 occurrences (`rotation`,
   `Posturo`), 4 lignes au total.
7. **`image-annotable`** — une image sur laquelle le praticien trace des
   traits au stylet. 4 occurrences.

Ces sept types couvrent 100 % des 53 contrôles de saisie et des 4 images du
formulaire actuel ; aucun élément n'est « non exprimable ».

### 4.2 Types écartés

- **`nombre`** — zéro occurrence dans `#form-bilan` : les pointures
  elles-mêmes sont saisies en texte (`pointure_ville` ligne 356,
  `pointure_sport` ligne 361). Le seul contrôle numérique de tout le fichier
  est `#epaisseur-trait` (ligne 61), un réglage de stylet situé hors du
  formulaire, donc hors du schéma.
- **`liste`** — zéro `<select>` dans le fichier entier : aucun champ actuel ne
  requiert une liste déroulante, et en ajouter une « au cas où » créerait un
  type à maintenir chez tous les clients sans qu'aucun champ existant n'en ait
  besoin.
- **`paragraphe`** — les seuls textes statiques du formulaire sont l'identité
  du cabinet (lignes 72-75, qui relève du thème, voir C2-T1 et section 9
  ci-dessous) et les libellés de lignes des deux tableaux, déjà portés par le
  type `tableau`. Aucun champ actuel n'a besoin d'un texte statique propre.

Ajouter un huitième type — que ce soit l'un de ces trois ou un autre — relève
d'une révision de la version du format de schéma (section 5.1), jamais d'un
ajout silencieux au jeu existant.

## 5. Structure du fichier de schéma

### 5.1 Document racine et version

```json
{
  "version_schema": 1,
  "blocs": []
}
```

`version_schema` (entier, obligatoire, première clé du fichier) est la
version du **format de schéma**, distincte du `version: 1` porté par
l'enveloppe du brouillon `localStorage` (`script.js:892`) : les deux ne
décrivent pas la même chose et ne doivent jamais être alignées par
convention.

Règle d'évolution : on n'incrémente `version_schema` que pour un changement
incompatible (un type retiré, un attribut obligatoire ajouté à un type
existant) ; un ajout purement facultatif ne change pas la version ; le moteur
refuse de rendre une version qu'il ne connaît pas, plutôt que de rendre au
mieux.

### 5.2 Bloc

Un bloc est l'unique niveau de regroupement (D6). Le document est une liste
**plate** de blocs, dans l'ordre, qui est l'ordre de rendu et l'ordre de
pagination.

| Attribut | Obligatoire | Valeur par défaut | Description |
|---|---|---|---|
| `cle` | oui | — | Identifiant stable du bloc, émis comme `id` HTML. |
| `en_tete` | non | `false` | `true` pour le bloc 1 uniquement ; ce bloc ne porte que le champ `date-bilan`, le reste (titre, logo, coordonnées) vient du thème (C2-T1). |
| `disposition` | non | `"empilee"` | Une des cinq valeurs fermées : `empilee`, `en-ligne`, `en-ligne-bas`, `atcd`, `chaussures` (D5). |
| `titre` | non | — | Libellé visible du bloc, quand il en a un dans le HTML actuel (ex. « Informations Patient », bloc 2) ; dix des 29 blocs en portent un, voir « Titre de bloc » en section 2. C'est toujours une donnée du schéma, jamais du thème, y compris pour les blocs dont l'`id` de titre est une clé gelée (`patient_info_title`). |
| `champs` | oui | — | Liste ordonnée d'objets champ (section 5.3). Peut contenir des types `tableau` ou `image-annotable` au même titre que les autres. |

Le schéma ne porte aucune largeur (D5) : la mise en page détaillée reste
entièrement dans le CSS du thème. Les largeurs observées dans l'inventaire
(section 3) sont documentaires.

### 5.3 Champ — attributs communs

| Attribut | Obligatoire | Description |
|---|---|---|
| `type` | oui | Une des sept valeurs de la section 4.1. |
| `cle` | selon le type (voir ci-dessous) | Clé de brouillon, identique à l'`id` actuel (D2). |
| `libelle` | oui, sauf exception documentée | Texte visible, relevé dans le HTML. |
| `defaut` | non | Valeur préremplie. **Aucun champ de la V1 n'en porte** (D4) : un champ clinique prérempli est un risque de bilan faux. Le moteur ne préremplit rien en son absence. Interdit sur `radio`, `tableau` et `image-annotable`. |
| `valeurs` | oui pour `radio` uniquement | Liste d'options, chacune `{ "cle": "...", "valeur": "...", "libelle": "..." }`. |
| `entetes` | oui pour `tableau` uniquement | En-tête de colonnes, partagé par toutes les lignes. |
| `lignes` | oui pour `tableau` uniquement | Liste de `{ "nom": "...", "cle": "...", "colonnes": [{ "valeur": "...", "libelle": "..." }, ...] }`. |
| `fichier` | oui pour `image-annotable` uniquement | Chemin de l'image à annoter. |
| `texte_alternatif` | oui pour `image-annotable` uniquement | Texte alternatif de l'image. |

`type`, `cle` (ou `valeurs`/`lignes` selon le type) et `libelle` forment
l'ensemble fermé des attributs structurants ; `disposition` ne vit qu'au
niveau du bloc (section 5.2), jamais au niveau du champ.

**Interdiction normative (D2, exception des radios de tableau) :** pour le
type `tableau`, il est interdit au moteur d'attribuer un `id` aux boutons
radio qu'il génère. Leur clé de brouillon reste `ligne.cle + "#" +
colonne.valeur`, par exemple `test_positif#G` — exactement la forme que
`cleChamp()` produit aujourd'hui pour un champ sans `id`. Leur attribuer un
`id` changerait la forme de leur clé et perdrait les cases déjà cochées d'un
brouillon en cours.

**Ordre normatif des images (D7) :** les traits de stylet sont stockés par
**index** dans le brouillon (`script.js:893`, `941-946`), et cet index suit
l'ordre d'apparition des `image-annotable` dans le document — bloc après
bloc, champ après champ — exactement comme `zonesDessin` est peuplé dans
l'ordre du DOM (`script.js:620`). Permuter deux `image-annotable` dans le
schéma, même sans toucher à leur `cle`, déplace les traits d'un brouillon
existant sur la mauvaise image. Chaque image a malgré cela sa propre `cle` —
`squelette_gauche`, `squelette_droite`, `squelette_dos`, `image_empreintes` —
qui ne sert qu'à l'identifier dans le schéma, pas à retrouver ses traits : la
position prime.

### 5.4 Un exemple par type

Chaque exemple est tiré d'un champ réel du formulaire actuel.

**`texte`** — champ `nom` (`formulaire/index.html:83-84`) :

```json
{
  "cle": "nom",
  "type": "texte",
  "libelle": "Nom"
}
```

**`zone-texte`** — champ `bilan_algique` (`formulaire/index.html:272-273`) :

```json
{
  "cle": "bilan_algique",
  "type": "zone-texte",
  "libelle": "Bilan algique"
}
```

**`date`** — champ `date-bilan` (`formulaire/index.html:69-70`) :

```json
{
  "cle": "date-bilan",
  "type": "date",
  "libelle": "Réalisé le"
}
```

**`case`** — champ `tibial` (`formulaire/index.html:294-295`) :

```json
{
  "cle": "tibial",
  "type": "case",
  "libelle": "Tibial"
}
```

**`radio`** — champ « Déjà SO » (`formulaire/index.html:113-123`) :

```json
{
  "type": "radio",
  "libelle": "Déjà SO",
  "valeurs": [
    { "cle": "SO_oui", "valeur": "oui", "libelle": "Oui" },
    { "cle": "SO_non", "valeur": "non", "libelle": "Non" }
  ]
}
```

**`tableau`** — bloc « rotation » (`formulaire/index.html:192-220`) :

```json
{
  "type": "tableau",
  "libelle": "Rotation tête",
  "entetes": ["Gauche(G)", "Droite (D)"],
  "lignes": [
    {
      "nom": "Positif",
      "cle": "test_positif",
      "colonnes": [
        { "valeur": "G", "libelle": "Gauche(G)" },
        { "valeur": "D", "libelle": "Droite (D)" }
      ]
    },
    {
      "nom": "Plus court",
      "cle": "membre_court",
      "colonnes": [
        { "valeur": "G", "libelle": "Gauche(G)" },
        { "valeur": "D", "libelle": "Droite (D)" }
      ]
    }
  ]
}
```

**`image-annotable`** — champ `squelette_gauche` (`formulaire/index.html:150`) :

```json
{
  "cle": "squelette_gauche",
  "type": "image-annotable",
  "libelle": "Squelette gauche",
  "fichier": "images/squelette_gauche.png",
  "texte_alternatif": "squelette gauche"
}
```

## 6. Règle de stabilité des clés

**Les clés reprennent à l'identique les `id` actuels. Aucune table de
correspondance n'existe ni ne sera créée** (D2). Accents, majuscules et
fautes comprises : `familliaux`, `spécialistes`, `symétrique`, `pédieux`,
`MDC`, `Isthme` sont des clés valides et définitives du schéma, exactement
comme elles sont aujourd'hui des clés du brouillon `localStorage`
(`cleChamp()`, `script.js:863-867`) d'une praticienne en exercice.

Les renommer perdrait le bilan d'une consultation en cours. Une table de
correspondance est refusée par principe : elle créerait deux noms pour une
même chose, à maintenir à vie. Un renommage, s'il devient un jour
souhaitable, se fera avec une migration de brouillon explicite et séparée de
toute bascule de moteur — jamais en même temps.

**Exception unique : les 8 boutons radio des deux tableaux**
(`formulaire/index.html:204, 207, 213, 216, 234, 237, 243, 246`). Ils n'ont
pas d'`id` ; leur clé de brouillon est `name + "#" + value`, par exemple
`test_positif#G`. Le schéma les décrit donc par le `nom` de leur ligne et la
`valeur` de leur colonne (section 5.3, type `tableau`), et il est **interdit**
au moteur de leur ajouter un `id` : la clé changerait de forme et le
brouillon serait perdu.

## 7. Règles de validation

Liste fermée et numérotée. Chaque règle est formulée pour qu'un test puisse
la mettre en échec (C7-T2).

1. Le document racine est un objet JSON avec exactement les clés
   `version_schema` et `blocs` ; toute clé supplémentaire à la racine est
   refusée.
2. `version_schema` doit être un entier connu du moteur. Une version
   supérieure à celle qu'il sait lire est refusée **sans rendu partiel** —
   jamais un rendu au mieux.
3. `blocs` est un tableau non vide ; chaque élément est un objet.
4. Chaque bloc porte une `cle` non vide, unique parmi tous les blocs. Un bloc
   sans `cle`, ou dont la `cle` est déjà prise par un autre bloc, est refusé
   en nommant l'index du bloc fautif.
5. `disposition`, quand il est présent, doit être une des cinq valeurs
   fermées `empilee`, `en-ligne`, `en-ligne-bas`, `atcd`, `chaussures` ;
   toute autre valeur est refusée en la citant.
6. `en_tete`, quand il vaut `true`, ne peut être porté que par un seul bloc
   du document, qui doit être le premier de la liste ; toute autre
   configuration est refusée.
7. Chaque champ porte un `type` parmi les sept retenus en section 4.1. Un
   type absent du jeu fermé — y compris `nombre`, `liste` ou `paragraphe` —
   est refusé en nommant le type et le bloc où il apparaît.
8. Pour les types `texte`, `zone-texte`, `date`, `case` et `image-annotable` :
   la `cle` du champ est obligatoire et unique dans tout le document, tous
   blocs confondus. Une collision est refusée en nommant les deux
   emplacements en cause.
9. Pour `radio` : `valeurs` est un tableau d'au moins deux entrées, chacune
   avec `cle`, `valeur` et `libelle` non vides. Les `cle` y sont soumises à
   la même règle d'unicité globale qu'au point 8.
10. Pour `tableau` : `lignes` est un tableau d'au moins une entrée, chacune
    avec un `nom`, une `cle` et au moins deux `colonnes`, chacune avec
    `valeur` et `libelle` non vides. Il est en outre interdit au moteur
    d'attribuer un `id` à ces boutons radio (section 5.3) : toute
    implémentation qui le ferait est non conforme à cette spécification,
    même si elle produit un document JSON valide.
11. L'attribut facultatif `defaut` n'est autorisé que sur `texte`,
    `zone-texte`, `date` et `case`. Présent sur `radio`, `tableau` ou
    `image-annotable`, il est refusé en nommant le champ.
12. `libelle` est obligatoire pour `texte`, `zone-texte`, `date`, `case`,
    `tableau` (titre du tableau) et `image-annotable` (sert alors de texte
    alternatif). Il est facultatif pour `radio`, dont les options portent
    chacune leur propre `libelle` — un groupe de radios peut n'avoir aucun
    libellé propre quand le HTML actuel n'en porte pas (cas de
    `isthme_cote`, regroupé visuellement sous le libellé du bloc « Podo »).

## 8. Anomalies du HTML consignées, non corrigées

Ces anomalies sont réelles, vérifiées, et **ne sont pas corrigées** par cette
tâche ni par aucune suivante sans migration explicite du brouillon : corriger
un `id` casserait le brouillon `localStorage` d'une consultation en cours.

- **A1 — Quatre attributs `nom=` au lieu de `name=`**
  (`formulaire/index.html:350, 356, 361, 366` : `nom="plan_appareillage_notes"`,
  `nom="pointure_ville"`, `nom="semelle_base"` deux fois). Traitement retenu :
  consigné dans l'inventaire (section 3), non corrigé. Sans effet observable,
  car ces champs sont identifiés par leur `id` dans `cleChamp()`.
- **A2 — `name` dupliqué entre les blocs chaussures ville et sport**
  (`chaussures_modele`, `chaussures_usees`, `chaussures_marque`,
  `chaussures_type`, lignes 315/330, 318/333, 322/337, 325/340). Traitement
  retenu : consigné, non corrigé. Sans effet aujourd'hui car `cleChamp()`
  préfère l'`id` ; le schéma ne porte d'ailleurs aucun attribut `name` (section
  5.3), ce qui empêche structurellement cette anomalie de se reproduire dans
  un futur moteur de rendu construit à partir de ce schéma.
- **A3 — Fautes et accents figés dans les `id`/`name`** (`familliaux` l.142,
  `spécialistes` l.129, `symétrique` l.173, `pédieux` l.290, `MDC` l.106 et
  `Isthme` l.177 en majuscules, `name="semelle_orthopédique"` l.117).
  Traitement retenu : conservés **à l'identique** dans le schéma, par décision
  D2 (section 6) — ce n'est pas une tolérance mais une protection du brouillon
  en cours.
- **A4 — `date_naissance` est un `input[type=text]`, pas un `type=date`**
  (`formulaire/index.html:90`). Traitement retenu : consigné, non corrigé ;
  le type retenu dans le schéma est `texte`, pas `date`, pour refléter
  fidèlement le comportement actuel du champ.
- **A5 — `<textarea type="text">`** (`formulaire/index.html:381`, champ
  `orientation`). Traitement retenu : consigné, non corrigé ; l'attribut
  `type` est sans effet sur un `textarea`.
- **A6 — `type=checkbox` sans guillemets, dans un `<label>` imbriqué dans un
  autre `<label>`** (`formulaire/index.html:307-310`, champ
  `empreinte_encre`). Traitement retenu : consigné, non corrigé.

## 9. Hors périmètre de ce schéma

Ce schéma décrit exclusivement les blocs, les champs et les images
annotables de `#form-bilan`. N'y figurent pas, et relèvent de `theme.json`
(C2-T1) :

- la palette de couleurs (cinq tokens, voir C1-T2) ;
- le logo et son emplacement ;
- le titre « Bilan Posturologique » et les autres textes d'en-tête fixes ;
- l'identité du cabinet (nom, adresse postale, courriel, téléphone),
  aujourd'hui en dur dans `formulaire/index.html:72-75`, délibérément **non
  reproduite** dans ce document.

Le bloc 1 (en-tête, section 2) porte le drapeau `en_tete: true` et ne contient
qu'un seul champ de schéma, `date-bilan` : tout le reste de son contenu visuel
— titre « Bilan Posturologique », logo, coordonnées — vient du thème. Aucun
type `paragraphe` n'est créé pour porter l'identité du cabinet (voir
section 4.2).

**Précision pour ne pas lire ce qui précède à l'envers :** cette exclusion ne
vaut que pour le bloc 1 et pour la palette/le logo/l'identité du cabinet. Le
`titre` d'un bloc **ordinaire** (section 5.2, section 2 « Titre de bloc »)
n'est pas un texte du thème : c'est une donnée du schéma, au même titre que
les champs. « Informations Patient » (bloc 2), « Consultation » (bloc 3),
« Podo » (bloc 10)… relèvent de `clients/morlaix/schema.json`, pas de
`theme.json` ; seuls le titre d'en-tête du bloc 1 et les éléments listés
ci-dessus en sont exemptés.

Sont également hors périmètre de ce document : le moteur de rendu
(`formulaire/moteur/rendu.js`, C1-T3), le fichier de production
`clients/morlaix/schema.json` (C1-T4), la bibliothèque de blocs réutilisables
(C1-T5) et le questionnaire commercial (C9-T1).
