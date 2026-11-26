export class AudioEngine {
  constructor(onAudio, onPlayback) {
    this.onAudio=onAudio;this.onPlayback=onPlayback;this.disposed=false;
    this.micLevel=0;this.muted=false;this.volume=.75;this.epoch=0;this.turn=0;this.blockedThrough=0;
    this.pauseMicrophoneWhileSpeaking=false;this.outputPending=false;this.captureResumeAt=0;
  }
  check() {if(this.disposed)throw new DOMException('Connection canceled.','AbortError');}
  async acquire(constraints) {
    this.check();
    const stream=await navigator.mediaDevices.getUserMedia({audio:constraints});
    if(this.disposed){stream.getTracks().forEach(t=>t.stop());this.check();}
    stream.getAudioTracks().forEach(t=>{t.enabled=!this.muted;});
    this.stream=stream;return stream;
  }
  async start({inputDevice='',outputDevice='',volume=.75,micGain=1,micMuted=false,echoCancellation=true,pauseMicrophoneWhileSpeaking=false}={}) {
    this.muted=micMuted===true;
    this.setPauseMicrophoneWhileSpeaking(pauseMicrophoneWhileSpeaking);
    if(!navigator.mediaDevices?.getUserMedia)throw new Error('Open Jarvis on localhost or HTTPS to use the microphone.');
    this.context=new AudioContext({latencyHint:'interactive'});
    // A regular browser may require a gesture; never leave startup hanging.
    if(this.context.state==='suspended' && !navigator.userActivation?.isActive){
      throw new DOMException('Activate the vocalizer to enable browser audio.', 'AudioGestureRequired');
    }
    await this.context.resume();this.check();
    const basic={echoCancellation,noiseSuppression:true,autoGainControl:false,channelCount:1};
    await this.acquire({...basic,...(inputDevice?{deviceId:{exact:inputDevice}}:{})});
    const devices=await navigator.mediaDevices.enumerateDevices();this.check();
    // Ignore aliases: selecting "Default - ADA ..." does not pin the reference
    // speaker. AEC needs the concrete microphone AND its matching playback sink.
    const concrete=d=>d.deviceId && !['default','communications'].includes(d.deviceId);
    const isAecInput=d=>/ada_aec_source|ADA Echo-Cancelled Microphone/i.test(d?.label || '');
    const isAecOutput=d=>/ada_aec_sink|ADA Echo-Cancelled Speaker/i.test(d?.label || '');
    const aecInput=devices.find(d=>d.kind==='audioinput' && concrete(d) && isAecInput(d));
    const aecOutput=devices.find(d=>d.kind==='audiooutput' && concrete(d) && isAecOutput(d));
    const selectedInput=devices.find(d=>d.kind==='audioinput' && d.deviceId===inputDevice);
    const selectedOutput=devices.find(d=>d.kind==='audiooutput' && d.deviceId===outputDevice);
    const explicitPair=isAecInput(selectedInput) || isAecOutput(selectedOutput);
    const usePair=echoCancellation && (!inputDevice || inputDevice===aecInput?.deviceId) &&
      (!outputDevice || outputDevice===aecOutput?.deviceId) && aecInput && aecOutput && this.context.setSinkId;
    if(explicitPair && !usePair)throw new DOMException('Use the echo-cancelled microphone and speaker together, or choose physical audio devices.', 'NotSupportedError');
    this.echoCancellationProvider=echoCancellation?'browser':'off';
    if(usePair){
      try{
        await this.context.setSinkId(aecOutput.deviceId);this.check();
        this.stream.getTracks().forEach(t=>t.stop());
        await this.acquire({...basic,echoCancellation:false,deviceId:{exact:aecInput.deviceId}});
        outputDevice=aecOutput.deviceId;
        this.echoCancellationProvider='system';
        this.route='Echo-canceled microphone & speakers';
      }catch(error){
        this.check();
        if(explicitPair)throw error;
        await this.context.setSinkId('');this.check();
        this.routeWarning=`System echo cancellation unavailable (${error.name}); using browser processing.`;
      }
    }
    if(this.echoCancellationProvider!=='system'){
      const physicalInputs=devices.filter(d=>d.kind==='audioinput' && concrete(d) && !isAecInput(d) && !/monitor/i.test(d.label));
      // A default processed microphone can survive a failed setSinkId(), or be
      // selected alongside explicit HDMI output. Always leave it on fallback.
      const currentTrack=this.stream.getAudioTracks()[0];
      const currentDevice=devices.find(d=>d.kind==='audioinput' && d.deviceId===currentTrack?.getSettings().deviceId);
      const needsPhysical=!echoCancellation || !this.stream.active || isAecInput(currentTrack) || isAecInput(currentDevice) || (!inputDevice && aecInput);
      if(needsPhysical){
        const microphone=inputDevice ? physicalInputs.find(d=>d.deviceId===inputDevice) :
          physicalInputs.find(d=>/PCM2902|USB PnP Sound Device/i.test(d.label)) ||
          (physicalInputs.length===1?physicalInputs[0]:null);
        if(!microphone)throw new DOMException('Choose a physical microphone in input_device for this audio route.', 'NotSupportedError');
        this.stream.getTracks().forEach(t=>t.stop());
        await this.acquire({...basic,deviceId:{exact:microphone.deviceId}});
      }
      if(!outputDevice && this.context.setSinkId){
        const speakers=devices.filter(d=>d.kind==='audiooutput' && concrete(d) && !isAecOutput(d));
        const output=speakers.find(d=>/HDMI/i.test(d.label)) || (speakers.length===1?speakers[0]:null);
        if(output)outputDevice=output.deviceId;
      }
      if(outputDevice){
        if(!this.context.setSinkId)throw new DOMException('Configured speaker selection is unsupported by this browser.', 'NotSupportedError');
        await this.context.setSinkId(outputDevice);this.check();
      }
      this.route=echoCancellation?'Browser echo cancellation':'Direct microphone & speakers (echo cancellation off)';
      if(echoCancellation){
        const applied=this.stream.getAudioTracks()[0]?.getSettings().echoCancellation;
        if(applied===false)throw new DOMException('The selected microphone has browser echo cancellation disabled.', 'NotSupportedError');
        if(applied===undefined){
          this.route='Browser echo cancellation requested (unverified)';
          this.routeWarning='This browser does not report whether echo cancellation is enabled.';
        }
      }
    }
    this.outputLabel=devices.find(d=>d.kind==='audiooutput' && d.deviceId===(outputDevice || 'default'))?.label || 'System default';
    const baseAudio = (typeof import.meta !== 'undefined' && import.meta.url)
      ? import.meta.url.replace(/\/[^/]+$/, '')
      : '/static/audio';
    await Promise.all([
      this.context.audioWorklet.addModule(`${baseAudio}/capture-worklet.js`).catch(() => this.context.audioWorklet.addModule('/static/audio/capture-worklet.js')),
      this.context.audioWorklet.addModule(`${baseAudio}/playback-worklet.js`).catch(() => this.context.audioWorklet.addModule('/static/audio/playback-worklet.js'))
    ]);this.check();
    this.source=this.context.createMediaStreamSource(this.stream);
    this.filter=this.context.createBiquadFilter();this.filter.type='lowpass';this.filter.frequency.value=7200;this.filter.Q.value=.707;
    this.capture=new AudioWorkletNode(this.context,'jarvis-capture',{numberOfInputs:1,numberOfOutputs:1,outputChannelCount:[1]});
    this.mute(this.muted);
    this.micGain=this.context.createGain();this.setMicGain(micGain);
    this.silent=this.context.createGain();this.silent.gain.value=0;
    this.source.connect(this.filter).connect(this.micGain).connect(this.capture).connect(this.silent).connect(this.context.destination);
    this.capture.port.onmessage=({data})=>{
      if(this.disposed || this.muted)return;
      // Keep capture/AEC running, but send silence while output is queued and
      // through the speaker/room tail. Capture time also rejects delayed frames
      // delivered after the main thread was busy, instead of leaking old echo.
      const paused=this.microphonePaused(data.capturedAt);
      if(paused)new Int16Array(data.audio).fill(0);
      this.micLevel=paused?0:data.level;this.onAudio(data.audio);
    };
    this.player=new AudioWorkletNode(this.context,'jarvis-playback',{numberOfInputs:0,numberOfOutputs:1,outputChannelCount:[1]});
    this.player.port.onmessage=({data})=>{
      if(this.disposed || data.epoch!==this.epoch || data.turn!==this.turn)return;
      if(['playback_drained','playback_stopped','overflow'].includes(data.type))this.releaseCaptureHold();
      this.onPlayback(data);
    };
    this.gain=this.context.createGain();
    this.analyser=this.context.createAnalyser();this.analyser.fftSize=1024;this.analyser.smoothingTimeConstant=.5;
    this.waveform=new Float32Array(1024);this.spectrum=new Uint8Array(512);
    this.visualBands=new Float32Array(24);
    // Speech bands in Hz keep the visual response consistent at any device rate.
    this.visualEdges=Array.from({length:25},(_,i)=>Math.max(1,Math.min(511,
      Math.round(90*Math.pow(8000/90,i/24)*this.analyser.fftSize/this.context.sampleRate))));
    this.player.connect(this.gain).connect(this.analyser).connect(this.context.destination);
    this.setVolume(volume);
    this.stream.getAudioTracks()[0].addEventListener('ended',()=>{
      if(!this.disposed)this.onPlayback({type:'device_lost'});
    });
    this.context.addEventListener('statechange',()=>{
      if(!this.disposed && this.context.state==='suspended')this.onPlayback({type:'audio_suspended'});
    });
    this.check();
    if(this.stream.getAudioTracks()[0]?.readyState!=='live')throw new DOMException('Microphone disconnected during startup.', 'NotFoundError');
    if(this.context.state!=='running')throw new DOMException('Activate the vocalizer to resume browser audio.', 'AudioGestureRequired');
    return this.route;
  }
  reset(epoch){
    if(this.outputPending)this.releaseCaptureHold();
    this.epoch=epoch;this.turn=this.blockedThrough=0;
    this.player?.port.postMessage({type:'reset',epoch});
  }
  begin(epoch,turn){
    if(epoch!==this.epoch || turn<=this.blockedThrough || turn<this.turn)return;
    this.turn=turn;this.player?.port.postMessage({type:'begin',epoch,turn});
  }
  enqueue(buffer){
    if(buffer.byteLength<14 || (buffer.byteLength-12)%2)return;
    const view=new DataView(buffer),epoch=view.getUint32(0,true),turn=view.getUint32(4,true),rate=view.getUint32(8,true);
    if(epoch!==this.epoch || turn<=this.blockedThrough || turn<this.turn || rate!==24000)return;
    this.turn=turn;const audio=buffer.slice(12);
    if(audio.byteLength){this.outputPending=true;if(this.pauseMicrophoneWhileSpeaking)this.micLevel=0;}
    this.player?.port.postMessage({type:'audio',epoch,turn,audio},[audio]);
  }
  finish(epoch,turn){this.player?.port.postMessage({type:'finish',epoch,turn});}
  interrupt(turn=this.turn){
    this.blockedThrough=Math.max(this.blockedThrough,turn);
    this.player?.port.postMessage({type:'cancel',turn});
  }
  mute(muted){
    this.muted=!!muted;
    this.capture?.port.postMessage({enabled:!this.muted});
    this.stream?.getAudioTracks().forEach(t=>{t.enabled=!this.muted;});this.micLevel=0;
  }
  setVolume(value){this.volume=value;if(this.gain)this.gain.gain.setTargetAtTime(value,this.context.currentTime,.02);}
  setMicGain(value){
    const gain=Number.isFinite(value)?Math.max(0,Math.min(2,value)):1;
    if(this.micGain)this.micGain.gain.setTargetAtTime(gain,this.context.currentTime,.02);
  }
  setPauseMicrophoneWhileSpeaking(value){this.pauseMicrophoneWhileSpeaking=value===true;}
  microphonePaused(capturedAt=this.context?.currentTime || 0){
    return this.pauseMicrophoneWhileSpeaking && (this.outputPending || capturedAt<this.captureResumeAt);
  }
  releaseCaptureHold(){
    if(!this.outputPending)return;
    this.outputPending=false;
    this.captureResumeAt=(this.context?.currentTime || 0)+(this.context?.outputLatency || 0)+.6;
  }
  diagnostics(){
    const track=this.stream?.getAudioTracks()[0],settings=track?.getSettings() || {};
    return {route:this.route,echo_cancellation_provider:this.echoCancellationProvider,
      browser_echo_cancellation:settings.echoCancellation ?? null,
      pause_microphone_while_speaking:this.pauseMicrophoneWhileSpeaking,
      microphone_paused_for_playback:this.microphonePaused(),
      input_device:track?.label,output_device:this.outputLabel,
      sample_rate:this.context?.sampleRate,output_latency_ms:Math.round((this.context?.outputLatency || 0)*1000),
      ...(this.routeWarning?{route_warning:this.routeWarning}:{})};
  }
  levels(){
    if(!this.analyser || this.disposed)return {energy:0,low:0,high:0};
    this.analyser.getFloatTimeDomainData(this.waveform);this.analyser.getByteFrequencyData(this.spectrum);
    let sum=0;for(const s of this.waveform)sum+=s*s;
    const energy=Math.min(1,Math.sqrt(sum/this.waveform.length)*5.5);
    const band=(a,b)=>{let v=0,n=0;for(let i=a;i<b;i++){v+=this.spectrum[i]/255;n++;}return v/n;};
    for(let i=0;i<24;i++){
      const start=this.visualEdges[i],end=Math.max(start+1,this.visualEdges[i+1]);
      let peak=0;for(let j=start;j<end;j++)peak=Math.max(peak,this.spectrum[j]/255);
      this.visualBands[i]=peak;
    }
    return {energy,low:band(1,12),high:band(20,90),spectrum:this.visualBands};
  }
  async close(){
    this.disposed=true;
    this.stream?.getTracks().forEach(t=>t.stop());
    this.capture?.disconnect();this.player?.disconnect();
    this.source?.disconnect();this.filter?.disconnect();this.silent?.disconnect();
    this.micGain?.disconnect();
    this.gain?.disconnect();this.analyser?.disconnect();
    if(this.capture)this.capture.port.onmessage=null;
    if(this.player)this.player.port.onmessage=null;
    if(this.context && this.context.state!=='closed')await this.context.close().catch(()=>{});
  }
}
