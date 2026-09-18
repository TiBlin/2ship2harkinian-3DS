"""Run the production renderer with strict host GPU ownership collaborators.

This is a memory/ordering and CPU-reference test, not PICA200 emulation.
The actual pinned LUS shader decoder is extracted and compiled unchanged.
"""
from pathlib import Path
import argparse,os,subprocess,tempfile
root=Path(__file__).resolve().parents[1];lus=root/'third_party/libultraship'
p=argparse.ArgumentParser();p.add_argument('--cxx',required=True);args=p.parse_args()
env=dict(os.environ);env['PATH']=str(Path(args.cxx).parent)+os.pathsep+env.get('PATH','')
header=(lus/'include/fast/interpreter.h').read_text();source=(lus/'src/fast/interpreter.cpp').read_text()
declarations=header[header.index('enum {\n    SHADER_0'):header.index('union Gfx;')]
start=source.index('void gfx_cc_get_features(');opening=source.index('{',start);level=1;end=opening+1
while level:
    if source[end]=='{':level+=1
    elif source[end]=='}':level-=1
    end+=1
with tempfile.TemporaryDirectory(prefix='blinky-renderer-') as temp:
    temp=Path(temp);(temp/'fast').mkdir()
    (temp/'fast/interpreter.h').write_text('#pragma once\n#include <cstdint>\n#include <compare>\n'+declarations+'\nnamespace Fast { constexpr int16_t ShaderIdUnmask(int id){return (id>>17)&0xffff;} }\n')
    (temp/'decode.cpp').write_text('#include "fast/interpreter.h"\n'+source[start:end])
    for mode,stats,debug in ((0,0,0),(0,1,0),(1,1,1),(1,0,0)):
        binary=temp/'renderer.exe'
        subprocess.run([args.cxx,'-std=c++20','-O1',f'-DBLINKY_OCCLUSION_CULLING={mode}',f'-DBLINKY_RENDER_STATS={stats}',f'-DBLINKY_OCCLUSION_DEBUG={debug}','-Wall','-Wextra','-I',str(temp),'-I',str(root/'tests/blinky/graphics'),'-I',str(lus/'include'),'-I',str(root/'third_party/build-deps/imgui'),'-I',str(root/'src/blinky'),str(root/'src/blinky/gfx_blinky_citro3d.cpp'),str(root/'src/blinky/visibility_bridge.cpp'),str(root/'tests/blinky/graphics/renderer.cpp'),str(temp/'decode.cpp'),'-o',str(binary)],check=True,env=env)
        subprocess.run([str(binary)],check=True,env=env,cwd=temp,timeout=60)
