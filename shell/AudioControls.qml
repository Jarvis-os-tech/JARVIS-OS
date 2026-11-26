pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell.Services.Pipewire
import "../widgets" as Widgets

ColumnLayout {
    id: controls
    readonly property var output: Pipewire.defaultAudioSink
    readonly property var input: Pipewire.defaultAudioSource

    function snapshot() {
        function state(node) {
            return node && node.audio
                ? {volume: Math.round(node.audio.volume * 100), muted: node.audio.muted}
                : null
        }
        return {output: state(output), microphone: state(input)}
    }

    PwObjectTracker {
        objects: [controls.output, controls.input].filter(node => node !== null && node !== undefined)
    }

    Repeater {
        model: ["Output", "Microphone"]
        ColumnLayout {
            id: endpoint
            required property string modelData
            readonly property var node: modelData === "Output" ? controls.output : controls.input
            readonly property var audio: node ? node.audio : null

            RowLayout {
                Layout.fillWidth: true

                Text {
                    Layout.fillWidth: true
                    text: endpoint.modelData
                    textFormat: Text.PlainText
                    color: "#EAF8FF"
                    font.weight: Font.DemiBold
                }

                Text {
                    text: endpoint.audio ? Math.round(endpoint.audio.volume * 100) + "%" : "Unavailable"
                    textFormat: Text.PlainText
                    color: "#A8BFCC"
                }

                Widgets.ActionButton {
                    text: endpoint.audio && endpoint.audio.muted ? "Unmute" : "Mute"
                    Accessible.name: text + " " + endpoint.modelData.toLowerCase()
                    enabled: !!endpoint.audio
                    onClicked: {
                        const audio = endpoint.audio
                        if (audio) audio.muted = !audio.muted
                    }
                }
            }

            Slider {
                Layout.fillWidth: true
                enabled: !!endpoint.audio
                from: 0
                to: 1
                stepSize: 0.01
                value: endpoint.audio ? Math.min(1, endpoint.audio.volume) : 0
                Accessible.name: endpoint.modelData + " level"
                onMoved: {
                    const audio = endpoint.audio
                    if (audio) audio.volume = value
                }
            }
        }
    }
}
