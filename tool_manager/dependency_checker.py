"""
Dependency Checker module.

Checks whether:
  1. The tool's own binary is present and importable via PATH.
  2. The tool's declared OS-level dependencies (apt packages, etc.) are
     installed.
Reports missing/incompatible items back to the caller instead of failing
silently, per the evaluation requirement.
"""

import shutil
import subprocess
from dataclasses import dataclass, field
from typing import List

from .config import get_current_platform, load_registry
from .logger_setup import get_logger

logger = get_logger()


def _resolve_check_binary(entry: dict) -> str:
    if get_current_platform() == "windows" and "check_binary_windows" in entry:
        return entry["check_binary_windows"]
    return entry["check_binary"]


@dataclass
class DependencyReport:
    tool: str
    binary_found: bool
    missing_dependencies: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.binary_found and not self.missing_dependencies


def _is_apt_package_installed(package: str) -> bool:
    try:
        result = subprocess.run(
            ["dpkg", "-s", package],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        # dpkg not available (non-Debian system) -- can't verify, assume unknown
        return False


def check_binary(binary_name: str) -> bool:
    return shutil.which(binary_name) is not None


def check_dependencies(tool_name: str) -> DependencyReport:
    registry = load_registry()
    if tool_name not in registry:
        raise ValueError(f"Unknown tool '{tool_name}'. Not in registry.")

    entry = registry[tool_name]
    plat = get_current_platform()
    report = DependencyReport(tool=tool_name, binary_found=check_binary(_resolve_check_binary(entry)))

    if not report.binary_found:
        report.notes.append(f"'{_resolve_check_binary(entry)}' not found on PATH.")

    if plat == "linux":
        deps = entry.get("dependencies_linux", [])
        for dep in deps:
            if not _is_apt_package_installed(dep):
                report.missing_dependencies.append(dep)
    else:
        # Always disclose that verification wasn't attempted on this
        # platform -- regardless of whether this specific tool happens
        # to declare a 'dependencies_<plat>' list in the registry.
        # Checking only when that key exists (the previous behaviour)
        # meant every non-Linux platform silently reported a clean
        # pass without ever actually checking anything, since no
        # registry entry currently declares darwin/windows dependency
        # lists. Caught by test_check_dependencies_non_linux_adds_note.
        report.notes.append(
            f"Automated dependency verification for '{plat}' is not implemented; "
            f"please verify manually."
        )

    if report.missing_dependencies:
        logger.warning(
            f"[{tool_name}] Missing dependencies: {', '.join(report.missing_dependencies)}"
        )
    elif not report.binary_found:
        logger.warning(f"[{tool_name}] Dependency check incomplete -- binary not found on PATH.")
    else:
        logger.info(f"[{tool_name}] Dependency check passed (binary_found={report.binary_found}).")

    return report