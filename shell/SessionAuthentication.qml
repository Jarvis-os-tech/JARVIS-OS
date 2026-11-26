pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Services.Polkit
import Quickshell.Wayland

Item {
    id: auth
    readonly property bool prompting: agent.isActive

    PolkitAgent {
        id: agent
        path: "/org/jarvis/PolkitAgent"
    }

    LazyLoader {
        active: auth.prompting
        PanelWindow {
            id: prompt
            readonly property var flow: agent.flow
            implicitWidth: Math.min(460, screen ? screen.width : 460)
            implicitHeight: Math.min(250, screen ? screen.height : 250)
            exclusionMode: ExclusionMode.Ignore
            color: "transparent"
            WlrLayershell.namespace: "jarvis-authentication"
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

            onBackingWindowVisibleChanged: if (backingWindowVisible) response.forceActiveFocus()
            onFlowChanged: response.clear()

            Rectangle {
                anchors.fill: parent
                radius: 14
                color: "#10141E"
                border.color: "#FFB300"

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    Keys.onEscapePressed: prompt.flow?.cancelAuthenticationRequest()

                    Label {
                        text: qsTr("System authentication")
                        color: "#FFB300"
                        font.pixelSize: 21
                        Accessible.role: Accessible.Heading
                    }
                    Label {
                        Layout.fillWidth: true
                        text: prompt.flow?.message || ""
                        textFormat: Text.PlainText
                        wrapMode: Text.WordWrap
                        maximumLineCount: 4
                        elide: Text.ElideRight
                    }
                    Label {
                        Layout.fillWidth: true
                        text: prompt.flow?.supplementaryMessage || ""
                        textFormat: Text.PlainText
                        wrapMode: Text.WordWrap
                        visible: text.length > 0
                    }
                    TextField {
                        id: response
                        Layout.fillWidth: true
                        enabled: !!prompt.flow?.isResponseRequired
                        placeholderText: prompt.flow?.inputPrompt || qsTr("Waiting for the system")
                        echoMode: prompt.flow?.responseVisible ? TextInput.Normal : TextInput.Password
                        Accessible.name: placeholderText
                        onEnabledChanged: {
                            clear()
                            if (enabled && prompt.backingWindowVisible) forceActiveFocus()
                        }
                        onAccepted: {
                            const flow = prompt.flow
                            if (!flow?.isResponseRequired) return
                            const value = text
                            clear()
                            flow.submit(value)
                        }
                    }
                    Button {
                        Layout.alignment: Qt.AlignRight
                        text: qsTr("Cancel")
                        onClicked: prompt.flow?.cancelAuthenticationRequest()
                    }
                }
            }
        }
    }
}
