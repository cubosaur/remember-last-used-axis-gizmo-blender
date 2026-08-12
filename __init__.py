# SPDX-License-Identifier: GPL-3.0-or-later
"""Maya Gizmo for Blender.

Brings Autodesk Maya's "transform along the last used gizmo axis" workflow to
Blender's 3D viewport:

* Dragging any transform gizmo handle (or using ``G``/``R``/``S`` with an axis
  constraint) remembers that axis.
* The remembered axis is drawn in yellow, by recolouring that axis in the
  theme. Blender's own gizmo is left completely alone.
* Middle-mouse-drag anywhere in the viewport re-runs that transform along that
  axis, interactively -- the drag distance drives the amount.
* Viewport orbit moves from middle-mouse to right-mouse-drag.

Every keymap change the addon makes is recorded and reverted automatically when
the addon is disabled, and can be reverted at any time from the preferences.
"""

from . import prefs
from . import state
from . import operators
from . import highlight
from . import keymaps
from . import ui

# Registration order matters: preferences hold the settings every other module
# reads, the highlight reads the tracked axis out of state, and the keymap
# module needs the operators to already exist.
_MODULES = (
    prefs,
    state,
    operators,
    highlight,
    keymaps,
    ui,
)


def register():
    for module in _MODULES:
        module.register()


def unregister():
    # Unregister in reverse, and never let one failure strand the rest --
    # keymaps.unregister() in particular is what gives the user their viewport
    # navigation back.
    for module in reversed(_MODULES):
        try:
            module.unregister()
        except Exception:
            import traceback
            traceback.print_exc()
