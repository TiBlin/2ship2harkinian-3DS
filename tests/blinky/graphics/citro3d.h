#pragma once
#include "3ds.h"
#include <algorithm>
#include <array>
#include <vector>
enum {GPU_CULL_NONE,GPU_FLOAT,GPU_TRIANGLES,GPU_SCISSOR_NORMAL,GPU_SCISSOR_DISABLE,GPU_GEQUAL,GPU_GREATER,GPU_ALWAYS,
GPU_WRITE_ALPHA=8,GPU_WRITE_COLOR=15,GPU_WRITE_DEPTH=16,GPU_BLEND_ADD,GPU_SRC_ALPHA,GPU_ONE_MINUS_SRC_ALPHA,GPU_ONE,GPU_ZERO,
GPU_RGBA8,GPU_RB_RGB8,GPU_RB_DEPTH16,GPU_TEXFACE_2D,GPU_LINEAR,GPU_NEAREST,GPU_CLAMP_TO_EDGE,GPU_MIRRORED_REPEAT,GPU_REPEAT};
constexpr int GPU_LOGICOP_SET=4;
enum GPU_TEVSRC {GPU_CONSTANT,GPU_PRIMARY_COLOR,GPU_TEXTURE0,GPU_TEXTURE1,GPU_PREVIOUS,GPU_PREVIOUS_BUFFER,GPU_TEXTURE2};
enum GPU_TEVOP_RGB {GPU_TEVOP_RGB_SRC_COLOR,GPU_TEVOP_RGB_SRC_ALPHA};
enum GPU_COMBINEFUNC {GPU_REPLACE,GPU_MODULATE,GPU_INTERPOLATE};
enum C3D_TexEnvMode {C3D_RGB=1,C3D_Alpha=2,C3D_Both=3};
using GPU_WRITEMASK=int;using C3D_ClearBits=int;using C3D_DEPTHTYPE=int;
constexpr unsigned C3D_DEFAULT_CMDBUF_SIZE=0x40000,GX_CMDLIST_FLUSH=1,C3D_CLEAR_COLOR=1,C3D_CLEAR_DEPTH=2,C3D_CLEAR_ALL=3;
constexpr unsigned GX_TRANSFER_FMT_RGB8=0,GX_TRANSFER_SCALE_NO=0;
#define GX_TRANSFER_RAW_COPY(x) ((x)<<3)
#define GX_TRANSFER_FLIP_VERT(x) ((x)&1)
#define GX_TRANSFER_OUT_TILED(x) 0
#define GX_TRANSFER_IN_FORMAT(x) 0
#define GX_TRANSFER_OUT_FORMAT(x) 0
#define GX_TRANSFER_SCALING(x) 0
struct C3D_Tex {void* data=nullptr;unsigned size=0,width=0,height=0;};
struct C3D_FrameBuf {void* colorBuf=nullptr;void* depthBuf=nullptr;unsigned width=0,height=0;};
struct C3D_RenderTarget {C3D_FrameBuf frameBuf;bool ownsColor=true;};
struct C3D_TexEnv {
    GPU_TEVSRC rgb[3]{GPU_PREVIOUS},alpha[3]{GPU_PREVIOUS};
    GPU_TEVOP_RGB operands[3]{};
    GPU_COMBINEFUNC rgbOp=GPU_REPLACE,alphaOp=GPU_REPLACE;
    unsigned color=0xffffffff;
};
struct C3D_AttrInfo{};struct C3D_BufInfo{};
namespace gpuFake {
inline bool frame=false,pending=false;inline unsigned draws=0,copies=0,targets=0,textures=0;
inline std::array<C3D_TexEnv,6> stages;
inline unsigned bufferColor=0,bufferMask=0;
inline const float* vertexData=nullptr;
inline std::vector<float> submitted;
inline C3D_Tex* bound[3]{};
inline C3D_RenderTarget* target=nullptr;
inline std::array<int,4> viewport{};
inline unsigned outputFlags=0;
inline void (*rasterize)(const float*,size_t,C3D_RenderTarget*,const std::array<int,4>&)=nullptr;
struct PixelState {bool depth=false,alpha=false;int depthFunction=GPU_ALWAYS,mask=15,alphaFunction=GPU_ALWAYS,alphaRef=0,logic=-1;int src=GPU_ONE,dst=GPU_ZERO;};
inline PixelState pixel;
inline std::vector<PixelState> drawStates;
}
inline bool C3D_Init(unsigned){std::fill_n(gpuFake::bound,3,nullptr);return true;}
inline void C3D_Fini(){assert(!gpuFake::frame && gpuFake::targets==0 && gpuFake::textures==0);}
inline bool C3D_FrameBegin(unsigned){assert(!gpuFake::frame);gpuFake::pending=false;gpuFake::frame=true;return true;}
inline void C3D_FrameEnd(unsigned){assert(gpuFake::frame);gpuFake::frame=false;}
inline bool C3D_FrameDrawOn(C3D_RenderTarget* target){assert(gpuFake::frame);gpuFake::target=target;return true;}
inline bool C3D_TexInit(C3D_Tex* t,unsigned w,unsigned h,int){t->width=w;t->height=h;t->size=w*h*4;t->data=std::calloc(1,t->size);++gpuFake::textures;return t->data;}
inline bool C3D_TexInitVRAM(C3D_Tex* t,unsigned w,unsigned h,int f){return C3D_TexInit(t,w,h,f);}
inline void C3D_TexDelete(C3D_Tex* t){assert(!gpuFake::pending);std::free(t->data);t->data=nullptr;--gpuFake::textures;}
inline void C3D_TexSetWrap(C3D_Tex*,int,int){}
inline void C3D_TexSetFilter(C3D_Tex*,int,int){}
inline void C3D_TexFlush(C3D_Tex*){}
inline void C3D_TexBind(int unit,C3D_Tex* tex){gpuFake::bound[unit]=tex;}
inline C3D_RenderTarget* C3D_RenderTargetCreate(unsigned w,unsigned h,int,int depth){
    auto* t=new C3D_RenderTarget;t->frameBuf={std::calloc(w*h,4),depth<0?nullptr:std::calloc(w*h,2),w,h};++gpuFake::targets;return t;
}
inline C3D_RenderTarget* C3D_RenderTargetCreateFromTex(C3D_Tex* image,int,int,int depth){
    auto* t=new C3D_RenderTarget;t->ownsColor=false;t->frameBuf={image->data,depth<0?nullptr:std::calloc(image->width*image->height,2),image->width,image->height};++gpuFake::targets;return t;
}
inline void C3D_RenderTargetDelete(C3D_RenderTarget* target){assert(!gpuFake::frame && !gpuFake::pending);if(target->ownsColor)std::free(target->frameBuf.colorBuf);std::free(target->frameBuf.depthBuf);delete target;--gpuFake::targets;}
inline void C3D_RenderTargetSetOutput(C3D_RenderTarget*,int,int,unsigned flags){gpuFake::outputFlags=flags;}
inline void C3D_RenderTargetClear(C3D_RenderTarget* target,int flags,unsigned color,unsigned depth){
    assert(!gpuFake::frame);auto& fb=target->frameBuf;
    if(flags&1)std::fill_n(static_cast<unsigned*>(fb.colorBuf),fb.width*fb.height,color);
    if((flags&2) && fb.depthBuf)std::fill_n(static_cast<uint16_t*>(fb.depthBuf),fb.width*fb.height,depth);
}
inline void C3D_SyncTextureCopy(u32* from,u32,u32* to,u32,unsigned bytes,unsigned flags){
    // Public SDK contract: only outside a frame does this call complete before
    // returning. Fail the test if production uses it as a fence inside a frame.
    assert(!gpuFake::frame && flags==8);++gpuFake::copies;std::memcpy(to,from,bytes);
}
inline void C3D_BindProgram(shaderProgram_s*){}
inline void C3D_CullFace(int){}
inline void C3D_DepthMap(bool,float,float){}
inline C3D_AttrInfo* C3D_GetAttrInfo(){static C3D_AttrInfo info;return &info;}
inline void AttrInfo_Init(C3D_AttrInfo*){}
inline void AttrInfo_AddLoader(C3D_AttrInfo*,int,int,int){}
inline C3D_BufInfo* C3D_GetBufInfo(){static C3D_BufInfo info;return &info;}
inline void BufInfo_Init(C3D_BufInfo*){}
inline void BufInfo_Add(C3D_BufInfo*,void* vertices,size_t stride,int,int){assert(stride==14*sizeof(float));gpuFake::vertexData=static_cast<float*>(vertices);}
inline void C3D_DrawArrays(int,int,size_t count){assert(gpuFake::frame);gpuFake::submitted.assign(gpuFake::vertexData,gpuFake::vertexData+count*14);gpuFake::drawStates.push_back(gpuFake::pixel);if(gpuFake::rasterize)gpuFake::rasterize(gpuFake::vertexData,count,gpuFake::target,gpuFake::viewport);gpuFake::pending=true;++gpuFake::draws;}
inline void C3D_SetViewport(int x,int y,int w,int h){gpuFake::viewport={x,y,w,h};}
inline void C3D_SetScissor(int,int,int,int,int){}
inline void C3D_DepthTest(bool enabled,int function,int mask){gpuFake::pixel.depth=enabled;gpuFake::pixel.depthFunction=function;gpuFake::pixel.mask=mask;}
inline void C3D_AlphaTest(bool enabled,int function,int ref){gpuFake::pixel.alpha=enabled;gpuFake::pixel.alphaFunction=function;gpuFake::pixel.alphaRef=ref;}
inline void C3D_AlphaBlend(int,int,int src,int dst,int,int){gpuFake::pixel.logic=-1;gpuFake::pixel.src=src;gpuFake::pixel.dst=dst;}
inline void C3D_ColorLogicOp(int operation){gpuFake::pixel.logic=operation;}
inline void C3D_TexEnvInit(C3D_TexEnv* env){*env={};}
inline void C3D_TexEnvSrc(C3D_TexEnv* e,int mode,GPU_TEVSRC a,GPU_TEVSRC b=GPU_PRIMARY_COLOR,GPU_TEVSRC c=GPU_PRIMARY_COLOR){
    if(mode&C3D_RGB){e->rgb[0]=a;e->rgb[1]=b;e->rgb[2]=c;}
    if(mode&C3D_Alpha){e->alpha[0]=a;e->alpha[1]=b;e->alpha[2]=c;}
}
inline void C3D_TexEnvFunc(C3D_TexEnv* e,int mode,GPU_COMBINEFUNC op){if(mode&C3D_RGB)e->rgbOp=op;if(mode&C3D_Alpha)e->alphaOp=op;}
inline void C3D_TexEnvOpRgb(C3D_TexEnv* e,GPU_TEVOP_RGB a,GPU_TEVOP_RGB b,GPU_TEVOP_RGB c){e->operands[0]=a;e->operands[1]=b;e->operands[2]=c;}
inline void C3D_TexEnvColor(C3D_TexEnv* e,unsigned color){e->color=color;}
inline void C3D_TexEnvBufUpdate(int mode,int mask){assert(mode==C3D_Both);gpuFake::bufferMask=mask;}
inline void C3D_TexEnvBufColor(unsigned color){gpuFake::bufferColor=color;}
inline void C3D_SetTexEnv(int i,C3D_TexEnv* env){gpuFake::stages.at(i)=*env;}
inline C3D_TexEnv* C3D_GetTexEnv(int i){return &gpuFake::stages.at(i);}

inline float C3D_GetDrawingTime(){return 0;}
inline float C3D_GetProcessingTime(){return 0;}
