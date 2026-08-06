"""
Unit tests for tool_manager.dependency_checker.

Covers the exact bug found during Windows testing: the log message
used to say "passed" even when binary_found was False. These tests
pin down the *correct* DependencyReport.ok behaviour so that
regression can't silently reappear.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tool_manager import dependency_checker as dc  # noqa: E402


def test_dependency_report_ok_when_binary_found_and_no_missing_deps():
    report = dc.DependencyReport(tool="ngspice", binary_found=True, missing_dependencies=[])
    assert report.ok is True


def test_dependency_report_not_ok_when_binary_missing():
    """This is the exact condition that produced a misleading 'passed'
    log message on Windows before the fix -- binary_found=False must
    make .ok False regardless of missing_dependencies being empty."""
    report = dc.DependencyReport(tool="kicad", binary_found=False, missing_dependencies=[])
    assert report.ok is False


def test_dependency_report_not_ok_when_deps_missing_even_if_binary_found():
    report = dc.DependencyReport(tool="kicad", binary_found=True, missing_dependencies=["python3-wxgtk4.0"])
    assert report.ok is False


def test_resolve_check_binary_windows_override(monkeypatch):
    monkeypatch.setattr(dc, "get_current_platform", lambda: "windows")
    entry = {"check_binary": "ngspice", "check_binary_windows": "ngspice_con"}
    assert dc._resolve_check_binary(entry) == "ngspice_con"


def test_resolve_check_binary_no_override_falls_back(monkeypatch):
    monkeypatch.setattr(dc, "get_current_platform", lambda: "linux")
    entry = {"check_binary": "ngspice", "check_binary_windows": "ngspice_con"}
    assert dc._resolve_check_binary(entry) == "ngspice"


def test_check_dependencies_unknown_tool_raises():
    with pytest.raises(ValueError, match="Unknown tool"):
        dc.check_dependencies("not_a_real_tool")


def test_check_dependencies_reports_missing_apt_packages(monkeypatch):
    monkeypatch.setattr(dc, "get_current_platform", lambda: "linux")
    monkeypatch.setattr(dc, "check_binary", lambda name: False)
    monkeypatch.setattr(dc, "_is_apt_package_installed", lambda pkg: False)
    report = dc.check_dependencies("kicad")
    assert report.binary_found is False
    assert "python3-wxgtk4.0" in report.missing_dependencies
    assert report.ok is False


def test_check_dependencies_all_ok(monkeypatch):
    monkeypatch.setattr(dc, "get_current_platform", lambda: "linux")
    monkeypatch.setattr(dc, "check_binary", lambda name: True)
    monkeypatch.setattr(dc, "_is_apt_package_installed", lambda pkg: True)
    report = dc.check_dependencies("kicad")
    assert report.ok is True


def test_check_dependencies_non_linux_adds_note_instead_of_false_pass(monkeypatch):
    """On a platform where dependency verification isn't implemented,
    the function must say so via a note rather than silently reporting
    a clean pass that wasn't actually checked."""
    monkeypatch.setattr(dc, "get_current_platform", lambda: "darwin")
    monkeypatch.setattr(dc, "check_binary", lambda name: True)
    report = dc.check_dependencies("kicad")
    assert any("not implemented" in note for note in report.notes)