"""
Unit tests for tool_manager.config.

Covers platform detection (the input to every '_windows'/'_darwin'
override lookup elsewhere in the codebase) and the PATH-instruction
formatting, without touching the real ~/.esim_tool_manager files or
os.environ permanently.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tool_manager import config  # noqa: E402


@pytest.mark.parametrize(
    "system_name,expected",
    [
        ("Windows", "windows"),
        ("WindowsCE", "windows"),   # startswith('win') check must not be exact-match only
        ("Linux", "linux"),
        ("Darwin", "darwin"),
        ("SunOS", "linux"),         # documents current behaviour: unknown OSes fall back to 'linux'
    ],
)
def test_get_current_platform(monkeypatch, system_name, expected):
    monkeypatch.setattr(config.platform, "system", lambda: system_name)
    assert config.get_current_platform() == expected


def test_path_needed_for_windows_uses_setx(monkeypatch):
    monkeypatch.setattr(config, "get_current_platform", lambda: "windows")
    result = config.path_needed_for("ngspice", r"C:\tools\ngspice")
    assert "setx PATH" in result
    assert r"C:\tools\ngspice" in result


def test_path_needed_for_linux_uses_export(monkeypatch):
    monkeypatch.setattr(config, "get_current_platform", lambda: "linux")
    result = config.path_needed_for("ngspice", "/usr/local/ngspice/bin")
    assert "export PATH" in result
    assert "/usr/local/ngspice/bin" in result


def test_load_registry_has_all_expected_tools():
    registry = config.load_registry()
    for tool in ("ngspice", "kicad", "ngveri", "gnuplot"):
        assert tool in registry
        assert "min_version" in registry[tool]
        assert "check_binary" in registry[tool]
        assert "install" in registry[tool]


def test_default_user_config_shape():
    assert "installed_tools" in config.DEFAULT_USER_CONFIG
    assert "preferred_manager" in config.DEFAULT_USER_CONFIG
    assert config.DEFAULT_USER_CONFIG["installed_tools"] == {}


def test_record_installed_tool_roundtrip(tmp_path, monkeypatch):
    """Uses a temp directory instead of the real ~/.esim_tool_manager
    so this test can't corrupt the person's actual config."""
    fake_user_dir = tmp_path / ".esim_tool_manager"
    monkeypatch.setattr(config, "USER_DIR", fake_user_dir)
    monkeypatch.setattr(config, "USER_CONFIG_FILE", fake_user_dir / "config.json")

    config.record_installed_tool("ngspice", "46", "/usr/bin/ngspice")
    cfg = config.load_user_config()

    assert cfg["installed_tools"]["ngspice"]["version"] == "46"
    assert cfg["installed_tools"]["ngspice"]["path"] == "/usr/bin/ngspice"