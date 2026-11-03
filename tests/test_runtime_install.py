import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1]/'container-template/install-tools.py'


class RuntimeInstallTests(unittest.TestCase):
    def test_runtime_seed_verifies_artifacts_without_installing_agents(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            artifacts={}
            for package,binaries in {'tailscale':['tailscale','tailscaled'],'caddy':['caddy']}.items():
                archive=root/(package+'.tar.gz')
                with tarfile.open(archive,'w:gz') as tar:
                    for binary in binaries:
                        data=b'#!/bin/sh\nprintf fixture-runtime\n'
                        member=tarfile.TarInfo(package+'/'+binary);member.size=len(data);member.mode=0o755
                        tar.addfile(member,io.BytesIO(data))
                artifacts[package]={'url':archive.as_uri(),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
            artifacts['node']={'url':'file:///must-not-be-downloaded','sha256':'not-used'}
            lock=root/'lock.json';lock.write_text(json.dumps({'artifacts':artifacts}))
            seed=root/'seed'
            args=[sys.executable,str(SCRIPT),'--runtime-only','--lock',str(lock),'--seed',str(seed)]
            result=subprocess.run(args,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual({p.name for p in (seed/'bin').iterdir()},{'tailscale','tailscaled','caddy'})
            artifacts['tailscale']['sha256']='0'*64
            lock.write_text(json.dumps({'artifacts':artifacts}))
            result=subprocess.run(args[:-1]+[str(root/'bad-seed')],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse((root/'bad-seed/bin/tailscale').exists())


if __name__=='__main__':
    unittest.main()
