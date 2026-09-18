#pragma once
// Host-only NDSP double: pointer-sized u32 for the address-taking syscall.
// Wave sample counts/status fields remain fixed width. No ARM ABI/cache emulation.
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <mutex>
#include <vector>
using u32=uintptr_t;using u16=uint16_t;using Result=int32_t;
#define CUR_PROCESS_HANDLE 1
#define R_FAILED(x) ((x)<0)
constexpr int NDSP_WBUF_FREE=0,NDSP_WBUF_QUEUED=1,NDSP_WBUF_PLAYING=2,NDSP_WBUF_DONE=3;
constexpr int NDSP_OUTPUT_STEREO=0,NDSP_INTERP_LINEAR=1,NDSP_FORMAT_STEREO_PCM16=2;
struct ndspWaveBuf { void* data_vaddr=nullptr; uint32_t nsamples=0; uint16_t sequence_id=0; int status=0; bool looping=false; };
struct LightLock { std::mutex mutex; };
namespace fake {
inline bool initialized=false;inline int initResult=0,flushResult=0,flushes=0,adds=0,afterExit=0;
inline int allocs=0,frees=0,failAlloc=-1;inline size_t lastBytes=0;inline u16 seq=0;inline u32 pos=0;
inline float rate=0;inline std::function<void()> beforeLock;inline std::vector<ndspWaveBuf*> waves;
inline void check(){if(!initialized)++afterExit;}
}
inline void LightLock_Init(LightLock*){}
inline void LightLock_Lock(LightLock* l){if(fake::beforeLock){auto fn=std::move(fake::beforeLock);fake::beforeLock=nullptr;fn();}l->mutex.lock();}
inline void LightLock_Unlock(LightLock* l){l->mutex.unlock();}
inline Result ndspInit(){if(fake::initResult)return fake::initResult;fake::initialized=true;return 0;}
inline void ndspExit(){fake::initialized=false;}
inline void* linearAlloc(size_t n){if(fake::allocs==fake::failAlloc)return nullptr;++fake::allocs;return std::malloc(n);}
inline void linearFree(void* p){++fake::frees;std::free(p);}
inline void ndspSetOutputMode(int){fake::check();}
inline void ndspChnReset(int){fake::check();}
inline void ndspChnWaveBufClear(int){fake::check();fake::waves.clear();}
inline void ndspChnSetInterp(int,int){fake::check();}
inline void ndspChnSetRate(int,float f){fake::check();fake::rate=f;}
inline void ndspChnSetFormat(int,int){fake::check();}
inline void ndspChnSetMix(int,float*){fake::check();}
inline void ndspChnSetPaused(int,bool){fake::check();}
inline u16 ndspChnGetWaveBufSeq(int){fake::check();return fake::seq;}
inline u32 ndspChnGetSamplePos(int){fake::check();return fake::pos;}
inline Result svcFlushProcessDataCache(int,u32,size_t n){fake::check();++fake::flushes;fake::lastBytes=n;return fake::flushResult;}
inline void ndspChnWaveBufAdd(int,ndspWaveBuf* wave){fake::check();++fake::adds;wave->status=NDSP_WBUF_QUEUED;fake::waves.push_back(wave);}
