; Inno Setup script for Dhaagudu Moothalu
; Edit AppVersion and OutputDir below as needed

[Setup]
AppName=Dhaagudu Moothalu
AppVersion=1.0.0
DefaultDirName={pf}\DhaaguduMoothalu
DefaultGroupName=Dhaagudu Moothalu
OutputDir=out
OutputBaseFilename=DhaaguduMoothalu_Installer
Compression=lzma
SolidCompression=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Main application executable produced by PyInstaller
Source: "{#SrcExe}"; DestDir: "{app}"; Flags: ignoreversion

; Optional: you can include separate data folders if you did not bundle them into the exe
; Uncomment and adjust the lines below if you prefer shipping assets separately
; Source: "{#ProjectDir}\data\*"; DestDir: "{app}\data"; Flags: recursesubdirs createallsubdirs
; Source: "{#ProjectDir}\images\*"; DestDir: "{app}\images"; Flags: recursesubdirs createallsubdirs
; Source: "{#ProjectDir}\sounds\*"; DestDir: "{app}\sounds"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Dhaagudu Moothalu"; Filename: "{app}\DhaaguduMoothalu.exe"
Name: "{commondesktop}\Dhaagudu Moothalu"; Filename: "{app}\DhaaguduMoothalu.exe"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Run]
Filename: "{app}\DhaaguduMoothalu.exe"; Description: "Launch Dhaagudu Moothalu"; Flags: nowait postinstall skipifsilent

; --- Script constants to make the ISS file portable ---
[Code]
function InitializeSetup(): Boolean;
begin
  // Provide defaults for the {#SrcExe} and {#ProjectDir} constants when compiled via ISCC
  Result := True;
end;

; If you compile this file with ISCC from the project root, pass compiler defines to set these
; Example (from command line):
; ISCC /DMyAppName="DhaaguduMoothalu" /DSrcExe="dist\\DhaaguduMoothalu.exe" installer.iss

; Fall back definitions when not provided
#ifndef SrcExe
#define SrcExe "dist\DhaaguduMoothalu.exe"
#endif
#ifndef ProjectDir
#define ProjectDir "."
#endif
