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
function display(key,info,name){if(key==="pic_mode"){return profileLabel(info.value,profiles()[String(info.value)]||{})}const pair=enumNames[key];if(pair){const e=data.menu_enumerations||{},labels=e[pair[0]],values=e[pair[1]];if(Array.isArray(labels)&&Array.isArray(values)){const i=values.findIndex(v=>String(v)===String(info.value));if(i>=0&&i<labels.length)return labels[i]}}return fallbackEnums[key]?.[info.value]??info.display_value??(["AI Contrast","Dynamic Color Enhancer","AI Super Resolution"].includes(name)?["Off","Low","Medium","High"][info.value]:undefined)??(switchLabels.has(name)&&[0,1].includes(info.value)?(info.value===1?"On":"Off"):info.value)??"—"}
function group(title){const section=document.createElement("section");section.className="group";const h=document.createElement("h2");h.textContent=title;section.append(h);return section}
function matches(key,name){const f=$("filter").value.toLowerCase();return (key+" "+name).toLowerCase().includes(f)}
const liveRanges={"backlight":[0,10],"contrast":[0,100],"brightness":[-50,50],"saturation":[0,100],"hue":[-50,50],"sharpness":[0,50],"memc_dejudder":[0,10],"memc_deblur":[0,10],"2p_wb_gain_red":[-25,25],"2p_wb_gain_green":[-25,25],"2p_wb_gain_blue":[-25,25],"2p_wb_offset_red":[-25,25],"2p_wb_offset_green":[-25,25],"2p_wb_offset_blue":[-25,25]},liveEnums={"color_temp":[0,1,2,3],"memc":[0,1,2,3,4,5],"pq_apply":[0,1],"20p_wb":[0,1]};
Object.assign(liveEnums,{"high_dynamic":[0,1],"dark_detail":[0,1],"active_contrast":[0,1,2,3],"high_brightness":[0,1],"hdr_enhancer":[0,1],"temp_wb":[0,1],"color_space":[0,1,2,3,4],"dynamic_color_enhancer":[0,1,2,3],"gradient_smooth":[0,1,2,3],"ai_sr":[0,1,2,3],"nr":[0,1,2,3],"mpeg_nr":[0,1,2,3],"gamma_adjust":[0,1,2,3,12,13]});
let live=null,reading=false,writing=false,dragging=false,scanBusy=false,epoch=0,liveSignature="";
const isLive=()=>$("liveEdit").checked;
const liveReady=()=>isLive()&&live&&live.device===registry.active&&!scanBusy;
let activeTile=null,optionMenu=null;
const parentMenu={luminance:"picture",color:"picture",clarity:"picture",calibration:"picture",white_balance:"calibration",wb2:"white_balance",white_balance_20_point:"white_balance",gamma_calibration:"calibration",color_management:"calibration",iris:"laser"};
function focusTile(row,key){activeTile=key;for(const tile of $("rows").querySelectorAll(".native-selected"))tile.classList.remove("native-selected");row.classList.add("native-selected")}
function menuRow(section,key,info,name=label(key)){
 if(!matches(key,name))return;
 const row=document.createElement("div");row.className="setting-row native-tile";row.dataset.key=key;if(activeTile===key)row.classList.add("native-selected");
 const left=document.createElement("div");left.className="setting-name";left.textContent=name;
 const raw=document.createElement("small");raw.className="raw-detail";raw.textContent=key+" · value: "+String(info.value??"—")+" · range: "+(Array.isArray(info.range)?info.range.join(" / "):info.range??"—")+" · state: "+(info.state??"—");left.append(raw);row.append(left);
 const right=document.createElement("div");right.className="setting-value";
 const value=document.createElement("strong");value.className="native-current";value.textContent=tab==="diagnostics"?(info.value??"—"):display(key,info,name);
 const range=info.range,limits=liveRanges[key],choices=key==="pic_mode"?live?.modes:liveEnums[key];
 const numeric=limits&&Array.isArray(range)&&range[0]===limits[0]&&range[2]===limits[1]&&Number.isInteger(info.value)&&info.value>=limits[0]&&info.value<=limits[1];
 const editable=liveReady()&&tab!=="diagnostics"&&Number.isInteger(live.settings.pq_apply?.value)&&live.settings[key]===info;
 if(editable&&(numeric||choices?.includes(info.value))){
   const locked=writing||(live.settings.pq_apply.value===1&&!$("allSourcesAck").checked);
   const state=live;
   if(numeric){
     row.classList.add("native-slider-tile");
     const control=document.createElement("input");control.type="range";control.min=limits[0];control.max=limits[1];control.step=1;control.value=info.value;control.disabled=locked;control.setAttribute("aria-label",name);
     control.oninput=()=>{value.textContent=control.value;focusTile(row,key)};
     control.onpointerdown=()=>{dragging=true;focusTile(row,key)};control.onkeydown=()=>{dragging=true;focusTile(row,key)};
     control.onchange=()=>{dragging=false;writeLive(key,name,Number(control.value),state,control)};
     control.onblur=()=>{dragging=false};control.onpointercancel=()=>{dragging=false};right.append(control);
   }else{
     row.classList.add("native-choice-tile");
     const valid=choices.filter(c=>!(key==="gamma_adjust"&&c>=12&&c!==info.value&&live.context.signal_dr_type<=2));
     const index=valid.indexOf(info.value);
     const arrow=(direction,caption)=>{
       const button=document.createElement("button");button.className="native-arrow";button.textContent=caption;button.setAttribute("aria-label",name+(direction<0?" previous":" next"));button.disabled=locked||index+direction<0||index+direction>=valid.length;
       button.onclick=()=>{focusTile(row,key);writeLive(key,name,valid[index+direction],state,button)};return button;
     };
     const current=document.createElement("button");current.className="native-option-value";current.textContent=display(key,info,name);current.disabled=locked;current.setAttribute("aria-label","Choose "+name);current.onclick=()=>{activeTile=key;optionMenu={key,name,choices:valid};render()};
     right.append(arrow(-1,"‹"),current,arrow(1,"›"));value.hidden=true;
   }
 }else if(Array.isArray(range)&&range.length===3&&range.every(Number.isFinite)&&range[2]>range[0]&&Number.isFinite(info.value)&&info.value>=range[0]&&info.value<=range[2]){
   row.classList.add("native-slider-tile");const meter=document.createElement("meter");meter.min=range[0];meter.max=range[2];meter.value=info.value;meter.setAttribute("aria-label",name+" value");right.append(meter)
 }
 right.append(value);row.append(right);section.append(row);
}
window.addEventListener("pointerup",()=>{dragging=false});
window.addEventListener("keyup",()=>{dragging=false});
function liveKeys(){
 if(nativeGroups[tab])return [...new Set(nativeGroups[tab][1].flatMap(x=>x[1]).concat(tab==="clarity"?["memc_dejudder","memc_deblur"]:[]))];
 if(tab==="wb2")return wbKeys;
 if(tab==="iris")return ["iris_mode"];
 if(tab==="white_balance_20_point")return ["20p_wb","20p_wb_point","20p_wb_red","20p_wb_green","20p_wb_blue"];
 if(tab==="gamma_calibration")return ["gamma_calibration_level","gamma_calibration_gain"];
 if(tab==="color_management")return ["color_tuner_clr","color_tuner_hue","color_tuner_sat","color_tuner_bri"];
 if(tab==="diagnostics")return [...new Set(Object.values(nativeGroups).flatMap(g=>g[1].flatMap(x=>x[1])).concat(wbKeys,["iris_mode","20p_wb","memc_dejudder","memc_deblur"]))];
 return [];
}
function selectLiveContext(state){
 const c=state.context;
 $("signal").replaceChildren();option($("signal"),c.signal_dr_type,state.signal_name+" ["+c.signal_dr_type+"]");
 $("profile").replaceChildren();option($("profile"),c.pic_mode,profileLabel(c.pic_mode,{name:data.profiles[c.signal_dr_type]?.profiles?.[c.pic_mode]?.name})+" ["+c.pic_mode+"]");
 $("signal").disabled=true;$("profile").disabled=true;$("dbSource").disabled=true;
 const s=$("dbSource");for(const o of Array.from(s.options))if(o.dataset.liveOnly)o.remove();
 if(!Array.from(s.options).some(o=>o.value===String(c.source))){option(s,c.source,state.source_name);s.lastChild.dataset.liveOnly="1"}
 s.value=c.source;
 $("context").textContent="Live source: "+state.source_name+" · "+state.signal_name+" · "+profileLabel(c.pic_mode,{name:data.profiles[c.signal_dr_type]?.profiles?.[c.pic_mode]?.name});
 $("connection").textContent="Live · Connected";$("connection").className="status ok";
 $("liveScope").textContent=state.settings.pq_apply?.value===1?"All Sources — enable the acknowledgment to unlock editing on all inputs":state.settings.pq_apply?.value===0?"Current Source":"Apply scope unknown — editing disabled";
}
async function syncLive(){
 if(!isLive()||!registry.active||reading||writing||dragging||scanBusy)return;
 reading=true;const generation=epoch,device=registry.active,menu=tab;
 try{
  const state=await api("/api/live/state",{device,keys:liveKeys()});
  if(generation!==epoch||!isLive()||device!==registry.active||menu!==tab||writing||dragging||scanBusy)return;
  const signature=JSON.stringify([menu,state]);
  if(signature!==liveSignature||!live){live=state;liveSignature=signature;selectLiveContext(state);render()}
 }catch(e){
  if(generation!==epoch||!isLive()||menu!==tab)return;
  live=null;liveSignature="";$("connection").textContent="Live unavailable";$("connection").className="status error";$("liveScope").textContent=e.message;render();
 }finally{reading=false}
}
async function writeLive(key,name,value,state,control){
 if(writing||!liveReady()){ $("liveMessage").textContent="Live controls are temporarily unavailable";render();return }
 if(state.device!==live.device||JSON.stringify(state.context)!==JSON.stringify(live.context)||state.settings[key]?.value!==live.settings[key]?.value||state.settings.pq_apply?.value!==live.settings.pq_apply?.value){$("liveMessage").textContent="Projector state changed; adjust again using the refreshed value";render();return}
 if(key!=="pic_mode"&&value===state.settings[key]?.value){render();return}
 if(state.settings.pq_apply?.value===1&&!$("allSourcesAck").checked){
   $("liveMessage").textContent="All Sources is active. Enable the All Sources acknowledgment before editing.";render();return
 }
 writing=true;epoch++;control.disabled=true;
 $("liveMessage").textContent="Applying "+name+" = "+value+"…";
 try{
  // Wait for an already-issued read to release the server ADB lock.
  for(let i=0;reading&&i<200;i++)await new Promise(resolve=>setTimeout(resolve,25));
  if(reading)throw Error("Live read still busy; try again");
  const result=await api("/api/live/setting",{device:state.device,context:state.context,key,value,previous:state.settings[key].value,scope:state.settings.pq_apply.value});
  $("liveMessage").textContent=name+": "+result.previous+" → "+result.setting.value+" verified";
 }catch(e){$("liveMessage").textContent=e.message}
 finally{writing=false;live=null;liveSignature="";render();await syncLive()}
}
async function setLive(on){
 epoch++;live=null;liveSignature="";dragging=false;
 $("liveEdit").checked=on;$("allSourcesAck").checked=false;
 for(const id of ["signal","profile","dbSource"])$(id).disabled=on;
 if(on){$("liveScope").textContent="Reading projector…";render();await syncLive()}
 else{for(const o of Array.from($("dbSource").options))if(o.dataset.liveOnly)o.remove();$("dbSource").value="";$("liveScope").textContent="Stored snapshots — read-only";await load()}
}
function mount(section){if(section.children.length<=1)return;if(tab!=="diagnostics"){section.classList.add("native-menu");if(parentMenu[tab]&&!section.classList.contains("native-options")){const back=document.createElement("button");back.className="native-back";back.textContent="‹ Back";back.onclick=()=>navigate(parentMenu[tab]);section.insertBefore(back,section.children[1])}}$("rows").append(section)}
// Native menu order follows the Aetherion Max recording. Aliases are read-only
// candidates; missing keys are shown explicitly, never substituted with defaults.
const nativeGroups={
 luminance:["Laser Luminance",[
 ["Laser Luminance Level",["backlight"]],
 ["Enhanced Black Level",["high_dynamic","enhanced_black_level"]],
 ["Contrast",["contrast"]],
 ["Black Level",["brightness"]],
 ["Dark Detail",["dark_detail"]],
 ["Gamma",["gamma_adjust","gamma"]],
 ["AI Contrast",["active_contrast"]],
 ["Brightness Enhancer",["high_brightness"]],
 ["HDR Enhancer",["hdr_enhancer","hdr_enhance"]]]],
 color:["Color",[
 ["Color",["saturation","color"]],
 ["Hue",["hue","tint"]],
 ["Color Temperature",["color_temp"]],
 ["Color Temperature Adaptation",["temp_wb"]],
 ["Color Space",["color_space"]],
 ["Dynamic Color Enhancer",["dynamic_color_enhancer","dynamic_color_enhance","dynamic_color"]]]],
 clarity:["Clarity",[
 ["Sharpness",["sharpness"]],
 ["Smooth Gradient",["gradient_smooth","smooth_gradient","gradation_smooth"]],
 ["AI Super Resolution",["ai_sr"]],
 ["Noise Reduction",["nr"]],
 ["MPEG Noise Reduction",["mpeg_nr"]],
 ["Motion Enhancement",["memc","motion_enhancement"]]]]
};
const modeLabels=["Vivid","Standard","Energy Saving","Theater","Game / PC","Sports","Theater Night","Filmmaker","IMAX"];
function profileLabel(id,p){return Number($("signal").value)<=2&&modeLabels[Number(id)]?modeLabels[Number(id)]:p.name||"Mode"}
const fallbackEnums={active_contrast:{0:"Off",1:"Low",2:"Medium",3:"High"},dynamic_color_enhancer:{0:"Off",1:"Low",2:"Medium",3:"High"},gradient_smooth:{0:"Off",1:"Low",2:"Medium",3:"High"},ai_sr:{0:"Off",1:"Low",2:"Medium",3:"High"},nr:{0:"Off",1:"Low",2:"Medium",3:"High"},mpeg_nr:{0:"Off",1:"Low",2:"Medium",3:"High"},iris_mode:{0:"Off",1:"Cinema 1",2:"Cinema 2",3:"Manual",4:"Dynamic"},pq_apply:{0:"Current Source",1:"All Sources"},color_temp:{0:"Warm1",1:"Warm2",2:"Standard",3:"Cool"},color_space:{0:"Native",1:"Auto",2:"BT.709",3:"DCI-P3",4:"BT.2020"},gamma_adjust:{0:"2.0",1:"2.2",2:"2.4",3:"BT1886",12:"HLG",13:"ST2084"},memc:{0:"Off",1:"Custom",2:"Film",3:"Clear",4:"Standard",5:"Smooth"}};
const switchLabels=new Set(["Enhanced Black Level","Dark Detail","Brightness Enhancer","HDR Enhancer","Color Temperature Adaptation","20 Point"]);
function resolve(p,keys){return keys.find(k=>Object.prototype.hasOwnProperty.call(p.settings,k))}
function showSetting(s,p,name,keys){const k=resolve(p,keys);if(k){menuRow(s,k,p.settings[k],name)}else if(matches(keys.join(" "),name)){const r=document.createElement("div");r.className="setting-row";r.textContent=name;const c=document.createElement("small");c.textContent=isLive()?"Not returned by projector":"Not in snapshot";r.append(c);s.append(r)}}
function navRow(s,name,id){if(!matches(id,name))return;const b=document.createElement("button");b.className="native-link";b.textContent=name;const chevron=document.createElement("span");chevron.textContent="›";chevron.setAttribute("aria-hidden","true");b.append(chevron);b.onclick=()=>navigate(id);s.append(b)}
function unavailableAction(s,name){if(!matches(name,name))return;const b=document.createElement("button");b.className="native-link";b.disabled=true;b.textContent=name+" (read-only)";s.append(b)}
function navigate(id){optionMenu=null;activeTile=null;tab=id;tabs();if(isLive()){epoch++;live=null;liveSignature="";render();syncLive()}else render()}
function calibrationLabel(tab,id,entry){if(entry.label&&tab!=="color_management")return entry.label;if(tab==="white_balance_20_point"||tab==="gamma_calibration")return (Number(id)+1)*5+"%";const e=data.menu_enumerations||{},v=e.picture_color_tuner_color_entries_values,l=e.picture_color_tuner_color_entries;if(Array.isArray(v)&&Array.isArray(l)){const i=v.findIndex(x=>String(x)===String(id));if(i>=0&&i<l.length)return l[i]}return ["Red","Green","Blue","Yellow","Cyan","Magenta","Flesh Tone"][Number(id)]||"Color "+id}
function indexedView(p,id){const s=group(indexedTabs[id]),values=p.indexed?.[id]?.values||{},entries=Object.entries(values).sort((a,b)=>Number(a[0])-Number(b[0]));
 if(id==="white_balance_20_point")showSetting(s,p,"20 Point",["20p_wb"]);
 const keys=id==="white_balance_20_point"?["20p_wb_red","20p_wb_green","20p_wb_blue"]:id==="gamma_calibration"?["gamma_calibration_gain"]:["color_tuner_hue","color_tuner_sat","color_tuner_bri"];
 if(isLive()){const selector={white_balance_20_point:"20p_wb_point",gamma_calibration:"gamma_calibration_level",color_management:"color_tuner_clr"}[id];showSetting(s,p,id==="color_management"?"Color":"Input Level",[selector]);for(const k of keys)showSetting(s,p,label(k),[k]);const note=document.createElement("p");note.className="notice";note.textContent="Current native calibration index only. Change index using projector remote; indexed writes are not enabled.";s.append(note)}
 else if(entries.length){const row=document.createElement("div");row.className="setting-row";const l=document.createElement("label");l.textContent=id==="color_management"?"Color":"Input Level";const select=document.createElement("select");for(const [k,e] of entries)option(select,k,calibrationLabel(id,k,e));select.value=Object.hasOwn(values,selectedLevels[id])?selectedLevels[id]:entries[0][0];selectedLevels[id]=select.value;select.onchange=()=>{selectedLevels[id]=select.value;render()};l.append(select);row.append(l);s.append(row);const entry=values[select.value];for(const k of keys)showSetting(s,{settings:entry.settings||{}},label(k),[k]);}
 else {const m=document.createElement("p");m.className="notice";m.textContent="No indexed records in this snapshot.";s.append(m)}
 unavailableAction(s,id==="color_management"?"Reset Color Tuner Settings":id==="gamma_calibration"?"Restore Gamma Calibration":"Reset White Balance");mount(s)}
function render(){ $("rows").replaceChildren();const p=isLive()?(liveReady()?{settings:live.settings,indexed:{}}:null):profiles()[$("profile").value];if(!p){$("rows").textContent=isLive()?"Waiting for live projector values…":"Select a device and import or scan a picture settings snapshot.";return}
 if(optionMenu&&isLive()){
   const {key,name,choices}=optionMenu,info=live.settings[key];
   if(info){
     const s=group(name);s.classList.add("native-options");
     const back=document.createElement("button");back.className="native-back";back.textContent="‹ Back";back.onclick=()=>{optionMenu=null;render()};s.append(back);
     for(const choice of choices){
       const button=document.createElement("button");button.className="native-radio"+(choice===info.value?" native-selected":"");button.setAttribute("role","radio");button.setAttribute("aria-checked",String(choice===info.value));button.textContent=display(key,{value:choice},name);button.disabled=writing||(live.settings.pq_apply?.value===1&&!$("allSourcesAck").checked);
       button.onclick=()=>{optionMenu=null;writeLive(key,name,choice,live,button)};s.append(button);
     }
     mount(s);return;
   }
   optionMenu=null;
 }
 if(tab==="picture"){const s=group("Picture");showSetting(s,p,"Picture Mode",["pic_mode"]);showSetting(s,p,"Apply Picture Settings",["pq_apply"]);for(const id of ["luminance","color","clarity"])navRow(s,nativeGroups[id][0],id);navRow(s,"Calibration Settings","calibration");unavailableAction(s,"Reset");mount(s)}
 else if(nativeGroups[tab]){const [title,items]=nativeGroups[tab],s=group(title);for(const [name,keys] of items)showSetting(s,p,name,keys);if(tab==="clarity"){const k=resolve(p,["memc","motion_enhancement"]);if(k&&Number(p.settings[k].value)===1){showSetting(s,p,"Judder Reduction",["memc_dejudder"]);showSetting(s,p,"Blur Reduction",["memc_deblur"])}}mount(s)}
 else if(tab==="laser"){const s=group("Laser Settings");for(const name of ["Projection Mode","Auto Keystone Correction","Manual Keystone Correction","Focus Adjustment","Eye Protection","3D","3D Left&Right Switch","3D to 2D"])unavailableAction(s,name+" — mapping pending");navRow(s,"IRIS","iris");unavailableAction(s,"Low Noise Mode — mapping pending");mount(s)}
 else if(tab==="iris"){const s=group("IRIS");showSetting(s,p,"IRIS Mode",["iris_mode"]);const mode=p.settings.iris_mode?.value;if(mode===3)unavailableAction(s,"IRIS Size — mapping pending");if(mode===4)unavailableAction(s,"Dynamic IRIS Level — mapping pending");mount(s)}
 else if(tab==="calibration"){const s=group("Calibration Settings");navRow(s,"Color Tuner","color_management");navRow(s,"White Balance","white_balance");navRow(s,"Gamma Calibration","gamma_calibration");mount(s)}
 else if(tab==="white_balance"){const s=group("White Balance");navRow(s,"2 Point","wb2");navRow(s,"20 Point","white_balance_20_point");mount(s)}
 else if(tab==="wb2"){const s=group("2 Point");for(const k of wbKeys)showSetting(s,p,label(k),[k]);unavailableAction(s,"Reset White Balance");mount(s)}
 else if(Object.hasOwn(indexedTabs,tab))indexedView(p,tab);
 else if(tab==="diagnostics"){const s=group("Raw Native Parameters");for(const [k,v] of Object.entries(p.settings))menuRow(s,k,v,k);mount(s);for(const [id,section] of Object.entries(p.indexed||{})){for(const [level,entry] of Object.entries(section.values||{})){const g=group(id+" · "+calibrationLabel(id,level,entry));for(const [k,v] of Object.entries(entry.settings||{}))menuRow(g,k,v,k);mount(g)}}}
}
function tabs(){const items=[["picture","Picture",0],["luminance","Laser Luminance",1],["color","Color",1],["clarity","Clarity",1],["calibration","Calibration Settings",1],["color_management","Color Tuner",2],["white_balance","White Balance",2],["wb2","2 Point",3],["white_balance_20_point","20 Point",3],["gamma_calibration","Gamma Calibration",2],["laser","Laser Settings",0],["iris","IRIS",1],["diagnostics","Raw Diagnostics",0]];$("tabs").replaceChildren();for(const [id,title,depth] of items){const b=document.createElement("button");b.textContent=title;b.style.paddingLeft=(10+depth*13)+"px";b.classList.toggle("active",tab===id);b.setAttribute("aria-pressed",String(tab===id));b.onclick=()=>navigate(id);$("tabs").append(b)}}
async function load(){
 const r=await fetch("/api/catalog"+($("dbSource").value!==""?"?source="+encodeURIComponent($("dbSource").value):""));if(!r.ok)throw Error("Catalog load failed");data=await r.json();
 $("signal").replaceChildren();$("stats").replaceChildren();
 for(const [id,g] of Object.entries(data.profiles||{}))option($("signal"),id,(g.format||"Signal")+" ["+id+"]");
 metric("Snapshot source",data.summary.source_name??data.summary.source);metric("Profiles",data.summary.profiles);metric("General records",data.summary.general);metric("Indexed records",data.summary.indexed);
 if(isLive()){liveSignature="";await syncLive()}else chooseProfiles();
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
  if(writing)throw Error("Wait for current adjustment to finish");
  epoch++;live=null;liveSignature="";$("liveEdit").checked=false;
  for(let i=0;reading&&i<200;i++)await new Promise(resolve=>setTimeout(resolve,25));
  if(reading)throw Error("Live read still busy");
  const r=await fetch("/api/connection",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});const result=await r.json();
  if(!r.ok)throw Error(result.error||"Connection failed");
  $("connection").textContent="Connected";$("connection").className="status ok";
  const c=result.context;
  $("context").textContent="Live source: "+(result.source_name??("Source "+c.source))+" · Signal "+c.signal_dr_type+" · Mode "+c.pic_mode+(data.summary.source!=null&&data.summary.source!==c.source?" — differs from imported snapshot":"");
  // Quiesce polling before the mirror acquires the shared ADB lock.
  epoch++;live=null;liveSignature="";$("liveEdit").checked=false;
  for(let i=0;reading&&i<200;i++)await new Promise(resolve=>setTimeout(resolve,25));
  if(window.apsmStartMirror)await window.apsmStartMirror();
  else $("remoteMessage").textContent="Remote module unavailable; use Start mirror after it loads.";
  await setLive(true);
 }catch(e){$("connection").textContent="Connection unavailable";$("connection").className="status error";$("context").textContent=e.message}finally{b.disabled=false}
};


let registry={devices:[],active:null}, editing=null;
async function api(path,body){const r=await fetch(path,body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});const v=await r.json();if(!r.ok)throw Error(v.error||"Request failed");return v}
function fillDevice(d){editing=d?.id||null;$("deviceName").value=d?.name||"";$("deviceHost").value=d?.host||"";$("devicePort").value=d?.port||""}
async function refreshDevices(){registry=await api("/api/devices");$("device").replaceChildren();option($("device"),"","Select device");for(const d of registry.devices)option($("device"),d.id,d.name+" · "+d.host+":"+d.port);$("device").value=registry.active||"";fillDevice(registry.devices.find(d=>d.id===registry.active));$("dbSource").replaceChildren();option($("dbSource"),"","Latest snapshot");for(const s of registry.sources)option($("dbSource"),s.source,s.name??("Source "+s.source));await load()}
function clearConnection(){epoch++;live=null;liveSignature="";$("liveEdit").checked=false;for(const id of ["signal","profile","dbSource"])$(id).disabled=false;$("connection").textContent="Not checked";$("connection").className="status";$("context").textContent="No live status requested."}
$("newDevice").onclick=()=>fillDevice(null);
$("saveDevice").onclick=async()=>{try{await api("/api/devices",{id:editing,name:$("deviceName").value,host:$("deviceHost").value,port:Number($("devicePort").value)});clearConnection();await refreshDevices();$("deviceMessage").textContent="Saved"}catch(e){$("deviceMessage").textContent=e.message}};
$("device").onchange=async()=>{try{await api("/api/devices",{select:$("device").value});clearConnection();await refreshDevices()}catch(e){$("deviceMessage").textContent=e.message}};
$("dbSource").onchange=()=>load().catch(e=>$("message").textContent=e.message);
$("scan").onclick=async()=>{if(!confirm("Scan all supported profiles on the current source? Picture modes and calibration selectors will temporarily change. Do not change inputs or settings during the scan."))return;try{await api("/api/scan",{});await pollScan()}catch(e){$("scanMessage").textContent=e.message}};
$("cancelScan").onclick=()=>api("/api/scan/cancel",{}).catch(e=>$("scanMessage").textContent=e.message);
let lastScan="";
async function pollScan(){try{const s=await api("/api/scan");$("scanProgress").max=s.total;$("scanProgress").value=s.done;$("scanMessage").textContent=s.status+(s.source_name?" · "+s.source_name:"")+" · "+s.done+"/"+s.total+(s.error?" · "+s.error:"");const busy=s.status==="running";if(busy!==scanBusy){scanBusy=busy;epoch++;live=null;liveSignature="";dragging=false;if(isLive())render()}for(const id of ["scan","saveDevice","newDevice","device","connect","import"])$(id).disabled=busy;$("cancelScan").disabled=!busy;$("openScan").textContent=busy?"Scan · "+s.done+"/"+s.total:"Scan";$("openScan").classList.toggle("active",busy);if(s.status==="complete"&&lastScan!=="complete")await refreshDevices();lastScan=s.status}catch(e){$("scanMessage").textContent=e.message}}
refreshDevices().then(pollScan).then(()=>{const connect=()=>{if(registry.active&&!scanBusy)$("connect").click()};if(document.readyState==="complete")connect();else window.addEventListener("load",connect,{once:true})}).catch(e=>$("message").textContent=e.message);
setInterval(pollScan,2000);

$("rawToggle").onchange=()=>document.body.classList.toggle("show-raw",$("rawToggle").checked);

$("allSourcesAck").onchange=render;
$("liveEdit").onchange=()=>setLive($("liveEdit").checked).catch(e=>$("liveMessage").textContent=e.message);
setInterval(syncLive,1000);

// Dialogs retain existing controls and state; closing does not cancel a scan.
for(const [button,dialog] of [["openScan","scanDialog"],["openSource","sourceDialog"]]){
 $(button).onclick=()=>{if(!$(dialog).open)$(dialog).showModal()};
}
for(const button of document.querySelectorAll("[data-close-dialog]"))button.onclick=()=>$(button.dataset.closeDialog).close();
for(const dialog of document.querySelectorAll(".utility-dialog"))dialog.addEventListener("click",e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close()}});
