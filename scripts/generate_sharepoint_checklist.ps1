<#
.SYNOPSIS
    Generates a SharePoint move checklist as CSV (easily opened in Excel).
.DESCRIPTION
    Scans the rollout folder and produces a checklist with columns:
    Current File Name | Proposed New Name | Destination Folder

    Save output as .csv and open in Excel, or import into SharePoint.
.PARAMETER Path
    Root folder containing the rollout files.
.PARAMETER OutputFile
    Output CSV path. Defaults to _sharepoint_move_checklist.csv in the target folder.
.EXAMPLE
    .\generate_sharepoint_checklist.ps1 -Path "C:\Users\Abe\OneDrive\Fuzzys Toast Rollout"
#>

param(
    [string]$Path = (Get-Location).Path,
    [string]$OutputFile = ""
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

$DocumentExtensions = @(".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".pdf", ".txt", ".csv", ".msg", ".eml")

# ── Helpers ────────────────────────────────────────────────────────────────────

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
    param([string]$FileName)
    $lower = $FileName.ToLower()
    foreach ($group in $FranchiseGroups.Keys) {
        foreach ($alias in $FranchiseGroups[$group]) {
            if ($lower -match [regex]::Escape($alias.ToLower())) { return $group }
        }
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
    param([string]$FileName, [System.IO.FileInfo]$FileInfo)
    if ($FileName -match '(\d{4})[-_](\d{2})[-_](\d{2})') {
        try { return [datetime]::ParseExact("$($Matches[1])-$($Matches[2])-$($Matches[3])", "yyyy-MM-dd", $null) } catch {}
    }
    return $FileInfo.LastWriteTime
}

# ── Main ───────────────────────────────────────────────────────────────────────

$RootPath = (Resolve-Path $Path).Path

if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    $OutputFile = Join-Path $RootPath "_sharepoint_move_checklist.csv"
}

$files = Get-ChildItem -Path $RootPath -File | Where-Object {
    $_.Extension.ToLower() -in $DocumentExtensions -and $_.Name -notlike "_*"
}

if ($files.Count -eq 0) {
    Write-Host "No document files found." -ForegroundColor Yellow
    exit 0
}

$checklist = @()

foreach ($file in $files) {
    $group = Get-FranchiseGroup -FileName $file.Name
    $specialFolder = Get-SpecialFolder -FileName $file.Name
    $fileDate = Get-DateFromFileName -FileName $file.Name -FileInfo $file
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

    $checklist += [PSCustomObject]@{
        "Current File Name"   = $file.Name
        "Proposed New Name"   = $newName
        "Destination Folder"  = $destFolder
        "Detected Group"      = if ($group) { $group } else { "" }
        "File Date"           = $dateStr
        "Status"              = ""  # For manual tracking
    }
}

$checklist | Export-Csv -Path $OutputFile -NoTypeInformation -Encoding UTF8

Write-Host ""
Write-Host "SharePoint move checklist generated!" -ForegroundColor Green
Write-Host "  File: $OutputFile"
Write-Host "  Entries: $($checklist.Count)"
Write-Host ""
Write-Host "Open this CSV in Excel to use as your manual move checklist." -ForegroundColor Cyan
