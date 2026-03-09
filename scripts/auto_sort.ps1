<#
.SYNOPSIS
    Fuzzy's Toast Rollout — Auto-Sort File Watcher
.DESCRIPTION
    Watches the rollout root folder for new files dropped in. When a new file appears,
    reads its name and content, determines the correct franchise group subfolder, and
    moves it using the standard naming convention (YYYY-MM-DD_GroupName_Description.ext).

    Prompts for confirmation before each move.
.PARAMETER Path
    Root folder to watch. Defaults to current directory.
.EXAMPLE
    .\auto_sort.ps1 -Path "C:\Users\Abe\OneDrive\Fuzzys Toast Rollout"
#>

param(
    [string]$Path = (Get-Location).Path
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Configuration (same as organize_rollout.ps1) ──────────────────────────────

$FranchiseGroups = @{
    "JRG"          = @("JRG", "Jobs Restaurant", "Jobs Rest")
    "MarcRogers"   = @("Marc Rogers", "MarcRogers", "Marc_Rogers", "Rogers Group")
    "BryantIrving" = @("Bryant Irving", "BryantIrving", "Bryant_Irving", "Bryant-Irving")
    "Copperfield"  = @("Copperfield", "Copper Field", "Copperfield's")
}

$TemplateKeywords = @("template", "checklist", "blank", "form", "guide", "how-to", "howto", "instructions")
$InternalKeywords = @("patrick", "executive", "internal", "deck", "leadership", "confidential", "update meeting")

$DocumentExtensions = @(".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".pdf", ".txt", ".csv", ".msg", ".eml")

# ── Helper Functions ───────────────────────────────────────────────────────────

function Get-CleanDescription {
    param([string]$FileName)
    $name = [System.IO.Path]::GetFileNameWithoutExtension($FileName)
    $name = $name -replace '^\d{4}[-_]\d{2}[-_]\d{2}[-_]?', ''
    $name = $name -replace '^\d{2}[-_]\d{2}[-_]\d{4}[-_]?', ''
    foreach ($group in $FranchiseGroups.Keys) {
        foreach ($alias in $FranchiseGroups[$group]) {
            $escaped = [regex]::Escape($alias)
            $name = $name -replace "^${escaped}[-_\s]*", '' -replace "[-_\s]*${escaped}$", ''
        }
    }
    $name = $name.Trim(' ', '-', '_') -replace '[\s\-]+', '_' -replace '_+', '_'
    $name = $name.Trim('_')
    if ([string]::IsNullOrWhiteSpace($name)) { $name = "Document" }
    return $name
}

function Get-FranchiseGroup {
    param([string]$FileName, [string]$FilePath)
    $fileNameLower = $FileName.ToLower()
    foreach ($group in $FranchiseGroups.Keys) {
        foreach ($alias in $FranchiseGroups[$group]) {
            if ($fileNameLower -match [regex]::Escape($alias.ToLower())) { return $group }
        }
    }
    # Try reading text files
    $ext = [System.IO.Path]::GetExtension($FilePath).ToLower()
    if ($ext -in @(".txt", ".csv")) {
        try {
            $content = (Get-Content -Path $FilePath -TotalCount 30 -ErrorAction SilentlyContinue) -join " "
            foreach ($group in $FranchiseGroups.Keys) {
                foreach ($alias in $FranchiseGroups[$group]) {
                    if ($content.ToLower() -match [regex]::Escape($alias.ToLower())) { return $group }
                }
            }
        } catch {}
    }
    return $null
}

function Get-SpecialFolder {
    param([string]$FileName)
    $lower = $FileName.ToLower()
    foreach ($kw in $TemplateKeywords) { if ($lower -match [regex]::Escape($kw)) { return "_Templates" } }
    foreach ($kw in $InternalKeywords) { if ($lower -match [regex]::Escape($kw)) { return "_Internal" } }
    return $null
}

function Get-DateFromFileName {
    param([string]$FileName)
    if ($FileName -match '(\d{4})[-_](\d{2})[-_](\d{2})') {
        try { return [datetime]::ParseExact("$($Matches[1])-$($Matches[2])-$($Matches[3])", "yyyy-MM-dd", $null) } catch {}
    }
    if ($FileName -match '(\d{2})[-_](\d{2})[-_](\d{4})') {
        try { return [datetime]::ParseExact("$($Matches[1])-$($Matches[2])-$($Matches[3])", "MM-dd-yyyy", $null) } catch {}
    }
    return (Get-Date)
}

# ── Watcher Setup ──────────────────────────────────────────────────────────────

$RootPath = (Resolve-Path $Path).Path

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Fuzzy's Toast Rollout — Auto-Sort Watcher" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Watching:  $RootPath"
Write-Host "  Extensions: $($DocumentExtensions -join ', ')"
Write-Host ""
Write-Host "  Press Ctrl+C to stop watching." -ForegroundColor DarkGray
Write-Host ""

$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path = $RootPath
$watcher.Filter = "*.*"
$watcher.IncludeSubdirectories = $false
$watcher.EnableRaisingEvents = $false  # We'll poll instead for interactive confirmation

# Track already-processed files to avoid duplicates
$processed = @{}

Write-Host "Watcher active. Waiting for new files...`n" -ForegroundColor Green

try {
    while ($true) {
        $newFiles = Get-ChildItem -Path $RootPath -File | Where-Object {
            $_.Extension.ToLower() -in $DocumentExtensions -and
            $_.Name -notlike "_*" -and
            -not $processed.ContainsKey($_.FullName)
        }

        foreach ($file in $newFiles) {
            # Small delay to ensure file is fully written
            Start-Sleep -Milliseconds 500

            $group = Get-FranchiseGroup -FileName $file.Name -FilePath $file.FullName
            $specialFolder = Get-SpecialFolder -FileName $file.Name
            $fileDate = Get-DateFromFileName -FileName $file.Name
            $description = Get-CleanDescription -FileName $file.Name
            $ext = $file.Extension
            $dateStr = $fileDate.ToString("yyyy-MM-dd")

            if ($specialFolder) {
                $destFolder = $specialFolder
            } elseif ($group) {
                $destFolder = $group
            } else {
                $destFolder = "_Unsorted"
            }

            if ($group -and -not $specialFolder) {
                $newName = "${dateStr}_${group}_${description}${ext}"
            } else {
                $newName = "${dateStr}_${description}${ext}"
            }

            $destPath = Join-Path $RootPath $destFolder
            $fullDest = Join-Path $destPath $newName

            # Prompt user
            Write-Host "─────────────────────────────────────" -ForegroundColor Yellow
            Write-Host "  NEW FILE DETECTED:" -ForegroundColor Yellow
            Write-Host "    Name:   $($file.Name)" -ForegroundColor White
            Write-Host "    Group:  $(if ($group) { $group } else { '(unknown)' })" -ForegroundColor Cyan
            Write-Host "    Move to: $destFolder\$newName" -ForegroundColor Green
            Write-Host ""

            $confirm = Read-Host "  Move this file? [Y/n/s(kip)]"

            if ($confirm -eq '' -or $confirm.ToLower() -eq 'y') {
                try {
                    if (-not (Test-Path $destPath)) {
                        New-Item -ItemType Directory -Path $destPath -Force | Out-Null
                    }
                    Move-Item -Path $file.FullName -Destination $fullDest -Force
                    Write-Host "  [OK] Moved successfully.`n" -ForegroundColor Green

                    # Log to file
                    $logLine = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | AUTO-SORT | $($file.Name) -> $destFolder\$newName"
                    $logFile = Join-Path $RootPath "_reorganization_log.txt"
                    Add-Content -Path $logFile -Value $logLine
                } catch {
                    Write-Host "  [ERROR] $($_.Exception.Message)`n" -ForegroundColor Red
                }
            } elseif ($confirm.ToLower() -eq 's') {
                Write-Host "  Skipped.`n" -ForegroundColor DarkGray
            } else {
                Write-Host "  Skipped.`n" -ForegroundColor DarkGray
            }

            $processed[$file.FullName] = $true
        }

        Start-Sleep -Seconds 3
    }
}
finally {
    $watcher.Dispose()
    Write-Host "`nWatcher stopped." -ForegroundColor Yellow
}
