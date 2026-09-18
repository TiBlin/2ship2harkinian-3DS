#include <iostream>
#include <string>
#include <vector>
int main(int argc,char**argv) {
    assert(argc==2);const std::string mode=argv[1];Ship::NdspAudioPlayer p;
    if(mode=="init-failure") {fake::initResult=-1;assert(!p.Init());p.Close();assert(fake::allocs==0);}
    else if(mode=="allocation-failure") {fake::failAlloc=3;assert(!p.Init());assert(fake::allocs==3 && fake::frees==3 && !fake::initialized);}
    else {
        assert(p.Init());assert(fake::allocs==8 && fake::rate==32000);
        std::vector<int16_t> samples(544*2,1234);
        auto play=[&]{p.Play(reinterpret_cast<const uint8_t*>(samples.data()),samples.size()*sizeof(int16_t));};
        if(mode=="flush-failure") {
            fake::flushResult=-123;play();assert(fake::flushes==1 && fake::adds==0 && p.Buffered()==0);
            fake::flushResult=0;play();assert(fake::adds==1);
        } else if(mode=="close-before-buffered") {
            fake::beforeLock=[&]{p.Close();};assert(p.Buffered()==0 && fake::afterExit==0);
        } else if(mode=="valid-submit") {
            play();assert(fake::adds==1 && fake::lastBytes==2176);
            auto* wave=fake::waves[0];assert(wave->nsamples==544 && p.Buffered()==544);
            assert(std::memcmp(wave->data_vaddr,samples.data(),2176)==0 && !wave->looping);
            wave->status=NDSP_WBUF_PLAYING;wave->sequence_id=5;fake::seq=5;fake::pos=44;assert(p.Buffered()==500);
        } else if(mode=="pool-capacity") {
            for(int i=0;i<8;++i)play();assert(fake::adds==8 && p.Buffered()==544*8);
            play();assert(fake::adds==8 && fake::flushes==8);
            fake::waves[0]->status=NDSP_WBUF_DONE;play();assert(fake::adds==9);
        } else return 2;
        p.Close();assert(fake::frees==fake::allocs && fake::afterExit==0);
        assert(p.Buffered()==0);play();assert(fake::afterExit==0);
    }
    std::cout<<"PASS "<<mode<<"\n";
}
