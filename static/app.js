"use strict";
const $=id=>document.getElementById(id);
let data={profiles:{},parameter_candidates:{},summary:{}}, tab="general";
const indexedTabs={white_balance_20_point:"20-point white balance",gamma_calibration:"Gamma calibration",color_management:"Color management"};
function option(select,id,label){const o=document.createElement("option");o.value=id;o.textContent=label;select.append(o)}
function metric(label,value){const el=document.createElement("div");el.className="metric";el.textContent=label;const strong=document.createElement("strong");strong.textContent=value??"—";el.append(strong);$("stats").append(el)}
function profiles(){return data.profiles[$("signal").value]?.profiles||{}}
function chooseProfiles(){$("profile").replaceChildren();for(const [id,p] of Object.entries(profiles()))option($("profile"),id,(p.name||"Mode")+" ["+id+"]");tabs();render()}
const wbKeys=["2p_wb_offset_red","2p_wb_offset_green","2p_wb_offset_blue","2p_wb_gain_red","2p_wb_gain_green","2p_wb_gain_blue"];
const names={pq_apply:"Apply Picture Settings",pic_mode:"Picture Mode",color_temp:"Color Temperature",gamma_adjust:"Gamma",saturation:"Color Saturation",hue:"Tint", "2p_wb":"2-Point White Balance","20p_wb":"20-Point White Balance","2p_wb_offset_red":"R-Offset","2p_wb_offset_green":"G-Offset","2p_wb_offset_blue":"B-Offset","2p_wb_gain_red":"R-Gain","2p_wb_gain_green":"G-Gain","2p_wb_gain_blue":"B-Gain","20p_wb_red":"Red","20p_wb_green":"Green","20p_wb_blue":"Blue",color_tuner_hue:"Hue",color_tuner_sat:"Saturation",color_tuner_bri:"Brightness",gamma_calibration_gain:"Gain"};
const enumNames={pq_apply:["picture_apply_picture_settings_entries","picture_apply_picture_settings_entry_values"],color_temp:["picture_color_temperature_entries","picture_color_temperature_entry_values"]};
function label(key){return names[key]||key.replace(/_/g," ").replace(/\b\w/g,s=>s.toUpperCase())}
function display(key,info){const pair=enumNames[key];if(pair){const e=data.menu_enumerations||{},labels=e[pair[0]],values=e[pair[1]];if(Array.isArray(labels)&&Array.isArray(values)){const i=values.findIndex(v=>String(v)===String(info.value));if(i>=0&&i<labels.length)return labels[i]}}return info.display_value??info.value??"—"}
function group(title){const section=document.createElement("section");section.className="group";const h=document.createElement("h2");h.textContent=title;section.append(h);return section}
function matches(key,name){const f=$("filter").value.toLowerCase();return (key+" "+name).toLowerCase().includes(f)}
function menuRow(section,key,info,name=label(key)){if(!matches(key,name))return;const row=document.createElement("div");row.className="setting-row";const left=document.createElement("div");left.className="setting-name";left.textContent=name;const raw=document.createElement("small");raw.className="raw-detail";raw.textContent=key+" · value: "+String(info.value??"—")+" · range: "+(Array.isArray(info.range)?info.range.join(" / "):info.range??"—")+" · state: "+(info.state??"—");left.append(raw);row.append(left);const right=document.createElement("div");right.className="setting-value";const value=document.createElement("strong");value.textContent=display(key,info);const range=info.range;if(Array.isArray(range)&&range.length===3&&range.every(Number.isFinite)&&range[2]>range[0]&&Number.isFinite(info.value)&&info.value>=range[0]&&info.value<=range[2]){const meter=document.createElement("meter");meter.min=range[0];meter.max=range[2];meter.value=info.value;meter.setAttribute("aria-label",name+" stored value");right.append(meter)}right.append(value);row.append(right);section.append(row)}
function mount(section){if(section.children.length>1)$("rows").append(section)}
function categories(p){const result={};const used=new Set(["source","signal_dr_type","pic_mode","2p_wb","20p_wb","20p_wb_point","20p_wb_red","20p_wb_green","20p_wb_blue","gamma_calibration","gamma_calibration_gain","gamma_calibration_level","color_tuner","color_tuner_clr","color_tuner_hue","color_tuner_sat","color_tuner_bri",...wbKeys]);for(const [name,keys] of Object.entries(data.parameter_candidates||{})){if(!Array.isArray(keys))continue;const available=keys.filter(k=>p.settings[k]&&!used.has(k));if(available.length){result[name]=available;available.forEach(k=>used.add(k))}}const rest=Object.keys(p.settings).filter(k=>!used.has(k));if(rest.length)result["Other settings"]=rest;return result}
function calibrationLabel(tab,id,entry){if(entry.label)return entry.label;if(tab==="white_balance_20_point"||tab==="gamma_calibration")return (Number(id)+1)*5+"%";const e=data.menu_enumerations||{},v=e.picture_color_tuner_color_entries_values,l=e.picture_color_tuner_color_entries;if(Array.isArray(v)&&Array.isArray(l)){const i=v.findIndex(x=>String(x)===String(id));if(i>=0&&i<l.length)return l[i]}return "Color "+id}
function render(){ $("rows").replaceChildren();const p=profiles()[$("profile").value];if(!p){$("rows").textContent="Select a device and import or scan a picture settings snapshot.";return}if(tab==="general"){for(const [name,keys] of Object.entries(categories(p))){const s=group(name);for(const k of keys)menuRow(s,k,p.settings[k]);mount(s)}}else if(tab==="wb2"){const s=group("2-Point White Balance");if(p.settings["2p_wb"])menuRow(s,"2p_wb",p.settings["2p_wb"]);for(const k of wbKeys)if(p.settings[k])menuRow(s,k,p.settings[k]);mount(s)}else if(tab.startsWith("category:")){const name=tab.slice(9),s=group(name);for(const k of categories(p)[name]||[])menuRow(s,k,p.settings[k]);mount(s)}else{const section=group(indexedTabs[tab]);const enable={white_balance_20_point:"20p_wb",gamma_calibration:"gamma_calibration",color_management:"color_tuner"}[tab];if(p.settings[enable])menuRow(section,enable,p.settings[enable]);mount(section);for(const [id,entry] of Object.entries(p.indexed?.[tab]?.values||{})){const s=group(calibrationLabel(tab,id,entry));for(const [k,v] of Object.entries(entry.settings||{}))menuRow(s,k,v,calibrationLabel(tab,id,entry)+" · "+label(k));mount(s)}}}
function tabs(){const p=profiles()[$("profile").value];const items=[["general","All Picture Settings"],...Object.keys(p?categories(p):{}).map(k=>["category:"+k,k]),["wb2","2-Point White Balance"],...Object.entries(indexedTabs)];if(!items.some(([id])=>id===tab))tab="general";$("tabs").replaceChildren();for(const [id,title] of items){const b=document.createElement("button");b.textContent=title;b.classList.toggle("active",tab===id);b.setAttribute("aria-pressed",String(tab===id));b.onclick=()=>{tab=id;tabs();render()};$("tabs").append(b)}}
async function load(){
 const r=await fetch("/api/catalog"+($("dbSource").value!==""?"?source="+encodeURIComponent($("dbSource").value):""));if(!r.ok)throw Error("Catalog load failed");data=await r.json();
 $("signal").replaceChildren();$("stats").replaceChildren();
 for(const [id,g] of Object.entries(data.profiles||{}))option($("signal"),id,(g.format||"Signal")+" ["+id+"]");
 metric("Snapshot source",data.summary.source);metric("Profiles",data.summary.profiles);metric("General records",data.summary.general);metric("Indexed records",data.summary.indexed);
 chooseProfiles();
}
$("signal").onchange=chooseProfiles;$("profile").onchange=()=>{tabs();render()};$("filter").oninput=render;tabs();
$("import").onclick=async()=>{
 const b=$("import");b.disabled=true;
 try{
  const f=$("file").files[0];if(!f)throw Error("Choose a scanner JSON file");
  if(!confirm("Replace the local snapshot with this export?"))return;
  const r=await fetch("/api/catalog",{method:"POST",headers:{"Content-Type":"application/json"},body:await f.text()});
  const result=await r.json();if(!r.ok)throw Error(result.error||"Import failed");
  await refreshDevices();$("message").textContent="Snapshot imported";$("message").className="ok";
 }catch(e){$("message").textContent=e.message;$("message").className="error"}finally{b.disabled=false}
};
$("connect").onclick=async()=>{
 const b=$("connect");b.disabled=true;$("connection").textContent="Checking…";
 try{
  const r=await fetch("/api/connection",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});const result=await r.json();
  if(!r.ok)throw Error(result.error||"Connection failed");
  $("connection").textContent="Connected";$("connection").className="status ok";
  const c=result.context;
  $("context").textContent="Live source "+c.source+" · Signal "+c.signal_dr_type+" · Mode "+c.pic_mode+(data.summary.source!=null&&data.summary.source!==c.source?" — differs from imported snapshot":"");
 }catch(e){$("connection").textContent="Connection unavailable";$("connection").className="status error";$("context").textContent=e.message}finally{b.disabled=false}
};


let registry={devices:[],active:null}, editing=null;
async function api(path,body){const r=await fetch(path,body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});const v=await r.json();if(!r.ok)throw Error(v.error||"Request failed");return v}
function fillDevice(d){editing=d?.id||null;$("deviceName").value=d?.name||"";$("deviceHost").value=d?.host||"";$("devicePort").value=d?.port||""}
async function refreshDevices(){registry=await api("/api/devices");$("device").replaceChildren();option($("device"),"","Select device");for(const d of registry.devices)option($("device"),d.id,d.name+" · "+d.host+":"+d.port);$("device").value=registry.active||"";fillDevice(registry.devices.find(d=>d.id===registry.active));$("dbSource").replaceChildren();option($("dbSource"),"","Latest snapshot");for(const s of registry.sources)option($("dbSource"),s.source,"Source "+s.source);await load()}
function clearConnection(){$("connection").textContent="Not checked";$("connection").className="status";$("context").textContent="No live status requested."}
$("newDevice").onclick=()=>fillDevice(null);
$("saveDevice").onclick=async()=>{try{await api("/api/devices",{id:editing,name:$("deviceName").value,host:$("deviceHost").value,port:Number($("devicePort").value)});clearConnection();await refreshDevices();$("deviceMessage").textContent="Saved"}catch(e){$("deviceMessage").textContent=e.message}};
$("device").onchange=async()=>{try{await api("/api/devices",{select:$("device").value});clearConnection();await refreshDevices()}catch(e){$("deviceMessage").textContent=e.message}};
$("dbSource").onchange=()=>load().catch(e=>$("message").textContent=e.message);
$("scan").onclick=async()=>{if(!confirm("Scan all supported profiles on the current source? Picture modes and calibration selectors will temporarily change. Do not change inputs or settings during the scan."))return;try{await api("/api/scan",{});await pollScan()}catch(e){$("scanMessage").textContent=e.message}};
$("cancelScan").onclick=()=>api("/api/scan/cancel",{}).catch(e=>$("scanMessage").textContent=e.message);
let lastScan="";
async function pollScan(){try{const s=await api("/api/scan");$("scanProgress").max=s.total;$("scanProgress").value=s.done;$("scanMessage").textContent=s.status+" · "+s.done+"/"+s.total+(s.error?" · "+s.error:"");const busy=s.status==="running";for(const id of ["scan","saveDevice","newDevice","device","connect","import"])$(id).disabled=busy;$("cancelScan").disabled=!busy;if(s.status==="complete"&&lastScan!=="complete")await refreshDevices();lastScan=s.status}catch(e){$("scanMessage").textContent=e.message}}
refreshDevices().then(pollScan).catch(e=>$("message").textContent=e.message);
setInterval(pollScan,2000);

$("rawToggle").onchange=()=>document.body.classList.toggle("show-raw",$("rawToggle").checked);
