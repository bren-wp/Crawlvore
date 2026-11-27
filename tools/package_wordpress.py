"""Reproducible, code-only WordPress plugin from the exact selected Git commit."""
import argparse
import io
from pathlib import Path
import subprocess
import zipfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.package_web import write_verified_zip, ROOT

PLUGIN = "crawlvora-business-directory"
REQUIRED = {PLUGIN + "/" + item for item in (
    "crawlvora-business-directory.php", "includes/class-catalog.php",
    "assets/directory.css", "readme.txt", "uninstall.php")}


def build(output, ref="HEAD", root=ROOT):
    raw = subprocess.check_output(
        ["git", "archive", "--format=zip", ref, "wordpress/" + PLUGIN], cwd=root)
    entries = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = info.filename.removeprefix("wordpress/")
            if name not in REQUIRED or name in entries:
                raise ValueError("Unexpected plugin member: " + name)
            if (info.external_attr >> 16) & 0o170000 not in (0, 0o100000):
                raise ValueError("Non-regular plugin member: " + name)
            entries[name] = archive.read(info)
    if set(entries) != REQUIRED:
        raise ValueError("Incomplete plugin package")
    return write_verified_zip(output, entries)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--ref", default="HEAD")
    args = parser.parse_args()
    print(build(args.output, args.ref))
