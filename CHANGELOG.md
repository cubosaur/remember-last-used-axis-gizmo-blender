# Changelog

All notable changes to this project are documented here. This project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.0] - 2026-08-12

### Changed

- **The transform moves from a middle mouse drag to a right mouse drag, and
  middle mouse goes back to Blender.** Middle mouse orbits again, exactly as it
  does by default, and Shift+MMB, Ctrl+MMB and Shift+Ctrl+MMB were never
  touched to begin with. Upgrading restores the middle mouse orbit
  automatically, from the backup the older version recorded before disabling
  it.
- Retiming the viewport context menus from press to click is now the *only*
  existing keymap entry the addon changes, and the right mouse *drag* it adds
  is a separate binding from the right mouse *click* the menu uses, so both
  fit on the same button.

### Removed

- The **Orbit With Right Mouse Drag** option. Orbit never leaves middle mouse
  now, so there is nothing to move.
- The **Also Pan/Zoom With Right Mouse** option, which only existed to make up
  for orbit having moved. Shift+MMB and Ctrl+MMB are untouched.
- The **Activation** option. On right mouse the transform has to start on a
  drag: starting on press would take the context menu with it.
- The **Orbit When Nothing To Transform** option. With nothing to transform the
  drag is handed straight back to Blender rather than being redirected.

### Verified

- After upgrading from a config with the middle mouse orbit disabled, the orbit
  entry is active again, the only binding the addon adds is
  `mgb.transform_last_axis` on RIGHTMOUSE / CLICK_DRAG, nothing at all sits on
  middle mouse, and the viewport context menus read CLICK.

## [1.4.0] - 2026-08-12

### Removed

- **The yellow highlight, and the Highlight Last Used Axis option with it.**
  Marking the handle meant one of two trades, and neither held up: rebuilding
  the gizmo out of Blender's gizmo primitives, which never quite matched the
  real one and is where every visual difference from 1.2.0 onwards came from,
  or recolouring the axis in the theme, which drags that axis' floor line and
  the navigation gizmo along with it. Blender's viewport is now left completely
  alone -- nothing drawn, nothing suppressed, no colour changed -- so the
  transform gizmo looks and behaves exactly as Blender draws it, at any
  interface scale and any Gizmo Size.
- The **Color** preference, which no longer applies.

### Changed

- The last used axis is reported in the sidebar, which is now the only place it
  is shown. Everything else is unchanged: the axis tracking, the middle mouse
  transform, the right mouse orbit and the keymap handling all work as they did.

### Fixed

- A leftover axis tint from 1.3.0 is put back on the next start. That version
  recorded the colours it replaced, and upgrading straight over a running
  Blender, or a crash while a highlight was applied, would otherwise have left a
  yellow axis behind with nothing to undo it.

### Verified

- Tracking an axis leaves all three theme axis colours untouched, and the
  preferences no longer carry `show_highlight` or `highlight_color`.
- A config saved mid-tint, reopened on this version, comes back to the theme's
  own colours and clears the record.

## [1.3.0] - 2026-08-12

### Changed

- **The last used axis is now highlighted by recolouring that axis in the
  theme, and Blender's own gizmo is left completely alone.** Since 1.2.0 the
  addon suppressed the native transform gizmo and drew a replacement built from
  Blender's gizmo primitives, which is what every visual difference since then
  came down to: handle shapes, arrow lengths, a missing uniform-scale ring, the
  zoom-independent sizing, and the doubled gizmos. None of that can happen now,
  because nothing is suppressed and nothing is drawn.
- Python cannot reach the handles Blender's gizmo is made of -- a `Region`
  exposes no gizmo map, `WindowManager` offers only `gizmo_group_type_ensure`
  and `gizmo_group_type_unlink_delayed`, and `context.gizmo_group` is `None`
  outside a Python gizmo group's own callbacks. The theme is the one colour
  source Python can write, so the entry for the last used axis is swapped for
  the highlight colour and put back when the axis changes.
- The highlight now follows the interface scale, the Gizmo Size preference and
  every gizmo behaviour exactly, because Blender is the one drawing it.

### Removed

- The **Opacity** preference. Theme colours have no alpha.

### Known issues

- `theme.user_interface.axis_x/y/z` also colours that axis' viewport floor line
  and its ball on the navigation gizmo, so those turn yellow along with the
  gizmo handle. Blender has no separate theme entry for the gizmo's axes, so
  there is no way to narrow it.
- A plane handle is coloured by the axis it is perpendicular to, so a two-axis
  transform lights up the two axes it used rather than the plane handle itself.

### Verified

- A last used X lands `axis_x` on the highlight colour with `axis_y` and
  `axis_z` untouched, and switching the highlight off, and disabling the addon,
  each put the exact original colours back and clear the recorded backup.

## [1.2.7] - 2026-08-12

### Fixed

- Two transform gizmos could still be drawn at once, the second slightly
  larger, whenever the **Object Gizmos** boxes were ticked and the active tool
  had no transform gizmo of its own -- Tweak, Annotate, Measure and the rest.
  Blender serves those boxes from `VIEW3D_GGT_xform_gizmo_context`, which is
  flagged `PERSISTENT` and cannot be unlinked from Python, so this addon was
  drawing a second set on top of one it had no way to remove. That case is left
  to Blender now: its stock gizmo, without the highlight.
- The active tool takes precedence over the Object Gizmos boxes, which is what
  Blender does -- measured, the Scale tool with all three boxes ticked is pixel
  for pixel the Scale tool with none of them ticked. This addon was combining
  the two instead, so ticking a box while a transform tool was active drew
  handles Blender would not have.
- The Scale gizmo was missing the thin outer ring that uniform scale rides on,
  so it looked wrong next to Blender's with **Highlight Last Used Axis** off.
  The ring is back, and its radius is corrected from 142px to 137px against the
  native gizmo's 137px. The rotation gizmo's outer ring is the same ring, so it
  tightens by the same amount.

### Verified

- With a non-transform tool and the Object Gizmos boxes ticked, the viewport is
  pixel for pixel Blender's own: 4604 pixels changed against a gizmo-free plate
  of the same view, with the addon on or off.
- The Scale tool matches the native gizmo -- outer ring, plane handles, axis
  boxes and centre circle all in the same places -- and the Move, Rotate and
  Transform tools are unchanged.

## [1.2.6] - 2026-08-12

### Fixed

- Hammering the transform tool shortcuts could leave two transform gizmos on
  screen at once, Blender's and this one, and once it happened they stayed
  until the tool or the mode next changed. The suppression was cached on
  (mode, tool) and re-applied only when that pair changed, so a re-link that
  changed neither -- which is exactly what re-activating the tool you are
  already on does -- was invisible to it. It is re-asserted on every poll now
  rather than cached: `gizmo_group_type_unlink_delayed` measures 0.6us per
  call, so there was nothing to save by tracking it.
- The Object Gizmos boxes (Move / Rotate / Scale) were honoured even with
  **Active Object** switched off above them in the same popover, so this addon
  drew a gizmo where Blender draws none.

### Verified

- Re-linking the native group directly, with the mode and tool left alone,
  reproduces the double gizmo on the old code and it then survives every
  later redraw. On the new code the very next redraw is already clean.
- With **Active Object** off and Move ticked, neither gizmo draws a single
  pixel, matching Blender. The Move, Rotate, Scale and Transform tools are
  pixel for pixel unchanged.

### Known issues

- Ticking an Object Gizmos box while **Active Object** is on still shows
  Blender's own transform gizmo alongside this one. Those boxes are served by
  `VIEW3D_GGT_xform_gizmo_context`, which carries the `PERSISTENT` option;
  `gizmo_group_type_unlink_delayed` refuses to unlink such a group, so it
  cannot be suppressed from Python at all. Switching **Active Object** off
  hides both, and the transform tools are unaffected either way.

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

[1.5.0]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.5.0
[1.4.0]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.4.0
[1.3.0]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.3.0
[1.2.7]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.2.7
[1.2.6]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.2.6
[1.2.5]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.2.5
[1.2.4]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.2.4
[1.2.3]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.2.3
[1.2.2]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.2.2
[1.2.1]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.2.1
[1.2.0]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.2.0
[1.1.0]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.1.0
[1.0.0]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.0.0
