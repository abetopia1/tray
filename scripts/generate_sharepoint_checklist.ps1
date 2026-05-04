<#
.SYNOPSIS
    Generates a SharePoint move checklist as CSV (easily opened in Excel).
.DESCRIPTION
    Scans the rollout folder and produces a checklist with columns:
    Current File Name | Proposed New Name | Destination Folder
.PARAMETER Path
    Root folder containing the rollout files.
.PARAMETER Recursive
    If set, scans subfolders for files too.
.PARAMETER OutputFile
    Output CSV path. Defaults to _sharepoint_move_checklist.csv in the target folder.
.EXAMPLE
    .\generate_sharepoint_checklist.ps1 -Path "C:\Users\Abe\OneDrive\Fuzzys Toast Rollout"
#>

param(
    [string]$Path = (Get-Location).Path,
    [switch]$Recursive,
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

$files = Get-RolloutFiles -Path $RootPath -Recursive:$Recursive

if ($files.Count -eq 0) {
    Write-Host "No document files found." -ForegroundColor Yellow
    exit 0
}

$checklist = @()

foreach ($file in $files) {
    $info = Get-FileClassification -File $file -RootPath $RootPath

    $newName = "$($info.BaseName)$($info.Extension)"

    $checklist += [PSCustomObject]@{
        "Current File Name"   = $file.Name
        "Proposed New Name"   = $newName
        "Destination Folder"  = $info.DestFolder
        "Detected Group"      = if ($info.Group) { $info.Group } else { "" }
        "File Date"           = $info.DateStr
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
