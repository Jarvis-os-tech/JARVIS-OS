import {setupCad,openCad,closeCad,updateCad,control as controlCad,cadUIState} from './cad.js?v=3';
import {openPrinting,closePrinting,printingState,controlPlate,controlPrint} from './printing.js';
import {documentView, renderMarkdown, documentOutline} from './document-view.js?v=9';
import {panelDefaults as defaults, orbLayout} from './project-layout.js?v=9';
import {setupInventory,openInventory,mountProjectStock,pollInventory,inventoryUIState} from './inventory.js?v=12';
const $ = id => document.getElementById(id);
const node = (tag, cls, value) => { const e = document.createElement(tag); if (cls) e.className = cls; if (value !== undefined) e.textContent = value; return e; };
const icons = {
  expand:'M9 3H3v6M15 21h6v-6M3 3l7 7m11 11-7-7M15 3h6v6M21 3l-7 7M3 15v6h6',
  file:'M14 2H5v20h14V7zM14 2v6h5M8 13h8M8 17h6',
  image:'M3 3h18v18H3zM3 17l6-6 4 4 3-3 5 5M9 7h.01',
  folder:'M2 6h8l2 3h10v12H2z', plus:'M12 4v16M4 12h16',
  idea:'M9 18h6M10 21h4M8 13a7 7 0 1 1 8 0c-2 1-2 2-2 3h-4c0-1 0-2-2-3',
  check:'M9 12l2 2 5-5M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  mic:'M8 5a4 4 0 0 1 8 0v7a4 4 0 0 1-8 0zM5 10v2a7 7 0 0 0 14 0v-2M12 19v4M8 23h8',
  pin:'M9 3h6l-1 7 4 4H6l4-4zM12 14v8', chevron:'m9 5 7 7-7 7', clip:'m8 16 8-8a3 3 0 0 1 4 4L10 22a5 5 0 0 1-7-7L14 4',
};
function icon(name) { const s = document.createElementNS('http://www.w3.org/2000/svg','svg'); s.setAttribute('viewBox','0 0 24 24'); s.setAttribute('aria-hidden','true'); const p=document.createElementNS(s.namespaceURI,'path');p.setAttribute('d',icons[name]||icons.file);s.append(p);return s; }
function button(label, action, cls='', symbol) { const b=node('button',cls,label);b.type='button'; if(cls.includes('icon-button')){b.textContent='';b.setAttribute('aria-label',label);b.title=label;} if(symbol)b.prepend(icon(symbol)); b.onclick=()=>Promise.resolve().then(action).catch(report);return b; }
let snapshot={projects:[],project:null,files:[]}, version='', loading=false, timer=0, selectedTab='idea', lastView='', reply='', replyTurn='', lastProject, dragging=false;
let sendText=()=>false, pendingConfirmation=null, viewSequence=0;
const panelNames=['files','ideas','brief','plan','tasks'];
let boardTab='overview', focusedPanel='', selectedPath='', planKey='', planData=null, planRequest=0;
const demoPending=new Set(),demoDirections=new Map(),demoErrors=new Map();
const panelLabels={brief:'Project brief',files:'Files',ideas:'Ideas',plan:'Project plan',tasks:'Next steps'};
const host=node('section','workspace'); host.id='workspace';host.setAttribute('aria-label','Project workspace');
host.innerHTML=`<header class="project-header"><button id="projectPicker" type="button" aria-label="Open project library"><span class="project-breadcrumb">Projects /</span> <span id="projectName">Create a project</span><span class="down-chevron">⌄</span></button><p id="projectSaved">Your ideas, in one place</p></header>
<nav id="projectTabs" class="project-tabs" aria-label="Project views" hidden></nav>
<div id="projectBoard" class="project-board" hidden><svg id="projectLinks" class="project-links" aria-hidden="true"></svg></div>
<section class="ada-reply" id="adaReply" hidden aria-label="Ada’s response"><button id="readReply" type="button"></button></section>
<input id="projectUpload" type="file" multiple hidden><p id="workspaceNotice" class="workspace-notice" role="status" aria-live="polite"></p>
<dialog id="workspaceDialog" class="workspace-dialog"><header><h2 id="dialogTitle"></h2><button id="dialogClose" type="button" aria-label="Close">×</button></header><div id="dialogBody"></div></dialog>`;
document.body.append(host);
setupInventory({dialog,request,button,field,submit,notice,report,projectId:()=>snapshot.active_id,openParts:()=>partsView()});
setupCad({host,request,act,fileURL,openFile,report,open:()=>selectBoardTab('cad')});
host.querySelector('.project-header').append(button('Inventory',()=>openInventory(),'inventory-open'));
for(const [name,label] of [['overview','Overview'],['plan','Plan'],['cad','CAD'],['parts','Parts'],['files','Files'],['ideas','Ideas']]){
  const tab=button(label,()=>selectBoardTab(name),'project-tab');tab.dataset.tab=name;
  tab.setAttribute('aria-controls',name==='cad'?'cadWorkspace':'projectBoard');$('projectTabs').append(tab);
}
const panels={};
for (const [i,name] of panelNames.entries()) {
  const p=node('section',`project-panel panel-${name}`);p.dataset.panel=name;p.setAttribute('aria-label',name);
  const header=node('header','panel-heading'); const grip=node('button','panel-grip',panelLabels[name]);grip.type='button';grip.title='Ask Ada to move or resize this panel';
  grip.prepend(icon({files:'folder',ideas:'idea',brief:'file',plan:'file',tasks:'check'}[name]));
  header.append(grip,button(`Expand ${name}`,()=>openPanel(name),'icon-button','expand'));
  const body=node('div','panel-body');p.append(header,body);
  const resize=node('button','panel-resize');resize.type='button';resize.setAttribute('aria-label',`Resize ${name} panel`);p.append(resize);
  panels[name]={element:p,body};$('projectBoard').append(p);
  grip.addEventListener('pointerdown',e=>startDrag(e,name,false));resize.addEventListener('pointerdown',e=>startDrag(e,name,true));
}
function selectBoardTab(name){
  if(name==='cad'){$('workspaceDialog').close();setBoardFocus('','cad');return openCad(snapshot);}
  closeCad();
  if(name==='parts')return partsView();
  $('workspaceDialog').close();setBoardFocus(name==='overview'?'':name,name);
  if(name==='files')filesView();
  if(name==='ideas')cardsView('idea');
  if(name==='plan'){
    selectedPath=findPlan()?.path||'';updateSelectedFiles();
    panels.plan.body.scrollTop=0;
    if(matchMedia('(max-width:1000px)').matches)panels.plan.element.scrollIntoView({block:'start',behavior:'instant'});
  }
}
function setBoardFocus(name,tab){
  focusedPanel=name;
  boardTab=tab||({brief:'overview',tasks:'plan',inspiration:'ideas'}[name]||name||'overview');
  for(const b of $('projectTabs').children){const active=b.dataset.tab===boardTab;b.classList.toggle('active',active);if(active)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');}
  for(const [key,panel] of Object.entries(panels))panel.element.classList.toggle('is-focused',key===name);
  for(const link of $('projectLinks').children)link.classList.toggle('active',link.dataset.link===name);
  requestAnimationFrame(drawLinks);
}
function notice(message) { $('workspaceNotice').textContent=message;clearTimeout(timer);timer=setTimeout(()=>$('workspaceNotice').textContent='',7000); }
function report(error) { notice(error.message||'Something went wrong. Please try again.'); }
async function request(url, options={}) { const r=await fetch(url,{signal:AbortSignal.timeout(30000),...options});let data;try{data=await r.json();}catch{throw Error('Ada’s local service did not respond.');}if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:'Could not complete this action.');return data; }
async function act(name,args={}) {
  const arguments_={...(name==='list_projects'||name==='create_project'?{}:{project_id:snapshot.active_id}),...args};
  const {result}=await request('/api/workspace/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,arguments:arguments_}),signal:AbortSignal.timeout(name==='generate_demo_image'?150000:30000)});
  if(!['read_file','list_files','list_projects','list_trash','list_versions'].includes(name))await refresh(true);
  return result;
}
async function refresh(force=false) {
  if(loading)return;loading=true;
  try{
    const data=await request('/api/workspace');snapshot=data;
    const next=JSON.stringify([data.active_id,data.project?.revision,data.image_generation,data.cad,data.projects.map(p=>[p.id,p.revision]),data.files]);
    // Voice requests still fetch fresh data, while unchanged panels keep their
    // DOM, scroll position and decoded images instead of rebuilding.
    if(next!==version){version=next;render();}
    void updateCad(snapshot).catch(report);
    if(data.view&&data.view.id!==lastView){lastView=data.view.id;if(data.view.project_id===data.active_id)await showView(data.view);}
  }catch(error){report(error);}finally{loading=false;}
}
function fileURL(path,download=false,pid=snapshot.active_id){return `/api/projects/${encodeURIComponent(pid)}/file?path=${encodeURIComponent(path)}${download?'&download=true':''}`;}
function render() {
  const p=snapshot.project, changed=lastProject!==snapshot.active_id;
  if(changed){closeCad();reply='';replyTurn='';$('adaReply').hidden=true;selectedTab='idea';lastProject=snapshot.active_id;$('workspaceDialog').close();planKey='';planData=null;planRequest++;selectedPath='';focusedPanel='';boardTab='overview';}
  document.body.classList.toggle('has-workspace',!!p);$('projectBoard').hidden=!p;$('projectTabs').hidden=!p;
  $('projectName').textContent=p?p.name:'Create a project';$('projectSaved').textContent=p?'●  Saved on this device':'Your ideas, in one place';
  if(changed)window.dispatchEvent(new Event('ada:workspace-layout'));
  if(!p)return;
  const brief=panels.brief.body;brief.replaceChildren(button(p.brief||'Tell Ada your idea to draft a brief.',()=>projectPreview(),'brief-copy'));
  const fs=panels.files.body;fs.replaceChildren();
  const plan=findPlan();
  const files=[...snapshot.files].sort((a,b)=>Number(b.path===plan?.path)-Number(a.path===plan?.path));
  for(const f of files.slice(0,4))fs.append(fileRow(f));
  if(!files.length)fs.append(node('p','empty-copy','Ask Ada to create a file or bring one in.'));
  if(files.length>4)fs.append(button(`All ${files.length} files`,()=>filesView(),'panel-footer'));
  renderIdeas();renderNextSteps();layoutPanels();
  if(changed&&plan){boardTab='plan';focusedPanel='plan';selectedPath=plan.path;}
  updateSelectedFiles();setBoardFocus(focusedPanel,boardTab);
  if(changed)requestAnimationFrame(()=>{drawLinks();unfoldPanels();});
  void refreshPlan().catch(report);
}
function findPlan(){return snapshot.files.find(f=>!f.folder&&/(?:^|\/)(?:project[ _-]*)?plan\.md$/i.test(f.path))||snapshot.files.find(f=>!f.folder&&/(?:plan|roadmap)[^/]*\.(?:md|markdown|txt)$/i.test(f.path));}
function findParts(){return snapshot.files.find(f=>!f.folder&&/^parts[ _-]+list\.md$/i.test(f.path))||snapshot.files.find(f=>!f.folder&&/(?:^|\/)parts[ _-]+list\.md$/i.test(f.path));}
function partsView(){
  const file=findParts();
  if(file)return openFile(file.path);
  setBoardFocus('plan','parts');
  const body=dialog('Parts list');
  body.append(button('Open inventory',()=>openInventory()));
  body.append(node('p','empty-copy','Once your direction and main components are clear, Ada will save a parts list here with quantities, specifications, and what you still need.'),
    button('Generate parts list',()=>ask('Create a parts list for this project from the current saved plan and decisions. Save it as Parts list.md and show it. If the design is still developing, label it provisional and mark unknowns to confirm. Include quantities, specifications, tools, and confirmed inventory.'),'primary'));
}
function updateSelectedFiles(){for(const row of panels.files.body.querySelectorAll('[data-path]')){const active=row.dataset.path===selectedPath;row.classList.toggle('selected',active);row.setAttribute('aria-current',String(active));}}
function renderIdeas(){
  const body=panels.ideas.body;body.replaceChildren();
  const cards=snapshot.project.cards.filter(c=>c.kind==='idea').sort((a,b)=>Number(!!b.selected)-Number(!!a.selected)||Number(!!b.pinned)-Number(!!a.pinned));
  for(const c of cards.slice(0,2)){const row=button((c.done?'✓  ':'')+c.title,()=>cardView(c),`idea-row${c.selected?' selected':''}`);row.dataset.cardId=c.id;body.append(row);}
  if(!cards.length)body.append(node('p','empty-copy','Say “Brainstorm a few directions.”'));
  const imageCards=snapshot.project.cards.filter(c=>c.kind==='image'&&snapshot.files.some(f=>f.path===c.path));
  const reference=imageCards.find(c=>c.selected)||imageCards[0];
  const imageFile=reference?.path||snapshot.files.find(f=>f.image)?.path;
  if(imageFile){const b=button('',()=>openFile(imageFile),'constellation-reference');const img=node('img');img.src=fileURL(imageFile);img.alt=reference?.title||imageFile;img.loading='lazy';b.append(img);body.append(b);}
  else{
    const sketch=node('div','idea-constellation');sketch.setAttribute('aria-hidden','true');
    sketch.innerHTML='<svg viewBox="0 0 230 90"><path d="M30 52L84 20 152 46 200 18M30 52l78 25 44-31 48 20M84 20l24 57M152 46l48-28M108 77l92-11"/><circle cx="30" cy="52" r="8"/><circle cx="84" cy="20" r="6"/><circle cx="108" cy="77" r="6"/><circle cx="152" cy="46" r="12"/><circle cx="200" cy="18" r="5"/><circle cx="200" cy="66" r="5"/></svg>';body.append(sketch);
  }
  const footer=node('div','panel-actions');footer.append(button('Compare ideas',()=>compareView(),'panel-footer'),button('Add',()=>editCard(null,'idea'),'small-add','plus'));body.append(footer);
}
function renderNextSteps(){
  const body=panels.tasks.body;body.replaceChildren();
  const task=snapshot.project.cards.find(c=>c.kind==='task'&&!c.done);
  if(task){const b=button(task.title,()=>cardView(task),'next-step');b.dataset.cardId=task.id;body.append(b);}
  else body.append(button('Ask Ada for next steps',()=>ask('Suggest the next practical steps for this project and save them as tasks.'),'next-step empty-copy'));
}
async function refreshPlan(){
  const file=findPlan(),pid=snapshot.active_id,key=JSON.stringify([pid,file?.path,snapshot.project?.revision]);
  if(planKey===key){renderPlan();return;}
  planKey=key;const seq=++planRequest;
  if(!file){planData=null;renderPlan();return;}
  if(planData?.path!==file.path||planData?.pid!==pid){planData=null;panels.plan.body.replaceChildren(node('p','empty-copy','Opening the project plan…'));}
  try{
    const result=await act('read_file',{project_id:pid,path:file.path,limit:262144});
    if(seq!==planRequest||snapshot.active_id!==pid)return;
    planData={pid,path:file.path,revision:result.revision,content:result.content||'',sections:/\.(md|markdown|mdown)$/i.test(file.path)?documentOutline(result.content||''):[],truncated:result.truncated};renderPlan();
  }catch(error){if(seq===planRequest&&snapshot.active_id===pid){planKey='';planData=null;panels.plan.body.replaceChildren(node('p','empty-copy','The plan could not be loaded. Ask Ada to open it again.'));}throw error;}
}
function renderPlan(){
  const body=panels.plan.body;body.replaceChildren();
  if(!planData){body.append(node('p','empty-copy','Your project plan will unfold here.'),button('Draft a plan with Ada',()=>ask('Create a practical first-draft Plan.md for this project using what we already know.'),'plan-empty-action'));return;}
  body.append(demoImageView());
  const list=node('ol','plan-roadmap');
  for(const section of planData.sections){
    const item=node('li'),b=button('',async()=>{await openFile(planData.path);focusDocumentSection(section.number);},'plan-phase');
    b.dataset.planSection=section.number;
    const title=section.title.replace(/^(?:phase|step|stage)\s*\d+\s*[:.·–—-]?\s*/i,'');
    b.append(node('span','phase-label',`Phase ${section.number}`),node('span','phase-title',title||section.title));item.append(b);list.append(item);
  }
  if(list.children.length)body.append(list);
  else{const preview=renderMarkdown(planData.content.slice(0,4000),{path:planData.path});preview.classList.add('plan-preview');body.append(preview);}
  const actions=node('div','plan-actions');actions.append(button('Read full plan',()=>openFile(planData.path),'panel-footer'),button('Discuss',()=>ask(`Review ${JSON.stringify(planData.path)} and help me refine the plan.`),'small-add'),button('Finish planning → CAD',()=>act('generate_cad',{request_id:crypto.randomUUID()}),'small-add'));
  body.append(actions);
  body.append(button(findParts()?'View parts list':'Parts & materials',()=>partsView(),'panel-footer'));
  if(planData.truncated)body.append(node('p','empty-copy','Preview of the first part of this plan.'));
}
function demoImageView(){
  const pid=snapshot.active_id,state=snapshot.image_generation||{},busy=demoPending.has(pid)||state.status==='generating';
  const card=[...snapshot.project.cards].reverse().find(c=>c.kind==='image'&&c.generation?.purpose==='plan_demo'&&snapshot.files.some(f=>f.image&&f.path===c.path));
  const section=node('section','plan-demo');section.setAttribute('aria-label','Plan demo image');section.setAttribute('aria-busy',String(busy));
  const heading=node('div','demo-heading');heading.append(node('span','','Demo image'),node('span','demo-badge','AI concept'));section.append(heading);
  if(card){
    const preview=button('',()=>openFile(card.path),'demo-preview');preview.setAttribute('aria-label','Open demo image');preview.dataset.path=card.path;
    const img=node('img');img.src=fileURL(card.path,false,pid);img.alt=card.generation.prompt||`Concept preview of ${snapshot.project.name}`;preview.append(img);section.append(preview);
    const stale=card.generation.plan_path!==planData.path||card.generation.plan_revision!==planData.revision;
    section.append(node('p','demo-caption',stale?'The plan has changed. Generate a new preview when ready.':'Illustrative preview · earlier versions stay in Files'));
  }else section.append(node('p','demo-caption','See a visual concept based on your saved plan.'));
  const form=node('form','demo-form'),label=node('label','demo-direction','Visual direction (optional)'),input=node('input');
  input.type='text';input.maxLength=4000;input.placeholder='Style, viewpoint, or details to include…';input.value=demoDirections.get(pid)||'';input.disabled=busy;
  input.oninput=()=>demoDirections.set(pid,input.value);label.append(input);
  if(card){const details=node('details','demo-options');details.append(node('summary','','Refine the image'),label);form.append(details);}else form.append(label);
  const generate=node('button','demo-generate',busy?'Generating image…':card?'Generate another':'Generate demo image');generate.type='submit';generate.disabled=busy;form.append(generate);
  form.onsubmit=e=>{e.preventDefault();void generateDemo(pid,planData.path).catch(report);};section.append(form);
  const message=busy?'Creating your preview. This may take up to two minutes.':demoErrors.get(pid)||(state.status==='error'?state.message:'');
  const status=node('p','demo-status',message);status.setAttribute('role','status');status.hidden=!message;section.append(status);
  return section;
}
async function generateDemo(pid,path){
  if(demoPending.has(pid))return;
  demoPending.add(pid);demoErrors.delete(pid);renderPlan();
  try{
    await act('generate_demo_image',{project_id:pid,plan_path:path,prompt:demoDirections.get(pid)||''});
  }catch(error){demoErrors.set(pid,error.name==='TimeoutError'?'The image request timed out. Check the preview before trying again.':error.message);}
  finally{demoPending.delete(pid);await refresh(true);if(snapshot.active_id===pid)renderPlan();}
}
function focusDocumentSection(value){
  const sections=[...$('workspaceDialog').querySelectorAll('[data-document-section]')],query=String(value||'').trim().toLowerCase();
  if(!$('workspaceDialog').open||!query)throw Error('Choose a section in the open document.');
  const exact=sections.filter(e=>e.dataset.documentSection===query||e.dataset.sectionTitle.toLowerCase()===query);
  const matches=exact.length?exact:sections.filter(e=>e.dataset.sectionTitle.toLowerCase().includes(query));
  if(matches.length!==1)throw Error('Choose one section by its number or full title.');
  matches[0].scrollIntoView({block:'start',behavior:'instant'});return {section:matches[0].dataset.sectionTitle};
}
function fileRow(f){const b=button(f.path,()=>f.folder?filesView(f.path):openFile(f.path),'file-row',f.folder?'folder':f.image?'image':'file');b.dataset.path=f.path;b.dataset.folder=String(!!f.folder);return b;}
function dialog(title,wide=false){viewSequence++;pendingConfirmation=null;$('dialogTitle').textContent=title;const d=$('workspaceDialog');delete d.dataset.path;delete d.dataset.cardId;delete d.dataset.documentMode;delete d.dataset.editable;d.classList.remove('document-dialog');d.classList.toggle('wide',wide);d.scrollTop=0;const b=$('dialogBody');b.replaceChildren();if(!d.open)d.showModal();return b;}
$('dialogClose').onclick=()=>$('workspaceDialog').close();
$('workspaceDialog').addEventListener('click',e=>{if(e.target===$('workspaceDialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}});
function field(form,label,value='',multiline=false){const l=node('label','form-field',label);const input=node(multiline?'textarea':'input');input.value=value;if(multiline)input.rows=7;l.append(input);form.append(l);return input;}
function submit(form,label,callback){const b=node('button','primary',label);b.type='submit';form.append(b);form.adaSubmit=async()=>{if(!form.reportValidity())throw Error('Tell Ada the missing details to save this form.');b.disabled=true;try{await callback();}finally{b.disabled=false;}};form.onsubmit=e=>{e.preventDefault();void form.adaSubmit().catch(report);};}
function confirmAction(title,description,callback){const b=dialog(title);pendingConfirmation=async()=>{await callback();$('workspaceDialog').close();pendingConfirmation=null;};b.append(node('p','',description+' Say “confirm” or “cancel”.'),button('Continue',pendingConfirmation,'danger'),button('Cancel',()=>{$('workspaceDialog').close();pendingConfirmation=null;},'secondary'));}
function library(query=''){const b=dialog('Your projects');const top=node('div','toolbar');top.append(button('New project',()=>newProject(),'primary','plus'));if(snapshot.project)top.append(button('Project settings',()=>editProject()),button('Reset panel layout',async()=>{await act('save_layout',{layout:{}});notice('Panel layout reset.');}));b.append(top);
  const search=field(b,'Find a project',query);const list=node('div','project-list');b.append(list);
  const fill=()=>{list.replaceChildren();for(const p of snapshot.projects.filter(p=>p.name.toLowerCase().includes(search.value.toLowerCase()))){const row=button(p.name+(p.archived?' · Archived':''),async()=>{await act('open_project',{project_id:p.id});$('workspaceDialog').close();},'project-choice','folder');row.dataset.projectId=p.id;row.append(node('small','',p.brief||'Open workspace'));list.append(row);}if(!list.children.length)list.append(node('p','empty-copy','No projects yet. Start with an idea.'));};search.oninput=fill;fill();}
function newProject(){const b=dialog('Create a project');const f=node('form');b.append(f);const name=field(f,'Project name');name.required=true;name.maxLength=100;const brief=field(f,'What would you like to explore?','',true);brief.maxLength=8000;submit(f,'Create project',async()=>{await act('create_project',{name:name.value,brief:brief.value});$('workspaceDialog').close();notice('Project created. Tell Ada what you have in mind.');});name.focus();}
function editProject(){const p=snapshot.project;if(!p)return newProject();const b=dialog('Project details');const f=node('form');b.append(f);const name=field(f,'Project name',p.name);name.required=true;name.maxLength=100;const brief=field(f,'Project brief',p.brief,true);brief.maxLength=8000;const summary=field(f,'Working summary · remembered by Ada',p.summary,true);summary.maxLength=12000;submit(f,'Save project',async()=>{await act('update_project',{project_id:p.id,name:name.value,brief:brief.value,summary:summary.value});$('workspaceDialog').close();notice('Project saved.');});b.append(button('Archive project',()=>confirmAction('Archive project?', 'Your files and ideas will stay saved. You can reopen this project from the library.',()=>act('update_project',{project_id:p.id,archived:true})),'text-button'));
  const notes=p.cards.filter(c=>c.kind==='note');if(notes.length){b.append(node('h3','','Saved notes'));for(const c of notes)b.append(button(c.title,()=>cardView(c),'idea-row'));}}
function filesView(folder='',query='') {setBoardFocus('files');const b=dialog('Project files',true);const tools=node('div','toolbar');tools.append(button('Add files',()=>chooseFiles(folder),'primary','clip'),button('New file',()=>newFile(folder),'','plus'),button('New folder',()=>newFolder(folder),'','folder'),button('Trash',()=>trashView()));b.append(tools);
  const search=field(b,'Search files and folders',query);const list=node('div','file-list');b.append(list);const fill=()=>{list.replaceChildren();if(folder)list.append(button('← All files',()=>filesView(),'text-button'));for(const f of snapshot.files.filter(f=>(!folder||f.path.startsWith(folder+'/'))&&f.path.toLowerCase().includes(search.value.toLowerCase()))){const row=node('div','file-list-row');row.append(fileRow(f),button('Move / rename',()=>moveFile(f)),button('Copy',()=>moveFile(f,true)),button('Delete',()=>confirmAction('Move to trash?',f.path+' will be recoverable from this project’s trash.',async()=>{await act('delete_file',{path:f.path});notice('Moved to trash.');}),'danger-quiet'));list.append(row);}if(!list.children.length)list.append(node('p','empty-copy','No files here yet.'));};search.oninput=fill;fill();
}
function newFile(folder=''){const b=dialog('New file');const form=node('form');b.append(form);const path=field(form,'File path',folder?folder+'/notes.md':'notes.md');path.required=true;const content=field(form,'Content','',true);content.classList.add('code-editor');submit(form,'Create file',async()=>{await act('write_file',{path:path.value,content:content.value});await openFile(path.value);});}
function newFolder(folder=''){const b=dialog('New folder');const form=node('form');b.append(form);const path=field(form,'Folder path',folder?folder+'/':'');path.required=true;submit(form,'Create folder',async()=>{await act('create_folder',{path:path.value});filesView();});}
function moveFile(file,copy=false){const b=dialog(copy?'Copy file or folder':'Move or rename');const f=node('form');b.append(f);const destination=field(f,'Destination path',file.path);destination.required=true;submit(f,copy?'Copy':'Move',async()=>{await act(copy?'copy_file':'move_file',{path:file.path,destination:destination.value});filesView();});}
async function openFile(path,edit=false){
  selectedPath=path;updateSelectedFiles();
  if(path===findParts()?.path)setBoardFocus('plan','parts');else setBoardFocus(path===findPlan()?.path?'plan':'files');
  const pid=snapshot.active_id,b=dialog(path,true),sequence=viewSequence,d=$('workspaceDialog');
  d.dataset.path=path;b.append(node('p','empty-copy','Opening file…'));
  const result=await act('read_file',{project_id:pid,path,limit:262144});
  if(sequence!==viewSequence||pid!==snapshot.active_id||!d.open)return;
  b.replaceChildren();d.classList.add('document-dialog');d.dataset.documentMode=edit&&result.editable?'edit':'read';d.dataset.editable=String(result.editable);
  const bar=node('div','document-toolbar'),toolbar=node('div','toolbar');
  bar.append(node('span','document-mode',d.dataset.documentMode==='edit'?'EDITING':'READING VIEW'),toolbar);b.append(bar);
  const download=node('a','secondary','Download original');download.href=fileURL(path,true,pid);download.download=path.split('/').pop();
  toolbar.append(button('Discuss with Ada',()=>ask(`Read the project file ${JSON.stringify(path)} and explain its key points.`)),download,button('History',()=>versionsView(path,pid)));
  if(edit&&result.editable){
    const form=node('form','document-editor');b.append(form);
    const content=field(form,'File content',result.content,true);content.classList.add('code-editor');content.rows=18;content.adaOriginal=result.content;
    toolbar.prepend(button('Reading view',()=>{if(content.value!==result.content)throw Error('Save your edits before returning to reading view. You can say “save this”.');return openFile(path);}));
    submit(form,'Save and view',async()=>{await act('write_file',{project_id:pid,path,content:content.value,expected_revision:result.revision});if(pid===snapshot.active_id&&sequence===viewSequence&&d.open)await openFile(path);notice('File saved. Previous version kept.');});
  }else if(result.image){
    const frame=node('div','document-editor'),img=node('img','full-image');img.src=fileURL(path,false,pid);img.alt=path;frame.append(img);b.append(frame);
  }else if(result.content!==undefined){
    const ext=path.split('.').pop().toLowerCase();
    const kind=['md','markdown','mdown'].includes(ext)?'markdown':ext==='pdf'?'pdf':['js','ts','jsx','tsx','py','json','html','css','yaml','yml','xml','svg','toml','ini','sh','sql'].includes(ext)?'code':'text';
    const renderContent=content=>documentView({content,path,kind,projectName:snapshot.project?.name,fileURL:p=>fileURL(p,false,pid),openFile:p=>void openFile(p).catch(report)});
    if(path===findParts()?.path){
      const stock=node('section'),reader=node('div','parts-document');b.append(stock,reader);
      reader.append(renderContent(result.content));
      await mountProjectStock(stock,pid,content=>{if(reader.isConnected)reader.replaceChildren(renderContent(content));});
    }else b.append(renderContent(result.content));
    if(result.editable)toolbar.append(button('Edit text',()=>openFile(path,true)));
  }
  if(result.notice&&!result.image)b.append(node('p','empty-copy document-reader-notice',result.notice));
  if(result.truncated)b.append(node('p','empty-copy document-reader-notice','Showing the first part of this file. Ask Ada to read further or save the original to Downloads.'));
  if(edit&&!result.editable)throw Error('This file supports reading only. Ada can create a separate text document with your changes.');
  return {path,mode:d.dataset.documentMode};
}
function projectPreview(){
  setBoardFocus('brief');
  const p=snapshot.project;if(!p)return library();
  const b=dialog('Project details',true),d=$('workspaceDialog');d.classList.add('document-dialog');d.dataset.documentMode='read';
  const bar=node('div','document-toolbar');bar.append(node('span','document-mode','PROJECT OVERVIEW'),button('Edit project details',()=>editProject()));b.append(bar);
  const content=[p.brief||'Tell Ada your idea and she’ll draft a brief.',p.summary?'## Working summary\n\n'+p.summary:''].filter(Boolean).join('\n\n');
  b.append(documentView({content,title:p.name,path:'Project brief.md',kind:'markdown',projectName:p.name}));
}
async function versionsView(path,pid){const b=dialog('Previous versions');const {entries}=await act('list_versions',{project_id:pid,path});if(!entries.length)b.append(node('p','empty-copy','Previous content is kept each time this file is edited.'));for(const e of entries)b.append(button('Restore '+new Date(e.created_at).toLocaleString(),async()=>{const current=await act('read_file',{project_id:pid,path});await act('restore_version',{project_id:pid,item_id:e.id,expected_revision:current.revision});await openFile(path);} ,'idea-row'));}
async function trashView(){const pid=snapshot.active_id;const b=dialog('Project trash');const {entries}=await act('list_trash',{project_id:pid});if(!entries.length)b.append(node('p','empty-copy','Trash is empty.'));for(const e of entries){const row=node('div','trash-row');row.append(node('span','',e.path),button('Restore',async()=>{await act('restore_file',{project_id:pid,item_id:e.id});await trashView();}));b.append(row);}}
function editCard(card=null,kind='idea'){const pid=snapshot.active_id;if(!pid)return newProject();const b=dialog(card?'Edit '+card.kind:'New '+kind);const f=node('form');b.append(f);const title=field(f,'Title',card?.title||'');title.required=true;title.maxLength=160;const body=field(f,'Details',card?.body||'',true);body.maxLength=12000;submit(f,'Save '+(card?.kind||kind),async()=>{const c=await act('save_card',{project_id:pid,kind:card?.kind||kind,title:title.value,body:body.value,...(card?{card_id:card.id}:{})});cardView(c);});}
function cardView(c){setBoardFocus(c.kind==='task'?'tasks':'ideas');const b=dialog(c.title);$('workspaceDialog').dataset.cardId=c.id;const content=renderMarkdown(c.body||'Tell Ada how you’d like to develop this direction.');content.classList.add('card-detail');b.append(content);const actions=node('div','toolbar');actions.append(button('Edit',()=>editCard(c)),button(c.pinned?'Unpin':'Pin',async()=>{const updated=await act('save_card',{...cardArgs(c),pinned:!c.pinned});cardView(updated);}));
  if(c.kind==='idea')actions.append(button(c.selected?'Selected':'Select direction',async()=>{await act('save_card',{...cardArgs(c),selected:true});notice('Direction selected.');}),button('Save as decision',async()=>{await act('save_card',{kind:'decision',title:c.title,body:c.body});notice('Decision saved.');}),button('Explore with Ada',()=>ask(`Explore the saved idea ${JSON.stringify(c.title)}. Read its details and propose practical next steps.`)));
  if(c.kind==='task')actions.append(button(c.done?'Mark incomplete':'Mark complete',async()=>{const updated=await act('save_card',{...cardArgs(c),done:!c.done});cardView(updated);}));
  if(c.path)actions.append(button('Open source',()=>openFile(c.path)));
  actions.append(button('Remove card',()=>confirmAction('Remove this card?', 'This removes the card, while linked files stay in your project.',async()=>{await act('delete_card',{card_id:c.id});notice('Card removed.');}),'danger-quiet'));b.append(actions);}
function cardArgs(c){return {card_id:c.id,kind:c.kind,title:c.title,body:c.body||''};}
function cardsView(kind='idea'){setBoardFocus(kind==='task'?'tasks':'ideas');const b=dialog(kind==='task'?'Next steps':kind==='decision'?'Decisions':'Ideas & notes');b.append(button('Add '+kind,()=>editCard(null,kind),'primary','plus'));for(const c of snapshot.project.cards.filter(c=>c.kind===kind||kind==='idea'&&c.kind==='note')){const row=button((c.done?'✓  ':c.pinned?'Pinned · ':'')+c.title,()=>cardView(c),'idea-row');row.dataset.cardId=c.id;b.append(row);}}
function compareView(ids=[]){setBoardFocus('ideas');const b=dialog('Compare directions',true);const cards=snapshot.project.cards.filter(c=>c.kind==='idea'&&(!ids.length||ids.includes(c.id)));if(!cards.length){b.append(node('p','empty-copy','Save a few ideas, then compare their strengths here.'),button('Brainstorm three directions',()=>ask('Brainstorm three distinct directions for this project. Save each as an idea card with benefits, trade-offs and a next step.'),'primary'));return;}const grid=node('div','compare-grid');for(const c of cards){const col=node('article','compare-card');col.dataset.cardId=c.id;col.append(node('h3','',c.title),node('p','card-detail',c.body),button('Choose this direction',async()=>{await act('save_card',{...cardArgs(c),selected:true});await act('save_card',{kind:'decision',title:c.title,body:c.body});notice('Direction saved as a decision.');}),button('Edit',()=>editCard(c)));grid.append(col);}b.append(grid);}
function galleryView(){setBoardFocus('ideas');const b=dialog('Inspiration',true);b.append(button('Add images',()=>chooseFiles(),'primary','plus'));const grid=node('div','gallery-grid');for(const f of snapshot.files.filter(f=>f.image)){const item=button('',()=>openFile(f.path),'gallery-image');item.dataset.path=f.path;const img=node('img');img.src=fileURL(f.path);img.alt=f.name;img.loading='lazy';item.append(img,node('span','',f.path));grid.append(item);}b.append(grid);}
function openPanel(name){if(name==='brief')projectPreview();if(name==='files')filesView();if(name==='inspiration')galleryView();if(name==='ideas')cardsView('idea');if(name==='tasks')cardsView('task');if(name==='plan'){const plan=findPlan();if(plan)return openFile(plan.path);selectBoardTab('plan');}}
async function showView(v){
  if(v.view==='inventory')return openInventory(v.scan_id||'');
  if(['overview','plan','parts','cad'].includes(v.view))return selectBoardTab(v.view);
  if(v.view==='compare')return compareView(v.card_ids);
  if(v.view==='file'&&v.path)return openFile(v.path);
  if(v.view==='file_editor'&&v.path)return openFile(v.path,true);
  if(v.view==='files')return filesView(v.path||'',v.query||'');
  if(v.view==='trash')return trashView();
  if(v.view==='versions')return versionsView(v.path,snapshot.active_id);
  if(v.view==='card'){const c=snapshot.project.cards.find(c=>c.id===v.card_ids[0]);if(!c)throw Error('That card is no longer available.');return cardView(c);}
  if(['ideas','decisions','tasks','notes'].includes(v.view)){const kind={ideas:'idea',decisions:'decision',tasks:'task',notes:'note'}[v.view];return cardsView(kind);}
  openPanel(v.view);
}
let uploadFolder='';function chooseFiles(folder=''){if(!snapshot.project)return newProject();uploadFolder=folder;$('projectUpload').click();}
async function uploadFiles(files,folder=''){if(!snapshot.project)return newProject();const pid=snapshot.active_id;for(const f of files){notice('Adding '+f.name+'…');if(f.size>20*1024*1024){notice(f.name+' exceeds 20 MB.');continue;}try{await request(`/api/projects/${pid}/upload?path=${encodeURIComponent(folder?folder+'/'+f.name:f.name)}`,{method:'POST',body:f});}catch(e){report(e);await refresh(true);return;}}await refresh(true);if($('workspaceDialog').open&&$('dialogTitle').textContent==='Inspiration')galleryView();else if($('workspaceDialog').open&&$('dialogTitle').textContent==='Project files')filesView(folder);notice('Files added to the project.');}
$('projectUpload').onchange=async e=>{const files=[...e.target.files];e.target.value='';await uploadFiles(files,uploadFolder);};
host.addEventListener('dragover',e=>{if(e.dataTransfer.types.includes('Files')){e.preventDefault();host.classList.add('drop-active');}});host.addEventListener('dragleave',e=>{if(!host.contains(e.relatedTarget))host.classList.remove('drop-active');});host.addEventListener('drop',e=>{e.preventDefault();host.classList.remove('drop-active');void uploadFiles([...e.dataTransfer.files]).catch(report);});
function ask(value){if(!sendText(value))return notice('Connect Ada’s voice session before sending a request.');$('workspaceDialog').close();reply='';$('adaReply').hidden=true;notice('Sent to Ada.');}
$('projectPicker').onclick=library;
function showReply(){const b=dialog('Ada’s response',true);b.append(node('p','card-detail',reply));if(snapshot.project)b.append(button('Save as a note',async()=>{await act('save_card',{kind:'note',title:'Brainstorming notes',body:reply.slice(0,12000)});notice('Response saved to this project.');},'primary'));}
$('readReply').onclick=showReply;
function layoutPanels(){if(dragging||!snapshot.project)return;for(const name of panelNames){const r=snapshot.project.layout[name]||defaults[name];for(const [k,prop] of Object.entries({x:'left',y:'top',w:'width',h:'height'}))panels[name].element.style[prop]=r[k]+'%';}}
function reducedMotion(){return document.body.dataset.reducedMotion==='true'||(document.body.dataset.reducedMotion!=='false'&&matchMedia('(prefers-reduced-motion:reduce)').matches);}
function unfoldPanels(){
  if(reducedMotion()||innerWidth<=1000)return;
  const center=orbLayout(innerWidth,innerHeight);
  $('projectBoard').classList.add('is-unfolding');
  setTimeout(()=>$('projectBoard').classList.remove('is-unfolding'),1400);
  panelNames.forEach((name,i)=>{
    const panel=panels[name].element,r=panel.getBoundingClientRect();
    panel.getAnimations().forEach(a=>a.cancel());
    const dx=center.x-r.left-r.width/2,dy=center.y-r.top-r.height/2;
    panel.animate([
      {opacity:0,transform:`translate(${dx}px,${dy}px) scale(.025,.16)`},
      {opacity:.85,transform:`translate(${dx*.2}px,${dy*.2}px) scale(.35,.9)`,offset:.45},
      {opacity:1,transform:'translate(0,0) scale(1)'},
    ],{duration:850,delay:i*65,easing:'cubic-bezier(.16,1,.3,1)',fill:'backwards'});
  });
}
let linkGeometry='';
function drawLinks(){
  const svg=$('projectLinks');
  if(!snapshot.project||innerWidth<=1000){svg.replaceChildren();linkGeometry='';return;}
  const r=$('projectBoard').getBoundingClientRect(),orb=orbLayout(innerWidth,innerHeight),cx=orb.x-r.x,cy=orb.y-r.y;
  const geometry=JSON.stringify([snapshot.active_id,r.width,r.height,orb,...panelNames.map(name=>{const e=panels[name].element;return [e.offsetLeft,e.offsetTop,e.offsetWidth,e.offsetHeight];})]);
  if(geometry===linkGeometry)return;
  linkGeometry=geometry;svg.replaceChildren();
  svg.setAttribute('viewBox',`0 0 ${r.width} ${r.height}`);
  for(const name of panelNames){
    const panel=panels[name].element,p={x:r.x+panel.offsetLeft,y:r.y+panel.offsetTop,width:panel.offsetWidth,height:panel.offsetHeight};
    const x=name==='tasks'?p.x+p.width*.46-r.x:p.x+(p.x<orb.x?p.width:0)-r.x;
    const y=name==='tasks'?p.y-r.y:p.y+p.height*(name==='plan'?.28:name==='brief'?.74:.5)-r.y;
    const angle=Math.atan2(y-cy,x-cx),sx=cx+Math.cos(angle)*orb.radius*.35,sy=cy+Math.sin(angle)*orb.radius*.35;
    const d=name==='tasks'?`M ${sx} ${sy} C ${sx} ${y-25}, ${x} ${y-40}, ${x} ${y}`:`M ${sx} ${sy} C ${(sx+x)/2} ${sy}, ${(sx+x)/2} ${y}, ${x} ${y}`;
    const group=document.createElementNS(svg.namespaceURI,'g');group.dataset.link=name;group.classList.toggle('active',name===focusedPanel);group.style.color=getComputedStyle(panel).getPropertyValue('--accent');
    for(const cls of ['connection-line','connection-pulse']){const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',d);path.setAttribute('class',cls);path.setAttribute('pathLength','1000');path.style.animationDelay=`${panelNames.indexOf(name)*-.7}s`;group.append(path);}
    const dot=document.createElementNS(svg.namespaceURI,'circle');dot.setAttribute('cx',x);dot.setAttribute('cy',y);dot.setAttribute('r','4');group.append(dot);svg.append(group);
  }
}
function startDrag(e,name,resize){if(e.button!==0||matchMedia('(max-width: 1000px)').matches)return;e.preventDefault();const b=$('projectBoard').getBoundingClientRect(),p=panels[name].element,r=p.getBoundingClientRect();const initial={x:(r.x-b.x)/b.width*100,y:(r.y-b.y)/b.height*100,w:r.width/b.width*100,h:r.height/b.height*100};let next={...initial};dragging=true;e.target.setPointerCapture(e.pointerId);const move=event=>{const dx=(event.clientX-e.clientX)/b.width*100,dy=(event.clientY-e.clientY)/b.height*100;next=resize?{...initial,w:Math.max(10,Math.min(100-initial.x,initial.w+dx)),h:Math.max(10,Math.min(100-initial.y,initial.h+dy))}:{...initial,x:Math.max(0,Math.min(100-initial.w,initial.x+dx)),y:Math.max(0,Math.min(100-initial.h,initial.y+dy))};for(const [k,prop] of Object.entries({x:'left',y:'top',w:'width',h:'height'}))p.style[prop]=next[k]+'%';drawLinks();};const end=()=>{dragging=false;e.target.removeEventListener('pointermove',move);e.target.removeEventListener('pointerup',end);e.target.removeEventListener('pointercancel',end);void act('save_layout',{layout:{...snapshot.project.layout,[name]:next}}).catch(report);};e.target.addEventListener('pointermove',move);e.target.addEventListener('pointerup',end);e.target.addEventListener('pointercancel',end);}
window.addEventListener('resize',()=>requestAnimationFrame(drawLinks));
new MutationObserver(()=>{if(reducedMotion())for(const panel of Object.values(panels))panel.element.getAnimations().forEach(a=>a.cancel());}).observe(document.body,{attributes:true,attributeFilter:['data-reduced-motion']});
export function initWorkspace(send){sendText=send;void refresh();const poll=setInterval(()=>{if(!document.hidden&&!dragging){void refresh();void pollInventory();}},2500);addEventListener('pagehide',()=>clearInterval(poll),{once:true});}
export function workspaceEvent(event){
  if(event.type==='workspace_changed'){demoErrors.delete(snapshot.active_id);void refresh(true);void pollInventory();}
  if(event.type==='tool_status'){if(event.status==='working')notice(['control_ui','get_ui_state'].includes(event.name)?'Ada is updating the screen…':'Ada is working on your project…');else if(event.status==='error')notice(event.message);else notice(event.name==='generate_demo_image'?'':'Done.');}
  if(event.type==='transcript'&&event.role==='assistant'){const key=`${event.epoch}:${event.turn}`;if(key!==replyTurn){reply='';replyTurn=key;}reply=(reply+event.text).slice(-16000);$('readReply').textContent=reply;$('adaReply').hidden=!reply;}
}

// Named screen operations keep voice control independent of DOM selectors in model output.
export async function workspaceUI(action,args={}){
  await refresh(true);
  if(action==='prepare_print'){const id=args.revision_id||snapshot.cad?.current?.id;if(!id)throw Error('Generate and check the CAD first.');await openPrinting(snapshot.active_id,id);return printingState();}
  if(action==='control_plate')return controlPlate(args);
  if(action==='control_print')return controlPrint(args);
  if(action==='close'&&printingState().print_view_open){closePrinting();return {view:'cad'};}
  if(action==='cad_control')return controlCad(args);
  if(action==='close'&&cadUIState().cad_view_open&&!$('workspaceDialog').open){selectBoardTab('overview');return {view:'overview'};}
  if(action==='read_document'||action==='edit_document'){
    const d=$('workspaceDialog');if(!d.open||!d.dataset.path)throw Error('Open a file first.');
    const editor=d.querySelector('.code-editor');
    if(action==='read_document'&&editor&&editor.value!==editor.adaOriginal)throw Error('Say “save this” to save your edits and return to reading.');
    return openFile(d.dataset.path,action==='edit_document');
  }
  if(action==='document_section'){
    if(!$('workspaceDialog').open&&planData)await openFile(planData.path);
    return focusDocumentSection(args.value);
  }
  if(action==='projects'){library(args.query||'');return {view:'projects'};}
  if(action==='close'||action==='cancel'){$('workspaceDialog').close();pendingConfirmation=null;return {closed:true};}
  if(action==='show_response'){showReply();return {view:'Ada’s response'};}
  if(action==='confirm'){if(!pendingConfirmation)throw Error('There is no confirmation waiting.');await pendingConfirmation();return {confirmed:true};}
  if(action==='save_visible'){const form=$('workspaceDialog').open&&$('dialogBody').querySelector('form');if(!form?.adaSubmit)throw Error('There is no open form to save.');await form.adaSubmit();return {saved:true};}
  throw Error('Unknown workspace screen action.');
}
export function workspaceUIState(){
  const d=$('workspaceDialog'),root=d.open?$('dialogBody'):snapshot.project?$('projectBoard'):host;
  const items=[...root.querySelectorAll('[data-card-id],[data-project-id],[data-path],[data-plan-section]')].slice(0,20).map((e,i)=>({number:i+1,label:e.innerText.slice(0,120),kind:snapshot.project?.cards.find(c=>c.id===e.dataset.cardId)?.kind,card_id:e.dataset.cardId,project_id:e.dataset.projectId,path:e.dataset.path||(e.dataset.planSection?planData?.path:undefined),section_number:e.dataset.planSection?Number(e.dataset.planSection):undefined,folder:e.dataset.folder==='true'}));
  return {...inventoryUIState(),...cadUIState(),...printingState(),active_project:snapshot.active_id,project_name:snapshot.project?.name||null,view:printingState().print_view_open?'print':d.open?$('dialogTitle').textContent:snapshot.project?boardTab:'welcome',
    path:d.open?d.dataset.path:undefined,card_id:d.open?d.dataset.cardId:undefined,document_mode:d.open?d.dataset.documentMode:undefined,
    document_sections:d.open?[...d.querySelectorAll('[data-document-section]')].slice(0,30).map(e=>({number:Number(e.dataset.documentSection),title:e.dataset.sectionTitle.slice(0,160)})):[],items,confirmation_pending:d.open&&!!pendingConfirmation,
    selected_tab:boardTab,focused_panel:focusedPanel,plan_path:findPlan()?.path,parts_path:findParts()?.path,plan_sections:planData?.sections||[],image_generation:snapshot.image_generation,
    panel_layout:snapshot.project?Object.fromEntries(panelNames.map(name=>[name,snapshot.project.layout[name]||defaults[name]])):{},
    visible_text:root.innerText.slice(0,1500)};
}
