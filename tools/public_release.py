"""Validate and promote the database-free public Online release separately from Full/HR/GB."""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.edition_acceptance import file_info
from tools.verify_release_assets import MAX_SIZE, validate_zip
from tools.package_web import approved

BINARIES=("Portable-Online.exe","Setup-Online.exe","Crawlvora-Linux-amd64.deb","Crawlvora-Linux-x86_64.tar.gz")
WEB=("Crawlvora-Web.zip","Crawlvora-Web-Upgrade.zip")
FILES=set(BINARIES+WEB+("Crawlvora-source.zip","Crawlvora-WordPress.zip","REGISTRY-MANIFEST.json"))
ALL_FILES=FILES|{"SHA256SUMS.txt"}


def no_catalog(path):
    parts=PurePosixPath(path).parts
    for part in parts:
        name=part.casefold()
        if (name in {"national-data","registry-bundle","tvrtk_output.csv"} or name.startswith("registry-seed")
                or re.search(r"\.(?:sqlite3?|db)(?:$|[-.])",name)):
            raise ValueError("Unexpected data member: "+path)


def accepted_files(root,names):
    expected={}
    for line in (root/"SHA256SUMS.txt").read_text(encoding="ascii").splitlines():
        match=re.fullmatch(r"([a-f0-9]{64}) [ *]([A-Za-z0-9._-]+)",line)
        if not match or match[2] in expected:
            raise ValueError("Invalid checksum manifest")
        expected[match[2]]=match[1]
    result={}
    for name in names:
        info=file_info(root/name)
        if info["size"]>=MAX_SIZE or expected.get(name)!=info["sha256"]:
            raise ValueError("Unverified artifact: "+name)
        result[name]=info
    return result


def online_tar(archive):
    found=0
    for member in archive:
        no_catalog(member.name)
        if member.issym() or member.islnk():
            no_catalog(member.linkname)
        if member.isfile() and PurePosixPath(member.name).name=="edition.json":
            if member.size>128:
                raise ValueError("Invalid edition metadata")
            with archive.extractfile(member) as stream:
                if json.load(stream)!={"edition":"Online"}:
                    raise ValueError("Not an Online package")
            found+=1
    if found!=1:
        raise ValueError("Missing or ambiguous Online edition metadata")


def check_linux(root):
    with tarfile.open(root/BINARIES[3],"r:gz") as archive:
        online_tar(archive)
    with subprocess.Popen(["dpkg-deb","--fsys-tarfile",str(root/BINARIES[2])],stdout=subprocess.PIPE) as process:
        with tarfile.open(fileobj=process.stdout,mode="r|") as archive:
            online_tar(archive)
        while process.stdout.read(65536):
            pass
        if process.wait()!=0:
            raise ValueError("Invalid Debian package")


def prepare(candidate,web,output,source,version):
    if not re.fullmatch(r"[a-f0-9]{40}",source) or not re.fullmatch(r"\d+\.\d+\.\d+",version):
        raise ValueError("Invalid source or version")
    selected=accepted_files(candidate,BINARIES+("Crawlvora-WordPress.zip",))
    web_selected=accepted_files(web,WEB)
    receipt=json.loads((candidate/"acceptance-Online.json").read_text(encoding="utf-8-sig"))
    if receipt!={"edition":"Online","source_commit":source,"snapshots":{},
                 "assets":{name:selected[name] for name in BINARIES[:2]}}:
        raise ValueError("Online acceptance receipt does not match artifacts")
    check_linux(candidate)
    validate_zip(candidate/"Crawlvora-WordPress.zip",wordpress=True)
    output.mkdir()
    for name in BINARIES+("Crawlvora-WordPress.zip",):
        shutil.copyfile(candidate/name,output/name)
    for name in WEB:
        shutil.copyfile(web/name,output/name)
    for name,info in {**selected,**web_selected}.items():
        if file_info(output/name)!=info:
            raise ValueError("Artifact changed during publication staging: "+name)
    subprocess.run(["git","archive","--format=zip","--prefix=Crawlvora/","-o",str(output/"Crawlvora-source.zip"),
                    source,"--",".",":(exclude)tvrtk_output.csv"],check=True)
    validate_zip(output/"Crawlvora-source.zip")
    with zipfile.ZipFile(output/"Crawlvora-source.zip") as archive:
        for member in archive.infolist():
            no_catalog(member.filename)
            prefix="Crawlvora/webstranica/storage/data/"
            if not member.is_dir() and member.filename.startswith(prefix):
                name=member.filename.removeprefix("Crawlvora/webstranica/")
                if name!="storage/data/.gitignore" and not approved(name,archive.read(member)):
                    raise ValueError("Source archive contains published catalog data")
    manifest={"edition":"Online","registry_bundle_included":False,"complete":False,
              "snapshot":None,"source_commit":source,"version":version,
              "reason":"Application release without bundled national catalogs. Full/HR/GB distribution is separate."}
    (output/"REGISTRY-MANIFEST.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    (output/"SHA256SUMS.txt").write_text("".join(file_info(output/name)["sha256"]+"  "+name+"\n" for name in sorted(FILES)),encoding="ascii")
    validate(output)


def validate(root):
    if {p.name for p in root.iterdir()}!=ALL_FILES:
        raise ValueError("Public release asset matrix mismatch")
    result=accepted_files(root,FILES)
    result["SHA256SUMS.txt"]=file_info(root/"SHA256SUMS.txt")
    return result


def verify_remote(root,release):
    expected=validate(root)
    if release.get("draft") is not True:
        raise ValueError("Release must still be a draft")
    assets=release.get("assets",[])
    if len(assets)!=len(ALL_FILES) or {a["name"] for a in assets}!=ALL_FILES:
        raise ValueError("Remote public release matrix mismatch")
    for asset in assets:
        info=expected[asset["name"]]
        if (asset.get("state")!="uploaded" or asset.get("size")!=info["size"]
                or asset.get("digest")!="sha256:"+info["sha256"]):
            raise ValueError("Remote verification failed: "+asset["name"])


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory",type=Path)
    parser.add_argument("--candidate",type=Path)
    parser.add_argument("--web",type=Path)
    parser.add_argument("--source")
    parser.add_argument("--version")
    parser.add_argument("--remote",type=Path)
    args=parser.parse_args()
    if args.remote:
        verify_remote(args.directory,json.loads(args.remote.read_text(encoding="utf-8")))
    elif args.candidate and args.web and args.source and args.version:
        prepare(args.candidate,args.web,args.directory,args.source,args.version)
    else:
        parser.error("Provide candidate, web, source and version, or a remote draft response")
    print("Public Online release verification passed")
