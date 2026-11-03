# Contrat C3-T3a — Corriger le calcul de racine des scripts d'installation

**Chantier :** C3  **Effort estimé :** M  **Date :** 2026-11-03
**Décisions bloquantes :** aucune

> **Note d'effort.** `docs/ROADMAP.md:651` annonce S. La correction elle-même
> tient en une ligne ; ce qui porte l'effort à M, c'est la garde qui doit mordre
> **sans PowerShell** sur le poste de développement, l'exécution réelle à sec en
> intégration continue Windows, et la double mise en échec (mode normal et `-O`).
> Pas de découpage : rien de tout cela ne se livre séparément.

> **Critère hors de portée de l'implémenteur.** L'essai sur une VM Windows
> propre (critère 8.9) et la lecture de la tâche planifiée du cabinet pilote
> (critère 8.10) demandent une machine Windows. L'implémenteur prépare le
> protocole et la fiche à remplir ; il **ne coche pas** ces deux cases. La tâche
> est livrable au dépôt sans elles, **pas au prospect**.

---

## 1. Objectif

Après cette tâche, `installer-demarrage.ps1` prend pour racine **le dossier qui
le contient** — celui où le paquet le dépose, à côté de `serveur\` et
`formulaire\` — et non plus le dossier parent. Un test Python, qui tourne
partout sans PowerShell, évalue le calcul de racine de chaque script `.ps1`
**tel que le paquet réel le livre** et échoue si la racine obtenue ne contient
pas `serveur/serveur.py`. Sous Windows, un second test exécute réellement le
script, à sec (`-Verifier`), sans tâche planifiée ni pare-feu.

## 2. Pourquoi

C'est le **premier geste de l'installation à distance du prospect de Bordeaux**
(`docs/ROADMAP.md:28-31`, `:663-664`) : le script s'arrêterait sur
« serveur\serveur.py introuvable » devant un praticien, au téléphone, avant
toute autre étape. Une installation à distance ratée au premier script ruine
l'argument « installé pour vous » (`docs/projection.md`, modèle *done for you*).

Le script n'a jamais tourné ailleurs qu'au cabinet pilote
(`docs/projection.md:36`), et l'intégration continue n'en vérifie que la
syntaxe (`.github/workflows/tests.yml`, job `scripts-windows`). Le défaut est
précisément du type que le dépôt connaît : une hypothèse jamais mise en échec.

C3-T3 (installateur en un geste) absorbera ce script ; d'ici là, c'est lui qui
installe. Ne pas attendre C3-T3 pour le corriger.

## 3. État actuel

Vérifié le 3 novembre 2026, `HEAD` = `9cb4447`. `fiche_presentation.html`
(non suivi) est sans rapport : **ne pas le commiter**.

**Travail concurrent dans l'arbre.** Pendant la rédaction de ce contrat, une
autre tâche (pied de page de version : `formulaire/version.json`,
`tests/test_version.*`) a modifié sans commiter `outils/faire-paquet.sh`,
`serveur/serveur.py`, `.github/workflows/tests.yml` et quatre autres fichiers.
**Ne pas commencer tant que ce travail n'est pas commité** : C3-T3a touche
`faire-paquet.sh`, et un `git add` mêlerait les deux tâches. Les numéros de
ligne de `faire-paquet.sh` cités ici (`:12-14`, `:26-27`, `:54`) ont été
revérifiés après cette modification.

**Le défaut.**
- `installer-demarrage.ps1:26` : `$racine  = Split-Path -Parent $PSScriptRoot`.
  `$PSScriptRoot` est le dossier du script ; la racine est donc son **parent**.
- `installer-demarrage.ps1:27` : repli `Split-Path -Parent $MyInvocation.MyCommand.Path`,
  soit **le dossier du script lui-même**. Les deux lignes ne calculent pas le
  même dossier : c'est la preuve interne que la ligne 26 est fautive. Le repli
  est par ailleurs mort : `$PSScriptRoot` existe dans tout script depuis
  PowerShell 3.0, et `#Requires -RunAsAdministrator` (`:19`) exige déjà 4.0.
- Origine probable : la formule de `RACINE` dans `serveur/serveur.py` (l. 40-41 à ce jour)
  (« Le script vit dans serveur/ : la racine du projet est le dossier
  parent »), juste pour un fichier rangé dans `serveur/`, transplantée dans un
  script rangé à la racine.
- `:28-29` : `serveur\serveur.py` et `config.json` sont joints à `$racine` ;
  `:31-36` lèvent « introuvable » s'ils manquent. Le message de `:32` ne dit pas
  **où** le script a cherché : c'est ce qui rend le défaut indiagnostiquable au
  téléphone.
- `:57` : `-WorkingDirectory $racine`, et l'argument est le chemin absolu
  `$serveur`. Une racine fausse mais existante enregistrerait donc une tâche
  pointant ailleurs, sans erreur.

**Où le script est livré, et où la doc dit de le lancer.**
- `outils/faire-paquet.sh:26` copie les deux `.ps1` dans `"$PAQUET/"`, à côté
  de `formulaire/` et `serveur/` (`:27`) ; `:54` zippe le dossier
  `BilanPosturo-AAAA-MM-JJ/`. Le commentaire `:12-14` affirme que « les scripts
  calculent leurs chemins à partir de leur propre emplacement » : faux pour ce
  script.
- `docs/LISEZMOI.txt:12-15` et `:51-56` (et `READ-ME-FIRST.txt:56-58`) : renommer
  le dossier en `C:\BilanPosturo`, puis lancer `installer-demarrage.ps1` par
  clic droit. `docs/Mode_emploi.md:140-150`, `docs/USER-GUIDE.md:134-146`,
  `README.md:129-136` : `.\installer-demarrage.ps1` depuis le dossier du projet.
  **Toutes s'accordent : le script se lance depuis la racine de l'application.**
  Après correction, le code rejoint la documentation ; **le dossier de lancement
  ne change pas.**
- La même erreur vaut dans le dépôt lui-même (script à la racine) : il
  n'existe **aucune** disposition livrée où la ligne 26 trouve `serveur\`.

**Les deux autres lanceurs.**
- `desinstaller-demarrage.ps1` (30 l.) ne calcule **aucun chemin** : il
  n'utilise que le nom de tâche `BilanPosturo` (`:16-24`). Non affecté, **non
  modifié**.
- `demarrer-serveur.bat:5` : `cd /d "%~dp0"`, soit le dossier du `.bat`
  lui-même, puis `python serveur\serveur.py` en relatif (`:8`). **Correct.**
  Hors périmètre de modification, mais couvert par le test en lecture.

**L'historique, et ce qu'il dit du cabinet pilote.**
`git log --follow -- installer-demarrage.ps1` ne rend que deux commits :
`e9fd8ee` (14 octobre 2026, création, **déjà à la racine, déjà avec la ligne
26**) et `5230ceb` (C6-T4, renormalisation sans changement de contenu). Le
script n'a donc jamais vécu ailleurs dans Git. Trois hypothèses pour
« il a tourné au cabinet pilote » :

| | Hypothèse | Ce qui la rend plausible | Ce qui se passe après correction |
|---|---|---|---|
| **H1** | **Paquet dézippé à l'intérieur de l'installation existante** : `C:\BilanPosturo\BilanPosturo-2026-10-14\installer-demarrage.ps1`. Le parent est alors `C:\BilanPosturo`, qui contient `serveur\` **et** `config.json`. | Le 14 octobre était une **mise à jour** d'une installation d'août, pas une installation neuve : `config.json` n'est pas dans le paquet et ne pouvait exister que dans l'ancien dossier. Le script a réussi *parce que* la ligne 26 remontait d'un cran. | Relancé depuis le sous-dossier, le script corrigé s'arrête sur « config.json introuvable » (le sous-dossier n'en a pas) — **avant** tout `Register-ScheduledTask`. Arrêt sûr, aucune tâche modifiée. |
| H2 | Tâche enregistrée à la main, commandes saisies une à une. | Les commandes de `Mode_emploi.md:152-157` montrent une familiarité avec `ScheduledTask`. | Sans effet. |
| H3 | Le script n'a jamais tourné ; le serveur démarre encore par le `.bat`. | `docs/projection.md:390` donne la tâche pour « livrée », sans preuve d'exécution. | Sans effet ; la tâche reste à installer. |

**Hypothèse retenue : H1**, la seule qui explique un succès avec le code tel
quel. **À confirmer** par une lecture seule au cabinet (critère 8.10) :
```powershell
Get-ScheduledTask -TaskName BilanPosturo | Select-Object -ExpandProperty Actions |
    Format-List Execute, Arguments, WorkingDirectory
Get-ChildItem C:\BilanPosturo -Directory | Select-Object Name
```
H1 est confirmée si `WorkingDirectory` vaut `C:\BilanPosturo` **et** qu'un
sous-dossier `BilanPosturo-AAAA-MM-JJ` existe. Aucune de ces commandes ne lit
de donnée patient.

**Tests existants concernés.** `tests/test_serveur.py:226-277`
(`PortabiliteWindows`) exige BOM UTF-8 (`:238`) et CRLF (`:251`) sur **tout
`.ps1` à la racine**. Le contrôle cp1252 (`:262`) ne porte que sur
`serveur.py` et `generer_autorite.py`, pas sur les `.ps1`.
`tests/test_paquet.py:39-89` fabrique déjà le paquet en bac à sable (sauté sans
`sh`/`zip`/`unzip`). Le job `test` de la CI tourne aussi sur `windows-latest`
(Python 3.9 et 3.13) : un test Python réservé à Windows y est donc exécuté
**sans toucher au workflow**.

## 4. Périmètre

### Dans le périmètre
- Corriger le calcul de `$racine` dans `installer-demarrage.ps1` et préciser
  le message d'erreur « introuvable ».
- Ajouter à ce script un commutateur `-Verifier` : toutes les vérifications
  préalables, puis sortie **avant** tâche planifiée et pare-feu.
- Corriger le commentaire faux de `outils/faire-paquet.sh:12-14`.
- Un nouveau fichier de test (statique, toutes plateformes + exécution réelle
  sous Windows).
- Deux lignes de documentation de maintenance sur `-Verifier` (FR et EN).
- La fiche d'essai Windows à remplir (`docs/essais/C3-T3a-windows.md`).

### Hors périmètre
- `desinstaller-demarrage.ps1` et `demarrer-serveur.bat` : **lus** par le test,
  **pas modifiés**.
- Toute autre évolution du script (IP fixe, QR code, vérification de
  `dossier_pdf` sous SYSTEM…) : c'est C3-T3.
- Le nettoyage du sous-dossier éventuel du cabinet pilote (H1) : geste de
  maintenance à décider après le critère 8.10, pas une modification de code.
- La procédure de recette générale (C3-T4).
- Le job `scripts-windows` du workflow : inchangé.
- La mise en accents des messages du script : il est délibérément écrit sans
  accents (hors « »), on garde cette convention.

## 5. Fichiers touchés

| Fichier | Nature | Remarque |
|---|---|---|
| `installer-demarrage.ps1` | modifié | `:26-27`, `:32`, ajout `param` et sortie `-Verifier`, en-tête. **CRLF + BOM conservés sur disque.** |
| `outils/faire-paquet.sh` | modifié | commentaire `:12-14` seulement |
| `tests/test_scripts_installation.py` | nouveau | deux classes, voir §9 |
| `docs/Mode_emploi.md` | modifié | section Maintenance, après `:145` |
| `docs/USER-GUIDE.md` | modifié | miroir anglais, après `:141` |
| `docs/essais/C3-T3a-windows.md` | nouveau | protocole VM + lecture au cabinet, résultats vides |
| `desinstaller-demarrage.ps1`, `demarrer-serveur.bat` | **inchangés** | vérifié par `git diff --quiet` |

## 6. Plan d'implémentation

**Avant toute chose** : copier `installer-demarrage.ps1` hors du dépôt
(`cp installer-demarrage.ps1 "$SCRATCH/installer-original.ps1"`). Toutes les
restaurations de cette tâche se font par `cp`, jamais par `git checkout`.

1. **Écrire d'abord le test statique** (`RacineDesScriptsDansLePaquet`, §7 D3),
   contre le script **non corrigé**.
   *Vérification* : `python3 -m unittest tests.test_scripts_installation -v`
   échoue sur `installer-demarrage.ps1`, avec un message qui cite la racine
   calculée et l'absence de `serveur/serveur.py`. Consigner la sortie.

2. **Corriger `installer-demarrage.ps1:26-27`** : remplacer les deux lignes par
   ```powershell
   $racine = $PSScriptRoot
   if (-not $racine) {
       throw "Emplacement du script inconnu. Lancer le fichier lui-meme (clic droit > Executer avec PowerShell), ne pas copier son contenu dans une console."
   }
   ```
   *Vérification* : l'étape 1 passe ; `PortabiliteWindows` passe.

3. **Préciser le message `:32`** :
   `throw "serveur\serveur.py introuvable dans $racine. Lancer ce script depuis le dossier de l'application, celui qui contient serveur\ et formulaire\."`
   Idem pour `:35` : inclure `$racine` dans le message `config.json introuvable`.
   *Vérification* : `grep -c 'introuvable dans \$racine' installer-demarrage.ps1` rend 2.

4. **Ajouter `-Verifier`.** Juste après le bloc d'aide (`:17`), avant
   `#Requires` : `param([switch]$Verifier)`. Après le bloc `Write-Host` des
   lignes `:49-52`, insérer :
   ```powershell
   if ($Verifier) {
       Write-Host "Verification seulement : aucune tache planifiee ni regle de pare-feu n'a ete modifiee."
       exit 0
   }
   ```
   Documenter le commutateur dans l'en-tête `<# … #>`.
   *Vérification* : `grep -n 'Register-ScheduledTask\|New-NetFirewallRule\|Start-ScheduledTask' installer-demarrage.ps1`
   ne rend que des numéros de ligne **supérieurs** à celui du `exit 0` de
   `-Verifier`.

5. **Contrôler l'encodage sur disque.** Si l'éditeur a écrit en LF ou retiré le
   BOM, le rétablir (`python3 -c` qui relit en `utf-8-sig` et réécrit avec BOM
   et `\r\n`).
   *Vérification* : `python3 -m unittest tests.test_serveur.PortabiliteWindows`
   passe, et `git diff --numstat HEAD -- installer-demarrage.ps1` rend moins de
   25 lignes ajoutées (au-delà, ce sont des fins de ligne : C6-T4 à refaire).

6. **Écrire le test d'exécution Windows** (`ExecutionReelleSousWindows`, §7 D4).
   Sur le Mac il est sauté ; il sera éprouvé en CI à l'étape 9.

7. **Corriger le commentaire `outils/faire-paquet.sh:12-14`** pour qu'il dise
   vrai : les scripts livrés à la racine du paquet prennent pour racine leur
   propre dossier, et `tests/test_scripts_installation.py` le vérifie sur
   l'archive produite. Aucune ligne exécutable de ce fichier ne change.
   *Vérification* : `git diff HEAD -- outils/faire-paquet.sh | grep '^[-+][^#-+]'`
   ne rend rien.

8. **Mises en échec**, chacune sur copie sauvegardée, restaurée par `cp`, rejouée
   en mode normal **et** sous `python3 -O`. Consigner les 2 × 6 résultats dans
   `docs/audits/C3-T3a.md` (section « mises en échec ») :
   - M1 : rétablir `Split-Path -Parent $PSScriptRoot` → le test statique rougit.
   - M2 : rétablir l'ancien repli `:27` **seul** avec un `$racine` principal
     correct → doit rester vert (repli cohérent) ; puis un repli
     `Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)` →
     rougit (toutes les affectations sont évaluées, pas seulement la première).
   - M3 : écrire `$racine = Resolve-Path "$PSScriptRoot\.."` → rougit avec
     « forme non reconnue » (vocabulaire fermé, D3).
   - M4 : dans `faire-paquet.sh`, livrer les `.ps1` dans `"$PAQUET/outils/"` →
     rougit (la position vient de l'archive, pas d'une constante).
   - M5 : ajouter `$racine = Split-Path -Parent $PSScriptRoot` dans
     `desinstaller-demarrage.ps1` → rougit.
   - M6 : remplacer `%~dp0` par `%~dp0..` dans `demarrer-serveur.bat` → rougit.
   Après restauration : `git status --short` ne montre que les fichiers du §5.

9. **Éprouver le test Windows en CI.** Pousser sur une branche ; dans le journal
   des deux jobs `windows-latest` du workflow, les tests
   `ExecutionReelleSousWindows` doivent apparaître **`ok`** — ni `skipped`, ni
   en échec sur `#Requires -RunAsAdministrator`. Puis pousser un commit de
   mutation M1 sur la même branche : ils doivent rougir. Retirer ce commit
   (`git revert` ou réécriture de la branche avant fusion). Consigner les liens
   des deux exécutions dans l'audit.
   *Si* le lanceur n'est pas administrateur : ne **pas** transformer le test en
   saut ; faire échouer le test avec un message explicite et remonter au
   donneur d'ordre (la question devient : étape de CI élevée ou retrait de
   `#Requires` en mode `-Verifier` — décision qui n'appartient pas à
   l'implémenteur).

10. **Documentation.** `docs/Mode_emploi.md`, section « Le démarrage
    automatique », après le bloc de `:144-146` : une phrase et le bloc
    ```powershell
    .\installer-demarrage.ps1 -Verifier   # contrôle seul, ne modifie rien
    ```
    à utiliser avant une installation à distance. Miroir anglais dans
    `docs/USER-GUIDE.md` après `:141`. Le dossier de lancement ne change pas :
    **aucune autre retouche** de `LISEZMOI.txt`, `READ-ME-FIRST.txt` ni
    `README.md`.

11. **Fiche d'essai.** Écrire `docs/essais/C3-T3a-windows.md` : le protocole du
    critère 8.9 et les commandes du critère 8.10, avec des champs de résultat
    **vides** (date, version de Windows, sortie, opérateur). Patient fictif
    uniquement ; aucune adresse IP du cabinet pilote ne doit y être recopiée.

## 7. Décisions de conception

**Tranchées.**
- **D1 — `$racine = $PSScriptRoot`, et non une recherche ascendante de
  `serveur\`.** Chercher « le premier parent qui contient `serveur\` »
  réussirait silencieusement dans le cas H1 en pointant sur l'**ancienne**
  installation. On veut l'inverse : un script lancé du mauvais dossier
  s'arrête, et dit où il a cherché.
- **D2 — Le repli `$MyInvocation` est supprimé**, remplacé par un `throw`
  explicite. Il était mort (PowerShell ≥ 4.0 imposé par `#Requires`) et, dans
  le seul cas où `$PSScriptRoot` est vide (contenu collé dans une console),
  `$MyInvocation.MyCommand.Path` l'est aussi.
- **D3 — Test statique : un évaluateur à vocabulaire fermé, appliqué à
  l'archive réelle.** Le test fabrique le paquet par `outils/faire-paquet.sh`
  dans un bac à sable (copie par `git ls-files -z`, **jamais** `copytree` du
  dépôt ni `cp -r`), extrait le zip, puis pour **chaque `.ps1` trouvé dans
  l'archive** (dérivé, pas listé à la main) :
  - relève toutes les affectations de `$racine` (y compris dans un `if`) ;
  - les évalue avec la position réelle du script dans l'archive, selon une
    grammaire fermée : `$PSScriptRoot` → dossier du script ;
    `$MyInvocation.MyCommand.Path` → chemin du script ;
    `Split-Path -Parent <expr>` → parent ; `(<expr>)` → `<expr>`. **Toute
    autre forme fait échouer le test** (« forme non reconnue : étendre
    l'évaluateur ») ;
  - exige que chaque résultat contienne `serveur/serveur.py` **et**
    `formulaire/` dans l'archive extraite ;
  - exige que `$serveur` et `$config` soient `Join-Path $racine "serveur\serveur.py"`
    et `Join-Path $racine "config.json"` ;
  - un script sans affectation de `$racine` doit ne contenir **aucun** des
    jetons `$PSScriptRoot`, `$MyInvocation`, `Split-Path`, `Join-Path`,
    `Set-Location`, `..` ; sinon échec (« calcule un chemin non modélisé »).
  - garde anti-vide : au moins un `.ps1` avec au moins une affectation de
    `$racine` doit avoir été évalué, sinon échec.
  Pour `demarrer-serveur.bat` (aussi pris dans l'archive) : exactement une
  ligne `cd`, égale à `cd /d "%~dp0"`, et aucun `..` dans le fichier.
  Toutes les gardes en `self.assert*` / `self.fail`, **aucun `assert` nu**.
- **D4 — Test d'exécution Windows : un vrai `powershell.exe`, dans un dossier
  temporaire factice.** `skipUnless(os.name == "nt")` ; sous Windows, l'absence
  de `powershell` est un **échec**, pas un saut. Disposition : copie du `.ps1`
  du dépôt, un `serveur/serveur.py` **vide** (jamais le vrai serveur, qui n'est
  ni copié ni lancé), un `config.json` réduit à `{"port": 8000}`. Lancement :
  `powershell.exe -NoProfile -ExecutionPolicy Bypass -File <copie> -Verifier`.
  - cas nominal : code 0, ligne `Application : <chemin>` présente, et
    `os.path.samefile(<chemin>, dossier)` (les chemins temporaires du lanceur
    peuvent être abrégés en `RUNNER~1` : ne jamais comparer les chaînes) ;
  - cas script rangé dans `dossier/outils/` : code ≠ 0 et `introuvable` dans la
    sortie. Ce cas garde D1 : il rougit si quelqu'un remplace le correctif par
    une recherche ascendante.
  Sortie décodée avec `errors="replace"`.
- **D5 — `-Verifier` sort après la vérification de `pythonw.exe`**, pas avant :
  c'est la vérification la plus utile à distance, et `actions/setup-python`
  met `pythonw.exe` dans le `PATH` du lanceur.
- **D6 — Nouveau fichier de test** plutôt qu'une extension de
  `tests/test_paquet.py` : le sujet est le comportement des scripts, pas la
  composition de l'archive ; et la copie par `git ls-files -z` ne doit pas
  être mêlée à la copie par `copytree` existante (à corriger ailleurs, pas ici).

**Laissés à l'implémenteur.**
- Le découpage des lignes PowerShell en jetons dans l'évaluateur (regex ou
  petit analyseur), tant que toute forme inconnue échoue.
- Le libellé exact des messages de test et de la phrase de documentation.
- Partager ou non la fabrication du paquet entre les deux classes
  (`setUpModule`).

## 8. Critères d'acceptation

- [ ] **8.1 La racine est le dossier du script** :
      `grep -n 'Split-Path -Parent \$PSScriptRoot' installer-demarrage.ps1` ne
      rend rien, et `grep -c '^\$racine = \$PSScriptRoot' installer-demarrage.ps1` rend 1.
- [ ] **8.2 Le test statique passe** :
      `python3 -m unittest tests.test_scripts_installation -v` et
      `python3 -O -m unittest tests.test_scripts_installation -v` passent, et
      leur sortie montre `RacineDesScriptsDansLePaquet` en `ok` (pas `skipped`).
- [ ] **8.3 Le test statique a été mis en échec** : les mutations M1 à M6
      (étape 8), × 2 modes, sont consignées dans `docs/audits/C3-T3a.md` avec
      le résultat attendu (M2 premier volet : vert ; tous les autres : rouge).
      `git status --short` ne montre ensuite que les fichiers du §5.
- [ ] **8.4 L'exécution réelle sous Windows passe en CI** : dans les deux jobs
      `windows-latest` du workflow `tests`, `ExecutionReelleSousWindows` affiche
      ses deux tests en `ok` ; lien de l'exécution consigné dans l'audit.
- [ ] **8.5 … et a été mise en échec en CI** : la même branche avec M1 fait
      rougir le test nominal sous Windows ; lien consigné ; le commit de
      mutation n'est pas dans `main` (`git log main --oneline -- installer-demarrage.ps1`
      ne le montre pas).
- [ ] **8.6 `-Verifier` ne modifie rien** : dans le script, tout appel à
      `Register-ScheduledTask`, `Start-ScheduledTask`, `New-NetFirewallRule` est
      situé après le `exit 0` du bloc `-Verifier` (vérifiable par
      `grep -n`, étape 4).
- [ ] **8.7 Encodage préservé, rien d'autre touché** :
      `python3 -m unittest tests.test_serveur.PortabiliteWindows` passe ;
      `git diff --quiet HEAD -- desinstaller-demarrage.ps1 demarrer-serveur.bat`
      rend 0 ; `git diff --numstat HEAD -- installer-demarrage.ps1` < 25 ajouts.
- [ ] **8.8 Suite complète verte** : `python3 -m unittest discover -s tests`
      et `python3 -O -m unittest discover -s tests` passent ; tous les tests
      Node du workflow passent ; job `scripts-windows` vert.
- [ ] **8.9 Essai réel sur VM Windows propre — consigné par Baptiste, pas par
      l'implémenteur.** Windows 10 ou 11 sans installation antérieure, Python
      3.9+ avec « Add python.exe to PATH ». Paquet produit par
      `outils/faire-paquet.sh`, installé selon `docs/LISEZMOI.txt` étapes 1 à 8
      dans `C:\BilanPosturo`. Puis, en administrateur, depuis `C:\BilanPosturo` :
      (a) `.\installer-demarrage.ps1 -Verifier` → code 0, `Application : C:\BilanPosturo` ;
      (b) clic droit > Exécuter avec PowerShell → « Le serveur ecoute sur le port » ;
      (c) la commande `Get-ScheduledTask … Format-List Execute, Arguments, WorkingDirectory`
      du §3 montre `C:\BilanPosturo` ;
      (d) redémarrage de la VM, `https://<ip>:<port>/sante` répond sans session
      ouverte ; (e) `.\desinstaller-demarrage.ps1` retire la tâche.
      Résultats datés dans `docs/essais/C3-T3a-windows.md`.
- [ ] **8.10 Hypothèse H1 tranchée — consigné par Baptiste.** Les deux
      commandes en lecture seule du §3 passées au cabinet pilote, résultat
      (H1 confirmée, H2, ou H3) inscrit dans `docs/essais/C3-T3a-windows.md`,
      sans adresse IP ni nom de patient.

Les critères 8.1 à 8.8 ferment la tâche au dépôt ; 8.9 conditionne l'envoi du
paquet au prospect de Bordeaux.

## 9. Tests à écrire

| Test | Fichier | Ce qu'il doit échouer à faire passer aujourd'hui |
|---|---|---|
| `RacineDesScriptsDansLePaquet.test_racine_contient_serveur` | `tests/test_scripts_installation.py` | **Échoue sur `HEAD`** : `Split-Path -Parent $PSScriptRoot` évalué depuis `BilanPosturo-…/installer-demarrage.ps1` donne le dossier d'extraction, sans `serveur/`. |
| `…test_forme_inconnue_refusee` | idem | Passe sur `HEAD` ; rougit sur M3. Garde le vocabulaire fermé. |
| `…test_script_sans_racine_ne_calcule_aucun_chemin` | idem | Passe sur `HEAD` (le désinstalleur) ; rougit sur M5. |
| `…test_lanceur_bat_dans_son_dossier` | idem | Passe sur `HEAD` ; rougit sur M6. |
| `…test_au_moins_un_script_evalue` | idem | Garde anti-vide : rougit si l'archive ne contient plus aucun `.ps1` à racine. |
| `ExecutionReelleSousWindows.test_verifier_depuis_la_racine` | idem | **Échoue sur `HEAD`** sous Windows (pas de `-Verifier`, et racine fausse). |
| `ExecutionReelleSousWindows.test_lance_d_un_sous_dossier_s_arrete` | idem | Rougit si D1 est contournée par une recherche ascendante. |

## 10. Points de sécurité à l'attention de l'auditeur

- **Exécution privilégiée chez le client** : le script tourne en administrateur et enregistre une tâche **SYSTEM** ; une racine fausse mais existante (cas H1) ferait exécuter sous SYSTEM un `serveur.py` autre que celui livré. D1 l'interdit ; vérifier qu'aucune recherche ascendante ne s'est glissée.
- **`-Verifier`** : s'assurer qu'aucun effet de bord (tâche, pare-feu, `Start-ScheduledTask`) n'est atteignable avant son `exit 0`.
- **Test Windows en CI** : il exécute un `.ps1` en administrateur sur le lanceur ; vérifier qu'il ne lance que la copie avec `-Verifier` et qu'aucun `serveur.py` réel n'est copié ni exécuté.
- **Bac à sable du test statique** : copie par `git ls-files -z` uniquement ; vérifier qu'aucune clé, `config.json`, journal ou bilan réel de la racine n'y entre (piège du 20 octobre).
- **Fiche d'essai** : ni adresse IP du cabinet pilote, ni nom de patient, ni contenu de `journal.log`.
- Messages d'erreur : ils affichent `$racine`, un chemin local de l'installation — information non sensible, affichée à l'administrateur seul, et absente des journaux.

## 11. Retour arrière

Le script n'est exécuté qu'à la main, une fois, à l'installation : **la
correction n'a aucun effet sur le cabinet pilote tant que personne ne relance
le script**, et la tâche planifiée déjà enregistrée garde ses chemins absolus.
Aucun retour arrière n'est donc nécessaire en consultation.

Si un défaut apparaissait lors d'une installation : dans le dossier de
l'application, remplacer `installer-demarrage.ps1` par la version du paquet
précédent (ou `git show 9cb4447:installer-demarrage.ps1` en CRLF + BOM), ou
plus simplement revenir au lancement manuel par `demarrer-serveur.bat`, qui
n'est pas touché. Au dépôt : `git revert` du commit de la tâche.

## 12. Risques

| Risque | Probabilité | Conséquence | Parade |
|---|---|---|---|
| L'éditeur réécrit le `.ps1` en LF ou sans BOM | Moyenne | PowerShell 5.1 écorche les messages ; `PortabiliteWindows` rouge | Étape 5 et critère 8.7 |
| Le lanceur Windows de CI n'est pas administrateur | Faible | `#Requires` fait échouer le test d'exécution | Étape 9 : échec explicite et remontée, jamais un saut |
| Le test statique est sauté partout (`zip` absent) et personne ne le voit | Faible | Garde vide | Critère 8.2 exige `ok` dans la sortie ; jobs Linux et macOS ont `zip` |
| H1 vraie et quelqu'un relance le script corrigé depuis le sous-dossier du cabinet | Faible | Arrêt sur « config.json introuvable dans … », sans rien modifier | Comportement voulu (D1) ; le message dit où relancer |
| Évaluateur trop permissif, qui accepte une forme qu'il ne comprend pas | Moyenne | Garde qui ne garde rien | Vocabulaire fermé (D3) et mutation M3 |
| Chemins abrégés (`RUNNER~1`) sur le lanceur Windows | Moyenne | Faux échec de comparaison | `os.path.samefile` (D4) |
| Le critère 8.9 n'est jamais fait faute de VM | Moyenne | Paquet envoyé au prospect sur la foi d'un test de CI | 8.9 conditionne explicitement l'envoi ; à porter dans la clôture |
