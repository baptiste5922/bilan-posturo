# Fiche d'essai C3-T3a — le script d'installation, sur de vrais Windows

Contrat : `docs/contrats/C3-T3a.md` (critères 8.9 et 8.10).
**À remplir par Baptiste.** L'implémenteur n'y a rien inscrit : les champs de
résultat sont vides à dessein, et les cases de l'audit ne se cochent qu'ici.

Règles de la fiche : **patient fictif uniquement** ; **aucune adresse IP du
cabinet pilote** ; aucun contenu de `journal.log` ; aucun nom de patient. Une
adresse de la VM d'essai peut figurer, pas celle du cabinet.

La tâche est livrable au dépôt sans cette fiche, **pas au prospect de
Bordeaux** : le paquet ne part pas tant que la partie A n'est pas complète.

---

## A. Essai sur une VM Windows propre (critère 8.9)

### Préparation

- Windows 10 ou 11, sans installation antérieure de l'application.
- Python 3.9 ou plus, installé avec « Add python.exe to PATH » coché.
- Paquet produit sur le poste de développement : `sh outils/faire-paquet.sh cabinet-01`.
- Une session **administrateur** pour les étapes (a) à (e).

| Champ | Valeur |
|---|---|
| Date de l'essai | |
| Version de Windows (`winver`) | |
| Version de Python (`python --version`) | |
| Archive utilisée (nom du zip) | |
| Opérateur | |

### Installation

Suivre `docs/LISEZMOI.txt`, étapes 1 à 8, avec le dossier d'installation
`C:\BilanPosturo` (le dossier du paquet **renommé**, pas un sous-dossier d'une
installation existante).

| Étape | Fait | Remarque |
|---|---|---|
| 1 à 8 de `LISEZMOI.txt` | | |

### Les cinq vérifications

Toutes en administrateur, depuis `C:\BilanPosturo`.

**(a) Contrôle à sec.**

```powershell
cd C:\BilanPosturo
.\installer-demarrage.ps1 -Verifier
echo $LASTEXITCODE
```

Attendu : code `0`, ligne `Application : C:\BilanPosturo`, dernière ligne
« Verification seulement : aucune tache planifiee ni regle de pare-feu n'a ete
modifiee. » Contrôler ensuite que rien n'a été créé :
`Get-ScheduledTask -TaskName BilanPosturo` doit répondre « introuvable ».

| Résultat | |
|---|---|
| Code de sortie | |
| Ligne `Application :` relevée | |
| Tâche absente après le contrôle (oui / non) | |
| Sortie complète (sans adresse du cabinet) | |

**(b) Installation réelle**, dans la **même console PowerShell ouverte en
administrateur** (pas par « clic droit > Exécuter avec PowerShell » : ce
verbe n'élève pas, et sa fenêtre se referme à la fin du script, ce qui rend
illisible tout message d'erreur, celui qu'on doit pouvoir dicter au
téléphone pendant une installation à distance) :

```powershell
.\installer-demarrage.ps1
```

Attendu : « Le serveur ecoute sur le port … ». Noter aussi, à part, si le
clic droit ouvre une fenêtre qui se referme avant qu'on puisse la lire : la
documentation d'installation devra alors cesser de le conseiller (C3-T3).

| Résultat | |
|---|---|
| Phrase affichée | |
| Adresse proposée pour la tablette (VM seulement) | |

**(b bis) Qui peut modifier ce que SYSTEM exécute ?** Constat moyen n°2 de
`docs/audits/C3-T3a.md` : la tâche tourne sous SYSTEM ; si un compte
standard peut modifier `serveur\` ou le `pythonw.exe` lancé, c'est une
élévation de privilège. Relever, sans rien changer :

```powershell
icacls C:\BilanPosturo
icacls C:\BilanPosturo\serveur
(Get-ScheduledTask -TaskName BilanPosturo).Actions.Execute
icacls (Split-Path (Get-ScheduledTask -TaskName BilanPosturo).Actions.Execute)
```

| Résultat | |
|---|---|
| « Utilisateurs authentifiés » ou « Utilisateurs » ont-ils (M) ou (F) sur `C:\BilanPosturo` ? | |
| Idem sur le dossier de `pythonw.exe` ? | |
| Python installé « pour tous les utilisateurs » (sous `C:\Program Files`) ? | |

**(c) La tâche pointe au bon endroit.**

```powershell
Get-ScheduledTask -TaskName BilanPosturo | Select-Object -ExpandProperty Actions |
    Format-List Execute, Arguments, WorkingDirectory
```

Attendu : `WorkingDirectory` = `C:\BilanPosturo`, `Arguments` contenant
`C:\BilanPosturo\serveur\serveur.py`.

| Résultat | |
|---|---|
| `Execute` | |
| `Arguments` | |
| `WorkingDirectory` | |

**(d) Redémarrage de la VM, sans ouvrir de session.** Depuis un autre poste du
réseau de la VM (ou la machine hôte), `https://<ip de la VM>:<port>/sante`
répond avant toute connexion à la VM.

| Résultat | |
|---|---|
| Réponse de `/sante` (code HTTP) | |
| Délai après le redémarrage | |

**(e) Désinstallation.**

```powershell
.\desinstaller-demarrage.ps1
Get-ScheduledTask -TaskName BilanPosturo
```

Attendu : « Demarrage automatique retire. », puis la tâche est introuvable.

| Résultat | |
|---|---|
| Message affiché | |
| Tâche absente ensuite (oui / non) | |

### Cas du mauvais dossier (facultatif, utile pour le support)

Copier `installer-demarrage.ps1` dans `C:\BilanPosturo\outils\` et l'y lancer
avec `-Verifier`. Attendu : arrêt sur « serveur\serveur.py introuvable dans
C:\BilanPosturo\outils … », avant toute tâche.

| Résultat | |
|---|---|

### Verdict de la partie A

| Critère 8.9 | Verdict (réussi / échoué) | Date | Signature |
|---|---|---|---|
| | | | |

---

## B. Hypothèse H1 au cabinet pilote (critère 8.10)

Lecture seule. Aucune de ces commandes ne lit de donnée patient, et rien n'est
modifié. À passer en PowerShell sur le PC du cabinet.

```powershell
Get-ScheduledTask -TaskName BilanPosturo | Select-Object -ExpandProperty Actions |
    Format-List Execute, Arguments, WorkingDirectory
Get-ChildItem C:\BilanPosturo -Directory | Select-Object Name
```

**Lecture du résultat.**

- **H1 confirmée** : `WorkingDirectory` vaut `C:\BilanPosturo` **et** un
  sous-dossier `BilanPosturo-AAAA-MM-JJ` existe. Le paquet du 14 octobre a été
  dézippé dans l'installation, et l'ancien calcul de racine « remontait d'un
  cran » pour retrouver `serveur\` et `config.json`.
- **H2** : tâche enregistrée à la main, sans le script. `Arguments` ou
  `WorkingDirectory` ne correspondent pas à ce que le script produirait.
- **H3** : aucune tâche `BilanPosturo` ; le serveur démarre encore par
  `demarrer-serveur.bat`.

| Champ | Valeur |
|---|---|
| Date de la lecture | |
| Opérateur | |
| `WorkingDirectory` relevé | |
| Sous-dossiers de `C:\BilanPosturo` (noms seulement, sans aucun nom de patient) | |
| Verdict (H1 / H2 / H3) | |
| Suite décidée (nettoyage du sous-dossier éventuel, etc.) | |

Ne rien recopier d'autre : ni adresse IP du cabinet, ni contenu de
`journal.log`, ni liste de bilans.
