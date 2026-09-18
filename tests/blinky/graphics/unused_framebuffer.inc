// Regression for unused framebuffer bindings in the Blinky CPU raster path.
// Exercises the production renderer and the maintained host GPU collaborators;
// it does not emulate PICA timing. The extracted LUS decoder remains upstream.
#include <cstdlib>

namespace {
struct FramebufferSnapshotResult {
    unsigned copies;
    std::array<uint16_t, 16 * 16> pixels;
};

FramebufferSnapshotResult RenderWithUnusedFramebuffer(bool bindFramebuffer, bool declaredButUnused) {
    Fast::GfxRenderingAPIBlinkyCitro3D gpu;
    gpu.Init();
    gpu.UpdateFramebufferParameters(0, 16, 16, 1, false, true, true, true);
    gpu.SetViewport(0, 0, 16, 16);
    gpu.SetScissor(0, 0, 16, 16);
    gpu.StartFrame();
    gpu.ClearFramebuffer(true, true);

    // The second recipe declares TEXEL0 in (TEXEL0-TEXEL0)*INPUT1+INPUT1,
    // but its result cannot read that sampler. This checks actual dependencies,
    // not merely the packed vertex layout's usedTextures flag.
    const uint64_t recipe = declaredButUnused ? 0x1188 : 0x1000;
    const uint64_t options = (uint64_t(0xffff) << 17) | 128;
    auto* shader = gpu.CreateAndLoadNewShader(recipe, options);
    uint8_t inputCount = 0;
    bool usedTextures[2];
    gpu.ShaderGetInfo(shader, &inputCount, usedTextures);
    assert(inputCount == 1 && usedTextures[0] == declaredButUnused && !usedTextures[1]);
    if (bindFramebuffer) gpu.SelectTextureFb(0);

    constexpr float corners[6][2] = {{-1,-1}, {1,-1}, {1,1}, {-1,-1}, {1,1}, {-1,1}};
    std::vector<float> vertices;
    for (const auto& corner : corners) {
        vertices.insert(vertices.end(), {corner[0], corner[1], 0, 1});
        if (declaredButUnused) vertices.insert(vertices.end(), {0.5f, 0.5f});
        // A nonzero grayscale effect keeps this a real fragment-effects
        // fallback; this is not an identity effect added only to force CPU.
        vertices.insert(vertices.end(), {0, 1, 0, 0.5f, 1, 0, 0});
    }
    gpu.SetDepthTestAndMask(true, true);
    const unsigned before = gpuFake::copies;
    gpu.DrawTriangles(vertices.data(), vertices.size(), 2);
    FramebufferSnapshotResult result{gpuFake::copies - before, {}};
    gpu.ReadFramebufferToCPU(0, 16, 16, result.pixels.data());
    // Red transformed halfway toward a green-tinted intensity: (1/2,1/6,0).
    for (uint16_t pixel : result.pixels) assert(pixel == 0x8141);
    return result;
}
}

static void UnusedFramebufferSnapshots() {
    const auto plain = RenderWithUnusedFramebuffer(false, false);
    const auto bound = RenderWithUnusedFramebuffer(true, false);
    const auto declared = RenderWithUnusedFramebuffer(true, true);
    assert(plain.copies > 0 && plain.pixels == bound.pixels && plain.pixels == declared.pixels);
    if (bound.copies != plain.copies || declared.copies != plain.copies) {
        std::fprintf(stderr,
            "FAIL unused framebuffer snapshots: plain=%u bound=%u declared_unused=%u\n",
            plain.copies, bound.copies, declared.copies);
        std::exit(86);
    }
    std::printf("PASS unused framebuffer snapshots: absent and canceled samplers preserve pixels with no extra readbacks (%u copies each)\n", plain.copies);
}
