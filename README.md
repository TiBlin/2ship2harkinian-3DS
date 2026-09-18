# 2Ship2Harkinian-3DS

Experimental **New Nintendo 3DS / New Nintendo 3DS XL port of 2Ship2Harkinian**, the Majora's Mask PC port by Harbour Masters.

This project is a work in progress. It is intended for development, testing, and hardware experimentation rather than as a finished or fully compatible release.

## Current status

The port has been brought up on real New Nintendo 3DS hardware and can reach Majora's Mask gameplay.

Current development goals and capabilities include:

- native New 3DS execution;
- `.3dsx` and `.cia` builds;
- native 3DS input and platform integration;
- 3DS-specific rendering;
- functional audio;
- hardware-tested gameplay;
- continued performance and stability work.

The project should currently be considered **experimental / pre-alpha**. Successful boot and gameplay do not imply full-game compatibility.

Known limitations may include:

- unstable behaviour or crashes in untested progression paths;
- scene-specific rendering issues;
- performance drops in demanding scenes or UI paths;
- incomplete validation of menus, transitions, effects, and long play sessions;
- additional New 3DS-specific bugs that have not yet been isolated.

Compatibility with the original Nintendo 3DS / 2DS hardware is **not currently 

## Upstream base

This port is based on **2Ship2Harkinian** by Harbour Masters:

- Upstream project: https://github.com/HarbourMasters/2ship2harkinian
- Current port base used by the build scripts: **2Ship 5.0.1**
- Upstream commit currently referenced by `build.py`: `6bfd6a35a0e0d8900273e61ce85cb038d4f4a528`

2Ship2Harkinian provides the Majora's Mask game-port codebase. This repository adds and adapts the platform-specific work required to run it on New Nintendo 3DS hardware.

## 3DS platform work and soh-3ds

A significant part of the New 3DS platform implementation is adapted from **soh-3ds** by **999sian**:

- soh-3ds: https://github.com/999sian/soh-3ds

The reused portions include 3DS-specific platform and rendering work that was adapted for 2Ship2Harkinian.

999sian explicitly granted permission to use, modify, and redistribute the portions of `soh-3ds` authored by them for this project, including source adaptations and compiled `.3dsx` / `.cia` releases.

The permission request and response are public here:

- https://github.com/999sian/soh-3ds/issues/1
- Permission response: https://github.com/999sian/soh-3ds/issues/1#issuecomment-5727366820

**Full credit for the original soh-3ds 3DS work belongs to 999sian and the relevant contributors.** Existing copyright, attribution, and license notices from upstream components should be preserved.

## Renderer note

The main branch uses the 3DS implementation adapted from `soh-3ds` as its primary platform/rendering base.

Some separate development/debug builds have also used an independently developed experimental renderer named **BlinkyCitro3ds**. Those builds exist for experimentation and comparison and should not be assumed to represent the renderer used by the current main branch unless a release explicitly says so.

## Building

### Requirements

A working Nintendo 3DS homebrew development environment is required, including:

- Python 3;
- devkitPro;
- devkitARM / the 3DS toolchain;
- libctru and the required 3DS libraries;
- CMake;
- Ninja;
- packaging tools such as `3dsxtool`, `makerom`, and `bannertool`.

The build scripts attempt to locate the required tools through the configured devkitPro installation and the project tool directories.

### Build command

From the repository root:

```bash
python build.py --jobs 4
