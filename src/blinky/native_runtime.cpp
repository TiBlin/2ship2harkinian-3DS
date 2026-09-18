#include <3ds.h>
#include <ship/port/3ds/BlinkyLifecycle.h>
#include <ship/audio/BlinkyNdspAudioPlayer.h>
#include <cstdio>
#include <cstdlib>
#include <cerrno>
#include <exception>
#include <new>
#include <algorithm>
#include <atomic>
#include <sys/stat.h>
#include <unistd.h>
#include "../port3ds/archive_checks.h"

// libctru owns heap allocation. These documented weak settings select a 16 MiB
// DMA arena and give the remaining process budget to the application heap.
// No copied private allocator or syscall implementation is installed.
extern "C" {
bool BlinkyDisplayActive();
uint32_t __ctru_linear_heap_size=16u*1024*1024;
uint32_t __stacksize__=1024u*1024;
int __real___syscall_thread_create(struct __pthread_t**,void*(*)(void*),void*,void*,size_t);
int __wrap___syscall_thread_create(struct __pthread_t** thread,void*(*entry)(void*),void* arg,void* stack,size_t bytes) {
    // Resource decoding uses C++ and needs a larger stack than newlib's small
    // default. Explicit caller-owned stacks must retain their original size.
    return __real___syscall_thread_create(thread,entry,arg,stack,stack?bytes:std::max(bytes,size_t(128*1024)));
}
}
namespace {
bool ready=false;
void Fatal(const char* message) {
    std::fprintf(stderr,"Blinky fatal: %s\n",message?message:"unknown");std::fflush(stderr);
    Ship::BlinkyNdspAudioPlayer::Quiesce();
    // Fatal termination can leave graphics/resource worker threads alive.
    // newlib _Exit reaches __libctru_exit, which unmaps both heaps before it
    // stops those threads (crash 28: GSP writes to its unmapped stack).
    // Let the kernel terminate the whole process before reclaiming memory.
    // This emergency path returns to HOME; normal shutdown remains unchanged.
    svcExitProcess();
}
bool Prepare() {
    if(ready)return true;
    if((mkdir("sdmc:/3ds",0777)!=0 && errno!=EEXIST) ||
       (mkdir("sdmc:/3ds/2ship",0777)!=0 && errno!=EEXIST) || chdir("sdmc:/3ds/2ship")!=0)return false;
    if(!std::freopen("blinky.log","w",stderr))return false;
    setvbuf(stderr,nullptr,_IONBF,0);
    std::set_terminate([](){
        const char* reason="unhandled exception";
        try{if(std::current_exception())std::rethrow_exception(std::current_exception());}
        catch(const std::exception& e){reason=e.what();Fatal(reason);}catch(...){ }
        Fatal(reason);
    });
    // Preserve standard bad_alloc propagation: archive/decoder boundaries can
    // recover without publishing a failed load. Unhandled failures still reach
    // the terminate handler above.
    std::set_new_handler(nullptr);
#ifndef BLINKY_EMULATOR_SAFE
    osSetSpeedupEnable(true);
#endif
    ready=true;std::fprintf(stderr,"Blinky runtime: occlusion prototype 12 (20 FPS), libctru heap, DMA=16 MiB, main stack=1 MiB\n");return true;
}
}
extern "C" void BlinkyAbortProcess() { Fatal("native startup aborted"); }
extern "C" void TwoShip3dsShowStartupError(const char* message) {
    // libctru's gfx allocation is not refcounted. Only initialize/free graphics
    // here when the renderer does not already own the LCD buffers.
    std::fprintf(stderr,"Blinky startup: %s\n",message?message:"unknown");
    const bool ownGraphics=!BlinkyDisplayActive();
    if(ownGraphics)gfxInitDefault();
    consoleInit(GFX_BOTTOM,nullptr);
    std::printf("\x1b[2J2Ship3DS / Blinky\n\n%s\n\nSTART: exit\n",message?message:"Startup failed");
    GSPGPU_FlushDataCache(gfxGetFramebuffer(GFX_BOTTOM,GFX_LEFT,nullptr,nullptr),320*240*3);
    gfxScreenSwapBuffers(GFX_BOTTOM,false);
    while(aptMainLoop()) {hidScanInput();if(hidKeysDown()&KEY_START)break;gspWaitForVBlank();}
    if(ownGraphics)gfxExit();
}
extern "C" bool TwoShip3dsPreflightArchives() {
    if(!Prepare()){TwoShip3dsShowStartupError("Cannot write sd:/3ds/2ship\nCheck the SD card.");return false;}
    bool newModel=false;Result result=APT_CheckNew3DS(&newModel);
    if(R_SUCCEEDED(result) && !newModel){TwoShip3dsShowStartupError("New 3DS / New 2DS XL required");return false;}
    char error[256]{};
    if(!TwoShip3ds::CheckArchive(".","2ship.o2r",true,error,sizeof(error)) ||
       !TwoShip3ds::CheckArchive(".","mm.o2r",false,error,sizeof(error))) {
        TwoShip3dsShowStartupError(error);return false;
    }
    std::fprintf(stderr,"Blinky resources: mm.o2r and 2ship.o2r accepted, cwd=sdmc:/3ds/2ship\n");
    return true;
}
extern "C" bool BlinkyReadableAddress(uintptr_t address) {
    if(!address)return false;
    MemInfo memory{};PageInfo page{};
    return R_SUCCEEDED(svcQueryMemory(&memory,&page,address)) &&
        (memory.perm&MEMPERM_READ) && address>=memory.base_addr && uint64_t(address)<uint64_t(memory.base_addr)+memory.size;
}
// MM resource bridges use this diagnostic ABI even when the archive loader
// has already returned nullptr. Bound repeated errors without allocating.
extern "C" void TwoShip3dsTraceResourceFailure(const char* path,const char* stage,const char* detail) {
    static std::atomic<unsigned> failures{0};
    const unsigned count=failures.fetch_add(1,std::memory_order_relaxed);
    if(count<128 || count%1024==0)
        std::fprintf(stderr,"Blinky resource #%u: %s [%s] %s\n",count+1,
            path?path:"(null)",stage?stage:"unknown",detail?detail:"");
}
