package com.ingramtrials.base;

import java.util.List;
import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api")
public class DeskController {
    private final Desk desk;
    @Value("${spring.datasource.url}") String database;
    DeskController(Desk desk) { this.desk=desk; }

    @GetMapping("/health")
    public Map<String,Object> health() {
        Integer ping=desk.db.queryForObject("SELECT 1",Integer.class);
        if (ping==null || ping!=1) throw new IllegalStateException("Database health check failed");
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
    public Map<String,Object> preview(@RequestBody Map<String,Object> body) { return desk.calculate(body,true); }
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
