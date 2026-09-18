#!/usr/bin/env python3
"""Check the production interpreter's mono work and stereo visibility contract.

Only projection endpoints and evaluation counters are substituted. The matrix,
vertex visibility and face rejection branches come from interpreter.cpp.
Actor coverage is exercised with the renderer's real slider/margin helper.
"""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'third_party/libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8')


def block(signature, text=source):
    start = text.index(signature)
    opening = text.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


matrix = block('void Interpreter::GfxSpMatrix(')
matrix = matrix[matrix.index('    if (parameters & mtx_projection) {'):
                matrix.index(' else { // G_MTX_MODELVIEW')]
vertex = block('void Interpreter::GfxSpVertex(')
active = vertex[vertex.index('    const bool stereoActive ='):
                vertex.index('    for (size_t i = 0;')]
offset = vertex[vertex.index('        d->stereoOffset ='):
                vertex.index('        short U =')]
clip = vertex[vertex.index('        // trivial clip rejection'):
              vertex.index('        d->x = x;')]
cull = block('bool Interpreter::GfxSpTri1Impl(')
cull = cull[:cull.index('    const bool viewportWork')]
cull = cull.replace('bool Interpreter::GfxSpTri1Impl(', 'unsigned Interpreter::EyeMask(')
cull = cull.replace('auto facing = [&](float x1, float x2, float x3) {',
                    'auto facing = [&](float x1, float x2, float x3) { ++facingCalls;')
cull += '    return eyeMask;\n}'
backend = (ROOT / 'platform/3ds/source/gfx_citro3d.cpp').read_text(encoding='utf-8')
actor = (ROOT / 'third_party/2ship/mm/src/code/z_actor.c').read_text(encoding='utf-8')
margin = block('extern "C" float Soh3dsStereoActorMargin(', backend)
actor_limit = block('static f32 Actor_HorizontalCullLimit(', actor)

cpp = r'''
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#include <limits>
#include "fast/stereo_3ds.h"
using f32 = float;
static bool sStereoOutputAvailable = false;
static float sliderState = 0;
float osGet3DSliderState() {return sliderState;}
''' + margin + '\n#define __3DS__\n' + actor_limit + '\n#undef __3DS__\n' + actor_limit.replace(
    'Actor_HorizontalCullLimit', 'Actor_HorizontalCullLimitDesktop') + r'''
enum { CULL_FRONT=1, CULL_BACK=2, CULL_BOTH=3, G_EX_INVERT_CULLING=1 };
unsigned get_attr(unsigned x) {return x;}
enum class Soh3dsProfileSection { Triangle };
struct Soh3dsProfileScope { Soh3dsProfileScope(Soh3dsProfileSection) {} };
struct LoadedVertex {float x=0,y=0,z=0,w=1,stereoOffset=0; unsigned clip_rej=0;};
struct ProjectionProbe {
 unsigned loads=0,multiplies=0,offsets=0;
 void Load(const float[4][4]) {++loads;}
 void Multiply(const float[4][4]) {++multiplies;}
 float ClipOffset(float,float,float) {++offsets;return 0.08f;}
};
struct Interpreter {
 struct Rsp {
  LoadedVertex loaded_vertices[3];
  unsigned geometry_mode=0,extra_geometry_mode=0;
  float P_matrix[4][4]{};
  ProjectionProbe stereoProjection;
 } rsp;
 Rsp* mRsp=&rsp;
 struct Clip {bool stereo_clip_offset=true;float stereo_strength=1,stereo_convergence=160;} mClipParameters;
 bool mFbActive=false;
 unsigned facingCalls=0,aspectCalls=0,matrixCalls=0;
 float AdjXForAspectRatio(float x) {++aspectCalls;return x;}
 void MatrixMul(float[4][4],const float[4][4],const float[4][4]) {++matrixCalls;}
 void Matrix(bool load) {
  const unsigned mtx_projection=1,mtx_load=2,parameters=1|(load?2:0);
  float matrix[4][4]{};matrix[0][0]=7;
''' + matrix + r'''
 }
 void Vertex(float x,float y=0,float z=0,float w=1) {
  LoadedVertex* d=&rsp.loaded_vertices[0];
''' + active + offset + clip + r'''
 }
 unsigned EyeMask(uint8_t,uint8_t,uint8_t,bool,bool);
};
''' + cull + r'''
int main() {
 for(bool available : {false,true}) {
  sStereoOutputAvailable=available;
  for(float slider : {-1.0f,0.0f,0.01f,0.011f,0.25f,1.0f,2.0f,
                     std::numeric_limits<float>::quiet_NaN(),std::numeric_limits<float>::infinity()}) {
   sliderState=slider;
   bool stereo=available && std::isfinite(slider) && slider>0.01f;
   assert(Soh3dsStereoActorMargin()==(stereo?0.10f:0.0f));
   assert(Actor_HorizontalCullLimit()==(stereo?1.10f:1.0f));
   assert(Actor_HorizontalCullLimitDesktop()==1.0f);
  }
 }
 Interpreter i;
 for(float strength : {0.0f,0.5f,1.0f,0.0f}) {
  i.mClipParameters.stereo_strength=strength;
  i.rsp.stereoProjection={};i.matrixCalls=0;
  i.Matrix(true);i.Matrix(false);
  assert(i.rsp.P_matrix[0][0]==7 && i.matrixCalls==1);
  assert(i.rsp.stereoProjection.loads==(strength>0));
  assert(i.rsp.stereoProjection.multiplies==(strength>0));
  for(bool offscreen : {false,true}) {
   i.mFbActive=offscreen;i.rsp.stereoProjection.offsets=0;i.aspectCalls=0;
   // A vertex just beyond the left edge is visible to the shifted right eye.
   i.Vertex(-1.03f);
   bool stereo=strength>0 && !offscreen;
   assert(i.rsp.stereoProjection.offsets==stereo && i.aspectCalls==stereo);
   assert(i.rsp.loaded_vertices[0].stereoOffset==(stereo?0.08f:0));
   assert(bool(i.rsp.loaded_vertices[0].clip_rej&1)==!stereo);
   i.Vertex(1.03f);assert(i.rsp.loaded_vertices[0].clip_rej==2);
   i.Vertex(0,-2);assert(i.rsp.loaded_vertices[0].clip_rej==4);
   i.Vertex(0,2);assert(i.rsp.loaded_vertices[0].clip_rej==8);
   i.Vertex(0,0,2);assert(i.rsp.loaded_vertices[0].clip_rej==32);
  }
 }
 i.mFbActive=false;i.mClipParameters.stereo_strength=1;i.mClipParameters.stereo_clip_offset=false;
 i.rsp.stereoProjection={};i.Matrix(true);i.Matrix(false);i.Vertex(-1.03f);
 assert(i.rsp.stereoProjection.loads==0 && i.rsp.stereoProjection.multiplies==0);
 assert(i.rsp.stereoProjection.offsets==0 && i.rsp.loaded_vertices[0].clip_rej==1);
 i.mClipParameters.stereo_clip_offset=true;
 // The face changes orientation between the two eyes.
 i.rsp.loaded_vertices[0]={0,0,0,1,0,0};
 i.rsp.loaded_vertices[1]={-0.01f,1,0,1,0.03f,0};
 i.rsp.loaded_vertices[2]={0,2,0,1,0,0};
 for(bool offscreen : {false,true})for(bool rect : {false,true})for(float strength : {0.0f,1.0f}) {
  i.mFbActive=offscreen;i.mClipParameters.stereo_strength=strength;
  bool stereo=strength>0 && !offscreen && !rect;
  i.rsp.geometry_mode=CULL_FRONT;i.facingCalls=0;
  assert(i.EyeMask(0,1,2,rect,false)==(stereo?1:3));
  assert(i.facingCalls==(stereo?2:1));
  i.rsp.geometry_mode=CULL_BACK;i.facingCalls=0;
  assert(i.EyeMask(0,1,2,rect,false)==(stereo?2:0));
  assert(i.facingCalls==(stereo?2:1));
 }
 // A cached stereo attribute cannot contaminate mono culling via NaN*0.
 i.mFbActive=false;i.mClipParameters.stereo_strength=0;i.rsp.geometry_mode=CULL_FRONT;
 for(auto& v:i.rsp.loaded_vertices)v.stereoOffset=std::numeric_limits<float>::quiet_NaN();
 assert(i.EyeMask(0,1,2,false,false)==3);
 i.rsp.geometry_mode=0;i.facingCalls=0;
 assert(i.EyeMask(0,1,2,false,false)==3 && i.facingCalls==0);
 for(auto& v:i.rsp.loaded_vertices)v.clip_rej=8;
 assert(i.EyeMask(0,1,2,false,false)==0 && i.facingCalls==0);
 std::puts("mono interpreter: zero stereo projection work, one face evaluation, offscreen/rect, actor coverage and stereo visibility PASS");
}
'''
with tempfile.TemporaryDirectory(prefix='soh-mono-') as directory:
    path = Path(directory)
    cpp_file = path / 'mono.cpp'
    binary = path / ('mono.exe' if os.name == 'nt' else 'mono')
    cpp_file.write_text(cpp)
    subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++20', '-O2', '-Wall', '-Wextra',
                    '-I' + str(ROOT / 'third_party/libultraship/include'),
                    str(cpp_file), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
