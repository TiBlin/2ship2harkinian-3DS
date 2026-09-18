#pragma once
#include "fast/backends/gfx_rendering_api.h"
#include <memory>
namespace Fast {
class GfxRenderingAPIBlinkyCitro3D final: public GfxRenderingAPI {
public:
    GfxRenderingAPIBlinkyCitro3D();
    ~GfxRenderingAPIBlinkyCitro3D() override;
    const char* GetName() override;
    int GetMaxTextureSize() override;
    GfxClipParameters GetClipParameters() override;
    void UnloadShader(ShaderProgram*) override;
    void LoadShader(ShaderProgram*) override;
    void ClearShaderCache() override;
    ShaderProgram* CreateAndLoadNewShader(uint64_t,uint64_t) override;
    ShaderProgram* LookupShader(uint64_t,uint64_t) override;
    void ShaderGetInfo(ShaderProgram*,uint8_t*,bool[2]) override;
    uint32_t NewTexture() override;
    void SelectTexture(int,uint32_t) override;
    void UploadTexture(const uint8_t*,uint32_t,uint32_t) override;
    void SetSamplerParameters(int,bool,uint32_t,uint32_t) override;
    void SetDepthTestAndMask(bool,bool) override;
    void SetZmodeDecal(bool) override;
    void SetViewport(int,int,int,int) override;
    void SetScissor(int,int,int,int) override;
    void SetUseAlpha(bool) override;
    void DrawTriangles(float[],size_t,size_t) override;
    void Init() override;
    void OnResize() override;
    void StartFrame() override;
    void EndFrame() override;
    void FinishRender() override;
    int CreateFramebuffer() override;
    void UpdateFramebufferParameters(int,uint32_t,uint32_t,uint32_t,bool,bool,bool,bool) override;
    void StartDrawToFramebuffer(int,float) override;
    void CopyFramebuffer(int,int,int,int,int,int,int,int,int,int) override;
    void ClearFramebuffer(bool,bool) override;
    void ClearDepthRegion(int,int,int,int) override;
    void ReadFramebufferToCPU(int,uint32_t,uint32_t,uint16_t*) override;
    void ResolveMSAAColorBuffer(int,int) override;
    std::unordered_map<std::pair<float,float>,uint16_t,hash_pair_ff>
    GetPixelDepth(int,const std::set<std::pair<float,float>>&) override;
    void* GetFramebufferTextureId(int) override;
    void SelectTextureFb(int) override;
    void DeleteTexture(uint32_t) override;
    bool TextureHasStorage(uint32_t) override;
    void SetTextureFilter(FilteringMode) override;
    FilteringMode GetTextureFilter() override;
    void SetSrgbMode() override;
    ImTextureID GetTextureById(int) override;
    void SetCurrentPrimDepth(float) override;
private:
    struct Device;
    std::unique_ptr<Device> device;
};
GfxRenderingAPI* CreateBlinkyCitro3DRenderingAPI();
}
