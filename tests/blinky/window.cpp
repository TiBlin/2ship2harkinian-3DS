#include <3ds.h>
#include "fast/backends/gfx_blinky_3ds_window.h"
#include <cmath>
namespace Fast {
int guiCalls=0, discoverCalls=0;
void BlinkyInitializeLusGui() { ++guiCalls; }
bool BlinkyUpdateLusControllers(bool discover) { discoverCalls+=discover; return true; }
}
extern "C" int BlinkyTouchRead(int*, int*);
extern "C" int BlinkyTargetFps();
int released=0; bool fullscreen=false;
void Release() { ++released; }
void Fullscreen(bool b) { fullscreen=b; }
int main() {
    Fast::GfxWindowBackendBlinky3DS window;
    assert(!window.IsRunning());
    window.SetKeyboardCallbacks(nullptr,nullptr,Release);
    window.Init("MM","test",false,1920,1080,25,35);
    window.Init("MM","test",false,1920,1080,25,35);
    assert(fake::hooks==1 && Fast::guiCalls==1 && window.IsFrameReady());
    uint32_t w=0,h=0; int32_t x=1,y=1;
    window.SetDimensions(800,480,100,100); window.GetDimensions(&w,&h,&x,&y);
    assert(w==400 && h==240 && x==0 && y==0);
    window.GetDimensions(nullptr,nullptr,nullptr,nullptr);
    window.SetFullscreenChangedCallback(Fullscreen); window.SetFullscreen(false);
    assert(fullscreen && window.IsFullscreen());
    assert(window.GetTargetFps()==20 && BlinkyTargetFps()==20);
    for (int fps : {20,30,60,999,0,-1}) { window.SetTargetFps(fps); assert(window.GetTargetFps()==20 && BlinkyTargetFps()==20); }
    window.SetTargetFps(10); assert(window.GetTargetFps()==10 && BlinkyTargetFps()==10);
    fake::ticks=static_cast<uint64_t>(SYSCLOCK_ARM11*3);
    assert(std::abs(window.GetTime()-3.0)<1e-8);
    fake::keys=KEY_TOUCH; fake::touch={12,210}; window.HandleEvents();
    int tx=0,ty=0; assert(BlinkyTouchRead(&tx,&ty)==1 && tx==12 && ty==210);
    assert(fake::scans==1 && Fast::discoverCalls==1);
    fake::event(APTHOOK_ONSUSPEND); fake::event(APTHOOK_ONSLEEP);
    assert(released==1 && !window.IsFrameReady() && BlinkyTouchRead(&tx,&ty)==0);
    fake::event(APTHOOK_ONWAKEUP); assert(!window.IsFrameReady());
    fake::event(APTHOOK_ONRESTORE); assert(window.IsFrameReady());
    fake::keys=0; window.HandleEvents(); assert(Fast::discoverCalls==1);
    window.Close(); fake::event(APTHOOK_ONRESTORE); assert(!window.IsRunning());
    window.Destroy(); window.Destroy(); assert(fake::unhooks==1);
    window.Init("MM","test",false,400,240,0,0); assert(fake::hooks==2);
    fake::running=false; window.HandleEvents(); assert(!window.IsRunning());
    window.Destroy(); assert(fake::unhooks==2);
}
