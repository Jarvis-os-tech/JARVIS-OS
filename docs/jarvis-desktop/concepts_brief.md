# JARVIS desktop concept brief

On first use, introduce the orb and collect the assistant and user names. Later logins open the normal orb desktop. Ryoku’s Hyprland configuration owns native windows, input, workspaces and monitors. JARVIS owns the visible desktop and dock. The existing Gemini voice core supplies voice input. The future learning harness has a separate milestone.

## Blocker for the first demonstration

ADA’s project workspace opens the parts list within the plan panel and uses a shared document dialog. The first demonstration needs two independently movable and closable instances. Reuse the project documents and editing operations. Give each open widget a stable identity linked to its document and task. See `ui/ada/frontend/workspace.js` around lines 97, 236 and 277. Check redistribution terms before packaging upstream assets.

## Major design decisions

- **Task switching.** Have a deliberate voice or pointer action activate a task and dock the previous task’s widgets. Clicking between the plan and parts list only changes focus. Agree on a visible task selector and what a second task within one project means. Focus changes should require zero model calls.
- **Lifecycle ownership.** Route voice, pointer and dock controls through one JARVIS operation per widget action. Hyprland supplies native window behavior. ADA owns document edits. Define what a user sees when they request restoration by pointer or voice and the saved workspace is empty.
- **Recovery.** Use ADA’s versioned documents as the source for edits. Persist references, widget IDs, task membership, geometry and dock state per user. Agree on when an edit or close becomes durable. A confirmed close must survive interruption and exclude the widget from future restoration. Define what happens to unsaved edits when closing.
- **First boot and upgrades.** Preserve existing profile names. Record onboarding completion after both names are saved. Establish recovery for interrupted onboarding and how an older image can preserve newer session data.
- **Desktop cost.** Coalesce resize writes and define which work pauses while docked. Measure idle CPU and memory with both representative widgets docked.

## Disposable KVM demonstration

Open the plan and parts list side by side, edit the plan and click between them. Verify both stay visible. Explicitly activate another task and check both enter the dock. Restore both, close the parts list, reboot and verify the orb desktop opens. Request restoration and verify only the edited plan returns. Repeat with forced interruption after a confirmed close and during an edit save. Verify an existing profile upgrades and can recover its original state on rollback. Record action source, opaque IDs, outcome and committed revision when needed to diagnose the test. Keep document text and transcripts out of diagnostics.

## Review coverage

Seven fresh native reviewers completed independently across design, codebase details, zoom-out, comprehension, implementation readiness, structural and inventive catalyst lenses. The inventive resolution is to treat task activation as a positive event, leaving ordinary focus changes free of docking side effects. Findings reflect concept and source review. KVM behavior, integration feasibility, packaging rights and resource costs await verification.
