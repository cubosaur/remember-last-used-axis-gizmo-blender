# SPDX-License-Identifier: GPL-3.0-or-later
"""Tracking of the last used transform axis.

Blender's transform gizmo is C code with no Python-visible "handle was
dragged" callback, so instead of hooking the gizmo we read the result: every
completed transform lands in ``wm.operators`` (the same data the F9 redo panel
shows), including transforms started by dragging a gizmo handle.

That means one capture path covers everything the user might do:

* dragging the X arrow of the move gizmo,
* dragging the XY plane handle,
* typing ``G`` ``X`` or ``S`` ``Shift+Z`` on the keyboard,

all of which produce a transform operator carrying ``constraint_axis`` and
``orient_type``.
"""

import bpy

TRANSLATE = 'TRANSLATE'
ROTATE = 'ROTATE'
RESIZE = 'RESIZE'
TRACKBALL = 'TRACKBALL'

#: Operator identifiers mapped to our transform kind. Both the ``CLASS_OT_name``
#: and ``class.name`` spellings are accepted so we do not depend on which one
#: ``Operator.bl_idname`` happens to return.
OP_KINDS = {
    "TRANSFORM_OT_translate": TRANSLATE,
    "TRANSFORM_OT_rotate": ROTATE,
    "TRANSFORM_OT_resize": RESIZE,
    "TRANSFORM_OT_trackball": TRACKBALL,
    "transform.translate": TRANSLATE,
    "transform.rotate": ROTATE,
    "transform.resize": RESIZE,
    "transform.trackball": TRACKBALL,
}

#: The operator each kind is replayed through.
KIND_OPERATORS = {
    TRANSLATE: "translate",
    ROTATE: "rotate",
    RESIZE: "resize",
    TRACKBALL: "trackball",
}

LABELS = {
    TRANSLATE: "Move",
    ROTATE: "Rotate",
    RESIZE: "Scale",
    TRACKBALL: "Trackball",
}

_AXIS_INDEX = {'X': 0, 'Y': 1, 'Z': 2}


class LastAxis:
    """The most recent transform kind + axis constraint the user performed."""

    __slots__ = ("kind", "constraint_axis", "orient_type", "orient_axis")

    def __init__(self):
        self.reset()

    def reset(self):
        self.kind = None
        self.constraint_axis = (False, False, False)
        self.orient_type = 'GLOBAL'
        self.orient_axis = 'Z'

    @property
    def valid(self):
        return self.kind is not None

    @property
    def axis_indices(self):
        """Indices of the constrained axes, e.g. ``[0, 1]`` for the XY plane."""
        return [i for i, enabled in enumerate(self.constraint_axis) if enabled]

    @property
    def rotate_axis_index(self):
        """Axis index a rotation spins around, or ``None`` for view rotation."""
        if self.orient_type == 'VIEW':
            return None
        indices = self.axis_indices
        if len(indices) == 1:
            return indices[0]
        return _AXIS_INDEX.get(self.orient_axis)

    def describe(self):
        """Short human readable summary, used by the sidebar panel."""
        if not self.valid:
            return "None yet"
        if self.kind == TRACKBALL:
            return "Trackball"
        axes = "".join(n for n, on in zip("XYZ", self.constraint_axis) if on)
        if not axes or self.orient_type == 'VIEW':
            free = {
                TRANSLATE: "Move (screen space)",
                RESIZE: "Scale (uniform)",
                ROTATE: "Rotate (view axis)",
            }
            return free.get(self.kind, LABELS.get(self.kind, "?"))
        return "{} {} ({})".format(
            LABELS.get(self.kind, "?"), axes, self.orient_type.capitalize()
        )


#: Module level singleton. The viewport draw handler refreshes it.
LAST = LastAxis()


def capture():
    """Refresh :data:`LAST` from the most recently registered operator.

    Returns ``True`` when the last operator was a transform (and the state was
    therefore updated). Cheap enough to call on every viewport redraw: it reads
    at most four RNA properties off an operator that already exists.
    """
    try:
        operators = bpy.context.window_manager.operators
        count = len(operators)
        if count == 0:
            return False
        op = operators[count - 1]
        kind = OP_KINDS.get(op.bl_idname)
        if kind is None:
            return False
        props = op.properties
    except Exception:
        # A half torn down operator, or no window manager (background mode).
        return False

    try:
        axis = tuple(bool(v) for v in getattr(props, "constraint_axis", ()))
    except Exception:
        axis = ()

    LAST.kind = kind
    LAST.constraint_axis = axis if len(axis) == 3 else (False, False, False)
    LAST.orient_type = _safe_enum(props, "orient_type", 'GLOBAL')
    LAST.orient_axis = _safe_enum(props, "orient_axis", LAST.orient_axis)
    return True


def _safe_enum(props, name, fallback):
    try:
        value = getattr(props, name, None)
    except Exception:
        return fallback
    return value if value else fallback


#: Draw handler used purely as a "something happened" tick. Blender offers no
#: operator-finished callback, and a viewport redraw is the closest equivalent.
#: It draws nothing.
_handle = None


def _on_redraw():
    capture()


def register():
    global _handle
    LAST.reset()
    if bpy.app.background or _handle is not None:
        return
    _handle = bpy.types.SpaceView3D.draw_handler_add(
        _on_redraw, (), 'WINDOW', 'POST_VIEW'
    )


def unregister():
    global _handle
    if _handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_handle, 'WINDOW')
        _handle = None
    LAST.reset()
