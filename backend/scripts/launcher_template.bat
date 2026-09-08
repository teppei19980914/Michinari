@echo off
rem Launcher bundled into the distribution package as "Michinari.bat"
rem (copied by scripts/build_package.py, see assemble_launcher).
rem
rem Michinari.exe writes startup failures (e.g. a database migration error) to
rem this console and exits with a non-zero code. Without the pause below the
rem window closes the instant that happens, so the user only sees a black box
rem flash and has no way to report what went wrong (observed 2026-09-08).
rem Keep the window open on failure only; a normal shutdown must not nag.
rem
rem Messages are ASCII on purpose: this file runs under the console's OEM code
rem page (932 on Japanese Windows), where UTF-8 text would come out garbled.
rem
rem The exe is launched by its full path rather than by bare name: cmd.exe does
rem not search the current directory when NoDefaultCurrentDirectoryInExePath is
rem set, so a bare "Michinari.exe" fails with "is not recognized" on machines
rem where that variable is present.
cd /d "%~dp0"
"%~dp0Michinari.exe"
if errorlevel 1 (
    echo.
    echo Michinari failed to start. Please report the error shown above.
    echo.
    pause
)
