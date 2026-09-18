#!/usr/bin/env python3
"""Execute the production menu initialization path before its first draw.

The Window/Config doubles supply available and saved backend IDs. The enum,
lookup maps, Gui::SetMenu, GuiElement::Init, Menu::InitElement and backend
lookup implementation are extracted from the real sources. A retained 07 map
fixture reproduces its startup exception; production must handle backend 4.
No ARM/GPU execution is emulated here.
"""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def block(text, signature, semicolon=False):
    start = text.index(signature)
    cursor = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[cursor] == "{") - (text[cursor] == "}")
        cursor += 1
    if semicolon:
        assert text[cursor] == ";"
        cursor += 1
    return text[start:cursor]


# Exact window-map declaration from release 07, identical to official MM.
# That desktop-only table lacks the public native enum value FAST3D_CITRO3D.
BASELINE_07_WINDOW_MAP = r'''
static const std::unordered_map<int32_t, const char*> windowBackendsMap = {
    { Fast::WindowBackend::FAST3D_DXGI_DX11, "DirectX" },
    { Fast::WindowBackend::FAST3D_SDL_OPENGL, "OpenGL" },
    { Fast::WindowBackend::FAST3D_SDL_METAL, "Metal" },
};
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default=os.environ.get("CXX", "g++"))
    args = parser.parse_args()
    compiler = shutil.which(args.cxx)
    if not compiler:
        parser.error("Set CXX or --cxx to a host C++20 compiler.")

    mm = ROOT / "third_party/2ship/mm/2s2h/BenGui"
    lus = ROOT / "third_party/libultraship"
    maps = (mm / "MenuTypes.h").read_text(encoding="utf-8")
    menu = (mm / "Menu.cpp").read_text(encoding="utf-8")
    gui = (lus / "src/ship/window/gui/Gui.cpp").read_text(encoding="utf-8")
    element = (lus / "src/ship/window/gui/GuiElement.cpp").read_text(encoding="utf-8")
    backend_enum = block((lus / "include/fast/Fast3dWindow.h").read_text(encoding="utf-8"),
                         "enum WindowBackend", True)
    audio_enum = block((lus / "include/ship/audio/Audio.h").read_text(encoding="utf-8"),
                       "enum class AudioBackend", True)
    native_map = block(maps, "static const std::unordered_map<int32_t, const char*> windowBackendsMap", True)
    audio_map = block(maps, "static const std::unordered_map<Ship::AudioBackend, const char*> audioBackendsMap", True)
    functions = "\n".join((
        block(gui, "void Gui::SetMenu("),
        block(element, "void GuiElement::Init()"),
        block(menu, "void Menu::InitElement()"),
        block(menu, "void Menu::UpdateWindowBackendObjects()"),
    ))

    # Verify the native boot caller reaches these production functions before
    # Hide; the harness itself also initializes an already-invisible menu.
    setup = block((mm / "BenGui.cpp").read_text(encoding="utf-8"), "void SetupMenu()")
    assert setup.index("gui->SetMenu(mBenMenu)") < setup.index("mBenMenu->Hide()")
    ben_init = block((mm / "BenMenu.cpp").read_text(encoding="utf-8"), "void BenMenu::InitElement()")
    assert ben_init.index("Ship::Menu::InitElement()") < ben_init.index("AddSettings()")

    declarations = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <memory>
#include <stdexcept>
#include <unordered_map>
#include <vector>
namespace Fast {
''' + backend_enum + r'''
}
namespace Ship {
''' + audio_enum + r'''
}
''' + audio_map + r'''
int CVarGetInteger(const char*, int fallback) { return fallback; }
namespace Ship {
struct Config {
    bool saved = false;
    int32_t id = -1;
    int GetInt(const char* key, int fallback) {
        assert(std::strcmp(key, "Window.Backend.Id") == 0);
        return saved ? id : fallback;
    }
};
struct Window {
    int32_t running = Fast::FAST3D_CITRO3D;
    std::shared_ptr<std::vector<int32_t>> available = std::make_shared<std::vector<int32_t>>();
    int32_t GetWindowBackend() { return running; }
    auto GetAvailableWindowBackends() { return available; }
    bool IsAvailableWindowBackend(int32_t backend) {
        return std::find(available->begin(), available->end(), backend) != available->end();
    }
};
struct Context {
    Window window;
    Config config;
    static Context* GetRawInstance() { static Context instance; return &instance; }
    Window* GetWindow() { return &window; }
    Config* GetConfig() { return &config; }
};
class GuiElement {
public:
    bool mIsInitialized = false;
    bool visible = false;
    bool IsInitialized() { return mIsInitialized; }
    bool IsVisible() { return visible; }
    virtual ~GuiElement() = default;
    virtual void InitElement() = 0;
    void Init();
};
class GuiWindow : public GuiElement {};
class Gui {
public:
    std::shared_ptr<GuiWindow> mMenu;
    auto GetMenu() { return mMenu; }
    void SetMenu(std::shared_ptr<GuiWindow> menu);
};
class Menu : public GuiWindow {
public:
    struct Vec2 { float x, y; } poppedSize{}, poppedPos{};
    bool popped = false;
    int32_t configWindowBackend = -1;
    std::shared_ptr<std::vector<int32_t>> availableWindowBackends;
    std::unordered_map<int32_t, const char*> availableWindowBackendsMap;
    void InitElement() override;
    void UpdateWindowBackendObjects();
};
}
'''
    cases = r'''
int main() {
    auto* context = Ship::Context::GetRawInstance();
    *context->window.available = {Fast::FAST3D_CITRO3D};
    context->window.running = Fast::FAST3D_CITRO3D;
#ifdef EXPECT_07_FAILURE
    Ship::Gui gui;
    auto menu = std::make_shared<Ship::Menu>();
    bool caught = false;
    try { gui.SetMenu(menu); }
    catch (const std::out_of_range& exception) {
        caught = true;
        std::printf("PASS: release 07 hidden-menu startup reproduces %s\n", exception.what());
    }
    assert(caught && !menu->IsInitialized() && !menu->IsVisible());
#else
    unsigned checked = 0;
#ifdef __3DS__
    // Missing, valid native, stale desktop, zero, and unknown saved selections.
    for (int id : {-1, 4, 1, 2, 3, 0, 999}) {
        context->config.saved = id != -1;
        context->config.id = id;
        Ship::Gui gui;
        auto menu = std::make_shared<Ship::Menu>();
        assert(!menu->IsVisible());
        gui.SetMenu(menu);
        assert(menu->IsInitialized() && !menu->IsVisible());
        assert(menu->configWindowBackend == Fast::FAST3D_CITRO3D);
        assert(menu->availableWindowBackendsMap.size() == 1);
        assert(std::strlen(menu->availableWindowBackendsMap.at(Fast::FAST3D_CITRO3D)) > 0);
        gui.SetMenu(menu); // The production Init guard permits repeated registration.
        assert(menu->availableWindowBackendsMap.size() == 1);
        ++checked;
    }
#else
    assert(!windowBackendsMap.contains(Fast::FAST3D_CITRO3D));
#endif
    *context->window.available = {Fast::FAST3D_DXGI_DX11, Fast::FAST3D_SDL_OPENGL, Fast::FAST3D_SDL_METAL};
    context->window.running = Fast::FAST3D_SDL_OPENGL;
    for (int id : {-1, 1, 2, 3, 4, 999}) {
        context->config.saved = id != -1;
        context->config.id = id;
        Ship::Gui gui;
        auto menu = std::make_shared<Ship::Menu>();
        gui.SetMenu(menu);
        const int expected = id >= 1 && id <= 3 ? id : Fast::FAST3D_SDL_OPENGL;
        assert(menu->IsInitialized() && menu->configWindowBackend == expected);
        assert(menu->availableWindowBackendsMap.size() == 3);
        ++checked;
    }
    // Restoring MenuTypes' audio labels must retain every public backend key,
    // including SDL (the native NDSP ABI selection) and the null fallback.
    for (auto id : {Ship::AudioBackend::WASAPI, Ship::AudioBackend::SDL,
                    Ship::AudioBackend::COREAUDIO, Ship::AudioBackend::NUL}) {
        assert(std::strlen(audioBackendsMap.at(id)) > 0);
        ++checked;
    }
    std::printf("PASS: %u production pre-frame menu/backend cases; hidden and repeated initialization\n", checked);
#endif
}
'''
    with tempfile.TemporaryDirectory(prefix="blinky-startup-") as temporary:
        work = Path(temporary)
        variants = (
            ("release07", BASELINE_07_WINDOW_MAP, ["-D__3DS__", "-DEXPECT_07_FAILURE"]),
            ("native", native_map, ["-D__3DS__"]),
            ("desktop", native_map, []),
        )
        for name, window_map, flags in variants:
            code = declarations + window_map + "\nnamespace Ship {\n" + functions + "\n}\n" + cases
            cpp = work / (name + ".cpp")
            binary = work / (name + (".exe" if os.name == "nt" else ""))
            cpp.write_text(code, encoding="utf-8")
            subprocess.run([compiler, "-std=c++20", "-O2", *flags, str(cpp), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
