// From the repo root: python -m pip install -e .
// From frontend/: npm ci && npx playwright install chromium && npm run build && npm run test:browser
// PYTHON can select a Python 3.11+ executable. ASM_TEST_BROWSER can select an installed Chromium executable.
import assert from "node:assert/strict";
import { execFileSync, spawn } from "node:child_process";
import { once } from "node:events";
import { copyFile, mkdir, mkdtemp, readFile, realpath, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { createInterface } from "node:readline";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const repo = resolve(import.meta.dirname, "../..");
const python = process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");
const mixed = "night-shift-workflow";
const curated = "field-crew";
const skill = name => ({ git: "https://github.com/example/verification-fixture", ref: "main", path: `skills/${name}` });
const state = (selected, portable) => ({ installed: true, enabled: true, selected, portable });
const inventory = (id, name, kind, apps, extra = {}) => ({ id, name, kind, description: "", apps, ...extra });

async function writeFixture(root) {
  const sharedRef = skill("relay-workflow");
  const observations = [
    inventory("relay", "Observed relay", "skill", { codex: state(true), claude: state(true) }, {
      apm: sharedRef,
      skillRepository: { owner: "example", repo: "verification-fixture", branch: "main", directory: sharedRef.path },
    }),
    inventory("preferences", "Observed preferences", "setting", { codex: state(true) }),
    inventory("prompt", "Readiness prompt", "instruction", { codex: state(false, { prompt: "Synthetic portable prompt." }) }),
    inventory("mcp", "Readiness MCP", "mcp", { codex: state(false, { mcp: { name: "readiness", url: "https://example.invalid/mcp" } }) }),
    inventory("stop", "Observed stop hook", "hook", { claude: state(true) }),
  ];
  for (const [id, apm, items] of [
    [mixed, [sharedRef, skill("native-mixed-drop"), skill("native-mixed-keep"),
      { name: "local-design", marketplace: "claude-plugins-official" }], observations],
    [curated, [skill("native-drop-a"), skill("native-drop-b"), skill("native-keep")], undefined],
  ]) {
    const manifest = join(root, "packages", id);
    const instructions = join(manifest, ".apm", "agents");
    await mkdir(instructions, { recursive: true });
    await writeFile(join(instructions, `${id}.agent.md`), `Synthetic primary instruction for ${id}.\n`);
    await writeFile(join(manifest, "apm.yml"), JSON.stringify({
      name: id, dependencies: { apm, hooks: [{ name: "watchdog" }] },
      "x-app-inventory": items && { items },
    }));
  }
  await mkdir(join(root, "catalog"));
  await copyFile(join(repo, "catalog", "consumers.json"), join(root, "catalog", "consumers.json"));
}

async function startServer(root) {
  const child = spawn(python, ["-B", "-m", "asm_app", "--root", root, "serve", "--port", "0"], {
    cwd: repo, stdio: ["ignore", "pipe", "pipe"],
  });
  let stderr = "";
  child.stderr.setEncoding("utf8").on("data", chunk => { stderr = (stderr + chunk).slice(-4000); });
  const finished = once(child, "close");
  // A missing Python executable also rejects the startup promise below.
  finished.catch(() => {});
  const stop = async () => {
    if (child.exitCode === null && child.signalCode === null) child.kill();
    await finished.catch(() => {});
  };
  const lines = createInterface({ input: child.stdout });
  try {
    const address = await Promise.race([
      once(lines, "line", { signal: AbortSignal.timeout(15000) }).then(([line]) => {
        const address = line.match(/^Agent Stack Manager: (http:\/\/127\.0\.0\.1:\d+)$/)?.[1];
        assert.ok(address, `Fixture server could not start: ${line}`);
        return address;
      }),
      finished.then(([code]) => { throw new Error(`Fixture server exited (${code}): ${stderr}`); }),
    ]);
    return { address, stop, log: () => stderr };
  } catch (error) {
    await stop();
    throw error;
  } finally {
    lines.close();
  }
}

test("bulk selection survives layouts, saves only on request, and controls real exports", { timeout: 90000 }, async t => {
  const tempParent = await realpath(tmpdir());
  const root = await realpath(await mkdtemp(join(tempParent, "asm-bulk-export-")));
  assert.equal(dirname(root), tempParent);
  try {
    await writeFixture(root);
    const server = await startServer(root);
    try {
      await runBrowser(server.address, root);
    } catch (error) {
      if (server.log()) t.diagnostic(server.log());
      throw error;
    } finally {
      await server.stop();
    }
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

async function runBrowser(base, root) {
  const browser = await chromium.launch({ executablePath: process.env.ASM_TEST_BROWSER });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, acceptDownloads: true });
    page.setDefaultTimeout(8000);
    const failures = [];
    const patches = [];
    const presetPath = id => `/api/presets/${id}`;
    const allowedPatches = [mixed, curated].map(presetPath);
    page.on("pageerror", error => failures.push(error.message));
    await page.route("**/*", route => {
      const { origin, pathname } = new URL(route.request().url());
      const method = route.request().method();
      if (origin === base) {
        if (method === "PATCH" && allowedPatches.includes(pathname)) {
          patches.push(pathname);
          return route.continue();
        }
        if (method === "GET" || method === "HEAD") {
          if (pathname === "/api/catalog/sources") return route.fulfill({ json: { items: {}, errors: [] } });
          return route.continue();
        }
      }
      failures.push(`${method} ${origin}${pathname}`);
      return route.abort();
    });

    const surface = page.getByRole("region", { name: "Preset components" });
    const search = surface.getByRole("searchbox", { name: "Search components" });
    const button = (name, scope = surface) => scope.getByRole("button", { name, exact: true });
    const check = name => surface.getByRole("checkbox", { name: `Select ${name}`, exact: true });
    const count = value => surface.getByText(`${value} selected`, { exact: true }).waitFor();
    const saveButton = button("Save changes", page);
    const api = async (path, status = 200) => {
      const response = await page.request.get(`${base}${path}`);
      if (response.status() !== status) assert.equal(response.status(), status, `${path}: ${await response.text()}`);
      return response.json();
    };
    const preset = id => api(presetPath(id));
    const review = id => api(`${presetPath(id)}/cc-switch`);
    const open = async id => {
      await page.goto(`${base}/#view=presets&preset=${id}`);
      await search.waitFor();
    };
    const save = async id => {
      const response = page.waitForResponse(result => result.request().method() === "PATCH" &&
        result.url() === `${base}${presetPath(id)}`);
      await saveButton.click();
      assert.equal((await response).status(), 200);
      await saveButton.waitFor({ state: "hidden" });
      // Finish in-flight Catalog reads before tearing down the page on reload.
      await page.waitForLoadState("networkidle");
      await page.reload();
      await search.waitFor();
    };
    const assertChecked = async names => {
      for (const name of names) assert.equal(await check(name).getAttribute("aria-checked"), "true", name);
    };
    const targets = page.getByRole("navigation", { name: "Export targets" });
    const target = name => targets.getByRole("link", { name, exact: true });
    const download = async (label, filename) => {
      const event = page.waitForEvent("download");
      await button(label, page).click();
      const artifact = await event;
      assert.equal(artifact.suggestedFilename(), filename);
      await artifact.saveAs(join(root, filename));
      return join(root, filename);
    };

    const initial = await preset(mixed);
    await open(mixed);
    await button("Grid view").click();
    await button("Select components").click();
    await button("Observed relay").click();
    await check("Observed preferences").click();
    await check("native-mixed-drop").click();
    await count(3);
    assert.equal(await page.getByRole("dialog").count(), 0);
    await button("List view").click();
    await assertChecked(["Observed relay", "Observed preferences", "native-mixed-drop"]);
    const pluginRow = surface.getByRole("listitem").filter({ has: button("local-design", page) });
    const badge = pluginRow.getByText("Claude Code plugin", { exact: true });
    for (const width of [1280, 390]) {
      await page.setViewportSize({ width, height: 900 });
      const fits = await badge.evaluate(async element => {
        await document.fonts.ready;
        const text = [...element.childNodes].find(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
        const range = document.createRange();
        range.selectNodeContents(text);
        const chip = element.getBoundingClientRect();
        const row = element.closest("li").getBoundingClientRect();
        return range.getClientRects().length === 1 && element.scrollWidth <= element.clientWidth &&
          chip.left >= Math.max(row.left, 0) && chip.right <= Math.min(row.right, document.documentElement.clientWidth);
      });
      assert.ok(fits, `Claude Code plugin badge must fit on one line within its row at ${width}px`);
    }
    await page.setViewportSize({ width: 1280, height: 900 });
    await search.fill("Observed relay");
    await check("Observed preferences").waitFor({ state: "hidden" });
    await count(3);
    assert.equal(await saveButton.count(), 0, "Selecting rows must leave the draft clean");
    await button("Exclude from preset").click();
    await search.fill("Readiness");
    await check("Readiness prompt").waitFor();
    await button("Select visible").click();
    await count(2);
    await assertChecked(["Readiness prompt", "Readiness MCP"]);
    await button("Include in preset").click();
    assert.deepEqual(patches, [], "Bulk edits must wait for Save changes");
    assert.equal((await preset(mixed)).revision, initial.revision);
    const lookup = (report, id, app) => report.items.find(item => item.id === id && item.app === app);
    assert.equal(lookup(await review(mixed), "prompt", "codex").status, "excluded");
    await save(mixed);

    await button("Observed relay").waitFor();
    assert.equal(await button("native-mixed-drop").count(), 0);
    const saved = await preset(mixed);
    assert.notEqual(saved.revision, initial.revision);
    const states = [["relay", "codex", false], ["relay", "claude", false], ["preferences", "codex", false],
      ["prompt", "codex", true], ["mcp", "codex", true], ["stop", "claude", true]];
    for (const [id, app, selected] of states) {
      const before = initial.appInventory.find(row => row.id === id).apps[app];
      const after = saved.appInventory.find(row => row.id === id).apps[app];
      assert.deepEqual(after, { ...before, selected }, `${id}/${app}`);
    }

    await page.getByRole("link", { name: "Export", exact: true }).click();
    await target("CC Switch").click();
    const jsonFile = await download("Download CC Switch review", `${mixed}-cc-switch.json`);
    const report = JSON.parse(await readFile(jsonFile, "utf8"));
    assert.deepEqual(report, await review(mixed));
    for (const [id, app, selected] of states.filter(row => !row[2])) {
      const result = lookup(report, id, app);
      assert.deepEqual([result.status, result.selected, result.url], ["excluded", selected, undefined]);
    }
    assert.deepEqual(report.skillRepositories, []);
    assert.equal(lookup(report, "stop", "claude").status, "unsupported");
    assert.equal(report.unassignedItems.find(row => row.name === "local-design").status, "unsupported");
    assert.equal(report.unassignedItems.some(row => row.name === "native-mixed-drop"), false);
    for (const [id, resource] of [["prompt", "prompt"], ["mcp", "mcp"]]) {
      const result = lookup(report, id, "codex");
      assert.equal(result.status, "import-ready");
      const url = new URL(result.url);
      assert.equal(url.searchParams.get("resource"), resource);
      assert.equal(url.searchParams.get(id === "prompt" ? "app" : "apps"), "codex");
      if (id === "prompt") {
        assert.equal(Buffer.from(url.searchParams.get("content"), "base64").toString(), "Synthetic portable prompt.");
      } else {
        assert.deepEqual(JSON.parse(Buffer.from(url.searchParams.get("config"), "base64")),
          { mcpServers: { readiness: { url: "https://example.invalid/mcp" } } });
      }
    }
    await target("Paperclip").click();
    const paperclip = await api(`${presetPath(mixed)}/paperclip`);
    assert.ok(paperclip.items.some(row => row.name === "Readiness MCP" && row.app === "codex" &&
      row.conversion.status === "unconverted"));
    await download("Download Paperclip package", `${mixed}-paperclip.zip`);

    await open(curated);
    await button("Select components").click();
    await search.fill("native-drop-");
    await check("native-keep").waitFor({ state: "hidden" });
    await button("Select visible").click();
    await count(2);
    await assertChecked(["native-drop-a", "native-drop-b"]);
    await button("Remove selected").click();
    await save(curated);
    await button("native-keep").waitFor();
    assert.equal(await button("native-drop-a").count(), 0);
    assert.equal(await button("native-drop-b").count(), 0);
    await page.getByRole("link", { name: "Export", exact: true }).click();
    await target("Paperclip").click();
    const unavailable = await api(`${presetPath(curated)}/cc-switch`, 400);
    assert.equal(await target("CC Switch").count(), 0);
    await page.getByText("CC Switch unavailable", { exact: true }).click();
    await page.getByText(unavailable.error, { exact: true }).waitFor();
    await download("Download Paperclip package", `${curated}-paperclip.zip`);

    execFileSync(python, ["-B", fileURLToPath(new URL("./assert-paperclip.py", import.meta.url)), root, mixed, curated]);
    assert.deepEqual(patches, allowedPatches);
    assert.deepEqual(failures, []);
  } finally {
    await browser.close();
  }
}
