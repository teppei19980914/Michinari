@echo off
rem Build, package, and zip the distribution (see scripts/build_package.py).
rem You will be prompted to enter the release version while this runs.
rem Uploading the zip to GitHub Releases is a manual step (scripts/publish_release.py).
cd /d "%~dp0"

rem "uv sync" (run implicitly by "uv run") occasionally fails to remove files
rem under .venv with an access-denied error while this repo lives inside a
rem OneDrive-synced folder (OneDrive briefly locks files during background
rem sync). Retry just the sync step a few times before giving up; the actual
rem test/build below only runs once the environment is confirmed in sync.
rem NOTE: a different OneDrive-related failure ("os error 396", hardlinking a
rem cloud file) is NOT fixed by retrying; it is avoided up front by
rem link-mode = "copy" in pyproject.toml ([tool.uv]). See OPERATIONS.md 7.4.
rem NOTE: every check below uses the single-line "if COND goto label" form.
rem "goto" inside a parenthesized if-block can corrupt cmd.exe's parser and
rem make the whole script abort silently, so no goto ever appears inside ( ).
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
echo reached: check the network connection and run build.bat again.
echo.
pause
exit /b 1

:sync_done
uv run --no-sync python scripts\build_package.py
if %errorlevel% neq 0 (
    echo.
    echo Build failed. See the log above for details.
) else (
    echo.
    echo Build completed successfully.
)
pause
