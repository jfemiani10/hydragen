# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
"""hydragen: a terminal UI for any Hydra application.

Hydra core calls :func:`launch_hydragen` when an app is run with ``--tui``. Keeping
the implementation here (rather than in hydra core) means the core patch stays
tiny and Textual never becomes a hydra-core dependency.
"""

__version__ = "0.1.0"

__all__ = ["launch_hydragen", "__version__"]


def launch_hydragen(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Lazy entry point so importing this package doesn't pull in Textual."""
    from ._app import launch_hydragen as _launch

    return _launch(*args, **kwargs)
