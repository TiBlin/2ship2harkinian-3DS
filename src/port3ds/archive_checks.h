#pragma once
// Blinky archive gate, independently implemented against public libzip calls.
// Version layout and compatibility policy belong to HarbourMasters 2Ship 5.0.1.
#include <array>
#include <cstdio>
#include <cstring>
#include <memory>
#include <unistd.h>
#include <zip.h>

namespace TwoShip3ds {
inline constexpr unsigned kPortMajor = 5, kPortMinor = 0, kPortPatch = 1;

inline bool CheckArchive(const char* directory, const char* name, bool support,
                         char* error, size_t errorSize) {
    auto reject = [&](const char* reason) {
        if (error && errorSize) std::snprintf(error, errorSize, "%s: %s", name, reason);
        return false;
    };
    if (error && errorSize) error[0] = '\0';
    std::array<char, 512> path{};
    const auto length = std::snprintf(path.data(), path.size(), "%s/%s", directory, name);
    if (length < 0 || static_cast<size_t>(length) >= path.size()) return reject("archive path is too long.");
    using File = std::unique_ptr<FILE, decltype(&std::fclose)>;
    File raw(std::fopen(path.data(), "rb"), &std::fclose);
    if (!raw) {
        std::array<char, 512> legacy{};
        const auto written = std::snprintf(legacy.data(), legacy.size(), "%s/%s.otr", directory, support ? "2ship" : "mm");
        const bool oldArchive = written >= 0 && static_cast<size_t>(written) < legacy.size() &&
                                access(legacy.data(), F_OK) == 0;
        return reject(oldArchive ? ".otr is not supported. Supply an .o2r ZIP; renaming is not enough."
                                 : "missing or unreadable.");
    }
    std::array<unsigned char, 4> signature{};
    const auto bytes = std::fread(signature.data(), 1, signature.size(), raw.get());
    raw.reset();
    if (bytes != signature.size() || signature != std::array<unsigned char, 4>{'P','K',3,4})
        return reject("not an .o2r ZIP. .otr/MPQ and renamed ROM files are unsupported.");

    int failure = 0;
    using Archive = std::unique_ptr<zip_t, decltype(&zip_discard)>;
    Archive archive(zip_open(path.data(), ZIP_RDONLY, &failure), &zip_discard);
    if (!archive) return reject("invalid ZIP archive.");
    zip_stat_t metadata{};
    std::array<unsigned char, 7> version{};
    if (zip_get_num_entries(archive.get(), 0) < 2 ||
        zip_stat(archive.get(), "portVersion", 0, &metadata) != 0 || metadata.size != version.size())
        return reject("missing or invalid portVersion metadata.");
    zip_file_t* stream = zip_fopen(archive.get(), "portVersion", 0);
    if (!stream) return reject("missing or invalid portVersion metadata.");
    const bool full = zip_fread(stream, version.data(), version.size()) == static_cast<zip_int64_t>(version.size());
    const bool closed = zip_fclose(stream) == 0;
    if (!full || !closed || version[0] > 1) return reject("missing or invalid portVersion metadata.");

    std::array<unsigned, 3> decoded{};
    for (unsigned field = 0; field != decoded.size(); ++field) {
        const unsigned first = version[1 + field * 2], second = version[2 + field * 2];
        decoded[field] = version[0] ? first * 256 + second : second * 256 + first;
    }
    const bool accepted = decoded[0] == kPortMajor &&
                          (!support || (decoded[1] == kPortMinor && decoded[2] == kPortPatch));
    if (!accepted && error && errorSize)
        std::snprintf(error, errorSize, "%s: version %u.%u.%u. Need %s.", name,
                      decoded[0], decoded[1], decoded[2], support ? "2Ship 5.0.1" : "2Ship 5.x game assets");
    return accepted;
}
} // namespace TwoShip3ds