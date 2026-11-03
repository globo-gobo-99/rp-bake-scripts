#!/usr/bin/env python3
"""Initialize a mounted private workspace without replacing human state."""
import json
import os
from pathlib import Path
import shutil
import subprocess

def verify_mount(root):
    if not root.is_dir() or subprocess.run(['mountpoint','-q',str(root)]).returncode:
        raise RuntimeError(f'Expected durable mount at {root}; refusing ephemeral bootstrap')

def initialize(root,seed,release):
    for name in ['home/dev','toolchains','toolchains/user','state','state/tailscale','vaults','vaults/gobo-vault']:
        (root/name).mkdir(parents=True,exist_ok=True)
    (root/'home').chmod(0o711)
    for name in ['home/dev','state','vaults']:
        (root/name).chmod(0o700)
    destination=root/'toolchains'/release
    if not destination.exists():
        staging=root/'toolchains'/('.'+release+'.staging')
        if staging.exists():shutil.rmtree(staging)
        shutil.copytree(seed,staging,symlinks=True)
        staging.rename(destination)
    current=root/'toolchains/current'
    if not current.exists():current.symlink_to(release,target_is_directory=True)
    home=root/'home/dev'
    defaults={'.bashrc':'source /etc/devpod-env\n', '.profile':'source /etc/devpod-env\n',
              '.tmux.conf':Path('/opt/devpod/tmux.conf').read_text() if Path('/opt/devpod/tmux.conf').exists() else 'set -g base-index 1\nsetw -g pane-base-index 1\nset -g renumber-windows on\n'}
    for name,content in defaults.items():
        p=home/name
        if not p.exists():p.write_text(content)
    return home

if __name__=='__main__':
    if os.geteuid()!=1000:raise RuntimeError('Bootstrap must create persistent files directly as developer UID 1000')
    root=Path('/workspace'); verify_mount(root)
    lock=json.loads(Path('/opt/devpod/tools.lock.json').read_text())
    initialize(root,Path('/opt/devpod/seed'),lock['release'])
