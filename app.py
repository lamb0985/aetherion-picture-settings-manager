"""Source-aware offline catalog and explicit, read-only projector status."""
import ipaddress
import logging
from collections import deque
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
from schema import SERVICE, CONTEXT_KEYS, INDEXED, MODES, SOURCE_NAMES, source_name, LIVE_RANGES, LIVE_ENUMS, SIGNALS, NATIVE_READ_KEYS, parameter_inventory, picture_snapshot
import device_manager as devices
import scanner
import bulk
import sqlite3
import time

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
CONFIG = Path(os.getenv("CONFIG_DIR", "/config"))
CATALOG = CONFIG / "catalog.json"
ADB_LOCK = threading.Lock()
sock = Sock(app)
REMOTE_TOKEN = None
DIAG_LOG = deque(maxlen=1000)
DIAG_LOCK = threading.Lock()
DIAG_SEQ = 0

def diagnostic(category, message):
    global DIAG_SEQ
    with DIAG_LOCK:
        DIAG_SEQ += 1
        DIAG_LOG.append({"id":DIAG_SEQ,"time":datetime.now().astimezone().strftime("%H:%M:%S"),
                         "category":category,"message":str(message)[:2000]})

class DiagnosticHandler(logging.Handler):
    def emit(self, record):
        diagnostic("Errors" if record.levelno >= logging.ERROR else "Scanner", record.getMessage())

scan_logger = logging.getLogger("apsm.scanner")
scan_logger.setLevel(logging.INFO)
scan_logger.addHandler(DiagnosticHandler())

@app.get("/api/diagnostics/logs")
def diagnostic_logs():
    with DIAG_LOCK:
        rows = list(DIAG_LOG)
    return jsonify(events=rows)

@app.get("/api/diagnostics/middleware")
def diagnostic_middleware():
    # Read-only logcat runs independently of the picture-operation lock.
    try:
        target = endpoint()
        raw = subprocess.check_output(
            ["adb","-s",target,"logcat","-d","-t","500","-v","threadtime",
             "-s","HISMW@video:V","HISMW@system:V","HISMW@dataoperator:W","HSPCore:W","libc:F"],
            text=True, errors="replace", stderr=subprocess.STDOUT, timeout=4)
        return jsonify(device=target, lines=[l[:1500] for l in raw.splitlines() if not l.startswith("---------")][-250:])
    except Exception as exc:
        return jsonify(error=str(exc)),503

@app.post("/api/diagnostics/console")
def diagnostic_console():
    if not ADB_LOCK.acquire(blocking=False):
        return jsonify(error="ADB operation in progress; console locked"),409
    try:
        command=request.get_json().get("command","")
        if not isinstance(command,str) or len(command)>4096:
            raise ValueError("Invalid command")
        command=command.strip()
        target=endpoint()
        if command in ("help","?"):
            return jsonify(output="Commands: adb get-state, adb shell pidof vendor.vt.hs_av_service@1.0-service, adb shell getenforce, adb shell sm list-volumes all, get picture context, get bypass mask, get {JSON} (known picture getters only)")
        allowed={
            "adb get-state":["get-state"],
            "adb shell pidof vendor.vt.hs_av_service@1.0-service":["shell","pidof","vendor.vt.hs_av_service@1.0-service"],
            "adb shell getenforce":["shell","getenforce"],
            "adb shell sm list-volumes all":["shell","sm","list-volumes","all"],
        }
        if command in allowed:
            output=adb("-s",target,*allowed[command])
        else:
            if command=="get picture context":
                payload={"cmd":"get_video_all","msg":{k:["value"] for k in (*CONTEXT_KEYS,"pq_apply","color_temp")}}
            elif command=="get bypass mask":
                payload={"get_value":"bypass_mask"}
            elif command.startswith("get "):
                payload=json.loads(command[4:])
            else:
                raise ValueError("Unsupported command; type help")
            if payload=={"get_value":"bypass_mask"}:
                from cli_transport import CliSession
                cli=CliSession(target)
                try:
                    cli.start()
                    result=cli.call(1,payload)
                finally:
                    cli.close()
            elif (isinstance(payload,dict) and set(payload)=={"cmd","msg"} and payload["cmd"]=="get_video_all"
                  and isinstance(payload["msg"],dict) and 0<len(payload["msg"])<=16
                  and all(k in LIVE_READ_KEYS or k=="pq_apply" for k in payload["msg"])
                  and all(isinstance(v,list) and v and all(x in ("value","range","state") for x in v) for v in payload["msg"].values())):
                result=picture_call(target,1,payload)
            else:
                raise ValueError("Only known read-only picture getters are allowed")
            output=json.dumps(result,indent=2)
        diagnostic("ADB", "Console command completed: "+command[:200])
        return jsonify(output=output[:24000])
    except Exception as exc:
        diagnostic("Errors","Console: "+str(exc))
        return jsonify(error=str(exc)),400
    finally:
        ADB_LOCK.release()


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
        "source_name": source_name(data.get("original_context", {}).get("source")),
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

def picture_call(target, tx, payload):
    encoded=json.dumps(payload,separators=(",",":"))
    return decode_parcel(adb("-s",target,"shell",f"service call {SERVICE} {tx} s16 '{encoded}'"))

# Read only known picture parameters; never change selectors during polling.
LIVE_READ_KEYS = NATIVE_READ_KEYS

@app.post("/api/live/state")
def live_state():
    if not ADB_LOCK.acquire(blocking=False):
        return jsonify(error="ADB operation in progress"),409
    try:
        p=request.get_json()
        d=devices.active_device(CONFIG)
        if not d or d["id"]!=p.get("device"):
            raise ValueError("Selected device changed")
        target=devices.address(d["host"],d["port"])
        if adb("-s",target,"get-state").strip()!="device":
            raise ValueError("Connect the projector first")
        before=live_context(target)
        seed=devices.snapshot(CONFIG,d["id"],before["source"])
        if not seed.get("profiles"):
            seed=devices.snapshot(CONFIG,d["id"])
        keys=parameter_inventory(seed)
        requested=p.get("keys",[])
        if not isinstance(requested,list) or any(not isinstance(k,str) or k not in keys for k in requested):
            raise ValueError("Invalid live parameter list")
        records={}
        for offset in range(0,len(keys),16):
            chunk=keys[offset:offset+16]
            msg=picture_call(target,1,{"cmd":"get_video_all","msg":{k:["value","range","state"] for k in chunk}})["msg"]
            records.update({k:v for k,v in msg.items() if k in chunk and isinstance(v,dict) and type(v.get("value")) is int})
        after=live_context(target)
        if before!=after or any(records.get(k,{}).get("value")!=after[k] for k in CONTEXT_KEYS):
            return jsonify(error="Projector context changed during read; retrying"),409
        devices.merge_live(CONFIG,d["id"],after,records)
        return jsonify(device=d["id"],context=after,source_name=source_name(after["source"]),
                       signal_name=SIGNALS.get(after["signal_dr_type"],"Signal "+str(after["signal_dr_type"])),
                       modes=MODES.get(after["signal_dr_type"],()),settings=records,
                       missing=sorted(set(keys)-set(records)))
    except Exception as exc:
        return jsonify(error=str(exc)),503
    finally:
        ADB_LOCK.release()

@app.post("/api/live/setting")
def live_setting():
    if not ADB_LOCK.acquire(blocking=False):
        return jsonify(error="ADB operation in progress"),409
    attempted=False
    try:
        p=request.get_json()
        key=p["key"]
        if key not in LIVE_RANGES and key not in LIVE_ENUMS and key!="pic_mode":
            raise ValueError("Setting is not enabled for experimental live editing")
        d=devices.active_device(CONFIG)
        if not d or d["id"]!=p.get("device"):
            raise ValueError("Selected device changed")
        expected=p["context"]
        if set(expected)!=set(CONTEXT_KEYS) or any(type(v) is not int for v in expected.values()):
            raise ValueError("Invalid expected context")
        target=devices.address(d["host"],d["port"])
        if adb("-s",target,"get-state").strip()!="device":
            raise ValueError("Connect the projector first")
        def check():
            if live_context(target)!=expected:
                raise ValueError("Live source, signal or picture mode differs from selected profile")
        def read():
            fields={"pq_apply":["value"],key:["value","range","state"]}
            item=picture_call(target,1,{"cmd":"get_video_all","msg":fields})["msg"]
            return item[key],item["pq_apply"]["value"]
        check()
        current,scope=read()
        if "value" not in p:
            return jsonify(setting=current,scope=scope,context=expected)
        value=p["value"]
        if type(value) is not int or p.get("previous")!=current["value"] or p.get("scope")!=scope:
            raise ValueError("Value or apply scope changed; read again")
        if key in LIVE_RANGES:
            lo,hi=LIVE_RANGES[key]
            bounds=current.get("range")
            if not isinstance(bounds,list) or len(bounds)!=3 or bounds[0]!=lo or bounds[2]!=hi or not lo<=value<=hi:
                raise ValueError("Live range does not match expected bounds")
        elif value not in (MODES.get(expected["signal_dr_type"],()) if key=="pic_mode" else LIVE_ENUMS[key]) or (key=="gamma_adjust" and value>=12 and expected["signal_dr_type"]<=2 and value!=current["value"]):
            raise ValueError("Unsupported enumeration value")
        check()
        attempted=True
        result=picture_call(target,2,{key:value})
        if result.get("status")!=0 or result.get("result")!=0:
            raise ValueError("Native setter rejected change")
        time.sleep(.2)
        if key=="pic_mode":
            expected={**expected,"pic_mode":value}
        check()
        actual,scope=read()
        if actual["value"]!=value:
            raise ValueError("Readback differs from requested value")
        return jsonify(setting=actual,scope=scope,context=expected,previous=current["value"])
    except Exception as exc:
        return jsonify(error=str(exc)+(" — write attempted; verify actual projector state before retrying" if attempted else "")),400
    finally:
        ADB_LOCK.release()

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
    data=picture_snapshot(data)
    # The public-facing API does not return local filesystem paths or ADB addresses.
    return jsonify(profiles=data["profiles"], parameter_candidates=data.get("parameter_candidates", {}),
                   menu_enumerations=data.get("menu_enumerations", {}), summary=summarize(data))

@app.post("/api/catalog")
def upload():
    if request.headers.get("Sec-Fetch-Site") == "cross-site":
        return jsonify(error="Cross-site request denied"), 403
    try:
        data = picture_snapshot(validate(request.get_json()))
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
        return jsonify(status="connected", context=context, source_name=source_name(context["source"]))
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        return jsonify(error=str(exc)), 503
    finally:
        ADB_LOCK.release()

BULK = {"status":"idle","done":0,"total":0,"results":[]}
BULK_CANCEL=threading.Event()
BULK_PLAN=None

@app.get("/api/bulk/options")
def bulk_options():
    d=devices.active_device(CONFIG)
    if not d: return jsonify(error="Save a device first"),400
    return jsonify(settings=bulk.inventory(devices.snapshot(CONFIG,d["id"])),device=d["id"])

@app.get("/api/bulk")
def bulk_status():
    return jsonify(dict(BULK))

@app.post("/api/bulk/cancel")
def bulk_cancel():
    BULK_CANCEL.set()
    return jsonify(status="cancellation requested")

@app.post("/api/bulk/preview")
def bulk_preview():
    global BULK_PLAN
    if not ADB_LOCK.acquire(blocking=False): return jsonify(error="ADB operation in progress"),409
    try:
        p=request.get_json()
        d=devices.active_device(CONFIG)
        if not d or d["id"]!=p.get("device"): raise ValueError("Selected device changed")
        target=devices.address(d["host"],d["port"])
        original=live_context(target)
        snapshot=devices.snapshot(CONFIG,d["id"],original["source"])
        rows=bulk.plan(snapshot,p["key"],p["value"],p["scope"],original,p.get("selected",[]))
        token=secrets.token_urlsafe(24)
        BULK_PLAN={"token":token,"created":time.monotonic(),"device":d["id"],"original":original,"key":p["key"],"value":p["value"],"rows":rows}
        return jsonify(token=token,rows=rows,source=source_name(original["source"]))
    except Exception as exc: return jsonify(error=str(exc)),400
    finally: ADB_LOCK.release()

@app.post("/api/bulk")
def start_bulk():
    global BULK_PLAN
    if not ADB_LOCK.acquire(blocking=False): return jsonify(error="ADB operation in progress"),409
    try:
        p=request.get_json()
        plan=BULK_PLAN
        if not plan or p.get("token")!=plan["token"] or time.monotonic()-plan["created"]>300: raise ValueError("Preview expired; preview again")
        d=devices.active_device(CONFIG)
        if not d or d["id"]!=plan["device"]: raise ValueError("Selected device changed")
        target=devices.address(d["host"],d["port"])
        if live_context(target)!=plan["original"]: raise ValueError("Projector context changed; preview again")
        if not any(x["status"]=="candidate" for x in plan["rows"]): raise ValueError("No eligible candidates")
        remote.stop()
        folder=Path(os.getenv("BACKUP_DIR","/backups"))
        folder.mkdir(parents=True,exist_ok=True)
        backup=folder/("bulk-"+datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")+".json")
        BULK_PLAN=None;BULK_CANCEL.clear()
        BULK.update(status="running",done=0,total=len(plan["rows"]),results=[],error=None,backup=backup.name)
        diagnostic("Bulk", f"Bulk apply started: {BULK['total']} profiles")
        def progress(row):
            diagnostic("Bulk", json.dumps(row,default=str))
            BULK["results"].append(row)
            BULK["done"]=len(BULK["results"])
        def worker():
            try:
                bulk.run(lambda tx,p:picture_call(target,tx,p),lambda:live_context(target),plan["original"],plan["key"],plan["value"],plan["rows"],backup,progress,BULK_CANCEL.is_set)
                BULK.update(status="complete")
                diagnostic("Bulk","Bulk apply completed")
            except InterruptedError as exc:
                BULK.update(status="cancelled",error=str(exc))
                diagnostic("Bulk",str(exc))
            except Exception as exc:
                BULK.update(status="failed",error=str(exc))
                diagnostic("Errors","Bulk: "+str(exc))
            finally: ADB_LOCK.release()
        threading.Thread(target=worker,daemon=True).start()
        return jsonify(dict(BULK)),202
    except Exception as exc:
        ADB_LOCK.release()
        return jsonify(error=str(exc)),400

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
    result["sources"]=[{**s, "name":source_name(s["source"])} for s in devices.sources(CONFIG,d["id"])] if d else []
    result["source_names"]=SOURCE_NAMES
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
    mirror_locked=False
    try:
        d=devices.active_device(CONFIG)
        if not d: raise ValueError("Save a device first")
        target=devices.address(d["host"],d["port"])
        seed=devices.snapshot(CONFIG,d["id"])
        if not seed.get("profiles"):
            raise ValueError("Import a discovery catalog first")
        if remote.running():
            if remote.target != target:
                raise ValueError("Mirror is connected to a different projector")
            try:
                mirror_locked=remote.set_view_only(True)
            except Exception as exc:
                remote.stop()
                diagnostic("Errors","Mirror input lock failed; mirror stopped: "+str(exc))
        CANCEL.clear()
        SCAN.update(status="running",done=0,error=None,started=time.time(),device=d["id"],source=None,source_name=None,signal=None,mode=None)
        diagnostic("Scanner","Scan started")
        def scan_progress(n,s,m):
            SCAN.update(done=n,signal=s,mode=m)
            diagnostic("Scanner",f"{n}/{SCAN['total']} | {SIGNALS[s]} | Mode {m}")
        def worker():
            try:
                adb("connect",target)
                if adb("-s",target,"get-state").strip()!="device":
                    raise ValueError("ADB not connected")
                data=scanner.scan(target,seed,adb,decode_parcel,scan_progress,CANCEL.is_set,
                                  on_source=lambda source: SCAN.update(source=source,source_name=source_name(source)))
                devices.store(CONFIG,d["id"],validate(data))
                SCAN.update(status="complete",summary=summarize(data))
                diagnostic("Scanner","Scan complete; catalog stored")
            except InterruptedError as exc:
                SCAN.update(status="cancelled",error=str(exc))
                diagnostic("Scanner",str(exc))
            except Exception as exc:
                SCAN.update(status="failed",error=str(exc))
                diagnostic("Errors","Scan: "+str(exc))
            finally:
                try:
                    if mirror_locked:
                        remote.set_view_only(False)
                except Exception as exc:
                    remote.stop()
                    diagnostic("Errors","Mirror input unlock failed; restart mirror: "+str(exc))
                finally:
                    ADB_LOCK.release()
        threading.Thread(target=worker,daemon=True).start()
    except Exception as exc:
        try:
            if mirror_locked:
                remote.set_view_only(False)
        except Exception:
            remote.stop()
        finally:
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
        if key not in ("DPAD_UP","DPAD_DOWN","DPAD_LEFT","DPAD_RIGHT","DPAD_CENTER","BACK","HOME","MENU","SETTINGS","PICTURE_SETTINGS","VOLUME_UP","VOLUME_DOWN","VOLUME_MUTE","HDMI_1","HDMI_2","HDMI_3"):
            raise ValueError("Unsupported remote key")
        if not remote.running() or remote.target!=endpoint() or p.get("token")!=REMOTE_TOKEN:
            raise ValueError("Start a remote session first")
        if key in ("HDMI_1","HDMI_2","HDMI_3"):
            port=int(key[-1])
            uri=f"content://android.media.tv/passthrough/com.vt.source.external%2F.hdmi.HdmiTvInputService%2FHW{port+1}"
            result=adb("-s",remote.target,"shell","am","start","-W","-a","android.intent.action.VIEW","-n","com.vt.tv.tvcenter/.LiveTVMainActivity","-d",uri)
            if "Error" in result or "Exception" in result:
                raise ValueError(result.strip())
            for _ in range(10):
                time.sleep(.5)
                if live_context(remote.target)["source"]==port+3:
                    remote.touch()
                    return jsonify(status="ok",source_name=f"HDMI {port}")
            raise ValueError("Input switch not confirmed")
        elif key == "PICTURE_SETTINGS":
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
