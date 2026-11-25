"use strict";
const $=id=>document.getElementById(id);
let data={profiles:{},parameter_candidates:{},summary:{}}, tab="general";
const indexedTabs={white_balance_20_point:"20-point white balance",gamma_calibration:"Gamma calibration",color_management:"Color management"};
function option(select,id,label){const o=document.createElement("option");o.value=id;o.textContent=label;select.append(o)}
function metric(label,value){const el=document.createElement("div");el.className="metric";el.textContent=label;const strong=document.createElement("strong");strong.textContent=value??"—";el.append(strong);$("stats").append(el)}
function profiles(){return data.profiles[$("signal").value]?.profiles||{}}
function chooseProfiles(){$("profile").replaceChildren();for(const [id,p] of Object.entries(profiles()))option($("profile"),id,(p.name||"Mode")+" ["+id+"]");render()}
function label(key){return key.replace(/_/g," ").replace(/\b\w/g,s=>s.toUpperCase())}
function table(title,records){
 const filter=$("filter").value.toLowerCase();
 const matches=records.filter(([key,name])=>(key+" "+name).toLowerCase().includes(filter));
 if(!matches.length)return;
 const section=document.createElement("section");section.className="group";
 const h=document.createElement("h2");h.textContent=title;section.append(h);
 const wrap=document.createElement("div");wrap.className="table-wrap";
 const t=document.createElement("table"), head=t.createTHead().insertRow();
 for(const title of ["Setting","Value","Reported range","Raw state"]){const th=document.createElement("th");th.textContent=title;head.append(th)}
 const body=t.createTBody();
 for(const [key,name,info] of matches){
  const tr=body.insertRow(), nameCell=tr.insertCell();nameCell.textContent=name;
  const sub=document.createElement("small");sub.textContent=key;nameCell.append(sub);
  const value=info.display_value!==undefined?info.display_value+" ("+info.value+")":info.value;
  for(const v of [value,Array.isArray(info.range)?info.range.join(" / "):info.range,info.state])tr.insertCell().textContent=v??"—";
 }
 wrap.append(t);section.append(wrap);$("rows").append(section);
}
function render(){
 $("rows").replaceChildren();
 const p=profiles()[$("profile").value];if(!p)return;
 if(tab==="general"){
  const seen=new Set();
  for(const [category,keys] of Object.entries(data.parameter_candidates||{})){
   const entries=keys.filter(k=>p.settings[k]).map(k=>{seen.add(k);return [k,label(k),p.settings[k]]});
   table(category,entries);
  }
  table("Other settings",Object.entries(p.settings).filter(([k])=>!seen.has(k)).map(([k,v])=>[k,label(k),v]));
 }else{
  const entries=Object.entries(p.indexed?.[tab]?.values||{}).flatMap(([id,level])=>Object.entries(level.settings||{}).map(([k,v])=>[k,(level.label||id)+" · "+label(k),v]));
  table(indexedTabs[tab],entries);
 }
}
function tabs(){
 $("tabs").replaceChildren();
 for(const [id,title] of Object.entries({general:"General settings",...indexedTabs})){
  const b=document.createElement("button");b.textContent=title;b.classList.toggle("active",tab===id);
  b.onclick=()=>{tab=id;tabs();render()};$("tabs").append(b);
 }
}
async function load(){
 const r=await fetch("/api/catalog"+($("dbSource").value!==""?"?source="+encodeURIComponent($("dbSource").value):""));if(!r.ok)throw Error("Catalog load failed");data=await r.json();
 $("signal").replaceChildren();$("stats").replaceChildren();
 for(const [id,g] of Object.entries(data.profiles||{}))option($("signal"),id,(g.format||"Signal")+" ["+id+"]");
 metric("Snapshot source",data.summary.source);metric("Profiles",data.summary.profiles);metric("General records",data.summary.general);metric("Indexed records",data.summary.indexed);
 chooseProfiles();
}
$("signal").onchange=chooseProfiles;$("profile").onchange=render;$("filter").oninput=render;tabs();
$("import").onclick=async()=>{
 const b=$("import");b.disabled=true;
 try{
  const f=$("file").files[0];if(!f)throw Error("Choose a scanner JSON file");
  if(!confirm("Replace the local snapshot with this export?"))return;
  const r=await fetch("/api/catalog",{method:"POST",headers:{"Content-Type":"application/json"},body:await f.text()});
  const result=await r.json();if(!r.ok)throw Error(result.error||"Import failed");
  await load();$("message").textContent="Snapshot imported";$("message").className="ok";
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
