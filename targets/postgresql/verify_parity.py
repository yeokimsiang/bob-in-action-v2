"""
verify_parity.py — Bob-authored reference source for invoice-preview parity cases.

This file defines expected rows and parity arithmetic using the standard library
only. It is NOT trusted controller evidence; it expresses the intended contract
so the controller-owned runner can compare results against it independently.

The controller-owned runner executes the SQL in a random disposable schema on the
isolated real PostgreSQL 18.6 instance and independently computes/queries parity.
This file was NOT executed or validated by Bob.

Caller-supplied tier is never trusted.  customerName and tier are always resolved
from the seeded customers table by customerId.  productCode existence is always
confirmed from the seeded products table before pricing is applied.
"""

from decimal import Decimal, ROUND_HALF_UP

# ---------------------------------------------------------------------------
# Expected seed rows — authoritative reference for controller parity checks
# ---------------------------------------------------------------------------

EXPECTED_CUSTOMERS = [
    {"id": 1, "name": "Aster Office Supplies", "tier": "A", "email": "orders@aster.example"},
    {"id": 2, "name": "Merlion Retail",        "tier": "B", "email": "finance@merlion.example"},
    {"id": 3, "name": "Straits Workshop",       "tier": "C", "email": "accounts@straits.example"},
]

EXPECTED_PRODUCTS = [
    {"code": "CABLE-USB", "description": "USB cable pack",        "unit_price": Decimal("3.3350"), "category": "Accessories"},
    {"code": "PAPER-A4",  "description": "A4 paper carton",       "unit_price": Decimal("10.0000"), "category": "Office"},
    {"code": "TONER-BK",  "description": "Black toner cartridge", "unit_price": Decimal("50.0000"), "category": "Print"},
]

PLACES = Decimal("0.01")

# ---------------------------------------------------------------------------
# Pricing constants
# ---------------------------------------------------------------------------

TIER_DISCOUNT = {
    "A": Decimal("0.05"),
    "B": Decimal("0.03"),
    "C": Decimal("0.00"),
}

GST_RATE = Decimal("0.09")
BULK_THRESHOLD = 100
BULK_DISCOUNT = Decimal("0.02")


def _round(value):
    return value.quantize(PLACES, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# In-memory lookup helpers that mirror the DB lookup the controller performs
# ---------------------------------------------------------------------------

def _lookup_customer(customer_id):
    """
    Return the matching customer dict from EXPECTED_CUSTOMERS, or None.
    Caller-supplied tier is NOT an argument; tier always comes from this lookup.
    """
    for row in EXPECTED_CUSTOMERS:
        if row["id"] == customer_id:
            return row
    return None


def _lookup_product(product_code):
    """Return the matching product dict from EXPECTED_PRODUCTS, or None."""
    for row in EXPECTED_PRODUCTS:
        if row["code"] == product_code:
            return row
    return None


# ---------------------------------------------------------------------------
# Pricing logic
# ---------------------------------------------------------------------------

def compute_line_net(unit_price, qty, tier):
    """Apply tier discount, then bulk discount when qty >= BULK_THRESHOLD."""
    price = Decimal(str(unit_price))
    quantity = Decimal(str(qty))
    tier_d = TIER_DISCOUNT[tier]
    after_tier = price * (Decimal("1") - tier_d)
    if qty >= BULK_THRESHOLD:
        after_tier = after_tier * (Decimal("1") - BULK_DISCOUNT)
    return _round(after_tier * quantity)


def compute_invoice(customer_id, lines):
    """
    Resolve customerName and tier by querying EXPECTED_CUSTOMERS for customer_id.
    Confirm each productCode exists in EXPECTED_PRODUCTS before pricing.

    lines: list of {"productCode": str, "qty": int, "unitPrice": str/Decimal}

    Returns dict with customerId, customerName, tier, subtotal, gst, total,
    or raises ValueError for unknown customer / unknown product.

    Caller-supplied tier is intentionally not accepted as a parameter.
    """
    customer = _lookup_customer(customer_id)
    if customer is None:
        raise ValueError(f"unknown-customer:{customer_id}")

    tier = customer["tier"]
    customer_name = customer["name"]

    line_nets = []
    for ln in lines:
        product = _lookup_product(ln["productCode"])
        if product is None:
            raise ValueError(f"unknown-product:{ln['productCode']}")
        line_nets.append(compute_line_net(ln["unitPrice"], ln["qty"], tier))

    subtotal = sum(line_nets)
    gst = _round(subtotal * GST_RATE)
    total = _round(subtotal + gst)
    return {
        "customerId": customer_id,
        "customerName": customer_name,
        "tier": tier,
        "subtotal": _round(subtotal),
        "gst": gst,
        "total": total,
    }


# ---------------------------------------------------------------------------
# Parity cases — each case drives resolution via customerId + productCode
# so that tier is always obtained from the DB lookup, never from the caller
# ---------------------------------------------------------------------------

PARITY_CASES = [
    {
        "id": "qty=99",
        "customerId": 1,
        "lines": [{"productCode": "PAPER-A4", "qty": 99,  "unitPrice": "10.00"}],
        "expected": {"customerName": "Aster Office Supplies", "tier": "A", "total": Decimal("1025.15")},
    },
    {
        "id": "qty=100",
        "customerId": 1,
        "lines": [{"productCode": "PAPER-A4", "qty": 100, "unitPrice": "10.00"}],
        "expected": {"customerName": "Aster Office Supplies", "tier": "A", "total": Decimal("1014.79")},
    },
    {
        "id": "qty=101",
        "customerId": 1,
        "lines": [{"productCode": "PAPER-A4", "qty": 101, "unitPrice": "10.00"}],
        "expected": {"customerName": "Aster Office Supplies", "tier": "A", "total": Decimal("1024.94")},
    },
    {
        "id": "rounding",
        "customerId": 1,
        "lines": [{"productCode": "CABLE-USB", "qty": 5, "unitPrice": "3.3350"}],
        "expected": {"customerName": "Aster Office Supplies", "tier": "A", "total": Decimal("17.27")},
    },
    {
        "id": "tier=B",
        "customerId": 2,
        "lines": [{"productCode": "PAPER-A4", "qty": 1, "unitPrice": "10.00"}],
        "expected": {"customerName": "Merlion Retail", "tier": "B", "total": Decimal("10.57")},
    },
    {
        "id": "tier=C",
        "customerId": 3,
        "lines": [{"productCode": "PAPER-A4", "qty": 1, "unitPrice": "10.00"}],
        "expected": {"customerName": "Straits Workshop", "tier": "C", "total": Decimal("10.90")},
    },
    {
        "id": "tier-B-bulk",
        "customerId": 2,
        "lines": [{"productCode": "PAPER-A4", "qty": 567, "unitPrice": "10.00"}],
        "expected": {"customerName": "Merlion Retail", "tier": "B", "total": Decimal("5180.77")},
    },
    # Caller injects tier="C" but customerId=1 maps to tier A; injected value must be ignored.
    {
        "id": "caller-tier-ignored",
        "customerId": 1,
        "_injected_caller_tier": "C",          # documented; compute_invoice does not accept this
        "lines": [{"productCode": "PAPER-A4", "qty": 1, "unitPrice": "10.00"}],
        "expected": {"customerName": "Aster Office Supplies", "tier": "A", "total": Decimal("10.36")},
    },
]

# ---------------------------------------------------------------------------
# Rejection cases — controller confirms these raise ValueError (not found)
# and that no write occurs during or after the rejection
# ---------------------------------------------------------------------------

REJECTION_CASES = [
    {
        "id": "unknown-customer",
        "customerId": 999,
        "lines": [{"productCode": "PAPER-A4", "qty": 1, "unitPrice": "10.00"}],
        "expected_error_fragment": "unknown-customer:999",
    },
    {
        "id": "unknown-product",
        "customerId": 1,
        "lines": [{"productCode": "UNKNOWN", "qty": 1, "unitPrice": "10.00"}],
        "expected_error_fragment": "unknown-product:UNKNOWN",
    },
]

# ---------------------------------------------------------------------------
# Row-count parity anchor — controller verifies DB counts match after all
# queries (no row was inserted, updated, or deleted by any read path)
# ---------------------------------------------------------------------------

EXPECTED_ROW_COUNTS = {
    "customers": 3,
    "products": 3,
}


# ---------------------------------------------------------------------------
# Verify helpers
# ---------------------------------------------------------------------------

def verify_all():
    """
    Check each parity case using in-memory lookups that mirror the DB resolution.
    customerName and tier are resolved from EXPECTED_CUSTOMERS by customerId;
    productCode existence is confirmed from EXPECTED_PRODUCTS.
    Returns a list of result dicts.
    Read-only intent: does not connect to a database or modify any state.
    """
    results = []

    for case in PARITY_CASES:
        # _injected_caller_tier is intentionally not passed to compute_invoice
        actual = compute_invoice(case["customerId"], case["lines"])
        exp = case["expected"]
        total_ok  = actual["total"]        == exp["total"]
        tier_ok   = actual["tier"]         == exp["tier"]
        name_ok   = actual["customerName"] == exp["customerName"]
        passed = total_ok and tier_ok and name_ok
        results.append({
            "id": case["id"],
            "expected_total":        exp["total"],
            "actual_total":          actual["total"],
            "expected_tier":         exp["tier"],
            "actual_tier":           actual["tier"],
            "expected_customerName": exp["customerName"],
            "actual_customerName":   actual["customerName"],
            "passed": passed,
        })

    for case in REJECTION_CASES:
        raised = False
        fragment_ok = False
        try:
            compute_invoice(case["customerId"], case["lines"])
        except ValueError as exc:
            raised = True
            fragment_ok = case["expected_error_fragment"] in str(exc)
        results.append({
            "id": case["id"],
            "expected_error_fragment": case["expected_error_fragment"],
            "raised_ValueError": raised,
            "fragment_matched": fragment_ok,
            "passed": raised and fragment_ok,
        })

    return results


def verify_row_count_parity(actual_counts):
    """
    actual_counts: dict {"customers": int, "products": int} from the controller DB query.
    Returns list of result dicts (one per table).
    """
    results = []
    for table, expected in EXPECTED_ROW_COUNTS.items():
        actual = actual_counts.get(table)
        results.append({
            "table": table,
            "expected": expected,
            "actual": actual,
            "passed": actual == expected,
        })
    return results


if __name__ == "__main__":
    print("=== Parity and rejection cases ===")
    any_fail = False
    for r in verify_all():
        if "expected_total" in r:
            status = "PASS" if r["passed"] else "FAIL"
            print(
                f"{status}  {r['id']:22s}"
                f"  total expected={r['expected_total']} actual={r['actual_total']}"
                f"  tier expected={r['expected_tier']} actual={r['actual_tier']}"
                f"  name expected={r['expected_customerName']!r} actual={r['actual_customerName']!r}"
            )
        else:
            status = "PASS" if r["passed"] else "FAIL"
            print(
                f"{status}  {r['id']:22s}"
                f"  raised_ValueError={r['raised_ValueError']}"
                f"  fragment_matched={r['fragment_matched']}"
                f"  expected_fragment={r['expected_error_fragment']!r}"
            )
        if not r["passed"]:
            any_fail = True

    print()
    print("=== Row-count parity (controller supplies actual DB counts) ===")
    print("  (pass --actual-counts to exercise; skipping in standalone run)")

    import sys
    sys.exit(1 if any_fail else 0)
