[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Add-Type -AssemblyName System.IO.Compression

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$pyproject = Join-Path $repoRoot "pyproject.toml"
$python = Join-Path $repoRoot ".pytest-temp\py312\Scripts\python.exe"
$wheelDir = Join-Path $repoRoot "wheels"
$buildDir = Join-Path $repoRoot "build\offline"
$manifestPath = Join-Path $buildDir "wheelhouse-manifest.json"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "Missing Python 3.12 build environment; run build_offline_wheels.ps1 first" }
$version = (& $python -c "import pathlib, sys, tomllib; print(tomllib.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))['project']['version'])" $pyproject)
if ($LASTEXITCODE -ne 0) { throw "Failed to read project version from pyproject.toml" }
$version = "$version".Trim()
if ($version -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid project version: $version" }

$releaseDir = Join-Path $repoRoot "release\$version"
$zipName = "ft-ftp-mcp-stdio-offline-$version-py312-win64.zip"
$zipPath = Join-Path $releaseDir $zipName
$tempZip = Join-Path $buildDir ("package-" + [guid]::NewGuid().ToString("N") + ".zip")
$versionFile = Join-Path $buildDir "VERSION.txt"

$wheels = @(Get-ChildItem -LiteralPath $wheelDir -File | Sort-Object Name)
if (@($wheels | Where-Object { $_.Extension -ne ".whl" }).Count -ne 0) {
    throw "The wheelhouse contains non-wheel files"
}
if (@($wheels | Where-Object { $_.Name -like "ft_ftp_mcp_stdio-$version-*.whl" }).Count -ne 1) {
    throw "Expected exactly one $version project wheel"
}
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw "Missing wheelhouse manifest; run build_offline_wheels.ps1 first" }
$wheelManifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$totalBytes = ($wheels | Measure-Object Length -Sum).Sum
if ($wheelManifest.version -cne $version -or $wheelManifest.file_count -ne $wheels.Count -or $wheelManifest.total_bytes -ne $totalBytes) {
    throw "Wheelhouse summary does not match its manifest"
}
$expectedWheels = @{}
foreach ($entry in $wheelManifest.files) {
    if ($expectedWheels.ContainsKey($entry.name)) { throw "Duplicate wheel in manifest: $($entry.name)" }
    $expectedWheels[$entry.name] = $entry
}
foreach ($wheel in $wheels) {
    if (-not $expectedWheels.ContainsKey($wheel.Name)) { throw "Wheel missing from manifest: $($wheel.Name)" }
    $expected = $expectedWheels[$wheel.Name]
    if ($expected.size -ne $wheel.Length -or $expected.sha256 -cne (Get-FileHash -LiteralPath $wheel.FullName -Algorithm SHA256).Hash) {
        throw "Wheel does not match manifest: $($wheel.Name)"
    }
}
if ($expectedWheels.Count -ne $wheels.Count) { throw "Manifest contains wheels that are not present" }

$manuals = @(Get-ChildItem -LiteralPath (Join-Path $repoRoot "docs") -Filter "*_v1.12.md" -File)
if ($manuals.Count -ne 1) { throw "Expected exactly one v1.12 user manual" }
$manual = $manuals[0]
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($versionFile, "$version`n", $utf8)

$inputs = @(
    @{ Path = (Join-Path $repoRoot "install.bat"); Name = "install.bat" },
    @{ Path = $versionFile; Name = "VERSION.txt" },
    @{ Path = (Join-Path $repoRoot "templates\workbuddy-mcp.json.template"); Name = "templates/workbuddy-mcp.json.template" },
    @{ Path = (Join-Path $repoRoot "templates\codex-config.toml.template"); Name = "templates/codex-config.toml.template" },
    @{ Path = $manual.FullName; Name = $manual.Name }
)
foreach ($wheel in $wheels) {
    $inputs += @{ Path = $wheel.FullName; Name = "wheels/$($wheel.Name)" }
}
$inputs = @($inputs | Sort-Object { $_.Name })
$hashes = @{}
foreach ($item in $inputs) {
    if (-not (Test-Path -LiteralPath $item.Path -PathType Leaf)) { throw "Missing input: $($item.Path)" }
    $hashes[$item.Name] = (Get-FileHash -LiteralPath $item.Path -Algorithm SHA256).Hash
}

New-Item -ItemType Directory -Force -Path $buildDir, $releaseDir | Out-Null
$manifest = (($inputs | ForEach-Object { "$($hashes[$_.Name])  $($_.Name)" }) -join "`n") + "`n"
$stream = [System.IO.File]::Open($tempZip, [System.IO.FileMode]::CreateNew)
try {
    $archive = New-Object System.IO.Compression.ZipArchive($stream, [System.IO.Compression.ZipArchiveMode]::Create, $false)
    try {
        foreach ($item in $inputs) {
            $entry = $archive.CreateEntry($item.Name, [System.IO.Compression.CompressionLevel]::Optimal)
            $source = [System.IO.File]::OpenRead($item.Path)
            $dest = $entry.Open()
            try { $source.CopyTo($dest) }
            finally { $dest.Dispose(); $source.Dispose() }
        }
        $entry = $archive.CreateEntry("SHA256SUMS.txt", [System.IO.Compression.CompressionLevel]::Optimal)
        $dest = $entry.Open()
        try {
            $bytes = $utf8.GetBytes($manifest)
            $dest.Write($bytes, 0, $bytes.Length)
        }
        finally { $dest.Dispose() }
    }
    finally { $archive.Dispose() }
}
finally { $stream.Dispose() }

foreach ($item in $inputs) {
    if ((Get-FileHash -LiteralPath $item.Path -Algorithm SHA256).Hash -cne $hashes[$item.Name]) {
        throw "Input changed while packaging: $($item.Name)"
    }
}

$stream = [System.IO.File]::OpenRead($tempZip)
try {
    $archive = New-Object System.IO.Compression.ZipArchive($stream, [System.IO.Compression.ZipArchiveMode]::Read, $false)
    try {
        if ($archive.Entries.Count -ne ($inputs.Count + 1)) { throw "ZIP file count mismatch" }
        $seen = @{}
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try {
            foreach ($entry in $archive.Entries) {
                if ($seen.ContainsKey($entry.FullName)) { throw "Duplicate ZIP entry: $($entry.FullName)" }
                $seen[$entry.FullName] = $true
                $entryStream = $entry.Open()
                try {
                    if ($entry.FullName -eq "SHA256SUMS.txt") {
                        $reader = New-Object System.IO.StreamReader($entryStream, $utf8)
                        if ($reader.ReadToEnd() -cne $manifest) { throw "Manifest mismatch" }
                    }
                    else {
                        if (-not $hashes.ContainsKey($entry.FullName)) { throw "Unexpected ZIP entry: $($entry.FullName)" }
                        $actual = [BitConverter]::ToString($sha.ComputeHash($entryStream)).Replace("-", "")
                        if ($actual -cne $hashes[$entry.FullName]) { throw "ZIP hash mismatch: $($entry.FullName)" }
                    }
                }
                finally { $entryStream.Dispose() }
            }
        }
        finally { $sha.Dispose() }
        foreach ($item in $inputs) {
            if (-not $seen.ContainsKey($item.Name)) { throw "Missing ZIP entry: $($item.Name)" }
        }
        if (-not $seen.ContainsKey("SHA256SUMS.txt")) { throw "Missing manifest" }
    }
    finally { $archive.Dispose() }
}
finally { $stream.Dispose() }

if (Test-Path -LiteralPath $zipPath) {
    $backup = Join-Path $buildDir ("previous-package-" + [guid]::NewGuid().ToString("N") + ".zip")
    Move-Item -LiteralPath $zipPath -Destination $backup
}
Move-Item -LiteralPath $tempZip -Destination $zipPath
$result = Get-Item -LiteralPath $zipPath
$zipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash
Write-Host "OFFLINE_PACKAGE_OK version=$version wheels=$($wheels.Count) wheel_bytes=$totalBytes files=$($inputs.Count + 1) bytes=$($result.Length) sha256=$zipHash path=$zipPath"
