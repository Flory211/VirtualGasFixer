Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!include "x64.nsh"
!include "WinVer.nsh"

!define PRODUCT "DJI Virtual Gas Fixer"
!define VERSION "1.0.0"
!define APPKEY "Software\DJIVirtualGasFixer"
!define UNINSTALLKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\DJIVirtualGasFixer"
!define INSTALLID "DJIVirtualGasFixer|NSIS|1"

Name "${PRODUCT}"
OutFile "..\dist\DJIVirtualGasFixer-Setup-${VERSION}.exe"
InstallDir "$LOCALAPPDATA\Programs\DJIVirtualGasFixer"
InstallDirRegKey HKCU "${APPKEY}" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
SetCompressorDictSize 32
ShowInstDetails show
ShowUninstDetails show
BrandingText "${PRODUCT}"
VIProductVersion "1.0.0.0"
VIAddVersionKey /LANG=1049 "ProductName" "${PRODUCT}"
VIAddVersionKey /LANG=1049 "FileDescription" "Мастер установки ${PRODUCT}"
VIAddVersionKey /LANG=1049 "FileVersion" "${VERSION}"
VIAddVersionKey /LANG=1049 "ProductVersion" "${VERSION}"
VIAddVersionKey /LANG=1049 "LegalCopyright" ""

!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Установка ${PRODUCT}"
!define MUI_WELCOMEPAGE_TEXT "Мастер установит программу управления газом для DJI RC RM330 и Xbox-контроллеров.$\r$\n$\r$\nУстановка выполняется для твоей учётной записи Windows.$\r$\n$\r$\nНажми «Далее», чтобы продолжить."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\DJIVirtualGasFixer.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Запустить ${PRODUCT}"
!insertmacro MUI_PAGE_FINISH
!define MUI_UNCONFIRMPAGE_TEXT_TOP "Будет удалена программа ${PRODUCT}.$\r$\nСохранённые настройки газа останутся для повторной установки."
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH
!insertmacro MUI_LANGUAGE "Russian"

!macro RequireClosed
check_running:
  System::Call 'kernel32::OpenMutexW(i 0x00100000, i 0, w "Local\DJIVirtualGasFixer") p.r0'
  StrCmp $0 0 application_closed
  System::Call 'kernel32::CloseHandle(p r0)'
  MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "Закрой ${PRODUCT}, чтобы продолжить." /SD IDCANCEL IDRETRY check_running
  Abort
application_closed:
!macroend

Function .onInit
  SetShellVarContext current
  ${IfNot} ${RunningX64}
    MessageBox MB_OK|MB_ICONSTOP "Нужна 64-разрядная Windows 10 или новее." /SD IDOK
    Abort
  ${EndIf}
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_OK|MB_ICONSTOP "Нужна Windows 10 или новее." /SD IDOK
    Abort
  ${EndIf}
  !insertmacro RequireClosed
FunctionEnd

Function .onVerifyInstDir
  ${GetRoot} "$INSTDIR" $0
  StrCmp $INSTDIR "" invalid_directory
  StrCmp $INSTDIR $0 invalid_directory
  StrCmp $INSTDIR "$0\" invalid_directory
  StrCmp $INSTDIR $WINDIR invalid_directory
  StrCmp $INSTDIR $SYSDIR invalid_directory
  StrCmp $INSTDIR $PROFILE invalid_directory
  StrCmp $INSTDIR $DESKTOP invalid_directory
  StrCmp $INSTDIR $DOCUMENTS invalid_directory
  StrCmp $INSTDIR $LOCALAPPDATA invalid_directory
  StrCmp $INSTDIR $APPDATA invalid_directory
  StrCmp $INSTDIR $PROGRAMFILES invalid_directory
  StrCmp $INSTDIR $PROGRAMFILES64 invalid_directory
  Return
invalid_directory:
  SetErrorLevel 1
  Abort
FunctionEnd

Section "Программа и меню «Пуск»" MainSection
  SectionIn RO
  !insertmacro RequireClosed
  Call .onVerifyInstDir
  SetShellVarContext current
  ClearErrors
  !include "payload-install.nsh"
  IfErrors install_failed
  SetOutPath "$INSTDIR"
  FileOpen $0 "$INSTDIR\install-id.txt" w
  IfErrors install_failed
  FileWrite $0 "${INSTALLID}"
  FileClose $0
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  IfErrors install_failed
  CreateDirectory "$SMPROGRAMS\${PRODUCT}"
  CreateShortcut "$SMPROGRAMS\${PRODUCT}\${PRODUCT}.lnk" "$INSTDIR\DJIVirtualGasFixer.exe"
  CreateShortcut "$SMPROGRAMS\${PRODUCT}\Инструкция.lnk" "$WINDIR\notepad.exe" '$\"$INSTDIR\README.md$\"'
  CreateShortcut "$SMPROGRAMS\${PRODUCT}\Удалить.lnk" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "${APPKEY}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALLKEY}" "DisplayName" "${PRODUCT}"
  WriteRegStr HKCU "${UNINSTALLKEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UNINSTALLKEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALLKEY}" "DisplayIcon" "$INSTDIR\DJIVirtualGasFixer.exe"
  WriteRegStr HKCU "${UNINSTALLKEY}" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
  WriteRegStr HKCU "${UNINSTALLKEY}" "QuietUninstallString" '$\"$INSTDIR\Uninstall.exe$\" /S'
  WriteRegDWORD HKCU "${UNINSTALLKEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALLKEY}" "NoRepair" 1
  WriteRegDWORD HKCU "${UNINSTALLKEY}" "EstimatedSize" ${PAYLOAD_KIB}
  Goto installation_done
install_failed:
  MessageBox MB_OK|MB_ICONSTOP "Не удалось установить все файлы. Проверь свободное место и доступ к выбранной папке." /SD IDOK
  SetErrorLevel 1
  Abort
installation_done:
SectionEnd

Section /o "Ярлык на рабочем столе" DesktopSection
  CreateShortcut "$DESKTOP\${PRODUCT}.lnk" "$INSTDIR\DJIVirtualGasFixer.exe"
  WriteRegDWORD HKCU "${APPKEY}" "DesktopShortcut" 1
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${MainSection} "Программа, необходимые библиотеки, инструкция и ярлыки в меню «Пуск»."
  !insertmacro MUI_DESCRIPTION_TEXT ${DesktopSection} "Добавить ярлык для быстрого запуска с рабочего стола."
!insertmacro MUI_FUNCTION_DESCRIPTION_END

Function un.onInit
  SetShellVarContext current
  FileOpen $0 "$INSTDIR\install-id.txt" r
  IfErrors not_our_install
  FileRead $0 $1
  FileClose $0
  StrCmp $1 "${INSTALLID}" valid_install
not_our_install:
  MessageBox MB_OK|MB_ICONSTOP "Не найдена установленная копия ${PRODUCT} в этой папке. Удаление отменено." /SD IDOK
  Abort
valid_install:
  !insertmacro RequireClosed
FunctionEnd

Section "Uninstall"
  SetShellVarContext current
  !insertmacro RequireClosed
  !include "payload-uninstall.nsh"
  ReadRegStr $0 HKCU "${APPKEY}" "InstallDir"
  StrCmp $0 $INSTDIR 0 keep_newer_registration
  ReadRegDWORD $0 HKCU "${APPKEY}" "DesktopShortcut"
  StrCmp $0 1 0 no_desktop_shortcut
  Delete "$DESKTOP\${PRODUCT}.lnk"
no_desktop_shortcut:
  Delete "$SMPROGRAMS\${PRODUCT}\${PRODUCT}.lnk"
  Delete "$SMPROGRAMS\${PRODUCT}\Инструкция.lnk"
  Delete "$SMPROGRAMS\${PRODUCT}\Удалить.lnk"
  RMDir "$SMPROGRAMS\${PRODUCT}"
  DeleteRegKey HKCU "${UNINSTALLKEY}"
  DeleteRegKey HKCU "${APPKEY}"
keep_newer_registration:
  Delete "$INSTDIR\install-id.txt"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  Goto uninstall_done
uninstall_failed:
  MessageBox MB_OK|MB_ICONSTOP "Не удалось удалить файл программы. Закрой программу, проверь доступ к её папке и повтори удаление. Запись в списке приложений и средство удаления сохранены." /SD IDOK
  SetErrorLevel 1
  Abort
uninstall_done:
SectionEnd
