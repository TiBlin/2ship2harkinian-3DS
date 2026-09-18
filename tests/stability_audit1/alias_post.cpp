}
int main(int argc,char**argv){
    assert(argc==2);std::string mode=argv[1];Ship::malformed=mode=="invalid-metadata";Ship::missing=mode=="no-alias";
    Ship::ResourceLoader loader;auto original=std::make_shared<Ship::File>();auto file=original;
    auto result=loader.ResolveMetaAlias("source",file);
    if(Ship::malformed||Ship::missing)assert(!result && file==original && Ship::targetReads==0);
    else assert(result && file->marker==99 && Ship::targetReads==1);
    std::cout<<"PASS "<<mode<<"\n";
}
