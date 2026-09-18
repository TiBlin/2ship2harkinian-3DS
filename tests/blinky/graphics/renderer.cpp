#include "gfx_blinky_citro3d.h"
#include "render_core.h"
#include <fast/interpreter.h>
#include <citro3d.h>
#include <ship/port/3ds/BlinkyLifecycle.h>
#include <array>
#include <cstdio>
#include <stdexcept>
#include <vector>
#include <random>
extern "C" {extern const unsigned char blinky_passthrough_shbin[]={0};extern const unsigned blinky_passthrough_shbin_size=1;
int BlinkyTargetFps(){return 30;}int BlinkyPreferredTextureFilter(){return 1;}void BlinkyDisplayReady(bool){}void BlinkyPresentDiagnostics(uint64_t,uint64_t,uint64_t,uint64_t,uint64_t){} }
namespace Ship::Blinky3DS {void SetRendererLifecycleCallbacks(RendererLifecycleCallbacks){}void ClearRendererLifecycleCallbacks(){} }
static Blinky::Color RunTexEnv(const Blinky::Color& primary,const Blinky::Color (&tex)[2],float fogU=0) {
    Blinky::Color previous{};
    assert(gpuFake::bufferMask==0);
    for(const auto& stage:gpuFake::stages) {
        auto read=[&](GPU_TEVSRC src,unsigned lane) {
            if(src==GPU_PRIMARY_COLOR)return primary[lane];
            if(src==GPU_TEXTURE0)return tex[0][lane];
            if(src==GPU_TEXTURE1)return tex[1][lane];
            if(src==GPU_TEXTURE2) {
                auto* ramp=gpuFake::bound[2];assert(ramp && ramp->width==256);
                float x=std::clamp(fogU*256-0.5f,0.f,255.f);
                unsigned left=unsigned(x),right=std::min(left+1,255u);
                auto* data=static_cast<unsigned char*>(ramp->data);
                float a=data[Blinky::TileOffset(left,0,256)*4+3-lane]/255.f;
                float b=data[Blinky::TileOffset(right,0,256)*4+3-lane]/255.f;
                return a+(b-a)*(x-left);
            }
            if(src==GPU_PREVIOUS)return previous[lane];
            unsigned color=src==GPU_CONSTANT?stage.color:gpuFake::bufferColor;
            assert(src==GPU_CONSTANT || src==GPU_PREVIOUS_BUFFER);
            return ((color>>(lane*8))&255)/255.f;
        };
        Blinky::Color result;
        for(unsigned lane=0;lane<4;++lane) {
            float args[3];
            for(unsigned arg=0;arg<3;++arg)
                args[arg]=read(lane==3?stage.alpha[arg]:stage.rgb[arg],
                    lane<3 && stage.operands[arg]==GPU_TEVOP_RGB_SRC_ALPHA?3:lane);
            auto op=lane==3?stage.alphaOp:stage.rgbOp;
            float value=op==GPU_REPLACE?args[0]:op==GPU_MODULATE?args[0]*args[1]:
                args[0]*args[2]+args[1]*(1-args[2]);
            result[lane]=std::clamp(value,0.f,1.f);
        }
        previous=result;
    }
    return previous;
}
static void MenuGpuPrograms() {
    Fast::GfxRenderingAPIBlinkyCitro3D gpu;gpu.Init();gpu.StartFrame();
    for(unsigned unit=0;unit<2;++unit){
        auto id=gpu.NewTexture();gpu.SelectTexture(unit,id);unsigned char image[8*8*4]{};
        gpu.UploadTexture(image,8,8);gpu.SetSamplerParameters(unit,false,2,2);
    }
    // These IDs are from the user's 05 shader report: text color interpolation,
    // the cursor and the three-input skybox. All previously used CPU raster.
    struct Case{uint64_t id,options;};
    const Case cases[]={{0x01082821,1},{0x01082821,0x21},{0x0108010c,1},
        {0xd0003d32818a818aULL,0x10},{0x20001000,1}};
    std::mt19937 random(6006);std::uniform_real_distribution<float> unit(0,1);
    unsigned compared=0;
    for(auto test:cases)for(unsigned attempt=0;attempt<16;++attempt) {
        uint64_t options=(uint64_t(0xffff)<<17)|test.options;CCFeatures f{};
        gfx_cc_get_features(test.id,options,&f);gpu.CreateAndLoadNewShader(test.id,options);
        Blinky::Recipe recipe;recipe.cycles=f.opt_2cyc?2:1;recipe.inputs=f.numInputs;recipe.useAlpha=f.opt_alpha;
        for(unsigned c=0;c<2;++c)for(unsigned n=0;n<4;++n){recipe.color[c].term[n]=f.c[c][0][n];recipe.alpha[c].term[n]=f.c[c][1][n];}
        Blinky::Color inputs[3][7]{};
        for(int input=0;input<f.numInputs;++input)for(unsigned lane=0;lane<4;++lane){
            float value=unit(random);
            for(unsigned vertex=0;vertex<3;++vertex)inputs[vertex][input][lane]=value;
        }
        if(test.id==0x20001000)for(unsigned vertex=0;vertex<3;++vertex){
            for(unsigned lane=0;lane<3;++lane)inputs[vertex][0][lane]=unit(random);
            inputs[vertex][1][3]=unit(random); // independent varying RGB/alpha inputs
        }
        std::vector<float> buffer;const float corners[3][2]={{-1,-1},{1,-1},{0,1}};
        for(unsigned vertex=0;vertex<3;++vertex){
            buffer.insert(buffer.end(),{corners[vertex][0],corners[vertex][1],0,1});
            for(unsigned t=0;t<2;++t)if(f.usedTextures[t])buffer.insert(buffer.end(),{.5f,.5f});
            for(int input=0;input<f.numInputs;++input)
                buffer.insert(buffer.end(),inputs[vertex][input].begin(),inputs[vertex][input].begin()+(f.opt_alpha?4:3));
        }
        unsigned before=gpuFake::draws,copies=gpuFake::copies;
        gpu.DrawTriangles(buffer.data(),buffer.size(),1);
        assert(gpuFake::draws==before+1 && gpuFake::copies==copies);
        for(unsigned sample=0;sample<32;++sample){
            Blinky::Fragment fragment;Blinky::Color primary{};
            float a=unit(random),b=unit(random);if(a+b>1){a=1-a;b=1-b;}float weights[3]={a,b,1-a-b};
            for(unsigned vertex=0;vertex<3;++vertex)for(unsigned lane=0;lane<4;++lane){
                primary[lane]+=weights[vertex]*gpuFake::submitted[vertex*14+4+lane];
                for(int input=0;input<f.numInputs;++input)fragment.inputs[input][lane]+=weights[vertex]*inputs[vertex][input][lane];
            }
            for(auto& texel:fragment.textures)for(auto& lane:texel)lane=unit(random);
            Blinky::Color expected;assert(Blinky::Evaluate(recipe,fragment,expected));
            auto actual=RunTexEnv(primary,fragment.textures);
            for(unsigned lane=0;lane<4;++lane)assert(std::abs(actual[lane]-expected[lane])<2.f/255);
            ++compared;
        }
    }
    std::printf("PASS menu GPU programs: %u independently evaluated TEV fragments, zero CPU readbacks\n",compared);
}
static void TextureDependencies() {
    // LUS declares BOTH UV slots for a two-cycle shader, even if only one
    // sampler is actually read. The interpreter imports only that sampler.
    for(unsigned unit=0;unit<2;++unit) {
        Fast::GfxRenderingAPIBlinkyCitro3D gpu;gpu.Init();
        gpu.UpdateFramebufferParameters(0,8,8,1,false,true,true,true);
        gpu.SetViewport(0,0,8,8);gpu.SetScissor(0,0,8,8);gpu.StartFrame();
        auto texture=gpu.NewTexture();gpu.SelectTexture(unit,texture);
        unsigned char red[8*8*4];for(unsigned i=0;i<64;++i){red[i*4]=red[i*4+3]=255;red[i*4+1]=red[i*4+2]=0;}
        gpu.UploadTexture(red,8,8);gpu.SetSamplerParameters(unit,false,2,2);
        // Second cycle swaps TEXEL0/1, so TEXEL1 reads slot 0 and vice versa.
        uint64_t id=uint64_t(unit?0x8000:0xa000)<<32;
        for(bool cpu:{false,true}) {
            gpu.ClearFramebuffer(true,true);
            auto* shader=gpu.CreateAndLoadNewShader(id,(uint64_t(0xffff)<<17)|16|(cpu?128:0));
            uint8_t inputs;bool used[2];gpu.ShaderGetInfo(shader,&inputs,used);
            assert(inputs==0 && used[0] && used[1]); // preserve the LUS VBO ABI
            std::vector<float> buffer;
            const float corners[6][2]={{-1,-1},{1,-1},{1,1},{-1,-1},{1,1},{-1,1}};
            for(auto& xy:corners) {
                buffer.insert(buffer.end(),{xy[0],xy[1],0,1, .5f,.5f,.5f,.5f});
                if(cpu)buffer.insert(buffer.end(),{0,0,0,0});
            }
            gpu.DrawTriangles(buffer.data(),buffer.size(),2);
            if(cpu){std::array<uint16_t,64> pixels;gpu.ReadFramebufferToCPU(0,8,8,pixels.data());for(auto p:pixels)assert(p==0xf801);}
        }
        // Missing a genuinely sampled texture remains a diagnosed error.
        gpu.DeleteTexture(texture);
        float buffer[36]{};bool rejected=false;
        try{gpu.DrawTriangles(buffer,36,1);}catch(const std::runtime_error&){rejected=true;}
        assert(rejected);
    }
}
static void GameplayGpuPrograms() {
    Fast::GfxRenderingAPIBlinkyCitro3D gpu;gpu.Init();gpu.StartFrame();
    for(unsigned unit=0;unit<2;++unit) {
        auto id=gpu.NewTexture();gpu.SelectTexture(unit,id);unsigned char pixels[8*8*4]{};
        gpu.UploadTexture(pixels,8,8);gpu.SetSamplerParameters(unit,true,2,2);
    }
    // Real 06 gameplay recipes, including S/T clamps on either texture unit.
    struct Case {uint64_t id;unsigned options;};
    const Case cases[]={{0xd0000d0280000108ULL,0x12},{0xd0000d0280000108ULL,0x112},
        {0xd0000d0280000108ULL,0x212},{0xd0000d0280000108ULL,0x312},
        {0xd0000d0280000108ULL,0x213},{0xd0000d0280000108ULL,0x313},
        {0x020d010d818a080aULL,0x12},{0x020d010d818a080aULL,0x212},
        {0x020d010d818a080aULL,0xc12},{0xd000020d818a818aULL,0x12},
        {0xd000020d10000108ULL,0x12},{0xd000d00001080108ULL,0x311},
        {0xd000d00001081000ULL,0x13},{0xd0000d0180008000ULL,0x113},
        {0xd0000d0210000108ULL,0x12}};
    std::mt19937 random(7007);std::uniform_real_distribution<float> unit(0,1);
    unsigned fragments=0,generated=0;
    const float positions[3][2]={{-.9f,-.8f},{.8f,-.6f},{-.1f,.9f}},w[3]={.75f,2,1.25f};
    auto edge=[](const float* a,const float* b,float x,float y){return (b[0]-a[0])*(y-a[1])-(b[1]-a[1])*(x-a[0]);};
    float originalArea=edge(positions[0],positions[1],positions[2][0],positions[2][1]);
    for(auto test:cases)for(unsigned attempt=0;attempt<8;++attempt) {
        uint64_t options=(uint64_t(0xffff)<<17)|test.options;CCFeatures f{};
        gfx_cc_get_features(test.id,options,&f);gpu.CreateAndLoadNewShader(test.id,options);
        Blinky::Recipe recipe;recipe.cycles=f.opt_2cyc?2:1;recipe.inputs=f.numInputs;
        recipe.useAlpha=f.opt_alpha;recipe.fog=f.opt_fog;recipe.threshold=f.opt_alpha_threshold;
        for(unsigned c=0;c<2;++c)for(unsigned term=0;term<4;++term) {
            recipe.color[c].term[term]=f.c[c][0][term];recipe.alpha[c].term[term]=f.c[c][1][term];
        }
        Blinky::Color inputs[3][7]{},fog[3];float uv[3][2][2],limits[3][2][2];
        Blinky::Color fogColor{unit(random),unit(random),unit(random),0};
        for(int input=0;input<f.numInputs;++input)for(unsigned lane=0;lane<4;++lane) {
            float value=lane==3?1:unit(random);
            for(unsigned vertex=0;vertex<3;++vertex)inputs[vertex][input][lane]=input==0 && lane<3?unit(random):value;
        }
        std::vector<float> buffer;
        for(unsigned vertex=0;vertex<3;++vertex) {
            fog[vertex]=fogColor;fog[vertex][3]=vertex==0?0:vertex==1?1:unit(random);
            buffer.insert(buffer.end(),{positions[vertex][0]*w[vertex],positions[vertex][1]*w[vertex],0,w[vertex]});
            for(unsigned t=0;t<2;++t)if(f.usedTextures[t]) {
                for(unsigned axis=0;axis<2;++axis) {
                    // Different axis permutations exercise intersecting clamp boundaries.
                    unsigned corner=(vertex+t+axis)%3;
                    uv[vertex][t][axis]=f.clamp[t][axis]?(corner==0?-.25f:corner==1?1.3f:.3f):.1f+unit(random)*.8f;
                }
                buffer.insert(buffer.end(),{uv[vertex][t][0],uv[vertex][t][1]});
                for(unsigned axis=0;axis<2;++axis)if(f.clamp[t][axis]) {
                    limits[vertex][t][axis]=(axis?.8125f:.6875f)*(attempt<4?1:.7f+.1f*vertex);
                    buffer.push_back(limits[vertex][t][axis]);
                }
            }
            if(f.opt_fog)buffer.insert(buffer.end(),fog[vertex].begin(),fog[vertex].end());
            for(int input=0;input<f.numInputs;++input)
                buffer.insert(buffer.end(),inputs[vertex][input].begin(),inputs[vertex][input].begin()+(f.opt_alpha?4:3));
        }
        unsigned before=gpuFake::draws,copies=gpuFake::copies;
        gpu.DrawTriangles(buffer.data(),buffer.size(),1);
        assert(gpuFake::draws==before+1 && gpuFake::copies==copies);
        float submittedArea=0;
        for(size_t start=0;start<gpuFake::submitted.size();start+=3*14) {
            const float* p[3];float xy[3][2];
            for(unsigned v=0;v<3;++v) {
                p[v]=gpuFake::submitted.data()+start+v*14;
                xy[v][0]=p[v][0]/p[v][3];xy[v][1]=p[v][1]/p[v][3];
            }
            float area=edge(xy[0],xy[1],xy[2][0],xy[2][1]);assert(area>=-1e-6f);submittedArea+=area;++generated;
            for(unsigned sample=0;sample<12;++sample) {
                float a=unit(random)*.98f+.01f,b=unit(random)*.98f+.01f;
                if(a+b>1){a=1-a;b=1-b;}float bary[3]={a,b,1-a-b};
                float point[2]{},denominator=0,weights[3];
                for(unsigned v=0;v<3;++v) {
                    for(unsigned axis=0;axis<2;++axis)point[axis]+=bary[v]*xy[v][axis];
                    weights[v]=bary[v]/p[v][3];denominator+=weights[v];
                }
                for(auto& weight:weights)weight/=denominator;
                float original[3];denominator=0;
                for(unsigned v=0;v<3;++v) {
                    original[v]=edge(positions[(v+1)%3],positions[(v+2)%3],point[0],point[1])/originalArea;
                    assert(original[v]>=-1e-5f);original[v]/=w[v];denominator+=original[v];
                }
                for(auto& weight:original)weight/=denominator;
                Blinky::Fragment fragment;Blinky::Color primary{};float fogU=0;
                for(unsigned v=0;v<3;++v) {
                    fogU+=weights[v]*p[v][12];
                    for(unsigned lane=0;lane<4;++lane) {
                        primary[lane]+=weights[v]*p[v][4+lane];fragment.fog[lane]+=original[v]*fog[v][lane];
                        for(int input=0;input<f.numInputs;++input)fragment.inputs[input][lane]+=original[v]*inputs[v][input][lane];
                    }
                }
                auto sampled=Blinky::SampledTextures(recipe);
                for(unsigned t=0;t<2;++t)if(sampled[t])for(unsigned axis=0;axis<2;++axis) {
                    float expected=0,actual=0;
                    for(unsigned v=0;v<3;++v) {expected+=original[v]*uv[v][t][axis];actual+=weights[v]*p[v][8+t*2+axis];}
                    if(f.clamp[t][axis]) {
                        float cap=0;for(unsigned v=0;v<3;++v)cap+=original[v]*limits[v][t][axis];
                        expected=std::clamp(expected,.0625f,cap);
                    }
                    assert(std::abs(actual-expected)<2e-5f);
                }
                for(auto& texel:fragment.textures)for(auto& lane:texel)lane=unit(random);
                Blinky::Color expected;Blinky::Evaluate(recipe,fragment,expected);
                auto actual=RunTexEnv(primary,fragment.textures,fogU);
                for(unsigned lane=0;lane<4;++lane)assert(std::abs(actual[lane]-expected[lane])<2.f/255);
                ++fragments;
            }
        }
        assert(std::abs(submittedArea-originalArea)<1e-4f);
    }
    std::printf("PASS gameplay GPU: %u perspective fragments, %u partition triangles, fog and texture clamps, zero CPU readbacks\n",fragments,generated);
}
static void SmallTextureRepeats() {
    Fast::GfxRenderingAPIBlinkyCitro3D gpu;gpu.Init();gpu.StartFrame();
    auto id=gpu.NewTexture();gpu.SelectTexture(0,id);
    gpu.CreateAndLoadNewShader(0x0108,uint64_t(0xffff)<<17);
    float triangle[]={-1,-1,0,1,-2.17f,-1.73f,1,1,1, 1,-1,0,1,3.21f,-1.73f,1,1,1, 0,1,0,1,.37f,4.29f,1,1,1};
    unsigned checked=0;
    for(unsigned width:{1u,2u,4u})for(unsigned height:{1u,2u,4u}) {
        std::vector<unsigned char> image(width*height*4);
        for(unsigned y=0;y<height;++y)for(unsigned x=0;x<width;++x) {
            size_t p=(y*width+x)*4;image[p]=x*37+3;image[p+1]=y*53+5;image[p+2]=x+y+7;image[p+3]=255;
        }
        gpu.UploadTexture(image.data(),width,height);
        for(unsigned s:{0u,1u,2u})for(unsigned t:{0u,1u,2u}) {
            gpu.SetSamplerParameters(0,true,s,t);
            unsigned before=gpuFake::draws,copies=gpuFake::copies;
            gpu.DrawTriangles(triangle,std::size(triangle),1);
            assert(gpuFake::draws==before+1 && gpuFake::copies==copies);
            auto* native=gpuFake::bound[0];assert(native->width==8 && native->height==8);
            auto* pixels=static_cast<unsigned char*>(native->data);
            for(unsigned y=0;y<8;++y)for(unsigned x=0;x<8;++x) {
                unsigned sx=Blinky::Address(x,width,s),sy=Blinky::Address(y,height,t);
                auto* expected=image.data()+(sy*width+sx)*4;
                auto* actual=pixels+Blinky::TileOffset(x,7-y,8)*4;
                for(unsigned lane=0;lane<4;++lane)assert(actual[3-lane]==expected[lane]);++checked;
            }
        }
    }
    std::printf("PASS small texture GPU: %u repeated/mirrored/clamped padding texels and live sampler transitions\n",checked);
}
static void CutoutGpuAndBatching() {
    Fast::GfxRenderingAPIBlinkyCitro3D gpu;gpu.Init();gpu.StartFrame();
    for(unsigned unit=0;unit<2;++unit) {
        auto id=gpu.NewTexture();gpu.SelectTexture(unit,id);unsigned char pixels[8*8*4]{};
        gpu.UploadTexture(pixels,8,8);gpu.SetSamplerParameters(unit,true,2,2);
    }
    const uint64_t id=0xd000d00080000108ULL,options=(uint64_t(0xffff)<<17)|0x1f;
    CCFeatures f{};gfx_cc_get_features(id,options,&f);gpu.CreateAndLoadNewShader(id,options);
    Blinky::Recipe recipe;recipe.cycles=2;recipe.inputs=1;recipe.useAlpha=true;recipe.fog=true;recipe.edge=true;recipe.noise=true;
    for(unsigned c=0;c<2;++c)for(unsigned term=0;term<4;++term) {
        recipe.color[c].term[term]=f.c[c][0][term];recipe.alpha[c].term[term]=f.c[c][1][term];
    }
    Blinky::Fragment fragment;fragment.inputs[0]={.7f,.3f,.6f,1};fragment.fog={.2f,.4f,.6f,.5f};
    std::vector<float> buffer;
    const float xy[3][2]={{-.8f,-.8f},{.8f,-.8f},{0,.8f}};
    for(auto& p:xy) {
        buffer.insert(buffer.end(),{p[0],p[1],0,1,.5f,.5f,.5f,.5f});
        buffer.insert(buffer.end(),fragment.fog.begin(),fragment.fog.end());
        buffer.insert(buffer.end(),fragment.inputs[0].begin(),fragment.inputs[0].end());
    }
    unsigned comparisons=0;
    for(bool test:{false,true})for(bool write:{false,true})for(bool decal:{false,true}) {
        gpu.SetDepthTestAndMask(test,write);gpu.SetZmodeDecal(decal);gpu.SetUseAlpha(true);
        unsigned draws=gpuFake::draws,copies=gpuFake::copies;
        gpu.DrawTriangles(buffer.data(),buffer.size(),1);
        assert(gpuFake::draws==draws+2 && gpuFake::copies==copies);
        auto first=gpuFake::drawStates[draws],second=gpuFake::drawStates[draws+1];
        assert(first.mask==GPU_WRITE_ALPHA && first.logic==GPU_LOGICOP_SET);
        assert(second.mask==(7|(write?GPU_WRITE_DEPTH:0)) && second.logic==-1);
        assert(second.src==GPU_ONE && second.dst==GPU_ZERO);
        for(unsigned alpha=0;alpha<256;++alpha)for(float incoming:{.25f,.5f,.75f}) {
            fragment.textures[0]={.3f,.5f,.8f,alpha/255.f};fragment.noise=.37f;
            Blinky::Color expected;bool accepted=Blinky::Evaluate(recipe,fragment,expected);
            auto source=RunTexEnv(fragment.inputs[0],fragment.textures,(.5f*255+.5f)/256);
            Blinky::Color initial{.1f,.3f,.7f,.37f},actual=initial;
            float depth=.5f;
            for(auto state:{first,second}) {
                assert(state.alpha && state.alphaFunction==GPU_GREATER && state.alphaRef==48);
                if(std::lround(source[3]*255)<=state.alphaRef)continue;
                if(state.depth && (state.depthFunction==GPU_GREATER?incoming<=depth:
                    state.depthFunction==GPU_GEQUAL?incoming<depth:false))continue;
                for(unsigned lane=0;lane<4;++lane)if(state.mask&(1<<lane))
                    actual[lane]=state.logic==GPU_LOGICOP_SET?1:source[lane];
                if(state.mask&GPU_WRITE_DEPTH)depth=incoming;
            }
            accepted&=!test || (decal?incoming>=.5f:incoming>.5f);
            if(!accepted)expected=initial;
            for(unsigned lane=0;lane<4;++lane)assert(std::abs(actual[lane]-expected[lane])<2.f/255);
            assert(depth==(accepted && write?incoming:.5f));++comparisons;
        }
    }
    // A single LUS call carrying 300 compatible triangles emits two cutout
    // draws, sharing one immutable VBO, instead of 600 per-triangle draws.
    std::vector<float> batch;for(unsigned i=0;i<300;++i)batch.insert(batch.end(),buffer.begin(),buffer.end());
    unsigned before=gpuFake::draws,copies=gpuFake::copies;
    gpu.DrawTriangles(batch.data(),batch.size(),300);
    assert(gpuFake::draws==before+2 && gpuFake::copies==copies && gpuFake::submitted.size()==300*3*14);
    std::printf("PASS cutout GPU: %u alpha/depth cases (including equal Z), 300 triangles in two draws, zero CPU readbacks\n",comparisons);
}
#include "orientation.inc"
#include "unused_framebuffer.inc"
#include "occlusion.inc"
int main(){
    OcclusionIntegration();
    OrientationRegression();
    UnusedFramebufferSnapshots();
    MenuGpuPrograms();
    GameplayGpuPrograms();
    CutoutGpuAndBatching();
    SmallTextureRepeats();
    TextureDependencies();
    {
        Fast::GfxRenderingAPIBlinkyCitro3D gpu;gpu.Init();
        gpu.UpdateFramebufferParameters(0,16,16,1,false,true,true,true);
        gpu.SetViewport(0,0,16,16);gpu.SetScissor(0,0,16,16);gpu.StartFrame();gpu.ClearFramebuffer(true,true);
        std::array<uint16_t,256> blank{};gpu.ReadFramebufferToCPU(0,16,16,blank.data());
        for(auto pixel:blank)assert(pixel==1); // opaque black, not transparent red
        // Force the CPU reference path with a zero-amount grayscale operation. The
        // full-screen red quad is decoded with the real LUS CCFeatures routine.
        uint64_t options=(uint64_t(0xffff)<<17)|128;
        auto* shader=gpu.CreateAndLoadNewShader(0x1000,options);
        uint8_t count=0;bool used[2];gpu.ShaderGetInfo(shader,&count,used);assert(count==1 && !used[0]);
        float triangle[]={-1,-1,0,1, 0,0,0,0, 1,0,0, 1,-1,0,1, 0,0,0,0, 1,0,0, 1,1,0,1, 0,0,0,0, 1,0,0,
                          -1,-1,0,1, 0,0,0,0, 1,0,0, 1,1,0,1, 0,0,0,0, 1,0,0, -1,1,0,1, 0,0,0,0, 1,0,0};
        gpu.SetDepthTestAndMask(true,true);gpu.DrawTriangles(triangle,std::size(triangle),2);
        std::array<uint16_t,256> pixels{};gpu.ReadFramebufferToCPU(0,16,16,pixels.data());
        for(auto pixel:pixels)assert(pixel==0xf801);
        auto depths=gpu.GetPixelDepth(0,{{8,8}});assert(depths.at({8,8})>=32764 && depths.at({8,8})<=32768);
        gpu.ClearDepthRegion(0,0,8,8);depths=gpu.GetPixelDepth(0,{{0,0},{8,8}});assert(depths.at({0,0})==65532 && depths.at({8,8})<65532);
        int target=gpu.CreateFramebuffer();gpu.UpdateFramebufferParameters(target,8,8,1,false,true,true,true);
        gpu.CopyFramebuffer(target,0,0,0,16,16,0,0,8,8);gpu.ReadFramebufferToCPU(target,8,8,pixels.data());assert(pixels[0]==0xf801 && pixels[63]==0xf801);
        // Interleave hardware submission with texture replacement and resize.
        gpu.LoadShader(gpu.CreateAndLoadNewShader(0x1000,uint64_t(0xffff)<<17));
        float hardware[]={-1,-1,0,1,1,0,0, 1,-1,0,1,1,0,0, 0,1,0,1,1,0,0};
        gpu.DrawTriangles(hardware,std::size(hardware),1);assert(gpuFake::pending);
        auto texture=gpu.NewTexture();gpu.SelectTexture(0,texture);unsigned char bytes[8*8*4]{};
        gpu.UploadTexture(bytes,8,8);gpu.UploadTexture(bytes,8,8);gpu.DeleteTexture(texture);
        gpu.UpdateFramebufferParameters(target,16,8,1,false,true,true,true);
        gpu.EndFrame();gpu.StartFrame();gpu.ClearShaderCache();
        // The observed 05 scanout put logical x=0 at the right of the LCD.
        // Verify every presented corner against native Y -> landscape left.
        assert(gpuFake::submitted.size()==6*14);
        for(unsigned vertex=0;vertex<6;++vertex){
            const float* p=gpuFake::submitted.data()+vertex*14;
            float screenX=(1-p[1])*.5f,screenY=(1-p[0])*.5f;
            assert(screenX==p[8] && screenY==1-p[9]);
        }
    }
    assert(gpuFake::targets==0 && gpuFake::textures==0);
    std::printf("PASS real Blinky renderer: CPU raster/readback/depth/copy, real LUS decoder, GPU lifetime fences (%u copies)\n",gpuFake::copies);
}
