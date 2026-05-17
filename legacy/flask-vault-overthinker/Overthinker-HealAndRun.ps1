param(
  [string]$ComposeDir  = 'C:\docker\homeagent',
  [string]$Container   = 'overthinker'
)

$ErrorActionPreference = 'Stop'
function OK($m){ Write-Host ("OK  " + $m) -ForegroundColor Green }
function Info($m){ Write-Host ("• "  + $m) -ForegroundColor Yellow }
function Err($m){ Write-Host ("X   " + $m) -ForegroundColor Red }

# Bring stack up
Push-Location $ComposeDir
docker compose up -d | Out-Null
Pop-Location
OK "Compose up -d issued"

# Wait until container is Up
$up = $false
foreach ($i in 1..40) {
  Start-Sleep -Seconds 1
  $status = docker ps --filter "name=$Container" --format "{{.Status}}"
  if ($status -match '^Up ') { $up = $true; break }
}
if (-not $up) { Err "Container didn't reach 'Up'. See: docker logs $Container"; exit 1 }
OK "Container is running"

# Heal scheduler (resume if paused)
$hasStatus = $true
try {
  $s = Invoke-RestMethod -Uri "http://localhost:7000/api/scheduler/status" -Method GET -TimeoutSec 10
  $nr = $null; if ($s -and $s.PSObject.Properties.Name -contains 'next_run') { $nr = $s.next_run }
  if ($null -eq $nr) { $nr = "-" }
  Info ("Scheduler enabled: {0}, next_run: {1}" -f $s.enabled, $nr)

  if (-not $s.enabled) {
    Info "Resuming scheduler…"
    Invoke-RestMethod -Uri "http://localhost:7000/api/scheduler/toggle" -Method POST -TimeoutSec 10 | Out-Null
    Start-Sleep -Seconds 1
    $s2 = Invoke-RestMethod -Uri "http://localhost:7000/api/scheduler/status" -Method GET -TimeoutSec 10
    $nr2 = $null; if ($s2 -and $s2.PSObject.Properties.Name -contains 'next_run') { $nr2 = $s2.next_run }
    if ($null -eq $nr2) { $nr2 = "-" }
    OK ("Scheduler resumed. next_run: {0}" -f $nr2)
  }
} catch {
  $hasStatus = $false
  Info "Scheduler status API not reachable; continuing."
}

# Trigger one run (API first, fallback to python -c)
$ran = $false
if ($hasStatus) {
  try {
    $r = Invoke-RestMethod -Uri "http://localhost:7000/api/run_once" -Method POST -TimeoutSec 30
    if ($r.ok -and $r.ran) { OK ("Manual run via API ok @ {0}" -f $r.ts); $ran = $true }
  } catch {
    Info "run_once API failed; will try python -c."
  }
}
if (-not $ran) {
  $py = 'import app; app.iterate_once(); print("ran")'
  $out = docker exec $Container python -c $py 2>&1
  if ($LASTEXITCODE -eq 0) { OK "Manual run via python ok" } else { Err "Manual run failed:`n$out" }
}

# Logs
Info "Last 80 container logs:"
docker logs --tail 80 $Container

OK "Healed and ran once."
