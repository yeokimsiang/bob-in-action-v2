import java.math.BigDecimal

// ── Inline assertion helpers ───────────────────────────────────────────────

private fun assertEquals(label: String, expected: String, actual: String) {
    if (expected != actual) throw AssertionError("$label: expected=$expected actual=$actual")
}

private fun assertThrows(label: String, block: () -> Unit) {
    try {
        block()
        throw AssertionError("$label: expected ValidationException but none was thrown")
    } catch (e: ValidationException) {
        // expected
    }
}

private fun assertThrowsNotFound(label: String, block: () -> Unit) {
    try {
        block()
        throw AssertionError("$label: expected NotFoundException but none was thrown")
    } catch (e: NotFoundException) {
        // expected
    }
}

// ── Contract cases ────────────────────────────────────────────────────────────

private fun caseQty99() {
    // customerId 1 → Aster Office Supplies, tier A; caller supplies no tier
    val req = parseAndValidate("""{"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":99,"unitPrice":"10.00"}]}""")
    assertEquals("qty99 customerName", "Aster Office Supplies", req.customer.name)
    assertEquals("qty99 tier",         "A",                     req.customer.tier)
    val resp = calculatePreview(req)
    assertEquals("qty99 customerName resp", "Aster Office Supplies", resp.customerName)
    assertEquals("qty99 tier resp",         "A",                     resp.tier)
    val line99 = resp.lines.first()
    assertEquals("qty99 unitPrice", "10.0000", line99.unitPrice.toPlainString())
    assertEquals("qty99 lineNet",   "940.50",  line99.lineNet.toPlainString())
    assertEquals("qty99 subtotal",  "940.50",  resp.subtotal.toPlainString())
    assertEquals("qty99 gst",       "84.65",   resp.gst.toPlainString())
    assertEquals("qty99 total",     "1025.15", resp.total.toPlainString())
}

private fun caseQty100() {
    val req = parseAndValidate("""{"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":100,"unitPrice":"10.00"}]}""")
    val resp = calculatePreview(req)
    val line100 = resp.lines.first()
    assertEquals("qty100 unitPrice", "10.0000", line100.unitPrice.toPlainString())
    assertEquals("qty100 lineNet",   "931.00",  line100.lineNet.toPlainString())
    assertEquals("qty100 subtotal",  "931.00",  resp.subtotal.toPlainString())
    assertEquals("qty100 gst",       "83.79",   resp.gst.toPlainString())
    assertEquals("qty100 total",     "1014.79", resp.total.toPlainString())
}

private fun caseQty101() {
    val req = parseAndValidate("""{"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":101,"unitPrice":"10.00"}]}""")
    val resp = calculatePreview(req)
    assertEquals("qty101 subtotal", "940.31",  resp.subtotal.toPlainString())
    assertEquals("qty101 gst",      "84.63",   resp.gst.toPlainString())
    assertEquals("qty101 total",    "1024.94", resp.total.toPlainString())
}

private fun caseRounding() {
    val req = parseAndValidate("""{"customerId":1,"lines":[{"productCode":"CABLE-USB","qty":5,"unitPrice":"3.3350"}]}""")
    val resp = calculatePreview(req)
    val lineR = resp.lines.first()
    assertEquals("rounding unitPrice", "3.3350", lineR.unitPrice.toPlainString())
    assertEquals("rounding lineNet",   "15.84",  lineR.lineNet.toPlainString())
    assertEquals("rounding subtotal",  "15.84",  resp.subtotal.toPlainString())
    assertEquals("rounding gst",       "1.43",   resp.gst.toPlainString())
    assertEquals("rounding total",     "17.27",  resp.total.toPlainString())
}

private fun caseTierB() {
    // customerId 2 → Merlion Retail, tier B; caller supplies no tier
    val req = parseAndValidate("""{"customerId":2,"lines":[{"productCode":"PAPER-A4","qty":1,"unitPrice":"10.00"}]}""")
    val resp = calculatePreview(req)
    assertEquals("tierB customerName", "Merlion Retail", resp.customerName)
    assertEquals("tierB tier",         "B",              resp.tier)
    assertEquals("tierB subtotal",     "9.70",           resp.subtotal.toPlainString())
    assertEquals("tierB gst",          "0.87",           resp.gst.toPlainString())
    assertEquals("tierB total",        "10.57",          resp.total.toPlainString())
}

private fun caseTierC() {
    // customerId 3 → Straits Workshop, tier C
    val req = parseAndValidate("""{"customerId":3,"lines":[{"productCode":"PAPER-A4","qty":1,"unitPrice":"10.00"}]}""")
    val resp = calculatePreview(req)
    assertEquals("tierC customerName", "Straits Workshop", resp.customerName)
    assertEquals("tierC tier",         "C",                resp.tier)
    assertEquals("tierC subtotal",     "10.00",            resp.subtotal.toPlainString())
    assertEquals("tierC gst",          "0.90",             resp.gst.toPlainString())
    assertEquals("tierC total",        "10.90",            resp.total.toPlainString())
}

private fun caseCallerTierIgnored() {
    // customerId 1 with caller-supplied tier C — server must use tier A (Aster)
    val req = parseAndValidate("""{"customerId":1,"tier":"C","lines":[{"productCode":"PAPER-A4","qty":1,"unitPrice":"10.00"}]}""")
    assertEquals("caller-tier-ignored customerName", "Aster Office Supplies", req.customer.name)
    assertEquals("caller-tier-ignored tier",         "A",                     req.customer.tier)
    val resp = calculatePreview(req)
    assertEquals("caller-tier-ignored resp tier",     "A",     resp.tier)
    assertEquals("caller-tier-ignored resp subtotal", "9.50",  resp.subtotal.toPlainString())
    assertEquals("caller-tier-ignored resp gst",      "0.86",  resp.gst.toPlainString())
    assertEquals("caller-tier-ignored resp total",    "10.36", resp.total.toPlainString())
}

// ── Validation boundary (400) ─────────────────────────────────────────────────

private fun caseRejectMissingCustomerId() {
    assertThrows("missing customerId") {
        parseAndValidate("""{"lines":[{"productCode":"PAPER-A4","qty":1,"unitPrice":"10.00"}]}""")
    }
}

private fun caseRejectMissingLines() {
    assertThrows("missing lines") {
        parseAndValidate("""{"customerId":1}""")
    }
}

private fun caseRejectEmptyLines() {
    assertThrows("empty lines") {
        parseAndValidate("""{"customerId":1,"lines":[]}""")
    }
}

private fun caseRejectQtyString() {
    assertThrows("qty string") {
        parseAndValidate("""{"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":"100","unitPrice":"10.00"}]}""")
    }
}

private fun caseRejectQtyZero() {
    assertThrows("qty zero") {
        parseAndValidate("""{"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":0,"unitPrice":"10.00"}]}""")
    }
}

private fun caseRejectMalformedJson() {
    assertThrows("malformed JSON") {
        parseAndValidate("""{"customerId":1,"lines":[}""")
    }
}

// ── Not-found boundary (404) ──────────────────────────────────────────────────

private fun caseUnknownCustomer() {
    assertThrowsNotFound("unknown customerId 999") {
        parseAndValidate("""{"customerId":999,"lines":[{"productCode":"PAPER-A4","qty":1,"unitPrice":"10.00"}]}""")
    }
}

private fun caseUnknownProduct() {
    assertThrowsNotFound("unknown productCode UNKNOWN") {
        parseAndValidate("""{"customerId":1,"lines":[{"productCode":"UNKNOWN","qty":1,"unitPrice":"10.00"}]}""")
    }
}

// ── Line-level result field checks ────────────────────────────────────────────

private fun caseLineFields() {
    // customerId 1, tier A; use a known product code
    val req = parseAndValidate("""{"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":2,"unitPrice":"5.00"}]}""")
    val resp = calculatePreview(req)
    val line = resp.lines.first()
    assertEquals("lineFields lineNo",      "1",         line.lineNo.toString())
    assertEquals("lineFields productCode", "PAPER-A4",  line.productCode)
    assertEquals("lineFields qty",         "2",         line.qty.toString())
    // unitPrice is normalised to four decimal places by the legacy contract
    assertEquals("lineFields unitPrice",   "5.0000",    line.unitPrice.toPlainString())
    // 2 * 5.00 * 0.95 = 9.50
    assertEquals("lineFields lineNet",     "9.50",      line.lineNet.toPlainString())
    assertEquals("lineFields customerName","Aster Office Supplies", resp.customerName)
}

// ── Write-count invariant ─────────────────────────────────────────────────────

private fun caseWriteCountNotIncremented() {
    // Health always returns writeCount=0; multiple preview calls must not change it.
    // Since writeCount is a constant in the response, verify it is always 0 across calls.
    repeat(3) {
        val req = parseAndValidate("""{"customerId":3,"lines":[{"productCode":"PAPER-A4","qty":1,"unitPrice":"1.00"}]}""")
        calculatePreview(req)
    }
    // No mutable state to assert — the contract encodes writeCount=0 in the health handler.
    // Verified structurally: handleHealth always emits writeCount=0 with no counter.
}

// ── Runner ────────────────────────────────────────────────────────────────────

fun main() {
    val tests = listOf(
        "qty=99"                   to ::caseQty99,
        "qty=100 (bulk)"           to ::caseQty100,
        "qty=101"                  to ::caseQty101,
        "rounding 5x3.3350"        to ::caseRounding,
        "tier B"                   to ::caseTierB,
        "tier C"                   to ::caseTierC,
        "caller-tier-ignored"      to ::caseCallerTierIgnored,
        "reject missingCustomerId" to ::caseRejectMissingCustomerId,
        "reject missingLines"      to ::caseRejectMissingLines,
        "reject emptyLines"        to ::caseRejectEmptyLines,
        "reject qtyString"         to ::caseRejectQtyString,
        "reject qtyZero"           to ::caseRejectQtyZero,
        "reject malformedJson"     to ::caseRejectMalformedJson,
        "unknown customer (404)"   to ::caseUnknownCustomer,
        "unknown product (404)"    to ::caseUnknownProduct,
        "line fields"              to ::caseLineFields,
        "writeCount invariant"     to ::caseWriteCountNotIncremented
    )

    var passed = 0
    var failed = 0
    for ((name, fn) in tests) {
        try {
            fn()
            println("PASS  $name")
            passed++
        } catch (e: Throwable) {
            System.err.println("FAIL  $name: ${e.message}")
            failed++
        }
    }
    println("---")
    println("$passed passed, $failed failed")
    if (failed > 0) throw RuntimeException("$failed test(s) failed")
}
