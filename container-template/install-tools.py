#!/usr/bin/env python3
"""Fetch pinned public artifacts; never reads host configuration or credentials."""
import argparse,hashlib,io,json,os,shutil,subprocess,sys,tarfile,tempfile,urllib.request
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runtime-only',action='store_true',help='Install the small Test-Pod private networking/HTTP runtime only')
parser.add_argument('--lock',type=Path,default=Path('/opt/devpod/tools.lock.json'))
parser.add_argument('--seed',type=Path,default=Path('/opt/devpod/seed'))
args=parser.parse_args()
lock=json.loads(args.lock.read_text())
if args.runtime_only:
    for required in ['tailscale','caddy']:assert required in lock['artifacts'],required
seed=args.seed;(seed/'bin').mkdir(parents=True,exist_ok=True)
for name,artifact in lock['artifacts'].items():
    if args.runtime_only and name not in ['tailscale','caddy']:continue
    data=urllib.request.urlopen(artifact['url'],timeout=120).read()
    if hashlib.sha256(data).hexdigest()!=artifact['sha256']:raise RuntimeError('Checksum mismatch: '+name)
    if name in ['herdr','buildx']:
        dest=seed/'bin'/('docker-buildx' if name=='buildx' else name);dest.write_bytes(data);dest.chmod(0o755)
        continue
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:archive.extractall(tmp,filter='data')
        root=Path(tmp)
        if name=='node':
            folder=next(root.iterdir());shutil.copytree(folder,seed,dirs_exist_ok=True,symlinks=True)
        else:
            wanted={'uv':['uv','uvx'],'gh':['gh'],'tailscale':['tailscale','tailscaled'],'tuios':['tuios'],'docker':['docker'],'caddy':['caddy']}[name]
            for binary in wanted:
                source=next(p for p in root.rglob(binary) if p.is_file());shutil.copy2(source,seed/'bin'/binary)
                (seed/'bin'/binary).chmod(0o755)
if args.runtime_only:sys.exit(0)
env=os.environ.copy();env['PATH']=str(seed/'bin')+':'+env['PATH']
# npm's own CLI and app dependency graph are pinned independently of the Node bundle.
subprocess.run([str(seed/'bin/npm'),'install','--global','--prefix',str(seed),'npm@'+lock['npm_cli']],env=env,check=True)
for file in ['package.json','package-lock.json']:
    shutil.copy2('/opt/devpod/npm/'+file,seed/file)
subprocess.run([str(seed/'bin/npm'),'ci','--prefix',str(seed),'--ignore-scripts','--no-audit','--no-fund'],env=env,check=True)
# Claude's pinned wrapper ships a placeholder until its vendor postinstall selects
# the already locked platform package. Run this one reviewed script explicitly.
env['FAIL_ON_MISSING_NATIVE']='1'
subprocess.run([str(seed/'bin/node'),str(seed/'node_modules/@anthropic-ai/claude-code/install.cjs')],env=env,check=True)
for tool in ['codex','claude','pi','ob']:
    (seed/'bin'/tool).symlink_to('../node_modules/.bin/'+tool)
# Vendor Python is a relocatable user tool; distro Python remains the bootstrap prerequisite.
env['UV_PYTHON_INSTALL_DIR']=str(seed/'python')
subprocess.run([str(seed/'bin/uv'),'python','install',lock['python'],'--no-bin'],env=env,check=True)
python=next((seed/'python').glob('cpython-*/bin/python3'))
for name in ['python','python3']:
    (seed/'bin'/name).symlink_to(os.path.relpath(python,seed/'bin'))
plugin=seed/'lib/docker/cli-plugins';plugin.mkdir(parents=True);shutil.copy2(seed/'bin/docker-buildx',plugin/'docker-buildx')
