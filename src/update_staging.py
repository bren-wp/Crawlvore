"""Stage a signed update into a new directory without replacing or executing anything."""
import hashlib
import hmac
import os
import shutil
import tempfile
from pathlib import Path
from update_verification import verify_manifest

def stage_update(raw, signature, trusted_key, installed, platform, package, edition, payload, staging):
    entry = verify_manifest(raw, signature, trusted_key, installed, platform, package, edition)
    payload, staging = Path(payload), Path(staging)
    if payload.name != entry["name"] or payload.is_symlink() or not payload.is_file():
        raise ValueError("Neočekivana datoteka ažuriranja.")
    if staging.exists() or staging.is_symlink():
        raise FileExistsError("Radna mapa ažuriranja već postoji.")
    if not staging.parent.is_dir() or staging.parent.is_symlink():
        raise ValueError("Neispravna radna mapa ažuriranja.")
    if shutil.disk_usage(staging.parent).free < entry["size"] + 64 * 1024**2:
        raise ValueError("Nedovoljno prostora za pripremu ažuriranja.")
    # mkdir is exclusive, and only this operation owns its contents.
    staging.mkdir(mode=0o700)
    try:
        count = 0
        digest = hashlib.sha256()
        fd, pending = tempfile.mkstemp(prefix="package-", dir=staging)
        try:
            with os.fdopen(fd,"wb") as target, payload.open("rb") as source:
                while chunk := source.read(1024*1024):
                    count += len(chunk)
                    if count > entry["size"]: raise ValueError("Veličina paketa ne odgovara manifestu.")
                    digest.update(chunk)
                    target.write(chunk)
                if count != entry["size"] or not hmac.compare_digest(digest.hexdigest(),entry["sha256"]):
                    raise ValueError("Integritet paketa nije potvrđen.")
                target.flush()
                os.fsync(target.fileno())
            os.link(pending,staging/entry["name"])
        finally:
            Path(pending).unlink(missing_ok=True)
        for name, value in (("UPDATE-MANIFEST.json",raw),("UPDATE-MANIFEST.sig",signature)):
            with (staging/name).open("xb") as file:
                file.write(value)
                file.flush()
                os.fsync(file.fileno())
        if os.name!="nt":
            fd=os.open(staging,os.O_RDONLY)
            try:os.fsync(fd)
            finally:os.close(fd)
        return {"staged":True,"version":entry["version"],"name":entry["name"],"bytes":count}
    except BaseException:
        # Never recursively delete an arbitrary caller directory or a user workspace.
        for name in (entry["name"],"UPDATE-MANIFEST.json","UPDATE-MANIFEST.sig"):
            (staging/name).unlink(missing_ok=True)
        try:staging.rmdir()
        except OSError:pass
        raise
