#!/usr/bin/env python3
"""Run production ADPCM boundary arithmetic against checked DMEM operations.

The harness extracts the count, offset, decoder dispatch and loop advancement
blocks from AudioSynth_ProcessSample. Rendering and resource loads are doubles;
the boundary guard and arithmetic are the unchanged production source. The
desktop control reproduces the exact invalid address/count captured in V8 GDB.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from test_mm_3ds_timing_audio import body

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = (ROOT / "third_party/2ship/mm/src/audio/lib/synthesis.c").read_text(encoding="utf-8")
    start = source.index("            // Continue processing samples until")
    loop = body(source[start:], "while (numSamplesProcessed != numSamplesToLoadAdj)")
    counts = loop[:loop.index("                // Set parameters based on compression type")]
    offsets = loop[loop.index("                if (synthState->atLoopPoint)"):
                   loop.index("                // Decompress the raw sample")]
    decode_start = loop.index("                // Decompress the raw sample")
    decode = loop[decode_start:loop.index("                if (numSamplesProcessed != 0)", decode_start)]
    advance = loop[loop.index("                if (numSamplesProcessed != 0)", decode_start):]
    code = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
using s16 = int16_t; using s32 = int32_t; using u32 = uint32_t;
using Acmd = uint64_t;
#define SAMPLES_PER_FRAME 16
#define SAMPLE_SIZE sizeof(s16)
#define ALIGN16(x) (((x) + 15) & ~15)
enum { A_CONTINUE = 0, A_INIT = 1, A_LOOP = 2, A_ADPCM_SHORT = 4 };
enum { CODEC_ADPCM = 0, CODEC_S8 = 1, CODEC_SMALL_ADPCM = 3, CODEC_UNK7 = 7 };
enum { DMEM_UNCOMPRESSED_NOTE = 0x570, DMEM_COMPRESSED_ADPCM_DATA = 0x930 };
struct AdpcmLoop { u32 start, loopEnd, count; s16 predictorState[16]; };
struct Buffers { s16 adpcmState[16]; };
struct SynthState { s32 samplePosInt; bool atLoopPoint, stopLoop; Buffers* synthesisBuffers; };
struct Sample { int codec; AdpcmLoop* loop; };
struct Note { struct { struct { bool finished; } bitField0; } sampleState; };
struct BadRange { unsigned addr, bytes; };
unsigned decodeOut, decodeBytes, clearBytes, decodeCalls;
int loopPasses;
bool disabled;
void osSyncPrintf(const char*, ...) {}
void range(unsigned addr, unsigned bytes) {
    if (addr < 0x330 || addr > 0xfb0 || bytes > 0xfb0 - addr) throw BadRange{addr, bytes};
}
void setBuffer(int, uint16_t in, uint16_t out, uint16_t bytes) {
    range(in, 0); decodeOut = out; decodeBytes = bytes;
}
void decodeBuffer(int, s16*) {
    // Actual aADPCMdecImpl writes a 16-sample history prefix, then rounds
    // the requested decode length up to whole 16-sample ADPCM frames.
    range(decodeOut, 32 + ((decodeBytes + 31) & ~31u));
    ++decodeCalls;
}
void moveBuffer(uint16_t from, uint16_t to, int bytes) {
    const unsigned rounded = ALIGN16(bytes);
    range(from, rounded); range(to, rounded);
}
void AudioSynth_ClearBuffer(Acmd*, s32 dmem, s32 bytes) {
    const unsigned rounded = ALIGN16(bytes);
    range(uint16_t(dmem), rounded); clearBytes += rounded;
}
void AudioSynth_DisableSampleStates(s32, s32) { disabled = true; }
void AudioSynth_SetBuffer(Acmd*, s32 flags, s32 in, s32 out, size_t bytes) {
    setBuffer(flags, in, out, bytes);
}
void AudioSynth_S8Dec(Acmd*, s32 flags, s16* state) { decodeBuffer(flags, state); }
#define aSetLoop(pkt, state) ((void)(state))
#define aSetBuffer(pkt, flags, in, out, bytes) setBuffer(flags, in, out, bytes)
#define aADPCMdec(pkt, flags, state) decodeBuffer(flags, state)
#define aDMEMMove(pkt, in, out, bytes) moveBuffer(in, out, bytes)
struct Result { int pos, processed; bool finished; unsigned cleared; };
Result run(int pos, u32 repeat, int requested, int codec, int initialFlags) {
    AdpcmLoop loopValue{3452, 5408, repeat, {}};
    AdpcmLoop* loopInfo = &loopValue;
    Buffers buffers{};
    SynthState state{pos, false, true, &buffers};
    SynthState* synthState = &state;
    Sample sampleValue{codec, loopInfo}; Sample* sample = &sampleValue;
    Note noteValue{}; Note* note = &noteValue;
    Acmd commands[64]{}; Acmd* cmd = commands;
    s32 sampleEndPos = loopInfo->loopEnd;
    s32 numSamplesProcessed = 0, numSamplesToLoadAdj = requested;
    s32 dmemUncompressedAddrOffset1 = 0, dmemUncompressedAddrOffset2;
    s32 numFirstFrameSamplesToIgnore, numSamplesUntilEnd, numSamplesToProcess;
    s32 numSamplesInFirstFrame, numSamplesToDecode, numFramesToDecode;
    s32 numTrailingSamplesToIgnore, numSamplesInThisIteration, skipBytes = 0;
    s32 frameSize = codec == CODEC_SMALL_ADPCM ? 5 : 9;
    s32 sampleDataChunkSize, sampleDataDmemAddr, sampleDataChunkAlignPad = 8;
    s32 flags = initialFlags, updateIndex = 0, noteIndex = 22;
    bool sampleFinished, loopToPoint, finished = false;
    clearBytes = decodeCalls = 0; loopPasses = 0; disabled = false;
''' + counts + r'''
    assert(++loopPasses < 8);
''' + offsets + decode + advance + r'''
    assert(finished == note->sampleState.bitField0.finished && finished == disabled);
    assert(decodeCalls > 0);
    return {state.samplePosInt, numSamplesProcessed, finished, clearBytes};
}
void validCase(int pos, u32 repeat, int requested, int codec, int flags) {
    Result result = run(pos, repeat, requested, codec, flags);
    const int clamped = std::min(pos, 5408);
    const int remaining = 5408 - clamped;
    if (requested >= remaining && repeat == 0) {
        assert(result.finished && result.processed == remaining);
        assert(result.cleared >= unsigned((requested - remaining) * 2));
    } else {
        assert(!result.finished && result.processed == requested);
        const int expected = requested >= remaining ? 3452 + requested - remaining : pos + requested;
        assert(result.pos == expected);
    }
}
int main() {
#ifndef __3DS__
    bool reproduced = false;
    try { run(8280, 0xffffffffu, 93, CODEC_ADPCM, A_CONTINUE); }
    catch (const BadRange&) {
        // Exact aSetBuffer values captured in gdb-v8-bad-adpcm.log.
        assert(decodeOut == 61216 && decodeBytes == 3904);
        reproduced = true;
    }
    assert(reproduced);
    std::puts("PASS: desktop control reproduces V8 DMEM address61216/count3904");
#else
    unsigned checked = 0;
    for (int codec : {CODEC_ADPCM, CODEC_SMALL_ADPCM}) {
        for (int flags : {A_CONTINUE, A_INIT}) {
            for (u32 repeat : {0u, 0xffffffffu}) {
                for (int requested : {1, 8, 16, 93, 184, 352}) {
                    for (int pos : {0, 3452, 5315, 5359, 5360, 5400, 5407, 5408, 5409, 8280}) {
                        validCase(pos, repeat, requested, codec, flags); ++checked;
                    }
                }
            }
        }
    }
    const Result looped = run(8280, 0xffffffffu, 93, CODEC_ADPCM, A_CONTINUE);
    assert(looped.pos == 3545 && looped.processed == 93 && !looped.finished);
    const Result stopped = run(8280, 0, 93, CODEC_ADPCM, A_CONTINUE);
    assert(stopped.pos == 5408 && stopped.finished && stopped.cleared >= 186);
    std::printf("PASS: %u native ADPCM boundary cases; looping, oneshot, normal offsets fit DMEM\n", checked);
#endif
}
'''
    compiler = shutil.which(os.environ.get("CXX", "g++"))
    if not compiler:
        raise SystemExit("A host C++ compiler is required (set CXX).")
    with tempfile.TemporaryDirectory(prefix="2ship-adpcm-boundaries-", dir=ROOT.parent) as tmp:
        tmp = Path(tmp)
        source = tmp / "adpcm_boundaries.cpp"
        source.write_text(code, encoding="utf-8")
        environment = os.environ.copy()
        environment["PATH"] = str(Path(compiler).parent) + os.pathsep + environment.get("PATH", "")
        for native in (False, True):
            binary = tmp / ("native" if native else "desktop")
            if os.name == "nt":
                binary = binary.with_suffix(".exe")
            options = ["-D__3DS__=1"] if native else []
            subprocess.run([compiler, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror",
                            "-Wno-unused-variable", "-Wno-unused-but-set-variable", "-Wno-unused-label",
                            *options, str(source), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True, env=environment, timeout=20)


if __name__ == "__main__":
    main()
