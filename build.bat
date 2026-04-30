@echo off
:: =============================================================================
:: build.bat — One-click builder for TrackerApp.exe
:: Place this file in the tracker_app\ folder (same level as main.py)
:: =============================================================================

title TrackerApp Builder

echo.
echo  ============================================
echo   TrackerApp ^| Building .exe
echo  ============================================
echo.

:: Move to the folder this .bat lives in
cd /d "%~dp0"

:: ── Check Python ─────────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found.
    echo  Install from https://www.python.org/downloads/
    echo  Check "Add Python to PATH" during install.
    pause & exit /b 1
)

:: ── Install dependencies ─────────────────────────────────────────────────────
echo  Installing dependencies...
echo.
python -m pip install --upgrade --quiet pyautogui pillow opencv-python pyinstaller

if errorlevel 1 (
    echo.
    echo  [ERROR] pip install failed. Try running as Administrator.
    pause & exit /b 1
)

:: ── Clean previous build ─────────────────────────────────────────────────────
echo.
echo  Cleaning previous build...
if exist "dist\TrackerApp.exe" del /f /q "dist\TrackerApp.exe"
if exist "build" rmdir /s /q "build"

:: ── Build — call PyInstaller via python -m to avoid PATH issues ──────────────
echo.
echo  Building TrackerApp.exe (this takes 1-3 minutes)...
echo.

python -m PyInstaller TrackerApp.spec --noconfirm

if errorlevel 1 (
    echo.
    echo  ============================================
    echo   [ERROR] Build FAILED
    echo  ============================================
    echo.
    echo  Common fixes:
    echo   1. Make sure all .py files are in the right folders
    echo   2. Check that config.py exists in this folder
    echo   3. Try running as Administrator
    echo   4. Check the error messages above
    echo.
    pause & exit /b 1
)

:: ── Verify exe exists ────────────────────────────────────────────────────────
if not exist "dist\TrackerApp.exe" (
    echo  [ERROR] Build completed but TrackerApp.exe not found in dist\
    pause & exit /b 1
)

:: ── Copy startup helpers into dist\ ─────────────────────────────────────────
echo.
echo  Copying startup helpers to dist\...
if exist "dist_add_to_startup.bat"       copy /y "dist_add_to_startup.bat"       "dist\add_to_startup.bat"       >nul
if exist "dist_remove_from_startup.bat"  copy /y "dist_remove_from_startup.bat"  "dist\remove_from_startup.bat"  >nul

:: ── Done ─────────────────────────────────────────────────────────────────────
echo.
echo  ============================================
echo   BUILD SUCCESSFUL
echo  ============================================
echo.
echo  Output folder contents:
echo.
dir /b dist\
echo.
echo  NEXT STEPS:
echo   1. Make sure config.py has your Gmail details
echo   2. Open the dist\ folder
echo   3. Right-click add_to_startup.bat ^> Run as administrator
echo.
pause