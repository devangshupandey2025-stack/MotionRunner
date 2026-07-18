@echo off
setlocal EnableExtensions
set "APP_HOME=%~dp0"
set "GRADLE_VERSION=8.11.1"
set "GRADLE_HOME=%USERPROFILE%\.motionrunner\gradle\gradle-%GRADLE_VERSION%"
set "GRADLE_ZIP=%TEMP%\motionrunner-gradle-%GRADLE_VERSION%.zip"

if not exist "%GRADLE_HOME%\bin\gradle.bat" (
  echo Bootstrapping Gradle %GRADLE_VERSION% for MotionRunner...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; Invoke-WebRequest 'https://services.gradle.org/distributions/gradle-%GRADLE_VERSION%-bin.zip' -OutFile '%GRADLE_ZIP%'; New-Item -ItemType Directory -Force -Path '%GRADLE_HOME%\..' | Out-Null; Expand-Archive -Force '%GRADLE_ZIP%' '%GRADLE_HOME%\..'; Remove-Item '%GRADLE_ZIP%' -Force"
  if errorlevel 1 exit /b %errorlevel%
)

call "%GRADLE_HOME%\bin\gradle.bat" -p "%APP_HOME%" %*
exit /b %errorlevel%
