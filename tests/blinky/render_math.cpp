#include "render_core.h"
#include "input_core.h"
#include <cassert>
#include <cstdio>
#include <random>
#include <set>
using namespace Blinky;
static void Near(float actual,float expected){assert(std::fabs(actual-expected)<0.00002f);}
int main() {
    Recipe dependencies;
    dependencies.cycles=2;dependencies.color[1].term={0,0,0,Tex1};
    assert((SampledTextures(dependencies)==std::array<bool,2>{true,false}));
    dependencies.color[1].term={0,0,0,Tex0Alpha};
    assert((SampledTextures(dependencies)==std::array<bool,2>{false,true}));
    dependencies.alpha[0].term={0,0,0,Tex0}; // alpha disabled
    assert((SampledTextures(dependencies)==std::array<bool,2>{false,true}));
    dependencies.useAlpha=true;
    assert((SampledTextures(dependencies)==std::array<bool,2>{true,true}));
    dependencies.cycles=1;dependencies.useAlpha=false;
    dependencies.color[0].term={Tex0,Tex0,Tex1,Input1};
    assert((SampledTextures(dependencies)==std::array<bool,2>{false,false}));
    dependencies.color[0].term={Tex0,Tex1,Zero,Tex1Alpha};
    assert((SampledTextures(dependencies)==std::array<bool,2>{false,true}));
    // The tiling permutation must be bijective for every supported allocation.
    for(unsigned size=8;size<=1024;size*=2) {
        std::set<size_t> offsets;
        for(unsigned y=0;y<size;++y)for(unsigned x=0;x<size;++x)offsets.insert(TileOffset(x,y,size));
        assert(offsets.size()==size_t(size)*size);assert(*offsets.begin()==0);assert(*offsets.rbegin()==size_t(size)*size-1);
    }
    assert(TileOffset(1,0,16)==1 && TileOffset(0,1,16)==2 && TileOffset(8,0,16)==64 && TileOffset(0,8,16)==128);
    assert(TextureExtent(1)==8 && TextureExtent(9)==16 && TextureExtent(400)==512);
    assert(Address(-1,4,0)==3 && Address(-1,4,1)==0 && Address(4,4,1)==3);
    assert(Address(-2,4,2)==0 && Address(-2,4,3)==1 && Address(-9,4,3)==3);
    assert(Pack5551({1,0,0,1})==0xf801 && Pack5551({0,1,0,1})==0x07c1);
    Fragment f;f.inputs[0]={0.8f,0.4f,0.2f,0.5f};f.inputs[1]={0.1f,0.3f,0.9f,0.25f};
    f.textures[0]={0.4f,0.8f,0.5f,0.1f};f.textures[1]={0.7f,0.2f,0.9f,0.8f};
    Recipe recipe;recipe.color[0].term={Tex0,Zero,Input1,Zero};Color color;
    assert(Evaluate(recipe,f,color));Near(color[0],0.32f);Near(color[1],0.32f);Near(color[2],0.1f);Near(color[3],1);
    recipe.cycles=2;recipe.color[1].term={Combined,Zero,Tex0,Zero};
    assert(Evaluate(recipe,f,color));Near(color[0],0.32f*0.7f); // second-cycle texture swap
    recipe.cycles=1;recipe.useAlpha=true;recipe.alpha[0].term={0,0,0,Tex0Alpha};recipe.edge=true;
    assert(!Evaluate(recipe,f,color));f.textures[0][3]=0.2f;assert(Evaluate(recipe,f,color));Near(color[3],1);
    recipe.edge=false;recipe.threshold=true;f.textures[0][3]=7.f/256;assert(!Evaluate(recipe,f,color));
    f.textures[0][3]=8.f/256;assert(Evaluate(recipe,f,color));
    recipe.threshold=false;recipe.fog=true;f.fog={1,0,0,0.5f};
    assert(Evaluate(recipe,f,color));Near(color[0],0.66f);Near(color[1],0.16f);
    recipe.fog=false;recipe.color[0].term={Zero,One,One,Zero};
    assert(Evaluate(recipe,f,color));Near(color[0],1); // signed -1 wraps to 1.02, then clamps
    recipe.color[0].term={One,Zero,One,One};assert(Evaluate(recipe,f,color));Near(color[0],0); // 2 wraps to -0.02
    // Exhaustive source combinations, random values, independent arithmetic
    // evaluation versus the convex operations accepted for the GPU path.
    std::mt19937 random(1847);std::uniform_real_distribution<float> uniform(0,1);
    size_t cases=0;
    for(unsigned a=0;a<=13;++a)for(unsigned b=0;b<=13;++b)for(unsigned c=0;c<=13;++c)for(unsigned d=0;d<=13;++d) {
        Formula formula{{uint8_t(a),uint8_t(b),uint8_t(c),uint8_t(d)}};auto lowered=Lower(formula);if(!lowered.exact)continue;
        for(unsigned n=0;n<4;++n){for(auto& input:f.inputs)for(auto& lane:input)lane=uniform(random);
            for(auto& tex:f.textures)for(auto& lane:tex)lane=uniform(random);
            Color previous{uniform(random),uniform(random),uniform(random),uniform(random)};
            float x=Read(lowered.source[0],0,f,previous),y=Read(lowered.source[1],0,f,previous),z=Read(lowered.source[2],0,f,previous);
            float actual=lowered.op==Operation::Replace?x:lowered.op==Operation::Multiply?x*y:x*z+y*(1-z);
            Near(actual,Calculate(formula,0,f,previous));++cases;
        }
    }
    Near(Blend({1,0,0,0.5f},{0,1,0,1},true)[1],0.5f);
    assert(Axis(15,15)==0 && Axis(-15,15)==0 && Axis(156,15)==85 && Axis(-156,15)==-85);
    int8_t x=85,y=85;LimitStick(x,y);assert(x==60 && y==60);
    struct Pad {uint32_t button=0x80000000;int8_t stick_x=12,stick_y=0,right_stick_x=0,right_stick_y=0;float gyro_x=0,gyro_y=0;} pad;
    struct Native {uint32_t buttons=0x8000;int8_t x=-50,y=20,cx=30,cy=-40;float gyroX=1,gyroY=2;} native;
    MergePad(pad,native);assert(pad.button==0x80008000 && pad.stick_x==12 && pad.stick_y==20 && pad.right_stick_y==-40);
    std::printf("PASS Blinky render math: %zu convex combiner cases, tiled layouts, cycles, fog/alpha/wrap, input\n",cases);
}
