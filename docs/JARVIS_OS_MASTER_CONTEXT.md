# J.A.R.V.I.S. OS — MASTER ARCHITECTURE & CONTEXT BLUEPRINT

> **Sovereign, Voice-First Autonomous AI Operating System**  
> **Document Version**: 2.0.0 (Master Release — Fully Comprehensive)  
> **Host Platform**: Arch Linux x86_64 | Omarchy 4.0.3 | Kernel 7.2.3-arch1-3 PREEMPT_DYNAMIC | GCC 16.2.1  
> **Compositor**: Hyprland 0.56.2 (Wayland) | Audio: PipeWire 1.6.8 + WirePlumber  
> **Hardware Node**: HP Laptop 15s-fq5xxx (`g0pi`) | Intel Core i5-1235U (Alder Lake, 2P + 8E, 12 Threads)  
> **Operator**: Gopi (*"Sir"*)  
> **Primary Voice Persona**: `Zephyr` (British Received Pronunciation, Tactical, Concise, Articulate)  
> **GitHub Repository**: `https://github.com/Jarvis-os-tech/JARVIS-OS`  

---

## TABLE OF CONTENTS
1. [Executive Vision & Core Operational Invariants](#1-executive-vision--core-operational-invariants)
2. [Real Hardware Baseline & Platform Ground Truth](#2-real-hardware-baseline--platform-ground-truth)
3. [The 5-Agent Specialist Corporate Matrix](#3-the-5-agent-specialist-corporate-matrix)
4. [Dual-Tier Security, Ultron Intercept & Btrfs Armor](#4-dual-tier-security-ultron-intercept--btrfs-armor)
5. [Multi-Provider KeyPool & Fault-Tolerant Router](#5-multi-provider-keypool--fault-tolerant-router)
6. [Native Audio Pipeline (PipeWire Low-Latency Engine)](#6-native-audio-pipeline-pipewire-low-latency-engine)
7. [Gemini Live Speech Engine & Prosody Optimization](#7-gemini-live-speech-engine--prosody-optimization)
8. [Parallel Google Search Grounding & Real-Time Facts](#8-parallel-google-search-grounding--real-time-facts)
9. [Sub-1ms Regex Heuristic Memory & Anti-Stale Data Law](#9-sub-1ms-regex-heuristic-memory--anti-stale-data-law)
10. [Desktop & Hardware Actuation Layer (18 C++17 Workers & Tools)](#10-desktop--hardware-actuation-layer-18-c17-workers--tools)
11. [Hardware-Accelerated Vision Pipeline (Intel VA-API)](#11-hardware-accelerated-vision-pipeline-intel-va-api)
12. [Dual IPC Mechanism & State Synchronization](#12-dual-ipc-mechanism--state-synchronization)
13. [Native Wayland Layer-Shell Orbit HUD (Quickshell Qt6)](#13-native-wayland-layer-shell-orbit-hud-quickshell-qt6)
14. [System Rebranding & Desktop Immersion Pipeline](#14-system-rebranding--desktop-immersion-pipeline)
15. [Master Orchestrator Daemon & Lifecycle Management](#15-master-orchestrator-daemon--lifecycle-management)
16. [Booting, CLI Control & System Commands (run.sh)](#16-booting-cli-control--system-commands-runsh)
17. [Multi-Tier Test Harness & Quality Verification Matrix](#17-multi-tier-test-harness--quality-verification-matrix)
18. [Directory Layout & File Structure Reference](#18-directory-layout--file-structure-reference)

---

## 1. EXECUTIVE VISION & CORE OPERATIONAL INVARIANTS

J.A.R.V.I.S. OS transforms a standard Arch Linux / Omarchy workstation into a fully autonomous, voice-driven cognitive operating system. Rather than relying on cloud-mediated push-to-talk delays, heavy browser wrappers (Electron), or sandboxed web views, J.A.R.V.I.S. OS integrates directly against the Linux kernel, Wayland compositor, and PipeWire audio server.

### The Five Inviolable Operational Laws:

1. **Sub-50ms Instant Barge-In Interruption**: Whenever Gopi begins speaking while J.A.R.V.I.S. is outputting speech, audio playback terminates in **under 25 milliseconds** via real-time Root Mean Square (RMS) energy detection and an immediate `SIGKILL` sent to the active `pw-play` process.
2. **Sub-3-Second Flash Execution (Local Actuation)**: Common operating system tasks (tiling windows, adjusting volume/brightness, switching workspaces, querying thermals, killing processes) execute directly through native compiled C++17 binaries in **under 5 milliseconds** without cloud round-trip delay.
3. **The 3-Second Hand-Off Protocol (Background Delegation)**:
   * **$\le$ 3 Seconds**: Executed immediately in-process on screen.
   * **> 3 Seconds** (multi-file refactoring, deep compilation, massive web crawling):
     1. J.A.R.V.I.S. speaks an immediate millisecond confirmation: *"Routing intent downstream, Sir."*
     2. Serializes the task payload into a structured JSON packet onto `/tmp/jarvis_ipc.sock`.
     3. Immediately severs the active Gemini Live voice WebSocket channel back to low-power standby mode.
     4. Delegates processing to background agents (**F.R.I.D.A.Y.**, **Hermes**, **Prime**) running on Intel Efficient Cores.
4. **Anti-Stale Data Law**: No dynamic or real-time metric (cryptocurrency valuations, stock market prices, live weather, sports scores, system thermals) may ever be answered from static LLM training weights or conversational cache. Real-time queries automatically invoke parallel Google Search Grounding or native C++ telemetry workers.
5. **Asymmetric Core Affinity & Memory Safeguard**:
   * Performance Cores (0–1) are strictly reserved for Gopi's interactive desktop, Hyprland, Quickshell HUD, and real-time audio.
   * Efficient Cores (2–9) host background Docker sandboxes and agent routines.
   * Total background orchestrator daemon memory footprint must remain strictly **under 200 MB RAM**. **Zero local LLM weights** may ever be loaded into physical RAM.

---

## 2. REAL HARDWARE BASELINE & PLATFORM GROUND TRUTH

All system engineering decisions, memory bounds, and execution paths are calibrated directly to the verified hardware topology of `g0pi`:

| Subsystem | Hardware Specification | Architectural Allocation & Constraints |
| :--- | :--- | :--- |
| **Model & Board** | HP Laptop 15s-fq5xxx (SKU 6P129PA#ACJ), Board HP 8A20 | Chassis: Laptop, AMI BIOS F.22 (Apr 2024), UEFI Bare Metal. |
| **CPU Silicon** | 12th Gen Intel Core i5-1235U (Alder Lake-UP3) | 10 Cores / 12 Threads (2 Performance Cores + 8 Efficient Cores), Boost to 4.4 GHz. VT-x enabled. |
| **Volatile Memory** | 7.4 GiB Physical RAM + **7.4 GiB zram** (15.5 GB total virtual pool) | 3.4 GiB dynamic available. Prevents OOM locks. High headroom for compiled C++ workers and PipeWire buffers. |
| **Storage Node** | Samsung PM9B1 NVMe 476.9 GB | Partition 4: 255 GB **LUKS-encrypted Btrfs** (`/`, `/home`, `/var/log`). Partition 1: 218.9 GB Windows/Data (untouched). |
| **GPU / Display** | Integrated Intel Iris Xe Graphics (Alder Lake-UP3 GT2, `i915`) | VA-API hardware video acceleration (`/dev/dri/renderD128`). Resolution: 1920x1080 @ 60Hz. |
| **Audio Stack** | Intel Alder Lake PCH HD Audio | PipeWire 1.6.8 + WirePlumber + PipeWire-Pulse audio server graph. |
| **Compositor & Shell** | Hyprland 0.56.2 (Wayland) + `foot` terminal | Native Wayland Layer-Shell overlay via Quickshell Qt6 (`orbit.qml`). Input: `fcitx5`. |
| **Security Subsystem** | OpenClaw 2026.9.4 + Active Telegram Channel | Loopback token authentication gateway, zero plaintext credentials, out-of-band mobile 2FA authorization. |
| **Container Engine** | Docker 29.7.2 + compose + lazydocker | Worker sandbox isolation pinned to Intel Efficient Cores (`cpuset="4-11"`). |

---

## 3. THE 5-AGENT SPECIALIST CORPORATE MATRIX

J.A.R.V.I.S. OS operates under an integrated corporate hierarchy, passing down execution payloads:

```
                  ┌─────────────────────────────────────────┐
                  │        👑 J.A.R.V.I.S.                  │
                  │     (CEO & Flash Orchestrator)          │
                  └────────────────────┬────────────────────┘
                                       │ (IPC Bus: /tmp/jarvis_ipc.sock)
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
┌─────────────────────┐       ┌─────────────────────┐       ┌─────────────────────┐
│   🔧 F.R.I.D.A.Y.   │       │  🛡️ ULTRON / OPENCLAW│       │   🤖 HERMES         │
│ (Systems Intel &    │       │ (Security Gateway & │       │ (Deep Research &    │
│  Successor Brain)   │       │   Referee)          │       │  Vault Indexing)    │
└─────────────────────┘       └─────────────────────┘       └─────────────────────┘
                                                                       │
                                                                       ▼
                                                            ┌─────────────────────┐
                                                            │   💻 PRIME AGENT    │
                                                            │ (Software Eng.      │
                                                            │  via Antigravity)   │
                                                            └─────────────────────┘
```

### Detailed Agent Profiles:

| Agent | Core Identity | Primary Responsibility | Tool / System Access | Interaction Model |
| :--- | :--- | :--- | :--- | :--- |
| **👑 Jarvis** | **CEO & Flash Orchestrator** | Voice/vision UI, sub-3s actuation, routine approvals, user liaison. | PipeWire, Hyprland, C++ Workers, Gemini Live. | **Direct** (Voice/Vision/UI) |
| **🔧 Friday** | **Systems Intelligence** | Background workflow analysis, OS kernel tuning, memory optimization, updates, backup failover. | Systemd, Kernel sysctl, Telemetry, Docker. | **Proactive** (Background Daemon) |
| **🛡️ Ultron / OpenClaw** | **Security & Referee** | Permission gatekeeper, crash forensics, agent audit, critical task authorization. | Sudo elevation, Kernel logs, Firewall, Btrfs snapshots, Telegram. | **Referee** (Event Interceptor) |
| **🤖 Hermes** | **Worker Specialist** | Multi-turn deep research, retrieval, documentation, Obsidian vault syncing, sub-agent spawning. | Scoped Web, Obsidian Vault, SQLite, APIs. | **Delegated** (Deep Work Queue) |
| **💻 Prime** | **Software Engineer** | Codebase refactoring, compilation, test-driven debugging, git workflows, package builds. | Local Git repos, Compilers, Linter, Test Runners, Antigravity CLI. | **Delegated** (Autonomous Dev) |

### Embedded Operator Protocols:
* **576 System Shortcut Ledger**: Jarvis maintains a mathematical mapping of all system hotkeys, window configuration layout coordinates, macro binds, and shell parameters natively.
* **Neovim Editor Buffer Integration**: Binds natively to active text editor workflows. Tracks lines, indents characters, manages repository paths, and manipulates Neovim buffer splits entirely via voice.
* **Organic Bezier Cursor Splines**: For Computer Use Automation (CUA), the cursor does not teleport or move linearly; it moves dynamically using Cubic Bezier Splines with natural acceleration and deceleration curves, preventing bot detection and ensuring natural graphical interactions.

---

## 4. DUAL-TIER SECURITY, ULTRON INTERCEPT & BTRFS ARMOR

### 4.1 Tier 1: Routine Task Matrix (Jarvis Pre-Approved, < 3s)
* Operations pre-authorized for instant execution without human elevation:
  * Window focus, workspace movement, tiling splits, window minimization.
  * Display brightness adjustments, audio volume level modification, mute toggling.
  * Read-only system queries (`sys_telemetry`, `thermal_scan`, `pc_spec`, `storage_scan`).
  * Standard media controls (play, pause, skip, track query via MPRIS).
  * Launching desktop applications (`foot`, `firefox`, `nautilus`, `code`).

### 4.2 Tier 2: User-Critical Task Matrix (Ultron / OpenClaw Enforcement)
* Destructive, privileged, or network-sensitive actions require explicit human elevation:
  * Any command invoking `sudo` or modifying `/etc`, `/usr`, or systemd root units.
  * Disk formatting, partition resizing, filesystem deletion (`rm -rf`).
  * Firewall modifications (`ufw allow`, `iptables` rules).
  * Package installations and uninstalls (`pacman -S`, `pacman -R`).

### 4.3 Out-of-Band Telegram 2FA Intercept Flow:
1. Agent generates a Tier 2 privileged action.
2. Ultron intercepts the call via loopback socket and freezes the execution and CUA loop.
3. Ultron dispatches a cryptographic authorization ticket to Gopi's phone via Telegram:
   ```
   🛡️ ULTRON SECURITY INTERCEPT
   Agent: Prime
   Action: Execute privileged command
   Command: pacman -Syu --noconfirm
   Hash: a8f9c2e4...
   [ APPROVE ]   [ DENY ]
   ```
4. The process remains frozen until verified by physical phone tap or unique voice biometric confirmation.
5. Verification token, timestamp, command hash, and executing agent ID are logged to `/var/log/jarvis_audit.log`.

### 4.4 Pre-Execution Btrfs Snapshot Armor:
Prior to executing any approved Tier 2 modification:
```bash
SNAPSHOT_ID="pre-agent-$(date +%s)"
btrfs subvolume snapshot / "/.snapshots/${SNAPSHOT_ID}"
```
If post-execution diagnostics fail or system instability is detected within 10 seconds, Ultron restores the snapshot in **under 500 milliseconds**.

### 4.5 Post-Panic Forensics & Autonomous Self-Healing:
If an agent script crashes or causes a segmentation fault:
1. Ultron intercepts the kernel coredump / journal log via `coredumpctl`.
2. Extracts the faulting instruction pointer, script name, and exact line number into structured JSON:
   ```json
   {
     "culprit": "worker_script.py",
     "signal": "SIGSEGV",
     "stack": "line 42: in execute_payload",
     "timestamp": 1726421800
   }
   ```
3. Passes the clean diagnostic trace to F.R.I.D.A.Y.
4. F.R.I.D.A.Y. spins up an isolated Docker container on the E-cores to reproduce, debug, and patch the code before requesting clearance to re-deploy.

---

## 5. MULTI-PROVIDER KEYPOOL & FAULT-TOLERANT ROUTER

The LLM routing subsystem guarantees high availability and zero rate-limit downtime:

### 5.1 KeyPool Architecture (`src/router/keyPool.ts`):
* Ingests comma-separated API keys from environment variables:
  * `GEMINI_API_KEYS` (with fallback to `GEMINI_API_KEY`)
  * `GROQ_API_KEYS` (with fallback to `GROQ_API_KEY`)
  * `OPENROUTER_API_KEYS` (with fallback to `OPENROUTER_API_KEY`)
* Implements Round-Robin / Least-Recently-Used (LRU) key rotation among healthy keys.

### 5.2 Exponential 429 Cooldown Mathematics:
When any API endpoint returns HTTP 429 (`RESOURCE_EXHAUSTED` / rate limit):
$$\text{Cooldown}(f) = \min\left(1000 \times 2^{f}, 900000\right)\text{ ms} \quad (15\text{ mins max})$$
where $f$ is the consecutive failure count per key. The exhausted key is quarantined, and the next healthy key is activated in **< 200 ms**.

### 5.3 4-Tier Provider Cascade:
1. **Primary**: Google Gemini 2.0 Flash Live Preview (Bidirectional low-latency voice WebSocket).
2. **Secondary**: Gemini 2.5 Flash REST API (Parallel search grounding, complex reasoning, structured tool calls).
3. **Tertiary**: Groq LLaMA 3.3 70B Versatile (Sub-200ms ultra-fast inference).
4. **Quaternary**: OpenRouter Multi-Model Gateway (Ultimate global fallback).

---

## 6. NATIVE AUDIO PIPELINE (PIPEWIRE LOW-LATENCY ENGINE)

Interfaces directly with Arch Linux's PipeWire audio server without browser or Web Audio overhead:

### 6.1 Stream Specifications:
* **Microphone Capture**:
  * Command: `pw-record --raw --rate 16000 --channels 1 --format s16 -`
  * Format: 16kHz, 1-channel Mono, 16-bit Signed Integer Little-Endian Linear PCM (`s16le`).
  * Chunk Buffer: 512 samples.
* **Speaker Playback**:
  * Command: `pw-play --raw --rate 24000 --channels 1 --format s16 -`
  * Format: 24kHz, 1-channel Mono, 16-bit Signed Integer Little-Endian Linear PCM (`s16le`).

### 6.2 Voice Activity Detection (VAD) & Instant Barge-In:
* Real-time Root Mean Square (RMS) energy calculation on each incoming 16kHz PCM chunk:
  $$\text{RMS} = \sqrt{\frac{1}{N}\sum_{i=1}^{N} x_i^2}$$
* Default VAD Threshold: `0.015`.
* **Instant Barge-In Interruption**:
  * If `RMS > 0.015` while J.A.R.V.I.S. is outputting speech (`isSpeaking === true`):
    1. Immediately terminates the active `pw-play` process with `SIGKILL`.
    2. Closes `pw-play` standard input and flushes playback buffers.
    3. Emits `bargeIn` event to master orchestrator.
    4. Resets `isSpeaking = false` in **under 25 milliseconds**.

### 6.3 Algorithmic Harmonic Chime Synthesis:
Synthesizes raw PCM audio waveforms on the fly without disk MP3/WAV decoding delay:
* **Activation Chime**: Ascending harmonic chord ($D_5 = 587.33\text{ Hz} \to A_5 = 880\text{ Hz}$).
* **Standby Chime**: Descending harmonic chord ($A_5 = 880\text{ Hz} \to A_4 = 440\text{ Hz}$).
* Envelope: Exponential decay: $A(t) = A_0 e^{-\lambda t} \sin(2\pi f t)$.

---

## 7. GEMINI LIVE SPEECH ENGINE & PROSODY OPTIMIZATION

Connects to Google Gen AI Live WebSocket endpoint (`/live`):

### 7.1 Live Session Configuration:
* Model: `gemini-2.0-flash-exp` (or `gemini-2.5-flash`).
* Response Modality: `[Modality.AUDIO]`.
* Voice Preset: `Zephyr` (British RP prosody, crisp pronunciation, tactical delivery).
* System Directives:
  1. Address Gopi as *"Sir"*.
  2. Maintain concise (1–3 sentences), direct tactical responses.
  3. Execute local tools immediately without asking confirmation on routine tasks.
  4. Enforce parallel live search grounding for facts and prices.
  5. Calmly confirm standby mode when requested (*"Standing by, Sir"*).

### 7.2 Speech Prosody Optimizer:
Summarizes raw web and tool outputs into spoken text suitable for natural vocalization:
* Strips Markdown asterisks, headers, bullets, and table pipes.
* Removes raw URLs, HTTP slugs, and citation anchors (e.g., `[1]`, `(source: ...)`).
* Normalizes numbers and currency symbols (e.g., `$50,000` $\to$ *"fifty thousand dollars"*).

---

## 8. PARALLEL GOOGLE SEARCH GROUNDING & REAL-TIME FACTS

Triggered whenever queries involve dynamic, real-time information:
* Live asset prices (Bitcoin, Ethereum, S&P 500, stock tickers).
* Live weather and forecasts.
* Breaking news, current date/time, live sports scores.

### Execution Mechanism:
* Dispatches query in parallel to `gemini-2.5-flash` with Google Search tool enabled:
  ```json
  {
    "name": "search_realtime_information",
    "description": "Searches Google for live facts, current prices, weather, sports scores, and real-time information.",
    "parameters": {
      "type": "OBJECT",
      "properties": {
        "query": { "type": "STRING", "description": "The specific real-time search query." }
      },
      "required": ["query"]
    }
  }
  ```
* Output is piped through the Prosody Optimizer and vocalized directly.

---

## 9. SUB-1MS REGEX HEURISTIC MEMORY & ANTI-STALE DATA LAW

Memory is managed with zero latency and high precision without database locks:

### 9.1 Sub-1ms Regex Entity Extraction:
Parses conversation streams in real time using compiled regular expressions:
```typescript
export const MemoryPatterns = {
  operatorName: /(?:call me|my name is|i am)\s+([A-Z][a-z0-9_-]+)/i,
  location: /(?:i am in|weather in|location is)\s+([A-Z][a-z\s]+)/i,
  unitsCelsius: /\b(celsius|metric|kmh|km\/h)\b/i,
  unitsFahrenheit: /\b(fahrenheit|imperial|mph)\b/i,
  activeRepo: /(?:working on|repo|project)\s+([a-zA-Z0-9_-]+)/i
};
```
Extracted entities are stored in runtime state and injected into the prompt context automatically.

### 9.2 Anti-Stale Data Law Enforcement:
Keywords: `price`, `weather`, `score`, `temp`, `thermal`, `news`, `crypto`, `btc`, `stock` are marked **non-cacheable**.
Memory engine strictly prohibits answering volatile queries from memory; fresh sensor or web grounding execution is mandatory.

---

## 10. DESKTOP & HARDWARE ACTUATION LAYER (18 C++17 WORKERS & TOOLS)

### 10.1 18 Native C++17 Hardware Workers
All binaries compile with `-O3 -std=c++17` into `controls/workers_cpp/bin/` and output strict single-line JSON with $\le$ 5ms latency:

1. `sys_telemetry` (~4ms): Direct parse of `/proc/stat`, `/proc/meminfo`, and `/sys/class/power_supply/`.
2. `thermal_scan` (~2ms): Scans all `/sys/class/thermal/thermal_zone*/temp` sensor nodes.
3. `hardware_ctrl` (~3ms): PulseAudio/PipeWire volume adjustment, mute toggle, backlight sysfs control.
4. `desktop_control` (~3ms): Unix socket connection to Hyprland IPC (`.socket.sock`). Tiling splits and focus.
5. `storage_scan` (~3ms): POSIX `statvfs()` scan across mounted filesystems.
6. `pc_spec` (~5ms): DMI table and CPUID hardware topology parser.
7. `media_ctrl` (~4ms): D-Bus interface to `org.mpris.MediaPlayer2`.
8. `file_search` (~12ms): Multi-threaded POSIX filesystem walker.
9. `firewall_audit` (~5ms): Audits active iptables and UFW rules.
10. `net_inspector` (~4ms): Inspects `/proc/net/dev`, active route tables, and default gateway ping metrics.
11. `open_app` (~2ms): Spawns applications via `uwsm-app` or `xdg-open` in detached namespaces.
12. `process_ctrl` (~3ms): Traverses `/proc/[pid]/stat`. Implements renice, `SIGTERM`, and `SIGKILL`.
13. `service_ctrl` (~4ms): Interacts with Systemd D-Bus interface (`org.freedesktop.systemd1`).
14. `vision_ctrl` (~4ms): Direct V4L2 `ioctl(VIDIOC_QUERYCAP)` camera scan and Wayland display check.
15. `wifi_scan` (~8ms): Netlink `nl80211` wireless interface query for SSID, signal strength, and bitrate.
16. `jarvis_sysctl` (~2ms): Queries and tunes kernel sysctl parameters.
17. `memory_tester` (~6ms): Diagnostic RAM allocator and swap pressure tester.
18. `desktop_ctrl` (~3ms): Secondary dispatch wrapper for Hyprland window tiling.

### 10.2 Desktop Automation Skills (`controls/omarchy/tools.py`):
* **Hyprland Window Management**: `hypr_query`, `hypr_dispatch` (focus, move, float, resize).
* **Keyboard & Input Simulation**: `send_shortcut`, `type_text` (via `wtype` / `ydotool`).
* **Terminal Scrollback Buffer**: Direct scrollback capture from `foot` / `tmux` sessions (100% accurate raw text, 0% CPU).
* **Neovim Editor Integration**: Automated indentation, line navigation, and buffer splits via socket keystrokes.

---

## 11. HARDWARE-ACCELERATED VISION PIPELINE (INTEL VA-API)

To prevent software rendering from consuming CPU cycles on screen capture:
* **Driver**: Intel Alder Lake-UP3 GT2 (`i915` kernel module).
* **Hardware Acceleration**: VA-API (`/dev/dri/renderD128`).
* **Default State (Channel 1 - 0% CPU, 0 MB RAM)**: Continuous video streaming is **completely disabled**. J.A.R.V.I.S. tracks active terminal windows by dumping raw scrollback text directly from window buffers.
* **The Dynamic 3-Second Visual Spike (Channel 2)**: Triggered exclusively on spatial voice commands (*"Look at this"*, *"Target that button"*):
  1. Unpauses the VA-API pipeline for a strict 3-second flash window:
     ```bash
     ffmpeg -loglevel error \
       -vaapi_device /dev/dri/renderD128 \
       -f kmsgrab -i - \
       -vf 'hwmap=derive_device=vaapi,scale_vaapi=w=1920:h=1080:format=nv12' \
       -c:v mjpeg_vaapi -q:v 85 \
       -frames:v 1 -f image2 pipe:1
     ```
  2. Pushes frames to Gemini Live, pinpoints UI coordinates, executes the click/drag macro via `wtype`/`ydotool`, and immediately terminates the process.

---

## 12. DUAL IPC MECHANISM & STATE SYNCHRONIZATION

### 12.1 Atomic State File (`/tmp/jarvis_state.json`)
Written atomically using the temporary file + `fs.renameSync()` pattern to eliminate partial read corruptions. Read reactively by Quickshell via `Quickshell.Io.FileView` in **< 1 millisecond**:
```json
{
  "status": "active",
  "text": "Online",
  "activeAgent": "jarvis",
  "audioLevel": 0.0,
  "telemetry": {
    "cpuUsage": 14,
    "ramUsage": 38,
    "tempC": 52,
    "batteryWh": 18.1
  },
  "position": { "x": 883, "y": 894 },
  "updated": 1726421500000
}
```

### 12.2 Full-Duplex Command Socket (`/tmp/jarvis_ipc.sock`)
A Unix Domain Socket handling JSON-RPC messaging between the master orchestrator daemon, Quickshell UI, and CLI scripts:
* `toggle_standby`: Switches between Active listening and Standby mode.
* `enter_standby` / `exit_standby`: Explicit mode control.
* `speak`: Instructs J.A.R.V.I.S. to vocalize a text payload.
* `get_state`: Returns current state snapshot.
* `delegate_task`: Dispatches long-running task to background agent queue.
* `request_elevation`: Dispatches Tier 2 security ticket to Ultron / Telegram.

---

## 13. NATIVE WAYLAND LAYER-SHELL ORBIT HUD (QUICKSHELL QT6)

The floating HUD (`Jarvis UI/orbit.qml`) runs natively on Quickshell 0.3.1:
* **Compositor Namespace**: `jarvis-orbit-hud` on `WlrLayershell.layer: WlrLayer.Overlay`.
* **Zero Input Masking**: Uses `mask: Region { item: hudContainer }` so only the circular 154x154px container intercepts clicks; all clicks outside pass through to desktop applications.
* **Draggable Anywhere**: Full-screen draggable controller with screen edge clamping (`drag.minimumX: 4`, `drag.maximumX: root.width - 158`).
* **Double-Click Docking**: Instantly docks back to bottom center of the display.
* **5 Concentric Rotating Cybernetic Layers**:
  1. *Outer Tactical Ring* (138px): Cardinal direction ticks and dual blue arcs (16s clockwise rotation).
  2. *Gyroscopic Satellite Ring* (110px): 3 orbiting white satellite nodes with glowing halos (8.5s counter-clockwise rotation).
  3. *Inner Fast Ring* (78px): High-speed purple dashed ring with 2 orbiting emerald dots (4.5s clockwise rotation).
  4. *Segmented Core Vanes* (46px): 6 cyan power vanes framing the reactor core (3.0s counter-clockwise rotation).
  5. *Arc Reactor Core Spark* (10px): Center breathing pulse spark.
* **Cybernetic Color State Machine**:
  * 🟢 **Active / Listening**: Emerald Green (`#10b981`) with 2000ms breathing pulse.
  * 🟡 **Thinking / Tool Run**: Amber Gold (`#f59e0b`) with rapid 600ms pulse.
  * 🔵 **Speaking**: Neon Cyan (`#00f0ff`) with 400ms audio reactive pulse.
  * ⚪ **Standby**: Slate Grey (`#64748b`) with dimmed opacity (0.5).
  * 🔴 **Critical / Elevation**: Crimson Red (`#ef4444`) strobe for pending Telegram 2FA tickets.

---

## 14. SYSTEM REBRANDING & DESKTOP IMMERSION PIPELINE

The final visual conversion transforming Omarchy 4 into the custom J.A.R.V.I.S. OS identity:

1. **GRUB 2.0 Bootloader**:
   * File: `/etc/default/grub`
   * Target String: `GRUB_DISTRIBUTOR="Jarvis OS [Core Integration Partition]"`
   * Selection Timer: `GRUB_TIMEOUT=2` (clean 2-second auto-boot).
   * Preserves Windows partition (`p1`) mapping cleanly without interference.
2. **OS Identity Definition**:
   * Target Files: `/etc/os-release` and `/etc/issue`
   * Target Keys: `NAME="Jarvis OS"`, `PRETTY_NAME="J.A.R.V.I.S. Autonomous Cognitive OS"`, `ID=jarvis-os`, `ID_LIKE=arch`.
   * Preserves underlying Arch Linux / pacman package manager compatibility.
3. **Terminal Welcome Splash Banner**:
   * Injected into `~/.bashrc` targeting `foot` terminal sessions.
   * Text-bound ASCII tactical HUD banner displaying live telemetry, agent status, and uptime in $< 10$ ms.
4. **Neovim Environment Integration**:
   * Startup dashboard embedding active project tracks, recent edits, and F.R.I.D.A.Y.'s long-term memory logs.
5. **Desktop Login Audio Greeting**:
   * Synthesizes and plays a lightweight vocal greeting upon Hyprland login:
     *"Good morning Sir. All background agent daemons are active and operational."*

---

## 15. MASTER ORCHESTRATOR DAEMON & LIFECYCLE MANAGEMENT

The master daemon (`jarvis/server.ts`) ties all hardware, audio, and network subsystems together:

### Lifecycle States:
* `active`: PipeWire microphone open, audio streaming to Gemini Live, speaker unmuted, full desktop actuation ready.
* `standby`: PipeWire microphone muted/gated, no audio streamed to network, speaker muted, Orbit HUD indicates Standby.
* `thinking`: Tool or search grounding execution in flight; Orbit HUD glows amber.
* `speaking`: Audio streaming from Gemini Live to speakers; barge-in listener armed; Orbit HUD glows cyan.
* `critical`: Tier 2 action intercepted; awaiting Telegram 2FA confirmation; Orbit HUD glows crimson.

### Persistent Keep-Alive & Telemetry Heartbeat:
* Runs an internal 5-second interval querying `sys_telemetry` via native C++ workers.
* Pushes live CPU usage, temperature, and RAM metrics into IPC state (`/tmp/jarvis_state.json`).
* Ensures the Node.js event loop remains active continuously without premature exit.

---

## 16. BOOTING, CLI CONTROL & SYSTEM COMMANDS (RUN.SH)

The master launcher (`run.sh`) controls J.A.R.V.I.S. OS execution:

```bash
# Unified Master Execution
./run.sh                  # Interactive Boot: runs Core Backend + Native Wayland Orbit HUD
./run.sh --daemon         # Background Mode: launches both as background daemons
./run.sh --status         # Display running PID, IPC socket status, and state JSON
./run.sh --stop           # Cleanly terminate daemon, audio processes, and Quickshell HUD

# Subsystem-Only Execution
./run.sh --core-only      # Launch Core Backend only (Node.js + PipeWire)
./run.sh --ui-only        # Launch Native Wayland Orbit HUD UI only

# Tactical CLI Controls
./run.sh speak "Hello"    # Vocalize text directly through J.A.R.V.I.S. speech engine
./run.sh toggle           # Toggle between Active listening and Standby mode
./run.sh screen           # Trigger a 3-second hardware-accelerated screen vision capture
./run.sh camera           # Trigger a webcam frame capture
./run.sh search "query"   # Execute parallel Google Search Grounding query
```

---

## 17. MULTI-TIER TEST HARNESS & QUALITY VERIFICATION MATRIX

The system verification harness comprises 226 automated test targets:

| Test Suite | File Scope | Tests | Target Verification |
| :--- | :--- | :--- | :--- |
| **Unit Tests** | `tests/unit/*.test.ts` | 49 | KeyPool LRU rotation, exponential cooldown, C++ binary execution, IPC sockets, Standby state machine. |
| **Tier 1 Features** | `tests/e2e/tier1_features/*.test.ts` | 68 | PipeWire capture/play, Gemini Live client, Search Grounding prosody, Memory extraction, Desktop actuation bridge. |
| **Tier 2 Boundaries** | `tests/e2e/tier2_boundaries/*.test.ts` | 24 | Boundary conditions: 0 RMS audio, clipping audio, screen coordinate clamping, negative parameters. |
| **Tier 3 Pairwise** | `tests/e2e/tier3_pairwise/*.test.ts` | 8 | Cross-feature interactions: barge-in during search response, key rotation during query, mouse drag during audio. |
| **Tier 4 Workloads** | `tests/e2e/tier4_workloads/*.test.ts` | 5 | End-to-end real-world workloads: morning briefing, software engineering workflow, market research, hardware diagnostics. |
| **TOTAL** | **All Suites** | **226** | **100% Pass Rate Target** |

---

## 18. DIRECTORY LAYOUT & FILE STRUCTURE REFERENCE

```
JARVIS-OS/
├── .env                              # API keys (GEMINI_API_KEY, GROQ_API_KEY, etc.)
├── run.sh                            # Sovereign Unified Master Launcher
├── JARVIS_OS_MASTER_CONTEXT.md       # [THIS FILE] Authoritative System Context Blueprint
│
├── docs/                             # Complete Specification & Governance Suite
│   ├── PRD.md                        # Product Requirements Document (v1.1.0)
│   ├── TRD.md                        # Technical Requirements Document (v1.1.0)
│   ├── ProjectOverview.md            # Developer Onboarding & Architecture Summary
│   ├── MASTER_CONTEXT.md             # Ground-Truth Master Context Blueprint
│   ├── UI-Context.md                 # Quickshell QML & Wayland Layer-Shell Specs
│   ├── Code-Standards.md             # C++17, TypeScript, Python, Shell Standards
│   ├── AI-Workflow-Rules.md          # Agent Governance & Prompting Rules
│   ├── WorkStructure.md              # Sprint Workstreams & Module Boundaries
│   └── Progress-Tracker.md           # Live Implementation Milestone Checklist
│
├── jarvis/                           # Core Backend & Intelligent Voice System
│   ├── server.ts                     # Express + Gemini Live WebSocket server (:3000)
│   ├── package.json                  # Node.js dependencies (@google/genai, ws, express)
│   ├── system_modules/
│   │   ├── intelligent_system/       # Personas, memory engine, workspace tools
│   │   └── voice_latency/            # Audio queue player, processor, low-latency streaming
│   └── src/                          # Memory, greeting, and authentication utilities
│
├── Jarvis UI/                        # Native Wayland Orbit HUD (Quickshell Qt6)
│   ├── orbit.qml                     # Draggable cybernetic rotating HUD overlay
│   ├── run.sh                        # Standalone HUD runner
│   └── README.md                     # UI widget documentation
│
├── controls/                         # Native Actuation & System Drivers
│   ├── workers_cpp/                  # 18 compiled C++17 native workers (-O3)
│   │   ├── Makefile                  # C++ build script
    │   ├── bin/                      # Compiled standalone executable binaries
│   │   └── src/*.cpp                 # High-speed telemetry, window, and audio sources
│   └── omarchy/                      # Desktop automation tools & connectors
│       ├── tools.py                  # Hyprland, foot, and clipboard wrappers
│       ├── capabilities.py           # Actuation capability registry
│       └── omarchy_skills_connector.py # Python JSON-RPC desktop bridge
│
└── .memory/                          # Runtime working directory
    ├── state.json                    # Atomic system state file
    └── jarvis_os.log                 # Daemon execution and error logs
```

---
*Document prepared for Gopi ("Sir") — Sovereign J.A.R.V.I.S. OS Master Blueprint.*
