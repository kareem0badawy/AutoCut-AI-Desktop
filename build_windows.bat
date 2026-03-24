@echo off
title AutoCut Builder
color 0A
echo.
echo ============================================
echo   AutoCut - Windows EXE Builder
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause & exit /b 1
)
echo [OK] Python found.

REM Install / upgrade dependencies
echo.
echo [*] Installing Python dependencies...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [ERROR] Failed to install requirements.
    pause & exit /b 1
)

REM Fix NumPy version — many packages (nltk, pandas) need numpy < 2
echo.
echo [*] Fixing NumPy version for build compatibility...
pip install "numpy<2" -q
if errorlevel 1 (
    echo [WARN] Could not pin numpy, continuing anyway...
)
echo [OK] NumPy pinned to 1.x for build.

REM Install PyInstaller and Pillow
pip install pyinstaller pillow -q
if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller.
    pause & exit /b 1
)
echo [OK] All build tools ready.

REM Generate icon
echo.
echo [*] Generating application icon...
python create_icon.py
if errorlevel 1 (
    echo [WARN] Icon generation skipped, using existing icon.
)

REM Build EXE
echo.
echo [*] Building EXE -- this takes 3-7 minutes...
echo.
pyinstaller autocut.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. Check output above for the exact error.
    echo.
    echo   Common fixes:
    echo   1. Run: pip install "numpy^<2" then try again
    echo   2. Check autocut.log for details
    pause & exit /b 1
)

REM Copy user data files to dist folder
echo.
echo [*] Copying data files to dist...
if exist config.json        copy /y config.json        dist\AutoCut\ >nul
if exist style_config.json  copy /y style_config.json  dist\AutoCut\ >nul
if exist script.txt         copy /y script.txt         dist\AutoCut\ >nul
if exist autocut.ico        copy /y autocut.ico        dist\AutoCut\ >nul
if exist assets             xcopy /e /i /y assets      dist\AutoCut\assets\ >nul
if exist output             xcopy /e /i /y output      dist\AutoCut\output\ >nul
echo [OK] Data files copied.

REM Create Desktop shortcut via a temp PS1 file
echo.
echo [*] Creating Desktop shortcut...
set "TARGET=%CD%\dist\AutoCut\AutoCut.exe"
set "ICON=%CD%\autocut.ico"
set "WORKDIR=%CD%\dist\AutoCut"
set "SHORTCUT=%USERPROFILE%\Desktop\AutoCut.lnk"

echo $ws = New-Object -ComObject WScript.Shell > "%TEMP%\make_shortcut.ps1"
echo $s = $ws.CreateShortcut('%SHORTCUT%') >> "%TEMP%\make_shortcut.ps1"
echo $s.TargetPath = '%TARGET%' >> "%TEMP%\make_shortcut.ps1"
echo $s.IconLocation = '%ICON%' >> "%TEMP%\make_shortcut.ps1"
echo $s.WorkingDirectory = '%WORKDIR%' >> "%TEMP%\make_shortcut.ps1"
echo $s.Description = 'AutoCut AI Video Generator' >> "%TEMP%\make_shortcut.ps1"
echo $s.Save() >> "%TEMP%\make_shortcut.ps1"

powershell -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\make_shortcut.ps1" 2>nul
del "%TEMP%\make_shortcut.ps1" 2>nul

if exist "%SHORTCUT%" (
    echo [OK] Desktop shortcut created: AutoCut.lnk
) else (
    echo [WARN] Shortcut not created automatically.
    echo        Navigate to dist\AutoCut\ and run AutoCut.exe
)

echo.
echo ============================================
echo   BUILD COMPLETE!
echo ============================================
echo.
echo   EXE: dist\AutoCut\AutoCut.exe
echo   Icon on Desktop: AutoCut.lnk
echo.
echo   To share the app, zip the 'dist\AutoCut' folder.
echo.
pause
