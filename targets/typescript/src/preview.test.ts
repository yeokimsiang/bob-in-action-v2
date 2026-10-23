/**
 * preview.test.ts — self-contained ES-module test for invoice-preview-v1.
 *
 * No Jest, no Node type dependency.
 * Run after compilation: node dist/preview.test.js
 * Exits nonzero on any assertion failure (via throw, not process.exit).
 *
 * Key contract assertions:
 *   - qty=100 returns total "1014.79"
 *   - fetch input is exactly the relative string "/api/invoices/preview"
 *   - outgoing payload omits tier (server resolves tier from customerId)
 *   - response unitPrice is four-decimal (e.g. "10.0000")
 *   - full legacy response (customerId, customerName, tier, subtotal, gst, total, lines) is accepted
 *   - malformed responses are rejected
 *   - no persistence request is issued
 */

import {
  fetchPreview,
  validatePreviewResponse,
  PreviewApiError,
  PREVIEW_ROUTE,
} from "./preview.js";

// ---------------------------------------------------------------------------
// Minimal assertion harness
// ---------------------------------------------------------------------------

let passed = 0;
let failed = 0;

function assert(condition: boolean, label: string): void {
  if (condition) {
    console.log(`  PASS  ${label}`);
    passed++;
  } else {
    console.error(`  FAIL  ${label}`);
    failed++;
  }
}

function assertEq<T>(actual: T, expected: T, label: string): void {
  assert(actual === expected, `${label} — expected ${String(expected)}, got ${String(actual)}`);
}

// ---------------------------------------------------------------------------
// Stub types (no @types/node or @types/jest)
// ---------------------------------------------------------------------------

interface StubResponse {
  ok: boolean;
  status: number;
  statusText: string;
  json(): Promise<unknown>;
}

type StubFetch = (url: string, init?: RequestInit) => Promise<StubResponse>;

function makeFetchOk(body: unknown): { fn: StubFetch; calls: Array<[string, RequestInit | undefined]> } {
  const calls: Array<[string, RequestInit | undefined]> = [];
  const fn: StubFetch = async (url, init) => {
    calls.push([url, init]);
    return { ok: true, status: 200, statusText: "OK", json: async () => body };
  };
  return { fn, calls };
}

function makeFetchError(status: number, statusText: string): StubFetch {
  return async (_url, _init) => ({
    ok: false,
    status,
    statusText,
    json: async () => ({ message: statusText }),
  });
}

function makeFetchNetworkFailure(message: string): StubFetch {
  return async () => { throw new Error(message); };
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

interface PreviewResponseShape {
  customerId: number;
  customerName: string;
  tier: string;
  subtotal: string;
  gst: string;
  total: string;
  lines: Array<{
    lineNo: number;
    productCode: string;
    qty: number;
    unitPrice: string;
    lineNet: string;
  }>;
}

function makeResponse(overrides: Partial<PreviewResponseShape> = {}): PreviewResponseShape {
  return {
    customerId: 1,
    customerName: "Aster Office Supplies",
    tier: "A",
    subtotal: "931.00",
    gst: "83.79",
    total: "1014.79",
    lines: [
      { lineNo: 1, productCode: "PAPER-A4", qty: 100, unitPrice: "10.0000", lineNet: "931.00" },
    ],
    ...overrides,
  };
}

/** Base request: customerId and lines only — tier is intentionally absent. */
const baseRequest = {
  customerId: 1,
  lines: [{ productCode: "PAPER-A4", qty: 100, unitPrice: "10.0000" }],
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

async function runTests(): Promise<void> {

  // --- PREVIEW_ROUTE ---
  console.log("\nPREVIEW_ROUTE");
  assertEq(PREVIEW_ROUTE, "/api/invoices/preview", "is exactly /api/invoices/preview");
  assert(PREVIEW_ROUTE.endsWith("/preview"), "ends with /preview");
  // Compare as string to avoid impossible literal narrowing (TS2367)
  assert(String(PREVIEW_ROUTE) !== "/api/invoices", "is not the bare persistence route");

  // --- qty=100 returns total 1014.79 ---
  console.log("\nfetchPreview — qty=100 retained divergence");
  {
    const { fn } = makeFetchOk(makeResponse());
    const result = await fetchPreview(baseRequest, fn as unknown as typeof fetch);
    assertEq(result.total, "1014.79", "total is 1014.79 for qty=100");
    assertEq(result.subtotal, "931.00", "subtotal is 931.00");
    assertEq(result.gst, "83.79", "gst is 83.79");
  }

  // --- customerName returned and accepted ---
  console.log("\nfetchPreview — customerName in response");
  {
    const { fn } = makeFetchOk(makeResponse());
    const result = await fetchPreview(baseRequest, fn as unknown as typeof fetch);
    assertEq(result.customerName, "Aster Office Supplies", "customerName is Aster Office Supplies");
  }

  // --- four-decimal unitPrice in response line ---
  console.log("\nfetchPreview — four-decimal unitPrice");
  {
    const { fn } = makeFetchOk(makeResponse());
    const result = await fetchPreview(baseRequest, fn as unknown as typeof fetch);
    assertEq(result.lines[0]?.unitPrice, "10.0000", "response line unitPrice is four-decimal");
  }

  // --- outgoing payload omits tier ---
  console.log("\nfetchPreview — outgoing payload omits tier");
  {
    const { fn, calls } = makeFetchOk(makeResponse());
    await fetchPreview(baseRequest, fn as unknown as typeof fetch);
    const init = calls[0]?.[1];
    const body = JSON.parse(init?.body as string) as Record<string, unknown>;
    assert(!("tier" in body), "outgoing body does not contain tier");
    assert(body.customerId === 1, "outgoing body.customerId is 1");
    assert(Array.isArray(body.lines), "outgoing body.lines is an array");
  }

  // --- fetch input is exactly the relative string "/api/invoices/preview" ---
  console.log("\nfetchPreview — exact route");
  {
    const { fn, calls } = makeFetchOk(makeResponse());
    await fetchPreview(baseRequest, fn as unknown as typeof fetch);
    const url = calls[0]?.[0];
    assertEq(url, "/api/invoices/preview", "fetch called with exactly /api/invoices/preview");
    assert(url !== "/api/invoices", "never calls /api/invoices");
    assert(url !== "/api/invoice-preview", "never calls /api/invoice-preview");
  }

  // --- POST method and Content-Type ---
  console.log("\nfetchPreview — request shape");
  {
    const { fn, calls } = makeFetchOk(makeResponse());
    await fetchPreview(baseRequest, fn as unknown as typeof fetch);
    const init = calls[0]?.[1];
    assertEq((init?.method ?? "").toUpperCase(), "POST", "method is POST");
    const ct = (init?.headers as Record<string, string> | undefined)?.["Content-Type"];
    assertEq(ct, "application/json", "Content-Type is application/json");
    const body = JSON.parse(init?.body as string) as Record<string, unknown>;
    assert(body.customerId === 1, "body.customerId is 1");
    assert(!("tier" in body), "body does not contain tier");
  }

  // --- no persistence request is made ---
  console.log("\nfetchPreview — no persistence request");
  {
    const { fn, calls } = makeFetchOk(makeResponse());
    await fetchPreview(baseRequest, fn as unknown as typeof fetch);
    // Exactly one fetch call, to the preview route only
    assertEq(calls.length, 1, "exactly one fetch call was made");
    const url = calls[0]?.[0];
    const method = (calls[0]?.[1]?.method ?? "").toUpperCase();
    assert(url === "/api/invoices/preview" && method === "POST", "the single call is POST /api/invoices/preview");
    assert(url !== "/api/invoices", "no call to persistence route /api/invoices");
  }

  // --- malformed response ---
  console.log("\nfetchPreview — malformed response");
  {
    const { fn: fn1 } = makeFetchOk("not-an-object");
    try {
      await fetchPreview(baseRequest, fn1 as unknown as typeof fetch);
      assert(false, "throws on non-object response");
    } catch (e) {
      assert(e instanceof Error && e.message.includes("not an object"), "throws 'not an object'");
    }

    const noTotal = makeResponse();
    // Remove total to create malformed shape
    const malformed: Record<string, unknown> = { ...noTotal };
    delete malformed["total"];
    const { fn: fn2 } = makeFetchOk(malformed);
    try {
      await fetchPreview(baseRequest, fn2 as unknown as typeof fetch);
      assert(false, "throws when total missing");
    } catch (e) {
      assert(e instanceof Error && e.message.includes("total"), "throws on missing total");
    }

    // Missing customerName is malformed
    const noName = makeResponse();
    const malformed2: Record<string, unknown> = { ...noName };
    delete malformed2["customerName"];
    const { fn: fn3 } = makeFetchOk(malformed2);
    try {
      await fetchPreview(baseRequest, fn3 as unknown as typeof fetch);
      assert(false, "throws when customerName missing");
    } catch (e) {
      assert(e instanceof Error && e.message.includes("customerName"), "throws on missing customerName");
    }
  }

  // --- network failure ---
  console.log("\nfetchPreview — network failure");
  {
    const errFn = makeFetchNetworkFailure("fetch failed");
    try {
      await fetchPreview(baseRequest, errFn as unknown as typeof fetch);
      assert(false, "throws PreviewApiError on network failure");
    } catch (e) {
      assert(e instanceof PreviewApiError, "error is PreviewApiError");
      assert(e instanceof PreviewApiError && e.message.includes("fetch failed"), "error message propagated");
      assert(e instanceof PreviewApiError && e.statusCode === undefined, "statusCode is undefined");
    }
  }

  // --- HTTP 400 ---
  console.log("\nfetchPreview — HTTP errors");
  {
    const errFn400 = makeFetchError(400, "Bad Request");
    try {
      await fetchPreview(baseRequest, errFn400 as unknown as typeof fetch);
      assert(false, "throws PreviewApiError on 400");
    } catch (e) {
      assert(e instanceof PreviewApiError, "400 → PreviewApiError");
      assert(e instanceof PreviewApiError && e.statusCode === 400, "statusCode is 400");
    }

    const errFn500 = makeFetchError(500, "Internal Server Error");
    try {
      await fetchPreview(baseRequest, errFn500 as unknown as typeof fetch);
      assert(false, "throws PreviewApiError on 500");
    } catch (e) {
      assert(e instanceof PreviewApiError, "500 → PreviewApiError");
      assert(e instanceof PreviewApiError && e.statusCode === 500, "statusCode is 500");
    }
  }

  // --- validatePreviewResponse direct ---
  console.log("\nvalidatePreviewResponse");
  {
    const resp = makeResponse();
    try {
      validatePreviewResponse(resp);
      assert(true, "accepts valid response");
    } catch {
      assert(false, "accepts valid response");
    }

    try {
      validatePreviewResponse(null);
      assert(false, "rejects null");
    } catch {
      assert(true, "rejects null");
    }

    const { customerId: _cid, ...noCustomer } = makeResponse();
    try {
      validatePreviewResponse(noCustomer);
      assert(false, "rejects missing customerId");
    } catch (e) {
      assert(e instanceof Error && e.message.includes("customerId"), "rejects missing customerId");
    }

    const { customerName: _cn, ...noCustomerName } = makeResponse();
    try {
      validatePreviewResponse(noCustomerName);
      assert(false, "rejects missing customerName");
    } catch (e) {
      assert(e instanceof Error && e.message.includes("customerName"), "rejects missing customerName");
    }

    const { subtotal: _st, ...noSubtotal } = makeResponse();
    try {
      validatePreviewResponse(noSubtotal);
      assert(false, "rejects missing subtotal");
    } catch (e) {
      assert(e instanceof Error && e.message.includes("subtotal"), "rejects missing subtotal");
    }

    const { gst: _g, ...noGst } = makeResponse();
    try {
      validatePreviewResponse(noGst);
      assert(false, "rejects missing gst");
    } catch (e) {
      assert(e instanceof Error && e.message.includes("gst"), "rejects missing gst");
    }

    // extra top-level field rejected
    try {
      validatePreviewResponse({ ...makeResponse(), extraField: "x" });
      assert(false, "rejects extra top-level field");
    } catch (e) {
      assert(e instanceof Error && e.message.includes("unexpected field"), "rejects extra top-level field");
    }

    // invalid tier rejected
    try {
      validatePreviewResponse({ ...makeResponse(), tier: "Z" });
      assert(false, "rejects invalid tier");
    } catch (e) {
      assert(e instanceof Error && e.message.includes("tier"), "rejects invalid tier");
    }

    // empty lines rejected
    try {
      validatePreviewResponse({ ...makeResponse(), lines: [] });
      assert(false, "rejects empty lines");
    } catch (e) {
      assert(e instanceof Error && e.message.includes("empty"), "rejects empty lines");
    }

    // non-sequential lineNo rejected
    try {
      validatePreviewResponse({
        ...makeResponse(),
        lines: [{ lineNo: 2, productCode: "X", qty: 1, unitPrice: "10.0000", lineNet: "10.00" }],
      });
      assert(false, "rejects non-sequential lineNo");
    } catch (e) {
      assert(e instanceof Error && e.message.includes("lineNo"), "rejects non-sequential lineNo");
    }

    // extra line field rejected
    try {
      validatePreviewResponse({
        ...makeResponse(),
        lines: [{ lineNo: 1, productCode: "X", qty: 1, unitPrice: "10.0000", lineNet: "10.00", extra: "y" }],
      });
      assert(false, "rejects extra line field");
    } catch (e) {
      assert(e instanceof Error && e.message.includes("unexpected field"), "rejects extra line field");
    }
  }

  // --- Summary ---
  console.log(`\n--- Results: ${passed} passed, ${failed} failed ---\n`);
  if (failed > 0) {
    throw new Error(`${failed} test(s) failed`);
  }
}

runTests().catch((err: unknown) => {
  console.error("Unhandled error in test runner:", err);
  throw err;
});
