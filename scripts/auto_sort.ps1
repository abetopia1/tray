<#
.SYNOPSIS
    Fuzzy's Toast Rollout — Auto-Sort File Watcher
.DESCRIPTION
    Watches the rollout root folder for new files. When a new file appears,
    determines the correct franchise group subfolder, and prompts for confirmation
    before moving it using the standard naming convention.
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

Import-Module "$PSScriptRoot\rollout_helpers.psm1" -Force

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
            $ready = Wait-FileReady -FilePath $file.FullName
            if (-not $ready) {
                Write-Host "  [WARN] File still locked: $($file.Name) — will retry next cycle." -ForegroundColor DarkYellow
                continue
            }

            $info = Get-FileClassification -File $file -RootPath $RootPath
            $destPath = Join-Path $RootPath $info.DestFolder
            $fullDest = Get-SafeDestination -DestDir $destPath -BaseName $info.BaseName -Extension $info.Extension
            $newName = [System.IO.Path]::GetFileName($fullDest)

            Write-Host "─────────────────────────────────────" -ForegroundColor Yellow
            Write-Host "  NEW FILE DETECTED:" -ForegroundColor Yellow
            Write-Host "    Name:   $($file.Name)" -ForegroundColor White
            Write-Host "    Group:  $(if ($info.Group) { $info.Group } else { '(unknown)' })" -ForegroundColor Cyan
            Write-Host "    Move to: $($info.DestFolder)\$newName" -ForegroundColor Green
            Write-Host ""

            $confirm = Read-Host "  Move this file? [Y/n/s(kip)]"

            if ($confirm -eq '' -or $confirm.ToLower() -eq 'y') {
                try {
                    if (-not (Test-Path $destPath)) {
                        New-Item -ItemType Directory -Path $destPath -Force | Out-Null
                    }
                    Move-Item -Path $file.FullName -Destination $fullDest
                    Write-Host "  [OK] Moved successfully.`n" -ForegroundColor Green

                    $logLine = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | AUTO-SORT | $($file.Name) -> $($info.DestFolder)\$newName"
                    $logPath = Join-Path $RootPath "_reorganization_log.txt"
                    Add-Content -Path $logPath -Value $logLine
                } catch {
                    Write-Host "  [ERROR] $($_.Exception.Message)`n" -ForegroundColor Red
                }
            } else {
                Write-Host "  Skipped.`n" -ForegroundColor DarkGray
            }

            $processed[$file.FullName] = $true
        }

        Start-Sleep -Seconds 3
    }
}
finally {
    Write-Host "`nWatcher stopped." -ForegroundColor Yellow
}
