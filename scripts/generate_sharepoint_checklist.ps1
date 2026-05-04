<#
.SYNOPSIS
    Generates a SharePoint move checklist as CSV (easily opened in Excel).
.DESCRIPTION
    Scans the rollout folder and produces a checklist with columns:
    Current File Name | Proposed New Name | Destination Folder
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

Import-Module "$PSScriptRoot\rollout_helpers.psm1" -Force

# ── Main ───────────────────────────────────────────────────────────────────────

$RootPath = (Resolve-Path $Path).Path

if (-not (Test-Path $RootPath -PathType Container)) {
    Write-Error "Path not found: $RootPath"
    exit 1
}

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
    $group = Get-FranchiseGroup -FileName $file.Name -FilePath $file.FullName
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
        "Status"              = ""
    }
}

# Deduplicate proposed names
$seen = @{}
for ($i = 0; $i -lt $checklist.Count; $i++) {
    $key = "$($checklist[$i].'Destination Folder')\$($checklist[$i].'Proposed New Name')"
    if ($seen.ContainsKey($key)) {
        $seen[$key]++
        $oldName = $checklist[$i].'Proposed New Name'
        $checklist[$i].'Proposed New Name' = $oldName -replace '(\.[^.]+)$', "_$($seen[$key])`$1"
    } else {
        $seen[$key] = 0
    }
}

$checklist | Export-Csv -Path $OutputFile -NoTypeInformation -Encoding UTF8

Write-Host ""
Write-Host "SharePoint move checklist generated!" -ForegroundColor Green
Write-Host "  File: $OutputFile"
Write-Host "  Entries: $($checklist.Count)"
Write-Host ""
Write-Host "Open this CSV in Excel to use as your manual move checklist." -ForegroundColor Cyan
