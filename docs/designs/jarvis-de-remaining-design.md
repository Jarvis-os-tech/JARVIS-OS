# JARVIS desktop completion design

Working design · 2026-11-22

The existing JARVIS theme and the standalone Hyprland entry share the same Arc Reactor, widget engine, rails, and palette. Use Omarchy to develop and test individual workflows. A standalone session is ready when the workflows below also work from login through logout on the target hardware.

## Desktop features

| Feature | Interaction and implementation | Done when |
|---|---|---|
| Quick Controls | Summon a compact left-rail card. Reuse PipeWire for output and microphone, the installed network integration for Wi-Fi, BlueZ for Bluetooth, and the desktop brightness helper. Show the measured state and update on service events. Network credentials are entered in the OS authentication surface. | Sliders reflect hardware changes, missing services show unavailable, and keyboard and voice actions report the resulting state. |
| Notifications | Use the current Omarchy notification stream while testing in Omarchy. In standalone mode the JARVIS shell owns notification presentation. Show a short toast at top right and provide an on-demand history with a clear control. Lock-screen content is hidden by default. | One notification produces one toast, app actions reach their sender, expirations work, and blocked notifications never reserve a widget slot. |
| Media | Put the active MPRIS player on a left-rail card with play, pause, previous, next, and a seek control gated by the player's capabilities. Stop updating position when the card is unloaded. | Player changes, unsupported seeking, and player exit are reflected without stale controls. |
| Files, research, calendar, memory | Use the existing generated view renderer for result lists and summaries. Each item has a stable identity. File results open through the existing file opener, research sources through the URL opener, and calendar and memory changes through their owning services. Use explicit click or voice selection for effects. | A user can say or select “Open item two,” inspect the original source, and return to the same widget with its edits preserved. Empty and disconnected states have readable feedback. |
| App promotion | Put Expand on eligible results. Send an action keyed by result ID, resolve a supported desktop entry or resource in the backend, and preserve app dialogs and fullscreen behavior. Only collapse the source card after a positive open receipt. Keep manual per-window Park and Restore. | One action creates or focuses the intended app, restores the original widget state on return, and leaves unrelated windows where they are. |
| 3D and diagrams | Keep lightweight generated diagrams in QML. Enable 3D only when the compiler, payload validator, shell admission, renderer, and inspection flow agree on an end-to-end contract. | A 3D fixture reaches the renderer, the user can inspect it, and dismissal releases the view. Invalid or unavailable assets give a useful error. |
| Airlock and OS authentication | Use a lazy amber overlay for requests held by the existing execution policy. Show the pending action and consequence. Match confirm or cancel to the request's immutable ID and expiry. Use Polkit for credential entry and leave approval authority with the backend. | A duplicate or late approval has no effect, a hidden or expired prompt cannot be approved, and cancellation works from mouse and keyboard. |
| Lock, power, and session | Offer named actions for lock, logout, sleep, and reboot through existing OS services. Use a compositor-compatible lock surface with session recovery available by keyboard. Require the appropriate confirmation before session-ending actions. | Lock covers all monitors, suppresses HUD input and private content, and recovery works with JARVIS offline. Test logout and reboot from a disposable session first. |

## Voice and input contract

Expose the same named actions to the palette, widget controls, and voice tooling. Use the local router for deterministic desktop commands, including Clear HUD, Pin that, Show system, and window actions with a resolved target. Keep the active window, last interacted widget, and selected list result as distinct references. If a target is ambiguous, surface the matching results for selection.

Clear HUD clears unpinned widgets. Hide apps is a separate action for staged apps. The vault continues to contain running application processes. Emergency shortcuts, lock, and local desktop commands work when the conversational service or network is down. Measure voice input end to visible result on target hardware before assigning a latency claim.

## Implementation progress

The HUD now has PipeWire output and microphone controls and an MPRIS media card. Both mounted on the live desktop and returned service state. The Device controls card adds Wi-Fi and Bluetooth toggles and a backlight slider. Network selection, pairing, audio device switching, and live write-path verification remain in the quick-controls milestone.

## Integration order and acceptance

1. Connect quick controls and media to real desktop services and verify keyboard parity in Omarchy.
2. Add notifications and app promotion. Verify app ownership, click-through on empty HUD space, and restored state after overflow on multiple monitors.
3. Wire the updated tool manifest and widget controller into the managed voice release. Test offline HUD commands, spoken follow-ups, task reconnect, and delivery of a form action.
4. Connect the execution airlock, lock flow, and session controls. Test recovery with the daemon stopped and with the network disconnected.
5. Run the full standalone login-to-logout sequence on the 8 GB target. Record idle and active resource use, test display hotplug, and verify that the emergency terminal and TTY remain available.

For visual acceptance, run one continuous sequence from standby through a spoken request, a changing widget, app expansion, return to the widget, a safety prompt, and back to standby. The workshop-inspired composition applies throughout. Each animation should correspond to a state change or user action.

This is the working design for discussion. It does not certify the standalone session or authorize changes to the login manager.

The standalone session now has a packaged display-manager entry, a native notification toast and in-session inbox, a Hyprlock shortcut and config, and a keyboard-confirmed logout action. The package includes the desktop shell and uses the managed voice service when it is installed. Authentication, cold login and logout, and the complete spoken journey remain acceptance tests.
