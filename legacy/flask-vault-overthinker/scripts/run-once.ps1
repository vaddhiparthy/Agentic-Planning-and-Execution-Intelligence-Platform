$ErrorActionPreference='Stop'
. "\common.ps1"
$r = Invoke-Overthinker -Method 'POST' -Path '/api/run_once'
if ($r -and $r.ok) { Write-Host ('Run triggered at ' + ($r.ts ?? (Get-Date))) -ForegroundColor Green; exit 0 }
# Fallback: direct python call in container
try {
  docker exec overthinker sh -lc ""python - <<'PY'
import sys; sys.path.insert(0,'/app')
import app
app.iterate_once()
print('Manual iteration triggered.')
PY"" | Out-Null
  Write-Host 'Run triggered via python fallback.' -ForegroundColor Green
  exit 0
} catch { Write-Host 'Run-once failed (API + fallback).' -ForegroundColor Red; exit 1 }
