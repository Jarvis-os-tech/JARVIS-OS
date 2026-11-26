import {CaptureResampler} from './pcm.js';

class CaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super(); this.resampler = new CaptureResampler(sampleRate);
    this.enabled = true;
    this.port.onmessage = ({data}) => {
      this.enabled = data.enabled;
      this.resampler = new CaptureResampler(sampleRate); // Never retain pre-mute audio.
    };
  }
  process(inputs) {
    const samples = inputs[0]?.[0];
    if (!samples || !this.enabled) return true;
    this.resampler.push(samples, frame => {
      let power = 0; for(const x of frame)power += (x/32768)**2;
      this.port.postMessage({audio:frame.buffer,level:Math.sqrt(power/frame.length),capturedAt:currentTime},[frame.buffer]);
    });
    return true;
  }
}
registerProcessor('jarvis-capture',CaptureProcessor);
