pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import "HudModel.js" as Hud
import "style"
import "../omarchy-ai.orbit/OrbitState.js" as OrbitState
import "../jarvis_widgets/WidgetModel.js" as Widgets
import "../jarvis_widgets/TaskEvents.js" as Tasks
import "../jarvis_widgets/WorkspaceModel.js" as Workspaces
import "../jarvis_widgets/SessionModel.js" as Session

ShellRoot {
    id: root

    property bool followOmarchyTheme: false
    property bool standaloneMode: false
    readonly property bool liveMode: followOmarchyTheme || standaloneMode
    property string activeTheme: ""
    readonly property bool desktopVisible: !followOmarchyTheme || activeTheme === "jarvis"
    property var voiceSnapshot: ({})
    property var orbitReaction: OrbitState.initial()
    onVoiceSnapshotChanged: {
        const now = voiceClock || Date.now()
        orbitReaction = OrbitState.update(orbitReaction, voiceSnapshot, now)
        syncVoiceTimers(now)
    }
    property bool shellReducedMotion: false
    property bool hyprReducedMotion: false
    readonly property bool reducedMotion: shellReducedMotion || hyprReducedMotion
    onReducedMotionChanged: Style.reduceMotion = reducedMotion
    Component.onCompleted: {
        Style.reduceMotion = reducedMotion
        if (liveMode) hyprAnimProc.running = true
    }
    property double voiceClock: Date.now()
    property string previewVoiceState: "standby"
    readonly property var liveVoice: Hud.voicePresentation(voiceSnapshot, voiceClock)
    readonly property bool voiceMuted: liveMode && liveVoice.muted
    readonly property real voiceEnergy: liveMode ? liveVoice.energy : 0
    property var taskState: Tasks.initial()
    property var workspaceState: Workspaces.initial()
    property bool sessionReady: false
    readonly property bool widgetSessionAvailable: !liveMode || sessionReady
    property string sessionError: ""
    property bool sessionSaved: false
    property string savedSessionText: ""
    property string pendingSessionText: ""
    onDraftsChanged: sessionSaveTimer.restart()
    onWorkspaceStateChanged: sessionSaveTimer.restart()
    onTaskStateChanged: sessionSaveTimer.restart()
    function sessionUnavailable() {
        return {ok: false, error: sessionError || "Widget session is loading", retryable: sessionError === ""}
    }

    function saveSession() {
        if (!liveMode || !sessionReady) return
        const encoded = Session.encode(sourceWidgets, workspaceState, drafts, taskState)
        if (encoded === savedSessionText) { sessionSaved = true; return }
        sessionSaved = false
        pendingSessionText = encoded
        sessionFile.setText(encoded)
    }
    Timer { id: sessionSaveTimer; interval: 150; onTriggered: root.saveSession() }
    FileView {
        id: sessionFile
        path: root.liveMode ? (Quickshell.env("XDG_STATE_HOME") || Quickshell.env("HOME") + "/.local/state") + "/jarvis/widget-session/session.json" : ""
        preload: true
        atomicWrites: true
        blockWrites: true
        printErrors: false
        onLoaded: {
            if (root.sessionReady) return
            try {
                const restored = Session.decode(text(), Date.now())
                root.workspaceState = restored.workspaces
                root.taskState = restored.tasks
                root.commit(restored.widgets)
                root.drafts = restored.drafts
                root.sessionReady = true
                root.savedSessionText = text()
                root.sessionSaved = true
            } catch (error) { root.sessionError = String(error) }
        }
        onLoadFailed: error => {
            root.sessionReady = error === FileViewError.FileNotFound
            if (!root.sessionReady) root.sessionError = "Cannot load saved widget state"
        }
        onSaved: { root.savedSessionText = root.pendingSessionText; root.sessionSaved = true; root.sessionError = "" }
        onSaveFailed: error => { root.sessionSaved = false; root.sessionError = "Cannot save widget state" }
    }
    property bool canvasOpen: true
    property string sendingWidget: ""
    property bool sendingPalette: false
    property var submissionErrors: ({})
    property var submissionFeedback: ({})
    property var entries: []
    property var sourceWidgets: []
    property var drafts: Object.create(null)
    readonly property string voiceState: !liveMode ? previewVoiceState
        : liveVoice.state === "offline" ? "offline"
        : ["complete", "alert", "thinking"].includes(orbitReaction.state) ? orbitReaction.state : liveVoice.state
    property bool paletteOpen: false
    readonly property var pendingApproval: liveMode && voiceState !== "offline" ? voiceSnapshot.pending_approval : null
    property string approvalFeedback: ""
    readonly property string approvalId: pendingApproval?.id || ""
    onApprovalIdChanged: {
        if (approvalId) paletteOpen = false
        approvalFeedback = ""
    }

    property double logoutDeadline: 0
    onPaletteOpenChanged: if (!paletteOpen) logoutDeadline = 0
    property string paletteFeedback: ""
    property string lastWidgetId: ""
    readonly property string deviceWidgetId: "jarvis_device_controls"
    readonly property string mediaWidgetId: "jarvis_media_controls"
    readonly property string audioWidgetId: "jarvis_audio_controls"
    readonly property string systemWidgetId: "jarvis_system_telemetry"
    readonly property string runtimeDir: Quickshell.env("XDG_RUNTIME_DIR")

    onDesktopVisibleChanged: {
        if (!desktopVisible) {
            paletteOpen = false
            voiceStaleTimer.stop()
            reactionSettleTimer.stop()
        } else {
            syncVoiceTimers(Date.now())
        }
        scheduleExpiry()
    }

    function applyVoiceSnapshotText(raw) {
        try {
            applyVoiceSnapshotObject(JSON.parse(raw) || ({}))
        } catch (e) {
            applyVoiceSnapshotObject({})
        }
    }

    function applyVoiceSnapshotObject(payload) {
        voiceClock = Date.now()
        voiceSnapshot = payload
    }

    function syncVoiceTimers(now) {
        if (!desktopVisible || !liveMode) {
            voiceStaleTimer.stop()
            reactionSettleTimer.stop()
            return
        }
        const written = Number(voiceSnapshot.status_written_at) * 1000
        if (Number.isFinite(written) && Math.abs(now - written) <= 5000) {
            voiceStaleTimer.interval = Math.max(50, Math.min(5500, written + 5050 - now))
            voiceStaleTimer.restart()
        } else {
            voiceStaleTimer.stop()
        }
        let settleAt = orbitReaction.completeUntil > now ? orbitReaction.completeUntil + 20 : 0
        const alerts = Array.isArray(voiceSnapshot.recent_alerts) ? voiceSnapshot.recent_alerts : []
        for (const alert of alerts) {
            if (alert && (alert.priority === "critical" || alert.priority === "alert")) {
                const expires = (Number(alert.timestamp) + 6) * 1000
                if (expires > now && (!settleAt || expires + 20 < settleAt))
                    settleAt = expires + 20
            }
        }
        if (settleAt > now) {
            reactionSettleTimer.interval = Math.max(20, Math.min(6500, settleAt - now))
            reactionSettleTimer.restart()
        } else {
            reactionSettleTimer.stop()
        }
    }

    FileView {
        path: root.followOmarchyTheme ? Quickshell.env("HOME") + "/.local/state/omarchy/current/theme.name" : ""
        preload: true
        watchChanges: root.followOmarchyTheme
        onFileChanged: reload()
        onLoaded: root.activeTheme = text().trim().toLowerCase()
    }

    FileView {
        id: shellConfigFile
        path: root.liveMode ? Quickshell.env("HOME") + "/.config/omarchy/shell.json" : ""
        preload: true
        watchChanges: path !== ""
        printErrors: false
        onFileChanged: reload()
        onLoaded: {
            try {
                const cfg = JSON.parse(text()) || ({})
                let reduced = cfg.reducedMotion === true
                if (!reduced && Array.isArray(cfg.plugins)) {
                    const island = cfg.plugins.find(item => item && item.id === "omarchy-dynamic-island")
                    reduced = !!(island && island.reducedMotion === true)
                }
                root.shellReducedMotion = reduced
            } catch (e) {
                root.shellReducedMotion = false
            }
        }
        onLoadFailed: root.shellReducedMotion = false
    }

    Process {
        id: hyprAnimProc
        command: ["hyprctl", "-j", "getoption", "animations:enabled"]
        stdout: StdioCollector {
            waitForEnd: true
            onStreamFinished: {
                try {
                    root.hyprReducedMotion = JSON.parse(text || "{}").bool === false
                } catch (e) {}
            }
        }
    }

    Connections {
        target: Hyprland
        function onRawEvent(event) {
            if (root.liveMode && event && String(event.name) === "configreloaded" && !hyprAnimProc.running)
                hyprAnimProc.running = true
        }
    }

    FileView {
        id: stateFileView
        path: root.desktopVisible && root.liveMode && root.runtimeDir
            ? root.runtimeDir + "/jarvis/state.json" : ""
        preload: true
        watchChanges: path !== ""
        printErrors: false
        onFileChanged: reload()
        onLoaded: root.applyVoiceSnapshotText(text())
        onLoadFailed: root.applyVoiceSnapshotObject({})
    }

    Timer {
        id: voiceStaleTimer
        repeat: false
        onTriggered: {
            const now = Date.now()
            root.voiceClock = now
            root.orbitReaction = OrbitState.update(root.orbitReaction, root.voiceSnapshot, now)
            root.syncVoiceTimers(now)
        }
    }

    Timer {
        id: reactionSettleTimer
        repeat: false
        onTriggered: {
            const now = Date.now()
            root.voiceClock = now
            root.orbitReaction = OrbitState.update(root.orbitReaction, root.voiceSnapshot, now)
            root.syncVoiceTimers(now)
        }
    }

    function commit(widgets) {
        const feedback = {}
        for (const widget of widgets) {
            const old = sourceWidgets.find(item => item.id === widget.id)
            const changed = old && JSON.stringify(old.data) !== JSON.stringify(widget.data)
            if (old && !changed && submissionFeedback[widget.id]) feedback[widget.id] = submissionFeedback[widget.id]
            if (changed && widget.kind === "view" && drafts[widget.id] && Object.keys(drafts[widget.id]).some(key =>
                old.data.state?.[key] !== widget.data.state?.[key] && drafts[widget.id][key] !== widget.data.state?.[key]))
                feedback[widget.id] = "Source changed. Review your local edits before applying."
        }
        submissionFeedback = feedback
        entries = Hud.reconcile(entries, widgets, Date.now())
        sourceWidgets = widgets
        workspaceState = Workspaces.prune(sourceWidgets, workspaceState)
        const kept = Object.create(null)
        const errors = Object.create(null)
        for (const widget of widgets) {
            if (drafts[widget.id] !== undefined && widget.kind === "view") kept[widget.id] = Widgets.compatibleDraft(widget.data, drafts[widget.id])
            if (submissionErrors[widget.id]) errors[widget.id] = submissionErrors[widget.id]
        }
        drafts = kept
        submissionErrors = errors
        sessionSaveTimer.restart()
    }

    function checkData(value, depth) {
        if (depth > 12) throw Error("Payload is nested too deeply")
        if (typeof value === "number" && !Number.isFinite(value)) throw Error("Invalid number")
        if (value && typeof value === "object") {
            for (const key of Object.keys(value)) {
                if (["__proto__", "constructor", "prototype"].includes(key))
                    throw Error("Invalid payload key")
                checkData(value[key], depth + 1)
            }
        }
    }

    function event(message, controller) {
        try {
            const limit = controller ? 65536 : 16383
            if (typeof message !== "string" || message.length === 0 ||
                message.length > limit || (!controller && encodeURIComponent(message).replace(/%[0-9A-F]{2}/g, "x").length > limit))
                throw Error("Invalid event size")
            const request = JSON.parse(message)
            if (!request || typeof request !== "object" || Array.isArray(request) ||
                Object.keys(request).some(key => !["action", "id", "payload"].includes(key)))
                throw Error("Invalid event envelope")
            const payload = request.payload === undefined ? {} : request.payload
            if (!payload || typeof payload !== "object" || Array.isArray(payload))
                throw Error("Payload must be an object")
            checkData(payload, 0)
            if (request.action === "set_voice_state") {
                if ("id" in request || Object.keys(payload).length !== 1)
                    throw Error("Invalid voice event")
                if (!["idle", "standby", "listening", "thinking", "working", "speaking"].includes(payload.state))
                    throw Error("Unknown voice state")
                previewVoiceState = payload.state
                return {ok: true}
            }
            if (!widgetSessionAvailable) return sessionUnavailable()
            const id = request.id
            if (typeof id !== "string" || !/^[A-Za-z0-9_-]{1,80}$/.test(id))
                throw Error("Invalid widget ID")
            const existing = sourceWidgets.find(widget => widget.id === id)
            if (["spawn_widget", "update_widget"].includes(request.action) && existing?.workspace)
                throw Error("Update this panel through workspace " + existing.workspace)
            switch (request.action) {
            case "spawn_widget":
            case "update_widget": {
                if ([systemWidgetId, audioWidgetId, mediaWidgetId, deviceWidgetId].includes(id)) throw Error("This ID is reserved for native controls")
                if (request.action === "update_widget" && !existing)
                    throw Error("Widget not found")
                if (request.action === "spawn_widget" && existing)
                    throw Error("Use update_widget for an existing ID")
                const previous = existing ? {
                    kind: existing.kind, title: existing.title,
                    data: existing.data, side: existing.side,
                    expires_seconds: existing.lifetime
                } : {}
                const input = Object.assign({expires_seconds: payload.kind === "view" ? 0 : 25}, previous, payload, {id: id})
                if (input.side !== undefined && !["left", "right"].includes(input.side))
                    throw Error("Invalid widget side")
                const kinds = ["text", "progress", "table", "chart", "view"]
                if (controller) kinds.push("image", "pip", "qr")
                if (!kinds.includes(input.kind))
                    throw Error("Unsupported preview widget kind")
                if (existing && input.kind !== existing.kind)
                    throw Error("A widget update must keep its kind")
                // Revision comes from this request; partial updates cannot inherit it.
                const checked = Workspaces.checkUpdate(workspaceState, input)
                if (checked.stale || checked.dismissed)
                    return {ok: true, id: id, stale: !!checked.stale, dismissed: !!checked.dismissed}
                const widget = Widgets.validate(input)
                widget.side = input.side
                if (existing) widget.geometry = existing.geometry
                widget.lifetime = input.expires_seconds
                if (existing && payload.expires_seconds === undefined)
                    widget.expiresAt = existing.expiresAt
                const widgets = Widgets.upsert(sourceWidgets, widget)
                workspaceState = checked.state
                commit(widgets)
                saveSession()
                canvasOpen = true
                lastWidgetId = id
                break
            }
            case "pin_widget":
                if (Object.keys(payload).some(key => key !== "pinned") ||
                    (payload.pinned !== undefined && typeof payload.pinned !== "boolean"))
                    throw Error("pinned must be a boolean")
                if (!existing) throw Error("Widget not found")
                commit(sourceWidgets.map(widget => widget.id === id
                    ? Object.assign({}, widget, {pinned: payload.pinned !== false}) : widget))
                break
            case "dismiss_widget":
                if (Object.keys(payload).length) throw Error("Unexpected dismissal payload")
                if (existing) workspaceState = Workspaces.dismiss(workspaceState, existing)
                if (existing && existing.task) taskState = Tasks.hide(taskState, id)
                commit(Widgets.manage(sourceWidgets, id, "dismiss"))
                saveSession()
                break
            case "restore_widget":
                if (Object.keys(payload).length) throw Error("Unexpected restore payload")
                if (!existing) throw Error("Widget not found")
                entries = Hud.manage(entries, id, "restore", Date.now())
                break
            default:
                throw Error("Unknown event action")
            }
            return {ok: true, id: id}
        } catch (error) {
            return {ok: false, error: String(error)}
        }
    }

    function action(actionName, id, payload) {
        return event(JSON.stringify({action: actionName, id: id, payload: payload || {}}))
    }

    function formState(widget) {
        return widget.kind === "view"
            ? Hud.restoreDraft(widget.data.state, drafts[widget.id] || {})
            : {}
    }

    function setGeometry(id, geometry) {
        if (!widgetSessionAvailable) return sessionUnavailable()
        if (!sourceWidgets.some(item => item.id === id)) throw Error("Widget not found")
        if (![geometry.x, geometry.y, geometry.w, geometry.h].every(n => typeof n === "number" && Number.isFinite(n) && n >= 0 && n <= 1) || geometry.w <= 0 || geometry.h <= 0)
            throw Error("Invalid widget geometry")
        commit(sourceWidgets.map(item => item.id === id ? Object.assign({}, item, {geometry: geometry}) : item))
    }

    function clearWidgets(keepPinned) {
        if (!widgetSessionAvailable) return sessionUnavailable()
        workspaceState = Workspaces.clear(workspaceState, sourceWidgets, keepPinned)
        // Do not refill cleared space with old task cards waiting for capacity.
        taskState = Object.assign({}, taskState, {pending: {}})
        for (const widget of sourceWidgets)
            if (widget.task && (!keepPinned || !widget.pinned))
                taskState = Tasks.hide(taskState, widget.id)
        commit(sourceWidgets.filter(widget => keepPinned && widget.pinned))
        saveSession()
        return {ok: true, retained: sourceWidgets.length, saved: sessionSaved, persistenceError: sessionError}
    }

    function clearHud() {
        const result = clearWidgets(true)
        if (result.ok && standaloneMode) result.window = appStage.parkActiveFloating()
        return result
    }

    function submitWidget(id, prompt, values) {
        if (!liveMode || !widgetSessionAvailable || sendingWidget !== "" || sendingPalette) return
        const message = prompt + "\nWidget context: " + JSON.stringify({id: id, state: values})
        if (message.length > 16000) {
            submissionErrors = Object.assign({}, submissionErrors, {[id]: "Widget request exceeds the size limit."})
            return
        }
        submissionErrors = Object.assign({}, submissionErrors, {[id]: ""})
        submissionFeedback = Object.assign({}, submissionFeedback, {[id]: "Sending request…"})
        sendingWidget = id
        submitProcess.command = ["python3", "-u", Quickshell.shellPath("jarvis_widgets/backend.py"), "send", message]
        submitProcess.running = true
    }

    ApplicationStage { id: appStage }

    NotificationCenter {
        id: notifications
        active: root.standaloneMode
    }

    function paletteResult(result) {
        paletteFeedback = result.ok ? "" : result.error
        if (result.ok) paletteOpen = false
    }

    Process {
        id: submitProcess
        onExited: code => {
            if (root.sendingPalette) {
                root.sendingPalette = false
                root.paletteFeedback = code === 0 ? "Sent to JARVIS." : "The voice session could not accept the request."
                return
            }
            root.submissionFeedback = Object.assign({}, root.submissionFeedback, {[root.sendingWidget]: code === 0 ? "Request sent. Waiting for source update." : ""})
            if (code !== 0)
                root.submissionErrors = Object.assign({}, root.submissionErrors, {
                    [root.sendingWidget]: "The voice session could not accept the request."
                })
            root.sendingWidget = ""
        }
    }

    function showNativeWidget(id, title, kind) {
        if (!widgetSessionAvailable) return sessionUnavailable()
        if (!desktopVisible) return {ok: false, error: "The JARVIS HUD is hidden"}
        try {
            if (sourceWidgets.some(widget => widget.id === id))
                entries = Hud.manage(entries, id, "restore", Date.now())
            else
                commit(Widgets.upsert(sourceWidgets, {
                    id: id, title: title, kind: kind,
                    side: "left", pinned: false, expiresAt: 0, data: {}
                }))
            canvasOpen = true
            lastWidgetId = id
            const item = entries.find(widget => widget.id === id)
            return {ok: true, id: item.id, mounted: item.mounted}
        } catch (error) { return {ok: false, error: String(error)} }
    }

    Process {
        id: sessionAction
        onExited: code => {
            if (code !== 0) root.paletteFeedback = "The session action could not be completed."
        }
    }

    function runPalette(text) {
        const command = text.trim().toLowerCase()
        const current = entries.find(widget => widget.id === lastWidgetId && widget.mounted) ||
            entries.filter(widget => widget.mounted).slice(-1)[0]
        if (command.startsWith("open ")) {
            const apps = appStage.findApps(text.trim().slice(5))
            const exact = apps.find(app => app.id.toLowerCase() === command.slice(5) ||
                                           app.name.toLowerCase() === command.slice(5))
            if (exact) paletteResult(appStage.launch(exact.id))
            else paletteFeedback = apps.length ? "Choose a matching application." : "No installed app matched."
        } else if (["apps", "applications", "open"].includes(command)) {
            paletteFeedback = appStage.applications.length ? "Choose an application." : "No installed apps found."
        } else if (command === "windows" || command.startsWith("windows ")) {
            paletteFeedback = appStage.windows.length ? "" : "No open windows."
        } else if (command.startsWith("ask ") && text.trim().slice(4).trim()) {
            if (sendingWidget !== "" || sendingPalette) {
                paletteFeedback = "A request is already being sent."
                return
            }
            sendingPalette = true
            paletteFeedback = ""
            submitProcess.command = ["python3", "-u", Quickshell.shellPath("jarvis_widgets/backend.py"),
                                     "send", text.trim().slice(4)]
            submitProcess.running = true
        } else if (command === "lock session" && liveMode) {
            if (sessionAction.running) return
            sessionAction.command = standaloneMode
                ? [Quickshell.shellPath("../bin/jarvis-lock")]
                : ["omarchy", "system", "lock"]
            sessionAction.running = true
        } else if (command === "log out" && standaloneMode) {
            logoutDeadline = Date.now() + 10000
            paletteFeedback = "Type Confirm logout within 10 seconds to end this session."
        } else if (command === "confirm logout" && standaloneMode) {
            if (!logoutDeadline || Date.now() > logoutDeadline || sessionAction.running) {
                logoutDeadline = 0
                paletteFeedback = "Type Log out to start a new confirmation."
                return
            }
            logoutDeadline = 0
            sessionAction.command = ["hyprctl", "dispatch", Hyprland.usingLua ? "hl.dsp.exit()" : "exit"]
            sessionAction.running = true
        } else if (command === "notifications" && standaloneMode) {
            notifications.toggleHistory()
            paletteOpen = false
        } else if (command === "show system") {
            paletteResult(showNativeWidget(systemWidgetId, "System load", "system_telemetry"))
        } else if (command === "audio controls") {
            paletteResult(showNativeWidget(audioWidgetId, "Audio controls", "audio_controls"))
        } else if (command === "device controls") {
            paletteResult(showNativeWidget(deviceWidgetId, "Device controls", "device_controls"))
        } else if (command === "media controls") {
            paletteResult(showNativeWidget(mediaWidgetId, "Media controls", "media_controls"))
        } else if (command === "clear hud" || command === "dismiss all") {
            paletteResult(clearHud())
        } else if (["pin that", "unpin that", "dismiss that"].includes(command) && current) {
            const receipt = command === "dismiss that" ? action("dismiss_widget", current.id)
                : action("pin_widget", current.id, {pinned: command === "pin that"})
            paletteFeedback = receipt.ok ? "" : receipt.error
            if (receipt.ok) paletteOpen = false
        } else {
            if (appStage.findApps(text.trim()).length) {
                paletteFeedback = "Choose a matching application."
                return
            }
            paletteFeedback = "Try Open Firefox, Windows, Device controls, Audio controls, Media controls, Show system, Lock session, or Ask followed by a request."
        }
    }

    SocketServer {
        active: root.desktopVisible && root.runtimeDir !== ""
        path: root.runtimeDir + "/jarvis-hud-preview.sock"
        handler: Component {
            Socket {
                id: connection
                property bool handled: false
                property Timer connectionLimit: Timer {
                    interval: 2000
                    running: connection.connected
                    onTriggered: connection.connected = false
                }
                parser: SplitParser {
                    onRead: line => {
                        if (connection.handled) return
                        connection.handled = true
                        connection.write(JSON.stringify(root.event(line)) + "\n")
                        connection.flush()
                    }
                }
            }
        }
    }

    IpcHandler {
        target: "jarvis-hud-preview"
        function status(): string {
            return JSON.stringify({ok: true, engine: "jarvis-hud", sessionSaved: root.sessionSaved, sessionError: root.sessionError, visible: root.desktopVisible,
                voice: root.voiceState, palette: root.paletteOpen, taskCursor: root.taskState.cursor,
                active_widget_id: root.lastWidgetId,
                notificationCount: notifications.count, systemLoad: widgetCanvas.telemetryStatus(), audio: widgetCanvas.nativeStatus("audio"),
                media: widgetCanvas.nativeStatus("media"), devices: widgetCanvas.nativeStatus("devices"),
                widgets: root.entries.map(item => ({
                    id: item.id, title: item.title, kind: item.kind, side: item.side,
                    revision: item.workspace ? root.workspaceState.groups[Workspaces.key(item.workspace)]?.revision || 0 : root.workspaceState.versions[Workspaces.key(item.id)]?.revision || 0, geometry: item.geometry || null, workspace: item.workspace || "", section: item.section || "", mounted: item.mounted, pinned: item.pinned, state: root.formState(item)
                }))})
        }
        function showSystem(): string {
            return JSON.stringify(root.showNativeWidget(root.systemWidgetId, "System load", "system_telemetry"))
        }
        function showAudio(): string {
            return JSON.stringify(root.showNativeWidget(root.audioWidgetId, "Audio controls", "audio_controls"))
        }
        function toggleNotifications(): void { notifications.toggleHistory() }
        function showDevices(): string {
            return JSON.stringify(root.showNativeWidget(root.deviceWidgetId, "Device controls", "device_controls"))
        }
        function showMedia(): string {
            return JSON.stringify(root.showNativeWidget(root.mediaWidgetId, "Media controls", "media_controls"))
        }
        function desktop(json: string): string {
            try {
                if (!root.desktopVisible) throw Error("The JARVIS theme is inactive")
                const request = JSON.parse(json)
                if (request.action === "applications")
                    return JSON.stringify({ok: true, apps: appStage.findApps(String(request.query || ""))
                        .map(app => ({id: app.id, name: app.name}))})
                if (request.action === "windows")
                    return JSON.stringify({ok: true, windows: appStage.listWindows()})
                if (request.action === "launch") return JSON.stringify(appStage.launch(request.id))
                return JSON.stringify(appStage.control(request.action, request.address))
            } catch (error) { return JSON.stringify({ok: false, error: String(error)}) }
        }
        function present(json: string): string {
            try {
                if (!root.widgetSessionAvailable) return JSON.stringify(root.sessionUnavailable())
                if (!root.desktopVisible) throw Error("The JARVIS theme is inactive")
                const payload = JSON.parse(json)
                if (payload.kind === "workspace") {
                    const result = Workspaces.apply(root.sourceWidgets, root.workspaceState, payload)
                    root.workspaceState = result.state
                    root.commit(result.items)
                    root.saveSession()
                    root.canvasOpen = true
                    const panels = root.entries.filter(item => item.workspace === payload.id)
                    if (panels.length) root.lastWidgetId = panels[panels.length - 1].id
                    return JSON.stringify({ok: true, id: payload.id, stale: !!result.stale,
                        dismissed: !!result.dismissed, panels: panels.map(item => ({id: item.id, section: item.section, mounted: item.mounted}))})
                }
                const action = root.sourceWidgets.some(item => item.id === payload.id) ? "update_widget" : "spawn_widget"
                const receipt = root.event(JSON.stringify({action: action, id: payload.id, payload: payload}), true)
                if (receipt.ok && !receipt.stale && !receipt.dismissed) {
                    const mounted = root.entries.find(item => item.id === payload.id)
                    receipt.mounted = !!mounted?.mounted
                }
                return JSON.stringify(receipt)
            } catch (error) { return JSON.stringify({ok: false, error: String(error)}) }
        }
        function manage(json: string): string {
            try {
                if (!root.widgetSessionAvailable) return JSON.stringify(root.sessionUnavailable())
                const request = JSON.parse(json)
                if (request.id && root.workspaceState.groups[Workspaces.key(request.id)]) {
                    const members = root.sourceWidgets.filter(item => item.workspace === request.id)
                    if (request.action === "dismiss") {
                        root.workspaceState.groups = Object.assign({}, root.workspaceState.groups,
                            {[Workspaces.key(request.id)]: Object.assign({}, root.workspaceState.groups[Workspaces.key(request.id)], {closed: true})})
                        root.commit(root.sourceWidgets.filter(item => item.workspace !== request.id))
                        root.saveSession()
                        return JSON.stringify({ok: true, id: request.id, removed: members.length})
                    }
                    if (request.action === "pin" || request.action === "unpin") {
                        for (const member of members) root.action("pin_widget", member.id, {pinned: request.action === "pin"})
                        return JSON.stringify({ok: true, id: request.id})
                    }
                    if (["focus", "float", "canvas"].includes(request.action)) {
                        for (const member of members) root.entries = Hud.manage(root.entries, member.id, "restore", Date.now())
                        root.canvasOpen = true
                        return JSON.stringify({ok: true, id: request.id, panels: root.entries.filter(item => item.workspace === request.id).map(item => ({id: item.id, mounted: item.mounted}))})
                    }
                    if (request.action === "state") return JSON.stringify({ok: true, id: request.id, revision: root.workspaceState.groups[Workspaces.key(request.id)].revision, dismissed: root.workspaceState.groups[Workspaces.key(request.id)].closed,
                        panels: members.map(item => ({id: item.id, section: item.section, state: root.formState(item)}))})
                }
                const widget = root.sourceWidgets.find(item => item.id === (request.id || root.lastWidgetId))
                    || (!request.id && root.sourceWidgets[root.sourceWidgets.length - 1])
                if (!widget && request.action === "state" && request.id && root.workspaceState.dismissed[Workspaces.key(request.id)])
                    return JSON.stringify({ok: true, id: request.id, dismissed: true,
                        revision: Workspaces.dismissalRevision(root.workspaceState.dismissed[Workspaces.key(request.id)], root.workspaceState.versions[Workspaces.key(request.id)]?.revision)})
                if (!widget) throw Error("Widget not found")
                if (request.action === "select") {
                    if (widget.kind !== "view") throw Error("Selectable view widget not found")
                    const index = request.index
                    if (typeof index !== "number" || !Number.isInteger(index) || index < 1 || index > 9)
                        throw Error("Choice index must be an integer 1–9")
                    const choice = Widgets.findChoice(widget.data && widget.data.layout, index)
                    if (!choice) throw Error("Choice not found")
                    const nextState = Widgets.choiceSelectionState(root.formState(widget), choice)
                    const nextDrafts = Object.create(null)
                    Object.assign(nextDrafts, root.drafts, {[widget.id]: Hud.draftChanges(widget.data.state || {}, nextState)})
                    root.drafts = nextDrafts
                    root.lastWidgetId = widget.id
                    if (request.dismiss === true) root.action("dismiss_widget", widget.id)
                    return JSON.stringify({
                        ok: true, id: widget.id, action: "select",
                        selected: {
                            index: choice.index,
                            id: choice.id || ("choice_" + choice.index),
                            label: choice.label,
                            detail: choice.detail || "",
                            value: choice.value !== undefined ? choice.value : choice.label,
                            prompt: choice.prompt
                        },
                        state: nextState
                    })
                }
                if (request.action === "state") return JSON.stringify({ok: true, id: widget.id, state: root.formState(widget)})
                if (request.action === "dismiss") return JSON.stringify(root.action("dismiss_widget", widget.id))
                if (request.action === "pin" || request.action === "unpin")
                    return JSON.stringify(root.action("pin_widget", widget.id, {pinned: request.action === "pin"}))
                if (["focus", "float", "canvas"].includes(request.action)) {
                    root.canvasOpen = true
                    return JSON.stringify(root.action("restore_widget", widget.id))
                }
                if (request.action === "move") {
                    const geometry = widget.geometry || {x: 0.1, y: 0.1, w: 0.3, h: 0.35}
                    root.setGeometry(widget.id, Object.assign({}, geometry, {x: request.x, y: request.y}))
                    return JSON.stringify({ok: true, id: widget.id})
                }
                throw Error("Unsupported widget action")
            } catch (error) { return JSON.stringify({ok: false, error: String(error)}) }
        }
        function taskEvents(json: string): string {
            try {
                if (!root.widgetSessionAvailable) return JSON.stringify(root.sessionUnavailable())
                if (!root.desktopVisible) throw Error("The JARVIS theme is inactive")
                const result = Tasks.apply(root.sourceWidgets, root.taskState, JSON.parse(json), Date.now())
                root.commit(result.items)
                root.taskState = result.state
                return JSON.stringify({ok: true, accepted: result.accepted, cursor: result.state.cursor})
            } catch (error) { return JSON.stringify({ok: false, error: String(error)}) }
        }
        function open(): string {
            root.canvasOpen = true
            return JSON.stringify({ok: true, mode: "canvas"})
        }
        function close(): string {
            root.canvasOpen = false
            root.paletteOpen = false
            return JSON.stringify({ok: true, mode: "hidden"})
        }
        function input(): string {
            root.paletteOpen = root.desktopVisible
            return JSON.stringify({ok: root.paletteOpen, mode: "input"})
        }
        function closeInput(): string {
            root.paletteOpen = false
            return JSON.stringify({ok: true})
        }
        function clear(): string { return JSON.stringify(root.clearHud()) }
        function clearAll(): string { return JSON.stringify(root.clearWidgets(false)) }
        function togglePalette(): void {
            root.paletteFeedback = ""
            if (root.desktopVisible && !root.approvalId) root.paletteOpen = !root.paletteOpen
        }
        function stop(): void { Qt.quit() }
    }

    readonly property double nextWidgetDeadline: root.desktopVisible ? Hud.deadline(root.entries) : 0
    onNextWidgetDeadlineChanged: scheduleExpiry()
    function scheduleExpiry() {
        if (nextWidgetDeadline > 0) {
            widgetExpiryTimer.interval = Math.max(10, Math.min(60000, nextWidgetDeadline - Date.now()))
            widgetExpiryTimer.restart()
        } else {
            widgetExpiryTimer.stop()
        }
    }

    Timer {
        id: widgetExpiryTimer
        repeat: false
        onTriggered: {
            if (!root.widgetSessionAvailable) return
            const expired = Hud.expired(root.entries, Date.now())
            if (expired.length)
                root.commit(root.sourceWidgets.filter(widget => !expired.includes(widget.id)))
            root.scheduleExpiry()
        }
    }

    LazyLoader {
        active: root.standaloneMode
        SessionBar {
            onAppsRequested: if (!root.approvalId) root.paletteOpen = !root.paletteOpen
            onNotificationsRequested: notifications.toggleHistory()
        }
    }

    CoreCanvas {
        trackWindows: root.liveMode
        hudRects: widgetCanvas.screen === screen ? widgetCanvas.occupiedBounds : []
        visible: root.desktopVisible
        themeMode: root.followOmarchyTheme
        showShortcuts: root.standaloneMode
        voiceState: root.voiceState
        voiceMuted: root.voiceMuted
        voiceEnergy: root.voiceEnergy
    }

    LazyLoader {
        activeAsync: root.paletteOpen && !root.approvalId && !(authentication.item as SessionAuthentication)?.prompting

        CommandPalette {
            feedback: root.paletteFeedback
            stage: appStage
            busy: root.sendingPalette
            onAppRequested: id => root.paletteResult(appStage.launch(id))
            onWindowRequested: (action, address) => root.paletteResult(appStage.control(action, address))
            onSubmitted: text => root.runPalette(text)
            onCloseRequested: root.paletteOpen = false
        }
    }

    Process {
        id: approvalProcess
        onExited: code => {
            if (code !== 0) root.approvalFeedback = qsTr("The action could not be resolved.")
        }
    }

    LazyLoader {
        id: authentication
        active: root.standaloneMode
        SessionAuthentication {}
    }

    LazyLoader {
        active: root.desktopVisible && !!root.pendingApproval && !(authentication.item as SessionAuthentication)?.prompting
        ExecutionAirlock {
            request: root.pendingApproval || ({})
            busy: approvalProcess.running
            feedback: root.approvalFeedback
            onDecided: (requestId, approve) => {
                if (approvalProcess.running || root.pendingApproval?.id !== requestId) return
                approvalProcess.command = ["python3", "-u", Quickshell.shellPath("jarvis_widgets/backend.py"),
                    "approval", requestId, approve ? "approve" : "cancel"]
                approvalProcess.running = true
            }
        }
    }

    WidgetCanvas {
        id: widgetCanvas
        visible: root.desktopVisible && root.canvasOpen
        liveActions: root.liveMode
        reducedMotion: root.reducedMotion
        sendingWidget: root.sendingWidget
        submissionErrors: root.submissionErrors
        submissionFeedback: root.submissionFeedback
        entries: root.entries
        drafts: root.drafts
        apiState: root.voiceState === "offline" ? "Offline" : root.voiceSnapshot.connected === true ? "Connected" : "Unavailable"
        onGeometryRequested: (id, geometry) => root.setGeometry(id, geometry)
        onRestoreRequested: id => root.action("restore_widget", id)
        onDismissRequested: id => root.action("dismiss_widget", id)
        onPinRequested: (id, pinned) => root.action("pin_widget", id, {pinned: pinned})
        onInteractionChanged: (id, active) => {
            if (!root.widgetSessionAvailable) return
            if (active) root.lastWidgetId = id
            root.entries = Hud.interact(root.entries, id, active, Date.now())
        }
        onSubmitted: (id, prompt, values) => root.submitWidget(id, prompt, values)
        onDraftChanged: (id, values) => {
            if (!root.widgetSessionAvailable) return
            const widget = root.sourceWidgets.find(item => item.id === id)
            if (widget && widget.kind === "view")
                root.drafts = Object.assign({}, root.drafts, {[id]: Hud.draftChanges(widget.data.state, values)})
        }
    }
}
