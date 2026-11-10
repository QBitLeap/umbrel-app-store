"""Owned empty-chain integration tests for pinned standalone app images."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
import uuid

GENESIS = {
 "main": "0000000000004d60aa5d46013991d0a0e2995d89ee98e53068ae196d763e79f2",
 "testnet4": "000000000000796fe86bbc0bf1b66a07e4b4c0676f74b54cf7e5ce8b3f1a0090",
}
PURPOSE = "standalone-app-fixture"

class Docker:
 def __init__(self): self.prefix=["docker", "--host", "unix:///var/run/docker.sock"]
 def call(self,args,timeout=30,check=True):
  value=subprocess.run(self.prefix+args,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
  if check and value.returncode: raise RuntimeError("Docker operation failed: "+value.stderr.strip()[:2000])
  return value
 def inspect(self,kind,name): return json.loads(self.call([kind,"inspect",name]).stdout)[0]
 def ensure_image(self,image):
  if self.call(["image","inspect",image],check=False).returncode:
   self.call(["pull",image],timeout=300)

def fixture_mounts_only(mounts, volumes):
    return all((m.get("Type") == "volume" and m.get("Name") in volumes
                and m.get("Destination") in {"/data", "/auth"})
               or (m.get("Type") == "tmpfs" and m.get("Destination") == "/tmp")
               for m in mounts)

class Fixture:
    def __init__(self, docker, images, chain):
        self.docker, self.images, self.chain = docker, images, chain
        self.run_id = uuid.uuid4().hex
        self.prefix = "qbitleap-fixture-" + self.run_id[:12]
        self.containers, self.volumes = [], []
        self.network = None

    def labels(self):
        return ["--label", "qbitleap.run=" + self.run_id, "--label", "qbitleap.purpose=" + PURPOSE]

    def volume(self, name):
        name = self.prefix + "-" + name
        if self.docker.call(["volume", "inspect", name], check=False).returncode == 0:
            raise RuntimeError("Fixture volume exists; preserve it")
        self.docker.call(["volume", "create", *self.labels(), name])
        self.volumes.append(name)
        return name

    def start(self, suffix, image, command, environment, *, share=None, volumes=(), memory="512m"):
        self.docker.ensure_image(image)
        name = self.prefix + "-" + suffix
        if self.docker.call(["container", "inspect", name], check=False).returncode == 0:
            raise RuntimeError("Fixture container exists; preserve it")
        args = ["run", "--detach", "--init", "--pull=never", "--name", name, *self.labels(),
                "--network", "container:" + share if share else self.network,
                "--read-only", "--user", "1000:1000", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges=true", "--pids-limit", "256",
                "--cpus", "2", "--memory", memory, "--memory-swap", memory,
                "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=64m,mode=1777"]
        for key, value in environment.items():
            args += ["--env", key + "=" + value]
        for volume, target, readonly in volumes:
            if volume not in self.volumes or target not in {"/data", "/auth"}:
                raise RuntimeError("Unexpected fixture mount")
            args += ["--mount", "type=volume,src=" + volume + ",dst=" + target + (",readonly" if readonly else "")]
        self.containers.append(name)
        self.docker.call(args + [image, *command])
        info = self.docker.inspect("container", name)
        host = info["HostConfig"]
        if (info["Config"].get("User") != "1000:1000" or host.get("Binds") or host.get("Privileged")
                or host.get("PortBindings") or not host.get("ReadonlyRootfs") or host.get("Init") is not True
                or "ALL" not in host.get("CapDrop", [])
                or not fixture_mounts_only(info.get("Mounts", []), self.volumes)):
            raise RuntimeError("Fixture isolation differs")
        return name

    def probe(self, container, url, *, body=None, role=None, token_env=None):
        # Credentials are read inside the owned container and never printed.
        code = """import os,json,base64
from urllib.request import Request,urlopen
from urllib.error import HTTPError
url=URL
headers={'Content-Type':'application/json'}
if ROLE is not None:
 headers['Authorization']='Basic '+base64.b64encode((ROLE+':'+os.environ[TOKEN_ENV]).encode()).decode()
data=DATA
request=Request(url,data=None if data is None else json.dumps(data).encode(),headers=headers)
try:
 with urlopen(request,timeout=4) as response: code,raw=response.status,response.read(1048576)
except HTTPError as response: code,raw=response.code,response.read(1048576)
try:value=json.loads(raw)
except Exception:value=None
print(json.dumps({'status':code,'body':value}))
""".replace("URL", repr(url)).replace("ROLE", repr(role)).replace("TOKEN_ENV", repr(token_env)).replace("DATA", repr(body))
        value = self.docker.call(["exec", "--user", "1000:1000", container, "python3", "-c", code], timeout=10)
        return json.loads(value.stdout)

    def wait(self, function, names, timeout=75):
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            for name in names:
                if not self.docker.inspect("container", name)["State"]["Running"]:
                    # Only source/runtime initialization logs, never auth environment dumps.
                    log = self.docker.call(["logs", "--tail", "15", name], check=False)
                    raise RuntimeError("Fixture exited: " + (log.stdout + log.stderr)[-2500:])
            try:
                last = function()
                if last.get("status") == 200:
                    return last
            except Exception as error:
                last = str(error)
            time.sleep(1)
        raise RuntimeError("Fixture readiness timed out: " + str(last)[:1000])

    def cleanup(self):
        errors = []
        groups = [("container", list(reversed(self.containers))), ("volume", list(reversed(self.volumes))),
                  ("network", [self.network] if self.network else [])]
        for kind, names in groups:
            for name in names:
                try:
                    info = self.docker.inspect(kind, name)
                    labels = info.get("Labels", {}) if kind != "container" else info["Config"].get("Labels", {})
                    if labels.get("qbitleap.run") != self.run_id or labels.get("qbitleap.purpose") != PURPOSE:
                        raise RuntimeError("Ownership differs; cleanup refused")
                    if kind == "container":
                        self.docker.call(["stop", "--time", "30", name], timeout=40, check=False)
                        self.docker.call(["rm", "--force", name])
                    else:
                        self.docker.call([kind, "rm", name])
                except Exception as error:
                    errors.append({"kind": kind, "name": name, "error": str(error)})
        return errors

    def diagnostics(self):
        report = {}
        for name in self.containers:
            try:
                info = self.docker.inspect("container", name)
                labels = info["Config"].get("Labels", {})
                if labels.get("qbitleap.run") != self.run_id:
                    continue
                log = self.docker.call(["logs", "--tail", "20", name], check=False)
                namespace = self.docker.call(["exec", name, "readlink", "/proc/self/ns/net"], check=False)
                report[name.removeprefix(self.prefix + "-")] = {
                    "running": info["State"].get("Running"), "exitCode": info["State"].get("ExitCode"),
                    "networkNamespace": namespace.stdout.strip(),
                    "logTail": (log.stdout + log.stderr)[-4000:]}
            except Exception as error:
                report[name] = {"diagnosticError": str(error)[:300]}
        for suffix, role, token_env, host in [("broker", "reader", "QBIT_READ_TOKEN", "127.0.0.1"),
                                              ("core-ui", "ui", "QBIT_UI_TOKEN", self.prefix + "-core")]:
            name = self.prefix + "-" + suffix
            if name not in self.containers:
                continue
            reads = {}
            for method, params in [("getblockchaininfo", []), ("getindexinfo", ["txindex"]), ("getnetworkinfo", [])]:
                try:
                    reads[method] = self.probe(name, "http://" + host + ":8081/",
                        body={"id": 1, "method": method, "params": params}, role=role, token_env=token_env)
                except Exception as error:
                    reads[method] = {"diagnosticError": str(error)[:500]}
            report.setdefault(suffix, {})["readProbes"] = reads
        return report

    def run(self):
        result = {"passed": False, "chain": self.chain, "runId": self.run_id, "protocols": {}}
        try:
            result["stage"] = "create owned empty-chain Core fixture"
            self.network = self.prefix + "-private"
            self.docker.call(["network", "create", "--internal", *self.labels(), self.network])
            if not self.docker.inspect("network", self.network).get("Internal"):
                raise RuntimeError("Fixture network permits external traffic")
            core_data, core_auth = self.volume("core-data"), self.volume("core-auth")
            core_read, core_ui = secrets.token_hex(32), secrets.token_hex(32)
            core = self.start("core", self.images["core"], ["serve"],
                              {"QBIT_CHAIN": self.chain, "QBIT_NETWORK_ACTIVE": "0"},
                              volumes=[(core_data, "/data", False), (core_auth, "/auth", False)], memory="1536m")
            broker = self.start("broker", self.images["services"], ["broker"],
                                {"QBIT_CHAIN": self.chain, "QBIT_READ_TOKEN": core_read, "QBIT_UI_TOKEN": core_ui},
                                share=core, volumes=[(core_auth, "/auth", True)], memory="1024m")
            ui = self.start("core-ui", self.images["services"], ["ui"],
                            {"QBIT_CHAIN": self.chain, "QBIT_READ_URL": "http://" + core + ":8081/", "QBIT_UI_TOKEN": core_ui})
            query = {"jsonrpc": "2.0", "id": 1, "method": "getblockchaininfo", "params": []}
            result["stage"] = "Core read gateway initialization"
            node = self.wait(lambda: self.probe(broker, "http://127.0.0.1:8081/", body=query,
                                              role="reader", token_env="QBIT_READ_TOKEN"), [core, broker])
            # A JSON-RPC error also uses HTTP200, so wait for an affirmative node result.
            deadline = time.monotonic() + 60
            while node["body"].get("error"):
                if time.monotonic() > deadline:
                    raise RuntimeError("Core did not initialize")
                time.sleep(1)
                node = self.probe(broker, "http://127.0.0.1:8081/", body=query, role="reader", token_env="QBIT_READ_TOKEN")
            if node["body"]["result"].get("chain") != self.chain or node["body"]["result"].get("blocks") != 0:
                raise RuntimeError("Expected an empty correct-network node")
            result["stage"] = "Core UI status before restart"
            state = self.wait(lambda: self.probe(ui, "http://127.0.0.1:8080/api/status"), [core, broker, ui])["body"]
            result["coreBeforeRestart"] = state
            print("Core browser status passed before restart on " + self.chain, flush=True)
            result["stage"] = "Core read authentication and namespace isolation"
            if state.get("peerNetworkingEnabled") or state.get("connections") != 0 or state.get("transactionRoutingAccepted"):
                raise RuntimeError("Unexpected peer activity or transaction authority")
            unauthorized = self.probe(ui, "http://" + core + ":8081/", body=query)
            if unauthorized["status"] != 401:
                raise RuntimeError("Unauthenticated read accepted")
            forbidden = self.probe(broker, "http://127.0.0.1:8081/", body={**query, "method": "sendrawtransaction"},
                                   role="reader", token_env="QBIT_READ_TOKEN")
            if forbidden["status"] != 400:
                raise RuntimeError("Publication RPC was not refused")
            tip_error = self.probe(broker, "http://127.0.0.1:8081/", body={**query,
                "method": "getblockhash", "params": [1]}, role="reader", token_env="QBIT_READ_TOKEN")
            error = tip_error.get("body", {}).get("error")
            if not isinstance(error, dict) or error.get("code") != -8:
                raise RuntimeError("Core height-out-of-range error code was not preserved")
            no_cookie = self.docker.call(["exec", ui, "python3", "-c", "from pathlib import Path; assert not Path('/auth/.cookie').exists()"])
            raw_rpc = self.docker.call(["exec", ui, "python3", "-c",
                "import socket; s=socket.socket(); s.settimeout(2); code=s.connect_ex((" + repr(core) + ",18443)); s.close(); assert code != 0"])
            result["stage"] = "Core and dependent gateway restart"
            # The broker shares Core's network namespace. Recreate that attachment
            # after restarting its owner, as the app's compose restart dependency does.
            self.docker.call(["stop", "--time", "30", broker], timeout=40)
            self.docker.call(["stop", "--time", "30", core], timeout=40)
            if self.docker.inspect("container", core)["State"].get("ExitCode") != 0:
                raise RuntimeError("Core did not stop cleanly")
            self.docker.call(["start", core])
            self.docker.call(["start", broker])
            restarted = self.wait(lambda: self.probe(ui, "http://127.0.0.1:8080/api/status"),
                                  [core, broker, ui])["body"]
            if (restarted.get("network") != self.chain or restarted.get("blocks") != 0
                    or restarted.get("bestBlockHash") != GENESIS[self.chain]
                    or restarted.get("peerNetworkingEnabled")):
                raise RuntimeError("Core state or credentials did not survive restart")
            result["core"] = {**state, "unauthenticatedReadRejected": True,
                              "publicationRpcRejected": True, "uiHasNoCoreCookie": True,
                              "rawRpcNotReachableFromNeighbor": True, "restartAccepted": True,
                              "tipErrorCodePreserved": True}
            for protocol in ("leap", "pins", "qord"):
                result["stage"] = protocol + " initialization, API and restart"
                print("Checking isolated " + self.chain + " " + protocol + " app", flush=True)
                local, api = secrets.token_hex(32), secrets.token_hex(32)
                data = self.volume(protocol + "-data")
                common = {"INDEX_PROTOCOL": protocol, "QBIT_CHAIN": self.chain, "INDEX_LOCAL_TOKEN": local}
                transport = self.start(protocol + "-transport", self.images[protocol], ["transport"],
                    {**common, "INDEX_CORE_READ_URL": "http://" + core + ":8081/", "INDEX_CORE_READ_TOKEN": core_read}, memory="1024m")
                writer = self.start(protocol + "-indexer", self.images[protocol], ["indexer"],
                    {**common, "INDEX_ENABLED": "1"}, share=transport, volumes=[(data, "/data", False)], memory="2048m")
                front = self.start(protocol + "-ui", self.images[protocol], ["ui"],
                    {**common, "INDEX_API_TOKEN": api}, share=transport, volumes=[(data, "/data", True)])
                status = self.wait(lambda: self.probe(front, "http://127.0.0.1:8080/v1/status", role="reader", token_env="INDEX_API_TOKEN"),
                                   [transport, writer, front], timeout=100)["body"]
                if status.get("network") != self.chain or status.get("transactionRoutingAccepted"):
                    raise RuntimeError("Indexer status binding differs")
                if self.probe(front, "http://127.0.0.1:8080/v1/status")["status"] != 401:
                    raise RuntimeError("Unauthenticated index API accepted")
                tip_error = self.probe(transport, "http://127.0.0.1:8081/", body={**query,
                    "method": "getblockhash", "params": [1]}, role="reader", token_env="INDEX_LOCAL_TOKEN")
                error = tip_error.get("body", {}).get("error")
                if not isinstance(error, dict) or error.get("code") != -8:
                    raise RuntimeError("Indexer transport lost the normal chain-tip error code")
                self.docker.call(["stop", "--time", "30", writer], timeout=40)
                stopped = self.docker.inspect("container", writer)["State"]
                if stopped.get("OOMKilled") or stopped.get("ExitCode") not in (0, 143):
                    raise RuntimeError("Indexer did not stop cleanly: exit=" + str(stopped.get("ExitCode"))
                                       + ", OOMKilled=" + str(stopped.get("OOMKilled", False)))
                self.docker.call(["start", writer])
                self.wait(lambda: self.probe(front, "http://127.0.0.1:8080/v1/status", role="reader", token_env="INDEX_API_TOKEN"), [writer, front])
                # A duplicate writer must be refused by the persisted advisory lock.
                duplicate = self.docker.call(["exec", writer, "python3", "-c",
                    "import sys;sys.path.insert(0,'/opt/index-app');from indexapp import bind_writer;from pathlib import Path;bind_writer(Path('/data')," + repr(protocol) + "," + repr(self.chain) + ")"], check=False)
                if duplicate.returncode == 0:
                    raise RuntimeError("Duplicate writer lock was not enforced")
                result["protocols"][protocol] = {**status, "apiAuthenticationAccepted": True,
                                                "restartAccepted": True, "duplicateWriterRefused": True,
                                                "tipErrorCodePreserved": True}
            result["passed"] = True
            result["stage"] = "all isolated app checks passed"
        except BaseException as error:
            result["error"] = str(error)
            result["diagnostics"] = self.diagnostics()
        finally:
            errors = self.cleanup()
            result["fixtureCleanupComplete"] = not errors
            result["cleanupErrors"] = errors
            if errors:
                result["passed"] = False
        return result


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('images',type=Path)
 parser.add_argument('--output',type=Path,required=True)
 parser.add_argument('--sources',type=Path,required=True)
 args=parser.parse_args()
 sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
 from catalog import validate_images
 images=validate_images(json.loads(args.images.read_text()))
 sources=json.loads(args.sources.read_text())['apps']
 if sys.platform!='linux' or os.uname().machine!='x86_64': parser.error('Linux amd64 Docker host required')
 if args.output.exists(): parser.error('New acceptance receipt path required')
 docker=Docker()
 for role,image in images.items():
  docker.ensure_image(image)
  info=docker.inspect('image',image)
  if info.get('Architecture')!='amd64' or info['Config'].get('User')!='1000:1000':
   raise ValueError('Image architecture or user differs')
  source=sources['qbit-core' if role in {'core','services'} else role]
  labels=info['Config'].get('Labels',{})
  if (labels.get('org.opencontainers.image.revision')!=source['commit'] or
      labels.get('org.opencontainers.image.source')!=source['repository'].removesuffix('.git')):
   raise ValueError('Published image does not identify the pinned app source')
 result={'passed':False,'images':images,'networks':{},'productionServicesStarted':False,'operationalDataMounted':False,'peerNetworkingEnabled':False}
 try:
  for chain in GENESIS:
   result['networks'][chain]=Fixture(docker,images,chain).run()
   if not result['networks'][chain]['passed']: raise RuntimeError('Isolated '+chain+' acceptance failed')
  result['passed']=True
 except BaseException as error: result['error']=str(error)
 finally:
  args.output.parent.mkdir(parents=True,exist_ok=True)
  args.output.write_text(json.dumps(result,indent=2)+'\n')
  print(json.dumps(result,indent=2))
 return 0 if result['passed'] else 1

if __name__=='__main__': sys.exit(main())
