#include "gfx_window_manager_3ds.h"

#include "fast/Fast3dGui.h"
#include "ship/Context.h"
#include "ship/window/Window.h"
#include "ship/controller/controldeck/ControlDeck.h"
#include "ship/controller/physicaldevice/ConnectedPhysicalDeviceManager.h"
#include "ship/controller/controldevice/controller/Controller.h"
#include "ship/controller/controldevice/controller/mapping/sdl/SDLGyroMapping.h"

#include <cstdio>

#include <3ds.h>
#include <SDL2/SDL.h>

extern "C" bool Mk64Diagnostics3DSOwnsHid(void) __attribute__((weak));

// Read by gfx_citro3d.cpp StartFrame to pace the game loop (see there).
// File-scope extern "C": one declared inside namespace Fast would mangle.
namespace {
int sTargetFps = 60;
}
extern "C" int Soh3dsTargetFps(void) {
    return sTargetFps;
}

namespace Fast {

void GfxWindowBackend3DS::Init(const char*, const char*, bool, uint32_t width, uint32_t height,
                              int32_t, int32_t) {
    // The LCD dictates the dimensions, irrespective of desktop configuration.
    // An 800-pixel target selects wide mono output; the stereo target is 400.
    (void)height;
    mWidth = width == 800 ? 800 : 400;
    mHeight = 240;
    mFullScreen = true;
    mIsRunning = true;
    mTargetFps = 60;

    // Native Fast3dGui initialization is required before MM installs fonts
    // or draws a frame. Desktop SDL/GL startup is excluded on the 3DS.
    auto gui = Ship::Context::GetRawInstance()->GetWindow()->GetGui();
    if (gui != nullptr) {
        GuiWindowInitData impl{};
        impl.Backend = WindowBackend::FAST3D_CITRO3D;
        impl.Ctr.Width = mWidth;
        impl.Ctr.Height = mHeight;
        std::static_pointer_cast<Fast3dGui>(gui)->Init(impl);
        std::fprintf(stderr, "2ship-3ds gfx: Fast3dGui::Init done (ImGui context up)\n");
    } else {
        std::fprintf(stderr, "2ship-3ds gfx: no Gui on the window; ImGui will not initialise\n");
    }
}

void GfxWindowBackend3DS::Close() {
    mIsRunning = false;
}

void GfxWindowBackend3DS::SetKeyboardCallbacks(bool (*onKeyDown)(int), bool (*onKeyUp)(int),
                                                 void (*onAllKeysUp)()) {
    mOnKeyDown = onKeyDown;
    mOnKeyUp = onKeyUp;
    (void) onAllKeysUp;
}

void GfxWindowBackend3DS::SetMouseCallbacks(bool (*onMouseButtonDown)(int), bool (*onMouseButtonUp)(int)) {
    mOnMouseButtonDown = onMouseButtonDown;
    mOnMouseButtonUp = onMouseButtonUp;
}

void GfxWindowBackend3DS::SetFullscreenChangedCallback(void (*onFullscreenChanged)(bool)) {
    mOnFullscreenChanged = onFullscreenChanged;
}

void GfxWindowBackend3DS::SetFullscreen(bool fullscreen) {
    mFullScreen = fullscreen;
    if (mOnFullscreenChanged != nullptr) {
        mOnFullscreenChanged(fullscreen);
    }
}

void GfxWindowBackend3DS::GetActiveWindowRefreshRate(uint32_t* refreshRate) {
    if (refreshRate != nullptr) {
        *refreshRate = 60;
    }
}

void GfxWindowBackend3DS::SetCursorVisibility(bool) {
}

void GfxWindowBackend3DS::SetMousePos(int32_t, int32_t) {
}

void GfxWindowBackend3DS::GetMousePos(int32_t* x, int32_t* y) {
    if (x != nullptr) {
        *x = 0;
    }
    if (y != nullptr) {
        *y = 0;
    }
}

void GfxWindowBackend3DS::GetMouseDelta(int32_t* x, int32_t* y) {
    GetMousePos(x, y);
}

void GfxWindowBackend3DS::GetMouseWheel(float* x, float* y) {
    if (x != nullptr) {
        *x = 0.0f;
    }
    if (y != nullptr) {
        *y = 0.0f;
    }
}

bool GfxWindowBackend3DS::GetMouseState(uint32_t) {
    return false;
}

void GfxWindowBackend3DS::SetMouseCapture(bool) {
}

bool GfxWindowBackend3DS::IsMouseCaptured() {
    return false;
}

void GfxWindowBackend3DS::GetDimensions(uint32_t* width, uint32_t* height, int32_t* posX, int32_t* posY) {
    if (width != nullptr) {
        *width = mWidth;
    }
    if (height != nullptr) {
        *height = mHeight;
    }
    if (posX != nullptr) {
        *posX = 0;
    }
    if (posY != nullptr) {
        *posY = 0;
    }
}

void GfxWindowBackend3DS::SetDimensions(uint32_t width, uint32_t height, int32_t, int32_t) {
    // Match Init: resizing a desktop configuration cannot resize the LCD.
    (void)height;
    mWidth = width == 800 ? 800 : 400;
    mHeight = 240;
}

Ship::WindowRect GfxWindowBackend3DS::GetPrimaryMonitorRect() {
    return { 0, 0, static_cast<int32_t>(mWidth), static_cast<int32_t>(mHeight) };
}

namespace {
struct {
    int x = 0;
    int y = 0;
    bool held = false;
} sTouch;

// Optional v7 input diagnostic: sdmc:/3ds/2ship/autotouch.txt contains
// lines of "<frame> <x> <y> <hold>".
// (up to 16): the touch screen reads pressed at (x, y) for <hold> HandleEvents
// calls starting at that call ordinal. The emulator harness has no touch
// injection and the bottom-screen UI is unreachable without it. Read once;
// absent file is inert. Same shape as the autopress pad hook.
struct AutoTouch {
    unsigned frame;
    int x, y;
    unsigned hold;
};
AutoTouch sAutoTouch[16];
int sAutoTouchCount = 0;
bool sAutoTouchRead = false;
unsigned sHandleEventsCalls = 0;

bool AutoTouchSample(int* x, int* y) {
    if (!sAutoTouchRead) {
        sAutoTouchRead = true;
        if (FILE* f = fopen("sdmc:/3ds/2ship/autotouch.txt", "r")) {
            char line[64];
            while (sAutoTouchCount < 16 && fgets(line, sizeof(line), f) != nullptr) {
                AutoTouch& t = sAutoTouch[sAutoTouchCount];
                if (sscanf(line, "%u %d %d %u", &t.frame, &t.x, &t.y, &t.hold) == 4) {
                    ++sAutoTouchCount;
                }
            }
            fclose(f);
        }
    }
    for (int i = 0; i < sAutoTouchCount; i++) {
        if (sHandleEventsCalls >= sAutoTouch[i].frame && sHandleEventsCalls < sAutoTouch[i].frame + sAutoTouch[i].hold) {
            *x = sAutoTouch[i].x;
            *y = sAutoTouch[i].y;
            return true;
        }
    }
    return false;
}
} // namespace

// Game-side touch hook retained from the v7 backend. Returns held; x/y in
// bottom-LCD pixels (320x240) from the most recent HandleEvents sample.
extern "C" int Soh3dsTouchRead(int* x, int* y) {
    if (x != nullptr) {
        *x = sTouch.x;
    }
    if (y != nullptr) {
        *y = sTouch.y;
    }
    return sTouch.held ? 1 : 0;
}

void GfxWindowBackend3DS::HandleEvents() {
    // The diagnostics worker owns HID while the game is running so SELECT can
    // still be observed if the main thread is blocked in the renderer.
    if (Mk64Diagnostics3DSOwnsHid == nullptr || !Mk64Diagnostics3DSOwnsHid()) {
        hidScanInput();
    }
    // Dual screen: touch sample for the game side's bottom-screen UI. SDL's
    // 3DS driver reports touch as a mouse only through the video subsystem,
    // which this backend does not run, so read it here beside the pad scan.
    ++sHandleEventsCalls;
    int autoX = 0, autoY = 0;
    if ((hidKeysHeld() & KEY_TOUCH) != 0) {
        touchPosition touch = {};
        hidTouchRead(&touch);
        sTouch.x = touch.px;
        sTouch.y = touch.py;
        sTouch.held = true;
    } else if (AutoTouchSample(&autoX, &autoY)) {
        sTouch.x = autoX;
        sTouch.y = autoY;
        sTouch.held = true;
    } else {
        sTouch.held = false;
    }
    if (!aptMainLoop()) {
        mIsRunning = false;
    }

    // libultraship reads the pad through SDL, and SDL's 3DS joystick
    // driver only consumes hidKeysDown()/hidKeysUp()/hidCircleRead() when its
    // joystick state is updated. Normally SDL's *video* event pump does that,
    // but this backend owns the screens itself and only the GAMECONTROLLER
    // subsystem is up, so the pad reads permanently idle without this. The
    // scan above must precede the update: hidKeysDown() reports edges from the
    // most recent scan.
    SDL_JoystickUpdate();

    // Adopt the built-in pad once. On desktop the queued
    // SDL_CONTROLLERDEVICEADDED event is consumed by LUS's
    // SDLAddRemoveDeviceEventHandler, but that is an ImGui gui-window and
    // native window backend does not pump that event handler; the deck would keep zero devices
    // forever. The 3DS pad cannot hotplug; one refresh replaces the event
    // choreography.
    static bool sPadAdopted = false;
    if (!sPadAdopted) {
        auto* context = Ship::Context::GetRawInstance();
        if (context != nullptr && context->GetControlDeck() != nullptr) {
            context->GetControlDeck()->GetConnectedPhysicalDeviceManager()->RefreshConnectedSDLGamepads();
            sPadAdopted = true;
            const int joystickCount = SDL_NumJoysticks();
            std::fprintf(stderr, "2ship-3ds input: SDL_NumJoysticks=%d\n", joystickCount);
            for (int index = 0; index < joystickCount; ++index) {
                const char* name = SDL_JoystickNameForIndex(index);
                std::fprintf(stderr, "2ship-3ds input: [%d] \"%s\" isGameController=%d\n", index,
                             name != nullptr ? name : "(null)", (int)SDL_IsGameController(index));
            }
            const size_t adopted =
                context->GetControlDeck()->GetConnectedPhysicalDeviceManager()->GetConnectedSDLGamepadNames().size();
            std::fprintf(stderr, "2ship-3ds input: ControlDeck adopted %u gamepad(s)\n", (unsigned)adopted);

            // The gyroscope is built in, but a gyro mapping normally only
            // exists once a user creates one in the input editor - which this
            // port has no UI for. Seed a session-local default when the config
            // has none; SDLGyroMapping's 3DS branch reads the standalone SDL
            // sensor. Recalibrate captures the at-rest bias so first-person
            // aim does not drift.
            auto controller = context->GetControlDeck()->GetControllerByPort(0);
            if (controller != nullptr && controller->GetGyro() != nullptr &&
                controller->GetGyro()->GetGyroMapping() == nullptr) {
                auto gyroMapping = std::make_shared<Ship::SDLGyroMapping>(0, 1.0f, 0.0f, 0.0f, 0.0f);
                gyroMapping->Recalibrate();
                controller->GetGyro()->SetGyroMapping(gyroMapping);
                std::fprintf(stderr, "2ship-3ds input: seeded default gyro mapping\n");
            }
        }
    }
}

bool GfxWindowBackend3DS::IsFrameReady() {
    return mIsRunning;
}

void GfxWindowBackend3DS::SwapBuffersBegin() {
}

void GfxWindowBackend3DS::SwapBuffersEnd() {
}

double GfxWindowBackend3DS::GetTime() {
    return static_cast<double>(osGetTime()) / 1000.0;
}

int GfxWindowBackend3DS::GetTargetFps() {
    return static_cast<int>(mTargetFps);
}

void GfxWindowBackend3DS::SetTargetFps(int fps) {
    mTargetFps = fps > 0 ? static_cast<uint32_t>(fps) : 60;
    sTargetFps = static_cast<int>(mTargetFps);
}

void GfxWindowBackend3DS::SetMaxFrameLatency(int) {
}

const char* GfxWindowBackend3DS::GetKeyName(int) {
    return "3DS Button";
}

bool GfxWindowBackend3DS::CanDisableVsync() {
    return false;
}

bool GfxWindowBackend3DS::IsRunning() {
    return mIsRunning;
}

void GfxWindowBackend3DS::Destroy() {
    mIsRunning = false;
}

bool GfxWindowBackend3DS::IsFullscreen() {
    return true;
}

} // namespace Fast
