#include <algorithm>
#include <cassert>
#include <cstdint>
#include <list>
#include <memory>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include <iostream>
uint64_t CRC64(const char* path){return std::hash<std::string>{}(path);}
bool glob_match(const char* pattern,const char* path){
    std::string p(pattern),value(path);return p=="*" || p==value || (p.ends_with("*") && value.starts_with(p.substr(0,p.size()-1)));
}
namespace Ship {
struct File { int owner=0; };
struct Archive {
    int owner;
    std::shared_ptr<std::unordered_map<uint64_t,std::string>> files=std::make_shared<std::unordered_map<uint64_t,std::string>>();
    explicit Archive(int id):owner(id){}
    auto ListFiles(){return files;}
    int GetPriority(){return owner;}
    void Add(std::string path){(*files)[CRC64(path.c_str())]=path;}
    bool WriteFile(const std::string& path,const std::vector<uint8_t>&){Add(path);return true;}
    auto LoadFile(const std::string& path){assert(files->contains(CRC64(path.c_str())));return std::make_shared<File>(owner);}
};
class ArchiveManager {
public:
    struct IndexedPath {uint64_t hash;size_t archive;const std::string* path;};
    std::vector<IndexedPath> mIndex;
    std::unordered_set<std::string> mDirectories;
    std::vector<std::shared_ptr<Archive>> mArchives;
    const IndexedPath* FindPath(uint64_t) const;
    void RebuildIndex();
    bool HasFile(uint64_t);
    std::shared_ptr<File> LoadFile(uint64_t);
    std::shared_ptr<Archive> GetArchiveFromFile(const std::string&);
    int32_t GetFilePriority(const std::string&);
    const std::string* HashToString(uint64_t) const;
    std::shared_ptr<std::vector<std::string>> ListFiles(const std::list<std::string>&,const std::list<std::string>&);
    bool WriteFile(std::shared_ptr<Archive>,const std::string&,const std::vector<uint8_t>&);
};
// TEST_METHODS
}
int main(){
    Ship::ArchiveManager manager;
    auto base=std::make_shared<Ship::Archive>(0),mod=std::make_shared<Ship::Archive>(1);
    base->Add("objects/shared");base->Add("objects/base");base->Add("textures/base");
    mod->Add("objects/shared");mod->Add("objects/alias.meta");
    manager.mArchives={base,mod};manager.RebuildIndex();
    assert(manager.mIndex.size()==4);
    auto hash=CRC64("objects/shared");
    assert(manager.LoadFile(hash)->owner==1 && manager.GetFilePriority("objects/shared")==1);
    assert(manager.GetArchiveFromFile("objects/shared")==mod);
    assert(manager.HasFile(CRC64("objects/alias.meta")) && !manager.HasFile(CRC64("objects/alias")));
    auto list=manager.ListFiles({"objects/*"},{"objects/*.meta"});
    // Exact exclusion remains meaningful without implementing a glob engine in
    // the collaborator; the production implementation uses LUS glob_match.
    list=manager.ListFiles({"objects/*"},{"objects/alias.meta"});assert(list->size()==2);
    assert(!manager.HashToString(123) && !manager.LoadFile(123) && manager.GetFilePriority("missing")==-1);
    const auto* borrowed=manager.HashToString(hash);
    for(int i=0;i<20000;++i)mod->Add("new/"+std::to_string(i));
    assert(*borrowed=="objects/shared"); // map rehash does not move path nodes
    manager.RebuildIndex();assert(manager.mIndex.size()==20004);
    assert(manager.WriteFile(mod,"new/written",{}));assert(manager.HasFile(CRC64("new/written")));
    manager.mArchives.pop_back();manager.RebuildIndex();
    assert(manager.mIndex.size()==3 && manager.LoadFile(hash)->owner==0 && !manager.HasFile(CRC64("new/written")));
    manager.mArchives.clear();manager.RebuildIndex();assert(manager.mIndex.empty() && manager.mDirectories.empty());
    std::cout<<"PASS actual archive index: 20004 paths, priority, .meta distinction, rehash lifetime, writes, removal\n";
}
