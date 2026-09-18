// Regression contracts for the active backend, using the simulated SDK.
#include <3ds.h>
#include "ship/audio/BlinkyNdspAudioPlayer.h"
#include <array>
#include <cstring>
#include <string_view>
using Ship::BlinkyNdspAudioPlayer;

int main(int argc, char** argv) {
    assert(argc == 2);
    const std::string_view scenario = argv[1];
    std::array<uint8_t, 544 * 4> pcm{};
    for (size_t i = 0; i < pcm.size(); ++i) pcm[i] = static_cast<uint8_t>(i * 13);
    {
        BlinkyNdspAudioPlayer player({32000, 2});
        if (scenario == "init-failure") {
            fake::initResult = -1;
            assert(!player.Init());
            assert(fake::allocations == fake::frees && !fake::dsp);
            assert(player.Buffered() == 0);
            player.Play(pcm.data(), pcm.size());
            assert(fake::adds == 0);
            fake::initResult = 0;
            assert(player.Init()); // Failure must not retain exclusive ownership.
        } else if (scenario == "allocation-failure") {
            fake::failAllocation = true;
            assert(!player.Init());
            assert(fake::allocations == 0 && !fake::dsp);
            fake::failAllocation = false;
            assert(player.Init());
        } else {
            assert(player.Init());
            if (scenario == "flush-failure") {
                // Failure of the second chunk must also withhold the first.
                std::array<uint8_t, 8192> batch{};
                fake::failFlushAt = fake::flushes + 2;
                player.Play(batch.data(), batch.size());
                assert(fake::adds == 0 && player.Buffered() == 0);
                assert(player.GetDiagnostics().flushFailures == 1);
                fake::failFlushAt = -1;
                player.Play(batch.data(), batch.size());
                assert(fake::adds == 2 && player.Buffered() == 2048);
            } else if (scenario == "close-before-buffered") {
                player.Play(pcm.data(), pcm.size());
                BlinkyNdspAudioPlayer::Quiesce();
                // Buffered and Play must not touch NDSP after shutdown.
                assert(!fake::dsp && player.Buffered() == 0);
                const int adds = fake::adds;
                player.Play(pcm.data(), pcm.size());
                assert(fake::adds == adds && fake::badCalls == 0);
            } else if (scenario == "valid-submit") {
                player.Play(pcm.data(), pcm.size());
                assert(fake::adds == 1 && fake::rate == 32000);
                auto* wave = fake::waves.at(0);
                assert(wave->nsamples == 544);
                assert(std::memcmp(wave->data_vaddr, pcm.data(), pcm.size()) == 0);
                wave->status = NDSP_WBUF_PLAYING;
                fake::playing = wave->sequence_id;
                fake::position = 44;
                assert(player.Buffered() == 500);
            } else if (scenario == "pool-capacity") {
                std::array<uint8_t, 4096> block{};
                for (int i = 0; i < 12; ++i) player.Play(block.data(), block.size());
                assert(fake::adds == 12 && player.Buffered() == 12288);
                const int flushes = fake::flushes;
                player.Play(pcm.data(), pcm.size());
                assert(fake::adds == 12 && fake::flushes == flushes);
                auto* completed = fake::waves.at(0);
                completed->status = NDSP_WBUF_DONE;
                player.Play(pcm.data(), pcm.size());
                assert(fake::adds == 13 && fake::waves.back() == completed);
                assert(player.Buffered() == 11 * 1024 + 544);
            } else {
                assert(false && "Unknown scenario");
            }
        }
    }
    assert(!fake::dsp && fake::badCalls == 0 && fake::allocations == fake::frees);
}
