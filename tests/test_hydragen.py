# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
"""Tests for Hydragen.

The TUI derives everything from a ConfigLoader, so these build a loader over
the example app this repo ships and assert the UI adapts to it.
"""

import asyncio
from pathlib import Path

from hydra._internal.config_loader_impl import ConfigLoaderImpl
from hydra._internal.utils import create_config_search_path
from textual.widgets import Input

from hydra_plugins.hydragen._app import NONE, ConfigTree, Hydragen

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


# --- editing a node in the resolved config --------------------------------


def test_editing_a_node_generates_an_override():
    app = make_app()
    assert app.apply_edit(("epochs",), "20") == ""

    assert app.current_overrides() == ["epochs=20"]
    cfg, _ = app.compose_config(app.current_overrides())
    assert cfg.epochs == 20


def test_editing_the_same_node_twice_updates_instead_of_duplicating():
    app = make_app()
    app.apply_edit(("epochs",), "20")
    app.apply_edit(("epochs",), "30")

    assert app.current_overrides() == ["epochs=30"]


def test_editing_two_nodes_keeps_both_overrides():
    app = make_app()
    app.apply_edit(("epochs",), "20")
    app.apply_edit(("model", "dropout"), "0.5")

    assert app.current_overrides() == ["epochs=20", "model.dropout=0.5"]


def test_editing_a_list_element_uses_a_dotted_index():
    app = make_app()
    app.apply_edit(("model", "hidden_dims", "[0]"), "512")

    cfg, _ = app.compose_config(app.current_overrides())
    assert cfg.model.hidden_dims == [512, 128]


def test_invalid_edit_is_rejected_and_records_nothing():
    app = make_app()
    # A path that no longer exists -- what you get by editing a node and then
    # switching the group out from under it.
    error = app.apply_edit(("model", "kernel_size"), "5")

    assert error
    assert app.edits == {}
    assert app.current_overrides() == []


def test_edited_node_keeps_the_value_it_replaced_for_the_struck_out_label():
    app = make_app()
    app.apply_edit(("epochs",), "20")

    assert app.original_values() == {("epochs",): "10"}
    rows, _ = app.compose_outline(app.current_overrides())
    epochs = next(r for r in rows if r.path == ("epochs",))
    assert (epochs.label, epochs.original) == ("epochs: 20", "10")


def test_group_selection_and_node_edit_compose_together():
    app = make_app()
    app.selection["model"] = "cnn"
    app.apply_edit(("model", "kernel_size"), "7")

    assert app.current_overrides() == ["model=cnn", "model.kernel_size=7"]
    cfg, error = app.compose_config(app.current_overrides())
    assert not error
    assert cfg.model.kernel_size == 7


def test_free_form_override_still_wins_over_a_generated_one():
    app = make_app()
    app.apply_edit(("epochs",), "20")
    app.extra = "epochs=99"

    # Extras are appended last, so the advanced escape hatch stays usable.
    assert app.current_overrides() == ["epochs=20", "epochs=99"]
    cfg, _ = app.compose_config(app.current_overrides())
    assert cfg.epochs == 99


# --- keyboard-only wiring --------------------------------------------------
#
# The pure logic above says nothing about whether the keys are hooked up, so
# these drive the real app headlessly. `asyncio.run` stands in for
# pytest-asyncio, which this project does not depend on.


async def _edit_node(pilot, path, keys):
    """Move the outline cursor to ``path``, open the editor and retype it."""
    tree = pilot.app.query_one("#cfgpane", ConfigTree)
    tree.cursor_line = 0
    while tree.cursor_node is None or tree.cursor_node.data != path:
        await pilot.press("down")
    await pilot.press("enter")
    editor = pilot.app.query_one("#nodeedit", Input)
    assert editor.display and pilot.app.focused is editor
    for _ in range(len(editor.value)):
        await pilot.press("backspace")
    await pilot.press(*keys, "enter")


async def _run_edit_flow(app):
    async with app.run_test() as pilot:
        await pilot.press("c")  # focus the outline
        await _edit_node(pilot, ("epochs",), "200")
        assert app.edits == {("epochs",): "epochs=200"}

        # Same node again: the editor opens on the edited value and replaces it.
        await _edit_node(pilot, ("epochs",), "5")
        assert app.edits == {("epochs",): "epochs=5"}

        await _edit_node(pilot, ("model", "dropout"), "0.5")
        assert app.edits[("model", "dropout")] == "model.dropout=0.5"

        epochs = next(n for n in pilot.app.query_one("#cfgpane", ConfigTree).root.children if n.data == ("epochs",))
        assert epochs.label.plain == "epochs: 10 5"


def test_keyboard_only_edit_flow():
    asyncio.run(_run_edit_flow(make_app()))


async def _run_branch_flow(app):
    async with app.run_test() as pilot:
        await pilot.press("c")
        tree = app.query_one("#cfgpane", ConfigTree)
        tree.cursor_line = 0
        while tree.cursor_node is None or tree.cursor_node.data != ("model",):
            await pilot.press("down")
        was_expanded = tree.cursor_node.is_expanded
        await pilot.press("enter")

        # Enter on a branch keeps folding it; only leaves have a value to type over.
        assert not app.query_one("#nodeedit", Input).display
        assert tree.cursor_node.is_expanded != was_expanded


def test_enter_on_a_branch_folds_instead_of_editing():
    asyncio.run(_run_branch_flow(make_app()))
