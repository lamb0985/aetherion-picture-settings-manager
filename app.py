"""Source-aware offline catalog and explicit, read-only projector status."""
import ipaddress
import json
import os
import re
import struct
import subprocess
import tempfile
import threading
from pathlib import Path
from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_sock import Sock
from remote import remote
import socket
import secrets
from datetime import datetime, timezone
from werkzeug.exceptions import BadRequest
from schema import SERVICE, CONTEXT_KEYS, INDEXED, MODES
import device_manager as devices
import scanner
import sqlite3
import time

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
CONFIG = Path(os.getenv("CONFIG_DIR", "/config"))
CATALOG = CONFIG / "catalog.json"
ADB_LOCK = threading.Lock()
sock = Sock(app)
REMOTE_TOKEN = None

def read_catalog():
    d = devices.active_device(CONFIG)
    if d:
        return devices.snapshot(CONFIG, d["id"])
    if not CATALOG.exists():
        return {"profiles": {}}
    return json.loads(CATALOG.read_text())

def validate(data):
    if not isinstance(data, dict) or not isinstance(data.get("profiles"), dict):
        raise ValueError("Expected a scanner export containing profiles")
    context = data.get("original_context")
    if not isinstance(context, dict) or type(context.get("source")) is not int:
        raise ValueError("Missing source context")
    for sid, group in data["profiles"].items():
        if not isinstance(sid, str) or not sid.isdigit() or int(sid) not in MODES:
            raise ValueError("Unknown signal ID")
        if not isinstance(group, dict) or not isinstance(group.get("profiles"), dict):
            raise ValueError("Invalid signal group")
        for mid, profile in group["profiles"].items():
            if not mid.isdigit() or int(mid) not in MODES[int(sid)]:
                raise ValueError("Unknown profile ID")
            if not isinstance(profile, dict) or not isinstance(profile.get("settings"), dict):
                raise ValueError("Invalid profile settings")
            settings = profile["settings"]
            expected = {"source": context["source"], "signal_dr_type": int(sid), "pic_mode": int(mid)}
            for key, value in expected.items():
                if not isinstance(settings.get(key), dict) or settings[key].get("value") != value:
                    raise ValueError(f"Source or profile mismatch: {sid}/{mid}/{key}")
            for key, item in settings.items():
                if not isinstance(item, dict):
                    raise ValueError(f"Invalid setting: {key}")
            indexed = profile.get("indexed", {})
            if not isinstance(indexed, dict):
                raise ValueError("Invalid indexed sections")
            for name, section in indexed.items():
                if name not in INDEXED or not isinstance(section, dict) or not isinstance(section.get("values"), dict):
                    raise ValueError("Invalid indexed section")
                _, count, keys = INDEXED[name]
                for level, entry in section["values"].items():
                    if not level.isdigit() or not 0 <= int(level) < count or not isinstance(entry, dict):
                        raise ValueError("Invalid indexed selector")
                    records = entry.get("settings")
                    if not isinstance(records, dict) or any(k not in keys or not isinstance(v, dict) for k,v in records.items()):
                        raise ValueError("Invalid indexed settings")
    return data

def summarize(data):
    records = [p for g in data["profiles"].values() for p in g["profiles"].values()]
    return {
        "source": data.get("original_context", {}).get("source"),
        "profiles": len(records),
        "general": sum(len(p["settings"]) for p in records),
        "indexed": sum(len(e["settings"]) for p in records for s in p.get("indexed", {}).values() for e in s["values"].values()),
    }

def endpoint():
    d = devices.active_device(CONFIG)
    if d:
        return devices.address(d["host"], d["port"])
    host = ipaddress.ip_address(os.environ.get("ADB_HOST", ""))
    port = int(os.environ.get("ADB_PORT", ""))
    if not 1 <= port <= 65535:
        raise ValueError("Invalid ADB port")
    return f"[{host}]:{port}" if host.version == 6 else f"{host}:{port}"

def adb(*args):
    try:
        return subprocess.check_output(["adb", *args], text=True, stderr=subprocess.STDOUT, timeout=15)
    except subprocess.CalledProcessError as exc:
        raise ValueError((exc.output or str(exc)).strip()) from exc

def decode_parcel(raw):
    words = []
    for line in raw.splitlines():
        line = line.strip().removeprefix("Result: Parcel(")
        line = re.sub(r"^0x[0-9a-fA-F]+:\s*", "", line)
        line = line.split("'")[0].strip().rstrip(")")
        words.extend(w for w in line.split() if re.fullmatch(r"[0-9a-fA-F]{8}", w))
    data = b"".join(struct.pack("<I", int(w, 16)) for w in words)
    if len(data) < 8:
        raise ValueError("Incomplete Binder response")
    status, length = struct.unpack_from("<ii", data)
    if status or length <= 0 or len(data) < 8 + length * 2:
        raise ValueError("Invalid Binder response")
    return json.loads(data[8:8 + length * 2].decode("utf-16le"))

def live_context(target):
    payload = json.dumps({"cmd": "get_video_all", "msg": {k: ["value"] for k in CONTEXT_KEYS}}, separators=(",", ":"))
    raw = adb("-s", target, "shell", f"service call {SERVICE} 1 s16 '{payload}'")
    message = decode_parcel(raw)["msg"]
    return {k: message[k]["value"] for k in CONTEXT_KEYS}

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/health")
def health():
    return jsonify(status="ok", catalog=CATALOG.exists(), mode="scan")

@app.get("/api/catalog")
def catalog():
    d = devices.active_device(CONFIG)
    source = request.args.get("source", type=int)
    data = devices.snapshot(CONFIG, d["id"], source) if d else read_catalog()
    # The public-facing API does not return local filesystem paths or ADB addresses.
    return jsonify(profiles=data["profiles"], parameter_candidates=data.get("parameter_candidates", {}),
                   menu_enumerations=data.get("menu_enumerations", {}), summary=summarize(data))

@app.post("/api/catalog")
def upload():
    if request.headers.get("Sec-Fetch-Site") == "cross-site":
        return jsonify(error="Cross-site request denied"), 403
    try:
        data = validate(request.get_json())
    except (ValueError, BadRequest, TypeError, AttributeError, KeyError) as exc:
        return jsonify(error=str(exc)), 400
    d = devices.active_device(CONFIG)
    if d:
        devices.store(CONFIG, d["id"], data)
        return jsonify(status="imported", summary=summarize(data))
    CONFIG.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=CONFIG, delete=False) as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
        name = f.name
    os.replace(name, CATALOG)
    return jsonify(status="imported", summary=summarize(data))

@app.post("/api/connection")
def connect():
    if request.headers.get("Sec-Fetch-Site") == "cross-site":
        return jsonify(error="Cross-site request denied"), 403
    if not ADB_LOCK.acquire(blocking=False):
        return jsonify(error="ADB operation in progress"), 409
    try:
        target = endpoint()
        adb("connect", target)
        if adb("-s", target, "get-state").strip() != "device":
            raise ValueError("Device not authorized or not connected")
        context = live_context(target)
        return jsonify(status="connected", context=context)
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        return jsonify(error=str(exc)), 503
    finally:
        ADB_LOCK.release()

SCAN = {"status":"idle","done":0,"total":sum(map(len,MODES.values()))}
CANCEL = threading.Event()

@app.before_request
def guard_mutations():
    if request.method == "POST" and (request.headers.get("Sec-Fetch-Site") == "cross-site" or not request.is_json):
        return jsonify(error="Only same-site JSON requests allowed"),403

@app.get("/api/devices")
def list_devices():
    result=devices.registry(CONFIG)
    d=devices.active_device(CONFIG)
    result["sources"]=devices.sources(CONFIG,d["id"]) if d else []
    return jsonify(result)

@app.post("/api/devices")
def change_devices():
    if not ADB_LOCK.acquire(blocking=False):
        return jsonify(error="ADB operation in progress"),409
    try:
        remote.stop()
        payload=request.get_json()
        return jsonify(devices.select_device(CONFIG,payload["select"]) if "select" in payload else devices.save_device(CONFIG,payload))
    except (ValueError,KeyError,TypeError,AttributeError,sqlite3.IntegrityError) as exc:
        return jsonify(error=str(exc)),400
    finally:
        ADB_LOCK.release()

@app.get("/api/scan")
def scan_status():
    return jsonify(dict(SCAN))

@app.post("/api/scan/cancel")
def cancel_scan():
    CANCEL.set()
    return jsonify(status="cancellation requested")

@app.post("/api/scan")
def start_scan():
    if not ADB_LOCK.acquire(blocking=False):
        return jsonify(error="ADB operation in progress"),409
    try:
        remote.stop()
        d=devices.active_device(CONFIG)
        if not d: raise ValueError("Save a device first")
        target=devices.address(d["host"],d["port"])
        seed=devices.snapshot(CONFIG,d["id"])
        if not seed.get("profiles"):
            raise ValueError("Import a discovery catalog first")
        CANCEL.clear()
        SCAN.update(status="running",done=0,error=None,started=time.time(),device=d["id"])
        def worker():
            try:
                adb("connect",target)
                if adb("-s",target,"get-state").strip()!="device":
                    raise ValueError("ADB not connected")
                data=scanner.scan(target,seed,adb,decode_parcel,lambda n,s,m: SCAN.update(done=n,signal=s,mode=m),CANCEL.is_set)
                devices.store(CONFIG,d["id"],validate(data))
                SCAN.update(status="complete",summary=summarize(data))
            except InterruptedError as exc:
                SCAN.update(status="cancelled",error=str(exc))
            except Exception as exc:
                SCAN.update(status="failed",error=str(exc))
            finally:
                ADB_LOCK.release()
        threading.Thread(target=worker,daemon=True).start()
    except Exception as exc:
        ADB_LOCK.release()
        return jsonify(error=str(exc)),400
    return jsonify(dict(SCAN)),202

@app.get("/remote-client/<path:filename>")
def remote_client(filename):
    return send_from_directory("/usr/share/novnc",filename)

@app.post("/api/remote/start")
def remote_start():
    global REMOTE_TOKEN
    if not ADB_LOCK.acquire(blocking=False):
        return jsonify(error="ADB operation in progress"),409
    try:
        p=request.get_json()
        size,rate,fps=(p.get("size",720),p.get("bitrate",4),p.get("fps",30))
        if any(type(v) is not int for v in (size,rate,fps)) or size not in (480,720,1080,1280,1920) or rate not in (2,4,8,12) or fps not in (15,30,60):
            raise ValueError("Unsupported stream options")
        target=endpoint()
        adb("connect",target)
        if adb("-s",target,"get-state").strip()!="device":
            raise ValueError("ADB not connected")
        remote.start(target,size,rate,fps)
        REMOTE_TOKEN=secrets.token_urlsafe(32)
        return jsonify(token=REMOTE_TOKEN)
    except Exception as exc:
        return jsonify(error=str(exc)),503
    finally:
        ADB_LOCK.release()

@app.post("/api/remote/stop")
def remote_stop():
    global REMOTE_TOKEN
    if not ADB_LOCK.acquire(blocking=False):
        return jsonify(error="ADB operation in progress"),409
    try:
        remote.stop()
        REMOTE_TOKEN=None
        return jsonify(status="stopped")
    finally:
        ADB_LOCK.release()

@app.post("/api/remote/key")
def remote_key():
    if not ADB_LOCK.acquire(blocking=False):
        return jsonify(error="ADB operation in progress"),409
    try:
        p=request.get_json()
        key=p.get("key")
        if key not in ("DPAD_UP","DPAD_DOWN","DPAD_LEFT","DPAD_RIGHT","DPAD_CENTER","BACK","HOME","MENU","SETTINGS","PICTURE_SETTINGS","VOLUME_UP","VOLUME_DOWN","VOLUME_MUTE"):
            raise ValueError("Unsupported remote key")
        if not remote.running() or remote.target!=endpoint() or p.get("token")!=REMOTE_TOKEN:
            raise ValueError("Start a remote session first")
        if key == "PICTURE_SETTINGS":
            result = adb("-s",remote.target,"shell","am","start","-n","com.vt.customsettings/com.vt.customsettings.picture.ui.PictureActivity")
            if "Error" in result or "Exception" in result:
                raise ValueError(result.strip())
        else:
            adb("-s",remote.target,"shell","input","keyevent","1578" if key == "MENU" else "KEYCODE_"+key)
        remote.touch()
        return jsonify(status="ok")
    except Exception as exc:
        return jsonify(error=str(exc)),400
    finally:
        ADB_LOCK.release()

@app.post("/api/remote/screenshot")
def remote_screenshot():
    if not ADB_LOCK.acquire(blocking=False):
        return jsonify(error="ADB operation in progress"),409
    try:
        if not remote.running() or remote.target!=endpoint() or request.get_json().get("token")!=REMOTE_TOKEN:
            raise ValueError("Start a remote session first")
        data=subprocess.check_output(["adb","-s",remote.target,"exec-out","screencap","-p"],timeout=15)
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Device did not return PNG")
        folder=CONFIG/"screenshots"
        folder.mkdir(parents=True,exist_ok=True)
        name=datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")+".png"
        (folder/name).write_bytes(data)
        return jsonify(file=name)
    except Exception as exc:
        return jsonify(error=str(exc)),400
    finally:
        ADB_LOCK.release()

@sock.route("/remote-stream")
def remote_stream(ws):
    origin=request.headers.get("Origin","")
    from urllib.parse import urlsplit
    if urlsplit(origin).netloc!=request.host or not REMOTE_TOKEN or request.args.get("token")!=REMOTE_TOKEN:
        ws.close()
        return
    with remote.lock:
        if not remote.running():
            ws.close()
            return
        target=remote.target
        token=REMOTE_TOKEN
    try:
        with socket.create_connection(("127.0.0.1",5903),timeout=3) as conn:
            conn.settimeout(.1)
            done=threading.Event()
            def upstream():
                try:
                    while not done.is_set() and remote.running() and remote.target==target and REMOTE_TOKEN==token:
                        chunk=ws.receive(timeout=.5)
                        if chunk is None: continue
                        if isinstance(chunk,bytes): conn.sendall(chunk)
                        remote.touch()
                except Exception: pass
                finally: done.set()
            t=threading.Thread(target=upstream,daemon=True)
            t.start()
            try:
                while not done.is_set() and remote.running() and remote.target==target and REMOTE_TOKEN==token:
                    try: data=conn.recv(65536)
                    except socket.timeout: continue
                    if not data: break
                    ws.send(data)
                    remote.touch()
            finally:
                done.set()
                ws.close()
                t.join(timeout=2)
    except OSError:
        pass

def remote_reaper():
    while True:
        time.sleep(10)
        remote.reap()

threading.Thread(target=remote_reaper,daemon=True).start()
