@echo off
rem Run the pre-release smoke test (see scripts/release_smoke.py).
rem
rem Run this BEFORE release.bat. It checks the two things the test suites
rem cannot cover:
rem   1. the app actually starts and answers (schema upgrade + seeding included)
rem   2. the existing user database can be migrated without losing rows
rem
rem Add --package to also extract the latest dist zip and start the real
rem Michinari.exe. That is off by default because the packaged app bundles the
rem frontend and therefore opens a browser window on startup.
rem
rem Both run against throwaway copies: the app starts on a free port with a
rem temporary database, and the migration is applied to a copy of data/michinari.db.
rem Nothing touches a running app or the real data.
rem
rem See build.bat for why "uv sync" is retried (OneDrive file locking) and why
rem every check below uses the single-line "if COND goto label" form.
cd /d "%~dp0"

set SYNC_ATTEMPTS=0

:sync_retry
set /a SYNC_ATTEMPTS+=1
uv sync
if not errorlevel 1 goto sync_done

if %SYNC_ATTEMPTS% GEQ 5 goto sync_failed

echo.
echo uv sync failed (attempt %SYNC_ATTEMPTS%/5). Usual causes: OneDrive
echo briefly locking files under .venv, or a temporary network/DNS failure
echo reaching pypi.org. Retrying in 3 seconds...
timeout /t 3 /nobreak >nul
goto sync_retry

:sync_failed
echo.
echo uv sync failed %SYNC_ATTEMPTS% times in a row. Aborting.
echo If the log above shows "os error 396" (hardlink to a cloud file),
echo run "uv cache clean" once and try again. See OPERATIONS.md 7.4.
echo If it shows "dns error" / "os error 11001", pypi.org could not be
echo reached: check the network connection and run smoke.bat again.
echo.
pause
exit /b 1

:sync_done
uv run --no-sync python scripts\release_smoke.py
if %errorlevel% neq 0 (
    echo.
    echo Smoke test failed. Fix the problems above before running release.bat.
) else (
    echo.
    echo Smoke test passed. You can run release.bat now.
)
pause
