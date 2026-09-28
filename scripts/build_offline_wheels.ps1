[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$pyproject = Join-Path $repoRoot "pyproject.toml"
$python = Join-Path $repoRoot ".pytest-temp\py312\Scripts\python.exe"
$wheels = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "wheels"))
$buildDir = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "build\offline"))
$requirements = Join-Path $buildDir "requirements-py312.txt"
$manifestPath = Join-Path $buildDir "wheelhouse-manifest.json"

if ($wheels -ne [System.IO.Path]::GetFullPath((Join-Path $repoRoot "wheels"))) {
    throw "Unexpected wheels path: $wheels"
}

if (-not (Test-Path -LiteralPath $python)) {
    & uv venv (Join-Path $repoRoot ".pytest-temp\py312") --python 3.12 --seed
    if ($LASTEXITCODE -ne 0) { throw "Failed to create Python 3.12 build environment" }
}

& $python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)"
if ($LASTEXITCODE -ne 0) { throw "Build environment must use Python 3.12.x" }
& $python -m pip --version | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Build environment does not contain pip; recreate it with uv venv --seed" }
$version = (& $python -c "import pathlib, sys, tomllib; print(tomllib.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))['project']['version'])" $pyproject)
if ($LASTEXITCODE -ne 0) { throw "Failed to read project version from pyproject.toml" }
$version = "$version".Trim()
if ($version -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid project version: $version" }

New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
if (Test-Path -LiteralPath $wheels) {
    Remove-Item -LiteralPath $wheels -Recurse -Force
}
New-Item -ItemType Directory -Path $wheels | Out-Null

Push-Location $repoRoot
try {
    & uv lock --check
    if ($LASTEXITCODE -ne 0) { throw "uv.lock is not current" }

    & uv export --locked --format requirements-txt --no-dev --no-emit-project -o $requirements
    if ($LASTEXITCODE -ne 0) { throw "Failed to export locked runtime dependencies" }

    & uv build --wheel --out-dir $wheels --clear --python $python --no-create-gitignore
    if ($LASTEXITCODE -ne 0) { throw "Failed to build project wheel" }

    & $python -m pip download `
        -r $requirements `
        --require-hashes `
        --only-binary=:all: `
        --platform win_amd64 `
        --python-version 3.12 `
        --implementation cp `
        --abi cp312 `
        --dest $wheels
    if ($LASTEXITCODE -ne 0) { throw "Failed to download the offline dependency wheel set" }
}
finally {
    Pop-Location
}

$projectWheels = @(Get-ChildItem -LiteralPath $wheels -Filter "ft_ftp_mcp_stdio-$version-*.whl")
if ($projectWheels.Count -ne 1) {
    throw "Expected exactly one ft-ftp-mcp-stdio $version wheel, found $($projectWheels.Count)"
}
$unexpected = @(Get-ChildItem -LiteralPath $wheels -File | Where-Object { $_.Extension -ne ".whl" })
if ($unexpected.Count -ne 0) {
    throw "Offline dependency directory contains non-wheel files: $($unexpected.Name -join ', ')"
}

$files = @(Get-ChildItem -LiteralPath $wheels -File | Sort-Object Name)
$totalBytes = ($files | Measure-Object -Property Length -Sum).Sum
$manifest = [ordered]@{
    version = $version
    file_count = $files.Count
    total_bytes = [long]$totalBytes
    files = @($files | ForEach-Object {
        [ordered]@{
            name = $_.Name
            size = [long]$_.Length
            sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
        }
    })
}
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 4), $utf8)
Write-Host "OFFLINE_WHEELS_OK version=$version files=$($files.Count) bytes=$totalBytes manifest=$manifestPath path=$wheels"
