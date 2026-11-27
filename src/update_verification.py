"""Verify signed update metadata and local payloads; never execute downloaded files."""
import hashlib
import hmac
import json
import re
from pathlib import Path
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

MAX_MANIFEST = 64 * 1024
MAX_PAYLOAD = 2 * 1024**3 - 1
TARGETS = {
    ("windows", "setup", "HR"): "Setup-HR-Full.exe",
    ("windows", "setup", "Online"): "Setup-HR-Online.exe",
    ("windows", "portable", "HR"): "Portable-HR-Full.exe",
    ("windows", "portable", "Online"): "Portable-HR-Online.exe",
    ("linux", "deb", "HR"): "Crawlvora-Linux-HR-Full-amd64.deb",
    ("linux", "deb", "Online"): "Crawlvora-Linux-HR-Online-amd64.deb",
    ("linux", "portable", "HR"): "Crawlvora-Linux-HR-Full-x86_64.tar.gz",
    ("linux", "portable", "Online"): "Crawlvora-Linux-HR-Online-x86_64.tar.gz",
}

def version(value):
    if not isinstance(value, str) or not re.fullmatch(r"(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})", value):
        raise ValueError("Neispravna verzija.")
    return tuple(map(int, value.split(".")))

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicirani ključ manifesta.")
        result[key] = value
    return result

def verify_manifest(raw, signature, public_key, installed, platform, package, edition):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_MANIFEST:
        raise ValueError("Neispravna veličina manifesta.")
    if not isinstance(signature, bytes) or len(signature) != 64 or not isinstance(public_key, bytes) or len(public_key) != 32:
        raise ValueError("Nedostaje pouzdan potpis manifesta.")
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, raw)
    except InvalidSignature:
        raise ValueError("Potpis manifesta nije valjan.") from None
    data = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
    if not isinstance(data, dict) or set(data) != {"schema", "product", "version", "assets"} or type(data["schema"]) is not int or data["schema"] != 1 or data["product"] != "Crawlvora":
        raise ValueError("Neispravan manifest ažuriranja.")
    if version(data["version"]) <= version(installed):
        raise ValueError("Ažuriranje mora biti novije od instalirane verzije.")
    target = (platform, package, edition)
    if target not in TARGETS:
        raise ValueError("Nepodržano izdanje.")
    assets = data["assets"]
    if not isinstance(assets, list) or not 1 <= len(assets) <= len(TARGETS):
        raise ValueError("Neispravan popis paketa.")
    matched = None
    seen = set()
    for entry in assets:
        if not isinstance(entry, dict) or set(entry) != {"platform", "package", "edition", "name", "size", "sha256"}:
            raise ValueError("Neispravan zapis paketa.")
        if not all(isinstance(entry[k], str) for k in ("platform", "package", "edition", "name", "sha256")):
            raise ValueError("Neispravan tip zapisa paketa.")
        key = (entry["platform"], entry["package"], entry["edition"])
        if key in seen or TARGETS.get(key) != entry["name"]:
            raise ValueError("Duplicirano ili nepoznato ime paketa.")
        seen.add(key)
        if type(entry["size"]) is not int or not 0 < entry["size"] <= MAX_PAYLOAD or not re.fullmatch(r"[a-f0-9]{64}", entry["sha256"]):
            raise ValueError("Neispravan kontrolni zbroj ili veličina.")
        if key == target:
            matched = entry
    if matched is None:
        raise ValueError("Nema ažuriranja za instalirano izdanje.")
    return {"version": data["version"], **matched}

def verify_payload(path, entry):
    # Input must come from verify_manifest with an independently trusted key.
    path = Path(path)
    if path.name != entry["name"] or path.is_symlink() or not path.is_file():
        raise ValueError("Neočekivana datoteka ažuriranja.")
    count = 0
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            count += len(chunk)
            if count > entry["size"]:
                raise ValueError("Veličina paketa ne odgovara manifestu.")
            digest.update(chunk)
    if count != entry["size"] or not hmac.compare_digest(digest.hexdigest(), entry["sha256"]):
        raise ValueError("Integritet paketa nije potvrđen.")
    return {"verified": True, "version": entry["version"], "name": path.name}
