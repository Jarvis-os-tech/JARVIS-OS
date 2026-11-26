pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell.Io
import Quickshell.Networking
import "../omarchy-jarvis-island/ReactiveModel.js" as Reactive

Item {
    id: telemetry
    implicitHeight: 134
    property real cpu: -1
    property real memory: -1
    property var previousCpu: null
    property string apiState: "Unavailable"
    property real temperature: NaN
    readonly property bool networkConnected: Networking.devices.values.some(device =>
        device.type === DeviceType.Wifi && device.networks.values.some(network => network.connected))


    FileView {
        id: cpuFile
        path: "/proc/stat"
        printErrors: false
        onLoaded: {
            const counters = Reactive.cpuSample(text())
            telemetry.cpu = Reactive.cpuUsage(telemetry.previousCpu, counters)
            telemetry.previousCpu = counters
        }
        onLoadFailed: {
            telemetry.cpu = -1
            telemetry.previousCpu = null
        }
    }

    FileView {
        id: memoryFile
        path: "/proc/meminfo"
        printErrors: false
        onLoaded: telemetry.memory = Reactive.memoryUsage(text())
        onLoadFailed: telemetry.memory = -1
    }

    FileView {
        id: thermalFile
        // shortcut: read the first thermal zone, use the hardware monitor for named sensors.
        path: "/sys/class/thermal/thermal_zone0/temp"
        printErrors: false
        onLoaded: {
            const reading = text().trim()
            telemetry.temperature = /^-?\d+$/.test(reading) ? Number(reading) / 1000 : NaN
        }
        onLoadFailed: telemetry.temperature = NaN
    }

    Timer {
        interval: 2000
        running: telemetry.visible
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            cpuFile.reload()
            memoryFile.reload()
            thermalFile.reload()
        }
    }

    RowLayout {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: details.top
        anchors.margins: 10
        spacing: 16

        Repeater {
            model: ["CPU", "Memory"]

            ColumnLayout {
                id: gauge
                required property string modelData
                readonly property real value: modelData === "CPU" ? telemetry.cpu : telemetry.memory
                readonly property string reading: value < 0 ? "Unavailable" : Math.round(value * 100) + "%"
                Layout.fillWidth: true
                spacing: 4
                Accessible.role: Accessible.StaticText
                Accessible.name: modelData + " " + reading

                Item {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: Math.min(84, Math.max(50, gauge.width))
                    Layout.preferredHeight: width

                    Canvas {
                        id: ring
                        anchors.fill: parent
                        onWidthChanged: requestPaint()
                        onHeightChanged: requestPaint()
                        onPaint: {
                            const ctx = getContext("2d")
                            const centerX = width / 2
                            const centerY = height / 2
                            const radius = Math.min(centerX, centerY) - 5
                            if (radius <= 0) return
                            const start = Math.PI * 0.75
                            const sweep = Math.PI * 1.5
                            ctx.reset()
                            ctx.lineWidth = 3
                            ctx.lineCap = "round"
                            ctx.strokeStyle = "#244957"
                            ctx.beginPath()
                            ctx.arc(centerX, centerY, radius, start, start + sweep)
                            ctx.stroke()
                            if (gauge.value <= 0) return
                            ctx.strokeStyle = gauge.value >= 0.90 ? "#ffb300" : "#65eaff"
                            ctx.beginPath()
                            ctx.arc(centerX, centerY, radius, start, start + sweep * gauge.value)
                            ctx.stroke()
                        }

                        Connections {
                            target: gauge
                            function onValueChanged() { ring.requestPaint() }
                        }
                    }

                    Text {
                        anchors.centerIn: parent
                        text: gauge.value < 0 ? "—" : gauge.reading
                        textFormat: Text.PlainText
                        color: "#eaf8ff"
                        font.pixelSize: 19
                        font.weight: Font.DemiBold
                    }
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: gauge.modelData
                    textFormat: Text.PlainText
                    color: "#a8bfcc"
                    font.pixelSize: 13
                }
            }
        }
    }

    Text {
        id: details
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 12
        wrapMode: Text.WordWrap
        textFormat: Text.PlainText
        color: "#ACBED0"
        text: "Thermal " + (Number.isFinite(telemetry.temperature) ? telemetry.temperature.toFixed(0) + " °C" : "unavailable")
            + "   •   Wi-Fi " + (telemetry.networkConnected ? "connected" : "not connected")
            + "   •   Gemini " + telemetry.apiState
    }

}
