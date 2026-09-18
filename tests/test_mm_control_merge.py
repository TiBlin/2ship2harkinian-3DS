#!/usr/bin/env python3
"""Execute the production v7-hook adapter with MM's 32-bit button mask.

The block is extracted and compiled verbatim; only input services are doubled.
This catches truncation, aliasing and loss of MM virtual input bits.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "third_party/libultraship/src/libultraship/controller/controldeck/ControlDeck.cpp"


def main():
    text = SOURCE.read_text(encoding="utf-8")
    start = text.index("    if (Soh3dsControls_TransformPad != nullptr) {")
    opening = text.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    adapter = text[start:end]
    code = r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <initializer_list>
using CONTROLLERBUTTONS_T = uint32_t;
struct Pad { CONTROLLERBUTTONS_T button; uint32_t canary; };
static_assert(sizeof(decltype(Pad::button)) == 4);
uint16_t requestedLow = 0, observedLow = 0;
unsigned calls = 0;
uint32_t Soh3dsControls_ReadPhysicalButtons() { return 0x12345678u; }
void transform(uint32_t physical, uint16_t* buttons) {
    assert(physical == 0x12345678u);
    observedLow = *buttons;
    *buttons = requestedLow;
    ++calls;
}
void (*Soh3dsControls_TransformPad)(uint32_t, uint16_t*) = transform;
void apply(Pad* pad) {
''' + adapter + r'''
}
int main() {
    // Exhaust old N64 states with MM virtual buttons held, replacing low bits.
    for (uint32_t high : {0u, 0x00010000u, 0xA5A50000u, 0xFFFF0000u}) {
        for (uint32_t low = 0; low <= 0xFFFFu; ++low) {
            Pad pad{high | low, 0xBADCAFEu};
            requestedLow = static_cast<uint16_t>(low ^ 0xFFFFu);
            apply(&pad);
            assert(observedLow == low);
            assert((pad.button & 0xFFFF0000u) == high);
            assert((pad.button & 0xFFFFu) == requestedLow);
            assert(pad.canary == 0xBADCAFEu);
        }
    }
    const unsigned expectedCalls = 4 * 65536;
    assert(calls == expectedCalls);
    Soh3dsControls_TransformPad = nullptr;
    Pad untouched{0x81A5B6C7u, 0xBADCAFEu};
    apply(&untouched);
    assert(untouched.button == 0x81A5B6C7u && calls == expectedCalls);
    std::printf("PASS: %u production control-merge states and absent-hook case\n", expectedCalls);
}
'''
    compiler = shutil.which(os.environ.get("CXX", "g++"))
    if not compiler:
        raise SystemExit("A host C++ compiler is required (set CXX).")
    with tempfile.TemporaryDirectory(prefix="2ship-controls-", dir=ROOT.parent) as tmp:
        tmp = Path(tmp)
        source = tmp / "controls_test.cpp"
        binary = tmp / ("controls_test.exe" if os.name == "nt" else "controls_test")
        source.write_text(code, encoding="utf-8")
        subprocess.run([compiler, "-std=c++20", "-O2", "-fstrict-aliasing", "-Wall", "-Wextra", "-Werror",
                        str(source), "-o", str(binary)], check=True)
        environment = os.environ.copy()
        environment["PATH"] = str(Path(compiler).parent) + os.pathsep + environment.get("PATH", "")
        subprocess.run([str(binary)], check=True, env=environment)


if __name__ == "__main__":
    main()
