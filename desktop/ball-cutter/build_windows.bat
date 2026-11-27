@echo off
REM Builds Ball Cutter on a Windows PC (needs Python 3.10+ from python.org).
REM Result: dist\BallCutter\BallCutter.exe, and dist\BallCutter-Setup-*.exe if Inno Setup 6 is installed.
cd /d "%~dp0"
python -m venv .venv || goto :err
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller || goto :err
pyinstaller --noconfirm --clean --windowed --name BallCutter --icon packaging\icon.ico ^
  --add-data "packaging\icon.ico;packaging" --collect-all imageio_ffmpeg app.py || goto :err
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
  "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" packaging\installer.iss || goto :err
)
echo.
echo Done. Open the dist folder.
pause
exit /b 0
:err
echo Build failed.
pause
exit /b 1
