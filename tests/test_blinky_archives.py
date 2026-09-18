"""Compile the actual native ZIP TU against fault-injecting public API collaborators."""
from pathlib import Path
import argparse, os, subprocess, tempfile

root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--cxx',required=True);args=p.parse_args()
env=dict(os.environ);env['PATH']=str(Path(args.cxx).parent)+os.pathsep+env.get('PATH','')
with tempfile.TemporaryDirectory(prefix='blinky-archives-') as folder:
    folder=Path(folder);exe=folder/'zip.exe'
    subprocess.run([args.cxx,'-std=c++20','-O1','-pthread','-D__3DS__','-I',str(root/'tests/blinky/archives'),str(root/'third_party/libultraship/src/ship/resource/archive/BlinkyO2rArchive.cpp'),str(root/'tests/blinky/archives/zip.cpp'),'-o',str(exe)],check=True,env=env)
    subprocess.run([str(exe)],cwd=folder,check=True,env=env,timeout=60)
    source=(root/'third_party/libultraship/src/ship/resource/archive/ArchiveManager.cpp').read_text()
    signatures=['const ArchiveManager::IndexedPath* ArchiveManager::FindPath(',
        'void ArchiveManager::RebuildIndex(', 'bool ArchiveManager::HasFile(uint64_t',
        'std::shared_ptr<File> ArchiveManager::LoadFile(uint64_t',
        'std::shared_ptr<Archive> ArchiveManager::GetArchiveFromFile(',
        'int32_t ArchiveManager::GetFilePriority(', 'const std::string* ArchiveManager::HashToString(',
        'std::shared_ptr<std::vector<std::string>> ArchiveManager::ListFiles(const std::list',
        'bool ArchiveManager::WriteFile(']
    methods=[]
    for signature in signatures:
        start=source.index(signature);end=source.index('{',start)+1;depth=1
        while depth:
            depth+=(source[end]=='{')-(source[end]=='}');end+=1
        methods.append(source[start:end])
    unit=folder/'index.cpp'
    unit.write_text((root/'tests/blinky/archives/index.cpp').read_text().replace('// TEST_METHODS','\n'.join(methods)))
    exe=folder/'index.exe'
    subprocess.run([args.cxx,'-std=c++20','-O1',str(unit),'-o',str(exe)],check=True,env=env)
    subprocess.run([str(exe)],check=True,env=env,timeout=60)
