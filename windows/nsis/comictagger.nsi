;ComicTagger Installer
!addplugindir .

!include release.nsh

;--------------------------------
;Include Modern UI

!include "MUI2.nsh"

;--------------------------------

;General
	;file name
	OutFile "ComicTagger v${RELEASE_STR}.exe"

	;Default installation folder
	InstallDir "$PROGRAMFILES\ComicTagger"

	;Request application privileges for Windows Vista
	RequestExecutionLevel admin

	InstallDirRegKey HKLM "Software\ComicTagger" ""

	;Show all languages, despite user's codepage
	;!define MUI_LANGDLL_ALLLANGUAGES

;--------------------------------
;Variables

  Var StartMenuFolder 
	
;--------------------------------
;Interface Configuration

	!define MUI_ICON "installer.ico"
	!define MUI_WELCOMEFINISHPAGE_BITMAP "side_graphic.bmp"  ;shoukd be 164x314
	!define MUI_HEADERIMAGE
	!define MUI_HEADERIMAGE_BITMAP "top_graphic.bmp" ; ;should be 150x57
	;!define MUI_ABORTWARNING
	!define MUI_WELCOMEPAGE_TITLE $(app_WelcomePageTitle)
	!define MUI_WELCOMEPAGE_TEXT $(app_WelcomePageText) 

	!define  MUI_LICENSEPAGE_TEXT_TOP $(app_LicensePageTextTop)
	;!define  MUI_LICENSEPAGE_TEXT_BOTTOM  $(app_LicensePageTextBottom)
	;!define  MUI_LICENSEPAGE_CHECKBOX	
	
	!define MUI_FINISHPAGE_NOAUTOCLOSE	

	!define MUI_FINISHPAGE_SHOWREADME "todo.txt"
	!define MUI_FINISHPAGE_SHOWREADME_TEXT "Show Release Notes"
	!define MUI_FINISHPAGE_SHOWREADME_NOTCHECKED
	
	!define MUI_FINISHPAGE_TITLE $(app_FinishPageTitle)
	!define MUI_FINISHPAGE_TEXT $(app_FinishPageText)

	!define MUI_FINISHPAGE_LINK $(app_FinishPageLink)
	!define MUI_FINISHPAGE_LINK_LOCATION  "http://code.google.com/p/comictagger/"

	;Start Menu Folder Page Configuration
	!define MUI_STARTMENUPAGE_REGISTRY_ROOT "HKLM" 
	!define MUI_STARTMENUPAGE_REGISTRY_KEY "Software\ComicTagger" 
	!define MUI_STARTMENUPAGE_REGISTRY_VALUENAME "Start Menu Folder"
	!define MUI_STARTMENUPAGE_DEFAULTFOLDER "ComicTagger"
    
	;--------------------------------
;Pages

	!insertmacro MUI_PAGE_WELCOME
	
    !insertmacro MUI_PAGE_LICENSE "license.txt"

	!insertmacro MUI_PAGE_DIRECTORY
	!insertmacro MUI_PAGE_STARTMENU Application $StartMenuFolder
	!insertmacro MUI_PAGE_INSTFILES
	!insertmacro MUI_PAGE_FINISH
 
;--------------------------------
;Languages
!include "languages.nsh"

;--------------------------------
;Reserve Files
  
  ;If you are using solid compression, files that are required before
  ;the actual installation should be stored first in the data block,
  ;because this will make your installer start faster.
  
  !insertmacro MUI_RESERVEFILE_LANGDLL

;--------------------------------
	;App Name and file
	Name "$(app_AppName) ${RELEASE_STR}"

;Installer Sections

Section "Install Section" SecInstall

	SetOutPath "$INSTDIR"
	File /r ..\dist\*
	File ..\..\todo.txt

	;Store installation folder
	WriteRegStr HKLM "Software\ComicTagger" "" $INSTDIR

	;  Add registry entries for Control Panel Uninstall
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ComicTagger" \
                 "DisplayName" "ComicTagger"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ComicTagger" \
                 "UninstallString" "$\"$INSTDIR\uninstall.exe$\""
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ComicTagger" \
                 "QuietUninstallString" "$\"$INSTDIR\uninstall.exe$\" /S"	
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ComicTagger" \
                 "DisplayVersion" "${RELEASE_STR}"	
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ComicTagger" \
                 "Publisher" "ComicTagger"
				 
	;Create uninstaller
	WriteUninstaller "$INSTDIR\Uninstall.exe"

	!insertmacro MUI_STARTMENU_WRITE_BEGIN Application

		;Create shortcuts
		CreateDirectory "$SMPROGRAMS\$StartMenuFolder"
		CreateShortCut "$SMPROGRAMS\$StartMenuFolder\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
		CreateShortCut "$SMPROGRAMS\$StartMenuFolder\ComicTagger.lnk" "$INSTDIR\comictagger.exe"

	!insertmacro MUI_STARTMENU_WRITE_END

	CreateShortCut "$DESKTOP\ComicTagger.lnk" "$INSTDIR\comictagger.exe" ""

	
SectionEnd

;--------------------------------
;Installer Functions

Function .onInit

  !insertmacro MUI_LANGDLL_DISPLAY

FunctionEnd


;--------------------------------
;Uninstaller Section

Section "Uninstall"

	Delete "$INSTDIR\*"
	RMDir /r "$INSTDIR\imageformats"
	RMDir /r "$INSTDIR\PyQt4.uic.widget-plugins"
	
	Delete "$INSTDIR\Uninstall.exe"

	RMDir "$INSTDIR"

    Delete "$DESKTOP\ComicTagger.lnk"

	!insertmacro MUI_STARTMENU_GETFOLDER Application $StartMenuFolder

		Delete "$SMPROGRAMS\$StartMenuFolder\Uninstall.lnk"
		Delete "$SMPROGRAMS\$StartMenuFolder\ComicTagger.lnk"
		RMDir "$SMPROGRAMS\$StartMenuFolder"

	DeleteRegKey /ifempty HKLM "Software\ComicTagger"
	DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ComicTagger"
	
SectionEnd


