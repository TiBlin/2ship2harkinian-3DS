#!/usr/bin/env python3
"""Extract and execute production AudioPlayback_ProcessNotes unchanged.

Host control-flow test, NOT hardware, PCM, ABI, or performance validation.
Dependencies: Python 3 and a host C++ compiler (CXX); fixed image base on Windows, non-PIE on Linux.
No file in the source tree is modified. One temporary variant changes ONLY the
preprocessor guard excluding the N64 address heuristic on __3DS__.
Usage: python tests/test_mm_note_address_gate.py /path/to/2Ship3DS --require-fixed
The historical negative control is retained even when production is fixed.
Both guards are also tested under Wii U and default-platform preprocessor settings.
"""
from pathlib import Path
import argparse, subprocess, tempfile, shutil, hashlib, json, os

def function(text, signature):
    start=text.index(signature); opening=text.index('{',start); depth=1; i=opening+1
    while depth:
        depth+=(text[i]=='{')-(text[i]=='}'); i+=1
    return text[start:i]

STUBS=r'''
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cmath>
using s32=int32_t; using u8=uint8_t; using f32=float;
struct Note; struct SequenceLayer;
struct StereoData { int type=0; };
struct NoteSubAttributes { float frequency=0,velocity=0; int pan=0,targetReverbVol=0;
 StereoData stereoData; int gain=0; void* filter=nullptr; int combFilterSize=0,
 combFilterGain=0,surroundEffectIndex=0; };
struct NoteAttributes { float freqScale=0,velocity=0; int pan=0,targetReverbVol=0;
 StereoData stereoData; int gain=0; void* filter=nullptr; int combFilterSize=0,
 combFilterGain=0,surroundEffectIndex=0; };
struct SequencePlayer { bool muted=false; };
struct SequenceChannel { SequencePlayer* seqPlayer=nullptr; unsigned muteFlags=0;
 StereoData stereoData; int targetReverbVol=0,gain=0; void* filter=nullptr;
 int combFilterSize=0,combFilterGain=0,surroundEffectIndex=0,bookOffset=0; };
struct SequenceLayer { Note* note=nullptr; bool enabled=true,bit1=false;
 SequenceChannel* channel=nullptr; float noteFreqScale=1,noteVelocity=1; int notePan=0,
 surroundEffectIndex=0,targetReverbVol=0; StereoData stereoData;
 struct {struct {int bit_2=0,bit_9=0;} s;} unk_0A; };
struct Adsr { struct {struct {bool release=false; int status=1;} s;} action;
 float fadeOutVel=0; };
struct NotePlaybackState { SequenceLayer* parentLayer=nullptr;
 SequenceLayer* wantedParentLayer=nullptr; int status=0,priority=2; Adsr adsr;
 NoteAttributes attributes; float vibratoFreqScale=1,portamentoFreqScale=1; };
struct NoteSampleState { struct {bool finished=false,enabled=false,needsInit=false;} bitField0;
 struct {u8 bookOffset=0;} bitField1; int harmonicIndexCurAndPrev=0; float observedFrequency=-7,observedVelocity=-7; };
struct AudioListItem; struct Pool { AudioListItem* unused=nullptr;
 int active=0,decaying=0,disabled=0;};
struct AudioListItem {Pool* pool=nullptr;};
struct Note {NotePlaybackState playbackState; NoteSampleState sampleState; AudioListItem listItem;};
#define NO_LAYER ((SequenceLayer*)(-1))
#define PLAYBACK_STATUS_0 0
#define PLAYBACK_STATUS_1 1
#define PLAYBACK_STATUS_2 2
#define ADSR_STATUS_DISABLED 0
#define MUTE_FLAGS_STOP_NOTES 1
#define MUTE_FLAGS_STOP_SAMPLES 2
struct Context {int numNotes=1,sampleStateOffset=0; Note notes[1]; NoteSampleState sampleStateList[1];
 struct {float updatesPerFrameInv=1.0f/3,resampleRate=1;} audioBufferParameters; } gAudioCtx;
int adsrCalls=0,vibratoCalls=0,initCalls=0;
float AudioEffects_UpdateAdsr(Adsr*) {++adsrCalls; return 0.5f;}
void AudioEffects_UpdatePortamentoAndVibrato(Note*) {++vibratoCalls;}
void AudioPlayback_InitSampleState(Note* note,NoteSampleState* target,NoteSubAttributes* attrs) {
 target->bitField0=note->sampleState.bitField0; // Same flag copy as real InitSampleState (playback.c:32).
 ++initCalls; target->observedFrequency=attrs->frequency; target->observedVelocity=attrs->velocity;
}
void unreachable() {std::fprintf(stderr,"unexpected test fixture branch\n");std::abort();}
void AudioScript_SequenceChannelDisable(SequenceChannel*) {unreachable();}
void AudioPlayback_SeqLayerNoteRelease(SequenceLayer*) {unreachable();}
void AudioPlayback_AudioListRemove(AudioListItem*) {unreachable();}
void AudioPlayback_AudioListPushFront(int*,AudioListItem*) {unreachable();}
void AudioPlayback_NoteDisable(Note*) {unreachable();}
void AudioPlayback_NoteInitForLayer(Note*,SequenceLayer*) {unreachable();}
void AudioEffects_InitVibrato(Note*) {unreachable();}
void AudioEffects_InitPortamento(Note*) {unreachable();}
void AudioScript_AudioListPushBack(int*,AudioListItem*) {unreachable();}
'''
MAIN=r'''
static SequenceLayer layer; static SequenceChannel channel; static SequencePlayer player;
void check(bool value,const char* message) {if(!value){std::fprintf(stderr,"FAIL %s\n",message);std::exit(1);}}
void reset() {
 gAudioCtx=Context{}; adsrCalls=vibratoCalls=initCalls=0;
 layer=SequenceLayer{}; channel=SequenceChannel{}; player=SequencePlayer{};
 layer.channel=&channel; channel.seqPlayer=&player; layer.note=&gAudioCtx.notes[0];
 gAudioCtx.notes[0].playbackState.parentLayer=&layer;
 gAudioCtx.notes[0].playbackState.wantedParentLayer=NO_LAYER;
 gAudioCtx.notes[0].sampleState.bitField0.enabled=true;
 gAudioCtx.notes[0].sampleState.bitField0.needsInit=true;
}
int main() {
 reset();check((uintptr_t)&layer < 0x7FFFFFFF,"test requires a real low-address layer (-no-pie)");
 layer.noteFreqScale=2.0f;layer.noteVelocity=0.8f;
 AudioPlayback_ProcessNotes();
 if(EXPECT_SKIP) {
  check(initCalls==0 && adsrCalls==0 && vibratoCalls==0,"original must skip all note updates");
  check(gAudioCtx.sampleStateList[0].observedFrequency==-7,"original must leave stale state");
 } else {
  check(initCalls==1 && adsrCalls==1 && vibratoCalls==1,"variant must update valid low-address note");
  check(gAudioCtx.sampleStateList[0].observedFrequency==2.0f,"variant must propagate pitch");
  check(std::fabs(gAudioCtx.sampleStateList[0].observedVelocity-0.4f)<1e-6,"variant must apply ADSR");
 }
 std::printf("%s active layer=%p adsr=%d vibrato=%d state_writes=%d frequency=%g velocity=%g\n",
 LABEL,(void*)&layer,adsrCalls,vibratoCalls,initCalls,
 gAudioCtx.sampleStateList[0].observedFrequency,gAudioCtx.sampleStateList[0].observedVelocity);
 AudioSynth_SyncSampleStates(0);
 check(!gAudioCtx.notes[0].sampleState.bitField0.needsInit,"Sync consumes needsInit in either variant");
 check(gAudioCtx.sampleStateList[0].bitField0.needsInit==!EXPECT_SKIP,"init signal lost only with original guard");
 std::printf("%s after real Sync: note_needsInit=%d slice_needsInit=%d slice_enabled=%d\n",LABEL,
 gAudioCtx.notes[0].sampleState.bitField0.needsInit,gAudioCtx.sampleStateList[0].bitField0.needsInit,
 gAudioCtx.sampleStateList[0].bitField0.enabled);
 layer.noteFreqScale=0.5f;AudioPlayback_ProcessNotes();
 check(initCalls==(EXPECT_SKIP?0:2),"repeated active update count");
 check(gAudioCtx.sampleStateList[0].observedFrequency==(EXPECT_SKIP?-7:0.5f),"pitch change propagation");
 reset();gAudioCtx.notes[0].playbackState.parentLayer=NO_LAYER;
 gAudioCtx.notes[0].playbackState.status=PLAYBACK_STATUS_2;
 gAudioCtx.notes[0].playbackState.attributes.freqScale=1.5f;
 AudioPlayback_ProcessNotes();
 check(initCalls==1 && adsrCalls==1,"NO_LAYER release path must remain reachable");
 check(gAudioCtx.sampleStateList[0].observedFrequency==1.5f,"released note pitch unaffected");
 std::printf("%s NO_LAYER release: state_writes=%d frequency=%g PASS\n",LABEL,initCalls,
 gAudioCtx.sampleStateList[0].observedFrequency);
}
'''
def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path,nargs='?',default=Path(__file__).resolve().parents[1])
    p.add_argument('--cxx',default=os.environ.get('CXX','g++'))
    p.add_argument('--require-fixed',action='store_true',help='Fail if production still has the broken __3DS__ gate')
    args=p.parse_args()
    src=args.root/'third_party/2ship/mm/src/audio/lib/playback.c'
    text=src.read_text(encoding="utf-8"); body=function(text,'void AudioPlayback_ProcessNotes(void)')
    sync=function((args.root/'third_party/2ship/mm/src/audio/lib/synthesis.c').read_text(encoding="utf-8"),'void AudioSynth_SyncSampleStates(s32 updateIndex)')
    legacy='#ifndef __WIIU__'; fixed='#if !defined(__WIIU__) && !defined(__3DS__)'
    if body.count(legacy)==1:
        original=body; candidate=body.replace(legacy,fixed); production_is_fixed=False
    elif body.count(fixed)==1:
        original=body.replace(fixed,legacy); candidate=body; production_is_fixed=True
    else:raise SystemExit('Unexpected source: inspect guard manually')
    if args.require_fixed and not production_is_fixed:raise SystemExit('FAIL: production __3DS__ still excludes valid low-address notes')
    compiler=shutil.which(args.cxx)
    if not compiler:raise SystemExit('g++ is required')
    env=dict(os.environ);env['PATH']=str(Path(compiler).parent)+os.pathsep+env.get('PATH','')
    print('Source SHA256:',hashlib.sha256(src.read_bytes()).hexdigest(),flush=True)
    print('Production guard:', 'fixed' if production_is_fixed else 'BROKEN (reproduction mode)',flush=True)
    variants=[('original_3ds_control',original,['-D__3DS__=1'],1),
              ('fixed_guard_3ds_control',candidate,['-D__3DS__=1'],0),
              ('original_wiiu_control',original,['-D__WIIU__=1'],0),
              ('fixed_guard_wiiu_control',candidate,['-D__WIIU__=1'],0),
              ('original_other_platform_control',original,[],1),
              ('fixed_guard_other_platform_control',candidate,[],1)]
    with tempfile.TemporaryDirectory() as td:
        for name,code,defines,skip in variants:
            cpp=Path(td)/(name+'.cpp');exe=Path(td)/(name+('.exe' if os.name=='nt' else ''))
            cpp.write_text(f'#define EXPECT_SKIP {skip}\n#define LABEL "{name}"\n'+STUBS+code+sync+MAIN)
            address_flags=['-Wl,--image-base,0x400000,--disable-dynamicbase'] if os.name=='nt' else ['-fno-pie','-no-pie']
            subprocess.run([compiler,'-std=c++17','-O2',*address_flags,*defines,str(cpp),'-o',str(exe)],check=True,env=env)
            subprocess.run([str(exe)],check=True,env=env)
    print('PASS: actual ProcessNotes control flow; low-address active/repeated/release cases; no PCM/hardware claim.')
if __name__=='__main__':main()
