# Remember Last Used Axis

Bring Autodesk Maya's *"transform along the last used axis"* workflow to
Blender's 3D viewport.

In Maya, once you have used a gizmo handle you can keep transforming along that
axis by dragging anywhere in the viewport, without having to hit the handle
again. This addon brings that to Blender, on a right mouse drag.

Blender's viewport is left exactly as it is: nothing is drawn, replaced or
recoloured. The addon watches which axis you used, names it in the sidebar, and
gives you a way to reuse it.

---

## What it does

**1. It remembers the last axis you used.**

Drag the X arrow of the move gizmo, or the XY plane handle, or press `G` `X` on
the keyboard — either way the addon remembers *Move, X, Global*. Rotation dials,
the trackball at the centre of the rotate gizmo, scale handles, plane handles
and the screen-space / uniform handles are all tracked, along with the
transform orientation you used.

It registers the moment you grab the handle, not when you let go, so a
transform you **cancel** with right click or `Esc` still counts — you picked
that axis, and the addon takes you at your word.

**2. The sidebar names it.**

**View ▸ sidebar ▸ Remember Last Used Axis** spells out what a right mouse drag will do —
*Move X (Global)*, *Scale XY (Local)*, *Trackball*, and so on — with a **Clear**
button to forget it, the **RMB Transform** switch, and **Reset Hotkeys**.

**3. Right-mouse-drag re-runs that transform, anywhere in the viewport.**

Press RMB, drag, release. It is a real interactive transform: the drag distance
drives the amount, the header shows the live value, and it confirms when you
release the button. You never have to hit a handle at all.

**4. Everything else is Blender's.**

Middle mouse still orbits, Shift+MMB still pans, Ctrl+MMB still zooms, and a
plain right click still opens the context menu. The transform sits on a right
mouse *drag*, which is a separate binding from the click.

---

## Install

**Requires Blender 4.2 or newer** (it is packaged as a Blender Extension).
Developed and tested on Blender 5.1.

1. Download `remember_last_used_axis-<version>.zip` from the
   [Releases page](https://github.com/cubosaur/remember-last-used-axis-gizmo-blender/releases/latest).
2. Drag the zip straight into a Blender window and confirm.

   *Or:* **Edit ▸ Preferences ▸ Add-ons ▸ ▾ ▸ Install from Disk…** and pick the zip.
3. Enable **Remember Last Used Axis** in the add-on list if it is not enabled already.

The keymap changes are applied as soon as the addon is enabled, and reverted as
soon as it is disabled.

---

## Keymap

Applied while the addon is enabled, in the 3D viewport only:

| Input | Before | After |
|---|---|---|
| **RMB drag** | *(unassigned)* | **Transform along the last used axis** |
| **RMB click** | Context menu (on press) | Context menu (on release) |
| MMB drag | Orbit | Orbit *(unchanged)* |
| Shift+MMB | Pan | Pan *(unchanged)* |
| Ctrl+MMB | Zoom | Zoom *(unchanged)* |
| Shift+Ctrl+MMB | Dolly | Dolly *(unchanged)* |
| Shift+RMB | Place 3D cursor | Place 3D cursor *(unchanged)* |

Retiming the context menu is the *only* existing entry the addon changes. A
menu that opens on press never lets a drag begin, so the menu moves to the
release; a normal right click still opens it. Nothing about middle mouse is
touched at all.

If you have not used an axis yet, or there is nothing for a transform to act
on — no selection in Object Mode, no active object in any other mode — the
drag is handed straight back to Blender.

## Resetting your hotkeys

Two independent guarantees, because a broken viewport is not a fun surprise:

- **Automatic.** Disabling or removing the addon reverts every keymap change.
- **Manual.** **Preferences ▸ Add-ons ▸ Remember Last Used Axis ▸ Reset Hotkeys**, or the
  same button in **View3D ▸ Sidebar (N) ▸ View ▸ Remember Last Used Axis**.

Every change is written to a backup record in the addon preferences *before* it
is made, so a reset restores exactly what you had — including your own prior
customisations, and including after an unclean shutdown.

The record and the keymap can still come apart, because the keymap edit lives
in your preferences while the record lives in the addon's: changing the
extension id puts the record beyond the reach of the new id, and so does
deleting the addon without disabling it first. So the revert does not rely on
the record alone. It also hands back anything it recognises as its own — a
viewport context menu left on click, or a plain middle mouse navigation entry
left switched off — since Blender's own values there are press and enabled, and
this addon is the only thing in your config that changes them.

If the keymap ever ends up in a state a reset cannot fix, there is a
**Restore Blender Default Keymaps** button as a last resort. It resets the
affected keymaps to factory defaults, which also discards your own edits in
them, so it asks for confirmation first.

---

## Preferences

**Edit ▸ Preferences ▸ Add-ons ▸ Remember Last Used Axis**

| Setting | Default | |
|---|---|---|
| Right Mouse Transform | on | Master switch. Off leaves the keymap completely alone. |
| Transform Type | Last Used | *Last Used* repeats your last transform. *Active Tool* follows the Move/Rotate/Scale tool instead, falling back to the last used transform for other tools. |
| Context Menu On Click | on | Retimes the viewport context menus from press to click. The transform needs this to work at all, since a menu on press never lets the drag begin. |

---

## How it works

Blender's transform gizmo is C code with no Python-visible "this handle was
dragged" callback, so the addon does not hook the gizmo. It watches two places
instead, both on the viewport redraw it already runs on.

While a transform is *running* it reads `window.modal_operators`, whose
properties carry whatever the operator was invoked with — for a gizmo handle,
the constraint that handle stands for. That is what makes the axis appear as
you grab it, and it is the only way a cancelled transform registers at all: a
cancel never reaches `wm.operators`, so once it is over there is nothing left
to read.

Once a transform *finishes* it lands in `wm.operators` carrying its
`constraint_axis` and `orient_type` — the same data the F9 redo panel shows.
That is the authoritative reading, since it reflects any axis you typed
mid-drag. The addon remembers what it has already taken from that list, so the
transform before a cancelled one cannot overwrite it.

The viewport is never touched. Nothing is drawn, no gizmo is suppressed or
replaced, and no colour is changed, so Blender's transform gizmo behaves and
looks exactly as it always does, at any interface scale and any Gizmo Size.

Earlier versions did mark the last used handle in yellow. Doing that means
either rebuilding the gizmo out of Blender's gizmo primitives — which never
quite matches the real one — or recolouring `theme.user_interface.axis_x/y/z`,
which also colours that axis' floor line and its ball on the navigation gizmo.
Python cannot reach the handles themselves: a `Region` exposes no gizmo map,
`WindowManager` offers only `gizmo_group_type_ensure` and
`gizmo_group_type_unlink_delayed`, and `context.gizmo_group` is `None` anywhere
outside a Python gizmo group's own callbacks. Neither trade was worth it, so the
marker is gone and the sidebar reports the axis instead.

The right mouse binding starts a genuine `transform.translate` / `rotate` /
`resize` with `release_confirm` set, which is why it feels identical to dragging
the handle rather than like a scripted nudge.

### Known limitations

- An axis typed **mid-drag** only lands when the transform finishes. A running
  operator's properties keep the values it was invoked with, so `G` then `X`
  reads as an unconstrained move until you confirm it — and if you cancel that,
  the unconstrained move is what gets remembered. A gizmo handle carries its
  constraint from the moment you grab it, so cancelling one of those records
  the axis exactly.
- On the **right-click-select** keymap the RMB-drag transform is skipped
  automatically, since right mouse already selects there. The addon then makes
  no keymap changes at all, and says so in preferences.
- In **Sculpt**, **Texture Paint** and **Vertex Paint** right mouse is bound to
  `brush.stencil_control`, and those mode keymaps take priority, so the RMB-drag
  transform does not reach them. **Weight Paint** binds nothing there, so it
  works as it does in Object Mode.

---

## Development

```bash
git clone https://github.com/cubosaur/remember-last-used-axis-gizmo-blender.git
cd remember-last-used-axis-gizmo-blender
```

Build the installable zip — either with Blender:

```bash
blender --command extension build
```

or without it, using only the standard library:

```bash
python tools/build.py --output-dir dist
```

Validate the manifest:

```bash
blender --command extension validate .
```

Releases are cut by pushing a `v*` tag; CI checks that the tag matches the
version in `blender_manifest.toml`, builds the zip and attaches it to the
GitHub release.

---

## License

[GPL-3.0-or-later](LICENSE), matching Blender's own licensing for addons.
