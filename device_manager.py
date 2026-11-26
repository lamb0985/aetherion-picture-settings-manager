"""Persistent device registry and scan snapshots."""
import sqlite3
import json
import uuid
import ipaddress
import os
from contextlib import closing
from pathlib import Path

def address(host, port):
    ip = ipaddress.ip_address(host)
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Invalid ADB port")
    return f"[{ip}]:{port}" if ip.version == 6 else f"{ip}:{port}"

def db(root):
    root.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(root / "apsm.db", timeout=10)
    c.row_factory = sqlite3.Row
    c.executescript("""
    CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY, name TEXT NOT NULL, host TEXT NOT NULL, port INTEGER NOT NULL, UNIQUE(host,port));
    CREATE TABLE IF NOT EXISTS preferences(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS snapshots(device TEXT NOT NULL, source INTEGER NOT NULL, captured TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, data TEXT NOT NULL, PRIMARY KEY(device,source));
    """)
    return c

def registry(root):
    with closing(db(root)) as c, c:
        if not c.execute("SELECT 1 FROM preferences WHERE key='initialized'").fetchone():
            try:
                host = os.environ.get("ADB_HOST","")
                port = int(os.environ.get("ADB_PORT",""))
                address(host,port)
            except ValueError:
                pass
            else:
                ident = uuid.uuid4().hex
                c.execute("INSERT INTO devices VALUES(?,?,?,?)",(ident,"Aetherion",host,port))
                c.execute("INSERT INTO preferences VALUES('active',?)",(ident,))
                legacy = root / "catalog.json"
                if legacy.exists():
                    try:
                        data = json.loads(legacy.read_text())
                        source = data["original_context"]["source"]
                        if type(source) is int:
                            c.execute("INSERT INTO snapshots(device,source,data) VALUES(?,?,?)",(ident,source,json.dumps(data)))
                    except (ValueError,KeyError,TypeError,OSError):
                        pass
            c.execute("INSERT INTO preferences VALUES('initialized','1')")
        active=c.execute("SELECT value FROM preferences WHERE key='active'").fetchone()
        return {"devices":[dict(x) for x in c.execute("SELECT * FROM devices ORDER BY name,id")],"active":active[0] if active else None}

def save_device(root, payload):
    registry(root)
    name = payload.get("name","").strip()
    host = str(ipaddress.ip_address(payload["host"]))
    port = payload["port"]
    address(host,port)
    if not name or len(name)>100:
        raise ValueError("Invalid device name")
    ident=payload.get("id") or uuid.uuid4().hex
    with closing(db(root)) as c,c:
        if payload.get("id") and not c.execute("SELECT 1 FROM devices WHERE id=?",(ident,)).fetchone():
            raise ValueError("Unknown device")
        c.execute("INSERT INTO devices VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,host=excluded.host,port=excluded.port",(ident,name,host,port))
        c.execute("INSERT INTO preferences VALUES('active',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(ident,))
    return registry(root)

def select_device(root, ident):
    registry(root)
    with closing(db(root)) as c,c:
        if not c.execute("SELECT 1 FROM devices WHERE id=?",(ident,)).fetchone():
            raise ValueError("Unknown device")
        c.execute("INSERT INTO preferences VALUES('active',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(ident,))
    return registry(root)

def active_device(root):
    r=registry(root)
    return next((x for x in r["devices"] if x["id"]==r["active"]),None)

def store(root, ident, data):
    source=data["original_context"]["source"]
    with closing(db(root)) as c,c:
        c.execute("INSERT INTO snapshots(device,source,data) VALUES(?,?,?) ON CONFLICT(device,source) DO UPDATE SET captured=CURRENT_TIMESTAMP,data=excluded.data",(ident,source,json.dumps(data)))

def snapshot(root, ident, source=None):
    with closing(db(root)) as c:
        if source is None:
            row=c.execute("SELECT data FROM snapshots WHERE device=? ORDER BY captured DESC,source LIMIT 1",(ident,)).fetchone()
        else:
            row=c.execute("SELECT data FROM snapshots WHERE device=? AND source=?",(ident,source)).fetchone()
        return json.loads(row[0]) if row else {"profiles":{}}

def sources(root, ident):
    with closing(db(root)) as c:
        return [dict(x) for x in c.execute("SELECT source,captured FROM snapshots WHERE device=? ORDER BY source",(ident,))]

def merge_live(root, ident, context, records):
    """Refresh only the existing matching profile; keep indexed tables intact."""
    from schema import picture_snapshot
    with closing(db(root)) as c,c:
        c.execute("BEGIN IMMEDIATE")
        row=c.execute("SELECT data FROM snapshots WHERE device=? AND source=?",(ident,context["source"])).fetchone()
        if not row:
            return
        data=picture_snapshot(json.loads(row[0]))
        profile=data.get("profiles",{}).get(str(context["signal_dr_type"]),{}).get("profiles",{}).get(str(context["pic_mode"]))
        if not profile:
            return
        changed=False
        for key,value in records.items():
            if profile["settings"].get(key)!=value:
                profile["settings"][key]=value
                changed=True
        if changed:
            c.execute("UPDATE snapshots SET data=? WHERE device=? AND source=?",(json.dumps(data),ident,context["source"]))
