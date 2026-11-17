"""Consume verified Core image receipts; promote only Core entries after full integration.
Scheduled GitHub runner only: never installs or updates an owner's Umbrel instance.
"""
import argparse,hashlib,json,re,shutil
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from catalog import validate_images,accepted,promote
ROOT=Path(__file__).resolve().parents[1]
CORE_IDS=('qbitleap-core-main','qbitleap-core-testnet4')
def candidate(receipt,images,sources):
 if receipt.get('format')!='qbitleap-image-release-v1'or not re.fullmatch(r'v1\.\d+\.\d+',receipt.get('upstreamTag',''))or not re.fullmatch('[0-9a-f]{40}',receipt.get('sourceRevision','')):raise ValueError('Verified Core release receipt required')
 verification=receipt.get('upstreamVerification',{})
 if verification.get('upstreamTag')!=receipt['upstreamTag']or verification.get('signatureQuorum',0)<3 or len(set(verification.get('verifiedPrimarySigners',[])))<verification['signatureQuorum']:raise ValueError('Pinned upstream signature quorum receipt required')
 result=dict(images);seen=set()
 for row in receipt.get('images',[]):
  role={'qbit-core':'core','qbit-core-services':'services'}.get(row.get('component'))
  if role is None or role in seen or row.get('published')is not True or row.get('platform')!='linux/amd64'or row.get('sourceRevision')!=receipt['sourceRevision']:raise ValueError('Exact Core/services provenance required')
  seen.add(role);result[role]=row['image']
 if seen!={'core','services'}:raise ValueError('Both Core component receipts required')
 validate_images(result);new_sources=json.loads(json.dumps(sources));new_sources['apps']['qbit-core'].update(commit=receipt['sourceRevision'],packageCommit=receipt['sourceRevision'],repository='https://github.com/QBitLeap/qbit-core.git',imageSourceRepository='https://github.com/QBitLeap/qbit-core.git')
 return result,new_sources

def prepare():
 url='https://raw.githubusercontent.com/QBitLeap/qbit-core/main/releases/upstream/latest.json'
 try:
  with urlopen(Request(url,headers={'User-Agent':'QBitLeap-catalog-upstream'}),timeout=60)as response:raw=response.read(1048577)
 except HTTPError as exc:
  if exc.code==404:return None
  raise
 if len(raw)>1048576:raise ValueError('Core receipt budget')
 receipt=json.loads(raw);images=json.loads((ROOT/'images.lock.json').read_bytes());sources=json.loads((ROOT/'sources.lock.json').read_bytes());new_images,new_sources=candidate(receipt,images,sources)
 if new_images==images:return None
 out=ROOT/'.release/core-upstream';out.mkdir(parents=True,exist_ok=False)
 for name,value in [('images.json',new_images),('sources.json',new_sources),('receipt.json',receipt)]: (out/name).write_text(json.dumps(value,indent=2)+'\n')
 return receipt['upstreamTag'][1:]

def scope_catalog(generated,output,images,sources,acceptance):
 accepted(acceptance,images)
 if output.exists():raise ValueError('New Core scoped catalog staging required')
 old=json.loads((ROOT/'catalog-manifest.json').read_bytes());output.mkdir(parents=True)
 # Reconstitute existing managed catalog exactly; other apps are never regenerated.
 for name,digest in old['files'].items():
  path=Path(name);source=ROOT/path
  if path.is_absolute()or'..'in path.parts or source.is_symlink()or hashlib.sha256(source.read_bytes()).hexdigest()!=digest:raise ValueError('Concurrent catalog change; preserve it')
  target=output/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
 for app in CORE_IDS:
  target=output/app
  if target.exists():shutil.rmtree(target) # Owned disposable catalog staging only.
  shutil.copytree(generated/app,target)
 (output/'images.lock.json').write_text(json.dumps(images,sort_keys=True,indent=2)+'\n');(output/'acceptance.json').write_text(json.dumps(acceptance,sort_keys=True,indent=2)+'\n')
 files={p.relative_to(output).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in output.rglob('*')if p.is_file()}
 for name,digest in old['files'].items():
  if not name.startswith(tuple(app+'/'for app in CORE_IDS))and name not in('images.lock.json','acceptance.json')and files.get(name)!=digest:raise ValueError('Non-Core catalog entries changed')
 manifest={**old,'images':images,'sources':sources,'files':files};(output/'catalog-manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
 return manifest

if __name__=='__main__':
 import os
 p=argparse.ArgumentParser();p.add_argument('mode',choices=('prepare','promote'));a=p.parse_args();stage=ROOT/'.release/core-upstream'
 if a.mode=='prepare':
  version=prepare()
  if os.environ.get('GITHUB_OUTPUT'):
   with open(os.environ['GITHUB_OUTPUT'],'a')as f:f.write('changed='+str(version is not None).lower()+'\n'+('version='+version+'\n'if version else''))
  print(json.dumps({'changed':version is not None,'version':version}))
 else:
  images=json.loads((stage/'images.json').read_bytes());sources=json.loads((stage/'sources.json').read_bytes());acceptance=json.loads((stage/'acceptance.json').read_bytes());scoped=stage/'scoped';scope_catalog(stage/'generated',scoped,images,sources,acceptance);promote(scoped,ROOT);(ROOT/'sources.lock.json').write_text(json.dumps(sources,indent=2)+'\n');(ROOT/'core-upstream-acceptance.json').write_text(json.dumps({'sourceReceipt':json.loads((stage/'receipt.json').read_bytes()),'integration':acceptance},indent=2)+'\n')
