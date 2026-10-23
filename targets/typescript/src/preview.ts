/**
 * invoice-preview-v1 — TypeScript client boundary
 *
 * Scope: POST /api/invoices/preview only.
 * Never calls /api/invoices or any persistence route.
 * Server-side pricing logic is not reproduced here.
 *
 * qty >= 100 compatibility note: the legacy preview server applies the 2%
 * bulk discount inclusively at qty=100 (total 1014.79). The booked save path
 * applies it exclusively (qty > 100). This client preserves the preview
 * contract as-is and does not reconcile the divergence.
 */

// ---------------------------------------------------------------------------
// Request / Response models (invoice-preview-v1)
// ---------------------------------------------------------------------------

/** A single line on an invoice preview request. */
export interface PreviewLine {
  productCode: string;
  /** Integer, must be >= 1. */
  qty: number;
  /** Positive decimal string with 2 or 4 decimal places, e.g. "10.00" or "10.0000". */
  unitPrice: string;
}

/** Request body for POST /api/invoices/preview. */
export interface PreviewRequest {
  customerId: number;
  lines: PreviewLine[];
}

/** A single line on an invoice preview response. */
export interface PreviewResponseLine {
  lineNo: number;
  productCode: string;
  qty: number;
  /** Four-decimal money string from the controller, e.g. "10.0000". */
  unitPrice: string;
  /** Two-decimal money string. */
  lineNet: string;
}

/** Successful response from POST /api/invoices/preview. */
export interface PreviewResponse {
  customerId: number;
  customerName: string;
  tier: string;
  /** Two-decimal money string. */
  subtotal: string;
  /** Two-decimal money string. */
  gst: string;
  /** Two-decimal money string. */
  total: string;
  lines: PreviewResponseLine[];
}

// ---------------------------------------------------------------------------
// Route constant — the ONLY route this module ever calls
// ---------------------------------------------------------------------------

/** The legacy relative preview route. Never change to /api/invoices or any other path. */
export const PREVIEW_ROUTE = "/api/invoices/preview" as const;

// ---------------------------------------------------------------------------
// Response validation
// ---------------------------------------------------------------------------

/** Two-decimal money string, e.g. "1014.79". */
const MONEY_RE = /^\d+\.\d{2}$/;

/** Four-decimal unit price string, e.g. "10.0000". */
const UNIT_PRICE_RE = /^\d+\.\d{4}$/;

/** Valid tier values. */
const VALID_TIERS = new Set(["A", "B", "C"]);

/** Top-level response fields (exactly these, per invoice-preview-v1). */
const RESPONSE_TOP_FIELDS = new Set(["customerId", "customerName", "tier", "subtotal", "gst", "total", "lines"]);

/** Line response fields (exactly these). */
const RESPONSE_LINE_FIELDS = new Set(["lineNo", "productCode", "qty", "unitPrice", "lineNet"]);

function isMoneyString(v: unknown): v is string {
  return typeof v === "string" && MONEY_RE.test(v);
}

function isUnitPriceString(v: unknown): v is string {
  return typeof v === "string" && UNIT_PRICE_RE.test(v);
}

function isPreviewResponseLine(v: unknown, index: number): v is PreviewResponseLine {
  if (typeof v !== "object" || v === null) return false;
  const o = v as Record<string, unknown>;

  // Reject extra fields
  for (const key of Object.keys(o)) {
    if (!RESPONSE_LINE_FIELDS.has(key)) {
      throw new Error(`PreviewResponse.lines[${index}] contains unexpected field "${key}"`);
    }
  }

  if (typeof o["lineNo"] !== "number" || !Number.isInteger(o["lineNo"]) || !Number.isFinite(o["lineNo"]))
    throw new Error(`PreviewResponse.lines[${index}].lineNo must be a finite integer`);
  if (typeof o["productCode"] !== "string")
    throw new Error(`PreviewResponse.lines[${index}].productCode must be a string`);
  if (typeof o["qty"] !== "number" || !Number.isInteger(o["qty"]) || !Number.isFinite(o["qty"]) || (o["qty"] as number) < 1)
    throw new Error(`PreviewResponse.lines[${index}].qty must be a positive finite integer`);
  if (!isUnitPriceString(o["unitPrice"]))
    throw new Error(`PreviewResponse.lines[${index}].unitPrice must be a four-decimal string`);
  if (!isMoneyString(o["lineNet"]))
    throw new Error(`PreviewResponse.lines[${index}].lineNet must be a two-decimal money string`);

  return true;
}

/**
 * Validates that a raw JSON value conforms to PreviewResponse.
 * Returns the typed value or throws a descriptive Error.
 */
export function validatePreviewResponse(raw: unknown): PreviewResponse {
  if (typeof raw !== "object" || raw === null) {
    throw new Error("Preview response is not an object");
  }
  const o = raw as Record<string, unknown>;

  // Reject extra top-level fields
  for (const key of Object.keys(o)) {
    if (!RESPONSE_TOP_FIELDS.has(key)) {
      throw new Error(`PreviewResponse contains unexpected field "${key}"`);
    }
  }

  if (typeof o["customerId"] !== "number" || !Number.isInteger(o["customerId"]) || !Number.isFinite(o["customerId"]))
    throw new Error("PreviewResponse.customerId must be a finite integer number");
  if (typeof o["customerName"] !== "string" || (o["customerName"] as string).length === 0)
    throw new Error("PreviewResponse.customerName must be a non-empty string");
  if (typeof o["tier"] !== "string" || !VALID_TIERS.has(o["tier"] as string))
    throw new Error("PreviewResponse.tier must be A, B, or C");
  if (!isMoneyString(o["subtotal"]))
    throw new Error("PreviewResponse.subtotal must be a two-decimal money string");
  if (!isMoneyString(o["gst"]))
    throw new Error("PreviewResponse.gst must be a two-decimal money string");
  if (!isMoneyString(o["total"]))
    throw new Error("PreviewResponse.total must be a two-decimal money string");
  if (!Array.isArray(o["lines"]))
    throw new Error("PreviewResponse.lines must be an array");

  const lines = o["lines"] as unknown[];
  if (lines.length === 0) {
    throw new Error("PreviewResponse.lines must not be empty");
  }

  lines.forEach((line, i) => {
    isPreviewResponseLine(line, i);
    // Check sequential lineNo (1-based)
    const ln = (line as Record<string, unknown>)["lineNo"] as number;
    if (ln !== i + 1) {
      throw new Error(`PreviewResponse.lines[${i}].lineNo must be ${i + 1}, got ${ln}`);
    }
  });

  return raw as PreviewResponse;
}

// ---------------------------------------------------------------------------
// API client
// ---------------------------------------------------------------------------

export type FetchFn = typeof fetch;

export class PreviewApiError extends Error {
  constructor(
    message: string,
    public readonly statusCode?: number
  ) {
    super(message);
    this.name = "PreviewApiError";
  }
}

/**
 * Posts a preview request to the legacy /api/invoices/preview route.
 *
 * `fetchFn` is injected so tests can supply a stub without patching globals.
 *
 * @throws {PreviewApiError} on HTTP error or network failure.
 * @throws {Error}           on malformed response structure.
 */
export async function fetchPreview(
  request: PreviewRequest,
  fetchFn: FetchFn = fetch
): Promise<PreviewResponse> {
  let response: Response;
  try {
    response = await fetchFn(PREVIEW_ROUTE, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
  } catch (cause) {
    throw new PreviewApiError(
      cause instanceof Error ? cause.message : "Network error",
      undefined
    );
  }

  if (!response.ok) {
    throw new PreviewApiError(
      `Preview request failed: ${response.status} ${response.statusText}`,
      response.status
    );
  }

  const raw: unknown = await response.json();
  return validatePreviewResponse(raw);
}
