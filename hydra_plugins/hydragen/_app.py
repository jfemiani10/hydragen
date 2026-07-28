# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
"""The Textual application used by Hydragen.

Everything shown is derived from the running app's own ``ConfigLoader``, so the
TUI adapts to any Hydra project: groups, options and the initial selection all
come from Hydra itself rather than from hardcoded knowledge of a project.
"""

from __future__ import annotations

import contextlib
import subprocess
import sys
from typing import Any, ClassVar

from hydra.core.config_loader import ConfigLoader
from hydra.types import HydraContext, RunMode
from omegaconf import DictConfig, OmegaConf, open_dict
from rich.syntax import Syntax
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    RichLog,
    Static,
)

NONE = "(none)"


class Hydragen(App):  # type: ignore[misc]
    TITLE = "Hydra"
    SUB_TITLE = "compose, inspect, launch"

    CSS = """
    #body { height: 1fr; }
    #sidebar { width: 34; border-right: solid $accent; }
    #sidebar ListView { height: auto; max-height: 8; margin-bottom: 1; }
    .grouplabel { color: $accent; text-style: bold; padding: 0 1; }
    #right { width: 1fr; }
    #cfgpane { height: 1fr; border: round $primary; padding: 0 1; }
    #cmdline { color: $success; padding: 0 1; height: auto; }
    #log { height: 14; border: round $primary; }
    Input { margin: 0 1; }
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("r", "run_job", "Run"),
        ("m", "toggle_multirun", "Multirun"),
        ("x", "clear_log", "Clear log"),
        ("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        config_loader: ConfigLoader,
        config_name: str | None,
        overrides: list[str],
        app_path: str,
    ) -> None:
        super().__init__()
        self.config_loader = config_loader
        self.config_name = config_name
        self.base_overrides = list(overrides)
        self.app_path = app_path
        self.multirun = False
        self.extra = ""

        # Ask Hydra which groups exist and which option each one resolved to.
        self.groups: list[str] = [g for g in sorted(config_loader.list_groups("")) if g != "hydra"]
        cfg = config_loader.load_configuration(
            config_name=config_name,
            overrides=self.base_overrides,
            run_mode=RunMode.RUN,
        )
        self.choices: dict[str, Any] = dict(cfg.hydra.runtime.choices)

        self.options: dict[str, list[str]] = {}
        self.selection: dict[str, str] = {}
        # A group already in the defaults list is overridden as `group=opt`;
        # anything else has to be appended with `+group=opt`.
        self.in_defaults: dict[str, bool] = {}
        for group in self.groups:
            opts = sorted(config_loader.get_group_options(group))
            opts = self._hide_schema_configs(opts)
            chosen = self.choices.get(group)
            if chosen is not None and chosen not in opts:
                opts = [chosen, *opts]  # never hide what's actually selected
            self.in_defaults[group] = chosen is not None
            if chosen is None:
                opts = [NONE, *opts]
                chosen = NONE
            self.options[group] = opts
            self.selection[group] = chosen if chosen in opts else opts[0]

    @staticmethod
    def _hide_schema_configs(opts: list[str]) -> list[str]:
        """Drop structured-config schemas from the picker.

        Hydra's convention (and its own docs) is to register a group's schema in
        that same group as ``base_<name>``, which makes it show up alongside the
        real options. Those aren't meant to be selected, so hide them -- unless
        that would empty the group, in which case show everything.
        """
        visible = [o for o in opts if not o.startswith("base_")]
        return visible if visible else opts

    # --- composition ------------------------------------------------------

    def current_overrides(self) -> list[str]:
        out = list(self.base_overrides)
        for group in self.groups:
            value = self.selection[group]
            if value == NONE:
                continue
            if self.choices.get(group) == value and self.in_defaults[group]:
                continue  # already the default, no need to spell it out
            out.append(f"{group}={value}" if self.in_defaults[group] else f"+{group}={value}")
        out.extend(self.extra.split())
        return out

    def compose_yaml(self, overrides: list[str]) -> tuple[str, bool]:
        try:
            cfg = self.config_loader.load_configuration(
                config_name=self.config_name,
                overrides=overrides,
                run_mode=RunMode.MULTIRUN if self.multirun else RunMode.RUN,
            )
            cfg = cfg.copy()
            with open_dict(cfg):
                cfg.pop("hydra", None)  # show the job config, like --cfg job
            return OmegaConf.to_yaml(cfg), True
        except Exception as exc:  # noqa: BLE001 - surface compose errors in the pane
            return f"{type(exc).__name__}\n\n{exc}", False

    # --- layout -----------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            with VerticalScroll(id="sidebar"):
                for group in self.groups:
                    yield Label(f"{group}/", classes="grouplabel")
                    opts = self.options[group]
                    yield ListView(
                        *[ListItem(Label(o)) for o in opts],
                        id=f"g-{group}",
                        initial_index=opts.index(self.selection[group]),
                    )
            with Vertical(id="right"):
                yield Static(id="cfgpane")
                yield Static(id="cmdline")
                yield Input(placeholder="extra overrides, e.g.  db.user=me +debug=true")
                yield RichLog(id="log", highlight=True, markup=False, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_config()
        self.query_one("#log", RichLog).write("Ready. Arrow keys change a group, `r` runs.")

    def refresh_config(self) -> None:
        overrides = self.current_overrides()
        text, ok = self.compose_yaml(overrides)
        pane = self.query_one("#cfgpane", Static)
        if ok:
            pane.update(Syntax(text, "yaml", theme="ansi_dark", word_wrap=True))
        else:
            pane.update(f"compose failed\n\n{text}")
        flag = " --multirun" if self.multirun else ""
        app_name = self.app_path.replace("\\", "/").rsplit("/", 1)[-1]
        self.query_one("#cmdline", Static).update(f"$ python {app_name}{flag} " + " ".join(overrides))

    # --- events -----------------------------------------------------------

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        group = (event.list_view.id or "")[2:]
        if group in self.selection and event.list_view.index is not None:
            self.selection[group] = self.options[group][event.list_view.index]
            self.refresh_config()

    def on_input_changed(self, event: Input.Changed) -> None:
        self.extra = event.value
        self.refresh_config()

    def on_input_submitted(self) -> None:
        self.action_run_job()

    # --- actions ----------------------------------------------------------

    def action_toggle_multirun(self) -> None:
        self.multirun = not self.multirun
        self.refresh_config()

    def action_clear_log(self) -> None:
        self.query_one("#log", RichLog).clear()

    def action_run_job(self) -> None:
        cmd = [sys.executable, self.app_path]
        if self.multirun:
            cmd.append("--multirun")
        cmd += self.current_overrides()
        self.query_one("#log", RichLog).write(f"\n$ {' '.join(cmd[1:])}\n")
        self.run_job(cmd)

    @work(thread=True, exclusive=True)
    def run_job(self, cmd: list[str]) -> None:
        log = self.query_one("#log", RichLog)
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                self.call_from_thread(log.write, line.rstrip())
            self.call_from_thread(log.write, f"[exit {proc.wait()}]")
        except Exception as exc:  # noqa: BLE001 - report launch failures in the log
            self.call_from_thread(log.write, f"failed to launch: {exc}")


def launch_hydragen(
    config_loader: ConfigLoader,
    config_name: str | None,
    overrides: list[str],
    app_path: str | None = None,
) -> None:
    """Entry point invoked by hydra core through the patched integration path."""
    Hydragen(
        config_loader=config_loader,
        config_name=config_name,
        overrides=overrides,
        app_path=app_path or sys.argv[0],
    ).run()


def run_tui(
    *,
    hydra_context: HydraContext,
    config: DictConfig,
    overrides: list[str],
) -> None:
    """Launch the Hydragen UI from a Hydra launcher plugin."""
    filtered_overrides = [ov for ov in overrides if ov not in {"hydra/launcher=hydragen", "hydra.mode=MULTIRUN"}]

    config_name: str | None = None
    # Hydra schema differs across versions; config_name may not exist.
    with contextlib.suppress(AttributeError):
        config_name = config.hydra.job.config_name

    app = Hydragen(
        config_loader=hydra_context.config_loader,
        config_name=config_name,
        overrides=filtered_overrides,
        app_path=sys.argv[0],
    )

    # Hydra mode schema may not exist; default to RUN mode.
    with contextlib.suppress(AttributeError):
        app.multirun = str(config.hydra.mode).upper().endswith("MULTIRUN")

    app.run()
