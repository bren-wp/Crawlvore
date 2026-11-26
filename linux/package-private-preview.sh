#!/usr/bin/env bash
# Local-only native preview: require both already staged national snapshots.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != Linux ]]; then echo "Linux build requires Linux" >&2; exit 1; fi
if [[ "${CRAWLVORA_PRIVATE_PREVIEW:-}" != 1 ]]; then echo "Explicit private preview mode required" >&2; exit 1; fi
for path in native-preview release-assets; do
  if [[ -e "$path" ]]; then echo "Refusing to overwrite $path" >&2; exit 1; fi
done
python - <<'PY'
import json
from pathlib import Path
from registry_bundle import verify_bundle
root=Path('registry-bundle')
manifest=json.loads((root/'registry-seed.json').read_text(encoding='utf-8'))
report=verify_bundle(root/'registry-seed.sqlite3',allow_partial=True)
if report.get('complete') is not False or any(manifest.get(k)!=v for k,v in report.items()):
    raise SystemExit('Partial HR manifest mismatch')
if (root/'registry-seed.sha256').read_text(encoding='ascii').strip()!=report['database_sha256']:
    raise SystemExit('HR checksum mismatch')
gb=Path('national-data/GB')
if not (gb/'united-kingdom.sqlite3.gz').is_file():
    raise SystemExit('GB package missing')
PY
export CRAWLVORA_EXPECTED_REGISTRY_SHA256="$(tr -d '\r\n' < registry-bundle/registry-seed.sha256)"
export CRAWLVORA_EXPECTED_GB_SHA256="$(python -c "import json; print(json.load(open('national-data/GB/manifest.json',encoding='utf-8'))['database_sha256'])")"
npm ci --ignore-scripts --no-audit
npm run typecheck
npm run build:frontend
cargo +stable build --release --locked --manifest-path desktop/src-tauri/Cargo.toml
python -m PyInstaller --noconfirm --clean --onedir --console --name CrawlvoraWorker \
  --add-data 'static:static' --add-data 'tvrtk_output.csv:.' \
  --add-data 'registry-bundle/registry-seed.sqlite3:.' \
  --add-data 'registry-bundle/registry-seed.sha256:.' \
  --add-data 'registry-bundle/registry-seed.json:.' \
  --add-data 'national-data:national-data' \
  --exclude-module playwright --exclude-module webview tvrtk_scraper.py
mkdir native-preview release-assets
cp -R dist/CrawlvoraWorker native-preview/worker
cp desktop/src-tauri/target/release/crawlvora-desktop native-preview/Crawlvora
tar -czf release-assets/Crawlvora-Linux-x86_64.tar.gz -C native-preview .
bash linux/package.sh
temporary="$(mktemp -d)"
trap 'rm -rf "$temporary"' EXIT
mkdir "$temporary/tar" "$temporary/deb"
tar -xzf release-assets/Crawlvora-Linux-x86_64.tar.gz -C "$temporary/tar"
dpkg-deb -x release-assets/Crawlvora-Linux-amd64.deb "$temporary/deb"
for exe in "$temporary/tar/Crawlvora" "$temporary/deb/opt/crawlvora/Crawlvora"; do
  WEBKIT_DISABLE_COMPOSITING_MODE=1 timeout 240 xvfb-run -a "$exe" --native-smoke
done
(cd release-assets && sha256sum Crawlvora-Linux-x86_64.tar.gz Crawlvora-Linux-amd64.deb > SHA256SUMS.txt && sha256sum -c SHA256SUMS.txt)
