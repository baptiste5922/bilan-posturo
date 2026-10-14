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

    demarrer-serveur.bat reste utilisable pour un demarrage manuel ponctuel,
    par exemple pour lire les messages du serveur dans une fenetre.
#>

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

$NOM_TACHE = "BilanPosturo"
$NOM_REGLE = "Bilan posturologique"

$racine  = Split-Path -Parent $PSScriptRoot
if (-not $racine) { $racine = Split-Path -Parent $MyInvocation.MyCommand.Path }
$serveur = Join-Path $racine "serveur\serveur.py"
$config  = Join-Path $racine "config.json"

if (-not (Test-Path $serveur)) {
    throw "serveur\serveur.py introuvable. Lancer ce script depuis le dossier de l'application."
}
if (-not (Test-Path $config)) {
    throw "config.json introuvable. Definir d'abord le mot de passe : python serveur\serveur.py --config"
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
Write-Host ""

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
