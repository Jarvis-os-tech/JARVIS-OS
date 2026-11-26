import {GestureController} from './gesture-core.js';

const KEY='ada.gestures';
const defaults={enabled:false,mirror:true,hand:'any',rotation:0,sensitivity:1,
  bounds:{left:.16,right:.84,top:.12,bottom:.88}};
const connections=[[0,1,2,3,4],[0,5,6,7,8],[5,9,10,11,12],[9,13,14,15,16],[13,17,18,19,20],[0,17]];

function preferences() {
  let saved={};try{saved=JSON.parse(localStorage.getItem(KEY)||'{}')||{};}catch{}
  const p={...defaults,...saved};
  p.enabled=p.enabled===true;p.mirror=p.mirror!==false;
  if(!['any','left','right'].includes(p.hand))p.hand='any';
  if(![0,90,180,270].includes(p.rotation))p.rotation=0;
  p.sensitivity=Math.max(.6,Math.min(1.8,Number(p.sensitivity)||1));
  const b=p.bounds;
  if(!b||!['left','right','top','bottom'].every(k=>Number.isFinite(b[k])&&b[k]>=0&&b[k]<=1)||b.right-b.left<.2||b.bottom-b.top<.2)p.bounds={...defaults.bounds};
  return p;
}

export function initGestures() {
  const $=id=>document.getElementById(id),p=preferences();
  const toggle=$('gestureToggle'),notice=$('gestureStatus'),badge=$('gestureBadge');
  const cursor=$('gestureCursor'),overlay=$('gestureOverlay'),preview=$('gesturePreview');
  let socket=null,generation=0,disposed=false,retry=0,lastFrame=0,lastSeq=0,watchdog=0;
  let target=null,hovered=null,dragging=false,calibration=null,receivedReady=false;
  let point={x:0,y:0},lastPreview=0,lastBadge='';
  const core=new GestureController(handle,p);

  function save(){try{localStorage.setItem(KEY,JSON.stringify(p));}catch{message('Settings apply for this session; browser storage is unavailable.');}}
  function message(text){notice.textContent=text;}
  function status(text){if(lastBadge!==text){badge.textContent=text;lastBadge=text;}}
  function topLayer(){
    if(!p.enabled||disposed||document.hidden)return;
    try{if(overlay.matches(':popover-open'))overlay.hidePopover();overlay.showPopover();}catch{}
  }
  function validTarget(node){
    if(!node?.isConnected||node.closest('[inert],[hidden]')||node.matches(':disabled'))return false;
    const rect=node.getBoundingClientRect(),style=getComputedStyle(node);
    const modal=document.querySelector('dialog:modal');
    return rect.width>0&&rect.height>0&&style.visibility!=='hidden'&&(!modal||modal.contains(node));
  }
  function hit(x,y){
    const node=document.elementFromPoint(x,y);
    return node?.closest('[data-gesture-cad],button,a[href],input,textarea,select,summary,[role="button"],label')||null;
  }
  function highlight(node){
    if(hovered===node)return;
    hovered?.classList.remove('gesture-hover');hovered=node;
    if(validTarget(node))node.classList.add('gesture-hover');
  }
  function clearTarget(){
    if(dragging&&target?.isConnected)target.dispatchEvent(new CustomEvent('ada-gesture',{detail:{action:'end'}}));
    dragging=false;target=null;
  }
  function cancel(){core.reset();clearTarget();highlight(null);cursor.hidden=true;}
  function handle(event){
    if(event.type==='state'){cursor.dataset.state=event.state;return;}
    if(event.type==='move'){
      point={x:event.x,y:event.y};cursor.hidden=false;
      cursor.style.transform=`translate3d(${point.x}px,${point.y}px,0)`;
      if(!core.press)highlight(hit(point.x,point.y));
    } else if(event.type==='press'){
      target=hit(event.x,event.y);if(!validTarget(target))target=null;
    } else if(event.type==='dragstart'){
      if(validTarget(target)&&target.hasAttribute('data-gesture-cad')){
        dragging=true;target.dispatchEvent(new CustomEvent('ada-gesture',{detail:{action:'begin'}}));
      }
    } else if(event.type==='drag'){
      if(dragging&&validTarget(target))target.dispatchEvent(new CustomEvent('ada-gesture',{detail:{action:'rotate',dx:event.dx,dy:event.dy}}));
      else if(dragging)cancel();
    } else if(event.type==='click'){
      const clicked=target;clearTarget();
      if(validTarget(clicked))activate(clicked,event.x,event.y);
    } else if(event.type==='release'||event.type==='cancel')clearTarget();
  }
  function activate(node,x,y){
    if(node.hasAttribute('data-gesture-cad')){
      node.dispatchEvent(new CustomEvent('ada-gesture',{detail:{action:'select',x,y}}));return;
    }
    // Native pickers require a trusted mouse/touch event. Provide an HTML list for selects.
    if(node.tagName==='SELECT'){openChoices(node);return;}
    if(node.matches('input[type=file]')){message('Use the mouse or Ada’s voice file tools to choose a file.');return;}
    if(node.matches('input[type=range]')){
      const r=node.getBoundingClientRect(),min=Number(node.min)||0,max=Number(node.max)||100,step=Number(node.step)||1;
      node.value=Math.min(max,Math.max(min,min+Math.round((x-r.left)/r.width*(max-min)/step)*step));
      node.dispatchEvent(new Event('input',{bubbles:true}));node.dispatchEvent(new Event('change',{bubbles:true}));
    } else {
      node.focus?.({preventScroll:true});node.click();
    }
    cursor.dataset.clicked='true';setTimeout(()=>delete cursor.dataset.clicked,180);
  }
  function openChoices(select){
    const dialog=$('gestureChoices'),list=$('gestureChoiceList');
    list.replaceChildren();
    for(const option of select.options){
      const button=document.createElement('button');button.type='button';button.textContent=option.textContent;
      button.disabled=option.disabled;button.setAttribute('aria-pressed',String(option.selected));
      button.onclick=()=>{select.value=option.value;select.dispatchEvent(new Event('input',{bubbles:true}));select.dispatchEvent(new Event('change',{bubbles:true}));dialog.close();};
      list.append(button);
    }
    dialog.showModal();topLayer();
  }
  $('gestureChoicesClose').onclick=()=>$('gestureChoices').close();

  function drawPreview(sample){
    if($('settingsPanel').hidden||!preview.getBoundingClientRect().height||performance.now()-lastPreview<65)return;
    lastPreview=performance.now();
    const ctx=preview.getContext('2d'),w=preview.width,h=preview.height,b=p.bounds;
    ctx.clearRect(0,0,w,h);ctx.fillStyle='#041b20';ctx.fillRect(0,0,w,h);
    ctx.strokeStyle='#59968a';ctx.setLineDash([4,5]);ctx.strokeRect(b.left*w,b.top*h,(b.right-b.left)*w,(b.bottom-b.top)*h);ctx.setLineDash([]);
    const landmarks=sample.landmarks;
    if(!Array.isArray(landmarks)||landmarks.length!==21)return;
    const xy=landmarks.map(([x,y])=>[(p.mirror?1-x:x)*w,y*h]);
    ctx.strokeStyle=sample.pose==='fist'?'#efc28b':'#8bf9e0';ctx.lineWidth=2;
    for(const path of connections){ctx.beginPath();path.forEach((i,j)=>ctx[j?'lineTo':'moveTo'](...xy[i]));ctx.stroke();}
    ctx.fillStyle='#d0fff4';for(const [x,y] of xy){ctx.beginPath();ctx.arc(x,y,3,0,Math.PI*2);ctx.fill();}
  }
  function calibrate(sample){
    if(!calibration)return;
    if(sample.tracked&&sample.pose==='open')calibration.points.push([p.mirror?1-sample.x:sample.x,sample.y]);
    const remaining=Math.ceil((calibration.end-performance.now())/1000);
    message(`Calibration: move your open hand around your comfortable reach (${Math.max(0,remaining)}s).`);
    if(remaining>0)return;
    const points=calibration.points;calibration=null;
    $('gestureCalibrate').disabled=false;
    if(points.length<30){message('Calibration needs a visible open hand. Try again.');return;}
    const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);
    const bounds={left:Math.min(...xs),right:Math.max(...xs),top:Math.min(...ys),bottom:Math.max(...ys)};
    if(bounds.right-bounds.left<.2||bounds.bottom-bounds.top<.2){message('Move farther horizontally and vertically, then calibrate again.');return;}
    p.bounds=bounds;core.configure(p);cancel();save();message('Reach calibrated. Open your hand to resume.');
  }
  function disconnect(){
    generation++;clearTimeout(retry);clearInterval(watchdog);retry=watchdog=0;
    const old=socket;socket=null;if(old){old.onclose=old.onmessage=old.onerror=null;old.close();}
    cancel();calibration=null;$('gestureCalibrate').disabled=false;receivedReady=false;
    $('gesturePerformance').textContent='';
  }
  function connect(){
    disconnect();if(disposed||!p.enabled||document.hidden)return;
    const gen=generation;receivedReady=false;lastSeq=0;lastFrame=performance.now();
    message('Starting the Raspberry Pi ribbon camera…');status('Hand control · starting');badge.hidden=false;topLayer();
    const ws=socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws/gestures`);
    let failed=false;
    ws.onopen=()=>{if(gen===generation)ws.send(JSON.stringify({hand:p.hand,rotation:p.rotation}));};
    ws.onmessage=event=>{
      if(gen!==generation||disposed)return;
      let data;try{data=JSON.parse(event.data);}catch{return;}
      if(data.type==='ready'){
        receivedReady=true;message(`${data.camera} · ${data.accelerator}. Open your hand to begin.`);return;
      }
      if(data.type==='error'){
        failed=true;clearInterval(watchdog);cancel();message(data.message);status('Hand control · unavailable');return;
      }
      if(data.type!=='frame'||data.seq<=lastSeq)return;
      const now=performance.now();lastSeq=data.seq;lastFrame=now;
      drawPreview(data);
      if(calibration){calibrate(data);return;}
      core.update(data,now,innerWidth,innerHeight);
      if(!data.tracked){cursor.hidden=true;highlight(null);status('Hand control · show your hand');}
      else status(core.state==='dragging'&&dragging?'Hand control · rotating':core.state==='pressed'?'Hand control · pressed':core.state==='unarmed'?'Hand control · open your hand':'Hand control · ready');
      $('gesturePerformance').textContent=`${data.fps} fps · ${data.inference_ms} ms inference`;
    };
    ws.onerror=()=>{if(gen===generation){cancel();message('Cannot connect to hand tracking. Check the local service.');}};
    ws.onclose=()=>{
      if(gen!==generation)return;
      cancel();clearInterval(watchdog);
      if(!failed){message('Tracking disconnected. Retrying…');status('Hand control · reconnecting');retry=setTimeout(connect,2000);}
    };
    watchdog=setInterval(()=>{
      if(performance.now()-lastFrame>(receivedReady?300:26000)){
        cancel();status('Hand control · waiting for camera');
        if(calibration){calibration=null;$('gestureCalibrate').disabled=false;message('Calibration stopped because tracking stalled. Retry the camera.');}
      }
      if(target&&!validTarget(target))cancel();
    },100);
  }
  toggle.checked=p.enabled;$('gestureMirror').checked=p.mirror;$('gestureHand').value=p.hand;
  $('gestureRotation').value=p.rotation;$('gestureSensitivity').value=p.sensitivity;
  $('gestureSensitivityValue').textContent=`${p.sensitivity.toFixed(1)}×`;
  toggle.onchange=()=>{
    p.enabled=toggle.checked;save();
    if(p.enabled)connect();else{disconnect();badge.hidden=true;try{overlay.hidePopover();}catch{}message('Hand control is off.');}
  };
  $('gestureMirror').onchange=()=>{p.mirror=$('gestureMirror').checked;p.bounds={...defaults.bounds};core.configure(p);cancel();save();};
  $('gestureSensitivity').oninput=()=>{p.sensitivity=Number($('gestureSensitivity').value);$('gestureSensitivityValue').textContent=`${p.sensitivity.toFixed(1)}×`;core.configure(p);cancel();save();};
  for(const [id,key] of [['gestureHand','hand'],['gestureRotation','rotation']])$(id).onchange=()=>{
    p[key]=key==='rotation'?Number($(id).value):$(id).value;
    if(key==='rotation')p.bounds={...defaults.bounds};
    core.configure(p);save();connect();
  };
  $('gestureRetry').onclick=()=>{if(!p.enabled){p.enabled=toggle.checked=true;save();}connect();};
  $('gestureCalibrate').onclick=()=>{
    if(!receivedReady||!socket||socket.readyState!==WebSocket.OPEN){message('Enable hand control and wait for the camera before calibrating.');return;}
    cancel();calibration={end:performance.now()+8000,points:[]};$('gestureCalibrate').disabled=true;
    message('Move your open hand around your comfortable reach for 8 seconds.');
  };
  $('gestureReset').onclick=()=>{p.bounds={...defaults.bounds};p.sensitivity=1;$('gestureSensitivity').value=1;$('gestureSensitivityValue').textContent='1.0×';core.configure(p);cancel();save();message('Default reach restored.');};
  function escape(event){
    if(event.key!=='Escape'||!p.enabled)return;
    p.enabled=toggle.checked=false;disconnect();save();badge.hidden=true;
    try{overlay.hidePopover();}catch{}message('Hand control paused. Enable it to resume.');
  }
  function visibility(){if(document.hidden){disconnect();}else if(p.enabled)connect();}
  function physical(event){if(event.isTrusted){cancel();}}
  document.addEventListener('keydown',escape,true);
  document.addEventListener('visibilitychange',visibility);
  document.addEventListener('pointerdown',physical,true);
  const dialogs=new MutationObserver(records=>{if(records.some(r=>r.target.tagName==='DIALOG'&&r.attributeName==='open')){cancel();topLayer();}});
  dialogs.observe(document.body,{subtree:true,attributes:true,attributeFilter:['open']});
  drawPreview({});if(p.enabled)connect();
  return {dispose(){disposed=true;disconnect();dialogs.disconnect();badge.hidden=true;try{overlay.hidePopover();}catch{}
    document.removeEventListener('keydown',escape,true);document.removeEventListener('visibilitychange',visibility);document.removeEventListener('pointerdown',physical,true);}};
}
