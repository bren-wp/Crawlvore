param([ValidateSet('Legacy','Full','HR','GB','Online')][string]$Edition='Legacy')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$version = (Get-Content VERSION -Raw).Trim()
$privatePreview = $env:CRAWLVORA_PRIVATE_PREVIEW -eq '1'
if (!$env:GITHUB_ACTIONS -and !$privatePreview) { throw 'Local packaging requires explicit private preview mode.' }
if ($privatePreview -and ($env:CI -or $env:GITHUB_ACTIONS)) { throw 'Private preview must not run in public CI.' }
if ($Edition -ne 'Legacy') {
    $env:CRAWLVORA_REGISTRY_BUNDLE = if ($Edition -in @('Full','HR')) {'1'} else {'0'}
    $env:CRAWLVORA_NATIONAL_BUNDLE = if ($Edition -in @('Full','GB')) {'1'} else {'0'}
    Remove-Item Env:CRAWLVORA_EXPECTED_REGISTRY_SHA256,Env:CRAWLVORA_EXPECTED_GB_SHA256 -ErrorAction SilentlyContinue
} elseif ($privatePreview -and ($env:CRAWLVORA_REGISTRY_BUNDLE -ne '1' -or $env:CRAWLVORA_NATIONAL_BUNDLE -ne '1')) { throw 'Both national snapshots are required.' }
if ($privatePreview -and $Edition -eq 'Legacy' -and (Test-Path release-assets)) { throw 'Refusing to overwrite existing local artifacts.' }
if ($Edition -eq 'Legacy' -and (!(Test-Path native-preview/Crawlvora.exe) -or !(Test-Path native-preview/worker/CrawlvoraWorker.exe))) { throw 'Build the native preview host and worker first.' }
$output = if($Edition -eq 'Legacy') {'release-assets'} else {Join-Path 'edition-builds' $Edition}
if ($Edition -ne 'Legacy' -and (Test-Path $output)) { throw 'Edition staging exists' }
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
    $registryArgs = @('--add-data','registry-bundle/registry-seed.sqlite3;.','--add-data','registry-bundle/registry-seed.sha256;.','--add-data','registry-bundle/registry-seed.json;.')
}
if ($env:CRAWLVORA_NATIONAL_BUNDLE -eq '1') {
    if (!(Test-Path national-data/GB/manifest.json) -or !(Test-Path national-data/GB/united-kingdom.sqlite3.gz)) { throw 'National snapshot missing' }
    $env:CRAWLVORA_EXPECTED_GB_SHA256 = (Get-Content national-data/GB/manifest.json -Raw | ConvertFrom-Json).database_sha256
    $registryArgs += @('--add-data','national-data;national-data')
}
if ($Edition -eq 'Legacy') { $registryArgs+=@('--add-data','tvrtk_output.csv;.') }
else {
    @{edition=$Edition} | ConvertTo-Json -Compress | Set-Content (Join-Path $output 'edition.json') -Encoding ascii
    $registryArgs+=@('--add-data',((Join-Path $output 'edition.json')+';.'))
}
python -m PyInstaller @registryArgs --noconfirm --clean --onefile --console --name CrawlvoraWorker --distpath dist/embedded --add-data 'static;static' --exclude-module playwright --exclude-module webview tvrtk_scraper.py
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
$iscc = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
if (!(Test-Path $iscc)) { throw 'Inno Setup 6 is missing' }
# Bundle Microsoft's signed Evergreen bootstrapper for systems missing WebView2.
$bootstrapper = Join-Path (Resolve-Path windows).Path 'MicrosoftEdgeWebview2Setup.exe'
if (Test-Path $bootstrapper) { throw 'Existing WebView2 bootstrapper must not be overwritten.' }
Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $bootstrapper
$signature = Get-AuthenticodeSignature $bootstrapper
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'CN=Microsoft Corporation(,|$)') { throw 'Invalid Microsoft WebView2 installer signature' }
$acceptance = $null
try {
    if ($Edition -eq 'Legacy') { & $iscc "/DAppVersion=$version" windows/Crawlvora-native.iss } else { & $iscc "/DAppVersion=$version" "/DPrivatePortable=$(Join-Path $output 'Portable.exe')" "/DPrivateOutput=$output" windows/Crawlvora-native.iss }
    if ($LASTEXITCODE) { throw 'Native installer build failed' }
    if ($privatePreview -or $Edition -ne 'Legacy') {
        $acceptance = Join-Path $env:TEMP ('cv-acceptance-' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $acceptance | Out-Null
        if ($Edition -eq 'Legacy') { & $iscc "/DAppVersion=$version" "/DPrivateOutput=$acceptance" '/DPrivateSmoke=1' windows/Crawlvora-native.iss } else { & $iscc "/DAppVersion=$version" "/DPrivatePortable=$(Join-Path $output 'Portable.exe')" "/DPrivateOutput=$acceptance" '/DPrivateSmoke=1' windows/Crawlvora-native.iss }
        if ($LASTEXITCODE) { throw 'Isolated acceptance installer build failed' }
    }
} finally { Remove-Item $bootstrapper -Force -ErrorAction SilentlyContinue }
function Test-NativeWindow($exe) {
    $p = Start-Process -FilePath $exe -ArgumentList '--native-smoke' -PassThru
    if (!$p.WaitForExit(240000)) { taskkill /PID $p.Id /T /F | Out-Null; throw 'Native smoke timed out' }
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
    $setup = if ($privatePreview -or $Edition -ne 'Legacy') { Join-Path $acceptance 'Setup.exe' } else { Join-Path $output 'Setup.exe' }
    $p = Start-Process -FilePath $setup -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/DIR="' + $install + '"'),('/LOG="' + $log + '"')) -Wait -PassThru
    if ($p.ExitCode -ne 0) { if (Test-Path $log) { Get-Content $log -Tail 100 }; throw "Native installer failed (exit $($p.ExitCode))" }
    if ($Edition -ne 'Legacy' -and (Get-FileHash (Join-Path $install 'Crawlvora.exe')).Hash -ne (Get-FileHash (Join-Path $output 'Portable.exe')).Hash) { throw 'Edition installer payload mismatch' }
    Test-NativeWindow (Join-Path $install 'Crawlvora.exe')
    $p = Start-Process -FilePath (Join-Path $install 'unins000.exe') -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART') -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw 'Native uninstall failed' }
} finally {
    Remove-Item $smoke -Recurse -Force -ErrorAction SilentlyContinue
    if ($acceptance) { Remove-Item $acceptance -Recurse -Force -ErrorAction SilentlyContinue }
}
if (Test-Path $log) { Remove-Item $log -Force }
if ($Edition -ne 'Legacy') {
    New-Item -ItemType Directory -Force release-assets | Out-Null
    $suffix=if($Edition -eq 'Full'){''}else{'-'+$Edition}
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
        if($env:CRAWLVORA_EXPECTED_GB_SHA256){$receiptArgs+=@('--gb',$env:CRAWLVORA_EXPECTED_GB_SHA256)}
        python tools/edition_acceptance.py @receiptArgs
        if($LASTEXITCODE){throw 'Edition acceptance evidence failed'}
    }
}
Get-FileHash (Join-Path $output 'Portable.exe'),(Join-Path $output 'Setup.exe') -Algorithm SHA256
