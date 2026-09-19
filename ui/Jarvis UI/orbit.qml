import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Io

ShellRoot {
    id: shellRoot

    // High-speed Unix Domain Socket connection to J.A.R.V.I.S. Core Daemon
    Socket {
        id: ipcSocket
        path: "/tmp/jarvis_ipc.sock"
        connected: true
        parser: SplitParser {
            splitMarker: "\n"
            onRead: data => {
                try {
                    var msg = JSON.parse(data.trim());
                    if (msg.status) hudContainer.systemStatus = msg.status;
                    if (msg.text) hudContainer.systemText = msg.text;
                    if (msg.audioLevel !== undefined) hudContainer.audioLevel = msg.audioLevel;
                    if (msg.telemetry) {
                        hudContainer.cpuUsage = msg.telemetry.cpuUsage || 0;
                        hudContainer.ramUsage = msg.telemetry.ramUsage || 0;
                    }
                } catch (e) {}
            }
        }
        onConnectionStateChanged: {
            if (!connected) reconnectTimer.restart();
        }
        onError: {
            if (!connected) reconnectTimer.restart();
        }
    }

    Timer {
        id: reconnectTimer
        interval: 1000
        repeat: true
        running: !ipcSocket.connected
        onTriggered: {
            ipcSocket.connected = false;
            ipcSocket.connected = true;
        }
    }

    // High-frequency atomic state file polling (100ms) for guaranteed real-time synchronization
    Process {
        id: statePollProc
        command: ["cat", "/tmp/jarvis_state.json"]
        running: false
        stdout: StdioCollector {
            onDataChanged: {
                try {
                    var msg = JSON.parse(text.trim());
                    if (msg.status) hudContainer.systemStatus = msg.status;
                    if (msg.text) hudContainer.systemText = msg.text;
                    if (msg.audioLevel !== undefined) hudContainer.audioLevel = msg.audioLevel;
                    if (msg.telemetry) {
                        hudContainer.cpuUsage = msg.telemetry.cpuUsage || 0;
                        hudContainer.ramUsage = msg.telemetry.ramUsage || 0;
                    }
                } catch (e) {}
            }
        }
    }

    Timer {
        interval: 100
        repeat: true
        running: true
        onTriggered: {
            if (!statePollProc.running) {
                statePollProc.running = true;
            }
        }
    }

    PanelWindow {
        id: root
        visible: true
        color: "transparent"

        // Wayland Layer-Shell Overlay Configuration
        WlrLayershell.namespace: "jarvis-orbit-hud"
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

        // Full-screen fixed transparent surface: eliminates all compositor margin resizes
        anchors {
            top: true
            bottom: true
            left: true
            right: true
        }

        // Only the hudContainer intercepts input; the rest of the display is completely click-through
        mask: Region {
            item: hudContainer
        }

        // HUD Orbit Container: Freely draggable anywhere across the screen
        Item {
            id: hudContainer
            width: 154
            height: 154

            // Default initial placement: bottom center of the display
            x: Math.round((root.width - width) / 2)
            y: root.height - height - 32

            property bool isHovered: false
            property string systemStatus: "active" // active, listening, speaking, thinking, standby
            property string systemText: "ONLINE"
            property real audioLevel: 0.0
            property int cpuUsage: 0
            property int ramUsage: 0

            property color neonCyan: "#00f0ff"
            property color neonBlue: "#38bdf8"
            property color neonPurple: "#a855f7"
            property color neonEmerald: "#10b981"
            property color neonAmber: "#f59e0b"
            property color neonStandby: "#64748b"
            property color hudDarkBg: "#05091a"

            // Dynamic theme neon color based on system lifecycle state
            readonly property color activeNeon: {
                if (systemStatus === "standby") return neonStandby;
                if (systemStatus === "thinking") return neonAmber;
                if (systemStatus === "speaking") return neonCyan;
                if (systemStatus === "listening") return neonEmerald;
                return neonCyan;
            }

            // Semi-transparent Circular Backdrop Disc with Dynamic Glow
            Rectangle {
                id: coreBackdrop
                anchors.centerIn: parent
                width: 140
                height: 140
                radius: 70
                color: hudContainer.hudDarkBg
                opacity: hudContainer.systemStatus === "standby" ? 0.65 : 0.88
                border.color: hudContainer.isHovered ? hudContainer.neonCyan : Qt.rgba(hudContainer.activeNeon.r, hudContainer.activeNeon.g, hudContainer.activeNeon.b, 0.45)
                border.width: hudContainer.isHovered ? 1.5 : 1.0

                Behavior on border.color { ColorAnimation { duration: 250 } }
                Behavior on border.width { NumberAnimation { duration: 150 } }
                Behavior on opacity { NumberAnimation { duration: 250 } }

                // Outer ambient glow ring
                Rectangle {
                    anchors.centerIn: parent
                    width: parent.width + (hudContainer.isHovered || hudContainer.systemStatus === "speaking" ? 12 : 4)
                    height: parent.height + (hudContainer.isHovered || hudContainer.systemStatus === "speaking" ? 12 : 4)
                    radius: width / 2
                    color: "transparent"
                    border.color: Qt.rgba(hudContainer.activeNeon.r, hudContainer.activeNeon.g, hudContainer.activeNeon.b, hudContainer.isHovered ? 0.40 : 0.16)
                    border.width: 1.5

                    Behavior on width { NumberAnimation { duration: 200 } }
                    Behavior on height { NumberAnimation { duration: 200 } }
                    Behavior on border.color { ColorAnimation { duration: 250 } }
                }
            }

            // ================================================================
            // 1. OUTER ROTATING TACTICAL HUD DIAL (Clockwise rotation)
            // ================================================================
            Item {
                id: outerHudDial
                anchors.centerIn: parent
                width: 138
                height: 138

                RotationAnimation on rotation {
                    from: 0
                    to: 360
                    duration: hudContainer.systemStatus === "thinking" ? 6000 : (hudContainer.systemStatus === "speaking" ? 8000 : (hudContainer.isHovered ? 10000 : 16000))
                    loops: Animation.Infinite
                }

                // 4 Cardinal Direction Ticks (N, S, E, W)
                Repeater {
                    model: 4
                    Item {
                        anchors.centerIn: parent
                        width: parent.width
                        height: parent.height
                        rotation: index * 90

                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.top: parent.top
                            anchors.topMargin: 2
                            width: 2
                            height: 7
                            color: hudContainer.activeNeon
                            radius: 1
                            Behavior on color { ColorAnimation { duration: 250 } }
                        }
                    }
                }

                // 12 Perimeter Micro-Tick Marks
                Repeater {
                    model: 12
                    Item {
                        anchors.centerIn: parent
                        width: parent.width
                        height: parent.height
                        rotation: index * 30

                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.top: parent.top
                            anchors.topMargin: 3
                            width: 1
                            height: 3.5
                            color: Qt.rgba(hudContainer.activeNeon.r, hudContainer.activeNeon.g, hudContainer.activeNeon.b, 0.45)
                            Behavior on color { ColorAnimation { duration: 250 } }
                        }
                    }
                }

                // Twin Outer Segment Arcs
                Repeater {
                    model: 2
                    Item {
                        anchors.centerIn: parent
                        width: parent.width
                        height: parent.height
                        rotation: index * 180 + 45

                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.top: parent.top
                            anchors.topMargin: 1
                            width: 24
                            height: 1.5
                            color: hudContainer.neonBlue
                            radius: 1
                        }
                    }
                }
            }

            // ================================================================
            // 2. GYROSCOPIC SATELLITE ORBIT RING (Counter-Clockwise rotation)
            // ================================================================
            Item {
                id: gyroRing
                anchors.centerIn: parent
                width: 110
                height: 110

                RotationAnimation on rotation {
                    from: 360
                    to: 0
                    duration: hudContainer.systemStatus === "thinking" ? 3500 : (hudContainer.systemStatus === "speaking" ? 5000 : 8500)
                    loops: Animation.Infinite
                }

                Rectangle {
                    anchors.fill: parent
                    radius: width / 2
                    color: "transparent"
                    border.color: Qt.rgba(hudContainer.activeNeon.r, hudContainer.activeNeon.g, hudContainer.activeNeon.b, 0.35)
                    border.width: 1.2
                    Behavior on border.color { ColorAnimation { duration: 250 } }
                }

                // 3 Orbiting Satellites with Glowing Halos
                Repeater {
                    model: 3
                    Item {
                        anchors.centerIn: parent
                        width: parent.width
                        height: parent.height
                        rotation: index * 120

                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.top: parent.top
                            anchors.topMargin: -2.5
                            width: 5
                            height: 5
                            radius: 2.5
                            color: "#ffffff"

                            Rectangle {
                                anchors.centerIn: parent
                                width: 9
                                height: 9
                                radius: 4.5
                                color: "transparent"
                                border.color: hudContainer.activeNeon
                                border.width: 1.2
                                Behavior on border.color { ColorAnimation { duration: 250 } }
                            }
                        }
                    }
                }
            }

            // ================================================================
            // 3. INNER FAST ROTATING ORBIT (Clockwise rotation)
            // ================================================================
            Item {
                id: innerFastRing
                anchors.centerIn: parent
                width: 78
                height: 78

                RotationAnimation on rotation {
                    from: 0
                    to: 360
                    duration: hudContainer.systemStatus === "thinking" ? 1500 : (hudContainer.systemStatus === "speaking" ? 2500 : 4500)
                    loops: Animation.Infinite
                }

                Rectangle {
                    anchors.fill: parent
                    radius: width / 2
                    color: "transparent"
                    border.color: hudContainer.systemStatus === "thinking" ? hudContainer.neonAmber : Qt.rgba(0.66, 0.33, 0.97, 0.45)
                    border.width: 1.0
                    Behavior on border.color { ColorAnimation { duration: 250 } }
                }

                // Inner Orbiting Dots
                Repeater {
                    model: 2
                    Item {
                        anchors.centerIn: parent
                        width: parent.width
                        height: parent.height
                        rotation: index * 180 + 35

                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.top: parent.top
                            anchors.topMargin: -2
                            width: 4
                            height: 4
                            radius: 2
                            color: hudContainer.activeNeon
                            Behavior on color { ColorAnimation { duration: 250 } }
                        }
                    }
                }
            }

            // ================================================================
            // 4. CENTRAL PULSING ARC REACTOR CORE (Audio Reactive)
            // ================================================================
            Item {
                id: arcCoreGroup
                anchors.centerIn: parent
                width: 48
                height: 48

                // Dynamic Scale: Audio Amplitude Visualizer while Speaking, otherwise Gentle Breathing
                scale: hudContainer.systemStatus === "speaking" 
                    ? (1.0 + Math.min(0.40, hudContainer.audioLevel * 0.45))
                    : 1.0

                Behavior on scale {
                    NumberAnimation { duration: 80; easing.type: Easing.OutQuad }
                }

                // Gentle breathing pulse when active/listening
                SequentialAnimation on opacity {
                    loops: Animation.Infinite
                    running: hudContainer.systemStatus !== "standby"
                    NumberAnimation { from: 0.82; to: 1.0; duration: 1200; easing.type: Easing.InOutSine }
                    NumberAnimation { from: 1.0; to: 0.82; duration: 1200; easing.type: Easing.InOutSine }
                }

                // Core Backdrop
                Rectangle {
                    anchors.fill: parent
                    radius: width / 2
                    color: Qt.rgba(hudContainer.activeNeon.r, hudContainer.activeNeon.g, hudContainer.activeNeon.b, 0.22)
                    border.color: hudContainer.activeNeon
                    border.width: 1.5
                    Behavior on color { ColorAnimation { duration: 250 } }
                    Behavior on border.color { ColorAnimation { duration: 250 } }
                }

                // Rotating Internal Arc Reactor Vanes
                Item {
                    anchors.centerIn: parent
                    width: 30
                    height: 30

                    RotationAnimation on rotation {
                        from: 360
                        to: 0
                        duration: hudContainer.systemStatus === "thinking" ? 1200 : (hudContainer.systemStatus === "speaking" ? 2000 : 3200)
                        loops: Animation.Infinite
                    }

                    Repeater {
                        model: 6
                        Item {
                            anchors.centerIn: parent
                            width: parent.width
                            height: parent.height
                            rotation: index * 60

                            Rectangle {
                                anchors.horizontalCenter: parent.horizontalCenter
                                anchors.top: parent.top
                                width: 2.5
                                height: 4.5
                                color: hudContainer.activeNeon
                                radius: 1
                                Behavior on color { ColorAnimation { duration: 250 } }
                            }
                        }
                    }
                }

                // Bright Central Core Spark
                Rectangle {
                    anchors.centerIn: parent
                    width: 10
                    height: 10
                    radius: 5
                    color: "#ffffff"

                    Rectangle {
                        anchors.centerIn: parent
                        width: 16
                        height: 16
                        radius: 8
                        color: "transparent"
                        border.color: hudContainer.activeNeon
                        border.width: 1
                        Behavior on border.color { ColorAnimation { duration: 250 } }
                    }
                }
            }

            // ================================================================
            // 5. TACTICAL HUD LABELS
            // ================================================================
            Text {
                id: labelTitle
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: arcCoreGroup.top
                anchors.bottomMargin: 1
                text: "J.A.R.V.I.S."
                font.pixelSize: 8
                font.bold: true
                font.letterSpacing: 1.5
                font.family: "monospace"
                color: hudContainer.activeNeon
                opacity: hudContainer.systemStatus === "standby" ? 0.6 : 0.95
                Behavior on color { ColorAnimation { duration: 250 } }
            }

            Text {
                id: labelStatus
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: arcCoreGroup.bottom
                anchors.topMargin: 2
                text: dragArea.drag.active 
                    ? ("X:" + Math.round(hudContainer.x) + " Y:" + Math.round(hudContainer.y))
                    : hudContainer.systemText.toUpperCase()
                font.pixelSize: 7
                font.bold: true
                font.letterSpacing: 1.0
                font.family: "monospace"
                color: dragArea.drag.active 
                    ? hudContainer.neonEmerald 
                    : hudContainer.activeNeon
                Behavior on color { ColorAnimation { duration: 250 } }
            }

            // ================================================================
            // 6. HARDWARE-ACCELERATED DRAGGABLE & CLICK CONTROLLER
            // ================================================================
            MouseArea {
                id: dragArea
                anchors.fill: parent
                hoverEnabled: true

                // Qt Quick native drag engine: zero jitter, sub-pixel accuracy, 120 FPS
                drag.target: hudContainer
                drag.axis: Drag.XAndYAxis
                drag.minimumX: 4
                drag.maximumX: root.width - hudContainer.width - 4
                drag.minimumY: 4
                drag.maximumY: root.height - hudContainer.height - 4

                cursorShape: drag.active ? Qt.ClosedHandCursor : (containsMouse ? Qt.OpenHandCursor : Qt.ArrowCursor)

                onEntered: hudContainer.isHovered = true
                onExited: hudContainer.isHovered = false

                // Single Click: Instantly toggle Active / Standby mode
                onClicked: {
                    try {
                        ipcSocket.write(JSON.stringify({ command: "toggle_standby" }) + "\n");
                    } catch (e) {
                        // Fallback HTTP toggle
                        var xhr = new XMLHttpRequest();
                        xhr.open("POST", "http://127.0.0.1:3000/api/standby/toggle");
                        xhr.send();
                    }
                }

                // Double-click: Instantly dock back to bottom center
                onDoubleClicked: {
                    hudContainer.x = Math.round((root.width - hudContainer.width) / 2)
                    hudContainer.y = root.height - hudContainer.height - 32
                }
            }
        }
    }
}
