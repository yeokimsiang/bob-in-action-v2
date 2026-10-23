package demo.preview;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

// ---------------------------------------------------------------------------
// Application entry point
// ---------------------------------------------------------------------------

@SpringBootApplication
public class PreviewApplication {

    public static void main(String[] args) {
        SpringApplication.run(PreviewApplication.class, args);
    }
}

// ---------------------------------------------------------------------------
// Customer registry — server-side lookup; caller-supplied tier is ignored
// ---------------------------------------------------------------------------

class CustomerRegistry {

    record Customer(int id, String name, String tier) {}

    private static final List<Customer> CUSTOMERS = List.of(
            new Customer(1, "Aster Office Supplies", "A"),
            new Customer(2, "Merlion Retail",        "B"),
            new Customer(3, "Straits Workshop",      "C")
    );

    /** Returns null when customerId is not known. */
    static Customer find(int customerId) {
        for (Customer c : CUSTOMERS) {
            if (c.id() == customerId) return c;
        }
        return null;
    }
}

// ---------------------------------------------------------------------------
// Product registry — known product codes; unknown codes produce 404
// ---------------------------------------------------------------------------

class ProductRegistry {

    private static final java.util.Set<String> KNOWN = java.util.Set.of(
            "PAPER-A4",
            "CABLE-USB"
    );

    /** Returns true when the product code is registered. */
    static boolean isKnown(String productCode) {
        return productCode != null && KNOWN.contains(productCode);
    }
}

// ---------------------------------------------------------------------------
// Request / response types
// ---------------------------------------------------------------------------

class LineRequest {
    private String productCode;
    private Object qty;
    private String unitPrice;

    public String getProductCode() { return productCode; }
    public void setProductCode(String productCode) { this.productCode = productCode; }

    public Object getQty() { return qty; }
    public void setQty(Object qty) { this.qty = qty; }

    public String getUnitPrice() { return unitPrice; }
    public void setUnitPrice(String unitPrice) { this.unitPrice = unitPrice; }
}

class PreviewRequest {
    private Integer customerId;
    private List<LineRequest> lines;

    public Integer getCustomerId() { return customerId; }
    public void setCustomerId(Integer customerId) { this.customerId = customerId; }

    // tier field accepted in JSON but intentionally ignored; server resolves tier from customer table
    @SuppressWarnings("unused")
    public void setTier(String tier) { /* ignored */ }

    public List<LineRequest> getLines() { return lines; }
    public void setLines(List<LineRequest> lines) { this.lines = lines; }
}

class LineResponse {
    private final int lineNo;
    private final String productCode;
    private final int qty;
    private final String unitPrice;
    private final String lineNet;

    public LineResponse(int lineNo, String productCode, int qty, String unitPrice, String lineNet) {
        this.lineNo = lineNo;
        this.productCode = productCode;
        this.qty = qty;
        this.unitPrice = unitPrice;
        this.lineNet = lineNet;
    }

    public int getLineNo() { return lineNo; }
    public String getProductCode() { return productCode; }
    public int getQty() { return qty; }
    public String getUnitPrice() { return unitPrice; }
    public String getLineNet() { return lineNet; }
}

class PreviewResponse {
    private final int customerId;
    private final String customerName;
    private final String tier;
    private final String subtotal;
    private final String gst;
    private final String total;
    private final List<LineResponse> lines;

    public PreviewResponse(int customerId, String customerName, String tier,
                           String subtotal, String gst, String total,
                           List<LineResponse> lines) {
        this.customerId   = customerId;
        this.customerName = customerName;
        this.tier         = tier;
        this.subtotal     = subtotal;
        this.gst          = gst;
        this.total        = total;
        this.lines        = lines;
    }

    public int getCustomerId()      { return customerId; }
    public String getCustomerName() { return customerName; }
    public String getTier()         { return tier; }
    public String getSubtotal()     { return subtotal; }
    public String getGst()          { return gst; }
    public String getTotal()        { return total; }
    public List<LineResponse> getLines() { return lines; }
}

// ---------------------------------------------------------------------------
// Calculation engine (package-visible for direct test access)
// ---------------------------------------------------------------------------

class PricingEngine {

    static final BigDecimal GST_RATE = new BigDecimal("0.09");
    static final BigDecimal TIER_A   = new BigDecimal("0.05");
    static final BigDecimal TIER_B   = new BigDecimal("0.03");
    static final BigDecimal TIER_C   = BigDecimal.ZERO;
    static final BigDecimal BULK     = new BigDecimal("0.02");
    static final int        BULK_QTY = 100;

    /** Tier discount as a fraction (e.g. 0.05 for A). */
    static BigDecimal tierDiscount(String tier) {
        return switch (tier) {
            case "A" -> TIER_A;
            case "B" -> TIER_B;
            case "C" -> TIER_C;
            default  -> null;          // caller validates
        };
    }

    /**
     * lineNet = round(qty × unitPrice × (1 - tierDiscount) × (1 - bulkDiscount), 2, HALF_UP)
     * bulk discount applies when qty >= BULK_QTY.
     */
    static BigDecimal lineNet(int qty, BigDecimal unitPrice, BigDecimal tierDisc) {
        BigDecimal gross = unitPrice.multiply(BigDecimal.valueOf(qty));
        BigDecimal afterTier = gross.multiply(BigDecimal.ONE.subtract(tierDisc));
        BigDecimal afterBulk = qty >= BULK_QTY
                ? afterTier.multiply(BigDecimal.ONE.subtract(BULK))
                : afterTier;
        return afterBulk.setScale(2, RoundingMode.HALF_UP);
    }

    /** GST = round(subtotal × 0.09, 2, HALF_UP). */
    static BigDecimal gst(BigDecimal subtotal) {
        return subtotal.multiply(GST_RATE).setScale(2, RoundingMode.HALF_UP);
    }
}

// ---------------------------------------------------------------------------
// Health controller
// ---------------------------------------------------------------------------

@RestController
@RequestMapping("/internal")
class HealthController {

    // Package-visible for test assertions; never incremented by this service.
    static volatile long writeCount = 0L;

    @GetMapping(value = "/health", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> health() {
        return Map.of(
                "status", "UP",
                "readOnly", true,
                "writeCount", writeCount
        );
    }
}

// ---------------------------------------------------------------------------
// Invoice-preview controller
// ---------------------------------------------------------------------------

@RestController
@RequestMapping("/api")
class InvoicePreviewController {

    @PostMapping(value = "/invoice-preview",
                 consumes = MediaType.APPLICATION_JSON_VALUE,
                 produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<?> preview(@RequestBody(required = false) PreviewRequest req) {

        // Null body guard (required=false lets us return 400 instead of 415)
        if (req == null) {
            return badRequest("Request body is required");
        }

        // Validate customerId present
        if (req.getCustomerId() == null) {
            return badRequest("customerId is required");
        }

        // Resolve customer server-side; return 404 for unknown customerId
        CustomerRegistry.Customer customer = CustomerRegistry.find(req.getCustomerId());
        if (customer == null) {
            return notFound("Unknown customerId: " + req.getCustomerId());
        }

        // Tier resolved from customer table; caller-supplied tier is ignored
        String tier = customer.tier();
        BigDecimal tierDisc = PricingEngine.tierDiscount(tier);

        // Validate lines
        List<LineRequest> lineReqs = req.getLines();
        if (lineReqs == null || lineReqs.isEmpty()) {
            return badRequest("lines must be present and non-empty");
        }

        List<LineResponse> lineResponses = new ArrayList<>();
        BigDecimal subtotal = BigDecimal.ZERO;

        for (int i = 0; i < lineReqs.size(); i++) {
            LineRequest lr = lineReqs.get(i);
            int lineNo = i + 1;

            // Product code validation — return 404 for unknown productCode
            if (!ProductRegistry.isKnown(lr.getProductCode())) {
                return notFound("Unknown productCode: " + lr.getProductCode());
            }

            // qty validation: must be a JSON integer (not string, not fractional)
            Object rawQty = lr.getQty();
            if (!(rawQty instanceof Integer)) {
                return badRequest("line " + lineNo + ": qty must be a positive integer");
            }
            int qtyInt = (Integer) rawQty;
            if (qtyInt <= 0) {
                return badRequest("line " + lineNo + ": qty must be a positive integer");
            }

            // unitPrice validation
            if (lr.getUnitPrice() == null) {
                return badRequest("line " + lineNo + ": unitPrice is required");
            }
            BigDecimal unitPrice;
            try {
                unitPrice = new BigDecimal(lr.getUnitPrice());
            } catch (NumberFormatException e) {
                return badRequest("line " + lineNo + ": unitPrice is not a valid number");
            }
            if (unitPrice.compareTo(BigDecimal.ZERO) <= 0) {
                return badRequest("line " + lineNo + ": unitPrice must be positive");
            }

            BigDecimal net = PricingEngine.lineNet(qtyInt, unitPrice, tierDisc);
            subtotal = subtotal.add(net);

            lineResponses.add(new LineResponse(
                    lineNo,
                    lr.getProductCode(),
                    qtyInt,
                    unitPrice.setScale(4, RoundingMode.HALF_UP).toPlainString(),
                    net.toPlainString()
            ));
        }

        // subtotal already sum of rounded lineNets; round to 2dp for safety
        subtotal = subtotal.setScale(2, RoundingMode.HALF_UP);
        BigDecimal gst   = PricingEngine.gst(subtotal);
        BigDecimal total = subtotal.add(gst);

        // Preview never increments writeCount
        return ResponseEntity.ok(new PreviewResponse(
                customer.id(),
                customer.name(),
                tier,
                subtotal.toPlainString(),
                gst.toPlainString(),
                total.toPlainString(),
                lineResponses
        ));
    }

    private ResponseEntity<Map<String, String>> badRequest(String message) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(Map.of("error", message));
    }

    private ResponseEntity<Map<String, String>> notFound(String message) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(Map.of("error", message));
    }
}
