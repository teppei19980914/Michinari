@echo off
chcp 65001 >nul
cd /d "%~dp0"
uv run python scripts\build_package.py
if %errorlevel% neq 0 (
    echo.
    echo ビルドに失敗しました。上記のログを確認してください。
) else (
    echo.
    echo ビルドが完了しました。
)
pause
