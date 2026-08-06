"""
Unit tests for tool_manager.installer.

These deliberately mock subprocess/shutil.which rather than touching a
real package manager -- they test the manager's *decision logic*
(what command it would build, how it parses output, how it compares
versions), not whether apt/choco/brew themselves work. Live installs
are covered separately in EXECUTION_GUIDE.md with real transcripts.

Several of these tests exist specifically because they would have
caught real bugs found during Windows testing (see EXECUTION_GUIDE.md
section 4) before they shipped -- that's the point of having them.
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tool_manager import installer  # noqa: E402


# ---------------------------------------------------------------------------
# _leading_number / check_version_ok -- version comparison logic
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "version_string,expected",
    [
        ("46", 46.0),
        ("46.0", 46.0),
        ("8.0", 8.0),
        ("42+ds-3build1", 42.0),          # Debian-style suffix must be ignored
        ("v5.2", 0.0),                     # leading 'v' -- not handled, documents a real limitation
        ("", 0.0),
        ("unknown", 0.0),
    ],
)
def test_leading_number(version_string, expected):
    assert installer._leading_number(version_string) == expected


def test_leading_number_v_prefix_is_a_known_gap():
    """This test documents a real limitation rather than hiding it:
    a version like 'v5.2' (leading 'v') is NOT parsed and falls back to
    0.0, which would make check_version_ok wrongly report 'below
    minimum' for a tool that actually reports versions this way. None
    of the four registered tools (ngspice/kicad/ngveri/gnuplot) use a
    'v'-prefixed scheme in this prototype, so it hasn't bitten in
    practice, but a new registry entry for a tool that does would need
    _leading_number extended first.
    """
    assert installer._leading_number("v5.2") == 0.0


# ---------------------------------------------------------------------------
# _resolve_field / _resolve_version_command -- the exact mechanism that
# caused two real bugs on Windows (GUI vs console ngspice binary)
# ---------------------------------------------------------------------------

def test_resolve_field_uses_platform_override_when_present(monkeypatch):
    monkeypatch.setattr(installer, "get_current_platform", lambda: "windows")
    entry = {"check_binary": "ngspice", "check_binary_windows": "ngspice_con"}
    assert installer._resolve_field(entry, "check_binary") == "ngspice_con"


def test_resolve_field_falls_back_when_no_override(monkeypatch):
    monkeypatch.setattr(installer, "get_current_platform", lambda: "linux")
    entry = {"check_binary": "ngspice", "check_binary_windows": "ngspice_con"}
    # On Linux there's no '_linux' override in this entry, so it must
    # fall back to the plain 'check_binary' key rather than erroring.
    assert installer._resolve_field(entry, "check_binary") == "ngspice"


def test_resolve_field_falls_back_when_platform_has_no_matching_override(monkeypatch):
    monkeypatch.setattr(installer, "get_current_platform", lambda: "darwin")
    entry = {"check_binary": "ngspice", "check_binary_windows": "ngspice_con"}
    # No 'check_binary_darwin' key exists -- must not silently return
    # None or crash, must fall back to the generic field.
    assert installer._resolve_field(entry, "check_binary") == "ngspice"


def test_resolve_version_command_windows_override(monkeypatch):
    monkeypatch.setattr(installer, "get_current_platform", lambda: "windows")
    entry = {
        "version_command": ["ngspice", "-v"],
        "version_command_windows": ["ngspice_con", "-v"],
    }
    assert installer._resolve_version_command(entry) == ["ngspice_con", "-v"]


def test_resolve_version_command_linux_uses_default(monkeypatch):
    monkeypatch.setattr(installer, "get_current_platform", lambda: "linux")
    entry = {
        "version_command": ["ngspice", "-v"],
        "version_command_windows": ["ngspice_con", "-v"],
    }
    assert installer._resolve_version_command(entry) == ["ngspice", "-v"]


# ---------------------------------------------------------------------------
# get_installed_version -- regex extraction against real captured output
# ---------------------------------------------------------------------------

NGSPICE_LINUX_OUTPUT = "ngspice-42 : Circuit level simulation program\n"

NGSPICE_WINDOWS_CONSOLE_OUTPUT = (
    "******\n"
    "** ngspice-46 : Circuit level simulation program\n"
    "** Compiled with KLU Direct Linear Solver\n"
)

GNUPLOT_OUTPUT = "gnuplot 6.0 patchlevel 3\n"


def _mock_run_factory(stdout_text):
    def _mock_run(cmd, stdout=None, stderr=None, text=None, timeout=None):
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout_text)
    return _mock_run


def test_get_installed_version_parses_linux_ngspice_output(monkeypatch):
    monkeypatch.setattr(installer.shutil, "which", lambda name: "/usr/bin/ngspice")
    monkeypatch.setattr(installer.subprocess, "run", _mock_run_factory(NGSPICE_LINUX_OUTPUT))
    monkeypatch.setattr(installer, "get_current_platform", lambda: "linux")
    version = installer.get_installed_version("ngspice")
    assert version == "42"


def test_get_installed_version_parses_windows_console_output(monkeypatch):
    monkeypatch.setattr(installer.shutil, "which", lambda name: r"C:\ProgramData\chocolatey\bin\ngspice_con.exe")
    monkeypatch.setattr(installer.subprocess, "run", _mock_run_factory(NGSPICE_WINDOWS_CONSOLE_OUTPUT))
    monkeypatch.setattr(installer, "get_current_platform", lambda: "windows")
    version = installer.get_installed_version("ngspice")
    assert version == "46"


def test_get_installed_version_returns_none_when_binary_missing(monkeypatch):
    monkeypatch.setattr(installer.shutil, "which", lambda name: None)
    version = installer.get_installed_version("ngspice")
    assert version is None


def test_get_installed_version_gnuplot(monkeypatch):
    monkeypatch.setattr(installer.shutil, "which", lambda name: "/usr/bin/gnuplot")
    monkeypatch.setattr(installer.subprocess, "run", _mock_run_factory(GNUPLOT_OUTPUT))
    monkeypatch.setattr(installer, "get_current_platform", lambda: "linux")
    version = installer.get_installed_version("gnuplot")
    assert version == "6.0"


# ---------------------------------------------------------------------------
# check_version_ok -- combines detection + min-version comparison
# ---------------------------------------------------------------------------

def test_check_version_ok_true_when_meets_minimum(monkeypatch):
    monkeypatch.setattr(installer, "get_installed_version", lambda name: "46")
    ok, version = installer.check_version_ok("ngspice")
    assert ok is True
    assert version == "46"


def test_check_version_ok_false_when_below_minimum(monkeypatch):
    # ngspice's registered min_version is 35
    monkeypatch.setattr(installer, "get_installed_version", lambda name: "20")
    ok, version = installer.check_version_ok("ngspice")
    assert ok is False
    assert version == "20"


def test_check_version_ok_false_when_not_installed(monkeypatch):
    monkeypatch.setattr(installer, "get_installed_version", lambda name: None)
    ok, version = installer.check_version_ok("ngspice")
    assert ok is False
    assert version is None


# ---------------------------------------------------------------------------
# install_tool -- command construction per manager (dry_run, so no live
# side effects; asserts on what WOULD be run)
# ---------------------------------------------------------------------------

def _capture_run(monkeypatch):
    calls = []

    def fake_run(cmd, dry_run):
        calls.append(cmd)
        return 0, "[dry-run] not executed"

    monkeypatch.setattr(installer, "_run", fake_run)
    return calls


def test_install_tool_apt_command_no_version(monkeypatch):
    monkeypatch.setattr(installer, "get_current_platform", lambda: "linux")
    monkeypatch.setattr(installer, "_manager_available", lambda m: True)
    calls = _capture_run(monkeypatch)
    installer.install_tool("ngspice", dry_run=True)
    assert calls[0] == ["apt-get", "install", "-y", "ngspice"] or calls[0][-1] == "ngspice"


def test_install_tool_apt_command_with_version_pin(monkeypatch):
    monkeypatch.setattr(installer, "get_current_platform", lambda: "linux")
    monkeypatch.setattr(installer, "_manager_available", lambda m: True)
    calls = _capture_run(monkeypatch)
    installer.install_tool("ngspice", version="42", dry_run=True)
    assert calls[0][-1] == "ngspice=42"


def test_install_tool_choco_command_with_version_pin(monkeypatch):
    monkeypatch.setattr(installer, "get_current_platform", lambda: "windows")
    calls = _capture_run(monkeypatch)
    installer.install_tool("ngspice", version="46", dry_run=True)
    assert "--version=46" in calls[0]
    assert calls[0][0] == "choco"


def test_install_tool_brew_rejects_version_pin(monkeypatch):
    monkeypatch.setattr(installer, "get_current_platform", lambda: "darwin")
    with pytest.raises(installer.InstallError, match="does not reliably support pinning"):
        installer.install_tool("ngspice", version="42", dry_run=True)


def test_install_tool_unknown_tool_raises(monkeypatch):
    monkeypatch.setattr(installer, "get_current_platform", lambda: "linux")
    with pytest.raises(installer.InstallError, match="not a known tool"):
        installer.install_tool("definitely_not_a_real_tool", dry_run=True)


def test_install_tool_no_platform_support_raises(monkeypatch):
    # ngveri has no 'darwin' entry in tools_registry.json -- confirm
    # this fails loudly instead of silently doing nothing.
    monkeypatch.setattr(installer, "get_current_platform", lambda: "darwin")
    with pytest.raises(installer.InstallError, match="No install method registered"):
        installer.install_tool("ngveri", dry_run=True)