# Copyright (c) Jonah Femiani. All Rights Reserved
# License: MIT

"""Tests for the resolved-config outline.

``build_outline`` is deliberately free of Textual types, so the tree shape can
be asserted directly without standing up an app.
"""

from __future__ import annotations

from omegaconf import OmegaConf

from hydra_plugins.hydragen._app import build_outline


def outline_of(data: dict) -> tuple:
    """Build an outline the way the app does: OmegaConf -> container -> rows."""
    cfg = OmegaConf.create(data)
    return build_outline(OmegaConf.to_container(cfg, resolve=False))


def test_scalars_become_leaves_labelled_key_value():
    rows = outline_of({"epochs": 10, "lr": 0.001})

    assert [r.label for r in rows] == ["epochs: 10", "lr: 0.001"]
    assert all(r.children == () for r in rows)


def test_nested_mapping_becomes_a_branch():
    rows = outline_of({"model": {"name": "cnn", "kernel_size": 3}})

    (model,) = rows
    assert model.label == "model"  # branch label is the bare key
    assert [c.label for c in model.children] == ["name: cnn", "kernel_size: 3"]


def test_list_becomes_index_labelled_children():
    # example/conf/model/cnn.yaml ships exactly this.
    rows = outline_of({"channels": [32, 64, 128]})

    (channels,) = rows
    assert channels.label == "channels"
    assert [c.label for c in channels.children] == ["[0]: 32", "[1]: 64", "[2]: 128"]


def test_list_of_mappings_nests_further():
    rows = outline_of({"layers": [{"kind": "conv"}, {"kind": "pool"}]})

    (layers,) = rows
    assert [c.label for c in layers.children] == ["[0]", "[1]"]
    assert [c.label for c in layers.children[0].children] == ["kind: conv"]


def test_paths_are_recorded_for_every_row():
    rows = outline_of({"model": {"name": "cnn"}, "epochs": 10})

    model, epochs = rows
    assert model.path == ("model",)
    assert model.children[0].path == ("model", "name")
    assert epochs.path == ("epochs",)


def test_empty_containers_are_leaves_not_foldable_branches():
    # Rendering these as bare branches would look like a collapsed node.
    rows = outline_of({"empty_map": {}, "empty_list": []})

    assert [r.label for r in rows] == ["empty_map: {}", "empty_list: []"]
    assert all(r.children == () for r in rows)


def test_none_renders_as_null():
    (row,) = outline_of({"ckpt": None})

    assert row.label == "ckpt: null"


def test_interpolations_are_left_unresolved():
    # resolve=False keeps the pane showing what the YAML view showed.
    rows = outline_of({"name": "cnn", "run": "${name}_v1"})

    assert [r.label for r in rows] == ["name: cnn", "run: ${name}_v1"]


def test_scalar_input_produces_no_rows():
    assert build_outline(42) == ()
