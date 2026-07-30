# Copyright (c) Jonah Femiani. All Rights Reserved
# License: MIT

"""Whitelist symbols that are used indirectly by framework dispatch."""

from textual.widgets import Input

from hydra_plugins.hydragen._app import ConfigTree, Hydragen
from hydra_plugins.hydragen.plugin import HydragenLauncher

# These are called indirectly by the framework, so vulture can't see them. We need to
# explicitly whitelist them to avoid false positives when we run vulture to check for dead code.

# Used by textual to find the app class.
Hydragen.TITLE
Hydragen.SUB_TITLE
Hydragen.CSS
Hydragen.BINDINGS
Hydragen.compose
Hydragen.on_mount
Hydragen.on_list_view_highlighted
Hydragen.on_input_changed
Hydragen.on_input_submitted
Hydragen.on_tree_node_collapsed
Hydragen.on_tree_node_expanded
Hydragen.on_tree_node_selected
Hydragen.action_toggle_multirun
Hydragen.action_clear_log
Hydragen.action_focus_config
Hydragen.action_cancel_edit
Hydragen.action_remove_override

# Bound to arrow keys by textual through BINDINGS.
ConfigTree.BINDINGS
ConfigTree.action_expand_node
ConfigTree.action_collapse_node

# Textual widget properties, assigned to when swapping panes and when prompting
# for a node's new value.
ConfigTree.display
Input.placeholder

# Used by Hydra to find the launcher class.
HydragenLauncher.setup
HydragenLauncher.launch
