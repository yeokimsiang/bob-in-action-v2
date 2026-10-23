# ASP.NET Core (invoice preview)

Bob's bounded proof that the invoice-preview feature can be rebuilt as an ASP.NET Core minimal API (`Program.cs`, route `POST /api/invoice-preview`), with xUnit contract tests in `tests/PreviewApi.Tests/`. It is one feature, not a full migration.

## Build and test

Needs the .NET 10 SDK (NuGet packages are restored on first build). From the repository root:

```powershell
dotnet build targets/dotnet/PreviewApi.csproj --configuration Release --nologo
dotnet test targets/dotnet/tests/PreviewApi.Tests/PreviewApi.Tests.csproj --configuration Release --nologo
```

The tests pass: `Passed! - Failed: 0, Passed: 32` with the .NET 10 SDK.

## Run

`dotnet run --configuration Release --project targets/dotnet/PreviewApi.csproj --urls http://127.0.0.1:18083`

## Try the three orders

The demo page sends the same three orders to the legacy app and to this service. With the service running (see Run above), send them from PowerShell:

```powershell
$url = 'http://127.0.0.1:18083/api/invoice-preview'
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
curl -s -w ' HTTP %{http_code}\n' -H 'Content-Type: application/json' -d '{"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":100,"unitPrice":"10.00"}]}' http://127.0.0.1:18083/api/invoice-preview
```

Its answers, recorded with .NET SDK 10.0.402, beside the legacy app's answers to the same orders:

| Order | This service | The legacy app |
|---|---|---|
| Aster Office Supplies, 100 × PAPER-A4 | 931.00 + GST 83.79 = **1014.79** | the same answer, field for field |
| Merlion Retail, 10 × TONER-BK | HTTP 404 `{"error":"Product not found: TONER-BK"}` | 485.00 + GST 43.65 = 528.65 |
| Straits Workshop, 3 × CABLE-USB and 101 × PAPER-A4 | 999.81 + GST 89.98 = **1089.79** | the same answer, field for field |

It knows only two of the three products, so it refuses Merlion's toner.
