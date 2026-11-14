<#
    Retire le demarrage automatique du serveur du bilan posturologique.

    Le serveur redevient manuel : demarrer-serveur.bat, a double-cliquer
    chaque matin. La regle de pare-feu et la configuration du cabinet ne sont
    pas touchees, et aucun bilan n'est supprime.

    La tache de mise a jour automatique est retiree en premier. Si elle est en
    cours d'execution, le script refuse : l'arreter en pleine bascule laisserait
    des fichiers meles que plus aucune tache ne reprendrait.

    A lancer en tant qu'administrateur :
        .\desinstaller-demarrage.ps1
#>

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

$NOM_TACHE = "BilanPosturo"
# Egal a NOM_TACHE_MAJ de serveur\maj.py (un test les compare).
$NOM_TACHE_MAJ = "BilanPosturo-MiseAJour"

# La mise a jour d'abord : une tache qui lance le serveur ne doit pas survivre a
# celle qu'elle relancerait.
$tacheMaj = Get-ScheduledTask -TaskName $NOM_TACHE_MAJ -ErrorAction SilentlyContinue
if ($tacheMaj) {
    if ($tacheMaj.State -eq 'Running') {
        Write-Warning "Une mise a jour est en cours : reessayer dans quelques minutes."
        Write-Warning "Si l'etape indiquee par « python serveur\maj.py etat » n'est pas « repos » apres un long moment, lancer « python serveur\maj.py reprendre » avant de recommencer."
        exit 1
    }
    Unregister-ScheduledTask -TaskName $NOM_TACHE_MAJ -Confirm:$false
    Write-Host "Mise a jour automatique retiree."
}

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
