# 60 FPS presentation target

The 3DS build selects a 60 FPS presentation target through the existing frame-interpolation system.

This does **not** mean that game logic is forced to 60 Hz. The underlying Majora's Mask update cadence remains the authoritative simulation cadence; additional presentation frames are interpolated between game ticks.

The 60 FPS setting is re-selected at launch so an older saved 20/30 FPS presentation setting does not silently keep the port below the intended target.

A 60 FPS target is not a performance guarantee. If the renderer cannot finish the optional interpolated work on time, the adaptive frameskip path described in [FPS60-AUTO.md](FPS60-AUTO.md) can reduce presentation work without intentionally skipping the final render of a game tick.
