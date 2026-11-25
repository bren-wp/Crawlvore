$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
python -m pip install -r requirements.txt -r windows/requirements-build.txt
if ($LASTEXITCODE) { throw 'Dependency installation failed' }
python -m unittest discover -s tests -v
if ($LASTEXITCODE) { throw 'Tests failed' }
$env:PLAYWRIGHT_BROWSERS_PATH = '0'
python -m playwright install chromium
if ($LASTEXITCODE) { throw 'Browser installation failed' }
python -m PyInstaller --noconfirm --clean --onefile --windowed --name Portable --icon windows/Crawlvora.ico --add-data 'static;static' --add-data 'tvrtk_output.csv;.' --collect-all playwright --collect-all webview --collect-all pythonnet --collect-all clr_loader tvrtk_scraper.py
if ($LASTEXITCODE) { throw 'Portable build failed' }
$iscc = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
if (!(Test-Path $iscc)) { throw 'Install Inno Setup 6 before running this script.' }
& $iscc windows\Crawlvora.iss
if ($LASTEXITCODE) { throw 'Setup build failed' }
Get-FileHash dist\Portable.exe,dist\Setup.exe -Algorithm SHA256 | Format-Table

# Check the actual bundled browser, assets, database and Python runtime in both distributions.
$smoke = Join-Path $env:TEMP ('crawlvora-smoke-' + [guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $smoke | Out-Null
function Test-PackagedApp($exe, $report) {
    $p = Start-Process -FilePath $exe -ArgumentList @('--self-test', ('"' + $report + '"')) -PassThru
    if (!$p.WaitForExit(180000)) { $p.Kill(); throw 'Runtime smoke test timed out' }
    if ($p.ExitCode -ne 0 -or !(Test-Path $report) -or !(Get-Content $report -Raw | ConvertFrom-Json).ok) { throw 'Runtime smoke test failed' }
}
try {
    Test-PackagedApp (Resolve-Path dist\Portable.exe).Path (Join-Path $smoke 'portable.json')
    $install = Join-Path $smoke 'installed'
    $p = Start-Process -FilePath (Resolve-Path dist\Setup.exe).Path -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/DIR="' + $install + '"')) -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw 'Installer failed' }
    Test-PackagedApp (Join-Path $install 'Crawlvora.exe') (Join-Path $smoke 'installed.json')
    $p = Start-Process -FilePath (Join-Path $install 'unins000.exe') -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART') -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw 'Uninstaller failed' }
} finally { Remove-Item $smoke -Recurse -Force -ErrorAction SilentlyContinue }
