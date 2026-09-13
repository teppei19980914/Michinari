@echo off
rem Bundled into the distribution package as "Michinari-console.bat"
rem (copied by scripts/build_package.py, see assemble_launcher).
rem
rem THIS IS NOT THE NORMAL WAY TO START MICHINARI. Users double-click
rem Michinari.exe, which shows no console window and stays in the notification
rem area (system tray). This file is for developers and for troubleshooting: it
rem starts the same exe with the --console option, so the running log is shown
rem on screen instead of only being written to the log file under
rem %LOCALAPPDATA%\Michinari\data\logs\.
rem
rem Messages are ASCII on purpose: this file runs under the console's OEM code
rem page (932 on Japanese Windows), where UTF-8 text would come out garbled.
rem
rem The exe is launched by its full path rather than by bare name: cmd.exe does
rem not search the current directory when NoDefaultCurrentDirectoryInExePath is
rem set, so a bare "Michinari.exe" fails with "is not recognized" on machines
rem where that variable is present.
cd /d "%~dp0"
"%~dp0Michinari.exe" --console
if errorlevel 1 (
    echo.
    echo Michinari failed to start. Please report the error shown above.
    echo.
    pause
)
