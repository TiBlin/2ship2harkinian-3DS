#!/usr/bin/env python3
"""Host tests for the English wizard and ROM drag-and-drop orchestration.

These tests use synthetic files only. They do not contain a ROM, do not download
2Ship, do not invoke a Windows executable, and do not build ARM code.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "wizard/rom_drop_build.py"
spec = importlib.util.spec_from_file_location("rom_drop_build", MODULE)
r = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(r)


class RomDropTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="2ship-romdrop-test-")
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_validate_supported_synthetic_rom(self):
        rom = self.root / "synthetic.z64"
        rom.write_bytes(b"SYNTHETIC-ROM-NOT-GAME-DATA" * 400000)  # > 8 MiB
        digest = hashlib.sha1(rom.read_bytes()).hexdigest()
        info = r.validate_rom(rom, {digest: "Synthetic test ROM"})
        self.assertEqual(info["name"], "Synthetic test ROM")
        self.assertEqual(info["sha1"], digest)

    def test_validate_rejects_unknown_rom(self):
        rom = self.root / "unknown.z64"
        rom.write_bytes(b"X" * (8 * 1024 * 1024))
        with self.assertRaises(r.RomDropError):
            r.validate_rom(rom, {"0" * 40: "not this file"})

    def test_safe_extract_rejects_traversal(self):
        archive = self.root / "bad.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("../escape.txt", b"NO")
        with self.assertRaises(r.RomDropError):
            r.safe_extract_zip(archive, self.root / "out")
        self.assertFalse((self.root / "escape.txt").exists())

    def test_release_root_requires_exe_support_and_assets(self):
        kit = self.root / "kit"
        kit.mkdir()
        (kit / "2ship.exe").write_bytes(b"synthetic")
        (kit / "2ship.o2r").write_bytes(b"synthetic")
        (kit / "assets").mkdir()
        self.assertEqual(r.find_release_root(self.root), kit)

    def test_release_api_selects_win64_zip(self):
        fake = {"assets": [
            {"name": "source.zip", "browser_download_url": "https://github.com/a/source.zip"},
            {"name": "2Ship-Test-Win64.zip", "browser_download_url": "https://github.com/a/win.zip"},
        ]}
        with patch.object(r, "http_json", return_value=fake):
            self.assertEqual(r.discover_release_url(), "https://github.com/a/win.zip")

    def test_publish_sd_contains_only_requested_runtime_files_and_backs_up(self):
        dsx = self.root / "a.3dsx"; dsx.write_bytes(b"3DSX")
        mm = self.root / "mm.o2r"; mm.write_bytes(b"MM")
        support = self.root / "2ship.o2r"; support.write_bytes(b"SUPPORT")
        out = self.root / "sd"
        old = out / "old.txt"; old.parent.mkdir(); old.write_bytes(b"KEEP")
        report = {}
        final = r.publish_sd(out, dsx, mm, support, report, log=lambda *_: None)
        self.assertEqual(final, out)
        files = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
        self.assertEqual(files, [
            "3ds/2ship/2ship-3ds.3dsx",
            "3ds/2ship/2ship.o2r",
            "3ds/2ship/mm.o2r",
        ])
        backups = list(self.root.glob("sd.backup-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / "old.txt").read_bytes(), b"KEEP")
        self.assertEqual(len(report["output_files"]), 3)

    def test_output_must_be_named_sd(self):
        a = self.root / "a"; a.write_bytes(b"x")
        with self.assertRaises(r.RomDropError):
            r.publish_sd(self.root / "not-sd", a, a, a, {}, log=lambda *_: None)


class StaticWizardTests(unittest.TestCase):
    def test_launchers_have_drag_drop_route(self):
        for path in (ROOT / "LANCER-WIZARD.bat", ROOT / "START-WIZARD.bat"):
            text = path.read_text(encoding="utf-8")
            self.assertIn("RomDrop-2Ship3DS.ps1", text)
            self.assertIn("ROM-drop mode", text)

    def test_gui_has_no_banner_selector(self):
        text = (ROOT / "Wizard-2Ship3DS.ps1").read_text(encoding="utf-8-sig")
        self.assertNotIn("BannerBox", text)
        self.assertNotIn("Bannière", text)
        self.assertIn("3 · Icon", text)
        self.assertIn("built-in default", text)

    def test_worker_no_longer_accepts_banner_setting(self):
        text = (ROOT / "wizard/build_wizard.py").read_text(encoding="utf-8")
        self.assertNotIn('for key in ("icon", "banner")', text)
        self.assertIn('for key in ("icon",):', text)

    def test_drag_drop_output_is_sd_beside_launcher(self):
        ps1 = (ROOT / "RomDrop-2Ship3DS.ps1").read_text(encoding="utf-8-sig")
        for launcher in (ROOT / "LANCER-WIZARD.bat", ROOT / "START-WIZARD.bat"):
            text = launcher.read_text(encoding="utf-8")
            self.assertIn('set "OUTPUT_ROOT=%~dp0"', text)
            self.assertIn('-OutputRoot "%OUTPUT_ROOT%"', text)
        self.assertIn("Resolve-Path -LiteralPath $OutputRoot", ps1)
        self.assertIn("$output = Join-Path $outputBase 'sd'", ps1)
        self.assertIn("Resolve-Path -LiteralPath $RomPath", ps1)

    def test_gui_user_facing_text_is_english(self):
        text = (ROOT / "Wizard-2Ship3DS.ps1").read_text(encoding="utf-8-sig")
        worker = (ROOT / "wizard/build_wizard.py").read_text(encoding="utf-8")
        forbidden = ("Bannière", "Vérification", "Compilation terminée", "Mode de compilation inconnu",
                     "Choisir", "Erreur", "Résultat")
        for phrase in forbidden:
            self.assertNotIn(phrase, text)
            self.assertNotIn(phrase, worker)

    def test_romdrop_packages_3dsx_only(self):
        text = (ROOT / "wizard/rom_drop_build.py").read_text(encoding="utf-8")
        self.assertIn('"--no-cia"', text)
        self.assertNotIn('SD/cias', text)
        self.assertIn('"2ship-3ds.3dsx"', text)
        self.assertIn('"mm.o2r"', text)
        self.assertIn('"2ship.o2r"', text)

    def test_romdrop_temporary_o2r_files_keep_o2r_extension(self):
        text = (ROOT / "wizard/rom_drop_build.py").read_text(encoding="utf-8")
        self.assertEqual(text.count('with_suffix(".tmp.o2r")'), 2)
        self.assertNotIn('with_suffix(".o2r.tmp")', text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
