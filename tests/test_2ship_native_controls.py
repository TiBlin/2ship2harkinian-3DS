#!/usr/bin/env python3
"""Compile the production native control hook and exercise input sequences."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    compiler = shutil.which(os.environ.get("CXX", "g++"))
    if not compiler:
        raise SystemExit("A host C++ compiler is required (set CXX).")
    with tempfile.TemporaryDirectory(prefix="2ship-native-controls-", dir=ROOT.parent) as directory:
        directory = Path(directory)
        stub = directory / "libultraship/bridge/consolevariablebridge.h"
        stub.parent.mkdir(parents=True)
        stub.write_text("#pragma once\n#include <cstdint>\nextern \"C\" {\n"
                        "int32_t CVarGetInteger(const char*, int32_t);\n"
                        "void CVarSetInteger(const char*, int32_t);\nvoid CVarSave();\n}\n", encoding="utf-8")
        harness = directory / "native_controls_test.cpp"
        harness.write_text(r'''
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <string>
#include <unordered_map>
extern "C" void Soh3dsControls_TransformPad(uint32_t, uint16_t*);
static std::unordered_map<std::string, int32_t> variables;
static std::array<unsigned, 14> mappings;
static unsigned saves = 0;
extern "C" int32_t CVarGetInteger(const char* key, int32_t fallback) {
    const auto found = variables.find(key);
    return found == variables.end() ? fallback : found->second;
}
extern "C" void CVarSetInteger(const char* key, int32_t value) { variables[key] = value; }
extern "C" void CVarSave() { ++saves; }
extern "C" unsigned Soh3dsControls_CurrentMappingMask(int index) { return mappings.at(index); }
constexpr uint32_t A=1u, L=1u<<4, R=1u<<5, ZR=1u<<7, Up=1u<<8, Down=1u<<9;
constexpr uint32_t shoulders=L|R, up=shoulders|Up, down=shoulders|Down;
constexpr const char* scale="g3DS.RenderScalePercent";
constexpr const char* convergence="g3DS.ConvergenceMode";
uint16_t poll(uint32_t held, uint16_t pad=0xFFFFu) {
    Soh3dsControls_TransformPad(held, &pad);
    return pad;
}
void reset() {
    poll(0);
    variables.clear(); saves=0;
    mappings.fill(0);
    mappings[0]=0x8000; mappings[4]=0x2000; mappings[5]=mappings[7]=0x0010;
    mappings[8]=0x0008; mappings[9]=0x0004;
}
int main() {
    reset();
    // An ordinary single button or an incomplete chord stays unchanged.
    for (uint32_t held : {A,L,R,Up,Down,shoulders,L|Up,R|Down}) assert(poll(held)==0xFFFFu);
    assert(variables.empty() && saves==0);
    reset();
    assert(poll(up)==uint16_t(0xFFFFu & ~0x2018u));
    assert(variables.at(scale)==70 && saves==1);
    for (int i=0; i<1000; ++i) poll(up);
    assert(variables.at(scale)==70 && saves==1);
    // Shoulders remain consumed after the direction releases, until all four
    // resolution keys release. A fresh direction tap still gives one step.
    assert(poll(shoulders)==uint16_t(0xFFFFu & ~0x2010u));
    poll(up); assert(variables.at(scale)==80 && saves==2);
    poll(0); assert(poll(R)==0xFFFFu);
    for (int i=0; i<10; ++i) { poll(0); poll(up); }
    assert(variables.at(scale)==100 && saves==4);
    for (int i=0; i<20; ++i) { poll(0); poll(down); }
    assert(variables.at(scale)==10 && saves==13);
    poll(0); poll(down); assert(variables.at(scale)==10 && saves==13);
    reset();
    poll(up|Down); assert(variables.empty() && saves==0);
    poll(up); assert(variables.empty() && saves==0); // no replay after conflict
    poll(shoulders); poll(up); assert(variables.at(scale)==70 && saves==1);
    reset();
    assert(poll(ZR)==uint16_t(0xFFFFu & ~0x10u));
    assert(variables.at(convergence)==2 && saves==1);
    for (int i=0; i<1000; ++i) poll(ZR);
    assert(variables.at(convergence)==2 && saves==1);
    poll(0); poll(ZR); assert(variables.at(convergence)==0 && saves==2);
    poll(0); poll(ZR); assert(variables.at(convergence)==1 && saves==3);
    assert(poll(ZR|R)==0xFFFFu); // R retains shared logical mapping
    reset();
    poll(up|ZR);
    assert(variables.at(convergence)==2 && variables.count(scale)==0 && saves==1);
    poll(up); assert(variables.count(scale)==0); // ZR takes priority, no delayed scale change
    poll(shoulders); poll(up); assert(variables.at(scale)==70 && saves==2);
    reset();
    variables[scale]=54; poll(up); assert(variables.at(scale)==60);
    reset();
    variables[convergence]=-200; poll(ZR); assert(variables.at(convergence)==2);
    // Custom mappings are consumed by physical source, not hard-coded N64 keys.
    reset();
    mappings[4]=0x4000; mappings[5]=0x0020; mappings[8]=0x1000;
    assert(poll(up)==uint16_t(0xFFFFu & ~0x5020u));
    mappings[0]=0x4000;
    assert(poll(up|A)==uint16_t(0xFFFFu & ~0x1020u));
    // Unknown mappings do not cause guessed actions to be removed.
    reset(); mappings.fill(0); assert(poll(up)==0xFFFFu);
    reset();
    Soh3dsControls_TransformPad(ZR, nullptr);
    assert(variables.empty() && saves==0);
    poll(ZR); assert(variables.at(convergence)==2 && saves==1);
    std::puts("PASS: native controls defaults, tap/hold edges, bounds, conflict priority, persistence and mapped suppression");
}
''', encoding="utf-8")
        binary = directory / ("native_controls_test.exe" if os.name == "nt" else "native_controls_test")
        subprocess.run([compiler, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror",
                        "-I", str(directory), "-I", str(ROOT / "third_party/libultraship/include"),
                        str(ROOT / "src/port3ds/controls_3ds.cpp"), str(harness), "-o", str(binary)], check=True)
        environment = os.environ.copy()
        environment["PATH"] = str(Path(compiler).parent) + os.pathsep + environment.get("PATH", "")
        result = subprocess.run([str(binary)], env=environment, text=True, capture_output=True)
        if result.returncode:
            print(result.stderr)
            raise subprocess.CalledProcessError(result.returncode, str(binary))
        print(result.stdout.strip())


if __name__ == "__main__":
    main()
