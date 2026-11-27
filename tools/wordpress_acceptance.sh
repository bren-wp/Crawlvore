#!/usr/bin/env bash
set -euo pipefail
id="cvwp-$$-$RANDOM"
network="$id-net"; db="$id-db"; site="$id-site"; volume="$id-volume"
tmp="$(mktemp -d)"
cleanup() {
  docker rm -f "$site" "$db" >/dev/null 2>&1 || true
  docker volume rm "$volume" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
  rm -rf "$tmp"
}
trap cleanup EXIT
mkdir -p "$tmp/catalog/HR" "$tmp/catalog/GB"
chmod 755 "$tmp" "$tmp/catalog" "$tmp/catalog/HR" "$tmp/catalog/GB"
python - "$tmp/catalog" <<'PY'
import json,sys,pathlib
p=pathlib.Path(sys.argv[1])
for country,name,number in [('HR','Synthetic <script>alert(1)</script>','000000123'),('GB','Synthetic UK Ltd','AB123456')]:
 d=p/country;s=country+'-company-000001.json'
 (d/s).write_text(json.dumps([dict(country=country,kind='company',name=name,registration_number=number,as_of='2026-01-01')]))
 (d/'manifest.json').write_text(json.dumps(dict(country=country,count=1,shards=[s])))
PY
password="$(python -c 'import secrets;print(secrets.token_hex(24))')"
docker network create "$network" >/dev/null
docker volume create "$volume" >/dev/null
docker run -d --name "$db" --network "$network" -e MARIADB_DATABASE=wordpress -e MARIADB_USER=wordpress -e MARIADB_PASSWORD="$password" -e MARIADB_ROOT_PASSWORD="$password" mariadb:10.11@sha256:e5fe75b2b9de0eb9f6f9a4d9c97272fb3a7480e389ccd487a786bab2a12cc0d7 >/dev/null
docker run -d --name "$site" --network "$network" -p 127.0.0.1::80 \
  -e WORDPRESS_DB_HOST="$db" -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD="$password" -e WORDPRESS_DB_NAME=wordpress \
  -v "$volume:/var/www/html" -v "$PWD/wordpress/crawlvora-business-directory:/var/www/html/wp-content/plugins/crawlvora-business-directory:ro" \
  -v "$tmp/catalog:/catalog:ro" wordpress:php8.3-apache@sha256:9b46af6a41fd0dcb2e5cf85033a6350d05010356847ede1cfcac5cf94292eb26 >/dev/null
port="$(docker port "$site" 80/tcp | sed -n 's/^127\.0\.0\.1://p')"
base="http://127.0.0.1:$port"
for n in $(seq 1 60);do
  if docker exec "$db" mariadb-admin ping --silent >/dev/null 2>&1 && curl -fsS "$base/wp-admin/install.php" >/dev/null;then break;fi
  sleep 2
done
wp() {
  docker run --rm --network "$network" --volumes-from "$site" --user 33:33 \
    -e WORDPRESS_DB_HOST="$db" -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD="$password" -e WORDPRESS_DB_NAME=wordpress \
    wordpress:cli-php8.3@sha256:fc50189ac8d3256891d0d964f8d80cf62189eb6262f53c7fd8bfc40debd71029 wp --path=/var/www/html "$@"
}
wp core install --url="$base" --title=Crawlvora --admin_user=cvtest --admin_password="$password" --admin_email=qa@example.test --skip-email
wp plugin activate crawlvora-business-directory
wp option update crawlvora_catalog_root /catalog
page="$(wp post create --post_type=page --post_status=publish --post_title=Directory --post_content='[crawlvora_directory]' --porcelain)"
curl -fsS "$base/?page_id=$page&cv_country=HR&cv_q=123" > "$tmp/hr.html"
curl -fsS "$base/?page_id=$page&cv_country=GB&cv_q=AB123456" > "$tmp/gb.html"
grep -q '000000123' "$tmp/hr.html"
grep -q '&lt;script&gt;alert(1)&lt;/script&gt;' "$tmp/hr.html"
! grep -q '<script>alert(1)</script>' "$tmp/hr.html"
grep -q 'Synthetic UK Ltd' "$tmp/gb.html"
! grep -q '000000123' "$tmp/gb.html"
wp plugin deactivate crawlvora-business-directory
wp plugin activate crawlvora-business-directory
wp plugin uninstall crawlvora-business-directory --deactivate --skip-delete
test "$(wp option get crawlvora_catalog_root 2>/dev/null || true)" = ""
test -s "$tmp/catalog/HR/manifest.json"
echo WORDPRESS_INTEGRATION_PASS
