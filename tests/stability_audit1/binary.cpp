#include <cassert>
#include <climits>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#include "ship/utils/binarytools/MemoryStream.h"
#include "ship/utils/binarytools/BinaryReader.h"
#include "fast/resource/factory/TextureFactory.h"
#include "fast/resource/type/Texture.h"
using namespace Ship;
template<class F> void rejects(F fn) { bool bad=false;try {fn();}catch(const std::exception&){bad=true;}assert(bad); }
int main(int argc,char** argv) {
    assert(argc==2);const std::string mode=argv[1];
    if(mode=="bulk-oob") {
        char only='x';MemoryStream s(&only,1);char dst[4];
        rejects([&]{s.Read(dst,4);});assert(s.GetBaseAddress()==0);
    } else if(mode=="alloc-oob") {
        char only='x';MemoryStream s(&only,1);
        rejects([&]{auto value=s.Read(4);});assert(s.GetBaseAddress()==0);
    } else if(mode=="uint32-oob") {
        char only='x';Ship::BinaryReader r(&only,1);
        rejects([&]{(void)r.ReadUInt32();});assert(r.GetBaseAddress()==0);
    } else if(mode=="empty") {
        MemoryStream s; s.Read(nullptr,0); auto value=s.Read(0); assert(s.GetBaseAddress()==0);
        s.Write(nullptr,0);assert(s.GetLength()==0);
    } else if(mode=="failed-cursor") {
        MemoryStream s;rejects([&]{s.ReadByte();});assert(s.GetBaseAddress()==0);
    } else if(mode=="null-input") {
        rejects([&]{MemoryStream s(nullptr,4);});
        rejects([&]{MemoryStream s{std::shared_ptr<std::vector<char>>{}};});
        MemoryStream s(nullptr,0);assert(s.GetLength()==0);
    } else if(mode=="write-accounting") {
        char data[]="abcd";MemoryStream s(data,4);s.Seek(2,SeekOffsetType::Start);
        s.Write(data,4);assert(s.GetLength()==6);s.Seek(0,SeekOffsetType::End);
        assert(s.GetBaseAddress()==5 && s.ReadByte()=='d');
        MemoryStream b;b.WriteByte(11);b.Seek(0,SeekOffsetType::End);assert(b.GetBaseAddress()==0 && b.ReadByte()==11);
    } else if(mode=="overflow") {
        MemoryStream s; s.Seek(-1,SeekOffsetType::Start); char c='x';
        rejects([&]{s.Write(&c,2);});assert(s.GetLength()==0);
        rejects([&]{s.Read(&c,1);});
        s.Seek(0,SeekOffsetType::Start);rejects([&]{s.Read(std::numeric_limits<size_t>::max());});
    } else if(mode=="valid-binary") {
        char data[]={1,2,3,4}; MemoryStream s(data,4);char dst[4];s.Read(dst,4);
        assert(std::memcmp(data,dst,4)==0 && s.GetBaseAddress()==4);
        Ship::BinaryReader r(data,4);r.SetEndianness(Endianness::Native);
        assert(r.ReadUInt32()==0x04030201U);
        s.Seek(-2,SeekOffsetType::Current);assert(s.ReadByte()==3);
    } else if(mode.starts_with("texture")) {
        const bool v1=mode.find("v1")!=std::string::npos;
        const bool invalid=mode.find("short")!=std::string::npos || mode.find("dimension")!=std::string::npos || mode.find("zero")!=std::string::npos;
        auto buf=std::make_shared<std::vector<char>>();
        auto u32=[&](uint32_t x){for(int i=0;i<4;++i)buf->push_back(char(x>>(8*i)));};
        u32(6);u32(mode.find("dimension")!=std::string::npos?65536:32);u32(32);
        if(v1){u32(0);u32(0x3f800000);u32(0x3f800000);}
        u32(mode.find("zero")!=std::string::npos?0:1024);
        const size_t offset=buf->size();
        buf->resize(buf->size()+(mode.find("short")!=std::string::npos?7:1024),'X');
        auto file=std::make_shared<File>();file->Buffer=buf;
        auto reader=std::make_shared<Ship::BinaryReader>(std::make_shared<MemoryStream>(buf));
        reader->SetEndianness(Endianness::Native);file->Reader=reader;
        auto init=std::make_shared<ResourceInitData>();init->Format=RESOURCE_FORMAT_BINARY;init->Path="audit/texture";
        auto load=[&](){
            std::shared_ptr<IResource> value;
            if(v1){Fast::ResourceFactoryBinaryTextureV1 f;value=f.ReadResource(file,init);}
            else{Fast::ResourceFactoryBinaryTextureV0 f;value=f.ReadResource(file,init);}
            return std::static_pointer_cast<Fast::Texture>(value);
        };
        if(invalid)rejects([&]{auto tex=load();});
        else {auto tex=load();assert(tex && tex->Width==32 && tex->Height==32 && tex->ImageDataSize==1024);
            assert(tex->mImageBuffer==buf && tex->ImageData==reinterpret_cast<uint8_t*>(buf->data()+offset));
            file.reset();reader.reset();buf.reset();assert(tex->ImageData[1023]=='X');}
    } else return 2;
    std::cout<<"PASS "<<mode<<"\n";
}
