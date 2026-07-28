# Copyright (c) Jonah Femiani. All Rights Reserved
# License: MIT

"""Whitelist symbols that are used indirectly by framework dispatch."""

from hydra_plugins.hydragen._app import Hydragen
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
Hydragen.action_toggle_multirun
Hydragen.action_clear_log

# Used by Hydra to find the launcher class.
HydragenLauncher.setup
HydragenLauncher.launch
