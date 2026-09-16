#!/usr/bin/env python3
"""Execute the production Context destructor for partially initialized states."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    text = (ROOT / "third_party/libultraship/src/ship/Context.cpp").read_text(encoding="utf-8")
    begin = text.index("Context::~Context() {")
    end = text.index("\nContext* Context::CreateInstance", begin)
    destructor = text[begin:end]
    code = r'''
#include <cassert>
#include <cstdio>
#include <memory>
#define SPDLOG_TRACE(...) ((void)0)
unsigned saves = 0, windowSaves = 0, flushes = 0, destroyed = 0;
bool hasConfig = false;
struct Config { void Save() { ++saves; } };
struct Window { void SaveWindowToConfig() { assert(hasConfig); ++windowSaves; } };
struct Logger { void flush() { ++flushes; } };
struct Subsystem { ~Subsystem() { ++destroyed; } };
class Context {
public:
    std::shared_ptr<Config> mConfig;
    std::shared_ptr<Window> mWindow;
    std::shared_ptr<Logger> mLogger;
    std::shared_ptr<Subsystem> mAudio, mConsole, mCrashHandler, mControlDeck,
        mResourceManager, mConsoleVariables, mEventSystem, mLogThreadPool;
    ~Context();
};
''' + destructor + r'''
int main() {
    for (unsigned state = 0; state < 8; ++state) {
        saves = windowSaves = flushes = destroyed = 0;
        hasConfig = (state & 1) != 0;
        {
            Context context;
            if (state & 1) context.mConfig = std::make_shared<Config>();
            if (state & 2) context.mWindow = std::make_shared<Window>();
            if (state & 4) context.mLogger = std::make_shared<Logger>();
            context.mAudio = std::make_shared<Subsystem>();
            context.mConsole = std::make_shared<Subsystem>();
            context.mCrashHandler = std::make_shared<Subsystem>();
            context.mControlDeck = std::make_shared<Subsystem>();
            context.mResourceManager = std::make_shared<Subsystem>();
            context.mConsoleVariables = std::make_shared<Subsystem>();
            context.mEventSystem = std::make_shared<Subsystem>();
            context.mLogThreadPool = std::make_shared<Subsystem>();
        }
        assert(saves == ((state & 1) ? 1u : 0u));
        assert(windowSaves == (((state & 3) == 3) ? 1u : 0u));
        assert(flushes == ((state & 4) ? 1u : 0u));
        assert(destroyed == 8);
    }
    std::puts("PASS: 8 partial/full production Context teardown states");
}
'''
    compiler = shutil.which(os.environ.get("CXX", "g++"))
    if not compiler:
        raise SystemExit("A host C++ compiler is required (set CXX).")
    with tempfile.TemporaryDirectory(prefix="2ship-teardown-", dir=ROOT.parent) as tmp:
        tmp = Path(tmp)
        source = tmp / "teardown_test.cpp"
        binary = tmp / ("teardown_test.exe" if os.name == "nt" else "teardown_test")
        source.write_text(code, encoding="utf-8")
        subprocess.run([compiler, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror",
                        str(source), "-o", str(binary)], check=True)
        environment = os.environ.copy()
        environment["PATH"] = str(Path(compiler).parent) + os.pathsep + environment.get("PATH", "")
        subprocess.run([str(binary)], check=True, env=environment)


if __name__ == "__main__":
    main()
