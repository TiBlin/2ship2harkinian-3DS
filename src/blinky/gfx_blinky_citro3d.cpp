#include "gfx_blinky_citro3d.h"
#include "render_core.h"
#include <ship/port/3ds/BlinkyVisibility.h>
#if BLINKY_OCCLUSION_CULLING
#include "coarse_occlusion.h"
#endif
#include "fast/interpreter.h"
#include "ship/port/3ds/BlinkyLifecycle.h"
#include <3ds.h>
#include <citro3d.h>
#include <array>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <map>
#include <stdexcept>
#include <vector>
#include <limits>

extern "C" const unsigned char blinky_passthrough_shbin[];
extern "C" const unsigned int blinky_passthrough_shbin_size;
extern "C" int BlinkyTargetFps();
extern "C" void BlinkyPresentDiagnostics(uint64_t,uint64_t,uint64_t,uint64_t,uint64_t);
extern "C" void BlinkyDisplayReady(bool);
extern "C" int BlinkyPreferredTextureFilter();

namespace Fast {
namespace {
using Blinky::Color;
constexpr size_t VertexCapacity=16384;
struct PackedVertex { float clip[4],color[4],uv0[2],uv1[2],foguv[2]; };
struct Vertex {
    float clip[4]{};
    Color input[7]{},fog{},gray{};
    float uv[2][2]{},clamp[2][2]{{1,1},{1,1}};
};
struct Program {
    uint64_t id0=0,id1=0,hits=0,reference=0,rejected=0;
    CCFeatures features{};
    Blinky::Recipe recipe{};
    // CCFeatures describes the packed LUS vertex layout, which can include
    // UVs for unused samplers. Only the active combiner reads need storage.
    std::array<bool,2> sampled{};
    unsigned stride=0;
    std::map<std::string,uint64_t> reasons;
};
struct NativeTexture {
    C3D_Tex native{};
    unsigned width=0,height=0,wrapS=0,wrapT=0;
    bool ready=false,linear=false,framebuffer=false;
    unsigned paddingS=2,paddingT=2;
    bool freshUpload=false;
    uint64_t lastUse=0;
    ~NativeTexture(){if(ready)C3D_TexDelete(&native);}
};
struct Target {
    std::unique_ptr<NativeTexture> image;
    C3D_RenderTarget* native=nullptr;
    unsigned width=0,height=0;
    bool invertY=false;
    ~Target(){if(native)C3D_RenderTargetDelete(native);}
};
struct Linear {
    void* data=nullptr;size_t size=0;
    explicit Linear(size_t n):data(linearAlloc(n)),size(n){if(!data)throw std::bad_alloc();}
    ~Linear(){linearFree(data);}
    Linear(const Linear&)=delete;
};
struct Snapshot {
    Linear color;
    std::unique_ptr<Linear> depth;
    unsigned pitch,height;
    explicit Snapshot(Target& target):color(target.image->native.size),
      pitch(target.image->native.width),height(target.image->native.height) {
        BLINKY_RENDER_COUNT(copies,1);BLINKY_RENDER_COUNT(copyBytes,color.size);
        C3D_SyncTextureCopy(static_cast<u32*>(target.native->frameBuf.colorBuf),0,
            static_cast<u32*>(color.data),0,color.size,GX_TRANSFER_RAW_COPY(1));
        if(R_FAILED(GSPGPU_InvalidateDataCache(color.data,color.size)))throw std::runtime_error("Blinky color read cache");
        if(target.native->frameBuf.depthBuf) {
            depth=std::make_unique<Linear>(pitch*height*2);
            BLINKY_RENDER_COUNT(copies,1);BLINKY_RENDER_COUNT(copyBytes,depth->size);
            C3D_SyncTextureCopy(static_cast<u32*>(target.native->frameBuf.depthBuf),0,
                static_cast<u32*>(depth->data),0,depth->size,GX_TRANSFER_RAW_COPY(1));
            if(R_FAILED(GSPGPU_InvalidateDataCache(depth->data,depth->size)))throw std::runtime_error("Blinky depth read cache");
        }
    }
    Color Get(unsigned x,unsigned y) const {
        // PICA raster coordinates count upward; tiled storage counts from the
        // opposite edge of the allocated surface, including its padding.
        auto p=static_cast<uint8_t*>(color.data)+Blinky::TileOffset(x,height-1-y,pitch)*4;
        return {p[3]/255.f,p[2]/255.f,p[1]/255.f,p[0]/255.f};
    }
    void Set(unsigned x,unsigned y,Color c) {
        auto p=static_cast<uint8_t*>(color.data)+Blinky::TileOffset(x,height-1-y,pitch)*4;
        for(unsigned i=0;i<4;++i)p[3-i]=Blinky::Byte(c[i]);
    }
    uint16_t& Z(unsigned x,unsigned y){return static_cast<uint16_t*>(depth->data)[Blinky::TileOffset(x,height-1-y,pitch)];}
    void Store(Target& target,bool includeDepth=true) {
        if(R_FAILED(GSPGPU_FlushDataCache(color.data,color.size)))throw std::runtime_error("Blinky color write cache");
        BLINKY_RENDER_COUNT(copies,1);BLINKY_RENDER_COUNT(copyBytes,color.size);
        C3D_SyncTextureCopy(static_cast<u32*>(color.data),0,static_cast<u32*>(target.native->frameBuf.colorBuf),0,color.size,GX_TRANSFER_RAW_COPY(1));
        if(includeDepth && depth) {
            if(R_FAILED(GSPGPU_FlushDataCache(depth->data,depth->size)))throw std::runtime_error("Blinky depth write cache");
            BLINKY_RENDER_COUNT(copies,1);BLINKY_RENDER_COUNT(copyBytes,depth->size);
            C3D_SyncTextureCopy(static_cast<u32*>(depth->data),0,static_cast<u32*>(target.native->frameBuf.depthBuf),0,depth->size,GX_TRANSFER_RAW_COPY(1));
        }
    }
};
Vertex Interpolate(const Vertex& a,const Vertex& b,float t) {
    Vertex result;
    for(unsigned i=0;i<4;++i) {
        result.clip[i]=a.clip[i]+t*(b.clip[i]-a.clip[i]);
        result.fog[i]=a.fog[i]+t*(b.fog[i]-a.fog[i]);
        result.gray[i]=a.gray[i]+t*(b.gray[i]-a.gray[i]);
        for(unsigned j=0;j<7;++j)result.input[j][i]=a.input[j][i]+t*(b.input[j][i]-a.input[j][i]);
    }
    for(unsigned u=0;u<2;++u)for(unsigned axis=0;axis<2;++axis) {
        result.uv[u][axis]=a.uv[u][axis]+t*(b.uv[u][axis]-a.uv[u][axis]);
        result.clamp[u][axis]=a.clamp[u][axis]+t*(b.clamp[u][axis]-a.clamp[u][axis]);
    }
    return result;
}
float Plane(const Vertex& v,unsigned plane) {return v.clip[3]+(plane&1?-v.clip[plane/2]:v.clip[plane/2]);}
// Clamping a varying at the three corners is incorrect when a triangle crosses
// a clamp boundary. Split at that boundary first, then each resulting polygon
// has a linear (or constant) coordinate. Clip-space interpolation preserves the
// perspective-correct values of every other attribute.
void PartitionCoordinates(std::vector<std::vector<Vertex>>& polygons,unsigned unit,unsigned axis,float low) {
    for(unsigned boundary=0;boundary<2;++boundary) {
        std::vector<std::vector<Vertex>> next;
        auto distance=[&](const Vertex& v){return v.uv[unit][axis]-(boundary?v.clamp[unit][axis]:low);};
        for(const auto& polygon:polygons) {
            float minimum=0,maximum=0;
            for(const auto& v:polygon){float d=distance(v);minimum=std::min(minimum,d);maximum=std::max(maximum,d);}
            if(minimum>=0 || maximum<=0){next.push_back(polygon);continue;}
            std::vector<Vertex> sides[2];
            auto prior=polygon.back();float pd=distance(prior);
            for(const auto& vertex:polygon) {
                float vd=distance(vertex);
                if((pd<0 && vd>0) || (pd>0 && vd<0)) {
                    auto crossing=Interpolate(prior,vertex,pd/(pd-vd));
                    crossing.uv[unit][axis]=boundary?crossing.clamp[unit][axis]:low;
                    sides[0].push_back(crossing);sides[1].push_back(crossing);
                }
                if(vd<=0)sides[0].push_back(vertex);
                if(vd>=0)sides[1].push_back(vertex);
                prior=vertex;pd=vd;
            }
            for(auto& side:sides)if(side.size()>=3)next.push_back(std::move(side));
        }
        polygons.swap(next);
    }
    for(auto& polygon:polygons)for(auto& v:polygon)
        v.uv[unit][axis]=std::clamp(v.uv[unit][axis],low,v.clamp[unit][axis]);
}
std::vector<Vertex> Clip(const Vertex (&input)[3]) {
    std::vector<Vertex> polygon(input,input+3),next;next.reserve(12);
    for(unsigned plane=0;plane<6 && !polygon.empty();++plane) {
        next.clear();auto prior=polygon.back();float pd=Plane(prior,plane);
        for(const auto& vertex:polygon) {
            float vd=Plane(vertex,plane);
            if((pd>=0)!=(vd>=0))next.push_back(Interpolate(prior,vertex,pd/(pd-vd)));
            if(vd>=0)next.push_back(vertex);
            prior=vertex;pd=vd;
        }
        polygon.swap(next);
    }
    return polygon;
}
Color Fetch(const NativeTexture& texture,int x,int y,const Snapshot* framebuffer=nullptr) {
    x=Blinky::Address(x,texture.width,texture.wrapS);y=Blinky::Address(y,texture.height,texture.wrapT);
    if(framebuffer)return framebuffer->Get(x,y);
    auto p=static_cast<const uint8_t*>(texture.native.data)+Blinky::TileOffset(x,texture.native.height-1-y,texture.native.width)*4;
    return {p[3]/255.f,p[2]/255.f,p[1]/255.f,p[0]/255.f};
}
Color Sample(const NativeTexture& texture,float u,float v,FilteringMode filter,const Snapshot* framebuffer=nullptr) {
    float x=u*texture.width,y=v*texture.height;
    if(!texture.linear || filter==FILTER_NONE)return Fetch(texture,static_cast<int>(std::floor(x)),static_cast<int>(std::floor(y)),framebuffer);
    x-=0.5f;y-=0.5f;int ix=static_cast<int>(std::floor(x)),iy=static_cast<int>(std::floor(y));float a=x-ix,b=y-iy;
    Color p=Fetch(texture,ix,iy,framebuffer),q=Fetch(texture,ix+1,iy,framebuffer),r=Fetch(texture,ix,iy+1,framebuffer),s=Fetch(texture,ix+1,iy+1,framebuffer),out{};
    for(unsigned lane=0;lane<4;++lane) {
        if(filter==FILTER_THREE_POINT)out[lane]=a+b<=1?p[lane]+a*(q[lane]-p[lane])+b*(r[lane]-p[lane]):s[lane]+(1-a)*(r[lane]-s[lane])+(1-b)*(q[lane]-s[lane]);
        else out[lane]=(p[lane]*(1-a)+q[lane]*a)*(1-b)+(r[lane]*(1-a)+s[lane]*a)*b;
    }
    return out;
}
}

struct GfxRenderingAPIBlinkyCitro3D::Device {
    bool initialized=false,open=false,depthTest=false,depthWrite=false,decal=false,blend=false;
#if BLINKY_OCCLUSION_CULLING
    Blinky::CoarseOcclusion occlusion;
    bool OcclusionEligible() {
        if(gfxIs3D() || BlinkyVisibilityGetScope()!=BLINKY_SCOPE_ROOM_OPA || !current ||
           !depthTest || decal || blend || !Active().native->frameBuf.depthBuf)return false;
        const auto& f=current->features;
        if(f.shader_id!=-1 || f.opt_prim_depth || f.opt_texture_edge || f.opt_alpha_threshold ||
           f.opt_noise || f.opt_invisible || f.opt_grayscale)return false;
        for(unsigned i=0;i<2;++i)if(current->sampled[i] &&
            (f.used_masks[i] || f.used_blend[i] || !bound[i] || bound[i]->framebuffer))return false;
        // Full target viewport and scissor only. No coordinate conversion or
        // inference about partially clipped cells is needed in this prototype.
        if(viewport[0]!=0 || viewport[1]!=0 || viewport[2]!=int(Active().width) ||
           viewport[3]!=int(Active().height) || scissor[0]>0 || scissor[1]>0 ||
           scissor[0]+scissor[2]<viewport[2] || scissor[1]+scissor[3]<viewport[3])return false;
        return occlusion.Configure(Active().width,Active().height);
    }
    void InvalidateOcclusion() {
        if(occlusion.KnownCells()){
            BLINKY_PROFILE(occlusionTicks);
            occlusion.Invalidate();BLINKY_RENDER_COUNT(invalidations,1);
        }
    }
    void OcclusionReport() {
#if BLINKY_RENDER_STATS
        const auto& c=occlusion.counters;
        gBlinkyRenderStats.tested=c.tests;gBlinkyRenderStats.occluders=c.occluders;
        gBlinkyRenderStats.cellsWritten=c.writes;gBlinkyRenderStats.budgetStops=c.budgetStops;
#endif
#if BLINKY_OCCLUSION_DEBUG
        if(frames%120==0)if(FILE* file=std::fopen("blinky-occlusion.pgm","wb")) {
            std::fputs("P5\n50 30\n255\n",file);
            for(auto depth:occlusion.Cells())std::fputc(depth==65535?0:1+((65535-depth)*254u/65535),file);
            std::fclose(file);
        }
#endif
    }
#endif
    float primitiveDepth=0,noiseScale=1;
    FilteringMode filtering=FILTER_LINEAR;
    int activeTarget=0,selectedUnit=0;
    std::array<int,4> viewport{0,0,400,240},scissor{0,0,400,240};
    std::map<std::pair<uint64_t,uint64_t>,std::unique_ptr<Program>> programs;
    Program* current=nullptr;
    std::vector<std::unique_ptr<NativeTexture>> textures,retired;
    std::vector<std::unique_ptr<Target>> targets;
    std::array<NativeTexture*,6> bound{};
    DVLB_s* binary=nullptr;
    shaderProgram_s shader{};
    PackedVertex* vertices=nullptr;
    size_t vertexCount=0,commandDraws=0;
    C3D_RenderTarget* display=nullptr;
    C3D_Tex fogRamp{};
    bool fogRampReady=false;
    std::vector<PackedVertex> packet,hardwareBatch;
    std::array<C3D_TexEnv,6> batchStages{};
    uint32_t batchBufferColor=0;
    bool batchFog=false;
    uint64_t frames=0,draws=0,triangles=0,cpuTriangles=0,uploads=0;
    uint64_t frameStart=0;
    std::unique_ptr<Snapshot> referenceImage;
    void FlushReference() {
        if(referenceImage){referenceImage->Store(Active());referenceImage.reset();}
    }
    void FlushVertices() {
        if(vertexCount && R_FAILED(GSPGPU_FlushDataCache(vertices,vertexCount*sizeof(PackedVertex))))
            throw std::runtime_error("Blinky vertex cache flush");
    }
    void Wait() {
        BLINKY_PROFILE(fenceTicks);BLINKY_RENDER_COUNT(fences,1);
        FlushHardwareBatch();
        FlushReference();
        if(open){FlushVertices();C3D_FrameEnd(GX_CMDLIST_FLUSH);open=false;}
        if(initialized){
            if(!C3D_FrameBegin(0))throw std::runtime_error("Blinky GPU fence");
            C3D_FrameEnd(GX_CMDLIST_FLUSH);
        }
        // Remain OUTSIDE a frame. Citro3D's SyncTextureCopy is asynchronous
        // inside a frame; CPU snapshots and RenderTargetDelete require this.
        vertexCount=commandDraws=0;retired.clear();
    }
    void Bind() {
        C3D_BindProgram(&shader);C3D_CullFace(GPU_CULL_NONE);C3D_DepthMap(true,-1,0);
        C3D_AttrInfo* attributes=C3D_GetAttrInfo();AttrInfo_Init(attributes);
        AttrInfo_AddLoader(attributes,0,GPU_FLOAT,4);AttrInfo_AddLoader(attributes,1,GPU_FLOAT,4);
        AttrInfo_AddLoader(attributes,2,GPU_FLOAT,2);AttrInfo_AddLoader(attributes,3,GPU_FLOAT,2);
        AttrInfo_AddLoader(attributes,4,GPU_FLOAT,2);
    }
    void Reserve(size_t count) {
        if(vertexCount+count>VertexCapacity || commandDraws>=256){BLINKY_RENDER_COUNT(commandSplits,1);Wait();}
        if(!open){if(!C3D_FrameBegin(0))throw std::runtime_error("Blinky frame begin");open=true;}
    }
    void DrawPacked(const PackedVertex* input,size_t count) {
        std::memcpy(vertices+vertexCount,input,count*sizeof(PackedVertex));
        auto* buffers=C3D_GetBufInfo();BufInfo_Init(buffers);
        BufInfo_Add(buffers,vertices+vertexCount,sizeof(PackedVertex),5,0x43210);
        BLINKY_RENDER_COUNT(gpuDraws,1);BLINKY_RENDER_COUNT(gpuTriangles,count/3);BLINKY_RENDER_COUNT(gpuVertices,count);
        C3D_DrawArrays(GPU_TRIANGLES,0,count);vertexCount+=count;++commandDraws;
    }
    void FlushHardwareBatch() {
        if(hardwareBatch.empty())return;
        // Empty the pending queue before Reserve can fence and call Wait.
        std::vector<PackedVertex> upload;upload.swap(hardwareBatch);
        bool edge=current->recipe.useAlpha && current->features.opt_texture_edge;
        FlushReference();if(edge && commandDraws>=255)Wait();Reserve(upload.size());State();
        if(batchFog)C3D_TexBind(2,&fogRamp);
        C3D_TexEnvBufUpdate(C3D_Both,0);C3D_TexEnvBufColor(batchBufferColor);
        for(unsigned i=0;i<6;++i)C3D_SetTexEnv(i,&batchStages[i]);
        if(edge) {
            // The alpha test needs the original alpha; replacing it with 1 in
            // TexEnv would also fill transparent holes. Set surviving alpha
            // first without changing depth, then write opaque RGB and depth.
            // This order preserves strict depth rejection at equal Z.
            C3D_AlphaTest(true,GPU_GREATER,48);
            C3D_DepthTest(depthTest,depthTest?(decal?GPU_GEQUAL:GPU_GREATER):GPU_ALWAYS,GPU_WRITE_ALPHA);
            C3D_ColorLogicOp(GPU_LOGICOP_SET);
        }
        DrawPacked(upload.data(),upload.size());
        if(edge) {
            C3D_DepthTest(depthTest||depthWrite,depthTest?(decal?GPU_GEQUAL:GPU_GREATER):GPU_ALWAYS,
                static_cast<GPU_WRITEMASK>((GPU_WRITE_COLOR&~GPU_WRITE_ALPHA)|(depthWrite?GPU_WRITE_DEPTH:0)));
            C3D_AlphaBlend(GPU_BLEND_ADD,GPU_BLEND_ADD,GPU_ONE,GPU_ZERO,GPU_ONE,GPU_ZERO);
            // Reuse the same immutable VBO range and the same alpha test.
            BLINKY_RENDER_COUNT(gpuDraws,1);BLINKY_RENDER_COUNT(gpuTriangles,upload.size()/3);BLINKY_RENDER_COUNT(gpuVertices,upload.size());
            C3D_DrawArrays(GPU_TRIANGLES,0,upload.size());++commandDraws;
        }
        upload.clear();upload.swap(hardwareBatch);
    }
    void QueueHardware(const std::array<C3D_TexEnv,6>& stages,uint32_t bufferColor,bool fog) {
        if(!hardwareBatch.empty() && (hardwareBatch.size()+packet.size()>VertexCapacity ||
            batchBufferColor!=bufferColor || batchFog!=fog ||
            std::memcmp(batchStages.data(),stages.data(),sizeof(stages))))FlushHardwareBatch();
        if(hardwareBatch.empty()){batchStages=stages;batchBufferColor=bufferColor;batchFog=fog;}
        hardwareBatch.insert(hardwareBatch.end(),packet.begin(),packet.end());
    }
    Target& Active(){return *targets.at(activeTarget);}
    void State() {
        Bind();auto& target=Active();C3D_FrameDrawOn(target.native);
        C3D_SetViewport(viewport[0],viewport[1],std::max(1,viewport[2]),std::max(1,viewport[3]));
        C3D_SetScissor(GPU_SCISSOR_NORMAL,std::max(0,scissor[0]),std::max(0,scissor[1]),
            std::max(1,scissor[0]+scissor[2]),std::max(1,scissor[1]+scissor[3]));
        C3D_DepthTest(depthTest||depthWrite,depthTest?(decal?GPU_GEQUAL:GPU_GREATER):GPU_ALWAYS,
            static_cast<GPU_WRITEMASK>(GPU_WRITE_COLOR|(depthWrite?GPU_WRITE_DEPTH:0)));
        C3D_AlphaTest(current && current->features.opt_alpha_threshold,GPU_GEQUAL,8);
        C3D_AlphaBlend(GPU_BLEND_ADD,GPU_BLEND_ADD,blend?GPU_SRC_ALPHA:GPU_ONE,blend?GPU_ONE_MINUS_SRC_ALPHA:GPU_ZERO,
            blend?GPU_SRC_ALPHA:GPU_ONE,blend?GPU_ONE_MINUS_SRC_ALPHA:GPU_ZERO);
        for(int i=0;i<2;++i)if(bound[i] && bound[i]->ready) {
            auto filter=bound[i]->linear && filtering!=FILTER_NONE?GPU_LINEAR:GPU_NEAREST;
            C3D_TexSetFilter(&bound[i]->native,filter,filter);C3D_TexBind(i,&bound[i]->native);
        }
    }
    void Report(bool final=false) {
        if(!final && frames%120)return;
        std::fprintf(stderr,"Blinky Citro3D: frames=%llu draws=%llu triangles=%llu reference=%llu shaders=%u uploads=%llu linear=%lu\n",
            (unsigned long long)frames,(unsigned long long)draws,(unsigned long long)triangles,
            (unsigned long long)cpuTriangles,(unsigned)programs.size(),(unsigned long long)uploads,(unsigned long)linearSpaceFree());
    }
    void Export() {
        FILE* file=std::fopen("blinky-shaders.json","w");if(!file)return;
        std::fprintf(file,"{\"renderer\":\"Blinky Citro3D\",\"hardware_validated\":false,\"shaders\":[");bool first=true;
        for(const auto& [key,p]:programs) {
            std::fprintf(file,"%s{\"shaderId0\":\"%016llx\",\"shaderId1\":\"%016llx\",\"numInputs\":%d,\"usedTextures\":[%s,%s],\"cycles\":%u,\"draws\":%llu,\"referenceTriangles\":%llu,\"combiner\":[",
                first?"":",",(unsigned long long)key.first,(unsigned long long)key.second,p->features.numInputs,
                p->features.usedTextures[0]?"true":"false",p->features.usedTextures[1]?"true":"false",p->recipe.cycles,
                (unsigned long long)p->hits,(unsigned long long)p->reference);first=false;
            for(unsigned c=0;c<p->recipe.cycles;++c)for(unsigned lane=0;lane<2;++lane) {
                auto& t=(lane?p->recipe.alpha[c]:p->recipe.color[c]).term;
                std::fprintf(file,"%s[%u,%u,%u,%u]",c||lane?",":"",t[0],t[1],t[2],t[3]);
            }
            std::fprintf(file,"],\"options\":%llu,\"support\":\"%s\",\"rejectedDraws\":%llu,\"referenceReasons\":{",
                (unsigned long long)p->id1,p->features.shader_id==-1?"gpu-or-cpu-reference":"rejected-custom-shader",(unsigned long long)p->rejected);
            bool firstReason=true;
            for(const auto& [reason,count]:p->reasons){std::fprintf(file,"%s\"%s\":%llu",firstReason?"":",",reason.c_str(),(unsigned long long)count);firstReason=false;}
            std::fprintf(file,"}}");
        }
        std::fputs("]}\n",file);std::fclose(file);
    }
    ~Device() {
        if(!initialized)return;
        Ship::Blinky3DS::ClearRendererLifecycleCallbacks();
        FlushHardwareBatch();
        FlushReference();if(open){FlushVertices();C3D_FrameEnd(GX_CMDLIST_FLUSH);open=false;}
        if(C3D_FrameBegin(0))C3D_FrameEnd(GX_CMDLIST_FLUSH);
        Report(true);Export();targets.clear();textures.clear();retired.clear();
        if(fogRampReady)C3D_TexDelete(&fogRamp);
        if(display)C3D_RenderTargetDelete(display);
        if(vertices)linearFree(vertices);
        shaderProgramFree(&shader);if(binary)DVLB_Free(binary);
        BlinkyDisplayReady(false);C3D_Fini();gfxExit();
    }
    bool Hardware(const Vertex (&v)[3]);
    void Reference(const Vertex (&v)[3]);
    bool Fallback(const char* reason) {
        auto& count=current->reasons[reason];
        if(!count)std::fprintf(stderr,"Blinky reference shader=%016llx:%016llx inputs=%d textures=%d/%d cycles=%u reason=%s\n",
            (unsigned long long)current->id0,(unsigned long long)current->id1,current->features.numInputs,
            current->features.usedTextures[0],current->features.usedTextures[1],current->recipe.cycles,reason);
        ++count;return false;
    }
};

GfxRenderingAPIBlinkyCitro3D::GfxRenderingAPIBlinkyCitro3D():device(std::make_unique<Device>()){}
GfxRenderingAPIBlinkyCitro3D::~GfxRenderingAPIBlinkyCitro3D()=default;
const char* GfxRenderingAPIBlinkyCitro3D::GetName(){return "Blinky Citro3D";}
int GfxRenderingAPIBlinkyCitro3D::GetMaxTextureSize(){return 1024;}
GfxClipParameters GfxRenderingAPIBlinkyCitro3D::GetClipParameters(){return {false,device->Active().invertY};}
void GfxRenderingAPIBlinkyCitro3D::UnloadShader(ShaderProgram*){device->current=nullptr;}
void GfxRenderingAPIBlinkyCitro3D::LoadShader(ShaderProgram* p){device->current=reinterpret_cast<Program*>(p);}
void GfxRenderingAPIBlinkyCitro3D::ClearShaderCache(){device->current=nullptr;device->programs.clear();}
ShaderProgram* GfxRenderingAPIBlinkyCitro3D::LookupShader(uint64_t a,uint64_t b){auto i=device->programs.find({a,b});return i==device->programs.end()?nullptr:reinterpret_cast<ShaderProgram*>(i->second.get());}
ShaderProgram* GfxRenderingAPIBlinkyCitro3D::CreateAndLoadNewShader(uint64_t a,uint64_t b){
    if(auto* cached=LookupShader(a,b)){LoadShader(cached);return cached;}
    auto p=std::make_unique<Program>();p->id0=a;p->id1=b;gfx_cc_get_features(a,b,&p->features);
    auto& f=p->features;auto& r=p->recipe;r.cycles=f.opt_2cyc?2:1;r.inputs=f.numInputs;
    r.useAlpha=f.opt_alpha;r.fog=f.opt_fog;r.edge=f.opt_texture_edge;r.noise=f.opt_noise;
    r.threshold=f.opt_alpha_threshold;r.invisible=f.opt_invisible;r.gray=f.opt_grayscale;
    for(unsigned c=0;c<2;++c)for(unsigned term=0;term<4;++term){r.color[c].term[term]=f.c[c][0][term];r.alpha[c].term[term]=f.c[c][1][term];}
    p->sampled=Blinky::SampledTextures(r);
    p->stride=4+f.numInputs*(f.opt_alpha?4:3)+(f.opt_fog?4:0)+(f.opt_grayscale?4:0);
    for(unsigned unit=0;unit<2;++unit)if(f.usedTextures[unit])p->stride+=2+f.clamp[unit][0]+f.clamp[unit][1];
    device->current=p.get();auto* result=reinterpret_cast<ShaderProgram*>(p.get());device->programs.emplace(std::make_pair(a,b),std::move(p));return result;
}
void GfxRenderingAPIBlinkyCitro3D::ShaderGetInfo(ShaderProgram* shader,uint8_t* count,bool used[2]){
    auto& p=*reinterpret_cast<Program*>(shader);*count=p.features.numInputs;used[0]=p.features.usedTextures[0];used[1]=p.features.usedTextures[1];
}

bool GfxRenderingAPIBlinkyCitro3D::Device::Hardware(const Vertex (&v)[3]) {
    const auto& f=current->features;
    if(f.opt_grayscale || (f.opt_alpha && ((f.opt_noise && !f.opt_texture_edge) || f.opt_invisible)))
        return Fallback("fragment-effects");
    if(f.opt_fog)for(unsigned vertex=0;vertex<3;++vertex)for(unsigned lane=0;lane<4;++lane) {
        float value=v[vertex].fog[lane];
        if(!std::isfinite(value) || value<0 || value>1)return Fallback("fog-range");
        if(lane<3 && value!=v[0].fog[lane])return Fallback("varying-fog-color");
    }
    for(unsigned unit=0;unit<2;++unit)if(current->sampled[unit]) {
        if(f.used_masks[unit])return Fallback("texture-mask");
        auto* t=bound[unit];
        if(!t || !t->ready)throw std::runtime_error("Blinky draw references absent texture");
        if(t==Active().image.get())return Fallback("framebuffer-feedback");
        for(unsigned axis=0;axis<2;++axis)if(f.clamp[unit][axis])for(const auto& vertex:v) {
            float low=0.5f/(axis?t->height:t->width),limit=vertex.clamp[unit][axis];
            if(!std::isfinite(limit) || limit<low || !std::isfinite(vertex.uv[unit][axis]))
                return Fallback("texture-clamp-range");
        }
        if(filtering==FILTER_THREE_POINT && t->linear)return Fallback("three-point-filter");
        if(t->wrapS==3 || t->wrapT==3)return Fallback("mirror-clamp");
        for(unsigned axis=0;axis<2;++axis) {
            unsigned size=axis?t->height:t->width,extent=axis?t->native.height:t->native.width;
            unsigned mode=axis?t->wrapT:t->wrapS,padding=axis?t->paddingT:t->paddingS;
            if(size==extent || (mode&2) || (!t->framebuffer && padding==(mode&1)))continue;
            bool interior=true;
            for(const auto& vertex:v) {
                float coordinate=vertex.uv[unit][axis];
                if(f.clamp[unit][axis])coordinate=std::clamp(coordinate,.5f/size,vertex.clamp[unit][axis]);
                interior&=coordinate>=.5f/size && coordinate<=(size-.5f)/size;
            }
            if(!interior)return Fallback("padded-repeat");
        }
    }
    // PICA has one interpolated primary color, one constant per TEV stage,
    // and an independently programmable previous-buffer color. A constant
    // vertex color is useful too: menu primitive/environment colors must not
    // all compete for the same TEV constant. Allocate RGB and alpha separately.
    int primaryInput[2]={-1,-1};
    for(unsigned channel=0;channel<(current->recipe.useAlpha?2u:1u);++channel) {
        int first=-1;
        for(unsigned cycle=0;cycle<current->recipe.cycles;++cycle) {
            auto formula=channel?current->recipe.alpha[cycle]:current->recipe.color[cycle];
            auto expression=Blinky::Lower(formula);
            if(!expression.exact)return Fallback("signed-combiner");
            unsigned count=expression.op==Blinky::Operation::Replace?1:expression.op==Blinky::Operation::Multiply?2:3;
            for(unsigned argument=0;argument<count;++argument) {
                auto source=expression.source[argument];
                if(source<Blinky::Input1 || source>Blinky::Input7)continue;
                int input=source-Blinky::Input1;
                if(first<0)first=input;
                bool varying=false;
                for(unsigned lane=channel?3:0;lane<(channel?4:3);++lane)
                    varying|=v[0].input[input][lane]!=v[1].input[input][lane] ||
                             v[0].input[input][lane]!=v[2].input[input][lane];
                if(varying) {
                    if(primaryInput[channel]>=0 && primaryInput[channel]!=input)
                        return Fallback("multiple-varying-inputs");
                    primaryInput[channel]=input;
                }
            }
        }
        if(primaryInput[channel]<0)primaryInput[channel]=first;
    }
    Color primary[3];
    for(unsigned vertex=0;vertex<3;++vertex)for(unsigned lane=0;lane<4;++lane) {
        int input=primaryInput[lane==3];
        primary[vertex][lane]=input<0?1:v[vertex].input[input][lane];
        if(!std::isfinite(primary[vertex][lane]) || primary[vertex][lane]<0 || primary[vertex][lane]>1)
            return Fallback("signed-primary-color");
    }
    Color bufferColor{};
    bool bufferAssigned[2]{};
    std::array<C3D_TexEnv,6> stages;
    for(auto& stage:stages)C3D_TexEnvInit(&stage);
    for(unsigned cycle=0;cycle<current->recipe.cycles;++cycle) {
        auto& stage=stages[cycle];Color constant{1,1,1,1};
        for(unsigned channel=0;channel<2;++channel) {
            Blinky::Formula formula=channel?current->recipe.alpha[cycle]:current->recipe.color[cycle];
            if(channel && !current->recipe.useAlpha)formula.term={0,0,0,Blinky::One};
            auto expression=Blinky::Lower(formula);
            if(!expression.exact)return Fallback("signed-combiner");
            unsigned count=expression.op==Blinky::Operation::Replace?1:expression.op==Blinky::Operation::Multiply?2:3;
            GPU_TEVSRC sources[3]={GPU_CONSTANT,GPU_CONSTANT,GPU_CONSTANT};
            GPU_TEVOP_RGB operands[3]={GPU_TEVOP_RGB_SRC_COLOR,GPU_TEVOP_RGB_SRC_COLOR,GPU_TEVOP_RGB_SRC_COLOR};
            bool hasConstant=false;Color required{};
            for(unsigned argument=0;argument<count;++argument) {
                const auto source=Blinky::CycleSource(expression.source[argument],cycle);Color value{};bool isConstant=false;
                if(source>=Blinky::Input1 && source<=Blinky::Input7) {
                    int index=source-Blinky::Input1;
                    if(index==primaryInput[channel])sources[argument]=GPU_PRIMARY_COLOR;
                    else {isConstant=true;value=v[0].input[index];}
                } else switch(source) {
                    case Blinky::Tex0:case Blinky::Tex0Alpha:sources[argument]=GPU_TEXTURE0;break;
                    case Blinky::Tex1:case Blinky::Tex1Alpha:sources[argument]=GPU_TEXTURE1;break;
                    case Blinky::Combined:
                        if(cycle)sources[argument]=GPU_PREVIOUS;else isConstant=true;
                        break;
                    case Blinky::Zero:isConstant=true;break;
                    case Blinky::One:isConstant=true;value={1,1,1,1};break;
                    default:return Fallback("noise-source");
                }
                if(source==Blinky::Tex0Alpha || source==Blinky::Tex1Alpha)operands[argument]=GPU_TEVOP_RGB_SRC_ALPHA;
                if(isConstant) {
                    bool matchesPrimary=true,matchesStage=true,matchesBuffer=true;
                    for(unsigned lane=channel?3:0;lane<(channel?4:3);++lane) {
                        if(!std::isfinite(value[lane]) || value[lane]<0 || value[lane]>1)
                            return Fallback("signed-constant");
                        for(unsigned vertex=0;vertex<3;++vertex)matchesPrimary&=value[lane]==primary[vertex][lane];
                        matchesStage&=!hasConstant || required[lane]==value[lane];
                        matchesBuffer&=!bufferAssigned[channel] || bufferColor[lane]==value[lane];
                    }
                    if(matchesPrimary)sources[argument]=GPU_PRIMARY_COLOR;
                    else if(matchesStage) {
                        for(unsigned lane=channel?3:0;lane<(channel?4:3);++lane)required[lane]=constant[lane]=value[lane];
                        hasConstant=true;sources[argument]=GPU_CONSTANT;
                    } else if(matchesBuffer) {
                        for(unsigned lane=channel?3:0;lane<(channel?4:3);++lane)bufferColor[lane]=value[lane];
                        bufferAssigned[channel]=true;sources[argument]=GPU_PREVIOUS_BUFFER;
                    } else return Fallback("texenv-constant-conflict");
                }
            }
            auto mode=channel?C3D_Alpha:C3D_RGB;
            C3D_TexEnvSrc(&stage,mode,sources[0],sources[1],sources[2]);
            C3D_TexEnvFunc(&stage,mode,count==1?GPU_REPLACE:count==2?GPU_MODULATE:GPU_INTERPOLATE);
            if(!channel)C3D_TexEnvOpRgb(&stage,operands[0],operands[1],operands[2]);
        }
        C3D_TexEnvColor(&stage,Blinky::Pack(constant));
    }
    if(f.opt_fog) {
        auto& stage=stages[current->recipe.cycles];
        C3D_TexEnvSrc(&stage,C3D_RGB,GPU_CONSTANT,GPU_PREVIOUS,GPU_TEXTURE2);
        C3D_TexEnvOpRgb(&stage,GPU_TEVOP_RGB_SRC_COLOR,GPU_TEVOP_RGB_SRC_COLOR,GPU_TEVOP_RGB_SRC_ALPHA);
        C3D_TexEnvFunc(&stage,C3D_RGB,GPU_INTERPOLATE);
        C3D_TexEnvColor(&stage,Blinky::Pack(v[0].fog));
    }
    bool partition=false;
    for(unsigned unit=0;unit<2;++unit)if(current->sampled[unit])for(unsigned axis=0;axis<2;++axis)if(f.clamp[unit][axis]) {
        float low=0.5f/(axis?bound[unit]->height:bound[unit]->width);
        float minimum[2]={0,0},maximum[2]={0,0};
        for(const auto& vertex:v)for(unsigned side=0;side<2;++side) {
            float distance=vertex.uv[unit][axis]-(side?vertex.clamp[unit][axis]:low);
            minimum[side]=std::min(minimum[side],distance);maximum[side]=std::max(maximum[side],distance);
        }
        for(unsigned side=0;side<2;++side)partition|=minimum[side]<0 && maximum[side]>0;
    }
    packet.clear();
    auto append=[&](const Vertex& vertex) {
        PackedVertex p{};
        for(unsigned axis=0;axis<4;++axis)p.clip[axis]=vertex.clip[axis];
        p.clip[2]=(vertex.clip[2]-vertex.clip[3])*0.5f;
        // Primitive depth is an OpenGL [0,1] depth, whereas PICA uses reversed Z.
        if(f.opt_prim_depth)p.clip[2]=(primitiveDepth-1)*vertex.clip[3];
        for(unsigned lane=0;lane<4;++lane) {
            int input=primaryInput[lane==3];p.color[lane]=input<0?1:vertex.input[input][lane];
        }
        for(unsigned unit=0;unit<2;++unit)if(current->sampled[unit]) {
            auto& t=*bound[unit];float* uv=unit?p.uv1:p.uv0;
            for(unsigned axis=0;axis<2;++axis) {
                float size=axis?t.height:t.width,value=vertex.uv[unit][axis];
                if(f.clamp[unit][axis])value=std::clamp(value,.5f/size,vertex.clamp[unit][axis]);
                uv[axis]=value*size/(axis?t.native.height:t.native.width);
            }
            // PICA's sampler reverses the tiled row address. UploadTexture
            // already places logical row zero at the last allocated row, as
            // does PICA when rendering a framebuffer. Both use the same V.
        }
        p.foguv[0]=(vertex.fog[3]*255+0.5f)/256;p.foguv[1]=0.5f;
        packet.push_back(p);
    };
    if(partition) {
        std::vector<std::vector<Vertex>> polygons{std::vector<Vertex>(v,v+3)};
        for(unsigned unit=0;unit<2;++unit)if(current->sampled[unit])for(unsigned axis=0;axis<2;++axis)
            if(f.clamp[unit][axis])PartitionCoordinates(polygons,unit,axis,0.5f/(axis?bound[unit]->height:bound[unit]->width));
        for(const auto& polygon:polygons)for(size_t fan=1;fan+1<polygon.size();++fan)
            for(auto index:{size_t(0),fan,fan+1})append(polygon[index]);
    } else {
        for(const auto& vertex:v)append(vertex);
    }
    if(packet.size()>VertexCapacity)return Fallback("texture-clamp-budget");
    QueueHardware(stages,Blinky::Pack(bufferColor),f.opt_fog);return true;
}

void GfxRenderingAPIBlinkyCitro3D::Device::Reference(const Vertex (&input)[3]) {
    BLINKY_PROFILE(referenceTicks);BLINKY_RENDER_COUNT(cpuTriangles,1);
    FlushHardwareBatch();
    ++cpuTriangles;++current->reference;
    auto polygon=Clip(input);if(polygon.size()<3)return;
    if(!referenceImage){Wait();referenceImage=std::make_unique<Snapshot>(Active());}
    auto& target=Active();auto& destination=*referenceImage;
    std::map<NativeTexture*,std::unique_ptr<Snapshot>> samples;
    const auto& features=current->features;
    for(unsigned unit=0;unit<6;++unit) {
        unsigned base=unit%2;
        bool required=current->sampled[base] && (unit<2 ||
            (unit<4?features.used_masks[base]:features.used_masks[base] && features.used_blend[base]));
        if(!required || !bound[unit] || !bound[unit]->framebuffer)continue;
        for(auto& candidate:targets)if(candidate && candidate->image.get()==bound[unit])
            if(!samples.count(bound[unit]))samples.emplace(bound[unit],std::make_unique<Snapshot>(*candidate));
    }
    auto textureSample=[&](unsigned unit,float u,float v) {
        NativeTexture* t=bound[unit];if(!t || !t->ready)throw std::runtime_error("Blinky reference texture absent");
        auto it=samples.find(t);return Sample(*t,u,v,filtering,it==samples.end()?nullptr:it->second.get());
    };
    for(size_t fan=1;fan+1<polygon.size();++fan) {
        Vertex v[3]={polygon[0],polygon[fan],polygon[fan+1]};
        float x[3],y[3],z[3],inverseW[3];bool valid=true;
        for(unsigned i=0;i<3;++i) {
            if(v[i].clip[3]<=0 || !std::isfinite(v[i].clip[3])){valid=false;break;}
            inverseW[i]=1/v[i].clip[3];
            x[i]=viewport[0]+(v[i].clip[0]*inverseW[i]+1)*viewport[2]*0.5f;
            y[i]=viewport[1]+(v[i].clip[1]*inverseW[i]+1)*viewport[3]*0.5f;
            z[i]=(1-v[i].clip[2]*inverseW[i])*0.5f;
        }
        if(!valid)continue;
        auto edge=[](float ax,float ay,float bx,float by,float px,float py){return (bx-ax)*(py-ay)-(by-ay)*(px-ax);};
        float area=edge(x[0],y[0],x[1],y[1],x[2],y[2]);if(std::fabs(area)<1e-8f)continue;
        if(area<0){std::swap(v[1],v[2]);std::swap(x[1],x[2]);std::swap(y[1],y[2]);std::swap(z[1],z[2]);std::swap(inverseW[1],inverseW[2]);area=-area;}
        int left=std::max({0,scissor[0],int(std::floor(std::min({x[0],x[1],x[2]})))});
        int bottom=std::max({0,scissor[1],int(std::floor(std::min({y[0],y[1],y[2]})))});
        int right=std::min({int(target.width),scissor[0]+scissor[2],int(std::ceil(std::max({x[0],x[1],x[2]})))});
        int top=std::min({int(target.height),scissor[1]+scissor[3],int(std::ceil(std::max({y[0],y[1],y[2]})))});
        bool inclusive[3];for(unsigned i=0;i<3;++i){unsigned a=(i+1)%3,b=(i+2)%3;inclusive[i]=y[b]>y[a] || (y[b]==y[a] && x[b]<x[a]);}
        for(int py=bottom;py<top;++py)for(int px=left;px<right;++px) {
            float weights[3]={edge(x[1],y[1],x[2],y[2],px+0.5f,py+0.5f),
                edge(x[2],y[2],x[0],y[0],px+0.5f,py+0.5f),edge(x[0],y[0],x[1],y[1],px+0.5f,py+0.5f)};
            bool inside=true;for(unsigned i=0;i<3;++i)if(weights[i]<0 || (weights[i]==0 && !inclusive[i]))inside=false;
            if(!inside)continue;
            for(auto& weight:weights)weight/=area;
            float depth=features.opt_prim_depth?1-primitiveDepth:weights[0]*z[0]+weights[1]*z[1]+weights[2]*z[2];
            uint16_t incoming=uint16_t(std::lround(Blinky::Clamp(depth)*65535));
            if(depthTest && destination.depth && (decal?incoming<destination.Z(px,py):incoming<=destination.Z(px,py)))continue;
            float denominator=0;for(unsigned i=0;i<3;++i)denominator+=weights[i]*inverseW[i];
            if(denominator<=0)continue;
            for(unsigned i=0;i<3;++i)weights[i]=weights[i]*inverseW[i]/denominator;
            Blinky::Fragment fragment;
            uint32_t seed=uint32_t(px)*0x9e3779b9u ^ uint32_t(py)*0x85ebca6bu ^ uint32_t(frames)*0xc2b2ae35u;
            seed^=seed>>16;seed*=0x7feb352du;seed^=seed>>15;fragment.noise=(seed&65535)/65536.f;
            for(unsigned i=0;i<3;++i)for(unsigned lane=0;lane<4;++lane) {
                for(unsigned n=0;n<current->recipe.inputs;++n)fragment.inputs[n][lane]+=weights[i]*v[i].input[n][lane];
                fragment.fog[lane]+=weights[i]*v[i].fog[lane];fragment.gray[lane]+=weights[i]*v[i].gray[lane];
            }
            for(unsigned unit=0;unit<2;++unit)if(current->sampled[unit]) {
                float uv[2]{},limits[2]{};
                for(unsigned i=0;i<3;++i)for(unsigned axis=0;axis<2;++axis){uv[axis]+=weights[i]*v[i].uv[unit][axis];limits[axis]+=weights[i]*v[i].clamp[unit][axis];}
                if(features.clamp[unit][0])uv[0]=std::max(0.5f/bound[unit]->width,std::min(limits[0],uv[0]));
                if(features.clamp[unit][1])uv[1]=std::max(0.5f/bound[unit]->height,std::min(limits[1],uv[1]));
                auto texel=textureSample(unit,uv[0],uv[1]);
                if(features.used_masks[unit]) {
                    float amount=textureSample(unit+2,uv[0],uv[1])[3];
                    Color replacement=features.used_blend[unit]?textureSample(unit+4,uv[0],uv[1]):Color{};
                    for(unsigned lane=0;lane<4;++lane)texel[lane]+=(replacement[lane]-texel[lane])*amount;
                }
                fragment.textures[unit]=texel;
            }
            Color result;if(!Blinky::Evaluate(current->recipe,fragment,result))continue;
            destination.Set(px,py,Blinky::Blend(result,destination.Get(px,py),blend));
            if(depthWrite && destination.depth)destination.Z(px,py)=incoming;
        }
    }
}

uint32_t GfxRenderingAPIBlinkyCitro3D::NewTexture() {
    auto& list=device->textures;
    for(size_t i=0;i<list.size();++i)if(!list[i]){list[i]=std::make_unique<NativeTexture>();return i;}
    list.push_back(std::make_unique<NativeTexture>());return list.size()-1;
}
void GfxRenderingAPIBlinkyCitro3D::SelectTexture(int unit,uint32_t id) {
    if(unit<0 || unit>=6 || id>=device->textures.size() || !device->textures[id])throw std::out_of_range("Blinky texture selection");
    device->selectedUnit=unit;device->bound[unit]=device->textures[id].get();device->bound[unit]->lastUse=device->frames;
}
void GfxRenderingAPIBlinkyCitro3D::UploadTexture(const uint8_t* pixels,uint32_t width,uint32_t height) {
    if(!pixels || !width || !height || width>1024 || height>1024)throw std::invalid_argument("Blinky texture dimensions");
    auto& d=*device;auto* t=d.bound[d.selectedUnit];if(!t)throw std::logic_error("Blinky upload without selection");
    // Complete GPU reads before replacing a selected texture's storage.
    if(t->ready){d.Wait();C3D_TexDelete(&t->native);t->ready=false;}
    unsigned w=Blinky::TextureExtent(width),h=Blinky::TextureExtent(height);
    if(!C3D_TexInit(&t->native,w,h,GPU_RGBA8)) {
        d.Wait();
        // Evict only unbound textures. The interpreter asks TextureHasStorage
        // before reuse and reimports any lost allocation.
        for(auto& candidate:d.textures)if(candidate && candidate->ready &&
            std::find(d.bound.begin(),d.bound.end(),candidate.get())==d.bound.end()) {
            C3D_TexDelete(&candidate->native);candidate->ready=false;
        }
        if(!C3D_TexInit(&t->native,w,h,GPU_RGBA8))throw std::bad_alloc();
    }
    t->ready=true;t->width=width;t->height=height;t->lastUse=d.frames;
    t->paddingS=t->paddingT=2;t->freshUpload=true;
    auto* output=static_cast<uint8_t*>(t->native.data);
    for(unsigned y=0;y<h;++y)for(unsigned x=0;x<w;++x) {
        const auto* p=pixels+(std::min<uint32_t>(y,height-1)*width+std::min<uint32_t>(x,width-1))*4;
        auto* q=output+Blinky::TileOffset(x,h-1-y,w)*4;
        q[0]=p[3];q[1]=p[2];q[2]=p[1];q[3]=p[0];
    }
    C3D_TexFlush(&t->native);++d.uploads;
    SetSamplerParameters(d.selectedUnit,t->linear,t->wrapS,t->wrapT);
}
void GfxRenderingAPIBlinkyCitro3D::SetSamplerParameters(int unit,bool linear,uint32_t s,uint32_t t) {
    auto* tex=device->bound.at(unit);if(!tex)return;
    tex->linear=linear;tex->wrapS=s;tex->wrapT=t;if(!tex->ready)return;
    if(!tex->framebuffer) {
        auto padding=[](unsigned size,unsigned extent,unsigned mode) {
            unsigned period=size*((mode&1)?2:1);
            return size<extent && !(mode&2) && extent%period==0?mode&1:2u;
        };
        unsigned ps=padding(tex->width,tex->native.width,s),pt=padding(tex->height,tex->native.height,t);
        if(ps!=tex->paddingS || pt!=tex->paddingT) {
            if(!tex->freshUpload)device->Wait();
            auto* pixels=static_cast<uint8_t*>(tex->native.data);
            for(unsigned y=0;y<tex->native.height;++y)for(unsigned x=0;x<tex->native.width;++x)
                if(x>=tex->width || y>=tex->height) {
                    unsigned sx=Blinky::Address(x,tex->width,ps),sy=Blinky::Address(y,tex->height,pt);
                    auto* from=pixels+Blinky::TileOffset(sx,tex->native.height-1-sy,tex->native.width)*4;
                    auto* to=pixels+Blinky::TileOffset(x,tex->native.height-1-y,tex->native.width)*4;
                    std::memcpy(to,from,4);
                }
            tex->paddingS=ps;tex->paddingT=pt;C3D_TexFlush(&tex->native);
        }
        tex->freshUpload=false;
    }
    auto wrap=[](unsigned mode){return mode&2?GPU_CLAMP_TO_EDGE:mode&1?GPU_MIRRORED_REPEAT:GPU_REPEAT;};
    C3D_TexSetWrap(&tex->native,wrap(s),wrap(t));
    auto filter=linear && device->filtering!=FILTER_NONE?GPU_LINEAR:GPU_NEAREST;C3D_TexSetFilter(&tex->native,filter,filter);
}
void GfxRenderingAPIBlinkyCitro3D::DeleteTexture(uint32_t id) {
    auto& d=*device;if(id>=d.textures.size() || !d.textures[id])return;
    for(auto& binding:d.bound)if(binding==d.textures[id].get())binding=nullptr;
    d.retired.push_back(std::move(d.textures[id]));
    if(d.retired.size()>128)d.Wait();
}
bool GfxRenderingAPIBlinkyCitro3D::TextureHasStorage(uint32_t id){return id<device->textures.size() && device->textures[id] && device->textures[id]->ready;}
void GfxRenderingAPIBlinkyCitro3D::SetDepthTestAndMask(bool test,bool write){device->depthTest=test;device->depthWrite=write;}
void GfxRenderingAPIBlinkyCitro3D::SetZmodeDecal(bool decal){device->decal=decal;}
void GfxRenderingAPIBlinkyCitro3D::SetViewport(int x,int y,int w,int h){
#if BLINKY_OCCLUSION_CULLING
    if(device->viewport!=std::array<int,4>{x,y,w,h})device->InvalidateOcclusion();
#endif
    device->viewport={x,y,w,h};
}
void GfxRenderingAPIBlinkyCitro3D::SetScissor(int x,int y,int w,int h){device->scissor={x,y,w,h};}
void GfxRenderingAPIBlinkyCitro3D::SetUseAlpha(bool blend){device->blend=blend;}
void GfxRenderingAPIBlinkyCitro3D::SetTextureFilter(FilteringMode filter){device->filtering=filter;}
FilteringMode GfxRenderingAPIBlinkyCitro3D::GetTextureFilter(){return device->filtering;}
void GfxRenderingAPIBlinkyCitro3D::SetSrgbMode(){mSrgbMode=false;}
void GfxRenderingAPIBlinkyCitro3D::SetCurrentPrimDepth(float depth){device->primitiveDepth=Blinky::Clamp(depth);}
ImTextureID GfxRenderingAPIBlinkyCitro3D::GetTextureById(int id){return reinterpret_cast<ImTextureID>(TextureHasStorage(id)?device->textures[id].get():nullptr);}

void GfxRenderingAPIBlinkyCitro3D::DrawTriangles(float* buffer,size_t length,size_t count) {
    BLINKY_PROFILE(backendTicks);
    auto& d=*device;if(!count)return;
    BLINKY_RENDER_COUNT(apiDraws,1);BLINKY_RENDER_COUNT(apiTriangles,count);
#if BLINKY_RENDER_STATS
    if(BlinkyVisibilityGetScope()==BLINKY_SCOPE_ROOM_OPA)BLINKY_RENDER_COUNT(roomDraws,1);
#endif
    if(!d.current || !d.initialized)throw std::logic_error("Blinky draw outside shader/device");
    if(count>length/(3*d.current->stride))throw std::invalid_argument("Blinky truncated LUS VBO");
    auto& f=d.current->features;
    ++d.draws;++d.current->hits;d.triangles+=count;
    if(f.shader_id!=-1){++d.current->rejected;d.Fallback("custom-prism-shader-unimplemented");d.Export();throw std::runtime_error("Blinky custom Prism shader is not implemented; see blinky-shaders.json");}
    for(unsigned unit=0;unit<6;++unit) {
        unsigned base=unit%2;
        bool required=d.current->sampled[base] && (unit<2 ||
            (unit<4?f.used_masks[base]:f.used_masks[base] && f.used_blend[base]));
        if(required && (!d.bound[unit] || !d.bound[unit]->ready)) {
            std::fprintf(stderr,"Blinky missing sampled texture: unit=%u shader=%016llx:%016llx frame=%llu draw=%llu declared=%d/%d sampled=%d/%d bound=%d ready=%d\n",
                unit,(unsigned long long)d.current->id0,(unsigned long long)d.current->id1,
                (unsigned long long)d.frames,(unsigned long long)d.draws,f.usedTextures[0],f.usedTextures[1],
                d.current->sampled[0],d.current->sampled[1],d.bound[unit]!=nullptr,d.bound[unit] && d.bound[unit]->ready);
            ++d.current->rejected;d.Export();
            throw std::runtime_error("Blinky sampled texture absent; see blinky.log and blinky-shaders.json");
        }
    }
#if BLINKY_OCCLUSION_CULLING
    if((d.depthWrite && !d.depthTest) || gfxIs3D())d.InvalidateOcclusion();
    bool eligible;
    {
        BLINKY_PROFILE(occlusionTicks);
        eligible=d.OcclusionEligible();
        if(eligible)BLINKY_RENDER_COUNT(eligible,1);
        // Small calls are cheaper to draw; bounds cover every vertex in this
        // call, not an actor's approximate activation/culling sphere.
        if(eligible && count>=8 && d.occlusion.Hidden(buffer,count*3,d.current->stride)) {
            BLINKY_RENDER_COUNT(rejected,1);BLINKY_RENDER_COUNT(avoidedTriangles,count);
            return;
        }
    }
#endif
    for(size_t triangle=0;triangle<count;++triangle) {
        Vertex vertices[3];
        for(auto& vertex:vertices) {
            std::copy_n(buffer,4,vertex.clip);buffer+=4;
            for(unsigned unit=0;unit<2;++unit)if(f.usedTextures[unit]) {
                std::copy_n(buffer,2,vertex.uv[unit]);buffer+=2;
                for(unsigned axis=0;axis<2;++axis)if(f.clamp[unit][axis])vertex.clamp[unit][axis]=*buffer++;
            }
            if(f.opt_fog){std::copy_n(buffer,4,vertex.fog.begin());buffer+=4;}
            if(f.opt_grayscale){std::copy_n(buffer,4,vertex.gray.begin());buffer+=4;}
            for(int input=0;input<f.numInputs;++input) {
                std::copy_n(buffer,f.opt_alpha?4:3,vertex.input[input].begin());buffer+=f.opt_alpha?4:3;
                if(!f.opt_alpha)vertex.input[input][3]=1;
            }
        }
        if(!d.Hardware(vertices))d.Reference(vertices);
#if BLINKY_OCCLUSION_CULLING
        else if(eligible && d.depthWrite && d.packet.size()==3 &&
                d.occlusion.counters.attempts<Blinky::CoarseOcclusion::MaxOccluderAttempts &&
                d.occlusion.counters.rasterCells<Blinky::CoarseOcclusion::MaxRasterCells) {
            // Hardware accepted this exact triangle without subdivision. The
            // queued draw is guaranteed to precede the next candidate call.
            BLINKY_PROFILE(occlusionTicks);
            d.occlusion.RegisterTriangle(vertices[0].clip,vertices[1].clip,vertices[2].clip);
        }
#endif
    }
    // Bound textures, depth and blend state are fixed throughout this API call.
    // Finish the batch before the interpreter can change any of those states.
    d.FlushHardwareBatch();
}

int GfxRenderingAPIBlinkyCitro3D::CreateFramebuffer() {
    device->targets.push_back(std::make_unique<Target>());return device->targets.size()-1;
}
void GfxRenderingAPIBlinkyCitro3D::UpdateFramebufferParameters(int id,uint32_t width,uint32_t height,uint32_t msaa,
                                                              bool invertY,bool,bool depth,bool) {
    auto& d=*device;auto& target=d.targets.at(id);width=std::max<uint32_t>(1,width);height=std::max<uint32_t>(1,height);
    if(width>1024 || height>1024)throw std::invalid_argument("Blinky framebuffer exceeds 1024 pixels");
    if(msaa>1)throw std::invalid_argument("Blinky MSAA unavailable: set MSAA to 1");
#if BLINKY_OCCLUSION_CULLING
    if(id==d.activeTarget && (target->invertY!=invertY || target->width!=width || target->height!=height ||
       !target->native || bool(target->native->frameBuf.depthBuf)!=depth))d.InvalidateOcclusion();
#endif
    target->invertY=invertY;
    if(target->native && target->width==width && target->height==height && bool(target->native->frameBuf.depthBuf)==depth)return;
    d.Wait();
    for(auto& binding:d.bound)if(binding==target->image.get())binding=nullptr;
    // Release the old VRAM allocation after its GPU fence, before reallocating.
    target=std::make_unique<Target>();target->invertY=invertY;target->image=std::make_unique<NativeTexture>();
    auto& image=*target->image;
    if(!C3D_TexInitVRAM(&image.native,Blinky::TextureExtent(width),Blinky::TextureExtent(height),GPU_RGBA8))throw std::bad_alloc();
    image.ready=image.framebuffer=true;image.width=target->width=width;image.height=target->height=height;
    image.wrapS=image.wrapT=2;image.linear=true;
    C3D_TexSetWrap(&image.native,GPU_CLAMP_TO_EDGE,GPU_CLAMP_TO_EDGE);C3D_TexSetFilter(&image.native,GPU_LINEAR,GPU_LINEAR);
    target->native=C3D_RenderTargetCreateFromTex(&image.native,GPU_TEXFACE_2D,0,depth?C3D_DEPTHTYPE(GPU_RB_DEPTH16):C3D_DEPTHTYPE(-1));
    if(!target->native)throw std::bad_alloc();
    C3D_RenderTargetClear(target->native,C3D_CLEAR_ALL,0x000000ff,0);
}
void GfxRenderingAPIBlinkyCitro3D::StartDrawToFramebuffer(int id,float scale) {
    if(id<0 || size_t(id)>=device->targets.size() || !device->targets[id]->native)throw std::out_of_range("Blinky framebuffer selection");
#if BLINKY_OCCLUSION_CULLING
    if(device->activeTarget!=id)device->InvalidateOcclusion();
#endif
    device->FlushReference();device->activeTarget=id;device->noiseScale=scale>0?1/scale:1;
}
void GfxRenderingAPIBlinkyCitro3D::ClearFramebuffer(bool color,bool depth) {
    if(!color && !depth)return;
#if BLINKY_OCCLUSION_CULLING
    if(depth)device->InvalidateOcclusion();
#endif
    // FrameBufClear uses GX fills; split queued draws before the fill so clears
    // cannot overtake geometry already submitted in this logical framebuffer.
    device->Wait();C3D_RenderTargetClear(device->Active().native,
        static_cast<C3D_ClearBits>((color?C3D_CLEAR_COLOR:0)|(depth?C3D_CLEAR_DEPTH:0)),0x000000ff,0);
}
void GfxRenderingAPIBlinkyCitro3D::ClearDepthRegion(int x,int y,int w,int h) {
#if BLINKY_OCCLUSION_CULLING
    device->InvalidateOcclusion();
#endif
    auto& d=*device;d.Wait();auto& target=d.Active();if(!target.native->frameBuf.depthBuf)return;
    Snapshot image(target);
    for(int py=std::max(0,y);py<std::min(int(target.height),y+h);++py)
        for(int px=std::max(0,x);px<std::min(int(target.width),x+w);++px)image.Z(px,py)=0;
    image.Store(target);
}
void GfxRenderingAPIBlinkyCitro3D::CopyFramebuffer(int destinationId,int sourceId,int sx0,int sy0,int sx1,int sy1,int dx0,int dy0,int dx1,int dy1) {
    if(dx0==dx1 || dy0==dy1)return;
    auto& d=*device;d.Wait();auto& source=*d.targets.at(sourceId);auto& destination=*d.targets.at(destinationId);
    Snapshot from(source),to(destination);
    float firstY=source.invertY?float(sy0):float(source.height)-sy1;
    float lastY=source.invertY?float(sy1):float(source.height)-sy0;
    for(int y=std::max(0,std::min(dy0,dy1));y<std::min(int(destination.height),std::max(dy0,dy1));++y)
        for(int x=std::max(0,std::min(dx0,dx1));x<std::min(int(destination.width),std::max(dx0,dx1));++x) {
            int sx=std::clamp(int(std::floor(sx0+(x+0.5f-dx0)*(sx1-sx0)/float(dx1-dx0))),0,int(source.width)-1);
            float fraction=(y+0.5f-dy0)/float(dy1-dy0);
            if(source.invertY!=destination.invertY)fraction=1-fraction;
            int sy=std::clamp(int(std::floor(firstY+(lastY-firstY)*fraction)),0,int(source.height)-1);
            to.Set(x,y,from.Get(sx,sy));
        }
    to.Store(destination,false);
}
void GfxRenderingAPIBlinkyCitro3D::ResolveMSAAColorBuffer(int destination,int source) {
    auto& a=*device->targets.at(source);auto& b=*device->targets.at(destination);
    CopyFramebuffer(destination,source,0,0,a.width,a.height,0,0,b.width,b.height);
}
void GfxRenderingAPIBlinkyCitro3D::ReadFramebufferToCPU(int id,uint32_t width,uint32_t height,uint16_t* buffer) {
    if(!buffer || !width || !height)return;
    auto& d=*device;d.Wait();auto& target=*d.targets.at(id);Snapshot image(target);
    for(unsigned y=0;y<height;++y)for(unsigned x=0;x<width;++x)
        buffer[y*width+x]=x<target.width && y<target.height?Blinky::Pack5551(image.Get(x,y)):0;
}
std::unordered_map<std::pair<float,float>,uint16_t,hash_pair_ff> GfxRenderingAPIBlinkyCitro3D::GetPixelDepth(int id,const std::set<std::pair<float,float>>& coordinates) {
    std::unordered_map<std::pair<float,float>,uint16_t,hash_pair_ff> result;
    if(coordinates.empty())return result;
    auto& d=*device;d.Wait();auto& target=*d.targets.at(id);Snapshot image(target);
    for(auto [x,y]:coordinates) {
        uint16_t depth=0xfffc;
        if(image.depth && x>=0 && y>=0 && x<target.width && y<target.height)
            depth=(65535-image.Z(unsigned(x),target.invertY?target.height-1-unsigned(y):unsigned(y)))&0xfffc;
        result[{x,y}]=depth;
    }
    return result;
}
void* GfxRenderingAPIBlinkyCitro3D::GetFramebufferTextureId(int id){return device->targets.at(id)->image.get();}
void GfxRenderingAPIBlinkyCitro3D::SelectTextureFb(int id){device->bound[0]=device->targets.at(id)->image.get();device->selectedUnit=0;}

void GfxRenderingAPIBlinkyCitro3D::Init() {
    auto& d=*device;if(d.initialized)return;
    gfxInitDefault();gfxSet3D(false);
    if(!C3D_Init(C3D_DEFAULT_CMDBUF_SIZE)){gfxExit();throw std::runtime_error("Blinky Citro3D initialization");}
    d.initialized=true;
    d.binary=DVLB_ParseFile(reinterpret_cast<u32*>(const_cast<unsigned char*>(blinky_passthrough_shbin)),blinky_passthrough_shbin_size);
    if(!d.binary)throw std::runtime_error("Blinky vertex shader binary");
    shaderProgramInit(&d.shader);shaderProgramSetVsh(&d.shader,&d.binary->DVLE[0]);
    d.vertices=static_cast<PackedVertex*>(linearAlloc(VertexCapacity*sizeof(PackedVertex)));if(!d.vertices)throw std::bad_alloc();
    if(!C3D_TexInit(&d.fogRamp,256,8,GPU_RGBA8))throw std::bad_alloc();
    d.fogRampReady=true;
    // A sampled ramp interpolates the LUS fog varying without consuming shade
    // alpha, replacing the original fog equation, or using a depth-derived LUT.
    auto* ramp=static_cast<uint8_t*>(d.fogRamp.data);
    for(unsigned y=0;y<8;++y)for(unsigned x=0;x<256;++x) {
        auto* p=ramp+Blinky::TileOffset(x,y,256)*4;p[0]=x;p[1]=p[2]=p[3]=255;
    }
    C3D_TexSetWrap(&d.fogRamp,GPU_CLAMP_TO_EDGE,GPU_CLAMP_TO_EDGE);
    C3D_TexSetFilter(&d.fogRamp,GPU_LINEAR,GPU_LINEAR);C3D_TexFlush(&d.fogRamp);
    d.display=C3D_RenderTargetCreate(240,400,GPU_RB_RGB8,-1);if(!d.display)throw std::bad_alloc();
    const u32 transfer=GX_TRANSFER_FLIP_VERT(0)|GX_TRANSFER_OUT_TILED(0)|GX_TRANSFER_RAW_COPY(0)|
        GX_TRANSFER_IN_FORMAT(GX_TRANSFER_FMT_RGB8)|GX_TRANSFER_OUT_FORMAT(GX_TRANSFER_FMT_RGB8)|GX_TRANSFER_SCALING(GX_TRANSFER_SCALE_NO);
    C3D_RenderTargetSetOutput(d.display,GFX_TOP,GFX_LEFT,transfer);
    CreateFramebuffer();UpdateFramebufferParameters(0,400,240,1,false,true,true,true);
    BlinkyDisplayReady(true);
    // Callback storage belongs to this live renderer, never to an async job.
    static Device* lifecycleDevice=nullptr;lifecycleDevice=&d;
    Ship::Blinky3DS::SetRendererLifecycleCallbacks({[](){
        auto& gpu=*lifecycleDevice;
        gpu.Wait();
    },[](){lifecycleDevice->frameStart=0;}});
    std::fprintf(stderr,"Blinky Citro3D initialized: mono 400x240, reversed D16, RGBA8 tiled, CPU reference enabled\n");
}
void GfxRenderingAPIBlinkyCitro3D::OnResize(){}
void GfxRenderingAPIBlinkyCitro3D::StartFrame() {
    BlinkyVisibilityFrameBegin();
#if BLINKY_OCCLUSION_CULLING
    {BLINKY_PROFILE(occlusionTicks);device->occlusion.BeginFrame();}
#endif
    auto& d=*device;d.Wait();d.frameStart=svcGetSystemTick();d.filtering=static_cast<FilteringMode>(BlinkyPreferredTextureFilter());
}
void GfxRenderingAPIBlinkyCitro3D::EndFrame() {
    auto& d=*device;if(!d.initialized)return;
    // Main target is logical landscape. Rotate its quad into the LCD's native
    // 240x400 surface; neither the interpreter nor offscreen buffers rotate.
    d.FlushReference();d.Reserve(6);d.Bind();C3D_FrameDrawOn(d.display);C3D_SetViewport(0,0,240,400);C3D_SetScissor(GPU_SCISSOR_DISABLE,0,0,240,400);
    C3D_DepthTest(false,GPU_ALWAYS,GPU_WRITE_COLOR);C3D_AlphaTest(false,GPU_ALWAYS,0);
    C3D_AlphaBlend(GPU_BLEND_ADD,GPU_BLEND_ADD,GPU_ONE,GPU_ZERO,GPU_ONE,GPU_ZERO);
    auto& main=*d.targets[0]->image;C3D_TexBind(0,&main.native);
    for(unsigned i=0;i<6;++i) {auto* stage=C3D_GetTexEnv(i);C3D_TexEnvInit(stage);if(!i)C3D_TexEnvSrc(stage,C3D_Both,GPU_TEXTURE0);}
    PackedVertex quad[6]{};constexpr float corners[6][2]={{-1,-1},{1,-1},{1,1},{-1,-1},{1,1},{-1,1}};
    for(unsigned i=0;i<6;++i) {
        float x=corners[i][0],y=corners[i][1];
        // Citro3D's tilted projection maps logical (x,y) to native (y,-x).
        // Native +X points toward the landscape top, +Y toward its left.
        quad[i].clip[0]=y;quad[i].clip[1]=-x;quad[i].clip[2]=-0.5f;quad[i].clip[3]=1;
        for(auto& lane:quad[i].color)lane=1;
        quad[i].uv0[0]=(x+1)*0.5f*main.width/main.native.width;
        quad[i].uv0[1]=(y+1)*0.5f*main.height/main.native.height;
    }
    d.DrawPacked(quad,6);d.FlushVertices();C3D_FrameEnd(GX_CMDLIST_FLUSH);d.open=false;++d.frames;
#if BLINKY_OCCLUSION_CULLING
    d.OcclusionReport();
#endif
    d.Report();if(d.frames%600==0)d.Export();
    if(d.frames%6==0)BlinkyPresentDiagnostics(d.frames,d.draws,d.triangles,d.cpuTriangles,d.uploads);
    int fps=std::clamp(BlinkyTargetFps(),1,20);
    if(d.frameStart) {
        int64_t elapsed=static_cast<int64_t>(svcGetSystemTick()-d.frameStart);
        int64_t remaining=static_cast<int64_t>(SYSCLOCK_ARM11)/fps-elapsed;
        if(remaining>0)svcSleepThread(remaining*1000000000LL/SYSCLOCK_ARM11);
    }
    BlinkyVisibilityFrameEnd(d.frames);
}
void GfxRenderingAPIBlinkyCitro3D::FinishRender(){}
GfxRenderingAPI* CreateBlinkyCitro3DRenderingAPI(){return new GfxRenderingAPIBlinkyCitro3D();}
} // namespace Fast
