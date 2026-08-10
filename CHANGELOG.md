# Changelog

All notable changes to this project are documented here. This project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[1.0.0]: https://github.com/cubosaur/maya-gizmo-for-blender/releases/tag/v1.0.0
