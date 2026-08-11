# Changelog

All notable changes to this project are documented here. This project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.1] - 2026-08-11

### Fixed

- Handles were drawn far too thin, especially on HiDPI displays.
  ``Gizmo.line_width`` is a raw pixel count and does not follow the interface
  scale the way Blender's own gizmo lines do, so the line weight is now scaled
  by the UI scale at draw time. Axis, dial and ring weights were calibrated
  against the native gizmo at both 1x and 2x interface scale.
- Handle lengths and the rotation gizmo's outer ring were resized to match the
  native gizmo more closely.
- The move and scale plane handles drifted and popped about while orbiting.
  Their offset was derived from a world-per-pixel estimate that wobbled by
  around 10% from frame to frame; they now use ``matrix_offset`` with
  ``use_draw_offset_scale``, letting Blender scale the offset itself, which is
  the mechanism the native gizmo uses.

## [1.2.0] - 2026-08-11

### Changed

- The last used axis is now shown by **colouring the transform gizmo handle
  itself yellow** instead of adding a separate marker. The yellow circle from
  1.1.0 is gone.
- To make that possible the move / rotate / scale gizmos are rebuilt from
  Blender's own built-in gizmo primitives, and the native transform gizmo group
  is suppressed while the addon is enabled. Handles run the same `transform.*`
  operators as before, so dragging them behaves identically.
- Turning **Highlight Last Used Axis** off now restores Blender's stock
  transform gizmo, rather than leaving the viewport without one.

### Removed

- The **Size** and **Only With Gizmos Visible** preferences, which no longer
  apply. Handle sizes follow Blender's own gizmo size preference, and the gizmo
  already appears exactly when Blender's would.

### Notes

- Recolouring via the theme was evaluated and rejected: the transform gizmo
  takes its axis colours from `theme.user_interface.axis_x/y/z`, which also
  colour the viewport floor grid lines and the navigation gizmo.

## [1.1.0] - 2026-08-11

### Changed

- The last used axis is now marked by a single yellow circle parked just outside
  the tip of Blender's gizmo, pointing along the axis. It replaces the previous
  set of shapes (axis bar, plane quad, rotation arc, centre ring) and is the
  same circle for move, rotate and scale.
- That circle is a real gizmo, so it can be **clicked or dragged directly** to
  run the same transform a middle mouse drag does.
- It now **hides while a transform is running** and reappears when the drag
  ends, matching how Blender's own gizmos behave. Previously it stayed on screen
  and drifted about as the selection moved.

### Removed

- The **Line Width** preference, which no longer applies now that the marker is
  a circle rather than drawn lines. Colour, opacity and size remain.

## [1.0.0] - 2026-08-10

Initial release.

### Added

- Remembers the last used transform axis, whether it came from dragging a gizmo
  handle or from the `G`/`R`/`S` shortcuts. Single axes, two-axis plane handles,
  screen-space and uniform variants are all tracked, along with the transform
  orientation.
- Middle-mouse-drag anywhere in the 3D viewport re-runs that transform along
  that axis, interactively -- the drag distance drives the amount, and the
  transform confirms when the button is released.
- Yellow highlight drawn over the last used gizmo handle: a bar along a single
  axis, a quad on a plane handle, an arc on a rotation dial, a ring for
  screen-space and uniform transforms.
- Viewport orbit on right-mouse-drag, with the 3D viewport context menus retimed
  from mouse-press to mouse-click so a normal right click still opens them.
- **Reset Hotkeys** button in the addon preferences and in the sidebar panel.
  Every keymap change is recorded in the preferences before it is made, so a
  reset restores the previous state exactly, even after a crash.
- Keymap changes are reverted automatically when the addon is disabled.
- Preferences for the highlight colour, opacity, width and size, for the middle
  mouse activation mode, and for which transform a middle mouse drag runs.

### Notes

- Shift+MMB (pan), Ctrl+MMB (zoom), Shift+Ctrl+MMB (dolly) and Shift+RMB
  (place 3D cursor) are deliberately left untouched.
- The right-mouse-drag orbit is skipped automatically on the right-click-select
  keymap, where right mouse already selects.

[1.2.0]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.2.0
[1.1.0]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.1.0
[1.0.0]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.0.0
