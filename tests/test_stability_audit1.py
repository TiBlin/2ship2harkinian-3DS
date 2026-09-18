#!/usr/bin/env python3
"""Maintained MM/LUS ownership, binary-boundary, metadata and publication tests.

This original runner executes production functions with retained local test
fixtures. The retired SoH/NDSP baseline runner is archived in delivery06.
Blinky audio regressions are run separately by test_blinky_backends.py.
"""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "alias": ("invalid-metadata", "no-alias", "valid"),
    "pins": ("grass-lifetime", "ramp-lifetime", "grass-missing", "ramp-missing", "grass-short", "ramp-short", "ramp-disabled"),
    "binary": ("bulk-oob", "alloc-oob", "uint32-oob", "empty", "failed-cursor", "null-input", "write-accounting",
               "overflow", "valid-binary", "texture-v0-short", "texture-v1-short", "texture-v0-dimension",
               "texture-v1-dimension", "texture-v0-zero", "texture-v1-zero", "texture-v0-valid", "texture-v1-valid"),
    "manager": ("publication", "transient-read", "transient-import", "absent", "cache-hit", "late-failure", "destructor-lock"),
    "xml": ("null-document", "no-root", "root-present"),
}


def extract(source, declaration):
    begin = source.index(declaration)
    end = source.index("{", begin) + 1
    nesting = 1
    while nesting and end < len(source):
        nesting += (source[end] == "{") - (source[end] == "}")
        end += 1
    if nesting:
        raise ValueError("Unclosed production function: " + declaration)
    return source[begin:end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=ROOT)
    parser.add_argument("--cxx", default=os.environ.get("CXX", "g++"))
    parser.add_argument("--groups", nargs="+", choices=CASES, default=list(CASES))
    parser.add_argument("--sanitizers", action="store_true", help="Require host ASan/UBSan")
    parser.add_argument("--no-sanitizers", action="store_true", help="Compatibility option: default mode is functional checks")
    args = parser.parse_args()
    if args.sanitizers and args.no_sanitizers:
        parser.error("Choose one instrumentation mode")
    compiler = shutil.which(args.cxx)
    if not compiler:
        parser.error("Set CXX or --cxx to a host C++ compiler")
    root = args.root.resolve()
    fixtures = Path(__file__).resolve().parent / "stability_audit1"
    lus = root / "third_party/libultraship"
    env = dict(os.environ)
    env["PATH"] = str(Path(compiler).parent) + os.pathsep + env.get("PATH", "")
    manager = (lus / "src/ship/resource/ResourceManager.cpp").read_text(encoding="utf-8")
    loader = (lus / "src/ship/resource/ResourceLoader.cpp").read_text(encoding="utf-8")
    gfx = (root / "third_party/2ship/mm/2s2h/Enhancements/GfxPatcher/AuthenticGfxPatches.cpp").read_text(encoding="utf-8")
    bodies = {
        "manager": extract(manager, "std::shared_ptr<IResource> ResourceManager::LoadResourceProcess(const ResourceIdentifier&") +
                   extract(manager, "std::shared_ptr<IResource> ResourceManager::PublishResourceLoad("),
        "alias": extract(loader, "std::shared_ptr<ResourceInitData> ResourceLoader::ResolveMetaAlias("),
        "xml": extract(loader, "std::shared_ptr<ResourceInitData>\nResourceLoader::ReadResourceInitDataXml("),
        "pins": extract(gfx, "static void* BlinkyPinPatchResource(") + extract(gfx, "void PatchGeometrySeams(") +
                extract(gfx, "void GfxPatcher_ApplyFierceDeityGIPatch("),
    }
    total = 0
    with tempfile.TemporaryDirectory(prefix="blinky-resource-contracts-") as temporary:
        work = Path(temporary)
        include = work / "include/spdlog"
        include.mkdir(parents=True)
        (include / "spdlog.h").write_text("#pragma once\n" + "\n".join(
            "#define SPDLOG_" + level + "(...) ((void)0)" for level in ("TRACE", "INFO", "WARN", "ERROR", "DEBUG", "CRITICAL")), encoding="utf-8")
        flags = [compiler, "-std=c++20", "-g", "-O1", "-pthread", "-DAUDIT_FIXED",
                 "-I", str(work / "include"), "-I", str(lus / "include")]
        if args.sanitizers:
            flags += ["-fsanitize=address,undefined", "-fno-sanitize-recover=all", "-fno-omit-frame-pointer"]
        for group in args.groups:
            executable = work / (group + (".exe" if os.name == "nt" else ""))
            if group == "binary":
                units = [fixtures / "binary.cpp"] + [lus / "src" / file for file in (
                    "ship/utils/binarytools/Stream.cpp", "ship/utils/binarytools/MemoryStream.cpp",
                    "ship/utils/binarytools/BinaryReader.cpp", "ship/resource/Resource.cpp",
                    "ship/resource/ResourceFactoryBinary.cpp", "fast/resource/factory/TextureFactory.cpp",
                    "fast/resource/type/Texture.cpp")]
            else:
                source = work / (group + ".cpp")
                source.write_text((fixtures / (group + "_pre.cpp")).read_text(encoding="utf-8") +
                                  bodies[group] + (fixtures / (group + "_post.cpp")).read_text(encoding="utf-8"), encoding="utf-8")
                units = [source]
            subprocess.run([*flags, *map(str, units), "-o", str(executable)], env=env, check=True, timeout=60)
            for case in CASES[group]:
                subprocess.run([str(executable), case], env=env, check=True, timeout=15)
                total += 1
                print(f"PASS {group}/{case}", flush=True)
    print(f"PASS {total} production resource cases; sanitizers={'enabled' if args.sanitizers else 'disabled'}; host only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())