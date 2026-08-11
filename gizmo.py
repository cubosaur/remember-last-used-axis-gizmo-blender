# SPDX-License-Identifier: GPL-3.0-or-later
"""The last-used-axis gizmo.

A single yellow puck parked just beyond the tip of Blender's transform gizmo,
pointing along the axis that will be reused. Clicking or dragging it runs the
same transform that a middle mouse drag does.

This is a real ``GizmoGroup`` rather than a GPU overlay, which is what makes it
clickable, gives it a hover highlight, and lets it hide itself while a transform
is in flight the way Blender's own gizmos do.
"""

import bpy
from bpy.types import Gizmo, GizmoGroup
from mathutils import Matrix, Vector
from bpy_extras.view3d_utils import (
    location_3d_to_region_2d,
    region_2d_to_location_3d,
)

from . import state
from .operators import has_transform_target
from .prefs import get_prefs

#: Where the puck sits, as a multiple of the gizmo radius. Blender's axis tips
#: land at 1.0 and the outermost ring at about 1.15, so this clears both.
PUCK_DISTANCE = 1.3

#: Puck radius as a fraction of the gizmo radius, and a floor in pixels so it
#: stays comfortably clickable when the gizmo is small.
PUCK_RADIUS_FRACTION = 0.13
PUCK_RADIUS_MIN_PX = 8.0

#: Screen-space direction used when the transform has no axis constraint
#: (uniform scale, screen-space move, view-axis rotation).
_SCREEN_DIAGONAL = Vector((0.7071, 0.7071, 0.0))


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
    """Where Blender draws the transform gizmo, in world space.

    Object Mode, Edit Mode (mesh) and Pose Mode are computed properly; other
    edit modes fall back to the active object's origin.
    """
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
    # Median point, and individual origins (whose gizmo also sits at the median).
    return _mean([o.matrix_world.translation for o in selected])


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
        # NORMAL and GIMBAL depend on the selection, which we do not replicate;
        # the object's own axes match exactly in Object Mode and are the closest
        # cheap approximation elsewhere.
        if obj is not None:
            return obj.matrix_world.to_3x3().normalized()
    return Matrix.Identity(3)


def _world_per_pixel(region, rv3d, location):
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


def puck_direction(context, last):
    """Unit world direction the puck is parked along."""
    matrix = orientation_matrix(context, last.orient_type)

    if last.kind == state.ROTATE:
        index = last.rotate_axis_index
        if index is not None:
            return matrix.col[index].normalized()
    else:
        indices = last.axis_indices
        if len(indices) == 1:
            return matrix.col[indices[0]].normalized()
        if len(indices) == 2:
            # Park on the diagonal between the two axes of the plane.
            combined = (
                matrix.col[indices[0]].normalized()
                + matrix.col[indices[1]].normalized()
            )
            if combined.length > 1e-6:
                return combined.normalized()

    # No axis constraint: pin it to a fixed screen-space diagonal so it stays
    # somewhere predictable rather than jumping about with the view.
    rv3d = context.region_data
    if rv3d is not None:
        return (rv3d.view_rotation @ _SCREEN_DIAGONAL).normalized()
    return Vector((1.0, 0.0, 0.0))


def transform_in_progress(context):
    """True while a transform modal operator is running.

    Covers dragging a native gizmo handle, the G/R/S shortcuts and this addon's
    own middle mouse drag, since all three run a ``TRANSFORM_OT_*`` modal.
    """
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


# ---------------------------------------------------------------------------
# Gizmo
# ---------------------------------------------------------------------------

class MGB_GT_puck(Gizmo):
    """A circle that reruns the last used transform when clicked or dragged."""

    bl_idname = "MGB_GT_puck"
    bl_target_properties = ()

    #: Screen radius in pixels, refreshed by the group. Hit testing uses it
    #: instead of the drawn geometry, so the whole disc is clickable rather
    #: than just the thin ring.
    __slots__ = ("radius_px",)

    def setup(self):
        self.radius_px = 12.0

    def draw(self, context):
        self.draw_preset_circle(self.matrix_world, axis='POS_Z')

    # Deliberately no draw_select(): defining it makes Blender select via the
    # drawn geometry and ignore test_select entirely, which would mean only the
    # thin ring itself were clickable and not the disc inside it.
    def test_select(self, context, location):
        region = context.region
        rv3d = context.region_data
        if region is None or rv3d is None:
            return -1
        centre = location_3d_to_region_2d(
            region, rv3d, self.matrix_world.translation
        )
        if centre is None:
            return -1
        if (Vector(location) - centre).length <= max(self.radius_px, 8.0):
            return 0
        return -1


class MGB_GGT_last_axis(GizmoGroup):
    bl_idname = "MGB_GGT_last_axis"
    bl_label = "Last Used Axis"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    # No 'SCALE': the puck's screen size is baked into its matrix instead, so a
    # pixel radius means exactly that rather than depending on how Blender
    # happens to map scale_basis to screen space.
    # EXCLUDE_MODAL hides it while any gizmo is being dragged.
    bl_options = {'3D', 'PERSISTENT', 'EXCLUDE_MODAL'}

    @classmethod
    def poll(cls, context):
        p = get_prefs(context)
        if p is None or not p.show_highlight or not state.LAST.valid:
            return False
        space = context.space_data
        if space is None or space.type != 'VIEW_3D':
            return False
        if p.highlight_requires_gizmo and not space.show_gizmo:
            return False
        # Hide while transforming, so the puck does not chase the selection
        # around mid-drag. Blender's own gizmos behave the same way.
        if transform_in_progress(context):
            return False
        return has_transform_target(context)

    def setup(self, context):
        gz = self.gizmos.new(MGB_GT_puck.bl_idname)
        gz.target_set_operator("mgb.transform_last_axis")
        gz.use_draw_modal = False
        gz.use_select_background = True
        gz.use_tooltip = True
        self.puck = gz

    def refresh(self, context):
        self._place(context)

    def draw_prepare(self, context):
        # The position depends on the view (it is a screen-space offset from the
        # pivot), so it has to be recomputed every redraw, not just on refresh.
        self._place(context)

    def _place(self, context):
        gz = self.puck
        p = get_prefs(context)
        region = context.region
        rv3d = context.region_data
        if p is None or region is None or rv3d is None:
            gz.hide = True
            return

        pivot = pivot_world(context)
        if pivot is None:
            gz.hide = True
            return

        world_per_pixel = _world_per_pixel(region, rv3d, pivot)
        if not world_per_pixel:
            gz.hide = True
            return

        ui_scale = context.preferences.system.ui_scale or 1.0
        radius_px = context.preferences.view.gizmo_size * ui_scale
        offset = radius_px * PUCK_DISTANCE * world_per_pixel

        direction = puck_direction(context, state.LAST)
        position = pivot + direction * offset

        puck_px = max(
            radius_px * PUCK_RADIUS_FRACTION * p.highlight_scale,
            PUCK_RADIUS_MIN_PX,
        )
        # Rotate to face the viewer (otherwise the circle lies flat in the world
        # XY plane) and bake the radius into the matrix, so the circle that
        # draw_preset_circle draws at radius 1.0 lands at exactly puck_px pixels.
        gz.matrix_basis = (
            Matrix.Translation(position)
            @ rv3d.view_rotation.to_matrix().to_4x4()
            @ Matrix.Scale(puck_px * world_per_pixel, 4)
        )
        gz.scale_basis = 1.0
        gz.radius_px = puck_px
        gz.line_width = 3.0
        gz.color = tuple(p.highlight_color)
        gz.alpha = p.highlight_alpha
        gz.color_highlight = tuple(min(1.0, c + 0.25) for c in p.highlight_color)
        gz.alpha_highlight = min(1.0, p.highlight_alpha + 0.2)
        gz.hide = False


_CLASSES = (
    MGB_GT_puck,
    MGB_GGT_last_axis,
)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
