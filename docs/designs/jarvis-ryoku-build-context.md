# JARVIS OS with Ryoku — build scope for review

Status: proposed scope awaiting user corrections. This document describes the intended finished system. It does not claim that integration or release testing is complete.

## What we are building

A bootable, installable JARVIS OS ISO based on Arch Linux, using the full Ryoku desktop environment with Hyprland and the existing JARVIS visual shell. The installed system brings together desktop controls, dynamic native widgets, the existing voice core, persistent memory, agents and external integrations.

Ryoku supplies the desktop foundation and supporting facilities. The JARVIS shell provides the main visible experience. The integration must assign one owner to each desktop facility so panels, notifications, login hooks and services do not start twice.

## Appearance and interaction

Use the current JARVIS reactor/orb, dark canvas, cyan and amber visual language, HUD cards and command palette. The user has excluded Ryoku wallpapers and alternative themes from this build's visible experience.

The reactor occupies the clear desktop and docks into available space when applications or cards appear. Native application windows remain usable alongside the HUD. Empty HUD regions pass pointer input through to the desktop. Keyboard navigation, clear focus indicators and normal application switching remain available.

Use the existing five-visible-card behavior and overflow handling. Support updates by stable widget ID, pinning, dismissal, expiry paused during interaction, preservation of compatible edited fields, and unloading of inactive views.

## Ryoku desktop integration

Include the complete Ryoku desktop package set appropriate for the selected Arch/Hyprland release. Integrate its settings and supporting desktop facilities with the JARVIS shell.

Required desktop functions include application launching, window/workspace management, display configuration, keyboard shortcuts, networking, Bluetooth, audio devices, brightness, media playback controls, notifications, clipboard, screenshots, screen locking, power actions and session recovery.

The first integration task is to map which functions the existing JARVIS/Omarchy components already own and which Ryoku components will provide. The current JARVIS packaging depends on Omarchy, so replacing or adapting those dependencies is explicit implementation work. Nomarchy offers a possible compatibility path, subject to testing with the actual JARVIS plugin and selected Ryoku version.

## Dynamic native widgets

Render widgets inside the current Quickshell/QML shell. Use ADA's project-panel behavior and the supplied native prototype as references for interaction and data presentation.

The current workspace supports text, tables, progress, local media, QR cards and generated interactive views. The latest work adds metric, checklist, action-button and required-form inputs plus signed line charts by translating them into existing generated QML views.

Agents send bounded structured data through the existing widget controller. Widgets return selected values and requests through the existing conversation/action path. Generated executable UI code is outside this structured widget contract.

Project briefs, file results, plans, task progress and memory results should appear using these native components. Their data must come from the corresponding backend. A navigation label or simulated card does not establish a connected feature.

## Voice core

Integrate the existing JARVIS voice runtime, its current model/voice configuration, microphone and speaker handling, local command routing where available, and Gemini Live connection.

The shell displays confirmed connection, listening, thinking, working and speaking state, plus supported transcript and audio-level information. Typed commands provide another route to the same assistant.

Validate microphone permission, device selection, mute state, interruption, output cancellation, disconnect/reconnect, startup and shutdown. Local commands must report what remains available when cloud connectivity is absent.

Protected voice baselines and freezes remain applicable. Desktop integration should use the existing interfaces. Any required change to protected voice code must be identified for separate authorization.

The ISO contains software and setup flows. Personal API keys, account tokens, existing conversation history and private memory must be supplied on the user's installation rather than embedded in a distributable image.

## Memory, agents and connectors

Package the existing persistent-memory services and their required local storage/dependencies. Connect real memory retrieval and updates through existing backend contracts.

Integrate the existing Hermes/orchestration services, task status reporting and supported tool execution paths. Display actual task outcomes and failures in the shell.

External services use the existing connector authentication flows. Account-dependent features become operational after sign-in and configuration. The first-boot experience should make missing setup and connection failures clear.

## Actions and approvals

Reuse the existing execution policy, request-bound approval controls and action evidence. An approval must apply to the intended current request and respect expiry or cancellation.

Widget actions, forms and voice requests enter the existing validation and execution paths. Desktop display, memory changes and system actions retain their actual permission boundaries. Clearing widgets only clears presentation state.

## ISO, installation and first boot

Build a separately named candidate ISO from pinned source/package versions. Coordinate with the ISO work already performed in the other chat before selecting the baseline artifact or modifying shared build inputs.

The deliverable should boot into a live JARVIS environment and provide an installation route with explicit target-disk confirmation. Verify the installed system boots independently of the ISO.

First boot should cover network access, audio checks, account/API setup, service health and a brief introduction to keyboard and voice controls. JARVIS desktop services should start reliably after login.

Kernel, bootloader, login manager and autologin policy should follow the verified baseline unless a concrete Ryoku dependency requires a change. The earlier Caelestia guide's CachyOS kernel and greetd choices are not yet agreed requirements.

## Recovery and maintenance

Retain recovery access through a terminal and a usable prior release or snapshot. Validate application-release rollback separately from system recovery.

Back up user configuration and JARVIS memory independently where system snapshots exclude the home directory. Updates must preserve user settings, credentials, memory and approved privacy state.

## Completion checks

A final release requires all of the following evidence:

- Fresh ISO boot in a VM, installation to a disposable virtual disk, and successful reboot from that disk.
- JARVIS appearance displayed correctly with a single intended desktop session and expected services.
- Working app launch, focus, workspace controls, settings, notifications, clipboard and locking.
- All supported widget types render, update, accept input and dismiss through normal tool entry points.
- Pointer click-through, keyboard focus, fullscreen applications, overflow and reactor docking work in the compositor.
- Voice capture, playback, interruption, state display and recovery work with configured credentials and available hardware.
- Real agent and memory operations return verifiable outcomes, with approvals enforced for relevant actions.
- Reboot preserves intended configuration and memory, and recovery works after a deliberately failed candidate update.
- CPU, memory, frame behavior and response latency are measured. The 8 GB target from the supplied guide is provisional until confirmed and tested.

VM checks and physical microphone/GPU checks must be reported separately. Missing hardware or account access must be listed as an unverified item.

## Current evidence and outstanding work

The latest widget adaptation passed 53 focused Python tests with 22 subtests, 27 QML checks, and an offscreen render check of five converted examples. Live desktop deployment and a rebuilt ISO containing those changes remain pending.

Ryoku integration, end-to-end voice integration in that desktop, installed-system verification and final hardware validation remain pending. Existing ISO files in packaging/dist are baseline candidates, not evidence that this combined release is finished.

## Delivery and sequence

After the user reviews this scope, prepare the agreed integration design, complete the desktop and service integration, build a candidate ISO, test it, correct failures, and produce the final ISO with a checksum and a concise verification report.

Subsequent appearance or behavior changes can be made individually against that tested baseline.

## Scope decisions for user review

Confirm or correct the visible shell behavior, included desktop facilities, first-boot setup, login policy and the provisional 8 GB memory target. The exact baseline ISO must be identified from the completed work in the other chat before rebuilding.

CSE-OS by CSE-OS Contributors, adapted from Founder OS by Adam M. Adamek (Impact Brussels ASBL). Preserve applicable upstream attribution and license notices for all distributed components.
