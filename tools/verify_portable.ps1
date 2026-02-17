param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Section {
    param([string]$Message)
    Write-Host ""
    Write-Host "[verify_portable] $Message"
}

function Assert-Exists {
    param(
        [string]$Path,
        [string]$Label
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Label not found: $Path"
    }
}

function Invoke-PythonCheck {
    param(
        [string]$PythonExe,
        [string]$Code,
        [string]$Label
    )
    Write-Section $Label
    & $PythonExe -c $Code
    if ($LASTEXITCODE -ne 0) {
        throw "Python check failed: $Label (exit=$LASTEXITCODE)"
    }
}

$root = Resolve-Path -LiteralPath $PortableRoot
$runGui = Join-Path $root "run_gui.cmd"
$pythonExe = Join-Path $root "python\python.exe"
$pythonwExe = Join-Path $root "python\pythonw.exe"
$pythonPth = Join-Path $root "python\python311._pth"

Write-Section "Check required files"
Assert-Exists -Path $runGui -Label "run_gui.cmd"
Assert-Exists -Path $pythonExe -Label "python.exe"
Assert-Exists -Path $pythonwExe -Label "pythonw.exe"
Assert-Exists -Path $pythonPth -Label "python311._pth"

Push-Location $root
try {
    Invoke-PythonCheck -PythonExe $pythonExe -Code "import spacy, fitz, PyQt6, presidio_analyzer; print('core-import-ok')" -Label "Import core dependencies"
    Invoke-PythonCheck -PythonExe $pythonExe -Code "import importlib; [importlib.import_module(m) for m in ['ja_core_news_sm','ja_core_news_md','ja_core_news_lg','ja_core_news_trf']]; print('model-import-ok')" -Label "Import bundled models"
    Invoke-PythonCheck -PythonExe $pythonExe -Code "import src.gui_pyqt.main; print('gui-entry-ok')" -Label "Import GUI entrypoint"
}
finally {
    Pop-Location
}

Write-Section "Verification successful"
Write-Host "PortableRoot: $root"
