# Session du 1er octobre 2026 — Outillage de la V2

**Durée approximative :** une séance
**Tâches concernées :** aucune tâche de code — mise en place de la feuille de
route et de la chaîne de production qui servira à les traiter
**Branche :** `main`  **Commits :** aucun (travail non commité)

## Ce qui a été fait

La session ne touche pas une ligne de code applicatif. Elle construit ce qui
manquait pour attaquer la V2 sans improviser : une carte, et une chaîne de
production.

**La carte — `docs/ROADMAP.md` (784 lignes).** `docs/projection.md` disait
*pourquoi* aller vers la V2 et ce qu'elle doit contenir, mais restait au niveau
de la liste à cinq entrées de sa section 6. La feuille de route en est la
traduction opérationnelle : onze chantiers (C0 à C10), trente-six tâches
identifiées `C<chantier>-T<numéro>`, chacune avec son objectif, ses dépendances,
les fichiers touchés, le plan de travail, des critères d'acceptation
vérifiables, les tests à écrire et le risque principal.

Deux choix de structure méritent d'être consignés. D'abord, **C0 (licence et
cadre juridique) passe avant tout le reste** : chaque semaine de développement
sous MIT agrandit la base que n'importe qui, concurrent compris, pourra
reprendre et vendre, et le dépôt est public. Ensuite, **C10 énumère ce qui n'est
explicitement pas dans la V2** — connecteur MSSanté, PDF vectoriel, comptes par
praticien, historique, signature patient. Sans cette section, le périmètre
s'étend de lui-même et la V2 n'est jamais livrée.

Les tâches sont ancrées dans le code réel, pas déduites des noms de fichiers :
la palette dupliquée a été recomptée (`style.css:2` et `:14`, huit occurrences
de `#8C6D53` dans le CSS, `script.js:11-14`, un style en ligne à
`index.html:26`), l'identité du cabinet localisée (`index.html:65-68`), le point
d'accroche de la CSP repéré (`end_headers`, `serveur.py:394`), et
`calculerPages()` (`script.js:94`) désignée comme prochaine fonction à tester
parce qu'elle est pure.

**La chaîne de production — quatre agents dans `.claude/agents/`.** Chacun a un
rôle unique et un livrable écrit :

| Agent | Modèle | Effort | Livrable |
|---|---|---|---|
| `planificateur-tache` | opus | medium | `docs/contrats/<ID>.md` |
| `implementeur` | sonnet | high | code et tests |
| `auditeur-securite` | opus | medium | `docs/audits/<ID>.md` |
| `reviseur-code` | sonnet | high | `docs/revues/<ID>.md` |

Les trois agents de contrôle n'ont pas `Edit` : ils ne peuvent écrire que leur
propre rapport. La séparation n'est pas de principe, elle est mécanique.

Chacun porte les contraintes du projet dans sa définition, pour ne pas dépendre
de ce qu'un prompt pensera à rappeler : local-first, bibliothèque standard seule
côté serveur, Python 3.9 en plancher, racine web limitée à `formulaire/`, code
en français, et un utilisateur en production tous les jours. L'auditeur a une
grille en huit rubriques qu'il doit parcourir en entier — données de santé,
surface exposée, authentification, écriture de fichiers, robustesse de service,
navigateur, chaîne d'approvisionnement, conformité — et l'instruction explicite
de **ne pas signaler les limites déjà assumées** (pas de limitation des
tentatives en réseau local, pas de chiffrement au repos, autorité locale), sauf
si la tâche les aggrave. C'est la condition pour que ses constats restent lus.

**Quatre compétences dans `.claude/skills/`** enchaînent ces agents :
`/lancer-tache`, `/implementer-tache` (implémentation puis audit, avec deux
boucles de correction au maximum), `/revue-code`, `/cloture-projet`. Chacune
vérifie le travail de l'agent plutôt que de croire son compte rendu : relecture
du contrat, exécution de `npm test` par l'orchestrateur, parcours des critères
d'acceptation un par un.

**`CLAUDE.md` (141 lignes, plafond à 300).** Créé en appliquant `/cloture-projet` à cette
session même. Il porte l'architecture en bref, les contraintes non négociables,
l'avancement par chantier — jamais par tâche, c'est ce qui le garde court — la
méthode de travail, et une section « pièges connus » qui rassemble les neuf
difficultés déjà payées une fois : ALPN et le `ERR_EMPTY_RESPONSE` muet, les
erreurs TLS avalées par `socketserver`, la sémantique de `SO_REUSEADDR` sous
Windows, `compare_digest` qui lève sur un accent, la double pile IPv6, la
palette dupliquée, `dossier_pdf` vu depuis le compte SYSTEM, la file d'attente
jamais testée sur un vrai IndexedDB, et les scripts PowerShell jamais exécutés
hors du cabinet.

## Décisions prises

| Décision | Raison | Conséquence |
|---|---|---|
| C0 (licence) en tête de la feuille de route | Le dépôt est public et ce qui est publié sous MIT le reste ; attendre agrandit définitivement la base libre | Une décision à prendre avant d'investir des semaines de développement destiné à la vente |
| C10 « hors périmètre V2 » écrit noir sur blanc | Sans frontière, le périmètre s'étend et le jalon n'est jamais atteint | MSSanté, PDF vectoriel, multi-praticien et historique sont renvoyés à V3-V5 |
| Audit de sécurité systématique, pas optionnel | Le logiciel traite des données de santé ; un constat critique ne se livre pas | `/implementer-tache` enchaîne l'auditeur sauf modification sans aucune surface sensible |
| Agents de contrôle sans droit d'écriture sur le code | Un relecteur qui corrige ne relit plus | `auditeur-securite` et `reviseur-code` n'ont pas `Edit` |
| Un seul agent à la fois sur l'arbre de travail | Deux implémenteurs dans le même dépôt se marchent dessus | Pas de parallélisation dans les compétences |
| Deux boucles de correction au maximum | Trois tours signalent un contrat fautif, pas un code fautif | Au troisième, la compétence remonte le problème plutôt que d'insister |
| Le planificateur ne contourne pas une décision manquante | Un contrat écrit par-dessus un choix non fait produit du travail à refaire | Les décisions bloquantes sont nommées en tête de contrat |
| `CLAUDE.md` modifié exclusivement par `/cloture-projet` | C'est ce qui l'empêche de dériver et de doubler `docs/ROADMAP.md` | Règle inscrite dans le fichier lui-même |
| Ne pas commiter | Rien n'a été demandé en ce sens | Le travail reste dans l'arbre de travail, avec les modifications antérieures non commitées |

## État des tests

Inchangé, et vérifié en fin de session : **57 tests Python** (`Ran 57 tests —
OK`) et **7 scénarios Node** sur la file d'attente des dépôts, tous verts.
Aucun test écrit — la session ne produit pas de code applicatif.

La feuille de route fixe la suite sur ce terrain : `C7-T1` teste
`calculerPages()`, fonction pure et donc la moins chère à couvrir ; `C7-T2` le
futur moteur de rendu ; `C7-T3` fait enfin tourner la file d'attente dans un
vrai navigateur, sur la tablette du cabinet.

## Constats de sécurité

Aucun audit lancé : rien de sensible n'a été modifié. Les points de sécurité
relevés dans le code existant ont été versés dans la feuille de route plutôt que
corrigés au passage — CSP absente et style en ligne à supprimer d'abord (C6-T1),
pas de limitation des tentatives (C6-T2), données de `localStorage` réinjectées
sans contrôle de forme (C6-T3), `.DS_Store` versionné (C6-T4).

Un point mérite d'être souligné parce qu'il conditionne tout le support à
distance : **C4-T1 exige un test qui échoue si une ligne du journal technique
contient une adresse IP ou un fragment de nom de fichier déposé.** La propriété
« je diagnostique sans voir de nom de patient » doit être garantie par la suite
de tests, pas par une intention écrite dans un contrat — c'est ce qui tient lieu
de preuve en audit.

## Ce qui reste en suspens

- **Le choix de licence (C0-T1).** Décision de l'utilisateur, pas technique.
  Bloque C8-T1 et, raisonnablement, tout investissement lourd.
- **La voie d'adressage (C3-T1).** Le sous-domaine réel avec certificat
  Let's Encrypt par challenge DNS-01 est la piste privilégiée ; il reste à
  vérifier le comportement d'un sous-domaine résolvant vers une IP privée
  (rebinding DNS) sur Chrome Android. Ce point peut invalider la voie entière, et
  il bloque l'installateur.
- **Le vocabulaire de schéma (C1-T1).** À relire avant d'écrire une ligne du
  moteur : c'est là que se pose le plafond du sur-mesure.
- **Les lectures de `.claude/`** ont été refusées par les permissions de la
  session : impossible de vérifier s'il existait déjà des agents ou des
  compétences dans ce dossier. Si des fichiers homonymes préexistaient, ils ont
  pu être remplacés — à contrôler.
- **Le dépôt a des modifications non commitées antérieures à cette session**
  (quatorze fichiers modifiés, trois non suivis, dont
  `tests/test_file_depots.js` et les deux scripts PowerShell de démarrage). Elles
  ne viennent pas d'ici, mais elles brouilleront le premier `git diff` de la
  prochaine tâche.

## Prochaine étape recommandée

**`/lancer-tache C9-T1`** — le questionnaire de feuille de route client. Aucune
ligne de code, c'est l'outil de vente, et sa structure détermine ensuite la forme
du schéma côté moteur. C'est aussi ce que recommandait déjà la section 13 de
`docs/projection.md`.

Si la préférence va au code, alors **`/lancer-tache C1-T2`** (unifier la palette
en tokens) : court, sans dépendance, gain immédiat, et préalable obligé de la
CSP. Ou **`/lancer-tache C4-T1`** (journal technique non identifiant), qui
conditionne tout le support à distance.

## À savoir pour la prochaine session

- **`docs/projection.md` est la source de vérité produit.** Avant d'écrire un
  contrat, le lire : il contient les décisions actées (section 3), les verrous
  (section 5), le cadre juridique (section 9) et le dispositif de support
  (section 10). La feuille de route en dépend et ne le remplace pas. Ce document
  est interne : il ne se diffuse pas aux cabinets.
- **Le champ de frontmatter qui règle l'effort de raisonnement d'un agent
  s'appelle `effort`**, et accepte `low`, `medium`, `high`, `xhigh`, `max`. Ce
  n'est pas `reasoning_effort` ; vérifié dans la documentation officielle plutôt
  que supposé.
- **Les lectures de `.claude/` sont bloquées par un hook de permissions** dans
  cette session (`ls`, `find`, `cat` sur ce chemin). Les écritures passent, mais
  par l'outil `Write` : un `cat > fichier` dont le *contenu* mentionne un motif
  de fichier sensible (`.pem`, `config.json`) est également refusé. Pour écrire
  une compétence ou un agent, utiliser `Write` directement et ne pas perdre de
  temps à contourner.
- **Rester prudent sur le formulaire.** Il est en production chez une
  praticienne, tous les jours. C1-T4, la bascule du formulaire de production vers
  un schéma, est le point de non-retour du projet : le retour arrière doit être
  un geste d'une minute, et l'ancien `index.html` conservé le temps d'une
  campagne de bilans.
