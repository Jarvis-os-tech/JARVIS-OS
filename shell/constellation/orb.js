import {createVoiceCore} from './voice-core.js?v=9';
import {CanvasOrb} from './orb-fallback.js?v=9';

const STATES = {
  connecting: {color:'#448cba', brightness:.78, speed:.8},
  idle: {color:'#4fd9cf', brightness:1, speed:1},
  listening: {color:'#55e6c4', brightness:1.04, speed:1.08},
  thinking: {color:'#7d9ce5', brightness:.94, speed:1.2},
  speaking: {color:'#91acff', brightness:1.12, speed:1.25},
  reconnecting: {color:'#4f8eac', brightness:.7, speed:.65},
  error: {color:'#d99d58', brightness:.75, speed:.25},
  exiting: {color:'#4fd9cf', brightness:0, speed:1},
};
const clamp = value => Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : 0;
const approach = (a, b, dt, seconds) => {
  const next = a + (b - a) * (1 - Math.exp(-dt / seconds));
  return Math.abs(next - b) < .0001 ? b : next;
};

export class JarvisOrb {
  constructor(canvas) {
    this.canvas = canvas;
    this.state = 'connecting';
    this.reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.dim = 1;
    this.audio = {energy:0, listening:0};
    this.spectrum = new Float32Array(24);
    this.energy = this.listening = this.age = this.time = this.last = 0;
    this.brightness = STATES.connecting.brightness;
    this.resolution = 1;
    this.frameCount = this.slowFrames = 0;
    this.stableFrames = 0;
    this.lastQualityChange = 0;
    this.fitKey = '';
    this.dirty = true;
    this.lastReducedState = '';
    this.animate = this.animate.bind(this);
    this.onContextLost = event => { event.preventDefault(); this.useFallback(); };
    this.onVisibility = () => {
      cancelAnimationFrame(this.frame); this.last = 0;
      if (!document.hidden && !this.disposed && !this.fallback) {
        this.fit(); this.frame = requestAnimationFrame(this.animate);
      }
    };
    try {
      this.core = createVoiceCore(canvas);
      this.canvas.dataset.renderer = 'webgl';
      this.canvas.dataset.visual = 'voice-core';
      this.canvas.addEventListener('webglcontextlost', this.onContextLost);
      this.resize = new ResizeObserver(() => this.fit());
      this.resize.observe(canvas);
      document.addEventListener('visibilitychange', this.onVisibility);
      this.fit();
      if (!document.hidden) this.frame = requestAnimationFrame(this.animate);
    } catch { this.useFallback(); }
  }
  useFallback() {
    if (this.disposed || this.fallback) return;
    cancelAnimationFrame(this.frame);
    this.resize?.disconnect();
    document.removeEventListener('visibilitychange', this.onVisibility);
    this.canvas.removeEventListener('webglcontextlost', this.onContextLost);
    this.core?.dispose(); this.core = null;
    // A canvas that had a GL context cannot subsequently acquire a 2D context.
    this.backup = new CanvasOrb(this.canvas);
    this.canvas = this.backup.canvas;
    this.fallback = true;
    this.backup.reduced = this.reduced;
    this.backup.dim = this.dim;
    this.backup.setState(this.state);
    this.backup.setAudio(this.audio);
  }
  fit() {
    if (this.disposed || this.fallback || !this.core) return;
    const width = Math.max(1, this.canvas.clientWidth), height = Math.max(1, this.canvas.clientHeight);
    const ratio = Math.min(devicePixelRatio || 1, 1.5, 1280 / width, 800 / height) * this.resolution;
    const key = [width, height, ratio, document.body.classList.contains('has-workspace')].join(':');
    if (key === this.fitKey) return;
    this.fitKey = key;
    this.dirty = true;
    this.core.resize(width, height, ratio, this.resolution * this.resolution);
  }
  setState(state) {
    if (!STATES[state]) return;
    this.state = state;
    this.backup?.setState(state);
  }
  setAudio(audio = {}) {
    this.audio = audio;
    if (this.backup) {
      this.backup.reduced = this.reduced;
      this.backup.dim = this.dim;
      this.backup.setAudio(audio);
    }
  }
  animate(now) {
    if (this.disposed || this.fallback || document.hidden) return;
    this.frame = requestAnimationFrame(this.animate);
    const reducedState = `${this.state}:${this.dim}`;
    // Reduced motion has a fixed pose/color. Redraw only for actual changes.
    if (this.reduced && !this.dirty && reducedState === this.lastReducedState) return;
    // 30fps leaves capacity for the Pi's speech capture and playback worklets.
    // Keep the orb alive behind a document, leaving more time for scrolling it.
    const reading = document.getElementById('workspaceDialog')?.open;
    const interval = document.body.classList.contains('cad-open') ? 120 : reading ? 60 : this.reduced ? 48 : 30;
    const elapsed = this.last ? now - this.last : interval;
    if (elapsed < interval) return;
    this.last = now;
    const dt = Math.min(.5, elapsed / 1000), state = STATES[this.state];
    if (!this.reduced) {
      // A sustained 18–20fps used to miss the old 80ms threshold entirely.
      // Do not mistake the deliberate slower document cadence for overload.
      if (!reading && this.age > 2.5 && elapsed > 45) this.slowFrames++;
      this.stableFrames = !reading && elapsed < 38 ? this.stableFrames + 1 : 0;
      if (++this.frameCount >= 30) {
        if (this.slowFrames > 6 && this.resolution > .65) {
          this.resolution = Math.max(.65, this.resolution * .85); this.fit();
          this.lastQualityChange = now; this.stableFrames = 0;
        }
        this.frameCount = this.slowFrames = 0;
      }
      // Recover detail after sustained headroom, rather than keeping a quality
      // reduction forever after a temporary load spike. Hysteresis avoids churn.
      if (this.resolution < 1 && this.stableFrames >= 900 && now - this.lastQualityChange > 60000) {
        this.resolution = Math.min(1, this.resolution / .85); this.fit();
        this.lastQualityChange = now; this.stableFrames = 0;
      }
      this.age += dt;
      this.time += dt * (state.speed + this.energy * .2);
    }
    const target = clamp(this.audio.energy);
    this.energy = approach(this.energy, target, dt, target > this.energy ? .045 : .24);
    this.listening = approach(this.listening, clamp(this.audio.listening), dt, .16);
    this.brightness = this.reduced ? state.brightness * this.dim : approach(this.brightness, state.brightness * this.dim, dt, .25);
    for (let i = 0; i < 24; i++) {
      const value = clamp(this.audio.spectrum?.[i]);
      this.spectrum[i] = approach(this.spectrum[i], value, dt, value > this.spectrum[i] ? .045 : .22);
    }
    try {
      this.core.render({time:this.time, age:this.age, dt, energy:this.energy,
        listening:this.listening, spectrum:this.spectrum, color:state.color,
        brightness:this.brightness * (document.body.classList.contains('has-workspace') ? 1.2 : 1), reduced:this.reduced});
      this.dirty = false;
      this.lastReducedState = this.reduced ? reducedState : '';
      if (!this.canvas.dataset.rendered) this.canvas.dataset.rendered = 'true';
    } catch (error) {
      console.warn('Voice core unavailable; using Canvas renderer.', error);
      this.useFallback();
    }
  }
  dispose() {
    if (this.disposed) return;
    this.disposed = true;
    cancelAnimationFrame(this.frame);
    this.resize?.disconnect();
    document.removeEventListener('visibilitychange', this.onVisibility);
    this.canvas.removeEventListener('webglcontextlost', this.onContextLost);
    this.backup?.dispose(); this.core?.dispose();
  }
}
