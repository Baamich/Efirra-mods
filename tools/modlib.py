"""Rules for the mods folder. Only reads files as data: nothing from a mod is ever run here."""

import json
import os
import re
import subprocess
import tempfile

MAX_FILE = 1024 * 1024
MAX_SHORT = 64
MAX_DESCRIPTION = 500
MAX_PROJECTS = 20
SLUG = re.compile(r"^[a-z][a-z0-9-]*$")
LANGUAGE_CODE = re.compile(r"^[A-Za-z][A-Za-z0-9]{1,7}(-[A-Za-z0-9]{1,5})?$")
VERSION = re.compile(r"^\d{1,6}(\.\d{1,6}){0,3}$")
GITHUB_LOGIN = re.compile(r"^[A-Za-z0-9](-?[A-Za-z0-9]){0,38}$")
RESERVED = {"con", "prn", "aux", "nul"}
BUILTIN_LANGUAGES = {"ru", "en"}
# names people would take for the program itself
RESERVED_DEVELOPERS = {"sielo", "baamich", "official", "admin", "support", "partywatcher", "obs"}
PROJECT_FILES = {"mod.json", "main.lua", "main.json", "README.md", "LICENSE"}
MOD_FIELDS = {"kind", "name", "version", "license", "description", "code"}


def is_clean(text, limit):
    return (
        isinstance(text, str)
        and text.strip() != ""
        and len(text) <= limit
        and not any(ord(c) < 32 or ord(c) == 127 for c in text)
    )


def good_slug(name, longest):
    return (
        2 <= len(name) <= longest
        and SLUG.match(name) is not None
        and not name.endswith("-")
        and name not in RESERVED
    )


def read_json(path, errors, shown):
    try:
        with open(path, encoding="utf-8") as f:
            value = json.load(f)
    except (OSError, ValueError):
        errors.append(f"{shown}: not readable JSON in UTF-8")
        return None
    if not isinstance(value, dict):
        errors.append(f"{shown}: must be a JSON object")
        return None
    return value


def lua_syntax_problem(path, luac):
    with tempfile.TemporaryDirectory() as out:
        try:
            # -p only parses: the script is not run
            result = subprocess.run(
                [luac, "-p", "-o", os.path.join(out, "x"), path],
                capture_output=True, text=True, timeout=20,
            )
        except (OSError, subprocess.SubprocessError) as e:
            return f"lua check failed: {e}"
    if result.returncode != 0:
        lines = result.stderr.strip().splitlines()
        return lines[-1] if lines else "syntax error"
    return None


def check_main_file(path, kind, code, errors, shown, luac):
    size = os.path.getsize(path)
    if size == 0 or size > MAX_FILE:
        errors.append(f"{shown}: size must be from 1 byte to 1 MB")
        return
    with open(path, "rb") as f:
        data = f.read()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        errors.append(f"{shown}: must be UTF-8 text")
        return
    if kind == "script":
        if data[:1] == b"\x1b":
            errors.append(f"{shown}: compiled Lua is not accepted, send the source")
        elif luac:
            problem = lua_syntax_problem(path, luac)
            if problem:
                errors.append(f"{shown}: {problem}")
    else:
        try:
            value = json.loads(text.lstrip("﻿"))
        except ValueError:
            errors.append(f"{shown}: not valid JSON")
            return
        if not isinstance(value, dict) or not value or not all(
            isinstance(v, str) for v in value.values()
        ):
            errors.append(f"{shown}: must be an object of text values")
        elif f"language.{code}" not in value:
            errors.append(f"{shown}: needs language.{code} with the name of the language")


def check_project(root, developer, project, seen_ids, errors, luac):
    folder = os.path.join(root, "mods", developer, project)
    shown = f"mods/{developer}/{project}"
    if not good_slug(project, 20):
        errors.append(f"{shown}: folder name must be 2-20 of a-z, 0-9 and -, starting with a letter")
    found = set()
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if os.path.islink(path) or not os.path.isfile(path):
            errors.append(f"{shown}/{name}: only plain files, no folders or links")
        elif name not in PROJECT_FILES:
            errors.append(f"{shown}/{name}: file not allowed, only {', '.join(sorted(PROJECT_FILES))}")
        else:
            found.add(name)
    if "mod.json" not in found:
        errors.append(f"{shown}: mod.json is missing")
        return None
    mod = read_json(os.path.join(folder, "mod.json"), errors, f"{shown}/mod.json")
    if mod is None:
        return None
    before = len(errors)
    unknown = set(mod) - MOD_FIELDS
    if unknown:
        errors.append(f"{shown}/mod.json: unknown fields: {', '.join(sorted(unknown))}")
    kind = mod.get("kind")
    if kind not in ("script", "language"):
        errors.append(f"{shown}/mod.json: kind must be script or language")
        return None
    if not is_clean(mod.get("name"), MAX_SHORT):
        errors.append(f"{shown}/mod.json: name is required, one line up to {MAX_SHORT} characters")
    if not isinstance(mod.get("version"), str) or VERSION.match(mod["version"]) is None:
        errors.append(f"{shown}/mod.json: version must look like 1.0 or 1.2.3")
    if not is_clean(mod.get("license"), MAX_SHORT):
        errors.append(f"{shown}/mod.json: license is required")
    description = mod.get("description")
    if (
        not isinstance(description, dict)
        or "en" not in description
        or not all(
            LANGUAGE_CODE.match(k) and is_clean(v, MAX_DESCRIPTION) for k, v in description.items()
        )
    ):
        errors.append(
            f"{shown}/mod.json: description needs en, each one line up to {MAX_DESCRIPTION} characters"
        )
    code = mod.get("code")
    if kind == "language":
        if (
            not isinstance(code, str)
            or LANGUAGE_CODE.match(code) is None
            or len(code) > 8
            or code.lower() in RESERVED
            or code.lower() in BUILTIN_LANGUAGES
        ):
            errors.append(f"{shown}/mod.json: code must be a language code such as de or pt-BR, not ru or en")
            return None
        mod_id = code
        main = "main.json"
    else:
        if code is not None:
            errors.append(f"{shown}/mod.json: code is only for languages")
        mod_id = f"{developer}-{project}"
        main = "main.lua"
    other_main = "main.json" if main == "main.lua" else "main.lua"
    if other_main in found:
        errors.append(f"{shown}/{other_main}: a {kind} uses {main}")
    if main not in found:
        errors.append(f"{shown}: {main} is missing")
    else:
        check_main_file(os.path.join(folder, main), kind, code, errors, f"{shown}/{main}", luac)
    owner = seen_ids.get(mod_id.lower())
    if owner:
        errors.append(f"{shown}: {mod_id} is already taken by {owner}")
    seen_ids[mod_id.lower()] = shown
    if len(errors) != before:
        return None
    return {
        "id": mod_id,
        "kind": kind,
        "name": mod["name"],
        "author": developer,
        "version": mod["version"],
        "license": mod["license"],
        "description": description,
        "main": f"mods/{developer}/{project}/{main}",
        "homepage": shown,
    }


def validate_tree(root, luac=None):
    """All problems in the mods folder and the mods that are fine."""
    errors = []
    mods = []
    seen_ids = {}
    base = os.path.join(root, "mods")
    if not os.path.isdir(base):
        return errors, mods
    for developer in sorted(os.listdir(base)):
        folder = os.path.join(base, developer)
        if developer == ".gitkeep":
            continue
        shown = f"mods/{developer}"
        if os.path.islink(folder) or not os.path.isdir(folder):
            errors.append(f"{shown}: only developer folders belong here")
            continue
        if not good_slug(developer, 19):
            errors.append(f"{shown}: folder name must be 2-19 of a-z, 0-9 and -, starting with a letter")
        info = None
        projects = []
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            if os.path.islink(path):
                errors.append(f"{shown}/{name}: links are not allowed")
            elif os.path.isdir(path):
                projects.append(name)
            elif name == "developer.json":
                info = read_json(path, errors, f"{shown}/developer.json")
            else:
                errors.append(f"{shown}/{name}: only developer.json and project folders belong here")
        if not os.path.isfile(os.path.join(folder, "developer.json")):
            errors.append(f"{shown}: developer.json is missing")
        elif info is not None:
            unknown = set(info) - {"github"}
            if unknown:
                errors.append(f"{shown}/developer.json: unknown fields: {', '.join(sorted(unknown))}")
            login = info.get("github")
            if not isinstance(login, str) or GITHUB_LOGIN.match(login) is None:
                errors.append(f"{shown}/developer.json: github must be your GitHub login")
        if len(projects) > MAX_PROJECTS:
            errors.append(f"{shown}: up to {MAX_PROJECTS} mods for one developer")
        for project in projects:
            mod = check_project(root, developer, project, seen_ids, errors, luac)
            if mod:
                mods.append(mod)
    return errors, mods


def files_of(root):
    out = {}
    for folder, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in names + [d for d in dirs if os.path.islink(os.path.join(folder, d))]:
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            if os.path.islink(path):
                out[rel] = b"link:" + os.readlink(path).encode()
            else:
                with open(path, "rb") as f:
                    out[rel] = f.read()
    return out


def developer_login(root, developer):
    path = os.path.join(root, "mods", developer, "developer.json")
    try:
        with open(path, encoding="utf-8") as f:
            login = json.load(f).get("github")
    except (OSError, ValueError, AttributeError):
        return None
    return login if isinstance(login, str) else None


def mod_version(root, developer, project):
    path = os.path.join(root, "mods", developer, project, "mod.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("version")
    except (OSError, ValueError, AttributeError):
        return None


def changed_paths(base, tree):
    old = files_of(base)
    new = files_of(tree)
    return sorted(p for p in set(old) | set(new) if old.get(p) != new.get(p))


def banned_logins(base):
    try:
        with open(os.path.join(base, "banned.txt"), encoding="utf-8") as f:
            return {line.strip().lower() for line in f if line.strip() and not line.startswith("#")}
    except OSError:
        return set()


def can_merge_alone(base, tree):
    """Only mods changed: such a pull request needs no person once its check has passed."""
    changed = changed_paths(base, tree)
    return bool(changed) and all(p.startswith("mods/") for p in changed)


def validate_change(base, tree, author, owner):
    """What a pull request may touch: only its author's own developer folder."""
    errors = []
    if author.lower() == owner.lower():
        return errors
    if author.lower() in banned_logins(base):
        return [f"{author}: this login may not add mods"]
    changed = changed_paths(base, tree)
    developers = set()
    for path in changed:
        parts = path.split("/")
        if parts[0] != "mods" or len(parts) < 3:
            errors.append(f"{path}: a pull request may only change mods/<developer>/")
        else:
            developers.add(parts[1])
    for developer in sorted(developers):
        had = developer_login(base, developer)
        has = developer_login(tree, developer)
        if had is not None and had.lower() != author.lower():
            errors.append(f"mods/{developer}: this folder belongs to {had}")
        elif had is None and has is not None and has.lower() != author.lower():
            errors.append(f"mods/{developer}/developer.json: github must be your login, {author}")
        if had is None:
            if developer.lower() in RESERVED_DEVELOPERS:
                errors.append(f"mods/{developer}: this name is reserved")
            base_mods = os.path.join(base, "mods")
            names = os.listdir(base_mods) if os.path.isdir(base_mods) else []
            for other in sorted(names):
                login = developer_login(base, other)
                if login is not None and login.lower() == author.lower():
                    errors.append(f"mods/{developer}: you already have the folder mods/{other}")
    for path in changed:
        parts = path.split("/")
        if len(parts) == 4 and parts[0] == "mods" and parts[3] in ("main.lua", "main.json"):
            before = mod_version(base, parts[1], parts[2])
            existed = os.path.isfile(os.path.join(base, path))
            exists = os.path.isfile(os.path.join(tree, path))
            if existed and exists and before == mod_version(tree, parts[1], parts[2]):
                errors.append(f"mods/{parts[1]}/{parts[2]}: the file changed, raise version in mod.json")
    return errors
