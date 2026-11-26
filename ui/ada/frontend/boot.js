// This small, classic script can report failure even if an application module
// cannot load or parse. v=12 refreshes cached assets for hand control.
(() => {
  const panel = document.getElementById('startupPanel');
  const title = document.getElementById('startupTitle');
  const detail = document.getElementById('startupDetail');
  let fatal = false, ready = false, moduleReady = false, state = 'connecting';
  const clean = value => String(value || '').replace(/AIza[\w-]+/g, '[redacted]').replace(/([?&](?:key|token|access_token)=)[^\s&#]+/gi, '$1[redacted]').slice(0, 1500);
  const show = (heading, message, failed = false) => {
    panel.hidden = false; panel.classList.toggle('startup-error', failed);
    title.textContent = heading; detail.textContent = clean(message);
  };
  const diagnostics = window.jarvisDiagnostics = {
    phase(message) {
      console.info('[Jarvis startup]', message);
      if (!fatal) show('Starting…', message);
    },
    state(next, description) {
      state = next;
      if (next === 'exiting') { panel.hidden = true; clearInterval(watchdog); return; }
      if (fatal) return;
      if (next === 'error') show('Jarvis needs attention', description, true);
      else if (next === 'reconnecting') show('Reconnecting…', 'The voice connection was interrupted. Jarvis will retry.');
      else if (ready) panel.hidden = true;
    },
    error(code, error) {
      fatal = true;
      document.getElementById('apiConnection').dataset.state = 'disconnected';
      document.getElementById('apiConnectionLabel').textContent = 'API disconnected';
      const message = clean(error?.message || error);
      show(`Jarvis could not start · ${code}`, `${message}\nRestart with ./start.sh --debug. Details: data/logs/startup.log`, true);
      console.error('[Jarvis startup]', code, message, clean(error?.stack));
    },
  };
  addEventListener('error', event => {
    if (event.target !== window) {
      const element = event.target;
      if (element.tagName === 'SCRIPT' || element.tagName === 'LINK') diagnostics.error('asset_load', element.src || element.href);
      return;
    }
    diagnostics.error('javascript', event.error || `${event.message} (${event.filename}:${event.lineno})`);
  }, true);
  addEventListener('unhandledrejection', event => diagnostics.error('unhandled_promise', event.reason));
  const began = performance.now();
  const watchdog = setInterval(() => {
    if (fatal || state === 'exiting') { clearInterval(watchdog); return; }
    const canvas = document.getElementById('orb');
    if (!ready && canvas?.dataset.rendered === 'true') {
      ready = true;
      console.info('[Jarvis startup] First visualizer frame:', canvas.dataset.renderer);
    }
    if (ready && ['idle', 'speaking', 'listening', 'thinking'].includes(state)) {
      panel.hidden = true; clearInterval(watchdog);
    } else if (performance.now() - began > 15000 && state === 'connecting') {
      if (!ready) diagnostics.error('visualizer_timeout', 'The visualizer has not drawn a frame. Check the browser/module errors in the startup log.');
      else show('Waiting for the voice connection…', 'The visualizer is ready. Check microphone permission and data/logs/startup.log.');
    }
  }, 250);
  diagnostics.phase('Loading application modules…');
  // Keep Exit usable when the main module could not install its handlers.
  document.getElementById('exitButton').addEventListener('click', async event => {
    if (!fatal || moduleReady) return;
    const button = event.currentTarget;
    button.disabled = true; clearInterval(watchdog);
    try {
      const response = await fetch('/api/exit', {method:'POST', signal:AbortSignal.timeout(2500)});
      if (!response.ok) throw Error('Could not reach the local service. Close this window to exit.');
      if (!(await response.json()).kiosk) window.close();
    } catch (error) { button.disabled = false; diagnostics.error('exit_failed', error); }
  });
  import('./app.js?v=12').then(() => { moduleReady = true; }).catch(error => diagnostics.error('module_load', error));
})();
