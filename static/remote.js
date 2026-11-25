import RFB from "/remote-client/core/rfb.js";
const $=id=>document.getElementById(id);
let rfb=null,token=null;
async function post(path,p={}){const r=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(p)});const j=await r.json();if(!r.ok)throw Error(j.error||"Request failed");return j}
function msg(s){$("remoteMessage").textContent=s}
function detach(){if(rfb){rfb.disconnect();rfb=null}token=null}
$("remoteStart").onclick=async()=>{const b=$("remoteStart");b.disabled=true;try{detach();msg("Starting scrcpy…");const s=await post("/api/remote/start",{size:Number($("remoteSize").value),bitrate:Number($("remoteRate").value),fps:Number($("remoteFps").value)});token=s.token;const u=new URL("/remote-stream",location.href);u.protocol=location.protocol==="https:"?"wss:":"ws:";u.searchParams.set("token",token);rfb=new RFB($("remoteScreen"),u.href);rfb.scaleViewport=true;rfb.addEventListener("connect",()=>msg("Mirror connected"));rfb.addEventListener("disconnect",()=>msg("Mirror disconnected"));}catch(e){msg(e.message)}finally{b.disabled=false}};
$("remoteStop").onclick=async()=>{try{await post("/api/remote/stop");detach();msg("Stopped")}catch(e){msg(e.message)}};
$("remoteFull").onclick=()=> $("remoteScreen").requestFullscreen().catch(e=>msg(e.message));
$("remoteShot").onclick=async()=>{try{const r=await post("/api/remote/screenshot",{token});msg("Saved /config/screenshots/"+r.file)}catch(e){msg(e.message)}};
for(const b of document.querySelectorAll("[data-key]"))b.onclick=()=>post("/api/remote/key",{key:b.dataset.key,token}).catch(e=>msg(e.message));
