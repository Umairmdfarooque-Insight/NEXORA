// Run with: npm test (uses Node's built-in test runner, no extra packages).
import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import { ApiError, apiFetch } from "./api.ts";

const realFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = realFetch;
});

function mockFetch(status: number, body: unknown) {
  globalThis.fetch = (async () =>
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    })) as typeof fetch;
}

test("returns the parsed body on success", async () => {
  mockFetch(200, { ok: true });
  assert.deepEqual(await apiFetch("/x"), { ok: true });
});

test("a network failure is an unreachable ApiError", async () => {
  globalThis.fetch = (async () => {
    throw new TypeError("fetch failed");
  }) as typeof fetch;
  await assert.rejects(apiFetch("/x"), (error: unknown) => {
    assert.ok(error instanceof ApiError);
    return error.unreachable && error.code === "NETWORK";
  });
});

test("a 422 envelope yields field-level messages", async () => {
  mockFetch(422, {
    error: {
      code: "VALIDATION_ERROR",
      message: "Invalid prompt: too short",
      details: {
        errors: [
          { field: "prompt", message: "too short" },
          { field: "prompt", message: "second message is ignored" },
          { field: "workspace_id", message: "must be a GUID" },
        ],
      },
    },
  });
  await assert.rejects(apiFetch("/x"), (error: unknown) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, 422);
    assert.equal(error.code, "VALIDATION_ERROR");
    assert.deepEqual(error.fields, {
      prompt: "too short",
      workspace_id: "must be a GUID",
    });
    return true;
  });
});

test("a non-JSON error still gives a readable message", async () => {
  globalThis.fetch = (async () =>
    new Response("<html>bad gateway</html>", { status: 502 })) as typeof fetch;
  await assert.rejects(apiFetch("/x"), (error: unknown) => {
    assert.ok(error instanceof ApiError);
    return error.status === 502 && /HTTP 502/.test(error.message);
  });
});

test("keeps the code and message from the API", async () => {
  mockFetch(404, { error: { code: "RUN_NOT_FOUND", message: "Run not found: abc" } });
  await assert.rejects(apiFetch("/runs/abc"), (error: unknown) => {
    assert.ok(error instanceof ApiError);
    return error.code === "RUN_NOT_FOUND" && error.message === "Run not found: abc";
  });
});
