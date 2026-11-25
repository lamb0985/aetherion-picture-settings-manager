"use strict";
const $=id=>document.getElementById(id);
let data={profiles:{},parameter_candidates:{},summary:{}}, tab="picture";
let selectedLevels={};
const indexedTabs={white_balance_20_point:"20 Point",gamma_calibration:"Gamma Calibration",color_management:"Color Tuner"};
function option(select,id,label){const o=document.createElement("option");o.value=id;o.textContent=label;select.append(o)}
function metric(label,value){const el=document.createElement("div");el.className="metric";el.textContent=label;const strong=document.createElement("strong");strong.textContent=value??"—";el.append(strong);$("stats").append(el)}
function profiles(){return data.profiles[$("signal").value]?.profiles||{}}
function chooseProfiles(){$("profile").replaceChildren();for(const [id,p] of Object.entries(profiles()))option($("profile"),id,profileLabel(id,p)+" ["+id+"]");selectedLevels={};tabs();render()}
const wbKeys=["2p_wb_offset_red","2p_wb_offset_green","2p_wb_offset_blue","2p_wb_gain_red","2p_wb_gain_green","2p_wb_gain_blue"];
const names={pq_apply:"Apply Picture Settings",pic_mode:"Picture Mode",color_temp:"Color Temperature",gamma_adjust:"Gamma",saturation:"Color",hue:"Hue", "2p_wb":"2-Point White Balance","20p_wb":"20-Point White Balance","2p_wb_offset_red":"R-Offset","2p_wb_offset_green":"G-Offset","2p_wb_offset_blue":"B-Offset","2p_wb_gain_red":"R-Gain","2p_wb_gain_green":"G-Gain","2p_wb_gain_blue":"B-Gain","20p_wb_red":"Red","20p_wb_green":"Green","20p_wb_blue":"Blue",color_tuner_hue:"Hue",color_tuner_sat:"Saturation",color_tuner_bri:"Brightness",gamma_calibration_gain:"Gain"};
const enumNames={pq_apply:["picture_apply_picture_settings_entries","picture_apply_picture_settings_entry_values"],color_temp:["picture_color_temperature_entries","picture_color_temperature_entry_values"]};
function label(key){return names[key]||key.replace(/_/g," ").replace(/\b\w/g,s=>s.toUpperCase())}
function display(key,info,name){if(key==="pic_mode"){return profileLabel(info.value,profiles()[String(info.value)]||{})}const pair=enumNames[key];if(pair){const e=data.menu_enumerations||{},labels=e[pair[0]],values=e[pair[1]];if(Array.isArray(labels)&&Array.isArray(values)){const i=values.findIndex(v=>String(v)===String(info.value));if(i>=0&&i<labels.length)return labels[i]}}return fallbackEnums[key]?.[info.value]??info.display_value??(switchLabels.has(name)&&[0,1].includes(info.value)?(info.value===1?"On":"Off"):info.value)??"—"}
function group(title){const section=document.createElement("section");section.className="group";const h=document.createElement("h2");h.textContent=title;section.append(h);return section}
function matches(key,name){const f=$("filter").value.toLowerCase();return (key+" "+name).toLowerCase().includes(f)}
function menuRow(section,key,info,name=label(key)){if(!matches(key,name))return;const row=document.createElement("div");row.className="setting-row";const left=document.createElement("div");left.className="setting-name";left.textContent=name;const raw=document.createElement("small");raw.className="raw-detail";raw.textContent=key+" · value: "+String(info.value??"—")+" · range: "+(Array.isArray(info.range)?info.range.join(" / "):info.range??"—")+" · state: "+(info.state??"—");left.append(raw);row.append(left);const right=document.createElement("div");right.className="setting-value";const value=document.createElement("strong");value.textContent=tab==="diagnostics"?(info.value??"—"):display(key,info,name);const range=info.range;if(Array.isArray(range)&&range.length===3&&range.every(Number.isFinite)&&range[2]>range[0]&&Number.isFinite(info.value)&&info.value>=range[0]&&info.value<=range[2]){const meter=document.createElement("meter");meter.min=range[0];meter.max=range[2];meter.value=info.value;meter.setAttribute("aria-label",name+" stored value");right.append(meter)}right.append(value);row.append(right);section.append(row)}
function mount(section){if(section.children.length>1)$("rows").append(section)}
// Native menu order follows the Aetherion Max recording. Aliases are read-only
// candidates; missing keys are shown explicitly, never substituted with defaults.
const nativeGroups={
 luminance:["Laser Luminance",[
 ["Laser Luminance Level",["brightness","laser_luminance","backlight"]],
 ["Enhanced Black Level",["high_dynamic","enhanced_black_level"]],
 ["Contrast",["contrast"]],
 ["Black Level",["black_level"]],
 ["Dark Detail",["dark_detail"]],
 ["Gamma",["gamma_adjust","gamma"]],
 ["AI Contrast",["ai_active_contrast","active_contrast","ai_contrast"]],
 ["Brightness Enhancer",["brightness_enhancer","brightness_enhance"]],
 ["HDR Enhancer",["hdr_enhancer","hdr_enhance"]]]],
 color:["Color",[
 ["Color",["saturation","color"]],
 ["Hue",["hue","tint"]],
 ["Color Temperature",["color_temp"]],
 ["Color Temperature Adaptation",["color_temp_adaptation","color_temperature_adaptation","color_temp_adapt"]],
 ["Color Space",["color_space"]],
 ["Dynamic Color Enhancer",["dynamic_color_enhancer","dynamic_color_enhance","dynamic_color"]]]],
 clarity:["Clarity",[
 ["Sharpness",["sharpness"]],
 ["Smooth Gradient",["gradient_smooth","smooth_gradient","gradation_smooth"]],
 ["AI Super Resolution",["ai_super_resolution","super_resolution"]],
 ["Noise Reduction",["noise_reduction","nr"]],
 ["MPEG Noise Reduction",["digital_noise_reduction","mpeg_noise_reduction","mpeg_nr","digital_nr"]],
 ["Motion Enhancement",["memc","motion_enhancement"]]]]
};
const modeLabels=["Vivid","Standard","Energy Saving","Theater","Game / PC","Sports","Theater Night","Filmmaker","IMAX"];
function profileLabel(id,p){return Number($("signal").value)<=2&&modeLabels[Number(id)]?modeLabels[Number(id)]:p.name||"Mode"}
const fallbackEnums={pq_apply:{0:"Current Source",1:"All Sources"},color_temp:{0:"Warm1",1:"Warm2",2:"Standard",3:"Cool"},color_space:{0:"Native",1:"Auto",2:"BT.709",3:"DCI-P3",4:"BT.2020",5:"Adobe RGB"},gamma_adjust:{0:"2.0",1:"2.2",2:"2.4",3:"BT1886",12:"HLG",13:"ST2084"},memc:{0:"Off",1:"Custom",2:"Film",3:"Clear",4:"Standard",5:"Smooth"}};
const switchLabels=new Set(["Enhanced Black Level","Dark Detail","AI Contrast","Brightness Enhancer","HDR Enhancer","Color Temperature Adaptation","Dynamic Color Enhancer","20 Point"]);
function resolve(p,keys){return keys.find(k=>Object.prototype.hasOwnProperty.call(p.settings,k))}
function showSetting(s,p,name,keys){const k=resolve(p,keys);if(k){menuRow(s,k,p.settings[k],name)}else if(matches(keys.join(" "),name)){const r=document.createElement("div");r.className="setting-row";r.textContent=name;const c=document.createElement("small");c.textContent="Not in snapshot";r.append(c);s.append(r)}}
function navRow(s,name,id){if(!matches(id,name))return;const b=document.createElement("button");b.className="native-link";b.textContent=name+"  ›";b.onclick=()=>navigate(id);s.append(b)}
function unavailableAction(s,name){if(!matches(name,name))return;const b=document.createElement("button");b.className="native-link";b.disabled=true;b.textContent=name+" (read-only)";s.append(b)}
function navigate(id){tab=id;tabs();render()}
function calibrationLabel(tab,id,entry){if(entry.label)return entry.label;if(tab==="white_balance_20_point"||tab==="gamma_calibration")return (Number(id)+1)*5+"%";const e=data.menu_enumerations||{},v=e.picture_color_tuner_color_entries_values,l=e.picture_color_tuner_color_entries;if(Array.isArray(v)&&Array.isArray(l)){const i=v.findIndex(x=>String(x)===String(id));if(i>=0&&i<l.length)return l[i]}return ["Red","Green","Blue","Cyan","Magenta","Yellow","Skin Tone"][Number(id)]||"Color "+id}
function indexedView(p,id){const s=group(indexedTabs[id]),values=p.indexed?.[id]?.values||{},entries=Object.entries(values).sort((a,b)=>Number(a[0])-Number(b[0]));
 if(id==="white_balance_20_point")showSetting(s,p,"20 Point",["20p_wb"]);
 const keys=id==="white_balance_20_point"?["20p_wb_red","20p_wb_green","20p_wb_blue"]:id==="gamma_calibration"?["gamma_calibration_gain"]:["color_tuner_hue","color_tuner_sat","color_tuner_bri"];
 if(entries.length){const row=document.createElement("div");row.className="setting-row";const l=document.createElement("label");l.textContent=id==="color_management"?"Color":"Input Level";const select=document.createElement("select");for(const [k,e] of entries)option(select,k,calibrationLabel(id,k,e));select.value=Object.hasOwn(values,selectedLevels[id])?selectedLevels[id]:entries[0][0];selectedLevels[id]=select.value;select.onchange=()=>{selectedLevels[id]=select.value;render()};l.append(select);row.append(l);s.append(row);const entry=values[select.value];for(const k of keys)showSetting(s,{settings:entry.settings||{}},label(k),[k]);}
 else {const m=document.createElement("p");m.className="notice";m.textContent="No indexed records in this snapshot.";s.append(m)}
 unavailableAction(s,id==="color_management"?"Reset Color Tuner Settings":id==="gamma_calibration"?"Restore Gamma Calibration":"Reset White Balance");mount(s)}
function render(){ $("rows").replaceChildren();const p=profiles()[$("profile").value];if(!p){$("rows").textContent="Select a device and import or scan a picture settings snapshot.";return}
 if(tab==="picture"){const s=group("Picture");showSetting(s,p,"Picture Mode",["pic_mode"]);showSetting(s,p,"Apply Picture Settings",["pq_apply"]);for(const id of ["luminance","color","clarity"])navRow(s,nativeGroups[id][0],id);navRow(s,"Calibration Settings","calibration");unavailableAction(s,"Reset");mount(s)}
 else if(nativeGroups[tab]){const [title,items]=nativeGroups[tab],s=group(title);for(const [name,keys] of items)showSetting(s,p,name,keys);if(tab==="clarity"){const k=resolve(p,["memc","motion_enhancement"]);if(k&&Number(p.settings[k].value)===1){showSetting(s,p,"Judder Reduction",["judder_reduction","memc_judder","judder"]);showSetting(s,p,"Blur Reduction",["blur_reduction","memc_blur","blur"])}}mount(s)}
 else if(tab==="calibration"){const s=group("Calibration Settings");navRow(s,"Color Tuner","color_management");navRow(s,"White Balance","white_balance");navRow(s,"Gamma Calibration","gamma_calibration");mount(s)}
 else if(tab==="white_balance"){const s=group("White Balance");navRow(s,"2 Point","wb2");navRow(s,"20 Point","white_balance_20_point");mount(s)}
 else if(tab==="wb2"){const s=group("2 Point");for(const k of wbKeys)showSetting(s,p,label(k),[k]);unavailableAction(s,"Reset White Balance");mount(s)}
 else if(Object.hasOwn(indexedTabs,tab))indexedView(p,tab);
 else if(tab==="diagnostics"){const s=group("Raw Native Parameters");for(const [k,v] of Object.entries(p.settings))menuRow(s,k,v,k);mount(s);for(const [id,section] of Object.entries(p.indexed||{})){for(const [level,entry] of Object.entries(section.values||{})){const g=group(id+" · "+calibrationLabel(id,level,entry));for(const [k,v] of Object.entries(entry.settings||{}))menuRow(g,k,v,k);mount(g)}}}
}
function tabs(){const items=[["picture","Picture",0],["luminance","Laser Luminance",1],["color","Color",1],["clarity","Clarity",1],["calibration","Calibration Settings",1],["color_management","Color Tuner",2],["white_balance","White Balance",2],["wb2","2 Point",3],["white_balance_20_point","20 Point",3],["gamma_calibration","Gamma Calibration",2],["diagnostics","Raw Diagnostics",0]];$("tabs").replaceChildren();for(const [id,title,depth] of items){const b=document.createElement("button");b.textContent=title;b.style.paddingLeft=(10+depth*13)+"px";b.classList.toggle("active",tab===id);b.setAttribute("aria-pressed",String(tab===id));b.onclick=()=>navigate(id);$("tabs").append(b)}}
async function load(){
 const r=await fetch("/api/catalog"+($("dbSource").value!==""?"?source="+encodeURIComponent($("dbSource").value):""));if(!r.ok)throw Error("Catalog load failed");data=await r.json();
 $("signal").replaceChildren();$("stats").replaceChildren();
 for(const [id,g] of Object.entries(data.profiles||{}))option($("signal"),id,(g.format||"Signal")+" ["+id+"]");
 metric("Snapshot source",data.summary.source);metric("Profiles",data.summary.profiles);metric("General records",data.summary.general);metric("Indexed records",data.summary.indexed);
 chooseProfiles();
}
$("signal").onchange=chooseProfiles;$("profile").onchange=()=>{selectedLevels={};tabs();render()};$("filter").oninput=render;
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
