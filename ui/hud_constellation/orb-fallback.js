// Lightweight Canvas fallback for browsers without WebGL2.
import {orbLayout} from './project-layout.js?v=9';
const STATES = {
  connecting: {tint:[.13,.48,.83], brightness:.68, violet:.05, busy:1},
  idle: {tint:[.08,.86,.91], brightness:1, violet:.03, busy:0},
  listening: {tint:[.10,.96,.74], brightness:1.06, violet:0, busy:0},
  thinking: {tint:[.18,.64,1], brightness:.90, violet:.30, busy:.7},
  speaking: {tint:[.16,.83,1], brightness:1.25, violet:.65, busy:0},
  reconnecting: {tint:[.14,.43,.75], brightness:.65, violet:.05, busy:1},
  error: {tint:[1,.49,.13], brightness:.67, violet:0, busy:.45},
  exiting: {tint:[.08,.86,.91], brightness:0, violet:.03, busy:0},
};
const clamp = value => Number.isFinite(value) ? Math.min(1,Math.max(0,value)) : 0;
const mix = (a,b,k) => a+(b-a)*k;
// Finish fades exactly, so reduced motion settles instead of changing subpixels forever.
const settle = (a,b,k) => {const next=mix(a,b,k);return Math.abs(next-b)<.0001 ? b : next;};
const TAU=Math.PI*2;

// Subdivided icosahedron: 162 points / 480 unique edges, no external 3D library.
function geodesic() {
  const t=(1+Math.sqrt(5))/2;
  const vertices=[[-1,t,0],[1,t,0],[-1,-t,0],[1,-t,0],[0,-1,t],[0,1,t],
    [0,-1,-t],[0,1,-t],[t,0,-1],[t,0,1],[-t,0,-1],[-t,0,1]];
  const normalize=p=>{const n=Math.hypot(...p);return p.map(v=>v/n);};
  for(let i=0;i<vertices.length;i++)vertices[i]=normalize(vertices[i]);
  let faces=[[0,11,5],[0,5,1],[0,1,7],[0,7,10],[0,10,11],[1,5,9],[5,11,4],
    [11,10,2],[10,7,6],[7,1,8],[3,9,4],[3,4,2],[3,2,6],[3,6,8],[3,8,9],
    [4,9,5],[2,4,11],[6,2,10],[8,6,7],[9,8,1]];
  for(let pass=0;pass<2;pass++){
    const cache=new Map(),next=[];
    const mid=(a,b)=>{
      const key=[Math.min(a,b),Math.max(a,b)].join(':');
      if(!cache.has(key)){
        cache.set(key,vertices.length);
        vertices.push(normalize(vertices[a].map((v,i)=>(v+vertices[b][i])*.5)));
      }
      return cache.get(key);
    };
    for(const [a,b,c] of faces){
      const ab=mid(a,b),bc=mid(b,c),ca=mid(c,a);
      next.push([a,ab,ca],[b,bc,ab],[c,ca,bc],[ab,bc,ca]);
    }
    faces=next;
  }
  const edges=[],seen=new Set();
  for(const face of faces)for(let i=0;i<3;i++){
    const a=face[i],b=face[(i+1)%3],key=[Math.min(a,b),Math.max(a,b)].join(':');
    if(!seen.has(key)){seen.add(key);edges.push([a,b]);}
  }
  return {vertices,edges,points:new Float32Array(vertices.flat()),
    lines:new Float32Array(edges.flatMap(([a,b])=>[...vertices[a],...vertices[b]]))};
}
function rotation(time){
  const yaw=time*.12,pitch=.32+Math.sin(time*.09)*.13,roll=.13*Math.sin(time*.07);
  const cy=Math.cos(yaw),sy=Math.sin(yaw),cx=Math.cos(pitch),sx=Math.sin(pitch),cz=Math.cos(roll),sz=Math.sin(roll);
  return new Float32Array([
    cz*cy-sz*sx*sy,sz*cy+cz*sx*sy,-cx*sy,
    -sz*cx,cz*cx,sx,
    cz*sy+sz*sx*cy,sz*sy-cz*sx*cy,cx*cy,
  ]);
}
function surface(a,t,e,low,high,listening){
  const wave=Math.sin(a*3+t*.57)*.54+Math.sin(a*5-t*.43)*.30+Math.sin(a*8+t*.29)*.16;
  return wave*(.004+e*.070+low*.014+listening*.017)+Math.sin(a*17-t*.9)*high*.009;
}

export class CanvasOrb {
  constructor(canvas) {
    this.canvas=canvas;this.state='connecting';this.dim=1;
    this.audio={energy:0,low:0,high:0,listening:0};this.levels={...this.audio};
    this.style={...STATES.connecting,tint:[...STATES.connecting.tint]};
    this.reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.resolution=1;this.time=5;this.last=0;this.frameCount=0;this.slowFrames=0;
    this.disposed=false;this.fallback=false;
    this.core=geodesic();this.projected=new Float32Array(this.core.vertices.length*3);
    this.seeds=new Float32Array((8192+144)*4);
    for(let i=0;i<this.seeds.length/4;i++){
      const ambient=i>=8192;
      this.seeds.set([(i*2.39996323)%TAU,ambient ? (i*.754877666)%1 : ((i*.754877666)%1)*TAU,
        ((i*.569840296)%1)*TAU,ambient ? 1 : 0],i*4);
    }
    this.onContextLost=event=>{event.preventDefault();if(!this.disposed)this.useFallback();};
    this.onResize=()=>this.fit();
    this.onVisibility=()=>{
      this.last=0;if(!document.hidden)this.fit();cancelAnimationFrame(this.frame);
      if(!document.hidden&&!this.disposed)this.frame=requestAnimationFrame(this.animate);
    };
    this.animate=this.animate.bind(this);
    this.useFallback();
    this.resize=new ResizeObserver(()=>this.fit());this.resize.observe(this.canvas);this.fit();
    document.addEventListener('visibilitychange',this.onVisibility);window.addEventListener('resize',this.onResize);
    if(!document.hidden)this.frame=requestAnimationFrame(this.animate);
  }

  useFallback(){
    this.fallback=true;
    this.canvas.removeEventListener('webglcontextlost',this.onContextLost);
    const old=this.canvas,replacement=old.cloneNode(false);old.replaceWith(replacement);this.canvas=replacement;
    this.ctx=replacement.getContext('2d');this.canvas.dataset.renderer='canvas';
    if(this.resize){this.resize.unobserve(old);this.resize.observe(replacement);this.fit();}
  }
  fit(){
    if(this.disposed)return;
    const width=Math.max(1,this.canvas.clientWidth),height=Math.max(1,this.canvas.clientHeight);
    const ratio=Math.min(devicePixelRatio||1,1.5,1280/width,900/height)*this.resolution;
    this.canvas.width=Math.max(1,Math.round(width*ratio));this.canvas.height=Math.max(1,Math.round(height*ratio));
    this.pixelRatio=ratio;

  }
  setState(state){if(STATES[state])this.state=state;}
  setAudio({energy=0,low=0,high=0,listening=0}={}){
    this.audio={energy:clamp(energy),low:clamp(low),high:clamp(high),listening:clamp(listening)};
  }
  animate(now){
    if(this.disposed||document.hidden)return;
    this.frame=requestAnimationFrame(this.animate);
    const elapsed=this.last ? now-this.last : 16.67,interval=this.reduced ? 48 : this.resolution<.8 ? 30 : 15;
    if(elapsed<interval)return;
    this.last=now;const dt=Math.min(.08,elapsed/1000);
    if(elapsed>44)this.slowFrames++;
    if(++this.frameCount>=120){
      if(!this.reduced&&this.slowFrames>35&&this.resolution>.55){this.resolution=Math.max(.55,this.resolution*.8);this.fit();}
      this.frameCount=this.slowFrames=0;
    }
    const transition=1-Math.exp(-Math.min(1,elapsed/1000)/.3),target=STATES[this.state];
    for(const key of ['brightness','violet','busy'])this.style[key]=settle(this.style[key],target[key],transition);
    this.style.tint=this.style.tint.map((value,i)=>settle(value,target.tint[i],transition));
    for(const key of Object.keys(this.levels)){
      const value=this.audio[key],smoothing=1-Math.exp(-dt/(value>this.levels[key] ? .055 : .36));
      this.levels[key]=mix(this.levels[key],value,smoothing);
    }
    if(!this.reduced)this.time+=dt*(this.state==='error' ? .16 : 1+this.levels.energy*.45);
    const time=this.reduced ? 5 : this.time;
    const layout=orbLayout(this.canvas.clientWidth,this.canvas.clientHeight);
    this.origin={x:layout.x*this.pixelRatio,y:layout.y*this.pixelRatio};
    this.radius=(document.body.classList.contains('has-workspace')?layout.radius*this.pixelRatio:Math.min(this.canvas.width*.43,this.canvas.height*.395))*(1+.018*Math.sin(time*.98)+.005*Math.sin(time*.41));
    // Keep particle brightness/density consistent on the small display.
    this.ringCount=Math.round(Math.max(900,Math.min(8192,8192*(this.radius/(355*Math.max(.8,this.pixelRatio)))**2)));
    this.matrix=rotation(time);
    this.drawFallback(time);
    if(!this.canvas.dataset.rendered)this.canvas.dataset.rendered='true';
  }
  drawFallback(time){
    const ctx=this.ctx;if(!ctx)return;
    const w=this.canvas.width,h=this.canvas.height,R=this.radius;
    const e=this.reduced ? 0 : this.levels.energy,l=this.reduced ? 0 : this.levels.low;
    const hi=this.reduced ? 0 : this.levels.high,mic=this.reduced ? 0 : this.levels.listening;
    const base=this.style.tint.map(v=>Math.round(v*255));
    const hue=base.map((v,i)=>Math.round(mix(v,[143,71,255][i],this.style.violet*.6)));
    const brightness=this.style.brightness*this.dim*(this.reduced ? 1+this.levels.energy*.15 : 1);
    ctx.clearRect(0,0,w,h);ctx.save();ctx.translate(this.origin?.x??w/2,this.origin?.y??h/2);ctx.scale(R,R);ctx.globalCompositeOperation='lighter';
    const atmosphere=ctx.createRadialGradient(0,0,.15,0,0,1.16);
    atmosphere.addColorStop(0,`rgba(${base},.045)`);atmosphere.addColorStop(.26,`rgba(${base},.025)`);
    atmosphere.addColorStop(.7,`rgba(${hue},.003)`);atmosphere.addColorStop(.88,`rgba(${hue},.025)`);atmosphere.addColorStop(1,`rgba(${base},0)`);
    ctx.globalAlpha=brightness;ctx.fillStyle=atmosphere;ctx.fillRect(-1.2,-1.2,2.4,2.4);
    // Broad bloom underneath the narrow filaments.
    for(let band=0;band<5;band++){
      ctx.beginPath();
      for(let i=0;i<=240;i++){
        const a=i/240*TAU,r=.955+surface(a,time,e,l,hi,mic)+(band-2)*.012;
        i ? ctx.lineTo(Math.cos(a)*r,-Math.sin(a)*r) : ctx.moveTo(Math.cos(a)*r,-Math.sin(a)*r);
      }
      ctx.strokeStyle=`rgba(${hue},.045)`;ctx.lineWidth=.025;ctx.stroke();
      ctx.strokeStyle=`rgba(${hue},.22)`;ctx.lineWidth=.7/R;ctx.stroke();
    }
    for(const radius of [.69,.81]){
      ctx.beginPath();ctx.arc(0,0,radius,0,TAU);ctx.strokeStyle=`rgba(${hue},.12)`;ctx.lineWidth=.7/R;ctx.stroke();
    }
    for(let i=0;i<2;i++){
      const spread=(time*.115+i*.5)%1;
      ctx.beginPath();ctx.arc(0,0,.41+spread*.49,0,TAU);
      ctx.strokeStyle=`rgba(${base},${Math.sin(spread*Math.PI)*(.08+e*.09)})`;ctx.lineWidth=.7/R;ctx.stroke();
    }
    // Same low-discrepancy particle layout as WebGL, with a lower count for the Pi.
    const step=Math.max(1,Math.ceil(this.ringCount/(this.resolution<.8 ? 1000 : 1800)));
    for(let i=0;i<this.seeds.length/4;i+=step){
      if(i>=this.ringCount && i<8192)continue;
      const k=i*4,ambient=this.seeds[k+3]>.5,phase=this.seeds[k+2];
      let a=this.seeds[k]+time*.035,tube=this.seeds[k+1]+time*.11;
      let radius=.955+surface(a,time,e,l,hi,mic)+Math.sin(tube)*(.029+e*.010);
      let depth=Math.cos(tube),life=.65+.35*Math.sin(phase+time*.23);
      if(ambient){radius=.40+this.seeds[k+1]*.47;a=this.seeds[k]-time*(.012+this.seeds[k+1]*.018);depth=Math.sin(phase+time*.12);life=(.5+.5*Math.sin(phase+time*.20))**2*.34;}
      ctx.fillStyle=`rgba(${hue},${life*(.34+(depth+1)*.20+e*.16)})`;
      const size=(1.2+phase*.14+(depth+1)*.45)*Math.max(.8,this.pixelRatio)*(1+e*.25)/R;
      ctx.fillRect(Math.cos(a)*radius-size*.3,-Math.sin(a)*radius-size*.3,size*.6,size*.6);
    }
    ctx.globalAlpha=brightness;
    const coreSize=.34+e*.012,m=this.matrix;
    for(let i=0;i<this.core.vertices.length;i++){
      const [x,y,z]=this.core.vertices[i],rx=m[0]*x+m[3]*y+m[6]*z,ry=m[1]*x+m[4]*y+m[7]*z,rz=m[2]*x+m[5]*y+m[8]*z;
      this.projected.set([rx*coreSize*4.5/(4.5-rz),-ry*coreSize*4.5/(4.5-rz),(rz+1)*.5],i*3);
    }
    const coreGlow=ctx.createRadialGradient(-.06,-.07,.03,0,0,.43);
    coreGlow.addColorStop(0,`rgba(${base},.035)`);coreGlow.addColorStop(.72,`rgba(${base},.01)`);coreGlow.addColorStop(.82,`rgba(${base},.04)`);coreGlow.addColorStop(1,`rgba(${base},0)`);
    ctx.fillStyle=coreGlow;ctx.fillRect(-.44,-.44,.88,.88);
    const points=this.projected;
    for(let band=0;band<5;band++){
      ctx.beginPath();
      for(const [a,b] of this.core.edges){
        const depth=(points[a*3+2]+points[b*3+2])*.5;
        if(Math.min(4,Math.floor(depth*5))!==band)continue;
        ctx.moveTo(points[a*3],points[a*3+1]);ctx.lineTo(points[b*3],points[b*3+1]);
      }
      ctx.strokeStyle=`rgba(${hue},${.06+((band+.5)/5)**1.6*.48})`;ctx.lineWidth=.8/R;ctx.stroke();
    }
    for(let i=0;i<points.length;i+=3){
      const size=(.6+points[i+2]*.8)*Math.max(.8,this.pixelRatio)/R;
      ctx.beginPath();ctx.arc(points[i],points[i+1],size,0,TAU);
      ctx.fillStyle=`rgba(${hue},${.1+points[i+2]*.5})`;ctx.fill();
    }
    ctx.restore();
  }
  dispose(){
    if(this.disposed)return;
    this.disposed=true;cancelAnimationFrame(this.frame);this.resize?.disconnect();
    document.removeEventListener('visibilitychange',this.onVisibility);window.removeEventListener('resize',this.onResize);
    this.canvas.removeEventListener('webglcontextlost',this.onContextLost);
    this.ctx?.clearRect(0,0,this.canvas.width,this.canvas.height);
  }
}
