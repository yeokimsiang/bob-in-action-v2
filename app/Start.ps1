param(
  [int]$Port = 18080,
  [string]$DataDir,
  [switch]$NoBuild,
  [switch]$Offline
)
$ErrorActionPreference='Stop'
if ($Port -lt 1 -or $Port -gt 65535) { throw 'Port must be 1-65535' }
$caseRoot=(Resolve-Path -LiteralPath $PSScriptRoot).Path
if (((Get-Item -LiteralPath $caseRoot).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "App root is a reparse point: $caseRoot" }
$runtime=Join-Path $caseRoot 'runtime'
[IO.Directory]::CreateDirectory($runtime) | Out-Null
if (((Get-Item -LiteralPath $runtime).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Runtime root is a reparse point: $runtime" }
$statePath=Join-Path $runtime ("server-$Port.json")
if (Test-Path -LiteralPath $statePath) { throw "Existing owned state: $statePath. Run Stop.ps1 or inspect it." }
if (!$DataDir) { $DataDir=Join-Path $runtime 'data' }
if (![System.IO.Path]::IsPathRooted($DataDir)) { $DataDir=Join-Path $caseRoot $DataDir }
$DataDir=[System.IO.Path]::GetFullPath($DataDir)
if ($DataDir -match '[;\r\n]') { throw 'DataDir contains characters unsafe in the JDBC URL or command line' }
$ownedRuntime=[System.IO.Path]::GetFullPath($runtime)
$comparison=[StringComparison]::OrdinalIgnoreCase
$inRuntime=$DataDir.Equals($ownedRuntime,$comparison) -or $DataDir.StartsWith($ownedRuntime + [IO.Path]::DirectorySeparatorChar,$comparison)
if (!$inRuntime) { throw "DataDir must be inside app/runtime: $DataDir" }
$walk=$caseRoot
$tail=$DataDir.Substring($caseRoot.Length).TrimStart([IO.Path]::DirectorySeparatorChar)
$parts=if ($tail) { $tail.Split([IO.Path]::DirectorySeparatorChar) } else { @() }
foreach ($part in @('') + $parts) {
  if ($part) { $walk=Join-Path $walk $part }
  if (Test-Path -LiteralPath $walk) {
    if (((Get-Item -LiteralPath $walk).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
      throw "DataDir traverses a reparse point: $walk"
    }
  }
}
[IO.Directory]::CreateDirectory($DataDir) | Out-Null
if (!$NoBuild) { & (Join-Path $caseRoot 'Build.ps1') -Offline:$Offline }
$jar=Join-Path $caseRoot 'target\base-desk-1.0.0.jar'
if (!(Test-Path -LiteralPath $jar)) { throw "Built JAR missing: $jar" }
$jar=(Resolve-Path -LiteralPath $jar).Path
$javaHome8=if ($env:JAVA8_HOME) { $env:JAVA8_HOME } else { 'C:\Program Files\Eclipse Adoptium\jdk-8.0.504.1-hotspot' }
$java=Join-Path $javaHome8 'bin\java.exe'
if (!(Test-Path -LiteralPath $java)) { throw "Java 8 unavailable: $java (set JAVA8_HOME)" }
$connection=Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($connection) { throw "Port $Port is already in use; no process was stopped" }
$logPath=Join-Path $runtime ("ingram-trials-base-$Port.log")
$oldPort=[Environment]::GetEnvironmentVariable('DEMO_PORT','Process')
$oldData=[Environment]::GetEnvironmentVariable('DEMO_DATA_DIR','Process')
try {
  $env:DEMO_PORT="$Port"
  $env:DEMO_DATA_DIR=$DataDir.Replace('\','/')
  $process=Start-Process -FilePath $java -ArgumentList @('-jar',('"' + $jar + '"'),('"--logging.file.name=' + $logPath.Replace('\','/') + '"')) -WorkingDirectory 'C:\' -WindowStyle Hidden -PassThru
} finally {
  [Environment]::SetEnvironmentVariable('DEMO_PORT',$oldPort,'Process')
  [Environment]::SetEnvironmentVariable('DEMO_DATA_DIR',$oldData,'Process')
}
$state=[ordered]@{pid=$process.Id;port=$Port;dataDir=$DataDir;javaHome=$javaHome8;jarPath=$jar;startedAt=[DateTimeOffset]::UtcNow.ToString('o');logPath=$logPath}
$state | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
$url="http://127.0.0.1:$Port/api/health"
for ($i=0;$i -lt 40;$i++) {
  Start-Sleep -Milliseconds 500
  if ($process.HasExited) { throw "Server exited. See $logPath if Spring logging initialized" }
  try {
    $health=Invoke-RestMethod -Uri $url -TimeoutSec 2
    if ($health.status -eq 'UP' -and $health.case -eq 'BASE') { Write-Output "App ready at http://127.0.0.1:$Port/"; return }
  } catch {}
}
throw "Server did not become ready. See $logPath if Spring logging initialized"
