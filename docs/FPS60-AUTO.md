# Adaptive 3DS frameskip

The 3DS build can automatically skip **late interpolated presentation frames** while preserving the final render associated with each game tick.

## Design goal

When the renderer keeps up, all scheduled interpolated frames are submitted. When a presentation slot is already too late to be useful, the optional interpolation render can be skipped so the port does not compound its lateness.

## Invariants

The adaptive path is designed so that:

- game logic is not intentionally skipped;
- audio production/update is not intentionally skipped;
- the final render of each simulation tick is retained;
- a skipped frame still consumes its presentation slot instead of advancing the game clock;
- stereo rendering is treated as one frame-level decision rather than skipping only one eye;
- normal interpolated rendering resumes automatically once the renderer is back on schedule.

## User setting

The 3DS graphics settings include **Auto frameskip (3DS)**. It is enabled by default and can be disabled for A/B testing.

## Limit

If the mandatory game update plus mandatory final render is itself too expensive, dropping optional interpolation frames cannot restore 60 FPS. CPU/GPU bottlenecks in required work still need optimization.

Host-side coverage is in `tests/test_mm_3ds_frameskip.py`.
