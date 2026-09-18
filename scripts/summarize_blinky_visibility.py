#!/usr/bin/env python3
"""Summarize sampled Blinky visibility frames; does not infer a console speedup."""
import argparse
import json
import math
from pathlib import Path
import re
import statistics

def summarize(path):
    samples=[]
    for line in path.read_text(encoding='utf-8',errors='replace').splitlines():
        if 'Blinky visibility:' not in line:continue
        values={k:float(v) for k,v in re.findall(r'(\w+)=([0-9]+(?:\.[0-9]+)?)',line)}
        if 'frame_ms' in values and 'on' in values:samples.append(values)
    result={'log':str(path),'sampled_frames':len(samples),'hardware_verified_by_parser':False}
    for mode in (0,1):
        group=[s for s in samples if s['on']==mode]
        if not group:continue
        stats={}
        for key in sorted(set.intersection(*(set(s) for s in group)) - {'frame','on'}):
            v=sorted(s[key] for s in group)
            stats[key]={'median':statistics.median(v),'p95':v[max(0,math.ceil(.95*len(v))-1)],'mean':statistics.mean(v)}
        result['ON' if mode else 'OFF']={'samples':len(group),'metrics':stats}
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('logs',nargs='+',type=Path)
    print(json.dumps([summarize(path) for path in p.parse_args().logs],indent=2))
