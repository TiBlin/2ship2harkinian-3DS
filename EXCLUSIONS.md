# Exclusions

Files below are withheld in full. A withheld file can contain valid local additions; exclusion is not a determination about authorship or legal status.

## Candidate-level exclusions

| V2 path | Reason | Baseline evidence |
| --- | --- | --- |
| `cmake/3DS.cmake` | Modified alpha.3 toolchain file; substantial retained baseline blocks. | `cmake/3DS.cmake` |
| `cmake/Setup3DS.cmake` | Modified alpha.3 configuration file; substantial retained baseline blocks. | `cmake/Setup3DS.cmake` |
| `scripts/bin2c.py` | Whole-file content is identical to alpha.3; excluded. | `scripts/bin2c.py` |
| `src/compat3ds/SDL2/SDL_net.h` | Whole-file content is identical to alpha.3; excluded. | `src/compat3ds/SDL2/SDL_net.h` |
| `src/compat3ds/excluded_stubs.cpp` | Whole-file content is identical to alpha.3; excluded. | `src/compat3ds/excluded_stubs.cpp` |
| `src/compat3ds/logging_3ds.cpp` | Whole-file content is identical to alpha.3; excluded. | `src/compat3ds/logging_3ds.cpp` |
| `src/compat3ds/network_stubs.cpp` | Whole-file content is identical to alpha.3; excluded. | `src/compat3ds/network_stubs.cpp` |
| `src/compat3ds/ogg/config_types.h` | New path, but normalized type-definition block matches alpha.3 third_party/libogg/include/ogg/os_types.h. | `third_party/libogg/include/ogg/os_types.h` |
| `src/compat3ds/sleep_3ds.cpp` | Whole-file content is identical to alpha.3; excluded. | `src/compat3ds/sleep_3ds.cpp` |
| `src/mk_gfx_factory.cpp` | Whole-file content is identical to alpha.3; excluded. | `src/mk_gfx_factory.cpp` |
| `src/port3ds/runtime_3ds.cpp` | Explicitly declares derivation from SoH V7; cross-path blocks match alpha.3 tests/soh_3ds_main.cpp. | `tests/soh_3ds_main.cpp` |
| `tests/mono_interpreter_test.py` | New path; shared block-extraction helper matches alpha.3 tests/framebuffer_sampling_test.py. Entire file withheld conservatively. | `tests/framebuffer_sampling_test.py` |
| `tests/stereo_3ds_test.py` | New path; shared block-extraction helper matches alpha.3 tests/framebuffer_sampling_test.py. Entire file withheld conservatively. | `tests/framebuffer_sampling_test.py` |
| `third_party/libultraship/include/lus_3ds_controller.h` | Renamed upstream Controller header, matching alpha.3 at a different path. | `third_party/libultraship/include/libultraship/controller/controldevice/controller/Controller.h`; `third_party/shipwright/libultraship/include/libultraship/controller/controldevice/controller/Controller.h` |

## Excluded groups

| Group | Reason |
| --- | --- |
| `platform/3ds/` | Inherited or mixed 3DS renderer, runtime services, UI, headers and shaders; no implementation files from this tree are included. |
| `third_party/2ship/` | Upstream game/port code and mixed local edits, not a collection of independently established local source files. |
| `third_party/libultraship/` except the three manifest-listed helper headers | Existing library sources and mixed changes are omitted. |
| Other `third_party/` trees | Dependency sources, not claimed as project-original code. |
| `CMakeLists.soh-v7.txt` | Explicit inherited V7 build reference. |
| `patches/2ship-3ds.patch` | Contains existing upstream context/removals plus mixed additions. |
| `tools/`, `romfs/`, game assets, binaries and any packaging artwork | Not part of the selected source subset. Packaging script source is retained, but no generated artwork is bundled. |
| Original `README.md`, `README-BUILD-FR.md`, `THIRD-PARTY.md`, `source-manifest.json` | Describe the full kit and would misleadingly characterize this incomplete subset. Replaced only in the export by scoped documentation and a new manifest. |

## Retained V2 files

- `CMakeLists.txt`
- `build.py`
- `cmake/AudioCodecs3DS.cmake`
- `scripts/build_lus_3ds.py`
- `scripts/package_3ds.py`
- `scripts/prepare_support.py`
- `scripts/verify_port.py`
- `src/port3ds/archive_checks.h`
- `src/port3ds/backend_stubs.cpp`
- `src/port3ds/controls_3ds.cpp`
- `src/port3ds/memory_watch.cpp`
- `tests/mm_actor_stereo_test.py`
- `tests/preflight_archive_test.cpp`
- `tests/preflight_stubs/zip.h`
- `tests/test_2ship_extension_index.py`
- `tests/test_2ship_native_controls.py`
- `tests/test_2ship_preflight.py`
- `tests/test_2ship_scene_eviction.py`
- `tests/test_context_teardown_3ds.py`
- `tests/test_mm_3ds_timing_audio.py`
- `tests/test_mm_adpcm_boundaries.py`
- `tests/test_mm_audio_specs.py`
- `tests/test_mm_control_merge.py`
- `tests/test_mm_mixer_effects.py`
- `third_party/libultraship/include/fast/stereo_3ds.h`
- `third_party/libultraship/include/fast/stereo_resolution_3ds.h`
- `third_party/libultraship/include/ship/utils/transition_trace_3ds.h`

Every retained file is copied without edits. The complete list and checksums are in `MANIFEST.json`.
