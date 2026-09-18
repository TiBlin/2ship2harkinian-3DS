# 3DS audio note-address gate fix

## Problem

`AudioPlayback_ProcessNotes` inherited an N64 address heuristic that rejected a `SequenceLayer` when its pointer value was below `0x7FFFFFFF`. On a native 3DS process, that numeric range is not a valid way to distinguish an N64 address from a real native pointer.

A valid native layer could therefore be skipped before ADSR, vibrato/portamento and `AudioPlayback_InitSampleState` updates. `AudioSynth_SyncSampleStates` could then clear `needsInit` without the intended state reaching the synthesis slice.

## Fix

The address gate remains excluded on Wii U and is now also excluded on 3DS:

```c
#if !defined(__WIIU__) && !defined(__3DS__)
```

The threshold, note bodies, `NO_LAYER` sentinel and behavior of other platforms are unchanged.

## What this fix does not change

It does not alter:

- the renderer;
- stereo rendering;
- game logic;
- save data;
- audio sample rate or PCM format;
- NDSP buffer count;
- the 528/544/528 production cadence;
- mixer gain behavior;
- the audio mutex/barrier model.

## Regression test

`tests/test_mm_note_address_gate.py --require-fixed` extracts the relevant production logic into a host-side harness. The negative control reproduces the old skipped-update behavior; the fixed variant verifies that ADSR/vibrato/sample-state initialization are reached for a valid low native address.

This is a control-flow regression test. It is not a full PCM, ARM ABI or hardware-audio validation.
