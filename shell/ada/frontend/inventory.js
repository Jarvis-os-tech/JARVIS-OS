// Shared inventory and live project stock. All model suggestions remain editable drafts.
let H,activeRoot=null,activeScan='',lastRevision=-1,dirty=false,busy=false,query='';
let stockSnapshot={items:[],scans:[],history:[]},rowForms=[];
let stopCameraPreview=()=>{};
const pendingRequests=new Map();
const el=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e;};
const photoURL=name=>'/api/inventory/photos/'+encodeURIComponent(name);
const id=()=>crypto.randomUUID();
const api=(path='',options={})=>H.request('/api/inventory'+path,options);
const post=(path,body)=>api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
const button=(label,fn,cls='')=>H.button(label,fn,cls);
const field=(parent,label,value='',multi=false)=>H.field(parent,label,value,multi);
const number=(parent,label,value,min=0)=>{const e=field(parent,label,value);e.type='number';e.min=min;e.max=1000000;e.step=1;e.required=true;return e;};
function select(parent,label,options,value=''){
  const l=el('label','form-field',label),s=el('select');
  for(const [key,text] of options){const o=el('option','',text);o.value=key;s.append(o);}if(options.some(([key])=>key===value))s.value=value;l.append(s);parent.append(l);return s;
}
function link(label,url){const a=el('a','secondary',label);a.href=url;return a;}
function parseSpecs(text){const result={};for(const line of text.split('\n').filter(l=>l.trim())){const index=line.indexOf(':');if(index<1)throw Error('Write specifications as name: value, one per line.');result[line.slice(0,index).trim()]=line.slice(index+1).trim();}return result;}
function partFields(form,part={}){
  const name=field(form,'Part name',part.name||'');name.required=true;name.maxLength=160;
  const category=field(form,'Category',part.category||'Other');
  const manufacturer=field(form,'Manufacturer',part.manufacturer||'');
  const model=field(form,'Exact model / part number',part.model||'');
  const specs=field(form,'Confirmed specifications · one name: value per line',Object.entries(part.specifications||{}).map(([k,v])=>`${k}: ${v}`).join('\n'),true);
  const notes=field(form,'Notes',part.notes||'',true);
  return ()=>({name:name.value.trim(),category:category.value,manufacturer:manufacturer.value,model:model.value,
    specifications:parseSpecs(specs.value),notes:notes.value,aliases:part.aliases||''});
}
async function change(operation,data){
  const fingerprint=JSON.stringify([operation,data]);
  if(!pendingRequests.has(fingerprint))pendingRequests.set(fingerprint,id());
  const result=await post('/action',{operation,data,request_id:pendingRequests.get(fingerprint)});
  pendingRequests.delete(fingerprint);lastRevision=-1;return result;
}
function root(title){stopCameraPreview();const body=H.dialog(title,true);const r=el('section','inventory-view');body.append(r);activeRoot=r;dirty=true;rowForms=[];return r;}
function markDirty(r){r.addEventListener('input',()=>{dirty=true;});}
function navigation(r){const bar=el('div','inventory-toolbar');bar.append(button('All inventory',()=>openInventory()),button('Scan desk',()=>scanSetup(),'primary'),button('Add manually',()=>addStock()),button('History',()=>history()),button('Camera',()=>cameraSettings()),link('Back up inventory','/api/inventory/backup'));r.append(bar);}

export function setupInventory(hooks){H=hooks;}
export async function openInventory(scanId=''){
  activeScan=scanId;const r=root(scanId?'Review scanned parts':'Parts inventory');dirty=false;
  r.append(el('p','empty-copy','Loading inventory…'));
  stockSnapshot=await api();if(!r.isConnected)return;
  lastRevision=stockSnapshot.revision;render(r);
}
function render(r){
  r.replaceChildren();rowForms=[];navigation(r);
  if(activeScan){const scan=stockSnapshot.scans.find(s=>s.id===activeScan);if(scan){renderScan(r,scan);return;}void api('/scans/'+encodeURIComponent(activeScan)).then(scan=>{if(r.isConnected)renderScan(r,scan);}).catch(H.report);return;}
  const summary=el('div','inventory-summary');
  for(const [label,count] of [['Part types',stockSnapshot.items.length],['Units on hand',stockSnapshot.items.reduce((n,p)=>n+p.quantity,0)],['Reserved',stockSnapshot.items.reduce((n,p)=>n+p.reserved,0)]]){
    const card=el('div');card.append(el('strong','',String(count)),el('span','',label));summary.append(card);
  }r.append(summary);
  const search=field(r,'Find parts by name, model or specifications',query),grid=el('div','inventory-grid');r.append(grid);
  const fill=()=>{query=search.value;grid.replaceChildren();for(const part of stockSnapshot.items.filter(p=>JSON.stringify(p).toLowerCase().includes(query.toLowerCase()))){
    const card=el('article','inventory-card');card.dataset.partId=part.id;
    card.append(el('span','inventory-category',part.category),el('h3','',part.name),el('p','inventory-model',[part.manufacturer,part.model].filter(Boolean).join(' · ')||'Model not recorded'));
    const qty=el('p','inventory-quantity',`${part.quantity} on hand`);qty.append(el('small','',`${part.available} available · ${part.reserved} reserved`));card.append(qty);
    const locations=[...new Set(part.lots.map(l=>l.location||'Location not set'))];
    card.append(el('p','inventory-location',locations.join(', ')));
    card.append(button('Details & stock',()=>partDetail(part)),button('Add more',()=>addStock(part)));grid.append(card);
  }if(!grid.children.length)grid.append(el('p','empty-copy','No matching parts recorded. Scan the desk or add confirmed stock manually.'));};search.oninput=fill;fill();
  if(stockSnapshot.scans.length){r.append(el('h3','','Recent scans'));const scans=el('div','inventory-scans');for(const scan of stockSnapshot.scans){scans.append(button(`${new Date(scan.created_at).toLocaleString()} · ${scan.mode==='add'?'Add stock':'Recount'} · ${scan.status}`,()=>openInventory(scan.id)));}r.append(scans);}
}

async function scanSetup(){
  activeScan='';const r=root('Scan the desk');navigation(r);
  r.append(el('p','empty-copy','Separate the parts and turn labels toward the camera. USB is preferred; the Pi ribbon camera is used when USB capture is unavailable. Photos are sent to Gemini for identification.'));
  const form=el('form');r.append(form);
  const mode=select(form,'What is this scan for?',[['add','Add newly received / unrecorded stock'],['recount','Recount an existing storage batch']]);
  const location=field(form,'Storage location','');
  const requestId=id();
  H.submit(form,'Capture & identify',async()=>{const scan=await post('/scans',{mode:mode.value,location:location.value,request_id:requestId});await openInventory(scan.id);});
  form.append(button('Camera preview',()=>cameraSettings()));
}
function outline(imageFrame,scan){
  const img=el('img','scan-photo');img.src=photoURL(scan.photos[0]);img.alt='Desk photograph used for this scan';imageFrame.append(img);
  scan.rows.forEach((row,index)=>row.boxes.forEach(box=>{const b=button(String(index+1),()=>document.querySelector(`[data-scan-row="${row.id}"]`)?.scrollIntoView({block:'center'}),'scan-box');
    b.style.left=box[1]/10+'%';b.style.top=box[0]/10+'%';b.style.width=(box[3]-box[1])/10+'%';b.style.height=(box[2]-box[0])/10+'%';b.title=`Item ${index+1}: ${row.part.name}`;imageFrame.append(b);}));
}
function renderScan(r,scan){
  const heading=el('div','inventory-scan-heading');heading.append(el('h3','',scan.mode==='add'?'Add stock from this photograph':'Recount existing stock'),el('span','inventory-badge',scan.status));r.append(heading);
  r.append(el('p','empty-copy',scan.camera?.message||'USB camera first · Pi ribbon camera fallback'));
  if(scan.photos.length){const frame=el('div','scan-image');outline(frame,scan);r.append(frame);}
  if(scan.message)r.append(el('p','inventory-warning',scan.message));
  if(['capturing','analysing','refining'].includes(scan.status)){const status=el('p','inventory-progress',scan.status==='capturing'?'Taking a photograph…':scan.status==='refining'?'Reading the selected part more closely…':'Hydrogen is identifying and counting your parts…');status.setAttribute('role','status');r.append(status,button('Cancel scan',async()=>{const latest=await api('/scans/'+scan.id);await change('discard_scan',{scan_id:scan.id,expected_revision:latest.revision});await openInventory(scan.id);}));return;}
  if(scan.status!=='review'){r.append(el('p','empty-copy',scan.status==='complete'?'This scan has been saved. Reopening it does not add stock again.':'No further stock will be added from this scan.'));return;}
  const pending=scan.rows.filter(row=>!row.saved);
  for(const [index,row] of scan.rows.entries()){
    const card=el('form','scan-review-card');card.dataset.scanRow=row.id;card.dataset.partId=row.part_id||'';card.dataset.number=String(index+1);
    card.append(el('h3','',`${index+1}. ${row.part.name} · ${row.quantity} detected${row.saved?' · Saved':''}`));
    if(row.saved){r.append(card);continue;}
    card.append(el('p','inventory-evidence',row.label_text||'No readable label text'),el('p','inventory-warning',row.uncertainties||'Review the identity and count before saving.'));
    const selected=select(card,'Catalogue match',[['','Create a new part type'],...stockSnapshot.items.map(p=>[p.id,`${p.name} · ${p.model||'model unknown'} (${p.quantity} on hand)${row.suggested_part_ids?.includes(p.id)?' · suggested':''}`])],row.part_id);
    const details=el('details','inventory-details');details.append(el('summary','','Edit name, model & specifications'));card.append(details);
    const getPart=partFields(details,row.part);
    const qty=number(card,scan.mode==='recount'?'Count now present in this batch':'Units to add',row.quantity,1);
    const location=field(card,'Storage location',row.location);
    const condition=select(card,'Stock status',[['available','Available'],['untested','Untested · exclude from project availability'],['faulty','Faulty · exclude from availability']],row.condition);
    const lot=select(card,'Existing storage batch · required for recount',[['','Choose a batch'],...stockSnapshot.items.flatMap(p=>p.lots.map(l=>[l.id,`${p.name} · ${l.location||'No location'} · ${l.quantity} units`]))],row.lot_id);
    lot.hidden=scan.mode!=='recount';lot.parentElement.hidden=scan.mode!=='recount';
    const calc=el('p','inventory-calculation');card.append(calc);
    const update=()=>{const p=stockSnapshot.items.find(p=>p.id===selected.value);const before=p?.quantity||0;calc.textContent=scan.mode==='add'?`${before} currently recorded + ${qty.value||0} in this scan → ${before+Number(qty.value||0)} total`:'Recount replaces this storage batch’s quantity.';};selected.onchange=update;qty.oninput=update;update();
    const approvedLabel=el('label','inventory-check'),approved=el('input');approved.type='checkbox';approved.checked=row.confirmed;approvedLabel.append(approved,el('span','','I confirm this identity, quantity and stock status'));card.append(approvedLabel);
    const refine=async captureNew=>{if(dirty)throw Error('Save your review edits before requesting a close-up.');await post('/scans/'+scan.id+'/refine',{row_id:row.id,expected_revision:scan.revision,capture_new:captureNew,request_id:id()});await openInventory(scan.id);};
    card.append(button('Read label more closely',()=>refine(false)),button('Part is ready · take a new close-up',()=>refine(true)));
    if(row.detail_photo){const detail=el('img','inventory-evidence-photo');detail.src=photoURL(row.detail_photo);detail.alt='Close-up of '+row.part.name;card.append(detail);}
    markDirty(card);rowForms.push({id:row.id,card,read:()=>({...row,part:getPart(),part_id:selected.value,lot_id:lot.value,
      part_revision:stockSnapshot.items.find(p=>p.id===selected.value)?.revision??null,
      lot_revision:stockSnapshot.items.flatMap(p=>p.lots).find(l=>l.id===lot.value)?.revision??null,
      quantity:Number(qty.value),location:location.value,condition:condition.value,confirmed:approved.checked})});r.append(card);
  }
  const bar=el('div','inventory-save-bar');const save=button('Save confirmed items',async()=>{
    const selected=rowForms.filter(f=>f.read().confirmed);if(!selected.length)throw Error('Confirm at least one item to save.');
    for(const f of selected)if(!f.card.reportValidity())throw Error('Complete the highlighted item details.');
    save.disabled=true;
    try{
      let current=await api('/scans/'+scan.id);
      if(current.revision!==scan.revision)throw Error('This scan changed while you were reviewing it. Reload before saving.');
      for(const f of selected)current=await change('edit_scan',{scan_id:scan.id,expected_revision:current.revision,row:f.read()});
      await change('confirm_scan',{scan_id:scan.id,expected_revision:current.revision,row_ids:selected.map(f=>f.id),confirmed:true});
      dirty=false;H.notice('Confirmed stock saved. Project availability is now updated.');await openInventory(scan.id);
    }finally{save.disabled=false;}
  },'primary');bar.append(save,button('Save review edits',async()=>{
    let current=await api('/scans/'+scan.id);if(current.revision!==scan.revision)throw Error('This scan changed. Reload before saving edits.');
    for(const f of rowForms){if(!f.card.reportValidity())throw Error('Complete the highlighted item details.');current=await change('edit_scan',{scan_id:scan.id,expected_revision:current.revision,row:f.read()});}
    await openInventory(scan.id);
  }),button('Discard remaining items',async()=>{await change('discard_scan',{scan_id:scan.id,expected_revision:scan.revision});await openInventory();}));
  bar.append(button('Reload saved review',()=>openInventory(scan.id)));
  r.append(bar,el('p','empty-copy',`${pending.length} items awaiting review. Close-ups and reopened scans do not add stock.`));
}

async function addStock(part=null){
  activeScan='';const r=root(part?'Add '+part.name:'Add confirmed stock');navigation(r);
  const form=el('form','inventory-form');r.append(form);
  const getPart=part?()=>null:partFields(form);
  const qty=number(form,'Quantity',1),location=field(form,'Storage location','');
  const condition=select(form,'Stock status',[['available','Available'],['untested','Untested'],['faulty','Faulty']]);
  const serial=field(form,'Serial number · optional for a single unit','');
  H.submit(form,'Save stock',async()=>{await change('add_stock',{...(part?{part_id:part.id}:{part:getPart()}),quantity:Number(qty.value),location:location.value,condition:condition.value,serial:serial.value});await openInventory();});markDirty(r);
}
async function partDetail(part){
  const r=root(part.name);navigation(r);r.append(el('p','inventory-quantity',`${part.quantity} on hand · ${part.available} available · ${part.reserved} reserved`));
  r.append(el('p','',JSON.stringify(part.specifications)),el('p','',part.notes));
  r.append(button('Edit identity & specifications',()=>{const pane=root('Edit '+part.name),form=el('form');pane.append(form);const get=partFields(form,part);H.submit(form,'Save details',async()=>{await change('edit_part',{part_id:part.id,expected_revision:part.revision,part:get()});await openInventory();});markDirty(pane);}));
  for(const lot of part.lots){const card=el('article','inventory-card');card.append(el('h3','',lot.location||'Location not set'),el('p','',`${lot.quantity} units · ${lot.condition}${lot.serial?' · '+lot.serial:''}`));
    card.append(button('Use, return or correct quantity',()=>{const pane=root('Update '+part.name),form=el('form');pane.append(form);const qty=number(form,'New quantity in this storage batch',lot.quantity),reason=field(form,'Reason · used, returned or corrected','');reason.required=true;
      const project=H.projectId();const release=select(form,'Project usage',[['','No project reservation change'],...(project?[[project,'Release this project’s reservation for units used']]:[])]);
      H.submit(form,'Save quantity',async()=>{await change('adjust_stock',{lot_id:lot.id,expected_revision:lot.revision,quantity:Number(qty.value),reason:reason.value,project_id:release.value});await openInventory();});markDirty(pane);}),
    button('Move / change status',()=>{const pane=root('Storage & condition'),form=el('form');pane.append(form);const location=field(form,'Location',lot.location),condition=select(form,'Status',[['available','Available'],['untested','Untested'],['faulty','Faulty']],lot.condition),serial=field(form,'Serial number',lot.serial);
      H.submit(form,'Save batch',async()=>{await change('edit_lot',{lot_id:lot.id,expected_revision:lot.revision,location:location.value,condition:condition.value,serial:serial.value});await openInventory();});markDirty(pane);}));r.append(card);
  }
  for(const evidence of part.evidence||[]){const image=el('img','inventory-evidence-photo');image.src=photoURL(evidence.detail_photo||evidence.photos[0]);image.alt='Saved evidence for '+part.name;r.append(image);}
  markDirty(r);dirty=true; // Keep details stable until a deliberate refresh.
}
async function history(){const r=root('Stock history');navigation(r);const latest=await api();if(!r.isConnected)return;
  for(const op of latest.history){const row=el('article','inventory-card');row.append(el('strong','',op.kind.replaceAll('_',' ')),el('p','',new Date(op.created_at).toLocaleString()));if(['add_stock','adjust_stock','confirm_scan'].includes(op.kind)&&!op.undone)row.append(button('Undo quantity change',async()=>{await change('undo',{operation_id:op.id});await history();}));else if(op.undone)row.append(el('span','','Undone'));r.append(row);}dirty=true;
}
async function cameraSettings(){
  const r=root('Inventory camera');navigation(r);const state=await api('/camera');if(!r.isConnected)return;
  r.append(el('p','empty-copy','Live preview follows the selected camera. Automatic selection tries USB first, then the Pi ribbon camera. Preview stays on this device and is not sent to Gemini.'));
  const layout=el('div','inventory-camera-layout');r.append(layout);
  const form=el('form','inventory-form');layout.append(form);
  const device=select(form,'Preferred USB camera',[['','Automatically select a connected USB camera'],...[...new Set([...state.devices,...(state.settings.usb_device?[state.settings.usb_device]:[])])].map(d=>[d,d])],state.settings.usb_device);
  const rotation=select(form,'Rotate photograph',[['0','0°'],['90','90°'],['180','180°'],['270','270°']],String(state.settings.rotation));
  const width=number(form,'Capture width',state.settings.width,320),height=number(form,'Capture height',state.settings.height,240);
  const save=()=>post('/camera',{usb_device:device.value,rotation:Number(rotation.value),width:Number(width.value),height:Number(height.value)});
  H.submit(form,'Save camera settings',async()=>{await save();H.notice('Camera settings saved.');});
  const preview=el('div','inventory-live-preview'),status=el('p','empty-copy');status.setAttribute('role','status');
  const retry=button('Retry live preview',()=>startPreview());retry.hidden=true;preview.append(status,retry);layout.append(preview);
  const dialog=r.closest('dialog');let image=null,monitor=0,disposed=false,started=0;
  const stopStream=()=>{clearInterval(monitor);monitor=0;if(image){image.onerror=null;image.removeAttribute('src');image.remove();image=null;}};
  const startPreview=()=>{
    stopStream();if(disposed||!r.isConnected||!dialog?.open||document.hidden)return;
    status.textContent='Connecting to the selected camera…';retry.hidden=true;started=Date.now();
    image=el('img','inventory-preview');image.alt='Live view of the selected inventory camera';
    image.onerror=()=>{stopStream();status.textContent='Live preview unavailable. Check the selected camera, or retry after the scan finishes.';retry.hidden=false;};
    image.src='/api/inventory/camera/live?'+new URLSearchParams({device:device.value,rotation:rotation.value,session:id()});
    preview.insertBefore(image,retry);
    monitor=setInterval(()=>{
      if(!r.isConnected||!dialog.open){dispose();return;}
      if(image?.naturalWidth)status.textContent='Live preview · '+(device.value||'Automatic camera selection');
      else if(Date.now()-started>25000)image?.onerror?.();
    },250);
  };
  const visibility=()=>{if(document.hidden){stopStream();status.textContent='Live preview paused.';}else startPreview();};
  const observer=new MutationObserver(()=>{if(!r.isConnected||!dialog.open)dispose();});
  const dispose=()=>{if(disposed)return;disposed=true;stopStream();observer.disconnect();dialog?.removeEventListener('close',dispose);document.removeEventListener('visibilitychange',visibility);};
  stopCameraPreview=dispose;dialog?.addEventListener('close',dispose);document.addEventListener('visibilitychange',visibility);
  observer.observe(dialog,{childList:true,subtree:true,attributes:true,attributeFilter:['open']});
  device.addEventListener('change',startPreview);rotation.addEventListener('change',startPreview);startPreview();
  if(!state.usb_capture_installed)r.append(el('p','inventory-warning','USB capture software is missing. Run the camera setup script on the Pi.'));
  if(!state.pi_capture_installed)r.append(el('p','inventory-warning','Pi camera capture software is unavailable. USB capture can still work.'));
  dirty=true;
}

export async function mountProjectStock(panel,projectId,renderContent){
  panel.classList.add('live-stock');panel.dataset.projectId=projectId;panel.stockRender=renderContent;
  await updateStock(panel,true);
}
async function updateStock(panel,force=false){
  const current=await api('/projects/'+encodeURIComponent(panel.dataset.projectId));if(!panel.isConnected)return;
  const key=JSON.stringify(current);if(!force&&key===panel.stockKey)return;panel.stockKey=key;panel.replaceChildren();
  const bar=el('div','inventory-toolbar');bar.append(el('strong','','Live inventory'),button('Open inventory',()=>openInventory()),button('Scan desk',()=>scanSetup(),'primary'),link('Export current parts','/api/inventory/projects/'+encodeURIComponent(current.project_id)+'/export'));panel.append(bar);
  panel.append(el('p',current.plan_changed?'inventory-warning':'empty-copy',current.message));
  if(current.rows.length){const wrap=el('div','inventory-table-wrap'),table=el('table','inventory-stock-table');const head=el('thead'),tr=el('tr');for(const h of ['Part','Required','On hand','Available for this line','Reserved here','Still needed','Stock match'])tr.append(el('th','',h));head.append(tr);table.append(head);const body=el('tbody');
    for(const row of current.rows){const tr=el('tr');tr.dataset.requirementId=row.id;const num=n=>n===null?'Unknown':String(n);for(const text of [row.name,row.quantity===null?'To confirm':`${row.quantity} ${row.unit}`,num(row.on_hand),num(row.available),String(row.reserved),num(row.needed)])tr.append(el('td','',text));
      const controls=el('td');controls.append(button(row.part?'Matched: '+row.part.name:'Match stock',()=>matchRequirement(row,current,panel)));
      if(row.part&&!current.plan_changed&&!current.archived){controls.append(button('Reserve / release',()=>reserveRequirement(row,current)));}tr.append(controls);body.append(tr);
    }table.append(body);wrap.append(table);panel.append(wrap);
  }else panel.append(el('p','empty-copy','Save a required-parts table with Item, Quantity and Specification columns to connect this plan to inventory.'));
  panel.stockRender?.(current.display_content);
}
async function matchRequirement(row,current){
  const r=root('Match '+row.name);const snapshot=await api();if(!r.isConnected)return;
  r.append(el('p','',`Required specification: ${row.specification||'Not specified'}`),el('p','empty-copy','Choose a compatible part. Similar names alone do not establish compatibility.'));
  const form=el('form');r.append(form);const choice=select(form,'Catalogue part',[['','Unknown / not matched'],...snapshot.items.map(p=>[p.id,`${p.name} · ${p.model||'model unknown'} · ${JSON.stringify(p.specifications)}`])],row.part_id||'');
  H.submit(form,'Confirm compatible match',async()=>{await change('match_requirement',{project_id:current.project_id,requirement_id:row.id,source_revision:current.source_revision,part_id:choice.value,confirmed:true});await H.openParts();});dirty=true;
}
function reserveRequirement(row,current){const r=root('Reserve '+row.name),form=el('form');r.append(form);const quantity=number(form,'Units reserved for this project · zero releases',row.reserved);H.submit(form,'Save reservation',async()=>{await change('reserve',{project_id:current.project_id,requirement_id:row.id,source_revision:current.source_revision,quantity:Number(quantity.value)});await H.openParts();});dirty=true;}

export async function pollInventory(){
  if(busy)return;const dialog=document.getElementById('workspaceDialog');if(!dialog?.open)return;
  const panel=dialog.querySelector('.live-stock');if(!panel&&!activeRoot?.isConnected)return;busy=true;
  try{
    if(panel)await updateStock(panel);
    else if(activeRoot?.isConnected&&!dirty){const snapshot=await api();if(snapshot.revision!==lastRevision){stockSnapshot=snapshot;lastRevision=snapshot.revision;render(activeRoot);}}
  }catch(error){H.report(error);}finally{busy=false;}
}
export function inventoryUIState(){if(!activeRoot?.isConnected)return {};return {inventory_scan_id:activeScan||undefined,
  inventory_items:[...activeRoot.querySelectorAll('[data-part-id],[data-scan-row]')].slice(0,50).map((e,i)=>({number:i+1,part_id:e.dataset.partId,scan_row_id:e.dataset.scanRow,label:e.innerText.slice(0,200)}))};}
