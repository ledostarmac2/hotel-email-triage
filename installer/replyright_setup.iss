#define MyAppName "ReplyRight"
#define MyAppVersion "0.1.1"
#define MyAppPublisher "Waldorf Astoria New York"
#define MyAppExeName "ReplyRight.exe"
#define WebView2Url "https://go.microsoft.com/fwlink/p/?LinkId=2124703"

[Setup]
AppId={{58E9D4F9-EC76-48C9-B899-3FA76F3FCF24}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
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
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce

[Files]
Source: "..\dist\ReplyRight.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\.env"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\ReplyRight"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{commondesktop}\ReplyRight"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon; Check: IsAdminInstallMode
Name: "{userdesktop}\ReplyRight"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon; Check: not IsAdminInstallMode

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch ReplyRight"; Flags: nowait postinstall skipifsilent

[Code]
var
  DownloadPage: TDownloadWizardPage;

function GetDefaultDir(Param: String): String;
begin
  if IsAdminInstallMode then
    Result := ExpandConstant('{autopf}\ReplyRight')
  else
    Result := ExpandConstant('{localappdata}\Programs\ReplyRight');
end;

function IsWebView2Installed(): Boolean;
var
  Version: String;
begin
  Result :=
    RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) or
    RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) or
    RegQueryStringValue(HKCU, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version);
end;

function OnDownloadProgress(const Url, FileName: String; const Progress, ProgressMax: Int64): Boolean;
begin
  Result := True;
end;

procedure InstallWebView2IfMissing();
var
  ResultCode: Integer;
  Bootstrapper: String;
begin
  if IsWebView2Installed() then
    exit;

  DownloadPage := CreateDownloadPage(
    'Installing Microsoft Edge WebView2 Runtime',
    'ReplyRight uses the embedded Microsoft WebView2 runtime for its desktop window.',
    @OnDownloadProgress
  );
  DownloadPage.Add('{#WebView2Url}', 'MicrosoftEdgeWebView2Setup.exe', '');
  DownloadPage.Show;
  try
    DownloadPage.Download;
  finally
    DownloadPage.Hide;
  end;

  Bootstrapper := ExpandConstant('{tmp}\MicrosoftEdgeWebView2Setup.exe');
  if not Exec(Bootstrapper, '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    MsgBox('ReplyRight installed, but WebView2 Runtime could not be started. Install it from Microsoft if the desktop window does not open.', mbInformation, MB_OK);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    InstallWebView2IfMissing();
end;
