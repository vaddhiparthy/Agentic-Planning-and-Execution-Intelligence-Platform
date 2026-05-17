param(
  [string]$ProjectRoot = 'C:\Users\vaddh\OneDrive\Projects\Creations\ASTRA-X-Overthinker',
  [string]$ComposeDir  = 'C:\docker\homeagent',
  [string]$Container   = 'overthinker'
)

$cfg = Join-Path $ProjectRoot 'app\config.yaml'
if (!(Test-Path $cfg)) { Write-Host "config.yaml not found: $cfg" -f Red; exit 1 }

# 1) Set interval to 15 minutes
$text = Get-Content -Raw $cfg
$text = $text -replace '(?m)^iteration_interval_minutes:\s*\d+\s*$', 'iteration_interval_minutes: 15'
if ($text -notmatch 'iteration_interval_minutes:') {
  $text += "`r`niteration_interval_minutes: 15`r`n"
}
$text | Set-Content -Encoding UTF8 $cfg
Write-Host "✔ Interval set to 15 min in config.yaml"

# 2) Rebuild & restart (picks up config)
Push-Location $ComposeDir
docker compose up -d --build | Out-Null
Pop-Location
Start-Sleep -Seconds 2
Write-Host "✔ Container rebuilt & restarted"

# 3) Show scheduler status and run one pass
try {
  $s = Invoke-WebRequest http://localhost:7000/api/scheduler/status -UseBasicParsing -TimeoutSec 10
  Write-Host "Scheduler: $($s.Content)"
} catch {
  Write-Host "Scheduler status not reachable yet."
}

try {
  $r = Invoke-WebRequest http://localhost:7000/api/run_once -Method POST -UseBasicParsing -TimeoutSec 30
  Write-Host "Run once: $($r.Content)"
} catch {
  Write-Host "Run-once API not reachable (try again in a few seconds)."
}
