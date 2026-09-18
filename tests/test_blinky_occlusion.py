"""Exercise the allocation-free production grid with independent geometry oracles."""
from pathlib import Path
import argparse,os,subprocess,tempfile
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--cxx',required=True);args=p.parse_args()
env=dict(os.environ);env['PATH']=str(Path(args.cxx).parent)+os.pathsep+env.get('PATH','')
with tempfile.TemporaryDirectory(prefix='blinky-occlusion-') as temp:
    binary=Path(temp)/'occlusion.exe'
    subprocess.run([args.cxx,'-std=c++20','-O2','-Wall','-Wextra','-I',str(root/'src/blinky'),str(root/'tests/blinky/occlusion.cpp'),'-o',str(binary)],check=True,env=env)
    subprocess.run([str(binary)],check=True,env=env,timeout=30)
