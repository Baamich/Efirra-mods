"""python tools/test_check.py"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modlib  # noqa: E402

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


def add_script(root, developer="anna", project="timer", mod=None, source="-- sielo: scenes\n"):
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
        self.assert_problem("no folders")

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


class Change(Case):
    """self.other is the current repository, self.root is the pull request."""

    def change(self, author="anna-gh"):
        return modlib.validate_change(self.other, self.root, author, "Baamich")

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
        errors = self.change()
        for path in ["catalog.json", ".github/workflows/x.yml", "tools/check.py"]:
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
        add_developer(self.root, "sielo")
        self.assert_problem("reserved", self.change())
        self.assertEqual(self.change("baamich"), [])

    def test_only_a_mods_change_merges_alone(self):
        write(self.other, "README.md", "x")
        write(self.root, "README.md", "x")
        self.assertFalse(modlib.can_merge_alone(self.other, self.root))
        add_developer(self.root)
        self.assertTrue(modlib.can_merge_alone(self.other, self.root))
        write(self.root, "tools/check.py", "new")
        self.assertFalse(modlib.can_merge_alone(self.other, self.root))

    def test_the_owner_may_change_anything(self):
        write(self.root, "tools/check.py", "new")
        add_developer(self.other)
        add_developer(self.root, developer={"github": "other"})
        self.assertEqual(self.change("baamich"), [])


if __name__ == "__main__":
    unittest.main()
