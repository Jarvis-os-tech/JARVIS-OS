# JARVIS desktop

The installed `jarvis-shell.service` starts `ui/jarvis_shell/launch.sh`. This entry uses
the same HUD as the standalone preview and shows it when Omarchy's selected theme is
JARVIS. It reads the live voice state and microphone level from the existing JARVIS
runtime file. Switch to the JARVIS theme to use the live desktop. The workspace widget controller
routes `present`, widget management, and task batches to this HUD when JARVIS is
selected. Use the same widget ID to update a form without losing its edited fields.
Form buttons send the user's selected state to the existing voice session.

## Standalone preview

Launch the HUD from the repository while logged into Omarchy.

```bash
bin/jarvis-hud-preview
```

In another terminal, create a widget and open the keyboard palette.

```bash
python -m widget_engine.test_emit spawn_widget demo --payload '{"kind":"text","title":"JARVIS","data":{"text":"HUD online"}}'
qs -p ui/JarvisHudPreview.qml ipc call jarvis-hud-preview togglePalette
```

The palette handles Show system, Audio controls, Media controls, Device controls, Clear HUD, Pin that, Unpin that, and Dismiss that.
Audio controls show the current default output and microphone, with separate mute and level controls. Moving a level slider preserves mute. Media controls follow the active MPRIS player and only enable actions the player supports. Device controls show Wi-Fi and Bluetooth state and the default screen backlight level. Network selection and device pairing stay in the existing system panels.
Type `Open Firefox` or another installed app name to search and launch it. Type
`Windows` to focus an open window, park it in the vault, or restore it to the
current workspace. Type `Windows <title>` to filter the list. `Ask <request>`
sends a typed request to the existing JARVIS conversation. Use Up and Down to select a search result, and Enter to open the app or focus the selected window. Tab reaches the separate Park and Restore buttons. Show system opens live CPU and memory gauges that sample every two seconds while mounted. Escape closes the palette. Close the preview with Ctrl+C in its terminal or run `qs -p ui/JarvisHudPreview.qml ipc call jarvis-hud-preview stop`. The preview only accepts display data and local HUD lifecycle events. Its socket lives in your private session runtime directory. Text, progress, tables, charts, and generated views are available. Generated form fields work locally.

On the installed Omarchy system, run `jarvis-de` to activate the JARVIS shell or `jarvis-de --commands` to open its palette. Type an application name directly, select a result and press Enter. Run `jarvis-de --check` for the shell's live status. The post-boot hook activates the same shell at login.

On a clean preview, `python -m widget_engine.test_emit demo` sends six temporary cards across the two rails. Check that five mount and the remaining card appears in the overflow strip. **Show system** displays CPU, memory, the first thermal zone reading, Wi-Fi connection state, and Gemini connectivity.

The Omarchy preview exercises the widget stage without taking ownership of the existing desktop. The managed voice release needs the updated widget controller and tool manifest for spoken app-stage and widget commands. Automatic app promotion from a widget, native system controls, approvals, and session installation are separate integration milestones.

## Packaged standalone session

Run `packaging/build-jarvis-de` from the checkout to build an Arch package. The
builder uses a temporary staging directory and puts the package in
`packaging/dist/`, or in the directory set by `JARVIS_PACKAGE_OUT`. Install the resulting package on Arch Linux with `sudo pacman -U <package-file>`, then choose **JARVIS Desktop** on the display manager’s session screen. The session uses the installed Omarchy compositor configuration, top bar, Dynamic Island and JARVIS HUD. Its source theme assets, shell layout, and login hook are in `config/omarchy`. The setup command installs missing per-user links and uses existing settings on configured systems.
