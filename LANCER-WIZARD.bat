@echo off
setlocal DisableDelayedExpansion

rem Lanceur robuste: fonctionne depuis la racine du projet ou depuis le dossier parent du ZIP.
set "ROOT=%~dp0"

if exist "%ROOT%build.py" if exist "%ROOT%Wizard-2Ship3DS.ps1" goto :found
if exist "%ROOT%2Ship3DS\build.py" if exist "%ROOT%2Ship3DS\Wizard-2Ship3DS.ps1" (
    set "ROOT=%ROOT%2Ship3DS\"
    goto :found
)

rem Dernier recours: rechercher le projet sous le dossier du lanceur.
for /r "%ROOT%" %%F in (build.py) do (
    if exist "%%~dpFWizard-2Ship3DS.ps1" (
        set "ROOT=%%~dpF"
        goto :found
    )
)

echo ERREUR: build.py et Wizard-2Ship3DS.ps1 sont introuvables.
echo.
echo Le lanceur est ici: %~dp0
echo Le ZIP doit contenir le dossier 2Ship3DS complet; ne copiez pas seulement le .bat.
echo.
pause
exit /b 1

:found
cd /d "%ROOT%"
echo Projet detecte: %ROOT%
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -STA -ExecutionPolicy Bypass -File "%ROOT%Wizard-2Ship3DS.ps1"
set "WIZARD_EXIT=%ERRORLEVEL%"
if not "%WIZARD_EXIT%"=="0" (
    echo.
    echo Le wizard s'est termine avec le code %WIZARD_EXIT%.
    pause
)
exit /b %WIZARD_EXIT%
