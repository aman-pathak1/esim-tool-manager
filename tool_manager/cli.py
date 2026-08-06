"""
Command-line interface for the eSim Automated Tool Manager.

Usage examples:
    python -m tool_manager.cli list
    python -m tool_manager.cli status ngspice
    python -m tool_manager.cli install ngspice --dry-run
    python -m tool_manager.cli check-deps kicad
    python -m tool_manager.cli check-update ngspice
    python -m tool_manager.cli update ngspice --dry-run
    python -m tool_manager.cli configure ngspice --dry-run
"""

import argparse
import sys

from . import config
from .dependency_checker import check_dependencies
from .installer import check_version_ok, get_installed_version, install_tool
from .logger_setup import LOG_FILE, get_logger
from .updater import check_for_update, update_tool

logger = get_logger()


def cmd_list(_args):
    registry = config.load_registry()
    user_cfg = config.load_user_config()
    print(f"{'Tool':<10} {'Registry min ver':<18} {'Installed ver':<15} {'Path'}")
    print("-" * 70)
    for name, entry in registry.items():
        installed = user_cfg["installed_tools"].get(name)
        # Always prefer a live check over the cached config -- the cache
        # can go stale (e.g. it was written before a detection bug was
        # fixed, or the tool was updated/removed outside this manager).
        # Only fall back to the cached value if live detection itself
        # can't find anything right now.
        live_version = get_installed_version(name)
        if live_version:
            ver = live_version
        elif installed:
            ver = f"{installed['version']} (cached, not re-verified)"
        else:
            ver = "not installed"
        path = installed["path"] if installed else ""
        print(f"{name:<10} {entry['min_version']:<18} {ver:<15} {path}")


def cmd_status(args):
    ok, version = check_version_ok(args.tool)
    if version is None:
        print(f"{args.tool}: NOT INSTALLED")
        return 1
    status = "OK (meets min version)" if ok else "OUTDATED (below min version)"
    print(f"{args.tool}: installed version={version} -> {status}")
    return 0


def cmd_install(args):
    print(f"Installing {args.tool} (dry_run={args.dry_run}, version={args.version or 'latest'})...")
    try:
        success = install_tool(args.tool, version=args.version, dry_run=args.dry_run)
    except Exception as e:
        print(f"Install failed: {e}")
        return 1
    print("Done." if success else "Install failed -- see log for details.")
    return 0 if success else 1


def cmd_check_deps(args):
    report = check_dependencies(args.tool)
    print(f"Tool: {report.tool}")
    print(f"  Binary found: {report.binary_found}")
    print(f"  Missing dependencies: {report.missing_dependencies or 'none'}")
    for note in report.notes:
        print(f"  Note: {note}")
    return 0 if report.ok else 1


def cmd_check_update(args):
    available, installed, candidate = check_for_update(args.tool)
    if installed is None:
        print(f"{args.tool} is not installed.")
        return 1
    if candidate is None:
        print(f"{args.tool}: installed={installed}. Could not determine candidate version (manager unsupported or offline).")
        return 0
    if available:
        print(f"{args.tool}: update available ({installed} -> {candidate})")
    else:
        print(f"{args.tool}: up to date ({installed})")
    return 0


def cmd_update(args):
    print(f"Updating {args.tool} (dry_run={args.dry_run})...")
    success = update_tool(args.tool, dry_run=args.dry_run)
    print("Done." if success else "Update failed -- see log for details.")
    return 0 if success else 1


def cmd_configure(args):
    from shutil import which
    from .installer import _resolve_field
    registry = config.load_registry()
    entry = registry[args.tool]
    binary_name = _resolve_field(entry, "check_binary")
    binary = which(binary_name)
    if binary is None:
        print(f"{args.tool} binary not found on PATH; install it first.")
        return 1
    install_dir = str(__import__("pathlib").Path(binary).parent)
    msg = config.register_path(args.tool, install_dir, persist=not args.dry_run)
    print(msg)
    return 0


def cmd_log(_args):
    if not LOG_FILE.exists():
        print("No log file yet.")
        return 0
    with open(LOG_FILE) as f:
        print(f.read())
    return 0


def cmd_report(_args):
    """Combined view: for every known tool, show installed version,
    whether it meets the minimum, dependency status, and update
    availability -- in one pass instead of running four commands."""
    registry = config.load_registry()
    any_issue = False
    for name in registry:
        print(f"\n=== {name} ===")
        ok, version = check_version_ok(name)
        if version is None:
            print("  Installed: NOT INSTALLED")
            any_issue = True
            continue
        print(f"  Installed: {version} ({'OK' if ok else 'BELOW MINIMUM'})")
        if not ok:
            any_issue = True

        dep_report = check_dependencies(name)
        if dep_report.missing_dependencies:
            print(f"  Dependencies: MISSING {dep_report.missing_dependencies}")
            any_issue = True
        else:
            print(f"  Dependencies: OK")

        available, _, candidate = check_for_update(name)
        if available:
            print(f"  Update: available -> {candidate}")
            any_issue = True
        elif candidate is None:
            print(f"  Update: unknown (manager doesn't support checking)")
        else:
            print(f"  Update: up to date")

    print()
    return 1 if any_issue else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="esim-tool-manager", description="eSim Automated Tool Manager")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List known tools and their installed status").set_defaults(func=cmd_list)

    p = sub.add_parser("status", help="Show installed version vs required min version")
    p.add_argument("tool")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("install", help="Install a tool")
    p.add_argument("tool")
    p.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    p.add_argument("--version", default=None, help="Pin to a specific version instead of latest")
    p.set_defaults(func=cmd_install)

    p = sub.add_parser("check-deps", help="Check OS-level dependencies for a tool")
    p.add_argument("tool")
    p.set_defaults(func=cmd_check_deps)

    p = sub.add_parser("check-update", help="Check if a newer version is available")
    p.add_argument("tool")
    p.set_defaults(func=cmd_check_update)

    p = sub.add_parser("update", help="Upgrade a tool to the latest version")
    p.add_argument("tool")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("configure", help="Ensure tool's install dir is on PATH")
    p.add_argument("tool")
    p.add_argument("--dry-run", action="store_true", help="Don't persist to shell rc file")
    p.set_defaults(func=cmd_configure)

    sub.add_parser("log", help="Print the action log").set_defaults(func=cmd_log)

    sub.add_parser("report", help="Combined view: version + deps + update status for every tool").set_defaults(func=cmd_report)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())