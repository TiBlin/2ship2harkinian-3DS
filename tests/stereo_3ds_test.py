#!/usr/bin/env python3
"""Host tests of stereo math and extracted production culling/draw submission.

GPU endpoints record commands; projection, packing, clipping, face rejection,
eye masks, target binding and submission loops are taken from production code.
This does not emulate PICA rasterization or replace a physical console test.
"""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
backend = (ROOT / 'platform/3ds/source/gfx_citro3d.cpp').read_text(encoding='utf-8')
interpreter = (ROOT / 'third_party/libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8')


def block(text, signature):
    start = text.index(signature)
    opening = text.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


shader = block((ROOT / 'platform/3ds/include/gfx_citro3d.h').read_text(encoding='utf-8'), 'struct ShaderProgram {') + ';'
packed = block(backend, 'struct PackedVertex {') + ';'
helpers = backend[backend.index('#ifndef SOH3DS_EXPERIMENT_COMMON_PACK'):
                  backend.index('constexpr uint32_t kBottomDisplayTransferFlags')]
cull = block(interpreter, 'bool Interpreter::GfxSpTri1Impl(')
cull = cull[:cull.index('    const bool viewportWork')]
cull = cull.replace('bool Interpreter::GfxSpTri1Impl(', 'unsigned Interpreter::EyeMask(')
cull += '    return eyeMask;\n}'
draw_start = backend.index('    const bool drawStereo =', backend.index('void GfxRenderingAPICitro3D::DrawTriangles('))
draw_end = backend.index('    mImpl->packedVertexCount += vertexCount;', draw_start)
draw = backend[draw_start:draw_end]
start_frame = block(backend, 'void GfxRenderingAPICitro3D::StartFrame(')
right_frame_clear = block(start_frame, '    if (mImpl->stereoActive) {')

cpp = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>
#include <vector>
#include "fast/stereo_3ds.h"
#include "decal_depth_3ds.h"
using namespace Fast;
using namespace Fast::Stereo3DS;
''' + shader + packed + block(backend, 'uint8_t FloatColorToByte(') + '\n' + helpers + r'''
constexpr size_t kMaxVertexStrideFloats = 64;
''' + block(backend, 'size_t ClipTriangleAgainstW(') + r'''
enum { CULL_FRONT=1, CULL_BACK=2, CULL_BOTH=3, G_EX_INVERT_CULLING=1 };
unsigned get_attr(unsigned x) {return x;}
enum class Soh3dsProfileSection { Triangle };
struct Soh3dsProfileScope { Soh3dsProfileScope(Soh3dsProfileSection) {} };
struct LoadedVertex {float x=0,y=0,z=0,w=1,stereoOffset=0; unsigned clip_rej=0;};
struct Interpreter {
 struct Rsp {LoadedVertex loaded_vertices[3]; unsigned geometry_mode=0,extra_geometry_mode=0;} rsp;
 Rsp* mRsp=&rsp;
 struct Clip {float stereo_strength=1;} mClipParameters;
 bool mFbActive=false;
 unsigned EyeMask(uint8_t,uint8_t,uint8_t,bool,bool);
};
''' + cull + r'''
constexpr int GPU_RB_DEPTH16=0;
constexpr uint32_t kFramebufferClearColor=0;
constexpr uint32_t kTopLogicalWidth=400,kTopWideWidth=800,kTopHeight=240;
struct C3D_RenderTarget { int id; struct {void* depthBuf=(void*)1;int depthFmt=GPU_RB_DEPTH16;} frameBuf; };
''' + block(backend, 'float ActiveDepthUnits3DS(') + r'''
constexpr int GPU_VERTEX_SHADER=0,GPU_SCISSOR_NORMAL=1,GPU_SCISSOR_DISABLE=0,GPU_TRIANGLES=0;
enum C3D_ClearBits { C3D_CLEAR_COLOR=1,C3D_CLEAR_DEPTH=2,C3D_CLEAR_ALL=3 };
struct Event {int kind,a,b,c,d,e=0;};
std::vector<Event> events;
int targetId=-1;
void C3D_FrameDrawOn(C3D_RenderTarget* t) {targetId=t->id;events.push_back({0,targetId,0,0,0});}
void C3D_SetViewport(int x,int y,int w,int h) {events.push_back({1,x,y,w,h});}
void C3D_SetScissor(int mode,int x,int y,int w,int h) {events.push_back({2,mode,x,y,w,h});}
void C3D_FVUnifSet(int,int,float x,float,float,float) {events.push_back({3,int(x*100),0,0,0});}
void C3D_DrawArrays(int,int first,int count) {events.push_back({4,targetId,first,count,0});}
void C3D_DepthMap(bool,float,float) {}
void C3D_RenderTargetClear(C3D_RenderTarget* t,C3D_ClearBits bits,unsigned color,unsigned) {
 assert(color==0); // Raw RGB565 black, not the old RGBA8 0xFF.
 events.push_back({5,t->id,int(bits),0,0});
}
struct GfxRenderingAPICitro3D {
 C3D_RenderTarget left{0},right{1},bottom{2},leftScene{3},rightScene{4};
 struct State {
  bool stereoActive=true,stereoScaledActive=false,decal=false,scissorEnabled=true;
  float stereoStrength=0.75f;
  int stereoUniform=4;
  int viewportX=4,viewportY=8,viewportWidth=380,viewportHeight=220;
  int scissorX=5,scissorY=9,scissorWidth=360,scissorHeight=210;
  uint32_t outputWidth=400,renderWidth=400,renderHeight=240;
  C3D_RenderTarget *activeTarget,*topTarget,*rightTarget,*gameTarget,*sceneTarget,*stereoSceneTarget;
  PackedVertex *packedVertices;
  unsigned drawCallCount=0,sampleFogDrawCount=0,triangleCount=0;
 } state;
 State* mImpl=&state;
 GfxRenderingAPICitro3D() {
  state.activeTarget=state.topTarget=state.gameTarget=&left;state.rightTarget=&right;
  state.sceneTarget=&leftScene;state.stereoSceneTarget=&rightScene;
 }
 void BindTopEye(bool);
 void ClearFramebuffer(bool,bool);
 void SetViewport(int,int,int,int);
 void SetScissor(int,int,int,int);
 void ClearRightForNewFrame() {
''' + right_frame_clear + r'''
 }
 void Submit(const float* drawVertices,size_t vertexCount,ShaderProgram* program) {
  size_t firstVertex=0;
''' + draw + r'''
 }
};
''' + block(backend, 'void GfxRenderingAPICitro3D::BindTopEye(') + '\n' + block(backend, 'void GfxRenderingAPICitro3D::ClearFramebuffer(') + '\n' + block(backend, 'void GfxRenderingAPICitro3D::SetViewport(') + '\n' + block(backend, 'void GfxRenderingAPICitro3D::SetScissor(') + r'''
void near(float a,float b,float eps=0.00001f) {assert(std::isfinite(a));assert(std::fabs(a-b)<=eps);}
void Math() {
 float p[4][4]={{1.3f,0,0,0},{0,1.73f,0,0},{0,0,-1.01f,-1},{0,0,-20.1f,0}};
 Projection projection;projection.Load(p);
 near(projection.scale,1);near(projection.focalX,1.3f);
 near(projection.ClipOffset(Convergence),0);
 // Compare against the delivered V1 formula, including both disparity clamps.
 near(MaxNdcDisparity*400/2,16);
 for(float w:{0.001f,1.0f,40.0f,120.0f,160.0f,200.0f,1000.0f,100000.0f}) {
  const float oldOffset=std::clamp(1.3f*0.8f*3.0f*(w/160.0f-1.0f),-0.04f*w,0.04f*w);
  near(projection.ClipOffset(w,0.8f)/w,2*oldOffset/w);
 }
 for(int mode=0;mode<3;++mode) {
  const float convergence=ConvergenceForMode(mode);
  near(projection.ClipOffset(convergence,0.8f,convergence),0);
  assert(projection.ClipOffset(convergence/2,0.8f,convergence)<0);
  assert(projection.ClipOffset(convergence*2,0.8f,convergence)>0);
 }
 assert(projection.ClipOffset(160,0.8f,ConvergenceForMode(0))>0);
 assert(projection.ClipOffset(160,0.8f,ConvergenceForMode(2))<0);
 near(ConvergenceForMode(-1),160);near(ConvergenceForMode(3),160);
 near(projection.ClipOffset(300,0.8f,-1),projection.ClipOffset(300,0.8f));
 near(projection.ClipOffset(300,0.8f,std::numeric_limits<float>::quiet_NaN()),projection.ClipOffset(300,0.8f));
 assert(projection.ClipOffset(40)<0 && projection.ClipOffset(1000)>0);
 for(float scale:{0.125f,1.0f,3.0f}) {
  float scaled[4][4];for(int i=0;i<4;++i)for(int j=0;j<4;++j)scaled[i][j]=p[i][j]*scale;
  Projection q;q.Load(scaled);
  for(float distance:{60.0f,160.0f,500.0f,3000.0f}) {
   // Independent view translation and shifted projection, then divide by W.
   const float x=15;
   const float left=1.3f*x/distance;
   const float right=1.3f*(x-EyeSeparation)/distance+1.3f*EyeSeparation/Convergence;
   const float expected=std::clamp((right-left)*0.8f,-MaxNdcDisparity,MaxNdcDisparity);
   near(q.ClipOffset(scale*distance,0.8f)/(scale*distance),expected);
  }
 }
 for(float w:{0.0001f,1.0f,10.0f,100.0f,10000.0f})assert(std::fabs(projection.ClipOffset(w))<=MaxNdcDisparity*w);
 assert(projection.ClipOffset(-1)==0 && projection.ClipOffset(0)==0);
 assert(projection.ClipOffset(std::numeric_limits<float>::infinity())==0);
 const float expected=projection.ClipOffset(300);
 float view[4][4]={{0,0,1,0},{0,1,0,0},{-1,0,0,0},{10,20,30,1}};
 projection.Multiply(view);near(projection.ClipOffset(300),expected);
 float identity[4][4]={{1,0,0,0},{0,1,0,0},{0,0,1,0},{0,0,0,1}};
 projection.Load(identity);assert(projection.ClipOffset(300)==0);
 projection.Multiply(p);near(projection.ClipOffset(300),expected);
 projection.Multiply(p);assert(projection.ClipOffset(300)==0);
 p[0][0]*=-1;projection.Load(p);near(projection.ClipOffset(300),expected);
 p[0][1]=1;projection.Load(p);assert(projection.ClipOffset(300)==0);
 assert(Strength(-1)==0 && Strength(0.01f)==0 && Strength(0.5f)==0.5f && Strength(2)==1);
 assert(Strength(std::numeric_limits<float>::quiet_NaN())==0);
}
void Culling() {
 Interpreter i;
 // A face close to edge-on rotates across its silhouette between the eyes.
 i.rsp.loaded_vertices[0]={0,0,0,1,0,0};
 i.rsp.loaded_vertices[1]={-0.01f,1,0,1,0.03f,0};
 i.rsp.loaded_vertices[2]={0,2,0,1,0,0};
 i.rsp.geometry_mode=CULL_BACK;assert(i.EyeMask(0,1,2,false,false)==2);
 i.rsp.geometry_mode=CULL_FRONT;assert(i.EyeMask(0,1,2,false,false)==1);
 i.rsp.extra_geometry_mode=G_EX_INVERT_CULLING;assert(i.EyeMask(0,1,2,false,false)==2);
 i.rsp.extra_geometry_mode=0;
 i.mClipParameters.stereo_strength=0;assert(i.EyeMask(0,1,2,false,false)==3);
 i.mClipParameters.stereo_strength=1;i.mFbActive=true;assert(i.EyeMask(0,1,2,false,false)==3);
 i.mFbActive=false;assert(i.EyeMask(0,1,2,true,false)==3);
 i.rsp.geometry_mode=CULL_BOTH;assert(i.EyeMask(0,1,2,false,false)==0);
 i.rsp.geometry_mode=0;assert(i.EyeMask(0,1,2,false,false)==3);
 for(auto& v:i.rsp.loaded_vertices)v.clip_rej=8;
 assert(i.EyeMask(0,1,2,false,false)==0);
}
void Packing() {
 for(bool alpha:{false,true})for(bool fog:{false,true})for(bool tex2:{false,true}) {
  ShaderProgram p;p.usedTextures[0]=true;p.usedTextures[1]=tex2;p.numInputs=1;p.alpha=alpha;p.fog=fog;
  p.textureOffsets[0]=4;p.textureOffsets[1]=6;unsigned end=tex2?8:6;
  p.fogOffset=end;p.inputOffsets[0]=end+(fog?4:0);p.strideFloats=p.inputOffsets[0]+(alpha?4:3)+2;
  std::vector<float> source(p.strideFloats*3,0.5f);
  for(int i=0;i<3;++i){source[i*p.strideFloats+3]=1;source[(i+1)*p.strideFloats-2]=0.02f*i;source[(i+1)*p.strideFloats-1]=3;}
  PackedVertex generic[5]{},common[5]{};
  PackGenericVertices(source.data(),generic+1,3,&p,0,1,{1,1},{1,1},{0,0},{false,false});
  assert(TryPackCommonVertices(source.data(),common+1,3,&p,0,1,{1,1},{1,1},{false,false}));
  assert(std::memcmp(generic,common,sizeof(generic))==0);
  for(int i=0;i<3;++i){near(common[i+1].stereoOffset,0.02f*i);near(common[i+1].position[3],1);}
  // Near-plane clipping must preserve the mask on both generated triangles.
  source[2]=-2;
  const float* tri[]={source.data(),source.data()+p.strideFloats,source.data()+p.strideFloats*2};
  std::vector<float> clipped(p.strideFloats*6);
  const size_t count=ClipTriangleAgainstW(tri,p.strideFloats,clipped.data());
  assert(count==6);
  for(size_t v=0;v<count;++v){near(clipped[(v+1)*p.strideFloats-1],3);assert(std::isfinite(clipped[(v+1)*p.strideFloats-2]));}
 }
}
void Submission() {
 GfxRenderingAPICitro3D renderer;ShaderProgram p;p.strideFloats=6;
 PackedVertex vertices[9]{};renderer.state.packedVertices=vertices;
 float data[54]{};
 for(int i=0;i<9;++i)data[i*6+5]=3;
 events.clear();renderer.Submit(data,9,&p);
 unsigned draws=0;
 for(const auto& e:events)if(e.kind==4){assert(e.a==int(draws));assert(e.b==0 && e.c==9);++draws;}
 assert(draws==2 && renderer.state.activeTarget==renderer.state.topTarget);
 // Every target selection is followed by viewport, then scissor, then eye.
 for(size_t e=0;e<events.size();++e)if(events[e].kind==0){assert(events[e+1].kind==1 && events[e+2].kind==2 && events[e+3].kind==3);}
 for(int i=0;i<3;++i)data[i*6+5]=1;
 for(int i=3;i<6;++i)data[i*6+5]=2;
 events.clear();renderer.Submit(data,9,&p);draws=0;
 for(const auto& e:events)if(e.kind==4){if(e.a==0)assert(e.b==0 || e.b==6);else assert(e.b==3 && e.c==6);++draws;}
 assert(draws==3);
 renderer.state.activeTarget=&renderer.bottom;targetId=2;
 events.clear();renderer.Submit(data,9,&p);
 for(const auto& e:events)if(e.kind==4)assert(e.a==2);
 renderer.state.activeTarget=&renderer.left;
 events.clear();renderer.ClearFramebuffer(true,true);assert(events.size()==2 && events[0].a==0 && events[1].a==1);
 renderer.state.activeTarget=&renderer.bottom;
 events.clear();renderer.ClearFramebuffer(true,true);assert(events.size()==1 && events[0].a==2);
 renderer.state.activeTarget=&renderer.left;renderer.state.stereoActive=false;
 events.clear();renderer.ClearFramebuffer(false,true);assert(events.size()==1 && events[0].b==C3D_CLEAR_DEPTH);
 targetId=0;events.clear();renderer.Submit(nullptr,9,&p);
 assert(events.size()==1 && events[0].kind==4 && events[0].a==0 && events[0].c==9);
 renderer.state.decal=true;events.clear();renderer.Submit(nullptr,9,&p);
 draws=0;for(const auto& e:events)if(e.kind==4){assert(e.a==0 && e.c==3);++draws;}
 assert(draws==3);
}
void ScaledSubmission() {
 GfxRenderingAPICitro3D renderer;ShaderProgram p;p.strideFloats=6;
 PackedVertex vertices[9]{};renderer.state.packedVertices=vertices;
 float data[54]{};for(int i=0;i<9;++i)data[i*6+5]=3;
 renderer.state.stereoScaledActive=true;
 renderer.state.activeTarget=renderer.state.gameTarget=&renderer.leftScene;
 renderer.state.renderWidth=240;renderer.state.renderHeight=144;
 // Both scene targets receive the same unrotated, scaled viewport/scissor.
 for(C3D_RenderTarget* target:{&renderer.leftScene,&renderer.rightScene}) {
  renderer.state.activeTarget=target;events.clear();
  renderer.SetViewport(10,20,300,200);renderer.SetScissor(10,20,300,200);
  assert(events.size()==2);
  assert(events[0].kind==1 && events[0].a==6 && events[0].b==12 && events[0].c==180 && events[0].d==120);
  assert(events[1].kind==2 && events[1].a==GPU_SCISSOR_NORMAL && events[1].b==6 && events[1].c==12 && events[1].d==186 && events[1].e==132);
 }
 renderer.state.activeTarget=&renderer.leftScene;events.clear();renderer.Submit(data,9,&p);
 unsigned draws=0;
 for(size_t n=0;n<events.size();++n) {
  const auto& e=events[n];
  if(e.kind==4){assert(e.a==3+int(draws) && e.b==0 && e.c==9);++draws;}
  if(e.kind==0){
   const auto& v=events[n+1];const auto& s=events[n+2];
   assert(v.kind==1 && v.a==6 && v.b==12 && v.c==180 && v.d==120);
   assert(s.kind==2 && s.b==6 && s.c==12 && s.d==186 && s.e==132);
  }
 }
 assert(draws==2 && renderer.state.activeTarget==&renderer.leftScene);
 events.clear();renderer.ClearFramebuffer(true,true);
 assert(events.size()==2 && events[0].a==3 && events[1].a==4);
 assert(events[0].b==C3D_CLEAR_ALL && events[1].b==C3D_CLEAR_ALL);
 events.clear();renderer.ClearRightForNewFrame();
 assert(events.size()==2 && events[0].kind==0 && events[0].a==4 && events[1].kind==5 && events[1].a==4);
 events.clear();renderer.SetScissor(0,0,0,240);renderer.BindTopEye(true);
 assert(!renderer.state.scissorEnabled && events[0].a==GPU_SCISSOR_DISABLE);
 assert(events[3].kind==2 && events[3].a==GPU_SCISSOR_DISABLE);
 // At 100%, LCD targets retain the native tilted viewport and right clear.
 renderer.state.stereoScaledActive=false;
 renderer.state.activeTarget=renderer.state.gameTarget=&renderer.left;
 renderer.state.renderWidth=400;renderer.state.renderHeight=240;events.clear();
 renderer.SetViewport(10,20,300,200);renderer.SetScissor(10,20,300,200);
 assert(events[0].a==20 && events[0].b==10 && events[0].c==200 && events[0].d==300);
 assert(events[1].b==20 && events[1].c==10 && events[1].d==220 && events[1].e==310);
 events.clear();renderer.ClearRightForNewFrame();assert(events.size()==2 && events[1].a==1);
 renderer.state.stereoActive=false;events.clear();renderer.ClearRightForNewFrame();assert(events.empty());
}
int main(){Math();Culling();Packing();Submission();ScaledSubmission();std::puts("stereo: projection, convergence, limits, mirrors, culling, packing, clipping, eye masks, native/scaled viewport/scissor and paired clears PASS");}
'''

with tempfile.TemporaryDirectory(prefix='soh-stereo-') as directory:
    path = Path(directory)
    source = path / 'stereo.cpp'
    binary = path / ('stereo.exe' if os.name == 'nt' else 'stereo')
    source.write_text(cpp)
    compiler = os.environ.get('CXX', 'g++')
    subprocess.run([compiler, '-std=c++20', '-O2', '-Wall', '-Wextra',
                    '-I' + str(ROOT / 'third_party/libultraship/include'),
                    '-I' + str(ROOT / 'platform/3ds/include'), str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
