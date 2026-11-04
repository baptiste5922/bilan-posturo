# Session des 3 et 4 novembre 2026 — Un premier prospect, et huit tâches livrées

**Durée approximative :** une longue session, sur deux jours.
**Tâches concernées :** C2-T1, C6-T4, C9-T1, C7-T1, C4-T4, C7-T5, C3-T3a,
C4-T2. Les décisions métier touchent aussi C4-T5, C5, C8-T1 et C9-T3.
**Branches :** une par tâche, toutes intégrées à `main` en avance rapide.
**Commits :** de `53de9b4` à `27612f6`, quatorze en tout. `main` **n'est pas
poussé** ; seules les branches de tâche le sont.

## Ce qui a été fait

**Le déclencheur : un prospect.** Un formateur en posturologie installé à
Bordeaux pourrait ouvrir le réseau des podologues qu'il forme. Baptiste, à
Lille, a fourni sa fiche d'examen et deux tableaux (Maddox perceptif,
MCP 2 et 3). Il en est sorti trois choses.
- **Une fiche de démonstration** (`fiche_presentation.html`, hors dépôt et
  ignorée par Git). Elle synthétise le formulaire V1 et la fiche du
  formateur, et met en avant cinq marqueurs illustrés : inclinaison de tête,
  déviation rachidienne, bascule du bassin, genu valgum/varum, valgus
  calcanéen. Leur synthèse se rédige seule. Elle s'imprime sur six pages A4.
- **Une procédure d'installation à distance**, détaillée en conversation et
  reprise dans la fiche d'essai de C3-T3a.
- **Deux tâches nouvelles :** C1-T6, le type `grille` dont sa fiche a besoin,
  et C3-T3a.

**C2-T1 — identité du cabinet.**
- La revue a relevé un point bloquant : les deux critères qui exigent un vrai
  navigateur n'avaient jamais été démontrés. Ils l'ont été dans Chrome piloté,
  contre un serveur en bac à sable (`outils/reference-visuelle/essai-identite.js`,
  constat dans `docs/references-visuelles/CONSTAT-2026-11-03-C2-T1.md`).
- Quatre remarques importantes ont été corrigées.
- La garde d'absence d'identité couvre désormais les fichiers non suivis.
  **Elle a aussitôt trouvé le nom de voie réel du cabinet pilote** dans un
  rapport d'audit non suivi, qui aurait été publié au commit.

**C6-T4 — nettoyage du dépôt.**
- Renormalisation isolée des deux `.ps1` : la fin des 310 lignes fantômes.
- Le contrôle des secrets refuse d'avance les clés de l'éditeur
  (`cles-editeur/`, `.key`, etc.).

**C9-T1 — feuille de route client.** `docs/feuille-de-route-client.md` est le
questionnaire rempli avant devis. Il est dérivé du vocabulaire du schéma.

**C7-T1 — tests de pagination.** Sept cas. Une mutation a révélé une boucle
morte dans `calculerPages()`, laissée en place.

**C4-T4 — numéro de version.** La source unique est `formulaire/version.json`
(1.1.0). Elle s'affiche en pied de page, hors du PDF, et sur la ligne
`DEMARRAGE`.

**C7-T5 — l'instabilité Windows, enfin expliquée.** Les deux instabilités
consignées n'en faisaient qu'une : un tube `stdout=PIPE` jamais vidé par le
harnais. Une fois le petit tampon Windows plein, chaque requête qui journalise
se bloque. Un fil lecteur règle le problème : dix exécutions complètes de la
CI sont vertes.

**C3-T3a — racine des scripts d'installation.**
- Le défaut est confirmé : `installer-demarrage.ps1` cherchait `serveur\` un
  niveau trop haut. Il a sans doute fonctionné au cabinet pilote à cause d'un
  sous-dossier ; cette hypothèse reste à vérifier sur place.
- Le correctif ajoute un commutateur `-Verifier`.
- La CI Windows exécute réellement le script. Elle est verte, et rouge sur une
  branche de mutation jetable, supprimée depuis.

**C4-T2 — conservation des journaux, six mois.**
- **Le constat de départ :** la rotation n'était bornée qu'en taille, ce qui
  laissait plus de deux ans de lignes dans le journal courant.
- **Ce qui tient désormais la promesse :**
  - une rotation mensuelle ;
  - une purge par horodatage, au démarrage, à l'écriture une fois par jour, et
    par un fil toutes les 6 h ;
  - une rotation « tout ou rien ».
- **Mesure :** sur une simulation de 900 jours, l'âge maximal d'une ligne est
  de 179 j 6 h, à tout instant.

## Décisions prises

| Décision | Raison | Conséquence |
|---|---|---|
| **Pas de tunnel de support** (C4-T5 sort de la V2) | L'argument de vente est l'absence de lien permanent avec Internet | Le support passe par `technique.log` envoyé par courriel et par une séance d'assistance ouverte par le praticien |
| **Mises à jour tirées par le PC et signées** (C5) | Seul flux sortant : du code public | Plan de C5 inchangé |
| **Licence expirée : 30 jours de grâce, puis export bloqué** (C8-T1) | Ne jamais arrêter un cabinet un matin | Les bilans déjà produits ne sont jamais touchés |
| **Évolutions : une révision annuelle incluse** (C9-T3) | Plafonner le temps de fabrication | À écrire dans les CGV (C0-T2) |
| **`journal.log` conservé six mois** | Minimisation | Clé `conservation_journaux_mois`, défaut 6 |
| **Modèles juridiques génériques** (C0-T2) | Aucune structure créée à ce jour | Champs à compléter à la création |
| **Les branches de tâche peuvent être poussées, `main` non** sans demande expresse | Le dépôt est public | Jamais de journal ni de donnée poussés ; mémoire `regle-publication-github` |
| **La fiche du prospect reste hors du dépôt** | Elle reprend son protocole | `.gitignore` |
| **D1 prime sur D3 dans C4-T2** | « Au plus six mois » ne se tient pas à quelques semaines près | Purge à l'écriture et par un fil périodique |
| **Le mot de passe de `--config` reste obligatoire** (C2-T1) | Le rendre facultatif rouvrait un audit d'authentification | La documentation dit de retaper le mot de passe actuel |

## État des tests

**Avant :** 134 tests au 20 octobre (99 Python, 35 Node).

**Après :**
- **Python :** 219 tests, verts en mode normal et sous `-O`, 2 sautés hors
  Windows.
- **Node :** dix suites, toutes vertes.
- **CI :** verte sur Linux, macOS et Windows, en Python 3.9 et 3.13.

**Ce qui est couvert de nouveau :**
- la concurrence de l'export ;
- la pagination ;
- la version ;
- les scripts d'installation, dont une exécution réelle de PowerShell en CI ;
- la conservation des journaux (`tests/test_conservation.py`, 81 tests).

Chaque garde ajoutée a été mise en échec par mutation.

## Constats de sécurité

**C2-T1 :** audit conforme sous réserve, puis revue À CORRIGER. Les suites
ont tout fermé ; voir l'addendum de `docs/revues/C2-T1.md`.

**C3-T3a :** audit conforme sous réserve, constats fermés, revue À LIVRER.
- **Reporté dans C3-T3 :** la tâche planifiée exécute sous SYSTEM un dossier
  et un `pythonw.exe` qu'un compte standard peut modifier. C'est une
  élévation de privilège possible : l'installateur devra poser les droits et
  installer Python pour tous les utilisateurs.

**C4-T2 :** conforme après deux passes.
- **Défaut corrigé :** un journal tenu ouvert sous Windows décalait toute la
  chaîne d'archives à chaque écriture.
- **Limite acceptée :** une barrière au rang 1 bloque la rotation. Elle est à
  reprendre dans C0-T2.

## Ce qui reste en suspens

- **Essai de C3-T3a sur une VM Windows propre (8.9)** et vérification au
  cabinet pilote (8.10), fiche `docs/essais/C3-T3a-windows.md`. Il faut une VM
  et une visite. **Le paquet ne part pas à Bordeaux avant.**
- **Favori de secours sur la tablette du cabinet pilote**, en attente depuis le
  19 octobre ; c'est lui qui bloque C1-T4.
- **Annonce à la praticienne avant sa mise à jour :** l'historique de
  `journal.log` depuis août formera une archive supprimée en bloc vers
  février 2027.
- **Questions au formateur :** l'orthographe de « Brazlawski », le sens de
  « DUR HOMO / MOU CONTRO / BOUCHE INDIFFÉRENT », le « H contrôle » du
  Romberg, et le calcul de l'indice de labilité /7.
- **`main` n'est pas poussé :** il le sera sur décision de Baptiste.
- **L'ancienne branche distante `c3-t3a-racine-installation`** est périmée,
  remplacée par `-2`. Une poussée forcée a été refusée, à juste titre.
- **Critère « trente exécutions » de C7-T5 :** dix seulement à ce jour.

## Prochaine étape recommandée

**C1-T6, le type `grille`.** C'est lui qui rend la fiche du prospect
fabricable dans le moteur.

```
/lancer-tache C1-T6
```

## À savoir pour la prochaine session

- **`gh` :** une variable `GITHUB_TOKEN` invalide traîne dans l'environnement
  et masque le trousseau. Préfixer par `env -u GITHUB_TOKEN`.
- **La CI ne part que sur `main`, sur une pull request ou à la main.** Une
  branche poussée ne lance rien : il faut
  `env -u GITHUB_TOKEN gh workflow run tests.yml --ref <branche>`.
- **Les commits non poussés n'avaient jamais tourné en CI.** C'est ainsi que
  la régression Windows de C7-T5 est restée invisible deux semaines. Ne pas
  laisser `main` local trop longtemps sans CI.
- **Un harnais de mutation peut mentir.**
  - `$?` lu après un `printf` donne le code du `printf`.
  - Sous zsh, une commande rangée dans une variable n'est pas découpée en mots.
  - Une mutation mal placée, par exemple le bloc `-Verifier` déplacé *avant*
    l'effet au lieu d'après, ne prouve rien.

  Toujours faire tourner un **témoin** sans mutation, et lire le code de
  retour du test lui-même.
- **Le classificateur de permissions refuse les mutations faites en place**
  sur `serveur.py`, ainsi que les poussées forcées. Muter une copie faite par
  `git ls-files -z --cached --others --exclude-standard`, et pousser sous un
  nouveau nom de branche plutôt que de réécrire.
- **Un agent coupé par une limite d'usage reprend par `SendMessage`.** Avant
  toute autre chose, vérifier qu'aucune mutation n'est restée dans le dépôt.
- **Une mutation qui provoque un interblocage fige la suite.** C'est un échec,
  mais pas un échec propre. Préférer une garde statique (arbre syntaxique) qui
  rougit sans attendre.
- **Le pire piège de la session, encore une fois : les listes tenues à la
  main.** Celles des gardes de C4-T2 oubliaient deux fonctions ajoutées après
  l'audit. La dérivation par l'arbre syntaxique est la réponse.
