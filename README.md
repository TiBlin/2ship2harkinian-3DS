# 2Ship3DS

Experimental New Nintendo 3DS port of **2Ship2Harkinian / The Legend of Zelda: Majora's Mask**, based on the 2Ship 5.0.1 source tree and a native PICA200/Citro3D backend.

> **Status:** experimental development build. This source revision has host-side regression coverage, but it has not been fully validated on real New 3DS hardware after the latest stability changes. Expect incomplete rendering, performance issues, missing resources, audio defects, or crashes.

## Highlights

- Native New Nintendo 3DS target using devkitARM, libctru and Citro3D.
- 60 FPS presentation target through the existing interpolation path.
- Adaptive 3DS frameskip: late interpolated frames may be skipped while the final render of each game tick is preserved.
- 3DS audio fixes, including the Majora's Mask note-address gate correction.
- Resource-loading and lifetime hardening from the first stability audit.
- Windows build wizard in English.
- ROM drag-and-drop workflow that can generate the required O2R archives and build a **3DSX-only** SD-card layout.
- No ROM is included in this repository.

## Quick start — Windows wizard

Extract the repository to a normal folder and run:

```text
START-WIZARD.bat
```

The GUI lets you validate the toolchain, choose existing `mm.o2r` / `2ship.o2r` archives, optionally select a custom icon, and build the port. The custom CIA banner selector was intentionally removed; CIA packaging uses the built-in default banner.

See [WIZARD-README.md](WIZARD-README.md) for the full workflow.

## Quick start — drag a ROM onto the launcher

Drag **one supported Majora's Mask ROM** onto `START-WIZARD.bat`.

The automatic path will:

1. validate the ROM against the supported hashes used by 2Ship;
2. generate `mm.o2r`;
3. prepare the matching `2ship.o2r` support archive;
4. rebuild the 3DS port;
5. produce **3DSX only**;
6. publish an SD-ready folder named exactly `sd`.

Expected output:

```text
sd/
└── 3ds/
    └── 2ship/
        ├── 2ship-3ds.3dsx
        ├── mm.o2r
        └── 2ship.o2r
```

The ROM itself is never copied into the output folder.

## Manual build

See [BUILDING.md](BUILDING.md).

Typical Windows command with devkitPro installed at `C:\devkitPro`:

```powershell
& 'C:\devkitPro\msys2\mingw64\bin\python.exe' .\build.py --devkitpro C:/devkitPro --jobs 4 --output .\dist
```

A clean rebuild is strongly recommended after changing libultraship, resource-loading code, audio code, or the renderer.

## Current stability work

The current source includes the first stability-hardening pass. It addresses several independently reproducible classes of bugs, including:

- out-of-bounds binary reads;
- texture payload range validation;
- inconsistent concurrent resource-cache publication;
- persistent graphics commands retaining raw pointers to evictable resources;
- a cache-report lifetime issue;
- NDSP close/flush race handling;
- XML / `.meta` null handling;
- a null-resource crash observed in `ResourceMgr_LoadIfDListByName`.

The audit does **not** claim that the port is globally stable. Save-file replacement is still a known risk if an I/O failure occurs mid-write, and required-resource failures still need more end-to-end handling.

See [docs/STABILITY-AUDIT.md](docs/STABILITY-AUDIT.md) and [docs/CRASH26.md](docs/CRASH26.md).

## Performance model

The game logic is not forced to run at 60 Hz. The port targets 60 FPS through frame interpolation. When rendering falls behind, the 3DS-specific adaptive path may skip optional interpolated frames; it does not intentionally skip the final render of a game tick or the game/audio update itself.

See [docs/FPS60.md](docs/FPS60.md) and [docs/FPS60-AUTO.md](docs/FPS60-AUTO.md).

## Audio

The source includes the 3DS fix that disables an N64-address heuristic in `AudioPlayback_ProcessNotes` on 3DS. The old heuristic could reject valid native `SequenceLayer` pointers and skip ADSR/vibrato/sample-state updates.

See [docs/AUDIO-FIX.md](docs/AUDIO-FIX.md).

## Repository layout

```text
platform/3ds/        3DS platform layer and renderer
third_party/2ship/   2Ship / Majora's Mask source tree
third_party/libultraship/
                     local libultraship source used by the 3DS build
wizard/              Python wizard backend and ROM-drop worker
scripts/             build, packaging and support-archive tools
tests/               host-side regression tests
docs/                port-specific technical notes
```

## Game data

This repository does **not** include a ROM or `mm.o2r`. Game assets are supplied by the user from a compatible legally obtained ROM. The generated archives are separate from the source repository and should not be committed.

## Credits, provenance and licensing

This port builds on 2Ship2Harkinian, libultraship, devkitPro/libctru/Citro3D, and additional third-party libraries and prior 3DS work. See [THIRD-PARTY.md](THIRD-PARTY.md) and [platform/3ds/PROVENANCE.md](platform/3ds/PROVENANCE.md) for the detailed source and license/provenance notes.

Third-party components retain their own licenses. Nothing in this repository grants rights to Nintendo game data or ROM contents.
