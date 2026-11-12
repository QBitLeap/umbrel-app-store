"""Require anonymous access and the owner-accepted q20 image configuration."""
from hashlib import sha256
import json
import re
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,ProxyHandler,HTTPRedirectHandler,build_opener
from urllib.error import HTTPError

IMAGE_ID='sha256:0c1d5ce05023985360e4d92cd9fb12e2e0f36b59b327f4ad81be02c22bca9c1e'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*_):return None


def check(image):
    if not re.fullmatch(r'ghcr.io/qbitleap/q20@sha256:[0-9a-f]{64}',image):raise ValueError('Pinned q20 image required')
    repository,digest=image.removeprefix('ghcr.io/').split('@');opener=build_opener(ProxyHandler({}),NoRedirect())
    query=urlencode({'service':'ghcr.io','scope':'repository:'+repository+':pull'})
    with opener.open('https://ghcr.io/token?'+query,timeout=20) as response:token=json.load(response)['token']
    def get(route,expected):
        request=Request('https://ghcr.io/v2/'+repository+route,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json'})
        try:response=opener.open(request,timeout=20)
        except HTTPError as error:
            location=error.headers.get('Location','');target=urlsplit(location)
            if not route.startswith('/blobs/') or error.code not in (302,307) or target.scheme!='https' or target.hostname!='pkg-containers.githubusercontent.com' or target.username or target.password or target.fragment:raise
            # A signed CDN URL is fetched without the registry bearer header.
            response=opener.open(Request(location),timeout=20)
        with response:raw=response.read(4*1024*1024+1)
        if len(raw)>4*1024*1024 or 'sha256:'+sha256(raw).hexdigest()!=expected:raise ValueError('Public image content differs from digest')
        return json.loads(raw)
    manifest=get('/manifests/'+digest,digest)
    if manifest.get('config',{}).get('digest')!=IMAGE_ID:raise ValueError('Public image differs from owner-accepted runtime')
    config=get('/blobs/'+IMAGE_ID,IMAGE_ID)
    if config.get('architecture')!='amd64' or config.get('os')!='linux':raise ValueError('Unexpected native platform')
    return {'passed':True,'anonymousPullAccepted':True,'image':image,'imageId':IMAGE_ID}
