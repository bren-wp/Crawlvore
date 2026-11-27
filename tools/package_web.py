"""Build a code-only shared-hosting archive from the exact committed source."""
import argparse
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

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


def build(output, ref="HEAD", root=ROOT):
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
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(entries.items()):
            archive.writestr(name, data)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError("Web archive integrity failure")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--ref", default="HEAD")
    args = parser.parse_args()
    print(build(args.output, args.ref))
