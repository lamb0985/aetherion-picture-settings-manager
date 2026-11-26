(() => {
"use strict";
const el=id=>document.getElementById(id);
const output=el("consoleOutput"), command=el("consoleCommand"), run=el("consoleRun");
const history=[]; let historyIndex=0;
async function request(url,options){
  const response=await fetch(url,{cache:"no-store",...options});
  const data=await response.json();
  if(!response.ok) throw Error(data.error||response.statusText);
  return data;
}
async function copy(value){
  try {await navigator.clipboard.writeText(value);}
  catch {const t=document.createElement("textarea");t.value=value;document.body.append(t);t.select();document.execCommand("copy");t.remove();}
}
el("consoleCopy").onclick=()=>copy(output.textContent);
el("consoleClear").onclick=()=>{output.textContent="";};
function append(text){output.textContent=(output.textContent+"\n"+text).slice(-60000);output.scrollTop=output.scrollHeight;}
el("consoleForm").onsubmit=async e=>{
  e.preventDefault();const value=command.value.trim();if(!value||run.disabled)return;
  history.push(value);if(history.length>100)history.shift();historyIndex=history.length;
  command.value="";run.disabled=true;append("$ "+value);
  try {const data=await request("/api/diagnostics/console",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({command:value})});append(data.output);}
  catch(e){append("ERROR: "+e.message);}
  finally{run.disabled=false;command.focus();}
};
command.onkeydown=e=>{
  if(e.key==="ArrowUp"||e.key==="ArrowDown"){e.preventDefault();historyIndex=Math.max(0,Math.min(history.length,historyIndex+(e.key==="ArrowUp"?-1:1)));command.value=history[historyIndex]||"";}
};
let paused=false,busy=false,events=[],lastId=0,previous=[],device=null;
const log=el("logOutput");
function render(){
  const filter=el("logFilter").value;
  const visible=events.filter(x=>filter==="All"||x.category===filter||(filter==="APSM"&&x.category!=="Middleware"));
  const oldScroll=log.scrollTop;
  log.replaceChildren(...visible.map(x=>{const line=document.createElement("div");line.className="diag-"+x.category;line.textContent=(x.time?x.time+" ":"")+"["+x.category.toUpperCase()+"] "+x.message;return line;}));
  log.scrollTop=el("logAuto").checked?log.scrollHeight:oldScroll;
}
function add(rows){events.push(...rows);if(events.length>1500)events=events.slice(-1500);}
async function poll(){
  if(paused||busy||!el("logPanel").open||document.hidden)return;
  busy=true;
  try{
    const data=await request("/api/diagnostics/logs");
    if(data.events.length&&data.events[data.events.length-1].id<lastId)lastId=0;
    const fresh=data.events.filter(x=>x.id>lastId);
    if(fresh.length){lastId=fresh[fresh.length-1].id;add(fresh);}
    try{
      const native=await request("/api/diagnostics/middleware");
      if(device!==native.device){previous=[];device=native.device;events=events.filter(x=>x.category!=="Middleware");}
      const lines=native.lines;
      let overlap=Math.min(previous.length,lines.length);
      while(overlap>0&&!previous.slice(-overlap).every((x,i)=>x===lines[i]))overlap--;
      add(lines.slice(overlap).map(message=>({category:"Middleware",message})));
      previous=lines;
      el("logConnection").textContent="● Live";
    }catch(e){el("logConnection").textContent="APSM live · middleware unavailable";}
    render();
  }catch(e){el("logConnection").textContent="Log viewer: "+e.message;}
  finally{busy=false;}
}
el("logFilter").onchange=render;
el("logCopy").onclick=()=>copy(log.innerText);
el("logClear").onclick=()=>{events=[];render();};
el("logPause").onclick=()=>{paused=!paused;el("logPause").textContent=paused?"Resume":"Pause";el("logConnection").textContent=paused?"Paused":"Connecting…";if(!paused)poll();};
el("logPanel").addEventListener("toggle",poll);
setInterval(poll,3000);poll();
})();