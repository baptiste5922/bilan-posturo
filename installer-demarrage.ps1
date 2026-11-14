<#
    Installe le serveur du bilan posturologique en demarrage automatique.

    Sans cela, le serveur depend d'un double-clic quotidien sur
    demarrer-serveur.bat : une fenetre fermee par megarde, une mise a jour de
    Windows pendant la nuit, et la tablette affiche ERR_CONNECTION_REFUSED au
    premier patient de la journee. La tache planifiee ci-dessous demarre le
    serveur avec le PC, sans session ouverte, et le relance s'il s'arrete.

    A lancer UNE FOIS, en tant qu'administrateur :
        clic droit sur ce fichier > Executer avec PowerShell
    ou, depuis une console PowerShell ouverte en administrateur :
        .\installer-demarrage.ps1

    Option -Verifier : controle seul. Toutes les verifications prealables sont
    faites (serveur, config.json, pythonw.exe), le resultat est affiche, puis
    le script s'arrete avant la tache planifiee et le pare-feu. A utiliser
    avant une installation a distance : il ne modifie rien.

    demarrer-serveur.bat reste utilisable pour un demarrage manuel ponctuel,
    par exemple pour lire les messages du serveur dans une fenetre.
#>

param([switch]$Verifier)

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

$NOM_TACHE = "BilanPosturo"
# Egal a NOM_TACHE_MAJ de serveur\maj.py (un test les compare).
$NOM_TACHE_MAJ = "BilanPosturo-MiseAJour"
$NOM_REGLE = "Bilan posturologique"

# La racine est le dossier qui contient ce script : le paquet le depose a cote
# de serveur\ et formulaire\. Pas de recherche ascendante de serveur\ : un
# script lance du mauvais dossier doit s'arreter, pas aller executer sous
# SYSTEM le serveur d'une autre installation.
$racine = $PSScriptRoot
if (-not $racine) {
    throw "Emplacement du script inconnu. Lancer le fichier lui-meme (clic droit > Executer avec PowerShell), ne pas copier son contenu dans une console."
}
$serveur = Join-Path $racine "serveur\serveur.py"
$config  = Join-Path $racine "config.json"
$maj     = Join-Path $racine "serveur\maj.py"

if (-not (Test-Path $serveur)) {
    throw "serveur\serveur.py introuvable dans $racine. Lancer ce script depuis le dossier de l'application, celui qui contient serveur\ et formulaire\."
}
if (-not (Test-Path $config)) {
    throw "config.json introuvable dans $racine. Definir d'abord le mot de passe : python serveur\serveur.py --config"
}

$port = (Get-Content $config -Raw | ConvertFrom-Json).port
if (-not $port) { $port = 8000 }

# pythonw.exe plutot que python.exe : aucune fenetre de console n'est ouverte,
# ce qui est indispensable pour une tache qui tourne sans session. Le serveur
# ecrit de toute facon tout ce qu'il a a dire dans journal.log.
$python = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $python) {
    throw "pythonw.exe introuvable. Installer Python en cochant « Add python.exe to PATH »."
}

Write-Host "Application : $racine"
Write-Host "Python      : $python"
Write-Host "Port        : $port"
# Une simple presence de fichier : la regle de la mise a jour (adresse, plage,
# client) vit dans maj.py, jamais recopiee ici, et aucun processus n'est lance
# avant la sortie de -Verifier.
$presenceMaj = "absent"
if (Test-Path $maj) { $presenceMaj = "present" }
Write-Host "Client de mise a jour : $presenceMaj"
Write-Host ""

if ($Verifier) {
    Write-Host "Verification seulement : aucune tache planifiee ni regle de pare-feu n'a ete modifiee."
    exit 0
}

# --- La tache ------------------------------------------------------------

$action = New-ScheduledTaskAction -Execute $python `
    -Argument ('"' + $serveur + '"') -WorkingDirectory $racine

$declencheur = New-ScheduledTaskTrigger -AtStartup

# SYSTEM : la tache demarre avec le PC, avant et independamment de toute
# ouverture de session. Personne n'a besoin d'etre connecte au cabinet.
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" `
    -LogonType ServiceAccount -RunLevel Highest

$reglages = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $NOM_TACHE -Action $action `
    -Trigger $declencheur -Principal $principal -Settings $reglages `
    -Description "Serveur du bilan posturologique. Demarre avec le PC." `
    -Force | Out-Null

Write-Host "Tache planifiee « $NOM_TACHE » enregistree."

# --- La mise a jour automatique ------------------------------------------

# Seconde tache : elle ne fait que lancer "maj.py verifier" chaque heure. Le client
# decide seul, d'apres config.json, s'il y a quelque chose a faire et s'il est
# l'heure de le faire ; sans adresse configuree il ne se connecte a rien.
# Le serveur, lui, a deja sa tache : un echec ici ne l'empeche pas de tourner.
if (Test-Path $maj) {
    # Le dossier mise-a-jour\ est cree et protege (SYSTEM et administrateurs
    # seulement) par maj.py lui-meme : la regle des droits n'est ecrite qu'une
    # fois, la-bas, et le serveur la relit avant d'obeir a une demande d'arret.
    $protection = Start-Process -FilePath $python `
        -ArgumentList '-B', ('"' + $maj + '"'), 'proteger' `
        -WorkingDirectory $racine -Wait -PassThru -WindowStyle Hidden
    if ($protection.ExitCode -ne 0) {
        Write-Warning ("Le dossier mise-a-jour n'a pas pu etre protege : la mise a jour " +
                       "automatique n'est PAS installee (le serveur, lui, l'est). " +
                       "Pour lire le motif, en console administrateur : " +
                       "python serveur\maj.py proteger")
    } else {
        $actionMaj = New-ScheduledTaskAction -Execute $python `
            -Argument ('-B "' + $maj + '" verifier') -WorkingDirectory $racine

        # Au demarrage, apres trois minutes : le Wi-Fi a le temps de monter.
        $declencheurDemarrage = New-ScheduledTaskTrigger -AtStartup
        $declencheurDemarrage.Delay = "PT3M"
        # Puis toutes les heures. Vingt ans plutot que [TimeSpan]::MaxValue, que
        # les Windows recents refusent ; l'installateur relu les renouvelle.
        $declencheurHoraire = New-ScheduledTaskTrigger -Once -At (Get-Date) `
            -RepetitionInterval (New-TimeSpan -Hours 1) `
            -RepetitionDuration (New-TimeSpan -Days 7300)

        # Aucun -RestartCount : un client qui echoue reessaie a l'heure suivante.
        # Une heure au plus : une tache tuee a l'heure laisse un etat que le
        # passage suivant defait (reprendre).
        $reglagesMaj = New-ScheduledTaskSettingsSet `
            -MultipleInstances IgnoreNew `
            -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
            -StartWhenAvailable `
            -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

        Register-ScheduledTask -TaskName $NOM_TACHE_MAJ -Action $actionMaj `
            -Trigger @($declencheurDemarrage, $declencheurHoraire) `
            -Principal $principal -Settings $reglagesMaj `
            -Description "Mise a jour du bilan posturologique. Verifie chaque heure." `
            -Force | Out-Null

        Write-Host "Tache planifiee « $NOM_TACHE_MAJ » enregistree (inactive tant qu'aucune adresse n'est configuree)."
    }
}

# --- Le pare-feu ---------------------------------------------------------

# Profil prive uniquement : le serveur n'a rien a faire sur un reseau public.
if (-not (Get-NetFirewallRule -DisplayName $NOM_REGLE -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $NOM_REGLE -Direction Inbound `
    -LocalPort $port -Protocol TCP -Action Allow -Profile Private | Out-Null
    Write-Host "Regle de pare-feu creee sur le port $port (reseau prive)."
} else {
    Write-Host "Regle de pare-feu deja presente."
}

$publics = Get-NetConnectionProfile | Where-Object { $_.NetworkCategory -eq "Public" }
if ($publics) {
    Write-Warning ("Le reseau « " + ($publics[0].Name) + " » est classe Public : la " +
                   "tablette ne pourra pas joindre le PC. Le passer en Prive dans " +
                   "Parametres > Reseau et Internet.")
}

# --- Demarrage immediat --------------------------------------------------

Start-ScheduledTask -TaskName $NOM_TACHE
Write-Host ""
Write-Host "Demarrage du serveur..."

$limite = (Get-Date).AddSeconds(30)
$ecoute = $false
while ((Get-Date) -lt $limite -and -not $ecoute) {
    Start-Sleep -Milliseconds 500
    $ecoute = [bool](Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
}

if (-not $ecoute) {
    Write-Warning "Le serveur n'ecoute pas encore sur le port $port."
    Write-Warning "Voir journal.log, ou lancer demarrer-serveur.bat pour afficher l'erreur."
    exit 1
}

$adresses = (Get-NetIPAddress -AddressFamily IPv4 |
             Where-Object { $_.IPAddress -notlike "127.*" }).IPAddress

Write-Host ""
Write-Host "Le serveur ecoute sur le port $port et redemarrera avec le PC."
Write-Host "Adresse a utiliser sur la tablette :"
foreach ($adresse in $adresses) { Write-Host "    https://${adresse}:${port}" }
Write-Host ""
Write-Host "Pour revenir au demarrage manuel : .\desinstaller-demarrage.ps1"
