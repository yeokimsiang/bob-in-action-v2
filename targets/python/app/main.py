"""
Read-only FastAPI invoice-preview service.
Contract: invoice-preview-v1
Profile:  fastapi-legacy-v2
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator, model_validator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TIER_DISCOUNT = {"A": Decimal("0.05"), "B": Decimal("0.03"), "C": Decimal("0.00")}
BULK_THRESHOLD = 100
BULK_DISCOUNT = Decimal("0.02")
GST_RATE = Decimal("0.09")
TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")

# ---------------------------------------------------------------------------
# Customer registry — server-side resolution only; caller-supplied tier ignored
# ---------------------------------------------------------------------------
CUSTOMERS = {
    1: {"customerName": "Aster Office Supplies", "tier": "A"},
    2: {"customerName": "Merlion Retail",         "tier": "B"},
    3: {"customerName": "Straits Workshop",        "tier": "C"},
}

# ---------------------------------------------------------------------------
# Known product codes — any other code is 404
# ---------------------------------------------------------------------------
KNOWN_PRODUCTS = {"PAPER-A4", "CABLE-USB"}

# ---------------------------------------------------------------------------
# Pydantic models — strict JSON types enforced via validators
# ---------------------------------------------------------------------------

class LineItem(BaseModel):
    productCode: str
    qty: int
    unitPrice: str  # accepted as string; validated to positive Decimal below

    @field_validator("qty", mode="before")
    @classmethod
    def qty_must_be_strict_int(cls, v):
        # Reject fractional numbers passed as JSON number (float) and zero/negative
        if isinstance(v, float):
            raise ValueError("qty must be a whole integer, not a fractional number")
        if not isinstance(v, int):
            raise ValueError("qty must be an integer")
        if v <= 0:
            raise ValueError("qty must be positive")
        return v

    @field_validator("unitPrice", mode="before")
    @classmethod
    def unit_price_must_be_string_and_positive(cls, v):
        if not isinstance(v, str):
            raise ValueError("unitPrice must be a JSON string")
        try:
            d = Decimal(v)
        except Exception:
            raise ValueError("unitPrice must be a valid decimal string")
        if d <= 0:
            raise ValueError("unitPrice must be positive")
        return v


class InvoiceRequest(BaseModel):
    customerId: int
    tier: Optional[str] = None  # caller-supplied tier is accepted but ignored
    lines: List[LineItem]

    @model_validator(mode="before")
    @classmethod
    def check_required_fields(cls, values):
        if "customerId" not in values:
            raise ValueError("customerId is required")
        if "lines" not in values or values.get("lines") is None:
            raise ValueError("lines is required")
        if isinstance(values.get("lines"), list) and len(values["lines"]) == 0:
            raise ValueError("lines must not be empty")
        return values


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


# Override 422 → 400 for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400, content={"detail": exc.errors()})


# Catch malformed JSON bodies
@app.exception_handler(400)
async def bad_request_handler(request: Request, exc):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/internal/health")
async def health():
    return {"status": "UP", "readOnly": True, "writeCount": 0}


@app.post("/api/invoice-preview")
async def invoice_preview(request: Request):
    # Parse JSON manually so malformed JSON returns 400 instead of 422/500
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"detail": "Malformed JSON"})

    try:
        inv = InvoiceRequest.model_validate(body)
    except Exception as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    # Resolve customer server-side; ignore any caller-supplied tier
    customer = CUSTOMERS.get(inv.customerId)
    if customer is None:
        return JSONResponse(status_code=404, content={"detail": f"Unknown customerId: {inv.customerId}"})

    customer_name = customer["customerName"]
    tier = customer["tier"]
    tier_disc = TIER_DISCOUNT[tier]

    # Validate all product codes before computing any line
    for line in inv.lines:
        if line.productCode not in KNOWN_PRODUCTS:
            return JSONResponse(status_code=404, content={"detail": f"Unknown productCode: {line.productCode}"})

    lines_out = []
    subtotal = Decimal("0")

    for i, line in enumerate(inv.lines, start=1):
        up = Decimal(line.unitPrice)
        qty = line.qty

        line_gross = Decimal(qty) * up
        after_tier = line_gross * (1 - tier_disc)
        if qty >= BULK_THRESHOLD:
            after_tier = after_tier * (1 - BULK_DISCOUNT)
        line_net = after_tier.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        subtotal += line_net
        up_normalized = up.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)
        lines_out.append({
            "lineNo": i,
            "productCode": line.productCode,
            "qty": qty,
            "unitPrice": str(up_normalized),
            "lineNet": str(line_net),
        })

    subtotal = subtotal.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    gst = (subtotal * GST_RATE).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    total = (subtotal + gst).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    return {
        "customerId": inv.customerId,
        "customerName": customer_name,
        "tier": tier,
        "subtotal": str(subtotal),
        "gst": str(gst),
        "total": str(total),
        "lines": lines_out,
    }
