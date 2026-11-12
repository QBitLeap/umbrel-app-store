"""Stage/promote only q20's independently accepted community-store entry."""
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess

APP='qbitleap-q20-main'
IMAGE_ID='sha256:0c1d5ce05023985360e4d92cd9fb12e2e0f36b59b327f4ad81be02c22bca9c1e'
REQUIRED=('apiAuthenticationAccepted','readGatewayIntegrationAccepted','restartAccepted','fixtureDataSurvivedRestart','duplicateWriterRefused','wrongGenesisRejected','coreCookieAbsent','rawRpcNotReachable','publicationRouteAbsent','unsynchronizedProtectionRefused','coreAndGatewayRestartAccepted')


def validate(publication,integration):
    image=publication.get('image','')
    if publication.get('published') is not True or publication.get('imageId')!=IMAGE_ID or not re.fullmatch(r'ghcr.io/qbitleap/q20@sha256:[0-9a-f]{64}',image):raise ValueError('Published digest for exact accepted q20 image required')
    if integration.get('passed') is not True or integration.get('imageId')!=IMAGE_ID:raise ValueError('Accepted q20 image integration required')
    networks=integration.get('networks',{})
    if set(networks)!={'main'}:raise ValueError('Only the reviewed Mainnet profile is accepted')
    main=networks['main'];protocol=main.get('protocols',{}).get('q20',{})
    if not main.get('passed') or main.get('fixtureCleanupComplete') is not True or main.get('cleanupErrors') or any(protocol.get(k) is not True for k in REQUIRED):raise ValueError('Complete isolation/lifecycle/cleanup evidence required')
    if protocol.get('nativeCliVersion')!='0.1.1' or protocol.get('rulesFingerprint')!='273ee09c9c5eae7c490fd594c58417baf9b78f9b35e15a1a2f1ca1fdd6d9cde6':raise ValueError('Reviewed q20 version/rules required')
    return image


def assemble(output,source,publication,integration,revision):
    image=validate(publication,integration);output=Path(output);source=Path(source)
    if output.exists() or output.is_symlink() or not re.fullmatch(r'[0-9a-f]{40}',revision):raise ValueError('New output and pinned source commit required')
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()!=revision or subprocess.run(['git','diff','--quiet','HEAD'],cwd=source).returncode:raise ValueError('q20 package source differs from pinned commit')
    spec=importlib.util.spec_from_file_location('community_q20_package',source/'scripts/package_umbrel.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    output.mkdir(parents=True);module.package(output/APP,image)
    receipt={'passed':True,'version':'0.1.1','image':image,'imageId':IMAGE_ID,'sourceCommit':revision,'integration':integration,'publication':publication,'fullUmbrelInstallationAccepted':False,'realChainParityAccepted':False}
    (output/'q20-acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n')
    (output/'q20.sources.lock.json').write_text(json.dumps({'repository':'https://github.com/QBitLeap/q20.git','commit':revision,'image':image},indent=2)+'\n')
    manifest={'format':'qbitleap-q20-catalog-v1','image':image,'files':{p.relative_to(output).as_posix():sha256(p.read_bytes()).hexdigest() for p in output.rglob('*') if p.is_file()}}
    (output/'q20-catalog-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');return manifest


def promote(source,repository,anonymous_verified):
    if anonymous_verified is not True:raise ValueError('Anonymous image manifest/config verification required before promotion')
    source=Path(source);repository=Path(repository);manifest=json.loads((source/'q20-catalog-manifest.json').read_text())
    previous=repository/'q20-catalog-manifest.json';old=json.loads(previous.read_text())['files'] if previous.exists() else {}
    for relative in set(old)|set(manifest['files']):
        path=Path(relative)
        if path.is_absolute() or '..' in path.parts or not (path.parts[0]==APP or relative in ('q20-acceptance.json','q20.sources.lock.json')):raise ValueError('Unexpected q20 managed path')
        target=repository/path
        if any(p.is_symlink() for p in [target,*list(target.parents)[:len(path.parts)-1]]):raise ValueError('Linked catalog target refused')
        if target.exists() and (relative not in old or sha256(target.read_bytes()).hexdigest()!=old[relative]):raise ValueError('Existing q20 package differs; preserve it')
        if relative in manifest['files']:
            incoming=source/path
            if incoming.is_symlink() or sha256(incoming.read_bytes()).hexdigest()!=manifest['files'][relative]:raise ValueError('q20 candidate changed')
    for relative in set(old)-set(manifest['files']):(repository/relative).unlink()
    for relative in manifest['files']:
        target=repository/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/relative,target)
    shutil.copyfile(source/'q20-catalog-manifest.json',previous)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path);parser.add_argument('--source',type=Path,required=True);parser.add_argument('--revision',required=True);parser.add_argument('--integration',type=Path,required=True)
    args=parser.parse_args();publication=json.loads((args.source/'docs/validation/published-image-0.1.1.json').read_text());receipt=json.loads(args.integration.read_text())
    print(json.dumps(assemble(args.output,args.source,publication,receipt,args.revision),indent=2))
