2Ship3DS v1.0.6 ROM-drop O2R temporary-file fix

Fixes the drag-and-drop failure:
  ERROR: Select an .o2r archive, not a ROM or .otr file: 2ship-3ds-5.0.1.o2r.tmp

Cause:
The support archive was generated to a temporary filename ending in .tmp.
The archive validator intentionally accepts only files whose final suffix is .o2r,
so it rejected the wizard's own temporary file before publishing it.

Fix:
Temporary archives now use names ending in .tmp.o2r, preserving the required .o2r
final suffix while remaining clearly temporary.

Files replaced:
  wizard/rom_drop_build.py
  tests/test_rom_drop_wizard.py

Apply:
Merge this patch ZIP into the root of 2Ship3DS v1.0.6 and allow the two files to
be replaced. Then drag the ROM onto START-WIZARD.bat again.

Validation:
  python -m unittest tests.test_rom_drop_wizard -v
  14/14 tests pass.
