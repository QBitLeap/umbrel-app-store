import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from catalog import source_repository,source_root,packaging_root,image_source_repository
class RepositoryLayoutTests(unittest.TestCase):
 def test_explicit_layout_preserves_protocol_roles(self):
  root=Path('/arbitrary-workspace')
  self.assertEqual(source_repository('leap'),'https://github.com/QBitLeap/LEAP.git')
  self.assertEqual(packaging_root(root,'leap'),root/'leap/umbrel')
  self.assertEqual(source_repository('pins'),'https://github.com/QBitLeap/pins-app.git')
  self.assertEqual(source_repository('qord'),'https://github.com/QBitLeap/qord-app.git')
  self.assertEqual(source_repository('qbit-core'),'https://github.com/QBitLeap/qbit-core.git')
  self.assertEqual(packaging_root(root,'pins'),root/'pins')
 def test_image_labels_remain_exact_legacy_or_canonical_provenance(self):
  source={'repository':source_repository('leap'),'imageSourceRepository':'https://github.com/QBitLeap/leap-umbrel.git'}
  self.assertEqual(image_source_repository('leap',source),source['imageSourceRepository'])
  self.assertEqual(image_source_repository('leap',{'repository':source_repository('leap')}),source_repository('leap'))
  with self.assertRaises(ValueError):image_source_repository('leap',{**source,'imageSourceRepository':'https://github.com/other/LEAP.git'})
