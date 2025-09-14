@echo off
REM Overthinker-Trigger.cmd — fire one iteration immediately

REM Make sure Docker Desktop is running before this.
docker exec overthinker python -c import sys; sys.path.insert(0,'app'); import app; app.iterate_once(); print('Manual iteration triggered.')
if errorlevel 1 (
  echo ERROR manual iteration failed. Showing last 40 lines of logs...
  docker logs --tail 40 overthinker
) else (
  echo OK manual iteration executed.
)
echo.
pause
