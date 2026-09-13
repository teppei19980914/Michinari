@echo off
rem Run the release gate, then build and stage a draft GitHub Release.
rem
rem Run this AFTER merging your work into main (see OPERATIONS.md 7.4):
rem   1. develop on dev/YYYY-MM-DD
rem   2. merge into main (merge the PR on GitHub)
rem   3. run this file  <- everything below is automatic
rem   4. overwrite the release notes on the GitHub Releases page
rem   5. press "Publish release" to distribute
rem
rem The release gate runs the test suites AND the pre-release smoke (the app
rem really starts, and the existing user database still migrates). The smoke is
rem part of the gate rather than a separate step so it cannot be forgotten.
rem See scripts/release_smoke.py; smoke.bat runs the same checks on their own.
rem
rem You do NOT need to switch to main first: this checks out main and brings it
rem up to date on its own. It refuses to do so when your work is not yet merged,
rem because switching then would package changes that do not include your work.
rem
rem The release is created as a DRAFT so a release with unwritten notes is never
rem visible to users. The tag and the zip are attached to the draft already, so
rem step 4 is the only manual work left.
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
echo reached: check the network connection and run release.bat again.
echo.
pause
exit /b 1

:sync_done
uv run --no-sync python scripts\release.py --skip-merge --draft
if %errorlevel% neq 0 (
    echo.
    echo Release staging failed. See the log above for details.
) else (
    echo.
    echo Draft release is ready. Write the notes on GitHub, then publish.
)
pause
