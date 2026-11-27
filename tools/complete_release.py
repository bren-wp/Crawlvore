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
# Independent publication contract: changing updater targets cannot silently shrink a release.
MANDATORY_PACKAGES={
    ("windows","setup","HR"):"Setup-HR-Full.exe",
    ("windows","setup","Online"):"Setup-HR-Online.exe",
    ("windows","portable","HR"):"Portable-HR-Full.exe",
    ("windows","portable","Online"):"Portable-HR-Online.exe",
    ("linux","deb","HR"):"Crawlvora-Linux-HR-Full-amd64.deb",
    ("linux","deb","Online"):"Crawlvora-Linux-HR-Online-amd64.deb",
    ("linux","portable","HR"):"Crawlvora-Linux-HR-Full-x86_64.tar.gz",
    ("linux","portable","Online"):"Crawlvora-Linux-HR-Online-x86_64.tar.gz",
}
REQUIRED=set(MANDATORY_PACKAGES.values())|SUPPORT

COMPACT_PACKAGES={k:v for k,v in MANDATORY_PACKAGES.items() if k[2]=="Online"}
COMPACT_REQUIRED=set(COMPACT_PACKAGES.values())|(SUPPORT-{"REGISTRY-HR-MANIFEST.json"})

def require_contract():
    if TARGETS!=MANDATORY_PACKAGES or len(REQUIRED)!=16 or len(COMPACT_REQUIRED)!=11:
        raise ValueError("Mandatory 16-file Croatian release contract changed")

def digest(path):
    with path.open("rb") as stream:return hashlib.file_digest(stream,"sha256").hexdigest()

def verify(root,release_version,public_key=None,mode="full"):
    require_contract()
    if mode not in ("full","online"):raise ValueError("Invalid release mode")
    targets=MANDATORY_PACKAGES if mode=="full" else COMPACT_PACKAGES
    required=REQUIRED if mode=="full" else COMPACT_REQUIRED
    root=Path(root)
    if {p.name for p in root.iterdir()}!=required:raise ValueError("Incomplete or unexpected release asset set")
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
    if data["version"]!=release_version or len(data["assets"])!=len(targets):raise ValueError("Incomplete signed update matrix")
    for platform,package,edition in targets:
        entry=verify_manifest(raw,sig,key,"0.0.0",platform,package,edition)
        verify_payload(root/entry["name"],entry)
    if mode=="full":
        snapshot=json.loads((root/"REGISTRY-HR-MANIFEST.json").read_text(encoding="utf-8"))
        if (str(snapshot["snapshot"]),snapshot["rows"],snapshot["subjects"])!=("1370",11831255,392785):
            raise ValueError("Wrong Croatian snapshot")
    sizes=json.loads((root/"PACKAGE-SIZES.json").read_text(encoding="utf-8"))["packages"]
    if len(sizes)!=len(targets) or {x["name"] for x in sizes}!=set(targets.values()):
        raise ValueError("Incomplete size report")
    for item in sizes:
        if item["bytes"]!=(root/item["name"]).stat().st_size:raise ValueError("Incorrect size report")
    checks={}
    for line in (root/"SHA256SUMS.txt").read_text(encoding="ascii").splitlines():
        value,name=line.split("  ",1)
        if name in checks:raise ValueError("Duplicate checksum")
        checks[name]=value
    if set(checks)!=required-{"SHA256SUMS.txt"}:raise ValueError("Incomplete checksums")
    for name,value in checks.items():
        if digest(root/name)!=value:raise ValueError("Checksum mismatch: "+name)
    return len(required)

if __name__=="__main__":
    print("Verified complete stable release:",verify(sys.argv[1],sys.argv[2],mode=sys.argv[3] if len(sys.argv)>3 else "full"),"assets")
