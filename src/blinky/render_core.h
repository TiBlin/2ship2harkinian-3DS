#pragma once
// Portable Blinky reference math. The renderer supplies the decoded LUS recipe.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>

namespace Blinky {
using Color=std::array<float,4>;
enum Source : uint8_t { Zero,Input1,Input2,Input3,Input4,Input5,Input6,Input7,
                       Tex0,Tex0Alpha,Tex1,Tex1Alpha,One,Combined,Noise };
struct Formula { std::array<uint8_t,4> term{}; };
struct Recipe {
    Formula color[2],alpha[2];
    unsigned cycles=1,inputs=0;
    bool useAlpha=false,fog=false,edge=false,noise=false,threshold=false,invisible=false,gray=false;
};
struct Fragment {
    Color inputs[7]{},textures[2]{},fog{},gray{};
    float noise=0.5f;
};
inline float Clamp(float value) { return std::clamp(value,0.0f,1.0f); }
inline float Wrap(float value,float low,float high) {
    const float range=high-low;
    return value-range*std::floor((value-low)/range);
}
inline float Read(uint8_t source,unsigned lane,const Fragment& f,const Color& previous) {
    if(source>=Input1 && source<=Input7)return f.inputs[source-Input1][lane];
    switch(source) {
        case Tex0:return f.textures[0][lane]; case Tex1:return f.textures[1][lane];
        case Tex0Alpha:return f.textures[0][3]; case Tex1Alpha:return f.textures[1][3];
        case One:return 1;case Combined:return previous[lane];case Noise:return f.noise;
        default:return 0;
    }
}
inline uint8_t CycleSource(uint8_t source,unsigned cycle) {
    // The second RDP combiner cycle exchanges TEXEL0 and TEXEL1 (LUS contract).
    if(cycle && source>=Tex0 && source<=Tex1Alpha)return source<Tex1?source+2:source-2;
    return source;
}
inline std::array<bool,2> SampledTextures(const Recipe& recipe) {
    std::array<bool,2> used{};
    for(unsigned cycle=0;cycle<recipe.cycles;++cycle) {
        for(unsigned lane=0;lane<(recipe.useAlpha?2u:1u);++lane) {
            const auto& terms=(lane?recipe.alpha[cycle]:recipe.color[cycle]).term;
            // (A-B)*0+D and (A-A)*C+D only depend on D.
            unsigned first=terms[2]==Zero || terms[0]==terms[1]?3:0;
            for(unsigned i=first;i<4;++i) {
                auto source=CycleSource(terms[i],cycle);
                if(source==Tex0 || source==Tex0Alpha)used[0]=true;
                if(source==Tex1 || source==Tex1Alpha)used[1]=true;
            }
        }
    }
    return used;
}
inline float Calculate(const Formula& formula,unsigned lane,const Fragment& f,const Color& previous,unsigned cycle=0) {
    const auto& t=formula.term;
    return (Read(CycleSource(t[0],cycle),lane,f,previous)-Read(CycleSource(t[1],cycle),lane,f,previous))*
        Read(CycleSource(t[2],cycle),lane,f,previous)+Read(CycleSource(t[3],cycle),lane,f,previous);
}
inline bool Evaluate(const Recipe& r,const Fragment& f,Color& result) {
    Color previous{};
    for(unsigned cycle=0;cycle<r.cycles;++cycle) {
        if(cycle)for(unsigned lane=0;lane<4;++lane) {
            bool factor=(lane==3?r.alpha[cycle]:r.color[cycle]).term[2]==Combined;
            previous[lane]=Wrap(previous[lane],factor?-1.01f:-0.51f,factor?1.01f:1.51f);
        }
        for(unsigned lane=0;lane<4;++lane)
            result[lane]=(lane==3 && !r.useAlpha)?1:Calculate(lane==3?r.alpha[cycle]:r.color[cycle],lane,f,previous,cycle);
        previous=result;
    }
    for(auto& component:result)component=Clamp(Wrap(component,-0.51f,1.51f));
    if(r.fog)for(unsigned lane=0;lane<3;++lane)result[lane]+=f.fog[3]*(f.fog[lane]-result[lane]);
    if(r.edge && r.useAlpha) { if(result[3]<=0.19f)return false;result[3]=1; }
    if(r.noise && r.useAlpha)result[3]*=std::floor(Clamp(f.noise+result[3]));
    if(r.gray) {
        float intensity=(result[0]+result[1]+result[2])/3;
        for(unsigned lane=0;lane<3;++lane)result[lane]+=f.gray[3]*(f.gray[lane]*intensity-result[lane]);
    }
    if(r.useAlpha && r.threshold && result[3]<8.0f/256.0f)return false;
    if(r.useAlpha && r.invisible)result[3]=0;
    return true;
}

// GPU fast path only uses convex operations. Signed intermediate arithmetic is
// evaluated by the reference path instead of being silently clamped by TexEnv.
enum class Operation { Replace,Multiply,Mix,Add };
struct Expression { Operation op=Operation::Replace;std::array<uint8_t,3> source{};bool exact=true; };
inline Expression Lower(const Formula& f) {
    auto [a,b,c,d]=f.term;
    if(a==b || c==Zero)return {Operation::Replace,{d,0,0},true};
    if(b==Zero && d==Zero) {
        if(a==One)return {Operation::Replace,{c,0,0},true};
        if(c==One)return {Operation::Replace,{a,0,0},true};
        return {Operation::Multiply,{a,c,0},true};
    }
    if(d==b)return {Operation::Mix,{a,b,c},true};
    // Addition may overflow into LUS's signed wrap range; use the reference
    // path even though the GPU also has an ADD operation.
    return {Operation::Replace,{},false};
}
inline size_t TileOffset(unsigned x,unsigned y,unsigned pitch) {
    unsigned intra=0;
    for(unsigned bit=0;bit<3;++bit)intra|=((x>>bit)&1)<<(2*bit),intra|=((y>>bit)&1)<<(2*bit+1);
    return (static_cast<size_t>(y/8)*(pitch/8)+x/8)*64+intra;
}
inline unsigned TextureExtent(unsigned size) {
    unsigned result=8;while(result<size && result<1024)result*=2;return result;
}
inline uint8_t Byte(float value) { return static_cast<uint8_t>(std::lround(Clamp(value)*255)); }
inline uint32_t Pack(Color color) {
    return uint32_t(Byte(color[0])) | (uint32_t(Byte(color[1]))<<8) |
           (uint32_t(Byte(color[2]))<<16) | (uint32_t(Byte(color[3]))<<24);
}
inline uint16_t Pack5551(Color color) {
    return (Byte(color[0])>>3)<<11 | (Byte(color[1])>>3)<<6 | (Byte(color[2])>>3)<<1 | (color[3]>0);
}
inline int Address(int coordinate,int size,unsigned mode) {
    if(mode&2)return std::clamp((mode&1) && coordinate<0?-coordinate-1:coordinate,0,size-1);
    const int period=(mode&1)?2*size:size;
    int value=coordinate%period;if(value<0)value+=period;
    return value<size?value:period-1-value;
}
inline Color Blend(const Color& source,const Color& destination,bool enabled) {
    if(!enabled)return source;
    Color output{};
    for(unsigned i=0;i<4;++i)output[i]=source[i]*source[3]+destination[i]*(1-source[3]);
    return output;
}
}
