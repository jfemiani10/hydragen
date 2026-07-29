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
from dataclasses import dataclass, field
from typing import Any, ClassVar

from hydra.core.config_loader import ConfigLoader
from hydra.types import HydraContext, RunMode
from omegaconf import DictConfig, OmegaConf, open_dict
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import (
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    RichLog,
    Static,
    Tree,
)
from textual.widgets.tree import TreeNode

NONE = "(none)"

# Path from the config root to a node, used as a stable key for fold state.
ConfigPath = tuple[str, ...]


@dataclass(frozen=True)
class Outline:
    """One row of the resolved-config outline.

    Deliberately free of any Textual types so the tree shape can be built and
    tested without standing up an app.
    """

    label: str
    path: ConfigPath
    children: tuple[Outline, ...] = field(default_factory=tuple)


def _format_scalar(value: Any) -> str:
    """Render a leaf value the way the YAML view used to."""
    return "null" if value is None else str(value)


def build_outline(data: Any, parent: ConfigPath = ()) -> tuple[Outline, ...]:
    """Turn a plain container (from ``OmegaConf.to_container``) into outline rows.

    Mappings and sequences become branches that can be folded; everything else
    becomes a ``key: value`` leaf.
    """
    if isinstance(data, dict):
        items: list[tuple[str, Any]] = [(str(k), v) for k, v in data.items()]
    elif isinstance(data, list):
        items = [(f"[{i}]", v) for i, v in enumerate(data)]
    else:
        return ()

    rows = []
    for key, value in items:
        path = (*parent, key)
        if isinstance(value, dict) and not value:
            rows.append(Outline(f"{key}: {{}}", path))  # nothing to fold into
        elif isinstance(value, list) and not value:
            rows.append(Outline(f"{key}: []", path))
        elif isinstance(value, (dict, list)):
            rows.append(Outline(key, path, build_outline(value, path)))
        else:
            rows.append(Outline(f"{key}: {_format_scalar(value)}", path))
    return tuple(rows)


class ConfigTree(Tree[ConfigPath]):  # type: ignore[misc]
    """Outline tree with the arrow-key folding people expect from an outliner.

    Textual's ``Tree`` only binds ``space`` to toggle a node, so left/right are
    added here.
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("right", "expand_node", "Expand", show=False),
        Binding("left", "collapse_node", "Collapse", show=False),
    ]

    def action_expand_node(self) -> None:
        node = self.cursor_node
        if node is None or not node.allow_expand:
            return
        if node.is_expanded:
            self.action_cursor_down()  # already open, step into the first child
        else:
            node.expand()

    def action_collapse_node(self) -> None:
        node = self.cursor_node
        if node is None:
            return
        if node.allow_expand and node.is_expanded:
            node.collapse()
        else:
            self.action_cursor_parent()


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
    #cfgerror { height: 1fr; border: round $error; padding: 0 1; }
    #cmdline { color: $success; padding: 0 1; height: auto; }
    #log { height: 14; border: round $primary; }
    Input { margin: 0 1; }
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("r", "run_job", "Run"),
        ("c", "focus_config", "Config"),
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
        # Paths the user folded shut. Tracking the collapsed set (rather than the
        # expanded one) keeps this empty while the tree is fully open.
        self._collapsed: set[ConfigPath] = set()
        self._rebuilding = False
        self._focus_before_config: Widget | None = None

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

    def compose_config(self, overrides: list[str]) -> tuple[DictConfig | None, str]:
        """Compose the job config for ``overrides``.

        Returns ``(cfg, "")`` on success and ``(None, error_text)`` on failure,
        so compose errors reach the UI instead of taking the app down.
        """
        try:
            cfg = self.config_loader.load_configuration(
                config_name=self.config_name,
                overrides=overrides,
                run_mode=RunMode.MULTIRUN if self.multirun else RunMode.RUN,
            )
            cfg = cfg.copy()
            with open_dict(cfg):
                cfg.pop("hydra", None)  # show the job config, like --cfg job
            return cfg, ""
        except Exception as exc:  # noqa: BLE001 - surface compose errors in the pane
            return None, f"{type(exc).__name__}\n\n{exc}"

    def compose_outline(self, overrides: list[str]) -> tuple[tuple[Outline, ...], str]:
        """Compose ``overrides`` and shape the result into outline rows."""
        cfg, error = self.compose_config(overrides)
        if cfg is None:
            return (), error
        # resolve=False keeps ${...} interpolations rendered literally, matching
        # the old YAML pane and keeping a failing resolver from breaking the tree.
        return build_outline(OmegaConf.to_container(cfg, resolve=False)), ""

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
                yield ConfigTree("config", id="cfgpane")
                yield Static(id="cfgerror")
                yield Static(id="cmdline")
                yield Input(placeholder="extra overrides, e.g.  db.user=me +debug=true")
                yield RichLog(id="log", highlight=True, markup=False, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_config()
        self.query_one("#log", RichLog).write("Ready. Arrow keys change a group, `r` runs.")

    def refresh_config(self) -> None:
        overrides = self.current_overrides()
        rows, error = self.compose_outline(overrides)
        tree = self.query_one("#cfgpane", ConfigTree)
        errpane = self.query_one("#cfgerror", Static)

        tree.display = not error
        errpane.display = bool(error)
        if error:
            errpane.update(f"compose failed\n\n{error}")
        else:
            self._rebuild_tree(tree, rows)

        flag = " --multirun" if self.multirun else ""
        app_name = self.app_path.replace("\\", "/").rsplit("/", 1)[-1]
        self.query_one("#cmdline", Static).update(f"$ python {app_name}{flag} " + " ".join(overrides))

    def _rebuild_tree(self, tree: ConfigTree, rows: tuple[Outline, ...]) -> None:
        """Redraw the outline, keeping whatever the user had folded.

        The pane recomposes on every keystroke, so rebuilding blindly would
        re-open the whole tree while someone is typing.
        """
        cursor = tree.cursor_line
        self._rebuilding = True
        try:
            tree.clear()
            tree.root.data = ()
            self._add_rows(tree.root, rows)
            tree.root.expand()
        finally:
            self._rebuilding = False
        tree.cursor_line = cursor  # clamped by Tree.validate_cursor_line

    def _add_rows(self, node: TreeNode[ConfigPath], rows: tuple[Outline, ...]) -> None:
        for row in rows:
            if row.children:
                child = node.add(row.label, row.path, expand=row.path not in self._collapsed)
                self._add_rows(child, row.children)
            else:
                node.add_leaf(row.label, row.path)

    # --- events -----------------------------------------------------------

    def on_tree_node_collapsed(self, event: Tree.NodeCollapsed[ConfigPath]) -> None:
        if not self._rebuilding and event.node.data is not None:
            self._collapsed.add(event.node.data)

    def on_tree_node_expanded(self, event: Tree.NodeExpanded[ConfigPath]) -> None:
        if not self._rebuilding and event.node.data is not None:
            self._collapsed.discard(event.node.data)

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

    def action_focus_config(self) -> None:
        """Toggle between the config outline and wherever focus was before it.

        The sidebar contributes one tab stop per config group, so tabbing to the
        outline and back gets long in a project with many groups.
        """
        tree = self.query_one("#cfgpane", ConfigTree)
        if self.focused is tree:
            target = self._focus_before_config
            if target is None or not target.is_attached:
                target = self._first_group_list()
            if target is not None:
                target.focus()
        elif tree.display:  # nothing to focus while the error pane is up
            self._focus_before_config = self.focused
            tree.focus()

    def _first_group_list(self) -> ListView | None:
        return self.query_one(f"#g-{self.groups[0]}", ListView) if self.groups else None

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
