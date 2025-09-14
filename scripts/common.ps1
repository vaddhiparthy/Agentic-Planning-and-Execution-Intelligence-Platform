param(
  [string]\ = 'overthinker',
  [string]\      = 'http://localhost:7000'
)

function Invoke-Overthinker {
  param([string]\='GET',[string]\='/',[hashtable]\=\)
  try {
    if (\) { return Invoke-RestMethod -Method \ -Uri (\ + \) -Body (\ | ConvertTo-Json) -ContentType 'application/json' -TimeoutSec 15 }
    else       { return Invoke-RestMethod -Method \ -Uri (\ + \) -TimeoutSec 10 }
  } catch {
    try {
      # Linux container fallback via sh -lc
      \ = if (\) {
        "curl -s -m 10 -X \ -H 'Content-Type: application/json' -d '" + (\ | ConvertTo-Json -Compress).Replace("'","'\"'\"'") + "' http://127.0.0.1:7000" + \
      } else {
        "curl -s -m 10 http://127.0.0.1:7000" + \
      }
      \ = (docker exec \ sh -lc ""\"")
      if ([string]::IsNullOrWhiteSpace(\)) { return \ }
      return \ | ConvertFrom-Json
    } catch { return \ }
  }
}
