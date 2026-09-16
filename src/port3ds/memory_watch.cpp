// Optional boot diagnostic. Enabled only by TWOSHIP3DS_MEMORY_WATCH.
// Detects external libc bulk writes, not inline stores or GPU/DMA writes.
#include <3ds.h>
#include <atomic>
#include <cstddef>
#include <cstdint>

extern "C" {
void* __real_memset(void* destination, int value, size_t size);
void* __real_memcpy(void* destination, const void* source, size_t size);
void* __real_memmove(void* destination, const void* source, size_t size);
}

namespace {
std::atomic<uintptr_t> sWatchStart{0};
std::atomic<size_t> sWatchSize{0};
std::atomic<bool> sStopped{false};

// Formatting uses only stack storage and scalar stores. Logging a bad memcpy
// must not allocate or invoke another intercepted memory function.
void AppendText(char* output, size_t& length, const char* text) {
    while (*text != '\0') {
        output[length++] = *text++;
    }
}

void AppendHex(char* output, size_t& length, uintptr_t value) {
    static constexpr char digits[] = "0123456789abcdef";
    AppendText(output, length, "0x");
    for (int shift = static_cast<int>(sizeof(value) * 8) - 4; shift >= 0; shift -= 4) {
        output[length++] = digits[(value >> shift) & 15];
    }
}

[[noreturn]] void SleepStopped() {
    for (;;) {
        svcSleepThread(1'000'000'000LL);
    }
}

bool Overlaps(const void* destination, size_t size, uintptr_t watchStart, size_t watchSize) {
    if (size == 0 || watchSize == 0) {
        return false;
    }
    const uintptr_t address = reinterpret_cast<uintptr_t>(destination);
    // Subtraction avoids an overflowing address + size comparison.
    return address >= watchStart ? address - watchStart < watchSize : watchStart - address < size;
}

void CheckWrite(const char* operation, const void* destination, size_t size, const void* caller) {
    if (sStopped.load(std::memory_order_relaxed)) {
        SleepStopped();
    }
    const size_t watchSize = sWatchSize.load(std::memory_order_acquire);
    const uintptr_t watchStart = sWatchStart.load(std::memory_order_relaxed);
    if (!Overlaps(destination, size, watchStart, watchSize)) {
        return;
    }
    if (sStopped.exchange(true, std::memory_order_relaxed)) {
        SleepStopped();
    }
    char message[256];
    size_t length = 0;
    AppendText(message, length, "2SHIP MEMORY WATCH STOP operation=");
    AppendText(message, length, operation);
    AppendText(message, length, " destination=");
    AppendHex(message, length, reinterpret_cast<uintptr_t>(destination));
    AppendText(message, length, " size=");
    AppendHex(message, length, size);
    AppendText(message, length, " caller=");
    AppendHex(message, length, reinterpret_cast<uintptr_t>(caller));
    AppendText(message, length, " watch=");
    AppendHex(message, length, watchStart);
    AppendText(message, length, " watchSize=");
    AppendHex(message, length, watchSize);
    AppendText(message, length, "\n");
    svcOutputDebugString(message, static_cast<s32>(length));
    SleepStopped();
}
} // namespace

extern "C" void TwoShip3dsWatchStateRegion(void* start, size_t size) {
    sWatchSize.store(0, std::memory_order_release);
    sWatchStart.store(reinterpret_cast<uintptr_t>(start), std::memory_order_relaxed);
    sWatchSize.store(size, std::memory_order_release);
    char message[128];
    size_t length = 0;
    AppendText(message, length, "2SHIP MEMORY WATCH ARMED start=");
    AppendHex(message, length, reinterpret_cast<uintptr_t>(start));
    AppendText(message, length, " size=");
    AppendHex(message, length, size);
    AppendText(message, length, "\n");
    svcOutputDebugString(message, static_cast<s32>(length));
}

extern "C" void TwoShip3dsBadInterleave(uint16_t dest, uint16_t left, uint16_t right, uint16_t count) {
    char message[128];
    size_t length = 0;
    AppendText(message, length, "2SHIP BAD INTERLEAVE dest=");
    AppendHex(message, length, dest);
    AppendText(message, length, " left=");
    AppendHex(message, length, left);
    AppendText(message, length, " right=");
    AppendHex(message, length, right);
    AppendText(message, length, " count=");
    AppendHex(message, length, count);
    AppendText(message, length, "\n");
    svcOutputDebugString(message, static_cast<s32>(length));
    SleepStopped();
}

extern "C" void TwoShip3dsBadAdpcm(uint16_t input, uint16_t output, uint16_t count, uint16_t flags) {
    char message[128];
    size_t length = 0;
    AppendText(message, length, "2SHIP BAD ADPCM in=");
    AppendHex(message, length, input);
    AppendText(message, length, " out=");
    AppendHex(message, length, output);
    AppendText(message, length, " count=");
    AppendHex(message, length, count);
    AppendText(message, length, " flags=");
    AppendHex(message, length, flags);
    AppendText(message, length, "\n");
    svcOutputDebugString(message, static_cast<s32>(length));
    SleepStopped();
}

extern "C" __attribute__((noinline)) void* __wrap_memset(void* destination, int value, size_t size) {
    CheckWrite("memset", destination, size, __builtin_extract_return_addr(__builtin_return_address(0)));
    return __real_memset(destination, value, size);
}

extern "C" __attribute__((noinline)) void* __wrap_memcpy(void* destination, const void* source, size_t size) {
    CheckWrite("memcpy", destination, size, __builtin_extract_return_addr(__builtin_return_address(0)));
    return __real_memcpy(destination, source, size);
}

extern "C" __attribute__((noinline)) void* __wrap_memmove(void* destination, const void* source, size_t size) {
    CheckWrite("memmove", destination, size, __builtin_extract_return_addr(__builtin_return_address(0)));
    return __real_memmove(destination, source, size);
}
