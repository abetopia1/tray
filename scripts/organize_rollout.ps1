<#
.SYNOPSIS
    Fuzzy's Taco Shop Toast POS Rollout — File Organizer
.DESCRIPTION
    Scans a folder of rollout files (transcripts, PowerPoints, Word docs, Excel trackers),
    proposes a reorganized folder structure by franchise group, and optionally executes the plan.

    Naming convention: YYYY-MM-DD_GroupName_Description.ext
.PARAMETER Path
    Root folder containing the rollout files. Defaults to current directory.
.PARAMETER Execute
    If set, actually moves and renames files. Without this flag, only a dry-run plan is shown.
.PARAMETER Recursive
    If set, scans subfolders for files too (not just the root level).
.PARAMETER LogFile
    Path for the reorganization log. Defaults to _reorganization_log.txt in the target folder.
.EXAMPLE
    .\organize_rollout.ps1 -Path "C:\Users\Abe\OneDrive\Fuzzys Toast Rollout"
.EXAMPLE
    .\organize_rollout.ps1 -Path "C:\Users\Abe\OneDrive\Fuzzys Toast Rollout" -Execute
.EXAMPLE
    .\organize_rollout.ps1 -Path "C:\Users\Abe\OneDrive\Fuzzys Toast Rollout" -Recursive
#>

param(
    [string]$Path = (Get-Location).Path,
    [switch]$Execute,
    [switch]$Recursive,
    [string]$LogFile = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Import-Module "$PSScriptRoot\rollout_helpers.psm1" -Force

# ── Main Logic ─────────────────────────────────────────────────────────────────

$RootPath = (Resolve-Path $Path).Path

if (-not (Test-Path $RootPath -PathType Container)) {
    Write-Error "Path not found: $RootPath"
    exit 1
}

if ([string]::IsNullOrWhiteSpace($LogFile)) {
    $LogFile = Join-Path $RootPath "_reorganization_log.txt"
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Fuzzy's Toast Rollout — File Organizer" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Source:    $RootPath"
Write-Host "  Mode:      $(if ($Execute) { 'EXECUTE' } else { 'DRY RUN' })"
Write-Host "  Recursive: $(if ($Recursive) { 'YES' } else { 'NO' })"
Write-Host ""

$files = Get-RolloutFiles -Path $RootPath -Recursive:$Recursive

if ($files.Count -eq 0) {
    Write-Host "No document files found in: $RootPath" -ForegroundColor Yellow
    Write-Host "Supported extensions: $($DocumentExtensions -join ', ')"
    exit 0
}

Write-Host "Found $($files.Count) document file(s) to organize.`n" -ForegroundColor Green

# Build the plan
$plan = @()

foreach ($file in $files) {
    $info = Get-FileClassification -File $file -RootPath $RootPath
    $destPath = Join-Path $RootPath $info.DestFolder
    $fullDest = Get-SafeDestination -DestDir $destPath -BaseName $info.BaseName -Extension $info.Extension -ExistingPaths ($plan | ForEach-Object { $_.DestinationFull })
    $newName = [System.IO.Path]::GetFileName($fullDest)

    $plan += [PSCustomObject]@{
        OriginalName    = $file.Name
        OriginalPath    = $file.FullName
        DestinationDir  = $info.DestFolder
        NewName         = $newName
        DestinationFull = $fullDest
        DetectedGroup   = if ($info.Group) { $info.Group } else { "(none)" }
        DetectedDate    = $info.DateStr
    }
}

# Add _Unsorted to folder list if needed
$activeFolders = @($FolderStructure)
if ($plan | Where-Object { $_.DestinationDir -eq "_Unsorted" }) {
    $activeFolders += "_Unsorted"
}

# ── Display Plan ───────────────────────────────────────────────────────────────

Write-Host "─── PROPOSED FOLDER STRUCTURE ───" -ForegroundColor Yellow
Write-Host ""
Write-Host "  $RootPath\" -ForegroundColor White
foreach ($folder in ($activeFolders | Sort-Object)) {
    $count = ($plan | Where-Object { $_.DestinationDir -eq $folder }).Count
    if ($count -gt 0) {
        Write-Host "  ├── $folder\  ($count files)" -ForegroundColor Green
    } else {
        Write-Host "  ├── $folder\  (empty)" -ForegroundColor DarkGray
    }
}
Write-Host ""

Write-Host "─── FILE MOVE PLAN ───" -ForegroundColor Yellow
Write-Host ""

foreach ($item in $plan | Sort-Object DestinationDir, NewName) {
    Write-Host "  [$($item.DetectedGroup.PadRight(14))]  " -NoNewline -ForegroundColor DarkCyan
    Write-Host "$($item.OriginalName)" -ForegroundColor White
    Write-Host "                     -> $($item.DestinationDir)\$($item.NewName)" -ForegroundColor Green
    Write-Host ""
}

Write-Host "─── SUMMARY ───" -ForegroundColor Yellow
Write-Host "  Total files:       $($plan.Count)"
Write-Host "  Franchise groups:  $(($plan | Where-Object { $_.DetectedGroup -ne '(none)' } | Select-Object -ExpandProperty DetectedGroup -Unique) -join ', ')"
Write-Host "  Templates:         $(($plan | Where-Object { $_.DestinationDir -eq '_Templates' }).Count)"
Write-Host "  Internal:          $(($plan | Where-Object { $_.DestinationDir -eq '_Internal' }).Count)"
Write-Host "  Archive:           $(($plan | Where-Object { $_.DestinationDir -eq '_Archive' }).Count)"
Write-Host "  Unsorted:          $(($plan | Where-Object { $_.DestinationDir -eq '_Unsorted' }).Count)"
Write-Host ""

# ── Execute if requested ──────────────────────────────────────────────────────

if (-not $Execute) {
    Write-Host "This was a DRY RUN. No files were moved." -ForegroundColor Yellow
    Write-Host "To execute, run again with -Execute flag." -ForegroundColor Yellow
    Write-Host ""
    exit 0
}

# Confirmation prompt before destructive action
Write-Host "You are about to move and rename $($plan.Count) file(s)." -ForegroundColor Red
$confirm = Read-Host "Type YES to proceed"
if ($confirm -ne 'YES') {
    Write-Host "Aborted. No files were moved." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "EXECUTING file moves..." -ForegroundColor Magenta
Write-Host ""

$logEntries = @()
$logEntries += "Fuzzy's Toast Rollout — Reorganization Log"
$logEntries += "Executed: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$logEntries += "Source: $RootPath"
$logEntries += "=" * 60

foreach ($folder in ($activeFolders | Sort-Object)) {
    $folderPath = Join-Path $RootPath $folder
    if (-not (Test-Path $folderPath)) {
        New-Item -ItemType Directory -Path $folderPath -Force | Out-Null
        $msg = "CREATED FOLDER: $folder\"
        Write-Host "  $msg" -ForegroundColor DarkGreen
        $logEntries += $msg
    }
}

$logEntries += ""
$logEntries += "FILE MOVES:"
$logEntries += "-" * 60

$moved = 0
$errors = 0

foreach ($item in $plan | Sort-Object DestinationDir, NewName) {
    try {
        $destDir = Join-Path $RootPath $item.DestinationDir
        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        }

        Move-Item -Path $item.OriginalPath -Destination $item.DestinationFull
        $moved++

        $msg = "MOVED: $($item.OriginalName) -> $($item.DestinationDir)\$($item.NewName)"
        Write-Host "  [OK] $msg" -ForegroundColor Green
        $logEntries += $msg
    }
    catch {
        $errors++
        $msg = "ERROR: $($item.OriginalName) — $($_.Exception.Message)"
        Write-Host "  [!!] $msg" -ForegroundColor Red
        $logEntries += $msg
    }
}

$logEntries += ""
$logEntries += "=" * 60
$logEntries += "Completed: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$logEntries += "Moved: $moved | Errors: $errors | Total: $($plan.Count)"

$logEntries | Out-File -FilePath $LogFile -Encoding utf8
Write-Host ""
Write-Host "Done! Moved $moved file(s), $errors error(s)." -ForegroundColor Cyan
Write-Host "Log saved to: $LogFile" -ForegroundColor Cyan
