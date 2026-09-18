#!/usr/bin/env python3
"""Build the experimental 2Ship 3DS port, then produce installable containers."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'scripts'))
from build_lus_3ds import build_lus, build_environment, default_devkitpro
from build_clock import prepare_source_clock


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--devkitpro', type=Path, default=default_devkitpro())
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--output', type=Path, default=ROOT/'dist')
    parser.add_argument('--skip-lus', action='store_true', help='Use the existing matching LUS build')
    parser.add_argument('--no-package', action='store_true', help='Build only ELF and 3DSX')
    parser.add_argument('--emulator-safe', action='store_true', help='Skip the hardware CPU speed service')
    parser.add_argument('--memory-watch', action='store_true', help='Diagnostic: stop bulk writes over game-state pointers')
    args = parser.parse_args()
    if not 1 <= args.jobs <= 64:
        parser.error('--jobs must be between 1 and 64')
    started = time.time()
    build = ROOT/'build-arm'
    report = {'source': 'HarbourMasters/2ship2harkinian',
              'commit': '6bfd6a35a0e0d8900273e61ce85cb038d4f4a528',
              'version': '5.0.1', 'base': 'SoH3DS V7',
              'hardware_tested': False, 'gameplay_tested': False,
              'emulator_safe': args.emulator_safe, 'memory_watch': args.memory_watch, 'success': False}
    try:
        env, cmake, python = build_environment(args.devkitpro)
        clock = prepare_source_clock(ROOT)
        report['source_clock'] = clock
        if args.skip_lus and clock['changed_count']:
            print('Horodatages corriges : reconstruction LUS requise, --skip-lus ignore.', flush=True)
        if not args.skip_lus or clock['changed_count']:
            build_lus(args.devkitpro, args.jobs, clock_checked=True)
        lus = ROOT/'third_party/libultraship/build-3ds'
        if not (lus/'src/libultraship.a').is_file():
            raise RuntimeError('LUS not built. Run again without --skip-lus.')
        command = [str(cmake), '-S', str(ROOT), '-B', str(build), '-G', 'Ninja',
                   f'-DCMAKE_MAKE_PROGRAM={shutil.which("ninja", path=env["PATH"])}',
                   f'-DDEVKITPRO={args.devkitpro.resolve().as_posix()}',
                   f'-DCMAKE_TOOLCHAIN_FILE={(ROOT/"cmake/3DS.cmake").as_posix()}',
                   '-DCMAKE_BUILD_TYPE=Release', f'-DPython3_EXECUTABLE={python.as_posix()}',
                   f'-DTWOSHIP3DS_EMULATOR_SAFE={"ON" if args.emulator_safe else "OFF"}',
                   f'-DTWOSHIP3DS_MEMORY_WATCH={"ON" if args.memory_watch else "OFF"}']
        subprocess.run(command, env=env, check=True)
        subprocess.run([str(cmake), '--build', str(build), '--target', '2ship_3ds',
                        '--parallel', str(args.jobs)], env=env, check=True)
        if not args.no_package:
            subprocess.run([str(python), str(ROOT/'scripts/package_3ds.py'),
                            '--elf', str(build/'2ship-3ds.elf'), '--output', str(args.output),
                            '--devkitpro', str(args.devkitpro)],
                           env=env, check=True)
        report['success'] = True
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        report['error'] = str(error)
        print(f'2Ship 3DS build failed: {error}', file=sys.stderr)
    finally:
        report['elapsed_seconds'] = round(time.time() - started, 1)
        build.mkdir(exist_ok=True)
        (build/'build-report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
