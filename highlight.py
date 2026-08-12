# SPDX-License-Identifier: GPL-3.0-or-later
"""Colour the last used transform axis yellow, in Blender's own gizmo.

Blender's transform gizmo is C code, and Python cannot reach the handles it is
made of. A ``Region`` exposes no gizmo map, ``WindowManager`` offers only
``gizmo_group_type_ensure`` and ``gizmo_group_type_unlink_delayed``, and
``context.gizmo_group`` is ``None`` anywhere outside a Python gizmo group's own
callbacks -- there is simply no ``Gizmo`` object to recolour.

The one source of those handle colours that Python *can* write is the theme:
the transform gizmo takes its axis colours from
``theme.user_interface.axis_x/y/z``. Setting one of them to the highlight
colour tints that axis of Blender's own gizmo, at whatever size the interface
scale and the Gizmo Size preference give it, with nothing drawn on top and
nothing suppressed. The gizmo stays entirely Blender's, so it also picks up
every gizmo feature and fix for free.

Those same three entries colour the viewport's floor axis lines and the
navigation gizmo, so highlighting X turns the X floor line and the navigation
gizmo's X ball yellow as well. That is the accepted cost of leaving the gizmo
alone: there is no separate theme entry for the gizmo's axes.

The colours being replaced are recorded in the addon preferences before the
first change, so a crash while a highlight is applied cannot strand the theme
-- the next registration puts them back.
"""

import json

import bpy

from . import state
from .prefs import get_prefs

#: Theme entries the transform gizmo takes its axis colours from, in axis order.
AXIS_FIELDS = ("axis_x", "axis_y", "axis_z")

#: The native transform gizmo group. Nothing here suppresses it; this is only
#: used to undo the suppression that versions up to 1.2.7 applied, so upgrading
#: mid-session cannot leave a viewport without a gizmo.
NATIVE_GIZMO_GROUP = "VIEW3D_GGT_xform_gizmo"

#: How often the last used axis is checked, in seconds. The theme lives in
#: preferences, and writing preferences from the viewport draw handler that
#: tracks the axis is not safe, so the write happens on a timer instead. Well
#: below the threshold where the delay is noticeable after a transform.
INTERVAL = 0.15

#: Axis indices currently tinted, so the theme is only written when it changes.
#: ``None`` means "unknown", which forces the next check to write.
_applied = None


def _user_interface(context=None):
    ctx = context or bpy.context
    try:
        return ctx.preferences.themes[0].user_interface
    except (AttributeError, IndexError):
        return None


def wanted_axes(prefs):
    """Axis indices that should be drawn in the highlight colour."""
    if prefs is None or not prefs.show_highlight:
        return frozenset()

    last = state.LAST
    if not last.valid:
        return frozenset()

    if last.kind == state.ROTATE:
        index = last.rotate_axis_index
        return frozenset() if index is None else frozenset((index,))

    if last.kind in {state.TRANSLATE, state.RESIZE}:
        # A plane handle constrains two axes, and both of them light up. A
        # screen space move or a uniform scale constrains none, and the handles
        # Blender draws for those have no axis colour to borrow anyway.
        return frozenset(last.axis_indices)

    return frozenset()


# ---------------------------------------------------------------------------
# Theme colours
# ---------------------------------------------------------------------------

def _read_colours(ui):
    return [tuple(getattr(ui, field))[:3] for field in AXIS_FIELDS]


def _write_colours(ui, colours):
    for field, colour in zip(AXIS_FIELDS, colours):
        try:
            setattr(ui, field, colour)
        except (AttributeError, ValueError):
            pass


def _load_backup(prefs):
    """The user's own axis colours, or ``None`` if nothing is tinted."""
    raw = getattr(prefs, "theme_backup", "")
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, list) or len(data) != len(AXIS_FIELDS):
        return None
    try:
        return [tuple(float(c) for c in colour)[:3] for colour in data]
    except (TypeError, ValueError):
        return None


def _store_backup(prefs, colours):
    prefs.theme_backup = json.dumps([list(colour) for colour in colours])


def _tag_redraw():
    for window in getattr(bpy.context.window_manager, "windows", ()):
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


def apply(context=None):
    """Tint the last used axes, and put every other axis back."""
    global _applied

    prefs = get_prefs(context)
    ui = _user_interface(context)
    if prefs is None or ui is None:
        return

    wanted = wanted_axes(prefs)
    if wanted == _applied:
        return

    original = _load_backup(prefs)
    if wanted:
        if original is None:
            # Nothing is tinted yet, so what is in the theme now is the user's.
            original = _read_colours(ui)
            _store_backup(prefs, original)
        highlight = tuple(prefs.highlight_color)[:3]
        _write_colours(ui, [
            highlight if index in wanted else original[index]
            for index in range(len(AXIS_FIELDS))
        ])
    else:
        if original is not None:
            _write_colours(ui, original)
        prefs.theme_backup = ""

    _applied = wanted
    _tag_redraw()


def refresh(context=None):
    """Write the tint again, after the highlight colour itself changed."""
    global _applied
    _applied = None
    apply(context)


def restore():
    """Put the user's axis colours back, whatever state they were left in."""
    global _applied
    _applied = None

    prefs = get_prefs()
    ui = _user_interface()
    if prefs is None or ui is None:
        return
    original = _load_backup(prefs)
    if original is not None:
        _write_colours(ui, original)
    prefs.theme_backup = ""
    _tag_redraw()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def _tick():
    apply()
    return INTERVAL


@bpy.app.handlers.persistent
def _on_load(_dummy):
    # A file load replaces the window manager, so the tint is re-evaluated
    # against whatever the new file's last transform turns out to be.
    global _applied
    _applied = None


def register():
    global _applied
    _applied = None
    if bpy.app.background:
        return

    # Versions up to 1.2.7 unlinked the native gizmo group and drew their own.
    # Upgrading in place would otherwise leave it unlinked for the session.
    try:
        bpy.types.WindowManager.gizmo_group_type_ensure(NATIVE_GIZMO_GROUP)
    except Exception:
        import traceback
        traceback.print_exc()

    # Recover the theme if a crash left a highlight applied.
    restore()

    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=INTERVAL, persistent=True)
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)


def unregister():
    if _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    if not bpy.app.background:
        restore()
