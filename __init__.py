# SPDX-License-Identifier: GPL-3.0-or-later
"""Remember Last Used Axis.

Brings Autodesk Maya's "transform along the last used gizmo axis" workflow to
Blender's 3D viewport:

* Dragging any transform gizmo handle (or using ``G``/``R``/``S`` with an axis
  constraint) remembers that axis, and the sidebar names it.
* Blender's viewport is left exactly as it is: no gizmo is replaced, suppressed
  or drawn over, and no colour is changed.
* Right-mouse-drag anywhere in the viewport re-runs that transform along that
  axis, interactively -- the drag distance drives the amount. A plain right
  click still opens the context menu.
* Blender's own mouse bindings are left alone: middle mouse still orbits, pans
  and zooms exactly as it does by default.

Every keymap change the addon makes is recorded and reverted automatically when
the addon is disabled, and can be reverted at any time from the preferences.
"""

from . import prefs
from . import state
from . import operators
from . import keymaps
from . import ui

# Registration order matters: preferences hold the settings every other module
# reads, and the keymap module needs the operators to already exist.
_MODULES = (
    prefs,
    state,
    operators,
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
