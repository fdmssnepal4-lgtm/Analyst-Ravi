@echo off
title Move Analyst Ravi Match Insights
setlocal
set "APPNAME=AnalystRaviMatchInsights"
set "APPDIR=%LOCALAPPDATA%\%APPNAME%"
set "HERE=%~dp0"
set "ZIP=%HERE%%APPNAME%.zip"
set "ZIPR=%HERE%%APPNAME%-data.zip"

echo.
echo  ==========================================
echo    Move Analyst Ravi Match Insights
echo  ==========================================
echo.
echo   1 = OLD laptop: pack the app onto this USB/folder
echo   2 = NEW laptop: install the app from this USB/folder
echo.
choice /c 12 /n /m "Press 1 or 2: "
if errorlevel 2 goto install
goto pack

:pack
if not exist "%APPDIR%\%APPNAME%.exe" (
  echo.
  echo  The app was not found on this laptop:
  echo    %APPDIR%
  echo  Run this on the laptop where the app works.
  goto end
)
echo.
echo  Closing the app if it is open...
taskkill /f /im "%APPNAME%.exe" >nul 2>&1
echo  Packing the app. This can take a few minutes...
if exist "%ZIP%" del "%ZIP%"
powershell -NoProfile -Command "Compress-Archive -Path '%APPDIR%' -DestinationPath '%ZIP%' -Force"
if not exist "%ZIP%" ( echo  Packing failed. & goto end )
if exist "%APPDATA%\%APPNAME%" (
  echo  Packing saved data too...
  if exist "%ZIPR%" del "%ZIPR%"
  powershell -NoProfile -Command "Compress-Archive -Path '%APPDATA%\%APPNAME%' -DestinationPath '%ZIPR%' -Force"
)
echo.
echo  DONE. Now plug this USB into the NEW laptop,
echo  double-click Move-Ravi-App.bat there and press 2.
goto end

:install
if not exist "%ZIP%" (
  echo.
  echo  %APPNAME%.zip was not found next to this script.
  echo  First run this script on the OLD laptop and press 1.
  goto end
)
echo.
echo  Installing the app...
taskkill /f /im "%APPNAME%.exe" >nul 2>&1
powershell -NoProfile -Command "Expand-Archive -Path '%ZIP%' -DestinationPath '%LOCALAPPDATA%' -Force"
if exist "%ZIPR%" (
  echo  Restoring saved data...
  powershell -NoProfile -Command "Expand-Archive -Path '%ZIPR%' -DestinationPath '%APPDATA%' -Force"
)
if not exist "%APPDIR%\%APPNAME%.exe" ( echo  Install failed. & goto end )
powershell -NoProfile -Command "Get-ChildItem -LiteralPath '%APPDIR%' -Recurse | Unblock-File"
echo  Making a Desktop shortcut...
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Analyst Ravi Match Insights.lnk'); $s.TargetPath='%APPDIR%\%APPNAME%.exe'; $s.WorkingDirectory='%APPDIR%'; $s.Save()"
echo.
echo  DONE. Starting the app...
start "" "%APPDIR%\%APPNAME%.exe"

:end
echo.
pause
