}
int main(int argc,char**argv){
    assert(argc==2);std::string mode=argv[1];Ship::ResourceLoader loader;
    if(mode=="null-document")assert(!loader.ReadResourceInitDataXml("test.xml",nullptr));
    else{
        auto doc=std::make_shared<tinyxml2::XMLDocument>();tinyxml2::XMLElement element;
        if(mode=="root-present")doc->root=&element;
        auto result=loader.ReadResourceInitDataXml("test.xml",doc);
        if(mode=="no-root")assert(!result);
        else assert(result && result->Type==42 && result->ResourceVersion==1 && result->IsCustom);
    }
    std::cout<<"PASS "<<mode<<"\n";
}
