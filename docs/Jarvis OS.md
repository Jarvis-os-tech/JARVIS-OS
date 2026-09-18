Jarvis OS
Personal Voice AI Operating System — PRD & Phase-by-Phase Build Roadmap
Omarchy 4 (Arch Linux) → Jarvis OS

0. Read This First — Your Six Docs Disagree on a Few Load-Bearing Facts
Before any of this gets built (or handed to a coding agent), lock these down. They're not style nitpicks — a security-and-rollback system built on the wrong assumption here can genuinely break your machine.

Question	Doc says A	Doc says B	Resolve by
Filesystem	Master Context: LUKS-encrypted Btrfs (needed for the snapshot-rollback armor in Stage 3)	whole.md: plain ext4	Run lsblk -f / findmnt /. If it's ext4, the Btrfs snapshot-armor design in Stage 3 doesn't work as written — you'd need LVM snapshots or Timeshift/rsync-based rollback instead.
Dual-boot partner	Master Context: Windows partition, untouched	whole.md/world.md: Ubuntu recovery partition (ubendt), used as your disaster-recovery target	Run sudo blkid / check GRUB entries. This changes what "don't touch this partition" means in every GRUB step of Stage 5.
Hostname / node name	g0pi (Master Context)	friday-host (whole/world/jarvis docs)	Pick one now — it gets hardcoded into IPC paths, logs, and (eventually) /etc/hostname.
IPC socket paths	/tmp/jarvis_ipc.sock	/var/run/jarvis-ipc.sock, /var/run/ultron.sock	Pick one convention (recommend /run/jarvis/*.sock — tmpfs, root-owned, survives nothing across reboot by design) and use it everywhere.
Free RAM budget	"emergency services MB" (garbled in 3 of the 6 docs)	daytoday/breakbown agree: ~900–911 MB free	Treat 900 MB as your real ceiling. Every phase's memory budget below is built off this number, not 7.4 GB.
Action: spend 20 minutes running lsblk -f, df -h, free -h, hostnamectl, blkid once, and write the actual answers into a single docs/GROUND_TRUTH.md. Every agent and every future prompt references that file, not the six source docs, going forward.

One more structural note: your daytoday.md labels the AI-hive phase "PHASE 4" and the rebranding phase "PHASE 3" even though rebranding comes after the hive — a copy-paste numbering bug, not a real ordering. This roadmap uses your intended order (voice → hands → agents → hardening → rebrand), not the doc's numbering.

1. Product Vision
Turn the Omarchy 4 install on your HP 15s-fq5xxx into a sovereign, always-listening, voice-first personal operating system — a real Jarvis, not a chatbot in a terminal. It hears you, acts on the actual OS (windows, files, apps, code editor), and over time grows from "one assistant" into a small internal company of specialist agents with a security referee sitting between them and anything destructive. The cosmetic transformation — GRUB banner, /etc/os-release, hostname, boot splash — happens last, once the thing underneath actually works.

This is a distinct, OS-native track from your broader JARVIS work (React Native app, PersonaPlex voice layer, VPS-hosted Hermes, PWA for Android). Worth deciding explicitly whether this Omarchy build is a parallel experiment, a future backend for that app, or the thing that replaces it — but that's a call for later, not something this roadmap needs to resolve today.

The Five Laws (from your own docs — every stage below has to respect these)
Barge-in < 25ms — if you talk while it's talking, it shuts up via RMS energy detection + SIGKILL on the playback process, not a graceful fade.
Flash execution < 3s locally — routine OS tasks never touch the network; they run through compiled native workers.
The 3-second hand-off — anything that would take longer gets one spoken acknowledgment, then drops to a background queue and frees the voice channel.
Anti-stale data law — prices, weather, scores, thermals: never answered from memory or training weights, always fetched live.
Core affinity + memory ceiling — interactive stuff (voice, Hyprland, HUD) owns the 2 performance cores; agents live on the 8 efficient cores; no local LLM weights ever load into RAM — everything reasons in the cloud, the laptop just orchestrates.
How this actually gets built
You've said you're building engineering judgment, not writing code by hand — you direct AI coding agents and review what they produce. That's exactly how to run this: each stage below is written as a spec you hand to a coding agent (Claude Code is a reasonable default for this bootstrapping phase, since it can work directly in your Omarchy filesystem; Prime/agy becomes the in-system coding agent later, once Jarvis OS exists and needs its own ongoing dev agent). Your job at each stage is the same three things: write the spec, review the diff against the exit criteria below, and decide whether to advance or harden further.

2. The Five Build Stages
STAGE 1          STAGE 2          STAGE 3                 STAGE 4              STAGE 5
Voice        →   Hands        →   Single agent         →  Continuous       →   Rebrand
(hear/speak)     (control OS)     → multi-agent             hardening           (cosmetic,
                                  (Ultron→Friday→                (loop,             last)
                                   Hermes→Prime)               not a sprint)
STAGE 1 — VOICE: Give It a Voice
Objective: Jarvis can hear you, think, and speak back, with real-time interruption. No OS control yet — this stage is purely the ears/mouth.

What ships

Mic capture: pw-record --raw --rate 16000 --channels 1 --format s16 -, chunked at 512 samples.
Speaker out: pw-play --raw --rate 24000 --channels 1 --format s16 -.
Cloud reasoning/speech: Gemini Live WebSocket as primary, with a KeyPool router underneath (round-robin across comma-separated keys, exponential 429 backoff: cooldown = min(1000 × 2^f, 900000)ms) so a rate limit never kills the session — Groq and OpenRouter as tertiary/quaternary fallback.
Barge-in: RMS threshold 0.015 on incoming mic chunks; if it fires while isSpeaking === true, kill pw-play and reset state in under 25ms.
Two synthesized chimes (ascending D5→A5 on activate, descending A5→A4 on standby) — no MP3 decode latency.
One atomic state file (/run/jarvis/state.json, written via tmp-file + rename) that anything else on the system can read reactively.
A systemd unit (jarvis-core.service, Restart=always) so it survives crashes and reboots.
Build order

Confirm mic device via arecord -l, lock capture to mono 16kHz.
Async capture loop → WebSocket streaming pipe to Gemini Live.
KeyPool + cooldown logic, with keys injected via systemd environment, never hardcoded.
Downstream text/audio receiver + the RMS barge-in interrupt.
Chime synthesis (pure math, no audio files).
Atomic state file writer + systemd unit + crash-restart test.
Exit criteria (don't move on until all true)

You can hold a real back-and-forth spoken conversation with no push-to-talk button.
Talking over it stops playback in a way that feels instant, not just "fast."
Killing the process and rebooting brings it back on its own.
Idle RAM footprint stays under ~150 MB (your real budget is ~900 MB free — leave headroom for Stage 2's workers).
STAGE 2 — HANDS: Give It Control of the Whole OS
Objective: the one agent (still just Jarvis, no hive yet) can act on the desktop directly — windows, apps, editor, clipboard — fast, and safely.

What ships

The native worker layer: small, single-purpose C++17 binaries (-O3), each emitting one line of JSON, each targeting ≤5ms. Pull the 18 from Master Context §10.1, but before writing any of them, sort each into a tier:
Tier 1 (pre-approved, instant): sys_telemetry, thermal_scan, storage_scan, pc_spec, media_ctrl, desktop_control, hardware_ctrl (volume/brightness), open_app, file_search, net_inspector, wifi_scan, vision_ctrl (capability check only).
Tier 2 (needs a human gate — even before Ultron exists, this means "ask you directly," not "run silently"): process_ctrl (kill/renice), service_ctrl (systemd), firewall_audit, jarvis_sysctl, memory_tester. These touch things that can take the machine down; don't let Stage 2 auto-approve them just because Ultron isn't built yet.
Hyprland actuation via its IPC socket: focus, tiling, workspace switching.
Keyboard/mouse injection (wtype/ydotool) with Bezier-spline cursor motion — natural acceleration curves, not teleport-and-click.
Neovim buffer hooks (keystroke-level, not visual indexing — stays fast).
Clipboard read/write hooks into Omarchy's native clipboard manager.
The 576-hotkey ledger, as a static lookup table Jarvis can query.
A lightweight default perception channel: text/scrollback extraction from the active terminal (omarchy-cmd-ocr or raw buffer dump) so Jarvis knows what's on screen without touching the GPU video pipeline yet — that comes in Stage 4.
Build order

Write and bench each of the 18 workers against its own latency target; confirm the ≤5ms budget for real, not just in the docs.
Wire Hyprland IPC actuation + test tiling/focus/workspace commands end to end.
Bezier cursor engine + keystroke injector; verify natural-looking motion (this also matters for not tripping bot-detection heuristics in any app you interact with).
Neovim + clipboard hooks.
Terminal scrollback/text-context reader as the default "eyes."
Wire the 3-second rule: anything crossing 3s gets the "Routing intent downstream, Sir" hand-off and drops to the IPC queue — even though there's no background agent to receive it yet. Build the queue now so Stage 3 just plugs into it.
Exit criteria

You can say "split the terminal, open the code editor, turn the volume down, tell me what's on screen" and it happens, hands-free, sub-3-seconds for each.
A Tier 2 command (e.g. "kill this process") correctly stops and asks you directly — it does not execute silently just because Ultron doesn't exist yet.
The IPC queue accepts a task payload and does nothing with it yet (that's expected — Stage 3 builds the receiver).
STAGE 3 — Single Agent → Multi-Agent: The Corporate Matrix
Objective: split growing responsibility across the specialist agents. Build order matters here more than the docs suggest — bring the referee online before the agent that can actually cause damage.

Recommended order (not the docs' order):

Ultron / OpenClaw (security referee) — first. Why first: the moment any agent can write files, run scripts, or touch system config, you need the gate that intercepts privileged actions before that agent's first real action, not after an incident. Build:

Persistent daemon on /run/jarvis/ultron.sock (per your Stage 0 path decision).
Namespace isolation for anything spawned by a worker/agent.
Telegram out-of-band 2FA: intercept → freeze → push ticket (agent, action, command hash) → wait for approve/deny → log to /var/log/jarvis_audit.log.
Snapshot-armor rollback — implementation depends on your Stage 0 filesystem finding: btrfs subvolume snapshot if you're actually on Btrfs, otherwise substitute LVM snapshots or a scoped rsync backup before any Tier 2 action.
Post-panic forensics: coredumpctl → structured JSON (culprit, signal, line) → handed to Friday.
Retrofit Stage 2's Tier 2 workers to route through Ultron now, replacing the "ask you directly" placeholder.
Friday (systems intelligence / successor) — second.

Background telemetry + proactive workflow automation (pre-fetch/pre-build patterns you repeat).
Isolated sandbox lab (chroot/systemd-nspawn) for testing optimization scripts before they touch the live system.
The successor/hot-swap: a synchronized mirror of Jarvis's active context, so a crash doesn't mean starting cold.
3AM memory ledger cron: raw logs → SOP extraction → compressed Markdown.
Hermes (research/vault) — third.

Scoped web research worker, Obsidian vault indexing, sub-agent spawning for deep multi-turn research tasks Jarvis hands off via the IPC queue.
Prime (software engineer via Antigravity/agy) — last, and deliberately last.

This is the agent that writes and executes code changes to your actual system. Only bring it online once Ultron has been exercised — i.e. you've watched it correctly intercept and gate at least one real Tier 2 action — not just built.
Cloud-side subagent spawning for multi-file work, TDD loop against your make/compiler output, clean git diffs surfaced back to Jarvis's UI.
Build order (within this stage)

Ultron daemon + Telegram flow + snapshot armor → test with a deliberately harmless "privileged" action to confirm the full loop.
Retrofit Stage 2's Tier 2 workers through Ultron.
Friday: telemetry loop, sandbox, hot-swap, nightly ledger.
Hermes: research delegation via the IPC queue built in Stage 2.
Prime: only after step 1 has been proven end-to-end at least once.
Exit criteria

A real Tier 2 action (e.g. a package install) freezes, sends a Telegram ticket, and only proceeds on your approval — with a full audit log entry.
A >3s task spoken to Jarvis is handed off, executed by the right specialist in the background, and reported back without holding the voice channel open the whole time.
If you kill the main Jarvis process, Friday's hot-swap keeps basic function alive.
STAGE 4 — Continuous Hardening (a loop, not a single sprint)
This isn't a stage you "finish" — it's the backlog you cycle through once Stages 1–3 are solid and stable in daily use. Pull from it in whatever order actually matters to you:

GPU vision spike: VA-API-accelerated 3-second screen capture, triggered only by explicit spatial commands ("look at this," "target that button"), 0% CPU/RAM when idle.
Quickshell Orbit HUD: the layered rotating status widget, color-state machine (green/amber/cyan/grey/red) reflecting Jarvis's actual state file.
Full test harness: the 226-target matrix (unit → tier1 features → boundary conditions → pairwise interactions → real-world workload tests) — build this incrementally as each stage lands, not all at once at the end.
Memory/entity extraction: the regex heuristic layer for names, locations, unit preferences, active-repo tracking — nice-to-have, not blocking.
Thermal/perf tuning: sysctl tweaks, core-affinity verification under real multi-agent load.
Treat this stage as "always open" rather than something with an exit criterion.

STAGE 5 — Rebrand: Omarchy 4 → Jarvis OS (Last, Cosmetic Only)
Objective: make it look like your OS, now that it is your OS underneath. Deliberately last — renaming system identity early makes every earlier debugging step harder for no functional benefit.

What ships

GRUB: /etc/default/grub → distributor string (pick one wording from Stage 0's reconciliation, e.g. "Jarvis OS [Core Integration Partition]"), 2-second timeout, verify your actual dual-boot partner is untouched (Stage 0 resolves whether that's Windows or ubendt).
Identity: /etc/os-release, /etc/issue → NAME="Jarvis OS", ID=jarvis-os, ID_LIKE=arch (keeps pacman compatibility).
Hostname → whatever Stage 0 decided.
Terminal welcome banner in ~/.bashrc for foot sessions — live telemetry/agent-status ASCII HUD.
Neovim startup dashboard — active project tracks, recent edits, Friday's long-term memory log.
Login voice greeting via hardware-accelerated audio.
Exit criteria

Fresh boot shows Jarvis OS branding end to end (GRUB → login → terminal → editor) with zero regression to anything built in Stages 1–4.
pacman, package installs, and your dual-boot partner all still work exactly as before.
3. Cross-Stage Guardrails (apply throughout, not just at the end)
Guardrail	Rule
RAM	~900 MB is your real ceiling. Track cumulative footprint after every stage, not just at Stage 1.
Local model weights	Never. Every reasoning call goes to cloud (Gemini/Groq/OpenRouter/Claude) — the laptop only orchestrates.
Privilege	Anything touching sudo, /etc, partitions, firewall, or package management is Tier 2 from Stage 2 onward, gated by Ultron from Stage 3 onward — never "temporarily allowed" while a stage is incomplete.
Testing	Don't defer all 226 tests to the end — write each stage's relevant subset as that stage lands.
Docs	Keep docs/GROUND_TRUTH.md (from Stage 0) as the single source of truth; update it, don't let the six original docs drift back into being "the spec."
4. This Week: Concrete Next Actions
Run the five verification commands in §0 and write docs/GROUND_TRUTH.md.
Pick your canonical IPC path convention and hostname — one line each in that same file.
Start Stage 1, Day 1: confirm mic hardware via arecord -l.
Hand Stage 1's spec (§Stage 1 above) to your coding agent as its first task; review the resulting capture pipeline against the exit criteria before moving to KeyPool/barge-in.