"""Checks a copy of this repository: python3 tools/check.py <tree> [--base <tree> --author <login>] [--ci]"""

import argparse
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modlib  # noqa: E402

OWNER = "Baamich"


def summary_lines(tree, mods):
    """Which permissions each script asks for."""
    lines = []
    for mod in mods:
        asks = "text only"
        if mod["kind"] == "script":
            with open(os.path.join(tree, mod["main"]), encoding="utf-8") as f:
                head = f.read().splitlines()[:16]
            found = [m.group(1).strip() for m in (re.match(r"\s*--\s*sielo:(.*)", l) for l in head) if m]
            asks = ", ".join(found) or "no permissions"
        lines.append(f"- {mod['homepage']} {mod['version']}: {asks}")
    return lines


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tree")
    parser.add_argument("--base")
    parser.add_argument("--author")
    parser.add_argument("--ci", action="store_true", help="the Lua check is required")
    args = parser.parse_args()

    luac = shutil.which("luac5.4") or shutil.which("luac")
    if args.ci and luac is None:
        print("luac is not installed", file=sys.stderr)
        return 2
    errors, mods = modlib.validate_tree(args.tree, luac=luac)
    if args.base:
        errors += modlib.validate_change(args.base, args.tree, args.author or "", OWNER)

    lines = [f"Mods that passed: {len(mods)}", *summary_lines(args.tree, mods)]
    if errors:
        lines += ["", f"Problems: {len(errors)}", *[f"- {e}" for e in errors]]
    print("\n".join(lines))
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    output = os.environ.get("GITHUB_OUTPUT")
    if output and args.base and not errors and modlib.can_merge_alone(args.base, args.tree):
        with open(output, "a", encoding="utf-8") as f:
            f.write("merge=true\n")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
