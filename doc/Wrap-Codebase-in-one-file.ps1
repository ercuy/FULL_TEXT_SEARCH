
<# 
Concateneer toegelaten bronbestanden vanuit een root + subfolders naar 1 outputbestand:
  1) "### FILENAME = <full path>" per bestand,
  2) bovenaan een schema ("### SCHEMA = "),
  3) 8 lege lijnen tussen opeenvolgende bestanden,
  4) parameters voor root, extensies en te excluderen folders,
  5) per bestand lijnnummers (3 posities) + 3 spaties indent.

Gebruik (voorbeeld):
  .\Wrap-Codebase-in-one-file.ps1 `
    -Root 'C:\AUTOMATION\PYTHON\POC_GuardTool' `
    -AllowedExtensions @('.json','.toml','.py') `
    -ExcludeFolders @('.git','.vscode','.venv','__pycache__','node_modules')
  # Zonder -OutputFile -> CODEBASE.TXT in de $Root-map
#>

param(
    [Parameter(Mandatory = $false)]
    [string]$Root = 'C:\AUTOMATION\PYTHON\FULL_TEXT_SEARCH', 

    [Parameter(Mandatory = $false)]
    [string[]]$AllowedExtensions = @('.json', '.toml', '.py', '.ipynb', '.sql','.html','.css'),
    # [string[]]$AllowedExtensions = @('.sql'),

    [Parameter(Mandatory = $false)]
    [string[]]$ExcludeFolders = @(
        '.git', '.vscode', '.venv', '__pycache__', 'node_modules', '.idea',
        'dist', 'build', '.pytest_cache', '.mypy_cache', '.ruff_cache',
        '.tox', '.eggs', '.svn', '.hg'
    ),

    [Parameter(Mandatory = $false)]
    [string]$OutputFile = $null
)

# -- Validatie + Output default in $Root --
if (-not (Test-Path -Path $Root -PathType Container)) {
    Write-Host "Root-map niet gevonden: $Root" -ForegroundColor Red
    exit 1
}
if (-not $OutputFile) {
    $OutputFile = Join-Path $Root 'doc/CODEBASE.TXT'
}

# -- Helpers --
function Convert-Exts {
    param([string[]]$Exts)
    $Exts | ForEach-Object {
        $e = "$_".Trim().ToLower()
        if ($e -and $e -notmatch '^\.') { ".$e" } else { $e }
    }
}

function Test-IsExcluded {
    param([string]$Path, [string[]]$Folders)
    if (-not $Path) { return $false }
    $segments = ($Path -split '[\\/]').ForEach({ $_.ToLower() })
    $ex = $Folders.ForEach({ $_.Trim().ToLower() }) | Where-Object { $_ -ne '' }
    foreach ($f in $ex) {
        if ($segments -contains $f) { return $true }
    }
    return $false
}

function Get-AllowedFiles {
    param([string]$BasePath, [string[]]$Exts, [string[]]$Excl)
    $normalized = Convert-Exts -Exts $Exts
    Get-ChildItem -Path $BasePath -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object {
        -not (Test-IsExcluded -Path $_.FullName -Folders $Excl) -and
        ($normalized -contains $_.Extension.ToLower())
    } |
    Sort-Object FullName
}

function Get-TreeLines {
    param([string]$BasePath, [string[]]$Exts, [string[]]$Excl)
    $lines = New-Object System.Collections.Generic.List[string]
    $normExts = Convert-Exts -Exts $Exts

    $BRANCH = '|-- '
    $LAST = '\-- '
    $PIPE = '|   '
    $SPACE = '    '

    function Add-Node {
        param([string]$Path, [string]$Prefix)
        if (Test-IsExcluded -Path $Path -Folders $Excl) { return }

        $dirs = Get-ChildItem -Path $Path -Directory -ErrorAction SilentlyContinue |
        Where-Object { -not (Test-IsExcluded -Path $_.FullName -Folders $Excl) } |
        Sort-Object Name

        $files = Get-ChildItem -Path $Path -File -ErrorAction SilentlyContinue |
        Where-Object {
            -not (Test-IsExcluded -Path $_.FullName -Folders $Excl) -and
            ($normExts -contains $_.Extension.ToLower())
        } | Sort-Object Name

        $items = @(); $items += $dirs; $items += $files
        for ($i = 0; $i -lt $items.Count; $i++) {
            $isLast = ($i -eq $items.Count - 1)
            $connector = if ($isLast) { $LAST } else { $BRANCH }
            $newPrefix = if ($isLast) { "$Prefix$SPACE" } else { "$Prefix$PIPE" }

            if ($items[$i].PSIsContainer) {
                $lines.Add("$Prefix$connector$($items[$i].Name)/")
                Add-Node -Path $items[$i].FullName -Prefix $newPrefix
            }
            else {
                $lines.Add("$Prefix$connector$($items[$i].Name)")
            }
        }
    }

    $rootName = Split-Path -Path $BasePath -Leaf
    $lines.Add("$rootName/")
    Add-Node -Path $BasePath -Prefix ''
    return $lines
}

# -- Main --
$normalizedExts = Convert-Exts -Exts $AllowedExtensions
$files = Get-AllowedFiles -BasePath $Root -Exts $normalizedExts -Excl $ExcludeFolders
if (-not $files -or $files.Count -eq 0) {
    Write-Host "Geen bestanden gevonden met extensies $($AllowedExtensions -join ', ') in '$Root'." -ForegroundColor Yellow
    exit 0
}

$schemaLines = Get-TreeLines -BasePath $Root -Exts $normalizedExts -Excl $ExcludeFolders

$nl = "`r`n"
Set-Content -Path $OutputFile -Value "### SCHEMA = $nl$($schemaLines -join $nl)$nl$nl" -Encoding UTF8

for ($idx = 0; $idx -lt $files.Count; $idx++) {
    $f = $files[$idx]
    Add-Content -Path $OutputFile -Value "### FILENAME = $($f.FullName)$nl" -Encoding UTF8

    $contentLines = Get-Content -Path $f.FullName -ErrorAction SilentlyContinue
    if ($null -ne $contentLines) {
        # Lijnnummers (3 posities) + 3 spaties; reset per bestand
        $numbered = for ($ln = 0; $ln -lt $contentLines.Count; $ln++) {
            '{0:D3}   {1}' -f ($ln + 1), $contentLines[$ln]
        }
        Add-Content -Path $OutputFile -Value $numbered -Encoding UTF8
        Add-Content -Path $OutputFile -Value $nl -Encoding UTF8
    }
    else {
        Add-Content -Path $OutputFile -Value "# [WAARSCHUWING] Kon inhoud niet lezen: $($f.FullName)$nl" -Encoding UTF8
    }

    if ($idx -lt ($files.Count - 1)) {
        Add-Content -Path $OutputFile -Value ($nl * 8) -Encoding UTF8
    }
}

Write-Host "Concatenatie voltooid. Output: $OutputFile" -ForegroundColor Green

