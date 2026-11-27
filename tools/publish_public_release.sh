#!/usr/bin/env bash
# Publish only an exact, previously validated asset set. Drafts are addressed by numeric ID.
set -euo pipefail
directory="$1"
version="$2"
source="$3"
notes="$4"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]
[[ "$source" =~ ^[0-9a-f]{40}$ ]]
tag="v$version-online"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
lookup() {
    gh api --paginate "repos/$GITHUB_REPOSITORY/releases?per_page=100" --jq ".[] | select(.tag_name == \"$tag\") | .id"
}
ids="$(lookup)"
if [ -z "$ids" ]; then
    gh api "repos/$GITHUB_REPOSITORY/git/matching-refs/tags/$tag" > "$work/refs.json"
    python -c 'import json,sys; p=json.load(open(sys.argv[1])); assert isinstance(p,list); assert not any(r["ref"]=="refs/tags/"+sys.argv[2] for r in p), "Tag already exists"' "$work/refs.json" "$tag"
    test -f "$notes"
    gh release create "$tag" --target "$source" --draft --title "Crawlvora $version - Online" --notes-file "$notes" "$directory"/*
    ids="$(lookup)"
fi
[[ "$ids" =~ ^[0-9]+$ ]] || { echo "Missing or ambiguous release ID"; exit 1; }
endpoint="repos/$GITHUB_REPOSITORY/releases/$ids"
gh api "$endpoint" > "$work/draft.json"
python -c 'import json,sys; p=json.load(open(sys.argv[1])); assert p["id"]==int(sys.argv[2]) and p["tag_name"]==sys.argv[3] and p["target_commitish"]==sys.argv[4]' "$work/draft.json" "$ids" "$tag" "$source"
# Never overwrite an uploaded asset or promote a different build.
python tools/public_release.py "$directory" --remote "$work/draft.json"
gh api --method PATCH "$endpoint" -F draft=false -F prerelease=false -f make_latest=true > "$work/promoted.json"
python - "$directory" "$work/promoted.json" "$ids" "$tag" "$source" <<'PY'
import json,sys
from pathlib import Path
from tools.public_release import verify_remote
root,path,identity,tag,source=sys.argv[1:]
p=json.loads(Path(path).read_text())
assert p["id"]==int(identity) and p["tag_name"]==tag and p["target_commitish"]==source
assert p["draft"] is False and p["prerelease"] is False
verify_remote(Path(root),dict(p,draft=True))
print("Verified published stable release:",p["html_url"])
PY
gh api "repos/$GITHUB_REPOSITORY/git/ref/tags/$tag" > "$work/tag.json"
python -c 'import json,sys; p=json.load(open(sys.argv[1])); assert p["object"]["type"]=="commit" and p["object"]["sha"]==sys.argv[2]' "$work/tag.json" "$source"
gh api "repos/$GITHUB_REPOSITORY/releases/latest" --jq .id > "$work/latest.txt"
test "$(cat "$work/latest.txt")" = "$ids"
