import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import Quickshell.Io
import "HudModel.js" as Hud
import "style"

PanelWindow {
    id: root
    property bool themeMode: false
    property bool showShortcuts: false
    property bool trackWindows: false
    property var hudRects: []
    readonly property HyprlandMonitor monitor: screen && trackWindows ? Hyprland.monitorFor(screen) : null
    readonly property bool hasWidgets: (hudRects || []).length > 0
    readonly property var occupied: {
        if (!hasWidgets) return []
        const bounds = hudRects.slice()
        if (!monitor) return bounds
        for (const window of Hyprland.toplevels.values) {
            const data = window.lastIpcObject
            if (!data || window.monitor !== monitor ||
                (window.workspace !== monitor.activeWorkspace && !data.pinned) ||
                data.mapped === false || data.hidden || !data.at || !data.size ||
                data.size[0] <= 0 || data.size[1] <= 0) continue
            bounds.push({x: data.at[0] - monitor.x, y: data.at[1] - monitor.y,
                width: data.size[0], height: data.size[1]})
        }
        return bounds
    }
    property string dock: ""
    readonly property var placement: Hud.reactorPlacement(width, height, occupied, dock)
    onPlacementChanged: {
        if ((placement.size > 0 || !occupied.length) && dock !== placement.corner) {
            Qt.callLater(() => {
                if (dock !== placement.corner) dock = placement.corner
            })
        }
    }
    property bool voiceMuted: false
    property real voiceEnergy: 0
    property string voiceState: "standby"
    anchors { left: true; right: true; top: true; bottom: true }
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.namespace: "jarvis-core"
    WlrLayershell.layer: themeMode ? WlrLayer.Bottom : WlrLayer.Background
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    mask: Region { item: reactor.visible ? reactor : null }
    color: "#05080F"

    Canvas {
        id: bgCanvas
        anchors.fill: parent
        readonly property real glowX: root.placement.size > 0 ? (root.placement.x + root.placement.size * 0.5) : width * 0.5
        readonly property real glowY: root.placement.size > 0 ? (root.placement.y + root.placement.size * 0.5) : height * 0.5
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            const glow = ctx.createRadialGradient(glowX, glowY, 0, glowX, glowY, Math.max(width,height)*0.68)
            glow.addColorStop(0, "#0C2230")
            glow.addColorStop(0.58, "#08141E")
            glow.addColorStop(1, "#050A10")
            ctx.fillStyle = glow
            ctx.fillRect(0,0,width,height)
            ctx.fillStyle = "#193743"
            for (let y=23; y<height; y+=33)
                for (let x=19; x<width; x+=33) ctx.fillRect(x,y,1,1)
        }
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        Connections {
            target: root
            function onPlacementChanged() { bgCanvas.requestPaint() }
        }
    }

    Process {
        id: listenToggle
        command: [Quickshell.env("HOME") + "/.local/bin/jarvis", "listen", "toggle"]
    }
    ArcReactorCore {
        id: reactor
        visible: root.placement.size > 0
        x: root.placement.x
        y: root.placement.y
        width: root.placement.size
        height: width
        Behavior on x { NumberAnimation { duration: Style.duration(240); easing.type: Easing.Bezier; easing.bezierCurve: Style.easeOut } }
        Behavior on y { NumberAnimation { duration: Style.duration(240); easing.type: Easing.Bezier; easing.bezierCurve: Style.easeOut } }
        Behavior on width { NumberAnimation { duration: Style.duration(240); easing.type: Easing.Bezier; easing.bezierCurve: Style.easeOut } }
        voiceState: root.voiceState
        muted: root.voiceMuted
        energy: root.voiceEnergy
        scale: orbitHover.hovered ? 1.025 : 1
        Behavior on scale { NumberAnimation { duration: Style.duration(160); easing.type: Easing.OutCubic } }
        HoverHandler { id: orbitHover }
        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: if (!listenToggle.running) listenToggle.running = true
        }
    }

    Text {
        visible: root.showShortcuts && !root.occupied.length
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 24
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.max(0, parent.width - 32)
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: qsTr("Super+Space  Apps and commands     ·     Super+N  Notifications")
        textFormat: Text.PlainText
        color: "#ACBED0"
        font.pixelSize: 13
    }

}
