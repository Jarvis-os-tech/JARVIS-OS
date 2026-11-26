import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "OrbitState.js" as OrbitState

Item {
    id: root
    property string voiceState: "connecting"
    property bool standby: false
    property bool muted: false
    property string activityLabel: "Ready"
    property real micLevel: 0.0
    property real cpuPercent: 0.0
    property real ramPercent: 0.0
    property real ramUsed: 0.0

    property var reaction: OrbitState.initial()
    readonly property string displayState: reaction.state
    signal reacted(string gesture)

    function acceptStatus(payload) {
        reaction = OrbitState.update(reaction, payload, Date.now());
        micLevel = reaction.level;
        muted = displayState === "disabled";
        standby = displayState === "standby";
        if (reaction.gesture) reacted(reaction.gesture);
    }

    // 1. Live Voice State Polling (every 200ms)
    Process {
        id: stateProc
        command: ["sh", "-c", "cat ${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/jarvis/state.json 2>/dev/null || echo '{}'"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                try { root.acceptStatus(JSON.parse(text)); }
                catch (error) { root.acceptStatus(null); }
            }
        }
    }

    Timer {
        interval: 200
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: {
            if (!stateProc.running)
                stateProc.running = true;
        }
    }

    // 2. Real-time Telemetry Polling (every 1.5s)
    Process {
        id: telemetryProc
        command: ["/home/g0pi/.local/bin/jarvis-sysinfo"]
        running: false
        stdout: SplitParser {
            onRead: function(line) {
                try {
                    var data = JSON.parse(line || "{}");
                    if (data.cpu !== undefined) root.cpuPercent = Number(data.cpu) || 0.0;
                    if (data.ram !== undefined) root.ramPercent = Number(data.ram) || 0.0;
                    if (data.ram_used !== undefined) root.ramUsed = Number(data.ram_used) || 0.0;
                } catch (err) {}
            }
        }
    }

    Timer {
        interval: 1500
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: {
            if (!telemetryProc.running)
                telemetryProc.running = true;
        }
    }

    // 3. Mute Toggle Process
    Process {
        id: muteProc
        command: ["/home/g0pi/.local/bin/jarvis-voice-toggle"]
    }

    function toggleMute() {
        if (!muteProc.running) {
            muteProc.running = true;
        }
    }

    // Top-level Floating Holographic Stark HUD Window
    Variants {
        model: Quickshell.screens
        PanelWindow {
            id: panel
            required property var modelData
            screen: modelData
            visible: true
            WlrLayershell.namespace: "jarvis-aura-orbit"
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
            exclusionMode: ExclusionMode.Ignore
            color: "transparent"

            anchors {
                top: true
                right: true
            }
            margins {
                top: 56
                right: 20
            }

            property real dragStartTop: 56
            property real dragStartRight: 20
            implicitWidth: 216
            implicitHeight: 112

            Rectangle {
                id: orbitCard
                anchors.fill: parent
                radius: 18
                color: Qt.rgba(0.027, 0.047, 0.082, 0.82)
                border.color: hover.hovered ? Qt.rgba(0.0, 0.898, 1.0, 0.8) : Qt.rgba(0.0, 0.898, 1.0, 0.35)
                border.width: 1.2

                // Left Wing: Real-Time CPU Telemetry
                Column {
                    anchors.left: parent.left
                    anchors.leftMargin: 12
                    anchors.top: parent.top
                    anchors.topMargin: 16
                    spacing: 3
                    width: 48

                    Text {
                        text: "CPU"
                        color: "#4f7285"
                        font.family: "JetBrainsMono Nerd Font, monospace"
                        font.pixelSize: 8
                        font.weight: Font.Bold
                        font.letterSpacing: 0.5
                    }

                    Text {
                        text: Math.round(root.cpuPercent) + "%"
                        color: root.cpuPercent > 80 ? "#ff3b5c" : "#00e5ff"
                        font.family: "JetBrainsMono Nerd Font, monospace"
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }

                    Rectangle {
                        width: 44
                        height: 3
                        radius: 1.5
                        color: "#132230"
                        Rectangle {
                            width: Math.min(parent.width, parent.width * (root.cpuPercent / 100.0))
                            height: parent.height
                            radius: 1.5
                            color: root.cpuPercent > 80 ? "#ff3b5c" : "#00e5ff"
                        }
                    }
                }

                // Center: Animated Glowing JARVIS Orbit
                Item {
                    id: orbitCenter
                    anchors.centerIn: parent
                    width: 76
                    height: 76

                    Rectangle {
                        anchors.centerIn: parent
                        width: 66
                        height: 66
                        radius: 33
                        color: Qt.rgba(0.0, 0.1, 0.18, 0.45)
                        border.color: Qt.rgba(0.0, 0.898, 1.0, hover.hovered ? 0.45 : 0.2)
                        border.width: 1
                    }

                    AuraFieldOrbit {
                        id: aura
                        anchors.centerIn: parent
                        width: 78
                        height: 78
                        orbitState: root.displayState
                        level: root.micLevel
                        scale: hover.hovered ? 1.08 : 1
                        Behavior on scale { NumberAnimation { duration: 160 } }
                        Connections {
                            target: root
                            function onReacted(gesture) {
                                if (gesture === "roll") roll.restart();
                                else if (gesture === "nod") nod.restart();
                                else if (gesture === "recoil") recoil.restart();
                            }
                        }
                        NumberAnimation { id: roll; target: aura; property: "rotation"; from: 0; to: 360; duration: 700; easing.type: Easing.InOutCubic }
                        SequentialAnimation {
                            id: nod
                            NumberAnimation { target: aura; property: "translationY"; to: 5; duration: 110 }
                            NumberAnimation { target: aura; property: "translationY"; to: 0; duration: 170 }
                        }
                        SequentialAnimation {
                            id: recoil
                            NumberAnimation { target: aura; property: "translationX"; to: -6; duration: 70 }
                            NumberAnimation { target: aura; property: "translationX"; to: 5; duration: 90 }
                            NumberAnimation { target: aura; property: "translationX"; to: 0; duration: 110 }
                        }
                        property real translationX: 0
                        property real translationY: 0
                        transform: Translate { x: aura.translationX; y: aura.translationY }
                    }
                }

                // Right Wing: Real-Time RAM Telemetry
                Column {
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    anchors.top: parent.top
                    anchors.topMargin: 16
                    horizontalAlignment: Text.AlignRight
                    spacing: 3
                    width: 48

                    Text {
                        anchors.right: parent.right
                        text: "RAM"
                        color: "#4f7285"
                        font.family: "JetBrainsMono Nerd Font, monospace"
                        font.pixelSize: 8
                        font.weight: Font.Bold
                        font.letterSpacing: 0.5
                    }

                    Text {
                        anchors.right: parent.right
                        text: Math.round(root.ramPercent) + "%"
                        color: root.ramPercent > 85 ? "#ff3b5c" : "#00e5ff"
                        font.family: "JetBrainsMono Nerd Font, monospace"
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }

                    Rectangle {
                        anchors.right: parent.right
                        width: 44
                        height: 3
                        radius: 1.5
                        color: "#132230"
                        Rectangle {
                            anchors.right: parent.right
                            width: Math.min(parent.width, parent.width * (root.ramPercent / 100.0))
                            height: parent.height
                            radius: 1.5
                            color: root.ramPercent > 85 ? "#ff3b5c" : "#00e5ff"
                        }
                    }
                }

                // Bottom: High-Tech Status Pill
                Row {
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 8
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: 5

                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 5
                        height: 5
                        radius: 2.5
                        color: root.muted ? "#ff3b5c"
                             : root.displayState === "standby" ? "#64748b"
                             : root.displayState === "speaking" ? "#ffb86b"
                             : root.displayState === "thinking" ? "#a855f7"
                             : root.displayState === "listening" ? "#00e5ff"
                             : "#00f0a8"
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: root.muted ? "MUTED"
                            : root.displayState === "standby" ? "STANDBY"
                            : root.displayState === "speaking" ? "SPEAKING"
                            : root.displayState === "thinking" ? "THINKING"
                            : root.displayState === "listening" ? "LISTENING"
                            : root.displayState === "complete" ? "COMPLETE"
                            : root.displayState === "alert" ? "ALERT"
                            : root.displayState === "offline" ? "OFFLINE"
                            : root.displayState === "connecting" ? "CONNECTING"
                            : "JARVIS LIVE"
                        color: root.muted ? "#ff8da1"
                             : root.displayState === "standby" ? "#94a3b8"
                             : "#d8f6ff"
                        font.family: "JetBrainsMono Nerd Font, monospace"
                        font.pixelSize: 8
                        font.weight: Font.Bold
                        font.letterSpacing: 0.8
                    }
                }

                HoverHandler { id: hover }
                DragHandler {
                    target: null
                    onActiveChanged: if (active) {
                        panel.dragStartTop = panel.margins.top;
                        panel.dragStartRight = panel.margins.right;
                    }
                    onTranslationChanged: {
                        panel.margins.top = Math.max(0, Math.min(panel.screen.height - panel.height, panel.dragStartTop + translation.y));
                        panel.margins.right = Math.max(0, Math.min(panel.screen.width - panel.width, panel.dragStartRight - translation.x));
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        root.toggleMute();
                    }
                }
            }
        }
    }
}
