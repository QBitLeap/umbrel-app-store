import copy,importlib.util,json,sys,tempfile,unittest,hashlib,shutil
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'));import core_upstream as m
class CoreUpstream(unittest.TestCase):
 def receipt(self):
  revision='a'*40
  receipt={'format':'qbitleap-image-release-v1','upstreamTag':'v1.0.1','sourceRevision':revision,'upstreamVerification':{'upstreamTag':'v1.0.1','signatureQuorum':3,'verifiedPrimarySigners':['1','2','3']},'images':[{'component':c,'published':True,'platform':'linux/amd64','sourceRevision':revision,'image':'ghcr.io/qbitleap/'+c+'@sha256:'+str(i)*64}for i,c in enumerate(('qbit-core','qbit-core-services'),1)]}
  targets=['macos-arm64','macos-x64','windows-x64','linux-x64','linux-arm64'];receipt['platformChecksPassed']=True;receipt['upstreamVerification']['platformArtifacts']={t:{'sha256':'a'*64}for t in targets};receipt['platformChecks']={t:{'target':t,'passed':True,'upstreamTag':'v1.0.1','archiveSha256':'a'*64,'nodeStarted':False,'installedDataAccessed':False}for t in targets};return receipt
 def test_only_core_images_and_source_change(self):
  images=json.loads((ROOT/'images.lock.json').read_bytes());sources=json.loads((ROOT/'sources.lock.json').read_bytes());result,new=m.candidate(self.receipt(),images,sources)
  for role in('leap','pins','qord'):self.assertEqual(result[role],images[role]);self.assertEqual(new['apps'][role],sources['apps'][role])
  self.assertEqual(new['apps']['qbit-core']['packageCommit'],'a'*40)
 def test_missing_duplicate_unpublished_or_wrong_provenance_refused(self):
  images=json.loads((ROOT/'images.lock.json').read_bytes());sources=json.loads((ROOT/'sources.lock.json').read_bytes())
  for mode in('missing','duplicate','unpublished','revision','quorum','network'):
   r=self.receipt()
   if mode=='missing':r['images'].pop()
   if mode=='duplicate':r['images'].append(r['images'][0])
   if mode=='unpublished':r['images'][0]['published']=False
   if mode=='revision':r['images'][0]['sourceRevision']='b'*40
   if mode=='quorum':r['upstreamVerification']['verifiedPrimarySigners']=['1','1','1']
   if mode=='network':r['upstreamTag']='v0.9.0'
   with self.subTest(mode=mode),self.assertRaises(ValueError):m.candidate(r,images,sources)
 def test_desktop_failures_do_not_block_umbrel_candidate(self):
  images=json.loads((ROOT/'images.lock.json').read_bytes());sources=json.loads((ROOT/'sources.lock.json').read_bytes());receipt=self.receipt();receipt.pop('platformChecks');receipt['upstreamVerification'].pop('platformArtifacts');receipt['platformChecksPassed']=False
  result,_=m.candidate(receipt,images,sources);self.assertNotEqual(result['core'],images['core'])
 def test_scoped_catalog_preserves_other_apps(self):
  with tempfile.TemporaryDirectory()as tmp:
   root=Path(tmp);generated=root/'generated';generated.mkdir();out=root/'scoped';files={}
   for app in(*m.CORE_IDS,'qbitleap-leap-main','qbitleap-pins-main','qbitleap-qord-main'):
    p=root/app/'keep';p.parent.mkdir();p.write_text('original '+app);files[p.relative_to(root).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    p=generated/app/'keep';p.parent.mkdir();p.write_text('changed '+app)
   for name in('images.lock.json','acceptance.json','core-broker-acceptance.json'):(root/name).write_text('{}');files[name]=hashlib.sha256(b'{}').hexdigest()
   (root/'catalog-manifest.json').write_text(json.dumps({'files':files}))
   with patch.object(m,'ROOT',root),patch.object(m,'accepted',return_value=None):manifest=m.scope_catalog(generated,out,{}, {},{})
   self.assertEqual((out/'qbitleap-leap-main/keep').read_text(),'original qbitleap-leap-main');self.assertEqual((out/'qbitleap-core-main/keep').read_text(),'changed qbitleap-core-main')
   m.promote(out,root);self.assertEqual((root/'core-broker-acceptance.json').read_text(),'{}')
   altered=json.loads((out/'catalog-manifest.json').read_bytes());altered['files']['core-broker-acceptance.json']='f'*64;(out/'catalog-manifest.json').write_text(json.dumps(altered))
   with self.assertRaises(ValueError):m.promote(out,root)
   (root/'qbitleap-leap-main/keep').write_text('concurrent work')
   with patch.object(m,'ROOT',root),patch.object(m,'accepted',return_value=None),self.assertRaises(ValueError):m.scope_catalog(generated,root/'second',{}, {},{})
if __name__=='__main__':unittest.main()
