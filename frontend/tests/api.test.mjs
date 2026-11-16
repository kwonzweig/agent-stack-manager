import assert from "node:assert/strict";
import test from "node:test";
import { api } from "../src/api.ts";

function stubFetch() {
  const calls = [];
  globalThis.fetch = async path => {
    calls.push(path);
    return new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } });
  };
  return calls;
}

test("the dashboard asks only its own server", async () => {
  const calls = stubFetch();
  await api("/api/presets");
  assert.deepEqual(calls, ["/api/presets"]);
});

test("a path outside the dashboard's own /api/ is refused before any request", async () => {
  const calls = stubFetch();
  for (const path of ["https://example.com/api/presets", "//example.com/api/presets", "api/presets", "/other"]) {
    await assert.rejects(api(path), /own \/api\//, path);
  }
  assert.deepEqual(calls, []);
});
