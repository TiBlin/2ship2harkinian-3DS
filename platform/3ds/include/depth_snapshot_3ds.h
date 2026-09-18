#pragma once

#include <cmath>
#include <cstdint>
#include <cstring>
#include <new>
#include <vector>

// CPU-owned copy of a completed PICA D16 or D24S8 buffer. Retaining the packed
// layout makes capture a memcpy, with conversion only at queried pixels.
class DepthSnapshot3DS {
  public:
    enum class Format { D16, D24S8 };

    bool requested = false;
    static constexpr uint16_t Far = 0xFFFC;

    void Reset() {
        requested = false;
        valid = false;
        std::vector<uint8_t>().swap(pixels);
    }

    bool Capture(const void* source, uint32_t width, uint32_t height,
                 uint32_t contentWidth, uint32_t contentHeight, bool rotate,
                 Format format = Format::D24S8) {
        valid = false;
        if (format != Format::D16 && format != Format::D24S8) return false;
        if (!source || width == 0 || height == 0 || width > 1024 || height > 1024 ||
            width % 8 || height % 8 || contentWidth == 0 || contentHeight == 0 ||
            contentWidth > (rotate ? height : width) || contentHeight > (rotate ? width : height)) {
            return false;
        }
        const size_t pixelBytes = format == Format::D16 ? 2U : 4U;
        try {
            pixels.resize(static_cast<size_t>(width) * height * pixelBytes);
        } catch (const std::bad_alloc&) {
            return false;
        }
        std::memcpy(pixels.data(), source, pixels.size());
        backingWidth = width;
        backingHeight = height;
        drawWidth = contentWidth;
        drawHeight = contentHeight;
        rotated = rotate;
        depthFormat = format;
        valid = true;
        return true;
    }

    uint16_t Sample(float x, float y) const {
        if (!valid || !std::isfinite(x) || !std::isfinite(y) || x < 0 || y < 0 || x >= 400 || y >= 240) {
            return Far;
        }
        // Same containing-pixel convention as GL's integer glReadPixels args.
        const uint32_t px = static_cast<uint32_t>(x * drawWidth / 400.f);
        const uint32_t py = static_cast<uint32_t>(y * drawHeight / 240.f);
        if (px >= drawWidth || py >= drawHeight) return Far;
        // Queries use GL window coordinates (Y up). The tilted projection
        // maps (x,y) to (y,-x); PICA memory then reverses rasterizer Y about
        // the full backing height, including any power-of-two padding.
        const uint32_t tx = rotated ? py : px;
        const uint32_t ty = rotated ? backingHeight - drawWidth + px : backingHeight - 1 - py;
        size_t morton = 0;
        for (unsigned bit = 0; bit < 3; ++bit) {
            morton |= ((tx >> bit) & 1U) << (2 * bit);
            morton |= ((ty >> bit) & 1U) << (2 * bit + 1);
        }
        const size_t offset = ((ty / 8U) * (backingWidth / 8U) + tx / 8U) * 64U + morton;
        // PICA uses little-endian reversed depth: zero is far. Both formats
        // use the same Morton pixel order; only the bytes per pixel differ.
        // Return the same 14-bit N64 depth convention in either case.
        if (depthFormat == Format::D16) {
            const size_t byte = offset * 2U;
            const uint32_t depth = pixels[byte] | (uint32_t(pixels[byte + 1]) << 8U);
            return static_cast<uint16_t>((0xFFFFU - depth) & 0xFFFCU);
        }
        const size_t byte = offset * 4U;
        const uint32_t depth = pixels[byte] | (uint32_t(pixels[byte + 1]) << 8U) |
                               (uint32_t(pixels[byte + 2]) << 16U);
        // The fourth byte of D24S8 is stencil and never contributes to depth.
        return static_cast<uint16_t>(((0xFFFFFFU - depth) >> 10U) << 2U);
    }

  private:
    std::vector<uint8_t> pixels;
    uint32_t backingWidth = 0, backingHeight = 0, drawWidth = 0, drawHeight = 0;
    bool valid = false, rotated = false;
    Format depthFormat = Format::D24S8;
};
