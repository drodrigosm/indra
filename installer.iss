#define MyAppName "Costes Indra"
#define MyAppVersion "1.0.0"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={pf}\Costes Indra
DefaultGroupName={#MyAppName}
OutputDir=installer
OutputBaseFilename=Costes_Indra_Setup_v{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=icono_indra.ico

[Files]
Source: "dist\Costes_Indra\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Costes Indra"; Filename: "{app}\Costes_Indra.exe"; IconFilename: "{app}\Costes_Indra.exe"
Name: "{commondesktop}\Costes Indra"; Filename: "{app}\Costes_Indra.exe"; IconFilename: "{app}\Costes_Indra.exe"

[Run]
Filename: "{app}\Costes_Indra.exe"; Description: "Abrir Costes Indra"; Flags: nowait postinstall skipifsilent