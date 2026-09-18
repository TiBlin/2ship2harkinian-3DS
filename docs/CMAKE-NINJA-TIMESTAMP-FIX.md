# CMake/Ninja regeneration-loop protection

## Symptom

A Windows build could repeatedly print:

```text
[0/N] Re-running CMake...
```

without reaching normal C/C++ compilation.

## Root cause

A ZIP timestamp/timezone mismatch could extract source files with modification times later than a freshly generated `build.ninja`. Ninja correctly treated the build manifest as out of date, CMake regenerated it, and the regenerated file was still older than the future-dated source input. That created a regeneration loop.

## Current protection

`scripts/build_clock.py`:

1. scans only project build-input trees;
2. ignores SDK files, game archives and build outputs;
3. detects source mtimes that are in the future;
4. preserves existing game/libultraship build caches before changing metadata;
5. normalizes only those future mtimes without changing file contents;
6. performs a Ninja dry-run check on the libultraship manifest after configuration;
7. stops with a diagnostic instead of entering a repeated regeneration loop if the manifest is still dirty.

The protection does not disable CMake regeneration globally. Legitimate dependency changes can still regenerate the build system normally.
