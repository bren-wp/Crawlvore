$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$version = (Get-Content VERSION -Raw).Trim()
New-Item -ItemType Directory -Force release-assets | Out-Null
$env:PLAYWRIGHT_BROWSERS_PATH = '0'
python -m PyInstaller --noconfirm --clean --onefile --console --name CrawlvoraWorker --distpath dist/embedded --add-data 'static;static' --add-data 'tvrtk_output.csv;.' --collect-all playwright --exclude-module webview tvrtk_scraper.py
if ($LASTEXITCODE) { throw 'Embedded worker build failed' }
$env:CRAWLVORA_EMBEDDED_WORKER = (Resolve-Path dist/embedded/CrawlvoraWorker.exe).Path
cargo +stable build --release --locked --features portable --manifest-path desktop/src-tauri/Cargo.toml
if ($LASTEXITCODE) { throw 'Native portable build failed' }
Copy-Item desktop/src-tauri/target/release/crawlvora-desktop.exe release-assets/Portable.exe
Remove-Item Env:CRAWLVORA_EMBEDDED_WORKER
$iscc = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
if (!(Test-Path $iscc)) { throw 'Inno Setup 6 is missing' }
& $iscc "/DAppVersion=$version" windows/Crawlvora-native.iss
if ($LASTEXITCODE) { throw 'Native installer build failed' }
function Test-NativeWindow($exe) {
    $p = Start-Process -FilePath $exe -ArgumentList '--native-smoke' -PassThru
    if (!$p.WaitForExit(240000)) { taskkill /PID $p.Id /T /F | Out-Null; throw 'Native smoke timed out' }
    if ($p.ExitCode -ne 0) { throw 'Native smoke failed' }
}
$base = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { $env:TEMP }
$smoke = Join-Path $base ('cv-' + [guid]::NewGuid().ToString('N').Substring(0,8))
$log = Join-Path (Resolve-Path release-assets).Path 'native-install.log'
New-Item -ItemType Directory -Path $smoke | Out-Null
try {
    # No adjacent worker: tests the actual standalone embedded executable.
    Test-NativeWindow (Resolve-Path release-assets/Portable.exe).Path
    $install = Join-Path $smoke 'installed'
    $p = Start-Process -FilePath (Resolve-Path release-assets/Setup.exe).Path -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/DIR="' + $install + '"'),('/LOG="' + $log + '"')) -Wait -PassThru
    if ($p.ExitCode -ne 0) { if (Test-Path $log) { Get-Content $log -Tail 100 }; throw "Native installer failed (exit $($p.ExitCode))" }
    Test-NativeWindow (Join-Path $install 'Crawlvora.exe')
    $p = Start-Process -FilePath (Join-Path $install 'unins000.exe') -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART') -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw 'Native uninstall failed' }
} finally { Remove-Item $smoke -Recurse -Force -ErrorAction SilentlyContinue }
if (Test-Path $log) { Remove-Item $log -Force }
Get-FileHash release-assets/Portable.exe,release-assets/Setup.exe -Algorithm SHA256
