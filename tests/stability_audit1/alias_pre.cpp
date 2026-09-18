#include <cassert>
#include <cstdint>
#include <iostream>
#include <memory>
#include <string>
#include <vector>
namespace Ship {
struct File{int marker=0;};
struct ResourceInitData{std::string Path="target";};
static bool malformed=false,missing=false;static int targetReads=0;
struct ArchiveManager{
    std::shared_ptr<std::vector<int>> GetArchives(){return std::make_shared<std::vector<int>>(1);}
    std::shared_ptr<std::vector<std::string>> ListFiles(const char*){auto r=std::make_shared<std::vector<std::string>>();if(!missing)r->push_back("source.meta");return r;}
    int GetFilePriority(const std::string&){return 0;}
};
struct ResourceManager{
    ArchiveManager* GetArchiveManager(){static ArchiveManager a;return &a;}
    std::shared_ptr<File> LoadFileProcess(const std::string& path){if(missing && path=="source.meta")return nullptr;auto f=std::make_shared<File>();if(path=="target"){f->marker=99;++targetReads;}return f;}
};
struct Context{static Context* GetRawInstance(){static Context c;return &c;}ResourceManager* GetResourceManager(){static ResourceManager r;return &r;}};
struct ResourceLoader{
    std::shared_ptr<ResourceInitData> ReadResourceInitData(const std::string&,std::shared_ptr<File>){return malformed?nullptr:std::make_shared<ResourceInitData>();}
    std::shared_ptr<ResourceInitData> ResolveMetaAlias(const std::string&,std::shared_ptr<File>&);
};
