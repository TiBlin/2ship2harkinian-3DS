#include <3ds.h>
#include "ship/port/3ds/BlinkyLifecycle.h"
#include "ship/audio/BlinkyNdspAudioPlayer.h"
#include "fast/backends/gfx_blinky_3ds_window.h"
#include <array>
using namespace Ship::Blinky3DS;
namespace Fast {
void BlinkyInitializeLusGui() {}
bool BlinkyUpdateLusControllers(bool) { return true; }
}
namespace {
int drains=0, invalidations=0, releases=0;
bool graphicsAlive=false;
void Drain() { assert(graphicsAlive && fake::paused); ++drains; }
void Invalidate() { assert(graphicsAlive && fake::paused); ++invalidations; }
void Release() { ++releases; }
}
int main() {
    std::array<uint8_t, 64> pcm{};
    assert(!GetLifecycleSnapshot().installed);
    StopLifecycle(); // Partial boot / repeated destruction.
    StartLifecycle(); StartLifecycle();
    assert(fake::hooks==1 && fake::badCalls==0);
    fake::event(APTHOOK_ONSUSPEND);
    StartLifecycle(); // Duplicate start must not erase an outstanding pause.
    assert(GetLifecycleSnapshot().pauseReasons==Background);
    {
        Ship::BlinkyNdspAudioPlayer audio({32000,2});
        assert(audio.Init() && fake::paused); // Pause precedes NDSP creation.
        audio.Play(pcm.data(),pcm.size()); assert(fake::adds==0);
        fake::event(APTHOOK_ONRESTORE); assert(!fake::paused);
        audio.Play(pcm.data(),pcm.size()); assert(fake::adds==1);

        Fast::GfxWindowBackendBlinky3DS window;
        window.SetKeyboardCallbacks(nullptr,nullptr,Release);
        window.Init("MM","native",false,400,240,0,0);
        assert(fake::registeredHooks.size()==2);
        graphicsAlive=true;
        SetRendererLifecycleCallbacks({Drain,Invalidate});

        // Lid-only: stop sound before draining GPU; invalidate before unpause.
        fake::event(APTHOOK_ONSLEEP); fake::event(APTHOOK_ONSLEEP);
        assert(fake::paused && !window.IsFrameReady() && drains==1 && releases==1);
        fake::event(APTHOOK_ONWAKEUP); fake::event(APTHOOK_ONWAKEUP);
        assert(!fake::paused && window.IsFrameReady() && invalidations==1);

        // Both nesting orders: neither individual restore can resume alone.
        fake::event(APTHOOK_ONSUSPEND); fake::event(APTHOOK_ONSLEEP);
        assert(GetLifecycleSnapshot().pauseReasons==(Background|ClosedLid));
        assert(drains==1); // GPU must not be touched while HOME owns it.
        fake::event(APTHOOK_ONWAKEUP);
        assert(fake::paused && !window.IsFrameReady() && invalidations==1);
        fake::event(APTHOOK_ONRESTORE);
        assert(!fake::paused && window.IsFrameReady() && invalidations==2);

        fake::event(APTHOOK_ONSLEEP); fake::event(APTHOOK_ONSUSPEND);
        fake::event(APTHOOK_ONRESTORE);
        assert(fake::paused && !window.IsFrameReady() && drains==2);
        fake::event(APTHOOK_ONWAKEUP);
        assert(!fake::paused && window.IsFrameReady() && invalidations==3);
        auto state=GetLifecycleSnapshot();
        assert(state.pauses==4 && state.resumes==4 && state.lidSleeps==3 && state.lidWakes==3);

        // Renderer destruction during suspension cannot be followed by callbacks.
        fake::event(APTHOOK_ONSLEEP);
        ClearRendererLifecycleCallbacks(); graphicsAlive=false;
        fake::event(APTHOOK_ONWAKEUP);
        assert(!fake::paused && invalidations==3 && !GetLifecycleSnapshot().rendererAttached);
        fake::event(static_cast<APT_HookType>(99));
        assert(GetLifecycleSnapshot().pauseReasons==0);

        fake::event(APTHOOK_ONSLEEP);
        graphicsAlive=true;
        SetRendererLifecycleCallbacks({Drain,Invalidate});
        assert(drains==3); // Attaching to an asleep session makes no GPU calls.
        fake::event(APTHOOK_ONWAKEUP);
        assert(invalidations==4 && !fake::paused);

        // APT exit is terminal. Late restores and starts cannot restart audio.
        fake::event(APTHOOK_ONSUSPEND);
        fake::event(APTHOOK_ONEXIT);
        assert(!fake::dsp && !window.IsRunning() && GetLifecycleSnapshot().stopping);
        const int submitted=fake::adds;
        audio.Play(pcm.data(),pcm.size());
        assert(fake::adds==submitted && audio.Buffered()==0);
        fake::event(APTHOOK_ONRESTORE); fake::event(APTHOOK_ONWAKEUP);
        StartLifecycle(); SetRendererLifecycleCallbacks({Drain,Invalidate});
        assert(GetLifecycleSnapshot().stopping && !GetLifecycleSnapshot().rendererAttached);
        StopLifecycle(); StopLifecycle();
        assert(fake::registeredHooks.size()==1 && invalidations==4);
        window.Destroy(); window.Destroy();
        assert(fake::registeredHooks.empty());
    }
    assert(fake::badCalls==0 && fake::allocations==fake::frees);

    // A fresh session explicitly resets terminal state and the NDSP pause latch.
    StartLifecycle();
    {
        Ship::BlinkyNdspAudioPlayer audio({32000,2});
        assert(audio.Init() && !fake::paused);
        fake::event(APTHOOK_ONSLEEP);
        StopLifecycle(); // Normal shutdown while asleep also quiesces; never wakes GPU.
        assert(!fake::dsp && audio.Buffered()==0);
    }
    assert(fake::registeredHooks.empty() && fake::hooks==fake::unhooks);
    assert(fake::badCalls==0 && fake::allocations==fake::frees);
}
