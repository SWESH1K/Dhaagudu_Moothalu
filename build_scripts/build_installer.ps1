<#
PowerShell helper to build a one-file exe with PyInstaller and produce a Windows installer using Inno Setup (if available).

Usage (PowerShell, run as Administrator if you want per-machine install):
.
  cd "<project root>"
  pwsh ./build_scripts/build_installer.ps1  # if using PowerShell Core
  .\build_scripts\build_installer.ps1     # if using Windows PowerShell

This script will:
- ensure pip and PyInstaller are installed
- run PyInstaller to produce a single-file executable for `client.py`
- attempt to run Inno Setup Compiler (ISCC.exe) with `installer/installer.iss` to produce the final installer

Notes:
- Install Inno Setup (https://jrsoftware.org/isinfo.php) to enable automatic .exe installer creation.
- You can edit the variables at the top to change the app name or entrypoint.
#>

param(
    [string]$Entry = "client.py",
    [string]$AppName = "DhaaguduMoothalu",
    [string]$AppVersion = "1.0.0",
    [switch]$Console
)

Set-StrictMode -Version Latest

function Write-Info($m) { Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Write-Err($m) { Write-Host "[ERROR] $m" -ForegroundColor Red }

Push-Location -Path (Split-Path -Path $MyInvocation.MyCommand.Definition -Parent) | Out-Null
Push-Location -Path .. | Out-Null

Write-Info "Project root: $(Get-Location)"

# Ensure pip is available and upgraded
Write-Info "Ensuring pip and wheel are available..."
python -m pip install --upgrade pip wheel | Out-Null

# Install project requirements + pyinstaller
Write-Info "Installing requirements and PyInstaller (may take a few minutes)..."
if (Test-Path -Path "requirements.txt") {
    python -m pip install -r requirements.txt | Out-Null
}
python -m pip install --upgrade pyinstaller | Out-Null

# Cleanup previous builds
Write-Info "Cleaning previous build artifacts..."
if (Test-Path -Path build) { Remove-Item -Recurse -Force build }
if (Test-Path -Path dist) { Remove-Item -Recurse -Force dist }
Get-ChildItem -Filter "*.spec" -Path . -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

# Compose add-data arguments for common asset dirs (PyInstaller expects 'SRC;DEST' on Windows)
# IMPORTANT: Pass options and their values as separate array elements so quoting is correct.
$pyArgs = @("--noconfirm", "--onefile", "--name", $AppName, "--hidden-import", "server")
if (-not $Console) { $pyArgs += "--windowed" }
foreach ($d in @('data','images','sounds')) {
    if (Test-Path -Path $d) {
        $pyArgs += @("--add-data", "$d;$d")
    }
}

$pyArgs += $Entry

Write-Info "Running PyInstaller..."
Write-Host "pyinstaller $($pyArgs -join ' ')"
pyinstaller @($pyArgs) | Write-Output

if (-not (Test-Path -Path "dist\$AppName.exe")) {
    Write-Err "PyInstaller did not produce dist\$AppName.exe. Check PyInstaller output above for errors."
    Pop-Location; Pop-Location
    exit 1
}

Write-Info "Exe built: dist\$AppName.exe"

# Try to find Inno Setup Compiler (ISCC.exe)
$isccPaths = @(
    "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe",
    "C:\\Program Files\\Inno Setup 6\\ISCC.exe"
)
$iscc = $null
foreach ($p in $isccPaths) { if (Test-Path -Path $p) { $iscc = $p; break } }
if (-not $iscc) {
    # try PATH
    try { $iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Path } catch { $iscc = $null }
}

if ($iscc) {
    Write-Info "Found Inno Setup Compiler: $iscc"
    $issPath = Join-Path -Path (Get-Location) -ChildPath "installer\installer.iss"
    if (-not (Test-Path -Path $issPath)) {
        Write-Err "Installer definition not found at installer\installer.iss"
        Pop-Location; Pop-Location
        exit 1
    }
    Write-Info "Compiling installer with Inno Setup..."
    & "$iscc" `"$issPath`" | Write-Output
    Write-Info "If compilation succeeded, the installer will be in the OutputDir configured in installer.iss (default: out)"
} else {
    Write-Info "Inno Setup Compiler (ISCC.exe) not found."
    Write-Info "Install Inno Setup (https://jrsoftware.org/isinfo.php) or run the script at 'installer/installer.iss' manually from the Inno Setup IDE."
}

Pop-Location; Pop-Location

Write-Info "Done."
