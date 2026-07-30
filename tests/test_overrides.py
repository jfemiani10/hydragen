# Copyright (c) Jonah Femiani. All Rights Reserved
# License: MIT

"""Tests for turning an edited config node into a Hydra override.

These helpers are deliberately free of Textual and of the ConfigLoader, so the
path -> override translation can be asserted on its own.
"""

from __future__ import annotations

from hydra_plugins.hydragen._app import (
    Outline,
    build_outline,
    format_override,
    lookup_value,
    mark_edits,
    node_label,
    override_key,
)

# --- config path -> override key ------------------------------------------


def test_nested_path_becomes_a_dotted_key():
    assert override_key(("model", "name")) == "model.name"


def test_top_level_path_is_the_bare_key():
    assert override_key(("epochs",)) == "epochs"


def test_list_index_loses_its_brackets():
    # The outline labels list elements `[0]`, but Hydra's grammar only takes `.0`.
    assert override_key(("model", "hidden_dims", "[0]")) == "model.hidden_dims.0"


# --- value formatting ------------------------------------------------------


def test_simple_values_are_left_bare():
    assert format_override(("epochs",), "20") == "epochs=20"
    assert format_override(("lr",), "1e-4") == "lr=1e-4"
    assert format_override(("model", "ckpt"), "null") == "model.ckpt=null"


def test_surrounding_whitespace_is_dropped():
    assert format_override(("epochs",), "  20  ") == "epochs=20"


def test_values_needing_quotes_get_them():
    # Without quotes this would be two shell words in the command preview.
    assert format_override(("model", "name"), "my model") == "model.name='my model'"


def test_embedded_quotes_are_escaped():
    assert format_override(("run", "note"), "it's fine") == "run.note='it\\'s fine'"


def test_empty_value_becomes_an_empty_string_not_a_bare_key():
    assert format_override(("model", "name"), "") == "model.name=''"


# --- reading the pre-edit value -------------------------------------------


def test_lookup_walks_mappings():
    found, value = lookup_value({"model": {"name": "cnn"}}, ("model", "name"))
    assert (found, value) == (True, "cnn")


def test_lookup_walks_list_indices():
    found, value = lookup_value({"dims": [32, 64]}, ("dims", "[1]"))
    assert (found, value) == (True, 64)


def test_lookup_reports_a_missing_key():
    # Switching a group can retire a node someone already edited.
    assert lookup_value({"model": {"name": "cnn"}}, ("model", "kernel_size")) == (False, None)


def test_lookup_reports_an_out_of_range_index():
    assert lookup_value({"dims": [32]}, ("dims", "[7]")) == (False, None)


def test_lookup_reports_descending_into_a_scalar():
    assert lookup_value({"epochs": 10}, ("epochs", "nope")) == (False, None)


# --- marking edited rows ---------------------------------------------------


def test_edited_leaf_records_what_it_replaced():
    rows = build_outline({"epochs": 20})

    (epochs,) = mark_edits(rows, {("epochs",): "10"})
    assert epochs.original == "10"
    assert epochs.label == "epochs: 20"  # label still shows the live value


def test_unchanged_leaf_is_not_marked():
    # Re-stating a value would strike it out and reprint it identically.
    rows = build_outline({"epochs": 10})

    (epochs,) = mark_edits(rows, {("epochs",): "10"})
    assert epochs.original is None


def test_marking_reaches_nested_rows():
    rows = build_outline({"model": {"name": "cnn"}})

    (model,) = mark_edits(rows, {("model", "name"): "mlp"})
    assert model.original is None  # the branch itself was not edited
    assert model.children[0].original == "mlp"


def test_untouched_rows_are_left_alone():
    rows = build_outline({"epochs": 10, "lr": 0.001})

    assert mark_edits(rows, {}) == rows


# --- rendering -------------------------------------------------------------


def test_plain_row_renders_as_its_label():
    label = node_label(Outline("epochs: 10", ("epochs",)))

    assert label.plain == "epochs: 10"
    assert not label.spans  # nothing to highlight


def test_edited_row_strikes_the_old_value_before_the_new_one():
    label = node_label(Outline("epochs: 20", ("epochs",), original="10"))

    assert label.plain == "epochs: 10 20"
    assert any("strike" in str(span.style) for span in label.spans)
