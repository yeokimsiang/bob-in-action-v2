# Java 8 to Java 21 (invoice preview)

Bob's bounded migration of one feature, invoice preview, from the legacy Java 8 app to Java 21. It is a strangler-style change, not a full migration:

- `preview-sidecar/` — a new Spring Boot service on Java 21 that calculates invoice previews.
- `app/` — the legacy Java 8 app, changed only so its preview route calls the sidecar. Everything else (saving invoices, credit notes, jobs) is unchanged.

Bob wrote the code. It passed independent build, API, browser, rollback and unaffected-workflow checks.

## Build and test

Needs Maven, a Java 21 JDK for the sidecar and a Java 8 JDK for the app. From the repository root:

```powershell
# sidecar (Java 21): 12 tests
$env:JAVA_HOME = '<path to JDK 21>'
mvn -B -f targets/java/preview-sidecar/pom.xml verify

# gateway app (Java 8): 1 test
$env:JAVA_HOME = '<path to JDK 8>'
mvn -B -f targets/java/app/pom.xml verify
```

Both builds pass (sidecar 12 tests, app 1 test) with Temurin 21 and 8 and Maven 3.10.

## Run

Start the sidecar (`java -jar targets/java/preview-sidecar/target/preview-sidecar-1.0.0.jar`, port 18081, set `SIDECAR_PORT` to change it), then the app (`java -jar targets/java/app/target/base-desk-1.0.0.jar`, port 18080; it finds the sidecar through `SIDECAR_URL`). Both bind to `127.0.0.1`.

Known and kept on purpose: the legacy preview applies the bulk discount at quantity 100, while saving applies it above 100. The migration preserves that difference rather than silently changing business behaviour.

## Try the three orders

The demo page sends the same three orders to the legacy app and to this one. Here they still go to the old app's own address, which now passes each one to the sidecar. With both running (see Run above), send them from PowerShell:

```powershell
$url = 'http://127.0.0.1:18080/api/invoices/preview'
$orders = @(
  '{"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":100,"unitPrice":"10.00"}]}',
  '{"customerId":2,"lines":[{"productCode":"TONER-BK","qty":10,"unitPrice":"50.00"}]}',
  '{"customerId":3,"lines":[{"productCode":"CABLE-USB","qty":3,"unitPrice":"3.3350"},{"productCode":"PAPER-A4","qty":101,"unitPrice":"10.00"}]}'
)
foreach ($order in $orders) {
  try { Invoke-RestMethod $url -Method Post -ContentType 'application/json' -Body $order | ConvertTo-Json -Depth 5 -Compress }
  catch {
    $answer = $_.ErrorDetails.Message   # PowerShell 7 keeps the answer here
    if (-not $answer) { $answer = (New-Object IO.StreamReader $_.Exception.Response.GetResponseStream()).ReadToEnd() }
    "HTTP $([int]$_.Exception.Response.StatusCode) $answer"
  }
}
```

On macOS or Linux, send each with curl, for example the first:

```bash
curl -s -w ' HTTP %{http_code}\n' -H 'Content-Type: application/json' -d '{"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":100,"unitPrice":"10.00"}]}' http://127.0.0.1:18080/api/invoices/preview
```

Its answers, recorded with the sidecar on Java 21.0.12.1 and the app on Java 1.8.0_504, beside the legacy app's answers to the same orders:

| Order | The old app, priced by the sidecar | The legacy app before |
|---|---|---|
| Aster Office Supplies, 100 × PAPER-A4 | 931.00 + GST 83.79 = **1014.79** | 931.00 + GST 83.79 = 1014.79, with the customer name |
| Merlion Retail, 10 × TONER-BK | 485.00 + GST 43.65 = **528.65** | 485.00 + GST 43.65 = 528.65, with the customer name |
| Straits Workshop, 3 × CABLE-USB and 101 × PAPER-A4 | 999.81 + GST 89.98 = **1089.79** | 999.81 + GST 89.98 = 1089.79, with the customer name |

The figures are the same for all three orders. The answer no longer carries the customer's name (`customerName`), so the old screen shows "undefined" where the name was.
