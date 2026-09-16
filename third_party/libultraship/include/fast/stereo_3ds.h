#pragma once

#include <algorithm>
#include <cmath>

namespace Fast::Stereo3DS {

// Sixteen pixels of total disparity at 400 px (twice the initial range). The left eye remains the game's
// reference camera, so its depth queries and framebuffer captures stay exact.
constexpr float MaxNdcDisparity = 0.08f;
constexpr float EyeSeparation = 6.0f;
constexpr float Convergence = 160.0f;

// Short convergence places more of the scene behind the screen. A distant
// convergence brings more geometry in front. Default remains the middle mode.
inline int NormalizeConvergenceMode(int mode) { return mode >= 0 && mode < 3 ? mode : 1; }
inline int NextConvergenceMode(int mode) { return (NormalizeConvergenceMode(mode) + 1) % 3; }
inline float ConvergenceForMode(int mode) {
    constexpr float distances[] = { 80.0f, Convergence, 320.0f };
    return distances[NormalizeConvergenceMode(mode)];
}

inline float Strength(float slider) {
    return std::isfinite(slider) && slider > 0.01f ? std::min(slider, 1.0f) : 0.0f;
}

inline float ClampClipOffset(float offset, float w) {
    if (w <= 0.0f || !std::isfinite(w) || !std::isfinite(offset)) return 0.0f;
    const float limit = MaxNdcDisparity * w;
    return std::clamp(offset, -limit, limit);
}

struct Projection {
    float scale = 0.0f;
    float focalX = 0.0f;
    bool identity = false;

    void Load(const float p[4][4]) {
        *this = {};
        bool isIdentity = true;
        bool perspective = true;
        for (unsigned i = 0; i < 4; ++i) {
            for (unsigned j = 0; j < 4; ++j) {
                if (!std::isfinite(p[i][j])) return;
                if (std::fabs(p[i][j] - (i == j ? 1.0f : 0.0f)) > 0.00002f) isIdentity = false;
                const bool coefficient = (i == 0 && j == 0) || (i == 1 && j == 1) ||
                                         (i == 2 && j == 2) || (i == 2 && j == 3) || (i == 3 && j == 2);
                if (!coefficient && std::fabs(p[i][j]) > 0.00002f) perspective = false;
            }
        }
        identity = isIdentity;
        if (perspective && p[2][3] < -0.00001f && std::fabs(p[0][0]) > 0.00001f &&
            std::fabs(p[1][1]) > 0.00001f && p[3][2] < 0.0f) {
            scale = -p[2][3];
            focalX = p[0][0] / scale;
        }
    }

    void Multiply(const float m[4][4]) {
        if (identity) { Load(m); return; }
        // OoT loads P, then multiplies the affine view on its left. Preserve
        // P's original scale; the resulting combined matrix is not a pure P.
        for (unsigned i = 0; i < 4; ++i) {
            for (unsigned j = 0; j < 4; ++j) {
                if (!std::isfinite(m[i][j])) { *this = {}; return; }
            }
            if (std::fabs(m[i][3] - (i == 3 ? 1.0f : 0.0f)) > 0.00002f) {
                *this = {};
                return;
            }
        }
    }

    float ClipOffset(float w, float aspect = 1.0f, float convergence = Convergence) const {
        if (scale <= 0.0f || w <= 0.0f || !std::isfinite(w) || !std::isfinite(aspect)) return 0.0f;
        // Row-vector off-axis projection: x' = x + fx*e*(w/Z0 - scale).
        // Using |fx| keeps depth direction stable under a mirrored projection.
        if (!std::isfinite(convergence) || convergence <= 0.0f) convergence = Convergence;
        const float offset = std::fabs(focalX) * aspect * EyeSeparation * (w / convergence - scale);
        return ClampClipOffset(offset, w);
    }
};

} // namespace Fast::Stereo3DS
