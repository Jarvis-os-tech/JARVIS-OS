import {openPrinting,closePrinting} from './printing.js';
const $=s=>root.querySelector(s);
const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
let root,hooks,snapshot,viewer=null,manifest=null,selected='',chosenRevision='',loaded='',sequence=0,opened=false,loading=false;
let clock=null,planSelected='',planSignature='',followBuild=true;
const busyStates=['queued','designing','reviewing_plan','building','checking','reviewing'];
const steps=[['designing','Design'],['reviewing_plan','Part review'],['building','Build'],['checking','Fit checks'],['reviewing','Assembly review']];
const labels={planning:'Ready when you are',queued:'Queued',designing:'Designing',reviewing_plan:'Reviewing parts',building:'Building',checking:'Checking fit',reviewing:'Reviewing assembly',ready:'Geometry checked',needs_review:'Needs review',needs_input:'Measurements needed',error:'Build interrupted',interrupted:'Build interrupted',cancelled:'Cancelled'};
const fmt=n=>Number(n).toLocaleString(undefined,{maximumFractionDigits:2});
function button(text,action,cls=''){const b=el('button',cls,text);b.type='button';b.onclick=()=>Promise.resolve().then(action).catch(hooks.report);return b;}
function link(text,path,download=true){const a=el('a','cad-download',text);a.href=hooks.fileURL(path,download,snapshot.active_id);if(download)a.download='';return a;}
function read(text,path){return button(text,()=>hooks.openFile(path),'cad-text-button');}

export function setupCad(options){
  hooks=options;root=el('section','cad-workspace');root.id='cadWorkspace';root.hidden=true;root.setAttribute('aria-label','CAD design studio');
  root.innerHTML=`<header class="cad-header"><div><p class="cad-eyebrow">ADA / DESIGN STUDIO</p><h2>From idea to assembly<span class="cad-title-dot"></span></h2></div><div class="cad-version-tools"><select aria-label="CAD version" class="cad-versions"></select><span class="cad-model-label"></span></div></header>
  <ol class="cad-pipeline" aria-label="CAD generation progress"></ol>
  <div class="cad-layout"><aside class="cad-parts"><div class="cad-section-title"><h3>Components</h3><span class="cad-count">—</span></div><div class="cad-part-list"></div><div class="cad-part-detail"></div></aside>
  <div class="cad-centre"><div class="cad-viewport"><div class="cad-grid-overlay"></div><div class="cad-viewer-host"></div><div class="cad-empty"><div class="cad-reactor"><i></i><i></i><i></i><span>◇</span></div><h3>Your design, assembled.</h3><p>Finish planning to create precise parts and see how they fit together.</p></div><div class="cad-view-label"><span class="cad-live-dot"></span><span class="cad-view-name">ASSEMBLY</span></div><div class="cad-scale"></div><div class="cad-load-notice" role="status"></div></div><div class="cad-toolbar"></div><div class="cad-revision-request"><form><input aria-label="Revise CAD design" maxlength="4000" placeholder="Make the base wider, increase the clearance…"><button type="submit">Revise design ↗</button></form></div></div>
  <aside class="cad-review"><section class="cad-activity" hidden><div class="cad-section-title"><h3>Design activity</h3><span class="cad-elapsed"></span></div><div class="cad-now"><span class="cad-eyebrow">CURRENT STEP</span><p class="cad-now-title"></p><p class="cad-now-detail"></p></div><div class="cad-activity-list" role="log" aria-label="CAD design activity"></div></section><div class="cad-section-title"><h3>Design checks</h3><span class="cad-check-symbol">◇</span></div><div class="cad-check-list"></div><div class="cad-review-notes"></div><div class="cad-files"></div></aside></div>
  <footer class="cad-footer"><div><span class="cad-status" role="status" aria-live="polite"></span><p class="cad-stale" hidden></p></div><div class="cad-actions"></div></footer>`;
  hooks.host.append(root);
  const telemetry=el('section','cad-telemetry');telemetry.hidden=true;
  telemetry.innerHTML='<div class="cad-section-title"><h3>Carbon & tools</h3><span class="cad-stream-state"></span></div><div class="cad-token-usage" aria-label="Reported token usage"></div><p class="cad-token-note"></p><details class="cad-thinking-panel" open><summary>Carbon’s thinking summary</summary><p class="cad-thinking-text"></p></details><details class="cad-call-panel"><summary>Requests & CAD tools <span class="cad-call-count"></span></summary><p class="cad-footnote">Carbon supplies the design and code. Ada runs the build123d tools below. Model-side tools are not enabled.</p><div class="cad-call-list"></div></details>';
  $('.cad-activity').before(telemetry);
  const build=el('div','cad-build-progress');build.hidden=true;build.innerHTML='<div><span class="cad-build-count"></span><span class="cad-preview-state"></span></div><progress aria-label="Parts built"></progress>';
  build.append(button('Follow build',()=>{followBuild=true;chosenRevision='';planSignature='';void updateCad(snapshot).catch(hooks.report);},'cad-follow'));
  $('.cad-centre').prepend(build);
  for(const [id,label] of steps){const item=el('li');item.dataset.step=id;item.append(el('span','cad-step-dot'),el('span','',label));$('.cad-pipeline').append(item);}
  for(const [label,action] of [['Fit view','fit'],['Explode','explode'],['Assemble','assemble'],['Orbit','orbit'],['Stop orbit','stop_orbit'],['Show all','show_all']]){
    const b=button(label,()=>control({action}),'cad-view-button');b.dataset.cadAction=action;$('.cad-toolbar').append(b);
  }
  $('.cad-versions').onchange=()=>{chosenRevision=$('.cad-versions').value;loaded='';void updateCad(snapshot).catch(hooks.report);};
  $('.cad-revision-request form').onsubmit=e=>{e.preventDefault();const input=$('.cad-revision-request input');if(!input.value.trim())return;void generate(input.value.trim(),true).then(()=>input.value='').catch(hooks.report);};
}

async function generate(instruction='',regenerate=false){
  if(loading)return;loading=true;$('.cad-actions').querySelectorAll('button').forEach(b=>b.disabled=true);
  try{await hooks.act('generate_cad',{instruction,regenerate,request_id:crypto.randomUUID()});chosenRevision='';}
  finally{loading=false;renderStatus();}
}

export async function openCad(next){
  opened=true;root.hidden=false;document.body.classList.add('cad-open');
  if(!clock)clock=setInterval(renderElapsed,1000);
  await updateCad(next);
}

export function closeCad(){
  closePrinting();
  if(!root)return;opened=false;root.hidden=true;document.body.classList.remove('cad-open');
  clearInterval(clock);clock=null;
  sequence++;viewer?.dispose();viewer=null;loaded='';$('.cad-viewer-host').replaceChildren();
}

export async function updateCad(next){
  if(!root)return;
  if(snapshot?.cad?.job_id!==next.cad?.job_id){chosenRevision='';planSelected='';planSignature='';followBuild=true;}
  if(snapshot?.active_id!==next.active_id){chosenRevision='';loaded='';manifest=null;selected='';planSelected='';planSignature='';followBuild=true;viewer?.dispose();viewer=null;sequence++;}
  snapshot=next;if(!opened)return;
  if(!snapshot.project){closeCad();return;}
  renderStatus();
  const cad=snapshot.cad||{},entry=(cad.history||[]).find(e=>e.id===chosenRevision)||cad.preview||cad.current;
  if(!entry){if(manifest){viewer?.dispose();viewer=null;loaded='';sequence++;$('.cad-viewer-host').replaceChildren();}manifest=null;renderModelDetails();return;}
  const key=snapshot.active_id+':'+entry.id;
  if(loaded===key){renderStale();return;}
  loaded=key;const seq=++sequence,pid=snapshot.active_id;
  $('.cad-load-notice').textContent='Opening assembly…';
  try{
    const preview=entry===cad.preview;
    const data=await hooks.request(preview?hooks.fileURL(entry.path+'/manifest.json',false,pid):`/api/projects/${pid}/cad?revision_id=${encodeURIComponent(entry.id)}`);
    if(seq!==sequence||!opened)return;
    const previouslyVisible=data.preview&&manifest?.job_id===data.job_id?manifest?.design.instances.map(i=>i.id):[];
    manifest=data;renderModelDetails();
    viewer?.dispose();viewer=null;$('.cad-viewer-host').replaceChildren();
    const {createCadViewer}=await import('./cad-viewer.js?v=3');
    if(seq!==sequence||!opened)return;
    const result=await createCadViewer($('.cad-viewer-host'),hooks.fileURL(data.path+'/assembly.glb',false,pid),data,selectPart,previouslyVisible||[]);
    if(seq!==sequence||!opened){result.dispose();return;}
    viewer=result;$('.cad-load-notice').textContent='';if(selected)viewer.select(selected);renderStatus();
  }catch(error){if(seq===sequence){$('.cad-load-notice').textContent=`3D preview unavailable: ${error.message} Reopen CAD to retry. Saved downloads remain available.`;}}
}

function renderStatus(){
  if(!snapshot)return;
  const cad=snapshot.cad||{status:'planning'},state=cad.status,busy=busyStates.includes(state);
  root.dataset.status=state;root.classList.toggle('is-generating',busy);
  $('.cad-model-label').textContent=cad.model==='gemini-4-carbon'?'GEMINI 4 CARBON':cad.model||'GEMINI 4 CARBON';
  $('.cad-status').textContent=cad.message||labels[state]||'Finish planning to begin CAD.';
  const progress=steps.findIndex(([s])=>s===state);
  for(const [index,node] of [...$('.cad-pipeline').children].entries()){
    node.classList.toggle('is-active',index===progress||state==='queued'&&index===0);
    node.classList.toggle('is-done',index<progress||['ready','needs_review'].includes(state));
  }
  const versions=$('.cad-versions'),history=cad.history||[],value=chosenRevision||(cad.preview?'':cad.current?.id)||'';
  const versionKey=JSON.stringify([history,!!cad.preview]);
  if(versions.dataset.history!==versionKey){
    versions.replaceChildren();if(cad.preview){const o=el('option','','Live build · unfinished');o.value='';versions.append(o);}history.slice().reverse().forEach((entry,index)=>{const o=el('option','',`Version ${history.length-index} · ${entry.status==='ready'?'checked':'review'}`);o.value=entry.id;versions.append(o);});
    versions.dataset.history=versionKey;
  }
  versions.value=value;versions.hidden=!history.length;
  const actions=$('.cad-actions');actions.replaceChildren();
  if(busy)actions.append(button('Cancel build',()=>hooks.act('cancel_cad',{}),'cad-secondary'));
  else{
    const label=['error','interrupted','cancelled'].includes(state)?'Retry CAD':cad.current?'Regenerate':'Finish planning → Create CAD';
    actions.append(button(label,()=>generate('',state!=='planning'),'cad-primary'));
  }
  if(cad.design_path)actions.append(read('Part plans ↗',cad.design_path));
  if(cad.runtime_notice){const n=el('p','cad-runtime-notice',cad.runtime_notice);actions.append(n);}
  if(!manifest){
    $('.cad-empty h3').textContent=busy?'Engineering your idea…':state==='needs_input'?'A few details to resolve.':'Your design, assembled.';
    $('.cad-empty p').textContent=busy?cad.message:(cad.missing_measurements||[]).join(' ')||'Finish planning to create precise parts and see how they fit together.';
    $('.cad-review-notes').replaceChildren();
    if(cad.plan_review)renderReview(cad.plan_review,$('.cad-review-notes'));
    else if(cad.design){$('.cad-review-notes').append(el('p','',cad.design.summary));}
  }
  $('.cad-revision-request input').disabled=busy;
  $('.cad-revision-request button').disabled=busy;
  renderActivity();renderTelemetry();renderBuildParts();renderStale();
}

function renderElapsed(){
  if(!opened||!snapshot)return;
  const cad=snapshot.cad||{},busy=busyStates.includes(cad.status);
  const seconds=Math.max(0,Math.floor((Date.now()-Date.parse(cad.phase_started_at||cad.started_at))/1000));
  $('.cad-elapsed').textContent=busy&&Number.isFinite(seconds)?`${Math.floor(seconds/60)}m ${String(seconds%60).padStart(2,'0')}s`:'';
  const call=[...(cad.calls||[])].reverse().find(c=>c.kind==='model');
  if(call?.status==='running'){
    const ago=Math.max(0,Math.floor((Date.now()-Date.parse(call.last_event_at||call.started_at))/1000));
    const phase={connecting:'Connecting',connected:'Connected',thinking:'Thinking',responding:'Receiving output',received:'Response received'}[call.phase]||'Working';
    $('.cad-stream-state').textContent=`${phase} · ${ago}s since update`;
  }
}

function renderTelemetry(){
  const calls=snapshot.cad?.calls||[],models=calls.filter(c=>c.kind==='model'),latest=models.at(-1);
  $('.cad-telemetry').hidden=!calls.length;if(!calls.length)return;
  const totals=$('.cad-token-usage');totals.replaceChildren();
  for(const [key,label] of [['thinking','Thinking tokens'],['input','Input tokens'],['output','Output tokens']]){
    const known=models.filter(c=>Number.isInteger(c.usage?.[key]));
    const tile=el('div');tile.append(el('strong','',known.length?fmt(known.reduce((sum,c)=>sum+c.usage[key],0)):'—'),el('span','',label));totals.append(tile);
  }
  const pending=models.filter(c=>!Number.isInteger(c.usage?.total)).length;
  $('.cad-token-note').textContent=pending?`Reported totals only · ${pending} request${pending===1?' has':'s have'} no usage report. Counts usually arrive at completion.`:'Reported totals for this build. Thinking summaries are not a token-by-token transcript.';
  const summary=latest?.summary;
  $('.cad-thinking-text').textContent=summary|| (latest?.status==='running'?'Waiting for Carbon’s public summary. The API may not provide a summary for every request.':'Carbon did not return a public summary for this request.');
  $('.cad-stream-state').textContent=latest?.status==='running'?'Connected':latest?.status||'';
  $('.cad-call-count').textContent=`(${calls.length})`;
  const host=$('.cad-call-list'),signature=JSON.stringify(calls);
  if(host.dataset.signature!==signature){
    const open=new Set([...host.children].filter(n=>n.open).map(n=>n.dataset.call));
    const scroll=host.scrollTop;host.replaceChildren();host.dataset.signature=signature;
    for(const call of calls.slice().reverse()){
      const row=el('details','cad-call');row.dataset.call=call.id;row.dataset.status=call.status;row.open=open.has(call.id);
      const title=el('summary');title.append(el('span','cad-call-kind',call.kind==='model'?'CARBON':'ADA TOOL'),el('span','',call.name),el('span','cad-call-status',call.status));row.append(title);
      const duration=call.duration_seconds!==undefined?`${fmt(call.duration_seconds)}s`:'In progress';
      row.append(el('p','',`${duration}${call.part_id?' · '+call.part_id:''}${call.part_ids?.length?' · '+call.part_ids.join(', '):''}`));
      if(call.kind==='model'){
        const counts=Object.entries(call.usage||{}).map(([k,v])=>`${k}: ${fmt(v)}`).join(' · ');
        row.append(el('p','',counts||'Token counts not reported.'));
        if(call.summary)row.append(el('p','cad-call-summary',call.summary));
        if(call.model_tool)row.append(el('p','cad-warning',`Model requested ${call.model_tool}; execution blocked because no model-side tools are enabled.`));
      }else if(call.files?.length)row.append(el('p','',`Produced: ${call.files.join(', ')}`));
      if(call.error)row.append(el('p','cad-warning',call.error));host.append(row);
    }
    host.scrollTop=scroll;
  }
  renderElapsed();
}

function renderActivity(){
  const cad=snapshot.cad||{},events=cad.activity||[],host=$('.cad-activity-list');
  $('.cad-activity').hidden=!events.length;
  if(host.dataset.job!==cad.job_id){host.replaceChildren();host.dataset.job=cad.job_id||'';}
  const pinned=host.scrollHeight-host.clientHeight-host.scrollTop<40;
  const ids=new Set([...host.children].map(n=>n.dataset.event));
  for(const event of events){
    if(ids.has(String(event.id)))continue;
    const row=el('details','cad-activity-event');row.dataset.event=event.id;
    const title=el('summary');title.append(el('time','',new Date(event.at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})),el('span','',event.message));
    row.append(title);if(event.detail)row.append(el('p','',event.detail));host.append(row);
  }
  while(host.children.length>200)host.firstChild.remove();
  if(pinned)host.scrollTop=host.scrollHeight;
  const latest=events.at(-1);$('.cad-now-title').textContent=latest?.message||'';$('.cad-now-detail').textContent=latest?.detail||'';
  $('.cad-now').hidden=!busyStates.includes(cad.status);renderElapsed();
}

function renderBuildParts(){
  const cad=snapshot.cad||{},parts=cad.part_progress||[],busy=busyStates.includes(cad.status);
  const showingBuild=!chosenRevision&&cad.design&&(!manifest||manifest.preview||busy);
  $('.cad-build-progress').hidden=!parts.length||!showingBuild;
  if(!showingBuild)return;
  const count=parts.filter(p=>['built','checked','needs_review'].includes(p.state)).length;
  $('.cad-build-count').textContent=`${count} / ${parts.length} parts built`;
  $('.cad-preview-state').textContent=manifest&&!manifest.preview?'Previous saved model':manifest?.preview?'Live geometry · unfinished':'Part plans → live geometry';
  $('.cad-build-progress progress').max=parts.length;$('.cad-build-progress progress').value=count;
  $('.cad-follow').classList.toggle('active',followBuild);
  const signature=JSON.stringify([cad.job_id,parts,manifest?.id,followBuild]);
  if(signature===planSignature)return;planSignature=signature;
  const list=$('.cad-part-list');list.replaceChildren();$('.cad-count').textContent=String(parts.length);
  const statusLabels={planned:'QUEUED',drafting:'DESIGNING',building:'BUILDING',checking:'CHECKING',repairing:'REPAIRING',built:'BUILT',checked:'CHECKED',failed:'FAILED',cancelled:'STOPPED',interrupted:'STOPPED',needs_review:'REVIEW'};
  for(const [index,p] of parts.entries()){
    const row=button('',()=>{followBuild=false;selectPlannedPart(p.id);$('.cad-follow').classList.remove('active');},'cad-part-row cad-building-part');
    row.dataset.planPart=p.id;row.dataset.partState=p.state;row.style.setProperty('--part-color',['#55dfcc','#b59ae8','#f0c17d','#77b9dc','#a5d799','#e5a2c1'][index%6]);
    row.append(el('span','cad-part-index',String(index+1).padStart(2,'0')),el('span','cad-part-name',p.name),el('span','cad-part-stage',statusLabels[p.state]||p.state));list.append(row);
  }
  const focus=followBuild?(cad.active_part_id||manifest?.focus_part_id):planSelected;
  selectPlannedPart(parts.some(p=>p.id===focus)?focus:parts[0]?.id);
}

function selectPlannedPart(id){
  const cad=snapshot.cad||{},part=cad.design?.parts.find(p=>p.id===id);if(!part)return;
  planSelected=id;
  const instance=manifest?.preview&&manifest.job_id===cad.job_id?manifest.design.instances.find(i=>i.part_id===id):null;
  if(instance){selected=instance.id;viewer?.select(selected);}
  for(const b of $('.cad-part-list').children){b.classList.toggle('selected',b.dataset.planPart===id);b.setAttribute('aria-pressed',String(b.dataset.planPart===id));}
  const detail=$('.cad-part-detail'),progress=cad.part_progress.find(p=>p.id===id);
  detail.replaceChildren(el('p','cad-eyebrow',instance?'BUILT COMPONENT':'PART PLAN'),el('h3','',part.name),el('p','',part.purpose),el('p','cad-dimensions',part.dimensions_mm.map(fmt).join(' × ')+' mm'),el('p','cad-material',`${part.material} · ${cad.design.instances.filter(i=>i.part_id===id).length} required`));
  detail.append(el('p','cad-part-progress-note',progress?.message||''));
  if(instance){const actions=el('div','cad-part-actions');actions.append(button('Isolate',()=>control({action:'isolate',part_id:instance.id})),button('Show assembly',()=>control({action:'show_all'})));detail.append(actions);}
  const list=el('ol','cad-modeling-plan');for(const step of part.steps)list.append(el('li','',step));detail.append(list,el('p','',part.print_notes));
  const review=cad.plan_review?.parts.find(p=>p.part_id===id);if(review)detail.append(el('p','cad-part-review',review.notes));
}

function renderStale(){
  const cad=snapshot.cad||{},n=$('.cad-stale');
  const entry=(cad.history||[]).find(e=>e.id===manifest?.id);
  const stale=manifest&&(manifest.preview?cad.stale:(manifest.stale||entry?.source_hash!==cad.source_hash||cad.stale));
  n.hidden=!stale;
  n.textContent=stale?'This model belongs to an earlier design. Regenerate to use the current plan.':'';
}

function renderReview(review,host){
  host.append(el('p','cad-review-summary',review.summary));
  for(const note of review.issues||[])host.append(el('p','cad-warning',note));
  const details=el('details','cad-review-detail');details.append(el('summary','','Assembly review'));
  for(const note of review.assembly_notes||[])details.append(el('p','',note));
  host.append(details);
}

function renderModelDetails(){
  planSignature='';
  root.dataset.preview=String(!!manifest?.preview);
  $('.cad-empty').hidden=!!manifest;
  $('.cad-toolbar').querySelectorAll('button').forEach(b=>b.disabled=!manifest);
  const list=$('.cad-part-list'),checks=$('.cad-check-list'),notes=$('.cad-review-notes'),files=$('.cad-files');
  list.replaceChildren();checks.replaceChildren();notes.replaceChildren();files.replaceChildren();$('.cad-part-detail').replaceChildren();
  if(!manifest){renderStatus();return;}
  const {design,geometry}=manifest;
  $('.cad-count').textContent=String(design.instances.length);
  $('.cad-view-name').textContent=design.name.toUpperCase();
  $('.cad-scale').textContent=geometry.assembly_dimensions_mm.map(fmt).join(' × ')+' mm';
  if(manifest.preview){
    root.dataset.preview='true';
    checks.append(el('p','cad-warning','Work in progress · assembly checks and final review are still pending.'));
    notes.append(el('p','cad-footnote','Each visible part has passed its solid, mesh and dimension checks. Print downloads appear after the assembly review.'));
    planSignature='';renderBuildParts();renderActivity();renderStale();return;
  }
  root.dataset.preview='false';
  for(const [index,instance] of design.instances.entries()){
    const part=design.parts.find(p=>p.id===instance.part_id),b=button('',()=>selectPart(instance.id),'cad-part-row');
    b.dataset.cadPart=instance.id;b.style.setProperty('--part-color',['#55dfcc','#b59ae8','#f0c17d','#77b9dc','#a5d799','#e5a2c1'][index%6]);
    b.append(el('span','cad-part-index',String(index+1).padStart(2,'0')),el('span','cad-part-name',part.name),el('span','cad-part-kind',part.printable?'PRINT':'HARDWARE'));list.append(b);
  }
  const tests=[['Valid solids',geometry.parts.every(p=>p.valid_solid)],['Closed print meshes',geometry.parts.every(p=>p.closed_mesh&&p.consistent_winding)],['Planned dimensions',geometry.parts.every(p=>p.dimensions_match)],['Assembly interference',geometry.pairs.every(p=>p.passed)],['Connection gaps',geometry.connections.every(p=>p.passed)],['Carbon review',manifest.review.passed]];
  tests.push(['Printer volume',design.printer_build_volume_mm?geometry.parts.filter(p=>p.printable).every(p=>p.printer_fit):null]);
  for(const [label,passed] of tests){const row=el('div','cad-check '+(passed===null?'pending':passed?'passed':'failed'));row.append(el('span','',passed===null?'—':passed?'✓':'!'),el('span','',label+(passed===null?' · unspecified':'')));checks.append(row);}
  renderReview(manifest.review,notes);
  for(const failure of geometry.failures)notes.append(el('p','cad-warning',failure));
  const connections=el('details','cad-review-detail');connections.append(el('summary','',`${geometry.connections.length} measured connections`));
  for(const c of geometry.connections)connections.append(el('p','',`${c.name}: ${fmt(c.measured_gap_mm)} mm gap · ${c.passed?'passed':'review'}`));notes.append(connections);
  notes.append(el('p','cad-footnote','Checks cover the saved pose. Motion, strength and real print fit still need testing.'));
  files.append(link('↓ All print files',manifest.path+'/print-files.zip'),link('Assembly STEP',manifest.path+'/assembly.step'),read('Read all checks ↗',manifest.path+'/Checks.md'),read('Assembly instructions ↗',manifest.path+'/Parts.md'));
  if(manifest.status==='ready')files.prepend(button('Prepare print →',()=>openPrinting(snapshot.active_id,manifest.id),'cad-primary prepare-print'));
  if(manifest.calls)files.append(link('Request & tool log',manifest.path+'/Calls.json'));
  if(manifest.status!=='ready')files.prepend(el('p','cad-warning','Draft files · resolve the review findings before printing.'));
  selected=design.instances.some(i=>i.id===selected)?selected:design.instances[0].id;selectPart(selected);renderStale();renderBuildParts();
}

function selectPart(id){
  if(!manifest)return;
  const instance=manifest.design.instances.find(i=>i.id===id);if(!instance)return;
  if(manifest.preview){followBuild=false;selectPlannedPart(instance.part_id);return;}
  selected=id;viewer?.select(id);
  for(const b of $('.cad-part-list').children){b.classList.toggle('selected',b.dataset.cadPart===id);b.setAttribute('aria-pressed',String(b.dataset.cadPart===id));}
  const part=manifest.design.parts.find(p=>p.id===instance.part_id),report=manifest.geometry.parts.find(p=>p.id===part.id),detail=$('.cad-part-detail');
  detail.replaceChildren(el('p','cad-eyebrow','SELECTED COMPONENT'),el('h3','',part.name),el('p','',part.purpose),el('p','cad-dimensions',report.dimensions_mm.map(fmt).join(' × ')+' mm'),el('p','cad-material',`${part.material} · ${report.quantity} required`));
  const views=el('div','cad-part-actions');views.append(button('Isolate',()=>control({action:'isolate',part_id:id})),button('Hide',()=>control({action:'hide',part_id:id})));detail.append(views);
  const plan=el('details','cad-review-detail');plan.append(el('summary','','Part plan'));const list=el('ol');for(const step of part.steps)list.append(el('li','',step));plan.append(list,el('p','',part.print_notes));detail.append(plan);
  const review=manifest.review.parts.find(p=>p.part_id===part.id);if(review)detail.append(el('p','cad-part-review',review.notes));
  if(part.printable){const downloads=el('div','cad-part-downloads');for(const type of ['stl','3mf','step'])downloads.append(link(type.toUpperCase(),manifest.path+'/'+report.files[type]));detail.append(downloads);}
}

export async function control(args){
  if(!opened)await hooks.open();
  if(args.action==='follow_build'){
    followBuild=true;chosenRevision='';planSignature='';await updateCad(snapshot);return {following_build:true};
  }
  if(args.action==='version'){
    if(!(snapshot.cad?.history||[]).some(e=>e.id===args.revision_id))throw Error('Choose a saved CAD version.');
    chosenRevision=args.revision_id;loaded='';await updateCad(snapshot);return {revision_id:chosenRevision};
  }
  if(args.action==='select'&&!chosenRevision&&snapshot.cad?.design&&(!manifest||manifest.preview||busyStates.includes(snapshot.cad.status))){
    const instance=snapshot.cad.design.instances.find(i=>i.id===args.part_id);
    if(!instance)throw Error('Choose a part from the current design plan.');
    followBuild=false;selectPlannedPart(instance.part_id);return {action:'select',part_id:instance.id,planned:true};
  }
  if(!viewer)throw Error('The assembled 3D preview is still loading or unavailable.');
  const id=args.part_id||selected;
  const result=viewer.control(args.action,id);
  if(args.action==='select'||args.action==='isolate')selectPart(id);
  root.dataset.exploded=String(result.exploded);return result;
}

export function cadUIState(){
  const design=!chosenRevision&&(!manifest||manifest.preview||busyStates.includes(snapshot?.cad?.status))?snapshot?.cad?.design:manifest?.design;
  return opened?{cad_view_open:true,cad_revision:manifest?.id,cad_status:snapshot?.cad?.status,
  cad_build:snapshot?.cad?{active_part_id:snapshot.cad.active_part_id,parts:snapshot.cad.part_progress||[],latest_activity:snapshot.cad.activity?.at(-1),latest_call:snapshot.cad.calls?.at(-1),preview:!!manifest?.preview}:null,
  cad_instances:(design?.instances||[]).map(i=>({id:i.id,part_id:i.part_id,name:design.parts.find(p=>p.id===i.part_id)?.name})),
  cad_versions:snapshot?.cad?.history||[],cad_view:viewer?.state()||null}:{cad_view_open:false};}
