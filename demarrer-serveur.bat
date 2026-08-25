@echo off
REM Lanceur du serveur du bilan posturologique.
REM A double-cliquer chaque matin. Laisser la fenetre ouverte.

cd /d "%~dp0"
title Bilan posturologique - serveur

python serveur\serveur.py
if errorlevel 1 (
    echo.
    echo Le serveur s^'est arrete sur une erreur. Voir le message ci-dessus.
)

echo.
echo Appuyez sur une touche pour fermer cette fenetre.
pause >nul
