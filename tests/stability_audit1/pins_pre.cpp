#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <memory>
#include <string>
#include <unordered_map>
#include <vector>
#define __3DS__ 1
struct Vtx{uint8_t data[16];};struct Gfx{uint8_t* pointer;};
#define gsDPPipeSync() Gfx{nullptr}
#define gsDPLoadMultiBlock(texture, ...) Gfx{reinterpret_cast<uint8_t*>(texture)}
#define gsSPEndDisplayList() Gfx{nullptr}
#define gsSPVertex(v, ...) Gfx{reinterpret_cast<uint8_t*>(v)}
#define gsSP2Triangles(...) Gfx{nullptr}
#define gsSP1Triangle(...) Gfx{nullptr}
#define gsSPDisplayList(dl) Gfx{reinterpret_cast<uint8_t*>(dl)}
const char* gGiFierceDeityMaskHairAndHatDL="item";Vtx southClockTownRampVtx[5]{};
static Gfx* published=nullptr;static bool enabled=true;static bool absent=false;static bool tiny=false;
int CVarGetInteger(const char*,int){return enabled;}
namespace Ship {
struct IResource{std::vector<uint8_t> data;IResource(size_t n):data(n,77){}void* GetRawPointer(){return data.data();}size_t GetPointerSize(){return data.size();}};
struct ResourceManager {
    std::unordered_map<std::string,std::shared_ptr<IResource>> cache;
    std::shared_ptr<IResource> LoadResource(const char* path){
        if(absent)return nullptr;
        auto& p=cache[path];if(!p)p=std::make_shared<IResource>(tiny?1:2048);return p;
    }
};
struct Context {ResourceManager manager;static Context* GetRawInstance(){static Context c;return &c;}ResourceManager* GetResourceManager(){return &manager;}};
}
char* ResourceMgr_LoadTexOrDListByName(const char* path){return static_cast<char*>(Ship::Context::GetRawInstance()->manager.LoadResource(path)->GetRawPointer());}
char* ResourceMgr_LoadVtxArrayByName(const char* path){return ResourceMgr_LoadTexOrDListByName(path);}
void ResourceMgr_PatchGfxByName(const char*,const char*,int,Gfx inst){published=reinterpret_cast<Gfx*>(inst.pointer);}
void ResourceMgr_UnpatchGfxByName(const char*,const char*){published=nullptr;}
