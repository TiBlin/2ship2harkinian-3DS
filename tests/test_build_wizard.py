#!/usr/bin/env python3
"""Host tests for the wizard. All assets/ELFs generated here are SYNTHETIC.

No game compilation, Windows GUI execution, DSP, or hardware test is implied.
External packaging calls are mocked except in the optional artwork smoke test.
"""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wizard"))
import build_wizard as w
p = w.packager


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="2ship wizard tests é ")
        self.root = Path(self.temp.name)
        self.silent = lambda *args: None

    def tearDown(self):
        self.temp.cleanup()

    def archive(self, version=(5, 0, 1), endian=1, support=False, duplicate=False):
        target = self.root / ("2ship.o2r" if support else "mm.o2r")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as z:
                z.writestr("portVersion", bytes([endian]) + struct.pack(">HHH" if endian else "<HHH", *version))
                z.writestr("synthetic-resource", b"NOT GAME ASSETS; HOST TEST ONLY")
                if duplicate:
                    z.writestr("synthetic-resource", b"DUPLICATE")
                if support:
                    for name in w.ADDITIONS:
                        z.writestr(name, b"SYNTHETIC")
        return target

    def config(self, **updates):
        result = {"devkitpro": str(self.root / "sdk"), "output_base": str(self.root / "output"),
                  "jobs": 4, "mode": "clean", "copy_assets": False, "check_crc": True, "with_cia": True}
        result.update(updates)
        path = self.root / "run.json"
        path.write_text(json.dumps(result), encoding="utf-8-sig")
        return path, result

    def cache(self, source=None, sdk=None, generator="Ninja"):
        build = self.root / "build-arm"
        build.mkdir(exist_ok=True)
        sdk = sdk or self.root / "sdk"
        data = {"CMAKE_HOME_DIRECTORY": str(source or self.root), "CMAKE_CACHEFILE_DIR": str(build),
                "DEVKITPRO": str(sdk), "CMAKE_GENERATOR": generator}
        (build / "CMakeCache.txt").write_text("\n".join(k + ":STRING=" + v for k, v in data.items()))
        return build


class ConfigTests(Fixture):
    def test_bom_and_unicode_path(self):
        path, expected = self.config()
        self.assertEqual(w.read_config(path), expected)

    def test_job_bounds_and_types(self):
        for value in (0, 65, "4", True, 3.5):
            with self.subTest(value=value):
                path, _ = self.config(jobs=value)
                with self.assertRaises(w.WizardError): w.read_config(path)

    def test_invalid_mode(self):
        path, _ = self.config(mode="reuse-any-old-elf")
        with self.assertRaises(w.WizardError): w.read_config(path)

    def test_invalid_bool(self):
        path, _ = self.config(with_cia="false")
        with self.assertRaises(w.WizardError): w.read_config(path)

    def test_empty_output(self):
        path, _ = self.config(output_base="")
        with self.assertRaises(w.WizardError): w.read_config(path)


class ArchiveTests(Fixture):
    def test_mm_major_version_rule(self):
        a = self.archive(version=(5, 9, 9))
        r = w.inspect_archive(a, False, log=self.silent)
        self.assertEqual(r["version"], [5, 9, 9])
        self.assertTrue(r["crc_checked"])
        self.assertFalse(r["semantic_resources_validated"])

    def test_support_full_version(self):
        a = self.archive(version=(5, 1, 0), support=True)
        with self.assertRaises(w.WizardError): w.inspect_archive(a, True, log=self.silent)

    def test_support_expected_version_and_additions(self):
        a = self.archive(support=True)
        r = w.inspect_archive(a, True, log=self.silent)
        self.assertEqual(r["missing_support_resources"], [])

    def test_support_missing_additions_warning(self):
        a = self.archive()
        r = w.inspect_archive(a, True, log=self.silent)
        self.assertEqual(len(r["missing_support_resources"]), 15)

    def test_little_endian(self):
        a = self.archive(endian=0)
        self.assertEqual(w.inspect_archive(a, False, log=self.silent)["version"], [5, 0, 1])

    def test_other_major_rejected(self):
        a = self.archive(version=(9, 0, 1))
        with self.assertRaises(w.WizardError): w.inspect_archive(a, False, log=self.silent)

    def test_invalid_metadata(self):
        for data in (b"", b"\x02" + b"\0"*6, b"\x01" + b"\0"*5):
            with self.subTest(data=data):
                with self.assertRaises(w.WizardError): w.valid_version(data, False)

    def test_renamed_rom_rejected(self):
        a = self.root / "mm.o2r"; a.write_bytes(b"\x80\x37\x12\x40" + bytes(256))
        with self.assertRaises(w.WizardError): w.inspect_archive(a, False, log=self.silent)

    def test_otr_name_rejected(self):
        a = self.archive(); b = a.with_suffix(".otr"); a.rename(b)
        with self.assertRaises(w.WizardError): w.inspect_archive(b, False, log=self.silent)

    def test_duplicate_rejected(self):
        with self.assertRaises(w.WizardError):
            w.inspect_archive(self.archive(duplicate=True), False, log=self.silent)

    def test_crc_corruption_detected(self):
        a = self.archive()
        data = a.read_bytes().replace(b"NOT GAME ASSETS", b"BAD GAME ASSETS", 1)
        a.write_bytes(data)
        with self.assertRaises(w.WizardError): w.inspect_archive(a, False, log=self.silent)

    def test_metadata_only_does_not_claim_crc(self):
        r = w.inspect_archive(self.archive(), False, False, log=self.silent)
        self.assertFalse(r["crc_checked"])
        self.assertEqual(len(r["sha256"]), 64)

    def test_archive_cancellation(self):
        def cancel(): raise w.Cancelled("test cancellation")
        with self.assertRaises(w.Cancelled):
            w.inspect_archive(self.archive(), False, cancel=cancel, log=self.silent)


class CacheTests(Fixture):
    def test_correct_cache_resumes(self):
        self.cache(); w.check_resume(self.root, self.root / "sdk")

    def test_moved_cache_rejected(self):
        self.cache(source=self.root / "old-place")
        with self.assertRaises(w.WizardError): w.check_resume(self.root, self.root / "sdk")

    def test_different_sdk_rejected(self):
        self.cache(sdk=self.root / "old-sdk")
        with self.assertRaises(w.WizardError): w.check_resume(self.root, self.root / "sdk")

    def test_other_generator_rejected(self):
        self.cache(generator="Unix Makefiles")
        with self.assertRaises(w.WizardError): w.check_resume(self.root, self.root / "sdk")

    def test_partial_cache_requires_clean(self):
        a = self.root / "build-arm"; a.mkdir(); (a / "old.o").write_bytes(b"KEEP")
        with self.assertRaises(w.WizardError): w.check_resume(self.root, self.root / "sdk")

    def test_backups_keep_objects(self):
        for build, _ in w.caches(self.root):
            build.mkdir(parents=True); (build / "old.o").write_bytes(b"KEEP")
        report = w.backup_caches(self.root, "test", self.silent)
        self.assertEqual(len(report), 2)
        for record in report:
            self.assertFalse(Path(record["from"]).exists())
            self.assertEqual((Path(record["backup"]) / "old.o").read_bytes(), b"KEEP")

    @unittest.skipIf(os.name == "nt", "Creating symlinks may need Windows privileges")
    def test_symlink_cache_refused(self):
        external = self.root / "elsewhere"; external.mkdir()
        (self.root / "build-arm").symlink_to(external, target_is_directory=True)
        with self.assertRaises(w.WizardError): w.backup_caches(self.root, "test", self.silent)

    def test_project_lock_and_recovery(self):
        with w.project_lock(self.root):
            with self.assertRaises(w.WizardError):
                with w.project_lock(self.root): pass
        with w.project_lock(self.root): pass


class CopyAndAudioTests(Fixture):
    def test_audio_fix_present_and_identical(self):
        self.assertTrue(w.check_audio_fix()["matches_supplied_audio_fix"])

    def test_old_guard_rejected(self):
        source = self.root / w.PLAYBACK; source.parent.mkdir(parents=True)
        source.write_text((ROOT / w.PLAYBACK).read_text().replace(
            '#if !defined(__WIIU__) && !defined(__3DS__)', '#ifndef __WIIU__', 1))
        with self.assertRaises(w.WizardError): w.check_audio_fix(self.root)

    def test_checked_copy_keeps_source(self):
        a = self.archive(); before = a.read_bytes(); dest = self.root / "copie é/mm.o2r"
        w.copy_checked(a, dest, w.digest(a))
        self.assertEqual(dest.read_bytes(), before)
        self.assertEqual(a.read_bytes(), before)

    def test_copy_rejects_source_mutation(self):
        a = self.archive(); h = w.digest(a); a.write_bytes(b"changed")
        with self.assertRaises(w.WizardError): w.copy_checked(a, self.root / "new.o2r", h)

    def test_copy_will_not_overwrite_existing_file(self):
        a = self.archive(); b = self.root / "save.bin"; b.write_bytes(b"SAVE")
        with self.assertRaises(FileExistsError): w.copy_checked(a, b, w.digest(a))
        self.assertEqual(b.read_bytes(), b"SAVE")

    def test_copy_to_self_refused(self):
        a = self.archive()
        with self.assertRaises(w.WizardError): w.copy_checked(a, a, w.digest(a))


class ProcessTests(Fixture):
    def test_subprocess_failure_is_not_retried(self):
        config, opts = self.config(); worker = w.Worker(config, opts); worker.log = self.silent
        with self.assertRaises(w.WizardError): worker.run([sys.executable, "-c", "raise SystemExit(17)"])

    def test_marker_cancels_before_process_starts(self):
        config, opts = self.config(); worker = w.Worker(config, opts)
        worker.cancel_file.write_text("cancel")
        with self.assertRaises(w.Cancelled): worker.run([sys.executable, "-c", "raise SystemExit(0)"])

    def test_timeout_terminates_child(self):
        config, opts = self.config(); worker = w.Worker(config, opts); worker.log = self.silent
        start = time.monotonic()
        with self.assertRaises(w.WizardError):
            worker.run([sys.executable, "-c", "import time; time.sleep(60)"], timeout=0.1)
        self.assertLess(time.monotonic() - start, 10)

    def test_json_status_is_readable(self):
        config, opts = self.config(); worker = w.Worker(config, opts)
        worker.status(stage="Vérification é", status="checked")
        self.assertEqual(json.loads(worker.status_file.read_text())["status"], "checked")


class PipelineTests(Fixture):
    def test_preflight_standard_citro3d_location(self):
        config, opts = self.config()
        sdk = Path(opts["devkitpro"])
        required = ["libctru/include/3ds.h", "libctru/lib/libctru.a",
                    "libctru/include/citro3d.h", "libctru/lib/libcitro3d.a",
                    "portlibs/3ds/include/SDL2/SDL.h", "portlibs/3ds/include/zip.h",
                    "portlibs/3ds/include/zlib.h", "portlibs/3ds/include/tinyxml2.h",
                    "portlibs/3ds/include/spdlog/spdlog.h", "portlibs/3ds/include/nlohmann/json.hpp"]
        required += ["portlibs/3ds/lib/" + name for name in
                     ("libSDL2.a", "libzip.a", "libzlibstatic.a", "libtinyxml2.a", "libspdlog.a")]
        ext = ".exe" if os.name == "nt" else ""
        required += ["devkitARM/bin/arm-none-eabi-gcc" + ext, "devkitARM/bin/arm-none-eabi-g++" + ext]
        required += ["tools/bin/" + name + ext for name in ("picasso", "3dsxtool", "bannertool", "makerom")]
        if os.name == "nt": required += ["msys2/mingw64/bin/cmake.exe", "msys2/mingw64/bin/ninja.exe"]
        for relative in required:
            f = sdk / relative; f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(b"MOCK TOOL OR LIB")
        worker = w.Worker(config, opts); worker.log = self.silent
        def tool(name, dkp): return sdk / "tools/bin" / (name + ext)
        def version(args):
            name = Path(args[0]).name
            if "cmake" in name: return "cmake version 3.26.4"
            if "python" in name: return "Python 3.13.1"
            return "1.12.0"
        with patch.object(w, "build_environment", return_value=({"PATH": "MOCK"}, Path("cmake"), Path("python"))), \
             patch.object(p, "find_tool", side_effect=tool), patch.object(worker, "probe", side_effect=version), \
             patch.object(w.shutil, "which", return_value="ninja"):
            result = worker.preflight()
        self.assertTrue(result["audio_fix"]["guard_detected"])
        self.assertFalse((self.root / "output").exists())
        self.assertFalse((sdk / "citro3d").exists())

    def test_pipeline_stages_without_overwriting_old_result(self):
        config, opts = self.config()
        (self.root / "source-manifest.json").write_text("{}")
        old = self.root / "output/BUILD-OLD"; old.mkdir(parents=True)
        (old / "old-result.3dsx").write_bytes(b"KEEP OLD")
        worker = w.Worker(config, opts); worker.log = self.silent
        audio = {"sha256": "synthetic-test-fingerprint", "guard_detected": True}
        report = {"python_executable": sys.executable, "assets": [], "audio_fix": audio}
        calls = []
        def simulate(command, timeout=7200):
            calls.append(list(map(str, command)))
            if "--no-package" in command:
                elf = self.root / "build-arm/2ship-3ds.elf"; elf.parent.mkdir(parents=True, exist_ok=True)
                elf.write_bytes(b"MOCK ELF; NOT EXECUTABLE")
            else:
                stage = Path(command[command.index("--output") + 1])
                f = stage / "SD/3ds/2ship/2ship-3ds.3dsx"; f.parent.mkdir(parents=True)
                f.write_bytes(b"MOCK 3DSX; NOT EXECUTABLE")
        with patch.object(w, "ROOT", self.root), patch.object(w, "check_audio_fix", return_value=audio), \
             patch.object(worker, "run", side_effect=simulate):
            worker.build(report)
        self.assertEqual(len(calls), 2)
        self.assertIn("--no-package", calls[0])
        self.assertNotIn("--skip-lus", calls[0])
        self.assertEqual((old / "old-result.3dsx").read_bytes(), b"KEEP OLD")
        self.assertEqual(worker.state["status"], "success")
        result = Path(worker.state["output"])
        self.assertTrue((result / "wizard-build-report.json").is_file())
        self.assertFalse(list(result.parent.glob(".incomplet-*")))

    def test_failed_build_never_publishes_ready_folder(self):
        config, opts = self.config()
        worker = w.Worker(config, opts); worker.log = self.silent
        report = {"python_executable": sys.executable, "assets": [], "audio_fix": {"sha256": "MOCK"}}
        with patch.object(w, "ROOT", self.root), patch.object(worker, "run", side_effect=w.WizardError("MOCK FAIL")):
            with self.assertRaises(w.WizardError): worker.build(report)
        self.assertFalse(list((self.root / "output").glob("BUILD-*")))


class PackagingTests(Fixture):
    def test_png_dimensions(self):
        a = self.root / "image.png"
        p.write_art_png(a, 48, 48, "2S", "3DS", 4)
        self.assertEqual(p.checked_artwork(a, "icon"), a)
        with self.assertRaises(RuntimeError): p.checked_artwork(a, "banner")

    def test_compiled_artwork_validation(self):
        a = self.root / "icon.smdh"; a.write_bytes(b"SMDH" + bytes(0x36C0 - 4))
        self.assertEqual(p.checked_artwork(a, "icon"), a)
        b = self.root / "banner.bnr"; b.write_bytes(b"CBMD" + bytes(512))
        self.assertEqual(p.checked_artwork(b, "banner"), b)
        a.write_bytes(b"SMDH")
        with self.assertRaises(RuntimeError): p.checked_artwork(a, "icon")

    def test_bad_png_rejected(self):
        a = self.root / "image.png"; a.write_bytes(b"PNG" + bytes(64))
        with self.assertRaises(RuntimeError): p.checked_artwork(a, "icon")

    def test_no_cia_never_invokes_makerom_and_embeds_smdh(self):
        # A SYNTHETIC ELF HEADER and MOCK 3DSX are used only to exercise orchestration.
        elf = self.root / "fake.elf"
        header = bytearray(52); header[:7] = b"\x7fELF\x01\x01\x01"; struct.pack_into("<HH", header, 16, 2, 40)
        elf.write_bytes(header)
        icon = self.root / "icon.smdh"; icon.write_bytes(b"SMDH" + bytes(0x36C0 - 4))
        banner = self.root / "banner.bnr"; banner.write_bytes(b"CBMD" + bytes(512))
        calls = []
        def find(name, sdk):
            self.assertNotEqual(name, "makerom"); return Path(name)
        def run(command):
            calls.append(list(command))
            Path(command[2]).write_bytes(b"3DSX" + icon.read_bytes())
        with patch.object(p, "find_tool", side_effect=find), patch.object(p, "run", side_effect=run), \
             patch.object(p, "create_artwork", return_value=(icon, banner)):
            result = p.package(elf, self.root / "out", self.root / "sdk", with_cia=False)
        self.assertEqual(len(calls), 1)
        self.assertFalse(result["validation"]["cia_generated"])
        self.assertFalse(list((self.root / "out").rglob("*.cia")))
        self.assertFalse(list((self.root / "out").rglob("*.3ds")))
        self.assertEqual((self.root / "out/SD/3ds/2ship/2ship-3ds.smdh").read_bytes(), icon.read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=2)
