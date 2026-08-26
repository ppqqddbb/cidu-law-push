param(
    [string]$TaskName = "Law-Push-Filtered-Daily",
    [string]$PythonExecutable = "python",
    [string]$RunAt = "08:00"
)

$ErrorActionPreference = "Stop"

try {
    $runTime = [DateTime]::ParseExact($RunAt, "HH:mm", $null)
} catch {
    throw "RunAt must use HH:mm format, for example 08:00."
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot ".")).Path
$jobScript = Join-Path $projectRoot "run_filter.py"
if (-not (Test-Path -LiteralPath $jobScript -PathType Leaf)) {
    throw "Cannot find run_filter.py under $projectRoot."
}

$pythonPath = @(
    Get-Command $PythonExecutable -CommandType Application -ErrorAction Stop |
        Where-Object { $_.Source -and (Test-Path -LiteralPath $_.Source) } |
        Select-Object -First 1 -ExpandProperty Source
)[0]
if (-not $pythonPath) {
    throw "Could not resolve a real Python executable for '$PythonExecutable'."
}

$logDir = Join-Path $projectRoot ".run"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$logFile = Join-Path $logDir "law_filter_schedule.log"

$commandLine = '"{0}" -u "{1}" 30 >> "{2}" 2>&1' -f $pythonPath, $jobScript, $logFile
$action = New-ScheduledTaskAction `
    -Execute $env:ComSpec `
    -Argument ('/d /c "{0}"' -f $commandLine) `
    -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $runTime
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal `
    -UserId ("{0}\{1}" -f $env:USERDOMAIN, $env:USERNAME) `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Run python run_filter.py 30 every day at $RunAt." `
    -Force | Out-Null

Write-Host "Registered task '$TaskName' at $RunAt."
Write-Host "Command: $pythonPath `"$jobScript`" 30"
Write-Host "Log: $logFile"
Write-Host "Run now: Start-ScheduledTask -TaskName '$TaskName'"
