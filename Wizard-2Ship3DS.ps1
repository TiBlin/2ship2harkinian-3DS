#requires -Version 5.1
param([switch]$SelfTest)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function ConvertTo-NativeArgument([string]$Value) {
    # Windows CRT quoting: double runs of backslashes before quotes and at end.
    if ($Value.Length -gt 0 -and $Value -notmatch '[\s"]') { return $Value }
    $escaped = [regex]::Replace($Value, '(\\*)"', '${1}${1}\"')
    $escaped = [regex]::Replace($escaped, '(\\+)$', '${1}${1}')
    return '"' + $escaped + '"'
}

if ($SelfTest) {
    $cases = @(
        @('simple', 'simple'),
        @('a b', '"a b"'),
        @('', '""'),
        @('C:\mes sources\', '"C:\mes sources\\"'),
        @('a"b', '"a\"b"')
    )
    foreach ($case in $cases) {
        if ((ConvertTo-NativeArgument $case[0]) -cne $case[1]) { throw "Argument quoting failed: $($case[0])" }
    }
    Write-Output 'PASS: native argument quoting (5 cases).'
    exit 0
}

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw 'Cette interface nécessite Windows. Le moteur Python peut être testé séparément.'
}
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)

$script:Root = $PSScriptRoot
$script:Worker = Join-Path $script:Root 'wizard\build_wizard.py'
$script:Settings = Join-Path $script:Root 'wizard\settings.json'
$script:Logs = Join-Path $script:Root 'wizard-logs'
$script:Process = $null
$script:OutputReader = $null
$script:ErrorReader = $null
$script:ResultFolder = ''
$script:ConfigFile = ''
$script:OutLog = ''
$script:ErrLog = ''
$script:CurrentAction = ''
$script:Cancelled = $false
$script:LastOutputTime = Get-Date
$script:Started = Get-Date
$script:LastStage = ''
$script:LastAutoPython = ''
$script:PollBusy = $false

function Show-Error([string]$Message) {
    [void][Windows.Forms.MessageBox]::Show($script:Form, $Message, '2Ship3DS',
        [Windows.Forms.MessageBoxButtons]::OK, [Windows.Forms.MessageBoxIcon]::Error)
}

function Find-Python([string]$Sdk) {
    $candidates = [Collections.Generic.List[string]]::new()
    if ($Sdk) { $candidates.Add((Join-Path $Sdk 'msys2\mingw64\bin\python.exe')) }
    if ($env:LOCALAPPDATA) {
        $base = Join-Path $env:LOCALAPPDATA 'Programs\Python'
        if (Test-Path -LiteralPath $base) {
            Get-ChildItem -LiteralPath $base -Directory -ErrorAction SilentlyContinue |
                Sort-Object Name -Descending | ForEach-Object { $candidates.Add((Join-Path $_.FullName 'python.exe')) }
        }
    }
    foreach ($registry in @('HKCU:\Software\Python\PythonCore', 'HKLM:\Software\Python\PythonCore')) {
        if (Test-Path $registry) {
            foreach ($key in (Get-ChildItem $registry -ErrorAction SilentlyContinue)) {
                $install = Join-Path $key.PSPath 'InstallPath'
                if (Test-Path $install) {
                    $item = Get-Item $install
                    $value = $item.GetValue('ExecutablePath', '')
                    if ($value) { $candidates.Add([string]$value) }
                    $directory = $item.GetValue('', '')
                    if ($directory) { $candidates.Add((Join-Path $directory 'python.exe')) }
                }
            }
        }
    }
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($command -and $command.Source -notlike '*\WindowsApps\*') { $candidates.Add($command.Source) }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    return ''
}

function Find-Sdk {
    $candidates = @('C:\devkitPro', $env:DEVKITPRO, 'D:\devkitPro', 'E:\devkitPro')
    foreach ($candidate in $candidates) {
        if ($candidate -and $candidate -notmatch '^/' -and
            (Test-Path -LiteralPath (Join-Path $candidate 'devkitARM'))) { return $candidate }
    }
    return 'C:\devkitPro'
}

function Add-Label($Parent, [string]$Text, [int]$X, [int]$Y, [int]$Width, [int]$Height = 24) {
    $label = [Windows.Forms.Label]::new()
    $label.Text = $Text
    $label.Location = [Drawing.Point]::new($X, $Y)
    $label.Size = [Drawing.Size]::new($Width, $Height)
    $label.Anchor = 'Top, Left, Right'
    $Parent.Controls.Add($label)
    return $label
}

function Add-Button($Parent, [string]$Text, [int]$X, [int]$Y, [int]$Width) {
    $button = [Windows.Forms.Button]::new()
    $button.Text = $Text
    $button.Location = [Drawing.Point]::new($X, $Y)
    $button.Size = [Drawing.Size]::new($Width, 32)
    $Parent.Controls.Add($button)
    return $button
}

function Add-PathRow($Parent, [string]$Text, [int]$Y, [string]$Kind, [string]$Filter = '') {
    [void](Add-Label $Parent $Text 20 $Y 900)
    $box = [Windows.Forms.TextBox]::new()
    $box.Location = [Drawing.Point]::new(20, ($Y + 25))
    $box.Size = [Drawing.Size]::new(778, 27)
    $box.Anchor = 'Top, Left, Right'
    $Parent.Controls.Add($box)
    $button = Add-Button $Parent 'Parcourir...' 811 ($Y + 23) 120
    $button.Anchor = 'Top, Right'
    $button.Tag = @{ Box = $box; Kind = $Kind; Filter = $Filter }
    $button.Add_Click({
        param($sender, $eventArgs)
        try {
            $info = $sender.Tag
            if ($info.Kind -eq 'folder') {
                $dialog = [Windows.Forms.FolderBrowserDialog]::new()
                $dialog.Description = 'Choisir un dossier'
                $dialog.ShowNewFolderButton = $true
                if (Test-Path -LiteralPath $info.Box.Text -PathType Container) { $dialog.SelectedPath = $info.Box.Text }
            } else {
                $dialog = [Windows.Forms.OpenFileDialog]::new()
                $dialog.Filter = $info.Filter
                $dialog.CheckFileExists = $true
                $dialog.Multiselect = $false
                if (Test-Path -LiteralPath $info.Box.Text -PathType Leaf) { $dialog.FileName = $info.Box.Text }
            }
            try {
                if ($dialog.ShowDialog($script:Form) -eq [Windows.Forms.DialogResult]::OK) {
                    if ($info.Kind -eq 'folder') { $info.Box.Text = $dialog.SelectedPath }
                    else { $info.Box.Text = $dialog.FileName }
                }
            } finally { $dialog.Dispose() }
        } catch { Show-Error $_.Exception.Message }
    })
    return $box
}

function Write-Json([string]$Path, $Value) {
    $json = $Value | ConvertTo-Json -Depth 8
    [IO.File]::WriteAllText($Path, $json, [Text.UTF8Encoding]::new($false))
}

function Export-Artwork([string]$Source, [string]$Destination, [int]$Width, [int]$Height) {
    if ([string]::IsNullOrWhiteSpace($Source)) { return '' }
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) { throw "Image introuvable : $Source" }
    $Source = [IO.Path]::GetFullPath($Source)
    $extension = [IO.Path]::GetExtension($Source).ToLowerInvariant()
    if ($extension -in @('.smdh', '.bnr', '.bin', '.banner')) { return $Source }
    # Decode off disk, preserve aspect ratio, center in an exact-size RGB canvas.
    # Original artwork is never overwritten; no external imaging package needed.
    $image = [Drawing.Image]::FromFile($Source)
    try {
        if ($image.Width -gt 16384 -or $image.Height -gt 16384 -or
            ([long]$image.Width * [long]$image.Height) -gt 80000000) { throw 'Image trop grande.' }
        $bitmap = [Drawing.Bitmap]::new($Width, $Height, [Drawing.Imaging.PixelFormat]::Format24bppRgb)
        try {
            $graphics = [Drawing.Graphics]::FromImage($bitmap)
            try {
                $graphics.Clear([Drawing.Color]::Black)
                $graphics.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
                $graphics.PixelOffsetMode = [Drawing.Drawing2D.PixelOffsetMode]::HighQuality
                $ratio = [Math]::Min($Width / [double]$image.Width, $Height / [double]$image.Height)
                $w = [Math]::Max(1, [int][Math]::Round($image.Width * $ratio))
                $h = [Math]::Max(1, [int][Math]::Round($image.Height * $ratio))
                $rectangle = [Drawing.Rectangle]::new([int](($Width - $w) / 2), [int](($Height - $h) / 2), $w, $h)
                $graphics.DrawImage($image, $rectangle)
            } finally { $graphics.Dispose() }
            $bitmap.Save($Destination, [Drawing.Imaging.ImageFormat]::Png)
        } finally { $bitmap.Dispose() }
    } finally { $image.Dispose() }
    return $Destination
}

function Add-Log([string]$Text) {
    if (-not $Text) { return }
    $script:LastOutputTime = Get-Date
    if ($script:LogBox.TextLength -gt 300000) {
        $script:LogBox.Select(0, 120000)
        $script:LogBox.SelectedText = ''
    }
    $script:LogBox.AppendText($Text)
    $script:LogBox.SelectionStart = $script:LogBox.TextLength
    $script:LogBox.ScrollToCaret()
}

function Read-LogUpdates {
    foreach ($which in @('OutputReader', 'ErrorReader')) {
        $path = if ($which -eq 'OutputReader') { $script:OutLog } else { $script:ErrLog }
        $reader = Get-Variable -Name $which -Scope Script -ValueOnly
        if ($null -eq $reader -and $path -and (Test-Path -LiteralPath $path -PathType Leaf)) {
            $file = [IO.File]::Open($path, [IO.FileMode]::Open, [IO.FileAccess]::Read,
                ([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
            $reader = [IO.StreamReader]::new($file, [Text.Encoding]::UTF8, $true)
            Set-Variable -Name $which -Scope Script -Value $reader
        }
        if ($null -ne $reader) { Add-Log ($reader.ReadToEnd()) }
    }
}

function Close-Readers {
    if ($null -ne $script:OutputReader) { $script:OutputReader.Dispose(); $script:OutputReader = $null }
    if ($null -ne $script:ErrorReader) { $script:ErrorReader.Dispose(); $script:ErrorReader = $null }
}

function Set-Running([bool]$Running) {
    $script:BuildButton.Enabled = -not $Running
    $script:CheckButton.Enabled = -not $Running
    $script:StopButton.Enabled = $Running
    $script:PreviousButton.Enabled = -not $Running
    $script:NextButton.Enabled = -not $Running
    foreach ($page in @($script:PageSetup, $script:PageAssets, $script:PageArt)) { $page.Enabled = -not $Running }
    $script:Progress.Style = if ($Running) { 'Marquee' } else { 'Blocks' }
    $script:Progress.Value = 0
}

function Stop-Worker {
    if ($null -eq $script:Process -or $script:Process.HasExited) { return }
    $script:Cancelled = $true
    $script:Status.Text = 'Arrêt des processus de compilation...'
    # A cooperative marker also makes command-line cancellation possible.
    [IO.File]::WriteAllText([IO.Path]::ChangeExtension($script:ConfigFile, '.cancel'), 'cancel')
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = Join-Path $env:SystemRoot 'System32\taskkill.exe'
    $start.Arguments = '/PID ' + $script:Process.Id + ' /T /F'
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $killer = [Diagnostics.Process]::Start($start)
    try { [void]$killer.WaitForExit(5000) } finally { $killer.Dispose() }
    Add-Log "`r`nArrêt demandé. Les sources et les sorties terminées précédentes sont conservées.`r`n"
}

function Get-Selections {
    return [ordered]@{
        devkitpro = $script:SdkBox.Text.Trim()
        python = $script:PythonBox.Text.Trim()
        output_base = $script:OutputBox.Text.Trim()
        jobs = [int]$script:Jobs.Value
        mode = $(if ($script:Mode.SelectedIndex -eq 1) { 'resume' } else { 'clean' })
        with_cia = [bool]$script:Cia.Checked
        copy_assets = [bool]$script:CopyAssets.Checked
        check_crc = [bool]$script:Crc.Checked
        mm_archive = $script:MmBox.Text.Trim()
        support_archive = $script:SupportBox.Text.Trim()
        icon = $script:IconBox.Text.Trim()
        banner = $script:BannerBox.Text.Trim()
    }
}

function Start-Worker([string]$Action) {
    try {
        if ($null -ne $script:Process -and -not $script:Process.HasExited) { return }
        $selection = Get-Selections
        if (-not (Test-Path -LiteralPath $script:Worker -PathType Leaf)) { throw 'Extraire le ZIP complet avant de lancer le wizard.' }
        if (-not (Test-Path -LiteralPath $selection.python -PathType Leaf)) {
            throw 'Choisir python.exe (3.10 ou ultérieur), normalement dans C:\devkitPro\msys2\mingw64\bin.'
        }
        if (-not $selection.output_base) { throw 'Choisir un dossier de sortie.' }
        if (-not (Test-Path -LiteralPath $selection.devkitpro -PathType Container)) { throw 'Choisir le dossier devkitPro.' }
        if ($Action -eq 'build' -and $selection.mode -eq 'clean') {
            $answer = [Windows.Forms.MessageBox]::Show($script:Form,
                "Le wizard conservera les anciens caches en les renommant, puis reconstruira le jeu et libultraship.`r`n`r`nAucune sauvegarde ni archive source ne sera supprimée. Continuer ?",
                'Reconstruction propre', [Windows.Forms.MessageBoxButtons]::YesNo, [Windows.Forms.MessageBoxIcon]::Question)
            if ($answer -ne [Windows.Forms.DialogResult]::Yes) { return }
        }
        [void][IO.Directory]::CreateDirectory($script:Logs)
        [void][IO.Directory]::CreateDirectory((Split-Path -Parent $script:Settings))
        Write-Json $script:Settings $selection
        $runDirectory = Join-Path $script:Logs ((Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 6))
        [void][IO.Directory]::CreateDirectory($runDirectory)
        $selection.icon = Export-Artwork $selection.icon (Join-Path $runDirectory 'icon.png') 48 48
        $selection.banner = Export-Artwork $selection.banner (Join-Path $runDirectory 'banner.png') 256 128
        $selection.output_base = [IO.Path]::GetFullPath($selection.output_base)
        $selection.devkitpro = [IO.Path]::GetFullPath($selection.devkitpro)
        $script:ConfigFile = Join-Path $runDirectory 'run.json'
        $script:OutLog = Join-Path $runDirectory 'stdout.log'
        $script:ErrLog = Join-Path $runDirectory 'stderr.log'
        Write-Json $script:ConfigFile $selection
        Close-Readers
        $script:LogBox.Clear()
        $script:Cancelled = $false
        $script:CurrentAction = $Action
        $script:LastStage = 'Démarrage du moteur Python'
        $script:Status.Text = $script:LastStage
        $script:Started = Get-Date
        $script:LastOutputTime = Get-Date
        $script:Tabs.SelectedTab = $script:PageLog
        Add-Log ("Dossier source : " + $script:Root + "`r`nLogs : " + $runDirectory + "`r`n")
        $arguments = @('-u', $script:Worker, '--config', $script:ConfigFile, '--action', $Action)
        $argumentString = ($arguments | ForEach-Object { ConvertTo-NativeArgument ([string]$_) }) -join ' '
        $env:PYTHONIOENCODING = 'utf-8'
        $env:PYTHONUNBUFFERED = '1'
        $options = @{
            FilePath = $selection.python; ArgumentList = $argumentString; WorkingDirectory = $script:Root
            PassThru = $true; WindowStyle = 'Hidden'
            RedirectStandardOutput = $script:OutLog; RedirectStandardError = $script:ErrLog
        }
        $script:Process = Start-Process @options
        $null = $script:Process.Handle
        Set-Running $true
    } catch {
        Set-Running $false
        Show-Error $_.Exception.Message
    }
}

try {
    $script:Form = [Windows.Forms.Form]::new()
    $script:Form.Text = '2Ship3DS | Wizard AUDIO-FIX v1.0.3-FPS60-AUTO'
    $script:Form.ClientSize = [Drawing.Size]::new(1000, 735)
    $script:Form.MinimumSize = [Drawing.Size]::new(1016, 620)
    $script:Form.StartPosition = 'CenterScreen'
    $script:Form.AutoScaleMode = 'Font'
    $script:Form.Font = [Drawing.Font]::new('Segoe UI', [single]9, [Drawing.FontStyle]::Regular)
    $title = Add-Label $script:Form '2Ship3DS — compilation guidée' 20 14 940 32
    $title.Font = [Drawing.Font]::new('Segoe UI', [single]17, [Drawing.FontStyle]::Bold)
    [void](Add-Label $script:Form 'Sources V2 AUDIO-FIX · New Nintendo 3DS · aucun téléchargement ou changement du code du jeu par le wizard' 22 49 950)

    $script:Tabs = [Windows.Forms.TabControl]::new()
    $script:Tabs.Location = [Drawing.Point]::new(12, 80)
    $script:Tabs.Size = [Drawing.Size]::new(976, 537)
    $script:Tabs.Anchor = 'Top, Bottom, Left, Right'
    $script:Form.Controls.Add($script:Tabs)
    $pages = @()
    foreach ($name in @('1 · Compilation', '2 · Archives', '3 · Icône et bannière', '4 · Journal')) {
        $page = [Windows.Forms.TabPage]::new($name)
        $page.AutoScroll = $true
        $script:Tabs.TabPages.Add($page)
        $pages += $page
    }
    $script:PageSetup, $script:PageAssets, $script:PageArt, $script:PageLog = $pages

    $script:SdkBox = Add-PathRow $script:PageSetup 'Dossier devkitPro' 18 'folder'
    $script:PythonBox = Add-PathRow $script:PageSetup 'Python 3.10+ utilisé par le wizard (celui de devkitPro est recommandé)' 93 'file' 'Python|python.exe|Exécutables|*.exe'
    $script:OutputBox = Add-PathRow $script:PageSetup 'Dossier des résultats — chaque compilation crée son propre sous-dossier BUILD-...' 168 'folder'
    [void](Add-Label $script:PageSetup 'Tâches parallèles' 20 258 170)
    $script:Jobs = [Windows.Forms.NumericUpDown]::new()
    $script:Jobs.Location = [Drawing.Point]::new(200, 255)
    $script:Jobs.Size = [Drawing.Size]::new(78, 27)
    $script:Jobs.Minimum = 1; $script:Jobs.Maximum = 64; $script:Jobs.Value = 4
    $script:PageSetup.Controls.Add($script:Jobs)
    $detect = Add-Button $script:PageSetup 'Redétecter Python' 620 251 185
    $detect.Add_Click({
        try {
            $found = Find-Python $script:SdkBox.Text
            if ($found) { $script:PythonBox.Text = $found; $script:LastAutoPython = $found }
            else { Show-Error 'python.exe non trouvé. Le choisir avec Parcourir.' }
        } catch { Show-Error $_.Exception.Message }
    })
    [void](Add-Label $script:PageSetup 'Mode de reconstruction' 20 304 300)
    $script:Mode = [Windows.Forms.ComboBox]::new()
    $script:Mode.DropDownStyle = 'DropDownList'
    $script:Mode.Location = [Drawing.Point]::new(20, 330)
    $script:Mode.Size = [Drawing.Size]::new(910, 30)
    $script:Mode.Anchor = 'Top, Left, Right'
    [void]$script:Mode.Items.Add('Reconstruction propre — conserver et remplacer les caches du jeu ET de libultraship')
    [void]$script:Mode.Items.Add('Reprendre la compilation — réutiliser les caches compatibles de ce même dossier')
    $script:Mode.SelectedIndex = 0
    $script:PageSetup.Controls.Add($script:Mode)
    $script:Cia = [Windows.Forms.CheckBox]::new()
    $script:Cia.Text = 'Créer également le CIA (le packager produit aussi un CCI .3ds de vérification)'
    $script:Cia.Checked = $true
    $script:Cia.SetBounds(20, 378, 920, 30)
    $script:PageSetup.Controls.Add($script:Cia)
    [void](Add-Label $script:PageSetup "Le 3DSX et le SMDH sont toujours produits. Aucun ancien ELF n'est simplement reconditionné.`r`nLa chaîne devkitPro et ses bibliothèques ARM/3DS doivent déjà être installées; le wizard signale ce qui manque." 20 424 913 65)

    $script:CopyAssets = [Windows.Forms.CheckBox]::new()
    $script:CopyAssets.Text = 'Copier mes archives existantes dans la sortie (facultatif pour compiler)'
    $script:CopyAssets.SetBounds(20, 18, 900, 30)
    $script:PageAssets.Controls.Add($script:CopyAssets)
    $script:MmBox = Add-PathRow $script:PageAssets 'Archive du jeu — mm.o2r (2Ship 5.x)' 70 'file' 'Archives O2R|*.o2r'
    $script:SupportBox = Add-PathRow $script:PageAssets 'Archive support — 2ship.o2r (version 5.0.1)' 148 'file' 'Archives O2R|*.o2r'
    $fromSd = Add-Button $script:PageAssets 'Chercher depuis une SD / un dossier...' 20 232 335
    $fromSd.Add_Click({
        try {
            $dialog = [Windows.Forms.FolderBrowserDialog]::new()
            $dialog.Description = 'Choisir la racine de la carte SD ou le dossier contenant les deux archives.'
            $dialog.ShowNewFolderButton = $false
            foreach ($drive in [IO.DriveInfo]::GetDrives()) {
                if ($drive.IsReady -and $drive.DriveType -eq [IO.DriveType]::Removable) {
                    $dialog.SelectedPath = $drive.RootDirectory.FullName; break
                }
            }
            try {
                if ($dialog.ShowDialog($script:Form) -eq [Windows.Forms.DialogResult]::OK) {
                    $base = $dialog.SelectedPath
                    $found = $false
                    foreach ($candidate in @($base, (Join-Path $base '3ds\2ship'), (Join-Path $base 'SD\3ds\2ship'), (Join-Path $base '2ship'))) {
                        $mm = Join-Path $candidate 'mm.o2r'
                        $support = Join-Path $candidate '2ship.o2r'
                        if ((Test-Path -LiteralPath $mm -PathType Leaf) -and (Test-Path -LiteralPath $support -PathType Leaf)) {
                            $script:MmBox.Text = $mm; $script:SupportBox.Text = $support
                            $script:CopyAssets.Checked = $true; $found = $true; break
                        }
                    }
                    if (-not $found) { Show-Error 'Les deux archives ne sont pas présentes dans ce dossier. Les sélectionner individuellement avec Parcourir.' }
                }
            } finally { $dialog.Dispose() }
        } catch { Show-Error $_.Exception.Message }
    })
    $script:Crc = [Windows.Forms.CheckBox]::new()
    $script:Crc.Text = 'Vérifier intégralement les CRC des archives sélectionnées (recommandé)'
    $script:Crc.Checked = $true
    $script:Crc.SetBounds(20, 286, 910, 30)
    $script:PageAssets.Controls.Add($script:Crc)
    [void](Add-Label $script:PageAssets "Aucune ROM n'est extraite. Les archives .otr/MPQ ne sont pas converties ni acceptées par renommage.`r`n`r`nSans copie d'archives, garder les fichiers compatibles déjà présents dans /3ds/2ship/ sur ta SD.`r`nAvec copie, les entrées ZIP, la version et les empreintes sont contrôlées, mais pas chaque ressource du jeu.`r`n`r`nLe wizard n'écrit rien directement sur la carte SD et ne touche pas aux sauvegardes ou réglages." 20 341 910 148)

    $script:IconBox = Add-PathRow $script:PageArt 'Icône — laisser vide pour conserver le visuel par défaut' 25 'file' 'Images ou SMDH|*.png;*.jpg;*.jpeg;*.bmp;*.smdh|Tous les fichiers|*.*'
    $script:BannerBox = Add-PathRow $script:PageArt 'Bannière CIA — laisser vide pour conserver le visuel par défaut' 108 'file' 'Images ou bannière compilée|*.png;*.jpg;*.jpeg;*.bmp;*.bnr;*.bin;*.banner|Tous les fichiers|*.*'
    $resetArt = Add-Button $script:PageArt 'Revenir aux visuels par défaut' 20 201 285
    $resetArt.Add_Click({ $script:IconBox.Text = ''; $script:BannerBox.Text = '' })
    [void](Add-Label $script:PageArt "Les images PNG/JPG/BMP sont redimensionnées dans une copie temporaire :`r`n`r`nIcône : 48 × 48 pixels. Bannière : 256 × 128 pixels.`r`nLe rapport largeur/hauteur est conservé; des marges noires peuvent être ajoutées.`r`n`r`nUne icône .smdh ou une bannière .bnr/.bin/.banner déjà compilée est utilisée telle quelle après contrôle.`r`nAvec une image de bannière, le son de bannière reste silencieux. Une bannière compilée conserve son propre son.`r`n`r`nLes visuels d'origine, le TitleID et le code du jeu ne sont pas modifiés." 20 263 910 220)

    $script:LogBox = [Windows.Forms.RichTextBox]::new()
    $script:LogBox.Dock = 'Fill'
    $script:LogBox.ReadOnly = $true
    $script:LogBox.WordWrap = $false
    $script:LogBox.Font = [Drawing.Font]::new('Consolas', [single]9)
    $script:LogBox.DetectUrls = $false
    $script:PageLog.Controls.Add($script:LogBox)
    $script:Status = Add-Label $script:Form 'Prêt. Vérifier les chemins, puis cliquer sur Compiler.' 18 628 960 25
    $script:Status.Anchor = 'Bottom, Left, Right'
    $script:Progress = [Windows.Forms.ProgressBar]::new()
    $script:Progress.SetBounds(18, 659, 964, 7)
    $script:Progress.Anchor = 'Bottom, Left, Right'
    $script:Form.Controls.Add($script:Progress)
    $script:PreviousButton = Add-Button $script:Form 'Précédent' 18 682 105
    $script:NextButton = Add-Button $script:Form 'Suivant' 132 682 105
    $script:CheckButton = Add-Button $script:Form 'Vérifier' 255 682 110
    $script:BuildButton = Add-Button $script:Form 'Compiler' 375 682 126
    $script:StopButton = Add-Button $script:Form 'Arrêter' 511 682 95
    $script:OpenButton = Add-Button $script:Form 'Ouvrir le résultat' 628 682 180
    $script:LogsButton = Add-Button $script:Form 'Ouvrir les logs' 818 682 164
    foreach ($button in @($script:PreviousButton, $script:NextButton, $script:CheckButton, $script:BuildButton, $script:StopButton, $script:OpenButton, $script:LogsButton)) {
        $button.Anchor = 'Bottom, Left'
    }
    $script:StopButton.Enabled = $false
    $script:OpenButton.Enabled = $false
    $script:PreviousButton.Add_Click({ if ($script:Tabs.SelectedIndex -gt 0) { $script:Tabs.SelectedIndex-- } })
    $script:NextButton.Add_Click({ if ($script:Tabs.SelectedIndex -lt 3) { $script:Tabs.SelectedIndex++ } })
    $script:CheckButton.Add_Click({ Start-Worker 'check' })
    $script:BuildButton.Add_Click({ Start-Worker 'build' })
    $script:StopButton.Add_Click({ try { Stop-Worker } catch { Show-Error $_.Exception.Message } })
    $script:OpenButton.Add_Click({
        if (Test-Path -LiteralPath $script:ResultFolder -PathType Container) { Start-Process explorer.exe -ArgumentList (ConvertTo-NativeArgument $script:ResultFolder) }
    })
    $script:LogsButton.Add_Click({
        try {
            [void][IO.Directory]::CreateDirectory($script:Logs)
            Start-Process explorer.exe -ArgumentList (ConvertTo-NativeArgument $script:Logs)
        } catch { Show-Error $_.Exception.Message }
    })
    $script:SdkBox.Text = Find-Sdk
    $script:PythonBox.Text = Find-Python $script:SdkBox.Text
    $script:LastAutoPython = $script:PythonBox.Text
    $script:OutputBox.Text = Join-Path $script:Root 'dist-wizard'
    if (Test-Path -LiteralPath $script:Settings -PathType Leaf) {
        try {
            $saved = [IO.File]::ReadAllText($script:Settings, [Text.Encoding]::UTF8) | ConvertFrom-Json
            foreach ($pair in @(@('devkitpro', $script:SdkBox), @('python', $script:PythonBox), @('output_base', $script:OutputBox), @('mm_archive', $script:MmBox), @('support_archive', $script:SupportBox), @('icon', $script:IconBox), @('banner', $script:BannerBox))) {
                if ($saved.PSObject.Properties.Name -contains $pair[0]) { $pair[1].Text = [string]$saved.($pair[0]) }
            }
            if ($saved.PSObject.Properties.Name -contains 'jobs') { $script:Jobs.Value = [Math]::Max(1, [Math]::Min(64, [int]$saved.jobs)) }
            foreach ($pair in @(@('with_cia', $script:Cia), @('copy_assets', $script:CopyAssets), @('check_crc', $script:Crc))) {
                if ($saved.PSObject.Properties.Name -contains $pair[0]) { $pair[1].Checked = [bool]$saved.($pair[0]) }
            }
            # Always default to a clean rebuild on a new GUI session, rather than
            # silently trusting a saved choice from another source location.
        } catch { Add-Log ("Préférences ignorées : " + $_.Exception.Message + "`r`n") }
    }
    $script:SdkBox.Add_TextChanged({
        try {
            if (-not $script:PythonBox.Text -or $script:PythonBox.Text -eq $script:LastAutoPython) {
                $found = Find-Python $script:SdkBox.Text
                if ($found) { $script:PythonBox.Text = $found; $script:LastAutoPython = $found }
            }
        } catch { }
    })

    $timer = [Windows.Forms.Timer]::new()
    $timer.Interval = 400
    $timer.Add_Tick({
        if ($script:PollBusy -or $null -eq $script:Process) { return }
        $script:PollBusy = $true
        try {
            Read-LogUpdates
            $state = $null
            $path = [IO.Path]::ChangeExtension($script:ConfigFile, '.status.json')
            if (Test-Path -LiteralPath $path) {
                try { $state = [IO.File]::ReadAllText($path, [Text.Encoding]::UTF8) | ConvertFrom-Json } catch { }
            }
            if ($state) { $script:LastStage = $state.stage }
            $elapsed = [int]((Get-Date) - $script:Started).TotalSeconds
            $quiet = [int]((Get-Date) - $script:LastOutputTime).TotalSeconds
            $suffix = if ($quiet -ge 30) { " — aucune nouvelle ligne depuis ${quiet}s (processus encore actif)" } else { '' }
            $script:Status.Text = $script:LastStage + " — ${elapsed}s écoulées" + $suffix
            if ($script:Process.HasExited) {
                $script:Process.WaitForExit()
                Read-LogUpdates
                $code = $script:Process.ExitCode
                Close-Readers
                Set-Running $false
                if ($script:Cancelled) { $script:Status.Text = 'Arrêté. Aucune relance automatique.' }
                elseif ($code -eq 0 -and $state -and $state.status -eq 'success') {
                    $script:ResultFolder = $state.output
                    $script:OpenButton.Enabled = $true
                    $script:Progress.Value = 100
                    $script:Status.Text = 'Compilation terminée. Ouvrir le résultat pour récupérer les nouveaux fichiers.'
                    [void][Windows.Forms.MessageBox]::Show($script:Form,
                        "Nouveaux fichiers :`r`n$($state.output)`r`n`r`nCopier le contenu de SD à la racine de la carte SD. Le résultat sonore reste à tester sur console.",
                        'Compilation terminée', [Windows.Forms.MessageBoxButtons]::OK, [Windows.Forms.MessageBoxIcon]::Information)
                } elseif ($code -eq 0 -and $state -and $state.status -eq 'checked') {
                    $script:Status.Text = 'Vérification réussie. Cliquer sur Compiler.'
                } else {
                    $script:Status.Text = "Échec (code $code). Voir la fin du journal et stderr.log; aucune relance automatique."
                    if ($state -and $state.PSObject.Properties.Name -contains 'error') { Add-Log ("`r`n" + $state.error + "`r`n") }
                }
                $script:Process.Dispose()
                $script:Process = $null
            }
        } catch {
            # Transient log sharing errors must not stop the timer or the build.
            $script:Status.Text = 'Lecture du journal : ' + $_.Exception.Message
        } finally { $script:PollBusy = $false }
    })
    $script:Form.Add_FormClosing({
        param($sender, $eventArgs)
        if ($null -ne $script:Process -and -not $script:Process.HasExited) {
            $answer = [Windows.Forms.MessageBox]::Show($script:Form,
                'Arrêter la compilation et fermer le wizard ?', 'Compilation en cours',
                [Windows.Forms.MessageBoxButtons]::YesNo, [Windows.Forms.MessageBoxIcon]::Question)
            if ($answer -ne [Windows.Forms.DialogResult]::Yes) { $eventArgs.Cancel = $true; return }
            try { Stop-Worker } catch { Show-Error $_.Exception.Message; $eventArgs.Cancel = $true }
        }
    })
    $area = [Windows.Forms.Screen]::PrimaryScreen.WorkingArea
    if ($script:Form.Height -gt ($area.Height - 20)) {
        $script:Form.Height = [Math]::Max(620, ($area.Height - 20))
    }
    $timer.Start()
    [Windows.Forms.Application]::Run($script:Form)
    $timer.Stop()
    $timer.Dispose()
    Close-Readers
    $script:Form.Dispose()
} catch {
    [void][Windows.Forms.MessageBox]::Show($_.Exception.ToString(), 'Erreur du wizard')
    Write-Error $_
    exit 1
}
