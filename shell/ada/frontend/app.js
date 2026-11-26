import {initWorkspace, workspaceEvent, workspaceUI, workspaceUIState} from './workspace.js?v=14';
import {JarvisOrb} from './orb.js?v=9';
import {AudioEngine} from './audio/engine.js';
import {initGestures} from './gestures.js?v=1';
const gestures = initGestures();
window.jarvisDiagnostics?.phase('Starting the visualizer…');
const orb = new JarvisOrb(document.getElementById('orb'));
const status = document.getElementById('status');
const apiConnection = document.getElementById('apiConnection');
const apiConnectionLabel = document.getElementById('apiConnectionLabel');
const exitButton = document.getElementById('exitButton');
const motion = matchMedia('(prefers-reduced-motion: reduce)');
const captions = {
  connecting: 'Connecting.', idle: 'Ready — say hello.',
  listening: 'Speech detected.', thinking: 'Waiting for a reply…',
  speaking: 'Speaking.', reconnecting: 'Reconnecting.',
  error: 'The connection needs attention. See the local diagnostic log.', exiting: 'Closed.',
};
let state = '', attempt = null, serial = 0, retries = 0, retryTimer = 0;
let exiting = false, config = null, recovery = '', configRequest = null;
let preferences = {}, meterFrame = 0, lastMeter = 0, envelope = 0;
try { preferences = JSON.parse(localStorage.getItem('jarvis.preferences') || '{}') || {}; } catch {}
const settingsButton = document.getElementById('settingsButton');
const settingsPanel = document.getElementById('settingsPanel');
const voiceSelect = document.getElementById('voiceSelect');
const voiceStatus = document.getElementById('voiceStatus');
const pauseWhileSpeaking = document.getElementById('pauseWhileSpeaking');
const speakerModeStatus = document.getElementById('speakerModeStatus');
const stopSpeaking = document.getElementById('stopSpeaking');
const instructionsInput = document.getElementById('instructionsInput');
const instructionsSave = document.getElementById('instructionsSave');
const instructionsReset = document.getElementById('instructionsReset');
const instructionsDefault = document.getElementById('instructionsDefault');
const instructionsStatus = document.getElementById('instructionsStatus');
let settingsSaving = false, settingsRequest = null, instructionsDirty = false;
let micResumeTimer = 0, deferredUI = null;
const uiResults = new Map();
function syncSettingsControls() {
  const disabled = !config || settingsSaving || exiting;
  voiceSelect.disabled = instructionsInput.disabled = disabled;
  pauseWhileSpeaking.disabled = disabled;
  const valid = instructionsInput.value.trim() && instructionsInput.value.length <= 8000;
  const atDefault = instructionsInput.value === config?.default_instructions && config?.settings.instructions === config?.default_instructions;
  // Saving the current text is safe, even when an edit did not emit input.
  // Keep dirty tracking for draft preservation, not permission to save.
  instructionsSave.disabled = disabled || !valid;
  instructionsReset.disabled = disabled || atDefault;
  instructionsDefault.disabled = disabled || !valid || atDefault;
}
instructionsInput.oninput = () => {
  instructionsDirty = instructionsInput.value !== config?.settings.instructions;
  instructionsStatus.textContent = instructionsDirty ? 'Unsaved changes.' : '';
  syncSettingsControls();
};
document.getElementById('instructionsForm').onsubmit = event => {
  event.preventDefault();
  if (instructionsSave.disabled) return;
  void saveConversationSetting('instructions', instructionsInput.value, instructionsStatus);
};
instructionsReset.onclick = () => {
  if (!instructionsReset.disabled) void saveConversationSetting('instructions', null, instructionsStatus, 'reset');
};
instructionsDefault.onclick = () => {
  if (!instructionsDefault.disabled) void saveConversationSetting('instructions', instructionsInput.value, instructionsStatus, 'default');
};
const micSlider = document.getElementById('micVolume');
const micMuteButton = document.getElementById('micMute');
function syncMicVolume() {
  const percent = Math.round((Number.isFinite(preferences.micGain) ? Math.max(0, Math.min(2, preferences.micGain)) : 1) * 100);
  micSlider.value = percent;
  micSlider.setAttribute('aria-valuetext', `${percent}%`);
  document.getElementById('micVolumeValue').textContent = `${percent}%`;
  const muted = preferences.micMuted === true;
  micMuteButton.textContent = muted ? 'Unmute microphone' : 'Mute microphone';
  micMuteButton.setAttribute('aria-pressed', String(muted));
  document.getElementById('micMutedNotice').hidden = !muted;
}
function saveAudioPreferences() {
  try { localStorage.setItem('jarvis.preferences', JSON.stringify({...preferences,micMuted:micResumeTimer?false:preferences.micMuted})); }
  catch { document.getElementById('micVolumeHelp').textContent = 'Audio settings applied for this session. Browser storage is unavailable.'; }
}
micMuteButton.onclick = () => {
  clearTimeout(micResumeTimer);micResumeTimer=0;
  preferences.micMuted = preferences.micMuted !== true;
  attempt?.engine?.mute(preferences.micMuted);
  send(attempt, {type:'mute', muted:preferences.micMuted});
  if (attempt && preferences.micMuted) { attempt.hearing = false; refresh(attempt); }
  syncMicVolume(); saveAudioPreferences();
};
function showSettings(show, focus = true) {
  settingsPanel.hidden = !show; settingsButton.setAttribute('aria-expanded', String(show));
  if (focus) (show ? document.getElementById('settingsPanelClose') : settingsButton).focus({preventScroll:true});
}
settingsButton.onclick = () => showSettings(settingsPanel.hidden);
document.getElementById('settingsPanelClose').onclick = () => showSettings(false);
micSlider.oninput = () => {
  preferences.micGain = Number(micSlider.value) / 100;
  attempt?.engine?.setMicGain(preferences.micGain);
  syncMicVolume();
  saveAudioPreferences();
};
pauseWhileSpeaking.onchange = async () => {
  if (!config || settingsSaving || exiting) return;
  settingsSaving = true; syncSettingsControls();
  speakerModeStatus.textContent = 'Saving…';
  const controller = new AbortController(); settingsRequest = controller;
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch('/api/settings/audio', {
      method:'PATCH', headers:{'Content-Type':'application/json'}, signal:controller.signal,
      body:JSON.stringify({pause_microphone_while_speaking:pauseWhileSpeaking.checked}),
    });
    const data = await response.json();
    if (!response.ok) throw new Error('save_failed');
    if (exiting) return;
    config = data; configure(data); saveAudioPreferences();
    speakerModeStatus.textContent = pauseWhileSpeaking.checked ? 'Saved. Listening pauses during replies.' : 'Saved. You can interrupt Ada by speaking.';
    if (attempt) refresh(attempt);
  } catch {
    if (!exiting) {
      pauseWhileSpeaking.checked = preferences.pauseMicrophoneWhileSpeaking;
      speakerModeStatus.textContent = 'Could not save. Please try again.';
    }
  } finally {
    clearTimeout(timer); settingsRequest = null; settingsSaving = false; syncSettingsControls();
    if (!exiting && !attempt && recovery === 'network') scheduleRetry();
  }
};
stopSpeaking.onclick = () => {
  if (!valid(attempt) || !attempt.engine?.outputPending) return;
  attempt.engine.interrupt(); send(attempt, {type:'stop'});
  attempt.playing = attempt.waiting = attempt.hearing = false;
  resetResponseStatus(attempt); refresh(attempt);
};
document.addEventListener('pointerdown', event => {
  if (!settingsPanel.hidden && !settingsPanel.contains(event.target) && !settingsButton.contains(event.target)) showSettings(false, false);
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && !settingsPanel.hidden) { showSettings(false); event.stopImmediatePropagation(); }
}, true);
syncMicVolume();

function syncVoice(data) {
  const selected = data.settings.voice;
  const voices = {...data.voices};
  // Keep manually configured voices visible without replacing their value.
  if (!voices[selected]) voices[selected] = 'Configured voice';
  voiceSelect.replaceChildren(...Object.entries(voices).map(([name, style]) => new Option(`${name} · ${style}`, name)));
  voiceSelect.value = selected;
  syncSettingsControls();
}
voiceSelect.onchange = () => {
  if (!config || settingsSaving || exiting || voiceSelect.value === config.settings.voice) return;
  void saveConversationSetting('voice', voiceSelect.value, voiceStatus);
};
async function saveConversationSetting(field, value, notice, action = '', deferReconnect = false) {
  if (!config || settingsSaving || exiting) return;
  settingsSaving = true; syncSettingsControls();
  notice.textContent = field === 'voice' ? `Saving ${value}…` : 'Saving instructions…';
  const controller = new AbortController(); settingsRequest = controller;
  const timer = setTimeout(() => controller.abort(), 8000);
  let restart = false;
  try {
    const response = await fetch(`/api/settings/${field}${action ? '/' + action : ''}`, {
      method: action === 'reset' ? 'POST' : 'PATCH', headers: {'Content-Type': 'application/json'},
      body: action === 'reset' ? undefined : JSON.stringify({[field]: value}), signal: controller.signal,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Check the setting and try again.');
    if (exiting) return;
    const changed = data.settings[field] !== config.settings[field];
    if (field === 'instructions') instructionsDirty = false;
    config = data; configure(data);
    if (changed && !deferReconnect) {
      clearTimeout(retryTimer); retryTimer = 0; retries = 0;
      await release();
      if (exiting) return;
      restart = true;
    }
    notice.textContent = field === 'voice' ? `${value} saved. Starting a new conversation…`
      : action === 'default' ? 'Default saved. Reset will restore these instructions.'
      : action === 'reset' ? 'Default instructions restored.' : 'Instructions saved.';
    return {changed};
  } catch (error) {
    if (!exiting) {
      voiceSelect.value = config.settings.voice;
      notice.textContent = error.name === 'AbortError' || error instanceof TypeError
        ? 'Could not confirm the change. Check the connection and try again.'
        : `Save failed. ${error.message}`;
    }
    if (deferReconnect) throw error;
  } finally {
    clearTimeout(timer); settingsRequest = null; settingsSaving = false;
    syncSettingsControls();
    if (!exiting && restart) void start();
    else if (!exiting && !attempt && recovery === 'network') scheduleRetry();
  }
}

function setApiConnection(next) {
  const labels = {connecting:'API connecting…', connected:'API connected', reconnecting:'API reconnecting…', disconnected:'API disconnected', closed:'API closed'};
  apiConnection.dataset.state = next;
  if (apiConnectionLabel.textContent !== labels[next]) apiConnectionLabel.textContent = labels[next];
}
function audioDebug(session, event, values = {}) {
  if (session?.debug) console.info('[Jarvis audio]', JSON.stringify({event, session:session.id, epoch:session.epoch, ...values}));
}
function resetResponseStatus(session) {
  clearTimeout(session.responseTimer); session.responseTimer = 0;
  session.slowResponse = session.heardByGemini = session.responseReceived = session.noReply = false;
}
function setState(next, description = captions[next]) {
  if (['connecting','reconnecting','error','exiting'].includes(next)) stopSpeaking.hidden = true;
  if (state !== next) {
    state = next;
    document.body.dataset.state = next;
    orb.setState(next);
  }
  if (status.textContent !== description) {
    status.textContent = description;
    audioDebug(attempt, 'state', {state:next, description});
  }
  window.jarvisDiagnostics?.state(next, description);
}
function valid(session) { return !!session && !exiting && attempt === session && !session.disposed; }
function refresh(session) {
  if (!valid(session) || !session.audioReady || !session.serverReady) return;
  if(deferredUI?.finished&&!session.playing){runDeferredUI();return;}
  if (!session.stableTimer) session.stableTimer = setTimeout(() => {
    session.stableTimer = 0;
    if (valid(session) && session.audioReady && session.serverReady) retries = 0;
  }, 20000);
  const paused = session.engine.microphonePaused();
  stopSpeaking.hidden = !session.engine.outputPending;
  const next = session.hearing && !paused ? 'listening' : session.playing ? 'speaking' : session.waiting ? 'thinking' : 'idle';
  let description = captions[next];
  if (next === 'thinking') {
    description = session.heardByGemini ? 'Speech recognized. Waiting for a reply…' : 'Speech detected. Waiting for a reply…';
    if (session.slowResponse) description = session.heardByGemini
      ? 'Speech recognized, but no reply yet. You can try again.'
      : 'No reply yet. Try speaking again, or check the microphone in Settings.';
    else if (!session.responseTimer) session.responseTimer = setTimeout(() => {
      session.responseTimer = 0;
      if (valid(session) && session.waiting && !session.hearing && !session.playing) {
        session.slowResponse = true;
        audioDebug(session, 'response_wait', {speech_recognized:!!session.heardByGemini, waited_seconds:12});
        refresh(session);
      }
    }, 12000);
  } else {
    clearTimeout(session.responseTimer); session.responseTimer = 0; session.slowResponse = false;
    if (next === 'idle' && session.noReply) description = 'No reply received. Please try again.';
    else if (next === 'idle' && preferences.micMuted) description = 'Microphone muted. Unmute in Settings to speak.';
    else if (next === 'idle' && document.body.classList.contains('has-workspace')) description = 'Ready to explore your project.';
  }
  if (paused && !preferences.micMuted) description = session.engine.outputPending
    ? 'Ada is speaking. Listening is paused.' : 'Listening resumes in a moment…';
  setState(next, description);
}
function send(session, event) {
  if (valid(session) && session.socket?.readyState === WebSocket.OPEN) session.socket.send(JSON.stringify(event));
}
function configure(data) {
  if (!instructionsDirty) instructionsInput.value = data.settings.instructions;
  syncVoice(data);
  const settings = data.settings || {}, explicit = new Set(data.preferences_configured || []);
  const pick = (key, legacy, fallback) => explicit.has(key) ? settings[key] : (preferences[legacy] ?? settings[key] ?? fallback);
  preferences = {
    volume: Math.max(0, Math.min(1, Number(pick('volume', 'volume', .75)) || 0)),
    inputDevice: pick('input_device', 'inputDevice', ''),
    outputDevice: pick('output_device', 'outputDevice', ''),
    echoCancellation: settings.echo_cancellation ?? true,
    pauseMicrophoneWhileSpeaking: settings.pause_microphone_while_speaking === true,
    reducedMotion: pick('reduced_motion', 'reducedMotion', null),
    micGain: Number.isFinite(preferences.micGain) ? Math.max(0, Math.min(2, preferences.micGain)) : 1,
    micMuted: preferences.micMuted === true,
  };
  syncMicVolume();
  pauseWhileSpeaking.checked = preferences.pauseMicrophoneWhileSpeaking;
  attempt?.engine?.setPauseMicrophoneWhileSpeaking(preferences.pauseMicrophoneWhileSpeaking);
  orb.reduced = preferences.reducedMotion ?? motion.matches;
  document.body.dataset.reducedMotion = String(orb.reduced);
}
async function loadConfig() {
  const controller = new AbortController(); configRequest = controller;
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch('/api/settings', {signal: controller.signal, cache: 'no-store'});
    if (!response.ok) throw new DOMException('Configuration unavailable.', response.status === 422 ? 'ConfigurationError' : 'NetworkError');
    const data = await response.json();
    if (!exiting) { config = data; configure(data); }
    return data;
  } finally { clearTimeout(timer); if (configRequest === controller) configRequest = null; }
}
async function release(session = attempt) {
  if (!session) return;
  session.disposed = true;
  clearTimeout(session.timer); clearTimeout(session.stableTimer);
  resetResponseStatus(session);
  if (attempt === session) attempt = null;
  setApiConnection(exiting ? 'closed' : 'disconnected');
  if (session.socket) {
    session.socket.onmessage = session.socket.onclose = session.socket.onerror = null;
    session.socket.close();
  }
  orb.setAudio(); envelope = 0;
  await session.engine?.close();
}
function scheduleRetry() {
  if (exiting || retryTimer) return;
  recovery = 'network';
  setApiConnection('reconnecting');
  setState('reconnecting');
  const delay = Math.min(500 * 2 ** Math.min(retries++, 5), 10000);
  retryTimer = setTimeout(() => { retryTimer = 0; start(); }, delay);
}
function fail(session, code, retryable = false, description = '') {
  if (session && !valid(session)) return;
  // Codes only: SDK exception strings can contain credentials or private URLs.
  console.warn('[Jarvis]', code);
  void release(session);
  if (retryable) scheduleRetry();
  else {
    recovery = code;
    const help = {
      permission_denied: 'Allow microphone access, then tap the visualizer to retry.',
      microphone_missing: 'Connect a microphone, then tap the visualizer to retry.',
      microphone_busy: 'The microphone is busy. Release it in the other application and tap to retry.',
      audio_suspended: 'Tap the visualizer to enable browser audio.',
      device_lost: 'The audio device disconnected. Reconnect it and tap to retry.',
    };
    setState('error', `${code}: ${description || help[code] || 'Check data/logs/startup.log for details.'}`);
  }
}
function deferUI(kind){
  clearTimeout(deferredUI?.timer);
  deferredUI={kind,finished:false,timer:setTimeout(runDeferredUI,30000)};
}
function runDeferredUI(){
  if(!deferredUI)return;
  const {kind,timer}=deferredUI;deferredUI=null;clearTimeout(timer);
  if(kind==='exit')void exitApp();
  else void (async()=>{await release();if(!exiting)await start();})().catch(()=>{if(!exiting)scheduleRetry();});
}
async function voiceUIAction(args){
  const {action,value}=args;
  const amount=(fallback,min,max)=>{const n=args.amount??fallback;if(!Number.isFinite(n)||n<min||n>max)throw Error(`Choose a value between ${min} and ${max}.`);return n;};
  if(['projects','close','cancel','show_response','save_visible','confirm','read_document','edit_document','document_section'].includes(action)){
    if(['close','cancel'].includes(action)){showSettings(false,false);if(action==='cancel'){clearTimeout(deferredUI?.timer);deferredUI=null;}}
    else showSettings(false,false);
    return workspaceUI(action,args);
  }
  if(action==='settings'){await workspaceUI('close');showSettings(true,false);return {view:'settings'};}
  if(action==='scroll'){
    const dialog=document.getElementById('workspaceDialog');
    const editor=dialog.open&&dialog.querySelector('.code-editor');
    const focused=document.querySelector('.project-panel.is-focused .panel-body');
    const boardScroll=document.body.classList.contains('cad-open')?document.getElementById('cadWorkspace'):innerWidth>1000&&focused&&focused.scrollHeight>focused.clientHeight?focused:document.getElementById('workspace');
    const target=dialog.open?(editor||dialog):!settingsPanel.hidden?settingsPanel:boardScroll;
    const direction=args.direction||'down',pages=amount(1,.1,10);
    const top=direction==='top'?0:direction==='bottom'?target.scrollHeight:target.scrollTop+(direction==='up'?-1:direction==='down'?1:0)*target.clientHeight*.8*pages;
    const left=target.scrollLeft+(direction==='left'?-1:direction==='right'?1:0)*target.clientWidth*.8*pages;
    target.scrollTo({top,left,behavior:'instant'});return {scroll_top:target.scrollTop,scroll_left:target.scrollLeft};
  }
  if(action==='set_microphone_level'){
    preferences.micGain=amount(100,1,200)/100;attempt?.engine?.setMicGain(preferences.micGain);syncMicVolume();saveAudioPreferences();return {microphone_percent:preferences.micGain*100};
  }
  if(action==='pause_microphone'){
    const seconds=amount(15,1,300);clearTimeout(micResumeTimer);
    preferences.micMuted=true;attempt?.engine?.mute(true);send(attempt,{type:'mute',muted:true});syncMicVolume();
    micResumeTimer=setTimeout(()=>{micResumeTimer=0;preferences.micMuted=false;attempt?.engine?.mute(false);send(attempt,{type:'mute',muted:false});syncMicVolume();saveAudioPreferences();if(attempt)refresh(attempt);},seconds*1000);
    return {microphone_paused_seconds:seconds,resumes_automatically:true};
  }
  if(action==='set_volume'||action==='set_motion'){
    if(action==='set_motion'&&!['reduced','full'].includes(value))throw Error('Choose reduced or full motion.');
    const changes=action==='set_volume'?{volume:amount(75,0,100)/100}:{reduced_motion:value==='reduced'};
    const response=await fetch('/api/settings/audio',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(changes),signal:AbortSignal.timeout(8000)});
    const data=await response.json();if(!response.ok)throw Error(data.detail||'Could not save audio preferences.');
    config=data;configure(data);attempt?.engine?.setVolume(preferences.volume);saveAudioPreferences();return changes;
  }
  if(['set_voice','set_instructions','reset_instructions','save_default_instructions'].includes(action)){
    if(!config||settingsSaving)throw Error('Settings are still loading or saving. Please retry.');
    const voice=action==='set_voice';if(voice&&!Object.hasOwn(config.voices,value))throw Error('Choose a voice returned by get_ui_state.');
    const mode=action==='reset_instructions'?'reset':action==='save_default_instructions'?'default':'';
    if(!voice&&mode!=='reset'&&(typeof value!=='string'||!value.trim()))throw Error('Provide the complete revised instructions.');
    const saved=await saveConversationSetting(voice?'voice':'instructions',value,voice?voiceStatus:instructionsStatus,mode,true);
    if(saved?.changed)deferUI('restart');
    return {saved:true,reconnect_after_reply:!!saved?.changed};
  }
  if(action==='exit'){deferUI('exit');return {closing_after_reply:true};}
  throw Error('Unknown screen action.');
}
async function handleUIRequest(session,event){
  if(typeof event.id!=='string'||event.epoch!==session.epoch)return;
  let response=uiResults.get(event.id);
  if(!response){
    try{
      if(event.name!=='get_ui_state'&&workspaceUIState().active_project!==event.project_id)throw Error('The screen has changed projects. Inspect the current view and retry.');
      const result=event.name==='get_ui_state'?{...workspaceUIState(),settings_open:!settingsPanel.hidden,
        settings:{voice:config?.settings.voice,voices:config?.voices,instructions:config?.settings.instructions,
          volume_percent:Math.round(preferences.volume*100),microphone_percent:Math.round(preferences.micGain*100),microphone_muted:preferences.micMuted,reduced_motion:orb.reduced}}
        :event.name==='control_ui'?await voiceUIAction(event.arguments||{}):event.name==='control_cad'?await workspaceUI('cad_control',event.arguments||{}):['prepare_print','control_plate','control_print'].includes(event.name)?await workspaceUI(event.name,event.arguments||{}):null;
      if(!result)throw Error('Unknown screen tool.');
      response={type:'ui_result',id:event.id,ok:true,result};
    }catch(error){response={type:'ui_result',id:event.id,ok:false,error:error.message||'Could not complete the screen action.'};}
    uiResults.set(event.id,response);if(uiResults.size>100)uiResults.delete(uiResults.keys().next().value);
  }
  send(session,response);
}
function handle(session, event) {
  if (!valid(session)) return;
  workspaceEvent(event);
  switch (event.type) {
    case 'ui_request':
      void handleUIRequest(session,event);
      return;
    case 'connecting':
      resetResponseStatus(session);
      setApiConnection(event.resuming ? 'reconnecting' : 'connecting');
      clearTimeout(session.stableTimer); session.stableTimer = 0;
      session.serverReady = session.playing = session.hearing = session.waiting = false;
      session.epoch = event.epoch;
      session.engine.reset(event.epoch);
      setState(event.resuming ? 'reconnecting' : 'connecting');
      break;
    case 'ready':
      session.debug = event.debug === true;
      audioDebug(session, 'ready', {model:event.model});
      session.serverReady = true;
      voiceStatus.textContent = `${config.settings.voice} is selected.`;
      send(session, {type:'mute', muted:preferences.micMuted === true});
      setApiConnection('connected');
      clearTimeout(session.timer);
      recovery = '';
      break;
    case 'reconnecting':
      resetResponseStatus(session);
      setApiConnection('reconnecting');
      clearTimeout(session.stableTimer); session.stableTimer = 0;
      session.serverReady = session.playing = session.hearing = session.waiting = false;
      session.engine.interrupt(); orb.setAudio();
      setState('reconnecting');
      break;
    case 'speech': {
      const wasHearing = session.hearing;
      session.hearing = Boolean(event.active) && preferences.micMuted !== true && !session.engine.microphonePaused();
      if (session.hearing && !wasHearing) resetResponseStatus(session);
      // Local speech detection updates the visual only. Gemini's interrupted
      // event stops playback when a conversational interruption is confirmed.
      if (session.hearing) session.waiting = false;
      else if (wasHearing && !session.playing) session.waiting = true;
      break;
    }
    case 'transcript':
      if (event.role === 'user') {
        session.heardByGemini = true;
        if (!session.hearing && !session.playing && !session.responseReceived) session.waiting = true;
      }
      break;
    case 'turn_started':
      session.responseReceived = true; session.noReply = false;
      session.engine.begin(event.epoch, event.turn);
      session.waiting = true;
      break;
    case 'generation_complete':
    case 'turn_complete':
      if(event.type==='turn_complete'&&deferredUI)deferredUI.finished=true;
      session.engine.finish(event.epoch, event.turn);
      if (event.type === 'turn_complete' && !session.playing) {
        session.noReply = session.waiting && !session.responseReceived;
        session.waiting = false;
      }
      break;
    case 'interrupted':
      session.engine.interrupt(event.turn);
      session.playing = session.waiting = false;
      orb.setAudio(); envelope = 0;
      break;
    case 'waiting':
      session.noReply = session.waiting && !session.responseReceived;
      session.waiting = false;
      break;
    case 'error':
      fail(session, event.code || 'gemini_error', event.retryable === true);
      return;
  }
  refresh(session);
}
async function start() {
  if (exiting || attempt || settingsSaving) return;
  clearTimeout(retryTimer); retryTimer = 0;
  const session = {id: ++serial, disposed: false, audioReady: false, serverReady: false, epoch: 0};
  attempt = session;
  setApiConnection(retries ? 'reconnecting' : 'connecting');
  setState(retries ? 'reconnecting' : 'connecting');
  try {
    if (!config) await loadConfig();
    if (!valid(session)) return;
    if (!config.configured) {
      fail(session, 'missing_key', false, 'Set GEMINI_API_KEY in the local .env file and restart Jarvis.');
      return;
    }
    const engine = new AudioEngine(audio => {
      const ws = session.socket;
      if (valid(session) && session.audioReady && session.serverReady && !preferences.micMuted && ws?.readyState === WebSocket.OPEN && ws.bufferedAmount < 12800) {
        ws.send(audio); session.sentFrames = (session.sentFrames || 0) + 1;
      }
    }, event => {
      if (!valid(session) || (event.turn && event.turn !== engine.turn)) return;
      audioDebug(session, event.type, {turn:event.turn});
      if (event.type === 'playback_started') { session.playing = true; session.waiting = false; }
      if (event.type === 'playback_drained' || event.type === 'playback_stopped') { session.playing = session.waiting = false; }
      if (event.type === 'buffering') { session.playing = false; session.waiting = true; }
      if (event.type === 'overflow') {
        engine.interrupt(); send(session, {type: 'stop'});
        session.playing = session.waiting = false;
        console.warn('[Jarvis] playback_overflow');
      }
      if (event.type === 'device_lost' || event.type === 'audio_suspended') {
        fail(session, event.type, event.type === 'device_lost', event.type === 'audio_suspended' ? 'Activate the vocalizer to resume browser audio.' : 'Waiting for the microphone to reconnect.');
        return;
      }
      refresh(session);
    });
    session.engine = engine;
    const ws = session.socket = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws/live`);
    ws.binaryType = 'arraybuffer';
    session.timer = setTimeout(() => fail(session, 'connection_timeout', true), 20000);
    ws.onmessage = message => {
      if (!valid(session)) return;
      if (typeof message.data === 'string') {
        try { handle(session, JSON.parse(message.data)); }
        catch { fail(session, 'invalid_server_message', true); }
      } else if (session.audioReady) { engine.enqueue(message.data); refresh(session); }
    };
    ws.onerror = () => fail(session, 'local_connection_lost', true);
    ws.onclose = () => fail(session, 'local_connection_closed', true);
    await engine.start(preferences);
    if (!valid(session)) return;
    audioDebug(session, 'audio_ready', engine.diagnostics());
    engine.setMicGain(preferences.micGain);
    engine.mute(preferences.micMuted);
    // A server handshake may complete while permission/worklets initialize.
    engine.reset(session.epoch);
    session.audioReady = true;
    refresh(session);
  } catch (error) {
    if (!valid(session)) return;
    const codes = {
      ConfigurationError: ['configuration_invalid', false, 'Correct data/settings.json and restart Jarvis.'],
      NotAllowedError: ['permission_denied', false, 'Allow microphone access in browser permissions.'],
      NotFoundError: ['microphone_missing', false, 'Connect a microphone. Jarvis will detect it automatically.'],
      NotReadableError: ['microphone_busy', true],
      OverconstrainedError: ['microphone_missing', false, 'Reconnect the configured microphone or update local audio preferences.'],
      NotSupportedError: ['audio_configuration', false, error.message || 'Update local audio preferences for this browser.'],
      AudioGestureRequired: ['audio_suspended', false, 'Activate the vocalizer to enable browser audio.'],
    };
    const [code, retryable, description] = codes[error.name] || [session.engine ? 'audio_unavailable' : 'service_unavailable', true];
    fail(session, code, retryable, description);
  }
}
function recover() {
  if (exiting || attempt) return;
  if (['audio_suspended', 'permission_denied', 'microphone_missing', 'microphone_busy', 'device_lost', 'network'].includes(recovery)) {
    retries = 0; void start();
  }
}
document.querySelector('.stage').addEventListener('pointerdown', recover);
document.addEventListener('keydown', event => {
  if (event.target?.closest?.('button,input,textarea,select,a')) return;
  if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); recover(); }
});
navigator.mediaDevices?.addEventListener('devicechange', () => {
  if (['microphone_missing', 'microphone_busy', 'device_lost', 'network'].includes(recovery)) recover();
});
window.addEventListener('online', () => { if (recovery === 'network') recover(); });
// Browsers supporting permission events can recover after a site permission change.
navigator.permissions?.query({name: 'microphone'}).then(permission => {
  permission.addEventListener('change', () => { if (permission.state === 'granted') recover(); });
}).catch(() => {});
motion.addEventListener('change', () => {
  orb.reduced = preferences.reducedMotion ?? motion.matches;
  document.body.dataset.reducedMotion = String(orb.reduced);
});

async function exitApp() {
  if (exitButton.disabled) return;
  clearTimeout(micResumeTimer);clearTimeout(deferredUI?.timer);deferredUI=null;
  exiting = true; recovery = ''; clearTimeout(retryTimer); retryTimer = 0;
  gestures.dispose();
  setApiConnection('closed');
  showSettings(false, false); settingsButton.disabled = true;
  configRequest?.abort(); settingsRequest?.abort(); syncSettingsControls(); exitButton.disabled = true;
  setState('exiting');
  cancelAnimationFrame(meterFrame);
  const cleanup = release();
  // Audio teardown cannot hold the shutdown route hostage.
  await Promise.race([cleanup, new Promise(resolve => setTimeout(resolve, 350))]);
  orb.dispose();
  try {
    const response = await fetch('/api/exit', {method: 'POST', signal: AbortSignal.timeout(2500)});
    if (!response.ok) throw new Error('exit_failed');
    const result = await response.json();
    if (!result.kiosk) window.close();
  } catch {
    console.warn('[Jarvis] exit_failed');
    status.textContent = 'Exit could not reach the local service. Activate Exit to retry.';
    exitButton.disabled = false;
  }
}
exitButton.addEventListener('click', exitApp);
window.addEventListener('pagehide', () => {
  gestures.dispose();
  exiting = true; clearTimeout(retryTimer); configRequest?.abort(); settingsRequest?.abort();
  cancelAnimationFrame(meterFrame); void release(); orb.dispose();
});
// A browser back/forward-cache restoration needs a fresh microphone/session.
window.addEventListener('pageshow', event => { if (event.persisted) location.reload(); });
function meter(now) {
  if (exiting) return;
  meterFrame = requestAnimationFrame(meter);
  if (document.hidden || now - lastMeter < 30) return;
  const dt = Math.min((now - (lastMeter || now)) / 1000, .1); lastMeter = now;
  if (attempt?.audioReady) {
    const paused = attempt.engine.microphonePaused();
    if (paused !== attempt.capturePaused) {
      attempt.capturePaused = paused;
      if (paused) attempt.hearing = false;
      refresh(attempt);
    }
  }
  if (attempt?.debug && now - (attempt.lastAudioReport || 0) >= 10000) {
    attempt.lastAudioReport = now;
    audioDebug(attempt, 'browser_transport', {microphone_frames_sent:attempt.sentFrames || 0,
      muted:preferences.micMuted === true, context:attempt.engine?.context?.state,
      ...attempt.engine?.diagnostics(),
      websocket_buffered_bytes:attempt.socket?.bufferedAmount || 0});
  }
  const levels = attempt?.audioReady ? attempt.engine.levels() : {energy: 0, low: 0, high: 0};
  envelope += (levels.energy - envelope) * (1 - Math.exp(-dt / (levels.energy > envelope ? .035 : .23)));
  orb.setAudio({...levels, energy: envelope, listening: attempt?.hearing ? Math.min(1, (attempt.engine.micLevel || 0) * 7) : 0});
}
window.addEventListener('ada:workspace-layout', () => orb.fit());
initWorkspace(text => {
  if (!valid(attempt) || !attempt.serverReady) return false;
  send(attempt, {type:'text', text});
  attempt.waiting = true; refresh(attempt);
  return true;
});
setState('connecting');
meterFrame = requestAnimationFrame(meter);
void start();
