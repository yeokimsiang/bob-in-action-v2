package com.ingramtrials.preview;

import java.math.BigDecimal;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import org.springframework.web.server.ResponseStatusException;

class PreviewControllerTest {

    private final PreviewController controller = new PreviewController();

    // -------------------------------------------------------------------------
    // qty=100 boundary: bulk discount applies at exactly 100 (inclusive)
    // -------------------------------------------------------------------------

    @Test
    void qty99_noTier_noBulkDiscount() {
        // price=10, qty=99, no tier: net = 10*99 = 990.00 (no bulk)
        BigDecimal net = controller.previewLineNet("", 99, new BigDecimal("10.0000"));
        assertEquals(new BigDecimal("990.00"), net);
    }

    @Test
    void qty100_noTier_bulkDiscountApplies() {
        // price=10, qty=100, no tier: net = 10*100*0.98 = 980.00
        BigDecimal net = controller.previewLineNet("", 100, new BigDecimal("10.0000"));
        assertEquals(new BigDecimal("980.00"), net);
    }

    @Test
    void qty101_noTier_bulkDiscountApplies() {
        // price=10, qty=101, no tier: net = 10*101*0.98 = 989.80
        BigDecimal net = controller.previewLineNet("", 101, new BigDecimal("10.0000"));
        assertEquals(new BigDecimal("989.80"), net);
    }

    @Test
    void qty100_tierA_bothDiscountsApply() {
        // price=10, qty=100, tier A: net = 10*100*0.95*0.98 = 931.00
        BigDecimal net = controller.previewLineNet("A", 100, new BigDecimal("10.0000"));
        assertEquals(new BigDecimal("931.00"), net);
    }

    @Test
    void qty100_tierB_bothDiscountsApply() {
        // price=10, qty=100, tier B: net = 10*100*0.97*0.98 = 950.60
        BigDecimal net = controller.previewLineNet("B", 100, new BigDecimal("10.0000"));
        assertEquals(new BigDecimal("950.60"), net);
    }

    @Test
    void qty99_tierA_onlyTierDiscountApplies() {
        // price=10, qty=99, tier A: net = 10*99*0.95 = 940.50
        BigDecimal net = controller.previewLineNet("A", 99, new BigDecimal("10.0000"));
        assertEquals(new BigDecimal("940.50"), net);
    }

    // -------------------------------------------------------------------------
    // Tier validation: A, B, C and blank are accepted; everything else rejected
    // -------------------------------------------------------------------------

    @Test
    void tierA_accepted() {
        // tier A alone must not throw a tier validation error
        BigDecimal net = controller.previewLineNet("A", 1, new BigDecimal("10.0000"));
        assertEquals(new BigDecimal("9.50"), net);
    }

    @Test
    void tierB_accepted() {
        BigDecimal net = controller.previewLineNet("B", 1, new BigDecimal("10.0000"));
        assertEquals(new BigDecimal("9.70"), net);
    }

    @Test
    void tierC_noDiscount() {
        // tier C has no discount — net = price * qty
        BigDecimal net = controller.previewLineNet("C", 1, new BigDecimal("10.0000"));
        assertEquals(new BigDecimal("10.00"), net);
    }

    @Test
    void blankTier_accepted() {
        BigDecimal net = controller.previewLineNet("", 1, new BigDecimal("10.0000"));
        assertEquals(new BigDecimal("10.00"), net);
    }

    @Test
    void invalidTier_rejectedAs400() {
        // The controller endpoint validates tier before calling previewLineNet;
        // test the validation path directly via the endpoint helper logic.
        PreviewController ctrl = new PreviewController();
        // Build a minimal valid body with an invalid tier
        java.util.Map<String,Object> body = new java.util.LinkedHashMap<>();
        body.put("customerId", 1);
        body.put("tier", "X");
        body.put("lines", java.util.List.of(
            PreviewController.map("productCode","PAPER-A4","qty",1,"unitPrice","10.0000")
        ));
        ResponseStatusException ex = assertThrows(ResponseStatusException.class, () -> ctrl.preview(body));
        assertEquals(400, ex.getStatusCode().value());
    }

    @Test
    void missingQty_rejectedAs400() {
        PreviewController ctrl = new PreviewController();
        java.util.Map<String,Object> body = new java.util.LinkedHashMap<>();
        body.put("customerId", 1);
        body.put("tier", "A");
        java.util.Map<String,Object> line = new java.util.LinkedHashMap<>();
        line.put("productCode", "PAPER-A4");
        // qty intentionally omitted
        line.put("unitPrice", "10.0000");
        body.put("lines", java.util.List.of(line));
        ResponseStatusException ex = assertThrows(ResponseStatusException.class, () -> ctrl.preview(body));
        assertEquals(400, ex.getStatusCode().value());
    }
}
