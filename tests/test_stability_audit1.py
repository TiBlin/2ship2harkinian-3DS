#!/usr/bin/env python3
"""Source-based host regressions for STABILITY-AUDIT1 (not an ARM build).

Compiles real MemoryStream/BinaryReader/Texture translation units. Compiles
extracted ResourceManager and XML-header methods with explicit collaborators,
and the real NDSP TU with a simulated SDK (pointer-sized host address type).
ASan/UBSan detect buffer errors. Controlled barriers model the publication race.
--baseline ROOT also requires the corresponding unpatched tests to FAIL. No
old assertion is relaxed. Tests are not a PCM/GPU/SD/hardware certification.
"""
from pathlib import Path
import argparse, json, os, shutil, subprocess, tempfile

CASES={
    'alias':['invalid-metadata','no-alias','valid'],
    'pins':['grass-lifetime','ramp-lifetime','grass-missing','ramp-missing','grass-short','ramp-short','ramp-disabled'],
    'binary':['bulk-oob','alloc-oob','uint32-oob','empty','failed-cursor','null-input',
              'write-accounting','overflow','valid-binary',
              'texture-v0-short','texture-v1-short','texture-v0-dimension','texture-v1-dimension',
              'texture-v0-zero','texture-v1-zero','texture-v0-valid','texture-v1-valid'],
    'manager':['publication','transient-read','transient-import','absent','cache-hit',
               'late-failure','destructor-lock','cache-report-empty','cache-report-content','cache-report-concurrent'],
    'ndsp':['flush-failure','close-before-buffered','valid-submit','pool-capacity','init-failure','allocation-failure'],
    'xml':['null-document','no-root','root-present']}
NEGATIVE={
    'alias':['invalid-metadata'],
    'pins':['grass-lifetime','ramp-lifetime'],
    'binary':['bulk-oob','alloc-oob','uint32-oob','empty','failed-cursor','write-accounting',
              'texture-v0-short','texture-v1-short','texture-v0-dimension','texture-v1-dimension',
              'texture-v0-zero','texture-v1-zero'],
    'manager':['publication','transient-read','transient-import','cache-report-empty','cache-report-concurrent'],
    'ndsp':['flush-failure','close-before-buffered'],
    'xml':['null-document','no-root']}

def extract(text,signature):
    start=text.index(signature);brace=text.index('{',start);depth=1;end=brace+1
    # These selected function bodies contain balanced braces in log strings.
    while depth:
        if end>=len(text):raise ValueError('Unterminated '+signature)
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('root',nargs='?',type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument('--baseline',type=Path)
    ap.add_argument('--cxx',default=os.getenv('AUDIT_CXX') or shutil.which('clang++') or 'g++')
    ap.add_argument('--output',type=Path)
    args=ap.parse_args();root=args.root.resolve();fixtures=Path(__file__).resolve().parent/'stability_audit1'
    cxx=shutil.which(args.cxx)
    if not cxx:raise SystemExit('Host C++20 compiler not found: '+args.cxx)
    records=[]
    def run(cmd,timeout=60):
        env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:abort_on_error=0',UBSAN_OPTIONS='halt_on_error=1')
        return subprocess.run([str(x) for x in cmd],capture_output=True,text=True,timeout=timeout,env=env)
    with tempfile.TemporaryDirectory(prefix='2ship-audit1-') as temp:
        tmp=Path(temp);fake=tmp/'include';(fake/'spdlog').mkdir(parents=True)
        (fake/'spdlog/spdlog.h').write_text('#pragma once\n'+'\n'.join('#define SPDLOG_'+name+'(...) ((void)0)' for name in ['TRACE','INFO','WARN','ERROR','DEBUG','CRITICAL']))
        (fake/'ship/audio').mkdir(parents=True)
        shutil.copyfile(fixtures/'fake_audio_player.h',fake/'ship/audio/AudioPlayer.h')
        shutil.copyfile(fixtures/'fake_3ds.h',fake/'3ds.h')
        def build(source_root,tag):
            lus=source_root/'third_party/libultraship';inc=lus/'include';src=lus/'src';result={}
            flags=[cxx,'-std=c++20','-g','-O1','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer','-I',str(fake),'-I',str(inc)]
            def compile(group,units,extra=()):
                exe=tmp/(tag+'-'+group);cmd=flags+list(extra)+[str(u) for u in units]+['-o',str(exe)]
                p=run(cmd);assert p.returncode==0,'Compile failed:\n'+' '.join(cmd)+'\n'+p.stdout+p.stderr
                result[group]=exe
            compile('binary',[fixtures/'binary.cpp',src/'ship/utils/binarytools/Stream.cpp',src/'ship/utils/binarytools/MemoryStream.cpp',src/'ship/utils/binarytools/BinaryReader.cpp',src/'ship/resource/Resource.cpp',src/'ship/resource/ResourceFactoryBinary.cpp',src/'fast/resource/factory/TextureFactory.cpp',src/'fast/resource/type/Texture.cpp'])
            manager=(src/'ship/resource/ResourceManager.cpp').read_text()
            fixed='ResourceManager::PublishResourceLoad(' in manager
            cpp=tmp/(tag+'-manager.cpp')
            body=extract(manager,'std::shared_ptr<IResource> ResourceManager::LoadResourceProcess(const ResourceIdentifier&')
            if fixed:body+='\n'+extract(manager,'std::shared_ptr<IResource> ResourceManager::PublishResourceLoad(')
            report=extract(manager,'void ResourceManager::Soh3dsCacheReport(')
            # Test-only scheduling point: another thread tries eviction after
            # collection, before formatting. Only the hook call is injected.
            report=report.replace('    // Largest buckets first, then format as many as fit.',
                                  '    if (reportPoint) reportPoint();\n    // Largest buckets first, then format as many as fit.')
            body+='\n'+report
            cpp.write_text((fixtures/'manager_pre.cpp').read_text()+body+(fixtures/'manager_post.cpp').read_text())
            compile('manager',[cpp],['-DAUDIT_FIXED'] if fixed else [])
            cpp=tmp/(tag+'-ndsp.cpp')
            # Include the unchanged production TU: namespace-local diagnostics are also testable.
            cpp.write_text('#include "'+(src/'ship/audio/NdspAudioPlayer.cpp').as_posix()+'"\n'+(fixtures/'ndsp_post.cpp').read_text())
            compile('ndsp',[cpp],['-D__3DS__'])
            cpp=tmp/(tag+'-xml.cpp')
            loader=(src/'ship/resource/ResourceLoader.cpp').read_text()
            body=extract(loader,'std::shared_ptr<ResourceInitData>\nResourceLoader::ReadResourceInitDataXml(')
            cpp.write_text((fixtures/'xml_pre.cpp').read_text()+body+(fixtures/'xml_post.cpp').read_text())
            compile('xml',[cpp])
            cpp=tmp/(tag+'-alias.cpp')
            body=extract(loader,'std::shared_ptr<ResourceInitData> ResourceLoader::ResolveMetaAlias(')
            cpp.write_text((fixtures/'alias_pre.cpp').read_text()+body+(fixtures/'alias_post.cpp').read_text())
            compile('alias',[cpp])
            gfx=(source_root/'third_party/2ship/mm/2s2h/Enhancements/GfxPatcher/AuthenticGfxPatches.cpp').read_text()
            cpp=tmp/(tag+'-pins.cpp')
            body=extract(gfx,'void PatchGeometrySeams(')+'\n'+extract(gfx,'void GfxPatcher_ApplyFierceDeityGIPatch(')
            cpp.write_text((fixtures/'pins_pre.cpp').read_text()+body+(fixtures/'pins_post.cpp').read_text())
            compile('pins',[cpp])
            return result
        for tag,source_root,groups,negative in [('fixed',root,CASES,False)]+([('baseline',args.baseline.resolve(),NEGATIVE,True)] if args.baseline else []):
            exes=build(source_root,tag)
            for group,cases in groups.items():
                for case in cases:
                    p=run([exes[group],case],timeout=15)
                    passed=p.returncode!=0 if negative else p.returncode==0
                    # A timeout or compile failure is NOT a reproduced failure.
                    if negative and case in ['bulk-oob','alloc-oob','uint32-oob']:
                        passed=passed and 'heap-buffer-overflow' in p.stderr
                    if negative and group=='pins':
                        passed=passed and 'heap-use-after-free' in p.stderr
                    if negative and case=='cache-report-concurrent':
                        passed=passed and ('heap-use-after-free' in p.stderr or 'std::string(out)' in p.stderr)
                    if negative and group=='manager' and case=='publication':
                        passed=passed and ('a && a==b' in p.stderr)
                    entry={'source':tag,'group':group,'case':case,'returncode':p.returncode,'expected_failure':negative,'passed':passed,'stdout':p.stdout,'stderr':p.stderr}
                    records.append(entry)
                    if args.output:args.output.write_text(json.dumps(records,indent=2),encoding='utf-8')
                    print(('PASS ' if passed else 'FAIL ')+tag+' '+group+'/'+case,flush=True)
                    if not passed:raise AssertionError(p.stdout+p.stderr)
    print(f'PASS {len(records)} cases; host-only. No ARM, real archive, DSP, SD or console validation.')
    return 0
if __name__=='__main__':raise SystemExit(main())
