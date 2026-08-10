# eSim Automated Tool Manager — Design Document

## 1. Problem framing and scope decisions

eSim depends on external tools (Ngspice, KiCad, Ngveri, etc.) that today
have to be installed and kept up to date by hand. That's fine once; it
becomes a support burden across contributors on different OSes and
different tool versions, and it's the actual source of a large fraction
of "eSim doesn't work" bug reports.

Scope decision made up front, and worth stating explicitly because it
drives every other design choice: **this manager does not reimplement
package management.** It orchestrates the OS-native package managers
(`apt` on Linux, `choco` on Windows, `brew` on macOS) rather than
downloading and unpacking binaries itself. The alternative — a
tool-manager that fetches tarballs/installers directly per platform —
gives finer control (works on machines without apt/choco/brew) but is a
much bigger surface: you inherit responsibility for checksum
verification, install-path conventions per OS, uninstall handling, and
staying in sync with upstream release pages. For a prototype whose job
is to prove the architecture, riding on package managers is the correct
trade-off. It's also the honest trade-off to flag to a reviewer rather
than pretending the manager is more self-sufficient than it is.

## 2. Architecture overview

```
                        +----------------------+
                        |         CLI          |   (cli.py)
                        |  list/status/install  |
                        |  update/check-deps/   |
                        |  configure/log         |
                        +----------+-----------+
                                   |
        +--------------------+----+----+-------------------+
        |                    |         |                   |
        v                    v         v                   v
+---------------+  +----------------+  +--------------+  +------------+
|   Installer   |  |    Updater     |  |  Dependency  |  |   Config   |
|installer.py   |  |  updater.py    |  |   Checker    |  |  config.py |
|               |  |                |  |dependency_   |  |            |
|- install_tool |  |- check_for_    |  | checker.py   |  |- registry  |
|- get_installed|  |  update        |  |              |  |  loader    |
|  _version     |  |- update_tool   |  |- check_deps  |  |- user cfg  |
|- check_version|  |                |  |              |  |- PATH mgmt|
|  _ok          |  |                |  |              |  |            |
+-------+-------+  +--------+-------+  +------+-------+  +-----+------+
        |                    |                 |               |
        +--------------------+-----------------+---------------+
                                   |
                                   v
                    +-------------------------------+
                    |     tools_registry.json        |
                    | (static: per-tool metadata,    |
                    |  install commands, version     |
                    |  regexes, min versions, deps)  |
                    +-------------------------------+
                                   |
                                   v
                    +-------------------------------+
                    |   logger_setup.py (cross-      |
                    |   cutting: every module logs   |
                    |   to ~/.esim_tool_manager/      |
                    |   tool_manager.log)             |
                    +-------------------------------+
```

Every module talks to the registry and to the logger; modules don't call
each other except where genuinely needed (`updater` and `cli.configure`
reuse `installer`'s helpers rather than duplicating subprocess logic).

## 3. Module breakdown

### 3.1 `tools_registry.json` — static tool metadata
Declarative source of truth: which binary to look for, which command/regex
extracts its version, minimum acceptable version, OS-level dependencies,
and the install package name per platform/manager. Adding a new tool to
the manager means adding a JSON entry, not writing new code — this is the
main lever for extensibility.

### 3.2 `config.py` — configuration handling
Two different kinds of "configuration" are conflated in the requirements
list, and the design keeps them explicitly separate:
- **Static registry config** (what tools exist, how to install them) —
  read-only, ships with the tool.
- **User/runtime config** (`~/.esim_tool_manager/config.json`) — which
  tools this user has installed, at what version, at what path. Updated
  automatically after every successful install.

PATH/environment handling is deliberately conservative: `register_path()`
always updates `os.environ["PATH"]` for the current process, but only
appends to the user's shell rc file when `persist=True` is explicitly
passed. Silently editing `.bashrc` is the kind of side effect that
should require opt-in, not be a default.

### 3.3 `installer.py` — tool installation management
- `install_tool()` dispatches to `apt-get` / `choco` / `brew` based on
  the current platform and the registry entry, with a `dry_run` flag so
  the exact command can be inspected/demoed without root access or an
  internet connection.
- `get_installed_version()` runs the tool's own version command and
  extracts the version via the registry's regex — this is what lets
  "version control" be meaningful rather than just "is it installed."
- `check_version_ok()` compares installed vs. `min_version` from the
  registry using a best-effort leading-number comparison. This is
  intentionally simple (not full semver) because tool version schemes
  here aren't semver-consistent (e.g., Ngspice uses bare integers).
- Root detection (`_apt_prefix`) avoids hardcoding `sudo`, since it
  doesn't exist in every environment (e.g. containers already running
  as root) — a hardcoded `sudo` would make the tool fail in exactly
  those environments.

### 3.4 `updater.py` — update/upgrade system
`check_for_update()` queries the package manager's own index
(`apt-cache policy` on Linux, `choco outdated` on Windows, `brew
outdated --json=v2` on macOS) for the candidate version and compares it
to the installed version. `update_tool()` runs the manager's upgrade
command.

### 3.5 `dependency_checker.py` — dependency checker
Two checks: (1) is the tool's own binary discoverable on PATH, (2) are
its declared OS packages installed (via `dpkg -s` on Debian-based
Linux). Returns a structured `DependencyReport` rather than a bare
bool, so the CLI/GUI layer can show *what's* missing, per the
requirement to "provide feedback ... if dependencies are missing."
Non-Linux dependency verification is explicitly marked unimplemented
rather than silently skipped.

### 3.6 `logger_setup.py` — action logging
Every install/update/dependency-check/configure action logs to both
stdout and a persistent file (`~/.esim_tool_manager/tool_manager.log`),
satisfying the "log of actions taken" requirement without each module
having to manage its own log file.

### 3.7 `cli.py` — user interface
A subcommand-based CLI (`list`, `status`, `install`, `check-deps`,
`check-update`, `update`, `configure`, `log`). A CLI was chosen over a
GUI for the prototype because it's what a reviewer can actually run in
five minutes without a display server, and because eSim itself is
frequently used in headless/lab environments — a GUI wrapper (e.g. a
PyQt front-end, since eSim already uses PyQt) is a natural follow-up
that would call the exact same module functions.

## 4. Data flow example: `esim-tool-manager install ngspice`

1. CLI parses args, calls `installer.install_tool("ngspice")`.
2. `installer` loads `tools_registry.json`, resolves platform via
   `config.get_current_platform()`, picks the `apt` entry.
3. Builds and runs `apt-get install -y ngspice` (or `sudo` variant).
4. On success, calls `get_installed_version()` to confirm what actually
   landed, then `config.record_installed_tool()` to persist it.
5. Every step is logged via `logger_setup`.

## 5. What's covered vs. the requirement list

| Requirement | Status |
|---|---|
| Tool Installation Management | Implemented (apt/choco/brew dispatch, version detection) |
| Update and Upgrade System | Implemented for apt/choco/brew package-manager flows |
| Configuration Handling | Implemented (user config persistence + PATH management) |
| Dependency Checker | Implemented (binary + OS package checks, structured report) |
| User Interface | Implemented (CLI: list/status/install/update/check-deps/configure/log) |
| Cross-platform (optional) | Registry supports Windows/macOS entries; only Linux/apt paths were live-tested |

Two things this prototype does **not** do, stated plainly rather than
glossed over:
- It doesn't verify installer checksums/signatures beyond what the
  underlying package manager already does.
- Windows/macOS code paths are written and structurally symmetric with
  Linux but were not executed against real choco/brew installs in this
  environment — only apt was exercised end-to-end.

## 6. Possible next steps
- PyQt GUI front-end reusing the same module functions (eSim's own UI
  is PyQt-based, so this would fit naturally).
- Parallel/batch install of eSim's full dependency set in one command.
- Signature/checksum verification for any future direct-download path.
