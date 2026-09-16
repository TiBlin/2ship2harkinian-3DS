#!/usr/bin/env python3
"""Execute MM's actual actor culling methods at mono/stereo frustum edges."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT/'third_party/2ship/mm/src/code/z_actor.c').read_text(encoding='utf-8')


def function(signature):
    start = text.rindex(signature)
    opening = text.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


cpp = r'''
#include <cassert>
#include <cmath>
#include <cstdio>
using f32=float; using s32=int;
struct Vec3f {float x,y,z;};
struct Actor {float cullingVolumeScale=0,cullingVolumeDistance=100,cullingVolumeDownward=0;};
struct PlayState {struct {float fovy=60;} view; Vec3f projectionMtxFDiagonal{1.2990381f,1.7320508f,1};};
static float margin=0;
float Soh3dsStereoActorMargin(){return margin;}
#define CLAMP_MIN(a,b) ((a)<(b)?(b):(a))
#define MAX(a,b) ((a)>(b)?(a):(b))
''' + function('static f32 Actor_HorizontalCullLimit(') + '\n' + function('s32 Actor_CullingVolumeTest(') + r'''
int main(){
    PlayState play; Actor actor; Vec3f point{1.05f,0,10};
    margin=0; assert(!Actor_CullingVolumeTest(&play,&actor,&point,1));
    margin=.1f; assert(Actor_CullingVolumeTest(&play,&actor,&point,1));
    point.x=-1.05f; assert(Actor_CullingVolumeTest(&play,&actor,&point,1));
    point.x=1.11f; assert(!Actor_CullingVolumeTest(&play,&actor,&point,1));
    point={0,1.01f,10}; assert(!Actor_CullingVolumeTest(&play,&actor,&point,1));
    point={0,-1.01f,10}; assert(!Actor_CullingVolumeTest(&play,&actor,&point,1));
    point={0,0,-1}; assert(!Actor_CullingVolumeTest(&play,&actor,&point,1));
    point={0,0,101}; assert(!Actor_CullingVolumeTest(&play,&actor,&point,1));
    point={10.5f,0,10}; assert(Actor_CullingVolumeTest(&play,&actor,&point,10));
    margin=0; assert(!Actor_CullingVolumeTest(&play,&actor,&point,10));
    actor.cullingVolumeScale=2; point={3.05f,0,10};
    play.view.fovy=45; margin=0; assert(!Actor_CullingVolumeTest(&play,&actor,&point,1));
    margin=.1f; assert(Actor_CullingVolumeTest(&play,&actor,&point,1));
    std::puts("MM actor culling: stereo edges, mono, W scale, FOV, vertical/forward rejection PASS");
}
'''
with tempfile.TemporaryDirectory(prefix='2ship-actor-') as temporary:
    directory = Path(temporary)
    source = directory/'test.cpp'
    binary = directory/('test.exe' if os.name=='nt' else 'test')
    source.write_text(cpp, encoding='utf-8')
    subprocess.run([os.environ.get('CXX','g++'), '-std=c++20', '-O2', '-D__3DS__', str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
