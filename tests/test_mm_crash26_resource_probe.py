#!/usr/bin/env python3
"""Host regressions for the real ResourceMgr_LoadIfDListByName/gSPSegment bodies.

Explicit doubles provide IResource, the resource cache and graphics emission.
The logger body is extracted unchanged; open/write/fsync/close are mocked.
This does NOT exercise the complete resource importer, ARM ABI or real SD I/O.
Requires a host C++17 compiler with UndefinedBehaviorSanitizer (GCC/Clang).
"""
from pathlib import Path
import argparse, os, shutil, subprocess, tempfile

BASELINE = r'''
extern "C" char* ResourceMgr_LoadIfDListByName(const char* filePath) {
    auto res = GetResourceByName(filePath);
    if (res->GetInitData()->Type == static_cast<uint32_t>(Fast::ResourceType::DisplayList))
        return (char*)&((std::static_pointer_cast<Fast::DisplayList>(res))->Instructions[0]);
    return nullptr;
}
'''
PRE = r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <memory>
#include <vector>
#include <string>
#include <iostream>
namespace Ship {
struct ResourceInitData { uint32_t Type; };
struct IResource {
    std::shared_ptr<ResourceInitData> init;
    std::shared_ptr<ResourceInitData> GetInitData() { return init; }
    virtual ~IResource() = default;
};
}
namespace Fast {
enum class ResourceType : uint32_t { DisplayList = 0x4f444c54 };
struct DisplayList : Ship::IResource { std::vector<uint64_t> Instructions; };
}
static std::shared_ptr<Ship::IResource> resource;
static unsigned loads=0, traces=0;
std::shared_ptr<Ship::IResource> GetResourceByName(const char*) { ++loads; return resource; }
extern "C" void TwoShip3dsTraceResourceFailure(const char*,const char*,const char*) { ++traces; }
static constexpr const char* target="__OTR__objects/object_cs/object_cs_Tex_00EE20";
int ResourceMgr_OTRSigCheck(char* p) { return p && std::strncmp(p,"__OTR__",7)==0; }
struct Command { int segment; uintptr_t target; };
void __gSPSegment(void* p, int seg, uintptr_t data) { *static_cast<Command*>(p)={seg,data}; }
'''
POST = r'''
int main(int argc, char** argv) {
    assert(argc==2); const std::string mode=argv[1];
    Command cmd{};
    if (mode=="missing") {
        gSPSegment(&cmd,9,reinterpret_cast<uintptr_t>(target));
        assert(loads==1 && traces==1 && cmd.segment==9);
        assert(cmd.target==reinterpret_cast<uintptr_t>(target));
    } else if (mode=="metadata") {
        resource=std::make_shared<Ship::IResource>();
        gSPSegment(&cmd,9,reinterpret_cast<uintptr_t>(target));
        assert(loads==1 && traces==1 && cmd.target==reinterpret_cast<uintptr_t>(target));
    } else if (mode=="texture") {
        resource=std::make_shared<Ship::IResource>();
        resource->init=std::make_shared<Ship::ResourceInitData>(Ship::ResourceInitData{0x4f544558});
        gSPSegment(&cmd,9,reinterpret_cast<uintptr_t>(target));
        assert(loads==1 && traces==0 && cmd.target==reinterpret_cast<uintptr_t>(target));
    } else if (mode=="displaylist" || mode=="empty") {
        auto list=std::make_shared<Fast::DisplayList>(); resource=list;
        list->init=std::make_shared<Ship::ResourceInitData>(Ship::ResourceInitData{0x4f444c54});
        if(mode=="displaylist") list->Instructions.push_back(0xdf00000000000000ULL);
        gSPSegment(&cmd,9,reinterpret_cast<uintptr_t>(target));
        assert(loads==1 && cmd.segment==9);
        if(mode=="displaylist") assert(traces==0 && cmd.target==reinterpret_cast<uintptr_t>(list->Instructions.data()));
        else assert(traces==1 && cmd.target==reinterpret_cast<uintptr_t>(target));
    } else if (mode=="raw") {
        static char raw[]="not-an-OTR-path";
        gSPSegment(&cmd,7,reinterpret_cast<uintptr_t>(raw));
        assert(loads==0 && traces==0 && cmd.segment==7 && cmd.target==reinterpret_cast<uintptr_t>(raw));
    } else return 2;
    std::cout<<"PASS "<<mode<<"\n";
}
'''
LOG_PRE = r'''
#include <algorithm>
#include <atomic>
#include <cassert>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <malloc.h>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include <iostream>
#include <unistd.h>
static std::mutex lock;
static unsigned opens=0,writes=0,flushes=0,closes=0,newpaths=0,oldpaths=0;
static std::string mode,output;
int testOpen(const char* p,int,int) {
    std::lock_guard<std::mutex> g(lock);++opens;
    if(std::strstr(p,"crash26"))++newpaths;else ++oldpaths;
    return 123;
}
ssize_t testWrite(int,const void* p,size_t n) {
    std::lock_guard<std::mutex> g(lock); ++writes;
    if(mode=="eintr") {errno=EINTR; return -1;}
    if(mode=="short") n=std::max(size_t(1),n/2);
    output.append(static_cast<const char*>(p),n); errno=EIO;
    return static_cast<ssize_t>(n);
}
int testFsync(int) {std::lock_guard<std::mutex> g(lock);++flushes;return 0;}
int testClose(int) {std::lock_guard<std::mutex> g(lock);++closes;return 0;}
#define open testOpen
#define write testWrite
#define fsync testFsync
#define close testClose
'''
LOG_POST = r'''
#undef open
#undef write
#undef fsync
#undef close
int main(int argc,char** argv) {
    assert(argc==2);mode=argv[1];
    const char* p="objects/object_cs/object_cs_Tex_00EE20";
    const char* old="icon_item_vtx_static/gItemNamePanelDL";
    auto emit=[&]{TwoShip3dsTraceResourceFailure(p,"factory-read","test-double");};
    if(mode=="filter") {
        TwoShip3dsTraceResourceFailure(nullptr,"x","x");
        TwoShip3dsTraceResourceFailure("other/resource","x","x");assert(opens==0);
        emit();TwoShip3dsTraceResourceFailure("__OTR__objects/object_cs/object_cs_Tex_00EE20","x","x");
        TwoShip3dsTraceResourceFailure(old,"x","x");assert(newpaths==2 && oldpaths==1);
    } else if(mode=="limit") {
        for(int i=0;i<200;++i){emit();TwoShip3dsTraceResourceFailure(old,"x","x");}
        assert(opens==32 && newpaths==16 && oldpaths==16 && closes==32);
    } else if(mode=="parallel") {
        std::vector<std::thread> threads;
        for(int i=0;i<64;++i)threads.emplace_back(emit);
        for(auto& t:threads)t.join();assert(opens==16 && writes==16 && closes==16);
    } else if(mode=="errno" || mode=="eintr" || mode=="short") {
        errno=ERANGE;emit();assert(errno==ERANGE && opens==1 && closes==1 && flushes==1);
        if(mode=="eintr")assert(writes==5);
        else {assert(output.find("stage=factory-read")!=std::string::npos);assert(output.find("test-double")!=std::string::npos);}
        if(mode=="short")assert(writes>1);
    } else if(mode=="disabled") {
        emit();TwoShip3dsTraceResourceFailure(old,"x","x");assert(newpaths==0 && oldpaths==1);
    } else return 2;
    std::cout<<"PASS logger "<<mode<<"\n";
}
'''

def extract(text, signature):
    start=text.index(signature); brace=text.index('{',start); depth=1; end=brace+1
    while depth:
        if end>=len(text):raise ValueError('Unterminated function '+signature)
        if text[end]=='{':depth+=1
        elif text[end]=='}':depth-=1
        end+=1
    return text[start:end]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('root',nargs='?',type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument('--cxx',default=os.environ.get('CXX','g++'))
    args=ap.parse_args(); root=args.root.resolve(); cxx=shutil.which(args.cxx)
    if not cxx:raise SystemExit('Host compiler not found: '+args.cxx)
    ben=(root/'third_party/2ship/mm/2s2h/BenPort.cpp').read_text()
    stubs=(root/'third_party/2ship/mm/src/code/stubs.c').read_text()
    loader=(root/'third_party/libultraship/src/ship/resource/ResourceLoader.cpp').read_text()
    manager=(root/'third_party/libultraship/src/ship/resource/ResourceManager.cpp').read_text()
    body=extract(ben,'extern "C" char* ResourceMgr_LoadIfDListByName(')
    seg=extract(stubs,'void gSPSegment(')
    log=extract(loader,'extern "C" void TwoShip3dsTraceResourceFailure(')
    tests=0
    with tempfile.TemporaryDirectory(prefix='crash26-test-') as tmp:
        tmp=Path(tmp)
        def compile(name,source,defines=()):
            cpp=tmp/(name+'.cpp'); exe=tmp/name;cpp.write_text(source)
            command=[cxx,'-std=c++17','-O0','-g','-pthread','-fsanitize=undefined','-fno-sanitize-recover=all','-Wno-deprecated-declarations',*['-D'+d for d in defines],str(cpp),'-o',str(exe)]
            res=subprocess.run(command,capture_output=True,text=True,timeout=45)
            if res.returncode:raise RuntimeError(res.stdout+res.stderr)
            return exe
        def run(exe,case):
            nonlocal tests
            res=subprocess.run([str(exe),case],capture_output=True,text=True,timeout=15)
            if res.returncode:raise RuntimeError(f'{exe.name} {case}:\n{res.stdout}{res.stderr}')
            print(res.stdout.strip());tests+=1
        old=compile('historical',PRE+BASELINE+seg+POST,['__3DS__'])
        negative=subprocess.run([str(old),'missing'],capture_output=True,text=True,timeout=15)
        assert negative.returncode!=0 and 'null pointer' in negative.stderr,negative.stderr
        print('PASS historical negative control (UBSan rejects the original null member call)')
        print(negative.stderr.strip().replace(str(tmp),'HOST_TEST'))
        tests+=1
        fixed=compile('fixed',PRE+body+seg+POST,['__3DS__'])
        for case in ['missing','metadata','texture','displaylist','empty','raw']:run(fixed,case)
        desktop=compile('non3ds',PRE+body+seg+POST)
        for case in ['texture','displaylist','raw']:run(desktop,case)
        trace=compile('trace',LOG_PRE+log+LOG_POST,['__3DS__'])
        for case in ['filter','limit','parallel','errno','eintr','short']:run(trace,case)
        disabled=compile('disabled',LOG_PRE+log+LOG_POST,['__3DS__','TWOSHIP3DS_DISABLE_CRASH26_TRACE'])
        run(disabled,'disabled')
    assert '"archive-load-exception", e.what()' in manager
    assert '"archive-load-null", "file-null; no-meta-alias"' in manager
    print('PASS source integration: archive failure paths instrumented'); tests+=1
    print(f'{tests} checks passed. Host doubles only; no ARM build or hardware verification.')

if __name__=='__main__':main()
