#pragma once

namespace Fast::Stereo3DS {

constexpr int RenderScaleDefault = 60;

// Clamp before rounding so even corrupt integer settings cannot overflow.
constexpr int NormalizeRenderScalePercent(int percent) {
    if (percent <= 10) return 10;
    if (percent >= 100) return 100;
    return ((percent + 5) / 10) * 10;
}

} // namespace Fast::Stereo3DS
