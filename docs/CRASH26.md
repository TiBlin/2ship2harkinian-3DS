# Crash 26 — null resource in the display-list probe

A hardware crash dump was matched byte-for-byte to its corresponding ELF around the faulting instruction.

## Observed failure

The validated call path was:

```text
EnBomjimb_Draw
  -> gSPSegment(segment 0x09, texture path)
    -> ResourceMgr_LoadIfDListByName
      -> GetResourceByName returns an empty shared_ptr
      -> Ship::IResource::GetInitData is called on null
```

The requested resource was:

```text
__OTR__objects/object_cs/object_cs_Tex_00EE20
```

At the crash, the failing method dereferenced a null resource object at `NULL + 4`.

## Immediate hardening

`ResourceMgr_LoadIfDListByName` now checks the resource before calling `GetInitData()`. It also protects missing init metadata and an empty display-list payload.

That prevents the specific null dereference. It does **not** explain why the resource load failed in the first place.

## Diagnostic trace

The diagnostic build can record failures for this resource in:

```text
sdmc:/3ds/2ship/resource-failure-crash26.log
```

The logging budget is bounded so repeated failures do not create an unbounded per-frame SD write path.

## What remains unknown

The original dump alone cannot distinguish among:

- missing archive entry;
- read/extraction failure;
- import/factory failure;
- allocation failure;
- an earlier cache/lifetime problem.

The stability audit addresses several independent resource-system hazards, but none of them should be claimed as the proven root cause of the original missing texture without matching runtime evidence.
