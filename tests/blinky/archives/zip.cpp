#include "ship/resource/archive/O2rArchive.h"
#include <algorithm>
#include <atomic>
#include <cassert>
#include <cstring>
#include <iostream>
#include <limits>
#include <thread>
struct zip_source_t {FILE* file=nullptr;std::vector<char> data;};
struct zip_t {zip_source_t* source=nullptr;zip_source_t* pending=nullptr;};
struct zip_file_t {size_t position=0;};
static std::string fault;
static int sources=0,zips=0,entries=0;
static std::vector<char> payload{'B','l','i','n','k','y','!'};
zip_source_t* zip_source_filep_create(FILE* f,uint64_t,int64_t,void*){
    if(fault=="source-open")return nullptr;
    ++sources;return new zip_source_t{f,{}};
}
zip_t* zip_open_from_source(zip_source_t* s,int,void*){
    if(fault=="open")return nullptr;
    ++zips;return new zip_t{s,nullptr};
}
void zip_source_free(zip_source_t* s){assert(s && sources>0);if(s->file)std::fclose(s->file);delete s;--sources;}
void zip_discard(zip_t* z){assert(z && zips>0);if(z->source)zip_source_free(z->source);if(z->pending)zip_source_free(z->pending);delete z;--zips;}
int zip_fclose(zip_file_t* f){assert(f && entries>0);delete f;--entries;return fault=="close-entry"?-1:0;}
zip_int64_t zip_get_num_entries(zip_t*,int){return fault=="directory"?-1:2;}
const char* zip_get_name(zip_t*,uint64_t i,int){return fault=="name"?nullptr:i==0?"folder/":"asset";}
void zip_stat_init(zip_stat_t* s){*s={};}
int zip_stat(zip_t*,const char* path,int,zip_stat_t* info){
    if(fault=="stat" || std::strcmp(path,"asset")!=0)return -1;
    info->valid=fault=="no-size"?0:ZIP_STAT_SIZE;
    info->size=fault=="empty"?0:fault=="oversize"?UINT64_MAX:payload.size();return 0;
}
zip_file_t* zip_fopen(zip_t*,const char*,int){if(fault=="entry")return nullptr;++entries;return new zip_file_t;}
zip_int64_t zip_fread(zip_file_t* f,void* dest,uint64_t count){
    assert(entries==1);std::this_thread::yield();
    if(fault=="allocation")throw std::bad_alloc();
    if(fault=="read-error" && f->position)return -1;
    if(fault=="truncated" && f->position)return 0;
    if(f->position==payload.size())return fault=="crc"?-1:fault=="extra"?1:0;
    const auto bytes=std::min({size_t(count),payload.size()-f->position,size_t(3)});
    std::memcpy(dest,payload.data()+f->position,bytes);f->position+=bytes;return bytes;
}
zip_t* zip_open(const char*,int,void*){if(fault=="writer")return nullptr;++zips;return new zip_t;}
zip_source_t* zip_source_buffer(zip_t*,const void* p,uint64_t n,int){
    if(fault=="write-source")return nullptr;++sources;
    auto s=new zip_source_t;s->data.assign(static_cast<const char*>(p),static_cast<const char*>(p)+n);return s;
}
zip_int64_t zip_file_add(zip_t* z,const char*,zip_source_t* s,int){if(fault=="add")return -1;z->pending=s;return 0;}
int zip_close(zip_t* z){if(fault=="commit")return -1;if(z->pending)payload=z->pending->data;zip_discard(z);return 0;}
int main(){
    auto file=std::fopen("archive-test.o2r","wb");assert(file);std::fputc(0,file);std::fclose(file);
    int cases=0;
    {
        Ship::O2rArchive archive("archive-test.o2r");
        for(auto mode:{"source-open","open","directory","name"}){
            fault=mode;assert(!archive.Open());assert(!sources && !zips && !entries);++cases;
        }
        fault.clear();assert(archive.Open());assert(sources==1 && zips==1);assert(archive.ListFiles()->size()==1);
        auto loaded=archive.LoadFile("asset");assert(loaded && loaded->IsLoaded && *loaded->Buffer==payload);++cases;
        assert(!archive.LoadFile("missing"));assert(!archive.LoadFile(uint64_t(1)));++cases;
        for(auto mode:{"stat","no-size","empty","oversize","entry","read-error","truncated","crc","extra","close-entry","allocation"}){
            fault=mode;assert(!archive.LoadFile("asset"));assert(entries==0 && sources==1 && zips==1);++cases;
        }
        fault.clear();
        auto read=[&]{for(int i=0;i<100;++i){auto result=archive.LoadFile("asset");assert(result && *result->Buffer==payload);}};
        std::thread a(read),b(read);a.join();b.join();++cases;
        const auto previous=payload;
        for(auto mode:{"writer","write-source","add","commit"}){
            fault=mode;assert(!archive.WriteFile("asset",{1,2,3,4}));assert(payload==previous);
            assert(entries==0 && sources==1 && zips==1);++cases;
        }
        fault.clear();assert(archive.WriteFile("asset",{1,2,3,4}));
        loaded=archive.LoadFile("asset");assert(loaded && *loaded->Buffer==std::vector<char>({1,2,3,4}));++cases;
        assert(archive.Close());assert(!archive.LoadFile("asset"));assert(archive.Close());++cases;
    }
    assert(!sources && !zips && !entries);std::remove("archive-test.o2r");
    std::cout<<"PASS "<<cases<<" native ZIP cases: partial reads, CRC, failures, ownership, writes, 200 concurrent reads\n";
}
