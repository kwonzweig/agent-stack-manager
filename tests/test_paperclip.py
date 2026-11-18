from copy import deepcopy
from io import BytesIO
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import yaml

from asm_app import paperclip
from asm_app.store import Store, _export_digest


ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/example/preset-tools"
PATH = "skills/check/SKILL.md"

PACKAGE = {
    "id": "test-preset",
    "title": "Test Preset",
    "description": "Exercise the Paperclip export.",
    "instruction": "Check the app.",
    "revision": "rev-1",
    "files": [{"path": "apm.yml", "content": "name: test-preset\n"}],
    "components": [
        {"id": "instruction", "name": "Instruction", "kind": "instruction"},
        {"id": "check", "name": "check", "kind": "skill", "description": "Check the app.",
         "source": {"repositoryUrl": REPO, "path": PATH, "ref": "main"}},
        {"id": "playwright", "name": "Playwright", "kind": "mcp",
         "configuration": {"name": "playwright", "transport": "stdio", "registry": False,
                           "command": "npx", "args": ["@playwright/mcp@latest"]}},
        {"id": "stop", "name": "Stop", "kind": "hook"},
        {"id": "design", "name": "Design", "kind": "plugin"},
    ],
}


def by_id(report):
    return {item["id"]: item for item in report["items"]}


def written(report):
    return {entry["path"]: entry["content"] for entry in report["files"]}


def frontmatter(text):
    _, header, body = text.split("---", 2)
    return yaml.safe_load(header), body.strip()


def agent(report, slug="test-preset"):
    files = written(report)
    front, body = frontmatter(files[f"agents/{slug}/AGENTS.md"])
    return front, body, yaml.safe_load(files[".paperclip.yaml"])["agents"][slug]


def skill(component_id, repository, path, ref="main", name=None):
    return {"id": component_id, "name": name or component_id, "kind": "skill", "description": f"{component_id}.",
            "source": {"repositoryUrl": repository, "path": path, "ref": ref}}


class PaperclipTests(unittest.TestCase):
    def setUp(self):
        self.package = deepcopy(PACKAGE)

    def convert(self, package=None, root=ROOT):
        return paperclip.convert(package or self.package, root=root)

    def test_written_files_are_the_package_and_one_stub_per_skill(self):
        self.assertEqual(set(written(self.convert())), {
            "COMPANY.md", ".paperclip.yaml", "agents/test-preset/AGENTS.md", "skills/check/SKILL.md"})

    def test_slug_is_the_package_id_not_the_title(self):
        self.package.update(id="ar", title="AI Resources")
        report = self.convert()
        self.assertIn("agents/ar/AGENTS.md", written(report))
        front, _, _ = agent(report, "ar")
        self.assertEqual((front["slug"], front["name"], front["title"]), ("ar", "AI Resources", "AI Resources"))
        self.assertEqual(list(yaml.safe_load(written(report)[".paperclip.yaml"])["agents"]), ["ar"])

    def test_company_has_the_required_fields(self):
        company, _ = frontmatter(written(self.convert())["COMPANY.md"])
        self.assertEqual((company["schema"], company["kind"], company["slug"]),
                         ("agentcompanies/v1", "company", "test-preset"))
        self.assertTrue(company["name"])
        self.assertTrue(company["description"])

    def test_agent_lists_its_skills_and_no_manager(self):
        front, body, _ = agent(self.convert())
        self.assertEqual(body, "Check the app.")
        self.assertEqual(front["kind"], "agent")
        self.assertEqual(front["skills"], ["check"])
        self.assertNotIn("reportsTo", front)
        self.assertEqual(front["role"], "general")

    def test_stub_follows_a_branch_and_names_no_commit(self):
        stub, body = frontmatter(written(self.convert())["skills/check/SKILL.md"])
        url = f"{REPO}/tree/main/skills/check"
        self.assertEqual(stub, {"key": "check", "name": "check", "description": "Check the app.", "metadata": {
            "sources": [{"kind": "github-dir", "repo": "example/preset-tools", "path": "skills/check",
                         "trackingRef": "main", "url": url}]}})
        self.assertEqual(body, f"Imported from {url}.")
        row = by_id(self.convert())["check"]
        self.assertEqual(row["target"], "skills/check/SKILL.md")
        self.assertEqual(row["conversion"], {"status": "converted",
                                             "reason": "Skill exported as skills/check, following main."})

    def test_nested_skill_path_drops_the_skill_file(self):
        self.package["components"][1] = skill("start-core", "https://github.com/TanStack/router",
                                               "packages/start-client-core/skills/start-core/SKILL.md")
        stub, _ = frontmatter(written(self.convert())["skills/start-core/SKILL.md"])
        self.assertEqual(stub["metadata"]["sources"][0]["path"], "packages/start-client-core/skills/start-core")

    def test_repo_root_skill_has_an_explicit_dot_path(self):
        self.package["components"][1] = skill("humanizer", "https://github.com/blader/humanizer", "SKILL.md",
                                               name="Humanizer")
        report = self.convert()
        stub, _ = frontmatter(written(report)["skills/humanizer/SKILL.md"])
        self.assertEqual(stub["metadata"]["sources"][0]["path"], ".")
        self.assertEqual(stub["metadata"]["sources"][0]["url"], "https://github.com/blader/humanizer/tree/main")
        self.assertEqual(agent(report)[0]["skills"], ["humanizer"])

    def test_skill_without_a_branch_needs_attention(self):
        for ref in ("", "HEAD", None):
            with self.subTest(ref=ref):
                source = {"repositoryUrl": REPO, "path": PATH}
                if ref is not None:
                    source["ref"] = ref
                self.package["components"][1]["source"] = source
                report = self.convert()
                self.assertEqual(by_id(report)["check"]["conversion"],
                                 {"status": "unconverted", "reason": "Name the branch this skill follows."})
                self.assertNotIn("skills/check/SKILL.md", written(report))
                self.assertEqual(agent(report)[0]["skills"], [])

    def test_skill_outside_github_needs_attention(self):
        self.package["components"][1]["source"]["repositoryUrl"] = "https://gitlab.com/example/preset-tools"
        conversion = by_id(self.convert())["check"]["conversion"]
        self.assertEqual(conversion, {"status": "unconverted", "reason": "Paperclip imports skills from GitHub only."})

    def test_skills_with_the_same_folder_name_get_distinct_keys(self):
        self.package["components"].append(skill("check:2", "https://github.com/other/kit", "skills/check/SKILL.md",
                                                name="check"))
        report = self.convert()
        self.assertEqual(agent(report)[0]["skills"], ["preset-tools-check", "kit-check"])
        self.assertIn("skills/kit-check/SKILL.md", written(report))
        self.assertEqual(written(report), written(self.convert()))

    def test_the_same_skill_twice_gives_one_stub(self):
        self.package["components"].append({**deepcopy(self.package["components"][1]), "id": "check-again"})
        report = self.convert()
        self.assertEqual(agent(report)[0]["skills"], ["check"])
        self.assertEqual(by_id(report)["check-again"]["target"], "skills/check/SKILL.md")

    def test_paperclip_settings_carry_the_package_and_its_revision_only(self):
        _, _, extension = agent(self.convert())
        self.assertEqual(set(extension), {"role", "runtime", "metadata"})
        self.assertEqual(extension["role"], "general")
        self.assertEqual(extension["runtime"], {"heartbeat": {"enabled": False}})
        self.assertEqual(set(extension["metadata"]), {"agentStackManagerPackageId", "agentStackManagerRevision"})
        self.assertEqual(extension["metadata"]["agentStackManagerPackageId"], "test-preset")
        self.assertRegex(extension["metadata"]["agentStackManagerRevision"], r"^[0-9a-f]{64}$")
        self.assertEqual(yaml.safe_load(written(self.convert())[".paperclip.yaml"])["schemaVersion"], 7)

    def test_mcp_is_left_for_the_adapter(self):
        conversion = by_id(self.convert())["playwright"]["conversion"]
        self.assertEqual(conversion, {
            "status": "unconverted", "cause": "adapter",
            "reason": "Paperclip's company package has no MCP entry; set it in the agent's adapter after import."})

    def test_hook_and_plugin_are_not_in_paperclips_format(self):
        items = by_id(self.convert())
        for item_id, kind in (("stop", "hook"), ("design", "plugin")):
            self.assertEqual(items[item_id]["conversion"], {
                "status": "unconverted", "cause": "not-in-format",
                "reason": f"Paperclip's company package has no {kind} entry."})
        self.assertNotIn("cause", items["check"]["conversion"])

    def test_additional_apm_instruction_is_reported_unconverted(self):
        self.package["components"].append({"id": "instructions:style", "name": "Style",
                                           "kind": "instruction", "configuration": "Use plain text."})
        items = by_id(self.convert())
        self.assertEqual(items["instruction"]["conversion"],
                         {"status": "converted", "reason": "Instruction exported as AGENTS.md."})
        self.assertEqual(items["instructions:style"]["conversion"], {
            "status": "unconverted",
            "reason": "Paperclip takes one Instruction per agent; merge it into the Instruction."})

    def test_report_targets_name_written_files(self):
        report = self.convert()
        targets = [row["target"] for row in report["items"] if isinstance(row["target"], str)]
        self.assertEqual(targets, ["agents/test-preset/AGENTS.md", "skills/check/SKILL.md"])
        self.assertTrue(set(targets) <= set(written(report)))

    def test_report_holds_the_conversion_alone(self):
        report = self.convert()
        self.assertEqual(set(report), {"consumer", "items", "summary", "files", "folder"})
        for row in report["items"]:
            self.assertEqual(set(row), {"id", "name", "kind", "supportKind", "source", "target", "conversion"})
        self.assertEqual(report["summary"], {"total": 5, "converted": 2, "unconverted": 3})

    def test_each_row_names_its_support_table_row(self):
        manifest = "https://github.com/example/plugins/blob/main/plugins/{}/{}/plugin.json"
        self.package["components"][4]["sourceUrl"] = manifest.format("design", ".claude-plugin")
        self.package["components"] += [
            {"id": "codex-tool", "name": "Codex tool", "kind": "plugin",
             "source": {"repositoryUrl": "https://github.com/example/plugins", "path": "tool/.codex-plugin/plugin.json"}},
            {"id": "plain", "name": "Plain", "kind": "plugin", "configuration": {"name": "plain", "marketplace": "x"}},
            {"id": "both", "name": "Both", "kind": "plugin", "file": ".apm/plugins/both/.claude-plugin/plugin.json",
             "sourceUrl": manifest.format("both", ".codex-plugin")},
        ]
        kinds = {row["id"]: row["supportKind"] for row in self.convert()["items"]}
        self.assertEqual(kinds, {"instruction": "instruction", "check": "skill", "playwright": "mcp", "stop": "hook",
                                 "design": "claude-code-plugin", "codex-tool": "codex-plugin",
                                 "plain": None, "both": None})

    def test_a_frontend_design_member_is_a_claude_code_plugin(self):
        store = Store(ROOT)
        report = self.convert(store.get("web-app-engineer"))
        row = next(row for row in report["items"] if row["name"] == "frontend-design")
        self.assertEqual(row["supportKind"], "claude-code-plugin")

    def test_report_names_the_committed_export_folder(self):
        self.assertEqual(self.convert()["folder"], {
            "path": "exports/paperclip/test-preset",
            "url": "https://github.com/kwonzweig/agent-stack-manager/tree/main/exports/paperclip/test-preset"})
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.convert(root=Path(directory))["folder"],
                             {"path": "exports/paperclip/test-preset", "url": None})
        self.package["kind"] = "stack"
        self.assertIsNone(self.convert()["folder"])

    def test_stack_members_expand_and_cycles_are_reported(self):
        self.package["components"] = [{"id": "instruction", "name": "Instruction", "kind": "instruction"},
                                      {"id": "package:web", "name": "Web", "kind": "package",
                                       "configuration": {"packageId": "web"}}]
        child = {"id": "web", "revision": "nested-1", "instruction": "", "files": [], "components": [
            {"id": "instruction", "name": "Instruction", "kind": "instruction"},
            deepcopy(PACKAGE["components"][1]),
            deepcopy(self.package["components"][1]),
        ]}
        with patch.object(Store, "get", return_value=child):
            report = self.convert()
        self.assertEqual(by_id(report)["check"]["conversion"]["status"], "converted")
        self.assertEqual(by_id(report)["package:web"]["conversion"]["reason"], "Stack members exported.")
        self.assertEqual(sum("cycle" in row["conversion"]["reason"].lower() for row in report["items"]), 1)
        self.assertEqual(len({row["id"] for row in report["items"]}), len(report["items"]))
        self.assertEqual(agent(report)[0]["skills"], ["check"])


class RevisionTests(unittest.TestCase):
    def test_digest_is_stable_and_ignores_line_endings(self):
        bundle = {"ar": {"apm.yml": b"name: ar\nversion: 0.1.0\n"}, "web": {"apm.yml": b"name: web\n"}}
        crlf = {"ar": {"apm.yml": b"name: ar\r\nversion: 0.1.0\r\n"}, "web": {"apm.yml": b"name: web\r\n"}}
        self.assertEqual(_export_digest(bundle), _export_digest(deepcopy(bundle)))
        self.assertEqual(_export_digest(bundle), _export_digest(crlf))
        self.assertRegex(_export_digest(bundle), r"^[0-9a-f]{64}$")

    def test_digest_changes_with_a_preset_file_or_a_nested_stack_file(self):
        bundle = {"ar": {"apm.yml": b"name: ar\n"}, "web": {"apm.yml": b"name: web\n"}}
        for package_id in ("ar", "web"):
            with self.subTest(package_id=package_id):
                changed = deepcopy(bundle)
                changed[package_id]["apm.yml"] += b"description: changed\n"
                self.assertNotEqual(_export_digest(bundle), _export_digest(changed))
        self.assertNotEqual(_export_digest(bundle), _export_digest({"web": bundle["ar"], "ar": bundle["web"]}))


class RepositoryTests(unittest.TestCase):
    """Exports of packages read from disk."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for name in ("components.json", "consumers.json"):
            (self.root / "catalog").mkdir(exist_ok=True)
            shutil.copy(ROOT / "catalog" / name, self.root / "catalog" / name)

    def package(self, identifier, manifest, files=None):
        directory = self.root / "packages" / identifier
        for path, text in {"apm.yml": manifest, **(files or {})}.items():
            (directory / path).parent.mkdir(parents=True, exist_ok=True)
            (directory / path).write_text(text, encoding="utf-8")

    def convert(self, identifier):
        return paperclip.convert(Store(self.root).get(identifier), root=self.root)

    def test_cao_exports_its_four_skills_with_a_root_path_for_humanizer(self):
        report = paperclip.convert(Store(ROOT).get("cao"), root=ROOT)
        front, _, extension = agent(report, "cao")
        self.assertEqual(front["skills"], ["agent-operating-standards", "find-tools", "find-skills", "humanizer"])
        self.assertEqual((front["role"], extension["role"]), ("general", "general"))
        source = frontmatter(written(report)["skills/humanizer/SKILL.md"])[0]["metadata"]["sources"][0]
        self.assertEqual((source["path"], source["url"]), (".", "https://github.com/blader/humanizer/tree/main"))
        self.assertNotIn("engineer", written(report)[".paperclip.yaml"])

    def test_ar_exports_its_skills(self):
        report = paperclip.convert(Store(ROOT).get("ar"), root=ROOT)
        self.assertEqual([row["id"] for row in report["items"] if paperclip.needs_attention(row)], [])
        front, body, extension = agent(report, "ar")
        self.assertEqual((front["slug"], front["name"]), ("ar", "AI Resources"))
        self.assertEqual(front["skills"], ["find-tools", "find-skills", "agent-operating-standards",
                                           "technology-research"])
        self.assertTrue(body)
        self.assertEqual((front["role"], extension["role"]), ("general", "general"))
        stub, _ = frontmatter(written(report)["skills/technology-research/SKILL.md"])
        self.assertEqual(stub["metadata"]["sources"], [{
            "kind": "github-dir", "repo": "kwonzweig/agent-stack-manager",
            "path": "packages/ar/.apm/skills/technology-research", "trackingRef": "main",
            "url": "https://github.com/kwonzweig/agent-stack-manager/tree/main/packages/ar/.apm/skills/technology-research"}])
        self.assertEqual(stub["name"], "technology-research")
        self.assertTrue(stub["description"])

    def test_presets_own_skill_tracks_this_repositorys_main(self):
        (self.root / "pyproject.toml").write_text(
            '[project]\nname = "x"\n\n[project.urls]\nRepository = "https://github.com/example/stack-repo"\n',
            encoding="utf-8")
        self.package("demo", "name: demo\nx-preset-labels:\n  title: Demo\n", {
            ".apm/agents/demo.agent.md": "Hire well.\n",
            ".apm/skills/hire/SKILL.md": "---\nname: hire\ndescription: Hire.\n---\nSteps.\n"})
        report = self.convert("demo")
        stub, _ = frontmatter(written(report)["skills/hire/SKILL.md"])
        self.assertEqual(stub["metadata"]["sources"], [{
            "kind": "github-dir", "repo": "example/stack-repo", "path": "packages/demo/.apm/skills/hire",
            "trackingRef": "main", "url": "https://github.com/example/stack-repo/tree/main/packages/demo/.apm/skills/hire"}])
        self.assertEqual(agent(report, "demo")[0]["skills"], ["hire"])
        self.assertEqual((stub["name"], stub["description"]), ("hire", "Hire."))

    def test_own_skill_without_a_frontmatter_name_is_named_after_its_folder(self):
        (self.root / "pyproject.toml").write_text(
            '[project]\nname = "x"\n\n[project.urls]\nRepository = "https://github.com/example/stack-repo"\n',
            encoding="utf-8")
        self.package("demo", "name: demo\n", {".apm/skills/hire-well/SKILL.md": "Steps.\n"})
        stub, _ = frontmatter(written(self.convert("demo"))["skills/hire-well/SKILL.md"])
        self.assertEqual(stub["name"], "hire-well")
        self.assertNotIn("description", stub)

    def test_own_skill_without_a_repository_url_needs_attention(self):
        self.package("demo", "name: demo\n", {".apm/skills/hire/SKILL.md": "---\nname: hire\n---\n"})
        row = next(row for row in self.convert("demo")["items"] if row["kind"] == "skill")
        self.assertEqual(row["conversion"]["status"], "unconverted")
        self.assertIn("pyproject.toml", row["conversion"]["reason"])

    def test_revision_follows_the_bundle_and_a_nested_stack(self):
        self.package("base", "name: base\nx-preset-labels:\n  kind: stack\n")
        self.package("demo", "name: demo\ndependencies:\n  apm:\n  - ../base\n")
        revision = lambda: agent(self.convert("demo"), "demo")[2]["metadata"]["agentStackManagerRevision"]
        first = revision()
        self.assertEqual(first, revision())
        self.package("base", "name: base\ndescription: changed\nx-preset-labels:\n  kind: stack\n")
        self.assertNotEqual(first, revision())

    def test_this_repositorys_url_is_in_pyproject(self):
        self.assertEqual(paperclip._repository(ROOT), "https://github.com/kwonzweig/agent-stack-manager")


class ZipTests(unittest.TestCase):
    def test_zip_holds_the_written_files(self):
        report = paperclip.convert(deepcopy(PACKAGE), root=ROOT)
        with ZipFile(BytesIO(paperclip.export_package(report))) as archive:
            self.assertEqual(set(archive.namelist()), set(written(report)))


if __name__ == "__main__":
    unittest.main()
