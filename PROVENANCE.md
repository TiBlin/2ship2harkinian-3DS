# Provenance and comparison method

## Exact input archives

| Role | Archive | SHA-256 |
| --- | --- | --- |
| Source | `2SHIP3DS-CORRECTIF-V2-SOURCES.zip` | `1806cc31f4d7f881934fe2efeaad37fba1ee71c8d41d00409ea8ca898234f4c0` |
| Baseline | `soh-3ds-0.1.0-alpha.3.zip` | `41602d1f75cc811d6d778352fc90105c0903af25c3c166ef61366de17c46eca9` |

The source root is `2Ship3DS/`; the baseline root is
`soh-3ds-0.1.0-alpha.3/`. Both ZIP central directories and entry CRCs passed.
The truncated `soh-3ds-0.1.0-alpha.3(3).zip` was **not** used.

## Scope

The source contains 8,873 file entries and the baseline 27,817.
Candidate selection covers project-root build/configuration files, `scripts`,
`src`, `tests`, and four added libultraship headers. Vendored game and library
sources are not assumed to be local work just because they are absent from SOH.
The inherited renderer, its mixed changes, upstream-context patches and assets
are excluded as groups. Thus this is not an exhaustive extraction of all newly
written lines in the full port.

## Checks actually performed

1. Same-relative-path comparisons and whole-file SHA-256 matching across all
   baseline paths, so renamed exact copies are detectable.
2. Cross-path screening against 5,714 baseline text/code files. UTF-8
   decoding with replacement was used for comparison; empty lines were removed
   and remaining lines stripped at both ends. A shared window of six consecutive
   nonempty lines with at least 150 characters was a review trigger.
3. For files with a trigger, line-sequence comparison against up to five
   highest-window-count baseline matches identified the retained blocks. These
   counts are diagnostic, not percentages of originality or effort.
4. Matching or explicitly derived files were withheld as whole files. The
   reworked root `CMakeLists.txt` is retained: it shares short conventional lines
   with the baseline, but triggered no six-line match under the above rule.
5. All 27 retained files were verified byte-for-byte against the V2 source.
   Their Python files passed syntax parsing. The final ZIP was checked for
   integrity, duplicate names and unexpected entries.

## Important limits

The screening does not prove absence of copying. Shorter fragments, rewritten
code, renamed identifiers, restructured algorithms and sources outside the
baseline can evade it. Simple boilerplate, declarations or generic constructs
may still be shared. A helper missed by the threshold is not thereby original.

The source identifies SoH3DS V7 as its direct base. Alpha.3 was deliberately
used instead, as requested. No exact V7 history or complete upstream history was
available to attribute the additions; some retained work may predate the 2Ship
adaptation. There is no conclusion that any percentage belongs to a particular
person or to a coding model.

Mixed files are not made independent merely by removing unchanged lines. No
such fragment extraction was used here. This necessarily withholds potential
original additions in the renderer, runtime, toolchain and upstream patches.

Permission status is carried from the maintainer's supplied context, not from a
new external verification. This archive does not claim publication clearance,
apply a blanket licence or override existing notices.

## Export-only files

`README.md`, `LIRE-MOI.md`, `PROVENANCE.md`, `EXCLUSIONS.md`, `MANIFEST.json`,
`.gitignore` and `CHECKSUMS.sha256` were generated for this export. They are not
counted among the 27 retained V2 files. `CHECKSUMS.sha256` covers every other
packaged file, avoiding a self-referential checksum.
