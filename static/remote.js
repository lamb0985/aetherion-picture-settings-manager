import RFB from "/remote-client/core/rfb.js";
const $=id=>document.getElementById(id);
let rfb=null,token=null;
async function post(path,p={}){const r=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(p)});const j=await r.json();if(!r.ok)throw Error(j.error||"Request failed");return j}
function msg(s){$("remoteMessage").textContent=s}
function detach(){if(rfb){rfb.disconnect();rfb=null}token=null}
async function startMirror(){const b=$("remoteStart");if(b.disabled)return;b.disabled=true;$("remotePanel").open=true;try{detach();msg("Starting scrcpy…");const s=await post("/api/remote/start",{size:Number($("remoteSize").value),bitrate:Number($("remoteRate").value),fps:Number($("remoteFps").value)});token=s.token;const u=new URL("/remote-stream",location.href);u.protocol=location.protocol==="https:"?"wss:":"ws:";u.searchParams.set("token",token);rfb=new RFB($("remoteScreen"),u.href);rfb.scaleViewport=true;rfb.addEventListener("connect",()=>msg("Mirror connected"));rfb.addEventListener("disconnect",()=>msg("Mirror disconnected"));}catch(e){msg(e.message)}finally{b.disabled=false}}
$("remoteStart").onclick=startMirror;
window.apsmStartMirror=startMirror;
$("remoteStop").onclick=async()=>{try{await post("/api/remote/stop");detach();msg("Stopped")}catch(e){msg(e.message)}};
$("remoteFull").onclick=()=> $("remoteScreen").requestFullscreen().catch(e=>msg(e.message));
$("remoteShot").onclick=async()=>{try{const r=await post("/api/remote/screenshot",{token});msg("Saved /config/screenshots/"+r.file)}catch(e){msg(e.message)}};
for(const b of document.querySelectorAll("[data-key]"))b.onclick=async()=>{b.disabled=true;try{const result=await post("/api/remote/key",{key:b.dataset.key,token});if(result.source_name)msg("Switched to "+result.source_name)}catch(e){msg(e.message)}finally{b.disabled=false}};

// Keep the existing VNC connection alive; reflect the server-side scan input lock.
let scanInputLocked=false, scanPollBusy=false;
async function updateScanInput(){
  if(scanPollBusy)return;
  scanPollBusy=true;
  try{
    const response=await fetch("/api/scan",{cache:"no-store"});
    if(!response.ok)return;
    const state=await response.json();
    const bulkResponse=await fetch("/api/bulk",{cache:"no-store"});
    const bulkState=bulkResponse.ok?await bulkResponse.json():{};
    const locked=state.status==="running"||bulkState.status==="running";
    if(rfb)rfb.viewOnly=locked;
    for(const button of document.querySelectorAll("[data-key]"))button.disabled=locked;
    if(locked!==scanInputLocked){
      scanInputLocked=locked;
      if(rfb)msg(locked?"Mirror connected · picture operation · view only":"Mirror connected · controls enabled");
    }
  }catch(e){}finally{scanPollBusy=false;}
}
setInterval(updateScanInput,1000);
