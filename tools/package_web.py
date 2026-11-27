"""Build a code-only shared-hosting archive from the exact committed source."""
import argparse
import io
import os
import re
import tempfile
import json
from pathlib import Path, PurePosixPath
import subprocess
import zipfile
from urllib.parse import urlsplit, urlunsplit, urlencode
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {"index.php", "catalog.php", "robots.txt", "sources.json",
            "assets/site.css", "storage/.htaccess", "storage/data/manifest.json",
            "storage/data/HR/manifest.json", "storage/data/GB/manifest.json"}
STATIC = REQUIRED - {name for name in REQUIRED if name.startswith("storage/")}
STATIC |= {"README.md", "assets/hero.jpg", "assets/analytics.jpg", "assets/partners.jpg",
           "storage/.htaccess"}


def approved(name, data):
    if name in STATIC:
        return True
    path = PurePosixPath(name)
    if path.parts[:2] != ("storage", "data") or path.name != "manifest.json":
        return False
    if len(path.parts) not in (3, 4):
        return False
    manifest = json.loads(data)
    expected = {"version": 1, "count": 0, "published_at": None, "shards": []}
    if len(path.parts) == 4:
        expected["country"] = path.parts[2]
        if expected["country"] not in {"HR", "GB", "BA", "HU", "ME", "RS", "SI"}:
            return False
    return manifest == expected


def write_verified_zip(output, entries):
    """Deterministic archive; never replace an existing package or expose a partial ZIP."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".package-", suffix=".zip", dir=output.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, data in sorted(entries.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None or set(archive.namelist()) != set(entries):
                raise ValueError("Package integrity failure")
        os.link(temporary, output)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return output


PAGES = ("home", "pretraga", "usluge", "features", "downloads", "cjenik",
         "o-nama", "kontakt", "privatnost", "uvjeti-koristenja", "kolacici",
         "impressum", "sources", "help")


def deployment_seo(base_url):
    parts = urlsplit(base_url)
    if (parts.scheme != "https" or not parts.hostname or parts.username is not None
            or parts.password is not None or parts.query or parts.fragment
            or not parts.hostname.isascii() or any(ch.isspace() for ch in base_url)
            or not re.fullmatch(r"/[A-Za-z0-9._~/-]*", parts.path or "/")
            or any(part in (".", "..") for part in parts.path.split("/"))):
        raise ValueError("Provide the actual HTTPS site base URL, without query or fragment")
    # Reject malformed/out-of-range explicit ports.
    _ = parts.port
    base = urlunsplit(("https", parts.netloc, parts.path.rstrip("/") + "/", "", ""))
    root = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for page in PAGES:
        for language in ("en", "hr"):
            ET.SubElement(ET.SubElement(root, "url"), "loc").text = (
                base + "index.php?" + urlencode({"view": page, "lang": language}))
    robots = ("User-agent: *\nDisallow: " + urlsplit(base).path + "storage/\n"
              + "Disallow: /*?*q=\nSitemap: " + base + "sitemap.xml\n")
    return {"site-config.json": json.dumps({"base_url": base}).encode(),
            "sitemap.xml": ET.tostring(root, encoding="utf-8", xml_declaration=True),
            "robots.txt": robots.encode()}


def build(output, ref="HEAD", root=ROOT, *, upgrade=False, base_url=None):
    raw = subprocess.check_output(
        ["git", "archive", "--format=zip", ref, "webstranica"], cwd=root)
    entries = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as source:
        for info in source.infolist():
            if info.is_dir():
                continue
            name = info.filename.removeprefix("webstranica/")
            if name == info.filename or name in entries:
                raise ValueError("Unexpected archive member: " + name)
            if (info.external_attr >> 16) & 0o170000 not in (0, 0o100000):
                raise ValueError("Non-regular archive member: " + name)
            data = source.read(info)
            if name == "storage/data/.gitignore":
                continue
            if not approved(name, data):
                raise ValueError("Unapproved web distribution member: " + name)
            entries[name] = data
    if not REQUIRED <= entries.keys():
        raise ValueError("Missing web distribution members: " + str(REQUIRED - entries.keys()))
    if entries["storage/.htaccess"].strip() != b"Require all denied":
        raise ValueError("Storage protection missing")
    if upgrade:
        # Keep the existing approved catalog untouched during hosting upgrades.
        entries = {name: data for name, data in entries.items()
                   if not name.startswith("storage/data/")}
    if upgrade and base_url is None:
        entries.pop("robots.txt", None)  # Preserve deployment-specific indexing rules.
    if base_url is not None:
        entries.update(deployment_seo(base_url))
    return write_verified_zip(output, entries)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--upgrade", action="store_true", help="Exclude all catalog data, including empty manifests")
    parser.add_argument("--base-url", help="Actual HTTPS hosting base URL for canonical URLs and sitemap.xml")
    args = parser.parse_args()
    print(build(args.output, args.ref, upgrade=args.upgrade, base_url=args.base_url))
