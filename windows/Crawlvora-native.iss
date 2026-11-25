#ifndef AppVersion
#define AppVersion "8.1.0"
#endif
[Setup]
AppId=Crawlvora.BusinessData
AppName=Crawlvora
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\Crawlvora
DefaultGroupName=Crawlvora
PrivilegesRequired=lowest
OutputDir=..\release-assets
OutputBaseFilename=Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=Crawlvora.ico
UninstallDisplayIcon={app}\Crawlvora.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
[Files]
Source: "..\native-preview\Crawlvora.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\native-preview\worker\*"; DestDir: "{app}\worker"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Crawlvora"; Filename: "{app}\Crawlvora.exe"
[Run]
Filename: "{app}\Crawlvora.exe"; Description: "Launch Crawlvora"; Flags: nowait postinstall skipifsilent
