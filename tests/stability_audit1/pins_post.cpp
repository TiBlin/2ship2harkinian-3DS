int main(int argc,char**argv){
    assert(argc==2);std::string mode=argv[1];auto& manager=Ship::Context::GetRawInstance()->manager;
    const bool grass=mode.starts_with("grass");
    absent=mode.ends_with("missing");tiny=mode.ends_with("short");enabled=!mode.ends_with("disabled");
    auto patch=[&]{if(grass)GfxPatcher_ApplyFierceDeityGIPatch();else PatchGeometrySeams();};patch();
    if(absent||tiny||!enabled){assert(!published);if(!enabled)assert(manager.cache.empty());}
    else{
        assert(published);auto* data=published[grass?1:3].pointer;assert(data);
        // Simulate the real scene eviction removing the only cache owner.
        manager.cache.clear();assert(data[0]==77);patch();assert(data==published[grass?1:3].pointer);
    }
    std::cout<<"PASS "<<mode<<"\n";
}
