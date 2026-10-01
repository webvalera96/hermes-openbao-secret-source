"""Scaffolding checks: package imports and the plugin manifest is well formed."""

from __future__ import annotations

from pathlib import Path

import yaml

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "src" / "hermes_openbao_secret_source"


def test_package_imports():
    import hermes_openbao_secret_source

    assert hermes_openbao_secret_source.__version__


def test_plugin_manifest_parses_with_expected_keys():
    manifest = yaml.safe_load((PACKAGE_DIR / "plugin.yaml").read_text())
    assert manifest["name"] == "openbao"
    assert manifest.get("description")
    assert any(dep.startswith("hvac") for dep in manifest["python_dependencies"])


def test_plugin_directory_has_register_entry_point():
    """A native directory plugin needs ``plugin.yaml`` and ``__init__.py`` side by side."""
    assert (PACKAGE_DIR / "plugin.yaml").is_file()
    assert (PACKAGE_DIR / "__init__.py").is_file()
