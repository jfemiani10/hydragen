# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
"""Tests for Hydragen.

The TUI derives everything from a ConfigLoader, so these build a loader over
hydra's own example configs and assert the UI adapts to them.
"""

from pathlib import Path

import pytest
from hydra._internal.config_loader_impl import ConfigLoaderImpl
from hydra._internal.utils import create_config_search_path

from hydra_plugins.hydragen._app import NONE, Hydragen

# hydra's 6_composition example: groups db / schema / ui
EXAMPLE = Path(__file__).resolve().parents[3] / "examples" / "tutorials" / "basic" / "your_first_hydra_app" / "6_composition" / "conf"


def make_app(overrides=None):
    loader = ConfigLoaderImpl(config_search_path=create_config_search_path(str(EXAMPLE)))
    return Hydragen(
        config_loader=loader,
        config_name="config",
        overrides=overrides or [],
        app_path="my_app.py",
    )


@pytest.mark.skipif(not EXAMPLE.exists(), reason="hydra examples not present")
def test_groups_discovered_from_config_loader():
    app = make_app()
    assert app.groups == ["db", "schema", "ui"]
    assert app.options["db"] == ["mysql", "postgresql"]


@pytest.mark.skipif(not EXAMPLE.exists(), reason="hydra examples not present")
def test_initial_selection_matches_defaults_list():
    app = make_app()
    assert app.selection == {"db": "mysql", "schema": "school", "ui": "full"}
    assert all(app.in_defaults.values())


@pytest.mark.skipif(not EXAMPLE.exists(), reason="hydra examples not present")
def test_default_selection_produces_no_redundant_overrides():
    app = make_app()
    assert app.current_overrides() == []


@pytest.mark.skipif(not EXAMPLE.exists(), reason="hydra examples not present")
def test_changed_group_becomes_an_override():
    app = make_app()
    app.selection["db"] = "postgresql"
    assert app.current_overrides() == ["db=postgresql"]


@pytest.mark.skipif(not EXAMPLE.exists(), reason="hydra examples not present")
def test_compose_hides_hydra_node_and_reflects_selection():
    app = make_app()
    app.selection["db"] = "postgresql"
    text, ok = app.compose_yaml(app.current_overrides())
    assert ok
    assert "postgresql" in text
    assert not text.startswith("hydra:")


@pytest.mark.skipif(not EXAMPLE.exists(), reason="hydra examples not present")
def test_bad_override_reports_error_instead_of_raising():
    app = make_app()
    app.extra = "db=nonexistent_option"
    text, ok = app.compose_yaml(app.current_overrides())
    assert not ok
    assert text  # error text is shown in the pane


@pytest.mark.skipif(not EXAMPLE.exists(), reason="hydra examples not present")
def test_optional_group_uses_plus_prefix():
    app = make_app()
    # Simulate a group that isn't in the defaults list.
    app.groups.append("experiment")
    app.options["experiment"] = [NONE, "exp1"]
    app.in_defaults["experiment"] = False
    app.selection["experiment"] = "exp1"
    assert "+experiment=exp1" in app.current_overrides()
