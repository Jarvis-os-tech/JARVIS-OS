import * as THREE from './vendor/three/build/three.module.js';
import {GLTFLoader} from './vendor/three/examples/jsm/loaders/GLTFLoader.js';
import {OrbitControls} from './vendor/three/examples/jsm/controls/OrbitControls.js';

const reduced=()=>document.body.dataset.reducedMotion==='true';
function release(root){root.traverse(o=>{o.geometry?.dispose();for(const m of (Array.isArray(o.material)?o.material:[o.material]))m?.dispose();});}

export async function createCadViewer(host,url,manifest,onSelect,previouslyVisible=[]){
  const canvas=document.createElement('canvas');canvas.setAttribute('aria-label','Assembled CAD model. Drag to rotate, scroll to zoom.');
  canvas.tabIndex=0;host.append(canvas);
  canvas.dataset.gestureCad='true';
  const renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true,powerPreference:'low-power'});
  renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.setClearColor(0x031014,0);
  renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;
  const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(35,1,.001,1000);
  scene.add(new THREE.HemisphereLight(0xc9fff2,0x153240,2.5));
  for(const [color,x,y,z,intensity] of [[0xa2fff0,3,5,4,3],[0xc29af4,-4,2,-2,2],[0xf1bd72,1,1,-3,1.5]]){
    const light=new THREE.DirectionalLight(color,intensity);light.position.set(x,y,z);scene.add(light);
  }
  const controls=new OrbitControls(camera,canvas);controls.enableDamping=false;controls.autoRotateSpeed=.65;
  let alive=true,frame=0,lastFrame=0,model=null,parts=[],radius=1,centre=new THREE.Vector3(),selected='',orbit=false;
  let explosion=0,target=0,reveal=reduced()?1:0,previous=performance.now(),cameraGoal=null;
  const abort=new AbortController();
  function schedule(){if(alive&&!frame&&!document.hidden)frame=requestAnimationFrame(draw);}
  function draw(time){
    frame=0;if(!alive||document.hidden)return;
    if(time-lastFrame<32){schedule();return;}lastFrame=time;
    const dt=Math.min(.06,(time-previous)/1000);previous=time;
    reveal=reduced()?1:Math.min(1,reveal+dt/.95);
    explosion=reduced()?target:THREE.MathUtils.damp(explosion,target,8,dt);
    if(Math.abs(explosion-target)<.002)explosion=target;
    const ease=1-Math.pow(1-reveal,3);
    if(cameraGoal){
      if(reduced())camera.position.copy(cameraGoal);
      else camera.position.lerp(cameraGoal,1-Math.exp(-6*dt));
      if(camera.position.distanceTo(cameraGoal)<radius*.002){camera.position.copy(cameraGoal);cameraGoal=null;}
      controls.update();
    }
    for(const p of parts){
      const partEase=previouslyVisible.includes(p.id)?1:ease;
      p.node.position.copy(p.home).addScaledVector(p.offset,explosion+(1-partEase)*1.2);
      p.node.traverse(o=>{if(o.isMesh)o.material.opacity=.35+.65*partEase;});
    }
    if(orbit&&!reduced()){controls.autoRotate=true;controls.update(dt);}else controls.autoRotate=false;
    renderer.render(scene,camera);canvas.dataset.rendered='true';
    if(reveal<1||explosion!==target||cameraGoal||orbit&&!reduced())schedule();
  }
  function fitDistance(){return radius/Math.sin(THREE.MathUtils.degToRad(camera.fov/2))*1.15/Math.min(1,camera.aspect)*(1+target*.7);}
  function easeCamera(){cameraGoal=camera.position.clone().sub(controls.target).normalize().multiplyScalar(fitDistance()).add(controls.target);}
  function fit(){
    cameraGoal=null;controls.target.copy(centre);camera.position.copy(centre).add(new THREE.Vector3(1,.72,1.25).normalize().multiplyScalar(fitDistance()));
    camera.near=Math.max(radius/1000,.00001);camera.far=radius*100;camera.updateProjectionMatrix();
    controls.minDistance=radius*.5;controls.maxDistance=radius*20;controls.update();schedule();
  }
  function resize(){const box=host.getBoundingClientRect();if(!box.width||!box.height)return;renderer.setSize(box.width,box.height,false);camera.aspect=box.width/box.height;camera.updateProjectionMatrix();schedule();}
  const observer=new ResizeObserver(resize);observer.observe(host);
  const motion=new MutationObserver(()=>{if(reduced())orbit=false;schedule();});motion.observe(document.body,{attributes:true,attributeFilter:['data-reduced-motion']});
  function visibility(){if(document.hidden){cancelAnimationFrame(frame);frame=0;}else {previous=performance.now();schedule();}}
  document.addEventListener('visibilitychange',visibility);controls.addEventListener('change',schedule);
  let pointerStart=null,gestureActive=false;
  const down=e=>{pointerStart=[e.clientX,e.clientY];};
  const up=e=>{
    if(!pointerStart||Math.hypot(e.clientX-pointerStart[0],e.clientY-pointerStart[1])>5)return;
    pointerStart=null;pick(e.clientX,e.clientY);
  };
  function pick(x,y){
    const b=canvas.getBoundingClientRect(),ray=new THREE.Raycaster();
    ray.setFromCamera(new THREE.Vector2((x-b.left)/b.width*2-1,-(y-b.top)/b.height*2+1),camera);
    const hit=ray.intersectObjects(parts.filter(p=>p.node.visible).map(p=>p.node),true).find(h=>h.object.isMesh);
    if(hit){let o=hit.object;while(o&&!parts.some(p=>p.node===o))o=o.parent;const part=parts.find(p=>p.node===o);if(part)onSelect(part.id);}
  }
  // Explicit camera control avoids synthetic pointer capture and accidental part clicks.
  function gesture(event){
    if(!alive||!model)return;
    const {action,dx,dy,x,y}=event.detail||{};
    if(action==='begin'){
      gestureActive=true;orbit=false;controls.autoRotate=false;cameraGoal=null;pointerStart=null;
      controls.enabled=false;
    }else if(action==='end'){
      gestureActive=false;controls.enabled=true;
    }else if(action==='rotate'&&gestureActive&&Number.isFinite(dx)&&Number.isFinite(dy)){
      const offset=camera.position.clone().sub(controls.target),spherical=new THREE.Spherical().setFromVector3(offset);
      const height=Math.max(1,canvas.getBoundingClientRect().height);
      spherical.theta-=2*Math.PI*dx/height;
      spherical.phi=THREE.MathUtils.clamp(spherical.phi-2*Math.PI*dy/height,.08,Math.PI-.08);
      camera.position.copy(controls.target).add(new THREE.Vector3().setFromSpherical(spherical));
      controls.update();schedule();
    }else if(action==='select'&&!gestureActive&&Number.isFinite(x)&&Number.isFinite(y))pick(x,y);
  }
  canvas.addEventListener('ada-gesture',gesture);
  canvas.addEventListener('pointerdown',down);canvas.addEventListener('pointerup',up);
  function select(id){
    selected=id;
    for(const p of parts)p.node.traverse(o=>{if(o.isMesh){o.material.emissive.set(p.id===id?0x146b67:0x000000);o.material.emissiveIntensity=p.id===id?.6:0;}});
    schedule();
  }
  function control(action,id){
    if(action==='fit')fit();
    else if(action==='explode'){target=1;easeCamera();}
    else if(action==='assemble'){target=0;easeCamera();}
    else if(action==='orbit')orbit=!reduced();
    else if(action==='stop_orbit')orbit=false;
    else if(action==='show_all')parts.forEach(p=>p.node.visible=true);
    else {
      const part=parts.find(p=>p.id===id);if(!part)throw Error('Choose a component from the assembly list.');
      if(action==='hide')part.node.visible=false;
      else if(action==='select'){part.node.visible=true;select(id);}
      else if(action==='isolate'){parts.forEach(p=>p.node.visible=p.id===id);select(id);}
      else throw Error('Unknown CAD view action.');
    }
    schedule();return {action,part_id:id||null,exploded:target===1,orbit};
  }
  function dispose(){
    if(!alive)return;
    alive=false;abort.abort();cancelAnimationFrame(frame);observer.disconnect();motion.disconnect();
    canvas.removeEventListener('ada-gesture',gesture);
    document.removeEventListener('visibilitychange',visibility);controls.dispose();release(scene);renderer.dispose();renderer.forceContextLoss();canvas.remove();
  }
  // The host may close while a model is loading; immediately release resources in that case.
  const removal=new MutationObserver(()=>{if(!host.isConnected||!canvas.isConnected){removal.disconnect();dispose();}});
  removal.observe(document.body,{childList:true,subtree:true});
  try{
    const response=await fetch(url,{signal:AbortSignal.any([abort.signal,AbortSignal.timeout(30000)])});if(!response.ok)throw Error('The saved preview could not be loaded.');
    const bytes=await response.arrayBuffer();
    const gltf=await new Promise((resolve,reject)=>new GLTFLoader().parse(bytes,'',resolve,reject));
    if(!alive){release(gltf.scene);throw Error('Viewer closed.');}
    model=gltf.scene;scene.add(model);model.updateMatrixWorld(true);
    const bounds=new THREE.Box3().setFromObject(model);bounds.getCenter(centre);radius=Math.max(bounds.getSize(new THREE.Vector3()).length()/2,.001);
    model.traverse(o=>{if(o.isMesh){const color=o.material.color?.clone()||new THREE.Color(0x70b9b5);o.material.dispose();o.material=new THREE.MeshStandardMaterial({color,metalness:.32,roughness:.4,transparent:true});
      const edge=new THREE.LineSegments(new THREE.EdgesGeometry(o.geometry,28),new THREE.LineBasicMaterial({color:0x91f9e3,transparent:true,opacity:.22}));o.add(edge);
    }});
    parts=manifest.design.instances.map((instance,index)=>{
      const node=model.getObjectByName(instance.id);if(!node)throw Error('The model is missing a named assembly component.');
      const c=new THREE.Box3().setFromObject(node).getCenter(new THREE.Vector3()),direction=c.clone().sub(centre);
      if(direction.length()<radius*.05)direction.set(Math.cos(index*2.4),.4,Math.sin(index*2.4));
      direction.normalize().multiplyScalar(radius*.8);
      const origin=node.parent.worldToLocal(c.clone()),offset=node.parent.worldToLocal(c.add(direction)).sub(origin);
      return {id:instance.id,node,home:node.position.clone(),offset};
    });
    const grid=new THREE.GridHelper(radius*5,24,0x327f7a,0x123d43);grid.position.set(centre.x,bounds.min.y-radius*.05,centre.z);
    grid.material.transparent=true;grid.material.opacity=.45;scene.add(grid);
    const ring=new THREE.Mesh(new THREE.RingGeometry(radius*1.6,radius*1.605,96),new THREE.MeshBasicMaterial({color:0x4fd9cf,transparent:true,opacity:.4,side:THREE.DoubleSide}));
    ring.rotation.x=-Math.PI/2;ring.position.copy(grid.position);scene.add(ring);
    resize();fit();schedule();
    return {control,select,dispose:()=>{removal.disconnect();dispose();},state:()=>({selected,exploded:target===1,orbit,gestureActive,camera:camera.position.toArray(),parts:parts.map(p=>({id:p.id,visible:p.node.visible}))})};
  }catch(error){removal.disconnect();dispose();throw error;}
}
