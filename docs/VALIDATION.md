# Validation notes

The repository contains host-side regression tests under `tests/`.

Important coverage includes:

- 3DS FPS60 target selection;
- adaptive frameskip invariants;
- MM audio timing and note-address gate behavior;
- ADPCM boundary cases and mixer effects;
- 2Ship 3DS native input/control merging;
- scene eviction and context teardown;
- CRASH26 resource-probe null handling;
- build-clock/CMake regeneration protection;
- Windows wizard logic and ROM-drop orchestration;
- the first stability-audit hardening cases.

Run the normal suite with:

```text
python scripts/verify_port.py
```

Some specialized tests can be launched directly from the repository root.

A passing host suite does not imply that the current source revision has completed:

- a full devkitARM production build;
- Windows GUI end-to-end validation;
- official extractor end-to-end validation;
- SD-card behavior testing;
- NDSP/DSP testing;
- PICA200/GPU testing;
- real New 3DS stability testing.

Treat those as separate validation layers.
