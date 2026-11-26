// Camera-independent gesture state machine. All timing is monotonic milliseconds.
const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
export class GestureController {
  constructor(emit,options={}) {this.emit=emit;this.configure(options);this.reset();}
  configure(options={}) {
    this.options={mirror:true,sensitivity:1,bounds:{left:.16,right:.84,top:.12,bottom:.88},...options};
  }
  reset() {
    if(this.press)this.emit({type:'cancel'});
    this.press=null;this.position=null;this.track=null;this.last=null;this.candidate='';
    this.since=0;this.unknownSince=null;this.state='unarmed';this.emit({type:'state',state:this.state});
  }
  update(sample,now,width,height) {
    if(!sample.tracked||sample.confidence<.75||![sample.x,sample.y,sample.confidence,now].every(Number.isFinite)) {
      this.reset();return;
    }
    if(this.track!==sample.track_id||(this.last!==null&&now-this.last>250))this.reset();
    this.track=sample.track_id;
    const dt=this.last===null?100:clamp(now-this.last,1,100);this.last=now;
    const o=this.options,b=o.bounds;
    const nx=o.mirror?1-sample.x:sample.x;
    const x=clamp(((nx-b.left)/(b.right-b.left)-.5)*o.sensitivity+.5,0,1)*(width-2)+1;
    const y=clamp(((sample.y-b.top)/(b.bottom-b.top)-.5)*o.sensitivity+.5,0,1)*(height-2)+1;
    if(!this.position)this.position={x,y};
    else {
      const distance=Math.hypot(x-this.position.x,y-this.position.y);
      const alpha=1-Math.exp(-dt/(distance>35?25:55));
      if(distance>.6){this.position.x+=alpha*(x-this.position.x);this.position.y+=alpha*(y-this.position.y);}
    }
    const point={...this.position};
    this.emit({type:'move',...point});
    const pose=sample.pose;
    if(!['open','fist'].includes(pose)) {
      this.candidate='';this.unknownSince??=now;
      if(now-this.unknownSince>160){this.reset();}
      return;
    }
    this.unknownSince=null;
    if(this.candidate!==pose){this.candidate=pose;this.since=now;}
    const stable=now-this.since>=110;
    if(this.state==='unarmed') {
      if(pose==='open'&&stable)this.change('hover');
      return;
    }
    if(this.state==='hover'&&pose==='fist'&&stable) {
      this.press={...point,last:point,maxDistance:0};
      this.change('pressed');this.emit({type:'press',...point});
      return;
    }
    if(!this.press)return;
    if(pose==='fist') {
      const p=this.press;
      p.maxDistance=Math.max(p.maxDistance,Math.hypot(point.x-p.x,point.y-p.y));
      if(p.maxDistance>16&&this.state==='pressed') {
        this.change('dragging');this.emit({type:'dragstart',x:p.x,y:p.y});
      }
      if(this.state==='dragging')this.emit({type:'drag',dx:point.x-p.last.x,dy:point.y-p.last.y,...point});
      p.last=point;
    } else if(pose==='open'&&stable) {
      const p=this.press;
      this.emit({type:this.state==='dragging'?'release':'click',x:p.x,y:p.y});
      this.press=null;this.change('hover');
    }
  }
  change(state){this.state=state;this.emit({type:'state',state});}
}
