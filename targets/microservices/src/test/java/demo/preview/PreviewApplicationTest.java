package demo.preview;

import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.math.BigDecimal;
import java.math.RoundingMode;

import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
class PreviewApplicationTest {

    @Autowired
    MockMvc mvc;

    final ObjectMapper mapper = new ObjectMapper();

    @BeforeEach
    void resetWriteCount() {
        HealthController.writeCount = 0L;
    }

    // -----------------------------------------------------------------------
    // PricingEngine unit tests
    // -----------------------------------------------------------------------

    @Test
    void tierDiscountA() {
        assertEquals(new BigDecimal("0.05"), PricingEngine.tierDiscount("A"));
    }

    @Test
    void tierDiscountB() {
        assertEquals(new BigDecimal("0.03"), PricingEngine.tierDiscount("B"));
    }

    @Test
    void tierDiscountC() {
        assertEquals(BigDecimal.ZERO, PricingEngine.tierDiscount("C"));
    }

    @Test
    void tierDiscountInvalid() {
        assertNull(PricingEngine.tierDiscount("X"));
    }

    @Test
    void lineNetQty99TierA() {
        // 99 × 10.00 × 0.95 = 940.50 (no bulk)
        BigDecimal result = PricingEngine.lineNet(99, new BigDecimal("10.00"),
                PricingEngine.tierDiscount("A"));
        assertEquals(new BigDecimal("940.50"), result);
    }

    @Test
    void lineNetQty100TierA() {
        // 100 × 10.00 × 0.95 × 0.98 = 931.00
        BigDecimal result = PricingEngine.lineNet(100, new BigDecimal("10.00"),
                PricingEngine.tierDiscount("A"));
        assertEquals(new BigDecimal("931.00"), result);
    }

    @Test
    void lineNetQty101TierA() {
        // 101 × 10.00 × 0.95 × 0.98 = 940.31
        BigDecimal result = PricingEngine.lineNet(101, new BigDecimal("10.00"),
                PricingEngine.tierDiscount("A"));
        assertEquals(new BigDecimal("940.31"), result);
    }

    @Test
    void lineNetRounding5x3_3350TierA() {
        // 5 × 3.3350 × 0.95 = 15.84125 → 15.84
        BigDecimal result = PricingEngine.lineNet(5, new BigDecimal("3.3350"),
                PricingEngine.tierDiscount("A"));
        assertEquals(new BigDecimal("15.84"), result);
    }

    @Test
    void lineNetTierB() {
        // 1 × 10.00 × 0.97 = 9.70
        BigDecimal result = PricingEngine.lineNet(1, new BigDecimal("10.00"),
                PricingEngine.tierDiscount("B"));
        assertEquals(new BigDecimal("9.70"), result);
    }

    @Test
    void lineNetTierC() {
        // 1 × 10.00 × 1.00 = 10.00
        BigDecimal result = PricingEngine.lineNet(1, new BigDecimal("10.00"),
                PricingEngine.tierDiscount("C"));
        assertEquals(new BigDecimal("10.00"), result);
    }

    @Test
    void gstCalculation() {
        // 940.50 × 0.09 = 84.645 → 84.65
        assertEquals(new BigDecimal("84.65"),
                PricingEngine.gst(new BigDecimal("940.50")));
    }

    @Test
    void bulkBoundaryExactly99NoBulk() {
        BigDecimal net = PricingEngine.lineNet(99, new BigDecimal("10.00"),
                PricingEngine.TIER_A);
        // no bulk: 99×10×0.95 = 940.50
        assertEquals(new BigDecimal("940.50"), net);
    }

    @Test
    void bulkBoundaryExactly100HasBulk() {
        BigDecimal net = PricingEngine.lineNet(100, new BigDecimal("10.00"),
                PricingEngine.TIER_A);
        // bulk applied: 100×10×0.95×0.98 = 931.00
        assertEquals(new BigDecimal("931.00"), net);
    }

    // -----------------------------------------------------------------------
    // Health endpoint
    // -----------------------------------------------------------------------

    @Test
    void healthReturns200WithRequiredFields() throws Exception {
        MvcResult result = mvc.perform(get("/internal/health"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andReturn();

        JsonNode body = mapper.readTree(result.getResponse().getContentAsString());
        assertEquals("UP",   body.get("status").asText());
        assertTrue(           body.get("readOnly").asBoolean());
        assertEquals(0,       body.get("writeCount").asInt());
    }

    @Test
    void healthReadOnly_writeCountRemainsZero() throws Exception {
        // Call preview then health; writeCount must still be 0
        String req = """
                {"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":1,"unitPrice":"10.00"}]}
                """;
        mvc.perform(post("/api/invoice-preview")
                .contentType(MediaType.APPLICATION_JSON)
                .content(req))
                .andExpect(status().isOk());

        MvcResult health = mvc.perform(get("/internal/health"))
                .andExpect(status().isOk())
                .andReturn();
        JsonNode body = mapper.readTree(health.getResponse().getContentAsString());
        assertEquals(0, body.get("writeCount").asInt());
    }

    // -----------------------------------------------------------------------
    // Invoice-preview happy path — contract cases
    // -----------------------------------------------------------------------

    @Test
    void previewQty99() throws Exception {
        // contract case qty=99: customerId 1 → Aster Office Supplies, tier A server-resolved
        String req = """
                {"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":99,"unitPrice":"10.00"}]}
                """;
        MvcResult result = mvc.perform(post("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(req))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andReturn();

        JsonNode body = mapper.readTree(result.getResponse().getContentAsString());
        assertEquals("Aster Office Supplies", body.get("customerName").asText());
        assertEquals("A",        body.get("tier").asText());
        assertEquals("940.50",   body.get("subtotal").asText());
        assertEquals("84.65",    body.get("gst").asText());
        assertEquals("1025.15",  body.get("total").asText());
    }

    @Test
    void previewQty100() throws Exception {
        // contract case qty=100: known compatibility boundary total = 1014.79
        String req = """
                {"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":100,"unitPrice":"10.00"}]}
                """;
        MvcResult result = mvc.perform(post("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(req))
                .andExpect(status().isOk())
                .andReturn();

        JsonNode body = mapper.readTree(result.getResponse().getContentAsString());
        assertEquals("Aster Office Supplies", body.get("customerName").asText());
        assertEquals("A",        body.get("tier").asText());
        assertEquals("931.00",   body.get("subtotal").asText());
        assertEquals("83.79",    body.get("gst").asText());
        assertEquals("1014.79",  body.get("total").asText());
    }

    @Test
    void previewQty101() throws Exception {
        String req = """
                {"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":101,"unitPrice":"10.00"}]}
                """;
        MvcResult result = mvc.perform(post("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(req))
                .andExpect(status().isOk())
                .andReturn();

        JsonNode body = mapper.readTree(result.getResponse().getContentAsString());
        assertEquals("Aster Office Supplies", body.get("customerName").asText());
        assertEquals("A",        body.get("tier").asText());
        assertEquals("940.31",   body.get("subtotal").asText());
        assertEquals("84.63",    body.get("gst").asText());
        assertEquals("1024.94",  body.get("total").asText());
    }

    @Test
    void previewRounding5x3_3350TierA() throws Exception {
        String req = """
                {"customerId":1,"lines":[{"productCode":"CABLE-USB","qty":5,"unitPrice":"3.3350"}]}
                """;
        MvcResult result = mvc.perform(post("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(req))
                .andExpect(status().isOk())
                .andReturn();

        JsonNode body = mapper.readTree(result.getResponse().getContentAsString());
        assertEquals("Aster Office Supplies", body.get("customerName").asText());
        assertEquals("A",      body.get("tier").asText());
        assertEquals("15.84",  body.get("subtotal").asText());
        assertEquals("1.43",   body.get("gst").asText());
        assertEquals("17.27",  body.get("total").asText());
    }

    // -----------------------------------------------------------------------
    // Legacy unitPrice scale contract — four-decimal normalization
    // -----------------------------------------------------------------------

    @Test
    void previewQty99_lineUnitPriceFourDecimals() throws Exception {
        // qty=99, unitPrice="10.00" → response line must carry unitPrice="10.0000", lineNet="940.50"
        String req = """
                {"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":99,"unitPrice":"10.00"}]}
                """;
        MvcResult result = mvc.perform(post("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(req))
                .andExpect(status().isOk())
                .andReturn();

        JsonNode line = mapper.readTree(result.getResponse().getContentAsString())
                .get("lines").get(0);
        assertEquals("10.0000", line.get("unitPrice").asText(),
                "unitPrice must be normalized to four decimals");
        assertEquals("940.50", line.get("lineNet").asText(),
                "lineNet must be 940.50 for qty=99, tier A, unitPrice=10.00");
    }

    @Test
    void previewQty100_lineUnitPriceFourDecimals() throws Exception {
        // qty=100, unitPrice="10.00" → response line must carry unitPrice="10.0000", lineNet="931.00"
        String req = """
                {"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":100,"unitPrice":"10.00"}]}
                """;
        MvcResult result = mvc.perform(post("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(req))
                .andExpect(status().isOk())
                .andReturn();

        JsonNode line = mapper.readTree(result.getResponse().getContentAsString())
                .get("lines").get(0);
        assertEquals("10.0000", line.get("unitPrice").asText(),
                "unitPrice must be normalized to four decimals");
        assertEquals("931.00", line.get("lineNet").asText(),
                "lineNet must be 931.00 for qty=100, tier A, unitPrice=10.00");
    }

    @Test
    void previewRounding3_3350_lineUnitPriceFourDecimals() throws Exception {
        // qty=5, unitPrice="3.3350" → response line must carry unitPrice="3.3350", lineNet="15.84"
        String req = """
                {"customerId":1,"lines":[{"productCode":"CABLE-USB","qty":5,"unitPrice":"3.3350"}]}
                """;
        MvcResult result = mvc.perform(post("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(req))
                .andExpect(status().isOk())
                .andReturn();

        JsonNode line = mapper.readTree(result.getResponse().getContentAsString())
                .get("lines").get(0);
        assertEquals("3.3350", line.get("unitPrice").asText(),
                "unitPrice 3.3350 already has four decimals; must be preserved");
        assertEquals("15.84", line.get("lineNet").asText(),
                "lineNet must round 15.84125 → 15.84 HALF_UP");
    }

    @Test
    void previewTierB() throws Exception {
        // customerId 2 → Merlion Retail, tier B server-resolved
        String req = """
                {"customerId":2,"lines":[{"productCode":"PAPER-A4","qty":1,"unitPrice":"10.00"}]}
                """;
        MvcResult result = mvc.perform(post("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(req))
                .andExpect(status().isOk())
                .andReturn();

        JsonNode body = mapper.readTree(result.getResponse().getContentAsString());
        assertEquals("Merlion Retail", body.get("customerName").asText());
        assertEquals("B",      body.get("tier").asText());
        assertEquals("9.70",   body.get("subtotal").asText());
        assertEquals("0.87",   body.get("gst").asText());
        assertEquals("10.57",  body.get("total").asText());
    }

    @Test
    void previewTierC() throws Exception {
        // customerId 3 → Straits Workshop, tier C server-resolved
        String req = """
                {"customerId":3,"lines":[{"productCode":"PAPER-A4","qty":1,"unitPrice":"10.00"}]}
                """;
        MvcResult result = mvc.perform(post("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(req))
                .andExpect(status().isOk())
                .andReturn();

        JsonNode body = mapper.readTree(result.getResponse().getContentAsString());
        assertEquals("Straits Workshop", body.get("customerName").asText());
        assertEquals("C",      body.get("tier").asText());
        assertEquals("10.00",  body.get("subtotal").asText());
        assertEquals("0.90",   body.get("gst").asText());
        assertEquals("10.90",  body.get("total").asText());
    }

    // -----------------------------------------------------------------------
    // Contract case: caller-supplied tier is ignored
    // -----------------------------------------------------------------------

    @Test
    void callerTierIgnored_InjectedTierMismatched() throws Exception {
        // customerId 1 is tier A; caller sends tier=C — server must ignore C and use A
        String req = """
                {"customerId":1,"tier":"C","lines":[{"productCode":"PAPER-A4","qty":1,"unitPrice":"10.00"}]}
                """;
        MvcResult result = mvc.perform(post("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(req))
                .andExpect(status().isOk())
                .andReturn();

        JsonNode body = mapper.readTree(result.getResponse().getContentAsString());
        // tier in response must be A (server-resolved), not the injected C
        assertEquals("Aster Office Supplies", body.get("customerName").asText());
        assertEquals("A",      body.get("tier").asText());
        assertEquals("9.50",   body.get("subtotal").asText());
        assertEquals("0.86",   body.get("gst").asText());
        assertEquals("10.36",  body.get("total").asText());
    }

    @Test
    void noTierLegacyPayload_TierResolvedServerSide() throws Exception {
        // Legacy payload with no tier field at all — must still resolve tier from customer table
        String req = """
                {"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":1,"unitPrice":"10.00"}]}
                """;
        MvcResult result = mvc.perform(post("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(req))
                .andExpect(status().isOk())
                .andReturn();

        JsonNode body = mapper.readTree(result.getResponse().getContentAsString());
        assertEquals("Aster Office Supplies", body.get("customerName").asText());
        assertEquals("A",      body.get("tier").asText());
        // 1 × 10.00 × 0.95 = 9.50
        assertEquals("9.50",   body.get("subtotal").asText());
        assertEquals("0.86",   body.get("gst").asText());
        assertEquals("10.36",  body.get("total").asText());
    }

    // -----------------------------------------------------------------------
    // Contract case: 404 for unknown customerId
    // -----------------------------------------------------------------------

    @Test
    void unknownCustomerReturns404() throws Exception {
        String req = """
                {"customerId":999,"lines":[{"productCode":"PAPER-A4","qty":1,"unitPrice":"10.00"}]}
                """;
        mvc.perform(post("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(req))
                .andExpect(status().isNotFound());
    }

    // -----------------------------------------------------------------------
    // Contract case: 404 for unknown productCode
    // -----------------------------------------------------------------------

    @Test
    void unknownProductReturns404() throws Exception {
        String req = """
                {"customerId":1,"lines":[{"productCode":"UNKNOWN","qty":1,"unitPrice":"10.00"}]}
                """;
        mvc.perform(post("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(req))
                .andExpect(status().isNotFound());
    }

    // -----------------------------------------------------------------------
    // Exact response fields — contract declares all of these present
    // -----------------------------------------------------------------------

    @Test
    void previewResponseContainsAllRequiredFields() throws Exception {
        String req = """
                {"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":1,"unitPrice":"10.00"}]}
                """;
        MvcResult result = mvc.perform(post("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(req))
                .andExpect(status().isOk())
                .andReturn();

        JsonNode body = mapper.readTree(result.getResponse().getContentAsString());
        assertTrue(body.has("customerId"),    "customerId must be present");
        assertTrue(body.has("customerName"),  "customerName must be present");
        assertTrue(body.has("tier"),          "tier must be present");
        assertTrue(body.has("subtotal"),      "subtotal must be present");
        assertTrue(body.has("gst"),           "gst must be present");
        assertTrue(body.has("total"),         "total must be present");
        assertTrue(body.has("lines"),         "lines must be present");

        JsonNode line = body.get("lines").get(0);
        assertTrue(line.has("lineNo"),        "lineNo must be present");
        assertTrue(line.has("productCode"),   "productCode must be present");
        assertTrue(line.has("qty"),           "qty must be present");
        assertTrue(line.has("unitPrice"),     "unitPrice must be present");
        assertTrue(line.has("lineNet"),       "lineNet must be present");
    }

    // -----------------------------------------------------------------------
    // Validation — 400 cases
    // -----------------------------------------------------------------------

    @Test
    void missingCustomerIdReturns400() throws Exception {
        // contract case "missing-customer": no customerId → 400
        String req = """
                {"lines":[{"productCode":"PAPER-A4","qty":1,"unitPrice":"10.00"}]}
                """;
        mvc.perform(post("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(req))
                .andExpect(status().isBadRequest());
    }

    @Test
    void missingLinesReturns400() throws Exception {
        // contract case "missing-lines": customerId present but lines absent → 400
        String req = """
                {"customerId":1}
                """;
        mvc.perform(post("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(req))
                .andExpect(status().isBadRequest());
    }

    @Test
    void emptyLinesReturns400() throws Exception {
        String req = """
                {"customerId":1,"lines":[]}
                """;
        mvc.perform(post("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(req))
                .andExpect(status().isBadRequest());
    }

    @Test
    void zeroQtyReturns400() throws Exception {
        // contract case "malformed-qty-zero"
        String req = """
                {"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":0,"unitPrice":"10.00"}]}
                """;
        mvc.perform(post("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(req))
                .andExpect(status().isBadRequest());
    }

    @Test
    void stringQtyReturns400() throws Exception {
        // contract case "malformed-qty-string": qty as JSON string → 400
        String req = """
                {"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":"100","unitPrice":"10.00"}]}
                """;
        mvc.perform(post("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(req))
                .andExpect(status().isBadRequest());
    }

    @Test
    void fractionalQtyReturns400() throws Exception {
        // qty as JSON fractional number — controller rejects non-Integer Object → 400
        String req = """
                {"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":1.5,"unitPrice":"10.00"}]}
                """;
        mvc.perform(post("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(req))
                .andExpect(status().isBadRequest());
    }

    @Test
    void invalidUnitPriceReturns400() throws Exception {
        String req = """
                {"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":1,"unitPrice":"not-a-number"}]}
                """;
        mvc.perform(post("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(req))
                .andExpect(status().isBadRequest());
    }

    @Test
    void malformedJsonReturns400() throws Exception {
        mvc.perform(post("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{bad json"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void errorResponseHasNoStackTrace() throws Exception {
        String req = """
                {"lines":[{"productCode":"PAPER-A4","qty":1,"unitPrice":"10.00"}]}
                """;
        MvcResult result = mvc.perform(post("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(req))
                .andExpect(status().isBadRequest())
                .andReturn();
        String body = result.getResponse().getContentAsString();
        assertFalse(body.contains("at demo."), "Stack trace must not appear in error response");
        assertFalse(body.contains("Exception"), "Exception class names must not appear");
    }

    // -----------------------------------------------------------------------
    // Write-route rejection
    // -----------------------------------------------------------------------

    @Test
    void putToPreviewReturns405() throws Exception {
        mvc.perform(put("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isMethodNotAllowed());
    }

    @Test
    void deleteToPreviewReturns405() throws Exception {
        mvc.perform(delete("/api/invoice-preview"))
                .andExpect(status().isMethodNotAllowed());
    }

    @Test
    void patchToPreviewReturns405() throws Exception {
        mvc.perform(patch("/api/invoice-preview")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isMethodNotAllowed());
    }

    @Test
    void undeclaredRouteReturns404() throws Exception {
        mvc.perform(get("/api/undeclared"))
                .andExpect(status().isNotFound());
    }

    // -----------------------------------------------------------------------
    // Zero write-count invariant
    // -----------------------------------------------------------------------

    @Test
    void writeCountNeverIncrements() throws Exception {
        // Perform several preview requests
        String req = """
                {"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":50,"unitPrice":"5.00"}]}
                """;
        for (int i = 0; i < 3; i++) {
            mvc.perform(post("/api/invoice-preview")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(req))
                    .andExpect(status().isOk());
        }
        assertEquals(0L, HealthController.writeCount,
                "writeCount must remain 0 after preview calls");
    }
}
