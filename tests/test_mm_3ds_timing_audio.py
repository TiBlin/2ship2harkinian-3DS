#!/usr/bin/env python3
"""Run the production 3DS FPS policy, audio worker and main-thread barrier.

This tests MM audio-update scheduling/sample arithmetic, not NDSP or gameplay.
The C++ function bodies are extracted unchanged from BenPort.cpp, so a copied
implementation cannot accidentally keep this test green after production edits.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def body(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    cursor = opening + 1
    while depth:
        depth += (source[cursor] == "{") - (source[cursor] == "}")
        cursor += 1
    return source[start:cursor]


def main():
    source = (ROOT / "third_party/2ship/mm/2s2h/BenPort.cpp").read_text(encoding="utf-8")
    fps = body(source, "uint32_t OTRGlobals::GetInterpolationFPS()")
    worker = body(source, "void OTRAudio_Thread()")
    audio_start = source.rindex("static struct {", 0, source.index("void OTRAudio_Thread()"))
    audio_end = source.index("} audio;", audio_start) + len("} audio;")
    graphics = body(source, 'extern "C" void Graph_ProcessGfxCommands(Gfx* commands)')
    barrier_start = graphics.index("last_update_rate = R_UPDATE_RATE;") + len("last_update_rate = R_UPDATE_RATE;")
    barrier_end = graphics.index("bool curAltAssets", barrier_start)
    barrier = graphics[barrier_start:barrier_end]
    code = r'''
#define __3DS__ 1
#include <algorithm>
#include <atomic>
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>
#include <mutex>
#include <thread>
#include <vector>
using s16 = int16_t;
using u32 = uint32_t;
int R_UPDATE_RATE = 3;
int32_t requestedRate = 20, matchRefreshRate = 0;
int32_t CVarGetInteger(const char* key, int32_t) {
    return std::strcmp(key, "gMatchRefreshRate") == 0 ? matchRefreshRate : requestedRate;
}
class OTRGlobals { public: uint32_t GetInterpolationFPS(); };
namespace Ship {
enum class AudioBackend { NUL, NATIVE };
struct Audio {
    AudioBackend backend = AudioBackend::NATIVE;
    AudioBackend GetCurrentAudioBackend() { return backend; }
};
struct Context {
    Audio output;
    static Context* GetRawInstance() { static Context context; return &context; }
    Audio* GetAudio() { return &output; }
};
}
void AudioMgr_CreateNextAudioBuffer(s16*, u32);
void AudioPlayer_Play(const uint8_t*, uint32_t);
int AudioPlayer_Buffered();
int AudioPlayer_GetDesiredBuffered();
''' + source[audio_start:audio_end] + "\n" + fps + "\n" + worker + "\nvoid WaitForFrameAudio() {\n" + barrier + "\n}\n" + r'''
std::vector<u32> updates;
unsigned played = 0;
int queueFrames = 0, desiredFrames = 2048;
std::atomic<bool> gameCpuActive{false}, holdSynthesis{false};
std::atomic<bool> synthesisEntered{false}, releaseSynthesis{false};
std::atomic<bool> barrierEntered{false}, barrierReturned{false};
std::mutex observationMutex;
std::condition_variable observationChanged;
void signal(std::atomic<bool>& condition) {
    {
        std::lock_guard<std::mutex> lock(observationMutex);
        condition = true;
    }
    observationChanged.notify_all();
}
void await(const std::atomic<bool>& condition) {
    std::unique_lock<std::mutex> lock(observationMutex);
    const bool complete = observationChanged.wait_for(lock, std::chrono::seconds(2),
        [&condition] { return condition.load(); });
    assert(complete);
}
void AudioMgr_CreateNextAudioBuffer(s16* buffer, u32 samples) {
    assert(!gameCpuActive);
    if (holdSynthesis.exchange(false)) {
        signal(synthesisEntered);
        await(releaseSynthesis);
    }
    assert(samples <= 544);
    std::fill(buffer, buffer + samples * 2, int16_t(0x1234));
    updates.push_back(samples);
}
void AudioPlayer_Play(const uint8_t* buffer, uint32_t bytes) {
    assert(!updates.empty());
    assert(bytes == updates.back() * 2 * sizeof(s16));
    assert(reinterpret_cast<const s16*>(buffer)[updates.back() * 2 - 1] == 0x1234);
    ++played;
}
int AudioPlayer_Buffered() { return queueFrames; }
int AudioPlayer_GetDesiredBuffered() { return desiredFrames; }
void reset(Ship::AudioBackend backend, int updateRate = 3) {
    updates.clear(); played = 0;
    queueFrames = backend == Ship::AudioBackend::NUL ? 2048 : 0;
    desiredFrames = 2048;
    Ship::Context::GetRawInstance()->GetAudio()->backend = backend;
    R_UPDATE_RATE = updateRate;
    audio.processing = false;
    audio.running = true;
    gameCpuActive = holdSynthesis = synthesisEntered = releaseSynthesis = false;
    barrierEntered = barrierReturned = false;
}
void requestTick() {
    {
        std::lock_guard<std::mutex> lock(audio.mutex);
        assert(!audio.processing);
        audio.processing = true;
    }
    audio.cv_to_thread.notify_one();
}
void finishWorker(std::thread& thread) {
    {
        std::lock_guard<std::mutex> lock(audio.mutex);
        audio.running = false;
    }
    audio.cv_to_thread.notify_all();
    thread.join();
}
void runTick(unsigned expectedUpdates) {
    const auto before = updates.size();
    requestTick();
    WaitForFrameAudio();
    assert(!audio.processing);
    assert(updates.size() == before + expectedUpdates);
}
void verifyIdleGamePhase() {
    size_t before;
    {
        std::lock_guard<std::mutex> lock(audio.mutex);
        before = updates.size();
        gameCpuActive = true;
    }
    // Longer than the previous worker's 5 ms autonomous refill interval.
    std::this_thread::sleep_for(std::chrono::milliseconds(25));
    {
        std::lock_guard<std::mutex> lock(audio.mutex);
        assert(updates.size() == before);
        gameCpuActive = false;
    }
}
void verifySamples() {
    const u32 cycle[] = {528, 544, 528};
    assert(played == updates.size());
    for (size_t i = 0; i < updates.size(); ++i) assert(updates[i] == cycle[i % 3]);
}
int main() {
    OTRGlobals globals;
    const std::pair<int32_t, uint32_t> rates[] = {
        {std::numeric_limits<int32_t>::min(), 20}, {-1, 20}, {0, 20}, {19, 20},
        {20, 20}, {29, 20}, {30, 20}, {40, 20}, {59, 20}, {60, 20},
        {120, 20}, {std::numeric_limits<int32_t>::max(), 20}};
    for (const auto& rate : rates) {
        requestedRate = rate.first; matchRefreshRate = 0;
        assert(globals.GetInterpolationFPS() == rate.second);
        assert(60 % globals.GetInterpolationFPS() == 0);
        matchRefreshRate = 1;
        assert(globals.GetInterpolationFPS() == 20);
    }
    reset(Ship::AudioBackend::NUL);
    audio.processing = audio.running = false;
    OTRAudio_Thread();
    assert(updates.empty());
    const std::pair<int, unsigned> tickRates[] = {
        {-100, 1}, {0, 1}, {1, 1}, {2, 2}, {3, 3}, {4, 3},
        {std::numeric_limits<int>::max(), 3}};
    for (auto backend : {Ship::AudioBackend::NUL, Ship::AudioBackend::NATIVE}) {
        for (const auto& rate : tickRates) {
            reset(backend, rate.first);
            std::thread thread(OTRAudio_Thread);
            runTick(rate.second);
            verifyIdleGamePhase();
            runTick(rate.second);
            finishWorker(thread);
            verifySamples();
        }
        for (int rate : {1, 2, 3}) {
            reset(backend, rate);
            std::thread thread(OTRAudio_Thread);
            verifyIdleGamePhase(); // No synthesis before the first tick.
            for (int tick = 0; tick < 180 / rate; ++tick) runTick(rate);
            finishWorker(thread);
            verifySamples();
            uint32_t sum = 0;
            for (auto samples : updates) sum += samples;
            assert(sum == 96000); // Three seconds at exactly 32000 samples/second.
        }
        reset(backend);
        holdSynthesis = true;
        std::thread thread(OTRAudio_Thread);
        requestTick();
        await(synthesisEntered);
        std::thread simulatedMain([] {
            signal(barrierEntered);
            WaitForFrameAudio();
            signal(barrierReturned);
        });
        await(barrierEntered);
        std::this_thread::sleep_for(std::chrono::milliseconds(25));
        assert(!barrierReturned); // Main must stay blocked during synthesis.
        signal(releaseSynthesis);
        await(barrierReturned);
        simulatedMain.join();
        assert(updates.size() == 3);
        verifyIdleGamePhase(); // Safe to run game CPU/destructors after the barrier.
        finishWorker(thread);
        verifySamples();
    }
    std::puts("PASS: 24 FPS cases; null/native per-tick bounds, idle exclusion, blocking barrier, 32000 Hz cadence");
}
'''
    compiler = shutil.which(os.environ.get("CXX", "g++"))
    if not compiler:
        raise SystemExit("A host C++ compiler is required (set CXX).")
    with tempfile.TemporaryDirectory(prefix="2ship-timing-audio-", dir=ROOT.parent) as tmp:
        tmp = Path(tmp)
        source_file = tmp / "timing_audio.cpp"
        binary = tmp / ("timing_audio.exe" if os.name == "nt" else "timing_audio")
        source_file.write_text(code, encoding="utf-8")
        subprocess.run([compiler, "-std=c++20", "-O2", "-pthread", "-Wall", "-Wextra", "-Werror",
                        str(source_file), "-o", str(binary)], check=True)
        environment = os.environ.copy()
        environment["PATH"] = str(Path(compiler).parent) + os.pathsep + environment.get("PATH", "")
        subprocess.run([str(binary)], check=True, env=environment, timeout=20)


if __name__ == "__main__":
    main()
