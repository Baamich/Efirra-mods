"""Revokes a dangerous mod: Efirra removes it from every computer where it is installed.

    python tools/revoke.py <id> "reason"     revoke the mod's current file
    python tools/revoke.py --sha <sha256> "reason"   revoke a file that is no longer in mods/
    python tools/revoke.py --list            what is revoked
    python tools/revoke.py --undo <id or sha256>   take a revocation back (a mistake or a test)

Revoking does not delete the mod folder: delete it too, so nobody installs it again. The app checks the list
when the Mods window opens and once at start if any mods are installed. Only the owner can change revoked.json.
"""

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modlib  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE = os.path.join(ROOT, "revoked.json")


def load():
    try:
        with open(FILE, encoding="utf-8") as f:
            return json.load(f).get("revoked", [])
    except (OSError, ValueError):
        return []


def save(items):
    with open(FILE, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"revoked": items}, f, ensure_ascii=False, indent=1)
        f.write("\n")


def main(args):
    items = load()
    if args == ["--list"]:
        for item in items:
            print(f"{item.get('id', '?')}: {item.get('sha256')} — {item.get('reason', '')}")
        return 0
    if len(args) == 2 and args[0] == "--undo":
        wanted = args[1].lower()
        left = [i for i in items if i.get("id", "").lower() != wanted and i.get("sha256") != wanted]
        if len(left) == len(items):
            print(f"{args[1]}: not revoked", file=sys.stderr)
            return 1
        save(left)
        print(f"{args[1]}: revocation taken back. Commit and push.")
        return 0
    if len(args) == 3 and args[0] == "--sha":
        sha, reason, mod_id = args[1].lower(), args[2], "?"
    elif len(args) == 2:
        mod_id, reason = args
        _, mods = modlib.validate_tree(ROOT)
        mod = next((m for m in mods if m["id"] == mod_id), None)
        if mod is None:
            print(f"{mod_id}: no such mod in mods/, use --sha", file=sys.stderr)
            return 1
        with open(os.path.join(ROOT, mod["main"]), "rb") as f:
            sha = hashlib.sha256(f.read()).hexdigest()
    else:
        print(__doc__, file=sys.stderr)
        return 2
    if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        print("sha256 must be 64 hex characters", file=sys.stderr)
        return 1
    if any(i.get("sha256") == sha for i in items):
        print("already revoked")
        return 0
    items.append({"id": mod_id, "sha256": sha, "reason": reason})
    save(items)
    print(f"{mod_id}: revoked. Delete its folder in mods/ too, then commit and push.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
