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

pip install pyinstaller pillow -q
if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller.
    pause & exit /b 1
)
echo [OK] All dependencies ready.

REM Generate icon
echo.
echo [*] Generating application icon...
python create_icon.py
if errorlevel 1 (
    echo [WARN] Icon generation failed, using default.
)

REM Build EXE
echo.
echo [*] Building EXE — this takes 3-7 minutes...
echo.
pyinstaller autocut.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. Check output above.
    pause & exit /b 1
)

REM Copy user data files to dist folder
echo.
echo [*] Copying data files...
if exist config.json        copy /y config.json        dist\AutoCut\ >nul
if exist style_config.json  copy /y style_config.json  dist\AutoCut\ >nul
if exist script.txt         copy /y script.txt         dist\AutoCut\ >nul
if exist autocut.ico        copy /y autocut.ico        dist\AutoCut\ >nul
if exist assets             xcopy /e /i /y assets      dist\AutoCut\assets\ >nul
if exist output             xcopy /e /i /y output      dist\AutoCut\output\ >nul

echo [OK] Data files copied.

REM Create Desktop shortcut
echo.
echo [*] Creating Desktop shortcut...
set "TARGET=%CD%\dist\AutoCut\AutoCut.exe"
set "ICON=%CD%\autocut.ico"
set "WORKDIR=%CD%\dist\AutoCut"
set "SHORTCUT=%USERPROFILE%\Desktop\AutoCut.lnk"

powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $s = $ws.CreateShortcut('%SHORTCUT%'); ^
   $s.TargetPath = '%TARGET%'; ^
   $s.IconLocation = '%ICON%'; ^
   $s.WorkingDirectory = '%WORKDIR%'; ^
   $s.Description = 'AutoCut AI Video Generator'; ^
   $s.Save()" 2>nul

if not errorlevel 1 (
    echo [OK] Desktop shortcut created: AutoCut.lnk
) else (
    echo [WARN] Could not create shortcut automatically.
    echo        Run dist\AutoCut\AutoCut.exe manually.
)

echo.
echo ============================================
echo   BUILD COMPLETE!
echo ============================================
echo.
echo   EXE location: dist\AutoCut\AutoCut.exe
echo   Desktop icon: AutoCut.lnk
echo.
echo   To distribute the app, zip the entire
echo   'dist\AutoCut' folder and share it.
echo.
pause
