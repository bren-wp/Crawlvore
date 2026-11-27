#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
version="$(tr -d '\r\n' < VERSION)"
root="$(mktemp -d)"
trap 'rm -rf "$root"' EXIT
mkdir -p "$root/DEBIAN" "$root/opt/crawlvora" "$root/usr/bin" "$root/usr/share/applications" "$root/usr/share/icons/hicolor/32x32/apps"
cp -a native-preview/. "$root/opt/crawlvora/"
ln -s /opt/crawlvora/Crawlvora "$root/usr/bin/crawlvora"
cp desktop/src-tauri/icons/icon.png "$root/usr/share/icons/hicolor/32x32/apps/crawlvora.png"
cat > "$root/DEBIAN/control" <<EOF
Package: crawlvora
Version: $version
Architecture: amd64
Maintainer: Crawlvora
Section: utils
Priority: optional
Depends: libc6 (>= 2.39), libwebkit2gtk-4.1-0, libgtk-3-0t64 | libgtk-3-0, libssl3t64 | libssl3, libayatana-appindicator3-1, librsvg2-2, libxdo3, libsecret-tools
Description: Crawlvora Court Registry business directory
 Local-first Croatian Court Registry workspace.
EOF
cat > "$root/usr/share/applications/crawlvora.desktop" <<'EOF'
[Desktop Entry]
Name=Crawlvora
Comment=Croatian Court Registry business directory
Exec=/usr/bin/crawlvora
Icon=crawlvora
Terminal=false
Type=Application
Categories=Office;Database;
StartupNotify=true
EOF
mkdir -p release-assets
dpkg-deb -Zxz -z6 --root-owner-group --build "$root" release-assets/Crawlvora-Linux-amd64.deb
