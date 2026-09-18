#!/usr/bin/env python3
"""Repair future-dated source mtimes without changing bytes or SDK files.

ZIP DOS timestamps carry no timezone. A source archive made in UTC and
extracted as local time can make CMake inputs newer than every freshly written
build.ninja. Do not disable regeneration: fix these source timestamps before
configuration, and retire existing build caches so timestamp repair cannot
hide a change from an incremental build.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time
import uuid
from collections.abc import Callable, Iterator

SOURCE_DIRS = ("cmake", "platform", "scripts", "third_party")
SOURCE_FILES = ("CMakeLists.txt", "build.py")
SKIP_DIRS = {".git", ".svn", ".hg", ".venv", "__pycache__", "_deps", "CMakeFiles",
             "build", "dist", "wizard-logs", "validation"}
SKIP_SUFFIXES = {".o2r", ".otr", ".z64", ".n64", ".v64", ".cia", ".3dsx",
                 ".sav", ".pyc"}


def emit(message: str) -> None:
    print(message, flush=True)


def is_link(path: Path) -> bool:
    info = path.lstat()
    # Reject name-surrogate reparse points (symlinks/junctions), NOT all
    # reparse points: OneDrive cloud files also carry FILE_ATTRIBUTE_REPARSE_POINT.
    # The name-surrogate bit is documented by Microsoft (0x20000000).
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_reparse_tag", 0) & 0x20000000)


def skip_directory(name: str) -> bool:
    lower = name.lower()
    if lower == "build-deps":  # These are pinned source dependencies, not a cache.
        return False
    return lower in {s.lower() for s in SKIP_DIRS} or lower.startswith(("build-", "build_", "dist-"))


def source_files(root: Path) -> Iterator[Path]:
    """Only the project's build-input trees, never SDK, archives or build caches."""
    for name in SOURCE_FILES:
        path = root / name
        if path.is_file() and not is_link(path):
            yield path
    for name in SOURCE_DIRS:
        base = root / name
        if not base.is_dir() or is_link(base):
            continue
        for directory, dirs, names in os.walk(base, followlinks=False):
            parent = Path(directory)
            dirs[:] = sorted(d for d in dirs if not skip_directory(d) and not is_link(parent / d))
            for filename in sorted(names):
                path = parent / filename
                if path.suffix.lower() in SKIP_SUFFIXES or is_link(path):
                    continue
                if path.is_file():
                    yield path


def prepare_source_clock(root: Path, log: Callable[[str], None] = emit) -> dict:
    """Clamp only future-dated build inputs to now; back up caches first.

    Call during a build, not in a check-only/preflight action. The caller must
    not run another build concurrently. The wizard already owns a project lock.
    No file contents, device clock, devkitPro installation or assets are edited.
    """
    root = root.resolve()
    started_ns = time.time_ns()
    future = [(path, path.stat()) for path in source_files(root)]
    future = [(path, info) for path, info in future if info.st_mtime_ns > started_ns]
    report = {"checked_at_ns": started_ns, "changed_count": 0,
              "source_bytes_modified": False, "files": [], "cache_backups": []}
    if not future:
        log("Source timestamps: OK (no build input is dated in the future).")
        return report

    lead = max(info.st_mtime_ns - started_ns for _, info in future) / 1_000_000_000
    log(f"Future-dated source timestamps detected: {len(future)} file(s), maximum lead {lead:.1f} s.")
    suffix = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    cache_paths = (root / "build-arm", root / "third_party/libultraship/build-3ds")
    # Validate both paths before moving either. Preserve old objects, do not
    # lower source mtimes while retaining a potentially inconsistent cache.
    for cache in cache_paths:
        if cache.exists() or cache.is_symlink():
            if is_link(cache) or not cache.resolve().is_relative_to(root) or not cache.is_dir():
                raise RuntimeError(f"External or invalid build cache: {cache}. No cache was removed.")
    for cache in cache_paths:
        if cache.exists():
            saved = cache.with_name(cache.name + ".avant-timestamps-" + suffix)
            if saved.exists():
                raise RuntimeError(f"Backup already exists: {saved}")
            cache.rename(saved)
            report["cache_backups"].append({"from": cache.relative_to(root).as_posix(),
                                             "backup": saved.relative_to(root).as_posix()})
            log(f"Previous build cache preserved: {saved}")

    journal = root / "wizard-logs" / ("timestamps-" + suffix + ".json")
    journal.parent.mkdir(parents=True, exist_ok=True)
    # Journal intent before touching metadata, so an interrupted run remains
    # auditable. mtimes and relative names suffice; no private asset paths.
    target_ns = time.time_ns()
    report.update({"target_mtime_ns": target_ns, "maximum_lead_seconds": round(lead, 3),
                   "journal": journal.relative_to(root).as_posix(), "completed": False})
    report["files"] = [{"path": path.relative_to(root).as_posix(), "old_mtime_ns": info.st_mtime_ns}
                       for path, info in future]
    journal.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for path, before in future:
        current = path.stat()
        if is_link(path) or current.st_mtime_ns != before.st_mtime_ns or current.st_size != before.st_size:
            raise RuntimeError(f"Source changed during timestamp verification: {path}. Retry without concurrent editing.")
        os.utime(path, ns=(before.st_atime_ns, target_ns))
        report["changed_count"] += 1
    report["completed"] = True
    journal.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    log(f"Source timestamps repaired: {report['changed_count']} file(s); file contents unchanged.")
    log(f"Timestamp report: {journal}")
    return report


def check_lus_ninja_manifest(build: Path, env: dict[str, str],
                             log: Callable[[str], None] = emit) -> None:
    """Dry-run the manifest target after explicit LUS configuration.

    This pinned LUS graph has no CONFIGURE_DEPENDS glob verification step.
    Scope this check to LUS, not to the game graph, whose legitimate glob check
    can appear dirty in a dry run. No configure/build command executes here.
    """
    ninja = shutil.which("ninja", path=env.get("PATH"))
    if not ninja:
        raise RuntimeError("Ninja was not found while checking the libultraship manifest.")
    command = [ninja, "-C", str(build), "-n", "-d", "explain", "build.ninja"]
    try:
        result = subprocess.run(command, env=env, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, encoding="utf-8", errors="replace",
                                timeout=30)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("Ninja manifest verification timed out; the build was stopped without retrying.") from error
    output = result.stdout + result.stderr
    dirty = "Re-running CMake" in output
    if result.returncode or dirty:
        diagnostic = build / "ninja-regeneration-diagnostic.txt"
        diagnostic.write_text("COMMAND: " + subprocess.list2cmdline(command) + "\n\n" + output,
                              encoding="utf-8")
        log(output.rstrip())
        raise RuntimeError(
            "The libultraship Ninja manifest is still out of date immediately after CMake. "
            "Preventive stop: do not enter a repeated CMake regeneration loop. "
            "Check the system clock and the input path reported by 'ninja explain' "
            "(external devkitPro files are never modified). "
            f"Diagnostic: {diagnostic}")
    log("libultraship Ninja manifest: stable; starting compilation.")
