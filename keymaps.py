# SPDX-License-Identifier: GPL-3.0-or-later
"""Keymap installation and removal.

Two different kinds of change are made, and they are undone differently:

1. **Additions** go into ``wm.keyconfigs.addon``. Blender discards those with
   the addon, and we remove them explicitly on unregister anyway.

2. **Edits to existing entries** (retiming the viewport context menus from press
   to click) have to happen in ``wm.keyconfigs.user``, which persists in the
   user preferences. Every one of those is recorded in
   :attr:`prefs.RememberLastUsedAxisPreferences.keymap_backup` as JSON *before* it is
   changed, so it can be restored exactly -- including after a crash, since the
   record lives in the preferences rather than in memory.

The mouse is left as Blender has it. Middle mouse still orbits, along with
Shift+MMB to pan and Ctrl+MMB to zoom, and the transform goes on a right mouse
*drag* -- a separate keymap value from the right mouse *click* the context menu
uses, which is why both fit on the same button. The menu has to move from press
to click for that to work, since a menu opening on press never lets a drag
begin; that retiming is the only existing entry this touches.
"""

import json

import bpy

from .prefs import get_prefs

#: Keymap items this addon created, as ``(KeyMap, KeyMapItem)`` pairs.
_addon_items = []

#: Set once the keymap has been fully installed (both stages).
_applied = False

#: Handle for the deferred apply timer.
_pending_timer = None
_pending_attempts = 0
_MAX_ATTEMPTS = 40

#: One-shot timers scheduled by :func:`_defer`, so they can all be cancelled.
_deferred_timers = set()

#: Delay between the two apply stages. Any value that spans an event loop
#: iteration works; this is short enough to be imperceptible.
_STAGE_DELAY = 0.05

BACKUP_VERSION = 1

#: Context menus are invoked through these; we only touch ones whose menu or
#: panel name is a 3D viewport one.
MENU_OPERATORS = {"wm.call_menu", "wm.call_panel"}
MENU_NAME_PREFIX = "VIEW3D_"


# ---------------------------------------------------------------------------
# Deferred work
# ---------------------------------------------------------------------------

def _defer(func, delay=None):
    """Run ``func`` once, after the given delay, tracked so it can be cancelled."""
    def run_once():
        _deferred_timers.discard(run_once)
        try:
            func()
        except Exception:
            import traceback
            traceback.print_exc()
        return None

    _deferred_timers.add(run_once)
    bpy.app.timers.register(
        run_once, first_interval=_STAGE_DELAY if delay is None else delay
    )
    return run_once


def _cancel_deferred():
    for timer in list(_deferred_timers):
        try:
            bpy.app.timers.unregister(timer)
        except ValueError:
            pass
    _deferred_timers.clear()


# ---------------------------------------------------------------------------
# Keymap item helpers
# ---------------------------------------------------------------------------

def _mods(kmi):
    """Modifier state as plain ints.

    Blender stores modifiers as -1 (any), 0 (must not be held) or 1 (held), so
    the values are compared numerically rather than as booleans.
    """
    return (int(kmi.shift), int(kmi.ctrl), int(kmi.alt), int(kmi.oskey))


def _unmodified(kmi):
    return _mods(kmi) == (0, 0, 0, 0) and not kmi.any and kmi.key_modifier == 'NONE'


def _menu_name(kmi):
    """Menu/panel name for ``wm.call_menu`` and ``wm.call_panel``, else ``None``."""
    if kmi.idname not in MENU_OPERATORS:
        return None
    try:
        return kmi.properties.name
    except AttributeError:
        return None


def _signature(km, kmi):
    """Enough information to find this item again in a later Blender session."""
    shift, ctrl, alt, oskey = _mods(kmi)
    sig = {
        "km": km.name,
        "space": km.space_type,
        "region": km.region_type,
        "id": kmi.id,
        "idname": kmi.idname,
        "type": kmi.type,
        "shift": shift,
        "ctrl": ctrl,
        "alt": alt,
        "oskey": oskey,
        "any": bool(kmi.any),
        "key_modifier": kmi.key_modifier,
    }
    menu = _menu_name(kmi)
    if menu:
        sig["menu"] = menu
    return sig


def _matches(kmi, entry, value):
    if kmi.idname != entry["idname"] or kmi.type != entry["type"]:
        return False
    if value is not None and kmi.value != value:
        return False
    if _mods(kmi) != (entry["shift"], entry["ctrl"], entry["alt"], entry["oskey"]):
        return False
    if bool(kmi.any) != entry["any"] or kmi.key_modifier != entry["key_modifier"]:
        return False
    if entry.get("menu") and _menu_name(kmi) != entry["menu"]:
        return False
    return True


def _find_item(keyconfig, entry, value):
    """Locate a previously modified item, by id first then by signature."""
    km = keyconfig.keymaps.get(entry["km"])
    if km is None:
        return None
    item_id = entry.get("id")
    if item_id is not None:
        try:
            kmi = km.keymap_items.from_id(item_id)
        except Exception:
            kmi = None
        if kmi is not None and _matches(kmi, entry, value):
            return kmi
    for kmi in km.keymap_items:
        if _matches(kmi, entry, value):
            return kmi
    return None


# ---------------------------------------------------------------------------
# Backup record
# ---------------------------------------------------------------------------

def _load_backup():
    p = get_prefs()
    if p is None or not p.keymap_backup:
        return []
    try:
        data = json.loads(p.keymap_backup)
    except ValueError:
        return []
    if not isinstance(data, dict) or data.get("version") != BACKUP_VERSION:
        return []
    entries = data.get("entries")
    return entries if isinstance(entries, list) else []


def _store_backup(entries):
    p = get_prefs()
    if p is None:
        return
    if entries:
        p.keymap_backup = json.dumps({"version": BACKUP_VERSION, "entries": entries})
    else:
        p.keymap_backup = ""


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def _iter_viewport_context_menus(keyconfig):
    """Unmodified right-mouse-press entries that open a 3D viewport menu.

    Filtering on the ``VIEW3D_`` menu name prefix keeps this away from every
    other editor's right click menu, and away from things that merely happen to
    use right mouse in the viewport (stencil control, lasso select, and so on).
    """
    for km in keyconfig.keymaps:
        for kmi in km.keymap_items:
            if kmi.type != 'RIGHTMOUSE' or kmi.value != 'PRESS':
                continue
            if not _unmodified(kmi):
                continue
            menu = _menu_name(kmi)
            if menu and menu.startswith(MENU_NAME_PREFIX):
                yield km, kmi


def _uses_right_mouse_select(keyconfig):
    """True when the user is on the right-click-select keymap preference.

    Scans every keymap rather than just '3D View': on that preference the
    selection bindings live in the per-tool keymaps ("3D View Tool: ...", and
    the mode keymaps), not in '3D View' itself.
    """
    for km in keyconfig.keymaps:
        for kmi in km.keymap_items:
            if (
                kmi.idname == "view3d.select"
                and kmi.type == 'RIGHTMOUSE'
                and kmi.value in {'PRESS', 'CLICK', 'CLICK_DRAG'}
                and not (kmi.ctrl or kmi.alt or kmi.oskey)
            ):
                return True
    return False


def compatibility_warning(context=None):
    """Lines describing keymap conflicts we cannot resolve, or ``None``."""
    ctx = context or bpy.context
    try:
        kc = ctx.window_manager.keyconfigs.user
    except AttributeError:
        return None
    if kc is None:
        return None
    p = get_prefs(ctx)
    if p is None or not p.enable_rmb_transform:
        return None
    if _uses_right_mouse_select(kc):
        return [
            "Right mouse is bound to Select in your keymap.",
            "The right-mouse-drag transform is disabled to avoid breaking it.",
        ]
    return None


# ---------------------------------------------------------------------------
# Apply / revert
# ---------------------------------------------------------------------------

#: Navigation operators plain middle mouse may be bound to.
MMB_NAV_OPERATORS = {"view3d.rotate", "view3d.move", "view3d.zoom", "view3d.dolly"}


def repair_legacy_mmb(context=None, force=False):
    """Switch middle mouse navigation back on if an older version disabled it.

    Versions up to 1.4.x put the transform on middle mouse, which meant turning
    Blender's own orbit entry off. That was recorded so it could be put back,
    but :func:`revert` used to clear the record even when the restore had
    failed, and a cleared record leaves the orbit off with nothing left to undo
    it.

    Middle mouse is never touched now, so an inactive plain middle mouse
    navigation entry can only be one of ours to give back. Done once unless
    ``force`` is set, so that a user who switches it off themselves is not
    overruled every time the addon loads.
    """
    ctx = context or bpy.context
    p = get_prefs(ctx)
    if p is None or (p.legacy_mmb_repaired and not force):
        return 0
    try:
        kc_user = ctx.window_manager.keyconfigs.user
    except AttributeError:
        return 0
    if kc_user is None:
        return 0

    repaired = 0
    for km in kc_user.keymaps:
        for kmi in km.keymap_items:
            if (
                kmi.type == 'MIDDLEMOUSE'
                and kmi.idname in MMB_NAV_OPERATORS
                and _unmodified(kmi)
                and not kmi.active
            ):
                kmi.active = True
                repaired += 1
    p.legacy_mmb_repaired = True
    return repaired


def _enabled(p, kc_user):
    """Whether the right-mouse-drag transform can be installed at all."""
    return p.enable_rmb_transform and not _uses_right_mouse_select(kc_user)


def _apply_user_keyconfig_edits(p, kc_user):
    entries = []

    # A context menu on right mouse *press* opens before a drag can start, so
    # it has to move to *click* for the drag to ever be seen. This is the only
    # existing keymap entry the addon changes.
    if _enabled(p, kc_user) and p.retime_context_menu:
        for km, kmi in _iter_viewport_context_menus(kc_user):
            entry = _signature(km, kmi)
            entry.update(field="value", old=kmi.value, new='CLICK')
            entries.append(entry)
            kmi.value = 'CLICK'

    return entries


def _add_addon_items(p, kc_addon, kc_user):
    """Install the binding, returning whether anything was actually added."""
    if not _enabled(p, kc_user):
        return False
    km = kc_addon.keymaps.new(name="3D View", space_type='VIEW_3D')
    # CLICK_DRAG rather than PRESS: press belongs to the context menu, and only
    # a drag can be told apart from the click that opens it.
    kmi = km.keymap_items.new(
        "rla.transform_last_axis", 'RIGHTMOUSE', 'CLICK_DRAG'
    )
    _addon_items.append((km, kmi))
    return True


def apply(context=None):
    """Install the addon keymap. Safe to call when already applied.

    Deliberately split across two event loop cycles. Blender rebuilds the
    resolved user keyconfig from ``default + addon`` in a single update pass,
    and when edits to existing user keyconfig entries and additions to the
    addon keyconfig arrive in the *same* pass, the additions are silently
    dropped: they remain visible in ``wm.keyconfigs.addon`` but never reach the
    resolved config, so the shortcut does nothing at all. Editing first and
    adding a cycle later avoids that.
    """
    revert(context, clear_backup=True)

    ctx = context or bpy.context
    p = get_prefs(ctx)
    if p is None:
        return False
    try:
        keyconfigs = ctx.window_manager.keyconfigs
    except AttributeError:
        return False

    kc_user = keyconfigs.user
    if kc_user is None or keyconfigs.addon is None:
        return False
    # At startup the user keyconfig exists before its keymaps are filled in.
    if kc_user.keymaps.get("3D View") is None:
        return False

    repair_legacy_mmb(ctx)
    # Anything revert() could not resolve is still on record, so add to it
    # rather than replacing it.
    _store_backup(_load_backup() + _apply_user_keyconfig_edits(p, kc_user))
    _defer(_apply_addon_items_stage)
    return True


def _apply_addon_items_stage():
    """The second half of :func:`apply`, one event loop cycle later."""
    global _applied

    ctx = bpy.context
    p = get_prefs(ctx)
    try:
        keyconfigs = ctx.window_manager.keyconfigs
    except AttributeError:
        return
    if p is None or keyconfigs.addon is None or keyconfigs.user is None:
        return
    # Only "applied" when a binding really went in. It does not on the
    # right-click-select keymap, or with the transform switched off, and the
    # preferences panel reports this state.
    _applied = _add_addon_items(p, keyconfigs.addon, keyconfigs.user)


def revert(context=None, clear_backup=True):
    """Undo every change this addon made to the keymap."""
    global _applied

    _cancel_deferred()

    for km, kmi in _addon_items:
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    _addon_items.clear()

    ctx = context or bpy.context
    try:
        kc_user = ctx.window_manager.keyconfigs.user
    except AttributeError:
        kc_user = None

    restored = 0
    unresolved = []
    if kc_user is not None:
        # Reverse order so that overlapping edits unwind cleanly.
        for entry in reversed(_load_backup()):
            field = entry.get("field")
            if field not in {"active", "value"}:
                continue
            kmi = _find_item(kc_user, entry, entry.get("new") if field == "value" else None)
            if kmi is None:
                unresolved.append(entry)
                continue
            try:
                setattr(kmi, field, entry["old"])
                restored += 1
            except Exception:
                unresolved.append(entry)

    if clear_backup:
        # Only forget what was actually put back. Clearing the record after a
        # failed lookup strands that change for good, with nothing left to say
        # what it had been -- which is how a disabled middle mouse orbit once
        # became permanent.
        _store_backup(list(reversed(unresolved)))
    _applied = False
    return restored


def reapply():
    """Re-install the keymap, e.g. after a preference changed."""
    if bpy.app.background:
        return
    apply()


def is_applied():
    return _applied


def restore_blender_defaults(context=None):
    """Reset every keymap this addon can touch to Blender's factory defaults.

    The escape hatch for a keymap that got into a bad state. This also discards
    unrelated user customisations in those keymaps, which is why it is a
    separate, confirmed action rather than part of the normal reset.
    """
    revert(context, clear_backup=True)

    ctx = context or bpy.context
    try:
        kc_user = ctx.window_manager.keyconfigs.user
    except AttributeError:
        return 0

    names = {"3D View"}
    for km, kmi in _iter_viewport_context_menus(kc_user):
        names.add(km.name)
    # Retimed menus no longer match the press filter, so collect those too.
    for km in kc_user.keymaps:
        for kmi in km.keymap_items:
            if kmi.type == 'RIGHTMOUSE' and _unmodified(kmi):
                menu = _menu_name(kmi)
                if menu and menu.startswith(MENU_NAME_PREFIX):
                    names.add(km.name)
                    break

    count = 0
    for name in sorted(names):
        km = kc_user.keymaps.get(name)
        if km is None:
            continue
        try:
            km.restore_to_default()
            count += 1
        except Exception:
            pass

    # These keymaps are factory fresh now, so anything still on record describes
    # entries that no longer exist in the state they were recorded from.
    # Discarding it is right here, unlike in revert(): there is nothing left for
    # it to restore, and keeping it would have every later reset report work it
    # did not do.
    _store_backup([])
    return count


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def _deferred_apply():
    """Retry applying until Blender has finished building the user keyconfig.

    At addon registration time during startup ``wm.keyconfigs.user`` exists but
    is still empty, so the edits have to wait for it.
    """
    global _pending_timer, _pending_attempts
    _pending_attempts += 1
    if apply() or _pending_attempts >= _MAX_ATTEMPTS:
        _pending_timer = None
        return None
    return 0.1


def register():
    global _pending_timer, _pending_attempts
    if bpy.app.background:
        return
    _pending_attempts = 0
    _pending_timer = _deferred_apply
    bpy.app.timers.register(_deferred_apply, first_interval=0.05)


def unregister():
    global _pending_timer
    if _pending_timer is not None:
        try:
            bpy.app.timers.unregister(_pending_timer)
        except ValueError:
            pass
        _pending_timer = None
    # Always give the user their default navigation back. revert() cancels any
    # pending second stage, so nothing can re-add bindings after this.
    revert(clear_backup=True)
