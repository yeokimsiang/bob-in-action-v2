package com.ingramtrials.base;

import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api")
public class DeskController {
    private final Desk desk;
    private final RestTemplate restTemplate;
    private final String sidecarBase;
    private final ObjectMapper objectMapper;

    @Value("${spring.datasource.url}") String database;

    DeskController(Desk desk, RestTemplate restTemplate, ObjectMapper objectMapper,
                   @Value("${sidecar.url}") String sidecarUrl) {
        this.desk = desk;
        this.restTemplate = restTemplate;
        this.objectMapper = objectMapper;
        this.sidecarBase = sidecarUrl.replaceAll("/+$", "");
    }

    @GetMapping("/health")
    public Map<String,Object> health() {
        Integer ping = desk.db.queryForObject("SELECT 1", Integer.class);
        if (ping == null || ping != 1) throw new IllegalStateException("Database health check failed");
        return Desk.map("status","UP","case","BASE","javaVersion",System.getProperty("java.version"),
            "businessDate",desk.today.toString(),"database",database);
    }
    @GetMapping("/customers")
    public List<Map<String,Object>> customers(@RequestParam(defaultValue="") String q) { return desk.customers(q); }
    @GetMapping("/products")
    public List<Map<String,Object>> products() { return desk.products(); }
    @GetMapping("/invoices")
    public List<Map<String,Object>> invoices(@RequestParam(defaultValue="") String q) { return desk.invoices(q); }
    @GetMapping("/invoices/{id}")
    public Map<String,Object> invoice(@PathVariable int id) { return desk.invoice(id); }

    @PostMapping("/invoices/preview")
    public ResponseEntity<Map<String,Object>> preview(@RequestBody Map<String,Object> body) {
        if (body == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Body is required");
        }
        Object customerIdRaw = body.get("customerId");
        if (customerIdRaw == null || String.valueOf(customerIdRaw).trim().isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "customerId is required");
        }
        int customerId = Desk.integer(customerIdRaw, "customerId");
        Map<String,Object> customer = desk.customer(customerId);
        // overwrite any caller-supplied tier with the database-backed value; never trust external caller
        body.put("tier", customer.get("tier"));

        String url = sidecarBase + "/api/invoices/preview";
        try {
            @SuppressWarnings("unchecked")
            ResponseEntity<Map> raw = restTemplate.postForEntity(url, body, Map.class);
            Object responseBody = raw.getBody();
            if (!(responseBody instanceof Map)) {
                return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                    .body(Desk.map("error","BAD_GATEWAY","message","Preview service returned an unexpected response"));
            }
            @SuppressWarnings("unchecked")
            Map<String,Object> result = (Map<String,Object>) responseBody;
            return ResponseEntity.ok(result);
        } catch (HttpClientErrorException ex) {
            // preserve the sidecar 4xx status and forward its exact safe JSON response body
            String rawBody = ex.getResponseBodyAsString();
            try {
                @SuppressWarnings("unchecked")
                Map<String,Object> errMap = objectMapper.readValue(rawBody, Map.class);
                return ResponseEntity.status(ex.getStatusCode()).body(errMap);
            } catch (Exception parseEx) {
                return ResponseEntity.status(ex.getStatusCode())
                    .body(Desk.map("error",ex.getStatusCode().name(),"message",rawBody));
            }
        } catch (ResourceAccessException ex) {
            // sidecar unavailable: connect timeout, read timeout, or connection refused
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                .body(Desk.map("error","BAD_GATEWAY","message","Preview service is unavailable"));
        } catch (Exception ex) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(Desk.map("error","INTERNAL_SERVER_ERROR","message","An unexpected error occurred"));
        }
    }

    @PostMapping("/invoices")
    @ResponseStatus(HttpStatus.CREATED)
    public Map<String,Object> save(@RequestBody Map<String,Object> body) { return desk.save(body); }
    @GetMapping("/credit-requests")
    public List<Map<String,Object>> creditRequests() { return desk.creditRequests(); }
    @PostMapping("/credit-requests")
    @ResponseStatus(HttpStatus.CREATED)
    public Map<String,Object> requestCredit(@RequestBody Map<String,Object> body) { return desk.requestCredit(body); }
    @GetMapping("/credit-notes")
    public List<Map<String,Object>> creditNotes() { return desk.creditNotes(); }
    @GetMapping("/orders")
    public List<Map<String,Object>> orders() { return desk.orders(); }
    @PostMapping("/jobs/invoices")
    public Map<String,Object> invoicesJob() throws Exception { return desk.runJob("invoices"); }
    @PostMapping("/jobs/credit-notes")
    public Map<String,Object> creditsJob() throws Exception { return desk.runJob("credit-notes"); }
    @GetMapping("/reports/monthly")
    public Map<String,Object> monthly(@RequestParam String month) { return desk.monthly(month); }
    @GetMapping("/reports/gst")
    public Map<String,Object> gst(@RequestParam int year) { return desk.annual(year); }
}
