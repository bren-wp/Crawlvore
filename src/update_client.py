"""Crawlvora signed update client: download, verify and stage one matching package."""
import argparse
import hashlib
import hmac
import json
import os
import re
import shutil
import sys
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
import requests
from update_verification import verify_manifest, verify_payload, version
from update_staging import stage_update
from update_trust import TRUSTED_KEY_HEX

REPO = "https://github.com/bren-wp/Crawlvore/releases/download/"
ALLOWED = {"github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com", "github-releases.githubusercontent.com"}
TAG = re.compile(r"v(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})-(online|hr)")

def safe_url(url):
    p=urlsplit(url)
    return p.scheme=="https" and p.hostname in ALLOWED and p.port in (None,443) and not p.username and not p.password

def fetch(session, url, limit, destination=None, expected_hash=None, exact_size=None):
    """No credentials, explicit HTTPS redirect allowlist, bounded streaming."""
    for _ in range(6):
        if not safe_url(url): raise ValueError("Nedopuštena adresa ažuriranja.")
        with session.get(url,stream=True,allow_redirects=False,timeout=(10,60),headers={"Accept-Encoding":"identity"}) as response:
            if response.status_code in (301,302,303,307,308):
                url=response.headers.get("Location","")
                continue
            response.raise_for_status()
            if response.status_code!=200:raise ValueError("Nepotpuni odgovor.")
            declared=response.headers.get("Content-Length")
            if declared is not None and (not declared.isascii() or not declared.isdigit() or int(declared)>limit):
                raise ValueError("Prevelik odgovor.")
            digest=hashlib.sha256();count=0;data=bytearray()
            stream=destination.open("xb") if destination else None
            try:
                for chunk in response.iter_content(chunk_size=1024*1024):
                    count+=len(chunk)
                    if count>limit:raise ValueError("Prevelik odgovor.")
                    digest.update(chunk)
                    if stream:stream.write(chunk)
                    else:data.extend(chunk)
                if exact_size is not None and count!=exact_size:raise ValueError("Veličina paketa nije valjana.")
                if expected_hash is not None and not hmac.compare_digest(digest.hexdigest(),expected_hash):raise ValueError("Kontrolni zbroj nije valjan.")
                if stream:stream.flush();os.fsync(stream.fileno())
                return bytes(data) if stream is None else None
            finally:
                if stream:stream.close()
    raise ValueError("Previše preusmjeravanja.")

def download(tag,installed,platform,package,edition,staging,session=None):
    if not TAG.fullmatch(tag) or (edition=="HR" and tag.split("-")[-1]!="hr") or edition not in ("HR","Online"):
        raise ValueError("Oznaka izdanja ne odgovara instalaciji.")
    if version(tag[1:].split("-")[0])<=version(installed):raise ValueError("Ažuriranje nije novije.")
    staging=Path(staging).absolute()
    if staging.exists() or staging.is_symlink() or not staging.parent.is_dir():
        raise ValueError("Odaberite novu mapu za pripremu.")
    owned=session is None
    session=session or requests.Session()
    # Do not forward local proxy/netrc credentials to GitHub.
    if owned:session.trust_env=False
    try:
        base=REPO+tag+"/"
        raw=fetch(session,base+"UPDATE-MANIFEST.json",65536)
        signature=fetch(session,base+"UPDATE-MANIFEST.sig",64)
        key=bytes.fromhex(TRUSTED_KEY_HEX)
        entry=verify_manifest(raw,signature,key,installed,platform,package,edition)
        if entry["version"]!=tag[1:].split("-")[0]:raise ValueError("Verzija manifesta nije jednaka izdanju.")
        if shutil.disk_usage(staging.parent).free<2*entry["size"]+64*1024**2:raise ValueError("Nedovoljno slobodnog prostora.")
        with tempfile.TemporaryDirectory(prefix="crawlvora-download-",dir=staging.parent) as tmp:
            payload=Path(tmp)/entry["name"]
            fetch(session,base+entry["name"],entry["size"],payload,entry["sha256"],entry["size"])
            return stage_update(raw,signature,key,installed,platform,package,edition,payload,staging)
    finally:
        if owned:session.close()

def install_staged(staging,installed,platform,package,edition):
    """Reverify immediately before explicitly requested installation."""
    staging=Path(staging).resolve()
    manifest=staging/"UPDATE-MANIFEST.json";signature=staging/"UPDATE-MANIFEST.sig"
    if any(p.is_symlink() or not p.is_file() for p in (manifest,signature)):
        raise ValueError("Nedostaje potpisani manifest.")
    if manifest.stat().st_size>65536 or signature.stat().st_size!=64:
        raise ValueError("Neispravan manifest.")
    entry=verify_manifest(manifest.read_bytes(),signature.read_bytes(),bytes.fromhex(TRUSTED_KEY_HEX),installed,platform,package,edition)
    payload=staging/entry["name"]
    verify_payload(payload,entry)
    if platform=="windows" and package=="setup":
        args=[str(payload)]
    elif platform=="linux" and package=="deb":
        if os.geteuid()==0:
            raise ValueError("Pokrenite updater kao obični korisnik.")
        if not Path("/usr/bin/sudo").is_file() or not Path("/usr/bin/apt-get").is_file():
            raise ValueError("Ovaj sustav nema podržani APT instalacijski mehanizam.")
        args=["/usr/bin/sudo","--","/usr/bin/apt-get","install",str(payload)]
    else:
        raise ValueError("Portable paket je provjeren; zamijenite aplikaciju ručno nakon zatvaranja.")
    return subprocess.run(args,check=False).returncode  # nosec B603 -- signed verified package and fixed installer arguments.

def main():
    parser=argparse.ArgumentParser(description="Crawlvora – sigurno preuzimanje nadogradnje")
    parser.add_argument("--version",action="version",version="Crawlvora Update 8.1.7")
    parser.add_argument("--tag",required=True)
    parser.add_argument("--installed",required=True)
    parser.add_argument("--edition",choices=("HR","Online"),required=True)
    parser.add_argument("--package",choices=("setup","deb","portable"),required=True)
    parser.add_argument("--staging",type=Path,required=True)
    parser.add_argument("--install",action="store_true",help="Nakon provjere, uz potvrdu pokreni instalacijski paket.")
    parser.add_argument("--staged",action="store_true",help="Upotrijebi postojeću potpisanu pripremu bez ponovnog preuzimanja.")
    a=parser.parse_args()
    platform="windows" if sys.platform=="win32" else "linux" if sys.platform.startswith("linux") else ""
    if not platform or a.package not in (("setup","portable") if platform=="windows" else ("deb","portable")):parser.error("Paket nije za ovaj operacijski sustav.")
    try:
        if not a.staged:
            result=download(a.tag,a.installed,platform,a.package,a.edition,a.staging)
            print(json.dumps(result,ensure_ascii=False))
        if a.staged and not a.install:raise ValueError("Za postojeću pripremu odaberite --install.")
        if a.install:
            print("Zatvorite sve prozore Crawlvora. Provjerite sigurnosnu kopiju prije instalacije.")
            if input("Pokrenuti instalaciju? Upišite DA: ").strip()!="DA":return 0
            return install_staged(a.staging,a.installed,platform,a.package,a.edition)
        print("Paket je provjeren i spreman. Zatvorite Crawlvora i pokrenite instalaciju iz odabrane mape.")
        return 0
    except (ValueError,OSError,requests.RequestException) as error:
        # Avoid displaying redirect URLs or transport secrets in exception text.
        print("Ažuriranje nije pripremljeno: "+(str(error) if isinstance(error,ValueError) else "Mrežna ili datotečna pogreška."),file=sys.stderr)
        return 1

if __name__=="__main__":sys.exit(main())
