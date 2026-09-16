// Essential native controls at the game's input boundary. These shortcuts work
// without an ImGui renderer. Physical bit indices match the v7 LUS input bridge.
#include <cstdint>
#include <cstdio>

#include <fast/stereo_3ds.h>
#include <fast/stereo_resolution_3ds.h>
#include <libultraship/bridge/consolevariablebridge.h>

extern "C" unsigned Soh3dsControls_CurrentMappingMask(int physical);

namespace {
constexpr uint32_t kL = 1u << 4;
constexpr uint32_t kR = 1u << 5;
constexpr uint32_t kZR = 1u << 7;
constexpr uint32_t kUp = 1u << 8;
constexpr uint32_t kDown = 1u << 9;
constexpr uint32_t kShoulders = kL | kR;
constexpr uint32_t kDirections = kUp | kDown;
constexpr uint32_t kResolutionKeys = kShoulders | kDirections;
constexpr const char* kScale = "g3DS.RenderScalePercent";
constexpr const char* kConvergence = "g3DS.ConvergenceMode";

bool sZrHeld = false;
uint32_t sChordDirections = 0;
uint32_t sConsumedResolution = 0;
} // namespace

extern "C" void Soh3dsControls_TransformPad(uint32_t physical, uint16_t* pad) {
    if (pad == nullptr) {
        return;
    }

    const bool zrHeld = (physical & kZR) != 0;
    const bool zrPressed = zrHeld && !sZrHeld;
    sZrHeld = zrHeld;
    const bool shouldersHeld = (physical & kShoulders) == kShoulders;
    const uint32_t directions = shouldersHeld ? physical & kDirections : 0;
    const uint32_t pressedDirections = directions & ~sChordDirections;
    // Track both directions even when they cancel or ZR takes precedence.
    // A suppressed edge must not run later when the conflicting key releases.
    sChordDirections = directions;
    if ((physical & kResolutionKeys) == 0) {
        sConsumedResolution = 0;
    } else if (directions != 0) {
        sConsumedResolution |= kShoulders | directions;
    }

    if (zrPressed) {
        const int next = Fast::Stereo3DS::NextConvergenceMode(CVarGetInteger(kConvergence, 1));
        CVarSetInteger(kConvergence, next);
        CVarSave();
        std::fprintf(stderr, "2ship-3ds controls: convergence mode %d\n", next);
    }
    if (!zrHeld && pressedDirections != 0 && (directions == kUp || directions == kDown)) {
        const int current = Fast::Stereo3DS::NormalizeRenderScalePercent(
            CVarGetInteger(kScale, Fast::Stereo3DS::RenderScaleDefault));
        const int next = Fast::Stereo3DS::NormalizeRenderScalePercent(current + (directions == kUp ? 10 : -10));
        if (next != current) {
            CVarSetInteger(kScale, next);
            CVarSave();
            std::fprintf(stderr, "2ship-3ds controls: stereo render scale %d%%\n", next);
        }
    }

    const uint32_t consumed = kZR | sConsumedResolution;
    if ((physical & consumed) == 0) {
        return;
    }
    uint16_t blocked = 0;
    uint16_t retained = 0;
    for (int index = 0; index < 14; ++index) {
        const uint32_t bit = 1u << index;
        if ((physical & bit) == 0) {
            continue;
        }
        const uint16_t mapping = static_cast<uint16_t>(Soh3dsControls_CurrentMappingMask(index));
        if ((consumed & bit) != 0) {
            blocked |= mapping;
        } else {
            retained |= mapping;
        }
    }
    // R and ZR may both map to N64 R: reserve ZR's contribution while allowing
    // another held, non-shortcut key to supply the same gameplay action.
    // LUS merges this low half into MM's uint32_t pad, preserving virtual bits.
    *pad &= static_cast<uint16_t>(~(blocked & static_cast<uint16_t>(~retained)));
}
