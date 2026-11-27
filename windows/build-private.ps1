# Private, same-user Windows packages only. Never run on a public CI runner.
$ErrorActionPreference = 'Stop'
if ($env:CI -or $env:GITHUB_ACTIONS) { throw 'Private build must run on the target Windows desktop.' }
Set-Location (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = (Resolve-Path src).Path
$version = (Get-Content VERSION -Raw).Trim()
$output = Join-Path (Get-Location).Path 'dist\private-release'
$staging = Join-Path (Get-Location).Path ('dist\private-build-' + [guid]::NewGuid().ToString('N'))
if (Test-Path $output) { throw 'Private output already exists. Move it to private storage before rebuilding.' }
$capsule = Join-Path $staging 'registry-private.dpapi'
$bootstrapper = Join-Path (Resolve-Path windows).Path 'MicrosoftEdgeWebview2Setup.exe'
if (Test-Path $bootstrapper) { throw 'An existing WebView2 build file is present. Do not overwrite it.' }
New-Item -ItemType Directory -Path $staging -Force | Out-Null
try {
    python tools/create_private_registry_capsule.py $capsule
    if ($LASTEXITCODE) { throw 'Private credential capsule failed.' }
    Remove-Item Env:SUDREG_CLIENT_ID,Env:SUDREG_CLIENT_SECRET -ErrorAction SilentlyContinue
    npm.cmd ci --ignore-scripts --no-audit
    if ($LASTEXITCODE) { throw 'Frontend dependencies failed.' }
    npm.cmd run typecheck
    if ($LASTEXITCODE) { throw 'Frontend typecheck failed.' }
    npm.cmd run build:frontend
    if ($LASTEXITCODE) { throw 'Frontend build failed.' }
    $registryArgs = @()
    if ($env:CRAWLVORA_REGISTRY_BUNDLE -eq '1') {
        python -c "from registry_bundle import verify_bundle; print(verify_bundle('registry-bundle/registry-seed.sqlite3'))"
        if ($LASTEXITCODE) { throw 'Registry bundle acceptance failed' }
        (Get-FileHash registry-bundle/registry-seed.sqlite3 -Algorithm SHA256).Hash.ToLower() | Set-Content registry-bundle/registry-seed.sha256 -Encoding ascii
        python tools/compress_registry_seed.py registry-bundle
    if ($LASTEXITCODE) { throw 'Registry compression failed' }
    $registryArgs = @('--add-data','registry-bundle/registry-seed.sqlite3.xz;.','--add-data','registry-bundle/registry-seed.size;.','--add-data','registry-bundle/registry-seed.sha256;.','--add-data','registry-bundle/registry-seed.json;.')
    }
    $edition = if ($env:CRAWLVORA_REGISTRY_BUNDLE -eq '1') {'HR'} else {'Online'}
    @{edition=$edition;language='hr';version=(Get-Content VERSION -Raw).Trim()} | ConvertTo-Json -Compress | Set-Content (Join-Path $staging 'edition.json') -Encoding ascii
    $registryArgs += @('--add-data',((Join-Path $staging 'edition.json')+';.'))
    python -m PyInstaller --paths src @registryArgs --noconfirm --clean --onefile --console --name CrawlvoraWorker --distpath "$staging" --workpath "$staging\work" --specpath "$staging" --add-data 'static;static' --add-data "$capsule;." --exclude-module playwright --exclude-module webview src/tvrtk_scraper.py
    if ($LASTEXITCODE) { throw 'Private embedded worker build failed.' }
    $worker = Join-Path $staging 'CrawlvoraWorker.exe'
    $env:CRAWLVORA_WORKER_SIZE = (Get-Item $worker).Length.ToString()
    $env:CRAWLVORA_WORKER_SHA256 = (Get-FileHash $worker -Algorithm SHA256).Hash.ToLower()
    $env:CARGO_TARGET_DIR = Join-Path $staging 'target'
    cargo +stable build --release --locked --features portable --manifest-path desktop/src-tauri/Cargo.toml
    if ($LASTEXITCODE) { throw 'Private native host build failed.' }
    $portable = Join-Path $staging 'Portable.exe'
    python tools/pack_portable.py "$env:CARGO_TARGET_DIR\release\crawlvora-desktop.exe" $worker $portable $env:CRAWLVORA_WORKER_SHA256 $env:CRAWLVORA_WORKER_SIZE
    if ($LASTEXITCODE) { throw 'Private portable assembly failed' }
    $iscc = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
    if (!(Test-Path $iscc)) { throw 'Inno Setup 6 is required.' }
    Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $bootstrapper
    $signature = Get-AuthenticodeSignature $bootstrapper
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'CN=Microsoft Corporation(,|$)') { throw 'Invalid WebView2 signature.' }
    & $iscc "/DAppVersion=$version" "/DPrivatePortable=$portable" "/DPrivateOutput=$staging" windows/Crawlvora-native.iss
    if ($LASTEXITCODE) { throw 'Private Setup build failed.' }
    foreach ($file in @($portable,(Join-Path $staging 'Setup.exe'))) {
        if (!(Test-Path $file) -or (Get-Item $file).Length -eq 0) { throw 'Missing private package.' }
    }
    function Test-PrivateWindow($exe) {
        $p = Start-Process -FilePath $exe -ArgumentList '--native-smoke' -PassThru
        if (!$p.WaitForExit(900000)) { taskkill /PID $p.Id /T /F | Out-Null; throw 'Private native smoke timed out.' }
        if ($p.ExitCode -ne 0) { throw 'Private native smoke failed.' }
    }
    Test-PrivateWindow $portable
    # Setup has a different smoke AppId to avoid changing a real existing installation.
    # Its payload and installer code are identical to the final private Setup.
    $acceptance = Join-Path $staging 'acceptance'
    New-Item -ItemType Directory -Path $acceptance | Out-Null
    & $iscc "/DAppVersion=$version" "/DPrivatePortable=$portable" "/DPrivateOutput=$acceptance" '/DPrivateSmoke=1' windows/Crawlvora-native.iss
    if ($LASTEXITCODE) { throw 'Private acceptance installer build failed.' }
    $install = Join-Path $acceptance 'installed'
    $p = Start-Process -FilePath (Join-Path $acceptance 'Setup.exe') -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/DIR="' + $install + '"')) -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw 'Private acceptance installation failed.' }
    Test-PrivateWindow (Join-Path $install 'Crawlvora.exe')
    $p = Start-Process -FilePath (Join-Path $install 'unins000.exe') -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART') -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw 'Private acceptance uninstallation failed.' }
    New-Item -ItemType Directory -Path $output | Out-Null
    Copy-Item $portable,(Join-Path $staging 'Setup.exe') $output
    Get-ChildItem $output -Filter '*.exe' | Sort-Object Name | ForEach-Object {
        ((Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower() + '  ' + $_.Name)
    } | Set-Content (Join-Path $output 'SHA256SUMS.txt') -Encoding ascii
    Write-Host 'Private packages created locally. Do not upload to public GitHub releases.'
} finally {
    Remove-Item Env:SUDREG_CLIENT_ID,Env:SUDREG_CLIENT_SECRET,Env:CRAWLVORA_WORKER_SIZE,Env:CRAWLVORA_WORKER_SHA256,Env:CARGO_TARGET_DIR -ErrorAction SilentlyContinue
    Remove-Item $bootstrapper -Force -ErrorAction SilentlyContinue
    Remove-Item $staging -Recurse -Force -ErrorAction SilentlyContinue
}
