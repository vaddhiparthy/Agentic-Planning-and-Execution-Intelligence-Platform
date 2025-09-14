$ErrorActionPreference='Stop'
. "\common.ps1"
$s = Invoke-Overthinker -Method 'GET' -Path '/api/scheduler/status'
if (-not $s) { Write-Host 'Status endpoint not reachable.' -ForegroundColor Red; exit 1 }
if (-not $s.enabled) { Write-Host 'Scheduler already OFF.' -ForegroundColor Yellow; exit 0 }
$t = Invoke-Overthinker -Method 'POST' -Path '/api/scheduler/toggle'
if (-not $t -or -not $t.ok) { Write-Host 'Failed to turn OFF.' -ForegroundColor Red; exit 1 }
Write-Host 'Turned OFF.' -ForegroundColor Green
