param(
    [string]$Adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
)

if (!(Test-Path -LiteralPath $Adb)) {
    Write-Error "adb.exe not found at $Adb"
    exit 1
}

& $Adb logcat -v time MotionRunner:D AndroidRuntime:E *:S
