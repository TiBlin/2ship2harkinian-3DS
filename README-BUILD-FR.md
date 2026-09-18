Rebuilding 2Ship 3DS on Windows

This directory contains an experimental Nintendo 3DS port of 2Ship 5.0.1,
featuring the Blinky renderer and native backends. Successful compilation and
container verification do not prove that the game functions correctly on real
hardware. The release test results are documented separately in its user-facing
README.

Reference Sources

The game is based on HarbourMasters/2ship2harkinian, commit
6bfd6a35a0e0d8900273e61ce85cb038d4f4a528, version 5.0.1. Public libraries
retain their original licenses and authorship. The native Blinky modules and the
release 07 build scripts were developed separately. 999sian’s alpha 3 is used
only for provenance comparison.

build.py builds Majora’s Mask using the installed devkitPro SDK. The
LANCER-WIZARD.bat launcher now opens a small PowerShell build frontend.
Its usage is documented in WIZARD-LIRE-MOI.md. Older patches and tests for
removed backends remain archived in release 06, outside these sources.

1. Prepare the Build Toolchain

The commands below use devkitPro installed in C:\devkitPro, which is the path
used in the tested environment. Another installation location can be specified
with --devkitpro; the Python path in the commands must also be adjusted
accordingly.

Use the native Windows tools from C:\devkitPro\msys2\mingw64\bin for CMake,
Ninja, and Python. Python 3.10 or later and CMake 3.26 or later are required.
The versions observed on the build machine are listed in THIRD-PARTY.md.

The ARM toolchain must provide:

* devkitARM/bin/arm-none-eabi-gcc.exe and arm-none-eabi-g++.exe;
* the libctru and citro3d headers and static libraries;
* tools/bin/picasso.exe and tools/bin/3dsxtool.exe;
* under portlibs/3ds/include: SDL2, libzip, zlib, tinyxml2, spdlog, and
    nlohmann/json;
* under portlibs/3ds/lib: libSDL2.a, libzip.a,
    libzlibstatic.a, libtinyxml2.a, libspdlog.a, as well as the CMake
    configuration files installed with these libraries.

These libraries must be compiled for ARM/3DS. MinGW x64 libraries cannot be
used when linking the game. build.py uses an existing SDK installation; it
does not install packages or automatically build missing portlibs libraries.

The V7 build used the following upstream revisions and build options to complete
portlibs/3ds:

Library	Revision	Special options
zlib	v1.3.1	ZLIB_BUILD_EXAMPLES=OFF
libzip	v1.11.4	BZIP2, LZMA, ZSTD, and cryptography providers disabled; tools, tests, examples, and documentation disabled; LIBZIP_DO_INSTALL=ON
nlohmann/json	v3.12.0	JSON_BuildTests=OFF
tinyxml2	11.0.0	tinyxml2_BUILD_TESTING=OFF
spdlog	v1.16.0	SPDLOG_BUILD_EXAMPLE=OFF, SPDLOG_BUILD_TESTS=OFF
SDL2	release-2.32.10	SDL_SHARED=OFF, SDL_STATIC=ON, SDL_TEST=OFF, SDL_TESTS=OFF

To rebuild a missing library from its upstream revision, the common
configuration is:

-G Ninja, -DCMAKE_BUILD_TYPE=Release,
-DCMAKE_POLICY_VERSION_MINIMUM=3.10, -DBUILD_SHARED_LIBS=OFF,
-DCMAKE_TOOLCHAIN_FILE=<sources>/cmake/3DS.cmake,
-DCMAKE_PREFIX_PATH=C:/devkitPro/portlibs/3ds, and
-DCMAKE_INSTALL_PREFIX=C:/devkitPro/portlibs/3ds.

Also define DEVKITPRO=C:/devkitPro.

Build with cmake --build, then install with cmake --install. Build zlib
before libzip. Upstream links are listed in THIRD-PARTY.md.

2. Run the Full Reconstruction

In PowerShell, open the directory containing build.py:

& 'C:\devkitPro\msys2\mingw64\bin\python.exe' .\build.py --devkitpro C:/devkitPro --jobs 4 --output .\dist

The script configures and builds, in order:

1. the local libultraship with Blinky backends, in
    third_party/libultraship/build-3ds;
2. the MM C/C++ sources, renderer, and codecs, in build-arm;
3. the 3DSX, CIA, and CCI containers from the same ELF.

The ImGui, prism, Monocypher, thread-pool, and stb sources are included under
third_party/build-deps. Their configuration is fully offline. Ogg, Vorbis,
Opus, opusfile, and libpng are also built from local source trees.

The makerom and bannertool executables are provided under tools/windows,
together with their licenses and verified fingerprints.

The source kit can be extracted into any other directory: its scripts calculate
paths relative to their own location. No CMake cache or ARM object files are
included.

All sources required for this 3DS target are included; initializing the desktop
2Ship submodules is not necessary.

Offline reconstruction assumes that the SDK and the ARM libraries described in
section 1 are already installed. Their initial installation remains a separate
step.

A complete second build from a newly extracted directory was not performed;
the kit paths and inventory were verified separately.

Useful options:

# Produce only the ELF and 3DSX.
& 'C:\devkitPro\msys2\mingw64\bin\python.exe' .\build.py --devkitpro C:/devkitPro --jobs 4 --no-package
# Reuse LUS after making changes only to the game-side code.
& 'C:\devkitPro\msys2\mingw64\bin\python.exe' .\build.py --devkitpro C:/devkitPro --jobs 4 --skip-lus
# Explicitly repackage an already-built ELF.
& 'C:\devkitPro\msys2\mingw64\bin\python.exe' .\scripts\package_3ds.py --elf .\build-arm\2ship-3ds.elf --output .\dist --devkitpro C:/devkitPro

--skip-lus requires a LUS archive already rebuilt using this source kit. Do
not reuse a SoH binary archive: MM uses a uint32_t button mask, whereas the
older engine uses uint16_t by default. A difference in field width changes
structure layouts and some C++ signatures.

--emulator-safe disables the renderer’s New 3DS CPU speedup call
(osSetSpeedupEnable(true)). libctru-specific startup calls may still occur.
This mode is intended for emulator diagnostics and does not constitute gameplay
validation. The standard configuration remains the default.

3. Locate the Build Outputs

A complete build places, among other files, the following under dist:

* SD/3ds/2ship/2ship-3ds.3dsx and 2ship-3ds.smdh;
* SD/cias/2ship-3ds.cia;
* 2ship-3ds.3ds, a real CCI/NCSD cartridge container;
* 2ship-3ds.elf and package-manifest.json.

build-arm/build-report.json records the result of the build command. The
packaging manifest contains file fingerprints, the TitleID
0004000002534800, and the structural checks that were performed.

This experimental TitleID differs from SoH’s and is not presented as an
officially allocated identifier.

The packager does not embed the ROM or game data inside the containers. The
embedded RomFS contains only a readme file.

The mm.o2r and 2ship.o2r archives must be placed under /3ds/2ship/ on the
SD card. They are handled separately in the user release. The build process does
not regenerate them.

A ROM merely renamed to .o2r, or an MPQ .otr archive, is not compatible.

The mm.o2r included with the initial V1 SD kit was extracted using the
official Windows 2Ship 5.0.1 executable, explicitly passing it a copy of the
compatible ROM:

2ship.exe baserom.z64

The mm-extraction.json report documents this operation.

The support archive must correspond to the source commit used by the port. See
2ship.provenance.json for the resources added relative to the official
release.

The SOURCES kit does not include mm.o2r. To rebuild the support archive from
the official Windows 5.0.1 2ship.o2r, use a separate output path:

python .\scripts\prepare_support.py --base C:\Path\To\Release-5.0.1\2ship.o2r --output .\dist\SD\3ds\2ship\2ship.o2r

The script verifies the fingerprint of the official archive, preserves its
converted resources, and adds the 15 raw resources present in the MM commit. It
also writes a .provenance.json file.

The initial V1 SD kit already includes the corresponding support archive. The
V2 patch contains only the executables; it preserves the existing archives,
settings, and save data.

Technical Checks and Limitations

* ARMv6K, VFPv2, and hard-float ABI, without NEON; game-side calculations are
    built without fast-math.
* cmake/AudioCodecs3DS.cmake builds real Opus/opusfile decoders, without
    HTTP/TLS networking or DRED/OSCE.
* HID input and the lower-screen menu are handled by Blinky. The controller
    bridge tests verify, among other things, preservation of MM command bits.
* The packager verifies the ARM ELF format, metadata, identifiers, and NCCH
    hashes, as well as ExeFS/RomFS identity between the CIA and CCI builds.

To run the maintained regression tests for this MM port, with a host C++
compiler available in PATH or specified through CXX:

python .\scripts\verify_port.py

Tests can also be run individually, for example:

python tests/test_2ship_scene_eviction.py

and

python tests/test_mm_control_merge.py

The compiler used for these tests must be a host compiler, not
arm-none-eabi-g++.

If the sources or toolchain have been moved, start again from a new build
directory: CMake caches contain absolute paths.

Renaming the previous build-arm and
third_party/libultraship/build-3ds directories before rebuilding preserves
the old results while allowing a clean configuration.
