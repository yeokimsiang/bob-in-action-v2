param([int]$Year=2026,[int]$Port=18080,[string]$OutputPath)
# Historical branch handoff
$ErrorActionPreference='Stop'
if (!$OutputPath) { throw 'Specify an output CSV path' }
$invoices=Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/invoices"
$invoices | Where-Object { $_.invoiceDate -like "$Year-*" } |
  Select-Object invoiceNo,customerName,invoiceDate,total |
  Export-Csv -LiteralPath $OutputPath -NoTypeInformation
