#!/usr/bin/env python3
"""Auto-frameskip regression using extracted production C++ functions.

RunCommands, Graph_ProcessGfxCommands, the real audio worker/barrier, both
renderer skip hooks and EndFrame's pacing block are compiled on the host.
The LCD clock, command submission, interpolator, CVar storage and synthesis
are explicit doubles. This is NOT ARM, GPU, PCM or real-time validation.

Usage: python tests/test_mm_3ds_frameskip.py [PROJECT_ROOT]
Optional environment: CXX=clang++ or g++; no SDK/download required.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def load_helpers():
    spec = importlib.util.spec_from_file_location(
        "fps60_test_helpers", Path(__file__).with_name("test_mm_3ds_fps60.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MOCK_PACER = r'''
uint32_t simulatedVblank = 0;
uint32_t clockReads = 0;
uint32_t renderCost = 0;
uint32_t matrixCost = 0;
int currentTarget = 60;
std::vector<int> drawIndices;
std::vector<int> drawTargets;
extern "C" int Soh3dsTargetFps(void) { return currentTarget; }
uint32_t C3D_FrameCounter(int id) { assert(id == 0); ++clockReads; return simulatedVblank; }
uint64_t svcGetSystemTick() { return static_cast<uint64_t>(simulatedVblank) * 1000; }
void gspWaitForAnyEvent() { ++simulatedVblank; }
'''

MAIN = r'''
void ResetPacing(uint32_t now = 100, uint32_t deadline = 0, uint32_t period = 0) {
    simulatedVblank = now; sPaceVblank = deadline; sPacePeriod = period;
    sFramesDropped = 0; clockReads = 0; renderCost = matrixCost = 0;
    currentTarget = 60; debuggerActive = false;
    drawIndices.clear(); drawTargets.clear(); interpolationSteps.clear();
    vars.clear(); // g3DS.FrameSkip defaults to ON without requiring a saved config
}

int main() {
    OTRGlobals globals;
    OTRGlobals::Instance = &globals;
    globals.context = std::make_shared<Ship::Context>();
    Ship::Context::current = globals.context.get();
    auto window = std::make_shared<Fast::Fast3dWindow>();
    globals.context->window = window;
    Gfx commands;
    auto reset = [&](uint32_t now = 100, uint32_t deadline = 0, uint32_t period = 0) {
        ResetPacing(now, deadline, period);
        window->frames.clear(); window->eventTicks = 0; window->target = 60;
    };

#ifdef TEST_HOOKS_MISSING
    reset(12, 10, 1);
    RunCommands(&commands, 0, 20, 60, 3);
    assert(window->frames.size() == 3 && sFramesDropped == 0);
    assert(interpolationSteps.size() == 2);
    assert((drawIndices == std::vector<int>{0, 1, 2}));
    std::puts("PASS missing renderer hook(s): fail closed; all three frames still drawn");
    return 0;
#endif

#ifndef __3DS__
    reset(12, 10, 1);
    RunCommands(&commands, 0, 20, 60, 3);
    assert(window->frames.size() == 3 && sFramesDropped == 0);
    assert(interpolationSteps.size() == 2);
    assert((drawIndices == std::vector<int>{0, 1, 2}));
    std::puts("PASS desktop rendering: native frameskip code compiled out");
    return 0;
#endif

#if !defined(TEST_HOOKS_MISSING) && defined(__3DS__)
    // Startup, target switches, bounded debt, suspend/load and counter wrap.
    reset(0, 0, 0); assert(!Soh3dsFrameBehind());
    reset(9, 10, 1); assert(!Soh3dsFrameBehind());
    simulatedVblank = 10; assert(Soh3dsFrameBehind());
    simulatedVblank = 16; assert(Soh3dsFrameBehind());
    simulatedVblank = 17; assert(!Soh3dsFrameBehind());
    simulatedVblank = 600; assert(!Soh3dsFrameBehind());
    simulatedVblank = 10; currentTarget = 30; assert(!Soh3dsFrameBehind());
    sPacePeriod = 2; assert(Soh3dsFrameBehind());
    const auto beforeDrop = sPaceVblank;
    Soh3dsFrameDropped();
    assert(sPaceVblank == beforeDrop + 2 && sFramesDropped == 1);
    currentTarget = 20; assert(!Soh3dsFrameBehind());
    sPacePeriod = 3; simulatedVblank = sPaceVblank;
    assert(Soh3dsFrameBehind());
    const auto before20 = sPaceVblank;
    Soh3dsFrameDropped(); assert(sPaceVblank == before20 + 3);
    reset(0xfffffffdu, 0xfffffffeu, 1); assert(!Soh3dsFrameBehind());
    simulatedVblank = 1; assert(Soh3dsFrameBehind());
    Soh3dsFrameDropped(); assert(sPaceVblank == 0xffffffffu);
    Soh3dsFrameDropped(); assert(sPaceVblank == 0);
    assert(!Soh3dsFrameBehind()); // sentinel causes a conservative rebase, not a skip burst
    reset(0xfffffffdu, 1, 1); assert(!Soh3dsFrameBehind());
    std::puts("PASS renderer hooks: deadline equality, debt bound, 60/30/20 periods, startup and wrap");

    // No load: exact original coefficients/indices and no skips.
    reset(9, 10, 1);
    RunCommands(&commands, 0, 20, 60, 3);
    assert(window->frames.size() == 3 && sFramesDropped == 0);
    assert((drawIndices == std::vector<int>{0, 1, 2}));
    assert(interpolationSteps.size() == 2 && sPaceVblank == 13);
    assert(window->eventTicks == 1);
    std::puts("PASS on-time: 1/3, 2/3, 1 draws; original schedule and event pump retained");

    // Already late: matrices for dropped frames are not computed. Always draw
    // the last slot, preserving its index (not renumbering the surviving frame).
    reset(12, 10, 1);
    RunCommands(&commands, 0, 20, 60, 3);
    assert(sFramesDropped == 2 && window->frames.size() == 1);
    assert(window->frames[0] == 1.0f && interpolationSteps.empty());
    assert((drawIndices == std::vector<int>{2}));
    assert(window->interpreter->mInterpolationIndex == 3);
    assert(sPaceVblank == 13 && window->eventTicks == 1);
    std::puts("PASS late: two optional slots consumed, no obsolete matrix work, last frame/index retained");

    const auto recoveredFrames = window->frames.size();
    const auto recoveredDrops = sFramesDropped;
    RunCommands(&commands, 0, 20, 60, 3);
    assert(window->frames.size() == recoveredFrames + 3 && sFramesDropped == recoveredDrops);
    std::puts("PASS recovery: all interpolation resumes immediately when deadlines are met again");

    // Interpolation cost can itself make a not-yet-late slot obsolete.
    reset(9, 10, 1); matrixCost = 1;
    RunCommands(&commands, 0, 20, 60, 3);
    assert(sFramesDropped == 2 && window->frames.size() == 1);
    assert(interpolationSteps.size() == 2 && drawIndices[0] == 2);
    assert(sPaceVblank == 13);
    std::puts("PASS deadline recheck after interpolation: no stale GPU submission");

    // Single scheduled draw, including a 30/20-Hz tick whose only t is 2/3.
    reset(12, 10, 2); currentTarget = window->target = 30;
    RunCommands(&commands, 0, 20, 30, 1);
    assert(sFramesDropped == 0 && window->frames.size() == 1);
    assert(std::fabs(window->frames[0] - 2.0f / 3.0f) < 1e-6f);
    reset(12, 10, 1);
    RunCommands(&commands, 60, 0, 60, 1);
    assert(sFramesDropped == 0 && window->frames.size() == 1);
    assert(window->frames[0] == 1.0f);
    std::puts("PASS mandatory draw: single-interpolated and debugger-final cases never disappear");

    // Settings/debugger can disable skipping; no active clock reads for the skip decision.
    reset(12, 10, 1); vars["g3DS.FrameSkip"] = 0;
    RunCommands(&commands, 0, 20, 60, 3);
    assert(sFramesDropped == 0 && window->frames.size() == 3);
    reset(12, 10, 1); debuggerActive = true;
    RunCommands(&commands, 0, 20, 60, 3);
    assert(sFramesDropped == 0 && window->frames.size() == 3);
    std::puts("PASS opt-out and debugger: normal rendering remains available");

    // A long stall is rebased by the real EndFrame pacer, not caught up in bulk.
    reset(1000, 10, 1);
    RunCommands(&commands, 0, 20, 60, 3);
    assert(sFramesDropped == 0 && window->frames.size() == 3);
    assert(sPaceVblank > 1000 && sPaceVblank <= 1004);
    reset(12, 10, 1); currentTarget = window->target = 30;
    RunCommands(&commands, -10, 20, 30, 2);
    assert(sFramesDropped == 0 && window->frames.size() == 2 && sPacePeriod == 2);
    assert((drawIndices == std::vector<int>{0, 1}));
    reset(12, 0, 0); // exact wake/reset pacing state
    RunCommands(&commands, 0, 20, 60, 3);
    assert(sFramesDropped == 0 && window->frames.size() == 3);
    std::puts("PASS load, wake and target switch: stale pacing does not trigger skips");

    // Integration: one logical tick, one audio request/barrier regardless of
    // optional render skips. Count time in scheduled slots, NOT wall seconds.
    for (int updateRate : {1, 2, 3}) {
        for (int load = 0; load < 3; ++load) {
            for (int ceiling : {20, 30, 60}) {
                reset(); vars["gInterpolationFPS"] = ceiling;
                R_UPDATE_RATE = updateRate;
                audioBlocks.clear(); submissions = 0;
                audio.running = true; audio.processing = false;
                std::thread worker(OTRAudio_Thread);
                const int effective = std::max(60 / updateRate, ceiling);
                const int ticks = 60 / updateRate;
                for (int tick = 0; tick < ticks; ++tick) {
                    if (load == 0) {
                        if (sPaceVblank != 0) simulatedVblank = std::max(simulatedVblank, sPaceVblank - 1);
                    } else if (sPaceVblank != 0) {
                        // Synthetic pressure on two of every three ticks in the mixed case.
                        const bool late = load == 1 || tick % 3 != 0;
                        simulatedVblank = std::max(simulatedVblank, late ? sPaceVblank + 1 : sPaceVblank - 1);
                    }
                    const size_t beforeFrames = window->frames.size();
                    const uint32_t beforeDropped = sFramesDropped;
                    const size_t beforeAudio = audioBlocks.size();
                    Graph_ProcessGfxCommands(&commands);
                    assert(!audio.processing); // real main-thread audio barrier
                    assert(audioBlocks.size() - beforeAudio == static_cast<size_t>(updateRate));
                    assert(window->frames.size() > beforeFrames); // no skipped game tick's entire draw batch
                    const auto accounted = window->frames.size() - beforeFrames + sFramesDropped - beforeDropped;
                    assert(accounted >= 1 && accounted <= static_cast<size_t>(updateRate));
                    assert(window->target == effective && window->target <= 60);
                }
                {
                    std::lock_guard<std::mutex> lock(audio.mutex);
                    audio.running = false;
                }
                audio.cv_to_thread.notify_one(); worker.join();
                assert(window->eventTicks == static_cast<unsigned>(ticks));
                assert(window->frames.size() + sFramesDropped == static_cast<size_t>(effective));
                assert(audioBlocks.size() == 60 && submissions == 60);
                uint32_t total = 0; const u32 cycle[] = {528, 544, 528};
                for (size_t i = 0; i < audioBlocks.size(); ++i) {
                    assert(audioBlocks[i] == cycle[i % 3]); total += audioBlocks[i];
                }
                assert(total == 32000);
                if (load == 0) assert(sFramesDropped == 0);
                if (load != 0 && effective > 60 / updateRate) assert(sFramesDropped > 0);
                if (effective == 60 / updateRate) assert(sFramesDropped == 0);
                std::printf("PASS integration: divisor=%d ceiling=%d load=%d; ticks=%d render=%zu skipped=%u "
                            "audio=60 blocks/32000 frames (scheduled second, not measured wall time)\n",
                            updateRate, ceiling, load, ticks, window->frames.size(), sFramesDropped);
            }
        }
    }
    // A surviving final image can still overrun: do not fake full-speed logic/audio.
    reset(12, 10, 1); renderCost = 20;
    RunCommands(&commands, 0, 20, 60, 3);
    assert(sFramesDropped == 2 && window->frames.size() == 1);
    assert(simulatedVblank >= 32); // frameskip cannot remove mandatory workload
    std::puts("PASS overload floor: final-frame cost remains visible, no hidden fast-forward/audio refill");
    std::puts("PASS AUTO: 27 integration combinations, deterministic edge cases, no game/audio tick skipped");
#endif
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    helpers = load_helpers()
    source = (args.root / "third_party/2ship/mm/2s2h/BenPort.cpp").read_text(encoding="utf-8")
    renderer = (args.root / "platform/3ds/source/gfx_citro3d.cpp").read_text(encoding="utf-8")
    fps = helpers.function(source, "uint32_t OTRGlobals::GetInterpolationFPS()")
    run = helpers.function(source, "void RunCommands(")
    graph = helpers.function(source, 'extern "C" void Graph_ProcessGfxCommands(Gfx* commands)')
    worker = helpers.function(source, "void OTRAudio_Thread()")
    audio_start = source.rindex("static struct {", 0, source.index("void OTRAudio_Thread()"))
    audio_end = source.index("} audio;", audio_start) + len("} audio;")
    behind = helpers.function(renderer, 'extern "C" bool Soh3dsFrameBehind(void)')
    dropped = helpers.function(renderer, 'extern "C" void Soh3dsFrameDropped(void)')
    endframe = helpers.function(renderer, "void GfxRenderingAPICitro3D::EndFrame()")
    # Exact lexical scope of EndFrame's game-loop pacing; no copied arithmetic.
    pacing_begin = endframe.index("    {\n        const int target = Soh3dsTargetFps")
    pacing = helpers.function(endframe[pacing_begin:], "    {")
    debt = re.search(r"constexpr uint32_t kMaxPacingDebtVblanks = [^;]+;", renderer).group(0)
    state = "\n".join(re.search(r"static uint32_t " + name + r" = [^;]+;", renderer).group(0)
                      for name in ("sPaceVblank", "sPacePeriod", "sFramesDropped"))
    declarations = '\n'.join([sig.split("{")[0].strip() + " __attribute__((weak));"
                              for sig in (behind, dropped)])
    prelude = helpers.PRELUDE
    marker = "namespace Fast {"
    assert prelude.count(marker) == 1
    prelude = prelude.replace(marker, "void SimulatedDraw(int index, int target);\nvoid SimulatedTarget(int target);\n" + marker)
    marker = "void SetTargetFps(int rate) { target = rate; }"
    assert prelude.count(marker) == 1
    prelude = prelude.replace(marker, "void SetTargetFps(int rate) { target = rate; SimulatedTarget(rate); }")
    marker = "        frames.push_back(interpreter->mInterpolationT);"
    assert prelude.count(marker) == 1
    prelude = prelude.replace(marker, marker + "\n        SimulatedDraw(interpreter->mInterpolationIndex, target);")
    marker = "std::unordered_map<Mtx*, MtxF> FrameInterpolation_Interpolate(float time) {"
    assert prelude.count(marker) == 1
    prelude = prelude.replace(marker, "void SimulatedInterpolation();\n" + marker + "\n    SimulatedInterpolation();")
    code = prelude + MOCK_PACER + '\n' + debt + '\n' + state + '\n' + declarations + '\n'
    code += '#ifndef OMIT_BEHIND\n' + behind + '\n#endif\n#ifndef OMIT_DROPPED\n' + dropped + '\n#endif\n'
    code += "void SimulatedEndFrame() {\nuint64_t pacingWait = 0;\n" + pacing + "\n(void)pacingWait;\n}\n"
    code += r'''
void SimulatedDraw(int index, int target) {
    drawIndices.push_back(index); drawTargets.push_back(target);
    currentTarget = target;
    simulatedVblank += renderCost;
    SimulatedEndFrame();
}
void SimulatedInterpolation() { simulatedVblank += matrixCost; }
void SimulatedTarget(int target) { currentTarget = target; }
'''
    code += source[audio_start:audio_end] + '\n' + fps + '\n#ifdef __3DS__\n' + worker + '\n#endif\n' + run + '\n' + graph + '\n' + MAIN
    compiler = shutil.which(os.environ.get("CXX", "g++"))
    if not compiler:
        raise RuntimeError("Host C++ compiler required; set CXX or install g++.")
    variants = [("native", ["-D__3DS__=1"]), ("desktop", []),
                ("no_behind", ["-D__3DS__=1", "-DOMIT_BEHIND", "-DTEST_HOOKS_MISSING"]),
                ("no_dropped", ["-D__3DS__=1", "-DOMIT_DROPPED", "-DTEST_HOOKS_MISSING"]),
                ("no_hooks", ["-D__3DS__=1", "-DOMIT_BEHIND", "-DOMIT_DROPPED", "-DTEST_HOOKS_MISSING"])]
    with tempfile.TemporaryDirectory(prefix="2ship-frameskip-") as tmp:
        base = Path(tmp)
        cpp = base / "frameskip.cpp"
        cpp.write_text(code, encoding="utf-8")
        for label, defines in variants:
            exe = base / (label + ".exe")
            subprocess.run([compiler, "-std=c++20", "-O1", "-pthread", *defines, str(cpp), "-o", str(exe)],
                           check=True, timeout=60)
            subprocess.run([str(exe)], check=True, timeout=30, cwd=base)
    print("PASS: all five compiled harness variants")


if __name__ == "__main__":
    main()
