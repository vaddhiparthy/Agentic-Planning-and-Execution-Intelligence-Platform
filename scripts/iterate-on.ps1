$ErrorActionPreference='Stop'
. "\common.ps1"
$s = Invoke-Overthinker -Method 'GET' -Path '/api/scheduler/status'
if (-not $s) { Write-Host 'Status endpoint not reachable.' -ForegroundColor Red; exit 1 }
if ($s.enabled) { Write-Host ('Scheduler already ON. Next: ' + $s.next_run) -ForegroundColor Green; exit 0 }
$t = Invoke-Overthinker -Method 'POST' -Path '/api/scheduler/toggle'
if (-not $t -or -not $t.ok) { Write-Host 'Failed to turn ON.' -ForegroundColor Red; exit 1 }
$s2 = Invoke-Overthinker -Method 'GET' -Path '/api/scheduler/status'
Write-Host ('Turned ON. Next: ' + ($s2?.next_run ?? '—')) -ForegroundColor Green
