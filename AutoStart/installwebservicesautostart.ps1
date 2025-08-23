# C:\wanderers_web\AutoStart\installwebservicesautostart.ps1
# Creates/updates a Scheduled Task that auto-starts the tray app at user logon,
# runs indefinitely (no time limit), runs on battery, and adds an hourly
# heartbeat trigger to ensure it stays running (no duplicate instances).

$ErrorActionPreference = 'Stop'

# --- Admin check & how-to ---
$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $IsAdmin) {
    Write-Error "Please run this script in an elevated PowerShell (Run as administrator)."
    Write-Host  'Open admin PowerShell then run:' -ForegroundColor Yellow
    Write-Host  'powershell -ExecutionPolicy Bypass -File "C:\wanderers_web\AutoStart\installwebservicesautostart.ps1"' -ForegroundColor Yellow
    exit 1
}

# --- Config ---
$TaskName   = "Wanderers Web AutoStart"
$ScriptPath = "C:\wanderers_web\AutoStart\StartOnlineBookingWebSite.py"
$UserId     = "$env:USERDOMAIN\$env:USERNAME"  # current user context

# --- Sanity checks ---
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Script not found: $ScriptPath"
    exit 1
}

# --- Resolve pythonw.exe from PATH, fallback to Nova's known location ---
$PythonwExe = Get-Command "pythonw.exe" -ErrorAction SilentlyContinue
if (-not $PythonwExe) {
    $Fallback = "C:\Users\Nova\AppData\Local\Programs\Python\Python312\pythonw.exe"
    if (Test-Path $Fallback) {
        $Execute = $Fallback
        Write-Host "[WARN] pythonw.exe not found in PATH, using fallback: $Execute" -ForegroundColor Yellow
    } else {
        Write-Error "pythonw.exe not found in PATH and fallback does not exist."
        exit 1
    }
} else {
    $Execute = $PythonwExe.Source
    Write-Host "[INFO] Using pythonw.exe at: $Execute"
}

# --- Remove any existing task ---
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Start-Sleep -Milliseconds 300
}

# --- Build action ---
$Action = New-ScheduledTaskAction -Execute $Execute -Argument ('"{0}"' -f $ScriptPath)

# --- Triggers ---
# 1) At logon for current user
$TriggerLogon = New-ScheduledTaskTrigger -AtLogOn -User $UserId

# 2) Hourly heartbeat (for ~10 years). Using a very long duration because "indefinite" is not valid XML.
$StartAt = (Get-Date).AddMinutes(1)  # first check in 1 minute
$TriggerHeartbeat = New-ScheduledTaskTrigger -Once -At $StartAt `
    -RepetitionInterval (New-TimeSpan -Hours 1) `
    -RepetitionDuration (New-TimeSpan -Days 3650)  # ~10 years

# --- Settings ---
# Unlimited run time, allow/continue on battery, ignore duplicate starts from heartbeat
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

# --- Register task in current user context ---
Register-ScheduledTask `
    -TaskName    $TaskName `
    -Action      $Action `
    -Trigger     @($TriggerLogon, $TriggerHeartbeat) `
    -Settings    $Settings `
    -Description "Start Wanderers Web tray (user context) at logon and keep it running via hourly heartbeat" `
    -User        $UserId `
    -RunLevel    Highest `
    -Force

# --- Start now ---
Write-Host "[INFO] Starting scheduled task '$TaskName' now..." -ForegroundColor Cyan
Start-ScheduledTask -TaskName $TaskName

Write-Host "[OK] Task '$TaskName' created/updated and started." -ForegroundColor Green
Write-Host "It will auto-start at logon and be verified every hour." -ForegroundColor Green
