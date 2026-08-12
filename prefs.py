# SPDX-License-Identifier: GPL-3.0-or-later
"""Addon preferences."""

import json

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    StringProperty,
)
from bpy.types import AddonPreferences

ADDON_ID = __package__


def get_prefs(context=None):
    """Return the addon preferences, or ``None`` if they are unavailable.

    Preferences can genuinely be missing -- during unregistration, or when
    Blender runs in background mode -- so every caller must handle ``None``.
    """
    ctx = context or bpy.context
    try:
        return ctx.preferences.addons[ADDON_ID].preferences
    except (KeyError, AttributeError):
        return None


def _keymap_update(self, context):
    """Re-apply keymap changes when a keymap related preference changes."""
    from . import keymaps
    keymaps.reapply()


#: Theme entries 1.3.0 recoloured to highlight the last used axis.
_AXIS_FIELDS = ("axis_x", "axis_y", "axis_z")


def repair_theme():
    """Put back an axis colour left tinted by 1.3.0.

    That version highlighted the last used axis by recolouring it in the theme,
    recording the colour it replaced in :attr:`MayaGizmoPreferences.theme_backup`
    first. The highlight is gone, so anything still recorded is a tint nothing
    else is going to undo -- an upgrade that skipped the old version's clean
    shutdown, or a crash while a highlight was applied.
    """
    prefs = get_prefs()
    if prefs is None or not prefs.theme_backup:
        return None

    try:
        colours = json.loads(prefs.theme_backup)
    except ValueError:
        colours = None

    if isinstance(colours, list) and len(colours) == len(_AXIS_FIELDS):
        try:
            ui = bpy.context.preferences.themes[0].user_interface
            for field, colour in zip(_AXIS_FIELDS, colours):
                setattr(ui, field, colour)
        except (AttributeError, IndexError, TypeError, ValueError):
            pass

    prefs.theme_backup = ""
    return None


class MayaGizmoPreferences(AddonPreferences):
    bl_idname = ADDON_ID

    # -- Middle mouse transform ------------------------------------------------

    enable_mmb_transform: BoolProperty(
        name="Middle Mouse Transform",
        description=(
            "Middle-mouse-drag in the 3D viewport runs the last used transform "
            "along the last used axis. Disables the default middle mouse orbit"
        ),
        default=True,
        update=_keymap_update,
    )
    mmb_activation: EnumProperty(
        name="Activation",
        description="When the middle mouse button starts the transform",
        items=(
            ('PRESS', "On Press",
             "Start as soon as the button goes down. Most responsive, matches Maya"),
            ('CLICK_DRAG', "On Drag",
             "Start after the mouse has moved a short distance. Use this if "
             "On Press misbehaves with your input device"),
        ),
        default='PRESS',
        update=_keymap_update,
    )
    transform_source: EnumProperty(
        name="Transform Type",
        description="Which transform the middle mouse drag performs",
        items=(
            ('LAST_USED', "Last Used",
             "Repeat the last transform you performed, whether you used a gizmo "
             "handle or the G/R/S shortcuts"),
            ('ACTIVE_TOOL', "Active Tool",
             "Use the active Move/Rotate/Scale tool, falling back to the last "
             "used transform for any other tool"),
        ),
        default='LAST_USED',
    )
    fallback_orbit: BoolProperty(
        name="Orbit When Nothing To Transform",
        description=(
            "If no axis has been used yet, or nothing is selected, "
            "middle-mouse-drag orbits the view as it normally would"
        ),
        default=True,
    )

    # -- Navigation ------------------------------------------------------------

    remap_orbit_to_rmb: BoolProperty(
        name="Orbit With Right Mouse Drag",
        description=(
            "Add right-mouse-drag as the viewport orbit. "
            "Shift+MMB pan and Ctrl+MMB zoom are left untouched"
        ),
        default=True,
        update=_keymap_update,
    )
    retime_context_menu: BoolProperty(
        name="Context Menu On Click",
        description=(
            "Change the 3D viewport context menus from mouse-press to "
            "mouse-click so that a right-mouse-drag can orbit instead of "
            "immediately opening the menu. A normal right click still opens it"
        ),
        default=True,
        update=_keymap_update,
    )
    rmb_pan_zoom: BoolProperty(
        name="Also Pan/Zoom With Right Mouse",
        description=(
            "WARNING: Shift+RMB places the 3D cursor and Ctrl+RMB is lasso "
            "select in the default keymap. Enabling this overrides both. "
            "Pan and zoom already work on Shift+MMB and Ctrl+MMB"
        ),
        default=False,
        update=_keymap_update,
    )

    # -- Internal --------------------------------------------------------------

    #: JSON record of every keymap change made, so they can be reverted exactly.
    #: Stored in preferences (rather than in memory) so a reset still works
    #: after a crash or an unclean shutdown.
    keymap_backup: StringProperty(default="", options={'HIDDEN'})

    #: Axis colours recorded by 1.3.0 while it tinted one of them. Kept only so
    #: :func:`repair_theme` can put a leftover tint back; nothing writes it now.
    theme_backup: StringProperty(default="", options={'HIDDEN'})

    def draw(self, context):
        from . import keymaps

        layout = self.layout

        header = layout.box()
        row = header.row()
        row.label(text="Keymap", icon='KEYINGSET')
        sub = row.row()
        sub.alignment = 'RIGHT'
        if keymaps.is_applied():
            sub.label(text="Active", icon='CHECKMARK')
        else:
            sub.label(text="Not applied", icon='X')

        col = header.column()
        col.prop(self, "enable_mmb_transform")
        sub = col.column()
        sub.enabled = self.enable_mmb_transform
        sub.prop(self, "mmb_activation")
        sub.prop(self, "transform_source")
        sub.prop(self, "fallback_orbit")

        col.separator()
        col.prop(self, "remap_orbit_to_rmb")
        sub = col.column()
        sub.enabled = self.remap_orbit_to_rmb
        sub.prop(self, "retime_context_menu")
        sub.prop(self, "rmb_pan_zoom", icon='ERROR' if self.rmb_pan_zoom else 'NONE')

        warning = keymaps.compatibility_warning(context)
        if warning:
            box = header.box()
            box.alert = True
            for line in warning:
                box.label(text=line, icon='ERROR')

        box = layout.box()
        box.label(text="Reset", icon='LOOP_BACK')
        col = box.column()
        col.label(
            text="Keymap changes are also reverted automatically when you "
                 "disable the addon.",
            icon='INFO',
        )
        row = col.row()
        row.scale_y = 1.4
        row.operator("mgb.reset_keymap", icon='LOOP_BACK')
        col.operator("mgb.restore_blender_defaults", icon='TRASH')


def register():
    bpy.utils.register_class(MayaGizmoPreferences)
    if bpy.app.background:
        return
    # Deferred by a tick: the addon preferences are not reachable until Blender
    # has finished enabling the addon, and this needs to read one.
    bpy.app.timers.register(repair_theme, first_interval=0.0)


def unregister():
    if bpy.app.timers.is_registered(repair_theme):
        bpy.app.timers.unregister(repair_theme)
    bpy.utils.unregister_class(MayaGizmoPreferences)
