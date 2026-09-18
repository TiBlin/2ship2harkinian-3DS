#include <3ds.h>
#include "ship/audio/BlinkyNdspAudioPlayer.h"
#include <array>
#include <cstring>
#include <thread>
using Ship::BlinkyNdspAudioPlayer;
int main() {
    std::array<uint8_t,8192> pcm{};
    for (size_t i=0;i<pcm.size();++i) pcm[i]=static_cast<uint8_t>(i*7);
    {
        BlinkyNdspAudioPlayer invalid({32000,6}); assert(!invalid.Init());
        BlinkyNdspAudioPlayer player({32000,2});
        fake::failAllocation=true; assert(!player.Init()); fake::failAllocation=false;
        fake::initResult=-22; assert(!player.Init()); fake::initResult=0;
        assert(player.Init()); assert(fake::rate==32000);
        BlinkyNdspAudioPlayer duplicate({32000,2}); assert(!duplicate.Init());
        player.Play(nullptr,4); player.Play(pcm.data(),3);
        assert(player.GetDiagnostics().rejectedBatches==2 && fake::adds==0);
        fake::failFlushAt=2; player.Play(pcm.data(),8192);
        assert(fake::adds==0 && player.Buffered()==0 && player.GetDiagnostics().flushFailures==1);
        fake::failFlushAt=-1; player.Play(pcm.data(),8192);
        assert(fake::adds==2 && player.Buffered()==2048);
        assert(std::memcmp(fake::waves[0]->data_vaddr,pcm.data(),4096)==0);
        assert(std::memcmp(fake::waves[1]->data_vaddr,pcm.data()+4096,4096)==0);
        fake::waves[0]->status=NDSP_WBUF_PLAYING; fake::playing=fake::waves[0]->sequence_id; fake::position=300;
        assert(player.Buffered()==1748);
        fake::position=5000; assert(player.Buffered()==1024);
        fake::waves[0]->status=NDSP_WBUF_DONE; fake::waves[1]->status=NDSP_WBUF_DONE;
        assert(player.Buffered()==0 && player.GetDiagnostics().completedBuffers==2);
        auto under=player.GetDiagnostics().underruns;
        player.Buffered(); assert(player.GetDiagnostics().underruns==under && under==1);
        fake::waves.clear();
        for(int i=0;i<6;++i) player.Play(pcm.data(),8192);
        assert(player.Buffered()==12288);
        int before=fake::adds; player.Play(pcm.data(),4); assert(fake::adds==before);
        BlinkyNdspAudioPlayer::Suspend(true); player.Play(pcm.data(),8);
        assert(fake::paused && player.GetDiagnostics().suspendedFrames==2);
        BlinkyNdspAudioPlayer::Suspend(false); assert(!fake::paused);
        BlinkyNdspAudioPlayer::Quiesce();
        player.Play(pcm.data(),8); assert(player.Buffered()==0 && fake::badCalls==0);
        assert(player.Init()); player.SetSampleRate(44100); player.Play(pcm.data(),8);
        assert(fake::rate==44100 && player.GetDiagnostics().sampleRate==44100);
        // Concurrent quiesce and producer: no NDSP calls after exit and no
        // descriptor/data access after free. The player outlives both threads.
        std::thread producer([&] { for(int i=0;i<100;++i) player.Play(pcm.data(),8); });
        BlinkyNdspAudioPlayer::Quiesce(); producer.join();
    }
    assert(fake::badCalls==0 && fake::allocations==fake::frees);
}
