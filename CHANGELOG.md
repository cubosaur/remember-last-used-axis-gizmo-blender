# Changelog

All notable changes to this project are documented here. This project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.5] - 2026-08-12

### Fixed

- With the **Transform** tool the move and scale handles were drawn in exactly
  the same place -- same position, same size, to the pixel. The scale handles
  were buried inside the move arrows, which of the two a click picked was
  arbitrary, and a last used *scale* axis was indistinguishable from a last
  used *move* axis, which defeats the point of the addon in that tool. Blender's
  own gizmo keeps the two apart by pushing the move arrows out past the
  rotation dials and pulling the scale handles in, and by dropping the plane
  handles and the duplicate centre ring rather than stacking them. The same
  layout is used now. The numbers are measured off the native gizmo, by diffing
  screenshots of each Object Gizmo combination against a gizmo-free plate of
  the same view: along Z, the least foreshortened axis, the move arrow tip runs
  136px on its own and 185px once the dials are there, and the scale handle
  115px on its own and 85px as soon as anything else shares the pivot.

### Verified

- With the Transform tool the move arrow tip now lands at 172px and the scale
  handle at about 82px along Z, against 185px and 85px for the native gizmo,
  and the plane handles and the duplicate centre ring are gone. The Move,
  Rotate and Scale tools on their own are unchanged.

### Known issues

- Ticking the viewport's **Object Gizmos** boxes (Gizmos popover -> Move /
  Rotate / Scale) shows Blender's own transform gizmo alongside this one. Those
  boxes are served by `VIEW3D_GGT_xform_gizmo_context`, which is a different
  gizmo group from the tool's `VIEW3D_GGT_xform_gizmo` and carries the
  `PERSISTENT` option -- `gizmo_group_type_unlink_delayed` refuses to unlink it,
  so the suppression this addon uses cannot reach it. The transform tools
  themselves are unaffected, and those boxes are off by default.

## [1.2.4] - 2026-08-12

### Fixed

- The gizmo grew as you zoomed in and shrank as you zoomed out instead of
  holding a constant size on screen, which is what Blender's own transform
  gizmo does. The gizmo group carried the ``SCALE`` option, which despite the
  name means "scale to respect zoom" -- it anchors the gizmo to world size.
  With it on the handles measured 144px zoomed out and 422px zoomed in, against
  a steady 154px for the native gizmo. Handle sizes are recalibrated for the
  scaling that applies without it.

### Verified

- **Zoom**: every handle holds its size to within a rounding error in
  perspective at view distances of 3, 12 and 48, and in orthographic at 2, 10
  and 60, measured in screen pixels from each handle's final matrix. The plane
  handles hold their offset from the pivot too.

## [1.2.3] - 2026-08-11

### Fixed

- Pressing a transform tool's shortcut while that tool was already active
  brought Blender's own transform gizmo back on top of this one, showing two
  overlapping gizmos at different sizes. Activating a tool re-links its gizmo
  group even when it is already active, and the suppression was keyed on
  (mode, tool), which cannot see a repeat of the same tool. It is now also
  driven by a message-bus subscription on tool activation, which fires on every
  activation including repeats.

## [1.2.2] - 2026-08-11

### Fixed

- Move arrow heads and scale handle boxes are chunkier, closer to Blender's
  own. ``aspect`` turns out to be a no-op on both the arrow and box styles, so
  the head is sized through ``scale_basis`` with ``length`` pulled back to keep
  the arrow tip where it was.
- The centre handle was oversized after the previous round's calibration and is
  back in proportion with the native one.

### Verified

- **Edit Mode**: the gizmo appears with the Move/Rotate/Scale tool, the pivot
  follows the selected geometry, and the axis highlight, handle drags and the
  middle mouse drag all transform the selection. With the Tweak tool no gizmo
  is shown, matching Blender.
- **Snapping**: scene snapping applies to both handle drags and the middle
  mouse drag. The transform operators are invoked without overriding `snap`,
  so they pick up the scene's snapping settings exactly as the native gizmo
  does.

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

[1.2.5]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.2.5
[1.2.4]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.2.4
[1.2.3]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.2.3
[1.2.2]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.2.2
[1.2.1]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.2.1
[1.2.0]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.2.0
[1.1.0]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.1.0
[1.0.0]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.0.0
