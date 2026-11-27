#!/usr/bin/env bash
# Real Apache/PHP storage access acceptance, with synthetic records only.
set -euo pipefail
tmp="$(mktemp -d)"
site="cvapache-$$-$RANDOM"
cleanup() {
  docker rm -f "$site" >/dev/null 2>&1 || true
  rm -rf "$tmp"
}
trap cleanup EXIT
mkdir "$tmp/site"
cp -a webstranica/. "$tmp/site/"
chmod 755 "$tmp" "$tmp/site"
cat > "$tmp/storage-acceptance.conf" <<'APACHE'
<Directory "/var/www/html">
  AllowOverride All
  Options -Indexes
  Require all granted
</Directory>
APACHE
python - "$tmp/site" <<'PY'
import json,sys,pathlib
root=pathlib.Path(sys.argv[1])/'storage/data/HR'
shard='HR-company-000001.json'
(root/shard).write_text(json.dumps([{'country':'HR','kind':'company','name':'Synthetic Apache company','registration_number':'000000123','as_of':'2026-01-01'}]),encoding='utf-8')
(root/'manifest.json').write_text(json.dumps({'country':'HR','count':1,'shards':[shard]}),encoding='utf-8')
PY
docker run -d --name "$site" -p 127.0.0.1::80 \
  --entrypoint apache2-foreground \
  -v "$tmp/site:/var/www/html:ro" \
  -v "$tmp/storage-acceptance.conf:/etc/apache2/conf-enabled/crawlvora-acceptance.conf:ro" \
  wordpress:php8.3-apache@sha256:9b46af6a41fd0dcb2e5cf85033a6350d05010356847ede1cfcac5cf94292eb26 >/dev/null
port="$(docker port "$site" 80/tcp | sed -n 's/^127\.0\.0\.1://p')"
base="http://127.0.0.1:$port"
for n in $(seq 1 40);do
  if curl -fsS "$base/index.php" >/dev/null 2>&1;then break;fi
  sleep 1
done
curl -fsS "$base/index.php?view=pretraga&country=HR&q=123" > "$tmp/search.html"
grep -q 'Synthetic Apache company' "$tmp/search.html"
for path in storage/ storage/data/HR/manifest.json storage/data/HR/HR-company-000001.json; do
  status="$(curl -sS -o "$tmp/denied.html" -w '%{http_code}' "$base/$path")"
  test "$status" = 403
  ! grep -q 'Synthetic Apache company' "$tmp/denied.html"
done
echo APACHE_STORAGE_ACCEPTANCE_PASS
