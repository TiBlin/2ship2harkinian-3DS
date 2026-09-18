} // Ship
int main(int argc,char**argv) {
    assert(argc==2);std::string mode=argv[1]; Ship::ResourceManager m;
    Ship::ResourceIdentifier id{"objects/long-long-long-long-path/entry"};
    if(mode=="publication") {
        std::barrier bothLoaded(2), bothSnapshots(2);m.loader->ready=&bothLoaded;m.snapshotGate=&bothSnapshots;
        std::shared_ptr<Ship::IResource> a,b;
        std::thread t1([&]{a=m.LoadResourceProcess(id,true,nullptr);});
        std::thread t2([&]{b=m.LoadResourceProcess(id,true,nullptr);});t1.join();t2.join();
        assert(a && a==b);auto cached=std::get<std::shared_ptr<Ship::IResource>>(m.mResourceCache.at(id));assert(a==cached);
    } else if(mode=="transient-read") {
        m.mAltAssetsEnabled=true;id.Path="alt/object/texture";
        m.readFailure=true;auto a=m.LoadResourceProcess(id,false,nullptr);assert(!a);
        assert(m.mResourceCache.find(id)==m.mResourceCache.end());
        m.readFailure=false;auto b=m.LoadResourceProcess(id,false,nullptr);assert(b);
    } else if(mode=="transient-import") {
        m.mAltAssetsEnabled=true;id.Path="alt/object/texture";m.loader->fail=true;
        assert(!m.LoadResourceProcess(id,false,nullptr));
        assert(m.mResourceCache.find(id)==m.mResourceCache.end());
        m.loader->fail=false;assert(m.LoadResourceProcess(id,false,nullptr));
    } else if(mode=="absent") {
        m.readFailure=true;m.mArchiveManager->hasFile=false;assert(!m.LoadResourceProcess(id,true,nullptr));
        assert(std::get<Ship::ResourceManager::ResourceLoadError>(m.mResourceCache.at(id))==Ship::ResourceManager::ResourceLoadError::NotFound);
    } else if(mode=="cache-hit") {
        auto a=m.LoadResourceProcess(id,true,nullptr);auto b=m.LoadResourceProcess(id,true,nullptr);assert(a && a==b);
#ifdef AUDIT_FIXED
    } else if(mode=="late-failure") {
        auto a=m.PublishResourceLoad(id,std::make_shared<Ship::IResource>(),false);
        assert(m.PublishResourceLoad(id,nullptr,true)==a);
        assert(m.PublishResourceLoad(id,nullptr,false)==a);
    } else if(mode=="destructor-lock") {
        bool destroyed=false;auto old=std::make_shared<Ship::IResource>();old->dirty=true;
        old->onDestroy=[&]{assert(m.mMutex.try_lock());m.mMutex.unlock();destroyed=true;};
        m.mResourceCache[id]=std::move(old);
        auto replacement=m.PublishResourceLoad(id,std::make_shared<Ship::IResource>(),false);assert(destroyed && replacement);
#endif
    } else if(mode=="cache-report-empty") {
        char out[8]="old";m.Soh3dsCacheReport(out,sizeof(out));assert(out[0]==0);
        m.Soh3dsCacheReport(nullptr,0);
    } else if(mode=="cache-report-concurrent") {
        m.mResourceCache[id]=std::make_shared<Ship::IResource>();
        Ship::reportPoint=[&]{std::thread remover([&]{if(m.mMutex.try_lock()){m.mResourceCache.clear();m.mMutex.unlock();}});remover.join();};
        char out[128];m.Soh3dsCacheReport(out,sizeof(out));assert(std::string(out)=="objects=1/1");
        Ship::reportPoint=nullptr;
    } else if(mode=="cache-report-content") {
        m.mResourceCache[id]=std::make_shared<Ship::IResource>();char out[128];m.Soh3dsCacheReport(out,sizeof(out));
        assert(std::string(out)=="objects=1/1");
    } else return 2;
    std::cout<<"PASS "<<mode<<"\n";
}
