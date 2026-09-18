#!/usr/bin/env python3
"""Generate a C11 aligned shader byte array and its C/C++ declaration."""
import argparse
from pathlib import Path
import re

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('symbol')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', args.symbol):
        parser.error('symbol must be a C identifier')
    data = args.input.read_bytes()
    if not data:
        parser.error('cannot embed an empty shader')
    values = list(data) + [0] * (-len(data) % 4)
    rows = ['    ' + ','.join(map(str, values[n:n+16])) + ',' for n in range(0, len(values), 16)]
    declaration = f'const unsigned char {args.symbol}'
    args.output.write_text('\n'.join([
        '/* Generated shader data. */',
        f'_Alignas(4) {declaration}[] = {{', *rows, '};',
        f'const unsigned int {args.symbol}_size = {len(data)};', '']), encoding='ascii')
    args.output.with_suffix('.h').write_text('\n'.join([
        '#pragma once', '#ifdef __cplusplus', 'extern "C" {', '#endif',
        f'extern {declaration}[];', f'extern const unsigned int {args.symbol}_size;',
        '#ifdef __cplusplus', '}', '#endif', '']), encoding='ascii')

if __name__ == '__main__':
    main()
