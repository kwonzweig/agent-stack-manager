import assert from "node:assert/strict";
import test from "node:test";
import { readRoute } from "../src/lib/route.ts";

test("reads the hashes the dashboard links to", () => {
  assert.deepEqual(readRoute(""), { view: "catalog" });
  assert.deepEqual(readRoute("view=catalog"), { view: "catalog" });
  assert.deepEqual(readRoute("view=presets"), { view: "presets", id: undefined, tab: "components" });
  assert.deepEqual(readRoute("view=presets&preset=cao"), { view: "presets", id: "cao", tab: "components" });
  assert.deepEqual(readRoute("view=presets&preset=cao&tab=source"), { view: "presets", id: "cao", tab: "source" });
  assert.deepEqual(readRoute("view=presets&preset=cao&tab=export&consumer=codex"),
    { view: "presets", id: "cao", tab: "export", consumer: "codex" });
});

test("an unknown tab or view falls back to the default page", () => {
  assert.deepEqual(readRoute("view=presets&preset=cao&tab=paperclip"), { view: "presets", id: "cao", tab: "components" });
  assert.deepEqual(readRoute("presets/cao"), { view: "catalog" });
  assert.deepEqual(readRoute("view=other"), { view: "catalog" });
});
