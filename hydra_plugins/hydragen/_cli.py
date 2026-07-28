# Copyright (c) 2026 Jonah Femiani. All Rights Reserved
# License: MIT

from __future__ import annotations

import runpy
import sys

from hydra_plugins.hydragen.plugin import register_launcher


def main() -> None:
    """Run a Python script or module with the Hydragen launcher enabled."""
    args = sys.argv[1:]

    if not args:
        raise SystemExit("Usage: hydragen SCRIPT [ARGS...]\n   or: hydragen -m MODULE [ARGS...]")

    register_launcher()

    if args[0] == "-m":
        if len(args) < 2:
            raise SystemExit("hydragen: -m requires a module name")

        module_name = args[1]
        sys.argv = [module_name, *args[2:], "--multirun", "hydra/launcher=hydragen"]
        runpy.run_module(module_name, run_name="__main__")
    else:
        script_path = args[0]
        sys.argv = [script_path, *args[1:], "--multirun", "hydra/launcher=hydragen"]
        runpy.run_path(script_path, run_name="__main__")
