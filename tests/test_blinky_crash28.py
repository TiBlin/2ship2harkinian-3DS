"""Run the production fatal/config paths with explicit kernel/SD collaborators."""
from pathlib import Path
import argparse, os, shutil, subprocess, tempfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--cxx', required=True)
parser.add_argument('--json-include', type=Path, help='Directory containing nlohmann/json.hpp')
args = parser.parse_args()
env = dict(os.environ)
env['PATH'] = str(Path(args.cxx).parent) + os.pathsep + env.get('PATH', '')

def body(path, signature):
    source = path.read_text()
    start = source.index(signature)
    opening = source.index('{', start)
    level, end = 1, opening + 1
    while level:
        level += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]

runtime = root/'src/blinky/native_runtime.cpp'
config = root/'third_party/libultraship/src/ship/config/Config.cpp'
fatal_test = r'''
#include <cassert>
#include <cstdio>
#include <cstdlib>
static bool stopped=false, kernelExit=false;
struct Exited {};
namespace Ship {struct BlinkyNdspAudioPlayer {static void Quiesce(){stopped=true;}};}
[[noreturn]] void svcExitProcess(){assert(stopped);kernelExit=true;throw Exited{};}
''' + body(runtime, 'void Fatal(') + r'''
int main(){try{Fatal("regression");assert(false);}catch(const Exited&){}assert(kernelExit);puts("PASS fatal: kernel terminates the process without unmapping live thread stacks");}
'''
config_test = r'''
#define __3DS__ 1
#include <cassert>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <string>
#include <nlohmann/json.hpp>
unsigned errors=0;
#define SPDLOG_ERROR(...) (++errors)
namespace fs {
using std::filesystem::path;using std::filesystem::exists;using std::filesystem::is_regular_file;
bool failCommit=false,failRestore=false,failBackup=false,failCleanup=false;
bool remove(const path& p,std::error_code& ec) {
    if(failCleanup && p.extension()==".blinky-backup"){ec=std::make_error_code(std::errc::permission_denied);return false;}
    return std::filesystem::remove(p,ec);
}
void rename(const path& from,const path& to,std::error_code& ec) {
    // Model the SD failure reported by this console when a target exists.
    if(exists(to)){ec=std::make_error_code(std::errc::no_such_file_or_directory);return;}
    if((failCommit && from.extension()==".tmp") ||
       (failRestore && from.extension()==".blinky-backup") ||
       (failBackup && to.extension()==".blinky-backup")){
        ec=std::make_error_code(std::errc::io_error);return;
    }
    std::filesystem::rename(from,to,ec);
}
}
struct Config {
    std::string mPath="./settings.json";
    nlohmann::json mNestedJson, mFlattenedJson=nlohmann::json{{"/value",2}};
    bool mIsNewInstance=false;
    void Save();void Reload();
};
static void put(const char* file,int value){std::ofstream(file)<<"{\"value\":"<<value<<"}";}
static int get(const char* file){std::ifstream in(file);return nlohmann::json::parse(in).at("value");}
static void reset(){fs::failCommit=fs::failRestore=fs::failBackup=fs::failCleanup=false;for(auto name:{"settings.json","settings.json.tmp","settings.json.blinky-backup"})std::filesystem::remove(name);errors=0;}
''' + body(config, 'void Config::Save()') + '\n' + body(config, 'void Config::Reload()') + r'''
int main(){
    Config c;reset();c.Save();assert(get("settings.json")==2 && errors==0);
    put("settings.json",1);c.Save();assert(get("settings.json")==2 && errors==0);
    assert(!fs::exists("settings.json.blinky-backup"));
    reset();put("settings.json",1);fs::failCommit=true;c.Save();assert(get("settings.json")==1 && errors==1);
    reset();put("settings.json",1);fs::failBackup=true;c.Save();assert(get("settings.json")==1 && errors==1);
    reset();put("settings.json",1);fs::failCommit=fs::failRestore=true;c.Save();
    assert(!fs::exists("settings.json") && get("settings.json.blinky-backup")==1 && errors==2);
    fs::failCommit=fs::failRestore=false;c.Reload();assert(get("settings.json")==1 && c.mFlattenedJson.at("/value")==1);
    reset();put("settings.json.blinky-backup",3);c.Reload();assert(get("settings.json")==3);
    reset();put("settings.json",4);put("settings.json.blinky-backup",3);c.Reload();assert(c.mFlattenedJson.at("/value")==4);
    reset();put("settings.json",1);fs::failCleanup=true;c.Save();assert(get("settings.json")==1 && errors==1);
    reset();c.mPath="None";c.Save();assert(!fs::exists("None") && !fs::exists("None.tmp"));
    puts("PASS config: create, replace, failed commit/backup/restore, restart recovery, committed precedence, cleanup failure, disabled persistence");
}
'''

with tempfile.TemporaryDirectory(prefix='blinky-crash28-') as directory:
    directory = Path(directory)
    sdk = Path(os.environ.get('DEVKITPRO', 'C:/devkitPro' if os.name=='nt' else '/opt/devkitpro'))
    if os.name=='nt' and not sdk.is_dir():
        sdk = Path('C:/devkitPro')
    json_include = args.json_include or sdk/'portlibs/3ds/include'
    # Isolate the header-only library from ARM SDK C headers on the host.
    shutil.copytree(json_include/'nlohmann', directory/'nlohmann')
    for name, code in [('fatal', fatal_test), ('config', config_test)]:
        source, binary = directory/(name+'.cpp'), directory/(name+'.exe')
        source.write_text(code)
        subprocess.run([args.cxx,'-std=c++20','-O1','-Wall','-Wextra','-I',str(directory),str(source),'-o',str(binary)],check=True,env=env)
        subprocess.run([str(binary)],cwd=directory,env=env,check=True,timeout=30)
