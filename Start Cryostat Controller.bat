@echo off
setlocal

:: Wrapper to launch the Cryostat Controller PowerShell script.
:: This bypasses the default Windows PowerShell execution policy
:: so the user does not need to change system settings.

title Cryostat Controller Launcher

set "PS1_PATH=%~dp0Start Cryostat Controller.ps1"
set "LOG_FILE=%TEMP%\CryostatLauncher.log"

if not exist "%PS1_PATH%" (
    echo ERROR: Could not find the launcher script:
    echo   %PS1_PATH%
    echo.
    echo Press any key to close.
    pause >nul
    exit /b 1
)

:: Try PowerShell 7 first, fall back to Windows PowerShell.
where pwsh.exe >nul 2>&1
if %errorlevel% equ 0 (
    set "PS_EXE=pwsh.exe"
) else (
    set "PS_EXE=powershell.exe"
)

echo Launching Cryostat Controller...
echo If this window closes immediately, check the log file:
echo   %LOG_FILE%
echo.

:: -ExecutionPolicy Bypass allows the script to run without changing system policy.
:: -NoProfile speeds up startup and avoids profile script side effects.
"%PS_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%PS1_PATH%" %*

:: If PowerShell exits with an error, keep this window open.
if %errorlevel% neq 0 (
    echo.
    echo The launcher exited with an error. Check the log file:
    echo   %LOG_FILE%
    echo.
    echo Press any key to close.
    pause >nul
)
