# Revue C3-T3a — Corriger le calcul de racine des scripts d'installation

**Date :** 2026-11-03  **Verdict :** À LIVRER (au dépôt ; pas au prospect, voir 8.9 et 8.10)
**Tests :** exécutés par moi sur la branche `c3-t3a-racine-installation-2`
(`0878abf`) : `python3 -m unittest discover -s tests` : 137 tests, OK, 2 sautés
(la classe Windows) ; la même sous `python3 -O` : 137, OK, 2 sautés ;
`npm test` : tout vert ; `python3 -m pyflakes serveur/ tests/` : aucune sortie.
`python3 -m unittest tests.test_scripts_installation -v` : les neuf tests de
`RacineDesScriptsDansLePaquet` en `ok` (aucun `skipped` sous macOS).
CI de la branche rebasée, run 41731923283 : sept jobs verts (dont
`windows-latest` en 3.9 et 3.13, `scripts-windows`, `ubuntu-latest` 3.9 et 3.13,
`macos-latest`).

Mutations rejouées par moi, sur sauvegarde hors dépôt restaurée par `cp`, `cmp`
vérifié, CRLF + BOM préservés (édition binaire), `git status --short` ne montre
ensuite que `fiche_presentation.html` : voir la section « Remarques ».

## Critères d'acceptation

| Critère | Vérifié par | Résultat |
|---|---|---|
| 8.1 Racine = dossier du script | `grep -n 'Split-Path -Parent \$PSScriptRoot' installer-demarrage.ps1` : rien ; `grep -c '^\$racine = \$PSScriptRoot'` : 1 | Rempli |
| 8.2 Test statique passe, en `ok`, normal et `-O` | exécution moi-même, sorties ci-dessus | Rempli (sous macOS ; voir remarque Mineur sur Windows) |
| 8.3 Mises en échec M1 à M6 × 2 modes consignées | table de `docs/audits/C3-T3a.md` ; M1 rejouée par moi : rouge ; et sur le `.ps1` de `main`, le test rougit avec « la racine calculée … ne contient pas serveur/serveur.py » (le test échoue bien sur le code d'avant) | Rempli. L'audit n'a pas été complété après le second commit (voir Important n°2) |
| 8.4 Exécution réelle Windows en CI | run 41731923283 (branche rebasée) : `test_verifier_depuis_la_racine` et `test_lance_d_un_sous_dossier_s_arrete` en `ok` sous `windows-latest` 3.13 (lu dans le journal), job 3.9 vert. Run 41730284715 (avant rebasage) : les deux tests en `ok` aussi, mais le run est rouge pour une autre raison (`TimeoutError` de `ServeurEnMarche`, le flake traité par C7-T5, absent de cette branche à l'époque) | Rempli. À consigner : **41731923283** comme preuve propre, 41730284715 en second |
| 8.5 … et mise en échec en CI par M1 | run 41730347550 (branche `c3-t3a-mutation-m1`, supprimée) : sous `windows-latest` 3.9, `test_verifier_depuis_la_racine` et `test_lance_d_un_sous_dossier_s_arrete` en FAIL. `git log main --oneline -- installer-demarrage.ps1` ne montre que `5230ceb` et `e9fd8ee` | Rempli |
| 8.6 `-Verifier` ne modifie rien | `grep -n` : `exit 0` à `:69`, `Register-ScheduledTask` `:91`, `New-NetFirewallRule` `:102`, `Start-ScheduledTask` `:118` ; et gardé par test (voir A4/A5 ci-dessous) | Rempli |
| 8.7 Encodage préservé, rien d'autre touché | `file` : « UTF-8 (with BOM), CRLF » ; `git diff --numstat main..HEAD` : 22 ajouts (< 25) ; `git diff --quiet main..HEAD -- desinstaller-demarrage.ps1 demarrer-serveur.bat` rend 0 ; `PortabiliteWindows` dans la suite verte ; l'unique ligne exécutable de `faire-paquet.sh` n'a pas bougé (diff = commentaires) | Rempli |
| 8.8 Suite complète verte | voir **Tests** ; job `scripts-windows` vert | Rempli |
| 8.9 Essai VM Windows propre | réservé à Baptiste ; fiche `docs/essais/C3-T3a-windows.md` : champs vides, aucune IP du cabinet, aucun nom de patient | **Ouvert** (conditionne l'envoi au prospect) |
| 8.10 H1 tranchée | idem, partie B de la fiche | **Ouvert** |

Partage Windows des tests statiques : assumé par le contrat. Son tableau des
risques (§12, ligne « sauté partout ») écrit que « jobs Linux et macOS ont `zip` »
et que 8.2 exige `ok` dans la sortie ; le journal Windows de la CI montre bien
les cinq tests qui fabriquent le paquet en `skipped 'sh/zip/unzip/git requis'`.
Le §1 (« tourne partout ») est plus fort que ce que le contrat accepte au §12 :
c'est une imprécision de rédaction, pas un défaut du code.

## Remarques

### Important — Le test Windows exécute le script en administrateur sans porter sa propre garde d'ordre de `-Verifier`
**Où :** `tests/test_scripts_installation.py:533-596` (classe `ExecutionReelleSousWindows`) ;
la garde est dans `RacineDesScriptsDansLePaquet.test_verifier_precede_les_effets_de_bord` (`:414`),
classe sautée sous Windows (`:298`).
**Problème :** le premier constat Moyen de l'audit demandait que « le test
d'exécution réelle ne puisse pas modifier la tâche planifiée ni le pare-feu de
l'hôte, même si le script testé régresse ». Le correctif a placé la garde dans la
classe qui exige `sh`, `zip`, `unzip`. Or le test d'exécution ne tourne que sous
Windows, où cette classe est sautée (confirmé dans le journal CI). Entrée : un
développeur lance la suite en administrateur sous Windows après avoir déplacé le
bloc `-Verifier` après `Register-ScheduledTask` (mutation A4). Effet : la garde ne
s'exécute pas, `test_verifier_depuis_la_racine` passe (code 0, ligne
`Application :` correcte), et la tâche SYSTEM `BilanPosturo` de la machine est
écrasée par `-Force`. Sur le poste de développement macOS et en CI Linux, la garde
rougit (je l'ai vérifié : A4 et A5 donnent 2 échecs chacune) ; le risque est donc
limité à la machine Windows d'un opérateur, par exemple la VM de 8.9.
**Attendu :** appeler `verifier_ordre_des_effets(_retirer_commentaires(_lire_script(SCRIPT_INSTALLATION)))`
dans `setUp` de `ExecutionReelleSousWindows`, avec échec avant tout lancement ;
c'est une fonction pure, sans dépendance au paquet.

### Important — L'audit n'a pas été mis à jour après le second commit, et les liens de CI exigés par 8.4/8.5 n'y sont pas
**Où :** `docs/audits/C3-T3a.md:15-20`, `:133-134`.
**Problème :** le rapport décrit encore comme ouverts les constats A1 à A5 et A7
(« vert / vert → constat »), et dit « Aucun lien d'exécution n'existe à ce jour ».
Le critère 8.4 exige « lien de l'exécution consigné dans l'audit », le 8.5 « lien
consigné ». Quiconque lit l'audit seul conclut que la tâche porte trois constats
non fermés et deux critères sans preuve.
**Attendu :** un addendum à l'audit (non fait par le réviseur) : fermeture des
trois constats par les mutations B1 à B3 et A4 du second commit, les liens
41731923283 (8.4), 41730347550 (8.5), 41730284715 (second témoin de 8.4), et la
raison de la couleur rouge du run 41730284715 (flake `ServeurEnMarche`, antérieur
à C7-T5), pour qu'on ne le lise pas comme un échec.

### Important — Le constat Moyen n°2 de l'audit (code exécuté sous SYSTEM depuis un dossier modifiable) n'est suivi nulle part
**Où :** `docs/essais/C3-T3a-windows.md` (partie A), `docs/ROADMAP.md` (C3-T3, C6).
**Problème :** l'audit demande « tranchée et documentée avant l'envoi au
prospect », et recommande d'ajouter `icacls C:\BilanPosturo`, `icacls` du dossier
de `pythonw.exe` et la portée de l'installation de Python à l'essai 8.9. La fiche
n'a pas reçu ces trois relevés et la ROADMAP n'en porte pas la décision
(`grep icacls docs/` ne trouve que l'audit). Entrée : l'essai 8.9 est passé sans
ces relevés, déclaré « réussi », le paquet part à Bordeaux. Effet : la limite
n'est ni mesurée ni décidée ; le seul endroit où elle est écrite est un rapport
d'audit.
**Attendu :** ajouter à la fiche, partie A, un tableau pour les trois relevés
(sortie de `icacls`, `(Get-Command pythonw.exe).Source`, installation pour tous ou
pour l'utilisateur), et inscrire la décision à prendre dans C3-T3 ou C6 de la
ROADMAP.

### Important — Fiche d'essai : l'étape (b) demande de lire un message que la fenêtre risque de ne pas laisser lire
**Où :** `docs/essais/C3-T3a-windows.md:67-73` ; `docs/LISEZMOI.txt:52-56`.
**Problème :** la fiche prescrit « clic droit > Exécuter avec PowerShell » et de
relever la « Phrase affichée ». Ce verbe de menu ouvre une fenêtre qui se referme
à la fin du script, et le script n'a ni `Read-Host` ni pause (`grep` : aucun). À
vérifier lors de l'essai : si la fenêtre se ferme, le champ « Phrase affichée »
reste vide, et l'adresse de la tablette n'est pas relevable. Cela touche aussi le
but du contrat : les messages « introuvable dans $racine » ne sont diagnostiquables
au téléphone que si on peut les lire. Pré-existant et hors périmètre pour le
script lui-même (C3-T3).
**Attendu :** dans la fiche, (b) proposé aussi en console administrateur
(`.\installer-demarrage.ps1`), ou avec la consigne de photographier/capturer
l'écran ; et un constat « la fenêtre se ferme » remonté comme entrée de C3-T3 si
l'essai le confirme. Même remarque pour « en administrateur » : le verbe de menu
n'élève pas, la fiche doit dire d'ouvrir d'abord une console élevée.

### Mineur — Un mot français ordinaire dans un message du script fait rougir trois tests
**Où :** `tests/test_scripts_installation.py:103-107` (`(?<!\$)racine`).
**Problème :** mutation A9, jouée par moi : ajouter « la racine, » dans le texte du
`throw` de `installer-demarrage.ps1:45` donne 3 échecs (`test_au_moins_un_script_evalue`,
`test_racine_contient_serveur`, `test_script_sans_racine_ne_calcule_aucun_chemin`),
avec « forme non reconnue : étendre l'évaluateur ». Le mot « racine » est exactement
celui qu'un message d'erreur de ce script voudra employer. Échec fail-safe et
explicite, donc pas dangereux, mais l'indication envoie chercher une affectation
alors que c'est un message.
**Attendu :** soit exclure le contenu des chaînes entre guillemets avant la
recherche, soit le dire dans le message d'échec (« même dans un texte : reformuler
ou étendre le test »).

### Mineur — La liste des verbes à effet ne voit que les cmdlets `Verbe-Nom`
**Où :** `tests/test_scripts_installation.py:148-151`.
**Problème :** mutation A8, jouée par moi : insérer `schtasks /create /tn X /tr y /sc onstart`
dans le bloc `-Verifier` laisse la suite verte. Aujourd'hui le script n'emploie que
des cmdlets, donc aucune conséquence ; un ajout par C3-T3 de `netsh`, `schtasks`
ou `sc.exe` échapperait à la garde.
**Attendu :** ajouter ces trois exécutables au motif, ou noter la limite dans le
commentaire au-dessus de `EFFETS_DE_BORD`.

### Mineur — Les tests purs sont sautés sous Windows avec ceux qui fabriquent le paquet
**Où :** `tests/test_scripts_installation.py:298-300`.
**Problème :** `test_forme_inconnue_refusee`, `test_garde_d_ordre_de_verifier_mord`,
`test_formes_d_affectation_non_evaluees_refusees`, `test_evaluation_de_toutes_les_affectations`
et `test_detecteur_de_donnees_reelles_mord` ne touchent ni au paquet ni à `sh`, mais
partagent `skipUnless(OUTILS_DISPONIBLES)` ; ils sont `skipped` sous Windows (journal
CI). Effet : l'évaluateur n'y est pas éprouvé, et la garde de l'Important n°1 ne
pourrait pas s'y appuyer. Sans conséquence sur la couverture globale (Linux et macOS
les jouent).
**Attendu :** les sortir dans une classe sans condition ; deux déplacements, aucune
réécriture.

### Mineur — Test Windows : décodage de la sortie en UTF-8 alors que PowerShell écrit en page de code OEM
**Où :** `tests/test_scripts_installation.py:564`, `:578-585`.
**Problème :** `Application : <chemin>` est décodé en UTF-8 `replace`. Sur un
poste dont le profil porte un accent (« C:\Users\Léa\… »), le chemin temporaire est
déformé et `os.path.samefile` lève `FileNotFoundError` : une erreur de test, pas un
défaut du script. Sans effet sur le lanceur GitHub (profil ASCII), mais possible sur
la VM de 8.9 si l'utilisateur est accentué.
**Attendu :** décoder avec `locale.getpreferredencoding(False)`/`oem`, ou forcer
`[Console]::OutputEncoding` — ou ne comparer que le nom du dossier temporaire
(`bilan-ps1-…`), ASCII.

### Mineur — Couplage du test à la forme textuelle de `tests.yml`
**Où :** `tests/test_scripts_installation.py:194-226`.
**Problème :** `lire_motif_des_secrets` relit deux lignes `motif=` consécutives du
fichier de CI avec une regex. Tout remaniement bénin de ce pas (une troisième ligne
`motif=`, une autre mise en forme) fait lever `RuntimeError` dans deux tests sans
que l'on touche aux scripts. C'est volontaire (échec bruyant, pas de liste
recopiée) et le message dit pourquoi : je le note seulement comme coût. La
protection réelle reste la copie par `git ls-files -z`.
**Attendu :** rien à faire maintenant ; savoir que ce test se mettra à jour avec le
pas de la CI.

### Mineur — Le contrat annonce `test_script_sans_racine…` pour M5 ; c'est `test_racine_contient_serveur` qui rougit
**Où :** `docs/contrats/C3-T3a.md:397` (§9) contre `docs/audits/C3-T3a.md:121`.
**Problème :** écart déjà expliqué et logique par l'auditeur (une fois `$racine`
affectée, le script relève de l'évaluateur) ; la garde mord. Le §9 n'a pas été
corrigé. Aucune conséquence sur le code.
**Attendu :** une ligne au contrat, à la clôture.

## Ce qui est bien fait

- **Le correctif tient en trois lignes et dit pourquoi** (`installer-demarrage.ps1:33-40`) :
  racine = `$PSScriptRoot`, pas de recherche ascendante, et le commentaire explique
  le risque réel (exécuter sous SYSTEM le serveur d'une autre installation). Le
  repli mort `$MyInvocation` est remplacé par un `throw` explicite.
- **Messages de diagnostic** (`:45`, `:48`) : ils disent où le script a cherché,
  ce qui est la raison d'être du contrat.
- **Le test lit l'archive réelle, pas une constante** : la position du script vient
  du zip fabriqué par `faire-paquet.sh`. Je l'ai vu échouer sur le `.ps1` de `main`
  avec un message qui nomme la racine calculée et l'absence de `serveur/serveur.py`.
- **Vocabulaire fermé tenu**, avec test des refus (`test_forme_inconnue_refusee`,
  `test_formes_d_affectation_non_evaluees_refusees`) et garde anti-vide. Les formes
  `$script:racine`, `${racine}`, `Set-Variable` sont refusées au lieu d'être ignorées.
- **Le motif des secrets est lu dans la CI** et non recopié, et son détecteur est
  éprouvé sur seize formes factices, dont celles que l'audit avait vues passer :
  c'est la leçon « dériver, ne pas transcrire » du dépôt, appliquée.
- **Les mutations que j'ai rejouées mordent** : M1 rouge (1 échec), A4 rouge (2),
  A5 rouge (2), sur le code et dans la CI Windows (run 41730347550).
- **La CI Windows est la vraie preuve** : exécution d'un `powershell.exe` réel,
  comparaison par `os.path.samefile` plutôt que par chaînes (`RUNNER~1`), absence
  de PowerShell traitée en échec et non en saut, détection explicite du refus de
  `#Requires`.
- **Périmètre respecté** : `desinstaller-demarrage.ps1` et `demarrer-serveur.bat`
  intacts, `faire-paquet.sh` ne change que des commentaires, `fiche_presentation.html`
  non commité, CRLF + BOM conservés, 22 ajouts sur le `.ps1`.
- **Fiche d'essai** : exploitable telle quelle pour la partie B (commandes
  copiables, lecture des trois hypothèses, interdits rappelés), avec la réserve de
  l'Important n°4 pour la partie A.

## Documentation à mettre à jour

- `docs/Mode_emploi.md` et `docs/USER-GUIDE.md` : à jour, miroir fidèle, la phrase
  décrit exactement ce que `-Verifier` contrôle (emplacement, `config.json`,
  `pythonw.exe`). Rien à changer.
- `README.md`, `docs/LISEZMOI.txt`, `READ-ME-FIRST.txt` : non touchés, conformément
  au contrat (le dossier de lancement ne change pas).
- `docs/audits/C3-T3a.md` : addendum à écrire (Important n°2).
- `docs/essais/C3-T3a-windows.md` : trois relevés `icacls` et l'étape (b) en console
  (Important n°3 et 4).
- `docs/ROADMAP.md` : la tâche **ne peut pas** être considérée comme close tant que
  8.9 et 8.10 sont vides ; inscrire la décision sur les droits du dossier exécuté
  sous SYSTEM dans C3-T3 ou C6.
- Clôture : porter 8.9 comme condition d'envoi au prospect ; noter que le dépôt
  contient désormais un test qui lit le zip, et que la H1 (version réellement en
  service au cabinet) reste à établir avant toute mise à jour.

## Suites données (3 novembre 2026)

| Remarque | Décision |
|---|---|
| Important n°1 — garde d'ordre absente de la classe Windows | **Corrigé** : `verifier_ordre_des_effets()` rejouée dans `_lancer()`, avant toute exécution ; A4 la fait échouer. |
| Important n°2 — audit non complété | **Corrigé** : addendum de `docs/audits/C3-T3a.md`, avec les trois runs et l'explication du run rouge. |
| Important n°3 — droits de ce que SYSTEM exécute non suivis | **Versé dans C3-T3** (feuille de route) ; relevé `icacls` ajouté à la fiche, étape (b bis). |
| Important n°4 — « clic droit > Exécuter avec PowerShell » | **Fiche corrigée** : console administrateur. La documentation générale attend le constat de l'essai (C3-T3). |
| Mineurs | **Laissés** : sans conséquence immédiate, et le décodage OEM ne se juge qu'à l'essai sur VM. |
