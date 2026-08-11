# SPDX-License-Identifier: GPL-3.0-or-later
"""Addon preferences."""

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
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

    # -- Highlight -------------------------------------------------------------

    show_highlight: BoolProperty(
        name="Show Axis Handle",
        description=(
            "Show the yellow handle marking the last used axis. Click or drag "
            "it to run the same transform a middle mouse drag would"
        ),
        default=True,
    )
    highlight_requires_gizmo: BoolProperty(
        name="Only With Gizmos Visible",
        description="Hide the handle when viewport gizmos are turned off",
        default=True,
    )
    highlight_color: FloatVectorProperty(
        name="Color",
        description="Handle color",
        subtype='COLOR',
        size=3,
        min=0.0,
        max=1.0,
        default=(1.0, 0.85, 0.1),
    )
    highlight_alpha: FloatProperty(
        name="Opacity",
        min=0.0,
        max=1.0,
        default=0.9,
    )
    highlight_scale: FloatProperty(
        name="Size",
        description="Multiplier on the handle size",
        min=0.1,
        max=4.0,
        default=1.0,
    )

    # -- Internal --------------------------------------------------------------

    #: JSON record of every keymap change made, so they can be reverted exactly.
    #: Stored in preferences (rather than in memory) so a reset still works
    #: after a crash or an unclean shutdown.
    keymap_backup: StringProperty(default="", options={'HIDDEN'})

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
        box.label(text="Axis Handle", icon='PROP_ON')
        col = box.column()
        col.prop(self, "show_highlight")
        sub = col.column()
        sub.enabled = self.show_highlight
        sub.prop(self, "highlight_requires_gizmo")
        row = sub.row(align=True)
        row.prop(self, "highlight_color", text="")
        row.prop(self, "highlight_alpha", text="Opacity", slider=True)
        sub.prop(self, "highlight_scale")

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


def unregister():
    bpy.utils.unregister_class(MayaGizmoPreferences)
