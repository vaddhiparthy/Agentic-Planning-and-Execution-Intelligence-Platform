param(
  [string]$ProjectRoot = 'C:\Users\vaddh\OneDrive\Projects\Creations\ASTRA-X-Overthinker',
  [string]$ComposeDir  = 'C:\docker\homeagent',
  [string]$Container   = 'overthinker',
  [int]$Minutes
)

$ErrorActionPreference = 'Stop'
function OK($m){ Write-Host ("OK  " + $m) -ForegroundColor Green }
function Info($m){ Write-Host ("• "  + $m) -ForegroundColor Yellow }
function Err($m){ Write-Host ("X   " + $m) -ForegroundColor Red }

# Ask if not passed
if (-not $Minutes) {
  $raw = Read-Host "Enter run frequency in minutes (e.g., 15)"
  if (-not ($raw -as [int])) { Err "Invalid number: '$raw'"; exit 1 }
  $Minutes = [int]$raw
}
OK "Setting frequency to every $Minutes minute(s)"

# Paths
$CfgPath = Join-Path $ProjectRoot 'app\config.yaml'
if (!(Test-Path $CfgPath)) { Err "config.yaml not found: $CfgPath"; exit 1 }

# Backup + update config
Copy-Item $CfgPath "$($CfgPath).bak_$(Get-Date -Format yyyyMMdd-HHmmss)" -Force
$cfg = Get-Content -Raw $CfgPath
if ($cfg -match 'iteration_interval_minutes\s*:\s*\d+') {
  $cfg = [regex]::Replace($cfg, 'iteration_interval_minutes\s*:\s*\d+', "iteration_interval_minutes: $Minutes")
} else {
  $cfg = $cfg.TrimEnd() + "`r`niteration_interval_minutes: $Minutes`r`n"
}
Set-Content -Encoding UTF8 $CfgPath $cfg
OK "Updated iteration_interval_minutes in config.yaml"

# Rebuild & restart
if (!(Test-Path $ComposeDir)) { Err "Compose dir not found: $ComposeDir"; exit 1 }
Push-Location $ComposeDir
docker compose up -d --build | Out-Null
Pop-Location

# Wait for container Up
Info "Waiting for container to be Up…"
$up = $false
foreach($i in 1..30){
  Start-Sleep -Seconds 1
  $status = docker ps --filter "name=$Container" --format "{{.Status}}"
  if ($status -match '^Up ') { $up = $true; break }
}
if (-not $up) {
  Err "Container did not reach 'Up'. Run: docker logs -n 200 $Container"
  exit 1
}
OK "Container is Up"

# Ensure scheduler is enabled
$hasApi = $true
try {
  $s = Invoke-RestMethod -Uri "http://localhost:7000/api/scheduler/status" -TimeoutSec 10 -Method GET
  $nrt = ($s | Select-Object -ExpandProperty next_run -ErrorAction SilentlyContinue); if (-not $nrt) { $nrt = "-" }
  Info ("Scheduler enabled: {0}, next_run: {1}" -f $s.enabled, $nrt)
  if (-not $s.enabled) {
    Info "Resuming scheduler…"
    Invoke-RestMethod -Uri "http://localhost:7000/api/scheduler/toggle" -TimeoutSec 10 -Method POST | Out-Null
    Start-Sleep -Seconds 1
    $s2 = Invoke-RestMethod -Uri "http://localhost:7000/api/scheduler/status" -TimeoutSec 10 -Method GET
    $nrt2 = ($s2 | Select-Object -ExpandProperty next_run -ErrorAction SilentlyContinue); if (-not $nrt2) { $nrt2 = "-" }
    OK ("Scheduler resumed. next_run: {0}" -f $nrt2)
  }
} catch {
  $hasApi = $false
  Info "Scheduler status API not reachable; proceeding to manual run anyway."
}

# Trigger one run (API first, fallback to python -c)
$ran = $false
if ($hasApi) {
  try {
    $r = Invoke-RestMethod -Uri "http://localhost:7000/api/run_once" -Method POST -TimeoutSec 30
    if ($r.ok -and $r.ran) { OK ("Manual run via API ok @ {0}" -f $r.ts); $ran = $true }
  } catch {
    Info "run_once API not available; trying python -c."
  }
}
if (-not $ran) {
  $py = 'import app; app.iterate_once(); print("ran")'
  $out = docker exec $Container python -c $py 2>&1
  if ($LASTEXITCODE -eq 0) { OK "Manual run via python ok" } else { Err "Manual run failed:`n$out"; exit 1 }
}

OK "Done. It should now run every $Minutes minute(s)."
