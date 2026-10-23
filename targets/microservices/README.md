# Microservices (invoice preview service)

Bob's bounded proof that invoice preview can be pulled out of the monolith into its own Spring Boot service on Java 21 (`src/main/java/demo/preview/PreviewApplication.java`, routes `GET /internal/health` and `POST /api/invoice-preview`), with contract tests. The monolith keeps everything else. It is one feature, not a full migration.

## Build and test

Needs Maven and a Java 21 JDK. From the repository root:

```powershell
mvn -B -f targets/microservices/pom.xml verify
```

The build passes: 43 tests, `BUILD SUCCESS`, with Temurin 21 and Maven 3.10.

## Run

`java -jar targets/microservices/target/preview-service.jar --server.address=127.0.0.1 --server.port=18085`

## Try the three orders

The demo page sends the same three orders to the legacy app and to this service. With the service running (see Run above), send them from PowerShell:

```powershell
$url = 'http://127.0.0.1:18085/api/invoice-preview'
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
curl -s -w ' HTTP %{http_code}\n' -H 'Content-Type: application/json' -d '{"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":100,"unitPrice":"10.00"}]}' http://127.0.0.1:18085/api/invoice-preview
```

Its answers, recorded with Java 21.0.12.1 and Maven 3.10.0, beside the legacy app's answers to the same orders:

| Order | This service | The legacy app |
|---|---|---|
| Aster Office Supplies, 100 × PAPER-A4 | 931.00 + GST 83.79 = **1014.79** | the same answer, field for field |
| Merlion Retail, 10 × TONER-BK | HTTP 404 `{"error":"Unknown productCode: TONER-BK"}` | 485.00 + GST 43.65 = 528.65 |
| Straits Workshop, 3 × CABLE-USB and 101 × PAPER-A4 | 999.81 + GST 89.98 = **1089.79** | the same answer, field for field |

It knows only two of the three products, so it refuses Merlion's toner.
