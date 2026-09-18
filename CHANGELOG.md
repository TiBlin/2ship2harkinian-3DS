# Changelog

## v1.0.6-EN-ROMDROP

GitHub/documentation cleanup and ROM-drop launcher hardening.

- Replaced the project-authored French documentation with English GitHub-ready documentation.
- Added a full English `README.md`, `BUILDING.md`, stability notes, FPS/audio notes and validation notes.
- Added `START-WIZARD.bat` as the English primary launcher; `LANCER-WIZARD.bat` remains as a compatibility alias.
- Kept the wizard GUI entirely in English.
- Custom CIA banner selection remains removed; packaging uses the built-in default banner.
- Hardened drag-and-drop path handling by resolving dropped ROM/output paths literally and stripping only invalid wrapping quotes before resolution.
- Dragging a supported ROM onto the launcher still produces 3DSX-only output in an `sd` folder with `mm.o2r` and `2ship.o2r`.
- Translated remaining user-facing build-clock diagnostics to English.
- Removed generated validation logs, obsolete distribution manifests and historical patch files that embedded the old French wizard UI from the GitHub-ready source package. Reproducible source tests remain under `tests/`.
- Added `.gitignore` and `.gitattributes` suitable for the repository.

No game ROM or generated O2R archive is included.
