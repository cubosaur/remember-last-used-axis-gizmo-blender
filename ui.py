# SPDX-License-Identifier: GPL-3.0-or-later
"""Sidebar panel."""

import bpy
from bpy.types import Panel

from . import state
from .prefs import get_prefs


class RLA_PT_sidebar(Panel):
    bl_label = "Remember Last Used Axis"
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
        row.operator("rla.clear_last_axis", text="Clear", icon='X')

        if p is None:
            return

        col = layout.column(align=True)
        col.prop(p, "enable_rmb_transform", text="RMB Transform")

        layout.operator("rla.reset_keymap", icon='LOOP_BACK')


def register():
    bpy.utils.register_class(RLA_PT_sidebar)


def unregister():
    bpy.utils.unregister_class(RLA_PT_sidebar)
