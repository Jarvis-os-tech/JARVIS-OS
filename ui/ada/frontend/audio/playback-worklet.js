import {PlaybackBuffer} from './pcm.js';

class PlaybackProcessor extends AudioWorkletProcessor {
  constructor() {
    super(); this.player = new PlaybackBuffer(sampleRate, event => this.port.postMessage({turn:this.player.turn,...event,epoch:this.player.epoch}));
    this.port.onmessage = ({data}) => {
      switch(data.type){
        case 'reset': this.player.reset(data.epoch); break;
        case 'begin': this.player.begin(data.epoch,data.turn); break;
        case 'audio': this.player.push(data.epoch,data.turn,new Int16Array(data.audio)); break;
        case 'cancel': this.player.cancel(data.turn); break;
        case 'finish': this.player.finish(data.epoch,data.turn); break;
      }
    };
  }
  process(inputs, outputs) {this.player.render(outputs[0][0]);return true;}
}
registerProcessor('jarvis-playback',PlaybackProcessor);
