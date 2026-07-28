# Copyright (c) Jonah Femiani. All Rights Reserved
# License: MIT

from __future__ import annotations

import pytest

from hydra_plugins.hydragen import _cli


def test_cli_requires_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_cli.sys, "argv", ["hydragen"])

    with pytest.raises(SystemExit) as exc:
        _cli.main()

    assert exc.value.code == ("Usage: hydragen SCRIPT [ARGS...]\n   or: hydragen -m MODULE [ARGS...]")


def test_cli_requires_module_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_cli.sys, "argv", ["hydragen", "-m"])

    with pytest.raises(SystemExit) as exc:
        _cli.main()

    assert exc.value.code == "hydragen: -m requires a module name"


def test_cli_runs_script_with_launcher(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_register() -> None:
        calls.append("register")

    def fake_run_path(path: str, run_name: str) -> None:
        calls.append(("run_path", path, run_name, list(_cli.sys.argv)))

    monkeypatch.setattr(_cli.sys, "argv", ["hydragen", "example/my_app.py", "model=cnn"])
    monkeypatch.setattr(_cli, "register_launcher", fake_register)
    monkeypatch.setattr(_cli.runpy, "run_path", fake_run_path)

    _cli.main()

    assert calls == [
        "register",
        (
            "run_path",
            "example/my_app.py",
            "__main__",
            [
                "example/my_app.py",
                "model=cnn",
                "hydra/launcher=hydragen",
            ],
        ),
    ]


def test_cli_runs_module_with_launcher(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_register() -> None:
        calls.append("register")

    def fake_run_module(module_name: str, run_name: str) -> None:
        calls.append(("run_module", module_name, run_name, list(_cli.sys.argv)))

    monkeypatch.setattr(
        _cli.sys,
        "argv",
        ["hydragen", "-m", "maptrace.segmentation.train", "model=unet"],
    )
    monkeypatch.setattr(_cli, "register_launcher", fake_register)
    monkeypatch.setattr(_cli.runpy, "run_module", fake_run_module)

    _cli.main()

    assert calls == [
        "register",
        (
            "run_module",
            "maptrace.segmentation.train",
            "__main__",
            [
                "maptrace.segmentation.train",
                "model=unet",
                "hydra/launcher=hydragen",
            ],
        ),
    ]
