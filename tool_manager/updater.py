"""
Update and Upgrade System module.

Checks whether a newer version is available via the platform package
manager's own metadata (apt-cache / choco outdated / brew outdated) and
performs the upgrade if requested.

Design note: we deliberately query the package manager's index rather
than scraping each tool's website/GitHub releases. It's less precise
(depot lag) but far more reliable and maintainable for a heterogeneous
tool set than per-tool scrapers, which is what this prototype needs
to demonstrate.
"""

import re
import shutil
import subprocess
from typing import Optional, Tuple

from .config import get_current_platform, load_registry
from .installer import _apt_prefix, get_installed_version
from .logger_setup import get_logger

logger = get_logger()


def _apt_candidate_version(package: str) -> Optional[str]:
    if shutil.which("apt-cache") is None:
        return None
    result = subprocess.run(
        ["apt-cache", "policy", package], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    match = re.search(r"Candidate:\s*(\S+)", result.stdout)
    return match.group(1) if match and match.group(1) != "(none)" else None


def check_for_update(tool_name: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Returns (update_available, installed_version, candidate_version).
    Only apt is implemented for the prototype; other managers log a
    'not implemented' note rather than pretending to check.
    """
    registry = load_registry()
    entry = registry[tool_name]
    plat = get_current_platform()
    install_info = entry["install"].get(plat)
    installed = get_installed_version(tool_name)

    if install_info is None or installed is None:
        return False, installed, None

    manager = install_info["manager"]
    if manager == "apt":
        candidate = _apt_candidate_version(install_info["package"])
    else:
        logger.info(f"[{tool_name}] Update check for manager '{manager}' not implemented in prototype.")
        return False, installed, None

    if candidate is None:
        return False, installed, None

    update_available = candidate.split("-")[0].split("+")[0] != installed and candidate not in installed
    return update_available, installed, candidate


def update_tool(tool_name: str, dry_run: bool = False) -> bool:
    registry = load_registry()
    entry = registry[tool_name]
    plat = get_current_platform()
    install_info = entry["install"].get(plat)
    if install_info is None:
        logger.error(f"[{tool_name}] No install/update method for platform '{plat}'.")
        return False

    manager = install_info["manager"]
    package = install_info["package"]

    if manager == "apt":
        cmd = _apt_prefix() + ["apt-get", "install", "--only-upgrade", "-y", package]
    elif manager == "choco":
        cmd = ["choco", "upgrade", package, "-y"]
    elif manager == "brew":
        cmd = ["brew", "upgrade", package]
    else:
        logger.error(f"[{tool_name}] Unsupported manager '{manager}' for update.")
        return False

    logger.info(f"$ {' '.join(cmd)}")
    if dry_run:
        logger.info(f"[{tool_name}] Dry run -- update command not executed.")
        return True

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode != 0:
        logger.error(f"[{tool_name}] Update failed:\n{result.stdout}")
        return False

    logger.info(f"[{tool_name}] Updated successfully.")
    return True
