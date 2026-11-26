import QtQuick
import Quickshell
import Quickshell.Services.Pipewire
import qs.Commons
import "../IslandModel.js" as Model

// What the island opens into when nothing is live:
// Clean typography clock, date/agenda, compact system telemetry capsule,
// and a quick-toggles utility dock.
Item {
    id: view

    property var island: null
    readonly property int pad: island.s(22)
    readonly property var nextEvent: island.calendar ? island.calendar.next : null
    readonly property var clocks: island ? island.clocks : null
    readonly property bool stopwatchRunning: clocks ? clocks.stopwatchRunning : false
    readonly property bool micMuted: island ? island.micMuted : (Pipewire.defaultAudioSource && Pipewire.defaultAudioSource.audio ? Pipewire.defaultAudioSource.audio.muted : false)

    SystemClock {
        id: clock
        precision: SystemClock.Seconds
    }

    readonly property bool hasAmPm: island.clockFormat.indexOf("AP") !== -1 || island.clockFormat.indexOf("ap") !== -1
    readonly property string timeNum: hasAmPm ? Qt.formatDateTime(clock.date, "h:mm AP").replace(/\s*[AaPp][Mm]$/, "") : Qt.formatDateTime(clock.date, island.clockFormat)
    readonly property string ampmText: hasAmPm ? Qt.formatDateTime(clock.date, "AP") : ""

    // ------------------------------------------------------------------
    // Header Row: Time & Date (Left), Telemetry Capsule (Right)
    // ------------------------------------------------------------------
    Column {
        id: timeCol
        x: view.pad
        y: island.s(20)
        spacing: island.s(3)

        Row {
            id: clockRow
            spacing: island.s(6)

            Text {
                id: timeText
                text: view.timeNum
                textFormat: Text.PlainText
                renderType: Text.NativeRendering
                font.family: island.fontFamily
                font.pixelSize: island.f(30)
                font.weight: Font.DemiBold
                font.letterSpacing: -1
                font.features: {
                    "tnum": 1
                }
                color: island.fg
            }

            Text {
                id: ampmLabel
                visible: view.ampmText.length > 0
                text: view.ampmText
                textFormat: Text.PlainText
                renderType: Text.NativeRendering
                font.family: island.textFamily
                font.pixelSize: island.f(11)
                font.weight: Font.DemiBold
                color: island.fgDim
                anchors.baseline: timeText.baseline
            }
        }

        // Clickable date or upcoming calendar meeting
        Text {
            id: dateLine
            text: view.nextEvent ? ("󰃭  " + view.nextEvent.title + "  ·  " + Qt.formatDateTime(new Date(view.nextEvent.start), view.hasAmPm ? "h:mm AP" : "HH:mm")) : ("󰃭  " + Qt.formatDateTime(clock.date, "dddd, d MMMM") + (island.calendar && island.calendar.todayAllDay && island.calendar.todayAllDay.length > 0 ? "  ·  " + island.calendar.todayAllDay.join(", ") : ""))
            width: telemetryCapsule.visible ? Math.max(0, telemetryCapsule.x - view.pad - island.s(14)) : parent.width * 0.65
            elide: Text.ElideRight
            textFormat: Text.PlainText
            renderType: Text.NativeRendering
            font.family: island.textFamily
            font.pixelSize: island.f(12)
            color: view.nextEvent ? island.accentColor : island.fgDim

            MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    if (island && typeof island.openCalendar === "function") {
                        island.openCalendar();
                    }
                }
                onContainsMouseChanged: dateLine.font.underline = containsMouse
            }
        }
    }

    // Telemetry Capsule (RAM + Battery)
    Rectangle {
        id: telemetryCapsule
        anchors.right: parent.right
        anchors.rightMargin: view.pad
        anchors.verticalCenter: timeCol.verticalCenter
        height: island.s(30)
        width: telemRow.implicitWidth + island.s(22)
        radius: height / 2
        color: Util.alpha(island.fg, 0.07)
        border.width: 1
        border.color: Util.alpha(island.fg, 0.1)
        visible: (island.showRam && island.ramUsage > 0) || island.hasBattery

        Row {
            id: telemRow
            anchors.centerIn: parent
            spacing: island.s(9)

            // RAM item
            Row {
                visible: island.showRam && island.ramUsage > 0
                spacing: island.s(5)
                anchors.verticalCenter: parent.verticalCenter

                Text {
                    text: "󰍛"
                    textFormat: Text.PlainText
                    renderType: Text.NativeRendering
                    font.family: island.fontFamily
                    font.pixelSize: island.f(13)
                    color: island.ramUsage >= 0.85 ? island.urgentColor : (island.ramUsage >= 0.70 ? island.orangeColor : island.accentColor)
                    anchors.verticalCenter: parent.verticalCenter
                }

                Text {
                    text: Math.round(island.ramUsage * 100) + "%"
                    textFormat: Text.PlainText
                    renderType: Text.NativeRendering
                    font.family: island.fontFamily
                    font.pixelSize: island.f(11)
                    font.weight: Font.DemiBold
                    font.features: {
                        "tnum": 1
                    }
                    color: island.fg
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            // Divider
            Rectangle {
                visible: (island.showRam && island.ramUsage > 0) && island.hasBattery
                width: 1
                height: island.s(12)
                color: Util.alpha(island.fg, 0.14)
                anchors.verticalCenter: parent.verticalCenter
            }

            // Battery item
            Row {
                visible: island.hasBattery
                spacing: island.s(5)
                anchors.verticalCenter: parent.verticalCenter

                Text {
                    text: Model.batteryIcon(island.batteryLevel, island.charging)
                    textFormat: Text.PlainText
                    renderType: Text.NativeRendering
                    font.family: island.fontFamily
                    font.pixelSize: island.f(14)
                    color: island.charging ? island.greenColor : (island.batteryLevel <= 0.2 ? island.urgentColor : (island.batteryLevel <= 0.4 ? island.orangeColor : island.greenColor))
                    anchors.verticalCenter: parent.verticalCenter
                }

                Text {
                    text: Math.round(island.batteryLevel * 100) + "%"
                    textFormat: Text.PlainText
                    renderType: Text.NativeRendering
                    font.family: island.fontFamily
                    font.pixelSize: island.f(11)
                    font.weight: Font.DemiBold
                    font.features: {
                        "tnum": 1
                    }
                    color: island.fg
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
        }
    }

    // ------------------------------------------------------------------
    // Bottom Dock: 4 Clean Quick Action Utility Tiles
    // ------------------------------------------------------------------
    Item {
        id: dock
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: view.pad
        anchors.rightMargin: view.pad
        anchors.bottomMargin: island.s(18)
        height: island.s(52)

        readonly property real tileSpacing: island.s(8)
        readonly property real tileWidth: (width - tileSpacing * 3) / 4

        Row {
            anchors.fill: parent
            spacing: dock.tileSpacing

            // 1. Quick Controls
            Rectangle {
                id: controlsTile
                width: dock.tileWidth
                height: dock.height
                radius: island.s(12)
                color: controlsMouse.pressed ? Util.alpha(island.accentColor, 0.25) : (controlsMouse.containsMouse ? Util.alpha(island.fg, 0.12) : Util.alpha(island.fg, 0.055))
                border.width: 1
                border.color: controlsMouse.containsMouse ? Util.alpha(island.accentColor, 0.4) : Util.alpha(island.fg, 0.08)
                scale: controlsMouse.pressed ? 0.94 : (controlsMouse.containsMouse ? 1.03 : 1)

                Behavior on scale {
                    NumberAnimation {
                        duration: 120
                        easing.type: Easing.OutQuad
                    }
                }
                Behavior on color {
                    ColorAnimation {
                        duration: 120
                    }
                }
                Behavior on border.color {
                    ColorAnimation {
                        duration: 120
                    }
                }

                Column {
                    anchors.centerIn: parent
                    spacing: island.s(3)

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "󰘳"
                        textFormat: Text.PlainText
                        renderType: Text.NativeRendering
                        font.family: island.fontFamily
                        font.pixelSize: island.f(17)
                        color: controlsMouse.containsMouse ? island.accentColor : island.fg
                    }

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "Controls"
                        textFormat: Text.PlainText
                        renderType: Text.NativeRendering
                        font.family: island.textFamily
                        font.pixelSize: island.f(10.5)
                        font.weight: Font.DemiBold
                        color: controlsMouse.containsMouse ? island.accentColor : island.fgDim
                    }
                }

                MouseArea {
                    id: controlsMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (island && typeof island.switchExpandedView === "function") {
                            island.switchExpandedView("controls");
                        }
                    }
                }
            }

            // 2. Screen Capture
            Rectangle {
                id: captureTile
                width: dock.tileWidth
                height: dock.height
                radius: island.s(12)
                color: captureMouse.pressed ? Util.alpha(island.accentColor, 0.25) : (captureMouse.containsMouse ? Util.alpha(island.fg, 0.12) : Util.alpha(island.fg, 0.055))
                border.width: 1
                border.color: captureMouse.containsMouse ? Util.alpha(island.accentColor, 0.4) : Util.alpha(island.fg, 0.08)
                scale: captureMouse.pressed ? 0.94 : (captureMouse.containsMouse ? 1.03 : 1)

                Behavior on scale {
                    NumberAnimation {
                        duration: 120
                        easing.type: Easing.OutQuad
                    }
                }
                Behavior on color {
                    ColorAnimation {
                        duration: 120
                    }
                }
                Behavior on border.color {
                    ColorAnimation {
                        duration: 120
                    }
                }

                Column {
                    anchors.centerIn: parent
                    spacing: island.s(3)

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "󰄀"
                        textFormat: Text.PlainText
                        renderType: Text.NativeRendering
                        font.family: island.fontFamily
                        font.pixelSize: island.f(17)
                        color: captureMouse.containsMouse ? island.accentColor : island.fg
                    }

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "Capture"
                        textFormat: Text.PlainText
                        renderType: Text.NativeRendering
                        font.family: island.textFamily
                        font.pixelSize: island.f(10.5)
                        font.weight: Font.DemiBold
                        color: captureMouse.containsMouse ? island.accentColor : island.fgDim
                    }
                }

                MouseArea {
                    id: captureMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (island && typeof island.collapse === "function") {
                            island.collapse();
                        }
                        Quickshell.execDetached(["/usr/share/omarchy/bin/omarchy-capture-screenshot"]);
                    }
                }
            }

            // 3. Mute Microphone
            Rectangle {
                id: micTile
                width: dock.tileWidth
                height: dock.height
                radius: island.s(12)
                readonly property bool isMuted: view.micMuted
                color: isMuted ? Util.alpha(island.urgentColor, micMouse.pressed ? 0.35 : 0.22) : (micMouse.pressed ? Util.alpha(island.accentColor, 0.25) : (micMouse.containsMouse ? Util.alpha(island.fg, 0.12) : Util.alpha(island.fg, 0.055)))
                border.width: 1
                border.color: isMuted ? Util.alpha(island.urgentColor, 0.5) : (micMouse.containsMouse ? Util.alpha(island.accentColor, 0.4) : Util.alpha(island.fg, 0.08))
                scale: micMouse.pressed ? 0.94 : (micMouse.containsMouse ? 1.03 : 1)

                Behavior on scale {
                    NumberAnimation {
                        duration: 120
                        easing.type: Easing.OutQuad
                    }
                }
                Behavior on color {
                    ColorAnimation {
                        duration: 120
                    }
                }
                Behavior on border.color {
                    ColorAnimation {
                        duration: 120
                    }
                }

                Column {
                    anchors.centerIn: parent
                    spacing: island.s(3)

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: micTile.isMuted ? "󰍭" : "󰍬"
                        textFormat: Text.PlainText
                        renderType: Text.NativeRendering
                        font.family: island.fontFamily
                        font.pixelSize: island.f(17)
                        color: micTile.isMuted ? island.urgentColor : (micMouse.containsMouse ? island.accentColor : island.fg)
                    }

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: micTile.isMuted ? "Unmute" : "Mute Mic"
                        textFormat: Text.PlainText
                        renderType: Text.NativeRendering
                        font.family: island.textFamily
                        font.pixelSize: island.f(10.5)
                        font.weight: Font.DemiBold
                        color: micTile.isMuted ? island.urgentColor : (micMouse.containsMouse ? island.accentColor : island.fgDim)
                    }
                }

                MouseArea {
                    id: micMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (island && typeof island.toggleMicMute === "function") {
                            island.toggleMicMute();
                        } else {
                            var src = Pipewire.defaultAudioSource;
                            if (src && src.audio)
                                src.audio.muted = !src.audio.muted;
                        }
                    }
                }
            }

            // 4. Stopwatch
            Rectangle {
                id: stopwatchTile
                width: dock.tileWidth
                height: dock.height
                radius: island.s(12)
                readonly property bool isRunning: view.stopwatchRunning
                color: isRunning ? Util.alpha(island.accentColor, swMouse.pressed ? 0.35 : 0.22) : (swMouse.pressed ? Util.alpha(island.accentColor, 0.25) : (swMouse.containsMouse ? Util.alpha(island.fg, 0.12) : Util.alpha(island.fg, 0.055)))
                border.width: 1
                border.color: isRunning ? Util.alpha(island.accentColor, 0.5) : (swMouse.containsMouse ? Util.alpha(island.accentColor, 0.4) : Util.alpha(island.fg, 0.08))
                scale: swMouse.pressed ? 0.94 : (swMouse.containsMouse ? 1.03 : 1)

                Behavior on scale {
                    NumberAnimation {
                        duration: 120
                        easing.type: Easing.OutQuad
                    }
                }
                Behavior on color {
                    ColorAnimation {
                        duration: 120
                    }
                }
                Behavior on border.color {
                    ColorAnimation {
                        duration: 120
                    }
                }

                Column {
                    anchors.centerIn: parent
                    spacing: island.s(3)

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "󱎫"
                        textFormat: Text.PlainText
                        renderType: Text.NativeRendering
                        font.family: island.fontFamily
                        font.pixelSize: island.f(17)
                        color: stopwatchTile.isRunning ? island.accentColor : (swMouse.containsMouse ? island.accentColor : island.fg)
                    }

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: stopwatchTile.isRunning ? "Running" : "Stopwatch"
                        textFormat: Text.PlainText
                        renderType: Text.NativeRendering
                        font.family: island.textFamily
                        font.pixelSize: island.f(10.5)
                        font.weight: Font.DemiBold
                        color: stopwatchTile.isRunning ? island.accentColor : (swMouse.containsMouse ? island.accentColor : island.fgDim)
                    }
                }

                MouseArea {
                    id: swMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (view.clocks) {
                            view.clocks.toggleStopwatch();
                        }
                    }
                }
            }
        }
    }
}
