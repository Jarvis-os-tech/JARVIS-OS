import * as THREE from './vendor/three/build/three.module.js';
import {OrbitControls} from './vendor/three/examples/jsm/controls/OrbitControls.js';

export const partColors=['#57dec6','#a796e8','#efbd77','#79b9dc','#c3d98a','#eb9ebd'];
function dispose(node){node.traverse(o=>{o.geometry?.dispose();for(const m of (Array.isArray(o.material)?o.material:[o.material])){m?.map?.dispose();m?.dispose();}});}
function readSTL(buffer){
  const data=new DataView(buffer),count=data.getUint32(80,true),vertices=new Float32Array(count*9);
  if(count>1e6||buffer.byteLength!==84+count*50)throw Error('Invalid saved STL.');
  for(let n=0;n<count;n++)for(let k=0;k<9;k++)vertices[n*9+k]=data.getFloat32(84+n*50+12+k*4,true);
  const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(vertices,3));geometry.computeVertexNormals();return geometry;
}
function label(text,color,size=12){
  const c=document.createElement('canvas');c.width=512;c.height=64;const ctx=c.getContext('2d');
  ctx.font='500 28px sans-serif';ctx.textAlign='center';ctx.fillStyle=color;ctx.fillText(text,256,43);
  const texture=new THREE.CanvasTexture(c),sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:texture,transparent:true,depthTest:false}));sprite.scale.set(size*8,size,1);return sprite;
}

export async function createPlateViewer(host,catalogue,onSelect,onChange){
  const canvas=document.createElement('canvas');canvas.setAttribute('aria-label','K2 build plate. Drag to orbit, scroll to zoom.');canvas.tabIndex=0;host.append(canvas);
  const renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true,powerPreference:'low-power'});
  renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.setClearColor(0x061218,0);
  const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(36,1,.1,3000);camera.up.set(0,0,1);
  scene.add(new THREE.HemisphereLight(0xe1fff6,0x263448,2.3));
  for(const [x,y,z,p] of [[-150,-250,450,3],[400,120,280,2]]){const l=new THREE.DirectionalLight(0xffffff,p);l.position.set(x,y,z);scene.add(l);}
  const controls=new OrbitControls(camera,canvas);controls.target.set(130,130,8);controls.enableDamping=false;controls.minDistance=170;controls.maxDistance=950;controls.maxPolarAngle=Math.PI*.49;
  const bed=new THREE.Mesh(new THREE.BoxGeometry(260,260,3),new THREE.MeshStandardMaterial({color:0x153239,roughness:.8,metalness:.25}));bed.position.set(130,130,-2);scene.add(bed);
  const grid=new THREE.GridHelper(260,26,0x537c7c,0x29494d);grid.rotation.x=Math.PI/2;grid.position.set(130,130,-.4);scene.add(grid);
  const edge=(min,max,color,z)=>{const p=[[min,min,z],[max,min,z],[max,max,z],[min,max,z],[min,min,z]].map(a=>new THREE.Vector3(...a));const g=new THREE.BufferGeometry().setFromPoints(p);scene.add(new THREE.Line(g,new THREE.LineBasicMaterial({color,transparent:true,opacity:.7})));};
  edge(0,260,0x77b6b3,-.2);edge(20,240,0x72a895,-.15);
  const front=label('CREALITY K2  /  260 × 260 MM','#8db6b5',7);front.position.set(130,-16,-1);scene.add(front);
  const axis=label('FRONT','#598682',5);axis.position.set(130,-29,-1);scene.add(axis);
  const partsGroup=new THREE.Group(),pathsGroup=new THREE.Group();scene.add(partsGroup,pathsGroup);
  let alive=true,frame=0,selected='',instances=[],mode='orbit',drag=null,down=null,layerData=null,ray=new THREE.Raycaster();
  const originals=new Map(),meshes=new Map(),partIndex=new Map(catalogue.parts.map((p,i)=>[p.id,i]));
  function draw(){frame=0;if(!alive)return;renderer.render(scene,camera);canvas.dataset.rendered='true';}
  function schedule(){if(alive&&!frame)frame=requestAnimationFrame(draw);}
  function fit(top=false){camera.position.set(...(top?[130,130,440]:[360,-200,315]));controls.target.set(130,130,8);controls.update();schedule();}
  function resize(){const r=host.getBoundingClientRect();if(!r.width||!r.height)return;renderer.setSize(r.width,r.height,false);camera.aspect=r.width/r.height;camera.updateProjectionMatrix();schedule();}
  const observer=new ResizeObserver(resize);observer.observe(host);controls.addEventListener('change',schedule);
  const abort=new AbortController();
  try{
    await Promise.all(catalogue.parts.map(async p=>{const r=await fetch(`/api/projects/${catalogue.project_id}/file?path=${encodeURIComponent(p.path)}`,{signal:abort.signal});if(!r.ok)throw Error('Could not load the saved part.');originals.set(p.id,readSTL(await r.arrayBuffer()));}));
  }catch(e){observer.disconnect();controls.dispose();renderer.dispose();dispose(scene);originals.forEach(g=>g.dispose());canvas.remove();throw e;}
  function update(next,report){
    instances=next;for(const mesh of meshes.values()){partsGroup.remove(mesh);dispose(mesh);}meshes.clear();
    for(const item of instances){
      const g=originals.get(item.part_id).clone(),euler=new THREE.Euler(...item.rotation.map(THREE.MathUtils.degToRad),'XYZ');
      g.applyMatrix4(new THREE.Matrix4().makeRotationFromEuler(euler));g.computeBoundingBox();const b=g.boundingBox,center=b.getCenter(new THREE.Vector3());
      g.translate(-center.x,-center.y,-b.min.z);
      const invalid=report?.errors.some(e=>e.includes(item.id)),color=invalid?'#f07778':partColors[partIndex.get(item.part_id)%partColors.length];
      const mesh=new THREE.Mesh(g,new THREE.MeshStandardMaterial({color,roughness:.47,metalness:.12,emissive:0x000000}));
      mesh.position.set(...item.position,0);mesh.userData.id=item.id;partsGroup.add(mesh);meshes.set(item.id,mesh);
      const wire=new THREE.LineSegments(new THREE.EdgesGeometry(g,30),new THREE.LineBasicMaterial({color,transparent:true,opacity:.32}));mesh.add(wire);
    }
    select(selected);schedule();
  }
  function select(id){selected=id;for(const [key,mesh] of meshes)mesh.material.emissive.set(key===id?0x183b40:0x000000);schedule();}
  function cast(e){const b=canvas.getBoundingClientRect();ray.setFromCamera(new THREE.Vector2((e.clientX-b.left)/b.width*2-1,-(e.clientY-b.top)/b.height*2+1),camera);return ray.intersectObjects([...meshes.values()],false)[0];}
  function planePoint(e){cast(e);return ray.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0,0,1),0),new THREE.Vector3());}
  function pointerDown(e){down=[e.clientX,e.clientY];const hit=cast(e);if(!hit||!partsGroup.visible)return;
    const id=hit.object.userData.id;select(id);onSelect(id);
    if(mode==='move'){const p=planePoint(e),item=instances.find(i=>i.id===id);drag={id,start:p,position:[...item.position]};controls.enabled=false;canvas.setPointerCapture(e.pointerId);}
    if(mode==='face'){
      const item=instances.find(i=>i.id===id),normal=hit.face.normal.clone().transformDirection(hit.object.matrixWorld);
      const q=new THREE.Quaternion().setFromUnitVectors(normal,new THREE.Vector3(0,0,-1));q.multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(...item.rotation.map(THREE.MathUtils.degToRad),'XYZ')));
      const euler=new THREE.Euler().setFromQuaternion(q,'XYZ');onChange(id,{rotation:[euler.x,euler.y,euler.z].map(v=>Math.round(THREE.MathUtils.radToDeg(v)*1000)/1000)});setMode('orbit');
    }
  }
  function pointerMove(e){if(!drag)return;const p=planePoint(e);if(!p)return;const mesh=meshes.get(drag.id);mesh.position.x=Math.round(drag.position[0]+p.x-drag.start.x);mesh.position.y=Math.round(drag.position[1]+p.y-drag.start.y);schedule();}
  function pointerUp(e){if(drag){const mesh=meshes.get(drag.id);onChange(drag.id,{position:[mesh.position.x,mesh.position.y]});drag=null;controls.enabled=mode==='orbit';if(canvas.hasPointerCapture(e.pointerId))canvas.releasePointerCapture(e.pointerId);}else if(down&&Math.hypot(e.clientX-down[0],e.clientY-down[1])<5){const hit=cast(e);if(hit&&partsGroup.visible)onSelect(hit.object.userData.id);}down=null;}
  canvas.addEventListener('pointerdown',pointerDown);canvas.addEventListener('pointermove',pointerMove);canvas.addEventListener('pointerup',pointerUp);canvas.addEventListener('pointercancel',pointerUp);
  function setMode(next){mode=next;controls.enabled=next==='orbit';canvas.style.cursor=next==='move'?'move':next==='face'?'crosshair':'grab';}
  function toolpaths(data,maxLayer,onlyLayer=false){
    layerData=data;dispose(pathsGroup);pathsGroup.clear();partsGroup.visible=!data;
    if(!data){schedule();return;}
    const groups=[[],[],[]];
    for(let i=onlyLayer?maxLayer:0;i<=maxLayer;i++){
      const layer=data.layers[i];if(!layer)continue;
      for(const s of layer.segments)groups[s[4]||0].push(s[0],s[1],layer.z+.03,s[2],s[3],layer.z+.03);
    }
    groups.forEach((points,i)=>{const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(points,3));pathsGroup.add(new THREE.LineSegments(g,new THREE.LineBasicMaterial({color:[0x5de0c4,0xf5b75f,0xb99be7][i],transparent:true,opacity:.95})));});schedule();
  }
  fit();resize();
  return {update,select,fit,setMode,toolpaths,
    dispose(){alive=false;abort.abort();cancelAnimationFrame(frame);observer.disconnect();controls.dispose();renderer.dispose();dispose(scene);originals.forEach(g=>g.dispose());canvas.remove();}
  };
}
