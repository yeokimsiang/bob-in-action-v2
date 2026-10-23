param(
  [ValidateSet('invoices','credit-notes')][string]$Job,
  [int]$Port=18080
)
$ErrorActionPreference='Stop'
if (!$Job) { throw 'Specify -Job invoices or -Job credit-notes' }
$url="http://127.0.0.1:$Port/api/jobs/$Job"
Invoke-RestMethod -Method Post -Uri $url -ContentType 'application/json' -Body '{}' | ConvertTo-Json
