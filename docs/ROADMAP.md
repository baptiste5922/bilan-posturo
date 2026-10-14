# Feuille de route V1 → V2

> **Objet.** Décrire, tâche par tâche, le travail qui sépare la V1 (un cabinet,
> installation manuelle, formulaire écrit à la main) de la **V2 « industrialisée »**
> définie en section 7 de `docs/projection.md` : installateur, moteur à schéma,
> mises à jour signées, diagnostic à distance, support.
>
> **Document de travail interne.** Il s'appuie sur `docs/projection.md`, dont il
> est la traduction opérationnelle. La projection dit *pourquoi* ; cette feuille
> de route dit *quoi faire, dans quel ordre, et comment savoir que c'est fini*.

**Dernière mise à jour :** 14 octobre 2026
**État de départ :** V1 en production chez un cabinet depuis deux mois.

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
- Toute tâche touchant au serveur ou au dépôt de fichiers passe par l'**audit de
  sécurité** (`/implementer-tache` enchaîne l'auditeur) avant la revue de code.

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
pour une praticienne : 17 blocs, ~78 champs identifiés, l'identité du cabinet en
dur lignes 65-68. Face au deuxième cabinet, les deux seules réponses possibles
sans moteur sont mauvaises : imposer le template (on devient le Cegedim que l'on
dénonce) ou maintenir un HTML par client (10 clients = 10 divergences, et le
premier correctif de pagination devient impossible à propager).

**Cible.** Un moteur unique, N descriptions. `schema.json` décrit les sections,
les champs et les images annotables ; `theme.json` décrit la palette, le logo et
l'en-tête ; le moteur de rendu, identique chez tous les clients, produit le DOM.

### C1-T1 — Inventorier le formulaire existant et en déduire le vocabulaire de schéma

- **Effort :** M
- **Dépendances :** aucune
- **Périmètre :** `docs/schema-formulaire.md` (spécification), lecture de
  `formulaire/index.html`
- **Travail :**
  1. Lister les 17 blocs et les ~78 champs, avec pour chacun : type
     (`texte`, `nombre`, `date`, `case`, `radio`, `liste`, `zone-texte`,
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
> chaque génération de PDF. 13 des 18 critères sont vérifiés ; les cinq
> autres demandent un navigateur et restent à exécuter par le praticien —
> procédure dans `docs/references-visuelles/LISEZMOI.md`. **Pas de
> déploiement sur la tablette avant.**

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

- **Effort :** L
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
- **Risque :** c'est la tâche la plus lourde du chantier et le point de
  non-retour. À ne pas démarrer avant que C1-T1 soit relu.

### C1-T4 — Rendre le formulaire de production depuis un schéma

- **Effort :** M
- **Dépendances :** C1-T3
- **Périmètre :** `clients/morlaix/schema.json`, `clients/morlaix/theme.json`,
  suppression du HTML sur mesure
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

- **Effort :** M
- **Dépendances :** C1-T4
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

## C2 — Identité du cabinet en configuration

**Pourquoi.** Le nom, l'adresse, le courriel et le téléphone de la praticienne
sont écrits dans `formulaire/index.html:65-68`, et le logo est un fichier au nom
fixe. Tant qu'il en est ainsi, installer un deuxième cabinet veut dire éditer du
HTML.

### C2-T1 — Bloc `cabinet` dans `config.json` et route `GET /cabinet`

- **Effort :** M
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
- **Critères d'acceptation :**
  - `grep -i "LE GOFF\|Grand'Rue\|legoffpodologue\|02 98 88" formulaire/` ne
    renvoie rien.
  - `GET /cabinet` sans identifiants renvoie 401.
  - Serveur injoignable : l'en-tête reste vide, le formulaire reste utilisable,
    et l'export PDF est refusé avec un message explicite.
  - Le nom de fichier produit par `construireNomFichier()` suit la convention
    déclarée en configuration.
- **Risque :** un bilan PDF portant l'en-tête d'un autre cabinet est un incident
  à déclarer, pas un bug.

### C2-T2 — Logo et actifs propres au client

- **Effort :** S
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

- **Effort :** M (étude), décision bloquante
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

- **Effort :** L
- **Dépendances :** C3-T1 (si voie 1 retenue)
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

- **Effort :** L
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

### C3-T4 — Procédure de recette d'installation

- **Effort :** S
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

- **Effort :** M
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

- **Effort :** S
- **Dépendances :** C0-T2, C4-T1
- **Périmètre :** `serveur/serveur.py`, configuration
- **Travail :** la rotation borne la taille, pas la durée. Ajouter une purge par
  ancienneté, en mois, paramétrée et alignée sur le chiffre du contrat.
- **Critères d'acceptation :** une archive plus ancienne que la durée configurée
  est supprimée au démarrage et à chaque rotation ; un test vérifie la bascule
  par horodatage.

### C4-T3 — Page de diagnostic authentifiée `GET /etat`

- **Effort :** M
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

- **Effort :** S
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

- **Effort :** M (dont exploitation)
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

- **Effort :** L
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
- **Dépendances :** aucune
- **Périmètre :** `formulaire/script.js` (`restaurerBilan`, ligne 845)
- **Travail :** contrôler la forme de ce qui sort de `localStorage` avant de le
  réinjecter dans le DOM. Le brouillon est écrit par le site lui-même, mais il
  est modifiable depuis la console et sa structure survit aux changements de
  schéma.
- **Critères d'acceptation :** un brouillon corrompu ou issu d'un schéma
  antérieur est ignoré avec un message, sans casser le formulaire ; test Node.

### C6-T4 — Nettoyage du dépôt

- **Effort :** S
- **Dépendances :** aucune
- **Périmètre :** `.DS_Store`, `.gitignore`
- **Travail :** retirer `.DS_Store` du suivi Git (il est versionné) et vérifier
  que le contrôle « aucun secret versionné » de l'intégration continue couvre
  bien les nouveaux fichiers sensibles (clé de publication, secret DNS).
- **Critères d'acceptation :** `git ls-files | grep DS_Store` est vide ; le
  contrôle de l'intégration continue échoue si l'on ajoute volontairement une
  clé de publication.

---

## C7 — Filet de tests

**Pourquoi.** 57 tests Python couvrent le serveur ; côté navigateur, seule la
file d'attente des dépôts est testée (`tests/test_file_depots.js`). Les ~1 100
autres lignes de `script.js` ne le sont pas, dont la pagination PDF, qui est la
partie la plus subtile du projet. Chaque régression non rattrapée par un test
devient un appel de support, et un appel de support consomme la marge du mois.

### C7-T1 — Tester `calculerPages()`

- **Effort :** S
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
- **Dépendances :** C1-T3
- **Périmètre :** `tests/test_moteur.js`
- **Travail :** un schéma de référence produit un DOM attendu ; chaque type de
  champ a son cas ; un schéma invalide produit une erreur et non un rendu
  partiel.
- **Critères d'acceptation :** tous les types du vocabulaire C1-T1 sont couverts.

### C7-T3 — Vérifier la file d'attente dans un vrai navigateur

- **Effort :** S
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
- **Dépendances :** C5-T2
- **Périmètre :** `.github/workflows/`
- **Travail :** ajouter un travail qui installe le paquet dans une VM Windows
  propre, applique une mise à jour, vérifie `/sante` et `/etat`. C'est le seul
  moyen de ne pas découvrir les défauts d'installation chez le client.
- **Critères d'acceptation :** le travail échoue si l'installateur ou la mise à
  jour régresse.

### C7-T5 — Stabiliser `ServeurEnMarche` sous Windows

- **Effort :** S
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

- **Effort :** M
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

- **Effort :** S
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
- **Dépendances :** C1-T5, C9-T1
- **Périmètre :** `outils/atelier/`
- **Travail :** un outil interne — **jamais une fonctionnalité vendue** — qui
  compose un schéma à partir des blocs, valide le résultat et produit un aperçu.
  Les praticiens ne veulent pas passer de temps dans un éditeur.
- **Critères d'acceptation :** fabriquer un client complet depuis une feuille de
  route remplie prend moins de trois heures, mesuré sur deux cas.

### C9-T3 — Politique d'évolution après livraison

- **Effort :** S
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
C1-T1 vocabulaire ──► C1-T3 moteur ──► C1-T4 production ──► C1-T5 blocs
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

Chaque tâche suit la même chaîne, outillée par les compétences du dépôt :

| Étape | Commande | Produit |
|---|---|---|
| 1. Contrat | `/lancer-tache C1-T3` | `docs/contrats/C1-T3.md` |
| 2. Implémentation + audit | `/implementer-tache C1-T3` | code, tests, rapport d'audit |
| 3. Revue | `/revue-code C1-T3` | verdict et corrections |
| 4. Clôture | `/cloture-projet` | `CLAUDE.md` à jour, `docs/resumes/<date>.md` |

Une tâche n'est cochée ici que lorsque ses critères d'acceptation sont tous
vérifiés et que la revue est passée.
