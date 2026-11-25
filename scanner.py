"""Conservative scanner: only context and index selectors are written."""
import json
import time
from schema import SERVICE, CONTEXT_KEYS, INDEXED, MODES, SIGNALS

def scan(target, seed, adb, decode, progress, cancelled):
    def call(tx,payload):
        return decode(adb("-s",target,"shell",f"service call {SERVICE} {tx} s16 '{json.dumps(payload,separators=(',',':'))}'"))
    def get(keys):
        last=None
        for _ in range(3):
            try:
                result=call(1,{"cmd":"get_video_all","msg":{k:["value","range","state"] for k in keys}})
                return result["msg"]
            except Exception as exc:
                last=exc
                time.sleep(.2)
        raise last
    def set_value(key,value):
        result=call(2,{key:value})
        if result.get("status")!=0 or result.get("result")!=0:
            raise ValueError(f"Selector rejected: {key}: {result}")
        time.sleep(.15)
    def context():
        return {k:getter["value"] for k,getter in get(CONTEXT_KEYS).items() if k in CONTEXT_KEYS}
    original=context()
    if set(original)!=set(CONTEXT_KEYS):
        raise ValueError("Incomplete initial context")
    candidates=seed.get("parameter_candidates",{})
    keys=sorted({k for group in candidates.values() if isinstance(group,list) for k in group if isinstance(k,str) and k.replace("_","").isalnum()} | set(CONTEXT_KEYS) | {"pq_apply"})
    for group in seed.get("profiles",{}).values():
        for p in group.get("profiles",{}).values():
            keys=sorted(set(keys)|{k for k in p.get("settings",{}) if k.replace("_","").isalnum()})
    if len(keys)<=4:
        raise ValueError("Import the discovery catalog once to supply the known parameter list")
    data={"original_context":original,"parameter_candidates":candidates,"menu_enumerations":seed.get("menu_enumerations",{}),"profiles":{}}
    modes={}
    selectors={}
    done=0
    def check(expected):
        c=context()
        if c!=expected:
            raise ValueError(f"Context changed: expected {expected}, got {c}")
    def select(key,value):
        if context().get("source")!=original["source"]:
            raise ValueError("Source changed; aborting")
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
                    restore_index(expected,saved)
                    selectors.pop((sid,mid),None)
                group["profiles"][str(mid)]=profile
                done+=1
                progress(done,sid,mid)
    finally:
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
