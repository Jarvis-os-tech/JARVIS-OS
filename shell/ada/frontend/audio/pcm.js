// Pure streaming primitives, shared with the browser audio regression tests.
export class CaptureResampler {
  constructor(sourceRate, targetRate = 16000, frameSize = 320) {
    this.ratio = sourceRate / targetRate;
    this.remaining = this.ratio;
    this.sum = 0; this.frame = new Int16Array(frameSize); this.offset = 0;
  }
  push(samples, emit) {
    for (let i = 0; i < samples.length; i++) {
      let available = 1;
      while (available > 1e-9) {
        const weight = Math.min(available, this.remaining);
        this.sum += samples[i] * weight; available -= weight; this.remaining -= weight;
        if (this.remaining < 1e-9) {
          const sample = Math.max(-1, Math.min(1, this.sum / this.ratio));
          this.frame[this.offset++] = Math.round(sample * (sample < 0 ? 32768 : 32767));
          this.sum = 0; this.remaining = this.ratio;
          if (this.offset === this.frame.length) {
            // postMessage may detach the emitted buffer synchronously. Allocate
            // its replacement first so detachment cannot turn future frames into length 0.
            const completed = this.frame;
            this.frame = new Int16Array(completed.length); this.offset = 0;
            emit(completed);
          }
        }
      }
    }
  }
}

export class PlaybackBuffer {
  constructor(outputRate, emit = () => {}, capacity = 24000 * 30) {
    this.outputRate = outputRate; this.emit = emit;
    this.buffer = new Float32Array(capacity); this.epoch = 0;
    this.turn = 0; this.blockedThrough = 0; this.clear();
  }
  clear() {
    this.read = 0; this.write = 0; this.count = 0; this.phase = 0;
    this.playing = false; this.finished = false; this.drained = false;
  }
  reset(epoch) {
    this.epoch = epoch; this.turn = 0; this.blockedThrough = 0; this.clear();
  }
  begin(epoch, turn) {
    if (epoch !== this.epoch || turn <= this.blockedThrough || turn < this.turn) return false;
    if (turn !== this.turn) {this.clear(); this.turn = turn;}
    return true;
  }
  push(epoch, turn, samples) {
    if (!this.begin(epoch, turn)) return false;
    if (this.count + samples.length > this.buffer.length) {
      this.cancel(turn); this.emit({type: 'overflow'}); return false;
    }
    for (let i=0;i<samples.length;i++) {
      this.buffer[this.write] = samples[i] / 32768;
      this.write = (this.write + 1) % this.buffer.length;
    }
    this.count += samples.length; return true;
  }
  cancel(turn) {
    this.blockedThrough = Math.max(this.blockedThrough, turn);
    if (this.turn <= turn) {this.clear(); this.emit({type:'playback_stopped',turn:this.turn});}
  }
  finish(epoch, turn) {
    if (epoch === this.epoch && turn === this.turn && turn > this.blockedThrough) this.finished = true;
  }
  render(out) {
    out.fill(0);
    if (!this.playing && this.count && (this.count >= 1440 || this.finished)) {
      this.playing = true; this.emit({type:'playback_started',turn:this.turn});
    }
    if (this.playing) {
      for (let n = 0; n < out.length && this.count; n++) {
        const first = this.buffer[this.read];
        const second = this.count > 1 ? this.buffer[(this.read + 1) % this.buffer.length] : first;
        out[n] = first + (second - first) * this.phase;
        this.phase += 24000 / this.outputRate;
        while (this.phase >= 1 && this.count) {
          this.read = (this.read + 1) % this.buffer.length; this.count--; this.phase--;
        }
      }
      if (!this.count) {
        this.playing = false;
        if (!this.finished) this.emit({type:'buffering',turn:this.turn});
      }
    }
    if (!this.count && this.finished && !this.drained) {
      this.drained = true; this.emit({type:'playback_drained',turn:this.turn});
    }
  }
}
