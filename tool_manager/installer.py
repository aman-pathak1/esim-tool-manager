"""
Tool Installation Management module.

Wraps native package managers (apt / choco / brew) so the manager stays
thin and doesn't reimplement package resolution or binary distribution --
reinventing that would be a much bigger, riskier project than what a
screening-task prototype should attempt.

Responsibilities:
  * Detect installed version of a tool (via its version_command/regex).
  * Install a tool through the correct package manager for the platform.
  * Record what got installed into user config.
"""

import os
import re
import shutil
import subprocess
from typing import Optional, Tuple

from .config import get_current_platform, load_registry, record_installed_tool
from .logger_setup import get_logger

logger = get_logger()


class InstallError(Exception):
    pass


def _resolve_field(entry: dict, field: str) -> Optional[str]:
    """Some tools ship a GUI-only binary on Windows that opens a window
    instead of printing to stdout (e.g. ngspice.exe). Registry entries
    can supply a '<field>_windows' override for those cases."""
    plat = get_current_platform()
    override_key = f"{field}_{plat}"
    if override_key in entry:
        return entry[override_key]
    return entry.get(field)


def _resolve_version_command(entry: dict) -> list:
    return _resolve_field(entry, "version_command")


def _leading_number(v: str) -> float:
    m = re.match(r"(\d+(\.\d+)?)", v)
    return float(m.group(1)) if m else 0.0


def get_installed_version(tool_name: str) -> Optional[str]:
    registry = load_registry()
    entry = registry[tool_name]
    cmd = _resolve_version_command(entry)

    if shutil.which(cmd[0]) is None:
        return None

    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=10)
        output = result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.error(f"[{tool_name}] Could not determine version: {e}")
        return None

    match = re.search(entry["version_regex"], output)
    return match.group(1) if match else None


def _manager_available(manager: str) -> bool:
    return shutil.which(manager) is not None


def _apt_prefix() -> list:
    """sudo is unavailable in some environments (e.g. containers already
    running as root, or minimal CI images). Only prefix with sudo when
    it exists and we're not already root."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return []
    if shutil.which("sudo"):
        return ["sudo"]
    return []


def _run(cmd: list, dry_run: bool) -> Tuple[int, str]:
    logger.info(f"$ {' '.join(cmd)}")
    if dry_run:
        return 0, "[dry-run] command not executed"
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return result.returncode, result.stdout


def install_tool(
    tool_name: str,
    version: Optional[str] = None,
    dry_run: bool = False,
    assume_yes: bool = True,
) -> bool:
    """
    Installs `tool_name` using the platform-appropriate package manager.
    Returns True on (apparent) success.

    dry_run=True prints the exact commands without executing them -- useful
    for demoing on a machine where sudo/apt isn't available (e.g. CI or a
    reviewer's sandbox).
    """
    registry = load_registry()
    if tool_name not in registry:
        raise InstallError(f"'{tool_name}' is not a known tool. Check tools_registry.json.")

    entry = registry[tool_name]
    plat = get_current_platform()
    install_info = entry["install"].get(plat)

    if install_info is None:
        raise InstallError(f"No install method registered for '{tool_name}' on '{plat}'.")

    manager = install_info["manager"]
    package = install_info["package"]

    if manager == "apt":
        if not _manager_available("apt-get") and not dry_run:
            raise InstallError("apt-get not available on this system.")
        package_spec = f"{package}={version}" if version else package
        cmd = _apt_prefix() + ["apt-get", "install"]
        if assume_yes:
            cmd.append("-y")
        cmd.append(package_spec)
    elif manager == "choco":
        if not _manager_available("choco") and not dry_run:
            raise InstallError("choco not available on this system.")
        cmd = ["choco", "install", package]
        if assume_yes:
            cmd.append("-y")
        if version:
            cmd.append(f"--version={version}")
    elif manager == "brew":
        if not _manager_available("brew") and not dry_run:
            raise InstallError("brew not available on this system.")
        if version:
            raise InstallError("brew does not reliably support pinning versions via this prototype.")
        cmd = ["brew", "install", package]
    else:
        raise InstallError(f"Unsupported package manager '{manager}'.")

    returncode, output = _run(cmd, dry_run)

    if returncode != 0:
        logger.error(f"[{tool_name}] Install failed (exit {returncode}):\n{output}")
        return False

    logger.info(f"[{tool_name}] Install command completed successfully.")

    if not dry_run:
        version = get_installed_version(tool_name) or "unknown"
        binary_name = _resolve_field(entry, "check_binary")
        binary_path = shutil.which(binary_name) or ""
        record_installed_tool(tool_name, version, binary_path)
        logger.info(f"[{tool_name}] Recorded install: version={version}, path={binary_path}")
    else:
        logger.info(f"[{tool_name}] Dry run complete -- nothing was actually installed.")

    return True


def check_version_ok(tool_name: str) -> Tuple[bool, Optional[str]]:
    """
    Returns (is_ok, installed_version). is_ok is True if the installed
    version meets or exceeds the registry's min_version (best-effort
    numeric comparison on the leading numeric component).
    """
    registry = load_registry()
    entry = registry[tool_name]
    installed = get_installed_version(tool_name)

    if installed is None:
        return False, None

    is_ok = _leading_number(installed) >= _leading_number(entry["min_version"])
    return is_ok, installed
