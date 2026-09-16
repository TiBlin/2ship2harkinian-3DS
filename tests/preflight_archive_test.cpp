// Production preflight runs against actual files plus libzip boundary doubles.
#include "archive_checks.h"
#include <algorithm>
#include <array>
#include <cassert>
#include <fstream>
#include <string>

struct ZipBehavior {
    bool opens = true, statOk = true, entryOpens = true;
    zip_int64_t entries = 2, readCount = 7;
    zip_uint64_t metadataSize = 7;
    int closeResult = 0, opened = 0, discarded = 0, filesOpened = 0, filesClosed = 0;
    std::array<unsigned char, 7> version = {1, 0, 5, 0, 0, 0, 1};
} behavior;
zip_t archive;
zip_file_t entry;

zip_t* zip_open(const char* name, int flags, int* error) {
    assert(std::strstr(name, ".o2r") != nullptr && flags == ZIP_RDONLY);
    if (!behavior.opens) { *error = 19; return nullptr; }
    ++behavior.opened;
    return &archive;
}
zip_int64_t zip_get_num_entries(zip_t* value, zip_flags_t) {
    assert(value == &archive);
    return behavior.entries;
}
int zip_stat(zip_t* value, const char* name, zip_flags_t, zip_stat_t* stat) {
    assert(value == &archive && std::strcmp(name, "portVersion") == 0);
    stat->size = behavior.metadataSize;
    return behavior.statOk ? 0 : -1;
}
zip_file_t* zip_fopen(zip_t* value, const char* name, zip_flags_t) {
    assert(value == &archive && std::strcmp(name, "portVersion") == 0);
    if (!behavior.entryOpens) return nullptr;
    ++behavior.filesOpened;
    return &entry;
}
zip_int64_t zip_fread(zip_file_t* value, void* output, zip_uint64_t size) {
    assert(value == &entry && size == 7);
    if (behavior.readCount > 0)
        std::memcpy(output, behavior.version.data(), std::min<zip_int64_t>(behavior.readCount, 7));
    return behavior.readCount;
}
int zip_fclose(zip_file_t* value) {
    assert(value == &entry);
    ++behavior.filesClosed;
    return behavior.closeResult;
}
void zip_discard(zip_t* value) {
    assert(value == &archive);
    ++behavior.discarded;
}

unsigned cases = 0;
std::string directory;
void file(const char* name, const std::string& bytes = std::string("PK\003\004data", 8)) {
    std::ofstream stream(directory + "/" + name, std::ios::binary);
    stream.write(bytes.data(), bytes.size());
    assert(stream.good());
}
void expect(const char* label, bool support, bool accepted, const char* message = "") {
    struct { char message[192]; unsigned canary; } output = {{}, 0xDEADBEEF};
    const bool actual = TwoShip3ds::CheckArchive(directory.c_str(), support ? "2ship.o2r" : "mm.o2r",
                                                support, output.message, sizeof(output.message));
    if (actual != accepted || std::strstr(output.message, message) == nullptr) {
        std::fprintf(stderr, "%s: accepted=%d, expected=%d, error=%s\n", label, actual, accepted, output.message);
        std::abort();
    }
    assert(output.canary == 0xDEADBEEF);
    assert(behavior.opened == behavior.discarded);
    assert(behavior.filesOpened == behavior.filesClosed);
    ++cases;
    behavior = {};
}

int main(int argc, char** argv) {
    assert(argc == 2);
    directory = argv[1];
    expect("missing game", false, false, "missing or unreadable");
    expect("missing support", true, false, "missing or unreadable");
    file("mm.otr", "MPQ\032");
    expect("legacy game .otr", false, false, ".otr is not supported");
    file("2ship.otr", "MPQ\032");
    expect("legacy support .otr", true, false, ".otr is not supported");
    for (unsigned length = 0; length < 4; ++length) {
        file("mm.o2r", std::string("PK\003\004", length));
        expect("short ZIP header", false, false, "not an .o2r ZIP");
    }
    file("mm.o2r", "MPQ\032renamed");
    expect("renamed MPQ", false, false, ".otr/MPQ");
    file("mm.o2r", std::string("\200\067\022\100", 4));
    expect("renamed ROM", false, false, "not an .o2r ZIP");
    file("mm.o2r");
    file("2ship.o2r");
    expect("game big endian", false, true);
    expect("support big endian", true, true);
    behavior.version = {0, 5, 0, 0, 0, 1, 0};
    expect("support little endian", true, true);
    behavior.version = {0, 5, 0, 9, 0, 99, 0};
    expect("compatible game minor and patch", false, true);
    behavior.version = {1, 0, 4, 0, 0, 0, 1};
    expect("game major mismatch", false, false, "Need 2Ship 5.x");
    behavior.version = {1, 1, 5, 0, 0, 0, 1};
    expect("major high byte used", false, false, "version 261.0.1");
    behavior.version = {1, 0, 5, 0, 1, 0, 1};
    expect("support minor mismatch", true, false, "Need 2Ship 5.0.1");
    behavior.version = {1, 0, 5, 0, 0, 0, 0};
    expect("support patch mismatch", true, false, "Need 2Ship 5.0.1");
    behavior.version[0] = 2;
    expect("invalid byte order", false, false, "invalid portVersion");
    behavior.opens = false;
    expect("libzip rejects archive", false, false, "invalid ZIP archive");
    behavior.entries = -1;
    expect("entry enumeration fails", false, false, "invalid portVersion");
    behavior.entries = 1;
    expect("version-only archive", false, false, "invalid portVersion");
    behavior.statOk = false;
    expect("missing version entry", false, false, "invalid portVersion");
    for (unsigned size : {0u, 6u, 8u, 4096u}) {
        behavior.metadataSize = size;
        expect("wrong metadata size", false, false, "invalid portVersion");
    }
    behavior.entryOpens = false;
    expect("metadata open fails", false, false, "invalid portVersion");
    for (int bytes : {-1, 0, 1, 6}) {
        behavior.readCount = bytes;
        expect("metadata error or short read", false, false, "invalid portVersion");
    }
    behavior.closeResult = -1;
    expect("metadata close or CRC failure", false, false, "invalid portVersion");
    const std::string longDirectory(520, 'a');
    char message[64] = {};
    assert(!TwoShip3ds::CheckArchive(longDirectory.c_str(), "mm.o2r", false, message, sizeof(message)));
    assert(std::strstr(message, "too long"));
    ++cases;
    std::printf("PASS: %u production archive preflight cases (libzip boundary double)\n", cases);
}
