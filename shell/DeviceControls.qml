pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell.Io
import Quickshell.Bluetooth
import Quickshell.Networking

ColumnLayout {
    id: controls

    readonly property var wifi: Networking.devices.values.find(device => device.type === DeviceType.Wifi) || null
    readonly property var connectedWifi: wifi ? wifi.networks.values.find(network => network.connected) : null
    readonly property var bluetooth: Bluetooth.defaultAdapter
    property int brightness: -1
    property int pendingBrightness: -1
    property string error: ""

    function snapshot() {
        return {
            brightness: brightness < 0 ? null : brightness,
            wifi: wifi ? Networking.wifiEnabled : null,
            bluetooth: bluetooth ? bluetooth.enabled : null
        }
    }

    Process {
        id: readBrightness
        command: ["brightnessctl", "-m", "-c", "backlight", "info"]
        stdout: StdioCollector { id: brightnessOutput }
        onExited: code => {
            const levels = brightnessOutput.text.trim().split(",")
            const percent = levels.length === 5 && /^\d{1,3}%$/.test(levels[3]) ? parseInt(levels[3], 10) : -1
            controls.brightness = code === 0 && percent <= 100 ? percent : -1
        }
    }

    Process {
        id: setBrightness
        onExited: code => {
            controls.error = code === 0 ? "" : "Brightness could not be changed."
            controls.pendingBrightness = -1
            readBrightness.running = true
        }
    }

    Timer {
        id: writeDelay
        interval: 140
        onTriggered: {
            setBrightness.command = ["brightnessctl", "-c", "backlight", "set", controls.pendingBrightness + "%"]
            setBrightness.running = true
        }
    }

    Timer {
        running: controls.visible
        repeat: true
        triggeredOnStart: true
        interval: 3000
        onTriggered: {
            if (controls.pendingBrightness < 0 && !readBrightness.running && !setBrightness.running)
                readBrightness.running = true
        }
    }

    RowLayout {
        Layout.fillWidth: true
        ColumnLayout {
            Layout.fillWidth: true
            Text { text: "Wi-Fi"; color: "#EAF8FF" }
            Text {
                Layout.fillWidth: true
                text: controls.connectedWifi ? controls.connectedWifi.name : controls.wifi ? "" : "Unavailable"
                textFormat: Text.PlainText
                elide: Text.ElideRight
                color: "#A8BFCC"
                visible: text !== ""
            }
        }
        Switch {
            checked: !!controls.wifi && Networking.wifiEnabled
            enabled: !!controls.wifi
            Accessible.name: "Wi-Fi"
            onClicked: if (controls.wifi) Networking.wifiEnabled = checked
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Text { Layout.fillWidth: true; text: "Bluetooth"; color: "#EAF8FF" }
        Text { visible: !controls.bluetooth; text: "Unavailable"; color: "#A8BFCC" }
        Switch {
            checked: !!controls.bluetooth && controls.bluetooth.enabled
            enabled: !!controls.bluetooth
            Accessible.name: "Bluetooth"
            onClicked: {
                const adapter = controls.bluetooth
                if (adapter) adapter.enabled = checked
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Text { Layout.fillWidth: true; text: "Brightness"; color: "#EAF8FF" }
        Text {
            readonly property int level: controls.pendingBrightness >= 0 ? controls.pendingBrightness : controls.brightness
            text: level < 0 ? "Unavailable" : level + "%"
            textFormat: Text.PlainText
            color: "#A8BFCC"
        }
    }

    Slider {
        Layout.fillWidth: true
        enabled: controls.brightness >= 0 && !setBrightness.running
        from: 1
        to: 100
        stepSize: 1
        value: Math.max(1, controls.pendingBrightness >= 0 ? controls.pendingBrightness : controls.brightness)
        Accessible.name: "Screen brightness"
        onMoved: {
            controls.pendingBrightness = Math.round(value)
            writeDelay.restart()
        }
    }

    Text {
        Layout.fillWidth: true
        visible: text !== ""
        text: controls.error
        textFormat: Text.PlainText
        color: "#FFB300"
        wrapMode: Text.WordWrap
    }
}
