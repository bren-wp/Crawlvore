#ifndef AppVersion
#define AppVersion "8.1.1"
#endif
[Setup]
AppId=Crawlvora.BusinessData
AppName=Crawlvora
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\Crawlvora
DefaultGroupName=Crawlvora
PrivilegesRequired=lowest
#ifdef PrivateOutput
OutputDir={#PrivateOutput}
#else
OutputDir=..\release-assets
#endif
OutputBaseFilename=Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=Crawlvora.ico
UninstallDisplayIcon={app}\Crawlvora.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
[Files]
Source: "MicrosoftEdgeWebview2Setup.exe"; Flags: dontcopy
#ifdef PrivatePortable
Source: "{#PrivatePortable}"; DestDir: "{app}"; DestName: "Crawlvora.exe"; Flags: ignoreversion
#else
Source: "..\native-preview\Crawlvora.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\native-preview\worker\*"; DestDir: "{app}\worker"; Flags: ignoreversion recursesubdirs createallsubdirs
#endif
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
[Icons]
Name: "{autodesktop}\Crawlvora"; Filename: "{app}\Crawlvora.exe"; Tasks: desktopicon
Name: "{group}\Crawlvora"; Filename: "{app}\Crawlvora.exe"
[Run]
Filename: "{app}\Crawlvora.exe"; Description: "Launch Crawlvora"; Flags: nowait postinstall skipifsilent

[Code]
function HasWebView2: Boolean;
var
  V: String;
  Key: String;
begin
  Key := 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  Result := (RegQueryStringValue(HKLM32, Key, 'pv', V) and (V <> '') and (V <> '0.0.0.0'))
    or (RegQueryStringValue(HKCU, Key, 'pv', V) and (V <> '') and (V <> '0.0.0.0'));
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
begin
  Result := '';
  if HasWebView2 then exit;
  ExtractTemporaryFile('MicrosoftEdgeWebview2Setup.exe');
  if not Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'), '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, Code) then
    Result := 'Microsoft WebView2 could not be started.'
  else if not HasWebView2 then
    Result := 'Microsoft WebView2 is required. Connect to the internet and retry Setup.';
end;
