// 2Ship 3DS runtime derived from the exact SoH v7 platform layer.
// Heap allocation, thread stacks and failure tracing stay isolated from MM
// libultra headers. Soh3ds* exports preserve the renderer/LUS hook ABI.

#include <3ds.h>
#include <ship/utils/logging_3ds.h>
#define SOH3DS_TRANSITION_TRACE_IMPLEMENTATION
#include <ship/utils/transition_trace_3ds.h>
#undef SOH3DS_TRANSITION_TRACE_IMPLEMENTATION
#include <spdlog/spdlog.h>

#include <unistd.h>
#include <sys/iosupport.h>
#include <cerrno>
#include <fcntl.h>
#include <cstdlib>

#include <atomic>
#include <exception>
#include <new>
#include <unwind.h>
#include <malloc.h>
#include <cstdio>
#include <cstring>
#include "archive_checks.h"

extern "C" void TwoShip3dsShowStartupError(const char* message);

extern "C" {
// Static constructors and game frames need more than libctru's default stack.
u32 __stacksize__ = 1 * 1024 * 1024;
u32 __ctru_linear_heap_size = 16 * 1024 * 1024;
u32 __ctru_heap_size = 66 * 1024 * 1024;
extern char* fake_heap_start;
extern char* fake_heap_end;
extern u32 __ctru_heap;
extern u32 __ctru_linear_heap;
static u32 sGrantedHeapSize = 0;

// Allocate against the process's actual commit budget; reserve GPU memory
// and a 2 MiB service margin before granting the remaining normal heap.
void __system_allocateHeaps(void) {
    Handle reslimit = 0;
    if (R_FAILED(svcGetResourceLimit(&reslimit, CUR_PROCESS_HANDLE))) {
        svcBreak(USERBREAK_PANIC);
    }
    s64 maxCommit = 0, currentCommit = 0;
    ResourceLimitType reslimitType = RESLIMIT_COMMIT;
    svcGetResourceLimitLimitValues(&maxCommit, reslimit, &reslimitType, 1);
    svcGetResourceLimitCurrentValues(&currentCommit, reslimit, &reslimitType, 1);
    svcCloseHandle(reslimit);

    if (maxCommit <= currentCommit) svcBreak(USERBREAK_PANIC);
    u32 remaining = (u32)(maxCommit - currentCommit) & ~0xFFF;
    const u32 margin = 2 * 1024 * 1024;
    u32 usable = remaining > (__ctru_linear_heap_size + margin) ? remaining - __ctru_linear_heap_size - margin : 0;
    usable &= ~0xFFF;
    if (usable == 0) svcBreak(USERBREAK_PANIC);
    __ctru_heap_size = usable;
    sGrantedHeapSize = __ctru_heap_size;

    if (R_FAILED(svcControlMemory(&__ctru_heap, OS_HEAP_AREA_BEGIN, 0x0, __ctru_heap_size, MEMOP_ALLOC,
                                  (MemPerm)(MEMPERM_READ | MEMPERM_WRITE)))) {
        svcBreak(USERBREAK_PANIC);
    }
    if (R_FAILED(svcControlMemory(&__ctru_linear_heap, 0x0, 0x0, __ctru_linear_heap_size, MEMOP_ALLOC_LINEAR,
                                  (MemPerm)(MEMPERM_READ | MEMPERM_WRITE)))) {
        svcBreak(USERBREAK_PANIC);
    }
    mappableInit(OS_MAP_AREA_BEGIN, OS_MAP_AREA_END);
    fake_heap_start = (char*)__ctru_heap;
    fake_heap_end = fake_heap_start + __ctru_heap_size;
}
int __real___syscall_thread_create(struct __pthread_t** thread, void* (*func)(void*), void* arg, void* stack_addr,
                                   size_t stack_size);
int __wrap___syscall_thread_create(struct __pthread_t** thread, void* (*func)(void*), void* arg, void* stack_addr,
                                   size_t stack_size) {
    constexpr size_t kMinThreadStack = 128 * 1024;
    if (stack_addr == nullptr && stack_size < kMinThreadStack) {
        stack_size = kMinThreadStack;
    }
    return __real___syscall_thread_create(thread, func, arg, stack_addr, stack_size);
}
static std::atomic<u32> sThreadBlocks[16] = {};
static std::atomic<unsigned> sThreadBlockCount{0};
typedef struct Thread_tag* Soh3dsWrapThread;
Soh3dsWrapThread __real_threadCreate(void (*entry)(void*), void* arg, size_t stack_size, int prio, int core_id,
                                     bool detached);
Soh3dsWrapThread __wrap_threadCreate(void (*entry)(void*), void* arg, size_t stack_size, int prio, int core_id,
                                     bool detached) {
    constexpr size_t kMinDirectStack = 16 * 1024;
    if (stack_size < kMinDirectStack) {
        stack_size = kMinDirectStack;
    }
    Soh3dsWrapThread t = __real_threadCreate(entry, arg, stack_size, prio, core_id, detached);
    if (t != NULL) {
        const unsigned slot = sThreadBlockCount.fetch_add(1, std::memory_order_relaxed);
        if (slot < 16) sThreadBlocks[slot].store((u32)t, std::memory_order_relaxed);
        fprintf(stderr, "2ship-3ds thread: entry=%p block=%p size=%u prio=%d core=%d\n", (void*)entry, (void*)t,
                (unsigned)stack_size, prio, core_id);
        FILE* f = Soh3dsLoggingEnabled(SOH3DS_LOG_GENERAL) ? fopen("bootinfo.txt", "a") : nullptr;
        if (f != NULL) {
            fprintf(f, "thread entry=%p block=%p size=%u prio=%d core=%d\n", (void*)entry, (void*)t,
                    (unsigned)stack_size, prio, core_id);
            fclose(f);
        }
    }
    return t;
}
void Soh3dsUnwindThrowTest(void);
static void SohCtrUnwindSelfTest() {
    try {
        Soh3dsUnwindThrowTest();
        fprintf(stderr, "2ship-3ds unwind: test function returned?!\n");
    } catch (...) {
        fprintf(stderr, "2ship-3ds unwind: cross-archive catch OK\n");
        return;
    }
}

} // extern "C"
static int sTransitionTraceFd = -1;
static unsigned sTransitionTraceEvents = 0;
static constexpr unsigned kTransitionTraceEventLimit = 64;

static void Soh3dsTransitionTraceClose() {
    if (sTransitionTraceFd >= 0) close(sTransitionTraceFd);
    sTransitionTraceFd = -1;
}

extern "C" void Soh3dsTransitionTraceEvent(const char* stage, uint32_t value) {
    if (sTransitionTraceFd < 0) return;
    char line[128];
    const int length = std::snprintf(line, sizeof(line), "%02u tick=%llu %.48s value=%lu\n",
                                     sTransitionTraceEvents,
                                     (unsigned long long)svcGetSystemTick(),
                                     stage ? stage : "(null)", (unsigned long)value);
    if (length <= 0) {
        Soh3dsTransitionTraceClose();
        return;
    }
    const size_t size = static_cast<size_t>(length) < sizeof(line)
                            ? static_cast<size_t>(length) : sizeof(line) - 1;
    size_t offset = 0;
    unsigned interrupted = 0;
    while (offset < size) {
        const ssize_t written = write(sTransitionTraceFd, line + offset, size - offset);
        if (written < 0 && errno == EINTR && ++interrupted <= 4) continue;
        if (written <= 0) {
            Soh3dsTransitionTraceClose();
            return;
        }
        offset += static_cast<size_t>(written);
    }
    if (fsync(sTransitionTraceFd) != 0 || ++sTransitionTraceEvents >= kTransitionTraceEventLimit) {
        Soh3dsTransitionTraceClose();
    }
}

extern "C" void Soh3dsTransitionTraceArm(void) {
    Soh3dsTransitionTraceClose();
    sTransitionTraceEvents = 0;
    sTransitionTraceFd = open("sdmc:/3ds/2ship/load-trace.txt", O_WRONLY | O_CREAT | O_TRUNC, 0666);
    Soh3dsTransitionTraceEvent("armed", 6);
}
static int sFatalFd = -1;
extern "C" void Soh3dsConfigureCrashLogging(bool enabled) {
    if (sFatalFd >= 0) { close(sFatalFd); sFatalFd = -1; }
    if (enabled) sFatalFd = open("lastfatal.txt", O_WRONLY | O_CREAT | O_APPEND, 0666);
}

static void SohCtrFatalMark(const char* stage, const char* detail = "") {
    if (sFatalFd < 0) {
        return;
    }
    char buf[192];
    int n = snprintf(buf, sizeof(buf), "%s tick=%llu %s\n", stage, (unsigned long long)svcGetSystemTick(), detail);
    if (n > 0) {
        size_t len = (size_t)n < sizeof(buf) - 1 ? (size_t)n : sizeof(buf) - 1;
        (void)write(sFatalFd, buf, len);
        (void)fsync(sFatalFd);
    }
}

extern "C" void Soh3dsLifecycleMark(const char* stage) {
    SohCtrFatalMark(stage);
    for (const auto& recorded : sThreadBlocks) {
        const u32 block = recorded.load(std::memory_order_relaxed);
        if (block == 0) continue;
        MemInfo memory = {};
        PageInfo page = {};
        const Result result = svcQueryMemory(&memory, &page, block);
        char detail[128];
        snprintf(detail, sizeof(detail), "block=%08lx rc=%08lx base=%08lx size=%08lx state=%lu perm=%lu",
                 (unsigned long)block, (unsigned long)result,
                 (unsigned long)memory.base_addr, (unsigned long)memory.size,
                 (unsigned long)memory.state, (unsigned long)memory.perm);
        SohCtrFatalMark("thread-map", detail);
    }
}
__attribute__((constructor(103))) static void SohCtrExitMarkInit() {
    std::atexit([] { SohCtrFatalMark("normal-exit"); });
}
static _Unwind_Reason_Code SohCtrTraceFrameToMarker(struct _Unwind_Context* ctx, void* arg) {
    int* count = (int*)arg;
    if (*count >= 12) {
        return _URC_FAILURE;
    }
    char frame[32];
    snprintf(frame, sizeof(frame), "pc=%08lx", (unsigned long)_Unwind_GetIP(ctx));
    SohCtrFatalMark("alloc-frame", frame);
    ++*count;
    return _URC_NO_REASON;
}
__attribute__((constructor(101))) static void SohCtrEarlyLogInit() {
    if (Soh3dsConfigureDebugOutput) Soh3dsConfigureDebugOutput();
    devoptab_list[STD_OUT] = devoptab_list[STD_ERR];
    setvbuf(stderr, nullptr, _IONBF, 0);
    setvbuf(stdout, nullptr, _IONBF, 0);
    if ((mkdir("sdmc:/3ds", 0777) != 0 && errno != EEXIST) ||
        (mkdir("sdmc:/3ds/2ship", 0777) != 0 && errno != EEXIST) ||
        chdir("sdmc:/3ds/2ship") != 0) {
        fprintf(stderr, "2ship-3ds: FATAL: could not create/use sdmc:/3ds/2ship (errno=%d). Exiting.\n", errno);
        gfxInitDefault();
        consoleInit(GFX_TOP, nullptr);
        printf("\n\n  2Ship 3DS\n  ---------------------\n\n"
               "  The app could not create or open:\n\n"
               "       sd:/3ds/2ship\n\n"
               "  Check that the SD card is writable and\n"
               "  that no file is using that name.\n\n"
               "  Press START to exit.\n");
        gfxFlushBuffers();
        gfxSwapBuffers();
        while (aptMainLoop()) {
            hidScanInput();
            if ((hidKeysDown() & KEY_START) != 0) break;
            gspWaitForVBlank();
        }
        gfxExit();
        exit(EXIT_FAILURE);
    }

    // Only a successful hardware query may reject an old model. An unavailable
    // query is not evidence of old hardware; actual MM allocations also check
    // and diagnose insufficient memory independently of this model check.
    bool newModel = false;
    const Result modelResult = APT_CheckNew3DS(&newModel);
    if (R_SUCCEEDED(modelResult) && !newModel) {
        TwoShip3dsShowStartupError("This build requires a New 3DS,\nNew 3DS XL or New 2DS XL.\n\n"
                                  "The original 3DS/3DS XL/2DS\nmodels are not supported.");
        exit(EXIT_FAILURE);
    }

    fprintf(stderr, "2ship-3ds: early log init, stack %u KiB, linear %u MiB, heap %u MiB (granted %u MiB)\n",
            (unsigned)(__stacksize__ / 1024), (unsigned)(__ctru_linear_heap_size / (1024 * 1024)),
            (unsigned)(__ctru_heap_size / (1024 * 1024)), (unsigned)(sGrantedHeapSize / (1024 * 1024)));
    {
        FILE* info = Soh3dsLoggingEnabled(SOH3DS_LOG_GENERAL) ? fopen("bootinfo.txt", "w") : nullptr;
        if (Soh3dsLoggingEnabled(SOH3DS_LOG_GENERAL))
            sFatalFd = open("lastfatal.txt", O_WRONLY | O_CREAT | O_TRUNC, 0666);
        SohCtrFatalMark("armed");
        u32 addr = 0x00100000;
        int regions = 0;
        if (info != NULL) {
            fprintf(info, "granted heap=%u MiB (requested %u), linear=%u MiB, main stack=%u KiB\n",
                    (unsigned)(sGrantedHeapSize / (1024 * 1024)), 66u,
                    (unsigned)(__ctru_linear_heap_size / (1024 * 1024)), (unsigned)(__stacksize__ / 1024));
        }
        while (Soh3dsLoggingEnabled(SOH3DS_LOG_GENERAL) && addr < 0x40000000 && regions < 40) {
            MemInfo mem;
            PageInfo page;
            if (R_FAILED(svcQueryMemory(&mem, &page, addr))) {
                break;
            }
            if (mem.state != MEMSTATE_FREE) {
                fprintf(stderr, "2ship-3ds map: %08lx-%08lx state=%u perm=%u\n", (unsigned long)mem.base_addr,
                        (unsigned long)(mem.base_addr + mem.size), (unsigned)mem.state, (unsigned)mem.perm);
                if (info != NULL) {
                    fprintf(info, "map %08lx-%08lx state=%u perm=%u\n", (unsigned long)mem.base_addr,
                            (unsigned long)(mem.base_addr + mem.size), (unsigned)mem.state, (unsigned)mem.perm);
                }
                ++regions;
            }
            u32 next = mem.base_addr + mem.size;
            if (next <= addr) {
                break;
            }
            addr = next;
        }
        if (info != NULL) {
            fclose(info);
        }
    }
    std::set_new_handler([] {
        std::set_new_handler(nullptr); // next failure throws instead of looping
        struct mallinfo mi = mallinfo();
        char detail[176];
        snprintf(detail, sizeof(detail), "uordblks=%u fordblks=%u ordblks=%u keepcost=%u arena=%u",
                 (unsigned)mi.uordblks, (unsigned)mi.fordblks, (unsigned)mi.ordblks, (unsigned)mi.keepcost,
                 (unsigned)mi.arena);
        SohCtrFatalMark("alloc-fail", detail);
        int frames = 0;
        _Unwind_Backtrace(SohCtrTraceFrameToMarker, &frames);
    });
    if (FILE* f = fopen("unwindtest.flag", "r")) {
        fclose(f);
        SohCtrUnwindSelfTest();
    }
}
#include <exception>
#include <unwind.h>
static _Unwind_Reason_Code SohCtrTraceFrame(struct _Unwind_Context* ctx, void* arg) {
    int* count = (int*)arg;
    if (*count >= 24) {
        return _URC_FAILURE;
    }
    fprintf(stderr, "2ship-3ds terminate bt[%02d]: %08lx\n", *count, (unsigned long)_Unwind_GetIP(ctx));
    ++*count;
    return _URC_NO_REASON;
}
extern "C" void Soh3dsAudioQuiesce(void) __attribute__((weak));

__attribute__((constructor(102))) static void SohCtrTerminateInit() {
    std::set_terminate([] {
        const char* what = "(unknown)";
        if (auto e = std::current_exception()) {
            try {
                std::rethrow_exception(e);
            } catch (const std::exception& ex) {
                what = ex.what();
            } catch (...) {
            }
        }
        fprintf(stderr, "2ship-3ds: FATAL uncaught exception: %s\n", what);
        SohCtrFatalMark("fatal", what);
        int frames = 0;
        _Unwind_Backtrace(SohCtrTraceFrame, &frames);
        if (Soh3dsAudioQuiesce != nullptr) {
            Soh3dsAudioQuiesce();
        }
        svcSleepThread(5'000'000'000LL); // 5 s to read the bottom screen
        SohCtrFatalMark("teardown-entered");
        abort();
    });
}
extern "C" {

static bool sBootConsoleUp = false;
static const devoptab_t* sBootConsoleOutput = nullptr;
static bool sRendererGraphicsReady = false;
void Soh3dsRestoreConsoleOutput(void) {
    if (sBootConsoleOutput) devoptab_list[STD_OUT] = sBootConsoleOutput;
}

void Soh3dsBootConsoleReady(void) {
    sRendererGraphicsReady = true;
    if (!sBootConsoleUp) {
        spdlog::set_level(Soh3dsLoggingEnabled(SOH3DS_LOG_GENERAL) ? spdlog::level::info : spdlog::level::off);
        consoleInit(GFX_BOTTOM, nullptr);
        if (sBootConsoleOutput == nullptr) sBootConsoleOutput = devoptab_list[STD_OUT];
        Soh3dsRestoreConsoleOutput();
        if (Soh3dsConfigureDebugOutput) Soh3dsConfigureDebugOutput();
        setvbuf(stderr, nullptr, _IONBF, 0);
        sBootConsoleUp = true;
        printf("2Ship 3DS\n---------------------\nStarting game...\n");
    }
}

void Soh3dsBootStatus(const char* msg) {
    fprintf(stderr, "2ship-3ds init: %s\n", msg);
    if (sBootConsoleUp) {
        printf("%s\n", msg);
        gfxFlushBuffers();
    }
}
void Soh3dsBootConsoleRelease(void) {
    if (sBootConsoleUp) {
        sBootConsoleUp = false;
        devoptab_list[STD_OUT] = devoptab_list[STD_ERR];
        setvbuf(stdout, nullptr, _IONBF, 0);
    }
}

} // extern C

namespace {

void StartErrorConsole(bool& ownsGraphics) {
    ownsGraphics = !sRendererGraphicsReady;
    if (ownsGraphics) gfxInitDefault();
    consoleInit(GFX_TOP, nullptr);
    if (sBootConsoleOutput == nullptr) sBootConsoleOutput = devoptab_list[STD_OUT];
    Soh3dsRestoreConsoleOutput();
    setvbuf(stdout, nullptr, _IONBF, 0);
}

void EndErrorConsole(bool ownsGraphics) {
    if (Soh3dsConfigureDebugOutput) Soh3dsConfigureDebugOutput();
    devoptab_list[STD_OUT] = devoptab_list[STD_ERR];
    if (ownsGraphics) gfxExit();
}

void PresentErrorConsole() {
    gfxFlushBuffers();
    gfxSwapBuffers();
    gspWaitForVBlank();
}

} // namespace

extern "C" void TwoShip3dsShowStartupError(const char* message) {
    bool ownsGraphics = false;
    StartErrorConsole(ownsGraphics);
    consoleClear();
    std::printf("2Ship 3DS\n---------\n\n%s\n\nPress START to exit.\n", message ? message : "Startup failed.");
    PresentErrorConsole();
    while (aptMainLoop()) {
        hidScanInput();
        if (hidKeysDown() & KEY_START) break;
        gspWaitForVBlank();
    }
    EndErrorConsole(ownsGraphics);
}

extern "C" bool TwoShip3dsPreflightArchives() {
    // The early constructor pins cwd for both CIA and Homebrew Launcher.
    // Check again here before allowing any game save/config initialization.
    if (chdir("sdmc:/3ds/2ship") != 0) {
        TwoShip3dsShowStartupError("Cannot open sd:/3ds/2ship.\nCheck the SD card.");
        return false;
    }
    bool consoleUp = false;
    bool ownsGraphics = false;
    for (;;) {
        char gameError[192] = {}, supportError[192] = {};
        const bool gameReady = TwoShip3ds::CheckArchive("sdmc:/3ds/2ship", "mm.o2r", false, gameError, sizeof(gameError));
        const bool supportReady = TwoShip3ds::CheckArchive("sdmc:/3ds/2ship", "2ship.o2r", true, supportError, sizeof(supportError));
        if (gameReady && supportReady) {
            if (consoleUp) EndErrorConsole(ownsGraphics);
            return true;
        }
        if (!consoleUp) {
            StartErrorConsole(ownsGraphics);
            consoleUp = true;
        }
        consoleClear();
        std::printf("2Ship 3DS\n---------\n\nRequired in sd:/3ds/2ship:\n  mm.o2r + 2ship.o2r\n\n");
        if (!gameReady) std::printf("%s\n\n", gameError);
        if (!supportReady) std::printf("%s\n\n", supportError);
        std::printf("Create the game archive with 2Ship\non your computer using your own ROM.\n"
                    "Use the 5.0.1 support archive.\n\n"
                    ".otr files cannot be loaded.\n\nA: retry    START: exit\n");
        PresentErrorConsole();
        bool retry = false;
        while (aptMainLoop()) {
            hidScanInput();
            const u32 pressed = hidKeysDown();
            if (pressed & KEY_START) break;
            if (pressed & KEY_A) { retry = true; break; }
            gspWaitForVBlank();
        }
        if (!retry) {
            EndErrorConsole(ownsGraphics);
            return false;
        }
    }
}
