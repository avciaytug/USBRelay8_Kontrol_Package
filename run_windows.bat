@echo off
rem USBRelay8 Kontrol - Windows calistirici (Win7/8/10/11)
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (
    python relay_gui.py %*
) else (
    py -3 relay_gui.py %*
)
if errorlevel 1 pause
