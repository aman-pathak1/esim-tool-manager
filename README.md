<<<<<<< HEAD
# eSim Automated Tool Manager — Prototype

Automates installation, dependency checking, updates, and PATH/config
management for eSim's external tools (Ngspice, KiCad, Ngveri, GnuPlot),
on top of the OS's native package manager (apt / choco / brew).

See `DESIGN.md` for the architecture writeup, `EXECUTION_GUIDE.md` for a
real (not simulated) test log, and `QUICK_REFERENCE.md` for a command
cheat sheet.

## Requirements

- Python 3.8+
- Linux: `apt-get` (Debian/Ubuntu). Root or passwordless `apt-get` access
  for actual (non-dry-run) installs/updates.
- Windows: [Chocolatey](https://chocolatey.org/install) installed and on PATH.
- macOS: [Homebrew](https://brew.sh) installed and on PATH.

No third-party Python packages are required — the prototype only uses
the standard library, so there's nothing to `pip install`.

## Running it

From the repo root:

```bash
# See all known tools and whether they're installed
python3 -m tool_manager.cli list

# Check a specific tool's installed version against the required minimum
python3 -m tool_manager.cli status ngspice

# Install a tool (use --dry-run first to see the exact command without
# executing it — useful if you don't have apt/sudo access in your shell)
python3 -m tool_manager.cli install ngspice --dry-run
python3 -m tool_manager.cli install ngspice

# Check OS-level dependencies for a tool
python3 -m tool_manager.cli check-deps kicad

# Check whether a newer version is available (apt only in this prototype)
python3 -m tool_manager.cli check-update ngspice

# Upgrade a tool
python3 -m tool_manager.cli update ngspice --dry-run

# Make sure the tool's install directory is on PATH
python3 -m tool_manager.cli configure ngspice --dry-run

# View the action log
python3 -m tool_manager.cli log
```

## What's actually been tested

This was developed and smoke-tested on a Debian/Ubuntu container:
- `install ngspice` and `install gnuplot` (both `--dry-run` and real
  installs) — verified the binaries actually land, versions are
  correctly parsed (`42`, `6.0`), and get recorded to
  `~/.esim_tool_manager/config.json`.
- `status`, `check-deps`, `check-update`, `configure`, `list`, `log` —
  all exercised against the real installs above.

Full command-by-command output is in `EXECUTION_GUIDE.md` — not a
coverage percentage, the actual transcript.

`choco`/`brew` code paths are implemented and structurally parallel to
the apt path but were **not** run against real Chocolatey/Homebrew
installs in this environment (no Windows/macOS host available here) —
flagging this rather than claiming untested coverage.

## Extending to a new tool

Add an entry to `tool_manager/tools_registry.json` with:
- `check_binary`: the executable name to look for on PATH
- `version_command` / `version_regex`: how to extract its version
- `min_version`: minimum acceptable version
- `install.<platform>.manager` / `.package`: package manager + package name
- `dependencies_linux`: list of apt package names it depends on

No code changes needed for a new tool that fits the existing pattern.

## Known limitations (stated explicitly, not hidden)

- Relies on the OS package manager rather than direct binary downloads —
  won't work on a machine without apt/choco/brew.
- Update-checking is only implemented for apt; choco/brew report
  "not implemented" rather than a fake result.
- Non-Linux dependency verification is not implemented (logged as a note,
  not silently skipped).
- CLI only — no GUI in this prototype (see DESIGN.md for the proposed
  PyQt follow-up, matching eSim's own UI stack).
=======
# esim-tool-manager
>>>>>>> 5b9ddde6093032477e43ab9741f525d586950031
