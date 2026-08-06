# Quick Reference

## Commands

| Command | What it does |
|---|---|
| `python3 -m tool_manager.cli list` | Show all known tools + install status |
| `python3 -m tool_manager.cli status <tool>` | Installed version vs. required minimum |
| `python3 -m tool_manager.cli install <tool> [--dry-run]` | Install via apt/choco/brew |
| `python3 -m tool_manager.cli check-deps <tool>` | Check OS-level dependencies |
| `python3 -m tool_manager.cli check-update <tool>` | Is a newer version available? (apt only) |
| `python3 -m tool_manager.cli update <tool> [--dry-run]` | Upgrade an installed tool |
| `python3 -m tool_manager.cli configure <tool> [--dry-run]` | Ensure tool's dir is on PATH |
| `python3 -m tool_manager.cli log` | Print the full action log |

## Tools currently in the registry

| Tool | Min version | Linux package | Windows package | macOS package |
|---|---|---|---|---|
| ngspice | 35 | `ngspice` (apt) | `ngspice` (choco) | `ngspice` (brew) |
| kicad | 6 | `kicad` (apt) | `kicad` (choco) | `kicad` (brew) |
| ngveri | 1.0 | `ngveri` (apt) | — not registered | — not registered |
| gnuplot | 5.0 | `gnuplot` (apt) | `gnuplot` (choco) | `gnuplot` (brew) |

## File locations

| Path | Contents |
|---|---|
| `tool_manager/tools_registry.json` | Static tool metadata (edit to add tools) |
| `~/.esim_tool_manager/config.json` | Per-user record of installed tools |
| `~/.esim_tool_manager/tool_manager.log` | Full action log |

## Adding a new tool (no code changes required)

Add a block like this to `tools_registry.json`:
```json
"mytool": {
  "description": "...",
  "min_version": "1.0",
  "version_command": ["mytool", "--version"],
  "version_regex": "([0-9]+\\.[0-9]+)",
  "check_binary": "mytool",
  "install": {
    "linux": {"manager": "apt", "package": "mytool"}
  },
  "dependencies_linux": []
}
```
