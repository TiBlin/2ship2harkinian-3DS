# 2Ship3DS Windows Wizard — v1.0.6-EN-ROMDROP

The Windows launcher provides two entry modes. Both use this source tree and an existing devkitPro installation.

## Mode 1 — graphical wizard

Double-click:

```text
START-WIZARD.bat
```

The GUI is entirely in English. It can:

- detect/validate devkitPro and the recommended Python installation;
- choose a clean rebuild or reuse compatible caches;
- validate existing `mm.o2r` and `2ship.o2r` archives;
- optionally copy those archives into the build output;
- optionally select a custom icon;
- build 3DSX and, when enabled in the GUI, the normal packaged outputs;
- preserve prior build caches instead of silently deleting them;
- show live build logs and open the result folder.

The custom **banner selector has been removed**. CIA packaging always uses the built-in default banner. The TitleID and product code are not changed by the wizard.

## Mode 2 — drag a ROM onto the BAT file

Drag exactly one supported Majora's Mask ROM onto:

```text
START-WIZARD.bat
```

`LANCER-WIZARD.bat` is retained as a compatibility alias and behaves the same way.

The launcher switches to automatic ROM-drop mode. It will:

1. resolve the dropped ROM path literally, including spaces and parentheses;
2. validate the ROM against the supported hashes used by 2Ship;
3. obtain/use the Windows 2Ship extractor needed to generate `mm.o2r`;
4. prepare the 3DS-compatible `2ship.o2r` support archive;
5. perform a clean 3DS build;
6. package **3DSX only** — no CIA and no `.3ds` image;
7. publish an SD-ready folder named exactly `sd` next to the launcher.

Output layout:

```text
sd/
└── 3ds/
    └── 2ship/
        ├── 2ship-3ds.3dsx
        ├── mm.o2r
        └── 2ship.o2r
```

Copy the **contents** of `sd` to the root of the SD card.

If an `sd` folder already exists, the worker preserves the previous output before publishing the new one rather than silently overwriting it.

The ROM itself is never copied into `sd`.

## devkitPro

The wizard reuses an existing devkitPro installation. The normal default is:

```text
C:\devkitPro
```

If required build components are missing, the wizard stops with a diagnostic rather than pretending that a build succeeded.

## O2R archives

GUI mode does not extract a ROM. It expects existing compatible archives if you want them copied into the output.

ROM-drop mode generates/prepares the archives automatically from a supported ROM and the matching 2Ship support data.

Renaming a ROM to `.o2r` does not make it a valid O2R archive.

## Logs

Wizard and ROM-drop logs are written below `wizard-logs/`. A failed automated build should be diagnosed from the corresponding `romdrop-*` log before changing the source.

## Validation limits

Host-side tests cover launcher routing, ROM validation logic, safe output publication, archive checks, English GUI configuration, build-clock protection, audio/FPS regressions and the stability-audit cases.

Those tests do **not** replace:

- a full Windows GUI run;
- execution of the official Windows extractor;
- a complete devkitARM link/package run;
- real New Nintendo 3DS hardware testing.
