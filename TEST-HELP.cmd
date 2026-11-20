@echo off
chcp 65001 >nul
setlocal
set "APP=%~dp0"
for %%I in ("%APP%..") do set "WS=%%~fI"
set "TOOLS=%WS%\tools"
if not exist "%WS%\tmp" mkdir "%WS%\tmp"
set "TEMP=%WS%\tmp"
set "TMP=%TEMP%"
set "GRADLE_USER_HOME=%WS%\.gradle"
set "JAVA_HOME=%TOOLS%\jdk"
set "ANDROID_HOME=%TOOLS%\android-sdk"
set "ANDROID_SDK_ROOT=%ANDROID_HOME%"
set "PATH=%JAVA_HOME%\bin;%ANDROID_HOME%\platform-tools;C:\Users\Ivan\flutter\3.47.9\bin;%PATH%"

cd /d "%APP%build\flutter\android"
echo == JAVA_HOME=%JAVA_HOME% ==
"%JAVA_HOME%\bin\java.exe" -version
echo.
echo == gradlew help ==
call gradlew.bat help --console=plain
set "RC=%ERRORLEVEL%"
echo.
echo == Код возврата: %RC% ==
pause