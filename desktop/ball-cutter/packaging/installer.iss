; Inno Setup script: builds BallCutter-Setup.exe from the PyInstaller output in dist\BallCutter
#define AppName "Ball Cutter"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6C1E4C2B-3F0A-4D7E-9B1E-BA11C0771E01}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Performance Analysis
DefaultDirName={autopf}\Ball Cutter
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\BallCutter.exe
OutputDir=..\dist
OutputBaseFilename=BallCutter-Setup-{#AppVersion}
SetupIconFile=icon.ico
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\BallCutter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\BallCutter.exe"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\BallCutter.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\BallCutter.exe"; Description: "Start {#AppName} now"; Flags: nowait postinstall skipifsilent
