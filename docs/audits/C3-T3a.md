# Audit C3-T3a — Corriger le calcul de racine des scripts d'installation

**Date :** 2026-11-03  **Périmètre audité :** `18f857d..6aaffd4` — `installer-demarrage.ps1`, `outils/faire-paquet.sh` (commentaire), `tests/test_scripts_installation.py`, `docs/Mode_emploi.md`, `docs/USER-GUIDE.md`, `docs/essais/C3-T3a-windows.md` ; lus en contexte : `desinstaller-demarrage.ps1`, `demarrer-serveur.bat`, `.gitignore`, `.gitattributes`.
**Verdict :** CONFORME SOUS RÉSERVE

> **Note sur le périmètre.** L'audit a commencé sur des modifications non
> commitées ; le commit `6aaffd4` a été créé pendant l'audit, avant ce rapport.
> Vérifié : les fichiers de l'arbre sont identiques octet pour octet à ceux qui
> ont été audités et soumis aux mutations (`cmp`). Le blob de
> `installer-demarrage.ps1` est en LF dans l'index (normalisation
> `*.ps1 text eol=crlf`), en CRLF + BOM sur disque, comme attendu.
> `desinstaller-demarrage.ps1` et `demarrer-serveur.bat` sont inchangés
> (`git diff --quiet 18f857d HEAD` rend 0).

**Réserves qui portent le verdict.** (1) Les critères 8.4 et 8.5 — exécution
réelle sous Windows en CI, puis mise en échec par M1 — ne sont pas remplis :
`ExecutionReelleSousWindows` n'a jamais tourné sur un vrai PowerShell, donc ni
l'acceptation de `param` avant `#Requires` par PowerShell 5.1, ni le code de
sortie de `-Verifier` ne sont prouvés. (2) Les critères 8.9 et 8.10 restent
ouverts et **conditionnent l'envoi au prospect**. (3) Constats Moyens ci-dessous.

## Constats

### Moyenne — « `-Verifier` ne modifie rien » n'est gardé par aucun test, et le test Windows modifierait la machine qui l'exécute
**Où :** `installer-demarrage.ps1:67-70` (sortie) et `:91`, `:102`, `:118` (effets) ; `tests/test_scripts_installation.py:372-403`.
**Scénario :** la propriété « aucun effet avant le `exit 0` » n'est vérifiée qu'à
la main, par `grep -n` (critère 8.6). J'ai joué deux mutations dans un bac à
sable :
- A4 : déplacer le bloc `if ($Verifier) { … exit 0 }` après `Register-ScheduledTask` → **toute la suite reste verte** (normal et `-O`). Sous Windows, `test_verifier_depuis_la_racine` passerait aussi : code 0, ligne `Application :` correcte — **après** avoir enregistré, avec `-Force`, une tâche SYSTEM `BilanPosturo` qui pointe vers un dossier temporaire supprimé aussitôt.
- A5 : retirer le `exit 0` → suite statique verte ; sous Windows, le script irait jusqu'à la tâche, la règle de pare-feu et `Start-ScheduledTask` avant d'échouer sur « n'ecoute pas encore » (`:129-133`).

Le test **exige** les droits administrateur (`:384-388`, échec explicite sinon).
Quiconque lance la suite sous Windows est donc poussé à le faire en élevé : sur
la VM de l'essai 8.9, ou sur un poste qui porte une vraie installation, la tâche
`BilanPosturo` existante est **écrasée** par `-Force`. Au redémarrage suivant, le
serveur ne démarre pas et la tablette ne joint plus le PC. Le même défaut atteint
aussi un client : `-Verifier` est désormais documenté comme le contrôle à passer
« avant une installation à distance » (`docs/Mode_emploi.md:152-158`).
**Propriété à rétablir :** l'ordre « sortie `-Verifier` avant tout effet » doit
être garanti par un test automatique qui rougit sur A4 et A5. Le test d'exécution
réelle ne doit pas pouvoir modifier la tâche planifiée ni le pare-feu de l'hôte,
même si le script testé régresse.

### Moyenne — Code exécuté sous SYSTEM depuis des emplacements modifiables par un compte standard (préexistant, rendu atteignable par la tâche)
**Où :** `installer-demarrage.ps1:37` (racine sans contrainte d'emplacement), `:57` (`pythonw.exe` pris dans le `PATH` de l'administrateur), `:74-82` (action SYSTEM, `RunLevel Highest`).
**Scénario :** avant la correction, le script échouait partout sauf dans la
disposition H1 : en pratique, il ne pouvait installer la tâche chez aucun
nouveau client. Après la correction, il l'installe là où on le lance, sans aucun
contrôle de l'emplacement ni des droits. Deux chemins mènent alors à SYSTEM :
- **Le dossier de l'application.** Un dossier créé sous `C:\` hérite par défaut, sous Windows 10/11, de `Authenticated Users : Modify` (`(OI)(CI)(IO)(M)`). Le cas est pire si le paquet est lancé depuis `Téléchargements`, ce qu'aucune vérification n'empêche puisque D1 accepte tout dossier contenant `serveur\` et `config.json`. Dans les deux cas, un processus du compte standard — pièce jointe piégée, ou autre utilisateur du PC — peut réécrire `serveur\serveur.py`, ou déposer un module qui masque un module de la bibliothèque standard dans `serveur\`, premier élément de `sys.path`. Au démarrage suivant, ce code s'exécute en SYSTEM et lit tous les bilans.
- **L'interpréteur.** L'installeur de python.org installe par défaut **pour l'utilisateur seul**, dans `%LOCALAPPDATA%\Programs\Python\…`, et y fait pointer le `PATH` de l'utilisateur. `Get-Command pythonw.exe` résout ce chemin, et la tâche SYSTEM exécute alors un binaire que le compte standard peut remplacer.

Le défaut n'est pas introduit par le diff, mais c'est cette tâche qui rend le
script utilisable chez le prospect. Le défaut n'est consigné nulle part comme
limite assumée : aucune occurrence dans `docs/` (`icacls`, ACL de fichiers,
installation de Python pour tous les utilisateurs). Point à confirmer sur la VM
de 8.9 : `icacls C:\BilanPosturo` et `(Get-Command pythonw.exe).Source`.
**Propriété à rétablir :** tout ce que la tâche SYSTEM exécute ou importe
(interpréteur, `serveur\`) doit être modifiable par les seuls administrateurs et
SYSTEM. `-Verifier` doit le contrôler, ou bien la limite doit être tranchée et
documentée avant l'envoi au prospect (C3-T3 ou C6).

### Faible — L'évaluateur à « vocabulaire fermé » ne voit que la forme littérale `$racine =`
**Où :** `tests/test_scripts_installation.py:71-91` (motif `\$racine\s*…=`).
**Scénario :** j'ai inséré après la ligne 37, l'une après l'autre :
`$script:racine = Split-Path -Parent $PSScriptRoot` (A1),
`${racine} = Split-Path -Parent $PSScriptRoot` (A2),
`Set-Variable -Name racine -Value (Split-Path -Parent $PSScriptRoot)` (A3).
Les trois rétablissent exactement le défaut d'origine, et le test statique reste
**vert** dans les deux modes. La grammaire est bien fermée sur les
**expressions** (M3 rougit), mais pas sur les **formes d'affectation**, qui
passent sans être vues. Le filet restant est le test Windows : il devrait rougir
sur A1 à A3 (racine sans `serveur\`), mais il n'a jamais tourné.
**Propriété à rétablir :** toute écriture de la variable `racine` que l'outil ne
sait pas évaluer doit faire échouer le test, comme le fait une expression
inconnue.

### Faible — Le contrôle du bac à sable tient une liste à la main, plus courte que `.gitignore`
**Où :** `tests/test_scripts_installation.py:208-217`.
**Scénario :** j'ai simulé, dans mon bac à sable, une copie par arborescence au
lieu de `git ls-files -z`, avec des fichiers **factices** :
`journal.log.1`, `technique.log.3`, `Bilan_entrants/Dupont.pdf` et
`cles-editeur/maj.key` passent sans alerte ; seul `config.json` est détecté.
C'est le piège « liste tenue à la main » de C4-T1. La protection réelle est
structurelle : la copie par `git ls-files -z` (`:142-159`), vérifiée et correcte.
Ce test n'est qu'un témoin, et il est aveugle à la moitié des motifs de
`.gitignore`.
**Propriété à rétablir :** le témoin doit dériver sa liste des motifs ignorés
(archives de journaux, `Bilan_entrants/`, `cles-editeur/`, `*.key` compris), et
avoir été vu rouge.

### Observation — Commit antérieur à l'audit
`6aaffd4` a été créé pendant l'audit, alors que le critère 8.3 (mutations
consignées ici) n'était pas rempli. Le contenu est identique à celui qui a été
audité. Le critère 8.5 demande un commit de mutation sur la branche : il ne doit
pas atteindre `main`.

### Observation — `param` avant `#Requires`
Selon la documentation de PowerShell, `#Requires` peut figurer sur n'importe
quelle ligne et `param` doit être la première instruction après les
commentaires : l'ordre retenu (`:22-26`) est donc a priori valide. Ce n'est pas
prouvé tant que 8.4 n'a pas tourné (voir réserve 1).

## Mises en échec (critère 8.3)

Bac à sable : copie du dépôt par `git ls-files -z` (plus le fichier de test, non
suivi au moment de la copie), `git init`, mutation **dans le bac à sable
seulement**. Restauration de chaque mutation par copie, vérifiée par `cmp`, puis
`git status --short` vide dans le bac à sable. Aucun fichier du dépôt n'a été
modifié. « Impl. » : résultat déclaré par l'implémenteur. « Audit » : rejoué par
l'auditeur, en mode normal **et** sous `python3 -O` (résultats identiques dans
les deux modes).

| # | Mutation | Attendu | Impl. (normal / `-O`) | Audit (normal / `-O`) | Test qui rougit |
|---|---|---|---|---|---|
| M1 | `$racine = Split-Path -Parent $PSScriptRoot` | rouge | rouge / rouge | **rouge / rouge** | `test_racine_contient_serveur` |
| M2a | ancien repli `$MyInvocation` seul, racine principale correcte | vert | vert / vert | **vert / vert** | — |
| M2b | repli `Split-Path -Parent (Split-Path -Parent $MyInvocation…)` | rouge | rouge / rouge | **rouge / rouge** | `test_racine_contient_serveur` |
| M3 | `$racine = Resolve-Path "$PSScriptRoot\.."` | rouge, « forme non reconnue » | rouge / rouge | **rouge / rouge** | `test_racine_contient_serveur` |
| M4 | `.ps1` livrés dans `$PAQUET/outils/` | rouge | rouge / rouge | **rouge / rouge** | `test_racine_contient_serveur` (`outils/installer-demarrage.ps1`) |
| M5 | `$racine = Split-Path -Parent $PSScriptRoot` dans le désinstalleur | rouge | rouge / rouge | **rouge / rouge** | `test_racine_contient_serveur`, et non `test_script_sans_racine…` comme le prévoit le §9. L'écart est logique : une fois `$racine` affectée, le script relève de l'évaluateur. La garde mord. |
| M6 | `%~dp0` → `%~dp0..` dans le `.bat` | rouge | rouge / rouge | **rouge / rouge** | `test_lanceur_bat_dans_son_dossier` |
| I1 | `Set-Location ..` dans le désinstalleur | rouge | rouge (mode non précisé) | **rouge / rouge** | `test_script_sans_racine_ne_calcule_aucun_chemin` |
| I2 | `$serveur = Join-Path $PSScriptRoot "..\serveur\serveur.py"` | rouge | rouge (mode non précisé) | **rouge / rouge** | `test_racine_contient_serveur` |
| A1 | `$script:racine = Split-Path -Parent $PSScriptRoot` | rouge | — | **vert / vert** | aucun → constat Faible |
| A2 | `${racine} = Split-Path -Parent $PSScriptRoot` | rouge | — | **vert / vert** | aucun → constat Faible |
| A3 | `Set-Variable -Name racine -Value (Split-Path -Parent $PSScriptRoot)` | rouge | — | **vert / vert** | aucun → constat Faible |
| A4 | bloc `-Verifier` déplacé après `Register-ScheduledTask` | rouge | — | **vert / vert** | aucun → constat Moyen |
| A5 | `exit 0` du bloc `-Verifier` retiré | rouge | — | **vert / vert** | aucun → constat Moyen |
| A6 | recherche ascendante `while (-not (Test-Path …serveur)) { $racine = Split-Path -Parent $racine }` | rouge | — | **rouge / rouge** | `test_racine_contient_serveur` (forme non reconnue) |
| A7 | copie par arborescence, fichiers factices ignorés par Git | rouge | — | **vert** pour `journal.log.1`, `technique.log.3`, `Bilan_entrants/`, `cles-editeur/*.key` ; rouge pour `config.json` | → constat Faible |

**Non rejoué, hors de portée sans Windows :** les critères 8.4 et 8.5 (CI
`windows-latest`, puis M1 en CI). Aucun lien d'exécution n'existe à ce jour.

Suite complète rejouée par l'auditeur : `python3 -m unittest discover -s tests`
et la même commande sous `-O` donnent 133 tests OK, dont 2 sautés (la classe
Windows) ; `PortabiliteWindows` est OK. Le diff du `.ps1` compte 22 ajouts
(< 25). Dans le diff de `faire-paquet.sh`, aucune ligne exécutable ne change.

## Rubriques sans constat

1. **Données de santé.** Les messages affichent `$racine` (`:45`, `:48`) et `Application :` (`:62`) dans la console de l'administrateur, et rien n'est écrit dans un journal ni dans `formulaire/`. La fiche d'essai interdit adresse IP du cabinet, nom de patient et contenu du journal, et n'en contient aucun. Les commandes de 8.10 ne listent que des dossiers de premier niveau, sans récursion.
2. **Surface exposée.** Sans objet : aucun changement de serveur, de route, de racine web ni de filtre d'extensions. La règle de pare-feu (`:101-107`, profil privé) n'a pas bougé.
3. **Authentification et cryptographie.** Sans objet. `config.json` n'est lu que pour son `port` ; aucun secret n'est affiché ni passé en argument. Le test Windows utilise un `config.json` factice `{"port": 8000}`.
4. **Écriture de fichiers.** Sans objet pour le dépôt de PDF. Bac à sable du test : `mkdtemp`, supprimé en cas d'échec (`:179-181`) et en `tearDownClass` ; le test Windows nettoie par `addCleanup`. Le `serveur.py` du test Windows est vide, et le vrai serveur n'est ni copié ni lancé (`:366-368`).
5. **Robustesse de service.** Le correctif lui-même ne crée aucune indisponibilité : relancé depuis le sous-dossier H1, le script s'arrête sur « introuvable dans … » **avant** toute modification (`:44-49`). D1 est respectée : aucune recherche ascendante (A6 rougit), et la tâche déjà enregistrée au cabinet garde ses chemins absolus. Le risque d'indisponibilité relève du premier constat Moyen.
6. **Côté navigateur.** Sans objet : aucun fichier de `formulaire/` touché.
7. **Chaîne d'approvisionnement.** Le paquet est fabriqué par `faire-paquet.sh` depuis l'arbre de travail ; le diff ne modifie aucune ligne exécutable. Le test fabrique le paquet à partir d'une copie par `git ls-files -z`, ce qui est correct. Rien ne change sur la préservation de `config.json`, des certificats ni de `bilans/`.
8. **Conformité.** Aucun stockage chez l'éditeur, aucune aide à la décision, aucun nouveau sous-traitant, aucune durée de conservation en jeu.

## Points à surveiller plus tard

- **Essai 8.9** : y ajouter `icacls C:\BilanPosturo`, `icacls` du dossier de `pythonw.exe` et la portée de l'installation de Python (pour l'utilisateur ou pour tous). Cela tranche le deuxième constat Moyen sur pièces.
- **H1 au cabinet pilote (8.10)** : si H1 se confirme, la tâche SYSTEM exécute le `serveur.py` d'**août**, à la racine, et non celui du paquet du 14 octobre resté dans le sous-dossier. La version réellement en service est à établir avant toute prochaine mise à jour.
- `demarrer-serveur.bat` est en LF dans l'arbre de travail, malgré `*.bat text eol=crlf`, et `faire-paquet.sh` copie l'arbre tel quel. Ce n'est pas un problème de sécurité ; à ranger avec la correction isolée des fins de ligne (C6-T4).
- Quand `C3-T3` absorbera ce script, le contrôle d'emplacement et de droits a toute sa place dans `-Verifier`, qui devient le premier geste de l'installation à distance.
