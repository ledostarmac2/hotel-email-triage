; ReplyRight v0.1.4 — Inno Setup installer script
; Builds a single-file Windows installer from dist\ReplyRight.exe

#define AppName      "ReplyRight"
#define AppVersion   "0.2.0"
#define AppPublisher "Waldorf Astoria Reservations"
#define AppURL       "https://github.com/brianmoses/hotel-email-triage"
#define AppExeName   "ReplyRight.exe"
#define SourceExe    "dist\ReplyRight.exe"
#define AppIcon      "outlook_dashboard\static\replyright.ico"

[Setup]
AppId={{E4A7C2B1-3F8D-4E9A-B2C5-6D7E8F9A0B1C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=installer\output
OutputBaseFilename=ReplyRight-v{#AppVersion}-Setup
SetupIconFile={#AppIcon}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName} {#AppVersion}
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} — Hotel email triage for reservations operations
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";  Description: "{cm:CreateDesktopIcon}";  GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon";  Description: "Launch {#AppName} when Windows starts"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "{#SourceExe}"; DestDir: "{app}"; DestName: "{#AppExeName}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}";          Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}";           Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}";           Filename: "{app}\{#AppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
