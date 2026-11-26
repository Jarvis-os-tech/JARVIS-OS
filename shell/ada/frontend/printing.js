import {createPlateViewer,partColors} from './plate-viewer.js';

const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
let root,viewer,catalogue,draft,selected='',job=null,preview=null,report=null,printerState=null,timer=0,epoch=0,inspection=0,busy=false;
const $=s=>root.querySelector(s),copy=o=>JSON.parse(JSON.stringify(o));
async function request(path,body){const r=await fetch('/api/printing'+path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:'Check the print settings and try again.');return d;}
function button(text,action,cls=''){const b=el('button',cls,text);b.type='button';b.onclick=()=>Promise.resolve().then(action).catch(error);return b;}
function error(e){if(root){$('.print-notice').textContent=e.message||String(e);$('.print-notice').dataset.error='true';}}
function notice(text){$('.print-notice').textContent=text;$('.print-notice').dataset.error='false';}
function key(){return 'ada-plate:'+catalogue.project_id+':'+catalogue.revision_id;}
function persist(){if(!catalogue||!draft)return;try{localStorage.setItem(key(),JSON.stringify({draft,job_id:job?.id}));}catch{}}
function current(){return draft.instances.find(i=>i.id===selected);}
function partFor(item){return catalogue.parts.find(p=>p.id===item.part_id);}
function field(label,input){const l=el('label','print-field');l.append(el('span','',label),input);return l;}
function number(value,min,max,step,change){const i=el('input');i.type='number';i.value=value;i.min=min;i.max=max;i.step=step;i.onchange=()=>{const n=Number(i.value);if(!Number.isFinite(n)||n<min||n>max){i.value=value;return;}change(n);};return i;}
function select(values,value,change){const s=el('select');for(const [v,label] of values){const o=el('option','',label);o.value=v;s.append(o);}s.value=value;s.onchange=()=>change(s.value);return s;}
function check(label,value,change){const l=el('label','print-check'),i=el('input');i.type='checkbox';i.checked=value;i.onchange=()=>change(i.checked);l.append(i,document.createTextNode(label));return l;}

export async function openPrinting(projectId,revisionId){
  closePrinting();const token=++epoch;
  root=el('section','print-workspace');root.id='printWorkspace';root.setAttribute('aria-label','Prepare print');
  root.innerHTML=`<header class="print-header"><div><p class="print-eyebrow">ADA / FABRICATION</p><h2>Prepare your build<span>.</span></h2><p class="print-project"></p></div><div class="print-header-right"><span class="print-connection">Checking K2…</span><button class="print-close" aria-label="Close print preparation">×</button></div></header>
  <div class="print-body"><aside class="print-parts"><div class="print-section-heading"><span>01 / PLATE CONTENTS</span><strong class="print-count"></strong></div><div class="print-part-list"></div><div class="print-add"></div><div class="print-part-detail"></div></aside>
  <main class="print-main"><div class="print-view-top"><div class="print-view-switch"></div><span>CREALITY K2 · 0.4 MM</span></div><div class="print-viewport"><div class="print-viewer"></div><div class="print-plate-label"><strong>Plate 01</strong><span>260 × 260 × 260 mm</span></div><div class="print-legend"><span>● Parts</span><span>● Supports</span><span>● Brim / skirt</span></div><div class="print-view-hint">Drag to orbit · Scroll to zoom</div></div><div class="print-view-toolbar"></div><div class="print-layer-panel" hidden></div><div class="print-summary"></div></main>
  <aside class="print-settings"><div class="print-section-heading"><span>02 / PRINT SETTINGS</span></div><div class="print-options"></div><details class="print-device"><summary>Printer & filament connection</summary><div></div></details><details class="print-history"><summary>Saved plates & print history</summary><div></div></details><div class="print-readiness"></div><div class="print-estimates"></div><div class="print-confirmations"></div><div class="print-send-actions"></div></aside></div>
  <footer class="print-footer"><p class="print-notice" role="status" aria-live="polite">Reading the saved CAD parts…</p><div class="print-footer-actions"></div></footer>`;
  document.body.append(root);document.body.classList.add('print-open');$('.print-close').onclick=closePrinting;
  try{
    const [data,status]=await Promise.all([request(`/projects/${projectId}?revision_id=${encodeURIComponent(revisionId)}`),request('/status')]);
    if(token!==epoch)return;catalogue=data;printerState=status;preview=null;report=null;job=null;busy=false;
    draft={project_id:projectId,revision_id:revisionId,instances:data.instances,material:status.settings.material==='PETG'?'PETG':'PLA',quality:'standard',infill:30,supports:'everywhere',support_angle:45,brim:false,acknowledge_stale:false};
    let saved;try{saved=JSON.parse(localStorage.getItem(key()));if(saved?.draft?.revision_id===revisionId)draft=saved.draft;}catch{}
    selected=draft.instances[0]?.id||'';$('.print-project').textContent=data.title+' · Saved CAD '+revisionId.slice(0,8);
    const v=await createPlateViewer($('.print-viewer'),data,selectPart,changePart);if(token!==epoch){v.dispose();return;}viewer=v;
    $('.print-view-switch').append(button('Build plate',()=>showMode(false),'active'),button('Sliced layers',()=>showMode(true)));
    $('.print-view-toolbar').append(button('↗ Perspective',()=>viewer.fit()),button('Top view',()=>viewer.fit(true)),button('Move part',()=>{viewer.setMode('move');$('.print-view-hint').textContent='Drag a part on the plate · Use Perspective to orbit again';}),button('Lay on face',()=>{viewer.setMode('face');$('.print-view-hint').textContent='Click a face to place it down on the bed';}),button('Auto arrange',arrange));
    $('.print-view-toolbar').firstChild.onclick=()=>{viewer.setMode('orbit');viewer.fit();$('.print-view-hint').textContent='Drag to orbit · Scroll to zoom';};
    renderParts();renderOptions();renderDevice();renderStatus();
    timer=setInterval(()=>poll().catch(error),3000);
    await inspect();
    if(saved?.job_id){try{const j=await request('/jobs/'+saved.job_id);if(JSON.stringify(j.request)===JSON.stringify(draft)||sameDraft(j.request,draft))await loadJob(j);}catch{}}
  }catch(e){if(token===epoch)error(e);}
}
function sameDraft(a,b){return JSON.stringify(Object.keys(a).sort().map(k=>[k,a[k]]))===JSON.stringify(Object.keys(b).sort().map(k=>[k,b[k]]));}
export function closePrinting(){++epoch;++inspection;clearInterval(timer);timer=0;viewer?.dispose();viewer=null;root?.remove();root=null;catalogue=null;draft=null;job=null;preview=null;document.body.classList.remove('print-open');}

function renderParts(){
  const host=$('.print-part-list');host.replaceChildren();$('.print-count').textContent=draft.instances.length+' parts';
  for(const item of draft.instances){const part=partFor(item),idx=catalogue.parts.indexOf(part),row=button('',()=>selectPart(item.id),'print-part-row');row.dataset.platePart=item.id;row.style.setProperty('--part-color',partColors[idx%partColors.length]);
    row.append(el('span','print-part-dot'),el('span','',part.name),el('small','',item.id.split('-').at(-1)));row.classList.toggle('selected',selected===item.id);host.append(row);}
  const add=$('.print-add');add.replaceChildren();const choice=select(catalogue.parts.map(p=>[p.id,p.name]),catalogue.parts[0].id,()=>{});
  add.append(choice,button('+ Add',()=>{if(draft.instances.length>=32)throw Error('A plate supports up to 32 copies.');const p=catalogue.parts.find(p=>p.id===choice.value);const item={id:p.id+'-'+crypto.randomUUID().slice(0,8),part_id:p.id,rotation:p.orientations[0].rotation,position:[130,130]};draft.instances.push(item);selected=item.id;changed();}));
  renderPart();
}
function selectPart(id){selected=id;viewer?.select(id);renderParts();}
function renderPart(){
  const host=$('.print-part-detail');host.replaceChildren();const item=current();if(!item)return;const p=partFor(item),m=report?.parts.find(p=>p.id===item.id);
  host.append(el('p','print-eyebrow','SELECTED PART'),el('h3','',p.name));
  const dimensions=m?.size_mm||p.dimensions_mm;host.append(el('p','print-dimensions',dimensions.map(n=>Number(n.toFixed(1))).join(' × ')+' mm'),el('p','print-footnote',`${draft.instances.filter(i=>i.part_id===p.id).length} on this plate · ${p.quantity} required for the assembly`));
  const best=p.orientations[0],recommend=el('div','print-recommendation');recommend.append(el('strong','','Suggested orientation'),el('p','',`${best.label} · ${best.contact_mm2} mm² bed contact · ${best.overhang_mm2} mm² overhang`),button('Use suggested face',()=>changePart(item.id,{rotation:copy(best.rotation)})));host.append(recommend);
  host.append(field('Orientation',select([['custom','Custom rotation'],...p.orientations.map((o,i)=>[String(i),o.label])],String(p.orientations.findIndex(o=>o.rotation.every((v,k)=>Math.abs(v-item.rotation[k])<.01))),v=>{if(v!=='custom')changePart(item.id,{rotation:copy(p.orientations[Number(v)].rotation)});})));if(!host.querySelector('select').value)host.querySelector('select').value='custom';
  const rotates=el('div','print-three-fields');['X','Y','Z'].forEach((axis,k)=>rotates.append(field(axis+' °',number(item.rotation[k],-360,360,1,v=>{const r=[...item.rotation];r[k]=v;changePart(item.id,{rotation:r});}))));host.append(rotates);
  const positions=el('div','print-two-fields');['X','Y'].forEach((axis,k)=>positions.append(field(axis+' mm',number(item.position[k],-1000,1000,1,v=>{const p=[...item.position];p[k]=v;changePart(item.id,{position:p});}))));host.append(positions);
  host.append(el('p','print-support-note',m?m.support_recommended?'Overhangs detected · review supports and bridges':'No substantial overhang detected':''));
  const notes=el('details','print-design-notes');notes.open=true;notes.append(el('summary','','CAD designer’s print notes'),el('p','',p.notes));host.append(notes);
  host.append(button('Remove from this plate',()=>{if(draft.instances.length===1)throw Error('Keep at least one part on the plate.');draft.instances=draft.instances.filter(i=>i.id!==item.id);selected=draft.instances[0].id;changed();},'print-remove'));
}
function changePart(id,values){const item=draft.instances.find(i=>i.id===id);if(!item)return;Object.assign(item,values);changed();}
function changed(){job=null;preview=null;report=null;inspection++;viewer?.toolpaths(null);viewer?.update(draft.instances);$('.print-layer-panel').hidden=true;$('.print-view-toolbar').hidden=false;$('.print-view-switch').children[0].classList.add('active');$('.print-view-switch').children[1].classList.remove('active');persist();renderParts();renderStatus();inspect().catch(error);}
async function inspect(){const seq=++inspection,token=epoch,r=await request('/inspect',draft);if(seq!==inspection||token!==epoch)return;report=r;viewer?.update(draft.instances,r);renderPart();renderStatus();persist();}
async function arrange(){const token=epoch,seq=inspection;const r=await request('/arrange',draft);if(token!==epoch||seq!==inspection)return;draft.instances=r.instances;changed();if(r.errors.length)error(Error(r.errors.join(' ')));}
function renderOptions(){
  const host=$('.print-options');host.replaceChildren();
  for(const [key,label,values] of [['material','Material',[['PLA','PLA'],['PETG','PETG']]],['quality','Layer height',[['fine','0.12 mm · Fine'],['standard','0.20 mm · Standard'],['draft','0.28 mm · Draft']]],['supports','Supports',[['everywhere','Automatic · Everywhere'],['buildplate','Automatic · Build plate only'],['off','Off']]]])host.append(field(label,select(values,draft[key],v=>{draft[key]=v;changed();})));
  host.append(field('Infill %',number(draft.infill,5,100,5,v=>{draft.infill=v;changed();})),field('Support threshold °',number(draft.support_angle,30,70,5,v=>{draft.support_angle=v;changed();})),check('Add a 5 mm brim',draft.brim,v=>{draft.brim=v;changed();}));
  host.append(el('p','print-footnote','5 walls · Gyroid infill · Snug supports. Geometry suggestions do not evaluate strength or support removal. Inspect holes and mating faces in sliced layers.'));
  if(catalogue.stale)host.append(check('Use this earlier saved CAD revision',draft.acknowledge_stale,v=>{draft.acknowledge_stale=v;changed();}));
}
function renderDevice(){
  const host=$('.print-device div');host.replaceChildren();const s=printerState.settings,inputs={};
  for(const [k,label] of [['host','Printer IP'],['hostname','Expected printer name']]){const i=el('input');i.value=s[k];inputs[k]=i;host.append(field(label,i));}
  inputs.port=number(s.port,1,65535,1,()=>{});host.append(field('Port',inputs.port));
  inputs.material=select([['unknown','Select loaded material'],['PLA','PLA'],['PETG','PETG']],s.material,()=>{});host.append(field('Loaded material',inputs.material));
  inputs.source=select([['unknown','Select feed source'],['cfs','CFS'],['external','External spool']],s.source,()=>{});host.append(field('Feed source',inputs.source));
  inputs.cfs_box=number(s.cfs_box,1,4,1,()=>{});inputs.cfs_slot=number(s.cfs_slot,1,4,1,()=>{});host.append(field('CFS box',inputs.cfs_box),field('CFS slot',inputs.cfs_slot));
  host.append(button('Save & check connection',async()=>{const values={...s};for(const [k,i] of Object.entries(inputs))values[k]=['port','cfs_box','cfs_slot'].includes(k)?Number(i.value):i.value;const settings=await request('/settings',values);printerState.settings=settings;await checkConnection();}));
  host.append(el('p','print-footnote',s.profile_verified?'Machine profile verified.':'Machine profile awaits a supervised calibration print (up to 30 mm), then inspection.'));
}
async function checkConnection(){
  const token=epoch;
  printerState.printer={connected:false,ready:false,state:'checking',message:'Checking printer…'};renderStatus();
  try{
    const status=await request('/test',{});if(token!==epoch)return;
    printerState.printer=status;renderStatus();notice(status.connected?'Printer connected.':status.message);
  }catch(e){
    if(token!==epoch)return;
    printerState.printer={connected:false,ready:false,state:'unknown',message:'Could not check the printer. '+e.message};renderStatus();throw e;
  }
}
function renderStatus(){
  if(!catalogue||!root)return;const p=printerState?.printer||{},state=job?.status;
  $('.print-connection').textContent=p.connected?'● K2 · '+p.state:({checking:'Checking K2…',unconfigured:'Set K2 IP',unknown:'K2 status unavailable'}[p.state]||'○ K2 OFFLINE');$('.print-connection').dataset.online=String(!!p.connected);
  $('.print-connection').title=p.message||'';
  const ready=$('.print-readiness');ready.replaceChildren();const problems=report?.errors||[];
  ready.append(el('h3','',problems.length?'Plate needs adjustment':'Plate checks'));
  ready.append(el('p',problems.length?'print-problem':'print-good',!report?'Checking plate…':problems.length?problems.join(' '):'✓ Parts fit the usable area · Spacing checked'));
  const needing=report?.parts.filter(p=>p.support_recommended).length||0;
  ready.append(el('p','print-support-note',`${needing} part${needing===1?'':'s'} with overhangs · ${draft.supports==='off'?'supports off':'automatic supports enabled'}`));
  if(!p.ready)ready.append(el('p',p.state==='checking'?'print-footnote':'print-problem',p.message||'Printer is not ready.'));
  const connection=button('Check connection',checkConnection,'print-secondary');connection.disabled=p.state==='checking';ready.append(connection);
  if(report?.warnings.length){const d=el('details');d.append(el('summary','',`Review ${report.warnings.length} geometry notes`));for(const w of report.warnings)d.append(el('p','',w));ready.append(d);}
  const summary=$('.print-summary');summary.replaceChildren();summary.append(el('span','',`${draft.instances.length} parts on this plate`),el('span','',draft.material+' · '+(draft.quality==='fine'?'0.12':draft.quality==='draft'?'0.28':'0.20')+' mm'),el('span','',state?state.replaceAll('_',' '):'Layout · not yet sliced'));
  const estimates=$('.print-estimates');estimates.replaceChildren();
  for(const [label,value] of [['ESTIMATED TIME',job?.summary?.estimate||'—'],['FILAMENT',job?.summary?.filament_g?job.summary.filament_g.toFixed(1)+' g':'—']]){const d=el('div');d.append(el('span','',label),el('strong','',value));estimates.append(d);}
  const actions=$('.print-footer-actions');actions.replaceChildren();const slice=button(busy||state==='slicing'||state==='queued'?'Slicing plate…':'Slice & review plate →',slicePlate,'print-primary');slice.disabled=busy||['queued','slicing'].includes(state)||!report?.valid;actions.append(slice);
  if(job?.summary)actions.prepend(button('Review layers',()=>showMode(true),'print-secondary'));
  const send=$('.print-send-actions');send.replaceChildren();const upload=button(state==='uploaded'?'Send again':'Send to K2',async()=>{const token=epoch,id=job.id;const result=await request('/jobs/'+id+'/upload',{fingerprint:job.fingerprint});if(token!==epoch||job?.id!==id)return;job=result;persist();renderStatus();notice('File sent to K2. Ready for your start command.');},'print-secondary');upload.disabled=!['ready','uploaded'].includes(state)||busy||!p.ready;send.append(upload);
  const confirmations=$('.print-confirmations');
  if(confirmations.dataset.job!==job?.id){confirmations.replaceChildren();confirmations.dataset.job=job?.id||'';for(const [key,label] of [['bed_clear','Build plate is clear'],['filament_ready','Correct filament is loaded'],['calibration_test','Supervised calibration test (≤30 mm)']]){const c=check(label,false,()=>{});c.querySelector('input').name=key;confirmations.append(c);}}
  confirmations.hidden=state!=='uploaded';
  const start=button('Start print',async()=>{const body={fingerprint:job.fingerprint};for(const i of confirmations.querySelectorAll('input'))body[i.name]=i.checked;await mutateJob('start',body,'Start requested. Waiting for the printer to confirm.');},'print-primary');start.disabled=state!=='uploaded'||!p.ready;send.append(start);
  if(job?.summary){const a=el('a','print-download','Download G-code');a.href='/api/printing/jobs/'+job.id+'/gcode';a.download='';send.append(a);}
  if(['printing','paused'].includes(state)){send.append(el('p','',`${p.progress||0}% · Nozzle ${Math.round(p.nozzle||0)}° · Bed ${Math.round(p.bed||0)}°`));for(const a of [state==='paused'?'resume':'pause','cancel'])send.append(button(a[0].toUpperCase()+a.slice(1),()=>controlPrint({action:a})));}
  if(['starting','start_unknown'].includes(state))send.append(button('Reconcile after checking printer',()=>mutateJob('resolve',{})));
  if(state==='complete'&&job.calibration_test)send.append(button('Test print looks good · Verify profile',async()=>{await request('/jobs/'+job.id+'/verify',{});await poll();renderDevice();}));
  if(job?.error)error(Error(job.error));else if(!busy)notice(state==='slicing'?'Generating actual toolpaths, supports and estimates…':state==='ready'?'Sliced plate ready. Inspect the layers before sending.':state==='uploaded'?'Uploaded to K2 · Print has not started.':'Arrange parts, review orientation, then slice this plate.');
  const history=$('.print-history div');history.replaceChildren();for(const j of (printerState?.jobs||[]).filter(j=>j.request.project_id===catalogue.project_id).slice(0,12))history.append(button(`${j.title} · ${j.status} · ${new Date(j.created*1000).toLocaleDateString()}`,()=>loadJob(j)));
}
async function slicePlate(){
  if(busy)return;busy=true;renderStatus();const token=epoch,body=copy(draft);
  try{const result=await request('/jobs',body);if(token!==epoch)return;if(!sameDraft(body,draft)){notice('A previous layout is slicing. Slice again to use your changes.');return;}job=result;preview=null;persist();}
  finally{if(token===epoch){busy=false;renderStatus();}}
}
async function mutateJob(action,body,message){const token=epoch,id=job?.id;if(!id)throw Error('Select a saved print job.');const result=await request('/jobs/'+id+'/'+action,body);if(token===epoch&&job?.id===id){job=result;persist();renderStatus();if(message)notice(message);}return result;}
async function loadJob(j){
  if(j.request.revision_id!==catalogue.revision_id){await openPrinting(j.request.project_id,j.request.revision_id);if(!root)return;}
  viewer.toolpaths(null);$('.print-layer-panel').hidden=true;$('.print-view-toolbar').hidden=false;
  $('.print-view-switch').children[0].classList.add('active');$('.print-view-switch').children[1].classList.remove('active');
  const token=epoch;
  draft=copy(j.request);job=j;preview=null;selected=draft.instances[0].id;renderParts();renderOptions();await inspect();if(token!==epoch||job?.id!==j.id)return;persist();
  if(j.summary){const data=await request('/jobs/'+j.id+'/preview');if(token!==epoch||job?.id!==j.id)return;preview=data;renderLayers();}
  renderStatus();
}
async function poll(){
  const token=epoch,data=await request('/status');if(token!==epoch)return;printerState=data;
  if(job){const latest=data.jobs.find(j=>j.id===job.id);if(latest){const completed=!job.summary&&latest.summary;job=latest;if(completed){const id=job.id,paths=await request('/jobs/'+id+'/preview');if(token!==epoch||job?.id!==id)return;preview=paths;renderLayers();persist();await showMode(true);}}}
  renderStatus();
}
async function showMode(sliced){
  const token=epoch,id=job?.id;
  if(sliced&&!job?.summary)throw Error('Slice the plate to see actual supports and toolpaths.');
  if(sliced&&!preview){const paths=await request('/jobs/'+id+'/preview');if(token!==epoch||job?.id!==id)return;preview=paths;}
  $('.print-view-switch').children[0].classList.toggle('active',!sliced);$('.print-view-switch').children[1].classList.toggle('active',sliced);
  $('.print-layer-panel').hidden=!sliced;$('.print-view-toolbar').hidden=sliced;
  if(sliced){renderLayers();drawLayer();}else viewer.toolpaths(null);
}
function renderLayers(){
  const host=$('.print-layer-panel');host.replaceChildren();if(!preview)return;
  const slider=el('input');slider.type='range';slider.min=0;slider.max=preview.layers.length-1;slider.value=slider.max;slider.setAttribute('aria-label','Print layer');slider.oninput=drawLayer;
  host.append(el('span','print-layer-label'),slider,check('Only this layer',false,drawLayer));
  if(preview.truncated)host.append(el('small','','Dense layers are simplified in this preview. Download G-code for the complete toolpath.'));
}
function drawLayer(){if(!preview||!viewer)return;const index=Number($('.print-layer-panel input[type=range]').value),only=$('.print-layer-panel input[type=checkbox]').checked;$('.print-layer-label').textContent=`Layer ${index+1} / ${preview.layers.length} · Z ${preview.layers[index]?.z||0} mm`;viewer.toolpaths(preview,index,only);}

export function printingState(){return {print_view_open:!!root,print_revision:catalogue?.revision_id,plate_instances:root?draft?.instances:[],print_job:root&&job?{id:job.id,status:job.status,summary:job.summary}:null,printer:printerState?.printer};}
export async function controlPlate(args){
  if(!root||!draft)throw Error('Prepare a saved CAD revision first.');
  const item=args.instance_id?draft.instances.find(i=>i.id===args.instance_id):current();
  if(args.action==='status')return printingState();
  if(args.action==='slice')await slicePlate();
  else if(args.action==='layers')await showMode(true);
  else if(args.action==='plate')await showMode(false);
  else if(args.action==='arrange')await arrange();
  else if(args.action==='select'){if(!item)throw Error('Choose an exact plate instance.');selectPart(item.id);}
  else if(args.action==='orientation'){if(!item)throw Error('Choose an exact plate instance.');changePart(item.id,{rotation:[args.x??item.rotation[0],args.y??item.rotation[1],args.z??item.rotation[2]]});}
  else if(args.action==='supports'){if(!['off','buildplate','everywhere'].includes(args.mode))throw Error('Choose off, buildplate or everywhere.');draft.supports=args.mode;renderOptions();changed();}
  return printingState();
}
export async function controlPrint(args){
  const status=await request('/test',{});if(!['pause','resume','cancel'].includes(args.action))throw Error('Unknown printer control.');
  if(!job?.filename||status.filename!==job.filename)throw Error('The printer is running a different file. Check its screen.');
  const r=await request('/control',{action:args.action,filename:job.filename});await poll();return r;
}
