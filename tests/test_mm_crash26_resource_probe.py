#!/usr/bin/env python3
"""Execute native resource/heap/message contracts extracted from production code.

The six native and three desktop segment probes use explicit resource doubles.
Memory cases exercise pinned ownership, payload spans, allocation arithmetic,
zero initialization and both partial heap-allocation failure orders. This test
does not emulate ARM/GPU/SD behavior and does not require sanitizers.
"""
from pathlib import Path
import argparse, os, shutil, subprocess, tempfile
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
parser.add_argument("--cxx", default=os.environ.get("CXX", "g++"))
args = parser.parse_args()
root = args.root.resolve()
cxx = shutil.which(args.cxx)
if not cxx:
    raise SystemExit("Set CXX or --cxx to a host C++20 compiler.")

def body(text, signature):
    start = text.index(signature)
    i = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[i] == "{") - (text[i] == "}")
        i += 1
    return text[start:i]

source = (root / "third_party/2ship/mm/2s2h/Enhancements/GfxPatcher/AuthenticGfxPatches.cpp").read_text(encoding="utf-8")
pin = body(source, "static void* BlinkyPinPatchResource(")
source = (root / "third_party/2ship/mm/2s2h/z_message_OTR.cpp").read_text(encoding="utf-8")
messages = body(source, "static void BlinkyCheckMessageStorage(") + "\n" + body(source, "static void* BlinkyAllocateMessageEntries(")
source = (root / "third_party/2ship/mm/src/buffers/heaps.c").read_text(encoding="utf-8")
heaps = body(source, "static void BlinkyAllocateGameHeaps(")

code = r'''
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <limits>
#include <cstdio>
namespace Ship {
struct IResource { unsigned char bytes[64]{}; size_t span = 64; size_t GetPointerSize(){return span;} void* GetRawPointer(){return bytes;} };
struct ResourceManager { std::shared_ptr<IResource> resource; unsigned loads = 0;
    auto LoadResource(const char*) { ++loads; return resource; }
};
struct Context { std::shared_ptr<ResourceManager> manager = std::make_shared<ResourceManager>();
    static Context* GetRawInstance(){static Context instance; return &instance;}
    auto GetResourceManager(){return manager;}
};
}
''' + pin + r'''
unsigned errors = 0;
void TwoShip3dsShowStartupError(const char*) {++errors;}
struct AllocationFailure {};
unsigned aborts = 0;
extern "C" [[noreturn]] void BlinkyAbortProcess() { ++aborts; throw AllocationFailure{}; }
''' + messages + r'''
using u8 = uint8_t;
u8* gAudioHeap = nullptr;
u8* gSystemHeap = nullptr;
struct { size_t heapSize; } gAudioHeapInitSizes{1234};
constexpr size_t SYSTEM_HEAP_SIZE = 5678;
unsigned heapCalls = 0, failCall = 0, frees = 0;
void* testMemalign(size_t alignment, size_t size) {
    assert(alignment == 16);
    ++heapCalls;
    assert(size == (heapCalls == 1 ? 1234 : 5678));
    return heapCalls == failCall ? nullptr : std::malloc(size);
}
void testFree(void* p) {if(p) ++frees; std::free(p);}
#define memalign testMemalign
#define free testFree
''' + heaps + r'''
#undef memalign
#undef free
int main() {
    auto manager = Ship::Context::GetRawInstance()->GetResourceManager();
    std::shared_ptr<Ship::IResource> owner;
    assert(BlinkyPinPatchResource(owner, "missing", 16) == nullptr);
    assert(!owner);
    manager->resource = std::make_shared<Ship::IResource>();
    assert(BlinkyPinPatchResource(owner, "valid", 65) == nullptr);
    assert(owner && manager->loads == 2);
    void* bytes = BlinkyPinPatchResource(owner, "valid", 64);
    assert(bytes != nullptr && manager->loads == 2);
    auto weak = std::weak_ptr<Ship::IResource>(owner);
    manager->resource.reset();
    assert(!weak.expired() && BlinkyPinPatchResource(owner, "valid", 32) == bytes);
    owner.reset(); assert(weak.expired());
    auto* entries = static_cast<unsigned char*>(BlinkyAllocateMessageEntries(8, 16));
    for (size_t i=0;i<128;++i) assert(entries[i] == 0);
    std::free(entries);
    try { BlinkyAllocateMessageEntries(std::numeric_limits<size_t>::max(), 2); assert(false); }
    catch (const AllocationFailure&) {}
    try { BlinkyAllocateMessageEntries(8, 0); assert(false); }
    catch (const AllocationFailure&) {}
    for (unsigned fail : {1u,2u,0u}) {
        failCall = fail; heapCalls = frees = 0;
        try { BlinkyAllocateGameHeaps(); assert(fail == 0); }
        catch (const AllocationFailure&) {assert(fail != 0);}
        assert(heapCalls == 2);
        if (fail) { assert(!gAudioHeap && !gSystemHeap && frees == 1); }
        else { assert(gAudioHeap && gSystemHeap); std::free(gAudioHeap); std::free(gSystemHeap); }
    }
    assert(errors == 4 && aborts == 4);
    std::puts("PASS: static payload lifetime/span; message zero-init/overflow; heap transaction success and both failure orders; fatal bridge");
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
ben = (root / "third_party/2ship/mm/2s2h/BenPort.cpp").read_text(encoding="utf-8")
stubs = (root / "third_party/2ship/mm/src/code/stubs.c").read_text(encoding="utf-8")
probe_code = PRE + body(ben, 'extern "C" char* ResourceMgr_LoadIfDListByName(') + body(stubs, "void gSPSegment(") + POST
log = []
with tempfile.TemporaryDirectory(prefix="mm-contracts-") as td:
    td = Path(td)
    for name, contents, defines, cases in [
        ("memory", code, [], [None]),
        ("native-probe", probe_code, ["-D__3DS__"], ["missing","metadata","texture","displaylist","empty","raw"]),
        ("desktop-probe", probe_code, [], ["texture","displaylist","raw"]),
    ]:
        cpp, exe = td / (name + ".cpp"), td / (name + ".exe")
        cpp.write_text(contents, encoding="utf-8")
        subprocess.run([cxx, "-std=c++20", "-O1", *defines, str(cpp), "-o", str(exe)], check=True)
        for case in cases:
            result = subprocess.run([str(exe)] + ([case] if case else []), capture_output=True, text=True, check=True)
            log.append(result.stdout)
            print(result.stdout.strip(), flush=True)
