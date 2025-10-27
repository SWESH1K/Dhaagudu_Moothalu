Dhaagudu Moothalu — Build an EXE and Windows installer
=====================================================

This repository includes helper scripts to build a single-file Windows executable with PyInstaller and optionally create a Windows installer using Inno Setup.

Files added
- `build_scripts/build_installer.ps1` — PowerShell script that installs PyInstaller (if needed), runs PyInstaller to build `dist\DhaaguduMoothalu.exe`, and invokes Inno Setup (if available).
- `installer/installer.iss` — Inno Setup script to package the built executable into a standard Windows installer (.exe).

Prerequisites
- Python 3.x installed and available as `python` on PATH.
- pip available (script upgrades pip/wheel automatically).
- (Optional, for installer) Inno Setup installed. Download from: https://jrsoftware.org/isinfo.php . The Inno Setup Compiler `ISCC.exe` should be on PATH or in the default installation folder.

Quick build steps
1. Open PowerShell (recommended: run as Administrator if you want a system-wide install). Change to the repository root:

   ```powershell
   cd "d:\Dhaagudu Moothalu"
   ```

2. Run the build script (Windows PowerShell):

   ```powershell
   .\build_scripts\build_installer.ps1
   ```

   The script will:
   - install requirements from `requirements.txt` and PyInstaller
   - run PyInstaller to create `dist\DhaaguduMoothalu.exe`
   - if Inno Setup is installed, it will try to compile `installer\installer.iss` and place the resulting installer in `out\`.

3. If you don't have Inno Setup or the automated step fails, open `installer\installer.iss` in the Inno Setup IDE and compile manually. Ensure the `Source` line points at the built exe (`dist\DhaaguduMoothalu.exe`) or pass a define to ISCC, for example:

   ```powershell
   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DSrcExe="dist\\DhaaguduMoothalu.exe" installer\\installer.iss
   ```

Notes & tips
- The PowerShell script uses PyInstaller `--onefile`. This embeds assets added with `--add-data` inside the single executable where PyInstaller can access them at runtime via the `_MEIPASS` temporary folder. If you prefer shipping data files separately, modify `installer\installer.iss` to include `data\*`, `images\*`, etc., as files to copy into `{app}`.
- If the game needs to be run as a server/client pair, only the client is packaged here. If you also want a server installer or service, tell me and I can add a separate packaging script for it.
- The default executable name is `DhaaguduMoothalu.exe`. You can change the name or version by editing `build_scripts/build_installer.ps1` or the `.iss` file.

Troubleshooting
- If PyInstaller fails with missing imports, check the PyInstaller output for errors and add hidden imports or hook files as needed.
- If Inno Setup compilation fails, open the `.iss` file in the Inno Setup IDE to get a clearer error message.

Next steps (optional enhancements)
- Add an automated CI job to produce signed installers.
- Add a small LICENSE / EULA to be shown at install time via the Inno Setup script.
- Add desktop shortcuts options and uninstaller customization.

If you want, I can also:
- run the build locally (I cannot run external installers from here) or
- add a batch (.bat) wrapper in addition to the PowerShell script.
