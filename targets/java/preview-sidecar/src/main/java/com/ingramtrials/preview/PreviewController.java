package com.ingramtrials.preview;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
public class PreviewController {

    private static final BigDecimal GST = new BigDecimal("0.09");

    @GetMapping("/internal/health")
    public Map<String,Object> health() {
        return map("status","UP","service","preview-sidecar","javaVersion",System.getProperty("java.version"));
    }

    @PostMapping("/api/invoices/preview")
    public Map<String,Object> preview(@RequestBody Map<String,Object> body) {
        if (body == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Body is required");
        }

        // customerId — required and must be an integer
        Object customerIdRaw = body.get("customerId");
        if (customerIdRaw == null || String.valueOf(customerIdRaw).trim().isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "customerId is required");
        }
        int customerId = integer(customerIdRaw, "customerId");

        // tier — must be A, B, C or blank (null treated as blank); reject everything else
        Object tierRaw = body.get("tier");
        String tier = tierRaw == null ? "" : String.valueOf(tierRaw).trim();
        if (!tier.isEmpty() && !tier.equals("A") && !tier.equals("B") && !tier.equals("C")) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "tier must be A, B, C or blank");
        }

        // lines
        Object rawLines = body.get("lines");
        if (!(rawLines instanceof List<?>)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "lines must be an array");
        }
        List<?> lines = (List<?>) rawLines;
        if (lines.isEmpty() || lines.size() > 50) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "lines must contain 1 to 50 entries");
        }

        List<Map<String,Object>> priced = new ArrayList<>();
        BigDecimal subtotal = BigDecimal.ZERO;
        int lineNo = 0;
        for (Object item : lines) {
            if (!(item instanceof Map<?,?>)) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "line must be an object");
            }
            @SuppressWarnings("unchecked")
            Map<String,Object> line = (Map<String,Object>) item;

            String code = required(line.get("productCode"), "productCode");

            // qty — required; reject missing as 400 (not NPE)
            Object qtyRaw = line.get("qty");
            if (qtyRaw == null) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "qty is required");
            }
            int qty = integer(qtyRaw, "qty");
            if (qty < 1 || qty > 10000) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "qty must be 1 to 10000");
            }

            BigDecimal price = decimal(line.get("unitPrice"), "unitPrice");
            if (price.compareTo(BigDecimal.ZERO) <= 0 || price.compareTo(new BigDecimal("100000")) > 0 || price.scale() > 4) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "unitPrice is out of range");
            }

            BigDecimal net = previewLineNet(tier, qty, price);
            subtotal = subtotal.add(net);
            priced.add(map("lineNo", ++lineNo, "productCode", code, "qty", qty,
                "unitPrice", price.setScale(4).toPlainString(), "lineNet", money(net)));
        }

        BigDecimal gst = subtotal.multiply(GST).setScale(2, RoundingMode.HALF_UP);
        return map("customerId", customerId, "tier", tier.isEmpty() ? null : tier,
            "subtotal", money(subtotal), "gst", money(gst), "total", money(subtotal.add(gst)),
            "lines", priced);
    }

    // qty>=100 triggers the bulk discount (preview boundary: inclusive at 100)
    BigDecimal previewLineNet(String tier, int qty, BigDecimal price) {
        BigDecimal net = price.multiply(BigDecimal.valueOf(qty));
        if ("A".equals(tier)) net = net.multiply(new BigDecimal("0.95"));
        if ("B".equals(tier)) net = net.multiply(new BigDecimal("0.97"));
        if (qty >= 100) net = net.multiply(new BigDecimal("0.98"));
        return net.setScale(2, RoundingMode.HALF_UP);
    }

    // helpers
    static Map<String,Object> map(Object... pairs) {
        Map<String,Object> result = new LinkedHashMap<>();
        for (int i = 0; i < pairs.length; i += 2) result.put((String) pairs[i], pairs[i + 1]);
        return result;
    }
    static String money(BigDecimal n) { return n.setScale(2, RoundingMode.HALF_UP).toPlainString(); }
    static BigDecimal decimal(Object value, String field) {
        try {
            if (value == null) throw new NumberFormatException();
            return new BigDecimal(value.toString());
        } catch (NumberFormatException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, field + " must be decimal");
        }
    }
    static int integer(Object value, String field) {
        try { return Integer.parseInt(value.toString()); }
        catch (Exception ex) { throw new ResponseStatusException(HttpStatus.BAD_REQUEST, field + " must be integer"); }
    }
    static String required(Object value, String field) {
        if (!(value instanceof String) || ((String) value).trim().isEmpty())
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, field + " is required");
        return ((String) value).trim();
    }
}
