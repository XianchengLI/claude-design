"""Push a folder to a LocalSend 2.x device over the LocalSend v2 HTTP protocol (mutual TLS).

usage: python localsend_push.py <target_ip> <folder> [--pin PIN]
Find the target IP with:  python localsend_push.py --scan [subnet-prefix e.g. 192.168.1]

Files are announced with their path relative to <folder>, so a receiver that supports
folders recreates the layout. The receiver must click "Accept" in its LocalSend window.

Notes (verified 2026-10-20, PC -> Mac, LocalSend 2.2, 54 files / 2.57 GB at 8.4 MB/s):
- LocalSend 2.x requires MUTUAL TLS: a client without a certificate is cut off with
  "tlsv13 alert certificate required", so plain curl / urllib probes find nothing,
  not even the local instance. A throw-away self-signed cert (CN=LocalSend User) is
  generated on first run into ~/.localsend_client/ (never commit it).
- Git Bash rewrites "-subj /CN=..." into a Windows path; the cert is therefore made
  with MSYS_NO_PATHCONV=1 in the environment.
- Send many small files as one zip (4,645 files -> 1 zip), one HTTP request per file.
- Do not use this for credentials: the Claude Code harness blocks it, and secrets go
  by hand from the LocalSend window.
Progress is appended to ~/.localsend_client/localsend_push.log.
"""
import hashlib, http.client, json, ssl, sys, time, uuid, urllib.parse
from pathlib import Path

import os, socket, subprocess, concurrent.futures

HERE = Path.home() / ".localsend_client"
HERE.mkdir(exist_ok=True)
LOG = HERE / "localsend_push.log"
CERT, KEY = HERE / "ls_client.pem", HERE / "ls_client.key"
if not CERT.exists():
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                    "-keyout", str(KEY), "-out", str(CERT), "-days", "365",
                    "-subj", "/CN=LocalSend User"],
                   check=True, capture_output=True, env={**os.environ, "MSYS_NO_PATHCONV": "1"})

def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
ctx.load_cert_chain(str(CERT), str(KEY))
der = ssl.PEM_cert_to_DER_cert(CERT.read_text())
fingerprint = hashlib.sha256(der).hexdigest().upper()

def _info(ip, timeout=1.5):
    with socket.create_connection((ip, 53317), timeout=timeout) as raw, ctx.wrap_socket(raw) as ss:
        ss.sendall(f"GET /api/localsend/v2/info HTTP/1.1\r\nHost: {ip}\r\nConnection: close\r\n\r\n".encode())
        buf = b""
        while chunk := ss.recv(4096):
            buf += chunk
    return json.loads(buf.partition(b"\r\n\r\n")[2] or b"{}")

if sys.argv[1] == "--scan":
    prefix = sys.argv[2] if len(sys.argv) > 2 else "192.168.1"
    def probe(ip):
        try:
            j = _info(ip); return ip, j.get("alias"), j.get("deviceModel")
        except Exception:
            return None
    with concurrent.futures.ThreadPoolExecutor(64) as ex:
        for r in ex.map(probe, [f"{prefix}.{i}" for i in range(1, 255)]):
            if r: print(*r)
    sys.exit(0)

target = sys.argv[1]
folder = Path(sys.argv[2])
pin = sys.argv[sys.argv.index("--pin") + 1] if "--pin" in sys.argv else None

info = {"alias": "Vault PC (Claude)", "version": "2.1", "deviceModel": "Windows",
        "deviceType": "desktop", "fingerprint": fingerprint, "port": 53317,
        "protocol": "https", "download": False}

files = {}
paths = {}
for p in sorted(folder.rglob("*")):
    if p.is_file():
        fid = uuid.uuid4().hex
        rel = p.relative_to(folder).as_posix()
        files[fid] = {"id": fid, "fileName": rel, "size": p.stat().st_size,
                      "fileType": "application/octet-stream"}
        paths[fid] = p
total = sum(f["size"] for f in files.values())
log(f"target {target}: {len(files)} files, {total/1e9:.2f} GB from {folder}")

def conn(timeout):
    return http.client.HTTPSConnection(target, 53317, context=ctx, timeout=timeout)

# 1. prepare-upload: blocks until the receiver accepts
q = "?pin=" + urllib.parse.quote(pin) if pin else ""
c = conn(timeout=600)
c.request("POST", "/api/localsend/v2/prepare-upload" + q,
          body=json.dumps({"info": info, "files": files}),
          headers={"Content-Type": "application/json"})
r = c.getresponse(); body = r.read().decode(errors="replace"); c.close()
log(f"prepare-upload -> {r.status} {body[:200]}")
if r.status == 401:
    sys.exit("PIN required: rerun with --pin <pin shown on the Mac>")
if r.status == 403:
    sys.exit("receiver rejected the transfer")
if r.status != 200:
    sys.exit(f"prepare-upload failed: {r.status}")
sess = json.loads(body)
session_id = sess["sessionId"]; tokens = sess["files"]
log(f"accepted: session {session_id}, {len(tokens)} files")

# 2. upload each file (streamed)
done = 0; sent = 0; t0 = time.time()
for fid, token in tokens.items():
    p = paths[fid]; size = files[fid]["size"]
    url = f"/api/localsend/v2/upload?sessionId={session_id}&fileId={fid}&token={token}"
    for attempt in range(3):
        try:
            c = conn(timeout=900)
            with p.open("rb") as fh:
                c.request("POST", url, body=fh,
                          headers={"Content-Type": "application/octet-stream", "Content-Length": str(size)})
            r = c.getresponse(); r.read(); c.close()
            if r.status == 200:
                break
            log(f"  {files[fid]['fileName']}: HTTP {r.status} (attempt {attempt+1})")
        except Exception as e:
            log(f"  {files[fid]['fileName']}: {e!r} (attempt {attempt+1})")
            time.sleep(2)
    else:
        log(f"FAILED {files[fid]['fileName']}")
        continue
    done += 1; sent += size
    if size > 50e6 or done % 10 == 0 or done == len(tokens):
        el = time.time() - t0
        log(f"  {done}/{len(tokens)} {sent/1e9:.2f}/{total/1e9:.2f} GB  {sent/1e6/max(el,1):.1f} MB/s  {files[fid]['fileName']}")

log(f"DONE {done}/{len(tokens)} files in {(time.time()-t0)/60:.1f} min")
