param(
  [string]$ProjectRoot = 'C:\Users\vaddh\OneDrive\Projects\Creations\ASTRA-X-Overthinker',
  [string]$ComposeDir  = 'C:\docker\homeagent',
  [string]$Container   = 'overthinker',
  [int]$IntervalMinutes = 15
)

$ErrorActionPreference = 'Stop'
function OK($m){ Write-Host ("OK  " + $m) -ForegroundColor Green }
function Info($m){ Write-Host ("• "  + $m) -ForegroundColor Yellow }
function Err($m){ Write-Host ("X   " + $m) -ForegroundColor Red }

# Paths
$CfgPath   = Join-Path (Join-Path $ProjectRoot 'app') 'config.yaml'
$ComposeYml = Join-Path $ComposeDir 'docker-compose.yml'

# --- Guard files ---
if (!(Test-Path $CfgPath))    { Err "Missing: $CfgPath"; exit 1 }
if (!(Test-Path $ComposeYml)) { Err "Missing: $ComposeYml"; exit 1 }

# --- Ensure interval = 15 in config.yaml (idempotent) ---
try {
  $cfg = Get-Content -Raw $CfgPath
  if ($cfg -match 'iteration_interval_minutes\s*:\s*\d+') {
    $cfg = [regex]::Replace($cfg, 'iteration_interval_minutes\s*:\s*\d+', "iteration_interval_minutes: $IntervalMinutes")
  } else {
    $cfg = $cfg.TrimEnd() + "`r`niteration_interval_minutes: $IntervalMinutes`r`n"
  }
  $cfg | Set-Content -Encoding UTF8 $CfgPath
  OK "Iteration interval set to $IntervalMinutes minutes in config.yaml"
} catch {
  Err "Failed updating config.yaml: $($_.Exception.Message)"; exit 1
}

# --- (Re)start container normally ---
try {
  Push-Location $ComposeDir
  docker compose up -d | Out-Null
  Pop-Location
  OK "Compose up -d issued"
} catch {
  Err "docker compose up failed: $($_.Exception.Message)"; exit 1
}

# --- Wait until container is 'Up' ---
$up = $false
foreach ($i in 1..30) {
  Start-Sleep -Seconds 1
  $status = docker ps --filter "name=$Container" --format "{{.Status}}"
  if ($status -match '^Up ') { $up = $true; break }
}
if (-not $up) {
  Err "Container never reached 'Up'. Run 'docker logs $Container' to investigate."; exit 1
}
OK "Container is running"

# --- Hit scheduler status ---
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

# --- Trigger one iteration now (API first, fallback to python -c) ---
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

# --- Show last logs so you can confirm activity ---
Info "Last 80 container logs:"
docker logs --tail 80 $Container

Write-Host ""
OK "Done. The scheduler should now run every $IntervalMinutes minutes. You can re-check with:"
Write-Host "    Invoke-RestMethod http://localhost:7000/api/scheduler/status -Method GET"
