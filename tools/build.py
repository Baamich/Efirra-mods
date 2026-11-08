"""Builds the list that the app reads: python tools/build.py <repo> <catalog.json>

Every file is pinned to its sum and to the commit that last changed it, so nothing can be swapped behind the list.
"""

import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modlib  # noqa: E402

REPOSITORY = "Baamich/Sielo-mods"


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def main():
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    repo, out = sys.argv[1:]
    errors, mods = modlib.validate_tree(repo)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    if git(repo, "status", "--porcelain", "--", "mods"):
        print("mods has changes that are not committed", file=sys.stderr)
        return 1
    entries = []
    for mod in mods:
        main_file = mod["main"]
        commit = git(repo, "log", "-1", "--format=%H", "--", main_file)
        try:
            git(repo, "merge-base", "--is-ancestor", commit, "origin/main")
        except subprocess.CalledProcessError:
            print(f"{main_file}: commit {commit} is not pushed yet", file=sys.stderr)
            return 1
        with open(os.path.join(repo, main_file), "rb") as f:
            data = f.read()
        entries.append({
            "id": mod["id"],
            "kind": mod["kind"],
            "name": mod["name"],
            "author": mod["author"],
            "version": mod["version"],
            "license": mod["license"],
            "description": mod["description"],
            "url": f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{main_file}",
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
            "homepage": f"https://github.com/{REPOSITORY}/tree/main/{mod['homepage']}",
        })
    entries.sort(key=lambda e: e["id"].lower())
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"mods": entries}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"Mods in the list: {len(entries)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
