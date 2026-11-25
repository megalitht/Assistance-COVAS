; covas.iss — Installateur tout-en-un du COVAS (Inno Setup 6).
; Fabriqué par : CONSTRUIRE APPLICATION.bat --installateur  (voir construire_application.py)
;
; Un seul fichier pour tout le monde. À l'installation, la carte graphique est détectée :
;   - NVIDIA : version complète (grand modèle vocal + bibliothèques NVIDIA, ~4,6 Go)
;   - autre (AMD, Intel...) : version processeur (petit modèle, ~1 Go installé)
; Installé dans le profil de l'utilisateur (pas besoin d'être administrateur) : le COVAS écrit
; dans son propre dossier (réglages, journaux), ce que « Program Files » interdirait.

#ifndef Source
  #define Source "..\Application\COVAS"
#endif
#ifndef Version
  #define Version "1.0"
#endif

[Setup]
AppId={{8E4B1C52-6F0A-4C2B-9D47-C0A5B0E1D7A3}
AppName=COVAS
AppVerName=COVAS {#Version}
AppVersion={#Version}
AppPublisher=COVAS
DefaultDirName={localappdata}\Programs\COVAS
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\Application
OutputBaseFilename=Installer COVAS
Compression=lzma2/normal
SolidCompression=yes
LZMANumBlockThreads=8
WizardStyle=modern
UninstallDisplayName=COVAS — Assistance de bord
UninstallDisplayIcon={app}\COVAS.exe
CloseApplications=yes

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "bureau"; Description: "Créer un raccourci sur le Bureau"

[Files]
; Commun à toutes les versions
Source: "{#Source}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; \
  Excludes: "\Backend\nvidia,\Backend\module\modele_vocal_turbo,\Backend\data\studio\reglages.json"
; Réglages de la voix du studio : jamais écrasés par une mise à jour (l'ami a pu étalonner sa voix)
Source: "{#Source}\Backend\data\studio\reglages.json"; DestDir: "{app}\Backend\data\studio"; Flags: onlyifdoesntexist
; Carte NVIDIA seulement
Source: "{#Source}\Backend\nvidia\*"; DestDir: "{app}\Backend\nvidia"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: AvecNvidia
Source: "{#Source}\Backend\module\modele_vocal_turbo\*"; DestDir: "{app}\Backend\module\modele_vocal_turbo"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: AvecNvidia

[InstallDelete]
; Carte changée (NVIDIA -> AMD) depuis la dernière installation : on retire ce qui ne sert plus
Type: filesandordirs; Name: "{app}\Backend\nvidia"; Check: not AvecNvidia
Type: filesandordirs; Name: "{app}\Backend\module\modele_vocal_turbo"; Check: not AvecNvidia

[Icons]
Name: "{autoprograms}\COVAS"; Filename: "{app}\COVAS.exe"
Name: "{autoprograms}\Lisez-moi du COVAS"; Filename: "{app}\LISEZ-MOI.txt"
Name: "{autodesktop}\COVAS"; Filename: "{app}\COVAS.exe"; Tasks: bureau

[Run]
Filename: "{app}\LISEZ-MOI.txt"; Description: "Lire le mode d'emploi"; Flags: postinstall shellexec skipifsilent unchecked
Filename: "{app}\COVAS.exe"; Description: "Lancer le COVAS"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; Tout ce que le COVAS a créé en tournant (réglages, journaux, suivi de jeu, profil de la fenêtre)
Type: filesandordirs; Name: "{app}"

[Code]
var
  Nvidia: Boolean;
  NomCarte: String;

{ Cartes graphiques du PC (Windows les connaît toutes, même sur un portable à deux cartes) }
procedure DetecterCarte;
var
  Locator, Service, Cartes, Carte: Variant;
  I: Integer;
  Nom: String;
begin
  Nvidia := False;
  NomCarte := '';
  try
    Locator := CreateOleObject('WbemScripting.SWbemLocator');
    Service := Locator.ConnectServer('.', 'root\CIMV2');
    Cartes := Service.ExecQuery('SELECT Name FROM Win32_VideoController');
    for I := 0 to Cartes.Count - 1 do
    begin
      Carte := Cartes.ItemIndex(I);
      Nom := Carte.Name;
      if NomCarte <> '' then
        NomCarte := NomCarte + ', ';
      NomCarte := NomCarte + Nom;
      if Pos('NVIDIA', Uppercase(Nom)) > 0 then
        Nvidia := True;
    end;
  except
    Nvidia := False;
  end;
end;

function AvecNvidia: Boolean;
begin
  Result := Nvidia;
end;

{ « Installer COVAS.exe /PROCESSEUR » : version processeur même avec une carte NVIDIA (carte trop ancienne...) }
function ForcerProcesseur: Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), '/PROCESSEUR') = 0 then
      Result := True;
end;

function InitializeSetup: Boolean;
begin
  DetecterCarte;
  if ForcerProcesseur then
    Nvidia := False;
  Result := True;
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo,
  MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
var
  Version: String;
begin
  if Nvidia then
    Version := 'complète, pour carte NVIDIA (reconnaissance vocale sur la carte graphique)'
  else
    Version := 'processeur (pas de carte NVIDIA : la reconnaissance vocale utilise le processeur)';
  if NomCarte = '' then
    NomCarte := 'inconnue';
  Result := 'Carte graphique : ' + NomCarte + NewLine + 'Version installée : ' + Version
    + NewLine + NewLine + MemoDirInfo;
  if MemoTasksInfo <> '' then
    Result := Result + NewLine + NewLine + MemoTasksInfo;
end;
