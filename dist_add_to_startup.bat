@echo off
:: =============================================================================
:: add_to_startup.bat — Adds TrackerApp.exe to Windows Startup
:: Keep this file in the SAME folder as TrackerApp.exe
:: Run once by right-clicking → "Run as administrator"
:: =============================================================================

title TrackerApp Startup Installer

echo.
echo  ============================================
echo   TrackerApp — Startup Installer
echo  ============================================
echo.

:: ── Everything is relative to THIS .bat file's folder ───────────────────────
set "HERE=%~dp0"
set "EXE_PATH=%HERE%TrackerApp.exe"

:: ── Check TrackerApp.exe exists in the same folder ───────────────────────────
if not exist "%EXE_PATH%" (
    echo  [ERROR] TrackerApp.exe not found in this folder:
    echo          %HERE%
    echo.
    echo  Make sure add_to_startup.bat is in the same
    echo  folder as TrackerApp.exe
    echo.
    pause
    exit /b 1
)

:: ── Create shortcut in Windows Startup folder ────────────────────────────────
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_PATH=%STARTUP_DIR%\TrackerApp.lnk"

echo  Creating startup shortcut...

powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $s  = $ws.CreateShortcut('%SHORTCUT_PATH%'); ^
   $s.TargetPath       = '%EXE_PATH%'; ^
   $s.WorkingDirectory = '%HERE%'; ^
   $s.WindowStyle      = 7; ^
   $s.Description      = 'TrackerApp background capture service'; ^
   $s.Save()"

:: ── Result ───────────────────────────────────────────────────────────────────
if exist "%SHORTCUT_PATH%" (
    echo.
    echo  ============================================
    echo   SUCCESS — TrackerApp added to startup!
    echo  ============================================
    echo.
    echo  TrackerApp will start automatically on login.
    echo.
    echo  Shortcut saved to:
    echo    %SHORTCUT_PATH%
    echo.
    echo  To remove it, run remove_from_startup.bat
    echo.
) else (
    echo.
    echo  [ERROR] Shortcut could not be created.
    echo  Right-click this file and choose "Run as administrator"
    echo.
)

pause
