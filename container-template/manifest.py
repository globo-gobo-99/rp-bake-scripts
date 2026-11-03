import argparse,json,os,subprocess
from pathlib import Path
commands={'node':['node','--version'],'npm':['npm','--version'],'uv':['uv','--version'],'gh':['gh','--version'],'codex':['codex','--version'],'claude':['claude','--version'],'pi':['pi','--version'],'ob':['ob','--version'],'herdr':['herdr','--version'],'tuios':['tuios','--version'],'tailscale':['tailscale','version'],'tailscaled':['tailscaled','--version'],'docker':['docker','--version'],'caddy':['caddy','version'],'python':['python3','--version'],'tmux':['tmux','-V']}
parser=argparse.ArgumentParser()
parser.add_argument('--role',choices=['devpod','testpod'],default='devpod')
args=parser.parse_args()
if args.role=='testpod':
 commands={name:cmd for name,cmd in commands.items() if name in ['tailscale','tailscaled','caddy','docker','python','tmux']}
 commands['git']=['git','--version']
versions={}
for name,cmd in commands.items():
 r=subprocess.run(cmd,capture_output=True,text=True,timeout=40);versions[name]={'exit':r.returncode,'version':(r.stdout+r.stderr).strip().splitlines()[:4]}
 if r.returncode:raise RuntimeError('Tool smoke failed: '+name+' '+r.stderr[:200])
manifest={'role':args.role,'tools':versions,'lock':json.loads(Path('/opt/devpod/tools.lock.json').read_text()),'os_packages':subprocess.check_output(['dpkg-query','-W','-f=${Package}=${Version}\n'],text=True).splitlines()}
Path('/opt/devpod/image-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
