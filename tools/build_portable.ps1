param(
    [string]$PythonVersion = "3.11.9",
    [string]$BuildPython = "",
    [string]$OutputDir = "dist"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Section {
    param([string]$Message)
    Write-Host ""
    Write-Host "[build_portable] $Message"
}

function Resolve-BuildPythonPath {
    param([string]$Requested)

    if ($Requested) {
        if (Test-Path -LiteralPath $Requested) {
            return (Resolve-Path -LiteralPath $Requested).Path
        }
        throw "BuildPython not found: $Requested"
    }

    $defaultUvPython = Join-Path $env:APPDATA "uv\python\cpython-3.11-windows-x86_64-none\python.exe"
    if (Test-Path -LiteralPath $defaultUvPython) {
        return (Resolve-Path -LiteralPath $defaultUvPython).Path
    }

    throw "Python 3.11 executable not found. Specify -BuildPython with python.exe path."
}

function Invoke-CommandChecked {
    param(
        [string]$Label,
        [string]$Exe,
        [string[]]$CommandArgs
    )

    Write-Section "$Label"
    & $Exe @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Failed: $Label (exit=$LASTEXITCODE)"
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")

$pyprojectPath = Join-Path $repoRoot "pyproject.toml"
if (-not (Test-Path -LiteralPath $pyprojectPath)) {
    throw "pyproject.toml not found: $pyprojectPath"
}

$pyprojectText = Get-Content -LiteralPath $pyprojectPath -Raw -Encoding UTF8
$versionMatch = [regex]::Match($pyprojectText, '(?m)^\s*version\s*=\s*"([^"]+)"')
if (-not $versionMatch.Success) {
    throw "Failed to read project.version from pyproject.toml."
}
$appVersion = $versionMatch.Groups[1].Value

$buildPythonPath = Resolve-BuildPythonPath -Requested $BuildPython

$portableName = "PresidioPDF-$appVersion-win64-portable"
$tmpDir = Join-Path $repoRoot ".tmp_portable"
$portableRoot = Join-Path $tmpDir $portableName
$outputRoot = Join-Path $repoRoot $OutputDir
$zipPath = Join-Path $outputRoot "$portableName.zip"

$pythonEmbedZipName = "python-$PythonVersion-embed-amd64.zip"
$pythonEmbedUrl = "https://www.python.org/ftp/python/$PythonVersion/$pythonEmbedZipName"
$pythonEmbedZipPath = Join-Path $tmpDir $pythonEmbedZipName

$requirementsPath = Join-Path $tmpDir "requirements-portable.txt"
$wheelsDir = Join-Path $tmpDir "wheels"
$pythonDir = Join-Path $portableRoot "python"
$sitePackagesDir = Join-Path $pythonDir "Lib\site-packages"
$pythonPthPath = Join-Path $pythonDir "python311._pth"

$templatePthPath = Join-Path $repoRoot "portable\templates\python311._pth"
$templateRunGuiPath = Join-Path $repoRoot "portable\templates\run_gui.cmd"
$runGuiOutPath = Join-Path $portableRoot "run_gui.cmd"

if (-not (Test-Path -LiteralPath $templatePthPath)) {
    throw "Template not found: $templatePthPath"
}
if (-not (Test-Path -LiteralPath $templateRunGuiPath)) {
    throw "Template not found: $templateRunGuiPath"
}

Write-Section "Initialize working directories"
if (Test-Path -LiteralPath $tmpDir) {
    Remove-Item -LiteralPath $tmpDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tmpDir | Out-Null

if (-not (Test-Path -LiteralPath $outputRoot)) {
    New-Item -ItemType Directory -Path $outputRoot | Out-Null
}
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

Write-Section "Download embeddable Python"
Invoke-WebRequest -Uri $pythonEmbedUrl -OutFile $pythonEmbedZipPath

Write-Section "Create portable root"
New-Item -ItemType Directory -Path $portableRoot | Out-Null
New-Item -ItemType Directory -Path $pythonDir | Out-Null
New-Item -ItemType Directory -Path $sitePackagesDir -Force | Out-Null

Write-Section "Extract embeddable Python"
Expand-Archive -LiteralPath $pythonEmbedZipPath -DestinationPath $pythonDir -Force

if (-not (Test-Path -LiteralPath $pythonPthPath)) {
    throw "python311._pth not found: $pythonPthPath"
}

Write-Section "Place python311._pth"
Copy-Item -LiteralPath $templatePthPath -Destination $pythonPthPath -Force

Invoke-CommandChecked -Label "Export dependencies from uv.lock (GUI + model-sm/md/lg/trf)" -Exe "uv" -CommandArgs @(
    "export",
    "--format", "requirements.txt",
    "--no-dev",
    "--extra", "gui",
    "--extra", "model-sm",
    "--extra", "model-md",
    "--extra", "model-lg",
    "--extra", "model-trf",
    "--no-emit-project",
    "-o", $requirementsPath
)

Write-Section "Validate requirements"
$requirementsText = Get-Content -LiteralPath $requirementsPath -Raw -Encoding UTF8
if ($requirementsText -match 'ja-ginza-electra') {
    throw "requirements unexpectedly contains ja-ginza-electra."
}

Invoke-CommandChecked -Label "Download wheels" -Exe $buildPythonPath -CommandArgs @(
    "-m", "pip", "download",
    "-r", $requirementsPath,
    "--dest", $wheelsDir,
    "--only-binary=:all:"
)

Invoke-CommandChecked -Label "Offline install from wheels" -Exe $buildPythonPath -CommandArgs @(
    "-m", "pip", "install",
    "--no-index",
    "--find-links", $wheelsDir,
    "-r", $requirementsPath,
    "-t", $sitePackagesDir
)

Write-Section "Copy src/"
$srcDir = Join-Path $repoRoot "src"
if (-not (Test-Path -LiteralPath $srcDir)) {
    throw "src directory not found: $srcDir"
}
Copy-Item -LiteralPath $srcDir -Destination (Join-Path $portableRoot "src") -Recurse -Force

Write-Section "Place GUI launcher"
Copy-Item -LiteralPath $templateRunGuiPath -Destination $runGuiOutPath -Force

Write-Section "Create ZIP"
Compress-Archive -Path $portableRoot -DestinationPath $zipPath -CompressionLevel NoCompression -Force

Write-Section "Done"
Write-Host "ZIP: $zipPath"
Write-Host "Verify example:"
Write-Host "  powershell -ExecutionPolicy Bypass -File tools\\verify_portable.ps1 -PortableRoot `"$portableRoot`""
