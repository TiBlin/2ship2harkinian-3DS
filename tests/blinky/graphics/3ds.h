#pragma once
#include <cstdint>
#include <cstdlib>
#include <cassert>
#include <cstring>
using u8=uint8_t;using u16=uint16_t;using u32=uint32_t;using Result=int;
#define R_FAILED(x) ((x)<0)
constexpr uint64_t SYSCLOCK_ARM11=268123480;
enum {GFX_TOP,GFX_BOTTOM,GFX_LEFT,GFX_RIGHT};
inline uint64_t svcGetSystemTick(){static uint64_t value=0;return value+=SYSCLOCK_ARM11/30;}
inline void svcSleepThread(int64_t){}
inline void gfxInitDefault(){}
inline bool fakeStereo=false;
inline void gfxSet3D(bool value){fakeStereo=value;}
inline bool gfxIs3D(){return fakeStereo;}
inline void gfxExit(){}
inline void* linearAlloc(size_t size){return std::calloc(1,size);}
inline void linearFree(void* data){std::free(data);}
inline size_t linearSpaceFree(){return 16*1024*1024;}
inline Result GSPGPU_FlushDataCache(const void*,size_t){return 0;}
inline Result GSPGPU_InvalidateDataCache(const void*,size_t){return 0;}
struct DVLE_s{};struct DVLB_s{DVLE_s DVLE[1];};struct shaderProgram_s{};
inline DVLB_s* DVLB_ParseFile(u32*,unsigned){return new DVLB_s;}
inline void DVLB_Free(DVLB_s* p){delete p;}
inline void shaderProgramInit(shaderProgram_s*){}
inline void shaderProgramSetVsh(shaderProgram_s*,DVLE_s*){}
inline void shaderProgramFree(shaderProgram_s*){}
