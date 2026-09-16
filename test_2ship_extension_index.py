#!/usr/bin/env python3
"""Compile production extension lookup functions against in-memory archives."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "third_party/2ship/mm/2s2h/BenPort.cpp"


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
    harness = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <memory>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
namespace Ship {
struct Archive {
    std::shared_ptr<std::unordered_map<uint64_t, std::string>> files =
        std::make_shared<std::unordered_map<uint64_t, std::string>>();
    auto ListFiles() { return files; }
};
struct ArchiveManager {
    std::shared_ptr<std::vector<std::shared_ptr<Archive>>> archives =
        std::make_shared<std::vector<std::shared_ptr<Archive>>>();
    auto GetArchives() { return archives; }
    const std::string* HashToString(uint64_t hash) {
        for (auto it = archives->rbegin(); it != archives->rend(); ++it) {
            if (!*it) continue;
            const auto found = (*it)->files->find(hash);
            if (found != (*it)->files->end()) return &found->second;
        }
        return nullptr;
    }
    bool HasFile(const std::string& path) {
        for (const auto& archive : *archives) {
            if (!archive) continue;
            for (const auto& [hash, name] : *archive->files) {
                if (name == path && HashToString(hash) == &name) return true;
            }
        }
        return false;
    }
    // No manager ListFiles: the production scan must not copy the complete list.
};
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
''' + production + r'''
int main() {
    auto resources = Ship::Context::GetRawInstance()->GetResourceManager();
    auto manager = resources->GetArchiveManager();
    auto vanilla = std::make_shared<Ship::Archive>();
    auto mods = std::make_shared<Ship::Archive>();
    manager->archives->assign({vanilla, nullptr, mods});
    for (uint64_t i=0; i<50496; ++i)
        (*vanilla->files)[1000+i] = "objects/object_test/gResource" + std::to_string(i);
    (*vanilla->files)[1] = "objects/gLink";
    (*vanilla->files)[2] = "textures/gIcon";
    OTRExtScanner();
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
    OTRExtScanner();
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
    manager->archives->pop_back();
    OTRExtScanner();
    assert(ExtensionAliases.size() == 1);
    assert(!ResourceMgr_FileExists("audio/my.sample")); // Removed mods do not leave stale aliases.
    assert(ResourceMgr_FileExists("shadowed/old"));
    assert(ResourceMgr_FileExists("__OTR__objects/gLink"));
    std::puts("PASS: production 3DS extension scanner, 50,496 generated resources, aliases, priority, prefixes, alt preloads");
}
'''
    compiler = shutil.which(os.environ.get("CXX", "g++"))
    if not compiler:
        raise SystemExit("A host C++ compiler is required (set CXX).")
    with tempfile.TemporaryDirectory(prefix="2ship-extension-index-", dir=ROOT.parent) as directory:
        directory = Path(directory)
        cpp = directory / "extension_index_test.cpp"
        executable = directory / "extension_index_test.exe"
        cpp.write_text(harness, encoding="utf-8")
        subprocess.run([compiler, "-std=c++20", "-D__3DS__", "-Wall", "-Wextra", "-Werror",
                        str(cpp), "-o", str(executable)], check=True)
        subprocess.run([str(executable)], check=True)


if __name__ == "__main__":
    main()
