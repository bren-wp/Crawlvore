[Setup]
AppId=Crawlvora.BusinessData
AppName=Crawlvora
AppVersion=8.0.0
DefaultDirName={localappdata}\Programs\Crawlvora
DefaultGroupName=Crawlvora
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=Crawlvora.ico
UninstallDisplayIcon={app}\Crawlvora.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
[Files]
Source: "..\dist\Portable.exe"; DestDir: "{app}"; DestName: "Crawlvora.exe"; Flags: ignoreversion
[Icons]
Name: "{group}\Crawlvora"; Filename: "{app}\Crawlvora.exe"
[Run]
Filename: "{app}\Crawlvora.exe"; Description: "Launch Crawlvora"; Flags: nowait postinstall skipifsilent
