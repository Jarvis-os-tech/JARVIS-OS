# JARVIS desktop and dynamic widget engine

Working hypothesis for Gopi · 2026-11-22

## Product

A complete voice-first desktop built from the existing JARVIS theme shell. The Arc Reactor shows whether JARVIS is listening and working. Widgets show the results and controls relevant to the current task. Hyprland still runs real apps when people need their full interfaces. Omarchy is the first test host. The eventual standalone session is a later release milestone.

The attached plan.pdf is a saved research conversation containing competing proposals and example commands. It informs this analysis. Its kernel claims, latency numbers, configuration syntax, and installation snippets have not been adopted as verified requirements.

## Architecture and trade-offs

| Area | Working direction | What would disprove it |
|---|---|---|
| Desktop surfaces | Evolve the existing Shell.qml into an ambient background, masked widget HUD, and on-demand safety overlays. Hyprland owns app windows and focus. The app vault is a workspace, independent of Wayland layer-shell ordering. | Empty HUD areas swallow mouse or scroll input, or a hidden safety overlay can still take focus. Test on two monitors and fractional scaling. |
| Widget engine | Keep two inputs to one presentation model. Typed widgets provide stable OS controls. Validated generated views provide task-specific layouts. Reuse the existing composed renderer, with one authority for IDs, placement and lifecycle. | The same task appears twice, a backend update erases a user's edits, or a backend-supported kind fails at the shell boundary as 3D currently does. |
| Lifecycle | Five ordinary visible cards with room limits per stage. Overflow keeps a lightweight record and releases the renderer. Restore uses the same ID and draft state. Pause expiry while hovered or focused. Give undoable user actions clear receipts. | All eligible cards are pinned. Keep them in place and queue the new ordinary card in overflow. Safety prompts need an independent slot. Measure component destruction and process memory separately. |
| Real apps | Expand runs a typed open action through the backend policy. Hyprland positions the resulting window. Start with explicitly promoted apps and preserve their dialogs, fullscreen shortcuts, and normal keyboard behavior. Offer an app-only hide action. | The intended app opens behind the HUD, a dialog is stranded in the vault, or users lose track of an unsaved window. |
| Voice and input | Voice, clicks, and keyboard shortcuts call the same named actions. Local commands handle common HUD actions. Gemini handles conversational work and Hermes supplies task progress. Route through existing voice interfaces. Treat 200 ms as a measurement target and record speech-end-to-visible-action separately from router time. | HUD actions depend on the network or a speech mistake is enough to trigger a risky operation. Test keyboard recovery with the voice daemon stopped. |
| IPC and approvals | Keep existing one-shot IPC while prototyping. Reuse task stream IDs, sequence and snapshots for progress. Add a bounded streaming channel when a test shows the existing path is inadequate. Bind confirmations to exact backend requests with expiry and one-time handling. Let Polkit manage credentials. | Reconnect duplicates cards, a delayed update revives a dismissed task, or a model-supplied payload can launch a raw command or approve itself. |
| Resource budget | Stop animation and polling on idle surfaces. Load heavy views on demand. Measure steady idle, five active cards, repeated open/close cycles, and the cost of apps parked in the vault on target hardware. | Component counts grow over repeated cycles or a typical browser plus HUD makes 8 GB operation sluggish. |

## What makes it a desktop

The basic session needs app launch and switching, notifications, audio and network controls, focus and monitor behavior, lock and session controls, and keyboard recovery. A first complete user journey should show a file list, open an actual file in a Linux app, return to the same widget, and dismiss it. A second should show a background task across shell reconnect. A third should exercise explicit confirmation and cancellation through the real policy.

## Staging

1. Redesign the existing shell in Omarchy. Prove click-through, keyboard focus, five-card overflow, restored edits, and component destruction. Use fixture events and one real existing widget tool.
2. Bring in system controls, notifications, command palette and recovery. Give any blocking safety flow its own tests for focus and expiry.
3. Connect typed app promotion and existing task events. Verify reconnect and app return journeys. Add the remaining catalog widgets where they make a workflow usable.
4. Test the standalone Hyprland session through the existing launcher, then measure resources and verify escape hatches before considering login changes.

## Decision to explore

What should happen to open Linux apps when the user says “Clear HUD”? My starting point is to clear unpinned cards and give “Hide apps” its own explicitly reversible command. That keeps the scope of a common voice command predictable, especially during typing or editing.

## Final visual target

Use Iron Man 2's workshop and molecule-discovery holograms as the primary reference for spatial composition. Use the original Iron Man Mark II First Flight HUD for peripheral diagnostics, fine cyan markings, and the way information appears as JARVIS responds.

- **Standby.** A near-black canvas with a dim, stationary Arc Reactor. The sides open up for summoned content or a real app.
- **Listening and working.** The core animates with voice activity. A compact status label and a few thin peripheral marks show the current state. Motion stops at rest.
- **Results.** Compact telemetry and task progress sit at the left edge. The main result appears on the right with a fine cyan outline, a translucent dark surface, and readable white text. A diagram or 3D object gets the open space when it is the task.
- **Interaction.** A panel traces in, then reveals its data. Focus brightens the edge and exposes controls. Restoring a minimized card brings back its previous content and edits.
- **Approval.** The center overlay uses amber and keeps the requested action, scope, and choices plainly visible.

The visual acceptance sequence is standby, a voice request, a populated widget, one direct interaction, then dismissal back to standby. Judge the composition and motion in that sequence, with real data and a working app visible underneath the HUD.

References: [Mark II First Flight HUD](https://www.thepartwhere.com/m/079423c6-ffcc-472f-9b1f-c6539172f28c), [Jorge Almeida's molecule-discovery graphics](https://jorgeonline.me/Iron-Man-2), and [Ilya Abulkhanov's Iron Man II UI and holograms](https://projectsbyilya.com/Iron-Man-II-U-I-Holograms).

## Remaining desktop design

See [JARVIS desktop completion design](jarvis-de-remaining-design.md) for the remaining surfaces, ownership, release sequence, and acceptance checks.
