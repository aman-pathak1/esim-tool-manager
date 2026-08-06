"""
Configuration Handling module.

Responsible for:
  * Loading the static tool registry (tools_registry.json)
  * Persisting user-specific config (installed tools, custom paths,
    preferred package manager) to ~/.esim_tool_manager/config.json
  * Exposing helpers to set/get environment variables and PATH entries
    so installed tools are discoverable by eSim.

NOTE: Editing the user's shell rc file is a real side effect. We only do
it if the user explicitly opts in (register_path(persist=True)); by
default we just report what *would* need to be set, which is safer and
easier to test/demo.
"""

import json
import os
import platform
from pathlib import Path
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parent
REGISTRY_FILE = BASE_DIR / "tools_registry.json"

USER_DIR = Path.home() / ".esim_tool_manager"
USER_CONFIG_FILE = USER_DIR / "config.json"

DEFAULT_USER_CONFIG: Dict[str, Any] = {
    "installed_tools": {},   # tool_name -> {"version": str, "path": str}
    "preferred_manager": None,
    "custom_paths": {}       # tool_name -> install path override
}


def load_registry() -> Dict[str, Any]:
    with open(REGISTRY_FILE, "r") as f:
        return json.load(f)


def load_user_config() -> Dict[str, Any]:
    USER_DIR.mkdir(parents=True, exist_ok=True)
    if not USER_CONFIG_FILE.exists():
        save_user_config(DEFAULT_USER_CONFIG)
        return dict(DEFAULT_USER_CONFIG)
    with open(USER_CONFIG_FILE, "r") as f:
        return json.load(f)


def save_user_config(cfg: Dict[str, Any]) -> None:
    USER_DIR.mkdir(parents=True, exist_ok=True)
    with open(USER_CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def record_installed_tool(name: str, version: str, path: str = "") -> None:
    cfg = load_user_config()
    cfg["installed_tools"][name] = {"version": version, "path": path}
    save_user_config(cfg)


def get_current_platform() -> str:
    """Return 'linux', 'windows', or 'darwin'."""
    sys_name = platform.system().lower()
    if sys_name.startswith("win"):
        return "windows"
    if sys_name == "darwin":
        return "darwin"
    return "linux"


def path_needed_for(tool_name: str, install_dir: str) -> str:
    """
    Returns a human-readable instruction for making `install_dir`
    available on PATH, without silently mutating the user's shell config.
    """
    plat = get_current_platform()
    if plat == "windows":
        return (
            f'setx PATH "%PATH%;{install_dir}"   '
            f"(restart terminal after running this)"
        )
    shell_rc = "~/.bashrc or ~/.zshrc"
    return f'echo \'export PATH="$PATH:{install_dir}"\' >> {shell_rc} && source {shell_rc}'


def register_path(tool_name: str, install_dir: str, persist: bool = False) -> str:
    """
    Adds install_dir to the current process PATH (always) and optionally
    persists it to the user's shell rc file (only if persist=True).
    """
    os.environ["PATH"] = install_dir + os.pathsep + os.environ.get("PATH", "")

    instruction = path_needed_for(tool_name, install_dir)
    if persist and get_current_platform() != "windows":
        rc_file = Path.home() / (".zshrc" if os.environ.get("SHELL", "").endswith("zsh") else ".bashrc")
        line = f'export PATH="$PATH:{install_dir}"  # added by esim-tool-manager for {tool_name}\n'
        with open(rc_file, "a") as f:
            f.write(line)
        return f"PATH updated for this session and appended to {rc_file}"
    return f"PATH updated for this session only. To persist: {instruction}"
