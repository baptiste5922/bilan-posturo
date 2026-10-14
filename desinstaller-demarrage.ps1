<#
    Retire le demarrage automatique du serveur du bilan posturologique.

    Le serveur redevient manuel : demarrer-serveur.bat, a double-cliquer
    chaque matin. La regle de pare-feu et la configuration du cabinet ne sont
    pas touchees, et aucun bilan n'est supprime.

    A lancer en tant qu'administrateur :
        .\desinstaller-demarrage.ps1
#>

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

$NOM_TACHE = "BilanPosturo"

if (-not (Get-ScheduledTask -TaskName $NOM_TACHE -ErrorAction SilentlyContinue)) {
    Write-Host "Aucun demarrage automatique installe."
    exit 0
}

Stop-ScheduledTask -TaskName $NOM_TACHE -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $NOM_TACHE -Confirm:$false

Write-Host "Demarrage automatique retire."
Write-Host "Le serveur se lance desormais par demarrer-serveur.bat."
Write-Host ""
Write-Host "La regle de pare-feu est conservee. Pour la supprimer aussi :"
Write-Host "    Remove-NetFirewallRule -DisplayName 'Bilan posturologique'"
