@echo off
chcp 65001 >nul
setlocal
echo TEMP сейчас: %TEMP%
echo USERPROFILE: %USERPROFILE%
echo.
if not exist "%USERPROFILE%\Temp" mkdir "%USERPROFILE%\Temp"
echo probe > "%USERPROFILE%\Temp\probe.txt" 2>nul
if exist "%USERPROFILE%\Temp\probe.txt" (echo [OK]   запись в %USERPROFILE%\Temp работает) else (echo [FAIL] запись в %USERPROFILE%\Temp запрещена)
echo probe > "%TEMP%\probe2.txt" 2>nul
if exist "%TEMP%\probe2.txt" (echo [OK]   запись в %TEMP% работает) else (echo [FAIL] запись в %TEMP% запрещена)
echo.
echo Кто я: %USERNAME%   Компьютер: %COMPUTERNAME%
whoami /groups | findstr /i "Mandatory Label"
echo.
pause