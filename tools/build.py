#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the installable extension zip.

Blender can do this itself::

    blender --command extension build

but that needs Blender on PATH, which CI does not have. This produces the same
archive using only the standard library, honouring the ``paths_exclude_pattern``
list in ``blender_manifest.toml`` so both routes agree.
"""

import argparse
import fnmatch
import pathlib
import sys
import tomllib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = "blender_manifest.toml"


def load_manifest():
    with open(ROOT / MANIFEST, "rb") as handle:
        return tomllib.load(handle)


def is_excluded(relative, patterns, is_dir):
    """Match a repo-relative POSIX path against Blender's exclude patterns.

    Supports the subset the manifest uses: a leading ``/`` anchors to the
    project root, a trailing ``/`` matches a directory, and ``*`` is a wildcard.
    """
    posix = relative.as_posix()
    for pattern in patterns:
        anchored = pattern.startswith("/")
        dir_only = pattern.endswith("/")
        cleaned = pattern.strip("/")
        if not cleaned:
            continue
        if dir_only and not is_dir:
            # A directory pattern also excludes everything beneath it.
            if any(part == cleaned for part in relative.parts[:-1]):
                return True
            continue
        if anchored:
            if fnmatch.fnmatch(posix, cleaned) or posix.startswith(cleaned + "/"):
                return True
        else:
            if fnmatch.fnmatch(relative.name, cleaned):
                return True
            if any(fnmatch.fnmatch(part, cleaned) for part in relative.parts):
                return True
    return False


def collect(patterns):
    files = []
    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT)
        if is_excluded(relative, patterns, path.is_dir()):
            continue
        if path.is_file():
            files.append(relative)
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="dist")
    parser.add_argument(
        "--expect-version",
        help="Fail if the manifest version is not this (used to check release tags)",
    )
    args = parser.parse_args(argv)

    manifest = load_manifest()
    ext_id = manifest["id"]
    version = manifest["version"]

    if args.expect_version and args.expect_version.lstrip("v") != version:
        print(
            "error: tag %r does not match manifest version %r"
            % (args.expect_version, version),
            file=sys.stderr,
        )
        return 1

    patterns = manifest.get("build", {}).get("paths_exclude_pattern", [])
    files = collect(patterns)
    if MANIFEST not in {str(f) for f in files} and pathlib.Path(MANIFEST) not in files:
        print("error: %s would not be included in the archive" % MANIFEST,
              file=sys.stderr)
        return 1

    out_dir = pathlib.Path(args.output_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / ("%s-%s.zip" % (ext_id, version))

    # Extension archives put the addon files at the root of the zip.
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for relative in files:
            zf.write(ROOT / relative, relative.as_posix())

    print("built %s" % archive)
    for relative in files:
        print("  %s" % relative.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
