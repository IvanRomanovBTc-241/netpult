@echo off
chcp 65001 >nul
setlocal
rem Прямой запуск Gradle с полным логом. TEMP и GRADLE_USER_HOME — внутри проекта.

set "APP=%~dp0"
for %%I in ("%APP%..") do set "WS=%%~fI"
set "TOOLS=%WS%\tools"

if not exist "%WS%\tmp" mkdir "%WS%\tmp"
set "TEMP=%WS%\tmp"
set "TMP=%TEMP%"
set "GRADLE_USER_HOME=%WS%\.gradle"
set "ANDROID_USER_HOME=%WS%\.android"
set "JAVA_HOME=%TOOLS%\jdk"
set "ANDROID_HOME=%TOOLS%\android-sdk"
set "ANDROID_SDK_ROOT=%ANDROID_HOME%"
set "PATH=%JAVA_HOME%\bin;%ANDROID_HOME%\platform-tools;C:\Users\Ivan\flutter\3.47.9\bin;%PATH%"

set "AND=%APP%build\flutter\android"
set "LOG=%APP%gradle-debug.log"

cd /d "%AND%"
call gradlew.bat --stop >nul 2>&1
call gradlew.bat assembleRelease --stacktrace --console=plain --info > "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"

echo.
echo == Код возврата: %RC% ==
echo.
powershell -NoProfile -Command "Get-Content -Path '%LOG%' -Tail 70"
echo.
echo == Полный лог: %LOG% ==
pause