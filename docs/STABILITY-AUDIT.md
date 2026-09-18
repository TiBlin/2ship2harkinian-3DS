# Stability audit — first hardening pass

**Source line:** `1.0.4-STABILITY-AUDIT1` and later wizard revisions.

This was a targeted review of high-risk paths rather than a line-by-line review of the entire game. It does **not** certify the port as stable.

The inspected areas included libultraship resource loading/cache publication, O2R-backed binary input, texture factories, persistent graphics commands, scene eviction, skeleton/resource consumers, save writing, context teardown, NDSP audio, the FPS60/adaptive-presentation path and Citro3D texture retirement.

## Fixed groups

### A01 — MemoryStream range checking

The old read path could validate only the first byte and then copy `length` bytes beyond the end of the backing buffer. The fixed path validates the complete range before allocation/copy and avoids overflow in `position + length` style checks.

Write-size bookkeeping and growth-overflow checks were hardened at the same time.

### A02 — zero-copy texture payload validation

Texture factories could publish an `ImageData` pointer without proving that the declared payload length fit inside the source buffer. Dimensions could also be narrowed without an explicit range check.

The fixed path validates dimensions and the full payload range before publishing the zero-copy pointer while retaining the owning image buffer.

### A03 — concurrent resource-cache publication

Two threads could both miss the cache, load the same key independently and publish different resource owners. A consumer could retain a raw pointer into the object that lost the race.

Publication is now canonicalized under the resource mutex so concurrent callers converge on one published owner. Temporary load failures are also kept distinct from a proven permanent absence.

### A04 — persistent graphics commands holding evictable raw pointers

Two persistent graphics commands retained raw addresses into scene resources after the owner could be evicted. Host-side AddressSanitizer reproduction demonstrated use-after-free behavior in the pre-fix path.

The fixed path retains strong ownership for the exact resources used by those persistent commands and validates the referenced ranges.

### A05 — cache report lifetime

A reporting path could retain `string_view` values after releasing the lock that protected the underlying cache entries. Eviction could invalidate the referenced strings while formatting continued.

The report now keeps the appropriate protection for the lifetime of the borrowed strings and guarantees a valid empty output.

### A06 — NDSP close/flush handling

`Buffered()` could continue across an interleaved close, and a failed cache flush was not treated as a reason to avoid submitting the wave buffer.

The backend now uses an atomic initialized/closing state, re-checks state under the buffer lock, and does not submit a block after a failed flush.

The sample rate, PCM format, buffer pool and producer cadence were not changed by this hardening.

### A07 — XML and `.meta` null handling

Missing XML documents/root nodes/metadata could be dereferenced. Invalid `.meta` alias data could also replace a usable original path.

The fixed path fails explicitly on missing metadata and keeps the original path when an alias is invalid.

## Important unresolved risks

### Save-file replacement is not yet transaction-safe

The existing save path writes the final file directly. A simulated short write demonstrated that an I/O failure can leave the old save replaced by a truncated file without a reliable error being surfaced.

Before calling the port stable, save writes should use a transactional pattern such as:

1. write a separate temporary file;
2. flush/close and verify success;
3. optionally validate the serialized data;
4. replace/promote the destination only after the new file is complete;
5. recover predictably after interruption.

Back up real save files before testing experimental builds.

### Required resources still need end-to-end failure semantics

A local null check is enough to avoid one dereference, but some animation/skeleton/scene/sequence callers still assume a required resource exists. A required load failure should abort the corresponding initialization path cleanly rather than allow partially initialized state to continue.

### Teardown and cache edge cases remain

Additional work is still warranted around worker teardown ordering, metadata-cache synchronization, ARM32 size checks and graphics-cache allocation failure paths.

## Validation scope

The hardening tests use host-compiled production functions or tightly scoped extracted functions with explicit test doubles. AddressSanitizer/UndefinedBehaviorSanitizer are used where applicable.

Those tests prove specific regressions and contracts; they do not prove global stability, real-memory pressure, DSP behavior or GPU behavior on a New Nintendo 3DS.
