# Fuzzy's Toast Rollout — Shared Helpers Module

Set-StrictMode -Version Latest

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

    $name = $name -replace '^\d{4}[-_]\d{2}[-_]\d{2}[-_]?', ''
    $name = $name -replace '^\d{2}[-_]\d{2}[-_]\d{4}[-_]?', ''
    $name = $name -replace '^\d{2}[-_]\d{2}[-_]\d{2}[-_]?', ''

    foreach ($group in $FranchiseGroups.Keys) {
        foreach ($alias in $FranchiseGroups[$group]) {
            $escaped = [regex]::Escape($alias)
            $name = $name -replace "^${escaped}[-_\s]*", '' -replace "[-_\s]*${escaped}$", ''
        }
    }

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
    param(
        [string]$FileName,
        [System.IO.FileInfo]$FileInfo = $null
    )

    if ($FileName -match '(\d{4})[-_](\d{2})[-_](\d{2})') {
        try {
            return [datetime]::ParseExact("$($Matches[1])-$($Matches[2])-$($Matches[3])", "yyyy-MM-dd", $null)
        } catch {}
    }

    if ($FileName -match '(\d{2})[-_](\d{2})[-_](\d{4})') {
        try {
            return [datetime]::ParseExact("$($Matches[1])-$($Matches[2])-$($Matches[3])", "MM-dd-yyyy", $null)
        } catch {}
    }

    if ($FileInfo) {
        return $FileInfo.LastWriteTime
    }
    return (Get-Date)
}

function Get-FranchiseGroup {
    param(
        [string]$FileName,
        [string]$FilePath = ""
    )

    $fileNameLower = $FileName.ToLower()

    foreach ($group in $FranchiseGroups.Keys) {
        foreach ($alias in $FranchiseGroups[$group]) {
            if ($fileNameLower -match [regex]::Escape($alias.ToLower())) {
                return $group
            }
        }
    }

    if ($FilePath -and (Test-Path $FilePath -ErrorAction SilentlyContinue)) {
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

    if ($fileNameLower -match '\((\d+)\)' -or $fileNameLower -match '_v\d+') {
        return "_Archive"
    }

    foreach ($kw in $ArchiveKeywords) {
        if ($fileNameLower -match [regex]::Escape($kw)) { return "_Archive" }
    }

    return $null
}

function Get-SafeDestination {
    param(
        [string]$DestDir,
        [string]$BaseName,
        [string]$Extension,
        [string[]]$ExistingPaths = @()
    )

    $candidate = Join-Path $DestDir "${BaseName}${Extension}"
    $counter = 1
    while (($ExistingPaths -contains $candidate) -or (Test-Path $candidate)) {
        $candidate = Join-Path $DestDir "${BaseName}_${counter}${Extension}"
        $counter++
    }
    return $candidate
}

function Wait-FileReady {
    param(
        [string]$FilePath,
        [int]$MaxRetries = 10,
        [int]$DelayMs = 300
    )

    for ($i = 0; $i -lt $MaxRetries; $i++) {
        try {
            $stream = [System.IO.File]::Open(
                $FilePath,
                [System.IO.FileMode]::Open,
                [System.IO.FileAccess]::Read,
                [System.IO.FileShare]::None
            )
            $stream.Close()
            return $true
        } catch {
            Start-Sleep -Milliseconds $DelayMs
        }
    }
    return $false
}

# ── Exports ────────────────────────────────────────────────────────────────────

Export-ModuleMember -Function Get-CleanDescription, Get-DateFromFileName, Get-FranchiseGroup, Get-SpecialFolder, Get-SafeDestination, Wait-FileReady
Export-ModuleMember -Variable FranchiseGroups, TemplateKeywords, InternalKeywords, ArchiveKeywords, DocumentExtensions, FolderStructure
