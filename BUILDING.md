# Building 2Ship3DS on Windows

This repository contains an experimental New Nintendo 3DS build of 2Ship 5.0.1. A successful compile or container validation does not prove that the resulting build is stable on hardware.

## Reference source

- 2Ship2Harkinian source: commit `6bfd6a35a0e0d8900273e61ce85cb038d4f4a528`, declared source version `5.0.1`.
- `CMakeLists.txt` is the active Majora's Mask 3DS build definition.
- `CMakeLists.soh-v7.txt` is retained only as a historical/reference build description; it is not the active root CMake file.
- The 3DS build uses the local `third_party/libultraship` tree included in this repository.

## 1. Toolchain requirements

The tested layout uses devkitPro at:

```text
C:\devkitPro
```

The build expects:

- `devkitARM/bin/arm-none-eabi-gcc.exe`
- `devkitARM/bin/arm-none-eabi-g++.exe`
- libctru and Citro3D headers/libraries
- `tools/bin/picasso.exe`
- `tools/bin/3dsxtool.exe`
- Windows-native Python, CMake and Ninja; the devkitPro MSYS2 `mingw64` copies are recommended
- ARM/3DS portlibs for SDL2, libzip, zlib, tinyxml2, spdlog and nlohmann/json

The portlibs must be built for ARM/3DS. MinGW x64 libraries cannot be linked into the game.

Recommended minimum host tools:

- Python 3.10+
- CMake 3.26+
- Ninja

See [THIRD-PARTY.md](THIRD-PARTY.md) for the versions observed in the development environment.

## 2. Full build

From PowerShell in the repository root:

```powershell
& 'C:\devkitPro\msys2\mingw64\bin\python.exe' .\build.py --devkitpro C:/devkitPro --jobs 4 --output .\dist
```

The build performs these stages:

1. configure/build the local 3DS libultraship tree in `third_party/libultraship/build-3ds`;
2. configure/build the Majora's Mask port in `build-arm`;
3. create the 3DSX and, unless packaging is disabled, the other configured 3DS containers from the same ELF.

No CMake cache or ARM object files are required from another machine. If the source directory was moved, use a clean build because CMake caches contain absolute paths.

## 3. Useful options

Build the game/ELF/3DSX without full packaging:

```powershell
& 'C:\devkitPro\msys2\mingw64\bin\python.exe' .\build.py --devkitpro C:/devkitPro --jobs 4 --no-package
```

Reuse a matching existing libultraship build after a game-only change:

```powershell
& 'C:\devkitPro\msys2\mingw64\bin\python.exe' .\build.py --devkitpro C:/devkitPro --jobs 4 --skip-lus
```

Do **not** use `--skip-lus` after modifying libultraship, the stability fixes, or any ABI-sensitive shared definitions.

Package an already-built ELF explicitly:

```powershell
& 'C:\devkitPro\msys2\mingw64\bin\python.exe' .\scripts\package_3ds.py --elf .\build-arm\2ship-3ds.elf --output .\dist --devkitpro C:/devkitPro
```

`--emulator-safe` prevents the renderer from enabling the New 3DS CPU speedup service. It is a diagnostic option for emulator compatibility, not a gameplay validation mode.

## 4. Expected outputs

A full package normally includes files such as:

```text
dist/
├── 2ship-3ds.elf
├── package-manifest.json
└── SD/
    ├── 3ds/
    │   └── 2ship/
    │       ├── 2ship-3ds.3dsx
    │       └── 2ship-3ds.smdh
    └── cias/
        └── 2ship-3ds.cia
```

The experimental TitleID used by the packager is `0004000002534800`, with product code `CTR-P-2SH3`. It is a local homebrew identifier, not a registered allocation.

## 5. Game archives

The source tree does not contain a ROM or `mm.o2r`.

On the SD card, compatible archives belong in:

```text
/3ds/2ship/mm.o2r
/3ds/2ship/2ship.o2r
```

A renamed ROM, `.otr`/MPQ file, or arbitrary ZIP is not a substitute for an O2R archive.

To prepare the support archive from the official Windows 5.0.1 `2ship.o2r` into a separate output:

```powershell
python .\scripts\prepare_support.py --base C:\Path\To\Release-5.0.1\2ship.o2r --output .\dist\SD\3ds\2ship\2ship.o2r
```

The ROM drag-and-drop workflow can automate both the game archive and support archive preparation; see [WIZARD-README.md](WIZARD-README.md).

## 6. Timestamp/CMake protection

ZIP timestamp/timezone mismatches previously caused Ninja to regenerate CMake indefinitely because source files appeared to be in the future. `scripts/build_clock.py` now checks build inputs before configuration, preserves existing caches when a repair is required, normalizes only future-dated source mtimes, and verifies that the libultraship Ninja manifest is stable before the build proceeds.

See [docs/CMAKE-NINJA-TIMESTAMP-FIX.md](docs/CMAKE-NINJA-TIMESTAMP-FIX.md).

## 7. Host-side regression tests

Run the port verification suite with a host C++ compiler available in `PATH` (or set with `CXX`):

```powershell
python .\scripts\verify_port.py
```

Individual tests can also be executed directly, for example:

```powershell
python .\tests\test_mm_3ds_frameskip.py
python .\tests\test_mm_note_address_gate.py --require-fixed
python .\tests\test_stability_audit1.py
python .\tests\test_rom_drop_wizard.py
```

Host tests validate specific contracts and regression cases. They do not substitute for ARM, DSP, GPU, SD-card, or real-console testing.

## 8. Clean rebuild advice

After a toolchain move, source relocation, ABI change, renderer change, audio change or libultraship change, preserve then replace these directories rather than trying to reuse them blindly:

```text
build-arm
third_party/libultraship/build-3ds
```

The wizard's **Clean rebuild** mode performs this preservation automatically.
