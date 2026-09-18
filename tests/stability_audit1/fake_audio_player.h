#pragma once
#include <cstdint>
#include <cstddef>
namespace Ship {
class AudioPlayer {
public:
    virtual ~AudioPlayer()=default;
    bool Init(){return DoInit();}
    void Close(){DoClose();}
    void Play(const uint8_t* p,size_t n){DoPlay(p,n);}
    uint32_t GetSampleRate(){return 32000;}
    virtual int32_t Buffered()=0;
protected:
    virtual bool DoInit()=0;
    virtual void DoClose()=0;
    virtual void DoPlay(const uint8_t*,size_t)=0;
};
}
