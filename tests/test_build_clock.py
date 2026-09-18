#!/usr/bin/env python3
"""Regression tests for future ZIP source timestamps and the LUS Ninja gate.

Real CMake/Ninja/C compiler fixtures are used where available, not ARM builds.
Original audio/wizard test assertions are intentionally not changed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_clock as clock
import build_lus_3ds as lus


class ClockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="2ship clock é ")
        self.root = Path(self.tmp.name) / "2Ship3DS"
        self.root.mkdir()
        self.silent = lambda *args: None
        self.future = time.time_ns() + 3 * 3600 * 1_000_000_000

    def tearDown(self):
        self.tmp.cleanup()

    def source(self, relative, data=b"untouched source\r\n", future=True):
        p = self.root / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        if future:
            os.utime(p, ns=(self.future, self.future))
        return p

    def test_repairs_future_inputs_without_byte_changes(self):
        paths = [self.source("CMakeLists.txt"), self.source("cmake/3DS.cmake"),
                 self.source("third_party/libultraship/CMakeLists.txt"),
                 self.source("third_party/2ship/mm/src/audio/lib/playback.c"),
                 self.source("third_party/build-deps/prism/CMakeLists.txt")]
        original = {p: p.read_bytes() for p in paths}
        report = clock.prepare_source_clock(self.root, self.silent)
        self.assertEqual(report["changed_count"], 5)
        for p in paths:
            self.assertEqual(p.read_bytes(), original[p])
            self.assertLessEqual(p.stat().st_mtime_ns, time.time_ns())
        saved = json.loads((self.root / report["journal"]).read_text())
        self.assertTrue(saved["completed"])
        self.assertFalse(saved["source_bytes_modified"])

    def test_past_timestamps_not_touched(self):
        p = self.source("cmake/past.cmake", future=False)
        os.utime(p, ns=(1_000_000_000, 2_000_000_000))
        before = p.stat().st_mtime_ns
        report = clock.prepare_source_clock(self.root, self.silent)
        self.assertEqual(report["changed_count"], 0)
        self.assertEqual(before, p.stat().st_mtime_ns)
        self.assertFalse((self.root / "wizard-logs").exists())

    def test_second_run_is_noop(self):
        p = self.source("CMakeLists.txt")
        clock.prepare_source_clock(self.root, self.silent)
        before = p.stat().st_mtime_ns
        report = clock.prepare_source_clock(self.root, self.silent)
        self.assertEqual(report["changed_count"], 0)
        self.assertEqual(before, p.stat().st_mtime_ns)

    def test_both_old_caches_are_preserved_before_repair(self):
        self.source("CMakeLists.txt")
        for name in ("build-arm", "third_party/libultraship/build-3ds"):
            self.source(name + "/old.o", b"DO NOT DELETE")
        report = clock.prepare_source_clock(self.root, self.silent)
        self.assertEqual(len(report["cache_backups"]), 2)
        self.assertEqual(report["changed_count"], 1)
        for item in report["cache_backups"]:
            self.assertFalse((self.root / item["from"]).exists())
            self.assertEqual((self.root / item["backup"] / "old.o").read_bytes(), b"DO NOT DELETE")
            self.assertEqual((self.root / item["backup"] / "old.o").stat().st_mtime_ns, self.future)

    def test_noop_preserves_existing_cache_location(self):
        self.source("CMakeLists.txt", future=False)
        p = self.source("build-arm/old.o")
        report = clock.prepare_source_clock(self.root, self.silent)
        self.assertEqual(report["changed_count"], 0)
        self.assertTrue(p.exists())

    def test_sdk_archives_saves_and_backups_are_not_touched(self):
        excluded = ["sdk/modules/foo.cmake", "mm.o2r", "platform/3ds/mm.o2r",
                    "platform/3ds/save.sav", "third_party/libultraship/build-3ds.avant-wizard-1/file.cmake",
                    "third_party/libultraship/_deps/generated.cmake", "wizard-logs/test.log"]
        paths = [self.source(name) for name in excluded]
        self.source("CMakeLists.txt")
        report = clock.prepare_source_clock(self.root, self.silent)
        self.assertEqual(report["changed_count"], 1)
        for path in paths:
            self.assertEqual(path.stat().st_mtime_ns, self.future)

    @unittest.skipIf(os.name == "nt", "Creating symlinks may require Windows privileges")
    def test_source_symlinks_are_not_followed(self):
        outside = Path(self.tmp.name) / "external"
        outside.mkdir()
        p = outside / "CMakeLists.txt"
        p.write_text("do not touch")
        os.utime(p, ns=(self.future, self.future))
        (self.root / "third_party").mkdir()
        (self.root / "third_party/link").symlink_to(outside, target_is_directory=True)
        (self.root / "CMakeLists.txt").symlink_to(p)
        report = clock.prepare_source_clock(self.root, self.silent)
        self.assertEqual(report["changed_count"], 0)
        self.assertEqual(p.stat().st_mtime_ns, self.future)

    @unittest.skipIf(os.name == "nt", "Creating symlinks may require Windows privileges")
    def test_linked_cache_is_rejected_before_timestamp_repair(self):
        source = self.source("CMakeLists.txt")
        outside = Path(self.tmp.name) / "external"
        outside.mkdir()
        (self.root / "build-arm").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "Cache externe"):
            clock.prepare_source_clock(self.root, self.silent)
        self.assertEqual(source.stat().st_mtime_ns, self.future)

    def test_all_cache_paths_validated_before_moving_first(self):
        self.source("CMakeLists.txt")
        cache = self.source("build-arm/old.o")
        self.source("third_party/libultraship/build-3ds", b"not a directory", future=False)
        with self.assertRaises(RuntimeError):
            clock.prepare_source_clock(self.root, self.silent)
        self.assertTrue(cache.exists())

    def test_cloud_reparse_points_not_confused_with_junctions(self):
        regular = clock.stat.S_IFREG | 0o644
        p = self.root / "cloud.cmake"
        with patch.object(Path, "lstat", return_value=SimpleNamespace(st_mode=regular, st_reparse_tag=0x9000001A)):
            self.assertFalse(clock.is_link(p))
        with patch.object(Path, "lstat", return_value=SimpleNamespace(st_mode=regular, st_reparse_tag=0xA0000003)):
            self.assertTrue(clock.is_link(p))

    def test_gate_missing_ninja_fails_clearly(self):
        with patch.object(clock.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Ninja introuvable"):
                clock.check_lus_ninja_manifest(self.root, {}, self.silent)

    def test_gate_timeout_is_bounded(self):
        with patch.object(clock.shutil, "which", return_value="ninja"), \
             patch.object(clock.subprocess, "run", side_effect=subprocess.TimeoutExpired("ninja", 30)):
            with self.assertRaisesRegex(RuntimeError, "sans relance"):
                clock.check_lus_ninja_manifest(self.root, {}, self.silent)

    def test_build_lus_checks_clock_then_configures_then_checks_manifest(self):
        for relative in ("imgui/imgui.cpp", "prism/CMakeLists.txt", "monocypher/src/monocypher.c",
                         "threadpool/include/BS_thread_pool.hpp", "stb/stb_image.h"):
            self.source("third_party/build-deps/" + relative, future=False)
        build = self.root / "third_party/libultraship/build-3ds"
        for relative in ("src/libultraship.a", "libImGui.a", "libstb.a", "libmonocypher.a", "_deps/prism-build/libprism.a"):
            self.source(str((build / relative).relative_to(self.root)), b"mock archive", future=False)
        calls = []
        with patch.object(lus, "SOURCE_ROOT", self.root), \
             patch.object(lus, "build_environment", return_value=({"PATH": os.defpath}, Path("cmake"), Path(sys.executable))), \
             patch.object(lus, "prepare_source_clock", side_effect=lambda *a: calls.append("clock")), \
             patch.object(lus, "check_lus_ninja_manifest", side_effect=lambda *a: calls.append("manifest")), \
             patch.object(lus.subprocess, "run", side_effect=lambda cmd, **kw: calls.append("build" if "--build" in cmd else "configure")):
            lus.build_lus(self.root / "sdk")
        self.assertEqual(calls, ["clock", "configure", "manifest", "build"])


@unittest.skipUnless(shutil.which("cmake") and shutil.which("ninja") and shutil.which("cc"),
                     "Real CMake/Ninja/host C compiler needed")
class RealNinjaTests(unittest.TestCase):
    setUp = ClockTests.setUp
    tearDown = ClockTests.tearDown

    def fixture(self):
        source = self.root / "third_party/libultraship"
        source.mkdir(parents=True)
        cmake = source / "CMakeLists.txt"
        cmake.write_text('cmake_minimum_required(VERSION 3.20)\nproject(clock_fixture C)\nadd_executable(clock_fixture main.c)\n')
        (source / "main.c").write_text('int main(void) { return 0; }\n')
        build = source / "build-3ds"
        return source, cmake, build

    def run_command(self, cmd):
        return subprocess.run(list(map(str, cmd)), capture_output=True, text=True, timeout=30)

    def configure(self, source, build):
        result = self.run_command(["cmake", "-S", source, "-B", build, "-G", "Ninja"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_real_historical_100_regeneration_loop_then_fixed_compilation(self):
        source, cmake, build = self.fixture()
        os.utime(cmake, ns=(self.future, self.future))
        self.configure(source, build)
        historical = self.run_command(["cmake", "--build", build])
        self.assertNotEqual(historical.returncode, 0)
        self.assertIn("still dirty after 100 tries", historical.stderr)
        self.assertGreaterEqual(historical.stdout.count("Re-running CMake"), 100)
        self.assertNotIn("Building C object", historical.stdout)
        report = clock.prepare_source_clock(self.root, self.silent)
        self.assertEqual(report["changed_count"], 1)
        self.configure(source, build)
        clock.check_lus_ninja_manifest(build, os.environ.copy(), self.silent)
        fixed = self.run_command(["cmake", "--build", build])
        self.assertEqual(fixed.returncode, 0, fixed.stdout + fixed.stderr)
        self.assertIn("Building C object", fixed.stdout)
        self.assertNotIn("Re-running CMake", fixed.stdout)
        executable = build / ("clock_fixture.exe" if os.name == "nt" else "clock_fixture")
        self.assertEqual(self.run_command([executable]).returncode, 0)
        second = self.run_command(["cmake", "--build", build])
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn("no work to do", second.stdout)
        # Legitimate edits STILL regenerate CMake: never suppress regeneration.
        time.sleep(0.02)
        cmake.write_text(cmake.read_text() + '\nadd_compile_definitions(REAL_CMAKE_EDIT=1)\n')
        edited = self.run_command(["cmake", "--build", build])
        self.assertEqual(edited.returncode, 0, edited.stdout + edited.stderr)
        self.assertIn("Re-running CMake", edited.stdout)
        self.assertIn("Building C object", edited.stdout)

    def test_real_gate_reports_external_future_input_without_mutating_it(self):
        source, cmake, build = self.fixture()
        external = Path(self.tmp.name) / "external sdk.cmake"
        external.write_text("set(TEST_EXTERNAL 1)\n")
        os.utime(external, ns=(self.future, self.future))
        cmake.write_text(cmake.read_text() + f'\ninclude("{external.as_posix()}")\n')
        self.configure(source, build)
        with self.assertRaisesRegex(RuntimeError, "Arret preventif"):
            clock.check_lus_ninja_manifest(build, os.environ.copy(), self.silent)
        diagnostic = (build / "ninja-regeneration-diagnostic.txt").read_text()
        self.assertIn("older than most recent input", diagnostic)
        self.assertIn(str(external), diagnostic)
        self.assertEqual(external.stat().st_mtime_ns, self.future)
        self.assertNotIn("still dirty after 100 tries", diagnostic)


if __name__ == "__main__":
    unittest.main(verbosity=2)
