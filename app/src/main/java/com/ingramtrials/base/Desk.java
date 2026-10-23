package com.ingramtrials.base;

import java.io.InputStream;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Properties;

import javax.annotation.PostConstruct;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

@Component
public class Desk {
    final JdbcTemplate db;
    final LocalDate today;
    private final Properties jobs = new Properties();
    static final BigDecimal GST = new BigDecimal("0.09");

    Desk(JdbcTemplate db, @Value("${demo.today:2026-10-13}") String date) {
        this.db = db;
        this.today = LocalDate.parse(date);
    }

    @PostConstruct
    void setup() throws Exception {
        for (String ddl : Arrays.asList(
            "CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY, name VARCHAR(120), tier CHAR(1), email VARCHAR(160))",
            "CREATE TABLE IF NOT EXISTS products (code VARCHAR(40) PRIMARY KEY, description VARCHAR(160), unit_price DECIMAL(18,4), category VARCHAR(80))",
            "CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, customer_id INTEGER, status VARCHAR(20), delivered_date DATE, invoice_id INTEGER)",
            "CREATE TABLE IF NOT EXISTS order_lines (order_id INTEGER, line_no INTEGER, product_code VARCHAR(40), qty INTEGER, unit_price DECIMAL(18,4), PRIMARY KEY(order_id,line_no))",
            "CREATE TABLE IF NOT EXISTS invoices (id INTEGER PRIMARY KEY, invoice_no VARCHAR(40) UNIQUE, customer_id INTEGER, order_id INTEGER UNIQUE, invoice_date DATE, subtotal DECIMAL(18,2), gst DECIMAL(18,2), total DECIMAL(18,2))",
            "CREATE TABLE IF NOT EXISTS invoice_lines (invoice_id INTEGER, line_no INTEGER, product_code VARCHAR(40), qty INTEGER, unit_price DECIMAL(18,4), line_net DECIMAL(18,2), PRIMARY KEY(invoice_id,line_no))",
            "CREATE TABLE IF NOT EXISTS credit_requests (id INTEGER PRIMARY KEY, invoice_id INTEGER, amount_net DECIMAL(18,2), reason VARCHAR(500), status VARCHAR(20), credit_note_id INTEGER)",
            "CREATE TABLE IF NOT EXISTS credit_notes (id INTEGER PRIMARY KEY, credit_note_no VARCHAR(40) UNIQUE, invoice_id INTEGER, credit_date DATE, amount_net DECIMAL(18,2), gst DECIMAL(18,2), total DECIMAL(18,2), reason VARCHAR(500))"
        )) db.execute(ddl);
        if (db.queryForObject("SELECT COUNT(*) FROM customers", Integer.class) == 0) {
            db.update("INSERT INTO customers VALUES (1,'Aster Office Supplies','A','orders@aster.example'),(2,'Merlion Retail','B','finance@merlion.example'),(3,'Straits Workshop','C','accounts@straits.example')");
            db.update("INSERT INTO products VALUES ('PAPER-A4','A4 paper carton',10.0000,'Office'),('TONER-BK','Black toner cartridge',50.0000,'Print'),('CABLE-USB','USB cable pack',3.3350,'Accessories')");
            db.update("INSERT INTO invoices VALUES (1001,'INV-2026-00001',2,NULL,DATE '2026-10-12',485.00,43.65,528.65)");
            db.update("INSERT INTO invoice_lines VALUES (1001,1,'TONER-BK',10,50.0000,485.00)");
            db.update("INSERT INTO orders VALUES (7001,1,'DELIVERED',DATE '2026-10-12',NULL),(7002,3,'PENDING',NULL,NULL)");
            db.update("INSERT INTO order_lines VALUES (7001,1,'PAPER-A4',101,10.0000),(7002,1,'TONER-BK',1,50.0000)");
        }
        try (InputStream in = getClass().getResourceAsStream("/jobs.properties")) {
            if (in == null) throw new IllegalStateException("Missing jobs.properties");
            jobs.load(in);
        }
    }

    static Map<String,Object> map(Object... pairs) {
        Map<String,Object> result = new LinkedHashMap<>();
        for (int i = 0; i < pairs.length; i += 2) result.put((String)pairs[i], pairs[i+1]);
        return result;
    }
    static String money(BigDecimal n) { return n.setScale(2, RoundingMode.HALF_UP).toPlainString(); }
    static String unit(BigDecimal n) {
        return n.setScale(n.stripTrailingZeros().scale()>2 ? 4 : 2, RoundingMode.UNNECESSARY).toPlainString();
    }
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
        if (!(value instanceof String) || ((String)value).trim().isEmpty())
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, field + " is required");
        return ((String)value).trim();
    }
    static ResponseStatusException missing(String what) {
        return new ResponseStatusException(HttpStatus.NOT_FOUND, "Unknown " + what);
    }

    public List<Map<String,Object>> customers(String q) {
        String sql = "SELECT * FROM customers WHERE LOWER(name) LIKE '%" + (q == null ? "" : q.toLowerCase()) + "%' ORDER BY id";
        return db.query(sql, (rs,n) -> map("id",rs.getInt("id"),"name",rs.getString("name"),"tier",rs.getString("tier"),"email",rs.getString("email")));
    }
    public List<Map<String,Object>> products() {
        return db.query("SELECT * FROM products ORDER BY code", (rs,n) -> map("code",rs.getString("code"),"description",rs.getString("description"),"unitPrice",unit(rs.getBigDecimal("unit_price")),"category",rs.getString("category")));
    }
    Map<String,Object> customer(int id) {
        List<Map<String,Object>> found = db.query("SELECT * FROM customers WHERE id=?", (rs,n) -> map("id",rs.getInt("id"),"name",rs.getString("name"),"tier",rs.getString("tier"),"email",rs.getString("email")), id);
        if (found.isEmpty()) throw missing("customer");
        return found.get(0);
    }
    void product(String code) {
        if (db.queryForObject("SELECT COUNT(*) FROM products WHERE code=?", Integer.class,code)==0) throw missing("product");
    }
    BigDecimal previewLineNet(String tier, int qty, BigDecimal price) {
        BigDecimal net=price.multiply(BigDecimal.valueOf(qty));
        if ("A".equals(tier)) net=net.multiply(new BigDecimal("0.95"));
        if ("B".equals(tier)) net=net.multiply(new BigDecimal("0.97"));
        if (qty>=100) net=net.multiply(new BigDecimal("0.98"));
        return net.setScale(2,RoundingMode.HALF_UP);
    }
    BigDecimal bookedLineNet(String tier, int qty, BigDecimal price) {
        BigDecimal net=price.multiply(BigDecimal.valueOf(qty));
        if ("A".equals(tier)) net=net.multiply(new BigDecimal("0.95"));
        if ("B".equals(tier)) net=net.multiply(new BigDecimal("0.97"));
        if (qty>100) net=net.multiply(new BigDecimal("0.98"));
        return net.setScale(2,RoundingMode.HALF_UP);
    }
    Map<String,Object> invoiceRow(ResultSet rs) throws SQLException {
        Object orderId = rs.getObject("order_id");
        return map("id",rs.getInt("id"),"invoiceNo",rs.getString("invoice_no"),"customerId",rs.getInt("customer_id"),
            "customerName",rs.getString("customer_name"),"invoiceDate",rs.getDate("invoice_date").toString(),
            "subtotal",money(rs.getBigDecimal("subtotal")),"gst",money(rs.getBigDecimal("gst")),
            "total",money(rs.getBigDecimal("total")),"orderId",orderId);
    }
    static final String INVOICE_SELECT = "SELECT i.*, c.name AS customer_name FROM invoices i JOIN customers c ON c.id=i.customer_id";
    public List<Map<String,Object>> invoices(String q) {
        String sql = INVOICE_SELECT + " WHERE LOWER(c.name) LIKE '%" + (q == null ? "" : q.toLowerCase()) +
            "%' OR LOWER(i.invoice_no) LIKE '%" + (q == null ? "" : q.toLowerCase()) + "%' ORDER BY i.id DESC";
        return db.query(sql, (rs,n) -> invoiceRow(rs));
    }
    public Map<String,Object> invoice(int id) {
        List<Map<String,Object>> found = db.query(INVOICE_SELECT + " WHERE i.id=?", (rs,n) -> invoiceRow(rs), id);
        if (found.isEmpty()) throw missing("invoice");
        Map<String,Object> result = found.get(0);
        result.put("lines", db.query("SELECT * FROM invoice_lines WHERE invoice_id=? ORDER BY line_no",
            (rs,n) -> map("lineNo",rs.getInt("line_no"),"productCode",rs.getString("product_code"),
                "qty",rs.getInt("qty"),"unitPrice",rs.getBigDecimal("unit_price").setScale(4).toPlainString(),
                "lineNet",money(rs.getBigDecimal("line_net"))), id));
        return result;
    }

    @SuppressWarnings("unchecked")
    public Map<String,Object> calculate(Map<String,Object> input, boolean preview) {
        if (input == null) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Body is required");
        int customerId = integer(input.get("customerId"),"customerId");
        Map<String,Object> customer = customer(customerId);
        Object raw = input.get("lines");
        if (!(raw instanceof List)) throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"lines must be an array");
        List<?> lines = (List<?>)raw;
        if (lines.size()<1 || lines.size()>50) throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"lines must contain 1 to 50 entries");
        List<Map<String,Object>> priced = new ArrayList<>();
        BigDecimal subtotal = BigDecimal.ZERO;
        int number = 0;
        for (Object item : lines) {
            if (!(item instanceof Map)) throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"line must be an object");
            Map<String,Object> line = (Map<String,Object>)item;
            String code = required(line.get("productCode"),"productCode");
            product(code);
            int qty = integer(line.get("qty"),"qty");
            if (qty<1 || qty>10000) throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"qty must be 1 to 10000");
            BigDecimal price = decimal(line.get("unitPrice"),"unitPrice");
            if (price.compareTo(BigDecimal.ZERO)<=0 || price.compareTo(new BigDecimal("100000"))>0 || price.scale()>4)
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"unitPrice is out of range");
            String tier = (String)customer.get("tier");
            BigDecimal net = preview ? previewLineNet(tier,qty,price) : bookedLineNet(tier,qty,price);
            subtotal = subtotal.add(net);
            priced.add(map("lineNo",++number,"productCode",code,"qty",qty,
                "unitPrice",price.setScale(4).toPlainString(),"lineNet",money(net)));
        }
        BigDecimal gst = subtotal.multiply(GST).setScale(2,RoundingMode.HALF_UP);
        return map("customerId",customerId,"customerName",customer.get("name"),"tier",customer.get("tier"),
            "subtotal",money(subtotal),"gst",money(gst),"total",money(subtotal.add(gst)),"lines",priced);
    }
    public synchronized Map<String,Object> save(Map<String,Object> input) {
        Map<String,Object> priced = calculate(input,false);
        int id = db.queryForObject("SELECT COALESCE(MAX(id),1000)+1 FROM invoices",Integer.class);
        String number = String.format("INV-%d-%05d",today.getYear(),id-1000);
        db.update("INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?)",id,number,priced.get("customerId"),null,today,
            priced.get("subtotal"),priced.get("gst"),priced.get("total"));
        for (Map<String,Object> line : (List<Map<String,Object>>)priced.get("lines"))
            db.update("INSERT INTO invoice_lines VALUES (?,?,?,?,?,?)",id,line.get("lineNo"),line.get("productCode"),
                line.get("qty"),line.get("unitPrice"),line.get("lineNet"));
        return invoice(id);
    }

    public List<Map<String,Object>> creditRequests() {
        return db.query("SELECT * FROM credit_requests ORDER BY id", (rs,n) -> map("id",rs.getInt("id"),
            "invoiceId",rs.getInt("invoice_id"),"amountNet",money(rs.getBigDecimal("amount_net")),
            "reason",rs.getString("reason"),"status",rs.getString("status"),"creditNoteId",rs.getObject("credit_note_id")));
    }
    public synchronized Map<String,Object> requestCredit(Map<String,Object> input) {
        if (input==null) throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Body is required");
        int invoiceId = integer(input.get("invoiceId"),"invoiceId");
        Map<String,Object> inv = invoice(invoiceId);
        BigDecimal amount = decimal(input.get("amountNet"),"amountNet");
        if (amount.scale()>2 || amount.compareTo(BigDecimal.ZERO)<=0 ||
            amount.compareTo(new BigDecimal((String)inv.get("subtotal")))>0)
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"amountNet must be positive and at most invoice subtotal");
        String reason = required(input.get("reason"),"reason");
        if (reason.length()>500) throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"reason is too long");
        int id = db.queryForObject("SELECT COALESCE(MAX(id),0)+1 FROM credit_requests",Integer.class);
        db.update("INSERT INTO credit_requests VALUES (?,?,?,?,?,?)",id,invoiceId,amount,reason,"APPROVED",null);
        return map("id",id,"invoiceId",invoiceId,"amountNet",money(amount),"reason",reason,"status","APPROVED","creditNoteId",null);
    }
    public List<Map<String,Object>> creditNotes() {
        return db.query("SELECT * FROM credit_notes ORDER BY id", (rs,n) -> map("id",rs.getInt("id"),
            "creditNoteNo",rs.getString("credit_note_no"),"invoiceId",rs.getInt("invoice_id"),
            "creditDate",rs.getDate("credit_date").toString(),"amountNet",money(rs.getBigDecimal("amount_net")),
            "gst",money(rs.getBigDecimal("gst")),"total",money(rs.getBigDecimal("total")),"reason",rs.getString("reason")));
    }
    public List<Map<String,Object>> orders() {
        return db.query("SELECT * FROM orders ORDER BY id", (rs,n) -> map("id",rs.getInt("id"),
            "customerId",rs.getInt("customer_id"),"status",rs.getString("status"),
            "deliveredDate",rs.getDate("delivered_date")==null?null:rs.getDate("delivered_date").toString(),
            "invoiceId",rs.getObject("invoice_id")));
    }
    public synchronized Map<String,Object> runJob(String name) throws Exception {
        String className = jobs.getProperty(name);
        if (className == null) throw missing("job");
        Job job = (Job)Class.forName(className).newInstance();
        return map("job",name,"created",job.execute(this));
    }
    public int invoiceBatch() {
        int created=0;
        List<Map<String,Object>> pending = db.query(
            "SELECT id,customer_id FROM orders WHERE status='DELIVERED' AND delivered_date=? AND invoice_id IS NULL ORDER BY id",
            (rs,n)->map("id",rs.getInt(1),"customerId",rs.getInt(2)),today.minusDays(1));
        for (Map<String,Object> order : pending) {
            int orderId=(Integer)order.get("id");
            List<Map<String,Object>> lines=db.query("SELECT product_code,qty,unit_price FROM order_lines WHERE order_id=? ORDER BY line_no",
                (rs,n)->map("productCode",rs.getString(1),"qty",rs.getInt(2),"unitPrice",rs.getBigDecimal(3).setScale(4).toPlainString()),orderId);
            Map<String,Object> priced=save(map("customerId",order.get("customerId"),"lines",lines));
            db.update("UPDATE invoices SET order_id=? WHERE id=?",orderId,priced.get("id"));
            db.update("UPDATE orders SET invoice_id=? WHERE id=?",priced.get("id"),orderId);
            created++;
        }
        return created;
    }
    public int creditBatch() {
        int created=0;
        for (Map<String,Object> req : creditRequests()) {
            if (!"APPROVED".equals(req.get("status"))) continue;
            int id=db.queryForObject("SELECT COALESCE(MAX(id),0)+1 FROM credit_notes",Integer.class);
            BigDecimal net=new BigDecimal((String)req.get("amountNet"));
            BigDecimal gst=net.multiply(new BigDecimal("0.09")).setScale(2,RoundingMode.HALF_UP);
            db.update("INSERT INTO credit_notes VALUES (?,?,?,?,?,?,?,?)",id,
                String.format("CN-%d-%05d",today.getYear(),id),req.get("invoiceId"),today,net,gst,net.add(gst),req.get("reason"));
            db.update("UPDATE credit_requests SET status='DONE',credit_note_id=? WHERE id=?",id,req.get("id"));
            created++;
        }
        return created;
    }
    public Map<String,Object> monthly(String month) {
        try { LocalDate.parse(month+"-01"); }
        catch (Exception ex) { throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"month must be YYYY-MM"); }
        List<Map<String,Object>> included=db.query(INVOICE_SELECT+" WHERE FORMATDATETIME(invoice_date,'yyyy-MM')=? ORDER BY i.id",
            (rs,n)->invoiceRow(rs),month);
        BigDecimal subtotal=BigDecimal.ZERO,gst=BigDecimal.ZERO,total=BigDecimal.ZERO;
        Map<Integer,Map<String,Object>> groups=new LinkedHashMap<>();
        for (Map<String,Object> inv:included) {
            subtotal=subtotal.add(new BigDecimal((String)inv.get("subtotal")));
            gst=gst.add(new BigDecimal((String)inv.get("gst")));
            total=total.add(new BigDecimal((String)inv.get("total")));
            int customerId=(Integer)inv.get("customerId");
            Map<String,Object> group=groups.get(customerId);
            if (group==null) { group=map("customerId",customerId,"customerName",inv.get("customerName"),
                "invoiceCount",0,"total","0.00"); groups.put(customerId,group); }
            group.put("invoiceCount",(Integer)group.get("invoiceCount")+1);
            group.put("total",money(new BigDecimal((String)group.get("total")).add(new BigDecimal((String)inv.get("total")))));
        }
        BigDecimal credits=db.queryForObject("SELECT COALESCE(SUM(total),0) FROM credit_notes WHERE FORMATDATETIME(credit_date,'yyyy-MM')=?",
            BigDecimal.class,month);
        return map("month",month,"invoiceCount",included.size(),"subtotal",money(subtotal),"gst",money(gst),
            "total",money(total),"credits",money(credits),"netTotal",money(total.subtract(credits)),
            "byCustomer",new ArrayList<>(groups.values()));
    }
    public Map<String,Object> annual(int year) {
        if (year<2000 || year>9999) throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"year must be four digits");
        List<Map<String,Object>> months=new ArrayList<>();
        for (int n=1;n<=12;n++) {
            String month=String.format("%04d-%02d",year,n);
            BigDecimal invoiced=db.queryForObject("SELECT COALESCE(SUM(gst),0) FROM invoices WHERE FORMATDATETIME(invoice_date,'yyyy-MM')=?",BigDecimal.class,month);
            BigDecimal credited=db.queryForObject("SELECT COALESCE(SUM(gst),0) FROM credit_notes WHERE FORMATDATETIME(credit_date,'yyyy-MM')=?",BigDecimal.class,month);
            months.add(map("month",month,"gstInvoiced",money(invoiced),"gstCredited",money(credited),
                "gstNet",money(invoiced.subtract(credited))));
        }
        return map("year",year,"months",months);
    }
}
