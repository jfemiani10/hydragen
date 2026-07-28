# Copyright (c) Jonah Femiani. All Rights Reserved
# License: MIT

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from hydra_plugins.hydragen import _cli


@patch("hydra_plugins.hydragen._cli.sys.argv", ["hydragen"])
def test_cli_requires_target() -> None:
    with pytest.raises(SystemExit) as exc:
        _cli.main()

    assert exc.value.code == ("Usage: hydragen SCRIPT [ARGS...]\n   or: hydragen -m MODULE [ARGS...]")


@patch("hydra_plugins.hydragen._cli.sys.argv", ["hydragen", "-m"])
def test_cli_requires_module_name() -> None:
    with pytest.raises(SystemExit) as exc:
        _cli.main()

    assert exc.value.code == "hydragen: -m requires a module name"


@patch("hydra_plugins.hydragen._cli.runpy.run_path")
@patch("hydra_plugins.hydragen._cli.register_launcher")
@patch("hydra_plugins.hydragen._cli.sys.argv", ["hydragen", "example/my_app.py", "model=cnn"])
def test_cli_runs_script_with_launcher(
    register_launcher: MagicMock,
    run_path: MagicMock,
) -> None:
    # Stacked @patch injects mocks from the inside out.
    # `sys.argv` is patched with a fixed value and does not add a function arg.

    _cli.main()

    # `assert_called_once_with` checks both call count and call arguments.
    # This gives a strong guarantee that we invoked exactly one launcher setup
    # and one script handoff with the expected parameters.
    register_launcher.assert_called_once_with()
    run_path.assert_called_once_with("example/my_app.py", run_name="__main__")
    assert _cli.sys.argv == [
        "example/my_app.py",
        "--multirun",
        "model=cnn",
        "hydra/launcher=hydragen",
    ]


@patch("hydra_plugins.hydragen._cli.runpy.run_module")
@patch("hydra_plugins.hydragen._cli.register_launcher")
@patch("hydra_plugins.hydragen._cli.sys.argv", ["hydragen", "-m", "maptrace.segmentation.train", "model=unet"])
def test_cli_runs_module_with_launcher(
    register_launcher: MagicMock,
    run_module: MagicMock,
) -> None:
    # Order reminder: nearest mock-producing decorator -> first function parameter.

    _cli.main()

    # This test ensures that the CLI correctly invokes the launcher and runs the specified module with the expected arguments.
    # The `assert_called_once_with` method checks that the mocked functions were called exactly once with the specified arguments,
    register_launcher.assert_called_once_with()
    run_module.assert_called_once_with("maptrace.segmentation.train", run_name="__main__")

    # The final assertion checks that the `sys.argv` list has been modified to include the `--multirun` flag and
    # the `hydra/launcher=hydragen` override, ensuring that the launcher is invoked correctly.
    assert _cli.sys.argv == [
        "maptrace.segmentation.train",
        "--multirun",
        "model=unet",
        "hydra/launcher=hydragen",
    ]

    # Since run_module is mocked, the actual module code is not executed, and we are only testing the CLI's
    # behavior in setting up the environment and invoking the module with the correct arguments.


@patch("hydra_plugins.hydragen._cli.runpy.run_path")
@patch("hydra_plugins.hydragen._cli.register_launcher")
@patch(
    "hydra_plugins.hydragen._cli.sys.argv",
    ["hydragen", "example/my_app.py", "model=cnn", "dataset=cifar"],
)
def test_cli_passes_multiple_overrides(
    register_launcher: MagicMock,
    run_path: MagicMock,
) -> None:
    """Test that CLI correctly passes multiple config overrides to the launcher.

    Regression test for: https://github.com/jfemiani10/hydragen/issues/1
    Issue: hydragen example/my_app.py model=cnn dataset=cifar should launch
    the TUI with those overrides pre-populated.

    Key insight: --multirun is required so Hydra invokes the launcher plugin.
    Placing it before user overrides ensures proper argument parsing.
    """
    _cli.main()

    # Verify:
    # 1. Launcher is registered before Hydra loads
    # 2. All overrides are preserved
    # 3. --multirun is placed before overrides (ensures launcher is invoked)
    register_launcher.assert_called_once_with()
    run_path.assert_called_once_with("example/my_app.py", run_name="__main__")
    assert _cli.sys.argv == [
        "example/my_app.py",
        "--multirun",
        "model=cnn",
        "dataset=cifar",
        "hydra/launcher=hydragen",
    ]


@patch("hydra_plugins.hydragen._cli.runpy.run_module")
@patch("hydra_plugins.hydragen._cli.register_launcher")
@patch(
    "hydra_plugins.hydragen._cli.sys.argv",
    ["hydragen", "-m", "maptrace.segmentation.train", "model=unet", "dataset=imagenet"],
)
def test_cli_module_passes_multiple_overrides(
    register_launcher: MagicMock,
    run_module: MagicMock,
) -> None:
    """Regression test for https://github.com/jfemiani10/hydragen/issues/1.

    Ensure module mode preserves multiple user overrides and places --multirun
    before them so Hydra invokes the custom launcher.
    """
    _cli.main()

    register_launcher.assert_called_once_with()
    run_module.assert_called_once_with("maptrace.segmentation.train", run_name="__main__")
    assert _cli.sys.argv == [
        "maptrace.segmentation.train",
        "--multirun",
        "model=unet",
        "dataset=imagenet",
        "hydra/launcher=hydragen",
    ]
