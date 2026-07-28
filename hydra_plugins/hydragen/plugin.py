# Copyright (c) Jonah Femiani. All Rights Reserved
# License: MIT

from __future__ import annotations

import contextlib
from collections.abc import Sequence

from hydra.core.config_store import ConfigStore
from hydra.core.utils import JobReturn
from hydra.plugins.launcher import Launcher
from hydra.types import HydraContext, TaskFunction
from omegaconf import DictConfig


class HydragenLauncher(Launcher):
    def setup(
        self,
        *,
        hydra_context: HydraContext,
        task_function: TaskFunction,
        config: DictConfig,
    ) -> None:
        self.hydra_context = hydra_context
        self.task_function = task_function
        self.config = config

    def launch(
        self,
        job_overrides: Sequence[Sequence[str]],
        initial_job_idx: int,
    ) -> Sequence[JobReturn]:
        del initial_job_idx

        # Import Textual lazily so normal Hydra startup remains fast.
        from ._app import run_tui

        overrides: list[str] = []
        if job_overrides:
            overrides = list(job_overrides[0])

        with contextlib.suppress(Exception):  #  Hydra schema differs across versions
            # Prefer Hydra's parsed task overrides when available.
            overrides = list(self.config.hydra.overrides.task)

        run_tui(
            hydra_context=self.hydra_context,
            config=self.config,
            overrides=overrides,
        )

        # UI handled execution directly.
        return []


def register_launcher() -> None:
    from hydra.core.plugins import Plugins

    if not any(cls is HydragenLauncher for cls in Plugins.instance().discover(Launcher)):
        Plugins.instance().register(HydragenLauncher)


ConfigStore.instance().store(
    group="hydra/launcher",
    name="hydragen",
    node={"_target_": "hydra_plugins.hydragen.plugin.HydragenLauncher"},
    provider="hydragen",
)
