"""Profile-aware bulk operations. No arbitrary Binder keys or automatic dependency changes."""
import json
import os
import time
from pathlib import Path
from schema import CONTEXT_KEYS, MODES, LIVE_RANGES, LIVE_ENUMS, INDEXED, VERIFIED_SETTERS, SIGNALS, picture_key

# Indexed setters are deliberately not enabled until independently verified.
INDEX_KEYS={k:(section,selector,count) for section,(selector,count,keys) in INDEXED.items() for k in keys}
EXCLUDED={"pq_apply","pic_mode",*CONTEXT_KEYS}
WRITABLE=(set(LIVE_RANGES)|set(LIVE_ENUMS))-EXCLUDED

def inventory(snapshot):
    found={}
    for sid,g in snapshot.get("profiles",{}).items():
        for mid,p in g.get("profiles",{}).items():
            for key,item in p.get("settings",{}).items():
                if not picture_key(key) or key in EXCLUDED or key in INDEX_KEYS or not isinstance(item,dict): continue
                found.setdefault(key,{"key":key,"count":0,"enabled":key in WRITABLE,"reason":"" if key in WRITABLE else "Setter not validated"})["count"]+=1
            for section,group in p.get("indexed",{}).items():
                keys=set(k for e in group.get("values",{}).values() for k in e.get("settings",{}))
                for key in keys:
                    if key not in INDEX_KEYS: continue
                    found.setdefault(key,{"key":key,"count":0,"enabled":False,"reason":"Indexed setter not validated","index_count":INDEX_KEYS[key][2],"section":section})["count"]+=1
    for key,item in found.items():
        if key in LIVE_RANGES: item["values"]=list(range(LIVE_RANGES[key][0],LIVE_RANGES[key][1]+1))
        elif key in LIVE_ENUMS: item["values"]=LIVE_ENUMS[key]
    return sorted(found.values(),key=lambda x:x["key"])

def eligibility(key,value,record,sid,dependencies):
    if key not in WRITABLE: return "Setter not validated"
    if not isinstance(record,dict) or type(record.get("value")) is not int: return "Not returned"
    state=record.get("state")
    if type(state) is not int or state<0: return "Unavailable native state"
    # Unknown positive states are not interpreted as permissions. Known 0/1/2
    # are observed in the native catalog; actual setter acceptance is checked.
    if state not in (0,1,2): return "Unclassified native state"
    if key in LIVE_RANGES:
        bounds=record.get("range")
        lo,hi=LIVE_RANGES[key]
        if not isinstance(bounds,list) or len(bounds)!=3 or bounds[0]!=lo or bounds[2]!=hi or not lo<=value<=hi: return "Range mismatch"
    elif value not in LIVE_ENUMS[key]: return "Unsupported value"
    if key=="gamma_adjust" and (sid>2 or value>=12): return "Gamma writes restricted to SDR"
    if key in ("memc_deblur","memc_dejudder") and dependencies.get("memc",{}).get("value")!=1: return "Requires Custom motion"
    return None

def plan(snapshot,key,value,scope,current,selected):
    if key not in WRITABLE or type(value) is not int: raise ValueError("Unsupported bulk setter or value")
    if key in LIVE_RANGES and not LIVE_RANGES[key][0]<=value<=LIVE_RANGES[key][1]: raise ValueError("Value outside range")
    if key in LIVE_ENUMS and value not in LIVE_ENUMS[key]: raise ValueError("Unsupported enumeration")
    if scope not in ("all","signal","selected","dv_only","exclude_dv"): raise ValueError("Invalid scope")
    if scope=="selected" and (not isinstance(selected,list) or not selected): raise ValueError("Select at least one profile")
    rows=[]
    for sid,g in snapshot.get("profiles",{}).items():
        sid=int(sid)
        if scope=="signal" and sid!=current["signal_dr_type"]: continue
        if scope=="dv_only" and sid!=5: continue
        if scope=="exclude_dv" and sid==5: continue
        for mid,p in g.get("profiles",{}).items():
            mid=int(mid)
            if mid not in MODES.get(sid,()): continue
            if scope=="selected" and f"{sid}:{mid}" not in selected: continue
            settings=p.get("settings",{})
            reason=eligibility(key,value,settings.get(key),sid,settings)
            rows.append({"signal":sid,"mode":mid,"name":f"{SIGNALS.get(sid,sid)} / {p.get('name',mid)}","status":"skip" if reason else "candidate","reason":reason or "Live verification required"})
    if not rows: raise ValueError("No scanned profiles for requested scope")
    return rows

def run(call,context,original,key,value,rows,backup,progress,cancelled,recover=lambda:None,on_verified=lambda c,r:None):
    modes={}
    journal={"original":original,"key":key,"value":value,"entries":[]}
    def persist():
        tmp=backup.with_suffix(".tmp")
        with tmp.open("w") as f:
            json.dump(journal,f,indent=2);f.flush();os.fsync(f.fileno())
        os.replace(tmp,backup)
    def get(*keys):
        return call(1,{"cmd":"get_video_all","msg":{k:["value","range","state"] for k in keys}})["msg"]
    def check(expected):
        if context()!=expected: raise RuntimeError("Context changed; operation stopped")
    def same_source():
        c=context()
        if c["source"]!=original["source"]: raise RuntimeError("Source changed; restoration stopped")
        return c
    def set_value(k,v):
        same_source()
        result=call(2,{k:v})
        if result.get("status")!=0 or result.get("result")!=0: raise ValueError(f"Native setter rejected {k}")
    def select(sid,mid):
        c=same_source()
        if c["signal_dr_type"]!=sid:
            set_value("signal_dr_type",sid)
            c=same_source()
        if c["signal_dr_type"]!=sid: raise RuntimeError("Signal selection failed")
        modes.setdefault(sid,c["pic_mode"])
        if c["pic_mode"]!=mid: set_value("pic_mode",mid)
        expected={"source":original["source"],"signal_dr_type":sid,"pic_mode":mid}
        check(expected)
        return expected
    persist()
    check(original)
    try:
        for row in rows:
            if cancelled(): raise InterruptedError("Bulk apply cancelled")
            sid,mid=row["signal"],row["mode"]
            expected=select(sid,mid)
            records=get(key,"pq_apply","memc")
            check(expected)
            reason=eligibility(key,value,records.get(key),sid,records)
            if reason:
                progress({**row,"status":"skip","reason":reason});continue
            scope=records.get("pq_apply",{}).get("value")
            if type(scope) is not int or scope not in (0,1):
                progress({**row,"status":"skip","reason":"Unknown apply scope"});continue
            previous=records[key]["value"]
            if previous==value:
                on_verified(expected,{key:records[key],"pq_apply":records["pq_apply"]})
                progress({**row,"status":"unchanged","reason":"Already target value"});continue
            entry={"context":expected,"previous":previous,"scope":scope,"status":"pending"}
            journal["entries"].append(entry);persist()
            check(expected)
            try:
                set_value(key,value)
            except ValueError as exc:
                recover()
                check(expected)
                actual=get(key).get(key,{}).get("value")
                entry.update(status="failed",actual=actual,reason=str(exc));persist()
                progress({**row,"status":"failed","reason":str(exc)})
                if actual!=previous: raise RuntimeError("Rejected setter changed value; stopped")
                continue
            check(expected)
            verified=get(key,"pq_apply")
            actual=verified.get(key,{}).get("value")
            entry.update(status="applied" if actual==value else "failed",actual=actual);persist()
            if actual!=value or verified.get("pq_apply",{}).get("value")!=scope:
                progress({**row,"status":"failed","reason":"Write or scope readback mismatch"})
                raise RuntimeError("Write or scope readback mismatch; stopped")
            on_verified(expected,verified)
            progress({**row,"status":"applied","reason":f"{previous} → {actual}"})
    finally:
        recover()
        same_source()
        for sid,mid in list(modes.items()): select(sid,mid)
        select(original["signal_dr_type"],original["pic_mode"])
        check(original)
        journal["restored"]=True;persist()
