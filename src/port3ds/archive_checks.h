#pragma once

// Platform-independent archive preflight used by the 3DS runtime and host tests.
#include <cstdio>
#include <cstring>
#include <unistd.h>
#include <zip.h>

namespace TwoShip3ds {

// Keep this translation unit independent of the MM/libultra typedefs. These
// version fields are the archive contract of the pinned 2Ship 5.0.1 source.
inline constexpr unsigned kPortMajor = 5;
inline constexpr unsigned kPortMinor = 0;
inline constexpr unsigned kPortPatch = 1;

inline bool CheckArchive(const char* directory, const char* name, bool support, char* error, size_t errorSize) {
    char path[512];
    const int pathSize = std::snprintf(path, sizeof(path), "%s/%s", directory, name);
    if (pathSize < 0 || static_cast<size_t>(pathSize) >= sizeof(path)) {
        std::snprintf(error, errorSize, "%s: archive path is too long.", name);
        return false;
    }
    FILE* file = std::fopen(path, "rb");
    if (file == nullptr) {
        char oldPath[512];
        std::snprintf(oldPath, sizeof(oldPath), "%s/%s.otr", directory, support ? "2ship" : "mm");
        const bool hasOtr = access(oldPath, F_OK) == 0;
        std::snprintf(error, errorSize, "%s: %s", name,
                      hasOtr ? ".otr is not supported. Supply an .o2r ZIP; renaming is not enough."
                             : "missing or unreadable.");
        return false;
    }
    unsigned char magic[4] = {};
    const size_t headerSize = std::fread(magic, 1, sizeof(magic), file);
    std::fclose(file);
    if (headerSize != sizeof(magic) || std::memcmp(magic, "PK\003\004", 4) != 0) {
        std::snprintf(error, errorSize, "%s: not an .o2r ZIP. .otr/MPQ and renamed ROM files are unsupported.", name);
        return false;
    }

    int zipError = 0;
    zip_t* archive = zip_open(path, ZIP_RDONLY, &zipError);
    if (archive == nullptr) {
        std::snprintf(error, errorSize, "%s: invalid ZIP archive (%d).", name, zipError);
        return false;
    }
    zip_stat_t stat = {};
    unsigned char version[7] = {};
    bool readable = zip_get_num_entries(archive, 0) > 1 &&
                    zip_stat(archive, "portVersion", 0, &stat) == 0 && stat.size == sizeof(version);
    zip_file_t* entry = readable ? zip_fopen(archive, "portVersion", 0) : nullptr;
    readable = entry != nullptr && zip_fread(entry, version, sizeof(version)) == sizeof(version);
    if (entry != nullptr && zip_fclose(entry) != 0) readable = false;
    zip_discard(archive);
    if (!readable || version[0] > 1) {
        std::snprintf(error, errorSize, "%s: missing or invalid portVersion metadata.", name);
        return false;
    }
    auto read16 = [&version](unsigned offset) -> unsigned {
        return version[0] == 1 ? (unsigned(version[offset]) << 8) | version[offset + 1]
                               : version[offset] | (unsigned(version[offset + 1]) << 8);
    };
    const unsigned major = read16(1), minor = read16(3), patch = read16(5);
    // MM asset compatibility follows upstream's major-version rule. The
    // support archive must match the executable's full version.
    if (major != kPortMajor || (support && (minor != kPortMinor || patch != kPortPatch))) {
        std::snprintf(error, errorSize, "%s: version %u.%u.%u. Need %s.", name, major, minor, patch,
                      support ? "2Ship 5.0.1" : "2Ship 5.x game assets");
        return false;
    }
    return true;
}

} // namespace TwoShip3ds
