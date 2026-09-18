// Blinky opt-in libc write guard. Public dependencies: GCC --wrap and libctru SVC.
// Scalar stores, inlined memory operations and GPU/DMA writes are outside its scope.
#include <3ds.h>
#include <atomic>
#include <cstddef>
#include <cstdint>
extern "C" {
void* __real_memset(void*, int, size_t);
void* __real_memcpy(void*, const void*, size_t);
void* __real_memmove(void*, const void*, size_t);
}
namespace {
std::atomic_flag regionLock = ATOMIC_FLAG_INIT;
uintptr_t regionAddress = 0;
size_t regionLength = 0;
std::atomic<bool> trapped{false};

struct DebugLine {
    char text[256];
    size_t used = 0;
    void add(const char* token) {
        while (*token && used < sizeof(text)) text[used++] = *token++;
    }
    void hex(uintptr_t number) {
        add("0x");
        for (unsigned digit = sizeof(number) * 2; digit; --digit) {
            if (used == sizeof(text)) break;
            const unsigned value = (number >> ((digit - 1) * 4)) & 15;
            text[used++] = char(value < 10 ? '0' + value : 'a' + value - 10);
        }
    }
    void field(const char* label, uintptr_t value) { add(label); hex(value); }
    void send() { add("\n"); svcOutputDebugString(text, static_cast<s32>(used)); }
};
[[noreturn]] void halt() { for (;;) svcSleepThread(1000000000LL); }
void lock() { while (regionLock.test_and_set(std::memory_order_acquire)) svcSleepThread(0); }
void unlock() { regionLock.clear(std::memory_order_release); }
bool intersects(uintptr_t address, size_t bytes, uintptr_t start, size_t length) {
    if (!bytes || !length) return false;
    if (address < start) return bytes > start - address;
    return address - start < length;
}
void inspect(const char* name, void* destination, size_t bytes, void* caller) {
    if (trapped.load(std::memory_order_acquire)) halt();
    lock();
    const uintptr_t start = regionAddress;
    const size_t length = regionLength;
    unlock();
    if (!intersects(reinterpret_cast<uintptr_t>(destination), bytes, start, length)) return;
    if (trapped.exchange(true, std::memory_order_acq_rel)) halt();
    DebugLine line;
    line.add("BLINKY MEMORY STOP "); line.add(name);
    line.field(" destination=", reinterpret_cast<uintptr_t>(destination));
    line.field(" size=", bytes); line.field(" caller=", reinterpret_cast<uintptr_t>(caller));
    line.field(" watch=", start); line.field(" length=", length); line.send();
    halt();
}
[[noreturn]] void audioTrap(const char* operation, uint16_t first, uint16_t second,
                            uint16_t third, uint16_t fourth) {
    trapped.store(true, std::memory_order_release);
    DebugLine line;
    line.add("BLINKY AUDIO STOP "); line.add(operation);
    line.field(" a=", first); line.field(" b=", second);
    line.field(" c=", third); line.field(" d=", fourth); line.send();
    halt();
}
}
extern "C" void TwoShip3dsWatchStateRegion(void* address, size_t bytes) {
    lock();
    regionAddress = reinterpret_cast<uintptr_t>(address);
    regionLength = bytes;
    unlock();
    DebugLine line;
    line.add("BLINKY MEMORY WATCH"); line.field(" start=", reinterpret_cast<uintptr_t>(address));
    line.field(" size=", bytes); line.send();
}
extern "C" void TwoShip3dsBadInterleave(uint16_t dest, uint16_t left, uint16_t right, uint16_t count) {
    audioTrap("INTERLEAVE", dest, left, right, count);
}
extern "C" void TwoShip3dsBadAdpcm(uint16_t input, uint16_t output, uint16_t count, uint16_t flags) {
    audioTrap("ADPCM", input, output, count, flags);
}
extern "C" __attribute__((noinline)) void* __wrap_memset(void* destination, int value, size_t bytes) {
    inspect("memset", destination, bytes, __builtin_extract_return_addr(__builtin_return_address(0)));
    return __real_memset(destination, value, bytes);
}
extern "C" __attribute__((noinline)) void* __wrap_memcpy(void* destination, const void* source, size_t bytes) {
    inspect("memcpy", destination, bytes, __builtin_extract_return_addr(__builtin_return_address(0)));
    return __real_memcpy(destination, source, bytes);
}
extern "C" __attribute__((noinline)) void* __wrap_memmove(void* destination, const void* source, size_t bytes) {
    inspect("memmove", destination, bytes, __builtin_extract_return_addr(__builtin_return_address(0)));
    return __real_memmove(destination, source, bytes);
}