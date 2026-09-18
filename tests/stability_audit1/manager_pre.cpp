#include <algorithm>
#include <array>
#include <atomic>
#include <barrier>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <functional>
#include <iostream>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <unordered_map>
#include <variant>
#define SPDLOG_TRACE(...) ((void)0)
#define SPDLOG_ERROR(...) ((void)0)
#define __3DS__ 1
extern "C" void TwoShip3dsTraceResourceFailure(const char*,const char*,const char*) {}
namespace Ship {
inline std::function<void()> reportPoint;
struct ResourceInitData {};
struct IResource {
    inline static const std::string gAltAssetPrefix="alt/";
    bool dirty=false;
    std::function<void()> onDestroy;
    bool IsDirty(){return dirty;}
    virtual ~IResource(){if(onDestroy)onDestroy();}
};
struct File {};
struct Archive {
    bool hasFile=true;
    bool HasFile(const std::string& path){return !path.ends_with(".meta") && hasFile;}
};
struct ResourceIdentifier {
    std::string Path;
    uintptr_t Owner=0;
    std::shared_ptr<Archive> Parent;
    bool operator==(const ResourceIdentifier& other) const {return Path==other.Path && Owner==other.Owner && Parent==other.Parent;}
};
struct Hash {size_t operator()(const ResourceIdentifier& id)const{return std::hash<std::string>{}(id.Path);}};
struct ResourceLoader {
    std::barrier<>* ready=nullptr;
    bool fail=false;
    std::shared_ptr<IResource> LoadResource(const std::string&,std::shared_ptr<File>,std::shared_ptr<ResourceInitData>){
        if(ready)ready->arrive_and_wait();return fail?nullptr:std::make_shared<IResource>();
    }
};
class ResourceManager {
public:
    enum class ResourceLoadError{NotCached,NotFound};
    using Line=std::variant<ResourceLoadError,std::shared_ptr<IResource>>;
    std::unordered_map<ResourceIdentifier,Line,Hash> mResourceCache;
    std::mutex mMutex;
    std::shared_ptr<Archive> mArchiveManager=std::make_shared<Archive>();
    std::shared_ptr<ResourceLoader> loader=std::make_shared<ResourceLoader>();
    bool mAltAssetsEnabled=false;
    bool readFailure=false;
    std::barrier<>* snapshotGate=nullptr;
    std::shared_ptr<File> LoadFileProcess(const std::string&){return readFailure?nullptr:std::make_shared<File>();}
    std::shared_ptr<File> LoadFileProcess(const ResourceIdentifier& id){return LoadFileProcess(id.Path);}
    std::shared_ptr<ResourceLoader> GetResourceLoader(){return loader;}
    bool OtrSignatureCheck(const char* p){return std::strncmp(p,"__OTR__",7)==0;}
    Line CheckCache(const ResourceIdentifier& id,bool) {
        std::lock_guard<std::mutex> lock(mMutex);auto it=mResourceCache.find(id);
        return it==mResourceCache.end()?Line(ResourceLoadError::NotCached):it->second;
    }
    std::shared_ptr<IResource> GetCachedResource(Line line){
        auto p=std::get_if<std::shared_ptr<IResource>>(&line);return p && *p && !(*p)->IsDirty()?*p:nullptr;
    }
    std::shared_ptr<IResource> GetCachedResource(const ResourceIdentifier& id,bool exact){
        auto result=GetCachedResource(CheckCache(id,exact));
        if(snapshotGate)snapshotGate->arrive_and_wait();return result;
    }
    std::shared_ptr<IResource> LoadResourceProcess(const ResourceIdentifier&,bool,std::shared_ptr<ResourceInitData>);
#ifdef AUDIT_FIXED
    std::shared_ptr<IResource> PublishResourceLoad(const ResourceIdentifier&,std::shared_ptr<IResource>,bool);
#endif
    void Soh3dsCacheReport(char*,unsigned);
};
