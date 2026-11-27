"""Generate and sign release metadata; secret is supplied only by CI environment."""
import hashlib
import json
import os
import sys
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from update_verification import TARGETS, version
from update_trust import TRUSTED_KEY_HEX

def sign(root, release_version, key_hex, edition):
    version(release_version)
    key=Ed25519PrivateKey.from_private_bytes(bytes.fromhex(key_hex))
    if key.public_key().public_bytes_raw().hex()!=TRUSTED_KEY_HEX:
        raise ValueError("Signing key does not match pinned update public key")
    root=Path(root)
    assets=[]
    for (platform,package,scope),name in TARGETS.items():
        if edition=="Online" and scope!="Online":continue
        path=root/name
        if not path.is_file() or path.is_symlink():raise ValueError("Missing package: "+name)
        with path.open("rb") as f:digest=hashlib.file_digest(f,"sha256").hexdigest()
        assets.append({"platform":platform,"package":package,"edition":scope,"name":name,"size":path.stat().st_size,"sha256":digest})
    raw=json.dumps({"schema":1,"product":"Crawlvora","version":release_version,"assets":assets},sort_keys=True,separators=(",",":")).encode()
    for name,value in (("UPDATE-MANIFEST.json",raw),("UPDATE-MANIFEST.sig",key.sign(raw))):
        with (root/name).open("xb") as stream:stream.write(value)

if __name__=="__main__":
    sign(sys.argv[1],sys.argv[2],os.environ["CRAWLVORA_UPDATE_SIGNING_KEY"],sys.argv[3])
