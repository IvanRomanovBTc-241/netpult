@echo off
chcp 65001 >nul
setlocal
rem Сборка с рабочей временной папкой: системный Temp на этой машине недоступен для записи.

set "APP=%~dp0"
for %%I in ("%APP%..") do set "WS=%%~fI"
set "TOOLS=%WS%\tools"

set "JAVA_HOME=%TOOLS%\jdk"
set "ANDROID_HOME=%TOOLS%\android-sdk"
set "ANDROID_SDK_ROOT=%ANDROID_HOME%"
set "PATH=%JAVA_HOME%\bin;%ANDROID_HOME%\platform-tools;C:\Users\Ivan\flutter\3.47.9\bin;%PATH%"
if not exist "%WS%\tmp" mkdir "%WS%\tmp"
set "TEMP=%WS%\tmp"
set "TMP=%TEMP%"
set "GRADLE_USER_HOME=%WS%\.gradle"
set "PYTHONPATH=%WS%\mobile_libs"
set "PYTHONIOENCODING=utf-8"

cd /d "%APP%"
echo == Чистая сборка APK (обычные системные каталоги) ==
python -c "import sys; sys.argv=['flet','build','apk','--project','netpult','--module-name','main']; from flet_cli.cli import main; main()" > "%APP%build-clean.log" 2>&1
set "RC=%ERRORLEVEL%"

echo.
echo == Код возврата: %RC% ==
powershell -NoProfile -Command "Get-Content -Path '%APP%build-clean.log' -Tail 50"
echo.
echo == Полный лог: %APP%build-clean.log ==
if exist "%APP%build\apk" dir /b "%APP%build\apk\*.apk"
pause