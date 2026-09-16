#!/usr/bin/env python3
"""Run the host checks maintained for this MM port (requires host g++ via CXX)."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TESTS = (
    'test_2ship_preflight.py', 'test_mm_control_merge.py',
    'test_2ship_native_controls.py', 'test_context_teardown_3ds.py',
    'test_mm_3ds_timing_audio.py', 'test_mm_audio_specs.py', 'test_mm_adpcm_boundaries.py',
    'test_mm_mixer_effects.py',
    'test_2ship_extension_index.py', 'test_2ship_scene_eviction.py', 'stereo_3ds_test.py',
    'mono_interpreter_test.py', 'mm_actor_stereo_test.py',
)

if __name__ == '__main__':
    compiler = shutil.which(os.environ.get('CXX', 'g++'))
    if not compiler:
        sys.exit('Set CXX to a host C++ compiler, not arm-none-eabi-g++.')
    env = os.environ.copy()
    env['CXX'] = compiler
    env['PATH'] = str(Path(compiler).parent) + os.pathsep + env.get('PATH', '')
    for test in TESTS:
        print(f'Checking {test}', flush=True)
        subprocess.run([sys.executable, str(ROOT / 'tests' / test)], cwd=ROOT, env=env, check=True)
    print('All host checks passed. GPU output, gameplay and physical hardware require separate validation.')
