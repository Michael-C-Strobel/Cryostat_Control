#Requires -Version 5.1
<#
CryostatControllerLauncher.ps1
Launch the Cryostat Controller via SSH tunnel.

Usage:
    .\Start Cryostat Controller.ps1
    .\Start Cryostat Controller.ps1 -Rebuild

If something goes wrong, send this file to the lab admin:
    $env:TEMP\CryostatLauncher.log
#>

param(
    [switch]$Rebuild
)

$ErrorActionPreference = "Continue"
$LogFile = "$env:TEMP\CryostatLauncher.log"

function Write-Log($Message, $Level = "INFO", $Screen = $false) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] [$Level] $Message"
    Add-Content -Path $LogFile -Value $line -ErrorAction SilentlyContinue
    if ($Screen -or $Level -eq "ERROR") {
        if ($Level -eq "ERROR") {
            Write-Host "ERROR: $Message" -ForegroundColor Red
        } elseif ($Level -eq "WARN") {
            Write-Host "WARNING: $Message" -ForegroundColor Yellow
        } else {
            Write-Host $Message
        }
    }
}

function Show-Failure($Message, $Detail = $null) {
    Write-Host ""
    Write-Host "FAILED" -ForegroundColor Red
    Write-Host "------" -ForegroundColor Red
    Write-Host $Message -ForegroundColor Red
    if ($Detail) {
        Write-Host $Detail -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "Please send this log file to the lab admin:" -ForegroundColor Cyan
    Write-Host "  $LogFile" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Press Enter to close..."
    Read-Host
    exit 1
}

"--- Cryostat Controller Launcher ---" | Set-Content -Path $LogFile -ErrorAction SilentlyContinue

try {
    Write-Host ""
    Write-Host "Cryostat Controller Launcher" -ForegroundColor Cyan
    Write-Host ""

    Write-Log "Checking OpenSSH client..."
    $sshCmd = Get-Command ssh.exe -ErrorAction SilentlyContinue
    if (-not $sshCmd) {
        Show-Failure "OpenSSH client (ssh.exe) not found." `
            "Install it via: Windows Settings > Apps > Optional features > Add a feature > OpenSSH Client."
    }
    Write-Log "OpenSSH client found: $($sshCmd.Source)"

    Write-Log "Checking SSH config for 'cryostat-controller'..."
    $sshConfigPath = "$env:USERPROFILE\.ssh\config"
    $hasHostEntry = $false
    if (Test-Path $sshConfigPath) {
        $configContent = Get-Content $sshConfigPath -Raw
        if ($configContent -match "(?m)^\s*Host\s+.*\b$cryostat-controller\b") {
            $hasHostEntry = $true
        }
    }
    if (-not $hasHostEntry) {
        Show-Failure "No SSH config entry found for 'cryostat-controller'." `
            "Add an entry to $sshConfigPath. Example:

Host cryostat-controller
    HostName 192.168.0.171
    User user
    IdentityFile ~/.ssh/id_rsa

If this computer is on a different network, you may also need a ProxyJump host."
    }
    Write-Log "SSH config entry found."

    $HostName = "cryostat-controller"
    $RemoteDir = "~/SourceCode/Cryostat_Control"
    $LocalPort = 8050
    $RemotePort = 8050
    $InitialWaitSec = 10
    $TimeoutSec = 60

    $sshDir = "$env:USERPROFILE\.ssh"
    $keyFiles = @("id_rsa", "id_ed25519", "id_ecdsa")
    $foundKey = $null
    foreach ($kf in $keyFiles) {
        if (Test-Path "$sshDir\$kf") { $foundKey = "$sshDir\$kf"; break }
    }
    if (-not $foundKey) {
        Write-Log "No default SSH private key found in $sshDir." "WARN" $true
        Write-Log "You may be prompted for a password." "WARN" $true
    } else {
        Write-Log "SSH private key found: $foundKey"
    }

    Write-Host "Connecting to $HostName..." -NoNewline
    Write-Log "Testing SSH connection to $HostName..."
    $testOutput = & ssh.exe -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new $HostName "echo cryostat-ssh-ok" 2>&1
    $testExit = $LASTEXITCODE
    $testOutput | ForEach-Object { Write-Log "SSH test: $_" }
    if ($testExit -ne 0) {
        Write-Host " FAILED" -ForegroundColor Red
        $hint = "Common causes: no SSH key on the server, wrong key, server offline, or wrong network."
        if ($foundKey) { $hint += " Run 'ssh -v $HostName' for detailed diagnostics." }
        Show-Failure "Could not connect to '$HostName' via SSH." $hint
    }
    if ($testOutput -notcontains "cryostat-ssh-ok") {
        Write-Host " FAILED" -ForegroundColor Red
        Show-Failure "SSH connected but did not get expected response." "Output was: $testOutput"
    }
    Write-Host " OK" -ForegroundColor Green
    Write-Log "SSH connection succeeded."

    Write-Host "Checking port $LocalPort..." -NoNewline
    Write-Log "Checking local port $LocalPort..."
    $testListener = $null
    $portInUse = $true
    try {
        $testListener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $LocalPort)
        $testListener.Start()
        $portInUse = $false
    } catch {
        Write-Log "Could not bind to port ${LocalPort}: $_" "WARN"
    } finally {
        if ($testListener) { $testListener.Stop() }
    }
    if ($portInUse) {
        Write-Host " FAILED" -ForegroundColor Red
        $tcpConn = Get-NetTCPConnection -LocalPort $LocalPort -ErrorAction SilentlyContinue | Select-Object -First 1
        $processName = "unknown"
        if ($tcpConn) {
            $p = Get-Process -Id $tcpConn.OwningProcess -ErrorAction SilentlyContinue
            if ($p) { $processName = $p.ProcessName }
        }
        Show-Failure "Port $LocalPort is already in use by '$processName'." "Close that program and try again."
    }
    Write-Host " OK" -ForegroundColor Green
    Write-Log "Port $LocalPort is free."

    Write-Log "Checking remote docker-compose.yml..."
    & ssh.exe -o BatchMode=yes -o StrictHostKeyChecking=accept-new $HostName "test -f $RemoteDir/docker-compose.yml" 2>&1 | ForEach-Object { Write-Log "Remote check: $_" }
    if ($LASTEXITCODE -ne 0) {
        Show-Failure "Remote file not found: $RemoteDir/docker-compose.yml" "The project may be in a different location on $HostName."
    }

    Write-Host "Starting Cryostat Controller..." -NoNewline
    Write-Log "Starting SSH tunnel and docker-compose..."
    if ($Rebuild) {
        Write-Log "Rebuild requested."
        $remoteCommand = "cd $RemoteDir && docker-compose down && docker-compose --compatibility build && docker-compose --compatibility up"
    } else {
        Write-Log "Using cached images."
        $remoteCommand = "cd $RemoteDir && docker-compose down && docker-compose --compatibility up"
    }

    $sshArgs = @(
        "-tt",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ExitOnForwardFailure=yes",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "-L", "$LocalPort`:localhost`:$RemotePort",
        $HostName,
        $remoteCommand
    )

    Start-Process -FilePath "ssh.exe" -ArgumentList $sshArgs

    Write-Log "Waiting $InitialWaitSec seconds for containers to start..."
    Start-Sleep -Seconds $InitialWaitSec

    Write-Host " waiting for server..." -NoNewline
    Write-Log "Polling http://localhost:$LocalPort ..."
    $end = (Get-Date).AddSeconds($TimeoutSec)
    $ready = $false
    while ((Get-Date) -lt $end) {
        try {
            Invoke-WebRequest "http://localhost:$LocalPort" -TimeoutSec 2 -UseBasicParsing | Out-Null
            $ready = $true
            break
        } catch {
            Start-Sleep 1
        }
    }

    if (-not $ready) {
        Write-Host " FAILED" -ForegroundColor Red
        Show-Failure "Server not responding after $TimeoutSec seconds." "Check the 'Cryostat SSH Tunnel' window for build or startup errors."
    }
    Write-Host " OK" -ForegroundColor Green
    Write-Log "Server ready."

    Write-Log "Opening browser to http://localhost:$LocalPort"
    Start-Process "http://localhost:$LocalPort"

    Write-Host ""
    Write-Host "SUCCESS: Cryostat Controller is running in your browser." -ForegroundColor Green
    Write-Host "You can close this window; keep the 'Cryostat SSH Tunnel' window open." -ForegroundColor Cyan
    Write-Host ""
    Read-Host "Press Enter to exit"
}
catch {
    Show-Failure "Unexpected error in launcher: $_" $_.ScriptStackTrace
}
