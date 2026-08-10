# SPDX-License-Identifier: GPL-3.0-or-later
"""Sidebar panel."""

import bpy
from bpy.types import Panel

from . import state
from .prefs import get_prefs


class MGB_PT_sidebar(Panel):
    bl_label = "Maya Gizmo"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "View"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        p = get_prefs(context)

        box = layout.box()
        row = box.row()
        row.label(text="Last Used Axis")
        row = box.row()
        row.label(text=state.LAST.describe(), icon='EMPTY_ARROWS')
        row = box.row()
        row.enabled = state.LAST.valid
        row.operator("mgb.clear_last_axis", text="Clear", icon='X')

        if p is None:
            return

        col = layout.column(align=True)
        col.prop(p, "enable_mmb_transform", text="MMB Transform")
        col.prop(p, "remap_orbit_to_rmb", text="RMB Orbit")
        col.prop(p, "show_highlight", text="Highlight")

        layout.operator("mgb.reset_keymap", icon='LOOP_BACK')


def register():
    bpy.utils.register_class(MGB_PT_sidebar)


def unregister():
    bpy.utils.unregister_class(MGB_PT_sidebar)
