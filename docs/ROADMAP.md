# Feuille de route V1 → V2

> **Objet.** Décrire, tâche par tâche, le travail qui sépare la V1 (un cabinet,
> installation manuelle, formulaire écrit à la main) de la **V2 « industrialisée »**
> définie en section 7 de `docs/projection.md` : installateur, moteur à schéma,
> mises à jour signées, diagnostic à distance, support.
>
> **Document de travail interne.** Il s'appuie sur `docs/projection.md`, dont il
> est la traduction opérationnelle. La projection dit *pourquoi* ; cette feuille
> de route dit *quoi faire, dans quel ordre, et comment savoir que c'est fini*.

**Dernière mise à jour :** 19 octobre 2026
**État de départ :** V1 en production chez un cabinet depuis deux mois.

> **Décisions métier du 3 novembre 2026** (Baptiste), reportées dans les
> tâches concernées :
> 1. **Pas de tunnel de support.** Le support passe par `technique.log` envoyé
>    par courriel et par une séance d'assistance ouverte par le praticien.
>    C4-T5 sort de la V2.
> 2. **Mises à jour tirées et signées** : le PC vérifie GitHub Releases et
>    n'installe qu'un paquet signé (C5, plan inchangé).
> 3. **Licence expirée : délai de grâce, puis export bloqué.** Trente jours de
>    bandeau, puis la saisie reste possible mais l'export est refusé. Jamais
>    d'arrêt du serveur, et jamais un bilan déjà produit n'est touché (C8-T1).
> 4. **Évolutions après livraison : une révision annuelle**, incluse dans
>    l'abonnement ; une urgence se facture à part (C9-T3).
>
> **Premier prospect hors cabinet pilote (novembre 2026)** : un formateur en
> posturologie, à installer à distance. Sa fiche impose un type `grille` que
> le vocabulaire n'a pas (C1-T6), et la relecture des scripts d'installation
> pour l'installer à distance a mis en évidence un défaut probable (C3-T3a).

---

## Sommaire

| Chantier | Intitulé | Verrou levé | Bloque la vente ? |
|---|---|---|---|
| [C0](#c0--cadre-juridique-et-licence) | Cadre juridique et licence | n°5 | **Oui, en amont de tout** |
| [C1](#c1--moteur-de-formulaire-à-schéma) | Moteur de formulaire à schéma | n°2 | **Oui** |
| [C2](#c2--identité-du-cabinet-en-configuration) | Identité du cabinet en configuration | n°2 | **Oui** |
| [C3](#c3--adressage-certificat-et-installateur) | Adressage, certificat et installateur | n°1 | **Oui** |
| [C4](#c4--observabilité-et-support-à-distance) | Observabilité et support à distance | n°4 | Oui (marge) |
| [C5](#c5--mises-à-jour-signées) | Mises à jour signées | n°3 | **Oui** |
| [C6](#c6--durcissement-de-sécurité) | Durcissement de sécurité | n°7 | Non |
| [C7](#c7--filet-de-tests) | Filet de tests | — | Non (mais pilote la marge) |
| [C8](#c8--mécanisme-de-licence-dabonnement) | Mécanisme de licence d'abonnement | — | Oui (facturation) |
| [C9](#c9--atelier-de-fabrication-dun-client) | Atelier de fabrication d'un client | — | Oui (plafond de croissance) |
| [C10](#c10--hors-périmètre-v2) | Hors périmètre V2 | — | — |

**Définition de « V2 livrée » :** un cabinet inconnu peut être installé en moins
de deux heures sans qu'un certificat racine soit manipulé à la main, son
formulaire est décrit par un fichier de schéma et non par du HTML sur mesure, un
correctif se propage à tout le parc sans déplacement, et une panne se diagnostique
à distance sans jamais lire une donnée de santé.

---

## Conventions

- **ID de tâche** : `C<chantier>-T<numéro>`. Il sert de nom de branche
  (`c1-t3-moteur-rendu`), de nom de contrat (`docs/contrats/C1-T3.md`) et de
  préfixe de message de commit.
- **Effort** : S = moins d'une demi-journée, M = 1 à 3 jours, L = 1 à 2 semaines,
  XL = au-delà, à découper avant d'être attaqué.
- **Critères d'acceptation** : rédigés pour être vérifiables sans interprétation.
  Une tâche dont les critères ne sont pas tous verts n'est pas livrée.
- **Process** : le niveau de chaîne à appliquer à la tâche, défini ci-dessous.
  Il est fixé une fois pour toutes ici et ne se renégocie pas au moment de coder.

### Les trois niveaux de process

La chaîne complète — contrat, implémentation, audit, revue, clôture — a été
écrite pour les tâches qui peuvent casser une consultation ou ouvrir une faille.
L'appliquer à l'écriture d'un document commercial coûte une session entière pour
rien. Chaque tâche porte donc un niveau, choisi sur une seule question :
**qu'est-ce qui se passe si c'est faux ?**

| Niveau | Chaîne | Pour quoi |
|---|---|---|
| **Direct** | Une consigne, l'implémentation, une vérification humaine. Pas de contrat, pas d'agent. | Documents, décisions, procédures, tests seuls, outillage hors production. Si c'est faux, on le voit et on le réécrit. |
| **Allégé** | Contrat court (périmètre + critères, pas de plan détaillé) → implémentation → tests. La revue est faite dans la foulée, sans agent séparé. | Code qui ne touche ni l'authentification, ni les données de santé, ni le formulaire de production. Si c'est faux, un test le voit. |
| **Allégé + audit** | Idem, plus l'auditeur de sécurité sur **un point nommé** dans le contrat. | Petites tâches de sécurité dont l'enjeu tient en une phrase : remontée de répertoire, purge de fichiers, validation d'entrée. L'audit cible, il ne balaie pas. |
| **Complet** | `/lancer-tache` → `/implementer-tache` (audit compris) → `/revue-code` → `/cloture-projet`. | Serveur, authentification, cryptographie, journalisation, formulaire de production, code installé chez un client. Si c'est faux, un cabinet s'en aperçoit avant nous. |

Trois règles qui ne se discutent pas :

1. **On peut monter de niveau en cours de route, jamais descendre.** Une tâche
   « Direct » qui se révèle toucher le serveur s'arrête et repart en contrat.
2. **Tout ce qui est marqué Complet le reste**, même si la modification paraît
   tenir en trois lignes le jour venu. C'est précisément là que la V1 a produit
   ses pièges.
3. **Le niveau ne change pas l'exigence de tests.** Il change qui écrit le
   cadrage et combien d'agents relisent — pas le fait qu'une tâche livrée soit
   verte en intégration continue.

**Répartition.** Sur les 33 tâches restantes : 9 en Direct, 7 en Allégé,
5 en Allégé + audit, 12 en Complet. La moitié du reste à faire n'a jamais eu
besoin de la chaîne complète.

---

## C0 — Cadre juridique et licence

**Pourquoi d'abord.** Chaque semaine de développement passée sous licence MIT
agrandit la base de code que n'importe qui — y compris un concurrent — pourra
reprendre et vendre. Le dépôt est public : ce qui est déjà publié sous MIT le
reste définitivement. Ce chantier ne produit presque pas de code, et il
conditionne la valeur de tout le reste.

### C0-T1 — Trancher la licence des développements à venir

> **État : livré le 14 octobre 2026.** BUSL 1.1 retenue, `Change License`
> MIT, `Change Date` 2030-10-14. Commit frontière `9339ee9`, étiqueté
> `frontiere-mit` et poussé. Les 17 critères sont vérifiés. Contrat,
> audit et revue : `docs/contrats/C0-T1.md`, `docs/audits/C0-T1.md`,
> `docs/revues/C0-T1.md`. Reste à faire relire l'`Additional Use Grant`
> par un conseil, groupé avec C0-T2.

- **Effort :** S (décision) + S (mise en œuvre)
- **Dépendances :** aucune
- **Périmètre :** `LICENSE`, `README.md`, en-têtes de fichiers, `package.json`
- **Travail :**
  1. Arrêter le modèle : (a) rester MIT et vendre le service ; (b) passer en
     source-available non concurrentielle (BUSL, PolyForm Noncommercial) pour la
     suite ; (c) fermer le dépôt et ne publier qu'un paquet binaire.
  2. Figer un **commit frontière** et le documenter : « tout ce qui précède
     `<sha>` reste MIT ».
  3. Si changement : nouveau `LICENSE`, `LICENSE-MIT-HISTORIQUE` conservé, section
     « Licence » du `README.md` réécrite, `license` de `package.json` mis à jour.
  4. Vérifier la compatibilité des dépendances vendorisées (jsPDF MIT, html2canvas
     MIT) : aucune ne s'oppose à un durcissement du code propre.
- **Critères d'acceptation :**
  - `LICENSE` décrit sans ambiguïté ce qui est permis à un tiers commercial.
  - Le commit frontière est nommé dans `README.md`.
  - Aucun fichier ne porte deux mentions de licence contradictoires.
- **Risque :** un durcissement rétroactif est impossible ; décider tard coûte
  définitivement.

### C0-T2 — Contrat de sous-traitance et registre

- **Effort :** M (dont une grande part hors code)
- **Process :** Direct — hors code ; la relecture par un conseil tient lieu de revue.
- **Dépendances :** C0-T1
- **Périmètre :** `docs/juridique/` (nouveau dossier, non versionné publiquement
  si le dépôt reste ouvert)
- **Travail :**
  1. Contrat de sous-traitance art. 28 RGPD, mentionnant nommément les
     sous-traitants ultérieurs (Tailscale, et lui seul si rien d'autre ne sort).
  2. Registre de sous-traitant art. 30.2 — une page.
  3. Notice de traitement remise au cabinet, incluant la phrase sur l'accès du
     prestataire de maintenance.
  4. CGU/CGV avec la durée de conservation de `journal.log` chiffrée en mois.
  5. Faire confirmer par un DPO l'exigibilité de l'AIPD pour un libéral seul.
- **Critères d'acceptation :**
  - Un cabinet peut signer sans que l'on ait à rédiger quoi que ce soit de plus.
  - La durée de conservation des journaux est un nombre, écrite au même endroit
    dans le contrat et dans le code (C4-T2).
- **Risque :** sans ce contrat, la non-conformité est la plus facile à constater
  lors d'un contrôle.

---

## C1 — Moteur de formulaire à schéma

**Pourquoi.** `formulaire/index.html` compte 388 lignes de HTML écrit à la main
pour une praticienne : 29 blocs, 45 champs logiques et 4 images annotables
identifiés (inventaire C1-T1), l'identité du cabinet en dur lignes 72-75.
Face au deuxième cabinet, les deux seules réponses possibles sans moteur sont
mauvaises : imposer le template (on devient le Cegedim que l'on
dénonce) ou maintenir un HTML par client (10 clients = 10 divergences, et le
premier correctif de pagination devient impossible à propager).

**Cible.** Un moteur unique, N descriptions. `schema.json` décrit les sections,
les champs et les images annotables ; `theme.json` décrit la palette, le logo et
l'en-tête ; le moteur de rendu, identique chez tous les clients, produit le DOM.

### C1-T1 — Inventorier le formulaire existant et en déduire le vocabulaire de schéma

> **État : livré le 15 octobre 2026.** `docs/schema-formulaire.md` inventorie
> les 29 blocs, 45 champs logiques et 4 images annotables de `#form-bilan`
> (contre l'estimation initiale de 17 blocs et d'une petite centaine de
> champs). Jeu fermé de sept types (`texte`, `zone-texte`, `date`, `case`,
> `radio`, `tableau`, `image-annotable`), trois types écartés et justifiés
> (`nombre`, `liste`, `paragraphe`), clés de brouillon reprises à l'identique
> des `id` actuels, fautes et accents compris — aucune table de
> correspondance. Les 13 critères sont vérifiés, dont les mises en échec
> délibérées (retrait d'une ligne de champ, retrait d'une justification,
> image annotable surnuméraire, attribut non guillemeté).
> `tests/test_inventaire_formulaire.js` (6 groupes) couvre la bijection clés
> HTML ↔ inventaire — avec recomptage des 29 blocs et des 4 images dans le
> HTML à chaque exécution, et contrôle de leur ordre —, la version du format,
> un exemple JSON par type, l'absence de type écarté dans un exemple, les
> justifications, et l'exhaustivité des clés gelées, conteneur `#form-bilan`
> compris. Un pas d'intégration continue vérifie en outre qu'aucune
> coordonnée du cabinet n'est recopiée dans les documents de la tâche. Aucun
> octet de `formulaire/` ni `serveur/` modifié. Contrat :
> `docs/contrats/C1-T1.md` ; audit : `docs/audits/C1-T1.md` (CONFORME) ;
> revue : `docs/revues/C1-T1.md` (une contradiction interne sur le titre du
> bloc 2, corrigée : un titre de bloc est une donnée du schéma, jamais du
> thème).

- **Effort :** M
- **Dépendances :** aucune
- **Périmètre :** `docs/schema-formulaire.md` (spécification), lecture de
  `formulaire/index.html`
- **Travail :**
  1. Lister les blocs et les champs du formulaire (une première estimation,
     révisée par l'inventaire, en comptait 17 et une petite centaine), avec
     pour chacun : type (`texte`, `nombre`, `date`, `case`, `radio`, `liste`, `zone-texte`,
     `image-annotable`, `paragraphe`, `tableau`), libellé, nom de clé, valeurs
     possibles, largeur, groupement.
  2. En déduire le **jeu minimal de types** qui couvre 100 % de l'existant. Tout
     type ajouté « au cas où » est à refuser : il devra être maintenu chez tous
     les clients.
  3. Écrire la spécification du schéma : structure, champs obligatoires, valeurs
     par défaut, règles de validation, numéro de version du format.
  4. Décider des **clés stables** : la clé d'un champ sert de nom dans le
     brouillon `localStorage` et devra survivre aux évolutions du schéma.
- **Critères d'acceptation :**
  - Aucun élément du formulaire actuel n'est « non exprimable » dans le schéma.
  - La spécification tient en un document relu, avec un exemple complet par type.
  - Le format porte un numéro de version dès la première ligne.
- **Risque :** un vocabulaire trop riche transforme le moteur en langage de
  programmation. Le plafond du sur-mesure se pose ici, pas plus tard.

### C1-T2 — Extraire les couleurs en tokens uniques

> **État : livré le 14 octobre 2026, sous réserve du contrôle visuel.**
> Cinq tokens, 36 littéraux remplacés, lecture par `getComputedStyle` à
> chaque génération de PDF. 15 des 18 critères sont vérifiés, **dont les deux
> critères de changement de thème**, confirmés par Baptiste le 14 octobre :
> forcer `--fond` rend magenta le fond de l'écran et la marge du PDF, forcer
> `--texte` rend rouge le numéro de page. Les deux chemins — html2canvas pour
> le fond, `setTextColor` pour le texte — sont donc validés, ce qui lève le
> seul point susceptible de faire échouer la tâche. Reste à produire le jeu de
> référence visuelle de la V1 — quatre fichiers, à faire **avant** C1-T3, qui
> rend la V1 inobservable : `docs/references-visuelles/LISEZMOI.md`. La
> comparaison avant/après C1-T2 qu'annonçait ce document est sans objet depuis
> le contrôle de thème, et a été retirée le 15 octobre.

- **Effort :** S
- **Dépendances :** aucune (peut partir en premier, gain immédiat)
- **Périmètre :** `formulaire/style.css`, `formulaire/script.js`,
  `formulaire/index.html`
- **Travail :**
  1. La palette est aujourd'hui en dur **et dupliquée** : `#cec1a3` dans
     `style.css:2` et `style.css:14`, `#8C6D53` à huit endroits du CSS, les mêmes
     valeurs redéclarées dans `script.js:11-14` (`FOND`, `FOND_RGB`,
     `TEXTE_RGB`), et `#8C6D53` une neuvième fois en style inline dans
     `index.html:26`.
  2. Définir les tokens sur `:root` (`--fond`, `--accent`, `--texte`, …) et
     remplacer toutes les occurrences CSS.
  3. Supprimer le style inline du bouton d'export, qui passe dans une classe.
  4. Côté PDF, lire les tokens via `getComputedStyle(document.documentElement)`
     et convertir en RGB : `FOND_RGB` et `TEXTE_RGB` ne sont plus écrits à la
     main. Une seule source de vérité.
- **Critères d'acceptation :**
  - `grep -E '#(cec1a3|8C6D53|3B4133)' formulaire/` ne renvoie plus que la
    définition des tokens.
  - Changer un token change simultanément l'écran et la couleur de marge du PDF.
  - Un PDF généré avant et après la bascule est visuellement identique.
- **Risque :** un PDF sortant aux couleurs du cabinet précédent est le genre de
  défaut qui se voit chez le client et pas en test.

### C1-T3 — Moteur de rendu du schéma

> **État : étapes 1 à 8 livrées le 15 octobre 2026. La bascule est C1-T3b.**
> Le moteur (`formulaire/moteur/rendu.js`), son validateur et le schéma de
> production (`formulaire/schema.json`, 28 blocs) existent et sont comparés
> automatiquement au formulaire V1 : `tests/test_comparaison_dom.js` vérifie
> les 29 blocs avec leur chaîne d'ancêtres, les champs, les deux tableaux et
> les 4 images, sous neuf tolérances écrites et motivées.
> **`formulaire/index.html` n'a pas été touché** — la V1 sert toujours les
> consultations — et le moteur n'est atteignable que par la page provisoire
> `formulaire/index-moteur.html`, exclue du paquet livré au cabinet.
> Audit **CONFORME** après correction de onze constats ; revue **À LIVRER**
> (0 bloquant, 0 important). 7 des 10 critères vérifiés : les trois autres
> (jeu de référence, PDF superposable, retour arrière éprouvé) exigent un
> navigateur et relèvent de C1-T3b.
> Contrat : `docs/contrats/C1-T3.md` ; audit : `docs/audits/C1-T3.md` ;
> revue : `docs/revues/C1-T3.md` ; journal des mises en échec :
> `docs/audits/C1-T3-mises-en-echec.md`.

- **Effort :** L
- **Process :** Complet — point de non-retour du chantier C1.
- **Dépendances :** C1-T1, C1-T2
- **Périmètre :** `formulaire/moteur/rendu.js` (nouveau),
  `formulaire/index.html` réduit à une coquille
- **Travail :**
  1. Charger `schema.json` et `theme.json` au démarrage, appliquer le thème aux
     tokens CSS avant le premier rendu (pas de clignotement).
  2. Construire le DOM section par section. Les `id` produits doivent respecter
     la convention actuelle : `collecterBilan()`, `restaurerBilan()` et
     `calculerPages()` reposent dessus.
  3. Conserver les classes de mise en page existantes (`bloc`, `titre_section`)
     pour que `style.css` continue de s'appliquer sans réécriture.
  4. Rendre les images annotables comme aujourd'hui, en déléguant à
     `preparerZoneDessin()`.
  5. Valider le schéma au chargement : un schéma invalide affiche une erreur
     explicite et ne produit pas un formulaire à moitié rendu.
- **Critères d'acceptation :**
  - Le schéma reproduisant le formulaire actuel produit un DOM **équivalent** :
    comparaison automatisée des `id`, types et libellés avec l'ancien HTML.
  - Un PDF généré depuis le moteur est superposable à un PDF de la V1 (contrôle
    visuel documenté, captures conservées).
  - Un champ ajouté au schéma apparaît sans toucher une ligne de JavaScript.
  - Un schéma volontairement cassé produit un message d'erreur lisible.
- **Hérité de l'audit de C1-T1** (`docs/audits/C1-T1.md`, faibles résiduelles,
  à traiter dans cette tâche) :
  - La garde d'intégration continue « aucune coordonnée du cabinet recopiée »
    est ancrée sur les **numéros** de ligne 72-75 de `formulaire/index.html`.
    C1-T3 réduit ce fichier à une coquille : la garde deviendra silencieusement
    verte. La réancrer sur le **contenu** du bloc d'identité, pas sur sa
    position, et conserver la règle « en cas d'échec, ne nommer qu'un numéro de
    ligne, jamais le contenu ».
  - La dérivation des clés gelées de `tests/test_inventaire_formulaire.js` ne
    reconnaît `getElementById` qu'en guillemets doubles (17 occurrences sur 17
    aujourd'hui). Un `getElementById('…')` en apostrophes y échapperait.
  - Le chemin de refus de `lireAttribut()` recopie les attributs du tag dans le
    journal d'intégration continue, qui est public. Sans exposition réelle —
    D4 interdit le préremplissage — mais à resserrer dès que le moteur écrit
    des attributs.
  - **À trancher avant d'écrire le validateur de schéma** (relevé par l'audit,
    puis par la revue) : la règle 1 de la section 7 de
    `docs/schema-formulaire.md` refuse toute clé supplémentaire à la racine,
    alors que la règle d'évolution de sa section 5.1 admet qu'« un ajout
    purement facultatif ne change pas la version ». Les deux se contredisent
    dès qu'un attribut racine facultatif est ajouté.
- **Risque :** c'est la tâche la plus lourde du chantier et le point de
  non-retour. À ne pas démarrer avant que C1-T1 soit relu.

### C1-T3b — Basculer le formulaire de production sur le moteur

> **État : livrée le 19 octobre 2026, à un geste près.** Les trois critères
> humains ont été levés : jeu de référence produit, six pages **identiques au
> pixel près** après correction de cinq écarts de rendu, et repli éprouvé de
> bout en bout contre un vrai serveur en bac à sable — une saisie commencée sur
> le moteur se reprend sur la fiche de secours, PDF déposé compris. Reste à
> poser le favori « Formulaire — secours V1 » sur la tablette et à l'ouvrir une
> fois : ce geste demande l'appareil, le chemin qu'il emprunte est éprouvé.
> Constat : `docs/references-visuelles/CONSTAT-2026-10-19.md` ; outillage
> rejouable : `outils/reference-visuelle/`.
>
> **État antérieur, conservé pour mémoire : bascule faite dans le dépôt les
> 15-16 octobre 2026.**
> `formulaire/index.html` est une coquille de 118 lignes que le moteur remplit ;
> la V1 est conservée octet pour octet dans `formulaire/index-v1.html`, servie,
> qui est le repli de niveau 1 et le témoin des clés de brouillon dans les
> tests. Le paquet livré au cabinet contient désormais le moteur et le schéma —
> l'ancienne exclusion aurait livré un formulaire vide.
> Audit **CONFORME SOUS RÉSERVE** (0 critique, 0 élevée, 0 moyenne, 2 faibles)
> après correction de huit constats, dont un **élevé** : le message de repli se
> retirait sur la foi du rendu et non du démarrage, si bien qu'un `script.js`
> tronqué produisait un formulaire d'apparence normale qui n'écrivait aucun
> brouillon — une heure de saisie perdue sans un mot. Revue **À LIVRER**.
> **Trois critères sur douze restent à prononcer, et ils n'appartiennent qu'à
> Baptiste** : le jeu de référence visuelle (critère 1), l'essai réel du favori
> de secours sur la tablette (critère 2), la superposition des PDF (critère 11).
> **Rien ne doit partir au cabinet avant.**
> Contrat : `docs/contrats/C1-T3b.md` ; audit : `docs/audits/C1-T3b.md` ;
> revue : `docs/revues/C1-T3b.md`.

> **Ouverte le 15 octobre 2026.** C'est l'étape 9 du contrat de C1-T3,
> détachée parce que son préalable — le jeu de référence visuelle de la V1 —
> n'a pas pu être produit le jour même. **C'est le point de non-retour du
> chantier.**

- **Effort :** M
- **Dépendances :** C1-T3 étapes 1 à 8 (livrées), **et le jeu de référence
  visuelle de la V1** : `docs/references-visuelles/LISEZMOI.md`, quatre
  fichiers, à produire par Baptiste au navigateur **avant** de commencer. Après
  la bascule, le critère « PDF superposable » est définitivement invérifiable.
- **Périmètre :** `formulaire/index.html` réduit à la coquille,
  `formulaire/index-v1.html` (copie gelée du repli), `tests/test_coquille.py`,
  réancrage des groupes 1 et 6 de `tests/test_inventaire_formulaire.js` sur
  « coquille + schéma », suppression de `formulaire/index-moteur.html`.
- **Travail :** la section 6, étape 9 du contrat de C1-T3, qui reste la
  référence — y compris le favori « Formulaire — secours V1 » à poser sur la
  tablette **avant** la bascule, et l'essai réel du repli.
- **Critères d'acceptation :** les critères 1, 3 et 9 du contrat de C1-T3, non
  cochés à ce jour. Le 3 est un critère **humain**, attribué à Baptiste.
- **Hérité du réaudit de C1-T3** : les `id` de la coquille situés **hors** de
  `#form-bilan` (`btn-export`, `barre-brouillon`, `zone-messages`, les boutons
  de la barre d'outils — seize au total) ne sont protégés que par l'ordre du
  document, puisqu'ils précèdent tous `#form-bilan`. Une `cle` de schéma valant
  `btn-export` rendrait un jour le bouton d'export inerte. À inscrire comme
  contrainte, ou à ajouter à `IDS_RESERVES_COQUILLE`.
- **Reste du réaudit, faible et volontairement non traité ici** : le rappel de
  CI sur `docs/references-visuelles/` repose sur `git ls-files`, donc il ne
  parle qu'**après** le commit, alors que le risque du §4 du LISEZMOI — une
  capture d'écran montrant plus que le formulaire — est irréversible. C'est une
  fuite signalée, pas une fuite empêchée. Une vraie barrière suppose de décider
  si ces images entrent dans le dépôt ou restent hors suivi : à trancher en
  C1-T4, quand les fichiers existeront.
  **Tranché par C1-T4a (D4, 6 novembre 2026) :** les images et PDF de mesure ne
  sont **jamais** versionnés ; le pas de CI devient une erreur pour tout fichier
  autre que `.md` ou `.json` sous `docs/references-visuelles/`.
- **Risque :** une consultation cassée le lendemain matin. Le retour arrière de
  niveau 1 — un favori, aucune ligne de commande — est la seule parade qui
  compte, et il se vérifie avant la bascule, pas après.

### C1-T4 — Rendre le formulaire de production depuis un schéma

> **Scindée le 6 novembre 2026** (décision de Baptiste) : le favori de secours
> ne pourra pas être posé sur la tablette avant deux mois environ. La version
> du cabinet est archivée (`production-cabinet-01` sur `d43350a`, branche
> `maintenance-cabinet-01`, fiche `docs/production/cabinet-01.md`), et le
> développement continue sans elle :
> - **C1-T4a — Écrire le schéma du cabinet dans le dépôt.** Travail 1 :
>   `clients/cabinet-01/` complet, rendu par le moteur **identique au pixel**
>   à la V1 (outillage `outils/reference-visuelle/`), brouillon et PDF compris,
>   tests. **Aucune livraison.** Process Complet. Dépendances : C1-T3b.
>   **État : livrée le 6 novembre 2026** sur la branche `c1-t4a-schema-cabinet`
>   (contrat `docs/contrats/C1-T4a.md`, mises en échec
>   `docs/audits/C1-T4a-mises-en-echec.md`, audit `docs/audits/C1-T4a.md`
>   CONFORME après réaudit, revue `docs/revues/C1-T4a.md` À LIVRER après
>   corrections). `clients/cabinet-01/schema.json` est
>   le schéma du cabinet, gardé égal à son miroir `formulaire/schema.json` ;
>   `faire-paquet.sh <client>` le livre ; la fidélité est mesurée contre
>   `d43350a`, pas contre la seule fiche de secours.
> - **C1-T4b — Livrer au cabinet.** Travaux 2 et 3 et les deux critères
>   ci-dessous : favori posé et ouvert, une semaine de bilans réels, puis
>   suppression du HTML écrit à la main. Dépendances : C1-T4a et la visite au
>   cabinet. La version installée étant celle du 26 août, cette livraison
>   franchit tout l'écart jusqu'à `main` (voir la fiche de production).
>   **Constat de la mesure : `docs/references-visuelles/CONSTAT-2026-11-06-C1-T4a.md`**
>   — la liste de ce que la praticienne verra changer (E1 à E7, N1), la consigne
>   de retour arrière (écouler la file d'attente avant de revenir à `d43350a`),
>   et la méthode de comparaison après livraison (ensembles de variantes, pas un
>   export contre un export). **Aucune décision bloquante** n'en est née : chaque
>   écart a son document.
>   **À traiter dans C1-T4b, pour le retour arrière** (consigne F9 complétée par
>   la revue de C1-T4a) : sur une base IndexedDB passée en version 2, `d43350a`
>   échoue non seulement à relire la file (les bilans en attente ne partent
>   plus : **écouler la file avant de revenir**), mais aussi à **écrire** son
>   réglage — « Choisir le dossier… » affiche « Le dossier n'a pas pu être
>   enregistré » (`d43350a:formulaire/script.js:775-783, 797-806, 812-833`) :
>   la praticienne perd son dossier d'enregistrement sans pouvoir le rétablir
>   tant qu'elle reste sur `d43350a`. Que le dossier mémorisé se retrouve au
>   retour sur `main` n'est pas vérifié. **Ce qu'il faudrait faire (supprimer la
>   base de la tablette, ou la ramener en version 1 avec le magasin `reglages`
>   seul) est à évaluer ici, pas décidé.**
>   **G4 et l'étiquette mobile.** `tests/test_schema_client.js` lit désormais le
>   brouillon de production par le **SHA complet** `d43350a0cf20…` et non par
>   l'étiquette `production-cabinet-01`, que `docs/production/cabinet-01.md`
>   déplace à chaque installation. Une nouvelle version livrée s'**ajoute**
>   comme seconde référence de brouillon ; elle ne remplace pas celle-ci, et
>   **G4 ne doit pas être assoupli**.
>
> C1-T5 et C9-T2 ne dépendent plus que de C1-T4a. **Rien ne part au cabinet
> avant C1-T4b.** Le texte d'origine est conservé ci-dessous.

- **Effort :** M
- **Process :** Complet — touche le formulaire de production, celui d'une consultation du lendemain.
- **Dépendances :** C1-T3
- **Périmètre :** `clients/cabinet-01/schema.json`, suppression du HTML sur mesure
  (décision D8 de C2-T1 : la convention de nommage des clients ne porte jamais
  un nom de ville).
  **Amendement (D3 de C1-T4a, 6 novembre 2026) : pas de `theme.json`.** Aucun
  code ne le lirait (le moteur ne charge que `schema.json`, décision de Baptiste
  à C1-T3), et il recopierait les cinq tokens de `:root`, source unique de la
  palette depuis C1-T2 : une seconde source, le défaut que C1-T2 a fermé. Il
  naîtra avec son premier consommateur (thème d'un deuxième cabinet, ou C2-T2
  pour le logo).
- **Travail :**
  1. Écrire le schéma du cabinet actuel, en totalité.
  2. Basculer la production dessus et faire valider un bilan réel par la
     praticienne avant de supprimer l'ancien HTML.
  3. Conserver l'ancien `index.html` en `docs/historique/` le temps d'une
     campagne de bilans, pas davantage.
- **Critères d'acceptation :**
  - La praticienne réalise une semaine de bilans sans régression signalée.
  - Le dépôt ne contient plus de HTML de formulaire écrit à la main.
- **Risque :** régression chez l'unique utilisatrice en production. Prévoir le
  retour arrière (remettre l'ancien `index.html`) comme un geste d'une minute.

### C1-T5 — Bibliothèque de blocs et templates de départ

> **État : implémentée le 6 novembre 2026** sur la branche `c1-t5-blocs`
> (contrat `docs/contrats/C1-T5.md`), **pas encore livrée** : le critère A13,
> la mesure chronométrée par l'opérateur d'atelier (Baptiste), reste à faire
> (protocole : `docs/essais/C1-T5-client-fictif.md`). Neuf fragments `blocs/*.json`
> tranchés dans le schéma du pilote, deux templates (`podologue-complet`, qui
> redonne `clients/cabinet-01/schema.json` à l'octet, et `podologue-court`),
> `outils/composer-schema.js` (Node nu), suite `tests/test_blocs.js`, garde
> « ni `blocs/` ni `templates/` dans le paquet ». Rien ne part au cabinet.

- **Effort :** M
- **Process :** Allégé — bibliothèque de départ, rien en production.
- **Dépendances :** C1-T4a (le schéma du cabinet dans le dépôt ; la livraison
  C1-T4b n'est pas requise)
- **Périmètre :** `blocs/` (fragments de schéma réutilisables),
  `templates/podologue-complet.json`, `templates/podologue-court.json`
- **Travail :** extraire de C1-T4 les blocs réutilisables (anamnèse, examen
  clinique, empreintes, orthèses, conclusion) et composer deux ou trois
  templates de départ. Un nouveau client part d'un template, pas d'une page
  blanche.
- **Critères d'acceptation :** fabriquer le schéma d'un client fictif à partir
  d'un template prend moins d'une heure, mesuré.
- **Risque :** sans ce plafond, chaque vente devient un projet et le temps
  disponible devient le facteur limitant du chiffre d'affaires.

---

### C1-T6 — Type `grille` : cases et mesures en tableau

> **État : livrée le 4 novembre 2026** sur la branche `c1-t6-grille`, après
> audit (`docs/audits/C1-T6.md`, CONFORME SOUS RÉSERVE, réserve R1 levée) et
> revue (`docs/revues/C1-T6.md`, À LIVRER). Contrat `docs/contrats/C1-T6.md`,
> 24 critères vérifiés. Format de schéma en version 2, huitième type `grille`
> (`case` et `texte-court` ; cellules à trois états écartées par décision du
> 4 novembre). **Élargie par l'amendement A1** : `script.js` réduit à l'export
> une grille trop large, et refuse au-delà de `LARGEUR_GRILLE_REFERENCE_PX`
> (1 192 px) ; la fiche de secours reste identique au pixel. Effort réel L + M.
> **Aucune grille dans un schéma client** avant les trois conditions de
> `docs/schema-formulaire.md` (« Livrer une grille dans un schéma client »),
> dont un export d'essai **sur la tablette du client**. Rien ne part au
> cabinet : le schéma pilote reste en version 1. Suites reportées : C1-T6b.

- **Effort :** M
- **Process :** Complet — révise le format de schéma (`version_schema` 2) et
  le moteur partagé par tous les cabinets.
- **Dépendances :** C1-T3b ; ne touche pas au schéma du cabinet pilote.
- **Périmètre :** `docs/schema-formulaire.md`, `formulaire/moteur/rendu.js`,
  `formulaire/script.js` (brouillon, PDF), `tests/`
- **Pourquoi :** le type `tableau` n'admet qu'**un seul choix par ligne**. Or
  la fiche du premier prospect hors pilote est faite surtout de grilles :
  - tests posturaux sur dur et mousse, en G et en D, avec plusieurs cases
    cochées par ligne ;
  - Maddox, Maddox perceptif, MCP 2 et 3, avec des valeurs à saisir ;
  - en-têtes de colonnes groupés et cellules neutralisées.

  Ce qu'il faut savoir rendre est maquetté dans une fiche de démonstration
  écrite hors moteur, non versionnée : elle reprend la fiche du prospect.
- **Travail :**
  1. Un huitième type `grille`. Ses cellules sont de nature fermée : `case` ou
     `texte-court`. Il porte des groupes d'en-têtes et des cellules
     neutralisées.
  2. La clé de brouillon de chaque cellule est stable et dérivée de la ligne et
     de la colonne.
  3. Le format passe en version 2 du schéma, et le moteur rend toujours la
     version 1 à l'identique.
- **Critères d'acceptation :**
  - Le schéma du cabinet pilote se rend au pixel près comme avant (outillage
    `outils/reference-visuelle/`).
  - Une grille saisie se restaure depuis le brouillon et s'imprime dans le PDF.
  - Chaque garde est mise en échec par une mutation, aussi sous `-O`.

### C1-T6b — Fiabiliser l'outillage et les gardes de la grille

> **État : livrée le 5 novembre 2026** sur la branche `c1-t6b-outillage`
> (tirée de `c1-t6-grille`), après audit (`docs/audits/C1-T6b.md`, CONFORME
> au réaudit) et revue (`docs/revues/C1-T6b.md`, À LIVRER). Contrat
> `docs/contrats/C1-T6b.md`, critères 1 à 27 et 21b vérifiés (DB1 et DB2 :
> voie A). Effort réel M, process monté à Allégé + audit.
> - `cdp.js` refuse tout port qui ne refuse pas la connexion.
> - La CI clone l'historique complet, et un commit de repère absent y échoue.
> - La garde de confidentialité lit les messages de commit, les noms de
>   référence, les `src`/`href` de la fiche et **tous les blobs introduits
>   dans la plage**, avec deux exemptions ancrées sur (SHA, ligne).
> - Largeur seuil de la donnée fictive : 735 px ; la hauteur se vérifie en
>   atelier, à la largeur de la tablette du client.
>
> **Restent hors garde** : les messages d'étiquettes annotées, et une image
> de la fiche commitée en binaire. Les deux exemptions visent des SHA de
> `c1-t6-grille` : une fusion qui réécrit l'historique les rendra sans objet.

- **Effort :** S
- **Process :** Allégé — outillage et CI, rien qui parte au cabinet.
- **Dépendances :** C1-T6. À faire **avant le premier schéma client à grille**.
- **Périmètre :** `outils/reference-visuelle/cdp.js`, `.github/workflows/tests.yml`,
  `tests/test_confidentialite_prospect.py`, `docs/schema-formulaire.md`
- **Pourquoi :** constats laissés ouverts par l'audit et la revue de C1-T6,
  hors de son périmètre.
- **Travail :**
  1. `cdp.js` réutilise sans le dire un Chrome déjà en écoute sur son port, à
     une taille de fenêtre inconnue (constat R2 de l'audit : six pages au lieu
     de trois pour le bilan témoin). Refuser un Chrome qu'il n'a pas lancé, ou
     le signaler et imposer la largeur.
  2. Un cas de `tests/test_export_grille.js` (options de capture identiques à
     `1ec796c`) est sauté en CI, faute d'historique : `fetch-depth: 0` ou un
     autre moyen de le jouer partout (remarque 4 de la revue).
  3. Les messages de commit et les noms de branche ne passent sous aucune garde
     de confidentialité (constat faible de l'audit) ; les valeurs `src` et
     `href` de la fiche non plus.
  4. Sous environ 680 px de fenêtre, une grille haute et trop étroite pour être
     réduite peut être coupée entre deux pages au milieu d'une ligne (réaudit) :
     mesurer, puis borner ou documenter.
- **Critères d'acceptation :** chaque point est fermé par une garde mise en
  échec par une mutation, ou consigné comme accepté avec sa raison.

## C2 — Identité du cabinet en configuration

**Pourquoi.** Le nom, l'adresse, le courriel et le téléphone de la praticienne
sont écrits dans `formulaire/index.html:65-68`, et le logo est un fichier au nom
fixe. Tant qu'il en est ainsi, installer un deuxième cabinet veut dire éditer du
HTML.

### C2-T1 — Bloc `cabinet` dans `config.json` et route `GET /cabinet`

> **État : livrée le 3 novembre 2026**, après revue (`docs/revues/C2-T1.md`)
> et constat de rendu réel. Contrat `docs/contrats/C2-T1.md`. L'identité du cabinet
> (praticienne, adresse, courriel, téléphone) ne vit plus dans le dépôt : elle
> est saisie par `--config`, servie par la route authentifiée `GET /cabinet`,
> et lue par le formulaire au chargement. Les deux en-têtes de production sont
> vides ; l'export est refusé, pas dégradé, quand l'identité manque (D7). Le
> critère ci-dessous, qui écrivait les motifs qu'il cherchait en clair, est
> remplacé par un renvoi à `tests/test_identite_absente.py` : la feuille de
> route ne doit pas elle-même porter la donnée qu'une tâche retire ailleurs.

- **Effort :** L (requalifiée par son contrat ; annoncée M)
- **Process :** Complet — nouvelle route serveur.
- **Dépendances :** C1-T2 souhaitable
- **Périmètre :** `serveur/serveur.py`, `formulaire/script.js`, `tests/test_serveur.py`
- **Travail :**
  1. Ajouter à `CONFIG_DEFAUT` un bloc `cabinet` : `nom`, `praticien`,
     `adresse`, `courriel`, `telephone`, `logo`, `convention_nommage`.
  2. Exposer `GET /cabinet` — **authentifiée**, contrairement à `/sante` : ce
     sont des coordonnées professionnelles, mais rien n'oblige à les offrir à
     qui scanne le port. Réponse JSON, `Cache-Control: no-store`.
  3. Étendre `--config` pour saisir ces champs, avec les valeurs actuelles en
     valeurs par défaut.
  4. Côté formulaire, remplir l'en-tête depuis la réponse ; en cas d'échec,
     afficher l'en-tête vide plutôt qu'un gabarit avec les coordonnées d'un
     autre cabinet — un faux en-tête sur un document de santé est pire qu'un
     en-tête absent.
  5. **Deux en-têtes à purger, pas un** (relevé par la revue de C1-T3) :
     `formulaire/index.html` et `formulaire/index-moteur.html` portent chacun
     l'identité en dur. Le second est la page du moteur, provisoire jusqu'à la
     bascule de C1-T3b ; si elle a disparu d'ici là, il n'y en aura qu'un. Le
     critère par `grep` couvre les deux de toute façon.
- **Critères d'acceptation :**
  - `python3 -m unittest tests.test_identite_absente` passe, et passe aussi
    sous `python3 -O` ; les quatre mutations de mise en échec le font rougir
    (contrat C2-T1, étape 9). Remplace l'ancien critère, qui écrivait en clair
    les quatre coordonnées qu'il cherchait — la feuille de route ne doit pas
    être elle-même le document qui les recopie.
  - `GET /cabinet` sans identifiants renvoie 401.
  - Serveur injoignable : l'en-tête reste vide, le formulaire reste utilisable,
    et l'export PDF est refusé avec un message explicite.
  - Le nom de fichier produit par `construireNomFichier()` suit la convention
    déclarée en configuration.
- **Risque :** un bilan PDF portant l'en-tête d'un autre cabinet est un incident
  à déclarer, pas un bug.

### C2-T2 — Logo et actifs propres au client

- **Effort :** S
- **Process :** Allégé + audit — sert un fichier depuis un chemin configuré : la remontée de répertoire est le seul vrai risque, et l'audit ne regarde qu'elle.
- **Dépendances :** C2-T1
- **Périmètre :** `formulaire/images/`, `serveur/serveur.py`
- **Travail :** servir le logo depuis un chemin déclaré en configuration, en
  respectant le filtre `EXTENSIONS_SERVIES` et sans élargir la racine web.
  Vérifier que le chemin ne permet aucune remontée hors de `formulaire/`.
- **Critères d'acceptation :** un logo déclaré hors de la racine web n'est pas
  servi et l'anomalie est journalisée ; un test couvre la tentative de remontée.

---

## C3 — Adressage, certificat et installateur

**Pourquoi.** C'est le verrou n°1, celui qui « tue le projet en silence ». Un
praticien à qui l'on demande d'installer un certificat racine dans les réglages
Android abandonne, ou le fait mal et appelle au support chaque semaine. À
40 €/mois, un appel de trente minutes consomme la marge du mois.

### C3-T1 — Décider la stratégie de nom et de certificat

> **État : livrée le 19 octobre 2026.** Voie retenue : **n°2 — IP privée fixe +
> autorité locale**, soit l'existant, conservé délibérément. Coût récurrent
> **0 €/cabinet/an** ; gestes à la charge du praticien **aucun**, en usage comme
> à l'installation. Décision écrite : `docs/adressage.md`.
>
> **Le point « qui peut tout invalider » a tranché, et contre la voie n°1 :** un
> nom public résolvant vers une adresse privée n'est pas fiable en France — les
> résolveurs IPv4 de Free le refusent, leurs IPv6 l'acceptent, donc la panne est
> intermittente. S'y ajoutent deux défauts non prévus : la voie n°1 rendait un
> usage purement local dépendant d'Internet (box en panne, plus de formulaire à
> deux mètres du PC), et publiait la liste des cabinets clients dans les journaux
> de *Certificate Transparency*. Enfin, les certificats publics passent à
> 100 jours en mars 2027 et **47 jours en mars 2029** (SC-081v3) ; une autorité
> locale installée à la main en est explicitement exemptée.
>
> **Conséquences, détaillées au §5 du document :** C3-T2 change de nature (voir
> sa note), C3-T3 garde son périmètre avec l'IP fixe et la racine comme vrais
> livrables, C3-T4 doit vérifier le **bail** DHCP et non l'adresse du jour, et
> **C4-T3 + C4-T5 deviennent moins optionnelles** — elles sont ce qui rend le
> seul coût récurrent de la voie n°2 (le remplacement de la box par l'opérateur,
> ~0,2 incident/cabinet/an) traitable à distance au lieu d'un déplacement.
> Une réserve documentée (§7) garde la voie n°1 pour un client dont les appareils
> n'admettent pas l'installation d'une autorité, avec l'essai qui tranche.

- **Effort :** M (étude), décision bloquante
- **Process :** Direct — étude et décision, aucune ligne de code.
- **Dépendances :** aucune
- **Périmètre :** `docs/adressage.md`
- **Travail :** comparer, pour chaque voie, la fiabilité constatée sur Chrome
  Android, le coût récurrent et ce qu'elle exige du praticien :
  1. **Sous-domaine réel + Let's Encrypt par challenge DNS-01**, résolvant vers
     l'IP privée. La tablette fait confiance nativement : zéro manipulation.
     Suppose un domaine, un compte DNS automatisable, et un renouvellement qui
     tourne tout seul sur le PC du cabinet.
  2. **IP statique + autorité locale** : l'existant. Fonctionne, mais impose
     l'installation du certificat racine.
  3. **mDNS `.local`** — déjà écartée faute de garantie de résolution par Chrome
     sous Android. À ne pas réinstruire sans élément nouveau.
  - Vérifier le comportement d'un sous-domaine résolvant vers une IP privée
    (rebinding DNS) sur les navigateurs visés, c'est le point qui peut tout
    invalider.
- **Critères d'acceptation :** une voie retenue, écrite, avec le coût annuel par
  cabinet et la liste des gestes restant à la charge du praticien (idéalement
  vide).
- **Risque :** se tromper ici fait refaire l'installateur entier.

### C3-T2 — Renouvellement automatique du certificat

> **Reconfigurée par C3-T1 le 19 octobre 2026.** Le travail décrit ci-dessous
> suppose un client ACME DNS-01 ; la voie n°1 n'ayant pas été retenue, il n'y a
> **ni challenge, ni compte DNS, ni secret d'API** : le certificat serveur se
> réémet **hors ligne** depuis l'autorité locale, déjà présente sur le PC avec sa
> clé. Le point 4 du travail devient sans objet, et l'effort tombe de L à M.
> **Second déclencheur à ajouter, et c'est le vrai sujet : le changement
> d'adresse IP du PC**, pas seulement l'approche de l'expiration. Les trois
> critères d'acceptation restent entiers. À reprendre tel quel dans le contrat.

- **Effort :** L
- **Process :** Complet — renouvellement de certificat, en plein chemin TLS.
- **Dépendances :** C3-T1 (livrée : voie locale, voir l'encadré). Lire
  `/etat` (C4-T3) : son verdict de concordance d'adresse est le déclencheur à
  surveiller, et C3-T2 y ajoutera son propre champ. Rejouer alors le test de
  résistance du lecteur de certificat.
- **Périmètre :** `serveur/certificat.py` (nouveau), tâche planifiée
- **Travail :**
  1. Client ACME DNS-01, ou appel d'un client existant, sans ajouter de
     dépendance au serveur lui-même.
  2. Renouvellement à J-30, rechargement du contexte TLS **sans coupure** ou,
     à défaut, redémarrage hors heures d'ouverture.
  3. Alerte à J-14 si le renouvellement a échoué, visible sur la page de
     diagnostic (C4-T3).
  4. Garder le secret de l'API DNS hors de la racine web et hors du dépôt.
- **Critères d'acceptation :**
  - Un certificat à 7 jours de l'expiration est renouvelé sans intervention.
  - L'échec de renouvellement est visible à distance avant l'expiration.
  - Le serveur ne démarre jamais sans certificat valide (comportement actuel
    préservé).
- **Risque :** un certificat expiré, c'est tout un cabinet à l'arrêt un matin.

### C3-T3 — Installateur en un geste

> **Deux exigences ajoutées le 3 novembre 2026 par l'audit et la revue de
> C3-T3a :**
> 1. **Droits de ce que SYSTEM exécute.** La tâche planifiée exécute sous
>    SYSTEM le dossier `serveur\` et un `pythonw.exe`. Or, par défaut, un
>    dossier créé sous `C:\` hérite du droit « Modifier » des utilisateurs
>    authentifiés, et un Python installé « pour l'utilisateur seul » vit dans
>    son profil. Un compte standard peut donc obtenir les droits SYSTEM.
>    L'installateur doit installer Python pour tous les utilisateurs (ou
>    embarquer le sien sous `C:\Program Files`), poser des droits restreints
>    sur le dossier de l'application, et le vérifier avant de se déclarer
>    installé. Relevé initial : fiche `docs/essais/C3-T3a-windows.md`,
>    étape (b bis).
> 2. **Ne plus conseiller « clic droit > Exécuter avec PowerShell »** si
>    l'essai confirme que la fenêtre se referme sans laisser lire le message.
>    Ce verbe n'élève pas non plus.

- **Effort :** L
- **Process :** Complet — écrit sur le poste d'un client ; le retour arrière y coûte un déplacement.
- **Dépendances :** C3-T1, C3-T2, C2-T1
- **Périmètre :** `outils/installateur/`, `installer-demarrage.ps1` absorbé
- **Travail :**
  1. Un exécutable unique pour Windows qui : vérifie Python ou embarque son
     interpréteur, écrit `config.json` à partir d'un questionnaire, obtient le
     certificat, enregistre la tâche planifiée `BilanPosturo`, ouvre le port du
     pare-feu, fixe l'IP statique si nécessaire, puis affiche l'adresse à saisir
     sur la tablette et un QR code vers celle-ci.
  2. Vérifications avant de se déclarer installé : port libre, `dossier_pdf`
     accessible **depuis le compte SYSTEM** (un lecteur réseau monté dans la
     session du praticien n'existe pas pour SYSTEM), `/sante` qui répond.
  3. Désinstallation symétrique, qui ne supprime jamais `bilans/`.
  4. Journal d'installation déposé à côté de l'exécutable, à joindre au support.
- **Critères d'acceptation :**
  - Sur une machine Windows neuve, l'installation aboutit en moins de 20 minutes
    sans ligne de commande ni manipulation de certificat.
  - Interrompre l'installateur en cours de route laisse une machine propre.
  - La tablette atteint le formulaire sans avertissement de sécurité.
- **Risque :** les scripts PowerShell actuels n'ont jamais tourné ailleurs qu'au
  cabinet ; seule leur syntaxe est vérifiée en intégration continue. Prévoir une
  VM Windows propre pour les essais, pas la machine de développement.

### C3-T3a — Corriger le calcul de racine des scripts d'installation

> **État : livrée au dépôt le 3 novembre 2026, pas encore au prospect.**
> - **Correctif :** la racine est le dossier du script, sans recherche
>   ascendante.
> - **Nouveau mode `-Verifier` :** il contrôle tout puis s'arrête avant la
>   tâche planifiée et le pare-feu.
> - **Tests et CI :** le test statique fabrique le vrai paquet. En CI, sous
>   Windows, le script est réellement exécuté : vert (run 41731923283), et
>   rouge sur la mutation (run 41730347550).
> - **Contrôles :** audit `docs/audits/C3-T3a.md`, revue
>   `docs/revues/C3-T3a.md`.
>
> **Restent à faire par Baptiste :** l'essai sur une VM Windows propre (8.9)
> et la vérification au cabinet pilote (8.10), sur
> `docs/essais/C3-T3a-windows.md`. **Le paquet ne part pas à Bordeaux avant
> 8.9.**

- **Effort :** S
- **Process :** Complet — script exécuté sur le poste d'un client.
- **Dépendances :** C6-T4 (renormalisation des `.ps1`, faite)
- **Périmètre :** `installer-demarrage.ps1`, `desinstaller-demarrage.ps1`,
  `tests/`
- **Problème, relevé à la lecture le 3 novembre 2026, à confirmer sous
  Windows :** `installer-demarrage.ps1` calcule
  `$racine = Split-Path -Parent $PSScriptRoot`, soit le dossier **parent** de
  celui du script. Or `outils/faire-paquet.sh` livre le script à la racine du
  paquet : sur une installation neuve, il chercherait `serveur\serveur.py` un
  niveau trop haut et s'arrêterait sur « introuvable ». Les scripts n'ont
  jamais tourné ailleurs qu'au cabinet pilote.
- **Critères d'acceptation :** un test lit les deux scripts et vérifie que la
  racine calculée est le dossier qui contient `serveur/`, tel que le paquet le
  livre ; essai réel sur une VM Windows propre, consigné.
- **Risque :** bloque toute installation à distance — c'est le premier geste
  du prospect de Bordeaux.

### C3-T4 — Procédure de recette d'installation

- **Effort :** S
- **Process :** Direct — procédure écrite et liste de contrôle.
- **Dépendances :** C3-T3
- **Périmètre :** `docs/recette-installation.md`
- **Travail :** liste de contrôle à dérouler chez le client : bilan de bout en
  bout, bilan serveur arrêté puis relancé (file d'attente), redémarrage du PC,
  vérification de la page de diagnostic depuis le réseau privé.
- **Critères d'acceptation :** la liste est signée par l'installateur et
  archivée par client.

---

## C4 — Observabilité et support à distance

**Pourquoi.** Le 23 septembre 2026, la tablette affiche `ERR_CONNECTION_REFUSED`
pendant un bilan ; le diagnostic se fait par téléphone, à l'aveugle. Les trois
causes racines ont été corrigées, mais rien ne permet encore de **voir** l'état
d'une installation à distance. L'éditeur est à Lille, le cabinet en Bretagne.

### C4-T1 — Journal technique non identifiant

> **État : livrée le 20 octobre 2026.** `technique.log` à la racine du cabinet,
> huit événements à vocabulaire fermé, rotation **partagée** avec le journal
> nominatif (5 Mo × 3), interrupteur `journal_technique` pour le retour arrière
> de niveau 1. **99 tests Python** (81 avant) **+ 35 Node**, verts en mode normal
> **et sous `python3 -O`**. Audit **CONFORME** (0 critique, 0 élevée, 0 moyenne)
> après correction d'une **élevée** ; revue **À LIVRER SOUS RÉSERVE**, les deux
> réserves traitées. Contrat : `docs/contrats/C4-T1.md` ; audit :
> `docs/audits/C4-T1.md` (v1 et v2) ; revue : `docs/revues/C4-T1.md`.
>
> **La tension avec `docs/adressage.md` est tranchée (décisions D1 et D2) :**
> aucune adresse dans `technique.log`, pas même celle du serveur — une exception
> exprimable est une exception contournable, et au cabinet les deux adresses ne
> diffèrent que du dernier octet. Le changement d'adresse reste reconstituable
> par l'**empreinte tronquée du certificat** chargé, qui porte l'IP en
> `subjectAltName`, comparée au démarrage précédent déjà inscrit dans le
> fichier. L'adresse courante relève exclusivement de C4-T3.
>
> **Le motif « garde-fou qui ne garde rien » a été rencontré quatre fois sur
> cette seule tâche**, et c'est l'enseignement à retenir : le premier test
> anti-fuite ne mordait pas sur `str(erreur)` (l'échec d'écriture survenait au
> `mkstemp`, dont le chemin ne porte pas le nom du patient) ; rien n'ancrait
> l'émission des lignes `REPONSE`, par lesquelles la détection passe ; la garde
> finale reposait sur des `assert` nus et **s'évaporait sous `python -O`** ; et
> la liste des noms à vérifier, alimentée à la main, manquait déjà un dépôt
> présent dans le dépôt. Les quatre sont refermés, le dernier en **dérivant les
> noms du contenu réel de `bilans/`** au lieu de les énumérer.
>
> **Reports, tous faibles et hors périmètre :** le doublement des lignes
> `REPONSE` (voir C4-T2) ; le test anti-fuite qui ne cherche pas les fragments
> de trois caractères ; `test_journal_illisible_ne_leve_pas` sans effet si
> l'utilisateur est privilégié ; la ligne `ARRET` presque jamais écrite au
> cabinet (voir C4-T3 et C4-T4) ; le flake de `ServeurArret` (voir C7-T5).

- **Effort :** M
- **Process :** Complet — journal : le risque est d'y laisser passer une donnée de santé.
- **Dépendances :** aucune
- **Périmètre :** `serveur/serveur.py` (autour de `journaliser()`, lignes
  209-288), `tests/test_serveur.py`
- **Travail :**
  1. Deuxième journal, `technique.log`, tenu en parallèle du journal nominatif :
     démarrages, arrêts, échecs TLS, échecs d'écriture, codes de réponse, heure
     du dernier dépôt réussi, taille des dépôts.
  2. **Ni nom de fichier, ni adresse IP, ni nom de patient.** Un dépôt s'y écrit
     `DEPOT ok 1066959 octets`.
  3. Même rotation que l'existant (5 Mo, 3 générations).
  4. Un test qui échoue si une ligne du journal technique contient une adresse IP
     ou un fragment de nom de fichier déposé — c'est la garantie qui tient lieu
     de preuve en audit, elle doit être automatisée et pas seulement promise.
- **Critères d'acceptation :**
  - Après un scénario complet (démarrage, dépôt, mauvais mot de passe, échec
    TLS, arrêt), `technique.log` permet de reconstituer l'incident et ne contient
    aucune donnée identifiante.
  - Le test anti-fuite échoue si l'on réintroduit volontairement un nom de
    fichier dans une ligne.
- **Risque :** une seule ligne identifiante dans un journal qui circule rouvre la
  question de l'exemption HDS.

### C4-T2 — Durée de conservation des journaux

> **État : livrée le 4 novembre 2026** (contrat court `docs/contrats/C4-T2.md`,
> amendé ; audit `docs/audits/C4-T2.md`, conforme après suites).
> - **La promesse :** aucune ligne de `journal.log` ni de `technique.log`
>   n'est conservée plus de six mois, serveur en marche.
> - **Ce qui la tient :**
>   - une rotation mensuelle, en plus de celle par taille ;
>   - une purge des archives par horodatage de première ligne (seuil :
>     N×30 j − 1 j), faite au démarrage, à chaque rotation, à l'écriture au
>     plus une fois par jour, et par un fil toutes les 6 h ;
>   - une rotation « tout ou rien » : un journal ouvert par un autre
>     programme ne fait plus disparaître d'archives.
> - **Mesure :** sur une simulation de 900 jours, l'âge maximal d'une ligne
>   est de 179 j 6 h à tout instant, quel que soit le rythme d'écriture.
> - **Réglage :** clé `conservation_journaux_mois` (1 à 120, défaut 6).
> - **À annoncer au cabinet pilote avant la mise à jour :** l'historique
>   antérieur forme une seule archive, supprimée en bloc vers février 2027.
> - **Pour C0-T2 :** reprendre « six mois de 30 jours, moins un jour, serveur
>   en marche », et la limite de la barrière au rang 1.

> **À chiffrer avant de dimensionner la purge, relevé par l'audit de C4-T1 le
> 20 octobre :** chaque réponse d'erreur produit **deux** lignes `REPONSE` dans
> `technique.log`, dont une à `code=0` issue de `log_error`. Le volume réel n'est
> donc pas celui qu'on déduirait du nombre de requêtes. Par ailleurs
> `technique.log` est aujourd'hui borné en **taille** (5 Mo × 3) et **pas en
> durée** : c'est exactement le trou que cette tâche ferme, et la documentation
> praticien le dit déjà en ces termes — ne pas la laisser mentir après coup.

- **Effort :** S
- **Process :** Allégé + audit — la purge supprime des fichiers ; vérifier qu'elle ne sort pas du dossier d'archives.
- **Dépendances :** C0-T2, C4-T1
- **Périmètre :** `serveur/serveur.py`, configuration
- **Travail :** la rotation borne la taille, pas la durée. Ajouter une purge par
  ancienneté, en mois, paramétrée et alignée sur le chiffre du contrat.
- **Critères d'acceptation :** une archive plus ancienne que la durée configurée
  est supprimée au démarrage et à chaque rotation ; un test vérifie la bascule
  par horodatage.

### C4-T3 — Page de diagnostic authentifiée `GET /etat`

> **État : livrée le 6 novembre 2026** sur la branche `c4-t3-etat`, après audit
> (`docs/audits/C4-T3.md`, CONFORME, aucun constat) et revue
> (`docs/revues/C4-T3.md`, À LIVRER). Contrat `docs/contrats/C4-T3.md`,
> 16 critères vérifiés.
> - **Contradiction tranchée par Baptiste (voie A) :** aucune adresse IP sur la
>   page, un verdict à la place (`conforme`, `adresse changée`, `indéterminé`),
>   obtenu par un `bind` sur chaque adresse du certificat. La page doit pouvoir
>   circuler comme `technique.log`, puisque le support passe par le praticien.
> - **Liste fermée de neuf clés** (la liste ci-dessous n'en comptait que sept) :
>   « état du renouvellement », sans objet tant que C3-T2 n'existe pas, est
>   remplacé par la concordance d'adresse ; ajout de l'empreinte du certificat
>   et de l'identité du cabinet renseignée ou non.
> - Lecteur DER en bibliothèque standard, éprouvé sur 600 000 entrées
>   corrompues ; interrupteur `page_etat` pour le retour arrière ; une garde
>   prouve désormais que `/sante` est la seule route non authentifiée.
>
> **Le texte d'origine est conservé ci-dessous.**
>
> **Contradiction à trancher dans son contrat, relevée le 19 octobre 2026 par
> le cadrage de C4-T1.** Le point 3 du travail ci-dessous interdit à `/etat`
> toute adresse IP, tandis que `docs/adressage.md:263-264` attend qu'il
> « affiche l'adresse courante » — c'est ce qui rend un changement d'adresse
> diagnosticable à distance, et donc traitable sans déplacement. Les deux ne
> peuvent pas tenir ensemble. La distinction qui résout probablement le conflit
> est celle retenue par C4-T1 : l'adresse d'un **client** est identifiante,
> l'adresse d'écoute du **serveur** ne l'est pas. Mais `/etat` est une route,
> pas un fichier : elle est authentifiée et ne circule pas, contrairement à
> `technique.log`, qui lui n'en porte aucune (décision D1 de
> `docs/contrats/C4-T1.md`). À arbitrer explicitement, pas par omission.

- **Effort :** M
- **Process :** Complet — nouvelle route authentifiée qui expose l'état du serveur.
- **Dépendances :** C4-T1
- **Périmètre :** `serveur/serveur.py`, `tests/test_serveur.py`
- **Travail :**
  1. Route **authentifiée** (ne pas la greffer sur l'exception de `/sante`)
     affichant : version du logiciel, date de démarrage, dernières lignes du
     journal technique, heure du dernier dépôt réussi, espace disque restant sur
     `dossier_pdf`, date d'expiration du certificat, état du renouvellement.
  2. Rendu lisible dans un navigateur et exploitable en JSON (`Accept`).
  3. Aucune donnée de santé, aucun nom de fichier, aucune adresse IP.
- **Critères d'acceptation :**
  - Sans identifiants : 401, et rien de la page ne fuit dans le corps de la
    réponse.
  - Avec identifiants : les neuf informations ci-dessus sont présentes.
  - Un test vérifie l'absence de données identifiantes dans la réponse.

### C4-T4 — Numéro de version affiché

> **État : livrée le 3 novembre 2026** (contrat court `docs/contrats/C4-T4.md`).
> La source unique est `formulaire/version.json` (1.1.0). Elle est lue :
> - par le serveur au démarrage (console et `DEMARRAGE version=…` dans
>   `technique.log`) ;
> - par le formulaire, pour un pied de page hors de `#form-bilan`, donc hors
>   du PDF.
>
> `tests/test_version.py` échoue si `package.json` diverge. Sept mutations sont
> toutes rouges, aussi sous `-O`. **Fait par C4-T3 :** `/etat` affiche la
> même valeur, lue par un seul appel à `lire_version()` au démarrage.

- **Effort :** S
- **Process :** Allégé — une constante propagée, couverte par un test de divergence.
- **Dépendances :** aucune
- **Périmètre :** `serveur/serveur.py`, `formulaire/`, `package.json`
- **Travail :** une constante de version, unique, lue par le serveur, le
  formulaire (pied de page discret) et la page de diagnostic. Sans elle, une
  question de support commence par « quelle version avez-vous ? » à laquelle
  personne ne sait répondre.
- **Critères d'acceptation :** la version apparaît au même endroit dans
  `/etat`, dans le pied de page et dans `technique.log` au démarrage ; un test
  échoue si les sources divergent.

### C4-T5 — Réseau privé Tailscale et ACL

> **Sortie de la V2 le 3 novembre 2026** (décision métier n°1). L'argument de
> vente « aucun lien permanent avec Internet » l'emporte sur le confort du
> support. Le diagnostic à distance passe par `technique.log` (C4-T1), envoyé
> par le praticien, et par `/etat` (C4-T3) consulté pendant une séance
> d'assistance qu'il ouvre lui-même. À rouvrir seulement sur demande
> explicite d'un client, en option.

- **Effort :** M (dont exploitation)
- **Process :** Complet — ouvre un accès distant ; le périmètre des ACL est tout le sujet.
- **Dépendances :** C4-T3, C0-T2
- **Périmètre :** `docs/support-distance.md`, configuration des postes
- **Travail :**
  1. Installer Tailscale sur le poste de l'éditeur et sur le PC du cabinet.
  2. **ACL restreintes au seul port du serveur.** Sans règle, le compte de
     l'éditeur accède à toute la machine, `bilans/` compris. Avec, l'accès est
     *techniquement* borné au diagnostic — ce qui s'écrit dans le contrat et se
     démontre en audit.
  3. Double authentification obligatoire sur le compte de l'éditeur : ce compte
     devient la clé d'entrée de tous les cabinets, l'actif le plus sensible du
     parc, bien avant le code source.
  4. Traçabilité des accès de l'éditeur : qui, quand, pourquoi.
  5. Vérifier le DPA du fournisseur et son cadre de transfert hors UE ; prévoir
     l'option des relais auto-hébergés en Europe si le point doit être fermé.
- **Critères d'acceptation :**
  - Depuis le poste de l'éditeur, `/etat` répond et une tentative d'accès à un
    autre port de la même machine échoue.
  - L'ACL est versionnée et commentée.
  - Tailscale est nommé dans le contrat de sous-traitance.

### C4-T6 — Chiffrement au repos

- **Effort :** S
- **Process :** Direct — étape d'installation, pas de code applicatif.
- **Dépendances :** aucune
- **Périmètre :** `docs/recette-installation.md`, liste de contrôle
  d'installation
- **Travail :** activer BitLocker sur le PC du cabinet et en faire une étape
  bloquante de l'installation. Les PDF ne sont pas chiffrés au repos ; c'est le
  point qu'un audit soulèvera avant même d'interroger le mode d'accès à distance.
- **Critères d'acceptation :** l'installateur refuse de se déclarer terminé si le
  volume de `dossier_pdf` n'est pas chiffré, ou consigne explicitement la
  dérogation.

---

## C5 — Mises à jour signées

**Pourquoi.** Verrou n°3 : aujourd'hui, un correctif égale N déplacements. C'est
la raison économique, et pas seulement technique, pour laquelle ce chantier passe
avant toute nouvelle fonctionnalité. La fiabilité est la marge.

### C5-T1 — Format de paquet et signature Ed25519

- **Effort :** M
- **Process :** Complet — format signé : une erreur ici se corrige mal une fois diffusée.
- **Dépendances :** C4-T4
- **Périmètre :** `outils/faire-paquet.sh`, `outils/signer-paquet.py` (nouveau)
- **Travail :**
  1. Paquet versionné contenant un manifeste : version, date, empreintes SHA-256
     de chaque fichier, version minimale depuis laquelle la montée est permise.
  2. Signature **Ed25519** du manifeste. La clé privée de publication ne quitte
     jamais le poste de l'éditeur et n'est pas la clé de l'autorité de
     certification — deux rôles, deux clés.
  3. Clé publique embarquée dans le paquet installé.
- **Critères d'acceptation :**
  - Un paquet dont un octet a été modifié est rejeté.
  - Un paquet signé par une autre clé est rejeté.
  - Un paquet de version antérieure est refusé (anti-retour arrière).
  - Chaque cas ci-dessus est couvert par un test.

### C5-T2 — Client de mise à jour

> **Décision du 3 novembre 2026 :** le PC tire les mises à jour lui-même et
> n'installe qu'un paquet signé. Seul flux sortant : du code public, jamais
> une donnée de santé. C'est à écrire tel quel dans le contrat de
> sous-traitance (C0-T2).

- **Effort :** L
- **Process :** Complet — remplace du code sur le parc, vérification de signature comprise.
- **Dépendances :** C5-T1
- **Périmètre :** `serveur/maj.py` (nouveau), tâche planifiée
- **Travail :**
  1. Vérification périodique de la disponibilité d'une version, par appel
     **sortant** vers un emplacement de publication. Rien n'entre dans le
     cabinet sans que le cabinet l'ait demandé.
  2. Téléchargement, vérification de signature et d'empreintes, application
     **hors heures d'ouverture**, jamais pendant un bilan.
  3. Sauvegarde de la version précédente et **retour arrière automatique** si
     `/sante` ne répond pas dans la minute suivant le redémarrage.
  4. `config.json`, les certificats, `bilans/` et les schémas du client ne sont
     jamais écrasés.
  5. Résultat de la mise à jour tracé dans le journal technique et visible dans
     `/etat`.
- **Critères d'acceptation :**
  - Une mise à jour volontairement cassée revient seule à la version précédente,
     et le cabinet n'a rien vu.
  - Une mise à jour pendant un dépôt en cours n'altère pas le PDF déposé.
  - La configuration du client survit à trois montées de version successives.
- **Risque :** c'est la fonctionnalité qui peut casser tout le parc d'un seul
  coup. Déploiement par vagues, le cabinet pilote en dernier.

### C5-T3 — Canal de publication

- **Effort :** S
- **Process :** Allégé — outil de publication interne, jamais exécuté chez un client.
- **Dépendances :** C5-T1
- **Périmètre :** `outils/publier.sh`
- **Travail :** emplacement de publication, canaux `stable` et `pilote`, et une
  procédure de retrait d'une version défectueuse qui ne dépende pas de la bonne
  volonté des clients.
- **Critères d'acceptation :** retirer une version la rend indisponible aux
  installations qui ne l'ont pas encore prise, en moins de cinq minutes.

---

## C6 — Durcissement de sécurité

**Pourquoi.** Le projet traite des données de santé. Ces points ne bloquent pas
la vente mais figureront dans tout audit, et deux d'entre eux sont presque
gratuits.

### C6-T1 — Politique de sécurité de contenu

- **Effort :** S
- **Process :** Allégé + audit — la politique elle-même est l'objet de l'audit ; le contrat serait une paraphrase.
- **Dépendances :** C1-T2 (le style inline doit avoir disparu)
- **Périmètre :** `formulaire/index.html`, `serveur/serveur.py` (`end_headers`,
  ligne 394)
- **Travail :** toutes les bibliothèques sont vendorisées localement : une CSP
  stricte (`default-src 'self'`, pas de `unsafe-inline`) est presque gratuite.
  Supprimer d'abord `onclick="exporterBilanPDF()"` (`index.html:26`) au profit
  d'un `addEventListener`.
- **Critères d'acceptation :** l'en-tête CSP est présent, la console du
  navigateur ne signale aucune violation sur un parcours complet, et un test
  vérifie la présence de l'en-tête.

### C6-T2 — Limitation des tentatives d'authentification

- **Effort :** S
- **Process :** Complet — touche l'authentification.
- **Dépendances :** aucune
- **Périmètre :** `serveur/serveur.py` (`authentifie`, ligne 363)
- **Travail :** compteur d'échecs par source avec temporisation progressive, et
  trace dans le journal technique (sans adresse IP : un compteur agrégé suffit).
  Faible gravité en réseau local, mais c'est la remarque d'audit la plus facile
  à formuler.
- **Critères d'acceptation :** dix échecs consécutifs ralentissent les réponses
  suivantes ; un identifiant valide reste accepté sans délai ; test couvrant.

### C6-T3 — Validation des données relues

- **Effort :** S
- **Process :** Allégé + audit — validation des données relues.
- **Dépendances :** aucune
- **Périmètre :** `formulaire/script.js` (`restaurerBilan`, ligne 845)
- **Travail :** contrôler la forme de ce qui sort de `localStorage` avant de le
  réinjecter dans le DOM. Le brouillon est écrit par le site lui-même, mais il
  est modifiable depuis la console et sa structure survit aux changements de
  schéma.
- **Critères d'acceptation :** un brouillon corrompu ou issu d'un schéma
  antérieur est ignoré avec un message, sans casser le formulaire ; test Node.

### C6-T4 — Nettoyage du dépôt

> **État : livrée le 3 novembre 2026**, en deux commits.
> - Renormalisation isolée des deux `.ps1` : l'index passe en LF, le disque
>   garde CRLF et BOM, et le diff est vide sous `--ignore-cr-at-eol`.
> - Contrôle des secrets étendu à `cles-editeur/` et aux extensions de clé
>   privée, avec lecture des chemins sans guillemets. Il a été éprouvé sur
>   quatre clés factices indexées, toutes refusées.
>
> `.DS_Store` n'était déjà plus suivi. Le secret d'API DNS est sans objet
> depuis C3-T1.

> **Divergence latente à refermer, diagnostiquée le 20 octobre pendant C4-T1.**
> `.gitattributes:23` exige `*.ps1 text eol=crlf`, mais les blobs de
> `installer-demarrage.ps1` et `desinstaller-demarrage.ps1` ont été commités
> **en CRLF** avant l'ajout de `.gitattributes` (commit `daf60aa`) : leur blob
> contient 125 CR. `git diff` compare donc le fichier nettoyé (0 CR) au blob
> (125 CR) et affiche **310 lignes modifiées** sur deux fichiers que personne
> n'a touchés — contenu, mode et date intacts. Conséquences : un `git add -A`
> fait entrer ces lignes fantômes dans un commit sans rapport, et tout diff de
> revue est pollué. La correction est un `git add --renormalize` isolé, dans son
> propre commit, **jamais mêlé à une tâche** — et à vérifier contre
> `tests/test_serveur.PortabiliteWindows`, qui exige CRLF et BOM sur le disque.

- **Effort :** S
- **Process :** Direct — retrait de fichiers du suivi Git et contrôle d'intégration continue.
- **Dépendances :** aucune
- **Périmètre :** `.DS_Store`, `.gitignore`
- **Travail :** retirer `.DS_Store` du suivi Git (il est versionné) et vérifier
  que le contrôle « aucun secret versionné » de l'intégration continue couvre
  bien les nouveaux fichiers sensibles (clé de publication, secret DNS).
- **Critères d'acceptation :** `git ls-files | grep DS_Store` est vide ; le
  contrôle de l'intégration continue échoue si l'on ajoute volontairement une
  clé de publication.

### C6-T5 — Une requête malformée reçoit un code, pas un silence

> **Ouverte le 15 octobre 2026**, par l'audit de C1-T3. Défaut **pré-existant**,
> non introduit par cette tâche : il est antérieur à l'ajout de `.json` dans la
> liste blanche, et se reproduit à l'identique sur `.html` et `.css`.

- **Effort :** S
- **Process :** Allégé + audit — codes de réponse sur requête malformée.
- **Dépendances :** aucune
- **Périmètre :** `serveur/serveur.py`, `autorise_lecture()` (lignes 404-434)
- **Constaté :** un octet nul encodé dans le chemin ferme la connexion sans
  réponse. `GET /journal.log%00.json` rend un `RemoteDisconnected` : l'exception
  n'est pas rattrapée dans le fil de la requête. Le serveur survit — la requête
  suivante répond 200 — et l'appel exige des identifiants valides. `/index%00.html`
  et `/style%00.css` produisent le même effet. Cause : l'extension est calculée
  sur le chemin **non décodé**, la résolution sur le chemin décodé.
- **Travail :** rattraper le cas, répondre un code d'erreur, et calculer
  l'extension et la résolution sur la **même** forme du chemin.
- **À ajouter (audit de C4-T3, 6 novembre) :** l'en-tête `Server` divulgue la
  version de Python sur toutes les routes, `/sante` comprise ; le réduire à un
  nom neutre (`server_version`, `sys_version`), et tester qu'aucune réponse ne
  porte plus de numéro de version Python.
- **Critères d'acceptation :** les formes malformées — octet nul compris —
  reçoivent 400, 403 ou 404, jamais un silence ; test d'intégration couvrant
  l'octet nul sur une extension servie et une extension refusée.
- **Déjà vérifié, à ne pas refaire :** la remontée de chemin est propre. Les
  22 formes essayées contre un serveur réel (`..`, `%2e%2e`, `..%2f`, `..\`,
  `%5c`, `/....//`, `//`, `/config%2Ejson`, `?`, `#`, `/moteur/../`) laissent
  `config.json` inatteignable, en 403 ou 404.

---

## C7 — Filet de tests

**Pourquoi.** 57 tests Python couvrent le serveur ; côté navigateur, seule la
file d'attente des dépôts est testée (`tests/test_file_depots.js`). Les ~1 100
autres lignes de `script.js` ne le sont pas, dont la pagination PDF, qui est la
partie la plus subtile du projet. Chaque régression non rattrapée par un test
devient un appel de support, et un appel de support consomme la marge du mois.

### C7-T1 — Tester `calculerPages()`

> **État : livrée le 3 novembre 2026.** `tests/test_pagination.js`, branché en
> intégration continue à côté de `test_file_depots.js`. Sept cas : les cinq
> demandés, plus une coupe ordinaire et une page unique. Des invariants sont
> vérifiés à chaque découpage : pages contiguës, première page en haut,
> dernière page au bas du document, aucun bloc ne déborde. La fonction est
> extraite du fichier de production, jamais recopiée.
>
> **Mises en échec :** trois mutations sur quatre rougissent. La quatrième
> retire la boucle `while (… blocs[i].bas <= debut) i++` qui suit une coupe
> franche. Elle reste verte parce que cette boucle **ne peut jamais avancer** :
> après la coupe, le bloc courant est par construction plus bas que la
> nouvelle limite. C'est du code mort, sans conséquence, à retirer lors d'une
> tâche qui touche `script.js`, pas ici (process Direct : tests seuls).

- **Effort :** S
- **Process :** Direct — tests seuls, aucun code de production modifié.
- **Dépendances :** aucune
- **Périmètre :** `tests/test_pagination.js` (nouveau), `formulaire/script.js:94`
- **Travail :** `calculerPages(blocs, hauteurPagePx, hauteurTotalePx)` est une
  fonction pure : c'est la prochaine à tester, et la moins chère. Cas à couvrir :
  bloc plus haut qu'une page, bloc qui tombe pile sur la coupe, dernier bloc,
  liste vide, hauteur totale nulle.
- **Critères d'acceptation :** les cinq cas passent, le test tourne en
  intégration continue à côté de `test_file_depots.js`.

### C7-T2 — Tester le moteur de rendu

- **Effort :** M
- **Process :** Allégé — le contrat court sert à fixer les cas couverts, pas à cadrer du code.
- **Dépendances :** C1-T3
- **Périmètre :** `tests/test_moteur.js`
- **Travail :** un schéma de référence produit un DOM attendu ; chaque type de
  champ a son cas ; un schéma invalide produit une erreur et non un rendu
  partiel.
- **Critères d'acceptation :** tous les types du vocabulaire C1-T1 sont couverts.

### C7-T3 — Vérifier la file d'attente dans un vrai navigateur

- **Effort :** S
- **Process :** Direct — essai manuel sur la tablette du cabinet, à consigner.
- **Dépendances :** aucune
- **Périmètre :** `docs/recette-installation.md`
- **Travail :** la file n'a jamais tourné sur un IndexedDB réel ; elle est
  validée sur un double simulé. Générer un bilan serveur arrêté sur la tablette
  du cabinet, relancer le serveur, voir le bilan partir seul. Consigner le
  résultat.
- **Critères d'acceptation :** essai réalisé et consigné, avec la date et la
  version.

### C7-T4 — Recette du parc en intégration continue

- **Effort :** M
- **Process :** Allégé — intégration continue, hors du chemin d'exécution du cabinet.
- **Dépendances :** C5-T2
- **Périmètre :** `.github/workflows/`
- **Travail :** ajouter un travail qui installe le paquet dans une VM Windows
  propre, applique une mise à jour, vérifie `/sante` et `/etat`. C'est le seul
  moyen de ne pas découvrir les défauts d'installation chez le client.
- **Critères d'acceptation :** le travail échoue si l'installateur ou la mise à
  jour régresse.

### C7-T5 — Stabiliser `ServeurEnMarche` sous Windows

> **État : livrée le 3 novembre 2026, cause unique trouvée.** Les deux
> instabilités ci-dessous n'en font qu'une : `ServeurEnMarche` lançait le
> serveur avec `stdout=PIPE` sans jamais lire ce tube.
> - **Le mécanisme :** le serveur écrit une ligne sur stderr par requête. Une
>   fois le petit tampon Windows plein, chaque requête qui journalise se
>   bloque, et les tests expirent en lecture TLS. `/sante`, muette, répond
>   seule.
> - **Les observations :** c'est le « délai TLS » du 14 octobre. Le
>   3 novembre, l'échec est devenu systématique sous Windows, en 3.9 comme en
>   3.13, une fois ajoutés les tests de C2-T1.
> - **Le correctif :** un fil lecteur vide le tube en continu.
> - **Mesure :** dix exécutions complètes de la CI, toutes vertes (runs
>   41731416364 à 41731824174). Le critère des trente exécutions consécutives
>   reste à compléter, au fil des CI suivantes.
> - **Reste :** `demarrer_sandbox_court` (`ServeurArret`) garde un `PIPE`
>   relu par `communicate()`. Son échec d'environ une fois sur soixante est le
>   même mécanisme : à traiter de la même façon si on le revoit.

> **Second flake, de mécanisme différent, mesuré le 20 octobre pendant C4-T1.**
> `ServeurArret.test_arret_journalise` échoue environ une fois sur vingt à
> soixante : ce n'est **pas** l'attente TLS de `ServeurEnMarche`, c'est le
> blocage de `Popen` dont le tube `stdout=PIPE` se remplit — banc dédié :
> 11 échecs sur 12 sous charge avec tube non vidé, **0 sur 4** avec un fil
> lecteur. Ce n'est pas `_verrou_journal` : `journaliser()` écrit sur `stderr`
> **hors** du verrou. `communicate()` a remplacé `wait()`, ce qui réduit
> nettement la fréquence et transforme l'échec en diagnostic lisible, mais ne
> l'élimine pas : un échec sur 60 subsiste, et il reviendra dès qu'une version
> plus bavarde du serveur tournera derrière ce test. **Risque en production
> nul**, argumenté dans `docs/audits/C4-T1.md` : sous `pythonw` en SYSTEM
> `sys.stderr` vaut `None` et il n'y a aucun tube, le `.bat` a une console
> drainante, et le service est tué par `TerminateProcess`, qui n'exécute jamais
> le `finally`. Critère qui discrimine au prochain échec : `ARRET` absent +
> processus vivant = tube plein ; `ARRET` absent + sortie immédiate = course du
> signal arrivant avant le `try`.

- **Effort :** S
- **Process :** Allégé — harnais de test ; le diagnostic compte plus que le correctif.
- **Dépendances :** aucune
- **Périmètre :** `tests/test_integration.py` (démarrage du serveur de test)
- **Constaté :** le 14 octobre 2026, après C1-T2, les dix tests de
  `test_integration.ServeurEnMarche` ont échoué sur la seule combinaison
  Windows + Python 3.9 — délai d'attente en lecture TLS (`ssl.recv_into`), le
  serveur de test ne répondant pas. Les cinq autres combinaisons étaient
  vertes, le commit précédent passait sur celle-ci, et une simple relance du
  même travail, sans aucune modification de code, est repassée au vert. C'est
  donc un défaut d'instabilité du harnais de test, pas une régression du
  serveur.
- **Travail :** rendre déterministe l'attente de disponibilité du serveur de
  test : attendre que le port accepte réellement une poignée de main TLS
  complète plutôt qu'une connexion TCP, et faire échouer le démarrage avec un
  message explicite plutôt que de laisser dix tests expirer un par un.
  Ce chantier croise trois pièges déjà payés : ALPN, les erreurs TLS avalées
  par `socketserver.get_request()`, et `SO_REUSEADDR` sous Windows.
- **Critères d'acceptation :**
  - Un démarrage de serveur de test qui échoue produit **un** message nommant
    la cause, et non dix expirations de dix secondes.
  - Trente exécutions consécutives du travail Windows + Python 3.9 sans échec.
- **Risque :** un test rouge par intermittence est pire qu'un test absent — on
  prend l'habitude de relancer, et le jour où l'échec est réel, on relance
  aussi.

---

## C8 — Mécanisme de licence d'abonnement

**Pourquoi.** Un abonnement en local-first suppose un moyen de distinguer un
abonné d'un ex-abonné. À cadrer pendant l'industrialisation, pas après.

### C8-T1 — Clé de licence signée à durée limitée

> **Comportement à l'expiration, tranché le 3 novembre 2026 :** trente jours
> de bandeau d'alerte, puis la saisie reste possible mais l'export est refusé,
> avec le même mécanisme et le même message clair que le refus d'un bilan
> anonyme (C2-T1). Le serveur ne s'arrête jamais, et les bilans déjà produits
> ne sont jamais touchés.

- **Effort :** M
- **Process :** Complet — clé signée et vérification : même exigence que C5-T1.
- **Dépendances :** C5-T1 (même outillage de signature), C0-T1
- **Périmètre :** `serveur/licence.py` (nouveau)
- **Travail :**
  1. Clé signée portant un identifiant d'installation et une date de fin.
  2. Renouvellement par appel sortant périodique. **Seul un identifiant
     d'installation circule** — compatible avec « aucune donnée de santé ne
     sort », et cette propriété doit rester vérifiable par lecture du code.
  3. Expiration **sans rien casser** : avertissement croissant, puis arrêt des
     mises à jour. Jamais de blocage de l'accès aux bilans déjà produits —
     bloquer l'accès à des données de santé pour un impayé est une faute.
  4. Tolérance de panne réseau : plusieurs semaines de grâce, un cabinet hors
     ligne n'est pas un fraudeur.
- **Critères d'acceptation :**
  - Une licence expirée affiche un avertissement et laisse le bilan se faire.
  - Trois semaines sans réseau n'altèrent rien.
  - La requête sortante ne contient que l'identifiant d'installation et la
    version ; un test le vérifie octet par octet.
- **Risque :** un mécanisme trop zélé transforme une panne d'abonnement en
  incident de soin.

---

## C9 — Atelier de fabrication d'un client

**Pourquoi.** « Done for you » : le praticien ne modèle jamais son template, il
remplit une feuille de route. L'éditeur fabrique. Le temps de fabrication
détermine le prix du setup **et** le plafond de croissance.

### C9-T1 — Questionnaire de feuille de route

> **État : livrée le 3 novembre 2026** (`docs/feuille-de-route-client.md`), à
> relire par Baptiste (process Direct). Le questionnaire est dérivé du
> vocabulaire du schéma : sept formes, les dispositions, `indication`, l'ordre
> des schémas. Il reprend aussi les sept champs de `cabinet` et les marqueurs
> de `convention_nommage`, ainsi que le questionnaire matériel de
> l'installation à distance. Les grilles y sont signalées à part, en attendant
> C1-T6. **Critère à mesurer :** produire un schéma depuis la première
> feuille réellement remplie, sans rappeler le client.

- **Effort :** S
- **Process :** Direct — document commercial, aucune ligne de code.
- **Dépendances :** C1-T1 (le vocabulaire du schéma détermine les questions
  utiles)
- **Périmètre :** `docs/feuille-de-route-client.md`
- **Travail :** le document commercial rempli **avant devis** : sections et leur
  ordre, champs de chaque section, schémas à annoter, palette et logo,
  coordonnées d'en-tête, convention de nommage des fichiers. C'est l'outil de
  vente, il ne demande aucune ligne de code, et sa structure détermine la forme
  du schéma côté moteur.
- **Critères d'acceptation :** une feuille de route remplie suffit à produire
  `schema.json` et `theme.json` sans rappeler le client.

### C9-T2 — Outil d'atelier de composition

- **Effort :** M
- **Process :** Allégé — outil d'atelier interne, jamais vendu ni installé.
- **Dépendances :** C1-T5, C9-T1
- **Périmètre :** `outils/atelier/`
- **Travail :** un outil interne — **jamais une fonctionnalité vendue** — qui
  compose un schéma à partir des blocs, valide le résultat et produit un aperçu.
  Les praticiens ne veulent pas passer de temps dans un éditeur.
- **Critères d'acceptation :** fabriquer un client complet depuis une feuille de
  route remplie prend moins de trois heures, mesuré sur deux cas.

### C9-T3 — Politique d'évolution après livraison

> **Tranchée le 3 novembre 2026 : une révision annuelle**, incluse dans
> l'abonnement ; une modification urgente hors révision se facture à part.
> Déjà annoncée au client dans `docs/feuille-de-route-client.md`. Il reste à
> l'écrire dans les CGV, qui naîtront avec C0-T2.

- **Effort :** S
- **Process :** Direct — décision commerciale, écrite dans les CGV.
- **Dépendances :** C9-T2
- **Périmètre :** CGV
- **Travail :** « Ajoutez-moi un champ » arrivera dès la deuxième semaine, chez
  tous les clients. Trancher maintenant : inclus, forfaité, ou groupé en une
  révision annuelle.
- **Critères d'acceptation :** la réponse est écrite dans les CGV et tarifée.

---

## C10 — Hors périmètre V2

Explicitement **pas** dans la V2, pour que le périmètre tienne :

| Sujet | Renvoyé à | Pourquoi pas maintenant |
|---|---|---|
| Connecteur MSSanté | V3 | Suppose la V2 installée chez plusieurs cabinets ; dépend aussi de questions ouvertes côté Cegedim |
| PDF vectoriel | V3 | Règlerait la pagination et le poids des fichiers, mais réécrit le générateur. À faire après la stabilisation du moteur à schéma |
| Comptes par praticien, traçabilité | V4 | Le vrai levier économique, mais sans objet avant un cabinet de groupe |
| Historique et comparaison de bilans | V5 | Suppose une base de données, donc l'abandon du « bilan = image » |
| Signature patient au stylet | Option | La mécanique de dessin existe déjà ; se vend à part |
| Module HPRIM | À instruire | Dépend d'une réponse du support Cegedim (question ouverte) |

---

## Ordre d'exécution conseillé

```
C0-T1 licence ────────────────────────────────┐ (décision, avant d'investir)
C1-T2 tokens ──┐                              │
C4-T1 journal  ├─ chantiers courts, en parallèle
C4-T4 version  │
C6-T4 dépôt  ──┘
C3-T1 adressage (étude) ──────────────────────┤ (décision, bloque C3)
C1-T1 vocabulaire ──► C1-T3 moteur ──► C1-T4a schéma ──► C1-T5 blocs
                                       └─► C1-T4b livraison (à la visite au cabinet)
C2-T1 identité ───────────────────────────────┤
C4-T3 /etat ──► C4-T5 Tailscale
C3-T2 certificat ──► C3-T3 installateur ──► C3-T4 recette
C5-T1 signature ──► C5-T2 client de MAJ ──► C5-T3 publication
C8-T1 licence technique
C9-T1 feuille de route ──► C9-T2 atelier ──► C9-T3 politique
C6, C7 au fil de l'eau, chaque tâche avec ses tests
```

**Première tâche à lancer, si une seule :** `C9-T1`, le questionnaire de feuille
de route. Aucune ligne de code, c'est l'outil de vente, et sa structure
détermine ensuite la forme du schéma. Côté technique, `C4-T1` : le journal
technique conditionne tout le support à distance.

---

## Comment ce document s'utilise

Chaque tâche porte un **niveau de process** (voir
[Les trois niveaux](#les-trois-niveaux-de-process)) qui dit quelle part de la
chaîne lui appliquer. La chaîne pleine, pour les tâches marquées **Complet** :

| Étape | Commande | Produit |
|---|---|---|
| 1. Contrat | `/lancer-tache C1-T3` | `docs/contrats/C1-T3.md` |
| 2. Implémentation + audit | `/implementer-tache C1-T3` | code, tests, rapport d'audit |
| 3. Revue | `/revue-code C1-T3` | verdict et corrections |
| 4. Clôture | `/cloture-projet` | `CLAUDE.md` à jour, `docs/resumes/<date>.md` |

Pour les niveaux inférieurs, on retire des étapes par le haut :

| Niveau | 1. Contrat | 2. Implémentation | Audit | 3. Revue | 4. Clôture |
|---|---|---|---|---|---|
| Direct | — | à la main, en conversation | — | relecture humaine | groupée |
| Allégé | court | `/implementer-tache` | — | dans la foulée | groupée |
| Allégé + audit | court, avec le point à auditer | `/implementer-tache` | ciblé | dans la foulée | groupée |
| Complet | `/lancer-tache` | `/implementer-tache` | complet | `/revue-code` | `/cloture-projet` |

« Clôture groupée » : plusieurs tâches de niveau Direct ou Allégé sont closes
ensemble en fin de session, en un seul `/cloture-projet`. C'est le second gain
de temps du dispositif, après la suppression des contrats inutiles.

Une tâche n'est cochée ici que lorsque ses critères d'acceptation sont tous
vérifiés — quel que soit son niveau. Le process allégé allège le cadrage, pas
les critères.
