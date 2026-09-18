#pragma once
#include <cstdint>
#include <cstdio>
#include <memory>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>
using zip_int64_t = int64_t;
using zip_uint64_t = uint64_t;
struct zip_t;
struct zip_file_t;
struct zip_source_t;
struct zip_stat_t { uint64_t size=0, valid=0; };
constexpr int ZIP_RDONLY=1, ZIP_CREATE=2, ZIP_FL_OVERWRITE=4, ZIP_FL_ENC_UTF_8=8, ZIP_STAT_SIZE=1;
zip_source_t* zip_source_filep_create(FILE*,uint64_t,int64_t,void*);
zip_t* zip_open_from_source(zip_source_t*,int,void*);
void zip_source_free(zip_source_t*);
void zip_discard(zip_t*);
int zip_fclose(zip_file_t*);
zip_int64_t zip_get_num_entries(zip_t*,int);
const char* zip_get_name(zip_t*,uint64_t,int);
void zip_stat_init(zip_stat_t*);
int zip_stat(zip_t*,const char*,int,zip_stat_t*);
zip_file_t* zip_fopen(zip_t*,const char*,int);
zip_int64_t zip_fread(zip_file_t*,void*,uint64_t);
zip_t* zip_open(const char*,int,void*);
zip_source_t* zip_source_buffer(zip_t*,const void*,uint64_t,int);
zip_int64_t zip_file_add(zip_t*,const char*,zip_source_t*,int);
int zip_close(zip_t*);
namespace Ship {
struct File { std::shared_ptr<std::vector<char>> Buffer; bool IsLoaded=false; };
class Archive {
    std::string path;
    std::shared_ptr<std::unordered_map<uint64_t,std::string>> files=std::make_shared<std::unordered_map<uint64_t,std::string>>();
public:
    explicit Archive(const std::string& p):path(p){}
    virtual ~Archive()=default;
    const std::string& GetPath() const { return path; }
    auto ListFiles(){ return files; }
    void IndexFile(const std::string& p){ (*files)[std::hash<std::string>{}(p)]=p; }
};
class O2rArchive : virtual public Archive {
    struct NativeZip;
    std::unique_ptr<NativeZip> mNative;
public:
    O2rArchive(const std::string&);
    ~O2rArchive();
    bool Open(); bool Close();
    bool WriteFile(const std::string&,const std::vector<uint8_t>&);
    std::shared_ptr<File> LoadFile(uint64_t);
    std::shared_ptr<File> LoadFile(const std::string&);
};
}
