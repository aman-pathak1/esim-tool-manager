# Execution & Testing Guide

This guide documents commands that were **actually run** against a live
Debian/Ubuntu container while building this prototype, with their real
output. Nothing in this file is a coverage-percentage estimate or a
projected/simulated result — where something wasn't tested, it says so.

## 1. Setup

```bash
unzip esim-tool-manager.zip
cd esim-tool-manager
python3 --version        # need 3.8+
python3 -m tool_manager.cli list
```

No `pip install` needed (see `requirements.txt`).

## 2. Test log (Linux / apt) — actually executed

### 2.1 Baseline: nothing installed yet
```
$ python3 -m tool_manager.cli list
Tool       Registry min ver   Installed ver   Path
----------------------------------------------------------------------
ngspice    35                 not installed
kicad      6                  not installed
ngveri     1.0                not installed
gnuplot    5.0                not installed
```

### 2.2 Dry-run install (no side effects, prints exact command)
```
$ python3 -m tool_manager.cli install ngspice --dry-run
Installing ngspice (dry_run=True)...
Done.

log:
$ apt-get install -y ngspice
[ngspice] Install command completed successfully.
[ngspice] Dry run complete -- nothing was actually installed.
```

### 2.3 Real install (root, no sudo binary present -> auto-detected)
```
$ python3 -m tool_manager.cli install ngspice
Installing ngspice (dry_run=False)...
Done.

log:
$ apt-get install -y ngspice
[ngspice] Install command completed successfully.
[ngspice] Recorded install: version=42, path=/usr/bin/ngspice
```

### 2.4 Status check after real install
```
$ python3 -m tool_manager.cli status ngspice
ngspice: installed version=42 -> OK (meets min version)
```

### 2.5 Update check (apt candidate lookup)
```
$ python3 -m tool_manager.cli check-update ngspice
ngspice: up to date (42)
```

### 2.6 Dependency check
```
$ python3 -m tool_manager.cli check-deps ngspice
Tool: ngspice
  Binary found: True
  Missing dependencies: none

$ python3 -m tool_manager.cli check-deps kicad     # not installed
Tool: kicad
  Binary found: False
  Missing dependencies: ['python3-wxgtk4.0']
  Note: 'kicad' not found on PATH.
```

### 2.7 Configure / PATH handling (dry-run, doesn't touch .bashrc)
```
$ python3 -m tool_manager.cli configure ngspice --dry-run
PATH updated for this session only. To persist:
echo 'export PATH="$PATH:/usr/bin"' >> ~/.bashrc or ~/.zshrc && source ~/.bashrc or ~/.zshrc
```

### 2.8 Second tool, to confirm the registry pattern generalizes (not just ngspice-specific hacks)
```
$ python3 -m tool_manager.cli install gnuplot
Installing gnuplot (dry_run=False)...
Done.

$ python3 -m tool_manager.cli status gnuplot
gnuplot: installed version=6.0 -> OK (meets min version)
```

### 2.9 Log inspection
```
$ python3 -m tool_manager.cli log
<contents of ~/.esim_tool_manager/tool_manager.log,
 timestamped entries for every command above>
```

## 3. What was NOT tested here, stated plainly

- **Windows (`choco`) and macOS (`brew`) install/update paths** — code is
  written and structurally parallel to the apt path, but this environment
  has no Windows/macOS host, so these branches were not exercised live.
  If you have access to either, running `install`/`check-update` there
  and reporting back would be the single most valuable thing to add.
- **Non-Debian Linux** (`check-deps`'s `dpkg -s` dependency check assumes
  a Debian-based system; on Fedora/Arch etc. it will report "unknown"
  rather than a false positive, but won't actually verify anything).
- **KiCad / Ngveri real installs** were not run in this session (only
  `check-deps` against them, since they weren't installed) — only
  ngspice and gnuplot were installed end-to-end. The registry entries
  should work the same way, but "should" isn't "confirmed."

## 4. Manual verification commands (useful if something looks wrong)

```bash
# Confirm what the tool itself would run, without going through the CLI
python3 -c "from tool_manager.installer import get_installed_version; print(get_installed_version('ngspice'))"

# Inspect the user config the manager wrote
cat ~/.esim_tool_manager/config.json

# Inspect the raw log file
cat ~/.esim_tool_manager/tool_manager.log
```

## 5. Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'tool_manager'` | Running from wrong directory | `cd` into the folder that directly contains `tool_manager/` |
| `apt-get: command not found` (Windows) | Wrong platform, apt is Linux-only | Use `choco` path — requires Chocolatey installed |
| Install fails with permission error | No root / sudo access | Run as admin/root, or use `--dry-run` to inspect the command instead |
| `check-update` says "not implemented" | Manager other than apt | Expected — only apt update-checking is implemented in this prototype |
