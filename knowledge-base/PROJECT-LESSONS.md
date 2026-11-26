# Project lessons

## 2026-11-04 — Keep memory layers and vault organization distinct from inferred knowledge

Outcome: installed a six-layer memory manager, typed user memories, scoped recall/replacement/forgetting, dated event and procedure records, and a separate organized Obsidian vault. Preserved 2,530 conversation messages and 334 historical agent notes. Removed 2,184 generated topic notes from the active vault by replacing the legacy export with six numbered sections; a repeat sync created no changes and all managed links resolved. Previous vault folders and generated clutter were moved to Trash, with database/configuration backups retained.

Lesson: conversation history, user instructions, current facts, procedures and shared-agent proposals need separate authority and lifecycle rules. Do not fabricate personal facts to fill empty folders or claim user-described procedures are verified. Keep ephemeral working context out of the vault. Fix the exporter as well as the files so cleanup persists. Preserve a deliberately stopped voice service during an offline-certified release update.

Sources: `docs/organized-memory-system.md`, `jarvis_memory/manager.py`, `jarvis_memory/categories.py`, `jarvis_memory/vault_layout.py`, `tests/test_memory/test_organized_memory.py`. Installed checks: 172 memory tests plus 81 subtests and 167 required behavior checks. Voice endpoint/microphone acceptance remains unclaimed while the service is stopped.

## 2026-11-04 — Evaluate memory ranking without confusing fixtures with model quality

Outcome: built an isolated synthetic evaluation of lexical, vector, weighted and RRF retrieval with 16 query probes and nine passing lifecycle checks. Fixed-vector hybrid and RRF rankings tied; project-scoped entries could enter general recall, and no-answer probes returned topical passages. Read-only runtime status showed lexical retrieval active, semantic embeddings disabled, structured capture enabled and model extraction stopped. No live memories, retrieval configuration or UI were changed.

Lesson: evaluate answerable recall, forbidden-state leakage and answerability separately. A nonempty related passage is not evidence of an answer. Report fixed-vector experiments as ranking/integration probes, not embedding-model accuracy. Freeze a compatible baseline that records existing failures and detects new regressions; do not promote RRF merely because it is fashionable.

Sources: `docs/memory-quality-evaluation.md`, `jarvis_memory/evaluation.py`, `tests/fixtures/memory_quality/cases.json`, `JARVIS OS DOCS/MEMORY-QUALITY-EVIDENCE-2026-11-04.json`, `JARVIS OS DOCS/MEMORY-QUALITY-RUNTIME-STATUS-2026-11-04.json`.

## 2026-11-04 — Keep provider failures visible but silent

Outcome: journal correlation showed that the apparent second voice during Gemini failures was JARVIS's cached `reply_unavailable.pcm` fallback, not the system healer. Seven fallback clips were queued between 08:59:41 and 09:02:42 while the live session repeatedly failed its opening handshake. The shared reply-notice gate now suppresses both waiting and unavailable recordings while retaining `last_error`, status and journal evidence. Forty focused voice checks passed, and the restarted service reconnected to Gemini with microphone input available.

Lesson: failure reporting should not introduce a second voice that can overlap a recovering live provider. Keep transport failures observable in the UI and logs; reserve speech for the authoritative conversational response.

Sources: `voice_layer/daemon.py`, `tests/test_reply_guard.py`, user journal for `jarvis-voice.service` on 2026-11-04 08:59–09:09 IST.

## 2026-11-04 — Verify floating task cards through the compositor

Outcome: deployed the task-event release after 148 installed-environment checks. The shell required a restart to load the changed plugin after rescans kept serving its prior handler. A live temporary-file task produced a verified completed card, and the compositor reported visible floating widget layers. The test card and file were removed; the voice connection and previous system microphone mute were verified.

Lesson: a hidden main canvas does not mean floating cards are absent. Check the actual presentation surface, and wait for the replacement audio source before restoring its mute setting after a voice restart.

Sources: `scripts/prepare_task_events_release.py`, `scripts/deploy_task_events_release.py`, `JARVIS OS DOCS/TASK-EVENTS-DEPLOYMENT-2026-11-04.json`, `JARVIS OS DOCS/TASK-EVENTS-LIVE-CHECK-2026-11-04.json`.

## 2026-11-03 — Verify convergence reports against authoritative source paths

Outcome: review of the supplied dual-codebase report found current-source mismatches: the active JARVIS OS checkout already has the Island UI and PipeWire WebRTC AEC; OMA's native WebRTC wrapper enables gain while explicitly disabling AEC; current memory fusion uses a weighted blend; model-backed fact extraction already exists.

Lesson: before planning a package import or framework replacement, inspect the current entry point, implementation and configuration path. Track source presence, configured use, tested behavior and installed readiness separately. Compare improvements on the same held-out task set.

Sources: `ui/omarchy-jarvis-island/Island.qml`, `bin/jarvis-voice`, `voice_layer/echo.py`, `jarvis_memory/hybrid.py`, `jarvis_memory/extractor.py`, `jarvis_memory/bridge.py`; `/home/g0pi/Projects/JARVIS-OMA/audio/plugins/native/webrtc_gain.cpp`; [analysis](../JARVIS%20OS%20DOCS/INSTAGRAM-CAPABILITY-SYNTHESIS-2026-11-03.md).

Capture note: the requested `capture-learning` skill was not found in the available skill catalog or searched project paths. This dated, sourced entry records the outcome directly; no runtime learning rules were activated.

## 2026-11-03 — Select upstream mechanisms against existing capabilities

Outcome: the OpenVoiceOS/Huw Prosser review selected standalone number/date parsing and Fury's separated UI/tool/transcript, interruption and session concepts. Existing Vosk and Spotify connector references mean those upstream wrappers need a specific demonstrated gap. The old OVOS Piper plugin redirects to a successor; jarvis-mlx declares itself outdated and Apple-specific. Fury and Spotify CLI root listings did not establish a reuse license.

Lesson: check the current upstream README, dependency overlap, platform fit and licensing before importing an appealing assistant stack. Preserve source links and distinguish interface concepts from code approved for reuse.

Sources: [selection record](../JARVIS%20OS%20DOCS/SELECTIVE-UPSTREAM-REUSE-2026-11-03.md), [Piper migration](https://github.com/OpenVoiceOS/ovos-tts-plugin-piper), [Fury sessions](https://github.com/huwprosser/fury-sdk/blob/main/docs/sessions.md), [jarvis-mlx](https://github.com/huwprosser/jarvis-mlx).

## 2026-11-03 — Verify interfaces and dependency declarations after collection

Outcome: screened 431 repository entries and collected 12 licensed OVOS references. Static inspection found that the CueLight wrapper imports an EOT template absent from the collected plugin-manager source despite apparently sufficient version constraints. The date parser imports additional OVOS/calendar dependencies. The corrections plugin catches timeout exceptions without passing a timeout to its substitution call.

Lesson: a compatible-looking version number, standalone README description, or mocked timeout test is insufficient evidence for production adoption. Check actual imported symbols, dynamic dependency files and where execution is bounded. Keep experiments out of the live voice path until their specific contracts are demonstrated.

Source: [collection review and pinned evidence](../JARVIS%20OS%20DOCS/upstream-sources/2026-11-03/README.md). Verification checked source integrity and syntax only; no upstream runtime was installed or tested.

## 2026-11-03 — Preserve multimodal input when adding optional widgets

Outcome: restored the original JARVIS attachment bar after an optional text-only canvas field had taken over its adapter. Fixed close cleanup, missing voice-vision imports and missing-input error reporting; retained the prior installed release. Focused tests passed and the original 600 × 50 input window was verified through the running service. A user-approved screen-vision check produced fresh frames and restored off mode.

Lesson: an optional UI extension must preserve the existing entry point's capabilities, including attachments and cleanup. Test both the preferred and fallback paths, and distinguish local preview capture from cloud interpretation. Preserve standby/mute settings during deployment. Verify hardware through a host-visible channel; restricted `/dev` visibility is not proof that a webcam is absent.

Source: [repair and verification record](../JARVIS%20OS%20DOCS/INPUT-BAR-AND-VISION-REPAIR-2026-11-03.md), `skills/skills.py`, `voice_layer/daemon.py`, `voice_layer/ipc.py`, `tests/test_widget_canvas.py`, `tests/test_vision_runtime.py`.

## 2026-11-03 — Make behavior certification stricter than ordinary test success

Outcome: built eight named behavior contracts with 49 passing checks, required in CI and standard source-release builds. Seeded failures, skips, expected failures, missing cases and cleanup errors were rejected. The attachment contracts exposed binary audio being decoded as text; the source now forwards audio bytes with their media type. Twenty broader release checks also passed, with overlap in rollback coverage.

Lesson: a zero test-runner exit code alone is insufficient evidence that all required behaviors ran. Require complete per-case execution, fresh result evidence and a source fingerprint. Keep deterministic contracts separate from live device/provider acceptance, and state which release paths actually enforce the gate.

Sources: `scripts/behavior_gate.py`, `tests/behavior/contracts.json`, `tests/behavior/test_gate_enforcement.py`, `tests/behavior/test_multimodal_contracts.py`; [implementation and evidence](../JARVIS%20OS%20DOCS/BEHAVIOR-REGRESSION-GATE-2026-11-03.md). No live runtime release was changed during this outcome.

## 2026-11-03 — Treat parser output as evidence that needs domain validation

Outcome: integrated OVOS number/date spans into a bounded English pilot. Experiments found that number spans omit a spoken minus sign, date parsing guesses bare AM/PM, and relative-hour arithmetic can count wall time across DST. JARVIS now preserves signed source evidence, rejects ambiguous numeric controls and conflicting model arguments, flags unclear dates/zones, and resolves explicit durations as elapsed time. Temporal parsing runs in a cancellable process outside the audio loop.

Lesson: validate the entire typed phrase and its domain bounds, not just the first numeric result. Keep original transcript offsets, protect quoted/code/path data, require explicit timezone anchors, and measure cold imports before placing a parser on a voice path. A parsed scheduling candidate is not an executed task or universal scheduling authorization.

Sources: `jarvis_control/command_values.py`, `jarvis_control/parsing_service.py`, `voice_layer/local_speech.py`, `tests/behavior/test_command_parsing.py`; [implementation and saved evidence](../JARVIS%20OS%20DOCS/VOICE-COMMAND-PARSING-2026-11-03.md). Focused checks: 170 passed plus 12 subtests; expanded behavior gate: 125 passed. Source/dev environment changed; installed voice release was not deployed.

## 2026-11-03 — Certify the actual installed layout before activation

Outcome: after explicit deployment authorization, staged parsing over the existing `jarvis_voice` runtime, installed 28 additional dependency packages without upgrades, and passed 125 behavior checks under the installed Python 3.13 environment. The first candidate correctly failed for a missing test helper. The corrected candidate was activated atomically; three read-only running-service parser checks passed and standby/mute/vision settings were preserved.

Lesson: checkout tests and installed-runtime certification are distinct evidence. Preserve the installed package layout and unrelated release content, include test support needed for certification, and retain an expected-parent rollback target. State that additive shared dependencies remain after code rollback.

Source: `scripts/prepare_parsing_release.py`; [deployment and live evidence](../JARVIS%20OS%20DOCS/VOICE-COMMAND-PARSING-2026-11-03.md#authorized-deployment). Active release: `20261103T165256169577Z-command-parsing`; prior input/vision repair retained.

## 2026-11-03 — Present task state from a shared journal rather than result prose

Outcome: built a canonical schema and bounded persistent task presentation journal shared by filesystem receipts, UI snapshots and terminal notices. Model/worker responses remain unverified, cancellation requests remain nonterminal until confirmed, and delayed updates/acknowledgements cannot overwrite a newer result. Generic widgets cannot forge task-owned cards. A presentation failure leaves an admitted task admitted rather than encouraging resubmission.

Lesson: keep execution authority, transcript, presentation and notification acknowledgement distinct. Persist stream/revision/generation identity, retain pending outcomes under backpressure, and resync from current snapshots when replay history is bounded. Use an exclusive presenter lease before inferring that an in-memory task vanished after restart. Progress is measured data, never decorative percentages.

Sources: `contracts/task-event-v1.json`, `orchestration/task_events.py`, `orchestration/task_presentation.py`, `ui/jarvis_widgets/TaskEvents.js`; [implementation and evidence](../JARVIS%20OS%20DOCS/CONSISTENT-TASK-UI-EVENTS-2026-11-03.md). Final gate: 148 passed; broader existing checks: 86 passed plus 10 subtests; Qt suite: 16 passed. Built in source; installed runtime and shell were not changed.


## 2026-11-04 — Admit early interruptions through evidence gates

Outcome: removed the voice capture loop's unconditional first-350-ms playback interruption exclusion. Existing speech/VAD and playback-reference correlation checks still govern admission. Added synthetic startup acceptance, echo rejection and missing-reference scenarios; updated the obsolete holdoff assertion. Parent validation passed 59 focused voice checks and 7 selected daemon checks. A broader daemon run stalled and was stopped; installed runtime and hardware were not changed.

Lesson: a fixed startup blackout can discard a short correction even when the interruption detector has enough evidence. Preserve minimum evidence and echo rejection when removing a timing exclusion, and distinguish synthetic correlation tests from acoustic verification. Pause timing and semantic turn completion remain separate unfinished work.

Sources: `voice_layer/daemon.py`, `voice_layer/speech.py`, `tests/test_hie_startup_interruption.py`, `tests/test_interruptions.py`, `docs/human-interaction-engine-plan.md`. The requested capture-learning skill is absent from the available catalog and project search; this sourced append records the result directly.

## 2026-11-04 — Review agent fixes against lifecycle and deployment contracts

Outcome: lower-cost agents implemented the PC audit repairs; parent review corrected
expiry authority, historical sensitivity, overwrite rollback, pending receipt semantics,
and installer validation. The full suite passed 1,722 checks plus 149 subtests;
the final behavior gate passed 167 checks. Reloaded PC voice/bridge services were
active, Gemini reconnected, privacy settings were preserved, and the bridge bound
to loopback. Android code and the Hermes gateway were not restarted or changed by this repair.

Lesson: review full lifecycle behavior after a narrow fix. Restricted classification
must cover old snapshots, admitted execution can outlive a response deadline, and
installer success requires a complete importable payload before publishing its pointer.
A checkout-based service can be valid development mode; validate the configured mode
instead of treating all checkout paths as deployment failures.

Sources: `docs/pc-audit-fixes-2026-11-04.md`, `tests/test_filesystem_audit_regressions.py`,
`tests/test_memory/test_audit_memory_regressions.py`, `tests/test_device_execution_admission.py`,
`tests/test_device_bridge_security.py`, `tests/test_installation.py`.


## 2026-11-04 — Keep human interaction presentation grounded and preserve microphone identity

Outcome: built the six-stage HIE V1 in the source checkout: 1.2-second default pause tolerance, early interruption evidence gates, contextual admitted-work acknowledgements with copied deferred arguments, idle event-grounded progress, native delivery guidance and sparse narrative listening cues. Buffered the first 80 ms of listening-cue microphone input for echo comparison; matched echo becomes silence and distinct speech is replayed with turn flags preserved. An independent playback epoch cancels listening audio without invalidating microphone generations. Final checks: 258 focused voice tests passed with no failures/skips; the existing required behavior gate passed 201 checks with an unchanged-source fingerprint. CLI dependency/config check passed. No installed release, service or existing profile was changed.

Lesson: action-specific acknowledgement needs execution admission, not transcript hints; deferred presentation must carry arguments and turn identity. Listening feedback must share output priority while preserving input PCM and boundaries through cancellation. Read progress snapshots off the audio loop, suppress stale/absent task updates and keep foreground tool calls free of synthetic conversation turns. A longer fixed pause is not semantic understanding; prompt coverage is not audible expressive-speech acceptance.

Sources: `voice_layer/daemon.py`, `voice_layer/playback.py`, `voice_layer/interaction.py`, `voice_layer/progress.py`, `voice_layer/persona.py`, `tests/test_hie_pipeline.py`, `tests/test_hie_playback_fence.py`, `tests/behavior/contracts.json`, `JARVIS OS DOCS/HIE-BEHAVIOR-GATE-2026-11-04.json`, `JARVIS OS DOCS/HIE-VERIFICATION-2026-11-04.json`, `docs/human-interaction-engine-plan.md`. The capture-learning skill is absent from the available catalog/project paths; this sourced append records the actual outcome directly.


## 2026-11-04 — Revalidate progress after waiting for the voice transport

Outcome: read-only HIE review reran 82 focused checks successfully and reproduced a stale-progress race with the real LiveVoice send lock. A running snapshot was selected, the task changed to completed while delivery waited for the lock, and the eventual provider payload still said background work was underway. No application fix was made in this review. No confirmed new buffer-loss or playback-epoch defect was found; a speculative stale acoustic-reference concern was withdrawn because retained reference also covers legitimate room echo tails.

Lesson: privacy checks under a transport lock do not refresh task facts selected before that lock. Bind a progress delivery to task identity/revision and revalidate its state immediately before dispatch. Ordinary passing tests do not prove this wait-window behavior.

Sources: `voice_layer/progress.py:124`, `voice_layer/daemon.py:858`, real-lock synthetic provider reproduction during this review; `tests/test_hie_progress.py`, `tests/test_hie_pipeline.py`, `tests/test_hie_playback_fence.py`. Live audio and the full repository suite were not verified. The capture-learning skill remains absent from the available catalog; this append records the sourced outcome directly.


## 2026-11-04 — Fence task progress at dispatch and verify interrupted deployments

Outcome: fixed the reviewed progress race by carrying immutable task identity/revision into the locked delivery path and re-reading its current journal snapshot before speech authorization. Revision-only changes refresh waiting tokens without repeating delivered notices. The regression first failed five stale cases; final checks passed 49 focused tests and 209 required gate checks with certified source intact. Deployed through the existing checkout-mode voice service restart. An interrupted deployment command omitted its report; read-only verification confirmed new PID 53309, active service, current source, Gemini connection, control and AEC. The helper had exited. The replacement AEC inherited the physical microphone mute; no unmute, UI restart, bridge restart or release-pointer switch was performed.

Lesson: a revision fence must refresh undelivered tokens even when the spoken state is unchanged. After an interrupted deployment, inspect actual process identity and service state before repeating a mutation. Preserve physical privacy signals rather than assuming an old virtual microphone's mute flag represents the underlying device.

Sources: `voice_layer/progress.py`, `voice_layer/daemon.py`, `tests/test_hie_progress.py`, `JARVIS OS DOCS/HIE-FIX-BEHAVIOR-GATE-2026-11-04.json`, `JARVIS OS DOCS/HIE-FIX-DEPLOYMENT-2026-11-04.json`; systemd/voice IPC/PipeWire/journal verification after the 2026-11-04 18:14 IST restart. Live acoustic behavior was not tested. Capture-learning remains unavailable; this dated source-backed append records the observed outcome.


## 2026-11-04 — Check physical and virtual microphone mute independently

Outcome: user reported no voice response after deployment. Live status showed Gemini connected but JARVIS's AEC source remained muted; the physical default microphone was already unmuted. Unmuted only the active JARVIS AEC source, then confirmed its mute was false, listening was true, four user turns were admitted and provider audio bytes increased from 162240 to 201120. No application source, physical microphone setting or service restart was needed. Speaker audibility was not verified.

Lesson: a virtual AEC source can retain a mute inherited at creation after the physical microphone is later unmuted. Diagnose both layers; a connected cloud session does not establish working microphone input. Do not automatically synchronize mute states without a defined privacy policy.

Sources: voice IPC status and PipeWire mute probes for `jarvis_aec_6c22a21f` during this repair. Capture-learning is unavailable; this append records the observed outcome.


## 2026-11-04 — Verify active timing overrides before claiming listening cues work

Outcome: user reported listening cues absent. Active config retained400ms turn closure while the cue needed400ms quiet +670ms audio +100ms margin, making it unreachable. Backed up and corrected the active profile to1.2s; reduced only the cue's quiet tail to460ms with a20ms fade and validated cache integrity. Small acknowledgement and native delivery refinements passed120 focused checks and209 required gate checks. Reload preserved standby via a temporarily muted startup; final read-only status later showed connected/listening, AEC unmuted, original autostart/greeting restored and1.2s configured. Audible cue occurrence remains unverified until a new narrative test.

Lesson: source defaults and synthetic timing tests do not establish the active profile's feasibility. Compare minimum quiet time, complete clip duration and safety margin against the actual endpoint. Preserve standby during deployment rather than waiting forever for a standby profile to report idle. Prefer removing empty audio tail and redundant promises over adding speech models or relaxing echo evidence thresholds.

Sources: `voice_layer/daemon.py`, `voice_layer/acknowledgements.py`, `voice_layer/persona.py`, `voice_layer/assets/ack_short_hmm.pcm`, `voice_layer/assets/acknowledgements.json`, `tests/test_situational_acknowledgements.py`, `JARVIS OS DOCS/VOICE-POLISH-BEHAVIOR-GATE-2026-11-04.json`, `JARVIS OS DOCS/LISTENING-CUE-PROFILE-FIX-2026-11-04.json`. Capture-learning remains unavailable; this append records the observed outcome.


## 2026-11-04 — Freeze the approved PC voice baseline without disturbing runtime

Outcome: at the user's request, froze 122 PC voice source/test/asset/entry-point paths and compatibility links with a hash manifest and local read-only permissions. Five source directories are non-writable; generated bytecode caches remain writable. The verifier preserves the existing internal compatibility asset link but rejects unexpected redirects, changes, additions and removals. Root CLAUDE.md and its AGENTS.md mirror require explicit user authorization for voice changes; CI and the existing evolution manifest guard use the recorded boundary. Five focused lock tests and 214 required behavior checks passed. CLI dependency/config validation passed. No service restart, runtime profile change or microphone change occurred.

Lesson: reuse the existing voice-lock manifest interface, protect real source plus compatibility paths, and pin legitimate internal links instead of rejecting or copying them. Keep mutable caches and shared application code out of a source freeze. Read-only modes protect local accidental writes; hashes and policy carry the baseline across Git clones, which do not preserve those permission bits. An owner-reversible lock is not a security boundary against the machine owner.

Sources: `audio/.voice_lock.json`, `scripts/verify_voice_lock.py`, `tests/test_voice_lock.py`, `AGENTS.md`, `CLAUDE.md`, `.github/workflows/ci.yml`, `JARVIS OS DOCS/VOICE-LOCK-BEHAVIOR-GATE-2026-11-04.json`, `JARVIS OS DOCS/VOICE-SUBSYSTEM-LOCK-2026-11-04.json`. Capture-learning is unavailable; this append records the actual sourced outcome.

## 2026-11-04 — Extract voice without carrying the application or bypassing its freeze

Outcome: explicitly requested standalone copy created under `universal-voice/` while preserving the locked PC baseline. Reused voice streaming, speech gating, interruption, playback, acknowledgement assets, wake listening and event-progress presentation; removed mandatory memory/desktop/vision/task dependencies and rejected unattached tool calls. Configuration, IPC, greeting markers and service name are independent; removed legacy socket-link creation. Built a wheel and source archive with attribution. 68 source checks and 68 checks against an isolated wheel passed; local dependency/VAD and shell preflights passed. Original voice-lock verification passed before and after. No service, microphone or original profile changed.

Lesson: portability requires tracing runtime paths and startup imports, not only copying source. A compatibility socket alias can silently interfere with the original even after renaming the package. Separate Linux distribution compatibility by prerequisites from tested distro/hardware support; an isolated wheel test does not establish a fresh dependency installation or live audio quality.

Sources: `universal-voice/README.md`, `universal-voice/VERIFICATION.json`, `universal-voice/tests/test_portable.py`, `universal-voice/ORIGIN.json`, `universal-voice/dist/SHA256SUMS`. Cross-distribution VMs and live cloud/audio remain untested. Capture-learning is unavailable; this append records the sourced outcome directly.

## 2026-11-04 — Lock both voice copies while preserving the selected system default

Outcome: user explicitly selected keeping the current full JARVIS system voice and locking both copies. Original baseline verifier passed; froze 77 standalone source, asset, test, packaging and distribution files with an independent checksum manifest, verifier and read-only permissions. Added matching agent freeze rules to both instruction mirrors. Both verifiers and source permission checks passed; 68 standalone regressions passed after locking. Existing full voice service was active and cloud connected; its system microphone was muted and was left unchanged. No voice service replacement, restart or audio setting change was performed.

Lesson: a standalone voice extraction does not carry the full assistant's desktop tools. Confirm which runtime should remain the default before substituting one for the other. A code freeze should preserve privacy state and maintain separate manifests rather than regenerating an already approved baseline.

Sources: `universal-voice/.voice_lock.json`, `universal-voice/scripts/verify_voice_lock.py`, `AGENTS.md`, `CLAUDE.md`, existing voice IPC and systemd inspection during this task. Capture-learning remains unavailable; this sourced append records the outcome. Live acoustic behavior was not tested; owner-reversible permissions are an accidental-edit guard.

## 2026-11-04 — Default to EGM for its supported design/document workflows

Outcome: installed egm@egm 0.1.0 and read its bundled Codex integration, execution constraints and skill descriptions. At the user's request, saved global and matching project instruction routing for brainstorming, design drafting, document review, resolution, documentation bootstrap and drift reporting. Ordinary implementation and small bug fixes retain the normal workflow. Both voice baseline checks passed; protected files and runtime settings were untouched.

Lesson: a design plugin is not an inference model or a universal coding mode. Persist task-specific routing, resolve installed skill paths dynamically, preserve real approval/isolation requirements and do not claim workflow execution merely from installation. A fresh session is recommended by the plugin for skill discovery.

Sources: installed `egm` bundle `docs/codex.md`, `resources/execution_instructions.md`, `skills/*/SKILL.md`; global Codex AGENTS.md and project CLAUDE.md/AGENTS.md. End-to-end Goldfish reviews were not run. Capture-learning remains unavailable; this dated append records the sourced outcome.

## 2026-11-04 — Test both frozen voice copies and distinguish distribution locks from local locks

Outcome: read-only audit using EGM drift-report plus existing executable tests passed 501 system voice tests, 214 overlapping required behavior-gate checks and 68 standalone checks. Both source-lock verifiers, source/archive byte comparisons, distribution hashes and dependency/VAD preflights passed. Restricted-environment runs stalled or timed out; host reruns completed without test edits. Runtime initially showed a provider handshake retry, then a connected provider with AEC active; the system microphone remained muted. No source, profile, service or mute changes were made.

Lesson: a local freeze created after packaging does not travel with the older archive/wheel. The downloadable standalone source matches the protected code, but its archive omits the later manifest/verifier/instruction files. Record that distribution gap instead of claiming extracted copies are locked. Automated tests and provider connection do not establish real-room listening cues, barge-in latency or voice quality.

Sources: `docs/voice-audit-2026-11-04/VOICE-TEST-REPORT.md`, `docs/voice-audit-2026-11-04/2026-11-04_DRIFT_REPORT.md`, saved JUnit and gate evidence in that directory; read-only service snapshots. Fresh installations, distro VMs and live audio remain untested. Capture-learning is unavailable; this append records the sourced outcome.

## 2026-11-04 — Mirror physical microphone mute transitions to the owned AEC source

Outcome: user authorized a specific unmute repair. Live state reproduced physical default input unmuted while JARVIS's AEC input remained muted despite a connected provider. Added transition-based synchronization to the existing microphone monitor, scoped to its echo owner's resolved physical source and private AEC. Independent AEC mutes persist when physical mute is unchanged; invalid/unknown state does not unmute. Fifteen new regressions, 516 full voice checks and 229 required gate checks passed. Restarted only the existing voice service; it reconnected with private input unmuted and no input error. Physical settings and saved config were unchanged. Authorized source hashes were recorded and read-only locks restored; standalone copy unchanged.

Lesson: initialization-only mute propagation is insufficient after a physical mute/unmute cycle. Follow observed physical transitions rather than continuously forcing virtual input to match, and preserve the last observation until a write succeeds. Track the actual source, not whatever later becomes the system default. Software regression and ready microphone state still do not prove audible conversation.

Sources: `docs/voice-unmute-repair-2026-11-04.md`, its source patch, `tests/test_microphone_mute_sync.py`, `JARVIS OS DOCS/VOICE-UNMUTE-BEHAVIOR-2026-11-04.json`, `JARVIS OS DOCS/VOICE-UNMUTE-DEPLOYMENT-2026-11-04.json`. Capture-learning remains unavailable; this append records the sourced outcome.

## 2026-11-04 — Separate whole-OS Harness² intent from research-only implementation

Outcome: reviewed the Antigravity system architecture map with fresh-context EGM zoom-out, comprehension, design, structural, style and intermediate zoom-out reviewers. Found open gaps in protected voice exclusions, runtime isolation, release authority/recovery, OS benchmarks, incident contracts and privacy. Existing learning suite passed 62 tests; both voice locks passed before/after. No deployment or source repair performed.

Lesson: Git worktrees isolate source trees, not host service effects. A research-instruction evaluator and successful fixtures do not certify whole-OS self-repair. Start with one sanitized incident producing an evaluated advisory proposal; define separate non-research candidate and recovery contracts before production mutation. Installed crash/healer notifications offer click-to-launch flows, not proof of an automatic evaluation pipeline.

Sources: `docs/harness2-review-2026-11-04/consolidated_review_report.md` and adjacent reviewer reports; `learning/refinement.py`, `learning/trials.py`, `learning/evidence.py`, `orchestration/release_manager.py`; installed `/usr/bin/omarchy-crash-watch` and external healer notification/playbook source. The capture-learning skill is absent in this checkout; this append records the sourced outcome. No implementation plan existed, so EGM Stage9 was explicitly not run; no convergence or runtime safety claim.

## 2026-11-04 — Establish Harness² contracts before live OS integration

Outcome: after the user instructed proceeding through the six-phase sequence, established the workspace architecture baseline with protected voice observation-only access, typed incident/proposal contracts, full-revision idempotency, single-owner job states and phase-specific acceptance obligations. Applied ten review fixes at the documentation level; production and Antigravity source artifacts unchanged.

Lesson: healer symptom IDs are fingerprint-derived and may recur; use occurrence identity for incident ingestion. Its incidents table does not expose direct structured service observations, so do not invent state from status/title or copy raw trace_json. An exporter must avoid MemoryStore initialization because it creates/configures database state. Written boundaries do not close runtime isolation, clean-install or recovery findings.

Sources: `docs/harness2-review-2026-11-04/architecture.md`, `goldfish_review_report.md`; read-only `/home/g0pi/Projects/omarchy-healer/src/omarchy_healer/models.py`, `memory.py`, `probes.py`. Capture-learning skill absent; this append records the sourced outcome.

## 2026-11-04 — Build OS contracts without importing the live voice runtime

Outcome: implemented learning/os_contracts.py as an independent standard-library validation CLI/API. It enforces fixture-only typed incidents, baseline/time checks, immutable revisions, evaluator-bound identities, evidence-supported advisory proposals and protected-path screening. Added 58 contract checks; all 120 learning tests passed with zero skips. Both voice locks passed before/after; no existing runtime entry point, service or dependency changed.

Lesson: canonical incident revisions must include baseline and timestamps, while run reuse must additionally bind evaluator/fixture identities. Reject nested duplicate keys and numeric overflow before hashing JSON. Path screening must reject symlinks, hardlinks and directory scopes; it is still only a point-in-time check and cannot replace enforcement at a future writer. Future limits should be explicitly marked unenforced until a worker actually exists.

Sources: learning/os_contracts.py; tests/test_learning/test_os_contracts.py; docs/harness2-review-2026-11-04/phase1-build.md and phase1-tests.xml. Real incident ingestion, job durability, VM containment and deployment/recovery remain later work. Capture-learning skill absent; this append records the sourced outcome.

## 2026-11-05 — Import healer occurrences as historical metadata without inventing observations

Outcome: built learning/os_ingestion.py for explicit one-occurrence read-only SQLite imports into private separate state. Real metadata has unknown service identity/state and empty evidence; Phase 1 parsing stays fixture-only unless the importer explicitly enables the profile. Source-instance/path/device/inode and row-metadata binding prevent silent replacement/reuse; baseline revisions and reopen duplicates are persisted atomically under one writer lease. All 146 learning tests passed (26 new ingestion checks), both voice locks passed, and a real recent healer occurrence returned ingested then duplicate using temporary state. No incident/schema mutation, voice repair or service operation was issued.

Lesson: use an explicit read transaction to retain one WAL snapshot across schema and occurrence reads. Read-only SQLite may still maintain WAL shared-memory bookkeeping and require host filesystem access; do not claim every live sidecar byte is unchanged. The source's recurring symptom ID and raw trace are not an occurrence identity or reliable structured current-state evidence. Keep typed historical metadata separate from fixture evaluation and disable real-record proposal verdicts until independently implemented.

Sources: learning/os_ingestion.py; learning/os_contracts.py; tests/test_learning/test_os_ingestion.py; docs/harness2-review-2026-11-04/phase2-build.md, phase2-tests.xml, phase2-live-check.json; read-only external healer memory.py schema inspection. Restricted full-suite collection stalled and was interrupted; final host rerun passed 146 tests in 8.78 seconds. Capture-learning skill absent; this append records the sourced outcome. Automatic polling, voice wiring, current-service probes, execution isolation and deployment/recovery remain unimplemented.

## 2026-11-15 — Verify retry and repeat-run behavior before enabling memory maintenance

Outcome: reviewed the local JARVIS OS changes against the recorded upstream commit `4713691`. Temporary-vault checks showed that repeat compaction removed substantive details from the active daily note and that a failed note append still advanced the sync cursor. A temporary voice configuration also reproduced a startup error when the new decision settings were present.

Lesson: make compaction idempotent, advance a persistence cursor only after the corresponding write succeeds, and load new configuration sections through the same typed path as existing settings. Exercise these paths with disposable data before enabling scheduled maintenance.

Sources: `scripts/midnight_summary_sync.py`, `departments/memory/agents/a5_day_rollover_compactor.py`, `departments/memory/department.py`, `voice_layer/config.py` and temporary-data review checks. The capture-learning skill was unavailable in the installed and repository skill paths, so this entry records the findings directly.

## 2026-11-15 — Give memory maintenance a single owner for each file

Outcome: repaired the Memory Department's rollover, session sync, scoped recall integration, and pruning. The agent's notes now live under `Memory Department/Conversations`. The existing exporter retains its own files. Recorded history sync writes the note and its progress marker together, including when the first run occurs after midnight. Temporary-vault checks confirmed retry, repeat compaction, transcript retention, and alternate-vault isolation.

Lesson: keep a durable progress marker in the same atomic write as the content it represents. Apply scope and deletion through one memory store, and keep transcript maintenance from re-promoting historical text into remembered facts.

Sources: `departments/memory/department.py`, `departments/memory/agents/a5_day_rollover_compactor.py`, `departments/memory/tests/test_memory_department.py`, `scripts/midnight_summary_sync.py`, and isolated alternate-vault verification. The capture-learning skill was unavailable, so this entry records the result directly.

## 2026-11-15 — Validate memory stability through retries and worker shutdown

Outcome: hardened the six Memory Department agents and the legacy memory adapter. The graph filters expired and superseded nodes, consolidation regenerates agent-owned fact notes after a failed write, reflection deduplicates its rules, and diagnostic capture redacts credential fields. The legacy adapter now uses the shared bounded worker. Isolated checks exercised tool routing, worker shutdown, and repeat midnight sync against an alternate vault.

Lesson: preserve a stable initial sync cutoff across retries, derive file projections from committed records, and exercise the real worker lifecycle alongside unit tests. Generated rules and agent notes need stable identities and their own write boundaries.

Sources: `departments/memory/tests/test_memory_department.py`, `departments/memory/db.py`, `jarvis_memory/skills.py`, `tests/test_memory/test_memory_worker.py`, and the disposable DesktopSkills and midnight-sync check. The capture-learning skill was unavailable, so this entry records the result directly.

## 2026-11-15 — Verify outcomes at the action boundary

Outcome: buffered voice classifications now reach the Live tool path, and classified confirmation requests block tool execution for the initial turn. Close App reports the window or tab operation's result. Package removal aggregates results across managers. Review cards expose the working Diff action, and widget expiry preserves milliseconds.

Lesson: a classification or dispatch acknowledgment does not establish that a tool ran. Test the actual handoff and retain failures when multiple backends contribute to one result.

Sources: `voice_layer/daemon.py`, `tests/test_gemini_decisions.py`, `tests/test_control/test_privileged_and_security.py`, and the WidgetModel expiry assertions. The capture-learning skill was unavailable.

## 2026-11-15 — Retry desktop submissions before execution starts

Outcome: the control worker now retries only rejected submissions, and shutdown drains active work before releasing the owned camera. In an isolated checkout with local sockets, the behavior gate passed 224 checks and the full suite passed 2,160 tests with 15 skips and 149 subtests. That full run preceded the final camera shutdown change, which passed 15 focused control and concurrency tests. The synthetic memory evaluation reported no baseline regressions and still failed the false-recall check.

Lesson: an admitted tool can change the desktop before raising an error. Retry only when submission itself fails. Drain the worker pool before closing resources an active operation can reopen.

Sources: `jarvis_control/skills.py`, `tests/test_control/test_skills.py`, and the isolated test runs. The capture-learning skill was unavailable.

## 2026-11-16 — Verify desktop repairs at their runtime boundaries

Outcome: repaired desktop voice confirmation and offline classification, file-write conflict handling and Trash recovery, memory sync cursors and evidence filtering, package removal outcomes, release readiness and source fingerprints, evolution cards, stale voice status, and installer packaging. Lower-cost independent reviewers checked the file, release, and memory changes. The final isolated suite passed 2,170 tests and 149 subtests with 15 skips. The behavior gate passed 224 checks when run on its own. The synthetic memory benchmark passed with zero baseline regressions. Phone and mobile work was deferred.

Lesson: verify failure paths through the real local entry point. Keep a file conflict check close to replacement and record which writers honor its lock. Run the required behavior gate separately when a concurrent run fails to produce evidence.

Sources: `tests/test_control/test_voice_control_boundary.py`, `tests/test_filesystem_and_task_runner.py`, `tests/test_release_switching.py`, `departments/memory/tests/test_memory_department.py`, `scripts/behavior_gate.py`, and disposable checkout test results. The capture-learning skill was unavailable.

## 2026-11-16 — Preserve entry and socket ownership during desktop recovery

Outcome: a lower-cost agent review found that an existing daily memory note did not repair its stale rollover marker, and task verification followed symlink targets instead of checking the operated-on entry. Fixed both, including dangling-link verification. Desktop control servers now refuse to replace live listeners or ordinary files, bind before handing sockets to asyncio, and compare device/inode ownership before cleanup. The independent runtime reviewer identified the replacement-path shutdown case; it was fixed and covered for core, voice control, and speak sockets. The final disposable desktop suite passed 2,105 tests and 150 subtests, with 15 optional/runtime skips and 91 phone/mobile-related tests deselected.

Lesson: a pathname is not an ownership identity. Verify the entry an action actually changed, and never let startup or cleanup remove another server's socket. Recover persistent progress markers even when their corresponding output already exists. Preserve repository symlinks when building isolated test snapshots.

Sources: `core/ipc.py`, `voice_layer/ipc.py`, `filesystem/task_runner.py`, `departments/memory/agents/a5_day_rollover_compactor.py`, their regression tests, and `/tmp/jarvis-desktop-audit-ujyf8b0h/.review/suite-final.log`. Phone/mobile code and deployment were excluded; optional integrations and live desktop/cloud behavior remain unverified. The capture-learning skill was unavailable, so this entry records the sourced outcome directly.

## 2026-11-16 — Verify optional desktop connectors without claiming a live connection

Outcome: continued desktop validation after additional YouTube Brain integration changes appeared. A lower-cost reviewer repaired its hardcoded home path, SQLite URI escaping, bus error propagation, missing-note handling, bounded results/content, and bus setup deadline. The parent removed duplicate unconditional connection claims and required observed status before reporting availability. Integration tests now use a temporary SQLite database and the real asynchronous connector rather than personal notes. The final current-source desktop suite passed 2,116 tests and 150 subtests, with 15 optional/runtime skips and 91 phone/mobile-related tests deselected.

Lesson: a declared tool or readable archive does not prove that a live worker or capture pipeline is connected. Keep test fixtures isolated while exercising the real asynchronous boundary, and preserve unsuccessful connector responses instead of turning missing content into success.

Sources: `connectors/yt_brain.py`, `voice_layer/persona.py`, `voice_layer/daemon.py`, `tests/test_yt_brain.py`, `tests/test_yt_brain_persona.py`, and the disposable desktop verification run. Upstream worker response shape was checked read-only in `/home/g0pi/jarvis-yt-brain/yt_brain/jarvis_yt_brain_worker.py`. No phone/mobile modifications or deployment. Capture-learning remains unavailable; this append records the sourced outcome.

Final gate evidence for this continuation: the unchanged final source snapshot passed all 224 required behavior checks (`passed=true`, `source_unchanged=true`). These deterministic checks do not establish live microphone, cloud-provider, desktop-display, or external YouTube worker acceptance.

## 2026-11-16 — Use one desktop-entry inventory across launch routes

Outcome: fixed a case-sensitive legacy app lookup and made DesktopSkills consume the existing XDG desktop_paths/read_desktop discovery helpers. Nested desktop entries are now included and a hidden user override cannot be resurrected by a system entry. Regression coverage includes Antigravity capitalization, separation from Antigravity IDE, nested entries, hidden overrides, failure-loop limits, and worker timing. Isolated focused verification passed 56 tests and 11 subtests.

Lesson: multiple launch routes must agree on entry identity and precedence. A working executable does not make every spoken spelling a valid desktop ID. Bound failed retries and measure queue and handler time without logging file contents.

Sources: `skills/skills.py`, `jarvis_control/tools.py`, `tests/test_antigravity_launch.py`, `tests/test_desktop_tool_failure_loop.py`. The earlier file-action delay remains unattributed; no live action was replayed. Capture-learning is unavailable, so this append records the outcome directly.

## 2026-11-16 — Ground agent inventory in system discovery

Outcome: the live tool catalog now exposes system agent discovery directly, and the voice prompt routes agent inventory questions to it. The orchestration selector recognizes plural “agents.” Focused orchestration and persona checks passed.

Lesson: an inventory question needs the current agent catalog. A list of jobs answers a different question, and an installed command provides no evidence of sign-in.

Sources: `orchestration/tool_tiers.py`, `voice_layer/persona.py`, and `tests/test_orchestration.py`. The capture-learning skill was unavailable. The installed runtime and live microphone were unverified.

## 2026-11-16 — Include native departments in agent discovery

Outcome: the agent lookup now includes the LinkedIn and Memory rosters alongside local command availability. Focused orchestration and persona tests verified 12 LinkedIn agents and six Memory agents.

Lesson: agent inventory should account for internal specialists as well as external delegates. A roster alone does not establish runtime readiness.

Sources: `skills/domains/orchestration.py`, `voice_layer/persona.py`, and `tests/test_orchestration.py`. The capture-learning skill was unavailable. Deployment and live voice were unverified.

## 2026-11-16 — Register teams in the JARVIS agent catalog

Outcome: JARVIS returns one agent list with department membership on native and pipeline entries. The list includes 12 LinkedIn, six Memory, five YouTube Brain, and eight local command entries. Focused routing and catalog tests passed.

Lesson: use department membership as catalog metadata and keep execution behind the owning workflow. Recording a pipeline stage in the inventory leaves its health unverified.

Sources: `skills/domains/orchestration.py`, `skills/domains/yt_brain.py`, `tests/test_orchestration.py`, and the five stages in the adjacent YouTube Brain project's `yt_brain/main.py`. The capture-learning skill was unavailable.

## 2026-11-17 — Keep voice responsive while department work runs

Outcome: synchronous LinkedIn operations now use a dedicated worker. Voice requests for drafts, sprint plans, and profile audits return a tracked background task receipt, and the main voice can give one factual status reply when an action lacks completion evidence. A regression test held a synchronous draft open while a second voice turn completed. The focused voice, interruption, background delivery, and task suites passed 125 tests.

Lesson: moving execution off the audio event loop keeps capture alive, while returning a task receipt releases the conversational turn. Reuse the task runner for status and idle delivery, and keep confirmation-bound actions out of automatic background admission.

Sources: `voice_layer/daemon.py`, `jarvis_control/skills.py`, `skills/domains/linkedin.py`, `filesystem/task_runner.py`, `tests/test_daemon.py`, and the JARVIS Voice service journal. Capture-learning was unavailable. Live microphone conversation and NVIDIA authentication were not exercised.

## 2026-11-17 — Recover missing voice replies without speculative acknowledgements

Outcome: the voice journal showed local “okay,” “sure,” and “hmm” clips followed by new speech turns before reply audio, and a provider reply that recovered only after an empty turn boundary. Ordinary turns now wait for actual reply audio or admitted work. A transcribed turn that stalls can request one spoken answer without replaying tools. All 154 focused checks passed. After restart, the journal recorded two microphone turns with provider audio beginning in roughly one second. Live stall recovery was not induced.

Lesson: a local acknowledgement does not establish that a reply reached playback. Check upload, provider audio, and turn transitions separately. Bound recovery to one attempt per recognized turn and keep it clear of tools in flight.

Sources: JARVIS Voice service journal, `voice_layer/daemon.py`, `tests/test_daemon.py`, `tests/test_gemini_decisions.py`, and `tests/test_spoken_fillers.py`. The capture-learning skill was unavailable.

## 2026-11-17 — Verify low-cost LinkedIn drafts against source facts

The live LinkedIn drafting workflow reached the review queue using the configured primary NVIDIA model alone after agents were fixed to honor their supplied client configuration. The draft invented activity counts, which were removed in review. An authenticity check does not verify factual claims. Sources: the department regression tests and review card `post_20261117_085823_f7`.

## 2026-11-17 — Publish approved images through the LinkedIn department

The Content Scheduler now hands an approved image to the LinkedIn publishing tool as a structured upload, and the department records the returned post ID. The department regression test confirms that approving a published draft again does not trigger another upload or post.

## 2026-11-17 — Route LinkedIn work through the department

The voice persona routes LinkedIn work through the department even when Hermes is absent. The tool catalog exposes post lookup through the department using the connector's `post_id` argument. Sources: `voice_layer/persona.py`, `skill_manifests/linkedin-department.json`, and the focused routing tests.

## 2026-11-17 — Use API Anything for other online services

Voice routing now selects mapped API Anything operations for non-LinkedIn online services. Removing the competing generic platform action instruction keeps the selected route consistent with the existing authorization flow. Sources: `voice_layer/persona.py`, `voice_layer/daemon.py`, and `tests/test_system_persona.py`.

## 2026-11-17 — Preserve sync checkpoints during vault maintenance

The vault pruner now preserves notes that carry session sync checkpoints and keeps index prose intact when cleaning standalone links. The legacy conversations folder also rejects symlinks. The Memory suite passed 198 tests and 87 subtests. A disposable DesktopSkills run verified session sync, replay protection, prune preview, remember, and recall. Sources: `departments/memory/tests/test_memory_department.py` and the disposable DesktopSkills check.

## 2026-11-17 — Keep simultaneous YouTube Brain requests on the live worker

Six parallel reads produced one live reply before the connector assigned unique broker client IDs. After the change, all six used the worker, and live note retrieval passed. A readable SQLite archive now has its own status. Sources: `connectors/yt_brain.py`, `tests/test_yt_brain.py`, and the live read-only smoke check.

## 2026-11-17 — Bound Google Workspace agents by service

The Google Workspace department now owns six agents for Gmail, Calendar, Tasks, Drive, Docs, and Sheets. Every existing Google tool has exactly one service owner or belongs to the department control plane, and off-service dispatch is rejected before the connector runs. JARVIS agent discovery and voice routing now identify Google Workspace as a native department. Forty-one focused offline checks passed, and the local connection check reported Gmail, Calendar, Tasks, and read-only Drive, Docs, and Sheets authorization.

Lesson: reuse the connector as the transport boundary and enforce service ownership above it with immutable allowlists. Capability isolation over one shared OAuth grant is not separate credential isolation.

Sources: `departments/google_workspace/`, `skills/domains/workspace.py`, `skills/domains/orchestration.py`, `voice_layer/persona.py`, and `tests/test_google_workspace_department.py`. No live Google content was read or changed.

## 2026-11-17 — Deploy agent catalogs before testing voice answers

The voice journal showed `list_system_agents` executing successfully while the active service still ran the November 5 managed release, which only returned local command agents. The tested department catalog had remained in the workspace. A prepared release now installs the catalog and Google department through the atomic runtime switch. The restarted voice service connected successfully, and its active package reports 38 registered agents: 12 LinkedIn, six Memory, five YouTube Brain, six Google Workspace, one Update agent, and eight local agents.

Lesson: a passing workspace test does not establish live voice behavior when systemd starts an installed release. Verify the active release path and execute the catalog from that package after activation.

Sources: the JARVIS Voice journal, `systemd/jarvis-voice.service`, `scripts/prepare_google_workspace_release.py`, and the post-activation `list_system_agents` check.

Live acceptance: a typed request was sent through the running voice session. JARVIS invoked `list_system_agents`, began response audio in about 1.5 seconds, and answered that 38 agents are registered with the correct department counts, including six Google Workspace agents. No runtime error appeared during the inventory call.

## 2026-11-20 — Standardize JARVIS Prompting Style into Cross-Runtime Skill

Standardized the Omarchy-derived prompt design invariants into a dedicated, cross-runtime skill `jarvis-prompt-style` located at `~/.agents/skills/jarvis-prompt-style/SKILL.md`. Symlinked the skill across Antigravity (`~/.gemini/config/skills/`), Claude Code (`~/.claude/skills/`), and the JARVIS workspace (`skills/jarvis-prompt-style`).

The skill provides 6 production prompt templates (Crash Forensics, Safe Customization, Zero-Polling Components, Native App Scaffolding, Idempotent Migrations, and Zero-Filler Voice Persona) and enforces the negative constraints matrix prohibiting affirmative filler, unverified root cause speculation, polling loops, raw numeric animation durations, and direct modifications to `/usr/share/omarchy`.

Verified that Claude's dynamic skill selector hook (`~/.claude/hooks/dynamic_skill_selector.py`) and Antigravity discover and select `jarvis-prompt-style` automatically.

Sources: `~/.agents/skills/jarvis-prompt-style/SKILL.md`, `knowledge-base/OMARCHY-PROMPT-STYLE-GUIDE.md`.

## 2026-11-22 — Reuse semantic browser bindings for ultrafast decisions

JARVIS now exposes a bounded Gemini Decision browser loop through its existing CUA semantic tab binding. Each fresh observation produces one locally validated click, caller-owned text entry, or stop decision; sign-in, CAPTCHA, payment, generation, and publishing surfaces require a handoff. The external Jev browser runtime was not installed because JARVIS already owns the safer visible browser transport.

A live CLI fixture test verified the requested URL, selected and clicked one link, re-observed the changed page, and confirmed the final heading. The focused GUI, CLI, workflow, and Gemini suites passed 125 tests and seven subtests.

Lesson: reuse decision-space indexing and single-use actions, but keep browser identity, payloads, safety policy, and execution inside the host system.

Sources: `skills/browser_decision.py`, `skills/gui_control.py`, `jarvis_control/__main__.py`, and `tests/fixtures/browser_decision/`.

## 2026-11-22 — Resolve browser targets within their operation

The browser runner now executes the same candidate it validated for the selected operation. A regression test places a button before a text field, then verifies text entry followed by a click on a newly observed page. Each decision also receives recent action history. A model stop is reported as unverified because the model's choice alone cannot establish completion.

Sources: `skills/browser_decision.py` and `tests/test_skills/test_browser_decision.py`.

## 2026-11-22 — Validate multi-step plans against the live skill registry

The background task runner previously hard-coded ten file and LinkedIn tools, so valid department and desktop steps were rejected before execution. It now accepts any enabled skill whose arguments match its manifest, while rejecting recursive task controls and confirmation-gated system actions. Sequential failure and ground-truth checks remain in force.

A live three-step run completed application discovery, assistant status, and memory status in order. The focused validation, safety-policy, and browser tests passed six checks.

Sources: `filesystem/task_runner.py`, `skill_manifests/task-runner.json`, `jarvis_control/execution_policy.py`, and `tests/test_filesystem_and_task_runner.py`.


## 2026-11-22 — Verify release summaries at the action boundary

Describe browser completion and safety by what the runtime checks. The decision loop returns an unverified model stop, and its sensitive-page handoff scans exposed element labels. Report those limits and distinguish environment-blocked tests from product failures when reviewing commit readiness.

Sources: `skills/browser_decision.py` and the focused `tests/test_self_healer.py` run, where Unix socket creation was denied by the execution environment.

## 2026-11-22 — Flush Gemini input when the local speech gate closes

The local speech gate stops sending frames after its closing frame. With automatic voice activity detection, the sender now flushes that stream after the last frame. Explicit detection retains its activity-end signal. The voice daemon also keeps microphone mute and gain under user control and forwards local content through attachments instead of path mentions in typed input.

The focused suite passed 24 tests. After restarting the workspace service, the journal recorded a typed diagnostic reply and a microphone turn with provider audio. A separate prerecorded probe timed out in both detection modes, so intermittent provider or input failures remain possible.

Browser handoff remains a heuristic over the available snapshot. The browser can verify a supplied heading independently of the model's stop decision. The StateGraph routes through ordered stages with bounded retries, and temporal fact history remains subject to an explicit store clear.

Sources: `voice_layer/daemon.py`, `skills/browser_decision.py`, `orchestration/state_graph.py`, `jarvis_memory/store.py`, focused regression tests, and the `jarvis-voice.service` journal.

## 2026-11-22 — Verify widget support at the shell entry point

Python can prepare a 3D widget and the card has a 3D renderer, but the shell model rejects the kind before the renderer is reached. The focused Python run passed 34 tests and 10 subtests with a writable temporary runtime directory. Add presentation-boundary coverage when fixing the mismatch.

Sources: `ui/jarvis_widgets/backend.py`, `ui/jarvis_widgets/WidgetModel.js`, `ui/jarvis_widgets/WidgetCard.qml`, and `tests/test_e2e_3d_widget.py`.

## 2026-11-22 — Test Quickshell imports and sockets on the real launch path

The JARVIS HUD preview shares the existing card renderer. Quickshell rejected sibling imports when launched from inside `ui/jarvis_shell/`. A thin entry point under `ui/` made both component directories available. The live Omarchy smoke test exercised socket acknowledgments, the five-card cap, pinning, overflow restoration, palette toggling, and dismissal. Add direct click-through and keyboard focus checks before switching login sessions.

Sources: `ui/JarvisHudPreview.qml`, `ui/jarvis_shell/HudPreview.qml`, `ui/jarvis_shell/WidgetCanvas.qml`, and live Omarchy preview verification.

## 2026-11-22 — Match the Omarchy fallback to the shell canvas

Omarchy applies the wallpaper before running its theme-set hooks. On a JARVIS theme switch that exposes the wallpaper while the theme-aware shell maps its window. Both JARVIS fallback backgrounds now match the shell color, with the original images backed up. Verified that the running service was active and that the applied background matches the replacement.

Sources: `/usr/share/omarchy/bin/omarchy-theme-set`, the installed JARVIS theme hook, and `ui/jarvis_shell/Shell.qml`.

## 2026-11-22 — Route the installed theme to the shared HUD

The JARVIS theme service used its own launcher and was still rendering the original shell. Its launcher now loads the shared HUD in theme-aware mode. A real Wayland test in an isolated instance verified hiding and showing with theme changes, reading live-style voice state, and mounting a widget using the same event sender as the standalone HUD.

Sources: `ui/JarvisTheme.qml`, `ui/jarvis_shell/launch.sh`, and `ui/jarvis_shell/HudPreview.qml`.

## 2026-11-22 — Verify real-time widgets through the controller and shell together

A live Wayland test sent a generated form through the Python controller, updated the same ID, and read the new state back. Two ordered events from the real task store updated one progress card. Test the managed voice service separately because it imports its own installed controller.

Sources: `ui/jarvis_widgets/backend.py`, `ui/jarvis_shell/HudPreview.qml`, `ui/jarvis_shell/WidgetCanvas.qml`, and the isolated Wayland test.

## 2026-11-22 — Sample HUD telemetry only while the card is mounted

The System load card reuses the existing CPU counter and available-memory parsers, with a two-second timer inside the loaded component. The running Wayland HUD returned measured CPU and memory percentages for the mounted card. Keep telemetry collection in the presentation lifecycle when the readings serve only that card.

Sources: `ui/jarvis_shell/SystemTelemetry.qml`, `ui/jarvis_shell/HologramCard.qml`, `ui/omarchy-jarvis-island/ReactiveModel.js`, and the live HUD status check.

## 2026-11-22 — Verify app staging against compositor state

The app stage launches a selected desktop entry and dispatches window actions against a selected live window address. A temporary terminal test confirmed creation, parking in the vault, and restoring onto a regular workspace. The command receipt reports dispatch requested. The live window list verifies the result.

Sources: `ui/jarvis_shell/ApplicationStage.qml`, `ui/jarvis_shell/CommandPalette.qml`, and the live Wayland terminal test.

## 2026-11-22 — Keep palette selection tied to a stable target

App search and window results can change while the palette is open. The highlighted row now follows a desktop entry ID or window address, never a mutable list index. Enter opens the selected app or focuses the selected window. Parking and restoring remain separate controls.

Source: `ui/jarvis_shell/CommandPalette.qml`.

## 2026-11-22 — Keep native controls synchronized with their owning services

The JARVIS HUD audio and media cards read PipeWire and MPRIS state directly. Live HUD status confirmed mounted cards, default audio endpoint levels and mute state, and media player capabilities. Volume sliders preserve mute, and media controls gate actions by capability.

Sources: `ui/jarvis_shell/AudioControls.qml`, `ui/jarvis_shell/MediaControls.qml`, and the live JARVIS HUD status check.

## 2026-11-22 — Verify device controls from live service state

The mounted Device controls card read Wi-Fi and Bluetooth state through Quickshell and the default backlight level through brightnessctl. The live HUD confirmed all three readings without changing device settings. The brightness reader runs only while the card is mounted, and the slider coalesces updates before writing.

Sources: `ui/jarvis_shell/DeviceControls.qml` and the live JARVIS HUD status check.

## 2026-11-22 — Package the standalone session around its real launch path

The Arch package includes the login entry, compositor config, HUD root and imported components, and lock helper. The extracted package's launcher passed the installed Hyprland config verifier. A separate Wayland test registered notifications on a private D-Bus session and verified that a replacement retained one history entry. Verify full login and authentication on a separate session before changing the primary login configuration.

Sources: `packaging/PKGBUILD`, `packaging/build-jarvis-de`, `ui/jarvis_shell/NotificationCenter.qml`, the extracted package check, and the private D-Bus test.

## 2026-11-23 — Separate provider synthesis from deployed conversation playback

An Antigravity experiment showed Fish Audio synthesis and added a speech-queue route in the JARVIS workspace. Six focused tests passed. The installed voice release did not contain the new client, and the fallback test exercised cooldown and cue stripping without calling the daemon playback path. A provider audio file or helper test is insufficient evidence of a microphone-to-speaker conversation.

Sources: `voice_layer/fish_speaker.py`, `voice_layer/daemon.py`, `tests/test_fish_speaker.py`, and the installed release inventory.

## 2026-11-23 — Verify Fish key failover and announcement playback at the queue

The Fish client accepts numbered credentials, deduplicates them, and skips credentials rejected by authentication. Provider rate limits use the Gemini fallback and cooldown. The announcement worker tests now exercise Fish playback, stripped-cue fallback, and rejection of stale audio after a new speech turn. Eleven focused tests passed without contacting either provider.

Sources: `voice_layer/fish_speaker.py`, `voice_layer/daemon.py`, and `tests/test_fish_speaker.py`.

## 2026-11-23 — Keep the Fish trial voice available for sound effects

The user liked the Fish trial voice and preferred Gemini for regular conversation latency. The trial used Fish `s2.1-pro` with the provider's default voice and no configured `FISH_AUDIO_REFERENCE_ID`. Preserve that setup for explicit laugh, cry, sad, and sigh requests. No specific reference ID was available to record.

Sources: Workspace voice configuration check, active service restart, and 16 focused Fish tests.

## 2026-11-23 — Verify connection plans against the requested application surface

The configured NVIDIA NIM primary model returned a connection plan for a synthetic Antigravity desktop request. Keep model plans advisory and require local evidence for the requested surface before advertising a connection. A successful headless CLI reply does not establish desktop control.

Sources: `departments/cli_agent/planning.py`, `orchestration/evolution.py`, and the synthetic NIM check.

## 2026-11-23 — Keep one owner for JARVIS speech

Outcome: JARVIS conversation and spoken alerts use Gemini Live. The old Fish trial setting can no longer suppress Gemini audio. Fish Audio is reserved for a future separate voice agent.

Lesson: route background announcements through the same guarded idle-turn path as task updates so mute, standby, active speech, and pending actions are checked before sending. Background speech should carry no tool authority.

Sources: `voice_layer/daemon.py`, `tests/test_background.py`.

## 2026-11-23 — Release cancelled speech turns

Outcome: cancelling the alert worker during Gemini send now finishes the queue item and releases its turn authorization. The focused voice suite passed 26 checks.

Lesson: finalize dequeued alerts on every exit and clear only the cancelled turn's authorization. Give startup tests a temporary device ledger and a mocked audio setup so they exercise startup without the running desktop.

Sources: `voice_layer/daemon.py`, `tests/test_background.py`, `tests/test_daemon.py`.

## 2026-11-23 — Verify voice tests with local process access and temporary state

Outcome: all 108 tests from the stalled run and 58 adjacent tests passed with temporary state and normal local process access. The service status reported Gemini connected and listening. Its process started before the workspace fixes.

Lesson: distinguish test-runner restrictions from voice failures by rerunning with isolated state and the required local process access. Check the service start time before using live status as evidence for a workspace change.

Sources: voice and control pytest results, `scripts/jarvisctl.py status`, and `jarvis-voice.service` process metadata.

## 2026-11-23 — Verify deployed Gemini playback

Outcome: restarted `jarvis-voice.service` at 09:14 IST. Gemini connected with an unmuted microphone and active echo cancellation. A local test alert produced 96,002 bytes of new Gemini audio, reached the playback stream, and returned the service to listening without a reported error.

Lesson: use a spoken alert to check Gemini output and playback after a restart. Verify physical microphone-to-reply behavior with a spoken turn.

Sources: systemd service metadata and the local voice status and announcement commands.

## 2026-11-23 — Show stale voice state as offline in the shell

Outcome: the JARVIS HUD distinguishes connecting, standby, and microphone states and shows offline when the voice status file stops updating. The offscreen QML suite passed 25 checks, including state expiry and recovery.

Lesson: a readable state file can outlive its writer. Use the daemon heartbeat timestamp to decide whether the shell can present its state as live.

Sources: `ui/jarvis_shell/HudPreview.qml`, `ui/jarvis_shell/HudModel.js`, and `tests/widget_canvas/tst_hud_model.qml`.

## 2026-11-23 — Verify shell outcomes at the compositor

Outcome: seven fresh-context Goldfish reviewers evaluated the Ada-inspired JARVIS shell. They identified that a launcher dispatch receipt does not prove an app window appeared and that HUD instances may contend for the same runtime socket.

Lesson: verify a mapped or focused window in the compositor, exercise a reproducible result card, and verify the voice link independently before requiring voice-generated results in the first desktop walkthrough.

Sources: EGM JARVIS desktop shell concepts brief, `ui/jarvis_shell/ApplicationStage.qml`, and `ui/jarvis_shell/HudPreview.qml`.

## 2026-11-23 — Restyle the shared desktop home in place

Outcome: the native JARVIS home gained a dark teal field, original voice-reactive contours, a legible status label, and a matching command palette. Twenty-five QML checks passed and the reactor rendered in standby and listening.

Lesson: keep visual state on the shared shell components and verify passive and active states with the real QML renderer. Test window and keyboard behavior separately on the compositor.

Sources: `ui/jarvis_shell/CoreCanvas.qml`, `ui/jarvis_shell/ArcReactorCore.qml`, `ui/jarvis_shell/CommandPalette.qml`, and offscreen QML render checks.

## 2026-11-23 — Apply the GUI guide to the existing desktop paths

Outcome: the standalone session validates with Hyprland 0.56.2, and the QML suite passed after the cyan spatial HUD restyle. The standalone launcher now defaults to its own config and resolves through symlinks. A six-card fixture checks the display cap and overflow without requiring Gemini.

Lesson: reuse the existing typed HUD protocol and local launcher. Keep desktop staging rules confined to the standalone compositor so a guide-driven shell change does not take over the active Omarchy session.

Sources: `guide-gui.txt`, `config/hypr/jarvis-minimal.conf`, `bin/jarvis-de`, and `widget_engine/test_emit.py`.

## 2026-11-23 — Package the native session and bind approvals to a request

Outcome: the Arch package registers JARVIS Desktop as a dedicated Wayland session. Extracted-package launcher and desktop entry checks passed, as did 204 Python tests and 25 QML checks.

Lesson: a managed daemon may start without the desktop's environment. Discover only the dedicated standalone shell entry for widget delivery. Match GUI and spoken approval to the held request ID under the executor lock so an expired or replaced request cannot act on a newer one.

Sources: `packaging/PKGBUILD`, `ui/JarvisDesktop.qml`, `ui/jarvis_widgets/backend.py`, and `tests/test_background.py`.

## 2026-11-23 — Dock the reactor around occupied desktop space

Outcome: the standalone shell now shrinks its circular reactor into a free corner when windows or cards occupy the desktop. It stays docked until its corner is occupied or the desktop clears. The Lua session configuration validated on Hyprland 0.56.2 after removing an unsupported idle-rendering key.

Lesson: use the same card bounds that drive click-through masking, and keep placement deterministic. Test the fullscreen case so the reactor does not cover a full-screen task.

Sources: `ui/jarvis_shell/CoreCanvas.qml`, `ui/jarvis_shell/HudModel.js`, `config/hypr/jarvis-minimal.lua`, and `tests/widget_canvas/tst_hud_model.qml`.

### 2026-11-23 — Boot the packaged shell in a clean guest

A passing placement-model test missed an unsupported JavaScript array method in the live QML window binding. The guest log identified the binding, and an in-guest screen capture also exposed compositor blur applied to the entire transparent HUD layer. Check the packaged session with its actual compositor, inspect runtime logs, and compare captures of the home screen and launcher.

Sources: `ui/jarvis_shell/CoreCanvas.qml`, `config/hypr/jarvis-minimal.lua`, `packaging/vm/install-init`, and the local KVM guest screenshots.

### 2026-11-23 — Use the live JARVIS theme as the desktop shell

The live compositor reported jarvis-core, jarvis-hud, omarchy-bar and omarchy-dynamic-island. The shell launcher now reuses these layers. A live IPC check found Foot in the application registry, opened the command palette and restored its previous visibility. The login hook uses the existing Omarchy post-boot event.

Sources: `bin/jarvis-de`, `config/omarchy/shell.json`, `config/omarchy/hooks/post-boot.d/20-jarvis-shell`.

## 2026-11-23 — Multimodal media ingestion for video, audio, image, and text

Outcome: Expanded JARVIS multimodal capabilities to full-spectrum media analysis. Video files (`.mp4`, `.mkv`, `.webm`, `.mov`, `.avi`, `.flv`) now automatically yield stream metadata (resolution, frame rate, container, codecs, duration), embedded subtitle transcripts via `ffmpeg`, and sampled keyframe scene inspection with OCR text via `tesseract`. In live Gemini sessions, keyframe images are extracted and forwarded as native JPEG image parts alongside video summaries. Audio files (`.mp3`, `.wav`, `.ogg`, `.flac`, `.m4a`, `.opus`) yield duration, sample rate, channels, codec, and ID3 tag metadata. Image analysis upgraded with Pillow (PIL) EXIF metadata extraction alongside OCR text. IPC and CLI (`jarvis send --file <path>`) now support direct file attachment ingestion by path or base64.

Lesson: Raw media attachments must not be cast to unicode strings without modality detection; binary fallback corrupts model token streams. Extracting representative visual keyframes as JPEG image parts allows multimodal LLMs to visually perceive video content across timestamps without hitting multi-megabyte video container upload barriers.

Sources: `filesystem/filesystem.py`, `filesystem/__init__.py`, `voice_layer/daemon.py`, `voice_layer/ipc.py`, `voice_layer/__main__.py`, `skills/input_bar.py`, `skill_manifests/filesystem.json`, `tests/test_multimodal_filesystem.py`, `tests/test_multimodal_daemon.py`, and `tests/test_ipc.py`.

## 2026-11-24 — Live desktop startup

A firmware boot reaching login did not prove that the JARVIS shell started. After changing the live profile to start JARVIS from the Hyprland startup event, a fresh diskless UEFI boot registered jarvis-core, jarvis-hud, omarchy-bar and omarchy-dynamic-island. Source: packaging/iso/build and the KVM serial probe in /tmp/jarvis-final-boot.log.

## 2026-11-24 — Welcome-only ISO preview

Outcome: Built jarvis-welcome-x86_64.iso and verified its reactor welcome screen in KVM on workspace 1. The live startup opens the HTML intro directly, with two local recorded prompts and no setup controls. Browser checks confirmed both audio files decode and no inputs or buttons remain; audible guest playback was not independently verified.

Lesson: For an intro-only review, reuse the supplied visual sample and local audio without starting the onboarding terminal or requiring cloud credentials. Verify the actual guest screen after building, not only the source page. The capture-learning skill was not available in the searched skill locations; this entry records the outcome directly.

Sources: packaging/iso/voice/welcome.html, packaging/iso/voice/hyprland.lua, packaging/dist/welcome-build.log, /tmp/jarvis-welcome-final.png.


## 2026-11-24 — Ryoku and Omarchy adoption assessment

Outcome: compared the local Ryoku source, current Omarchy manual, and JARVIS shell, packaging and release-manager sources. JARVIS already depends on Omarchy and has app/window search, device controls, widget integration, diagnostics and application-release rollback. Prioritize integration and discoverability over installing a second complete shell. Ryoku Nomarchy documents an Omarchy plugin compatibility path, but JARVIS compatibility has not been executed or verified.

Lesson: distinguish application rollback, system snapshot restore, and personal-data backup. Omarchy documents that root snapshots exclude /home and leave user configuration and migration records intact. Preserve independent backups for JARVIS user state. Treat unified settings, shared theme values and plugin capability declarations as adoption candidates, not implemented features. The capture-learning skill was not found in the searched local skill directories, so this sourced entry was appended directly.

Sources: upstream/ryoku/docs/nomarchy.md; upstream/ryoku/docs/plugins.md; upstream/ryoku/ryoku/hub/README.md; ui/jarvis_shell/README.md; packaging/PKGBUILD; orchestration/release_manager.py; https://github.com/omacom/omarchy/blob/quattro/manual/47-system-snapshots.md; https://github.com/omacom/omarchy/blob/quattro/manual/06-themes.md. This was source analysis, not a live hardware or performance test.


## 2026-11-25 — Adapt native card inputs to the existing JARVIS shell

Outcome: added metric, checklist, action and required-form inputs plus signed line charts to the existing widget controller and agent manifest. They compile to validated generated QML views and reuse existing widget identity, state, delivery and interaction handling. Focused verification passed 53 Python tests with 22 subtests, 27 QML suite checks and a separate offscreen rendering check of all five converted examples. The adapter unit test uses inline dispatch and mocked shell delivery; live service delivery was not tested.

Lesson: translate card data into the existing renderer before introducing another window or transport. Test required form fields through actual QML keyboard interaction. ADA workspace.js uses project-specific panels; its behavior was reference material, with no upstream source copied.

Sources: ui/jarvis_widgets/native_cards.py; tests/test_native_widget_cards.py; tests/widget_canvas/tst_widgets.qml; supplied /home/g0pi/Downloads/PROTOCOL.md; https://github.com/nazirlouis/ada-jarvis-public/blob/7697c32b929e762836291c83b070f51385ad793b/frontend/workspace.js. ISO rebuild and Ryoku deployment remain separate pending work.

## 2026-11-25 — Replace Caelestia with an Omarchy shell snapshot on the separate Arch root

Outcome: removed caelestia-cli, caelestia-shell-git and its debug package from /dev/nvme0n1p1 mounted at /mnt/jarvis (hostname jarvis-os). Copied the host's Omarchy 4.5.0 desktop files to the target, installed shell support dependencies, replaced Caelestia startup and launcher bindings, and supplied a limited desktop menu. The target remains Arch: this is a manually maintained shell snapshot, not an Omarchy system/package installation. Existing Hyprland and Quickshell remain. Previous Hyprland/Caelestia configuration is backed up under target /root/before-omarchy-shell-*.

Validation: target Hyprland reported "config ok". Offscreen Quickshell could not load PanelWindow without a Wayland backend; no successful graphical-session test is claimed. Hardware boot, authentication, audio and network panel behavior require target-session verification. No host desktop or EFI bootloader changes were made. The capture-learning skill was unavailable; recorded directly.

Sources: target /var/log/pacman.log; target /home/jarvis/.config/hypr/hyprland.lua; target /tmp/omarchy-load-check.log; host /usr/share/omarchy/shell and package metadata; https://github.com/omacom/omarchy/tree/quattro. Retain upstream MIT attribution when copying desktop files.

## 2026-11-26 — Clear widgets through the deployed native HUD controller

The active release still used an old backend that sent clear requests to omarchy-shell jarvis-canvas, while the visible cards belonged to jarvis-hud-preview. Transplanted the existing source routing helpers into that release's backend after backing it up, and restarted jarvis-voice to load the fix. The deployed controller's clearAll returned retained=0 and native status confirmed zero widgets. Regression checks: 22 Python tests and 10 subtests passed. Normal clear still intentionally retains pinned widgets; clearAll removes them. Sources: ui/jarvis_widgets/backend.py; tests/test_widget_canvas.py; deployed backend.py.before-routing-1795658589. No voice configuration changed.

## 2026-11-26 — Native widget styling and removal consistency

Updated shared native controls with ADA-inspired cyan surfaces, compact typography, task checkboxes and a subtle panel edge. Kept title bars and overflow menus removed. The voice domain now accepts clear/clear_all/status through manage_widget as well as manage_canvas; clear_all removes pins. Clearing the HUD also discards capacity-deferred task events so older queued cards cannot immediately refill the cleared space. Verified 23 Python tests (13 subtests), 32 QML checks, live rendering, and live clear_all including a pinned test widget. Spoken end-to-end removal remains unverified; shell reported voice offline and logs showed the pre-existing missing wake model. Sources: ui/ada/frontend/constellation.css; ui/jarvis_widgets/ViewNode.qml; ui/jarvis_shell/HudPreview.qml; skills/domains/widgets.py; tests/test_widget_canvas.py. capture-learning skill unavailable; recorded directly.
