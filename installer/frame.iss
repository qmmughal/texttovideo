; Windows installer for Frame. Built by CI: iscc /DAppVersion=1.2.0 installer\frame.iss
; The web interface ships prebuilt (frontend\out), so only Python is needed on the user's computer.
#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif

[Setup]
AppId={{6F1B7C2E-4C1D-4E0B-9C55-3A8F2B7E9D41}
AppName=Frame
AppVersion={#AppVersion}
AppPublisher=Frame contributors
AppPublisherURL=https://github.com/qmmughal/texttovideo
DefaultDirName={localappdata}\Programs\Frame
DefaultGroupName=Frame
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Frame-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\LICENSE
UninstallDisplayName=Frame local video studio
DisableProgramGroupPage=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\backend\*"; DestDir: "{app}\backend"; Excludes: "__pycache__\*"; Flags: recursesubdirs ignoreversion
Source: "..\scripts\*"; DestDir: "{app}\scripts"; Excludes: "__pycache__\*"; Flags: recursesubdirs ignoreversion
Source: "..\frontend\out\*"; DestDir: "{app}\frontend\out"; Flags: recursesubdirs ignoreversion
Source: "..\frontend\public\fonts\*"; DestDir: "{app}\frontend\public\fonts"; Flags: recursesubdirs ignoreversion
Source: "..\setup.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\start.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "first-run.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Frame"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\start.ps1"""; WorkingDir: "{app}"; Comment: "Start Frame and open it in your browser"
Name: "{group}\Uninstall Frame"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Frame"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\start.ps1"""; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\first-run.ps1"""; WorkingDir: "{app}"; StatusMsg: "Installing Python packages (a few minutes)..."; Flags: waituntilterminated
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\start.ps1"""; WorkingDir: "{app}"; Description: "Start Frame now"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; The Python environment is recreated on install; projects in {app}\data are kept.
Type: filesandordirs; Name: "{app}\.venv"
Type: filesandordirs; Name: "{app}\backend\__pycache__"
Type: filesandordirs; Name: "{app}\scripts\__pycache__"
