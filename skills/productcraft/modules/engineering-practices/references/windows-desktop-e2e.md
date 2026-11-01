# End-to-end tests for Windows desktop apps

Read this when writing, running or stabilizing GUI tests for a native Windows application: WPF, WinForms, WinUI 3 or UWP, Win32 or MFC, Qt. Web apps belong to `../../builder-tools/references/playwright-web-testing.md`. Electron and WebView2 apps are mostly web content: drive that layer with Playwright (its Electron support, or a connection over the Chrome DevTools Protocol to a WebView2 started with a remote-debugging port) and keep desktop automation for the native shell around it. Unit and component tests stay the base of the suite; GUI tests cover a few critical flows end to end.

## How it works

Windows exposes every window and control through **UI Automation (UIA)**, its accessibility API. Each UI framework ships a provider that publishes a tree of elements with properties (AutomationId, Name, ControlType, ClassName, IsEnabled) and patterns (Invoke for buttons, Value for text fields, Toggle, SelectionItem, ExpandCollapse, Scroll). A test finds elements by property and either calls a pattern or sends real mouse and keyboard input.

| Driver | Language | Use when |
|---|---|---|
| pywinauto 0.6 with `backend="uia"` | Python (pytest) | The team writes tests in Python, or the app is not .NET |
| FlaUI (UIA3) | C# with xUnit, NUnit or MSTest | The app and its team are .NET; tests live in the same solution |
| Appium with a Windows driver | Any WebDriver client | An existing Appium suite must cover Windows too; check the driver's maintenance status first, since Microsoft's WinAppDriver has seen little development in recent years |

Inspect the tree before writing a locator: Accessibility Insights for Windows (free, Microsoft) or `inspect.exe` from the Windows SDK show each element's properties; in pywinauto, `window.print_control_identifiers()` prints the subtree.

## Make the app testable first

Stable identifiers are the biggest single lever, and they are an accessibility fix as well: a control without a name is invisible to screen-reader users too.

| Framework | Stable identifier | Notes |
|---|---|---|
| WPF | `AutomationProperties.AutomationId`, or `x:Name` (used as the AutomationId when none is set) | Name comes from content or `AutomationProperties.Name` |
| WinForms | The control's `Name` property becomes the AutomationId | `AccessibleName` sets the UIA Name, not the id |
| WinUI 3, UWP | `AutomationProperties.AutomationId` | Full UIA support |
| Win32, MFC | The dialog control ID, exposed as a numeric AutomationId | Keep resource IDs stable across releases |
| Qt | Set `objectName` and `accessibleName` on widgets tests touch | Check in an inspector which property your Qt version maps to AutomationId; Qt 5 releases before 5.12 expose MSAA rather than native UIA, with fewer properties |

- Keep the ids in one constants file per screen so app and tests share them.
- Custom-drawn controls (owner-drawn lists, canvases, OpenGL or DirectX views, game engines) publish nothing inside. Add an automation peer (WPF `AutomationPeer`, a UIA provider for Win32), or a test-only hook that reports state, before reaching for image matching.
- Give the app a **testability seam for its data folder**, such as a `--data-dir` argument or an environment variable it reads on purpose (see Isolation).

## Locators and actions

Locator preference: AutomationId, then Name plus ControlType, then ClassName with an index as a last resort. Names change with the UI language and copy edits; ids do not.

- **Patterns** (`invoke()`, `set_edit_text()`, `select()`, `toggle()`) act without moving the mouse and work even when the window is not in front. Prefer them for setup and navigation.
- **Real input** (`click_input()`, `type_keys()`) goes through the mouse and keyboard and needs the window visible, unobscured and focused. Use it when input handling itself is under test (key-down validation, shortcuts, drag and drop), since patterns can skip handlers that only real input triggers.
- Assert on content and state (`window_text()`, `get_value()`, `is_enabled()`, `get_toggle_state()`), never on pixel coordinates.

## Fixtures and screen objects (pytest and pywinauto)

```python
# conftest.py
import os, subprocess, pytest
from pywinauto import Application

APP = os.environ["APP_PATH"]            # the built executable under test; no default path
TITLE_RE = os.environ.get("APP_TITLE_RE", ".*")

@pytest.fixture
def main_window(request, tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    proc = subprocess.Popen([APP, "--data-dir", str(data)])   # the app's own testability seam
    try:
        app = Application(backend="uia").connect(process=proc.pid, timeout=30)
        win = app.window(title_re=TITLE_RE, control_type="Window")
        win.wait("visible ready", timeout=30)                  # past the splash screen
        yield win
    finally:
        report = getattr(request.node, "rep_call", None)
        if report is not None and report.failed:
            out = tmp_path / "failure.png"
            try:
                win.capture_as_image().save(out)               # needs Pillow
                print(f"screenshot: {out}")
            except Exception as exc:                            # capture must not hide the real failure
                print(f"no screenshot: {exc}")
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)
```

```python
# screens/login.py
from pywinauto.timings import wait_until

class LoginScreen:
    def __init__(self, win):
        self.win = win

    def field(self, auto_id):
        return self.win.child_window(auto_id=auto_id, control_type="Edit")

    def sign_in(self, user, password):
        self.field("usernameInput").set_edit_text(user)
        self.field("passwordInput").set_edit_text(password)
        self.win.child_window(auto_id="btnLogin", control_type="Button").invoke()

    def error_text(self):
        label = self.win.child_window(auto_id="lblError")
        label.wait("visible", timeout=10)
        return label.window_text()

    def wait_for_status(self, text, timeout=10):
        status = self.win.child_window(auto_id="lblStatus")
        wait_until(timeout, 0.25, lambda: status.window_text() == text)
```

`taskkill /T` ends the whole process tree, so helper processes the app started do not survive the test. Credentials come from environment variables for a test account and are never logged; redact typed text in any step trace you add.

## Waiting

- No fixed sleeps. Wait for a state: `spec.wait("visible enabled", timeout=...)`, `spec.wait_not("visible")` for spinners, or `wait_until(timeout, interval, predicate)` for anything else.
- Dialogs, message boxes and the drop-down of many combo boxes are separate top-level windows. Find them from the application (`app.window(title="Confirm delete")`) or the desktop (`Desktop(backend="uia").window(title_re=...)`), not as children of the main window.
- Startup: wait for the main window by AutomationId or title, not "the first window", which may be a splash screen or an update prompt.

## Isolation

- **A fresh process per test,** or per test class at most. A session-wide app instance leaks state between tests and makes failures depend on order.
- **Per-test data folders need the app's cooperation.** Redirecting `APPDATA`, `LOCALAPPDATA` and `TEMP` in the child's environment only works for code that reads those variables. The usual Windows APIs (`SHGetKnownFolderPath`, .NET `Environment.GetFolderPath`, Qt `QStandardPaths`) resolve folders from the user profile and ignore them. Use the app's data-dir seam, a dedicated Windows test account, or a disposable virtual machine, and check after a run that the real profile was not touched.
- **Registry and machine state:** writes under `HKCU` or `HKLM` persist. Reset them in teardown, or run the suite in a throwaway environment: a CI virtual machine, or Windows Sandbox (Windows 10 or 11 Pro, Enterprise or Education) for a clean image per run.
- **Hangs:** cap each test with `pytest-timeout`, and end the process tree in teardown even when the test failed.

## Running in CI

- UI Automation and real input need an interactive desktop session. GitHub-hosted `windows-latest` runners provide one. A self-hosted runner installed as a Windows service runs in session 0, which has no interactive desktop: run it as a process in a logged-on session with automatic logon, and keep the screen from locking.
- Minimizing or disconnecting a Remote Desktop session stops the desktop from rendering; real-input tests then fail. Use a console session or keep the session visible.
- Pin the resolution and display scaling, and record them with the artifacts; screenshots and any coordinate-based step depend on them.
- Always upload artifacts: failure screenshots, the app's own logs, JUnit XML.

```yaml
jobs:
  desktop-e2e:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r tests/e2e/requirements.txt     # pinned pywinauto, pytest, pytest-timeout, Pillow
      - run: dotnet build -c Release                       # or the app's real build command
      - run: pytest tests/e2e --junitxml=artifacts/e2e.xml --timeout=120
        env:
          APP_PATH: ${{ github.workspace }}\src\App\bin\Release\net8.0-windows\App.exe   # match the real output path
      - uses: actions/upload-artifact@v4
        if: always()
        with: { name: desktop-e2e, path: artifacts/, retention-days: 14 }
```

Point the app at test services and test accounts only; never at production data.

## Flaky tests

| Symptom | Usual cause | Fix |
|---|---|---|
| Element exists but the wait times out | Window minimized, off-screen or behind another window | `win.restore()` and `win.set_focus()` before real input; prefer patterns |
| Typing lands in the wrong place | Focus stolen by a notification or another window | Patterns instead of `type_keys`; a dedicated, quiet test session |
| `set_edit_text` fails | The control has no Value pattern (common with older custom or Qt controls) | Click the field, select all, `type_keys` with `with_spaces=True`; better, fix the control's automation support |
| Passes locally, fails in CI | Resolution, scaling, theme, UI language or a slower machine | Pin them in CI; wait for state instead of time; locate by AutomationId |
| Fails after a copy change | Locator by Name | AutomationId |
| Next test fails after a failure | Process or dialog left behind | Kill the process tree in teardown; fresh data folder per test |

Measure before calling a test stable: run it 20 times in a loop (`pytest-repeat` with `--count=20`, or a shell loop) and report the failure count.

## Last resort: image matching

When a control is opaque and no hook can be added, locate it by template matching on a screenshot (OpenCV `matchTemplate`). It breaks with scaling, themes, fonts and partial overlap: capture templates at the exact scaling the run uses, record that scaling with each artifact, keep the number of image-based steps small, and plan to replace them with an automation peer or test hook.

## Safety

- A desktop test drives the real mouse and keyboard of the session it runs in. Run it on a dedicated machine, virtual machine or test account, never on a desktop with the user's own documents open, where a misdirected keystroke edits the wrong window.
- The suite runs the built executable with the session's permissions. Build it from the reviewed revision, keep production credentials out of the environment, and run anything untrusted only in a disposable machine.

## Done when

- [ ] Every control the tests touch has a stable AutomationId, set in the app rather than worked around in the test.
- [ ] Each test starts a fresh process with its own data folder and leaves no process, dialog or registry change behind.
- [ ] No fixed sleeps; waits are on states, and dialogs are found as top-level windows.
- [ ] CI runs in an interactive session with pinned resolution and scaling, uploads screenshots, logs and JUnit XML, and uses test accounts only.
- [ ] New tests passed a repeated run, and the report names the command, the machine type, pass and fail counts, and anything not covered.
