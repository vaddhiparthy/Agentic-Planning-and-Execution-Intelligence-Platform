# Overthinker-Trigger.ps1
$Container = 'overthinker'

# Build the Python command with proper quoting
$cmd = "import sys; sys.path.insert(0,'/app'); import app; app.iterate_once(); print('Manual iteration triggered.')"

# Run it inside the container
docker exec $Container python -c "$cmd"

if ($LASTEXITCODE -eq 0) {
  Write-Host "OK: manual iteration executed."
} else {
  Write-Host "ERROR: manual iteration failed. Check: docker logs -n 100 overthinker"
}
