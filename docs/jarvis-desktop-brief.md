# JARVIS desktop redesign

## First boot and everyday login

On first use by a new user, show the central orb and welcome them to JARVIS OS. Ask what to call the assistant, with Jarvis as the default, then ask what to call the user. Finish with “Welcome to your own personal OS.” Later logins open the normal orb desktop. The existing Gemini voice core provides the assistant. The future learning harness has its own integration milestone.

## Desktop ownership

Ryoku’s Hyprland configuration manages native windows, input, monitors and workspaces. JARVIS owns the visible desktop, orb and dock. Exclude the stock wallpaper and theme surfaces. Adapt ADA’s dynamic widgets to run on this desktop. The orb moves to a free corner when content needs its space.

## Widget behavior

Voice and pointer actions target the same widget instance. Support moving, resizing, minimizing, maximizing, restoring and closing. Related widgets can stay visible side by side. Changing focus between them keeps both visible. Switching to another task tucks the previous task’s widgets into the normal dock. An explicit close removes the widget from the running set and future restoration.

Save open and docked state, widget content and geometry per user. Begin each login with the normal desktop. Restore saved work when the user asks. Distinguish an intentionally closed widget from a saved widget awaiting restoration.

## First acceptance scenario

Open a project plan and parts list. Arrange them side by side and edit the plan. Switch between them, then switch to an unrelated task. Verify both widgets tuck into the dock and retain the edit. Restore them, close the parts list, and reboot. Verify the orb desktop opens and that “bring back my last workspace” restores only the plan with the edit intact.

## Review before implementation

Check how a task switch can be identified without minimizing a widget during ordinary focus changes. Verify ADA widget packaging and redistribution terms, the session state format, recovery after interruption, and ownership of the dock and desktop layers. Exercise the resulting session in a disposable KVM before replacing the current ISO.
