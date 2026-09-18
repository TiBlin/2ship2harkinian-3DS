#!/usr/bin/env python3
"""Bounded source timestamp repair, with a journal and preserved build caches.

Original Blinky implementation of os.walk/stat/utime and Ninja's dry-run API.
The repair is needed for ZIP archives extracted with future local timestamps.
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

SOURCE_DIRS = ("cmake", "platform", "scripts", "src", "third_party")
SOURCE_FILES = ("CMakeLists.txt", "build.py")
SKIP_DIRS = {".git", ".svn", ".hg", ".venv", "__pycache__", "_deps", "cmakefiles",
             "build", "dist", "wizard-logs", "validation"}
SKIP_SUFFIXES = {".o2r", ".otr", ".z64", ".n64", ".v64", ".cia", ".3dsx", ".sav", ".pyc"}


def emit(message):
    print(message, flush=True)


def is_link(path):
    metadata = path.lstat()
    # Microsoft IO_REPARSE_TAG_NAME_SURROGATE. Cloud placeholders are allowed.
    return stat.S_ISLNK(metadata.st_mode) or (getattr(metadata, "st_reparse_tag", 0) & 0x20000000) != 0


def skip_directory(name):
    lower = name.casefold()
    return lower != "build-deps" and (lower in SKIP_DIRS or lower.startswith(("build-", "build_", "dist-")))


def source_files(root):
    root = Path(root).resolve()
    pending = [root / name for name in (*SOURCE_FILES, *SOURCE_DIRS)]
    while pending:
        item = pending.pop()
        if not item.exists() or is_link(item):
            continue
        if item.is_dir():
            pending.extend(sorted((child for child in item.iterdir()
                                   if not child.is_dir() or not skip_directory(child.name)), reverse=True))
        elif item.suffix.lower() not in SKIP_SUFFIXES:
            yield item


def prepare_source_clock(root, log=emit):
    root = Path(root).resolve()
    now = time.time_ns()
    scheduled = []
    for source in source_files(root):
        before = source.stat()
        if before.st_mtime_ns > now:
            scheduled.append((source, before))
    report = {"checked_at_ns": now, "changed_count": 0, "source_bytes_modified": False,
              "files": [], "cache_backups": []}
    if not scheduled:
        log("Source timestamps: no future build inputs.")
        return report
    token = uuid.uuid4().hex
    moves = []
    for name in ("build-arm", "third_party/libultraship/build-3ds"):
        cache = root / name
        if cache.exists() or cache.is_symlink():
            destination = cache.with_name(cache.name + ".before-clock-" + token)
            if is_link(cache) or not cache.resolve().is_relative_to(root) or not cache.is_dir():
                raise RuntimeError(f"Cache externe ou non valide: {cache}")
            if destination.exists() or not destination.resolve().is_relative_to(root):
                raise RuntimeError(f"Invalid cache backup: {destination}")
            moves.append((cache, destination))
    # Validate every source and cache before the first filesystem mutation.
    for path, before in scheduled:
        current = path.stat()
        if is_link(path) or current.st_mtime_ns != before.st_mtime_ns or current.st_size != before.st_size:
            raise RuntimeError(f"Source changed during timestamp scan: {path}")
        report["files"].append({"path": path.relative_to(root).as_posix(), "old_mtime_ns": before.st_mtime_ns})
    journal = root / "wizard-logs" / ("source-clock-" + token + ".json")
    journal.parent.mkdir(parents=True, exist_ok=True)
    report.update(journal=journal.relative_to(root).as_posix(), completed=False,
                  maximum_lead_seconds=round(max(info.st_mtime_ns - now for _, info in scheduled) / 1e9, 3),
                  target_mtime_ns=now)
    def persist():
        journal.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    persist()
    for cache, destination in moves:
        cache.rename(destination)
        report["cache_backups"].append({"from": cache.relative_to(root).as_posix(),
                                        "backup": destination.relative_to(root).as_posix()})
        persist()
    for path, before in scheduled:
        current = path.stat()
        if is_link(path) or current.st_mtime_ns != before.st_mtime_ns or current.st_size != before.st_size:
            raise RuntimeError(f"Source changed during timestamp repair: {path}")
        os.utime(path, ns=(before.st_atime_ns, now))
        report["changed_count"] += 1
    report["completed"] = True
    persist()
    log(f"Repaired {len(scheduled)} future timestamps; source bytes and old caches preserved. Journal: {journal}")
    return report


def check_lus_ninja_manifest(build, env, log=emit):
    ninja = shutil.which("ninja", path=env.get("PATH"))
    if ninja is None:
        raise RuntimeError("Ninja introuvable; install native Ninja")
    command = [ninja, "-C", str(build), "-n", "-d", "explain", "build.ninja"]
    try:
        dry_run = subprocess.run(command, env=env, capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=30)
    except subprocess.TimeoutExpired as failure:
        raise RuntimeError("Ninja manifest check timed out; arret sans relance") from failure
    diagnostic = dry_run.stdout + dry_run.stderr
    if dry_run.returncode != 0 or "Re-running CMake" in diagnostic:
        output = Path(build) / "ninja-regeneration-diagnostic.txt"
        output.write_text(subprocess.list2cmdline(command) + "\n" + diagnostic, encoding="utf-8")
        log(diagnostic)
        raise RuntimeError(f"Arret preventif: Ninja manifest still dirty; inspect {output}. External SDK timestamps were not edited.")
    log("LUS Ninja regeneration check passed.")