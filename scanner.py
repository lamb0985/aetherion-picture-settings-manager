"""Conservative scanner: only context and index selectors are written."""
import json
import logging
log = logging.getLogger('apsm.scanner')
import time
from cli_transport import CliSession
from schema import SERVICE, CONTEXT_KEYS, INDEXED, MODES, SIGNALS, EXTRA_SCAN_KEYS

def scan(target, seed, adb, decode, progress, cancelled, on_source=None):
    session = CliSession(target)
    original_mask = None
    mask_attempted = False
    started = time.monotonic()
    try:
        session.start()
        original_mask = session.call(1, {"get_value":"bypass_mask"})["bypass_mask"]
        if type(original_mask) is not int or original_mask != 0:
            raise ValueError(f"Expected normal bypass mask 0, got {original_mask}; scan not started")
        mask_attempted = True
        session.call(2, {"bypass_mask":2})
        if session.call(1, {"get_value":"bypass_mask"}).get("bypass_mask") != 2:
            raise ValueError("Picture update suppression failed")
        next_keep_awake = time.monotonic() + 60
        def scan_call(tx, payload):
            nonlocal next_keep_awake
            now = time.monotonic()
            if not cancelled() and now >= next_keep_awake:
                next_keep_awake = now + 60
                try:
                    # Send both events in one remote shell invocation.
                    adb("-s", target, "shell",
                        "input keyevent KEYCODE_VOLUME_UP; input keyevent KEYCODE_VOLUME_DOWN")
                    print("APSM scan keep-awake: volume up/down sent", flush=True)
                    log.info("Keep-awake: volume up/down sent")
                except Exception as exc:
                    print(f"APSM scan keep-awake failed: {exc}", flush=True)
                    log.error("Keep-awake failed: %s", exc)
            return session.call(tx, payload)
        log.info("Bypass mask 2 verified; persistent CLI active")
        return _scan(seed, scan_call, progress, cancelled, on_source, session.recover)
    finally:
        try:
            if mask_attempted:
                session.recover()
                session.call(2, {"bypass_mask":original_mask})
                if session.call(1, {"get_value":"bypass_mask"}).get("bypass_mask") != original_mask:
                    raise ValueError("Bypass mask restoration failed")
                log.info("Original bypass mask restored and verified")
        finally:
            session.close()
            print(f"APSM optimized scan elapsed: {time.monotonic()-started:.2f}s", flush=True)
            log.info("Scan elapsed: %.2fs", time.monotonic()-started)

def _scan(seed, call, progress, cancelled, on_source, recover):
    def get(keys):
        last=None
        for _ in range(3):
            try:
                result=call(1,{"cmd":"get_video_all","msg":{k:["value","range","state"] for k in keys}})
                return result["msg"]
            except Exception as exc:
                last=exc
                recover()
                time.sleep(.2)
        raise last
    def set_value(key,value):
        result=call(2,{key:value})
        if result.get("status")!=0 or result.get("result")!=0:
            raise ValueError(f"Selector rejected: {key}: {result}")
        # Keep the proven settling delay for calibration selectors for now.
        if key not in ("signal_dr_type","pic_mode"):
            time.sleep(.15)
    def context():
        return {k:getter["value"] for k,getter in get(CONTEXT_KEYS).items() if k in CONTEXT_KEYS}
    original=context()
    if set(original)!=set(CONTEXT_KEYS):
        raise ValueError("Incomplete initial context")
    if on_source is not None:
        on_source(original["source"])
    candidates=seed.get("parameter_candidates",{})
    keys=sorted({k for group in candidates.values() if isinstance(group,list) for k in group if isinstance(k,str) and k.replace("_","").isalnum()} | set(CONTEXT_KEYS) | {"pq_apply"})
    for group in seed.get("profiles",{}).values():
        for p in group.get("profiles",{}).values():
            keys=sorted(set(keys)|{k for k in p.get("settings",{}) if k.replace("_","").isalnum()})
    if len(keys)<=4:
        raise ValueError("Import the discovery catalog once to supply the known parameter list")
    keys=sorted(set(keys)|set(EXTRA_SCAN_KEYS))
    data={"original_context":original,"parameter_candidates":candidates,"menu_enumerations":seed.get("menu_enumerations",{}),"profiles":{}}
    modes={}
    selectors={}
    done=0
    def check(expected):
        c=context()
        if c!=expected:
            raise ValueError(f"Context changed: expected {expected}, got {c}")
    def select(key,value):
        current=context()
        if current.get("source")!=original["source"]:
            raise ValueError("Source changed; aborting")
        if current.get(key)!=value:
            set_value(key,value)
    def restore_index(expected, saved):
        for key,value in saved.items():
            check(expected)
            set_value(key,value)
            if get([key]).get(key,{}).get("value")!=value:
                raise ValueError(f"Selector restoration failed: {key}")
    try:
        for sid, allowed in MODES.items():
            if cancelled(): raise InterruptedError("Scan cancelled")
            select("signal_dr_type",sid)
            c=context()
            if c.get("signal_dr_type")!=sid or c.get("source")!=original["source"]:
                raise ValueError("Signal selection failed")
            modes[sid]=c["pic_mode"]
            group={"format":SIGNALS[sid],"profiles":{}}
            data["profiles"][str(sid)]=group
            for mid in allowed:
                if cancelled(): raise InterruptedError("Scan cancelled")
                select("pic_mode",mid)
                expected={"source":original["source"],"signal_dr_type":sid,"pic_mode":mid}
                check(expected)
                records={}
                for i in range(0,len(keys),16):
                    if cancelled(): raise InterruptedError("Scan cancelled")
                    records.update(get(keys[i:i+16]))
                check(expected)
                records={k:v for k,v in records.items() if k in keys and isinstance(v,dict) and "value" in v}
                old=seed.get("profiles",{}).get(str(sid),{}).get("profiles",{}).get(str(mid),{})
                profile={"name":old.get("name",f"Mode {mid}"),"settings":records,"indexed":{}}
                saved={}
                selectors[(sid,mid)]=saved
                try:
                    for section,(selector,count,params) in INDEXED.items():
                        v=get([selector]).get(selector,{}).get("value")
                        if type(v) is not int or not 0<=v<count:
                            raise ValueError(f"Cannot preserve selector {selector}: {v}")
                        saved[selector]=v
                        entries={}
                        for level in range(count):
                            if cancelled(): raise InterruptedError("Scan cancelled")
                            check(expected)
                            set_value(selector,level)
                            values=get([selector,*params])
                            if values.get(selector,{}).get("value")!=level:
                                raise ValueError(f"Selector readback failed: {selector}")
                            if any(k not in values or not isinstance(values[k],dict) or "value" not in values[k] for k in params):
                                raise ValueError(f"Missing indexed settings: {section}/{level}")
                            entries[str(level)]={"settings":{k:values[k] for k in params}}
                        profile["indexed"][section]={"values":entries}
                finally:
                    recover()
                    restore_index(expected,saved)
                    selectors.pop((sid,mid),None)
                group["profiles"][str(mid)]=profile
                done+=1
                progress(done,sid,mid)
    finally:
        recover()
        if context().get("source")!=original["source"]:
            raise ValueError("Source changed; restoration stopped to avoid changing another input")
        for (sid,mid),saved in selectors.items():
            select("signal_dr_type",sid)
            select("pic_mode",mid)
            restore_index({"source":original["source"],"signal_dr_type":sid,"pic_mode":mid},saved)
        for sid,mid in modes.items():
            select("signal_dr_type",sid)
            select("pic_mode",mid)
            check({"source":original["source"],"signal_dr_type":sid,"pic_mode":mid})
        select("signal_dr_type",original["signal_dr_type"])
        select("pic_mode",original["pic_mode"])
        check(original)
    return data
