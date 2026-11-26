# Native dynamic widgets — implementation scope for review

Author: Gopi
Date: 2026-11-26
Status: Requirements intake; architecture and implementation not yet approved through EGM.

## Requested outcome

Build the ADA-style dynamic widget experience directly in the existing isolated JARVIS theme on the working Omarchy desktop. Widgets should render actual work and information, update as that work changes, accept useful interactions, and disappear reliably when dismissed. Keep the current JARVIS orbit and theme. The user has rejected ordinary generic cards, permanent title bars and the overflow widget list.

Earlier Ryoku and separate-install plans are superseded by the user's later instruction to work in this existing theme. ISO changes, another desktop installation and voice-core changes are separate work.

## Findings from the current implementation

- ADA's workspace has separate brief, files, ideas, plan and next-step panels. It fetches fresh project snapshots and compares versions before rendering, retaining unchanged content. Its file editor uses expected revisions to avoid overwriting newer edits. Panel positions are saved independently.
- Native `workspace` currently compiles all sections into one generic column. Files and ideas lose their structured identities and become plain text. Task checkboxes submit a natural-language request; that is not proof that an authoritative task record was saved.
- The shell already provides IPC delivery, validated declarative views, native rendering, input drafts, interaction callbacks and task events. These should remain the integration baseline.
- The current canvas exposes three left and two right mounted slots. Additional widgets can exist without a visible surface. A successful create response therefore does not by itself prove visibility.
- Most current widget state lives in shell memory. Durable dismissal, restoration and recovery need an explicit contract before they can be claimed.
- Clear-all now removes pinned widgets and discards deferred old task cards in the current session. Restart recovery and late producer updates still require dedicated verification.
- Prior focused checks passed, but spoken end-to-end removal remains unverified. A missing wake-model error is a separate known issue; it must not be described as a widget-engine success.

## Proposed definition of complete

| Area | Required observable behavior |
| --- | --- |
| Composition | Separate coordinated native panels for brief, files, ideas, plan and tasks; generic charts, tables, metrics, forms and media remain available. |
| Appearance | ADA-like composition, section accents, purposeful rows and plan steps, cut corners and subtle focus treatment; preserve the JARVIS theme and orbit. |
| Real-time updates | Stable widget and item identities; newer source revisions update existing panels; duplicate and older updates do not overwrite current content or recreate dismissed panels. |
| Interaction | Controls have explicit actions and pending, success or error feedback. File rows open their known file; task edits update the owning task source. A model acknowledgment alone is not a save receipt. |
| Lifecycle | Voice and pointer use the same create, update, focus, pin, dismiss and clear operations. Dismiss hides a view without cancelling underlying work. Explicit reopening is distinguishable from a late update. |
| State | Preserve typed input, selection and scroll position through unrelated updates. Handle source-edit conflicts visibly. Persist only the state needed for agreed recovery behavior. |
| Layout | Usable placement at supported monitor sizes; keyboard access and reduced motion; no silent acceptance of a panel that cannot be shown. Long content remains accessible without reviving the rejected global scrolling widget menu. |
| Integration | One native controller owns widget lifecycle; both JARVIS tool routes use its contract. Existing tools and task event producers remain compatible. |
| Failures | Invalid data is rejected, unavailable sources are shown honestly, reconnect does not duplicate panels, and clear remains effective despite queued or late updates. |
| Verification | Exercise real native rendering and interactions, source updates, out-of-order updates, dismissal, clear including pins, reconnect and restart recovery. Report spoken and KVM results separately. |

## Decisions still requiring a design

The user has selected native rendering and the current theme. Remaining design choices concern which existing service owns durable workspace records, how much of ADA's project/file editing behavior belongs in this engine, and the interaction for excess content when five visible slots are insufficient. These affect data ownership and user behavior and must not be hidden inside a cosmetic patch.

ADA contains project management, file editing/history, uploads, inventory, CAD and printing workflows in addition to its widget interface. "Complete widget engine" does not establish a requirement to port every one of those applications. The engine should show their data through explicit integrations; additional domain operations need an agreed scope.

## Files the implementation must reach

- `ui/jarvis_widgets/`: schema validation, native content adapters, shared controls and state handling.
- `ui/jarvis_shell/`: composition, layout, focus, lifecycle and interaction feedback.
- `skills/domains/widgets.py`, `skill_manifests/widgets.json`, and `jarvis_control/tools.py`: consistent tool contracts and receipts.
- Existing task producers and persistence owners, after identifying their authoritative contracts.
- Focused Python and QML tests, native runtime checks and widget documentation.

## Evidence

Locally inspected: `ui/ada/frontend/workspace.js` (refresh, file editing, layout and UI commands); `ui/ada/frontend/project-layout.js`; `ui/ada/frontend/constellation.css`; `ui/jarvis_widgets/native_cards.py`; `ui/jarvis_widgets/WidgetModel.js`; `ui/jarvis_shell/WidgetCanvas.qml`; `ui/jarvis_shell/HudPreview.qml`; `docs/jarvis-desktop/concepts_brief.md`.

The older desktop brief describes a broader desktop and KVM milestone. It is reference context, not evidence that those features have been implemented or tested. Root `concepts_brief.md` and `design_draft.md` belong to unrelated Google Workspace and YouTube work and were left untouched.
