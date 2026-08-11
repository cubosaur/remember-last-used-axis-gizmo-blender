# SPDX-License-Identifier: GPL-3.0-or-later
"""A transform gizmo whose last used handle is drawn in yellow.

Blender's own transform gizmo is C code, and Python cannot recolour one of its
handles. Recolouring through the theme does not work either: the transform
gizmo takes its axis colours from ``theme.user_interface.axis_x/y/z``, which
also drive the viewport floor grid lines and the navigation gizmo, so turning
"X" yellow turns the entire X grid line yellow as well.

So this module rebuilds the move / rotate / scale gizmos out of Blender's own
built-in gizmo *types* -- the same arrow, dial, plane and ring primitives the
native one is made of -- and suppresses the native group with
``gizmo_group_type_unlink_delayed``. Every handle keeps its usual axis colour
except the last used one, which is yellow. Dragging a handle runs the same
transform operator the native gizmo runs, so it behaves the same.

The native group is restored on unregister, so disabling the addon brings the
stock gizmo straight back.
"""

import bpy
from bpy.types import GizmoGroup
from bpy_extras.view3d_utils import (
    location_3d_to_region_2d,
    region_2d_to_location_3d,
)
from mathutils import Matrix, Vector

from . import state
from .operators import has_transform_target
from .prefs import get_prefs

#: The native transform gizmo group, suppressed while this addon is enabled.
NATIVE_GIZMO_GROUP = "VIEW3D_GGT_xform_gizmo"

#: (mode, tool) the native gizmo was last suppressed for. Blender re-links the
#: group whenever a tool is activated, so this has to be redone on each change.
_suppressed_for = None

#: Handle sizes, in gizmo units. Measured against the native gizmo on screen:
#: each primitive type has its own scale convention, so these are calibrated
#: rather than derived.
AXIS_SCALE = 0.41
PLANE_SCALE = 0.028
PLANE_OFFSET = 0.42
CENTRE_SCALE = 0.11
DIAL_SCALE = 0.41
VIEW_DIAL_SCALE = 0.47

ALPHA = 0.7
ALPHA_HIGHLIGHT = 1.0

AXIS_NAMES = ('X', 'Y', 'Z')

#: (u, v, normal) for the XY, YZ and ZX plane handles. Blender colours a plane
#: handle by the axis it is perpendicular to.
PLANES = ((0, 1, 2), (1, 2, 0), (2, 0, 1))


# ---------------------------------------------------------------------------
# Scene queries
# ---------------------------------------------------------------------------

def _bbox_centre(points):
    lo = Vector(points[0])
    hi = Vector(points[0])
    for point in points:
        for axis in range(3):
            lo[axis] = min(lo[axis], point[axis])
            hi[axis] = max(hi[axis], point[axis])
    return (lo + hi) * 0.5


def _mean(points):
    total = Vector((0.0, 0.0, 0.0))
    for point in points:
        total += Vector(point)
    return total / len(points)


def _edit_mesh_pivot(obj, pivot_mode):
    import bmesh

    try:
        bm = bmesh.from_edit_mesh(obj.data)
    except Exception:
        return None
    matrix = obj.matrix_world

    if pivot_mode == 'ACTIVE_ELEMENT':
        active = bm.select_history.active
        if active is not None:
            if hasattr(active, "co"):
                return matrix @ active.co.copy()
            if hasattr(active, "verts"):
                return matrix @ _mean([v.co for v in active.verts])

    selected = [v.co for v in bm.verts if v.select]
    if not selected:
        return None
    if pivot_mode == 'BOUNDING_BOX_CENTER':
        return matrix @ _bbox_centre(selected)
    return matrix @ _mean(selected)


def _pose_pivot(context, pivot_mode):
    bones = context.selected_pose_bones
    obj = context.active_object
    if not bones or obj is None:
        return None
    if pivot_mode == 'ACTIVE_ELEMENT':
        active = context.active_pose_bone
        if active is not None:
            return obj.matrix_world @ active.matrix.translation
    heads = [obj.matrix_world @ bone.matrix.translation for bone in bones]
    if pivot_mode == 'BOUNDING_BOX_CENTER':
        return _bbox_centre(heads)
    return _mean(heads)


def pivot_world(context):
    """Where Blender draws the transform gizmo, in world space."""
    scene = context.scene
    pivot_mode = scene.tool_settings.transform_pivot_point

    if pivot_mode == 'CURSOR':
        return scene.cursor.location.copy()

    obj = context.active_object
    mode = context.mode

    if mode == 'EDIT_MESH' and obj is not None:
        return _edit_mesh_pivot(obj, pivot_mode)
    if mode == 'POSE':
        return _pose_pivot(context, pivot_mode)
    if mode != 'OBJECT':
        return obj.matrix_world.translation.copy() if obj else None

    selected = list(context.selected_objects)
    if not selected:
        return None
    if pivot_mode == 'ACTIVE_ELEMENT' and obj is not None:
        return obj.matrix_world.translation.copy()
    if pivot_mode == 'BOUNDING_BOX_CENTER':
        corners = [
            o.matrix_world @ Vector(corner)
            for o in selected
            for corner in o.bound_box
        ]
        return _bbox_centre(corners)
    return _mean([o.matrix_world.translation for o in selected])


def scene_orient_type(context):
    try:
        return context.scene.transform_orientation_slots[0].type
    except (AttributeError, IndexError):
        return 'GLOBAL'


def orientation_matrix(context, orient_type):
    """3x3 matrix whose columns are the axes of the given orientation."""
    if orient_type == 'GLOBAL':
        return Matrix.Identity(3)

    obj = context.active_object

    if orient_type == 'VIEW':
        rv3d = context.region_data
        if rv3d is not None:
            return rv3d.view_matrix.to_3x3().inverted()
        return Matrix.Identity(3)

    if orient_type == 'CURSOR':
        return context.scene.cursor.matrix.to_3x3().normalized()

    if orient_type == 'PARENT':
        if obj is not None and obj.parent is not None:
            return obj.parent.matrix_world.to_3x3().normalized()
        orient_type = 'LOCAL'

    if orient_type in {'LOCAL', 'NORMAL', 'GIMBAL'}:
        if obj is not None:
            return obj.matrix_world.to_3x3().normalized()
        return Matrix.Identity(3)

    try:
        custom = context.scene.transform_orientation_slots[0].custom_orientation
        if custom is not None:
            return custom.matrix.copy()
    except (AttributeError, IndexError):
        pass
    return Matrix.Identity(3)


def world_per_pixel(region, rv3d, location):
    """World units covered by one screen pixel at ``location``."""
    screen = location_3d_to_region_2d(region, rv3d, location)
    if screen is None:
        return None
    near = region_2d_to_location_3d(region, rv3d, screen, location)
    far = region_2d_to_location_3d(
        region, rv3d, screen + Vector((1.0, 0.0)), location
    )
    if near is None or far is None:
        return None
    return (far - near).length


def transform_in_progress(context):
    """True while a ``TRANSFORM_OT_*`` modal operator is running."""
    window = context.window
    if window is None:
        return False
    try:
        running = window.modal_operators
    except AttributeError:
        return False
    for op in running:
        if op.bl_idname.startswith("TRANSFORM_OT_"):
            return True
    return False


def current_tool(context):
    try:
        tool = context.workspace.tools.from_space_view3d_mode(
            context.mode, create=False
        )
    except Exception:
        return None
    return getattr(tool, "idname", None)


def active_modes(context):
    """Which of translate/rotate/scale gizmos Blender would be showing."""
    space = context.space_data
    modes = set()
    if space is None or not space.show_gizmo:
        return modes

    if space.show_gizmo_object_translate:
        modes.add(state.TRANSLATE)
    if space.show_gizmo_object_rotate:
        modes.add(state.ROTATE)
    if space.show_gizmo_object_scale:
        modes.add(state.RESIZE)

    if space.show_gizmo_tool:
        try:
            tool = context.workspace.tools.from_space_view3d_mode(
                context.mode, create=False
            )
        except Exception:
            tool = None
        idname = getattr(tool, "idname", None)
        if idname == "builtin.move":
            modes.add(state.TRANSLATE)
        elif idname == "builtin.rotate":
            modes.add(state.ROTATE)
        elif idname in {"builtin.scale", "builtin.scale_cage"}:
            modes.add(state.RESIZE)
        elif idname == "builtin.transform":
            modes |= {state.TRANSLATE, state.ROTATE, state.RESIZE}
    return modes


def axis_colors(context):
    theme = context.preferences.themes[0].user_interface
    return (
        tuple(theme.axis_x)[:3],
        tuple(theme.axis_y)[:3],
        tuple(theme.axis_z)[:3],
    )


def last_used_key():
    """Key of the handle to draw yellow, matching the handle dictionary."""
    last = state.LAST
    if not last.valid:
        return None

    if last.kind == state.ROTATE:
        index = last.rotate_axis_index
        if index is None:
            return (state.ROTATE, 'view', 0)
        return (state.ROTATE, 'dial', index)

    if last.kind not in {state.TRANSLATE, state.RESIZE}:
        return None

    indices = last.axis_indices
    if len(indices) == 1:
        return (last.kind, 'axis', indices[0])
    if len(indices) == 2:
        for slot, (u, v, _normal) in enumerate(PLANES):
            if {u, v} == set(indices):
                return (last.kind, 'plane', slot)
    return (last.kind, 'centre', 0)


def _aim(direction):
    """Rotation placing a gizmo's local +Z along ``direction``."""
    return direction.to_track_quat('Z', 'Y').to_matrix().to_4x4()


# ---------------------------------------------------------------------------
# Gizmo group
# ---------------------------------------------------------------------------

class MGB_GGT_transform(GizmoGroup):
    bl_idname = "MGB_GGT_transform"
    bl_label = "Transform (Last Used Axis)"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    # SCALE keeps handles a constant size on screen, as the native gizmo does.
    # EXCLUDE_MODAL hides the whole set while one handle is being dragged.
    bl_options = {'3D', 'PERSISTENT', 'SCALE', 'EXCLUDE_MODAL'}

    @classmethod
    def poll(cls, context):
        # Activating a tool re-links its gizmo group, so the native transform
        # gizmo comes back every time the tool or mode changes and has to be
        # suppressed again. Keyed so this costs one comparison per poll.
        p = get_prefs(context)
        if p is None or not p.show_highlight:
            return False

        global _suppressed_for
        stamp = (context.mode, current_tool(context))
        if stamp != _suppressed_for:
            _suppressed_for = stamp
            _suppress_native()

        space = context.space_data
        if space is None or space.type != 'VIEW_3D':
            return False
        if not active_modes(context):
            return False
        return has_transform_target(context)

    # -- construction ------------------------------------------------------

    def setup(self, context):
        #: key -> gizmo, and key -> (operator properties, fixed orientation)
        self.handles = {}
        self.bindings = {}

        for kind, style in ((state.TRANSLATE, 'NORMAL'), (state.RESIZE, 'BOX')):
            operator = (
                "transform.translate" if kind == state.TRANSLATE
                else "transform.resize"
            )
            for index in range(3):
                gz = self.gizmos.new("GIZMO_GT_arrow_3d")
                gz.draw_style = style
                gz.draw_options = {'STEM'}
                gz.length = 1.0
                constraint = [False, False, False]
                constraint[index] = True
                self._add(gz, (kind, 'axis', index), operator, tuple(constraint))

            for slot, (u, v, _normal) in enumerate(PLANES):
                gz = self.gizmos.new("GIZMO_GT_primitive_3d")
                gz.draw_style = 'PLANE'
                constraint = [False, False, False]
                constraint[u] = constraint[v] = True
                self._add(gz, (kind, 'plane', slot), operator, tuple(constraint))

            gz = self.gizmos.new("GIZMO_GT_move_3d")
            gz.draw_style = 'RING_2D'
            self._add(gz, (kind, 'centre', 0), operator, None)

        for index in range(3):
            gz = self.gizmos.new("GIZMO_GT_dial_3d")
            gz.draw_options = {'CLIP'}
            constraint = [False, False, False]
            constraint[index] = True
            props = self._add(
                gz, (state.ROTATE, 'dial', index), "transform.rotate",
                tuple(constraint),
            )
            if props is not None:
                try:
                    props.orient_axis = AXIS_NAMES[index]
                except Exception:
                    pass

        gz = self.gizmos.new("GIZMO_GT_dial_3d")
        gz.draw_options = {'CLIP'}
        self._add(
            gz, (state.ROTATE, 'view', 0), "transform.rotate", None,
            orient_type='VIEW',
        )

        for gz in self.gizmos:
            gz.use_draw_modal = False

    def _add(self, gz, key, operator, constraint, orient_type=None):
        """Register a handle and attach the transform operator it runs."""
        self.handles[key] = gz
        props = None
        try:
            props = gz.target_set_operator(operator)
            props.release_confirm = True
            if constraint is not None:
                props.constraint_axis = constraint
            if orient_type is not None:
                props.orient_type = orient_type
        except Exception:
            import traceback
            traceback.print_exc()
        self.bindings[key] = (props, orient_type)
        return props

    # -- placement ---------------------------------------------------------

    def refresh(self, context):
        self._place(context)

    def draw_prepare(self, context):
        # Handle positions depend on the view, so they are recomputed on every
        # redraw rather than only when the scene changes.
        self._place(context)

    def _place(self, context):
        p = get_prefs(context)
        region = context.region
        rv3d = context.region_data
        if p is None or region is None or rv3d is None:
            self._hide_all()
            return

        pivot = pivot_world(context)
        if pivot is None:
            self._hide_all()
            return
        unit = world_per_pixel(region, rv3d, pivot)
        if not unit:
            self._hide_all()
            return

        orient_type = scene_orient_type(context)
        self._sync_orient(orient_type)

        matrix = orientation_matrix(context, orient_type)
        axes = [matrix.col[i].normalized() for i in range(3)]
        colors = axis_colors(context)

        radius = context.preferences.view.gizmo_size * (
            context.preferences.system.ui_scale or 1.0
        ) * unit

        modes = active_modes(context)
        # Hide everything mid-transform, unless one of our own handles is
        # driving it -- hiding a gizmo that is mid-drag is not safe.
        freeze = transform_in_progress(context) and not any(
            gz.is_modal for gz in self.gizmos
        )
        highlight = last_used_key()
        yellow = tuple(p.highlight_color)
        translation = Matrix.Translation(pivot)
        view_rotation = rv3d.view_rotation.to_matrix().to_4x4()

        for key, gz in self.handles.items():
            kind, role, index = key
            if freeze or kind not in modes:
                gz.hide = True
                continue
            gz.hide = False

            if role == 'axis':
                gz.matrix_basis = translation @ _aim(axes[index])
                gz.scale_basis = AXIS_SCALE
                base = colors[index]
            elif role == 'plane':
                u, v, normal = PLANES[index]
                offset = (axes[u] + axes[v]) * (PLANE_OFFSET * radius)
                gz.matrix_basis = (
                    Matrix.Translation(pivot + offset) @ _aim(axes[normal])
                )
                gz.scale_basis = PLANE_SCALE
                base = colors[normal]
            elif role == 'dial':
                gz.matrix_basis = translation @ _aim(axes[index])
                gz.scale_basis = DIAL_SCALE
                base = colors[index]
            elif role == 'view':
                gz.matrix_basis = translation @ view_rotation
                gz.scale_basis = VIEW_DIAL_SCALE
                base = (1.0, 1.0, 1.0)
            else:  # centre
                gz.matrix_basis = translation @ view_rotation
                gz.scale_basis = CENTRE_SCALE
                base = (1.0, 1.0, 1.0)

            is_last = key == highlight
            gz.color = yellow if is_last else base
            gz.color_highlight = yellow if is_last else (1.0, 1.0, 1.0)
            gz.alpha = p.highlight_alpha if is_last else ALPHA
            gz.alpha_highlight = ALPHA_HIGHLIGHT

    def _hide_all(self):
        for gz in self.gizmos:
            gz.hide = True

    def _sync_orient(self, orient_type):
        """Keep handles running whatever orientation the scene is set to."""
        for props, fixed in self.bindings.values():
            if props is None or fixed is not None:
                continue
            try:
                props.orient_type = orient_type
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def _suppress_native():
    try:
        bpy.types.WindowManager.gizmo_group_type_unlink_delayed(
            NATIVE_GIZMO_GROUP
        )
    except Exception:
        import traceback
        traceback.print_exc()


def _restore_native():
    try:
        bpy.types.WindowManager.gizmo_group_type_ensure(NATIVE_GIZMO_GROUP)
    except Exception:
        import traceback
        traceback.print_exc()


def set_enabled(enabled):
    """Swap between our gizmo and Blender's stock one.

    Turning the highlight off has to hand the native gizmo back rather than
    simply hiding ours, otherwise the viewport would be left with no transform
    gizmo at all.
    """
    global _suppressed_for
    if bpy.app.background:
        return
    _suppressed_for = None
    if enabled:
        _suppress_native()
    else:
        _restore_native()


@bpy.app.handlers.persistent
def _on_load(_dummy):
    # Loading a file rebuilds the tools, which re-links the native group.
    global _suppressed_for
    _suppressed_for = None


def register():
    global _suppressed_for
    bpy.utils.register_class(MGB_GGT_transform)
    if bpy.app.background:
        return
    _suppressed_for = None
    _suppress_native()
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)


def unregister():
    global _suppressed_for
    if _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    # Give the stock transform gizmo back first, so a later failure cannot
    # leave the viewport without a transform gizmo at all.
    if not bpy.app.background:
        _restore_native()
    _suppressed_for = None
    bpy.utils.unregister_class(MGB_GGT_transform)
