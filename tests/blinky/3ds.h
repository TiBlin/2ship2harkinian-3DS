#pragma once
// Host collaborators only: never on the ARM include path. No hardware claims.
#include <cstdint>
#include <cstdlib>
#include <cassert>
#include <vector>
#include <algorithm>
using u32 = uintptr_t; // syscall address argument must hold a host pointer
using u16 = uint16_t;
using Result = int32_t;
#define R_FAILED(r) ((r) < 0)
constexpr int CUR_PROCESS_HANDLE = 1;
constexpr double SYSCLOCK_ARM11 = 268123480.0;
constexpr uint32_t KEY_TOUCH = 1u << 20;
enum APT_HookType { APTHOOK_ONSUSPEND, APTHOOK_ONRESTORE, APTHOOK_ONSLEEP, APTHOOK_ONWAKEUP, APTHOOK_ONEXIT };
struct aptHookCookie { void (*callback)(APT_HookType, void*) = nullptr; void* param = nullptr; };
struct touchPosition { uint16_t px = 0, py = 0; };
enum { NDSP_WBUF_FREE, NDSP_WBUF_QUEUED, NDSP_WBUF_PLAYING, NDSP_WBUF_DONE };
enum { NDSP_OUTPUT_STEREO, NDSP_FORMAT_STEREO_PCM16, NDSP_INTERP_LINEAR };
struct ndspWaveBuf {
    const void* data_vaddr = nullptr;
    uint32_t nsamples = 0;
    bool looping = false;
    uint8_t status = NDSP_WBUF_FREE;
    uint16_t sequence_id = 0;
};
namespace fake {
inline std::vector<aptHookCookie*> registeredHooks;
inline int hooks = 0, unhooks = 0, scans = 0;
inline bool running = true;
inline uint32_t keys = 0;
inline uint64_t ticks = 0;
inline touchPosition touch{};
inline bool dsp = false, paused = false, failAllocation = false;
inline int initResult = 0, failFlushAt = -1, flushes = 0, adds = 0, badCalls = 0;
inline int allocations = 0, frees = 0;
inline uint16_t playing = 0, nextSequence = 1;
inline uint32_t position = 0;
inline float rate = 0;
inline std::vector<ndspWaveBuf*> waves;
inline void check() { if (!dsp) ++badCalls; }
inline void event(APT_HookType e) {
    // Observable APT contract: the most recently installed hook runs first.
    // Unlike libctru, this host collaborator does not copy linked-list cookies.
    auto listeners = registeredHooks;
    for (auto i = listeners.rbegin(); i != listeners.rend(); ++i)
        (*i)->callback(e, (*i)->param);
}
}
inline void aptHook(aptHookCookie* c, void (*f)(APT_HookType, void*), void* p) {
    assert(std::find(fake::registeredHooks.begin(),fake::registeredHooks.end(),c)==fake::registeredHooks.end());
    c->callback=f; c->param=p; fake::registeredHooks.push_back(c); ++fake::hooks;
}
inline void aptUnhook(aptHookCookie* c) {
    auto i=std::find(fake::registeredHooks.begin(),fake::registeredHooks.end(),c);
    assert(i!=fake::registeredHooks.end()); fake::registeredHooks.erase(i); ++fake::unhooks;
}
inline bool aptMainLoop() { return fake::running; }
inline void hidScanInput() { ++fake::scans; }
inline uint32_t hidKeysHeld() { return fake::keys; }
inline void hidTouchRead(touchPosition* p) { *p=fake::touch; }
inline uint64_t svcGetSystemTick() { return fake::ticks; }
inline void* linearAlloc(size_t n) { if (fake::failAllocation) return nullptr; ++fake::allocations; return std::malloc(n); }
inline void linearFree(void* p) { assert(!fake::dsp); ++fake::frees; std::free(p); }
inline Result ndspInit() { if (fake::initResult) return fake::initResult; fake::dsp=true; return 0; }
inline void ndspExit() { fake::check(); fake::dsp=false; }
inline void ndspChnReset(int) { fake::check(); }
inline void ndspSetOutputMode(int) { fake::check(); }
inline void ndspChnSetFormat(int, int) { fake::check(); }
inline void ndspChnSetRate(int, float rate) { fake::check(); fake::rate=rate; }
inline void ndspChnSetInterp(int, int) { fake::check(); }
inline void ndspChnSetMix(int, float* gains) { fake::check(); assert(gains[0]==1 && gains[1]==1); }
inline void ndspChnSetPaused(int, bool paused) { fake::check(); fake::paused=paused; }
inline void ndspChnWaveBufClear(int) { fake::check(); fake::waves.clear(); }
inline uint16_t ndspChnGetWaveBufSeq(int) { fake::check(); return fake::playing; }
inline uint32_t ndspChnGetSamplePos(int) { fake::check(); return fake::position; }
inline Result svcFlushProcessDataCache(int, u32, size_t) { fake::check(); return ++fake::flushes==fake::failFlushAt ? -42 : 0; }
inline void ndspChnWaveBufAdd(int, ndspWaveBuf* wave) {
    fake::check(); assert(wave->nsamples > 0 && wave->nsamples<=1024);
    wave->status=NDSP_WBUF_QUEUED; wave->sequence_id=fake::nextSequence++;
    fake::waves.push_back(wave); ++fake::adds;
}
