"""python tools/test_check.py"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modlib  # noqa: E402
import publish  # noqa: E402

LUAC = shutil.which("luac5.4") or shutil.which("luac")


def write(root, path, content):
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    mode = "wb" if isinstance(content, bytes) else "w"
    with open(full, mode, **({} if mode == "wb" else {"encoding": "utf-8", "newline": "\n"})) as f:
        f.write(content if isinstance(content, (bytes, str)) else json.dumps(content))


MOD = {
    "kind": "script",
    "name": "Scene timer",
    "version": "1.0",
    "license": "MIT",
    "description": {"en": "Switches scenes", "ru": "Меняет сцены"},
}
DEVELOPER = {"github": "anna-gh"}


def add_developer(root, name="anna", developer=None):
    write(root, f"mods/{name}/developer.json", developer or DEVELOPER)


def add_script(root, developer="anna", project="timer", mod=None, source="-- efirra: scenes\n"):
    write(root, f"mods/{developer}/{project}/mod.json", mod or MOD)
    write(root, f"mods/{developer}/{project}/main.lua", source)


class Case(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        self.other = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.other)

    def errors(self, root=None):
        return modlib.validate_tree(root or self.root, luac=LUAC)[0]

    def assert_problem(self, needle, errors=None):
        errors = self.errors() if errors is None else errors
        self.assertTrue(any(needle in e for e in errors), f"{needle!r} not in {errors}")


class Tree(Case):
    def test_a_good_script_passes(self):
        add_developer(self.root)
        add_script(self.root)
        errors, mods = modlib.validate_tree(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(mods[0]["id"], "anna-timer")
        self.assertEqual(mods[0]["author"], "anna")

    def test_a_good_language_passes(self):
        add_developer(self.root)
        write(self.root, "mods/anna/german/mod.json", {**MOD, "kind": "language", "code": "de"})
        write(self.root, "mods/anna/german/main.json", {"language.de": "Deutsch", "a": "b"})
        errors, mods = modlib.validate_tree(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(mods[0]["id"], "de")

    def test_an_empty_list_passes(self):
        write(self.root, "mods/.gitkeep", "")
        self.assertEqual(modlib.validate_tree(self.root), ([], []))

    def test_a_contact_is_not_needed(self):
        add_developer(self.root, developer={"github": "anna-gh"})
        self.assertEqual(self.errors(), [])

    def test_unknown_developer_fields_are_refused(self):
        add_developer(self.root, developer={"github": "anna-gh", "contact": {"email": "a@b.de"}})
        self.assert_problem("unknown fields")

    def test_github_login_is_required(self):
        add_developer(self.root, developer={"name": "anna"})
        self.assert_problem("github must be")

    def test_too_many_mods_for_one_developer(self):
        add_developer(self.root)
        for i in range(modlib.MAX_PROJECTS + 1):
            add_script(self.root, project=f"mod{i}")
        self.assert_problem("up to")

    def test_developer_file_is_required(self):
        add_script(self.root)
        self.assert_problem("developer.json is missing")

    def test_bad_folder_names(self):
        for name in ["Anna", "a", "bad_name", "1abc", "ends-"]:
            root = tempfile.mkdtemp()
            self.addCleanup(shutil.rmtree, root)
            add_developer(root, name)
            self.assert_problem("folder name", self.errors(root))
        # такую папку в Windows не создать, а на сервере можно
        self.assertFalse(modlib.good_slug("con", 19))

    def test_foreign_files_are_refused(self):
        add_developer(self.root)
        add_script(self.root)
        for name in ["plugin.dll", "run.exe", "page.html", "more.lua"]:
            write(self.root, f"mods/anna/timer/{name}", b"x")
        self.assert_problem("plugin.dll: file not allowed")
        self.assert_problem("run.exe: file not allowed")
        self.assert_problem("more.lua: file not allowed")

    def test_files_next_to_projects_are_refused(self):
        add_developer(self.root)
        write(self.root, "mods/anna/virus.dll", b"x")
        self.assert_problem("only developer.json")

    def test_nested_folders_are_refused(self):
        add_developer(self.root)
        add_script(self.root)
        write(self.root, "mods/anna/timer/deep/main.lua", "x")
        self.assert_problem("no other folders")

    def test_compiled_lua_is_refused(self):
        add_developer(self.root)
        add_script(self.root, source=b"\x1bLuaT\x00")
        self.assert_problem("compiled Lua")

    def test_binary_is_refused(self):
        add_developer(self.root)
        add_script(self.root, source=b"\xff\xfe\x00")
        self.assert_problem("UTF-8")

    def test_size_limit(self):
        add_developer(self.root)
        add_script(self.root, source=b"-" * (modlib.MAX_FILE + 1))
        self.assert_problem("size")
        add_script(self.root, source=b"")
        self.assert_problem("size")

    @unittest.skipUnless(LUAC, "no luac here")
    def test_lua_syntax_is_checked(self):
        add_developer(self.root)
        add_script(self.root, source="this is not lua (")
        self.assertTrue(self.errors())

    def test_required_fields(self):
        add_developer(self.root)
        for field, value, needle in [
            ("name", "", "name"),
            ("name", "x\ny", "name"),
            ("version", "latest", "version"),
            ("license", "", "license"),
            ("description", {"ru": "только русский"}, "description"),
            ("kind", "plugin", "kind"),
            ("extra", 1, "unknown fields"),
        ]:
            add_script(self.root, mod={**MOD, field: value})
            self.assert_problem(needle)

    def test_builtin_language_is_refused(self):
        add_developer(self.root)
        write(self.root, "mods/anna/rus/mod.json", {**MOD, "kind": "language", "code": "RU"})
        write(self.root, "mods/anna/rus/main.json", {"language.RU": "x"})
        self.assert_problem("language code")

    def test_a_language_code_has_one_owner(self):
        for name, login in [("anna", "anna-gh"), ("bern", "bern-gh")]:
            add_developer(self.root, name, {"github": login})
        for name, code in [("anna", "de"), ("bern", "DE")]:
            write(self.root, f"mods/{name}/german/mod.json", {**MOD, "kind": "language", "code": code})
            write(self.root, f"mods/{name}/german/main.json", {f"language.{code}": "Deutsch"})
        self.assert_problem("already taken")

    @unittest.skipIf(os.name == "nt", "links need rights on Windows")
    def test_links_are_refused(self):
        add_developer(self.root)
        add_script(self.root)
        os.symlink("/etc/passwd", os.path.join(self.root, "mods/anna/timer/README.md"))
        self.assert_problem("no folders or links")


def alert_bytes(files=(("a.png", b"png"),), path="file:0", kind=None):
    import json as _json
    kind = kind or {"type": "alert", "layers": [{"id": 1, "type": "media", "path": path, "x": 0, "y": 0, "w": 1, "h": 1}]}
    header = _json.dumps({"name": "A", "kind": kind, "files": [{"name": n, "size": len(b)} for n, b in files]}).encode()
    return b"EFIRRA-ALERT 1\n" + str(len(header)).encode() + b"\n" + header + b"".join(b for _, b in files)


class Kinds(Case):
    def add(self, kind, main, content):
        add_developer(self.root)
        write(self.root, "mods/anna/thing/mod.json", dict(MOD, kind=kind))
        write(self.root, f"mods/anna/thing/{main}", content)

    def test_a_good_theme_passes(self):
        self.add("theme", "theme.json", {"accent": "#4fd08a", "controls": "#ffffff", "warm": "#f2b872",
                                         "panels": "#121d19", "background": "#0a1210", "text": "#e8f3ed", "radius": 12})
        errors, mods = modlib.validate_tree(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(mods[0]["kind"], "theme")
        self.assertTrue(mods[0]["main"].endswith("theme.json"))

    def test_a_theme_with_a_bad_color_is_refused(self):
        self.add("theme", "theme.json", {"accent": "red", "controls": "#ffffff", "warm": "#f2b872",
                                         "panels": "#121d19", "background": "#0a1210", "text": "#e8f3ed", "radius": 12})
        self.assert_problem("colors look like")

    def test_a_good_panel_passes(self):
        self.add("panel", "panel.html", "<!doctype html><html><body>hi</body></html>")
        self.assertEqual(self.errors(), [])

    def test_a_panel_must_be_a_page(self):
        self.add("panel", "panel.html", "just text")
        self.assert_problem("must be an HTML page")

    def test_a_good_alert_passes(self):
        self.add("alert", "alert.efirra-alert", alert_bytes())
        self.assertEqual(self.errors(), [])

    def test_an_alert_with_a_program_inside_is_refused(self):
        self.add("alert", "alert.efirra-alert", alert_bytes(files=(("virus.exe", b"MZ"),)))
        self.assert_problem("only pictures, clips and sounds")

    def test_an_alert_pointing_outside_is_refused(self):
        self.add("alert", "alert.efirra-alert", alert_bytes(path="C:/Windows/win.ini"))
        self.assert_problem("must be a file inside the alert")

    def test_a_cut_alert_is_refused(self):
        self.add("alert", "alert.efirra-alert", alert_bytes()[:-1])
        self.assert_problem("file sizes do not match")

    def test_a_kind_uses_only_its_own_main_file(self):
        self.add("theme", "theme.json", "{}")
        write(self.root, "mods/anna/thing/main.lua", "-- x")
        self.assert_problem("a theme uses theme.json")


class Change(Case):
    """self.other is the current repository, self.root is the pull request."""

    def change(self, author="anna-gh"):
        changed = modlib.changed_paths(self.other, self.root)
        return modlib.validate_change(self.other, self.root, author, "Baamich", changed)

    def test_a_new_developer_passes(self):
        write(self.other, "README.md", "x")
        write(self.root, "README.md", "x")
        add_developer(self.root)
        add_script(self.root)
        self.assertEqual(self.change(), [])

    def test_only_mods_may_change(self):
        write(self.other, "catalog.json", "good")
        write(self.root, "catalog.json", "evil")
        write(self.root, ".github/workflows/x.yml", "evil")
        write(self.root, "tools/check.py", "evil")
        # the green check is the owner's word: nobody else may give it
        write(self.root, "verified.json", {"mods": {"x": {"version": "1", "sha256": "0" * 64}}})
        write(self.root, "revoked.json", {"revoked": [{"sha256": "0" * 64}]})
        errors = self.change()
        for path in ["catalog.json", ".github/workflows/x.yml", "tools/check.py", "verified.json", "revoked.json"]:
            self.assert_problem(path, errors)

    def test_another_developers_folder_is_closed(self):
        add_developer(self.other)
        add_script(self.other)
        add_developer(self.root)
        add_script(self.root, source="-- evil\n", mod={**MOD, "version": "2.0"})
        self.assert_problem("belongs to anna-gh", self.change("mallory"))

    def test_login_case_does_not_matter(self):
        add_developer(self.other)
        add_script(self.other)
        add_developer(self.root)
        add_script(self.root, source="-- new\n", mod={**MOD, "version": "2.0"})
        self.assertEqual(self.change("ANNA-GH"), [])

    def test_a_new_folder_must_name_its_author(self):
        add_developer(self.root)
        self.assert_problem("must be your login", self.change("mallory"))

    def test_one_login_has_one_folder(self):
        add_developer(self.other)
        add_developer(self.root)
        add_developer(self.root, "anna2")
        self.assert_problem("already have the folder", self.change())

    def test_a_changed_file_needs_a_new_version(self):
        add_developer(self.other)
        add_script(self.other)
        add_developer(self.root)
        add_script(self.root, source="-- changed\n")
        self.assert_problem("raise version", self.change())

    def test_a_banned_login_is_refused(self):
        write(self.other, "banned.txt", "# removed for piracy\nMallory\n")
        add_developer(self.root, developer={"github": "mallory"})
        self.assert_problem("may not add mods", self.change("mallory"))

    def test_reserved_names_are_closed(self):
        add_developer(self.root, "efirra")
        self.assert_problem("reserved", self.change())
        self.assertEqual(self.change("baamich"), [])

    def test_only_a_mods_change_merges_alone(self):
        self.assertFalse(modlib.can_merge_alone([]))
        self.assertTrue(modlib.can_merge_alone(["mods/anna/developer.json"]))
        self.assertFalse(modlib.can_merge_alone(["mods/anna/developer.json", "tools/check.py"]))
        self.assertFalse(modlib.can_merge_alone(["catalog.json"]))

    def test_main_moving_on_is_not_the_authors_change(self):
        write(self.other, "catalog.json", "newer list")
        add_developer(self.root)
        changed = ["mods/anna/developer.json"]
        self.assertEqual(modlib.validate_change(self.other, self.root, "anna-gh", "Baamich", changed), [])

    def test_the_owner_may_change_anything(self):
        write(self.root, "tools/check.py", "new")
        add_developer(self.other)
        add_developer(self.root, developer={"github": "other"})
        self.assertEqual(self.change("baamich"), [])


class Screenshots(Case):
    PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32
    JPG = b"\xff\xd8\xff\xe0" + b"\0" * 32

    def test_screenshots_are_listed_by_number(self):
        add_developer(self.root)
        add_script(self.root)
        write(self.root, "mods/anna/timer/screenshots/10.png", self.PNG)
        write(self.root, "mods/anna/timer/screenshots/2.jpg", self.JPG)
        write(self.root, "mods/anna/timer/screenshots/1.png", self.PNG)
        errors, mods = modlib.validate_tree(self.root)
        self.assertEqual(errors, [])
        self.assertEqual([p.rsplit("/", 1)[1] for p in mods[0]["screenshots"]], ["1.png", "2.jpg", "10.png"])

    def test_bad_screenshots_are_refused(self):
        add_developer(self.root)
        add_script(self.root)
        write(self.root, "mods/anna/timer/screenshots/1.png", self.JPG)
        write(self.root, "mods/anna/timer/screenshots/shot.png", self.PNG)
        write(self.root, "mods/anna/timer/screenshots/2.png", self.PNG)
        write(self.root, "mods/anna/timer/screenshots/2.webp", self.PNG)
        write(self.root, "mods/anna/timer/screenshots/3.exe", b"MZ")
        errors = self.errors()
        self.assert_problem("1.png: this is not a PNG picture", errors)
        self.assert_problem("shot.png: name a screenshot by its number", errors)
        self.assert_problem("2.webp: there is already a screenshot number 2", errors)
        self.assert_problem("3.exe: name a screenshot by its number", errors)

    def test_too_many_or_too_big_screenshots_are_refused(self):
        add_developer(self.root)
        add_script(self.root)
        for n in range(1, 10):
            write(self.root, f"mods/anna/timer/screenshots/{n}.png", self.PNG)
        self.assert_problem("up to 8 screenshots")
        write(self.root, "mods/anna/timer/screenshots/1.png", self.PNG + b"\0" * modlib.MAX_SCREENSHOT)
        self.assert_problem("a screenshot is up to 2 MB")

    def test_other_folders_are_still_refused(self):
        add_developer(self.root)
        add_script(self.root)
        write(self.root, "mods/anna/timer/images/1.png", self.PNG)
        self.assert_problem("images: only plain files and a screenshots folder")


class Official(Case):
    def change(self, author):
        changed = modlib.changed_paths(self.other, self.root)
        return modlib.validate_change(self.other, self.root, author, "Baamich", changed)

    def test_official_mods_belong_to_the_owner(self):
        add_developer(self.root, "official", {"github": "Baamich"})
        add_script(self.root, "official", "timer")
        errors, mods = modlib.validate_tree(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(mods[0]["id"], "official-timer")
        # чужой логин в официальной папке — ошибка в любом случае
        add_developer(self.root, "official", {"github": "anna-gh"})
        self.assert_problem("official mods belong to Baamich")

    def test_nobody_else_may_touch_official(self):
        add_developer(self.other, "official", {"github": "Baamich"})
        add_script(self.other, "official", "timer")
        add_developer(self.root, "official", {"github": "Baamich"})
        add_script(self.root, "official", "timer", source="-- efirra: scenes\n-- changed\n")
        errors = self.change("anna-gh")
        self.assertTrue(any("only Baamich may change official mods" in e for e in errors), errors)
        self.assertEqual(self.change("Baamich"), [])

    def test_a_changed_theme_needs_a_new_version(self):
        add_developer(self.other, "anna", DEVELOPER)
        write(self.other, "mods/anna/sky/mod.json", {**MOD, "kind": "theme"})
        write(self.other, "mods/anna/sky/theme.json", {"accent": "#ff0000"})
        add_developer(self.root, "anna", DEVELOPER)
        write(self.root, "mods/anna/sky/mod.json", {**MOD, "kind": "theme"})
        write(self.root, "mods/anna/sky/theme.json", {"accent": "#00ff00"})
        errors = self.change("anna-gh")
        self.assertTrue(any("raise version" in e for e in errors), errors)


class Publish(unittest.TestCase):
    def mod(self, data=b"-- script", version="1.0"):
        return {
            "id": "anna-timer", "kind": "script", "name": "Timer", "author": "anna", "version": version,
            "license": "MIT", "description": {"en": "x"}, "main": "mods/anna/timer/main.lua",
            "homepage": "mods/anna/timer", "data": data,
        }

    def test_a_new_mod_gets_a_release_and_a_file(self):
        entries, create, upload, stale = publish.plan([self.mod()], [])
        self.assertEqual(create, [("mod-anna-timer", "Timer")])
        self.assertEqual(len(upload), 1)
        self.assertEqual(stale, [])
        entry = entries[0]
        self.assertEqual(entry["installs"], 0)
        self.assertEqual(entry["size"], 9)
        self.assertNotIn("data", entry)
        self.assertTrue(entry["url"].startswith(
            "https://github.com/Baamich/Efirra-mods/releases/download/mod-anna-timer/anna-timer-1.0-"))
        self.assertTrue(entry["url"].endswith(".lua"))

    def test_screenshots_go_to_the_release_and_do_not_count_as_installs(self):
        mod = self.mod()
        mod["shots"] = [{"data": b"one", "extension": ".png"}, {"data": b"two", "extension": ".webp"}]
        entries, create, upload, stale = publish.plan([mod], [])
        names = [u[1] for u in upload]
        self.assertEqual(len(names), 3)
        self.assertTrue(names[1].startswith("shot-anna-timer-1-") and names[1].endswith(".png"))
        shots = entries[0]["screenshots"]
        self.assertEqual([s["size"] for s in shots], [3, 3])
        self.assertTrue(shots[1]["url"].endswith(names[2]))
        releases = [{"tag_name": "mod-anna-timer", "assets": [
            {"name": n, "download_count": 7} for n in names
        ]}]
        entries, create, upload, stale = publish.plan([mod], releases)
        self.assertEqual(entries[0]["installs"], 7, "screenshot downloads are not installs")
        self.assertEqual(upload, [])

    def test_official_mods_are_always_checked(self):
        mod = {**self.mod(), "id": "official-timer", "author": "official"}
        entry = publish.plan([mod], [])[0][0]
        self.assertTrue(entry["verified"] and entry["official"])
        self.assertFalse(publish.plan([self.mod()], [])[0][0]["official"])

    def test_installs_add_up_across_versions(self):
        first = publish.plan([self.mod()], [])[2][0][1]
        releases = [{"tag_name": "mod-anna-timer", "assets": [
            {"name": first, "download_count": 40}, {"name": "older.lua", "download_count": 2},
        ]}]
        entries, create, upload, stale = publish.plan([self.mod()], releases)
        self.assertEqual(entries[0]["installs"], 42)
        self.assertEqual((create, upload, stale), ([], [], []))

    def test_changed_bytes_are_a_new_file(self):
        first = publish.plan([self.mod()], [])[2][0][1]
        releases = [{"tag_name": "mod-anna-timer", "assets": [{"name": first, "download_count": 1}]}]
        entries, create, upload, stale = publish.plan([self.mod(b"-- changed")], releases)
        self.assertEqual(create, [])
        self.assertEqual(len(upload), 1)
        self.assertNotEqual(upload[0][1], first)
        self.assertEqual(entries[0]["installs"], 1)

    def test_the_owners_mark_holds_only_for_the_checked_file(self):
        import hashlib
        sha = hashlib.sha256(b"-- script").hexdigest()
        marks = {"anna-timer": {"version": "1.0", "sha256": sha}}
        self.assertTrue(publish.plan([self.mod()], [], verified=marks)[0][0]["verified"])
        self.assertFalse(publish.plan([self.mod(b"-- changed", "1.1")], [], verified=marks)[0][0]["verified"])
        self.assertFalse(publish.plan([self.mod()], [])[0][0]["verified"])

    def test_a_broken_marks_file_marks_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, "verified.json", "{not json")
            self.assertEqual(modlib.read_verified(root), {})
            write(root, "verified.json", {"mods": {"a": {"version": "1", "sha256": "short"}, "b": "x"}})
            self.assertEqual(modlib.read_verified(root), {})

    def test_revoked_prints_are_read(self):
        with tempfile.TemporaryDirectory() as root:
            good = "ab" * 32
            write(root, "revoked.json", {"revoked": [{"sha256": good.upper(), "reason": "x"}, {"sha256": "short"}, "bad"]})
            self.assertEqual(modlib.read_revoked(root), [good])
            write(root, "revoked.json", "{broken")
            self.assertEqual(modlib.read_revoked(root), [])

    def test_a_revocation_can_be_taken_back(self):
        import revoke
        with tempfile.TemporaryDirectory() as root:
            old = revoke.FILE
            revoke.FILE = os.path.join(root, "revoked.json")
            try:
                sha = "cd" * 32
                self.assertEqual(revoke.main(["--sha", sha, "test"]), 0)
                self.assertEqual(modlib.read_revoked(root), [sha])
                self.assertEqual(revoke.main(["--undo", "nobody"]), 1)
                self.assertEqual(revoke.main(["--undo", sha]), 0)
                self.assertEqual(modlib.read_revoked(root), [])
            finally:
                revoke.FILE = old

    def test_a_removed_mod_loses_its_release_and_others_stay(self):
        releases = [{"tag_name": "mod-gone", "assets": []}, {"tag_name": "v1.0", "assets": []}]
        self.assertEqual(publish.plan([], releases)[3], ["mod-gone"])


if __name__ == "__main__":
    unittest.main()
