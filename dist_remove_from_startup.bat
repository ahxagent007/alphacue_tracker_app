@echo off
:: =============================================================================
:: remove_from_startup.bat — Removes TrackerApp from Windows Startup
:: Keep this file in the SAME folder as TrackerApp.exe
:: =============================================================================

title TrackerApp Startup Remover

echo.
echo  ============================================
echo   TrackerApp — Remove from Startup
echo  ============================================
echo.

set "SHORTCUT_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\TrackerApp.lnk"

if not exist "%SHORTCUT_PATH%" (
    echo  TrackerApp is not in startup — nothing to remove.
    echo.
    pause
    exit /b 0
)

del "%SHORTCUT_PATH%"

if not exist "%SHORTCUT_PATH%" (
    echo  SUCCESS — TrackerApp removed from startup.
    echo.
    echo  The app will no longer start automatically.
    echo.
) else (
    echo  [ERROR] Could not remove shortcut.
    echo  Try right-clicking and choosing "Run as administrator"
    echo.
)

pause
