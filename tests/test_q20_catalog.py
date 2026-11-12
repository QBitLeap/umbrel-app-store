"""Independent q20 promotion must preserve existing apps and require all gates."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from q20_catalog import validate,promote,REQUIRED,IMAGE_ID


def publication():return {'published':True,'imageId':IMAGE_ID,'image':'ghcr.io/qbitleap/q20@sha256:'+'a'*64}
def integration():return {'passed':True,'imageId':IMAGE_ID,'networks':{'main':{'passed':True,'fixtureCleanupComplete':True,'cleanupErrors':[],'protocols':{'q20':{**{k:True for k in REQUIRED},'nativeCliVersion':'0.1.1','rulesFingerprint':'273ee09c9c5eae7c490fd594c58417baf9b78f9b35e15a1a2f1ca1fdd6d9cde6'}}}}}


class Q20CatalogTests(unittest.TestCase):
    def test_only_exact_published_image_with_complete_native_checks_is_accepted(self):
        self.assertEqual(validate(publication(),integration()),publication()['image'])
        for key in REQUIRED:
            value=integration();value['networks']['main']['protocols']['q20'][key]=False
            with self.subTest(key=key),self.assertRaises(ValueError):validate(publication(),value)
        for image in ['ghcr.io/qbitleap/q20:latest','ghcr.io/other/q20@sha256:'+'a'*64]:
            with self.assertRaises(ValueError):validate({**publication(),'image':image},integration())
        value=integration();value['networks']['testnet4']=deepcopy(value['networks']['main'])
        with self.assertRaises(ValueError):validate(publication(),value)
    def test_cleanup_and_wrong_image_never_promote(self):
        for key,val in [('imageId','sha256:'+'b'*64),('passed',False)]:
            value=integration();value[key]=val
            with self.assertRaises(ValueError):validate(publication(),value)
        value=integration();value['networks']['main']['fixtureCleanupComplete']=False
        with self.assertRaises(ValueError):validate(publication(),value)
    def test_public_gate_and_promotion_touch_only_q20_and_reject_owner_edits(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);candidate=root/'candidate';candidate.mkdir();repo=root/'repo';repo.mkdir()
            existing=repo/'qbitleap-leap-main';existing.mkdir();(existing/'umbrel-app.yml').write_text('preserved')
            app=candidate/'qbitleap-q20-main';app.mkdir();(app/'umbrel-app.yml').write_text('q20')
            (candidate/'q20-catalog-manifest.json').write_text(json.dumps({'files':{'qbitleap-q20-main/umbrel-app.yml':sha256(b'q20').hexdigest()}}))
            with self.assertRaises(ValueError):promote(candidate,repo,False)
            self.assertFalse((repo/'qbitleap-q20-main').exists())
            promote(candidate,repo,True);self.assertEqual((existing/'umbrel-app.yml').read_text(),'preserved')
            (repo/'qbitleap-q20-main/umbrel-app.yml').write_text('owner change')
            with self.assertRaises(ValueError):promote(candidate,repo,True)
    def test_candidate_path_and_content_tampering_refuse(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);candidate=root/'candidate';candidate.mkdir();repo=root/'repo';repo.mkdir()
            for relative in ['../escape','qbitleap-core-main/umbrel-app.yml','images.lock.json']:
                (candidate/'q20-catalog-manifest.json').write_text(json.dumps({'files':{relative:'0'*64}}))
                with self.assertRaises(ValueError):promote(candidate,repo,True)
