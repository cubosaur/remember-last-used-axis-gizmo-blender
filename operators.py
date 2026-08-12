# SPDX-License-Identifier: GPL-3.0-or-later
"""Operators."""

import bpy
from bpy.types import Operator

from . import state
from .prefs import get_prefs

#: Active tool identifiers mapped to a transform kind.
_TOOL_KINDS = {
    "builtin.move": state.TRANSLATE,
    "builtin.rotate": state.ROTATE,
    "builtin.scale": state.RESIZE,
    "builtin.scale_cage": state.RESIZE,
}


def _active_tool_kind(context):
    try:
        tool = context.workspace.tools.from_space_view3d_mode(
            context.mode, create=False
        )
    except Exception:
        return None
    if tool is None:
        return None
    return _TOOL_KINDS.get(tool.idname)


def has_transform_target(context):
    """Whether there is anything for a transform to act on."""
    if context.mode == 'OBJECT':
        return bool(context.selected_objects)
    return context.active_object is not None


class MGB_OT_transform_last_axis(Operator):
    """Transform along the last used gizmo axis, driven by the mouse drag"""

    bl_idname = "mgb.transform_last_axis"
    bl_label = "Transform Along Last Used Axis"
    # Deliberately no REGISTER/UNDO: the nested transform operator registers
    # itself, so it is the transform (not this wrapper) that appears in the redo
    # panel -- which is also what the axis tracking reads back.
    bl_options = set()

    @classmethod
    def poll(cls, context):
        return context.space_data and context.space_data.type == 'VIEW_3D'

    def invoke(self, context, event):
        p = get_prefs(context)
        if p is None:
            return {'PASS_THROUGH'}

        last = state.LAST
        kind = None
        if p.transform_source == 'ACTIVE_TOOL':
            kind = _active_tool_kind(context)
        if kind is None:
            kind = last.kind if last.valid else None

        if kind is None or not has_transform_target(context):
            # Nothing to transform, so hand the drag back to Blender rather
            # than swallowing it.
            return {'PASS_THROUGH'}

        return self._run_transform(context, kind, last)

    def _run_transform(self, context, kind, last):
        op = getattr(bpy.ops.transform, state.KIND_OPERATORS[kind])

        kwargs = {
            # Confirms the transform when the button that launched it is
            # released, which is what makes press-drag-release feel like Maya.
            "release_confirm": True,
        }
        if last.valid and any(last.constraint_axis):
            kwargs["constraint_axis"] = last.constraint_axis
            kwargs["orient_type"] = last.orient_type
            kwargs["orient_axis"] = last.orient_axis

        # transform.trackball has no constraint properties, and orient_axis only
        # exists on transform.rotate -- drop anything this operator lacks.
        try:
            available = op.get_rna_type().properties.keys()
            kwargs = {k: v for k, v in kwargs.items() if k in available}
        except Exception:
            kwargs = {}

        try:
            op('INVOKE_DEFAULT', **kwargs)
        except (RuntimeError, TypeError) as ex:
            self.report({'WARNING'}, "Transform failed: %s" % ex)
            return {'CANCELLED'}
        return {'FINISHED'}


class MGB_OT_clear_last_axis(Operator):
    """Forget the last used axis"""

    bl_idname = "mgb.clear_last_axis"
    bl_label = "Clear Last Used Axis"
    bl_options = {'REGISTER'}

    def execute(self, context):
        state.LAST.reset()
        _tag_redraw(context)
        return {'FINISHED'}


class MGB_OT_reset_keymap(Operator):
    """Undo every keymap change this addon made and restore your previous keys"""

    bl_idname = "mgb.reset_keymap"
    bl_label = "Reset Hotkeys"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from . import keymaps

        restored = keymaps.revert(context, clear_backup=True)
        # Forced: pressing this button is an explicit ask to be given the
        # default navigation back, whether or not the one-off repair already ran.
        repaired = keymaps.repair_legacy_mmb(context, force=True)

        if not restored and not repaired:
            self.report({'INFO'}, "Nothing to reset -- no keymap changes on record")
        else:
            parts = []
            if restored:
                parts.append("%d entr%s restored" % (restored, "y" if restored == 1 else "ies"))
            if repaired:
                parts.append("middle mouse navigation re-enabled")
            self.report({'INFO'}, "Hotkeys reset -- " + ", ".join(parts))
        return {'FINISHED'}


class MGB_OT_apply_keymap(Operator):
    """Re-apply this addon's keymap"""

    bl_idname = "mgb.apply_keymap"
    bl_label = "Apply Hotkeys"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from . import keymaps

        if keymaps.apply(context):
            self.report({'INFO'}, "Hotkeys applied")
            return {'FINISHED'}
        self.report({'WARNING'}, "Could not apply hotkeys")
        return {'CANCELLED'}


class MGB_OT_restore_blender_defaults(Operator):
    """Reset the affected keymaps to Blender's factory defaults.

    This also discards your own customisations in those keymaps
    """

    bl_idname = "mgb.restore_blender_defaults"
    bl_label = "Restore Blender Default Keymaps"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        from . import keymaps

        count = keymaps.restore_blender_defaults(context)
        self.report({'INFO'}, "Restored %d keymap(s) to Blender defaults" % count)
        return {'FINISHED'}


def _tag_redraw(context):
    for area in getattr(context.screen, "areas", ()):
        if area.type == 'VIEW_3D':
            area.tag_redraw()


_CLASSES = (
    MGB_OT_transform_last_axis,
    MGB_OT_clear_last_axis,
    MGB_OT_reset_keymap,
    MGB_OT_apply_keymap,
    MGB_OT_restore_blender_defaults,
)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
