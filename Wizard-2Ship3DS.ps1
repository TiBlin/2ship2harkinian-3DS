# Blinky command-line launcher. Does not download or modify game archives.
[CmdletBinding()]
param(
    [string]$DevkitPro = 'C:/devkitPro',
    [ValidateRange(1,64)][int]$Jobs = 4,
    [string]$Output = '',
    [switch]$VerifyOnly
)
$ErrorActionPreference = 'Stop'
$projectPath = $PSScriptRoot
$pythonPath = Join-Path $DevkitPro 'msys2/mingw64/bin/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    $pythonCommand = Get-Command python -ErrorAction Stop
    $pythonPath = $pythonCommand.Source
}
if ($VerifyOnly) {
    $verifyPath = Join-Path $projectPath 'scripts/verify_port.py'
    & $pythonPath -X utf8 $verifyPath
} else {
    if (-not $Output) { $Output = Join-Path $projectPath 'dist' }
    $buildPath = Join-Path $projectPath 'build.py'
    & $pythonPath -X utf8 $buildPath --devkitpro $DevkitPro --jobs $Jobs --output $Output
}
exit $LASTEXITCODE