"""Marks a mod as checked by the owner, or takes the mark away.

    python tools/verify.py <id>            mark the mod as it is now
    python tools/verify.py <id> --remove   take the mark away
    python tools/verify.py --list          what is marked and whether it still holds

The mark is tied to the exact file (its SHA-256). When the author changes the mod, the green check goes away
until the new version is checked and marked again. Only the owner can change verified.json: a pull request
from anyone else may only touch its own mods/<developer>/ folder.
"""

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modlib  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE = os.path.join(ROOT, "verified.json")


def load():
    return modlib.read_verified(ROOT)


def save(marks):
    with open(FILE, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"mods": dict(sorted(marks.items()))}, f, ensure_ascii=False, indent=1)
        f.write("\n")


def current(mod_id):
    errors, mods = modlib.validate_tree(ROOT)
    for mod in mods:
        if mod["id"] == mod_id:
            with open(os.path.join(ROOT, mod["main"]), "rb") as f:
                return mod, hashlib.sha256(f.read()).hexdigest()
    if errors:
        print("\n".join(errors), file=sys.stderr)
    return None, None


def main(args):
    marks = load()
    if args == ["--list"]:
        _, mods = modlib.validate_tree(ROOT)
        by_id = {m["id"]: m for m in mods}
        for mod_id, mark in sorted(marks.items()):
            mod = by_id.get(mod_id)
            if mod is None:
                state = "no such mod any more"
            else:
                with open(os.path.join(ROOT, mod["main"]), "rb") as f:
                    holds = hashlib.sha256(f.read()).hexdigest() == mark["sha256"]
                state = "green" if holds else f"changed since {mark['version']}: check again"
            print(f"{mod_id}: {state}")
        return 0
    if len(args) == 2 and args[1] == "--remove":
        if marks.pop(args[0], None) is None:
            print(f"{args[0]} has no mark", file=sys.stderr)
            return 1
        save(marks)
        print(f"{args[0]}: mark removed")
        return 0
    if len(args) != 1 or args[0].startswith("-"):
        print(__doc__, file=sys.stderr)
        return 2
    mod, sha = current(args[0])
    if mod is None:
        print(f"{args[0]}: no such mod in mods/", file=sys.stderr)
        return 1
    marks[mod["id"]] = {"version": mod["version"], "sha256": sha}
    save(marks)
    print(f"{mod['id']} {mod['version']}: marked as checked")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
