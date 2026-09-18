#requires -Version 5.1
param(
    [Parameter(Mandatory = $true)][string]$RomPath,
    [string]$OutputRoot = '',
    [switch]$NoPause
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)

function Find-Sdk {
    foreach ($rawCandidate in @('C:\devkitPro', $env:DEVKITPRO, 'D:\devkitPro', 'E:\devkitPro')) {
        $candidate = if ($rawCandidate) { $rawCandidate.Trim().Trim([char]34) } else { '' }
        if ($candidate -and $candidate -notmatch '^/' -and (Test-Path -LiteralPath (Join-Path $candidate 'devkitARM'))) {
            return (Resolve-Path -LiteralPath $candidate).ProviderPath
        }
    }
    throw 'devkitPro was not found. Install it first or set DEVKITPRO.'
}

function Find-Python([string]$Sdk) {
    $preferred = Join-Path $Sdk 'msys2\mingw64\bin\python.exe'
    if (Test-Path -LiteralPath $preferred -PathType Leaf) { return $preferred }
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($command -and $command.Source -notlike '*\WindowsApps\*') { return $command.Source }
    throw 'python.exe was not found. The devkitPro MSYS2 Python is recommended.'
}

$root = $PSScriptRoot
$exitCode = 1
try {
    # Drag-and-drop paths can arrive with literal wrapping quotes from some shells.
    # Quotes are not legal in Windows file names, so stripping only edge quotes is safe.
    $RomPath = $RomPath.Trim().Trim([char]34)
    if (-not [string]::IsNullOrWhiteSpace($OutputRoot)) { $OutputRoot = $OutputRoot.Trim().Trim([char]34) }
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'ROM drag-and-drop mode requires Windows.'
    }
    if (-not (Test-Path -LiteralPath $RomPath -PathType Leaf)) {
        throw "ROM file not found: $RomPath"
    }
    $rom = (Resolve-Path -LiteralPath $RomPath).ProviderPath
    $sdk = Find-Sdk
    $python = Find-Python $sdk
    $worker = Join-Path $root 'wizard\rom_drop_build.py'
    if (-not (Test-Path -LiteralPath $worker -PathType Leaf)) {
        throw 'rom_drop_build.py is missing. Extract the complete wizard ZIP.'
    }
    if ([string]::IsNullOrWhiteSpace($OutputRoot)) { $OutputRoot = $root }
    $outputBase = (Resolve-Path -LiteralPath $OutputRoot).ProviderPath
    $output = Join-Path $outputBase 'sd'
    Write-Host ''
    Write-Host '2Ship3DS automatic ROM-drop build' -ForegroundColor Cyan
    Write-Host '--------------------------------'
    Write-Host "ROM:       $rom"
    Write-Host "devkitPro: $sdk"
    Write-Host "Output:    $output"
    Write-Host ''
    & $python -u $worker --rom $rom --devkitpro $sdk --output $output
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0) {
        Write-Host ''
        Write-Host 'Build completed successfully.' -ForegroundColor Green
        Write-Host "Copy the CONTENTS of '$output' to the root of your SD card."
    } else {
        Write-Host ''
        Write-Host "Build failed with exit code $exitCode. See wizard-logs\romdrop-* for details." -ForegroundColor Red
    }
} catch {
    Write-Host ''
    Write-Host ('ERROR: ' + $_.Exception.Message) -ForegroundColor Red
    $exitCode = 1
}
if (-not $NoPause) {
    Write-Host ''
    [void](Read-Host 'Press Enter to close')
}
exit $exitCode
