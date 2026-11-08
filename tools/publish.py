"""Puts every mod into its release and writes the list: python3 tools/publish.py <repo> <catalog.json>

Each mod has a release mod-<id>. GitHub counts downloads of release files, and that count is the number of
installs shown in the app: the app itself reports nothing. A release of a removed mod is deleted with its files.
Needs gh and GH_TOKEN.
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modlib  # noqa: E402

REPOSITORY = "Baamich/Sielo-mods"
TAG_PREFIX = "mod-"


def plan(mods, releases, repository=REPOSITORY):
    """What has to happen. mods carry their file in data; releases are as the GitHub API gives them."""
    known = {r["tag_name"]: r for r in releases if r["tag_name"].startswith(TAG_PREFIX)}
    entries, create, upload = [], [], []
    for mod in mods:
        data = mod["data"]
        sha = hashlib.sha256(data).hexdigest()
        tag = f"{TAG_PREFIX}{mod['id']}"
        extension = os.path.splitext(mod["main"])[1]
        # a new file is a new name, so an old list never points at different bytes
        asset = f"{mod['id']}-{mod['version']}-{sha[:12]}{extension}"
        assets = known.get(tag, {}).get("assets", [])
        if tag not in known:
            create.append((tag, mod["name"]))
        if asset not in {a["name"] for a in assets}:
            upload.append((tag, asset, data))
        entries.append({
            "id": mod["id"],
            "kind": mod["kind"],
            "name": mod["name"],
            "author": mod["author"],
            "version": mod["version"],
            "license": mod["license"],
            "description": mod["description"],
            "url": f"https://github.com/{repository}/releases/download/{tag}/{asset}",
            "sha256": sha,
            "size": len(data),
            "homepage": f"https://github.com/{repository}/tree/main/{mod['homepage']}",
            "installs": sum(a.get("download_count", 0) for a in assets),
        })
    entries.sort(key=lambda e: e["id"].lower())
    wanted = {f"{TAG_PREFIX}{m['id']}" for m in mods}
    return entries, create, upload, sorted(set(known) - wanted)


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout


def main():
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    repo, out = sys.argv[1:]
    errors, mods = modlib.validate_tree(repo)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    for mod in mods:
        with open(os.path.join(repo, mod["main"]), "rb") as f:
            mod["data"] = f.read()
    pages = json.loads(gh("api", "--paginate", "--slurp", f"repos/{REPOSITORY}/releases?per_page=100"))
    releases = [r for page in pages for r in page]
    entries, create, upload, stale = plan(mods, releases)
    for tag, name in create:
        gh("release", "create", tag, "--repo", REPOSITORY, "--title", name,
           "--notes", "Files of this mod for the Sielo mods list.", "--latest=false")
    with tempfile.TemporaryDirectory() as folder:
        for tag, asset, data in upload:
            path = os.path.join(folder, asset)
            with open(path, "wb") as f:
                f.write(data)
            gh("release", "upload", tag, path, "--repo", REPOSITORY)
    for tag in stale:
        gh("release", "delete", tag, "--repo", REPOSITORY, "--cleanup-tag", "--yes")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"mods": entries}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"Mods: {len(entries)}, uploaded: {len(upload)}, removed: {len(stale)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
