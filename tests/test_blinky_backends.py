"""Compile real Blinky TUs against host collaborators, then exercise contracts.

This checks lifecycle and ownership; it cannot certify PICA200 or DSP output.
The complete ARM build separately checks the real SDK/LUS interfaces.
"""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import argparse

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--cxx', default=shutil.which('g++'))
args = parser.parse_args()
if not args.cxx:
    raise SystemExit('A host C++ compiler is required')
fixtures = root / 'tests/blinky'
lus = root / 'third_party/libultraship'
environment = dict(os.environ)
environment['PATH'] = str(Path(args.cxx).parent) + os.pathsep + environment.get('PATH', '')
with tempfile.TemporaryDirectory(prefix='blinky-test-') as directory:
    for name, units in [('window',['fast/backends/gfx_blinky_3ds_window.cpp']),
                        ('audio',['ship/audio/BlinkyNdspAudioPlayer.cpp']),
                        ('lifecycle',['ship/port/3ds/BlinkyLifecycle.cpp',
                                      'fast/backends/gfx_blinky_3ds_window.cpp',
                                      'ship/audio/BlinkyNdspAudioPlayer.cpp'])]:
        binary = Path(directory) / (name + '.exe')
        subprocess.run([args.cxx,'-std=c++20','-Wall','-Wextra','-Werror','-O1','-pthread',
                        '-D__3DS__','-I',str(fixtures),'-I',str(lus/'include'),
                        *[str(lus/'src'/unit) for unit in units],
                        str(fixtures/(name+'.cpp')),'-o',str(binary)],
                       check=True,env=environment)
        subprocess.run([str(binary)],check=True,env=environment,timeout=30)
        print('PASS Blinky ' + name + ' contract/ownership scenarios',flush=True)
