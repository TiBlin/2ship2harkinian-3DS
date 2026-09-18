#!/usr/bin/env python3
"""Exercise the production scene eviction boundary with owned fake resources."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "third_party/2ship/mm/2s2h/z_play_2SH.cpp"


def function(source, signature):
    begin = source.index(signature)
    end = source.index("{", begin) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[begin:end]


def main():
    source = SOURCE.read_text(encoding="utf-8")
    begin = source.index("// Blinky scene residency:")
    end = source.index("\n#endif", begin)
    production = source[begin:end]
    skeleton_source = (ROOT / "third_party/2ship/mm/2s2h/resource/type/Skeleton.cpp").read_text(encoding="utf-8")
    registry_production = "\n".join(function(skeleton_source, signature) for signature in (
        "void SkeletonPatcher::RegisterSkeleton(", "void SkeletonPatcher::UnregisterSkeleton(",
    ))
    # Check the real call sites as well as executing the production functions.
    spawn = source[source.index('extern "C" void OTRPlay_SpawnScene'):]
    assert spawn.index("TwoShip3dsPurgeDepartingScene(") < spawn.index("play->sceneSegment = OTRPlay_LoadFile")
    destroy = (ROOT / "third_party/2ship/mm/src/code/z_play.c").read_text(encoding="utf-8")
    destroy = destroy[destroy.index("void Play_Destroy("):destroy.index("#define PLAY_COMPRESS_BITS")]
    assert destroy.index("TwoShip3dsRecordDepartingObjects(ids, count)") < destroy.index("Effect_DestroyAll(this)")
    assert "this->objectCtx.numEntries" in destroy and "ARRAY_COUNT(this->objectCtx.slots)" in destroy
    assert "UnloadResource" not in destroy
    harness = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <iterator>
#include <map>
#include <memory>
#include <set>
#include <string>
#include <vector>
using s16 = int16_t;
using s32 = int32_t;
struct PlayState { void* sceneSegment = nullptr; };
struct SkelAnime {};
struct mallinfo { int uordblks; };
struct mallinfo mallinfo() { return {0}; }
static int enabled = 1;
int CVarGetInteger(const char*, int) { return enabled; }
static bool checkDestruction = true;
static std::set<const uint8_t*> invalidated;
static std::vector<std::string> events;
void Gfx_TextureCacheDelete(const uint8_t* address) { invalidated.insert(address); }
namespace Ship {
struct IResource {
    static inline const std::string gAltAssetPrefix = "alt/";
    std::string name;
    uint8_t bytes[16]{};
    explicit IResource(std::string n) : name(std::move(n)) {}
    virtual ~IResource() {
        if (checkDestruction) assert(invalidated.contains(bytes));
        events.push_back("destroy:" + name);
    }
    void* GetRawPointer() { return bytes; }
};
struct ArchiveManager {
    std::set<std::string> files;
    auto ListFiles(const std::string& mask) {
        auto result = std::make_shared<std::vector<std::string>>();
        const auto prefix = mask.substr(0, mask.size()-1);
        for (const auto& file : files) if (file.starts_with(prefix)) result->push_back(file);
        return result;
    }
};
struct ResourceManager {
    std::shared_ptr<ArchiveManager> archive = std::make_shared<ArchiveManager>();
    std::map<std::string, std::shared_ptr<IResource>> cache;
    auto GetArchiveManager() { return archive; }
    std::shared_ptr<IResource> GetCachedResource(const std::string& path) {
        const auto it = cache.find(path);
        return it == cache.end() ? nullptr : it->second;
    }
    void UnloadResources(const std::string& pattern) {
        events.push_back("unload:" + pattern);
        auto files = archive->ListFiles(pattern);
        for (const auto& file : *files) {
            cache.erase(file);
            if (file.ends_with(".meta")) cache.erase(file.substr(0, file.size()-5));
        }
    }
};
struct Context {
    std::shared_ptr<ResourceManager> manager = std::make_shared<ResourceManager>();
    static Context* GetRawInstance() { static Context instance; return &instance; }
    auto GetResourceManager() { return manager; }
};
}
namespace SOH {
struct SkeletonPatchInfo { SkelAnime* skelAnime; std::string vanillaSkeletonPath; };
struct SkeletonPatcher {
    static inline std::vector<SkeletonPatchInfo> skeletons;
    static void RegisterSkeleton(std::string& path, SkelAnime* skelAnime);
    static void UnregisterSkeleton(SkelAnime* skelAnime);
};
''' + registry_production + r'''
}
''' + production + r'''
int main() {
    auto manager = Ship::Context::GetRawInstance()->GetResourceManager();
    auto add = [&](const std::string& cacheName, const std::string& archiveName = "") {
        auto resource = std::make_shared<Ship::IResource>(cacheName);
        manager->cache[cacheName] = resource;
        manager->archive->files.insert(archiveName.empty() ? cacheName : archiveName);
        return std::weak_ptr<Ship::IResource>(resource);
    };
    auto scene = add("scenes/nonmq/A/scene");
    auto background = add("scenes/nonmq/A/background");
    auto alias = add("scenes/nonmq/A/alias", "scenes/nonmq/A/alias.meta");
    auto alt = add("alt/scenes/nonmq/A/texture");
    auto object = add("objects/object_nb/texture");
    auto objectAlias = add("objects/object_nb/alias", "objects/object_nb/alias.meta");
    auto altObject = add("alt/objects/object_nb/texture");
    auto keep = add("objects/gameplay_keep/texture");
    auto player = add("objects/object_link_boy/texture");
    auto other = add("objects/object_crow/texture");
    auto audio = add("audio/sample");
    auto pinned = add("objects/object_okuta/texture");
    auto external = pinned.lock();
    // Raw SkelAnime pointers do not increase shared_ptr::use_count.
    auto persistentSkeleton = add("objects/object_bubble/skeleton");
    auto persistentTexture = add("objects/object_bubble/texture");
    auto persistentAlt = add("alt/objects/object_bubble/texture");
    auto kafeiBackup = add("objects/object_test3/skeleton");
    SkelAnime persistentSkelAnime, neighboringSkelAnime;
    std::string persistentPath = "__OTR__alt/objects/object_bubble/skeleton";
    std::string neighborPath = "objects/object_nb_extra/skeleton";
    SOH::SkeletonPatcher::RegisterSkeleton(persistentPath, &persistentSkelAnime);
    SOH::SkeletonPatcher::RegisterSkeleton(neighborPath, &neighboringSkelAnime);
    assert(SOH::SkeletonPatcher::skeletons[0].vanillaSkeletonPath == "objects/object_bubble/skeleton");
    assert(TwoShip3dsHasPersistentObjectPointers("object_bubble"));
    assert(!TwoShip3dsHasPersistentObjectPointers("object_nb")); // Match a directory, not a partial name.
    assert(TwoShip3dsHasPersistentObjectPointers("object_test3")); // Global backup has no registry entry.
    auto newScene = add("scenes/nonmq/B/scene");
    PlayState fresh;
    TwoShip3dsPurgeDepartingScene(&fresh, "scenes/nonmq/A/*");
    assert(events.empty() && !scene.expired()); // First load cannot evict.
    const s16 ids[] = {4, 4, 5, 1, 0x10, 0x0E, 0x1C, -1, 0, 0x7fff};
    TwoShip3dsRecordDepartingObjects(ids, std::size(ids));
    assert(sTwoShip3dsDepartingObjectCount == 6); // Deduplicated, valid IDs only.
    TwoShip3dsPurgeDepartingScene(&fresh, "scenes/nonmq/A/*");
    assert(events.empty()); // Same-scene restart retains resources.
    TwoShip3dsRecordDepartingObjects(ids, std::size(ids));
    PlayState live{reinterpret_cast<void*>(1)};
    TwoShip3dsPurgeDepartingScene(&live, "scenes/nonmq/B/*");
    assert(events.empty() && sTwoShip3dsPreviousSceneDir == "scenes/nonmq/A/*");
    TwoShip3dsPurgeDepartingScene(&fresh, "scenes/nonmq/B/*");
    assert(scene.expired() && background.expired() && alias.expired() && alt.expired());
    assert(object.expired() && objectAlias.expired() && altObject.expired());
    assert(!keep.expired() && !player.expired() && !other.expired() && !audio.expired());
    assert(!pinned.expired() && !newScene.expired());
    assert(manager->cache.contains("objects/object_okuta/texture")); // Whole pinned dir remains cached.
    assert(!persistentSkeleton.expired() && !persistentTexture.expired() && !persistentAlt.expired());
    assert(!kafeiBackup.expired());
    assert(!invalidated.contains(static_cast<const uint8_t*>(persistentTexture.lock()->GetRawPointer())));
    assert(!invalidated.contains(static_cast<const uint8_t*>(persistentAlt.lock()->GetRawPointer())));
    assert(sTwoShip3dsDepartingObjectCount == 0 && !sTwoShip3dsDepartingPlayRecorded);
    const auto firstObjectUnload = std::find(events.begin(), events.end(), "unload:objects/object_nb/*");
    const auto firstSceneDestroy = std::find(events.begin(), events.end(), "destroy:scenes/nonmq/A/scene");
    assert(firstSceneDestroy < firstObjectUnload); // Scene dependencies released first.
    const auto before = events.size();
    TwoShip3dsPurgeDepartingScene(&fresh, "scenes/nonmq/C/*");
    assert(events.size() == before); // No recorded Play_Destroy: no eviction.
    enabled = 0;
    TwoShip3dsRecordDepartingObjects(ids, std::size(ids));
    TwoShip3dsPurgeDepartingScene(&fresh, "scenes/nonmq/D/*");
    assert(events.size() == before);
    // Once its last SkelAnime is unregistered, the model is reclaimable.
    SOH::SkeletonPatcher::UnregisterSkeleton(&persistentSkelAnime);
    assert(!TwoShip3dsHasPersistentObjectPointers("object_bubble"));
    assert(TwoShip3dsHasPersistentObjectPointers("object_test3"));
    enabled = 1;
    const s16 laterIds[] = {0x0E, 0x1C};
    TwoShip3dsRecordDepartingObjects(laterIds, std::size(laterIds));
    TwoShip3dsPurgeDepartingScene(&fresh, "scenes/nonmq/E/*");
    assert(persistentSkeleton.expired() && persistentTexture.expired() && persistentAlt.expired());
    assert(!kafeiBackup.expired());
    TwoShip3dsRecordDepartingObjects(nullptr, -1);
    assert(sTwoShip3dsDepartingObjectCount == 0);
    checkDestruction = false;
    std::puts("PASS: production scene boundary, GPU-before-free, aliases, pins, keeps, live skeleton registry, Kafei backup");
}
'''
    compiler = os.environ.get("CXX") or shutil.which("g++") or shutil.which("clang++")
    if not compiler:
        raise SystemExit("Set CXX to a native C++20 compiler.")
    with tempfile.TemporaryDirectory(prefix="2ship-scene-eviction-") as directory:
        source_path = Path(directory) / "scene_eviction.cpp"
        binary = Path(directory) / ("scene_eviction.exe" if os.name == "nt" else "scene_eviction")
        source_path.write_text(harness, encoding="utf-8")
        subprocess.run([compiler, "-std=c++20", "-O2", "-I", str(ROOT / "third_party/2ship/mm/include"),
                        str(source_path), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
