# Ingram Trials invoice desk (the legacy app)

This is the starting point: a small, deliberately imperfect Java 8 application that Bob assesses. It is a made-up distributor's invoice desk with customer search, invoice preview and save, credit notes and scheduled jobs. It has the kinds of problems real inherited code has: coupling, duplicated rules, stale documentation, weak tests, unsafe source patterns and code nobody is sure is still used.

Treat it as read-only. The Bob commands read it and write their reports under `runs/<name>/`; they never change this folder.

## Layout

- `pom.xml`, `src/` — the Spring Boot 2.7 application (Java 8, H2 database, browser UI under `src/main/resources/static/`).
- `docs/`, `scripts/` — material that came with the application. Some of it is out of date on purpose.
- `Build.ps1`, `Start.ps1`, `Stop.ps1`, `Run-Job.ps1` — Windows PowerShell helpers to build, run and stop it locally.

## What's in the code

Four layers, each in one place:

- **Screen**: `src/main/resources/static/index.html` and `src/main/resources/static/desk.js`, one page and its script in the browser.
- **Routes**: `src/main/java/com/ingramtrials/base/DeskController.java` turns each address under `/api` that the screen calls into a call on the rules.
- **Rules**: `src/main/java/com/ingramtrials/base/Desk.java` holds prices, invoices, credit notes, jobs and reports in one class. It also creates the database's tables when the app starts and fills in the sample data the first time.
- **Data**: an H2 database in a file under `app/runtime/data/`.

Also there: `src/main/resources/jobs.properties` names the two job classes, and `Desk.java` loads whichever one is asked for by its name. `src/main/java/com/ingramtrials/base/ScheduledJobs.java` would run both every night at 01:00 and 01:30, but a setting in `src/main/resources/application.properties` keeps them switched off. `InvoiceRunJobV2.java` is in no list, and nothing uses `LegacyInvoicePrinter.java`. The one test, `src/test/java/com/ingramtrials/base/DeskMoneyTest.java`, checks how money is rounded and nothing else.

The demo's [recorded copy of the app](https://yeokimsiang.github.io/bob-in-action-v2/legacy-desk/#code) links each part of the screen to the lines that run it, with the findings Bob made there.

## Build and run (optional)

You do not need to build the app to run the Bob commands. To see it working you need Java 8 (JDK) and Maven.

```powershell
.\app\Build.ps1                 # mvn clean verify with Java 8
.\app\Start.ps1                 # builds, starts on http://127.0.0.1:18080/ and waits for /api/health
.\app\Run-Job.ps1 -Job invoices # trigger a scheduled job by hand
.\app\Stop.ps1                  # stops the server Start.ps1 started
```

The scripts look for Java 8 in `JAVA8_HOME` (default `C:\Program Files\Eclipse Adoptium\jdk-8.0.504.1-hotspot`) and Maven in `MAVEN_CMD`, then `mvn` on `PATH`. On macOS or Linux, run Maven directly with a Java 8 JDK: `mvn -f app/pom.xml clean verify`.

The server binds to `127.0.0.1` only. Data lives in `app/runtime/` (ignored by git). Its only login is H2's default `sa` user with an empty password.

## What you'll see

Open http://127.0.0.1:18080/ after `Start.ps1`: the Ingram Trials invoice desk, with three customers, three products and one invoice in the sample data. The three orders the demo page follows, priced with Preview invoice:

| Order | Preview |
|---|---|
| Aster Office Supplies, 100 × PAPER-A4 | 931.00 + GST 83.79 = **1014.79** |
| Merlion Retail, 10 × TONER-BK | 485.00 + GST 43.65 = **528.65** |
| Straits Workshop, 3 × CABLE-USB and 101 × PAPER-A4 | 999.81 + GST 89.98 = **1089.79** |

Save the first and it is booked at a different total: the preview gives the bulk discount at 100 items, the save only above 100. That is one of the problems Bob found.

To send the same orders without the screen, for example to compare them with a migration target:

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

If you would rather not install Java 8, the demo page has a [recorded copy of the desk](https://yeokimsiang.github.io/bob-in-action-v2/legacy-desk/#use) that answers these orders as the real app does.
