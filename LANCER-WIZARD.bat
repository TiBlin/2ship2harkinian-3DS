@echo off
setlocal
if not exist "%~dp0Wizard-2Ship3DS.ps1" (
    echo Le dossier complet des sources est requis.
    pause
    exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Wizard-2Ship3DS.ps1" %*
set "BLINKY_RESULT=%ERRORLEVEL%"
echo.
if "%BLINKY_RESULT%"=="0" (echo Compilation terminee.) else (echo Echec de la compilation. Voir les erreurs ci-dessus.)
pause
exit /b %BLINKY_RESULT%