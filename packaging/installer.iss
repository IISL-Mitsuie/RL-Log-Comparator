#define MyAppName "RL-Log-Comparator"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "IISL Mitsuie Lab"

#define MyAppExeName "RL-Log-Comparator.exe"

[Setup]
; アプリケーション一意ID
AppId={{C9C1FFA6-677E-4772-8419-E94C1F7F7772}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\RL-Log-Comparator
DefaultGroupName={#MyAppName}
OutputDir=..\dist_installer
OutputBaseFilename=RL_Log_Comparator_Setup_v{#MyAppVersion}
SetupIconFile=app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes

; バージョンアップ時のプロセス自動検知・終了設定 (上書き更新時のファイルロック防止)
CloseApplications=yes
CloseApplicationsFilter=*.exe
RestartApplications=no

#ifndef SourceDir
#define SourceDir "..\dist\RL-Log-Comparator"
#endif

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs


[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

