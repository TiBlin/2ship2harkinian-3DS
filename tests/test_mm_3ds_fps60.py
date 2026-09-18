#!/usr/bin/env python3
"""FPS60 profile regression: real source functions, host-only collaborators.

Extracts the constructor's render CVar statement, GetInterpolationFPS,
RunCommands, Graph_ProcessGfxCommands and OTRAudio_Thread from BenPort.cpp.
The audio worker/barrier run on real host threads. Window, interpolation,
CVar storage, synthesis and backend are explicit doubles: no ARM/PCM/GPU/FPS
performance claim. The same FPS policy is also compiled without __3DS__.

Usage: python tests/test_mm_3ds_fps60.py [PROJECT_ROOT]
The unmodified v1.0.2 must FAIL this profile test (default target was 20).
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def function(source: str, signature: str) -> str:
    start = source.index(signature)
    opening = source.index("{", start)
    cursor, depth = opening + 1, 1
    while depth and cursor < len(source):
        depth += (source[cursor] == "{") - (source[cursor] == "}")
        cursor += 1
    if depth:
        raise RuntimeError(f"Unbalanced function: {signature}")
    return source[start:cursor]


PRELUDE = r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <condition_variable>
#include <cstdint>
#include <cstdio>
#include <limits>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>
using s16 = int16_t;
using u32 = uint32_t;
struct Gfx {};
struct Mtx {};
struct MtxF {};
int R_UPDATE_RATE = 3;
std::map<std::string, int32_t> vars;
int32_t CVarGetInteger(const char* key, int32_t fallback) {
    auto it = vars.find(key);
    return it == vars.end() ? fallback : it->second;
}
void CVarSetInteger(const char* key, int32_t value) { vars[key] = value; }
void CVarRegisterInteger(const char* key, int32_t value) { vars.emplace(key, value); }
#define CVAR_VSYNC_ENABLED "gVsync"
namespace Ship {
struct Window {
    virtual ~Window() = default;
    uint32_t refreshRate = 75;
    uint32_t GetCurrentRefreshRate() { return refreshRate; }
    bool CanDisableVerticalSync() { return true; }
};
struct ResourceManager { void SetAltAssetsEnabled(bool) { assert(false); } };
struct Context {
    std::shared_ptr<Window> window;
    ResourceManager resources;
    static Context* current;
    static Context* GetRawInstance() { return current; }
    std::shared_ptr<Window> GetWindow() { return window; }
    ResourceManager* GetResourceManager() { return &resources; }
};
Context* Context::current = nullptr;
}
namespace Fast {
struct Interpreter { int mInterpolationIndex = 0; float mInterpolationT = 0; };
struct Fast3dWindow : Ship::Window {
    std::shared_ptr<Interpreter> interpreter = std::make_shared<Interpreter>();
    std::vector<float> frames;
    unsigned eventTicks = 0;
    int target = 0;
    void HandleEvents() { ++eventTicks; }
    std::weak_ptr<Interpreter> GetInterpreterWeak() { return interpreter; }
    void SetTargetFps(int rate) { target = rate; }
    void DrawAndRunGraphicsCommands(Gfx*, const std::unordered_map<Mtx*, MtxF>&) {
        frames.push_back(interpreter->mInterpolationT);
    }
};
}
class OTRGlobals {
public:
    static OTRGlobals* Instance;
    std::shared_ptr<Ship::Context> context;
    uint32_t GetInterpolationFPS();
};
OTRGlobals* OTRGlobals::Instance = nullptr;
namespace UIWidgets {
enum Colors { LightBlue };
std::map<Colors, int> ColorValues{{Colors::LightBlue, 0}};
}
constexpr int ImGuiCol_TitleBgActive = 0;
namespace ImGui {
void PushStyleColor(int, int) {}
void PopStyleColor() {}
}
std::vector<float> interpolationSteps;
std::unordered_map<Mtx*, MtxF> FrameInterpolation_Interpolate(float time) {
    interpolationSteps.push_back(time);
    return {};
}
bool debuggerActive = false;
bool GfxDebuggerIsDebugging() { return debuggerActive; }
bool prevAltAssets = false;
void gfx_texture_cache_clear() { assert(false); }
void PlayerCustomFlipbooks_Patch() { assert(false); }
namespace SOH { namespace SkeletonPatcher { void UpdateSkeletons() { assert(false); } } }
std::vector<u32> audioBlocks;
unsigned submissions = 0;
void AudioMgr_CreateNextAudioBuffer(s16* samples, u32 count) {
    assert(count <= 544);
    std::fill(samples, samples + count * 2, int16_t(0x1234));
    audioBlocks.push_back(count);
}
void AudioPlayer_Play(const uint8_t* samples, uint32_t bytes) {
    assert(!audioBlocks.empty());
    assert(bytes == audioBlocks.back() * 2 * sizeof(s16));
    assert(reinterpret_cast<const s16*>(samples)[bytes / sizeof(s16) - 1] == 0x1234);
    ++submissions;
}
'''

NATIVE_MAIN = r'''
int main() {
    OTRGlobals globals;
    OTRGlobals::Instance = &globals;
    globals.context = std::make_shared<Ship::Context>();
    Ship::Context::current = globals.context.get();
    auto window = std::make_shared<Fast::Fast3dWindow>();
    globals.context->window = window;

    vars.clear();
    assert(globals.GetInterpolationFPS() == 60); // absent CVar fallback
    const int32_t saved[] = {-1, 0, 20, 30, 40, 59, 60, 120,
                            std::numeric_limits<int32_t>::max()};
    for (int32_t rate : saved) {
        for (int32_t match : {0, 1}) {
            vars = {{"gInterpolationFPS", rate}, {"gMatchRefreshRate", match}, {"unrelated", 123}};
            SeedNativeRenderProfile();
            assert(CVarGetInteger("gInterpolationFPS", -1) == 60);
            assert(globals.GetInterpolationFPS() == 60);
            assert(vars["unrelated"] == 123);
            assert(vars["gMatchRefreshRate"] == match);
        }
    }
    vars.clear();
    SeedNativeRenderProfile();
    assert(globals.GetInterpolationFPS() == 60);
    for (const auto& [requested, expected] : std::vector<std::pair<int32_t, uint32_t>>{
        {-1, 20}, {0, 20}, {20, 20}, {30, 30}, {40, 30}, {59, 30},
        {60, 60}, {61, 60}, {120, 60}, {360, 60}, {2147483647, 60}}) {
        vars["gInterpolationFPS"] = requested;
        assert(globals.GetInterpolationFPS() == expected);
    }
    SeedNativeRenderProfile();
    for (int updateRate : {1, 2, 3}) {
        R_UPDATE_RATE = updateRate;
        window->frames.clear(); window->eventTicks = 0;
        interpolationSteps.clear(); audioBlocks.clear(); submissions = 0;
        audio.processing = false;
        audio.running = true;
        std::thread worker(OTRAudio_Thread);
        for (int tick = 0; tick < 60 / updateRate; ++tick) {
            const auto beforeFrames = window->frames.size();
            const auto beforeAudio = audioBlocks.size();
            Graph_ProcessGfxCommands(nullptr); // includes the production barrier
            assert(!audio.processing);
            assert(window->target == 60);
            assert(R_UPDATE_RATE == updateRate);
            assert(window->frames.size() == beforeFrames + updateRate);
            assert(audioBlocks.size() == beforeAudio + updateRate);
            for (int frame = 0; frame < updateRate; ++frame) {
                const float expected = static_cast<float>(frame + 1) / updateRate;
                assert(std::fabs(window->frames[beforeFrames + frame] - expected) < 1e-6f);
            }
        }
        {
            std::lock_guard<std::mutex> lock(audio.mutex);
            audio.running = false;
        }
        audio.cv_to_thread.notify_one();
        worker.join();
        assert(window->eventTicks == static_cast<unsigned>(60 / updateRate));
        assert(window->frames.size() == 60);
        assert(interpolationSteps.size() == static_cast<unsigned>(60 - 60 / updateRate));
        assert(audioBlocks.size() == 60 && submissions == 60);
        unsigned total = 0;
        const u32 cycle[] = {528, 544, 528};
        for (size_t i = 0; i < audioBlocks.size(); ++i) {
            assert(audioBlocks[i] == cycle[i % 3]);
            total += audioBlocks[i];
        }
        assert(total == 32000);
        std::printf("PASS R_UPDATE_RATE=%d: %d logic submissions, 60 render submissions, "
                    "60 audio blocks, 32000 sample frames (simulated second)\n", updateRate, 60 / updateRate);
    }
    std::puts("PASS FPS60: absent default, 18 saved-setting combinations, session rate changes and upper cap");
}
'''

DESKTOP_MAIN = r'''
int main() {
    OTRGlobals globals;
    auto context = std::make_shared<Ship::Context>();
    context->window = std::make_shared<Fast::Fast3dWindow>();
    Ship::Context::current = context.get();
    vars.clear();
    assert(globals.GetInterpolationFPS() == 20);
    vars["gVsync"] = 0;
    vars["gInterpolationFPS"] = 120;
    assert(globals.GetInterpolationFPS() == 120);
    vars["gVsync"] = 1;
    assert(globals.GetInterpolationFPS() == 75);
    vars["gMatchRefreshRate"] = 1;
    assert(globals.GetInterpolationFPS() == 75);
    std::puts("PASS non-3DS: default 20, uncapped desktop 120, vsync and refresh matching unchanged");
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    source = (args.root / "third_party/2ship/mm/2s2h/BenPort.cpp").read_text(encoding="utf-8")
    ctor = function(source, "OTRGlobals::OTRGlobals()")
    start = ctor.index("context->InitConsoleVariables();")
    end = ctor.index("auto controlDeck", start)
    native_setup = ctor[start:end]
    assert "#ifdef __3DS__" in native_setup
    seed = re.findall(r'CVar(?:Set|Register)Integer\("gInterpolationFPS",\s*[^;]+;', native_setup)
    if len(seed) != 1:
        raise RuntimeError("Expected exactly one native FPS initialization statement")
    fps = function(source, "uint32_t OTRGlobals::GetInterpolationFPS()")
    worker = function(source, "void OTRAudio_Thread()")
    audio_start = source.rindex("static struct {", 0, source.index("void OTRAudio_Thread()"))
    audio_end = source.index("} audio;", audio_start) + len("} audio;")
    run = function(source, "void RunCommands(")
    graph = function(source, 'extern "C" void Graph_ProcessGfxCommands(Gfx* commands)')
    compiler = shutil.which(os.environ.get("CXX", "g++"))
    if not compiler:
        raise RuntimeError("Host C++ compiler required (set CXX or install g++)")
    # No renderer hooks in this nominal-load harness: their weak references
    # must disable skipping. Copy declarations from production, not stub bodies.
    hooks = "\n".join(line for line in source.splitlines()
                      if line.startswith('extern "C" ') and
                      any(name in line for name in ("Soh3dsFrameBehind(", "Soh3dsFrameDropped(")))
    code_native = PRELUDE + "\n" + hooks + "\nvoid SeedNativeRenderProfile() {\n" + seed[0] + "\n}\n" + fps + "\n"
    code_native += source[audio_start:audio_end] + "\n" + worker + "\n" + run + "\n" + graph + "\n" + NATIVE_MAIN
    code_desktop = PRELUDE + fps + "\n" + DESKTOP_MAIN
    with tempfile.TemporaryDirectory(prefix="2ship-fps60-") as tmp:
        base = Path(tmp)
        for label, code, defines in [("native", code_native, ["-D__3DS__=1"]),
                                     ("desktop", code_desktop, [])]:
            cpp, exe = base / (label + ".cpp"), base / (label + ".exe")
            cpp.write_text(code, encoding="utf-8")
            subprocess.run([compiler, "-std=c++20", "-O1", "-pthread", *defines, str(cpp), "-o", str(exe)],
                           check=True, timeout=60)
            subprocess.run([str(exe)], check=True, timeout=20)


if __name__ == "__main__":
    main()
