# SPDX-License-Identifier: GPL-3.0-or-later
"""Viewport highlight for the last used axis.

Blender's transform gizmo is implemented in C, and Python cannot recolor an
individual handle of it. So instead of changing the gizmo, this module draws on
top of it.

The handler runs in ``POST_PIXEL`` rather than ``POST_VIEW`` for two reasons:
Blender draws 3D gizmos *between* those two callbacks, so ``POST_PIXEL`` is what
lands on top of the gizmo; and working in screen space means the highlight is
naturally the same pixel size as the gizmo, which is itself drawn at a constant
screen size.
"""

import math

import bpy
import gpu
from bpy_extras.view3d_utils import (
    location_3d_to_region_2d,
    region_2d_to_location_3d,
)
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Vector

from . import state
from .prefs import get_prefs

#: Gizmo radius in pixels is ``gizmo_size * ui_scale``: Blender scales the
#: transform gizmo so its handles end at that many pixels from the pivot.
GIZMO_RADIUS_FACTOR = 1.0

#: Plane handle extent, as a fraction of the gizmo radius. Measured against
#: Blender's own plane handles, which sit at roughly 0.4 of the radius.
PLANE_INNER = 0.28
PLANE_OUTER = 0.52

#: Radius of the "no axis constraint" marker, as a fraction of the gizmo radius.
CENTRE_RADIUS = 0.18

#: Radius of the view-aligned rotation ring, as a fraction of the gizmo radius.
VIEW_RING_RADIUS = 1.16

CIRCLE_SEGMENTS = 72

_handle = None
_shader_line = None
_shader_flat = None


# ---------------------------------------------------------------------------
# Drawing primitives (screen space, 2D)
# ---------------------------------------------------------------------------

def _shaders():
    global _shader_line, _shader_flat
    if _shader_line is None:
        _shader_line = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
        _shader_flat = gpu.shader.from_builtin('UNIFORM_COLOR')
    return _shader_line, _shader_flat


def _draw_polyline(region, points, color, width, loop=False):
    if len(points) < 2:
        return
    coords = [(p.x, p.y, 0.0) for p in points]
    if loop:
        coords.append(coords[0])
    shader, _ = _shaders()
    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": coords})
    shader.bind()
    shader.uniform_float("viewportSize", (region.width, region.height))
    shader.uniform_float("lineWidth", width)
    shader.uniform_float("color", color)
    batch.draw(shader)


def _draw_fan(points, color):
    if len(points) < 3:
        return
    coords = [(p.x, p.y, 0.0) for p in points]
    indices = [(0, i, i + 1) for i in range(1, len(coords) - 1)]
    _, shader = _shaders()
    batch = batch_for_shader(shader, 'TRIS', {"pos": coords}, indices=indices)
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def _circle_points(centre, radius, segments=CIRCLE_SEGMENTS):
    step = math.tau / segments
    return [
        centre + Vector((math.cos(i * step), math.sin(i * step))) * radius
        for i in range(segments)
    ]


# ---------------------------------------------------------------------------
# Scene queries
# ---------------------------------------------------------------------------

def _bbox_centre(points):
    lo = Vector(points[0])
    hi = Vector(points[0])
    for p in points:
        for axis in range(3):
            lo[axis] = min(lo[axis], p[axis])
            hi[axis] = max(hi[axis], p[axis])
    return (lo + hi) * 0.5


def _mean(points):
    total = Vector((0.0, 0.0, 0.0))
    for p in points:
        total += Vector(p)
    return total / len(points)


def _edit_mesh_pivot(context, obj, pivot_mode):
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
    if not bones:
        return None
    obj = context.active_object
    if obj is None:
        return None
    heads = [obj.matrix_world @ bone.matrix.translation for bone in bones]
    if pivot_mode == 'ACTIVE_ELEMENT':
        active = context.active_pose_bone
        if active is not None:
            return obj.matrix_world @ active.matrix.translation
    if pivot_mode == 'BOUNDING_BOX_CENTER':
        return _bbox_centre(heads)
    return _mean(heads)


def _pivot_world(context):
    """Where Blender draws the transform gizmo, in world space.

    Object mode, edit mesh and pose mode are computed properly; other edit modes
    fall back to the active object's origin.
    """
    scene = context.scene
    pivot_mode = scene.tool_settings.transform_pivot_point

    if pivot_mode == 'CURSOR':
        return scene.cursor.location.copy()

    obj = context.active_object
    mode = context.mode

    if mode == 'EDIT_MESH' and obj is not None:
        return _edit_mesh_pivot(context, obj, pivot_mode)

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


def _orientation_matrix(context, orient_type):
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
        # the object's own axes are the closest cheap approximation and match
        # exactly in object mode.
        if obj is not None:
            return obj.matrix_world.to_3x3().normalized()
        return Matrix.Identity(3)

    # A custom transform orientation, referenced by name.
    try:
        slot = context.scene.transform_orientation_slots[0]
        custom = slot.custom_orientation
        if custom is not None:
            return custom.matrix.copy()
    except (AttributeError, IndexError):
        pass
    return Matrix.Identity(3)


def _world_per_pixel(region, rv3d, location):
    """World units covered by one screen pixel at ``location``."""
    screen = location_3d_to_region_2d(region, rv3d, location)
    if screen is None:
        return None
    a = region_2d_to_location_3d(region, rv3d, screen, location)
    b = region_2d_to_location_3d(region, rv3d, screen + Vector((1.0, 0.0)), location)
    if a is None or b is None:
        return None
    return (b - a).length


def _towards_viewer(rv3d, pivot):
    """Unit vector from the pivot towards the viewer."""
    if rv3d.is_perspective:
        eye = rv3d.view_matrix.inverted().translation
        direction = eye - pivot
        if direction.length_squared > 0.0:
            return direction.normalized()
    return (rv3d.view_rotation @ Vector((0.0, 0.0, 1.0))).normalized()


# ---------------------------------------------------------------------------
# Highlight shapes
# ---------------------------------------------------------------------------

def _draw_axis_line(region, rv3d, pivot, direction, length, color, width):
    tip = location_3d_to_region_2d(region, rv3d, pivot + direction * length)
    root = location_3d_to_region_2d(region, rv3d, pivot)
    if tip is None or root is None:
        return
    _draw_polyline(region, [root, tip], color, width)


def _draw_plane(region, rv3d, pivot, u, v, length, color, width):
    # Blender draws every plane handle in the positive quadrant of its two axes
    # and does not flip it towards the viewer, so neither do we -- measured
    # against the native handles, which is what this has to sit on top of.
    inner, outer = PLANE_INNER * length, PLANE_OUTER * length

    corners_3d = [
        pivot + u * a + v * b
        for a, b in ((inner, inner), (outer, inner), (outer, outer), (inner, outer))
    ]
    corners = [location_3d_to_region_2d(region, rv3d, c) for c in corners_3d]
    if any(c is None for c in corners):
        return
    _draw_fan(corners, (color[0], color[1], color[2], color[3] * 0.35))
    _draw_polyline(region, corners, color, width, loop=True)


def _draw_dial(region, rv3d, pivot, normal, e1, e2, length, color, width):
    """A rotation dial, clipped to the half facing the viewer like Blender's."""
    view = _towards_viewer(rv3d, pivot)
    step = math.tau / CIRCLE_SEGMENTS

    runs = []
    current = []
    for i in range(CIRCLE_SEGMENTS + 1):
        angle = i * step
        offset = e1 * math.cos(angle) + e2 * math.sin(angle)
        point_3d = pivot + offset * length
        if offset.dot(view) >= 0.0:
            screen = location_3d_to_region_2d(region, rv3d, point_3d)
            if screen is not None:
                current.append(screen)
                continue
        if current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)

    # A dial seen edge-on degenerates into a line; drawing it is still correct.
    for run in runs:
        _draw_polyline(region, run, color, width)


def _draw_screen_circle(region, centre, radius, color, width):
    _draw_polyline(region, _circle_points(centre, radius), color, width, loop=True)


def _draw_centre(region, centre, radius, color, width):
    points = _circle_points(centre, radius, 32)
    _draw_fan(points, (color[0], color[1], color[2], color[3] * 0.35))
    _draw_polyline(region, points, color, width, loop=True)


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

def _draw_highlight(context, p):
    last = state.LAST
    region = context.region
    rv3d = context.region_data
    if region is None or rv3d is None:
        return

    pivot = _pivot_world(context)
    if pivot is None:
        return

    centre = location_3d_to_region_2d(region, rv3d, pivot)
    if centre is None:
        return

    world_per_pixel = _world_per_pixel(region, rv3d, pivot)
    if not world_per_pixel:
        return

    ui_scale = context.preferences.system.ui_scale or 1.0
    radius_px = (
        context.preferences.view.gizmo_size
        * ui_scale
        * GIZMO_RADIUS_FACTOR
        * p.highlight_scale
    )
    length = radius_px * world_per_pixel

    matrix = _orientation_matrix(context, last.orient_type)
    axes = [matrix.col[i].normalized() for i in range(3)]

    color = (p.highlight_color[0], p.highlight_color[1], p.highlight_color[2],
             p.highlight_alpha)
    width = p.highlight_width

    gpu.state.blend_set('ALPHA')
    gpu.state.depth_test_set('NONE')
    try:
        if last.kind == state.TRACKBALL:
            _draw_screen_circle(region, centre, radius_px, color, width)
            return

        if last.kind == state.ROTATE:
            index = last.rotate_axis_index
            if index is None:
                _draw_screen_circle(
                    region, centre, radius_px * VIEW_RING_RADIUS, color, width
                )
            else:
                _draw_dial(
                    region, rv3d, pivot,
                    axes[index],
                    axes[(index + 1) % 3],
                    axes[(index + 2) % 3],
                    length, color, width,
                )
            return

        # Move and scale.
        indices = last.axis_indices
        if len(indices) == 1:
            _draw_axis_line(
                region, rv3d, pivot, axes[indices[0]], length, color, width
            )
        elif len(indices) == 2:
            _draw_plane(
                region, rv3d, pivot,
                axes[indices[0]], axes[indices[1]],
                length, color, width,
            )
        else:
            _draw_centre(region, centre, radius_px * CENTRE_RADIUS, color, width)
    finally:
        gpu.state.blend_set('NONE')


def _draw_callback():
    # Refresh the tracked axis first: this callback runs on every viewport
    # redraw, which is the closest thing Blender offers to an "operator
    # finished" notification.
    changed = state.capture()

    context = bpy.context
    p = get_prefs(context)
    if p is None or not p.show_highlight or not state.LAST.valid:
        return

    space = context.space_data
    if space is None or space.type != 'VIEW_3D':
        return
    if p.highlight_requires_gizmo and not space.show_gizmo:
        return

    try:
        _draw_highlight(context, p)
    except Exception:
        # A draw handler that raises spams the console every frame; report once
        # and disable the highlight rather than leave the viewport unusable.
        import traceback
        traceback.print_exc()
        p.show_highlight = False
    del changed


def register():
    global _handle
    if bpy.app.background or _handle is not None:
        return
    _handle = bpy.types.SpaceView3D.draw_handler_add(
        _draw_callback, (), 'WINDOW', 'POST_PIXEL'
    )


def unregister():
    global _handle, _shader_line, _shader_flat
    if _handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_handle, 'WINDOW')
        _handle = None
    _shader_line = None
    _shader_flat = None
