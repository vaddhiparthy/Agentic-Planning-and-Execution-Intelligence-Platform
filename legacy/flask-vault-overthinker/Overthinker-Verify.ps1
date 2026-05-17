param(
  [string]$Container = 'overthinker',
  [string]$VaultPath = '/vault'
)

$ErrorActionPreference = 'Stop'
function OK($m){ Write-Host "✔ $m" -ForegroundColor Green }
function Info($m){ Write-Host "• $m" -ForegroundColor Yellow }
function Err($m){ Write-Host "✖ $m" -ForegroundColor Red }

# 1. Container status
$running = docker ps --filter "name=$Container" --format "{{.Status}}"
if(-not $running){ Err "Container $Container not running"; exit 1 }
OK "Container is running ($running)"

# 2. Scheduler status
try {
  $s = Invoke-RestMethod -Uri "http://localhost:7000/api/scheduler/status" -TimeoutSec 10 -Method GET
  OK ("Scheduler: enabled={0}, next_run={1}" -f $s.enabled, $s.next_run)
} catch {
  Info "Scheduler API not reachable"
}

# 3. Trigger a manual run
try {
  $r = Invoke-RestMethod -Uri "http://localhost:7000/api/run_once" -TimeoutSec 20 -Method POST
  if($r.ok){ OK "Manual run succeeded @ $($r.ts)" }
} catch {
  Err "Manual run API failed"
}

# 4. Verify vault files
$out = docker exec $Container sh -lc "ls -1 $VaultPath/items | head -5"
if($LASTEXITCODE -eq 0 -and $out){
  OK "Found item files in vault/items (showing first 5):"
  $out
} else {
  Err "No item files found in vault/items"
}

$outGoals = docker exec $Container sh -lc "ls -l $VaultPath/goals || true"
OK "Goals dir content:"
$outGoals
