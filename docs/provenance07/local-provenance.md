# Blinky 07 — traitement de la provenance locale

Les scripts et aides natifs listés ci-dessous ont été traités sans importation de code de l’alpha 3.
Les tests encore pertinents ont été conservés et rattachés aux contrats de production ; leurs fonctions MM/LUS extraites gardent leur attribution amont.
Les tests ne sont pas déclarés nouvellement écrits simplement parce que leur runner ou leur point d’extraction a changé.

## Validation

- CMake configure-only succeeded: 816 MM C files and 532 enhancement files
- memory_watch.cpp compiled with devkitARM and -Wall -Wextra -Werror
- Real packaging of saved ELF06 to work/performance07/packager-smoke produced and validated 3DSX/CIA/CCI
- 34 archive gate cases passed
- 13 clock cases passed, including actual 100-regeneration reproduction/recovery and rejection of a future SDK file; only 2 Windows symbolic-link cases skipped (build-clock-full.log)
- Real bannertool PNG and compiled artwork tests passed
- Scene-lifetime and 50,496-resource extension index tests passed
- Six note-address platform controls passed on Windows with actual low-address static storage
- 37 preserved production resource stability cases passed, sanitizers disabled

## Décisions par fichier

| Fichier | Décision | Preuve |
|---|---|---|
| build.py | independent-reimplementation | Phase-based build driver with SDK environment propagation and explicit phase report |
| cmake/3DS.cmake | independent-reimplementation | Independently authored cross-compiler policy using public CMake variables and devkitARM ABI flags |
| cmake/AudioCodecs3DS.cmake | independent-reimplementation | Declarative adapter to upstream Opus/opusfile CMake options with consistent public integer types |
| CMakeLists.txt | independent-reimplementation | Target-based game graph preserving ARM ABI, source selection, codec options, PCH and link dependencies |
| LANCER-WIZARD.bat | independent-reimplementation | Minimal launcher rooted at its own directory; no recursive discovery or legacy wizard worker |
| scripts/build_clock.py | independent-reimplementation | Bounded traversal, prevalidated cache backup plan, incremental repair journal and source race checks |
| scripts/build_lus_3ds.py | independent-reimplementation | BuildTools orchestration with pinned inputs, disconnected FetchContent and archive verification |
| scripts/package_3ds.py | independent-reimplementation | Bounded binary-view validator, staged CLI packaging and new procedural two-sail artwork |
| scripts/prepare_support.py | independent-reimplementation | Digest-gated official resource overlay, temporary ZIP validation and atomic output publication |
| scripts/verify_port.py | independent-reimplementation | Explicit maintained production-test registry, host compiler resolution and failure propagation |
| src/port3ds/archive_checks.h | independent-reimplementation | RAII file/archive ownership, public libzip metadata validation and version-policy gate |
| src/port3ds/memory_watch.cpp | independent-reimplementation | Coherent locked watch-region snapshot, bounded scalar diagnostic writer and intercepted libc guards |
| tests/mm_actor_stereo_test.py | removed-obsolete | Retired SoH/stereo/FPS-worker/wizard implementation or unused test fixture; exact bytes retained in delivery06 source ZIP |
| tests/mono_interpreter_test.py | removed-obsolete | Retired SoH/stereo/FPS-worker/wizard implementation or unused test fixture; exact bytes retained in delivery06 source ZIP |
| tests/preflight_archive_test.cpp | retained-reviewed-test | Local failure-injection fixture validating 34 production archive gate cases and resource cleanup canaries |
| tests/preflight_stubs/zip.h | retained-reviewed-test | Minimal test-only libzip API declarations; signatures and constants derive from public libzip headers |
| tests/stability_audit1/alias_post.cpp | retained-reviewed-test | Local test-only fixture: error injection, canaries, ownership or publication assertions; production code is extracted/linked separately |
| tests/stability_audit1/alias_pre.cpp | retained-reviewed-test | Local test-only fixture: error injection, canaries, ownership or publication assertions; production code is extracted/linked separately |
| tests/stability_audit1/binary.cpp | retained-reviewed-test | Local test-only fixture: error injection, canaries, ownership or publication assertions; production code is extracted/linked separately |
| tests/stability_audit1/fake_3ds.h | removed-obsolete | Retired SoH/stereo/FPS-worker/wizard implementation or unused test fixture; exact bytes retained in delivery06 source ZIP |
| tests/stability_audit1/fake_audio_player.h | removed-obsolete | Retired SoH/stereo/FPS-worker/wizard implementation or unused test fixture; exact bytes retained in delivery06 source ZIP |
| tests/stability_audit1/manager_post.cpp | retained-reviewed-test | Local test-only fixture: error injection, canaries, ownership or publication assertions; production code is extracted/linked separately |
| tests/stability_audit1/manager_pre.cpp | retained-reviewed-test | Local test-only fixture: error injection, canaries, ownership or publication assertions; production code is extracted/linked separately |
| tests/stability_audit1/ndsp_post.cpp | removed-obsolete | Retired SoH/stereo/FPS-worker/wizard implementation or unused test fixture; exact bytes retained in delivery06 source ZIP |
| tests/stability_audit1/pins_post.cpp | retained-reviewed-test | Local test-only fixture: error injection, canaries, ownership or publication assertions; production code is extracted/linked separately |
| tests/stability_audit1/pins_pre.cpp | retained-reviewed-test | Local test-only fixture: error injection, canaries, ownership or publication assertions; production code is extracted/linked separately |
| tests/stability_audit1/xml_post.cpp | retained-reviewed-test | Local test-only fixture: error injection, canaries, ownership or publication assertions; production code is extracted/linked separately |
| tests/stability_audit1/xml_pre.cpp | retained-reviewed-test | Local test-only fixture: error injection, canaries, ownership or publication assertions; production code is extracted/linked separately |
| tests/stereo_3ds_test.py | removed-obsolete | Retired SoH/stereo/FPS-worker/wizard implementation or unused test fixture; exact bytes retained in delivery06 source ZIP |
| tests/test_2ship_extension_index.py | retained-reviewed-test | Retained generated 50,496-resource index, alias priority, prefix and alternate preload checks; PASS |
| tests/test_2ship_native_controls.py | removed-obsolete | Retired SoH/stereo/FPS-worker/wizard implementation or unused test fixture; exact bytes retained in delivery06 source ZIP |
| tests/test_2ship_preflight.py | retained-reviewed-test | Local host compilation runner for real archive gate plus libzip boundary double |
| tests/test_2ship_scene_eviction.py | retained-reviewed-test | Retained live resource-lifetime assertions; extraction marker updated to Blinky scene implementation; PASS |
| tests/test_build_clock.py | retained-reviewed-test | Retained filesystem/cache regressions; native Windows CMake/Ninja tests use normalized diagnostic paths and a 180-second bound only for the deliberate 100-regeneration negative control; 13 pass, 2 symbolic-link tests skip |
| tests/test_build_wizard.py | removed-obsolete | Retired SoH/stereo/FPS-worker/wizard implementation or unused test fixture; exact bytes retained in delivery06 source ZIP |
| tests/test_context_teardown_3ds.py | retained-reviewed-test | Local test compiles production LUS destructor with partially initialized subsystem collaborators |
| tests/test_mm_3ds_fps60.py | removed-obsolete | Retired SoH/stereo/FPS-worker/wizard implementation or unused test fixture; exact bytes retained in delivery06 source ZIP |
| tests/test_mm_3ds_frameskip.py | removed-obsolete | Retired SoH/stereo/FPS-worker/wizard implementation or unused test fixture; exact bytes retained in delivery06 source ZIP |
| tests/test_mm_3ds_timing_audio.py | retained-reviewed-test | Local test extracts production timing/audio operations and asserts bounded sample delivery |
| tests/test_mm_adpcm_boundaries.py | retained-reviewed-test | Local ADPCM range harness with independent checked DMEM operations and historical negative control |
| tests/test_mm_audio_specs.py | retained-reviewed-test | Local 21-spec fixture verifying actual MM synthesis split counts, canaries and platform policies |
| tests/test_mm_crash26_resource_probe.py | retained-reviewed-test | Maintained portable memory/resource contracts supplied by MM subtask, including new BlinkyAbortProcess failure bridge |
| tests/test_mm_mixer_effects.py | retained-reviewed-test | Local PCM gain fixtures compare production output to independent fixed-point arithmetic and whole-DMEM canaries |
| tests/test_mm_note_address_gate.py | retained-reviewed-test | Retained actual ProcessNotes controls; added CXX/root options and fixed PE image-base for real low-address Windows fixtures; six controls PASS |
| tests/test_stability_audit1.py | independent-reimplementation | New runner for 37 current resource contracts; retained relevant fixtures and removed retired SDK/NDSP baseline path |
| tests/test_wizard_artwork.py | retained-reviewed-test | Retained real bannertool roundtrip test, byte-preservation and custom/default distinction; no legacy GUI dependency |
| wizard/build_wizard.py | removed-obsolete | Retired SoH/stereo/FPS-worker/wizard implementation or unused test fixture; exact bytes retained in delivery06 source ZIP |
| Wizard-2Ship3DS.ps1 | independent-reimplementation | Direct SDK Python dispatcher for build and maintained verification commands |
| patches/2ship-3ds.patch | remove-obsolete | Historical patch or test references removed SoH/stereo/FPS-worker/wizard implementation; maintained production regressions preserved |
| patches/mm-3ds-auto-frameskip.patch | remove-obsolete | Historical patch or test references removed SoH/stereo/FPS-worker/wizard implementation; maintained production regressions preserved |
| patches/mm-3ds-fps60.patch | remove-obsolete | Historical patch or test references removed SoH/stereo/FPS-worker/wizard implementation; maintained production regressions preserved |
| patches/mm-3ds-note-address-gate.patch | remove-obsolete | Historical patch or test references removed SoH/stereo/FPS-worker/wizard implementation; maintained production regressions preserved |
| patches/stability-audit1-runtime.patch | remove-obsolete | Historical patch or test references removed SoH/stereo/FPS-worker/wizard implementation; maintained production regressions preserved |
| patches/stability-audit1-wizard.patch | remove-obsolete | Historical patch or test references removed SoH/stereo/FPS-worker/wizard implementation; maintained production regressions preserved |
| patches/wizard-packager.patch | remove-obsolete | Historical patch or test references removed SoH/stereo/FPS-worker/wizard implementation; maintained production regressions preserved |
| patches/wizard-v1.0.2-clock-fix.patch | remove-obsolete | Historical patch or test references removed SoH/stereo/FPS-worker/wizard implementation; maintained production regressions preserved |

Les SHA-256 avant/après et les références publiques sont dans `local-provenance.json`.
La comparaison de fichiers complets avec l’alpha 3 est une aide de revue, pas un certificat juridique d’originalité.
Le build global et les nouveaux binaires de livraison restent à valider par l’agent principal.
