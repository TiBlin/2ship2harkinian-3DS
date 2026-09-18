#pragma once
// Host substitute for LUS base-class collaborators; native build uses LUS.
#include <cstdint>
#include <cstddef>
namespace Ship {
struct AudioSettings { int32_t SampleRate=32000; int32_t Channels=2; };
class AudioPlayer {
    AudioSettings settings;
  public:
    explicit AudioPlayer(AudioSettings s) : settings(s) {}
    virtual ~AudioPlayer()=default;
    bool Init() { return DoInit(); }
    void Play(const uint8_t* p, size_t n) { DoPlay(p,n); }
    int32_t GetSampleRate() const { return settings.SampleRate; }
    int32_t GetNumOutputChannels() const { return settings.Channels; }
    void SetSampleRate(int32_t rate) { settings.SampleRate=rate; }
    virtual int32_t Buffered()=0;
  protected:
    virtual bool DoInit()=0;
    virtual void DoClose()=0;
    virtual void DoPlay(const uint8_t*,size_t)=0;
};
}
