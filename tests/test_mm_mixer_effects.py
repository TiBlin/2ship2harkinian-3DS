#!/usr/bin/env python3
"""Check production MM PCM gain boundaries and the removed OoT opcode.

These are short host arithmetic tests; they do not emulate NDSP or assert
that physical-console audio has been verified. No game assets are needed.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def function(source, signature):
    start = source.index(signature)
    cursor = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[cursor] == "{") - (source[cursor] == "}")
        cursor += 1
    return source[start:cursor]


def main():
    mixer = (ROOT / "third_party/2ship/mm/2s2h/mixer.c").read_text(encoding="utf-8")
    synthesis = (ROOT / "third_party/2ship/mm/src/audio/lib/synthesis.c").read_text(encoding="utf-8")
    gain = function(mixer, "void aHiLoGainImpl(")
    noop = function(synthesis, "void AudioSynth_UnkCmd19(")
    clamp = function(mixer, "static inline int16_t clamp16(")
    code = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
using s32 = int32_t;
struct Acmd { uint32_t words[2]; };
constexpr unsigned kDmemSize = 0xC80;
static int16_t samples[kDmemSize / 2];
#define BUF_S16(addr) (::samples + ((addr) - 0x330) / 2)
#define ROUND_UP_32(v) (((v) + 31) & ~31)
static unsigned legacyOpcodeCalls;
static uint16_t legacyCount, legacyOutput, legacyInput;
void aUnkCmd19Impl(uint8_t, uint16_t count, uint16_t out, uint16_t in) {
    ++legacyOpcodeCalls;
    legacyCount = count; legacyOutput = out; legacyInput = in;
}
#define aUnkCmd19(pkt, a1, a2, a3, a4) aUnkCmd19Impl(a1, a2, a3, a4)
''' + clamp + r'''
#define __3DS__ 1
''' + gain + "\n" + noop + r'''
#undef __3DS__
#define aHiLoGainImpl LegacyHiLoGain
#define AudioSynth_UnkCmd19 LegacyUnkCmd19
''' + gain + "\n" + noop + r'''
#undef aHiLoGainImpl
#undef AudioSynth_UnkCmd19
int main() {
    constexpr uint16_t address = 0x3B0;
    constexpr unsigned offset = (address - 0x330) / 2;
    const int16_t values[] = {-32768, -30000, -16385, -8193, -17, -1,
                             0, 1, 17, 8193, 16385, 30000, 32767};
    unsigned cases = 0;
    for (unsigned count : {0, 1, 15, 16, 31, 32, 33, 352, 368, 384, 400}) {
        for (unsigned gain : {0, 16, 17, 24, 32, 128, 255}) {
            for (unsigned i = 0; i < kDmemSize / 2; ++i)
                samples[i] = values[i % (sizeof(values) / sizeof(values[0]))];
            const auto before = std::to_array(samples);
            const unsigned end = offset + ((count + 31) / 32) * 16;
            aHiLoGainImpl(gain, count, address);
            for (unsigned i = 0; i < before.size(); ++i) {
                int32_t expected = before[i];
                if (i >= offset && i < end) {
                    // Division rounded toward minus infinity is the Q4.4
                    // arithmetic shift, computed separately from production.
                    const int32_t product = int32_t(before[i]) * gain;
                    expected = product < 0 ? -((-product + 15) / 16) : product / 16;
                    expected = std::clamp(expected, -32768, 32767);
                }
                assert(samples[i] == expected);
            }
            ++cases;
        }
    }
    // The unchanged legacy branch reproduces the actual boundary failure:
    // 32 requested bytes alter 64 bytes, including the first canary sample.
    std::fill(std::begin(samples), std::end(samples), int16_t(1000));
    LegacyHiLoGain(32, 32, address);
    assert(samples[offset + 15] == 2000);
    assert(samples[offset + 16] == 2000);
    assert(samples[offset + 32] == 1000);

    Acmd command{{0x12345678, 0xabcdef01}};
    for (unsigned frameSamples : {168, 176, 184, 192, 208}) {
        std::fill(std::begin(samples), std::end(samples), int16_t(1234));
        const auto before = std::to_array(samples);
        legacyOpcodeCalls = 0;
        AudioSynth_UnkCmd19(&command, address, address, frameSamples * 2, 0);
        assert(legacyOpcodeCalls == 0);
        assert(std::equal(std::begin(samples), std::end(samples), before.begin()));
        assert(command.words[0] == 0x12345678 && command.words[1] == 0xabcdef01);
        LegacyUnkCmd19(&command, address, address, frameSamples * 2, 0);
        assert(legacyOpcodeCalls == 1);
        assert(legacyCount == address && legacyOutput == frameSamples * 2 && legacyInput == 0);
        assert(legacyOutput < 0x330); // Legacy call addresses memory before DMEM.
    }
    std::printf("PASS: %u PCM gain vectors with whole-DMEM canaries; 5 MM no-op boundaries; legacy controls fail safely\n",
                cases);
}
'''
    compiler = shutil.which(os.environ.get("CXX", "g++"))
    if not compiler:
        raise SystemExit("A host C++ compiler is required (set CXX).")
    with tempfile.TemporaryDirectory(prefix="2ship-mixer-effects-", dir=ROOT.parent) as tmp:
        tmp = Path(tmp)
        source = tmp / "mixer_effects.cpp"
        binary = tmp / ("mixer_effects.exe" if os.name == "nt" else "mixer_effects")
        source.write_text(code, encoding="utf-8")
        subprocess.run([compiler, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror",
                        "-Wno-unused-parameter", str(source), "-o", str(binary)], check=True)
        env = os.environ.copy()
        env["PATH"] = str(Path(compiler).parent) + os.pathsep + env.get("PATH", "")
        subprocess.run([str(binary)], check=True, env=env, timeout=5)


if __name__ == "__main__":
    main()
