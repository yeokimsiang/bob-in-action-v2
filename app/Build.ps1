param([switch]$Offline)
$ErrorActionPreference = 'Stop'
# Java 8 (the app's target) and Maven. Set JAVA8_HOME or MAVEN_CMD to override the defaults.
$javaHome8 = if ($env:JAVA8_HOME) { $env:JAVA8_HOME } else { 'C:\Program Files\Eclipse Adoptium\jdk-8.0.504.1-hotspot' }
$maven = if ($env:MAVEN_CMD) { $env:MAVEN_CMD } elseif (Get-Command mvn -ErrorAction SilentlyContinue) { (Get-Command mvn).Source } else { 'C:\tools\apache-maven-3.10.0\bin\mvn.cmd' }
if (!(Test-Path -LiteralPath (Join-Path $javaHome8 'bin\javac.exe'))) { throw "Java 8 unavailable: $javaHome8 (set JAVA8_HOME)" }
if (!(Test-Path -LiteralPath $maven)) { throw "Maven unavailable: $maven (set MAVEN_CMD or put mvn on PATH)" }
$env:JAVA_HOME = $javaHome8
$env:Path = (Join-Path $javaHome8 'bin') + ';' + $env:Path
Push-Location -LiteralPath $PSScriptRoot
try {
  $args = @('-B','-ntp')
  if ($Offline) { $args += '-o' }
  $args += @('clean','verify')
  & $maven @args
  if ($LASTEXITCODE -ne 0) { throw "Maven failed with exit code $LASTEXITCODE" }
} finally { Pop-Location }
