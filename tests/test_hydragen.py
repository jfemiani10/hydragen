# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
"""Tests for Hydragen.

The TUI derives everything from a ConfigLoader, so these build a loader over
the example app this repo ships and assert the UI adapts to it.
"""

from pathlib import Path

from hydra._internal.config_loader_impl import ConfigLoaderImpl
from hydra._internal.utils import create_config_search_path

from hydra_plugins.hydragen._app import NONE, Hydragen

# The repo's own example app: groups model / dataset. Committed alongside the
# tests, so it is always present -- no skip guard, or a broken path would make
# the suite pass while asserting nothing.
EXAMPLE = Path(__file__).resolve().parents[1] / "example" / "conf"


def make_app(overrides=None):
    loader = ConfigLoaderImpl(config_search_path=create_config_search_path(str(EXAMPLE)))
    return Hydragen(
        config_loader=loader,
        config_name="config",
        overrides=overrides or [],
        app_path="my_app.py",
    )


def test_groups_discovered_from_config_loader():
    app = make_app()
    # Both groups and their options come back sorted.
    assert app.groups == ["dataset", "model"]
    assert app.options["model"] == ["cnn", "mlp"]
    assert app.options["dataset"] == ["cifar", "imagenet"]


def test_initial_selection_matches_defaults_list():
    app = make_app()
    assert app.selection == {"model": "mlp", "dataset": "cifar"}
    assert all(app.in_defaults.values())


def test_default_selection_produces_no_redundant_overrides():
    app = make_app()
    assert app.current_overrides() == []


def test_changed_group_becomes_an_override():
    app = make_app()
    app.selection["model"] = "cnn"
    assert app.current_overrides() == ["model=cnn"]


def test_compose_hides_hydra_node_and_reflects_selection():
    app = make_app()
    app.selection["model"] = "cnn"
    cfg, error = app.compose_config(app.current_overrides())
    assert not error
    assert cfg is not None
    assert cfg.model.name == "cnn"
    assert "hydra" not in cfg


def test_bad_override_reports_error_instead_of_raising():
    app = make_app()
    app.extra = "model=nonexistent_option"
    cfg, error = app.compose_config(app.current_overrides())
    assert cfg is None
    assert error  # error text is shown in the pane


def test_outline_is_built_from_the_composed_config():
    app = make_app()
    rows, _ = app.compose_outline(app.current_overrides())
    model = next(r for r in rows if r.label == "model")
    assert model.children  # nested group is foldable, not flat text


def test_bad_override_yields_no_outline_rows():
    app = make_app()
    app.extra = "model=nonexistent_option"
    rows, error = app.compose_outline(app.current_overrides())
    assert rows == ()
    assert error


def test_optional_group_uses_plus_prefix():
    app = make_app()
    # Simulate a group that isn't in the defaults list.
    app.groups.append("experiment")
    app.options["experiment"] = [NONE, "exp1"]
    app.in_defaults["experiment"] = False
    app.selection["experiment"] = "exp1"
    assert "+experiment=exp1" in app.current_overrides()
