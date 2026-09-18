#include <cassert>
#include <cstdint>
#include <iostream>
#include <memory>
#include <string>
#define RESOURCE_FORMAT_XML 1
#define SPDLOG_ERROR(...) ((void)0)
namespace tinyxml2 {
struct XMLElement {const char* Name() const{return "Texture";}int IntAttribute(const char*) const{return 1;}};
struct XMLDocument {XMLElement* root=nullptr;XMLElement* FirstChildElement(){return root;}};
}
namespace Ship {
struct ResourceInitData {std::string Path;bool IsCustom=false;int Format=0;uint32_t Type=0;int ResourceVersion=0;};
struct ResourceLoader {
    std::shared_ptr<ResourceInitData> CreateDefaultResourceInitData(){return std::make_shared<ResourceInitData>();}
    uint32_t GetResourceType(const char* name){assert(std::string(name)=="Texture");return 42;}
    std::shared_ptr<ResourceInitData> ReadResourceInitDataXml(const std::string&,std::shared_ptr<tinyxml2::XMLDocument>);
    ResourceLoader* GetResourceLoader(){return this;}
    ResourceLoader* GetResourceManager(){return this;}
};
struct Context {static ResourceLoader* GetRawInstance(){static ResourceLoader loader;return &loader;}};
