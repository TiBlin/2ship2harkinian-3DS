#include "input_core.h"
#include <ship/port/3ds/BlinkyVisibility.h>
#include <ship/port/3ds/BlinkyInput.h>
#include <ship/port/3ds/BlinkyLifecycle.h>
#include <ship/audio/BlinkyNdspAudioPlayer.h>
#include <libultraship/bridge/consolevariablebridge.h>
#include <3ds.h>
#include <array>
#include <cstdio>

namespace {
Ship::Blinky3DS::Pad state;
bool menu=false,displayReady=false,initialized=false,infrared=false;
unsigned selection=0;
uint64_t lastFrame=0,lastTick=0;
uint64_t lastDraws=0,lastTriangles=0,lastCpu=0,lastUploads=0;
float measuredFps=0;
// Native HID masks and N64 masks are public API constants. These are new
// defaults; old SDL mapping profiles are deliberately not interpreted here.
struct Binding {uint32_t key,button;const char* name;};
constexpr Binding bindings[]={
    {KEY_A,0x8000,"A"},{KEY_B,0x4000,"B"},{KEY_X,0x0008,"X"},{KEY_Y,0x0002,"Y"},
    {KEY_L,0x0020,"L"},{KEY_R,0x0010,"R"},{KEY_ZL,0x2000,"ZL"},{KEY_ZR,0x0001,"ZR"},
    {KEY_DUP,0x0800,"Up"},{KEY_DDOWN,0x0400,"Down"},{KEY_DLEFT,0x0200,"Left"},{KEY_DRIGHT,0x0100,"Right"},
    {KEY_START,0x1000,"Start"}};
constexpr uint32_t choices[]={0,0x8000,0x4000,0x2000,0x1000,0x20,0x10,8,4,2,1,0x0800,0x0400,0x0200,0x0100};
constexpr const char* names[]={"None","A","B","Z","Start","L","R","C up","C down","C left","C right","D up","D down","D left","D right"};
std::array<uint32_t,std::size(bindings)> mappings;
int stickDeadzone=15,cstickDeadzone=25;
void MappingKey(char (&buffer)[64],size_t index){std::snprintf(buffer,sizeof(buffer),"gBlinky.Input.%s",bindings[index].name);}
void LoadMappings() {
    for(size_t i=0;i<mappings.size();++i){char key[64];MappingKey(key,i);mappings[i]=CVarGetInteger(key,bindings[i].button);}
    stickDeadzone=std::clamp<int>(CVarGetInteger("gBlinky.Input.Deadzone",15),0,120);
    cstickDeadzone=std::clamp<int>(CVarGetInteger("gBlinky.Input.CStickDeadzone",25),0,120);
}
void Change(int direction) {
    if(selection==0)return; // The native presentation cap is fixed at 20 FPS.
    else if(selection==1)CVarSetInteger("gTextureFilter",(CVarGetInteger("gTextureFilter",1)+3+direction)%3);
    else if(selection==2){stickDeadzone=std::clamp(stickDeadzone+direction*5,0,120);CVarSetInteger("gBlinky.Input.Deadzone",stickDeadzone);}
    else if(selection==3){cstickDeadzone=std::clamp(cstickDeadzone+direction*5,0,120);CVarSetInteger("gBlinky.Input.CStickDeadzone",cstickDeadzone);}
    else {
        size_t i=selection-4,choice=0;
        for(size_t n=0;n<std::size(choices);++n)if(choices[n]==mappings[i])choice=n;
        choice=(choice+std::size(choices)+direction)%std::size(choices);mappings[i]=choices[choice];
        char key[64];MappingKey(key,i);CVarSetInteger(key,mappings[i]);
    }
    CVarSave();
}
}
namespace Ship::Blinky3DS {
void ReleaseInput(){state={};}
Pad ReadInput(){return GetLifecycleSnapshot().pauseReasons?Pad{}:state;}
void PollInput() {
    if(!initialized){LoadMappings();infrared=R_SUCCEEDED(irrstInit());initialized=true;}
    if(infrared)irrstScanInput();
    const uint32_t down=hidKeysDown(),held=hidKeysHeld()|(infrared?irrstKeysHeld():0);
    if(down&KEY_SELECT)menu=!menu;
    if(down&KEY_TOUCH){touchPosition touch{};hidTouchRead(&touch);if(touch.py<26)menu=!menu;}
    state={};
    if(menu) {
        if(down&KEY_DUP)selection=(selection+3+mappings.size())%(4+mappings.size());
        if(down&KEY_DDOWN)selection=(selection+1)%(4+mappings.size());
        if(down&KEY_DLEFT)Change(-1);
        if(down&(KEY_DRIGHT|KEY_A))Change(1);
        if(down&KEY_B)menu=false;
        return;
    }
    for(size_t i=0;i<mappings.size();++i)if(held&bindings[i].key)state.buttons|=mappings[i];
    circlePosition circle{},cstick{};hidCircleRead(&circle);if(infrared)hidCstickRead(&cstick);
    state.x=Blinky::Axis(circle.dx,stickDeadzone);state.y=Blinky::Axis(circle.dy,stickDeadzone);Blinky::LimitStick(state.x,state.y);
    state.cx=Blinky::Axis(cstick.dx,cstickDeadzone);state.cy=Blinky::Axis(cstick.dy,cstickDeadzone);Blinky::LimitStick(state.cx,state.cy);
    // Touch four explicit C-button areas. Coordinates belong to the bottom LCD.
    if(held&KEY_TOUCH){touchPosition touch{};hidTouchRead(&touch);if(touch.py>=176){constexpr uint32_t actions[]={2,8,4,1};unsigned column=std::min(3u,unsigned(touch.px)/80);state.buttons|=actions[column];}}
}
}
extern "C" void BlinkyDisplayReady(bool ready) {
    displayReady=ready;
    if(ready){
        consoleInit(GFX_BOTTOM,nullptr);gfxSetDoubleBuffering(GFX_BOTTOM,false);
        lastFrame=lastTick=lastDraws=lastTriangles=lastCpu=lastUploads=0;measuredFps=0;
    }
    else if(infrared){irrstExit();infrared=false;initialized=false;}
}
extern "C" bool BlinkyDisplayActive(){return displayReady;}
extern "C" int BlinkyPreferredTextureFilter(){return std::clamp<int>(CVarGetInteger("gTextureFilter",1),0,2);}
extern "C" void BlinkyPresentDiagnostics(uint64_t frames,uint64_t draws,uint64_t triangles,uint64_t cpu,uint64_t uploads) {
    if(!displayReady)return;
    uint64_t tick=svcGetSystemTick();
    if(lastTick && tick>lastTick)measuredFps=float((frames-lastFrame)*double(SYSCLOCK_ARM11)/(tick-lastTick));
    const double interval=frames>lastFrame?double(frames-lastFrame):1;
#if BLINKY_RENDER_STATS
    const double drawsPerFrame=gBlinkyRenderStats.gpuDraws;
    const double cpuPerFrame=gBlinkyRenderStats.cpuTriangles;
    const double gpuPerFrame=gBlinkyRenderStats.gpuTriangles;
#else
    const double drawsPerFrame=(draws-lastDraws)/interval;
    const double cpuPerFrame=(cpu-lastCpu)/interval;
    const double gpuPerFrame=(triangles-lastTriangles)/interval-cpuPerFrame;
#endif
    const double uploadsPerFrame=(uploads-lastUploads)/interval;
    lastFrame=frames;lastTick=tick;
    lastDraws=draws;lastTriangles=triangles;lastCpu=cpu;lastUploads=uploads;
    std::printf("\x1b[H\x1b[2J2Ship3DS - Blinky 12 Citro3D\nSELECT / touch title: settings\n\n");
    if(menu) {
        const char* filter[]={"3 point (CPU)","Linear","Nearest"};
        std::printf("%c Presentation: 20 FPS (fixed)\n",selection==0?'>':' ');
        std::printf("%c Filter: %s\n",selection==1?'>':' ',filter[std::clamp<int>(CVarGetInteger("gTextureFilter",1),0,2)]);
        std::printf("%c Circle deadzone: %d\n%c C-stick deadzone: %d\n",selection==2?'>':' ',stickDeadzone,selection==3?'>':' ',cstickDeadzone);
        for(size_t i=0;i<mappings.size();++i){const char* action="Custom";for(size_t c=0;c<std::size(choices);++c)if(choices[c]==mappings[i])action=names[c];std::printf("%c %-5s : %s\n",selection==i+4?'>':' ',bindings[i].name,action);}
        std::printf("\nD-pad: select/change  A: change\nB/SELECT: return to game\n");
    } else {
        auto life=Ship::Blinky3DS::GetLifecycleSnapshot();
        auto audio=Ship::BlinkyNdspAudioPlayer::GetActiveDiagnostics();
        std::printf("%.1f FPS   %.1f ms\nFrames: %llu\nDraws/frame: %.1f\nGPU tris/frame: %.1f\nCPU tris/frame: %.1f\nUploads/frame: %.1f\nLinear free: %lu KiB\nHOME/lid pauses: %lu / %lu\n\n",
            measuredFps,measuredFps>0?1000/measuredFps:0,(unsigned long long)frames,drawsPerFrame,
            gpuPerFrame,cpuPerFrame,uploadsPerFrame,(unsigned long)(linearSpaceFree()/1024),
            (unsigned long)life.pauses,(unsigned long)life.lidSleeps);
#if BLINKY_RENDER_STATS
        const auto& visibility=gBlinkyRenderStats;
        std::printf("Occ %s: %u tests / %u rejected\nSaved: %u tris / %u LUS calls\nOcc CPU: %.2f ms  GPU calls: %u\n",
            BLINKY_OCCLUSION_CULLING?"ON":"OFF",unsigned(visibility.tested),unsigned(visibility.rejected),
            unsigned(visibility.avoidedTriangles),unsigned(visibility.rejected),double(visibility.occlusionTicks)*1000/SYSCLOCK_ARM11,unsigned(visibility.gpuDraws));
#endif
        std::printf("Audio: %lu Hz, %lu queued\nEmpty queues: %llu  errors: %ld\n\nTouch C buttons below:\x1b[24;1H LEFT     UP     DOWN    RIGHT\n",
            (unsigned long)audio.sampleRate,(unsigned long)audio.queuedFrames,(unsigned long long)audio.underruns,(long)audio.lastError);
    }
    GSPGPU_FlushDataCache(gfxGetFramebuffer(GFX_BOTTOM,GFX_LEFT,nullptr,nullptr),320*240*3);
}
