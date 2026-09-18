# 2Ship3DS

Experimental New Nintendo 3DS port of 2Ship2Harkinian / The Legend of Zelda: Majora’s Mask.

## Current development version: Blinky 12
Status: Functional on real New Nintendo 3DS hardware, but still experimental and under heavy optimization.

⸻

## About

2Ship3DS is an experimental port of 2Ship2Harkinian targeting the New Nintendo 3DS family.

The project currently uses BlinkyCitro3ds, a custom rendering backend developed specifically for this port using the native 3DS graphics stack.

The primary goal is to establish a stable native 3DS implementation first, then progressively improve performance and move more rendering work toward efficient PICA200 / Citro3D execution.

This project is still in an early development stage and should not yet be considered a finished or production-quality port.

⸻

## Current Status

The game currently boots and runs on real New Nintendo 3DS hardware.

A hardware test lasting approximately one hour was completed across multiple scenes without a crash.

Gameplay, File Select and scene transitions are functional.

Known startup issue

The title screen is currently not rendered correctly and appears black.

The game is still running during this black screen, and the File Select screen remains accessible.

Therefore, a black screen immediately after startup does not necessarily mean that the game has crashed.

⸻

## Performance

Performance is currently one of the main limitations of the port.

The game is capped at:

20 FPS

This is only an upper limit. Some scenes may run significantly below 20 FPS.

The current performance cost mainly comes from the still-experimental implementation of BlinkyCitro3ds.

Some rendering paths currently involve:

* CPU-side rendering work;
* expensive memory copies;
* synchronization overhead;
* temporary fallback paths;
* incomplete hardware acceleration;
* rendering operations that have not yet been optimized for the PICA200.

These are active development areas.

⸻

## BlinkyCitro3ds

BlinkyCitro3ds is the custom rendering backend being developed for 2Ship3DS.

It is designed specifically around the capabilities and constraints of the Nintendo 3DS GPU and Citro3D.

The renderer is still experimental and currently prioritizes correctness and stability over maximum performance.

Blinky 12

Blinky 12 introduces an experimental conservative occlusion system.

Its purpose is to avoid submitting geometry to the GPU when that geometry can be safely determined to be completely hidden.

The system currently includes:

* conservative occlusion testing for selected static opaque geometry;
* a small 50 × 30 depth grid;
* a limited CPU processing budget;
* skipped GPU submissions for geometry proven to be hidden;
* preservation of actor draw callbacks;
* diagnostic instrumentation.

If visibility cannot be determined with sufficient confidence, the geometry is rendered normally.

This intentionally favors correctness over aggressive culling.

Diagnostic data

Blinky can collect information such as:

* occlusion tests;
* occlusion rejections;
* skipped triangles;
* skipped draw calls;
* CPU time spent performing occlusion;
* GPU submissions;
* frame timing information.

See:

BLINKY-OCCLUSION-12.md

for additional implementation details.

⸻

##Current Known Issues

The following limitations are currently known:

* title screen appears black;
* File Select remains accessible after the black title screen;
* performance can be poor depending on the scene;
* framerate may fall considerably below 20 FPS;
* BlinkyCitro3ds is not yet fully optimized;
* some rendering operations still perform expensive CPU-side work;
* graphical glitches may occur;
* the occlusion system is still experimental;
* hardware behavior may differ between scenes.

Additional bugs are expected at this stage of development.

⸻

## Hardware

This project currently targets:

* New Nintendo 3DS
* New Nintendo 3DS XL
* New Nintendo 2DS XL

The additional CPU performance of the New 3DS family is currently required.

Support for the original Nintendo 3DS / 2DS family is not currently a development target.

⸻

## Installation

Release builds may contain both:

* .3dsx
* .cia

Homebrew Launcher

Copy the supplied SD card files to the appropriate location on your SD card and launch the .3dsx through the Homebrew Launcher.

CIA

Install the supplied .cia using a compatible title manager on a console configured to run homebrew software.

Keep your existing game data and save files in their expected locations.

⸻

## Game Assets

No copyrighted Majora’s Mask game data is distributed with this repository or its releases.

You must provide the required game data yourself from a legally obtained copy where applicable.

This repository contains porting and compatibility work only.

⸻

## Building

2Ship3DS is intended to be built using the Nintendo 3DS development toolchain, including:

* devkitPro
* devkitARM
* libctru
* Citro3D

The port also depends on the upstream 2Ship2Harkinian / libultraship codebase and its associated components.

The build system is still evolving as the port develops.

⸻

## Testing

Hardware testing is especially useful for this project because emulator behavior does not always reproduce the performance characteristics and limitations of a real New Nintendo 3DS.

When reporting a problem, please include:

* console model;
* .3dsx or .cia;
* game location / scene;
* reproduction steps;
* approximate FPS if available;
* frame time if available;
* blinky.log;
* screenshots or video when relevant.

For crashes, please also include the corresponding Luma crash dump when available.

Important

A black screen during the title-screen phase is currently a known rendering issue.

Do not automatically report it as a crash if the game continues to File Select.

⸻

## Development Priorities

Current development work is focused on:

1. improving BlinkyCitro3ds performance;
2. reducing CPU-side rendering overhead;
3. reducing unnecessary memory copies and synchronization;
4. moving more work onto the PICA200 GPU;
5. improving visibility and occlusion handling;
6. fixing remaining rendering issues;
7. improving frame pacing;
8. maintaining stability on real hardware.

The current priority is stable execution first, optimization second.

⸻

## Upstream Projects

2Ship3DS exists because of the work of several upstream projects and communities.

The project builds upon work including:

* 2Ship2Harkinian / HarbourMasters
* Majora’s Mask decompilation project
* libultraship
* devkitPro
* libctru
* Citro3D

Their respective licenses, copyright notices and attribution requirements remain applicable.

⸻
## Credits

2Ship2Harkinian / HarbourMasters

2Ship3DS is based on the architecture and codebase of 2Ship2Harkinian.

Majora’s Mask decompilation

The Majora’s Mask reverse-engineering and decompilation work made projects such as 2Ship2Harkinian possible.

999sian / soh-3ds

Special thanks to 999sian for their work on the Nintendo 3DS port of Ship of Harkinian.

Their project has served as a useful technical reference during development of the 3DS platform work.

Any potential integration of relevant portions of that project’s code is subject to the appropriate permission and licensing requirements.

BlinkyCitro3ds

BlinkyCitro3ds is the custom renderer developed specifically for this port.

⸻

Project Status

2Ship3DS should currently be considered experimental software.

It is already capable of running Majora’s Mask gameplay on real New Nintendo 3DS hardware, but substantial optimization, testing and rendering work remains.

Expect bugs, graphical issues and poor performance in some areas.

Contributions, technical investigation and hardware test results are welcome.
