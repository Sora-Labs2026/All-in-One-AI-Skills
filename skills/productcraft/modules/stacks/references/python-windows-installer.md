# Shipping a Python app as a Windows installer

Read this when a Python desktop or command-line application must reach Windows users who do not have Python installed: freezing it with PyInstaller or Nuitka, keeping it small and quick to start, wrapping it in an installer (Inno Setup, or MSI and MSIX alternatives), signing it, and testing the result on a clean machine. Python environments, packaging libraries as wheels and testing are in `python.md`; command-line design in `cli-tools.md`; release pipelines in `../../engineering-practices/references/ci-and-release.md`.

## Decide the shape first

| Question | Options |
|---|---|
| How is the app frozen? | **PyInstaller** (bundles the interpreter and bytecode; widest library support, fast builds) or **Nuitka** (compiles to C, then a native executable; slower builds, often faster startup, needs a C compiler) |
| One folder or one file? | **One folder** (an executable beside its libraries) starts faster, is easier to patch and triggers fewer antivirus false positives. **One file** unpacks itself to a temporary folder on every launch: slower start, more false positives, leftover temp files after crashes. Ship one folder inside an installer unless there is a reason not to |
| Which installer? | **Inno Setup** (free, scriptable `.iss` files, per-user or per-machine EXE installers); **MSI** through the WiX Toolset when IT departments deploy through Group Policy or Intune (check WiX's current terms for commercial use); **MSIX** for the Microsoft Store and clean install and uninstall, with packaging-model restrictions to check first |
| Who installs it? | Per-user (no administrator rights, installs under `%LOCALAPPDATA%\Programs`) or per-machine (administrator, `Program Files`, all users) |

Record the choices in the README or an ADR; changing the installer type or the application identifier later breaks upgrades for existing users.

## Licensing before shipping

- **PyInstaller** is GPL 2 with an exception that allows distributing bundled applications under any license. **Nuitka** is Apache 2.0.
- **Qt bindings:** PySide6 is LGPL 3 (dynamic linking, and users must be able to replace the Qt libraries, which a one-folder layout makes straightforward); PyQt6 is GPL 3 or commercial. Check before choosing.
- Every bundled package's license applies to the distribution. Generate a list of third-party licenses (for example with `pip-licenses`) and ship it with the app; ask before bundling anything with an unclear license.

## Build environment

- Build on Windows for Windows, on the architecture you ship (x64, and ARM64 if needed). Neither tool cross-compiles.
- Use a clean virtual environment with only runtime dependencies, from the project's lockfile. Development tools in the environment end up in the bundle.
- Pin the freezing tool's version in the lockfile or the build script; behavior and options change between major versions.
- Supported Windows follows the Python version: current Python releases need Windows 10 or later.
- Build in CI on a Windows runner so builds are reproducible and signing keys stay in the CI secret store.

## Freezing with PyInstaller

- Generate a spec file once (`pyinstaller --name OrderDesk --windowed --onedir src/orderdesk/__main__.py`), commit it, and build from it (`pyinstaller OrderDesk.spec --clean --noconfirm`). The spec is where data files, hidden imports, excludes, the icon and version information live.
- PyInstaller 6 (2023) moved the bundled files into an `_internal` subfolder next to the executable (`contents_directory` changes the name).
- `--windowed` (no console) for GUI apps; keep the console for command-line tools.
- Missing modules at runtime come from dynamic imports; add them as `hiddenimports` or install the community hooks package. Read `build/<name>/warn-<name>.txt` after each build.
- Data files: declare them in `datas` and locate them at runtime relative to the bundle (`sys._MEIPASS` in a frozen app), or package them inside your Python package and read them with `importlib.resources`, which works frozen and unfrozen.

## Freezing with Nuitka

- Needs a C compiler: Visual Studio Build Tools (MSVC) is the dependable choice on Windows; check Nuitka's documentation for which compilers support your Python version.
- Typical one-folder build for a Qt app:

```bat
python -m nuitka --standalone --windows-console-mode=disable ^
  --enable-plugin=pyside6 --include-qt-plugins=platforms,styles,imageformats ^
  --include-package-data=orderdesk --windows-icon-from-ico=assets\app.ico ^
  --company-name="Example Ltd" --product-name="Order Desk" ^
  --file-version=1.4.0.0 --product-version=1.4.0.0 ^
  --report=build\nuitka-report.xml --output-dir=build src\orderdesk\__main__.py
```

- `--windows-console-mode` replaced the older `--disable-console` flag; newer releases also accept a `--mode=` option for standalone and onefile builds. Use the options of the pinned version.
- Plugins (`--enable-plugin=pyside6`, `tk-inter`, `anti-bloat`) handle libraries with special needs; the compilation report lists every included module and file, which is the starting point for size work.
- Long build times are normal (minutes to tens of minutes); `--lto` and other optimizations lengthen them further. Measure startup before and after enabling them.

## Size and startup

Measure first: list the largest files in the output folder and the modules in the build report. Typical savings, in order of payoff:

- Remove dependencies the app does not need at runtime (test frameworks, build tools, notebooks), and use slimmer variants where they exist (`opencv-python-headless` when no OpenCV windows are shown).
- Exclude unused parts of large frameworks (Qt WebEngine, 3D and chart modules when unused) with the tool's exclude options, then run the full test checklist: an exclusion that breaks a rarely used screen shows up only there.
- Import heavy libraries lazily, inside the function that needs them, so the window appears before they load.
- Do not delete files from the output folder by hand after the build; libraries read their own metadata (`*.dist-info`) and data at runtime. Exclude through the build configuration so the result is reproducible.
- Do not compress executables with UPX: savings are small and antivirus false positives rise.

## Runtime behavior that differs when frozen

- `multiprocessing` on Windows needs `multiprocessing.freeze_support()` as the first statement under `if __name__ == "__main__":`, or child processes relaunch the whole app.
- Without a console, `sys.stdout` and `sys.stderr` can be `None`; libraries that print will crash. Configure logging to a file under the user's local application-data folder (`platformdirs` resolves it) and guard writes to standard streams.
- Never write to the installation folder at runtime: `Program Files` is read-only for standard users. Settings, caches and logs go under `%APPDATA%` or `%LOCALAPPDATA%`.
- Paths with spaces and non-ASCII user names (`C:\Users\José Müller\`) break naive path handling; use `pathlib` and test with such a profile.
- The VC++ runtime DLLs that Python itself needs are bundled by both tools. Extension modules occasionally need a newer runtime than the machine has; then the installer installs the matching Microsoft Visual C++ Redistributable (`vc_redist.x64.exe /install /quiet /norestart`) only when a check shows it is missing.

## Inno Setup essentials

```ini
#define AppVersion "1.4.0"

[Setup]
AppId={{REPLACE-WITH-A-GUID-GENERATED-ONCE-FOR-THIS-APP}
AppName=Order Desk
AppVersion={#AppVersion}
AppPublisher=Example Ltd
DefaultDirName={autopf}\Order Desk
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
UninstallDisplayIcon={app}\OrderDesk.exe
OutputBaseFilename=OrderDesk-{#AppVersion}-x64-setup

[Files]
Source: "build\OrderDesk\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\Order Desk"; Filename: "{app}\OrderDesk.exe"

[Run]
Filename: "{app}\OrderDesk.exe"; Description: "Start Order Desk"; Flags: nowait postinstall skipifsilent
```

- **`AppId` is the upgrade identity.** Generate a GUID once for this app (the Inno Setup IDE's Generate GUID command, or `[guid]::NewGuid()` in PowerShell), never reuse one from an example, and never change it; every later version then installs over the previous one. The doubled opening brace escapes the brace in Inno Setup syntax.
- `PrivilegesRequired=lowest` with the override dialog installs per-user by default and lets administrators choose all users; `{autopf}` and `{autoprograms}` follow that choice. `x64compatible` (Inno Setup 6.3 and later) also covers Windows on ARM running x64 code.
- The version shown to users comes from one place (the build script passes it to both the freezer and the installer); the executable's file version and the installer's version must match.
- **Uninstall** removes what the installer installed. User data under `%APPDATA%` stays unless the user agrees to remove it; never delete a folder the app did not create.
- Build the installer with `ISCC.exe /DAppVersion=1.4.0 installer\orderdesk.iss` in CI.

## Code signing and SmartScreen

- Unsigned executables trigger Windows SmartScreen warnings and more antivirus false positives. Sign with an Authenticode certificate: the main executable and other executables you ship, the installer, and the uninstaller (Inno Setup's `SignTool` directive with `SignedUninstaller=yes` signs it during compilation).
- Since June 2023, code-signing private keys must live on hardware (a token or an HSM, including cloud HSM signing services); a key file in the repository is not an option. Signing runs in CI against that service; credentials never appear in the chat or in logs.
- Use SHA-256 and an RFC 3161 timestamp (`signtool sign /fd sha256 /td sha256 /tr <timestamp-url> ...`) so signatures stay valid after the certificate expires. Verify with `signtool verify /pa /v <file>`.
- SmartScreen reputation builds over time and downloads. Microsoft's documentation since 2024 says EV certificates no longer receive immediate reputation, so expect warnings for early releases either way and check the current guidance before paying extra for EV. Report false positives through the antivirus vendor's submission portal; never tell users to disable protection.
- Buying a certificate, enrolling in a signing service and submitting to the Microsoft Store are the owner's decisions and steps.

## Test on a clean machine

Use Windows Sandbox or a fresh virtual machine with no Python installed:

- Fresh install as a standard user, and as an administrator choosing all users.
- Launch from the Start menu; first-run behavior; no console window for GUI apps; every major screen and feature (exclusions break rarely used paths).
- Upgrade over the previous released version: settings kept, shortcuts work, no duplicate entries in Installed apps.
- Uninstall: program files and shortcuts gone, user data handled as agreed.
- A user profile with spaces and non-ASCII characters; offline operation; behavior under the antivirus that ships with Windows.
- Signature present and valid on every executable and the installer.

## Done when

- [ ] The build runs from a script or CI job on Windows, from a clean environment and pinned tool versions, and produces the installer and a license list.
- [ ] The app starts and passes the smoke checklist above on a clean machine without Python, or the report marks the missing checks `NOT VERIFIED`.
- [ ] `AppId` is fixed, the version comes from one source, and upgrade over the previous release was tested.
- [ ] Executables, installer and uninstaller are signed and timestamped, or the report states that signing is pending the owner's certificate.
- [ ] Nothing was published, uploaded or submitted to a store without the user.
