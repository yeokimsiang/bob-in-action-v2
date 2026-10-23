/**
 * browser.ts — wires the invoice-preview panel to the DOM.
 *
 * Reads form inputs named: customerId, productCode, qty, unitPrice.
 * Uses stable data-preview-* selectors declared in index.html.
 * Never reads window.lines or any inaccessible global.
 *
 * Scope: POST /api/invoices/preview only. Never persists.
 */

import { fetchPreview, PreviewRequest, PreviewResponse, PreviewApiError } from "./preview.js";

// ---------------------------------------------------------------------------
// DOM selectors — data-preview-* as declared in index.html
// ---------------------------------------------------------------------------

function requireEl<T extends HTMLElement>(selector: string): T {
  const el = document.querySelector<T>(selector);
  if (!el) throw new Error(`Required element ${selector} not found`);
  return el;
}

// ---------------------------------------------------------------------------
// Render helpers
// ---------------------------------------------------------------------------

/** Renders a successful preview response into the panel. */
export function renderPreview(
  response: PreviewResponse,
  totalEl: HTMLElement,
  errorEl: HTMLElement,
  customerNameEl: HTMLElement
): void {
  errorEl.textContent = "";
  errorEl.hidden = true;
  // [data-preview-customer-name] displays the resolved customer name from the response.
  customerNameEl.textContent = response.customerName;
  // [data-preview-total] must contain exactly the bare total (e.g. "1014.79").
  // Currency label is rendered outside this element in the HTML.
  totalEl.textContent = response.total;
}

/** Renders an error message into the panel. */
export function renderError(
  error: unknown,
  totalEl: HTMLElement,
  errorEl: HTMLElement
): void {
  const text =
    error instanceof Error ? error.message : "An unexpected error occurred";
  errorEl.textContent = text;
  errorEl.hidden = false;
  totalEl.textContent = "0.00";
}

// ---------------------------------------------------------------------------
// Request builder — reads only the four declared form inputs
// ---------------------------------------------------------------------------

function buildRequest(form: HTMLElement): PreviewRequest {
  function inputVal(name: string): string {
    const el = form.querySelector<HTMLInputElement | HTMLSelectElement>(`[name="${name}"]`);
    return el ? el.value.trim() : "";
  }

  const customerIdRaw = inputVal("customerId");
  const productCode = inputVal("productCode");
  const qtyRaw = inputVal("qty");
  const unitPriceRaw = inputVal("unitPrice");

  const customerId = Number(customerIdRaw);
  if (!Number.isInteger(customerId) || customerId < 1) {
    throw new Error("Enter a valid customer ID (integer ≥ 1)");
  }

  if (!productCode) {
    throw new Error("Enter a product code");
  }

  const qty = Number(qtyRaw);
  if (!Number.isInteger(qty) || qty < 1) {
    throw new Error("Enter a valid integer quantity ≥ 1");
  }

  // Positive decimal unitPrice: must match positive four-decimal or two-decimal string
  const UNIT_PRICE_VALID = /^\d+\.\d{2,4}$/.test(unitPriceRaw) && parseFloat(unitPriceRaw) > 0;
  if (!unitPriceRaw || !UNIT_PRICE_VALID) {
    throw new Error("Enter a valid positive decimal unit price (e.g. 10.00 or 10.0000)");
  }

  return {
    customerId,
    lines: [{ productCode, qty, unitPrice: unitPriceRaw }],
  };
}

// ---------------------------------------------------------------------------
// Panel mount
// ---------------------------------------------------------------------------

/**
 * Attaches the submit handler to [data-preview-form].
 * Safe to call after DOMContentLoaded.
 */
export function mountPreviewPanel(): void {
  const formEl = requireEl<HTMLFormElement>("[data-preview-form]");
  const totalEl = requireEl<HTMLElement>("[data-preview-total]");
  const errorEl = requireEl<HTMLElement>("[data-preview-error]");
  const customerNameEl = requireEl<HTMLElement>("[data-preview-customer-name]");

  const handleSubmit = async (e: Event): Promise<void> => {
    e.preventDefault();

    // Clear previous state
    errorEl.textContent = "";
    errorEl.hidden = true;
    totalEl.textContent = "Calculating…";
    customerNameEl.textContent = "";

    let request: PreviewRequest;
    try {
      request = buildRequest(formEl);
    } catch (err) {
      renderError(err, totalEl, errorEl);
      return;
    }

    try {
      const response = await fetchPreview(request);
      renderPreview(response, totalEl, errorEl, customerNameEl);
    } catch (err) {
      renderError(err, totalEl, errorEl);
    }
  };

  formEl.addEventListener("submit", handleSubmit);

  // Also support an explicit submit button click outside the form element
  const submitBtn = document.querySelector<HTMLElement>("[data-preview-submit]");
  if (submitBtn && !formEl.contains(submitBtn)) {
    submitBtn.addEventListener("click", handleSubmit);
  }
}

// Auto-mount when loaded as a module in the browser
if (typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountPreviewPanel);
  } else {
    mountPreviewPanel();
  }
}
