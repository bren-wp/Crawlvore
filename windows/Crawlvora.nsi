Unicode true
RequestExecutionLevel user
CRCCheck force
ManifestDPIAware true
SetCompressor /SOLID lzma
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!ifndef APP_VERSION
  !error "APP_VERSION is required"
!endif
!ifndef APP_EXE
  !error "APP_EXE is required"
!endif
!ifndef SETUP_EXE
  !error "SETUP_EXE is required"
!endif
!ifndef WEBVIEW_BOOTSTRAPPER
  !error "WEBVIEW_BOOTSTRAPPER is required"
!endif
!ifdef ACCEPTANCE
  !define APP_NAME "Tvrtke - test instalacije"
  !define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\Crawlvora.Acceptance.NSIS"
  InstallDir "$TEMP\Crawlvora-Acceptance"
!else
  !define APP_NAME "Tvrtke"
  !define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\Crawlvora.BusinessData_is1"
  InstallDir "$LOCALAPPDATA\Programs\Crawlvora"
!endif
Name "${APP_NAME}"
OutFile "${SETUP_EXE}"
BrandingText "Tvrtke"
!define MUI_ICON "Crawlvora.ico"
!define MUI_UNICON "Crawlvora.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Dobro došli u Tvrtke"
!define MUI_WELCOMEPAGE_TEXT "Instalacija poslovnog imenika za Hrvatsku. Postojeće baze, sigurnosne kopije i korisničke postavke ostaju sačuvane."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!ifndef ACCEPTANCE
  !define MUI_FINISHPAGE_RUN "$INSTDIR\Crawlvora.exe"
  !define MUI_FINISHPAGE_RUN_TEXT "Pokreni Tvrtke"
  !define MUI_FINISHPAGE_RUN_NOTCHECKED
!endif
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Croatian"
Var RuntimeVersion
Var LegacyUninstaller
Function HasWebView2
  SetRegView 32
  ReadRegStr $RuntimeVersion HKLM "SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" "pv"
  ${If} $RuntimeVersion == ""
  ${OrIf} $RuntimeVersion == "0.0.0.0"
    ReadRegStr $RuntimeVersion HKCU "SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" "pv"
  ${EndIf}
  SetRegView 64
FunctionEnd
Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "Tvrtke zahtijeva 64-bitni Windows." /SD IDOK
    Abort
  ${EndIf}
  SetShellVarContext current
  SetRegView 64
  !ifndef ACCEPTANCE
    ReadRegStr $LegacyUninstaller HKCU "${UNINSTALL_KEY}" "UninstallString"
    ReadRegStr $0 HKCU "${UNINSTALL_KEY}" "InstallLocation"
    ${If} $0 != ""
      StrCpy $INSTDIR $0
    ${EndIf}
  !endif
FunctionEnd
Section "Tvrtke (obavezno)" Main
  SectionIn RO
  Call HasWebView2
  ${If} $RuntimeVersion == ""
  ${OrIf} $RuntimeVersion == "0.0.0.0"
    InitPluginsDir
    SetOutPath "$PLUGINSDIR"
    File /oname=WebView2Setup.exe "${WEBVIEW_BOOTSTRAPPER}"
    ExecWait '"$PLUGINSDIR\WebView2Setup.exe" /silent /install' $0
    Call HasWebView2
    ${If} $RuntimeVersion == ""
    ${OrIf} $RuntimeVersion == "0.0.0.0"
      MessageBox MB_ICONSTOP "WebView2 nije dostupan. Provjerite vezu i pokušajte ponovno." /SD IDOK
      SetErrorLevel 2
      Abort
    ${EndIf}
  ${EndIf}
  SetOutPath "$INSTDIR"
  ; Recover a previous interrupted upgrade before writing a new candidate.
  IfFileExists "$INSTDIR\Crawlvora.exe" existing restore
  restore:
    IfFileExists "$INSTDIR\Crawlvora.previous.exe" 0 existing
    ClearErrors
    Rename "$INSTDIR\Crawlvora.previous.exe" "$INSTDIR\Crawlvora.exe"
    IfErrors failed
  existing:
  ClearErrors
  File /oname=Crawlvora.pending.exe "${APP_EXE}"
  IfErrors failed
  ; Never delete a previous backup until the current executable is present.
  Delete "$INSTDIR\Crawlvora.previous.exe"
  IfFileExists "$INSTDIR\Crawlvora.exe" 0 promote
  ClearErrors
  Rename "$INSTDIR\Crawlvora.exe" "$INSTDIR\Crawlvora.previous.exe"
  IfErrors failed
  promote:
  ClearErrors
  Rename "$INSTDIR\Crawlvora.pending.exe" "$INSTDIR\Crawlvora.exe"
  IfErrors rollback
  ClearErrors
  WriteUninstaller "$INSTDIR\Uninstall-Crawlvora.exe"
  IfErrors uninstaller_failed
  !ifndef ACCEPTANCE
    CreateDirectory "$SMPROGRAMS\Crawlvora"
    CreateShortcut "$SMPROGRAMS\Crawlvora\Crawlvora.lnk" "$INSTDIR\Crawlvora.exe"
    CreateShortcut "$SMPROGRAMS\Crawlvora\Deinstaliraj.lnk" "$INSTDIR\Uninstall-Crawlvora.exe"
  !endif
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "Publisher" "Brendigo"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "URLInfoAbout" "https://tvrtke.com.hr/"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\Crawlvora.exe"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\Uninstall-Crawlvora.exe"'
  WriteRegStr HKCU "${UNINSTALL_KEY}" "QuietUninstallString" '"$INSTDIR\Uninstall-Crawlvora.exe" /S'
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair" 1
  Delete "$INSTDIR\Crawlvora.previous.exe"
  ; Only the known obsolete Inno uninstaller files, never any workspace data.
  !ifndef ACCEPTANCE
    ${If} $LegacyUninstaller == '"$INSTDIR\unins000.exe"'
      Delete "$INSTDIR\unins000.exe"
      Delete "$INSTDIR\unins000.dat"
      Delete "$INSTDIR\unins000.msg"
    ${EndIf}
  !endif
  Goto done
  uninstaller_failed:
    Delete "$INSTDIR\Crawlvora.exe"
  rollback:
    Rename "$INSTDIR\Crawlvora.previous.exe" "$INSTDIR\Crawlvora.exe"
  failed:
    Delete "$INSTDIR\Crawlvora.pending.exe"
    MessageBox MB_ICONSTOP "Instalacija nije uspjela. Zatvorite Crawlvora i pokušajte ponovno. Korisnički podaci nisu uklonjeni." /SD IDOK
    SetErrorLevel 2
    Abort
  done:
SectionEnd
!ifndef ACCEPTANCE
Section /o "Prečac na radnoj površini" Shortcut
  CreateShortcut "$DESKTOP\Crawlvora.lnk" "$INSTDIR\Crawlvora.exe"
SectionEnd
!endif
Section "Uninstall"
  SetShellVarContext current
  SetRegView 64
  ClearErrors
  Delete "$INSTDIR\Crawlvora.exe"
  IfErrors uninstall_failed
  Delete "$INSTDIR\Crawlvora.previous.exe"
  Delete "$INSTDIR\Crawlvora.pending.exe"
  !ifndef ACCEPTANCE
    Delete "$DESKTOP\Crawlvora.lnk"
    Delete "$SMPROGRAMS\Crawlvora\Crawlvora.lnk"
    Delete "$SMPROGRAMS\Crawlvora\Deinstaliraj.lnk"
    RMDir "$SMPROGRAMS\Crawlvora"
  !endif
  DeleteRegKey HKCU "${UNINSTALL_KEY}"
  Delete "$INSTDIR\Uninstall-Crawlvora.exe"
  RMDir "$INSTDIR"
  Goto uninstall_done
  uninstall_failed:
    MessageBox MB_ICONSTOP "Zatvorite Crawlvora prije deinstalacije." /SD IDOK
    SetErrorLevel 2
    Abort
  uninstall_done:
SectionEnd
