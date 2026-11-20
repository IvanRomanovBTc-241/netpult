@echo off
chcp 65001 >nul
setlocal
rem Сборка APK на уже установленном тулчейне (tools\flutter, tools\jdk, tools\android-sdk).
rem Запускается двойным кликом, ставить ничего не нужно.

set "APP=%~dp0"
for %%I in ("%APP%..") do set "WS=%%~fI"
set "TOOLS=%WS%\tools"

set "TEMP=%WS%\tmp"
set "TMP=%TEMP%"
set "APPDATA=%WS%\.appdata"
set "LOCALAPPDATA=%WS%\.localappdata"
set "GRADLE_USER_HOME=%WS%\.gradle"
set "ANDROID_USER_HOME=%WS%\.android"
set "PUB_CACHE=%WS%\.pub-cache"
set "GIT_CONFIG_GLOBAL=%WS%\.gitconfig"
set "JAVA_HOME=%TOOLS%\jdk"
set "ANDROID_HOME=%TOOLS%\android-sdk"
set "ANDROID_SDK_ROOT=%ANDROID_HOME%"
set "PATH=%JAVA_HOME%\bin;%ANDROID_HOME%\platform-tools;%TOOLS%\flutter\bin;%PATH%"
set "PYTHONPATH=%WS%\mobile_libs"
set "PYTHONIOENCODING=utf-8"

rem --- проверка режима разработчика (нужен для симлинков плагинов Flutter) ---
reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock" /v AllowDevelopmentWithoutDevLicense 2>nul | find "0x1" >nul
if errorlevel 1 (
  echo.
  echo [!] Режим разработчика Windows выключен.
  echo     Без него Flutter не сможет собрать APK с плагинами.
  echo     Включи: Параметры - Система - Для разработчиков - Режим разработчика
  echo     или выполни от администратора:
  echo     reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock" /t REG_DWORD /f /v AllowDevelopmentWithoutDevLicense /d 1
  echo.
  pause
  exit /b 1
)

cd /d "%APP%"
echo == Сборка APK. Первый запуск долгий: Gradle скачивает зависимости. ==
python -c "import sys; sys.argv=['flet','build','apk','--project','netpult','--module-name','main']; from flet_cli.cli import main; main()" > "%APP%build-log.txt" 2>&1

type "%APP%build-log.txt"

if exist "%APP%build\apk" (
  echo.
  echo == Готово. APK лежит в %APP%build\apk ==
  dir /b "%APP%build\apk\*.apk"
) else (
  echo.
  echo == Сборка не дошла до APK. Скопируй вывод выше — разберём. ==
)
pause
