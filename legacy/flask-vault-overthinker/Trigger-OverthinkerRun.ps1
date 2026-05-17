param(
  [string]$Container = 'overthinker'
)

$ErrorActionPreference = 'Stop'
function OK($m){ Write-Host ("OK  " + $m) -ForegroundColor Green }
function Info($m){ Write-Host ("• "  + $m) -ForegroundColor Yellow }
function Err($m){ Write-Host ("X   " + $m) -ForegroundColor Red }

# Quick check: is the container up?
$status = (docker ps --filter "name=$Container" --format "{{.Status}}")
if ($status -notmatch '^Up ') {
  Err "Container '$Container' is not Up (status: '$status'). Start your stack first (docker compose up -d)."
  exit 1
}
OK "Container is running"

# Try API first
$ran = $false
try {
  $r = Invoke-RestMethod -Uri "http://localhost:7000/api/run_once" -Method POST -TimeoutSec 30
  if ($r.ok -and $r.ran) {
    OK ("Manual run via API ok @ {0}" -f $r.ts)
    $ran = $true
  } else {
    Info "API responded but didn't confirm run; falling back to python."
  }
} catch {
  Info "API not reachable; falling back to python -c."
}

# Fallback: in-container python
if (-not $ran) {
  $py = 'import app; app.iterate_once(); print("ran")'
  $out = docker exec $Container python -c $py 2>&1
  if ($LASTEXITCODE -eq 0) {
    OK "Manual run via python ok"
  } else {
    Err "Manual run failed:`n$out"
    exit 1
  }
}

# Show recent logs for confirmation
Info "Last 60 container log lines:"
docker logs --tail 60 $Container
