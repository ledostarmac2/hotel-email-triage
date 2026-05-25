#define MyAppName "ReplyRight"
#ifndef MyAppVersion
  #define MyAppVersion "0.5.0"
#endif
#define MyAppPublisher "Waldorf Astoria New York"
#define MyAppExeName "ReplyRight.exe"

[Setup]
AppId={{58E9D4F9-EC76-48C9-B899-3FA76F3FCF24}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://www.waldorfastorianewyork.com/
AppSupportURL=https://www.waldorfastorianewyork.com/
AppUpdatesURL=https://github.com/ledostarmac2/hotel-email-triage/releases
DefaultDirName={code:GetDefaultDir}
DefaultGroupName={#MyAppName}
DisableDirPage=no
DisableProgramGroupPage=no
OutputDir=output
OutputBaseFilename=ReplyRightSetup-v{#MyAppVersion}
SetupIconFile=..\outlook_dashboard\static\replyright.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=ReplyRight hotel reservations email triage
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel1=Welcome to the ReplyRight Setup Wizard
WelcomeLabel2=This will install ReplyRight, the read-only hotel reservations email triage assistant, on your computer.
FinishedHeadingLabel=ReplyRight is ready
FinishedLabel=Setup has finished installing ReplyRight. You can launch it now or from the Start Menu shortcut.

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce

[Files]
Source: "..\dist\ReplyRight\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "data\*,*.sqlite3,*.sqlite,*.db,*.log"
Source: "sample.env"; DestDir: "{app}"; DestName: "sample.env"; Flags: ignoreversion

[Icons]
Name: "{group}\ReplyRight"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{userdesktop}\ReplyRight"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch ReplyRight"; Flags: nowait postinstall skipifsilent

[Code]
function GetDefaultDir(Param: String): String;
begin
  Result := ExpandConstant('{localappdata}\Programs\ReplyRight');
end;
