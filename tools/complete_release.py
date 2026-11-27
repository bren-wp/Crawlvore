"""Fail closed unless the complete stable release has every required artifact."""
import hashlib
import json
import sys
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from update_verification import TARGETS, verify_manifest, verify_payload
from update_trust import TRUSTED_KEY_HEX

SUPPORT={"Update.exe","crawlvora-update","Crawlvora-source.zip","REGISTRY-HR-MANIFEST.json",
         "PACKAGE-SIZES.json","UPDATE-MANIFEST.json","UPDATE-MANIFEST.sig","SHA256SUMS.txt"}
REQUIRED=set(TARGETS.values())|SUPPORT

def digest(path):
    with path.open("rb") as stream:return hashlib.file_digest(stream,"sha256").hexdigest()

def verify(root,release_version,public_key=None):
    root=Path(root)
    if {p.name for p in root.iterdir()}!=REQUIRED:raise ValueError("Incomplete or unexpected release asset set")
    for path in root.iterdir():
        if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<2147483648:
            raise ValueError("Invalid asset: "+path.name)
    key=public_key if public_key is not None else bytes.fromhex(TRUSTED_KEY_HEX)
    manifest=root/"UPDATE-MANIFEST.json"
    signature=root/"UPDATE-MANIFEST.sig"
    if manifest.stat().st_size>65536 or signature.stat().st_size!=64:raise ValueError("Invalid signed metadata size")
    raw,sig=manifest.read_bytes(),signature.read_bytes()
    Ed25519PublicKey.from_public_bytes(key).verify(sig,raw)
    data=json.loads(raw)
    if data["version"]!=release_version or len(data["assets"])!=len(TARGETS):raise ValueError("Incomplete signed update matrix")
    for platform,package,edition in TARGETS:
        entry=verify_manifest(raw,sig,key,"0.0.0",platform,package,edition)
        verify_payload(root/entry["name"],entry)
    snapshot=json.loads((root/"REGISTRY-HR-MANIFEST.json").read_text(encoding="utf-8"))
    if (str(snapshot["snapshot"]),snapshot["rows"],snapshot["subjects"])!=("1370",11831255,392785):
        raise ValueError("Wrong Croatian snapshot")
    sizes=json.loads((root/"PACKAGE-SIZES.json").read_text(encoding="utf-8"))["packages"]
    if len(sizes)!=8 or {x["name"] for x in sizes}!=set(TARGETS.values()):
        raise ValueError("Incomplete size report")
    for item in sizes:
        if item["bytes"]!=(root/item["name"]).stat().st_size:raise ValueError("Incorrect size report")
    checks={}
    for line in (root/"SHA256SUMS.txt").read_text(encoding="ascii").splitlines():
        value,name=line.split("  ",1)
        if name in checks:raise ValueError("Duplicate checksum")
        checks[name]=value
    if set(checks)!=REQUIRED-{"SHA256SUMS.txt"}:raise ValueError("Incomplete checksums")
    for name,value in checks.items():
        if digest(root/name)!=value:raise ValueError("Checksum mismatch: "+name)
    return len(REQUIRED)

if __name__=="__main__":
    print("Verified complete stable release:",verify(sys.argv[1],sys.argv[2]),"assets")
