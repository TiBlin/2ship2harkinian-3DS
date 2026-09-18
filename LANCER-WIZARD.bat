@echo off
setlocal DisableDelayedExpansion

rem Robust launcher: works from the project root or from the parent ZIP folder.
set "ROOT=%~dp0"
set "OUTPUT_ROOT=%~dp0"
set "ROM_ARG="
if not "%~1"=="" set "ROM_ARG=%~f1"

if exist "%ROOT%build.py" if exist "%ROOT%Wizard-2Ship3DS.ps1" goto :found
if exist "%ROOT%2Ship3DS\build.py" if exist "%ROOT%2Ship3DS\Wizard-2Ship3DS.ps1" (
    set "ROOT=%ROOT%2Ship3DS\"
    goto :found
)

rem Last resort: find the complete project below the launcher folder.
for /r "%ROOT%" %%F in (build.py) do (
    if exist "%%~dpFWizard-2Ship3DS.ps1" (
        set "ROOT=%%~dpF"
        goto :found
    )
)

echo ERROR: build.py and Wizard-2Ship3DS.ps1 were not found.
echo.
echo Launcher folder: %~dp0
echo Extract the complete ZIP; do not copy only the .bat file.
echo.
pause
exit /b 1

:found
cd /d "%ROOT%"
echo Project detected: %ROOT%

if not "%ROM_ARG%"=="" goto :romdrop

"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -STA -ExecutionPolicy Bypass -File "%ROOT%Wizard-2Ship3DS.ps1"
set "WIZARD_EXIT=%ERRORLEVEL%"
if not "%WIZARD_EXIT%"=="0" (
    echo.
    echo The wizard exited with code %WIZARD_EXIT%.
    pause
)
exit /b %WIZARD_EXIT%

:romdrop
if not "%~2"=="" (
    echo ERROR: drag exactly one ROM onto START-WIZARD.bat.
    echo.
    pause
    exit /b 2
)
echo ROM-drop mode: %ROM_ARG%
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%ROOT%RomDrop-2Ship3DS.ps1" -RomPath "%ROM_ARG%" -OutputRoot "%OUTPUT_ROOT%"
exit /b %ERRORLEVEL%
