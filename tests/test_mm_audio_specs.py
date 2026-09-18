#!/usr/bin/env python3
"""Execute MM's real parameter calculation and sample splitter for every spec.

The host harness replaces audio rendering with range-checking doubles. It tests
the 3DS fixed output rate, and reproduces spec 0x13's oversized DMEM update when
the desktop rate policy is used with the native worker's output batches.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from test_mm_3ds_timing_audio import body

ROOT = Path(__file__).resolve().parents[1]
MM = ROOT / "third_party/2ship/mm"


def typedef(source, name):
    end = source.index("} " + name + ";") + len("} " + name + ";")
    return source[source.rindex("typedef struct {", 0, end):end]


def main():
    header = (MM / "include/z64audio.h").read_text(encoding="utf-8")
    heap = body((MM / "src/audio/lib/heap.c").read_text(encoding="utf-8"), "void AudioHeap_Init(void)")
    stubs = (MM / "src/code/stubs.c").read_text(encoding="utf-8")
    synthesis = (MM / "src/audio/lib/synthesis.c").read_text(encoding="utf-8")
    config = (MM / "src/audio/session_config.c").read_text(encoding="utf-8")
    specs = config[config.index("AudioSpec gAudioSpecs"):]
    # Reverb pointers are irrelevant to the parameter calculation. Keep the
    # production table and types intact while supplying opaque pointer values.
    reverb_names = sorted(set(re.findall(r"\breverbSettings[0-9A-F]+\b", specs)))
    parameters = heap[heap.index("    // audio buffer parameters"):heap.index("    // sample dma size")]
    scaling = heap[heap.index("    gAudioCtx.audioBufferParameters.specUnk4 ="):
                   heap.index("    // Determine the maximum allowable")]
    code = r'''
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <iterator>
#include <numeric>
#include <vector>
using u8 = uint8_t; using u16 = uint16_t; using u32 = uint32_t;
using s16 = int16_t; using s32 = int32_t; using f32 = float;
using Acmd = uint64_t;
#define ALIGN16(x) (((x) + 15) & ~15)
#define SAMPLE_SIZE sizeof(s16)
struct ReverbSettings;
''' + typedef(header, "AudioSpec") + "\n" + typedef(header, "AudioBufferParameters") + "\n" + "\n".join(
        "ReverbSettings* " + name + " = nullptr;" for name in reverb_names) + "\n" + specs + r'''
struct SynthesisReverb { bool useReverb; int framesToIgnore, curFrame; };
struct {
    AudioBufferParameters audioBufferParameters;
    int refreshRate = 60;
    void* adpcmCodeBook = nullptr;
    int numSynthesisReverbs = 0;
    SynthesisReverb synthesisReverbs[3]{};
} gAudioCtx;
''' + body(stubs, "s32 osAiSetFrequency(u32 frequency)") + "\nvoid InitParameters(AudioSpec* spec) {\n" + parameters + scaling + r'''
}
std::vector<int> chunks;
s16* outputStart;
int outputSamples;
int scriptUpdates, syncedUpdates;
bool overflow;
void AudioScript_ProcessSequences(int index) {
    assert(index >= 0 && index < gAudioCtx.audioBufferParameters.updatesPerFrame);
    ++scriptUpdates;
}
void AudioSynth_SyncSampleStates(int index) {
    assert(index == syncedUpdates++);
}
void AudioSynth_AddReverbBufferEntry(int samples, int index, int reverb) {
    assert(samples > 0 && index >= 0 && index < 3);
    assert(reverb >= 0 && reverb < 3);
}
Acmd* AudioSynth_ProcessSamples(s16* output, s32 samples, Acmd* commands, s32 index) {
    assert(index == int(chunks.size()));
    // Each stereo channel has 13 ADPCM frames of 16 samples in emulated DMEM.
    if (samples > 13 * 16) overflow = true;
    assert(samples > 0 && output >= outputStart);
    assert(output + samples * 2 <= outputStart + outputSamples * 2);
    std::fill(output, output + samples * 2, s16(0x1234));
    chunks.push_back(samples);
    return commands + 1;
}
''' + body(synthesis, "Acmd* AudioSynth_Update(Acmd* abiCmdStart") + r'''
int main() {
    static_assert(std::size(gAudioSpecs) == 21);
    unsigned checked = 0;
#ifndef __3DS__
    unsigned oversized = 0;
#endif
    for (size_t id = 0; id < std::size(gAudioSpecs); ++id) {
        auto& spec = gAudioSpecs[id];
        assert(spec.unk_04 == 1); // An altered spec requires revisiting the output budget.
        InitParameters(&spec);
        auto& p = gAudioCtx.audioBufferParameters;
#ifdef __3DS__
        assert(p.samplingFreq == 32000 && p.aiSamplingFreq == 32000);
        assert(p.updatesPerFrame == 3 && p.resampleRate == 1.0f);
#else
        assert(p.samplingFreq == spec.samplingFreq && p.aiSamplingFreq == 32006);
#endif
        gAudioCtx.numSynthesisReverbs = spec.numReverbs;
        for (auto& reverb : gAudioCtx.synthesisReverbs) reverb = {true, 2, 0};
        // Include the native worker's 528/544 batches and nearby aligned bounds.
        for (int batch : {512, 528, 544, 560}) {
            s16 guarded[2 + 560 * 2];
            std::fill(std::begin(guarded), std::end(guarded), s16(0x5678));
            outputStart = guarded + 1; outputSamples = batch;
            chunks.clear(); scriptUpdates = syncedUpdates = 0; overflow = false;
            Acmd commands[4]{};
            s32 count = -1;
            Acmd* end = AudioSynth_Update(commands, &count, outputStart, batch);
            assert(end == commands + p.updatesPerFrame && count == p.updatesPerFrame);
            assert(scriptUpdates == p.updatesPerFrame && syncedUpdates == p.updatesPerFrame);
            assert(std::accumulate(chunks.begin(), chunks.end(), 0) == batch);
            assert(guarded[0] == 0x5678 && guarded[batch * 2 + 1] == 0x5678);
#ifdef __3DS__
            assert(!overflow);
#else
            assert(overflow == (id == 0x13));
            oversized += overflow;
#endif
            ++checked;
        }
    }
#ifdef __3DS__
    std::printf("PASS: native 21 specs, %u real splits fit 208-sample DMEM; exact 32000 Hz\n", checked);
#else
    assert(oversized == 4);
    std::printf("PASS: desktop policy preserved; reproduces %u oversized spec0x13 splits\n", oversized);
#endif
}
'''
    compiler = shutil.which(os.environ.get("CXX", "g++"))
    if not compiler:
        raise SystemExit("A host C++ compiler is required (set CXX).")
    with tempfile.TemporaryDirectory(prefix="2ship-audio-specs-", dir=ROOT.parent) as tmp:
        tmp = Path(tmp)
        source = tmp / "audio_specs.cpp"
        source.write_text(code, encoding="utf-8")
        environment = os.environ.copy()
        environment["PATH"] = str(Path(compiler).parent) + os.pathsep + environment.get("PATH", "")
        for native in (False, True):
            binary = tmp / ("specs-native" if native else "specs-desktop")
            if os.name == "nt":
                binary = binary.with_suffix(".exe")
            options = ["-D__3DS__=1"] if native else []
            subprocess.run([compiler, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror",
                            "-Wno-unused-parameter", "-Wno-unused-variable", *options,
                            str(source), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True, env=environment, timeout=20)


if __name__ == "__main__":
    main()
