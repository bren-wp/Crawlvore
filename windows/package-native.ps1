param([ValidateSet('HR','Online')][string]$Edition='Online',[ValidateSet('en','hr')][string]$Language='hr')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = (Resolve-Path src).Path
$version = (Get-Content VERSION -Raw).Trim()
$privatePreview = $env:CRAWLVORA_PRIVATE_PREVIEW -eq '1'
if (!$env:GITHUB_ACTIONS -and !$privatePreview) { throw 'Local packaging requires explicit private preview mode.' }
if ($privatePreview -and ($env:CI -or $env:GITHUB_ACTIONS)) { throw 'Private preview must not run in public CI.' }
$env:CRAWLVORA_REGISTRY_BUNDLE = if ($Edition -eq 'HR') {'1'} else {'0'}
Remove-Item Env:CRAWLVORA_EXPECTED_REGISTRY_SHA256 -ErrorAction SilentlyContinue
$output = Join-Path 'edition-builds' $Edition
if (Test-Path $output) { throw 'Edition staging exists' }
New-Item -ItemType Directory -Force $output | Out-Null
$output=(Resolve-Path $output).Path
$registryArgs = @()
if ($env:CRAWLVORA_REGISTRY_BUNDLE -eq '1') {
    if ($env:CRAWLVORA_PRIVATE_PREVIEW -eq '1') {
        python -c "from pathlib import Path; import json; from registry_bundle import verify_bundle; p=Path('registry-bundle'); r=verify_bundle(p/'registry-seed.sqlite3',allow_partial=True); m=json.loads((p/'registry-seed.json').read_text(encoding='utf-8')); assert r.get('complete') is False and all(m.get(k)==v for k,v in r.items())"
    } else {
        python -c "from registry_bundle import verify_bundle; print(verify_bundle('registry-bundle/registry-seed.sqlite3'))"
    }
    if ($LASTEXITCODE) { throw 'Registry bundle acceptance failed' }
    (Get-FileHash registry-bundle/registry-seed.sqlite3 -Algorithm SHA256).Hash.ToLower() | Set-Content registry-bundle/registry-seed.sha256 -Encoding ascii
    $env:CRAWLVORA_EXPECTED_REGISTRY_SHA256 = (Get-Content registry-bundle/registry-seed.sha256 -Raw).Trim()
    python tools/compress_registry_seed.py registry-bundle
    if ($LASTEXITCODE) { throw 'Registry compression failed' }
    $registryArgs = @('--add-data','registry-bundle/registry-seed.sqlite3.gz;.','--add-data','registry-bundle/registry-seed.size;.','--add-data','registry-bundle/registry-seed.sha256;.','--add-data','registry-bundle/registry-seed.json;.')
}
@{edition=$Edition;language=$Language} | ConvertTo-Json -Compress | Set-Content (Join-Path $output 'edition.json') -Encoding ascii
$registryArgs+=@('--add-data',((Join-Path $output 'edition.json')+';.'))
python -m PyInstaller --paths src @registryArgs --noconfirm --clean --onefile --console --name CrawlvoraWorker --distpath dist/embedded --add-data 'static;static' --exclude-module playwright --exclude-module webview src/tvrtk_scraper.py
if ($LASTEXITCODE) { throw 'Embedded worker build failed' }
$worker = (Resolve-Path dist/embedded/CrawlvoraWorker.exe).Path
$env:CRAWLVORA_WORKER_SIZE = (Get-Item $worker).Length.ToString()
$env:CRAWLVORA_WORKER_SHA256 = (Get-FileHash $worker -Algorithm SHA256).Hash.ToLower()
cargo +stable build --release --locked --features portable --manifest-path desktop/src-tauri/Cargo.toml
if ($LASTEXITCODE) { throw 'Native portable build failed' }
$cargoTarget = if ($env:CARGO_TARGET_DIR) { $env:CARGO_TARGET_DIR } else { 'desktop/src-tauri/target' }
python tools/pack_portable.py (Join-Path $cargoTarget 'release/crawlvora-desktop.exe') $worker (Join-Path $output 'Portable.exe') $env:CRAWLVORA_WORKER_SHA256 $env:CRAWLVORA_WORKER_SIZE
if ($LASTEXITCODE) { throw 'Portable payload assembly failed' }
Remove-Item Env:CRAWLVORA_WORKER_SIZE,Env:CRAWLVORA_WORKER_SHA256
$nsis = Join-Path ${env:ProgramFiles(x86)} 'NSIS\makensis.exe'
if (!(Test-Path $nsis)) { throw 'NSIS compiler is missing' }
# Bundle Microsoft's signed Evergreen bootstrapper for systems missing WebView2.
$bootstrapper = Join-Path (Resolve-Path windows).Path 'MicrosoftEdgeWebview2Setup.exe'
if (Test-Path $bootstrapper) { throw 'Existing WebView2 bootstrapper must not be overwritten.' }
Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $bootstrapper
$signature = Get-AuthenticodeSignature $bootstrapper
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'CN=Microsoft Corporation(,|$)') { throw 'Invalid Microsoft WebView2 installer signature' }
$acceptance = $null
try {
    & $nsis /INPUTCHARSET UTF8 "/DAPP_VERSION=$version" "/DAPP_EXE=$(Join-Path $output 'Portable.exe')" "/DSETUP_EXE=$(Join-Path $output 'Setup.exe')" "/DWEBVIEW_BOOTSTRAPPER=$bootstrapper" windows/Crawlvora.nsi
    if ($LASTEXITCODE) { throw 'NSIS installer build failed' }
    $acceptance = Join-Path $env:TEMP ('cv-acceptance-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $acceptance | Out-Null
    & $nsis /INPUTCHARSET UTF8 "/DAPP_VERSION=$version" "/DAPP_EXE=$(Join-Path $output 'Portable.exe')" "/DSETUP_EXE=$(Join-Path $acceptance 'Setup.exe')" "/DWEBVIEW_BOOTSTRAPPER=$bootstrapper" /DACCEPTANCE windows/Crawlvora.nsi
    if ($LASTEXITCODE) { throw 'Isolated NSIS acceptance installer build failed' }
} finally { Remove-Item $bootstrapper -Force -ErrorAction SilentlyContinue }
function Test-NativeWindow($exe) {
    $p = Start-Process -FilePath $exe -ArgumentList '--native-smoke' -PassThru
    if (!$p.WaitForExit(900000)) { taskkill /PID $p.Id /T /F | Out-Null; throw 'Native smoke timed out' }
    if ($p.ExitCode -ne 0) { throw 'Native smoke failed' }
}
$base = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { $env:TEMP }
$smoke = Join-Path $base ('cv-' + [guid]::NewGuid().ToString('N').Substring(0,8))
$log = Join-Path $output 'native-install.log'
New-Item -ItemType Directory -Path $smoke | Out-Null
try {
    # No adjacent worker: tests the actual standalone embedded executable.
    Test-NativeWindow (Join-Path $output 'Portable.exe')
    $install = Join-Path $smoke 'installed'
    $setup = Join-Path $acceptance 'Setup.exe'
    $p = Start-Process -FilePath $setup -ArgumentList ('/S /D=' + $install) -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "NSIS installer failed (exit $($p.ExitCode))" }
    if ((Get-FileHash (Join-Path $install 'Crawlvora.exe')).Hash -ne (Get-FileHash (Join-Path $output 'Portable.exe')).Hash) { throw 'Edition installer payload mismatch' }
    Test-NativeWindow (Join-Path $install 'Crawlvora.exe')
    # Prove update and uninstall never recursively remove arbitrary files.
    $sentinel = Join-Path $install 'user-data-sentinel.sqlite3'
    'synthetic data must survive' | Set-Content -LiteralPath $sentinel -Encoding ascii
    $before = (Get-FileHash $sentinel).Hash
    $p = Start-Process -FilePath $setup -ArgumentList ('/S /D=' + $install) -Wait -PassThru
    if ($p.ExitCode -ne 0 -or (Get-FileHash $sentinel).Hash -ne $before) { throw 'NSIS update acceptance failed' }
    if ((Get-FileHash (Join-Path $install 'Crawlvora.exe')).Hash -ne (Get-FileHash (Join-Path $output 'Portable.exe')).Hash) { throw 'Updated payload mismatch' }
    Test-NativeWindow (Join-Path $install 'Crawlvora.exe')
    $p = Start-Process -FilePath (Join-Path $install 'Uninstall-Crawlvora.exe') -ArgumentList '/S' -Wait -PassThru
    if ($p.ExitCode -ne 0 -or (Test-Path (Join-Path $install 'Crawlvora.exe')) -or (Get-FileHash $sentinel).Hash -ne $before) { throw 'NSIS uninstall/data preservation failed' }
} finally {
    Remove-Item $smoke -Recurse -Force -ErrorAction SilentlyContinue
    if ($acceptance) { Remove-Item $acceptance -Recurse -Force -ErrorAction SilentlyContinue }
}
if (Test-Path $log) { Remove-Item $log -Force }
New-Item -ItemType Directory -Force release-assets | Out-Null
    $suffix='-'+$Edition
    foreach($name in @('Portable','Setup')){
        $dest=Join-Path 'release-assets' ($name+$suffix+'.exe')
        if(Test-Path $dest){throw 'Edition release asset exists'}
    }
    foreach($name in @('Portable','Setup')){
        Copy-Item (Join-Path $output ($name+'.exe')) (Join-Path 'release-assets' ($name+$suffix+'.exe'))
    }
    # CI source identity is supplied by GitHub; local archive builds need an explicit source identity.
    $source = if($env:GITHUB_SHA){$env:GITHUB_SHA}else{$env:CRAWLVORA_BUILD_SOURCE_SHA}
    if ($source) {
        $receiptArgs=@('release-assets','--edition',$Edition,'--source',$source)
        if($env:CRAWLVORA_EXPECTED_REGISTRY_SHA256){$receiptArgs+=@('--hr',$env:CRAWLVORA_EXPECTED_REGISTRY_SHA256)}
        python tools/edition_acceptance.py @receiptArgs
        if($LASTEXITCODE){throw 'Edition acceptance evidence failed'}
    }
Get-FileHash (Join-Path $output 'Portable.exe'),(Join-Path $output 'Setup.exe') -Algorithm SHA256
