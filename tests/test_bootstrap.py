import importlib.util
from pathlib import Path
import tempfile
import unittest

class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'workspace';self.root.mkdir()
        self.seed=Path(self.tmp.name)/'seed';self.seed.mkdir()
        spec=importlib.util.spec_from_file_location('bootstrap',Path(__file__).parents[1]/'container-template/bootstrap.py')
        self.mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.mod)
    def test_unmounted_workspace_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'mount'):
            self.mod.verify_mount(self.root)
    def test_seed_preserves_user_changes_and_existing_tool_release(self):
        (self.seed/'bin').mkdir();(self.seed/'bin/tool').write_text('version1')
        self.mod.initialize(self.root,self.seed,'r1')
        home=self.root/'home/dev';(home/'.bashrc').write_text('human edits')
        (self.root/'toolchains/r1/bin/tool').write_text('user tool state')
        (self.seed/'bin/tool').write_text('updated seed')
        self.mod.initialize(self.root,self.seed,'r1')
        self.assertEqual((home/'.bashrc').read_text(),'human edits')
        self.assertEqual((self.root/'toolchains/r1/bin/tool').read_text(),'user tool state')
        self.assertEqual((self.root/'toolchains/current').resolve(),self.root/'toolchains/r1')
    def test_new_release_does_not_silently_upgrade_existing_home(self):
        self.mod.initialize(self.root,self.seed,'r1')
        self.mod.initialize(self.root,self.seed,'r2')
        self.assertEqual((self.root/'toolchains/current').resolve(),self.root/'toolchains/r1')
        self.assertTrue((self.root/'vaults/gobo-vault').is_dir())
    def test_private_state_permissions(self):
        self.mod.initialize(self.root,self.seed,'r1')
        for p in ['home/dev','state','vaults']:
            self.assertEqual((self.root/p).stat().st_mode & 0o777,0o700)

if __name__=='__main__':unittest.main()
