# Python / FastAPI (invoice preview)

Bob's bounded proof that the invoice-preview feature can be rebuilt as a FastAPI service (`app/main.py`, route `POST /api/invoice-preview`), with unittest contract tests in `tests/`. It is one feature, not a full migration.

## Build and test

Needs Python 3.11 or later. Run from `targets/python`:

```powershell
cd targets/python
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt   # macOS/Linux: .venv/bin/python
.venv\Scripts\python -m compileall -q app
.venv\Scripts\python -m unittest discover -s tests -v
```

Verified here: 36 tests, `OK`, on Python 3.11.9 with the pinned FastAPI 0.143.1, httpx 0.28.1 and uvicorn 0.54.0 (an existing environment with those versions was used; the `pip install` step itself was not rerun).

## Run

`.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 18084`

## Try the three orders

The demo page sends the same three orders to the legacy app and to this service. With the service running (see Run above), send them from PowerShell:

```powershell
$url = 'http://127.0.0.1:18084/api/invoice-preview'
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
curl -s -w ' HTTP %{http_code}\n' -H 'Content-Type: application/json' -d '{"customerId":1,"lines":[{"productCode":"PAPER-A4","qty":100,"unitPrice":"10.00"}]}' http://127.0.0.1:18084/api/invoice-preview
```

What it answered when we recorded it on 23 October 2026 (a fresh virtual environment with Python 3.13.0, FastAPI 0.143.1 and uvicorn 0.54.0), beside the legacy app's answer to the same order:

| Order | This service | The legacy app |
|---|---|---|
| Aster Office Supplies, 100 × PAPER-A4 | 931.00 + GST 83.79 = **1014.79** | the same answer, field for field |
| Merlion Retail, 10 × TONER-BK | HTTP 404 `{"detail":"Unknown productCode: TONER-BK"}` | 485.00 + GST 43.65 = 528.65 |
| Straits Workshop, 3 × CABLE-USB and 101 × PAPER-A4 | 999.81 + GST 89.98 = **1089.79** | the same answer, field for field |

It knows only two of the three products, so it refuses Merlion's toner.
