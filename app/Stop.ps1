param([int]$Port=18080)
$ErrorActionPreference='Stop'
$caseRoot=(Resolve-Path -LiteralPath $PSScriptRoot).Path
$statePath=Join-Path $caseRoot ("runtime\server-$Port.json")
if (!(Test-Path -LiteralPath $statePath)) { throw "No app state file for port $Port" }
$state=Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
if ($state.port -ne $Port -or !$state.jarPath -or !$state.javaHome -or !$state.pid) { throw 'Invalid server state; no process stopped' }
$jar=[System.IO.Path]::GetFullPath($state.jarPath)
$expectedJar=Join-Path $caseRoot 'target\base-desk-1.0.0.jar'
if ($jar -ne [System.IO.Path]::GetFullPath($expectedJar)) { throw 'State JAR is outside this app folder; no process stopped' }
$process=Get-CimInstance Win32_Process -Filter "ProcessId = $($state.pid)"
if ($process) {
  $expectedJava=Join-Path $state.javaHome 'bin\java.exe'
  if ([System.IO.Path]::GetFullPath($process.ExecutablePath) -ne [System.IO.Path]::GetFullPath($expectedJava) -or
      !$process.CommandLine.Contains($jar)) { throw 'PID command does not match owned app server; no process stopped' }
  Stop-Process -Id $state.pid
  for ($i=0;$i -lt 30;$i++) {
    Start-Sleep -Milliseconds 200
    if (!(Get-Process -Id $state.pid -ErrorAction SilentlyContinue)) { break }
  }
  if (Get-Process -Id $state.pid -ErrorAction SilentlyContinue) { throw 'Owned process has not exited; state retained' }
}
Remove-Item -LiteralPath $statePath
Write-Output "App server stopped on port $Port"
