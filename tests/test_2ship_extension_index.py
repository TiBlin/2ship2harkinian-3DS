#!/usr/bin/env python3
"""Exercise production extension lookup and archive-snapshot owner lifetimes.

The snapshot factory is extracted from production ArchiveManager.cpp. The test
quarantines its storage separately from the owner exposed to the scanner, so an
expired owner is reported deterministically without dereferencing freed memory.
An in-memory mutation reintroduces the 07/08 temporary-owner regression and must
fail specifically at that lifetime check; no historical source fixture is used.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "third_party/2ship/mm/2s2h/BenPort.cpp"
ARCHIVE_MANAGER = ROOT / "third_party/libultraship/src/ship/resource/archive/ArchiveManager.cpp"


def function(source, signature):
    start = source.index(signature)
    end = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def main():
    source = SOURCE.read_text(encoding="utf-8")
    start = source.index("// Extension lookup storage:")
    storage = source[start:source.index("\nstatic struct {", start)]
    production = storage + "\n" + "\n".join(function(source, signature) for signature in (
        'extern "C" void OTRExtScanner()',
        'static void ResourceMgr_PreloadAltWhenItExists(',
        'extern "C" uint8_t ResourceMgr_FileExists(',
    ))
    snapshot_factory = function(ARCHIVE_MANAGER.read_text(encoding="utf-8"),
                               "std::shared_ptr<std::vector<std::shared_ptr<Archive>>> "
                               "ArchiveManager::GetArchives()")
    snapshot_factory = snapshot_factory.replace("ArchiveManager::GetArchives()",
                                                "ArchiveManager::BuildArchiveSnapshot()", 1)
    owner = "    const auto archives = index->GetArchives();\n"
    iteration = "for (const auto& archive : *archives)"
    if production.count(owner) != 1 or production.count(iteration) != 1:
        raise SystemExit("Update the lifetime regression mutation for the current scanner.")
    expired_owner = production.replace(owner, "", 1).replace(
        iteration, "for (const auto& archive : *index->GetArchives())", 1)
    harness = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <memory>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
namespace Ship {
struct Archive;
using ArchiveList = std::vector<std::shared_ptr<Archive>>;
static std::weak_ptr<ArchiveList> scannerSnapshot;
static size_t checkedFileLists = 0;
struct ExpiredSnapshot : std::runtime_error {
    ExpiredSnapshot() : std::runtime_error("snapshot owner expired before Archive::ListFiles") {}
};
struct Archive {
    std::shared_ptr<std::unordered_map<uint64_t, std::string>> files =
        std::make_shared<std::unordered_map<uint64_t, std::string>>();
    auto ListFiles() {
        // The snapshot storage remains quarantined, so reaching this guard never
        // requires dereferencing freed vector entries or an expired Archive.
        if (scannerSnapshot.expired()) throw ExpiredSnapshot();
        ++checkedFileLists;
        return files;
    }
};
struct ArchiveManager {
    ArchiveList mArchives;
    std::vector<std::shared_ptr<ArchiveList>> quarantine;
    size_t snapshots = 0;
    std::shared_ptr<ArchiveList> BuildArchiveSnapshot();
    auto GetArchives() {
        // BuildArchiveSnapshot is the real production GetArchives body below.
        auto snapshot = BuildArchiveSnapshot();
        assert(snapshot.use_count() == 1);
        quarantine.push_back(snapshot);
        // This independent control block has exactly the ownership lifetime
        // exposed to production callers. Its no-op deleter is safe only because
        // quarantine retains the underlying allocation until after the scan.
        auto exposed = std::shared_ptr<ArchiveList>(snapshot.get(), [](ArchiveList*) {});
        scannerSnapshot = exposed;
        ++snapshots;
        return exposed;
    }
    const std::string* HashToString(uint64_t hash) {
        for (auto it = mArchives.rbegin(); it != mArchives.rend(); ++it) {
            if (!*it) continue;
            const auto found = (*it)->files->find(hash);
            if (found != (*it)->files->end()) return &found->second;
        }
        return nullptr;
    }
    bool HasFile(const std::string& path) {
        for (const auto& archive : mArchives) {
            if (!archive) continue;
            for (const auto& [hash, name] : *archive->files) {
                if (name == path && HashToString(hash) == &name) return true;
            }
        }
        return false;
    }
    // No manager ListFiles: the production scan must not copy the complete list.
};
''' + snapshot_factory + r'''
struct ResourceManager {
    std::shared_ptr<ArchiveManager> manager = std::make_shared<ArchiveManager>();
    std::vector<std::string> loaded;
    auto GetArchiveManager() { return manager; }
    void LoadResource(const std::string& path, bool exact) {
        assert(exact); loaded.push_back(path);
    }
};
struct Context {
    std::shared_ptr<ResourceManager> resources = std::make_shared<ResourceManager>();
    static Context* GetRawInstance() { static Context context; return &context; }
    auto GetResourceManager() { return resources; }
};
struct IResource { static inline const std::string gAltAssetPrefix = "alt/"; };
}
static bool alternate = false;
bool ResourceMgr_IsAltAssetsEnabled() { return alternate; }
'''
    cases = r'''
static void Scan() {
    auto manager = Ship::Context::GetRawInstance()->GetResourceManager()->GetArchiveManager();
    assert(manager->quarantine.empty());
    const size_t snapshots = manager->snapshots;
    try {
        OTRExtScanner();
    } catch (...) {
        manager->quarantine.clear();
        throw;
    }
    assert(manager->snapshots == snapshots + 1);
    assert(Ship::scannerSnapshot.expired()); // No leaked scanner owner after return.
    manager->quarantine.clear();
}

static void RunCases() {
    auto resources = Ship::Context::GetRawInstance()->GetResourceManager();
    auto manager = resources->GetArchiveManager();
    auto vanilla = std::make_shared<Ship::Archive>();
    auto mods = std::make_shared<Ship::Archive>();
    // Verify the actual production factory creates fresh, independently owned
    // snapshots and preserves null entries, order, and pre-change membership.
    manager->mArchives = {vanilla, nullptr, mods};
    {
        auto first = manager->BuildArchiveSnapshot();
        auto second = manager->BuildArchiveSnapshot();
        assert(first.get() != second.get());
        assert(first.use_count() == 1 && second.use_count() == 1);
        assert(*first == manager->mArchives && *second == manager->mArchives);
        manager->mArchives.clear();
        assert(first->size() == 3 && second->size() == 3);
    }
    Scan();
    assert(ExtensionAliases.empty());
    assert(!ResourceMgr_FileExists("objects/gMissing"));
    manager->mArchives = {nullptr, nullptr};
    Scan();
    Scan();
    assert(ExtensionAliases.empty());
    assert(Ship::checkedFileLists == 0);
    manager->mArchives = {vanilla, nullptr, mods};
    for (uint64_t i=0; i<50496; ++i)
        (*vanilla->files)[1000+i] = "objects/object_test/gResource" + std::to_string(i);
    (*vanilla->files)[1] = "objects/gLink";
    (*vanilla->files)[2] = "textures/gIcon";
    Scan();
    assert(ExtensionAliases.empty()); // 50k vanilla paths consume no extra index.
    assert(ResourceMgr_FileExists("objects/gLink"));
    assert(ResourceMgr_FileExists("__OTR__objects/gLink"));
    assert(ResourceMgr_FileExists("objects/object_test/gResource50495"));
    assert(!ResourceMgr_FileExists("objects/gMissing"));
    (*mods->files)[20] = "alt/objects/gLink.png";
    (*mods->files)[21] = "audio/my.sample.wav";
    (*mods->files)[22] = "audio/my.sample.ogg"; // Same base is stored once.
    (*mods->files)[23] = "windows\\asset.png";
    (*mods->files)[24] = "windows\\extensionless";
    (*mods->files)[25] = "alt/textures/gIcon";
    (*vanilla->files)[30] = "shadowed/old.png";
    (*mods->files)[30] = "shadowed/new.png"; // Highest archive priority wins.
    Scan();
    assert(ExtensionAliases.size() == 5);
    assert(ResourceMgr_FileExists("alt/objects/gLink"));
    assert(ResourceMgr_FileExists("__OTR__alt/objects/gLink"));
    assert(ResourceMgr_FileExists("alt/objects/gLink.png"));
    assert(ResourceMgr_FileExists("audio/my.sample"));
    assert(ResourceMgr_FileExists("windows/asset"));
    assert(ResourceMgr_FileExists("windows/extensionless"));
    assert(!ResourceMgr_FileExists("shadowed/old"));
    assert(ResourceMgr_FileExists("shadowed/new"));
    ResourceMgr_PreloadAltWhenItExists("__OTR__objects/gLink");
    assert(resources->loaded.empty());
    alternate = true;
    ResourceMgr_PreloadAltWhenItExists("__OTR__objects/gLink");
    ResourceMgr_PreloadAltWhenItExists("textures/gIcon");
    ResourceMgr_PreloadAltWhenItExists("objects/gMissing");
    assert(resources->loaded == std::vector<std::string>({"alt/objects/gLink", "alt/textures/gIcon"}));
    Scan(); // Repeated scans preserve aliases and archive priority.
    assert(ExtensionAliases.size() == 5);
    manager->mArchives.pop_back();
    Scan();
    assert(ExtensionAliases.size() == 1);
    assert(!ResourceMgr_FileExists("audio/my.sample")); // Removed mods do not leave stale aliases.
    assert(ResourceMgr_FileExists("shadowed/old"));
    assert(ResourceMgr_FileExists("__OTR__objects/gLink"));
    manager->mArchives.clear();
    Scan();
    assert(ExtensionAliases.empty());
    assert(!ResourceMgr_FileExists("shadowed/old"));
    manager->mArchives = {nullptr};
    Scan();
    assert(ExtensionAliases.empty());
    assert(manager->snapshots == 9);
    assert(Ship::checkedFileLists == 7);
    std::puts("PASS: production GetArchives snapshots, owner lifetimes, empty/null/repeated scans, "
              "50,496 generated resources, aliases, priority, prefixes, alt preloads");
}

int main() {
    try {
        RunCases();
    } catch (const Ship::ExpiredSnapshot& error) {
        std::fprintf(stderr, "%s\n", error.what());
        return 86;
    }
}
'''
    compiler = shutil.which(os.environ.get("CXX", "g++"))
    if not compiler:
        raise SystemExit("A host C++ compiler is required (set CXX).")
    with tempfile.TemporaryDirectory(prefix="2ship-extension-index-", dir=ROOT.parent) as directory:
        directory = Path(directory)
        for name, scanner in (("production", production), ("expired_owner", expired_owner)):
            cpp = directory / f"extension_index_{name}.cpp"
            executable = directory / f"extension_index_{name}.exe"
            cpp.write_text(harness + scanner + cases, encoding="utf-8")
            subprocess.run([compiler, "-std=c++20", "-D__3DS__", "-Wall", "-Wextra", "-Werror",
                            str(cpp), "-o", str(executable)], check=True)
            result = subprocess.run([str(executable)], text=True, capture_output=True)
            if name == "production":
                if result.returncode:
                    raise SystemExit(f"Production scanner failed ({result.returncode}):\n"
                                     + result.stdout + result.stderr)
                print(result.stdout, end="", flush=True)
            elif (result.returncode != 86 or
                  "snapshot owner expired before Archive::ListFiles" not in result.stderr):
                raise SystemExit(f"The 07/08 lifetime regression was not detected ({result.returncode}):\n"
                                 + result.stdout + result.stderr)
            else:
                print("PASS: 07/08 temporary-owner regression rejected before using released storage", flush=True)


if __name__ == "__main__":
    main()
