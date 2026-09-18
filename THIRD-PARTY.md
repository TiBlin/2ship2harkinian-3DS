# Third-party components and provenance

Original licenses remain in the corresponding component directories. This file documents the main source origins used by the port; it does not replace those licenses and grants no rights to ROM or game data.

## Core project components

| Component | Source used | License / notice |
| --- | --- | --- |
| 2Ship2Harkinian | `HarbourMasters/2ship2harkinian`, commit `6bfd6a35a0e0d8900273e61ce85cb038d4f4a528`, source version `5.0.1` | `third_party/2ship/LICENSE`, CC0-1.0 |
| libultraship | Local source tree adapted for the 3DS target; upstream origin `kenix3/libultraship` | `third_party/libultraship/LICENSE`, MIT |
| 3DS PICA200/Citro3D platform work | Local 3DS platform tree with provenance documented separately | See `platform/3ds/PROVENANCE.md` and retained source notices |

The 3DS build explicitly uses `third_party/libultraship`. The desktop submodule declaration present in the upstream 2Ship repository is not the library used by this target.

## Source-built dependencies

| Component | Version / revision | Provenance and license |
| --- | --- | --- |
| ImGui | `v1.91.9b-docking` with the local libultraship compatibility patch | `ocornut/imgui`; MIT license under `third_party/build-deps/imgui/` |
| prism | `1de054450e7b3c5f777d2e3dfcb228ad120c329d` | `KiritoDv/prism-processor`; MIT |
| thread-pool | `v4.1.0` | `bshoshany/thread-pool`; license in `third_party/build-deps/threadpool/` |
| Monocypher | `0d85f98c9d9b0227e42cf795cb527dff372b40a4` | `LoupVaillant/Monocypher`; BSD-2-Clause / CC0-1.0 options |
| stb_image | source corresponding to `0bc88af4de5fb022db643c2d8e549a0927749354` | `nothings/stb`; notice embedded in header |
| libogg | `1.3.6` | Xiph.Org; `third_party/libogg/COPYING` |
| libvorbis / vorbisfile | `1.3.7` | Xiph.Org; `third_party/libvorbis/COPYING` |
| Opus | local pinned source copy | Xiph.Org; `third_party/opus/COPYING` and `LICENSE_PLEASE_READ.txt` |
| opusfile | local pinned source copy | Xiph.Org; `third_party/opusfile/COPYING` |
| libpng | `1.6.58`, commit `3061454d980de7d53608f594194cfac722721d2a` | `pnggroup/libpng`; `third_party/libpng/LICENSE` |
| dr_wav / dr_mp3 / dr_flac | `0.14.6` / `0.7.4` / `0.13.4` | `mackron/dr_libs`; notices in headers and `third_party/dr_libs/LICENSE` |

The local dependency sources are built for the 3DS target; host x64 static libraries are not reused for the ARM link.

## Observed 3DS SDK/toolchain versions

These are development-environment observations, not universal requirements:

| Item | Observed version |
| --- | --- |
| devkitARM | package `r68-1`, GCC `16.1.0` |
| ARM binutils | `2.46.0-1` |
| ARM newlib | `4.6.0.20260123-5` |
| libctru | `2.7.0-1` |
| Citro3D | `1.7.1-2` |
| Citro2D | `1.7.0-1` |
| picasso | `2.7.2-3` |
| 3dstools / 3dsxtool | package `1.3.1-3` |
| Native Windows CMake | `4.4.3` |
| Native Windows Ninja | `1.13.2` |
| Native Windows Python | `3.14.7` |
| SDL2 ARM headers | `2.32.10` |
| zlib ARM headers | `1.3.1` |
| libzip ARM headers | `1.11.4` |
| tinyxml2 ARM headers | `11.0.0` |
| spdlog ARM headers | `1.16.0` |
| nlohmann/json | `3.12.0` |

Primary SDK projects include devkitPro, libctru, Citro3D, Citro2D and 3dstools. Portlibs include SDL2, zlib, libzip, tinyxml2, spdlog and nlohmann/json.

## Packaging tools

- `makerom 0.19.0` — Project_CTR; license retained in `tools/LICENSE-makerom.txt`.
- `bannertool 1.2.3` — 3DS bannertool; license retained in `tools/LICENSE-bannertool.txt`.
- Binary provenance and hashes are recorded in `tools/provenance.json`.

The default icon/banner artwork produced by `scripts/package_3ds.py` consists of original geometric text/rectangles and silent banner audio. No Zelda or SoH artwork is reused for those generated package assets.

## Game resource archives

`mm.o2r` is generated from a compatible ROM supplied by the user. `2ship.o2r` is a support archive derived from the official 2Ship release and prepared for this source revision by `scripts/prepare_support.py`.

These archives are separate from the source repository and are not bundled here. Their redistribution conditions are distinct from the source-code licenses.
