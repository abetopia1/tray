<#
.SYNOPSIS
    Fuzzy's Taco Shop Toast POS Rollout — File Organizer
.DESCRIPTION
    Scans a folder of rollout files (transcripts, PowerPoints, Word docs, Excel trackers),
    proposes a reorganized folder structure by franchise group, and optionally executes the plan.

    Franchise Groups: JRG, MarcRogers, BryantIrving, Copperfield (+ auto-detected)
    Catch-all folders: _Templates, _Internal, _Archive

    Naming convention: YYYY-MM-DD_GroupName_Description.ext
.PARAMETER Path
    Root folder containing the rollout files. Defaults to current directory.
.PARAMETER Execute
    If set, actually moves and renames files. Without this flag, only a dry-run plan is shown.
.PARAMETER LogFile
    Path for the reorganization log. Defaults to _reorganization_log.txt in the target folder.
.EXAMPLE
    # Dry run — just show the plan
    .\organize_rollout.ps1 -Path "C:\Users\Abe\OneDrive\Fuzzys Toast Rollout"

    # Execute the plan
    .\organize_rollout.ps1 -Path "C:\Users\Abe\OneDrive\Fuzzys Toast Rollout" -Execute
#>

param(
    [string]$Path = (Get-Location).Path,
    [switch]$Execute,
    [string]$LogFile = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Configuration ──────────────────────────────────────────────────────────────

$FranchiseGroups = @{
    "JRG"          = @("JRG", "Jobs Restaurant", "Jobs Rest")
    "MarcRogers"   = @("Marc Rogers", "MarcRogers", "Marc_Rogers", "Rogers Group")
    "BryantIrving" = @("Bryant Irving", "BryantIrving", "Bryant_Irving", "Bryant-Irving")
    "Copperfield"  = @("Copperfield", "Copper Field", "Copperfield's")
}

$TemplateKeywords = @("template", "checklist", "blank", "form", "guide", "how-to", "howto", "instructions")
$InternalKeywords = @("patrick", "executive", "internal", "deck", "leadership", "confidential", "update meeting")
$ArchiveKeywords  = @("old", "backup", "copy", "v1", "v2", "draft", "deprecated", "archive")

$DocumentExtensions = @(".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".pdf", ".txt", ".csv", ".msg", ".eml")

$FolderStructure = @(
    "_Templates",
    "_Internal",
    "_Archive",
    "JRG",
    "MarcRogers",
    "BryantIrving",
    "Copperfield"
)

# ── Helper Functions ───────────────────────────────────────────────────────────

function Get-CleanDescription {
    param([string]$FileName)

    $name = [System.IO.Path]::GetFileNameWithoutExtension($FileName)

    # Remove existing date patterns
    $name = $name -replace '^\d{4}[-_]\d{2}[-_]\d{2}[-_]?', ''
    $name = $name -replace '^\d{2}[-_]\d{2}[-_]\d{4}[-_]?', ''
    $name = $name -replace '^\d{2}[-_]\d{2}[-_]\d{2}[-_]?', ''

    # Remove group name prefixes (will be re-added in new format)
    foreach ($group in $FranchiseGroups.Keys) {
        foreach ($alias in $FranchiseGroups[$group]) {
            $escaped = [regex]::Escape($alias)
            $name = $name -replace "^${escaped}[-_\s]*", '' -replace "[-_\s]*${escaped}$", ''
        }
    }

    # Clean up separators: replace spaces/dashes/underscores with underscores, trim
    $name = $name.Trim(' ', '-', '_')
    $name = $name -replace '[\s\-]+', '_'
    $name = $name -replace '_+', '_'
    $name = $name.Trim('_')

    if ([string]::IsNullOrWhiteSpace($name)) {
        $name = "Document"
    }

    return $name
}

function Get-DateFromFileName {
    param([string]$FileName, [System.IO.FileInfo]$FileInfo)

    # Try YYYY-MM-DD
    if ($FileName -match '(\d{4})[-_](\d{2})[-_](\d{2})') {
        try {
            return [datetime]::ParseExact("$($Matches[1])-$($Matches[2])-$($Matches[3])", "yyyy-MM-dd", $null)
        } catch {}
    }

    # Try MM-DD-YYYY
    if ($FileName -match '(\d{2})[-_](\d{2})[-_](\d{4})') {
        try {
            return [datetime]::ParseExact("$($Matches[1])-$($Matches[2])-$($Matches[3])", "MM-dd-yyyy", $null)
        } catch {}
    }

    # Fall back to file last modified date
    return $FileInfo.LastWriteTime
}

function Get-FranchiseGroup {
    param([string]$FileName, [string]$FilePath)

    $fileNameLower = $FileName.ToLower()

    # Check filename first
    foreach ($group in $FranchiseGroups.Keys) {
        foreach ($alias in $FranchiseGroups[$group]) {
            if ($fileNameLower -match [regex]::Escape($alias.ToLower())) {
                return $group
            }
        }
    }

    # If ambiguous, try reading first lines of text-based files
    $ext = [System.IO.Path]::GetExtension($FilePath).ToLower()
    if ($ext -in @(".txt", ".csv")) {
        try {
            $firstLines = Get-Content -Path $FilePath -TotalCount 30 -ErrorAction SilentlyContinue
            $content = $firstLines -join " "
            $contentLower = $content.ToLower()

            foreach ($group in $FranchiseGroups.Keys) {
                foreach ($alias in $FranchiseGroups[$group]) {
                    if ($contentLower -match [regex]::Escape($alias.ToLower())) {
                        return $group
                    }
                }
            }
        } catch {}
    }

    return $null
}

function Get-SpecialFolder {
    param([string]$FileName)

    $fileNameLower = $FileName.ToLower()

    foreach ($kw in $TemplateKeywords) {
        if ($fileNameLower -match [regex]::Escape($kw)) { return "_Templates" }
    }

    foreach ($kw in $InternalKeywords) {
        if ($fileNameLower -match [regex]::Escape($kw)) { return "_Internal" }
    }

    # Check for version patterns suggesting archive
    if ($fileNameLower -match '\((\d+)\)' -or $fileNameLower -match '_v\d+') {
        return "_Archive"
    }

    foreach ($kw in $ArchiveKeywords) {
        if ($fileNameLower -match [regex]::Escape($kw)) { return "_Archive" }
    }

    return $null
}

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
Write-Host "  Source:  $RootPath"
Write-Host "  Mode:    $(if ($Execute) { 'EXECUTE' } else { 'DRY RUN' })"
Write-Host ""

# Collect files from root (non-recursive to avoid reorganizing already-sorted subfolders)
$files = Get-ChildItem -Path $RootPath -File | Where-Object {
    $_.Extension.ToLower() -in $DocumentExtensions -and
    $_.Name -notlike "_*"  # Skip log/config files
}

if ($files.Count -eq 0) {
    Write-Host "No document files found in root of: $RootPath" -ForegroundColor Yellow
    Write-Host "Supported extensions: $($DocumentExtensions -join ', ')"
    exit 0
}

Write-Host "Found $($files.Count) document file(s) to organize.`n" -ForegroundColor Green

# Build the plan
$plan = @()
$detectedGroups = @{}

foreach ($file in $files) {
    $group = Get-FranchiseGroup -FileName $file.Name -FilePath $file.FullName
    $specialFolder = Get-SpecialFolder -FileName $file.Name
    $fileDate = Get-DateFromFileName -FileName $file.Name -FileInfo $file
    $description = Get-CleanDescription -FileName $file.Name
    $ext = $file.Extension

    # Determine destination folder
    if ($specialFolder) {
        $destFolder = $specialFolder
    } elseif ($group) {
        $destFolder = $group
        $detectedGroups[$group] = $true
    } else {
        # Unknown group — place in a catch-all
        $destFolder = "_Unsorted"
    }

    # Build new filename
    $dateStr = $fileDate.ToString("yyyy-MM-dd")
    if ($group -and -not $specialFolder) {
        $newName = "${dateStr}_${group}_${description}${ext}"
    } else {
        $newName = "${dateStr}_${description}${ext}"
    }

    # Avoid duplicate names
    $destPath = Join-Path $RootPath $destFolder
    $fullDest = Join-Path $destPath $newName
    $counter = 1
    while (($plan | Where-Object { $_.DestinationFull -eq $fullDest }) -or (Test-Path $fullDest)) {
        $newName = "${dateStr}_${description}_$counter${ext}"
        $fullDest = Join-Path $destPath $newName
        $counter++
    }

    $plan += [PSCustomObject]@{
        OriginalName    = $file.Name
        OriginalPath    = $file.FullName
        DestinationDir  = $destFolder
        NewName         = $newName
        DestinationFull = $fullDest
        DetectedGroup   = if ($group) { $group } else { "(none)" }
        DetectedDate    = $dateStr
    }
}

# Add _Unsorted to folder list if needed
if ($plan | Where-Object { $_.DestinationDir -eq "_Unsorted" }) {
    $FolderStructure += "_Unsorted"
}

# ── Display Plan ───────────────────────────────────────────────────────────────

Write-Host "─── PROPOSED FOLDER STRUCTURE ───" -ForegroundColor Yellow
Write-Host ""
Write-Host "  $RootPath\" -ForegroundColor White
foreach ($folder in ($FolderStructure | Sort-Object)) {
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

Write-Host "EXECUTING file moves..." -ForegroundColor Magenta
Write-Host ""

$logEntries = @()
$logEntries += "Fuzzy's Toast Rollout — Reorganization Log"
$logEntries += "Executed: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$logEntries += "Source: $RootPath"
$logEntries += "=" * 60

# Create folder structure
foreach ($folder in ($FolderStructure | Sort-Object)) {
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

        Move-Item -Path $item.OriginalPath -Destination $item.DestinationFull -Force
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
