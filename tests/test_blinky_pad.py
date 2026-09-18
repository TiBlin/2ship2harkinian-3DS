#!/usr/bin/env python3
"""Execute the actual LUS native-pad adapter, including its input-lag queue."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
text=(ROOT/'third_party/libultraship/src/libultraship/controller/controldevice/controller/Controller.cpp').read_text(encoding='utf-8')
start=text.index('void Controller::ReadToOSContPad(');opening=text.index('{',start);end=opening+1;level=1
while level:
    level+=(text[end]=='{')-(text[end]=='}');end+=1
function=text[start:end]
code=r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <deque>
#include <algorithm>
#include "ship/port/3ds/BlinkyInput.h"
#define CVAR_SIMULATED_INPUT_LAG "lag"
int lag=0;
namespace Ship {
struct Config {int GetInteger(const char*,int){return lag;}};
struct Context {static Context* GetRawInstance(){static Context c;return &c;}Config* GetConsoleVariables(){static Config c;return &c;}};
namespace Blinky3DS {Pad current;Pad ReadInput(){return current;}}
}
struct OSContPad {uint32_t button=0;int8_t stick_x=0,stick_y=0,right_stick_x=0,right_stick_y=0;float gyro_x=0,gyro_y=0;};
struct Controller {
    std::deque<OSContPad> mPadBuffer;unsigned port=0;
    unsigned GetPortIndex(){return port;}
    void ReadToOSContPad(OSContPad*);
};
'''+function+r'''
int main(){
    Controller controller;
    for(uint32_t high:{0u,0x10000u,0xa5a50000u,0xffff0000u})for(uint32_t low=0;low<=65535;++low){
        Ship::Blinky3DS::current={low,-50,20,30,-40,1,2};
        OSContPad pad;pad.button=high;pad.stick_x=12;
        controller.ReadToOSContPad(&pad);
        assert(pad.button==(high|low));assert(pad.stick_x==12 && pad.stick_y==20);
        assert(pad.right_stick_x==30 && pad.right_stick_y==-40 && pad.gyro_y==2);
        assert(controller.mPadBuffer.size()<=6);
    }
    controller.mPadBuffer.clear();lag=1;
    Ship::Blinky3DS::current={0x100};controller.ReadToOSContPad(nullptr);
    Ship::Blinky3DS::current={0x200};OSContPad delayed;controller.ReadToOSContPad(&delayed);assert(delayed.button==0x100);
    controller.mPadBuffer.clear();controller.port=1;lag=0;
    OSContPad other;controller.ReadToOSContPad(&other);assert(other.button==0);
    std::puts("PASS: 262144 real native LUS pad merges, 32-bit MM buttons, sticks, lag, queue bound and other port");
}
'''
compiler=shutil.which(os.environ.get('CXX','g++'))
if not compiler:raise SystemExit('Set CXX to a host C++ compiler')
env=dict(os.environ);env['PATH']=str(Path(compiler).parent)+os.pathsep+env.get('PATH','')
with tempfile.TemporaryDirectory(prefix='blinky-pad-') as temp:
    temp=Path(temp);source=temp/'pad.cpp';source.write_text(code,encoding='utf-8');binary=temp/'pad.exe'
    subprocess.run([compiler,'-std=c++20','-O2','-D__3DS__','-Wall','-Wextra','-Werror','-I',str(ROOT/'third_party/libultraship/include'),str(source),'-o',str(binary)],check=True,env=env)
    subprocess.run([str(binary)],check=True,env=env)
