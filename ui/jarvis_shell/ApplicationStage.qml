pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Hyprland

QtObject {
    id: stage
    readonly property string vault: "special:vault"
    readonly property var applications: DesktopEntries.applications.values
    readonly property var windows: Hyprland.toplevels.values.filter(window =>
        window.workspace && /^0x[0-9a-f]+$/i.test(stage.addressOf(window)))

    function addressOf(window) {
        const address = String(window.address || "")
        return address.startsWith("0x") ? address : "0x" + address
    }

    function findApps(query) {
        const needle = query.trim().toLowerCase().slice(0, 160)
        function exact(app) { return [app.id, app.name].some(value => String(value).toLowerCase() === needle) }
        return applications.filter(app => !app.noDisplay && (
            !needle || [app.name, app.id, app.genericName].some(value => String(value).toLowerCase().includes(needle))
        )).sort((a, b) => Number(exact(b)) - Number(exact(a)) || String(a.name).localeCompare(String(b.name))).slice(0, 6)
    }

    function listWindows() {
        return windows.map(window => ({
            address: addressOf(window), title: window.title || String(window.lastIpcObject.class || "Window"),
            parked: window.workspace.name === vault
        }))
    }

    function launch(id) {
        const entry = applications.find(app => app.id === id && !app.noDisplay)
        if (!entry) return {ok: false, error: "Choose an installed application."}
        entry.execute()
        return {ok: true, status: "requested", id: entry.id}
    }

    function parkActiveFloating() {
        const active = Hyprland.activeToplevel
        if (!active || !active.workspace || active.workspace.id <= 0 || active.lastIpcObject.floating !== true)
            return {ok: true, status: "no_floating_window"}
        return control("park", addressOf(active))
    }

    function control(action, address) {
        if (!/^0x[0-9a-f]+$/i.test(address) || !["focus", "park", "restore"].includes(action))
            return {ok: false, error: "Choose an open window and a window action."}
        const window = windows.find(item => addressOf(item) === address)
        if (!window) return {ok: false, error: "That window has closed."}
        const target = JSON.stringify("address:" + address)
        const parked = window.workspace.name === vault
        if (action === "park") {
            if (parked) return {ok: true, status: "already_parked"}
            Hyprland.dispatch('hl.dsp.window.move({ window = ' + target + ', workspace = "special:vault", follow = false })')
        } else if (parked) {
            const monitor = Hyprland.focusedMonitor
            const workspace = monitor ? monitor.activeWorkspace as HyprlandWorkspace : null
            if (!workspace || workspace.id <= 0)
                return {ok: false, error: "Open a regular workspace before restoring this window."}
            Hyprland.dispatch('hl.dsp.window.move({ window = ' + target + ', workspace = ' +
                              JSON.stringify(String(workspace.id)) + ', follow = true })')
        } else {
            Hyprland.dispatch("hl.dsp.focus({ window = " + target + " })")
        }
        return {ok: true, status: "requested", address: address}
    }
}
