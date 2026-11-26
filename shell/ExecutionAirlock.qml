pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland

PanelWindow {
    id: airlock
    required property var request
    readonly property string requestId: request.id || ""
    property bool busy: false
    property string feedback: ""
    signal decided(string requestId, bool approve)

    implicitWidth: Math.min(480, screen ? screen.width : 480)
    implicitHeight: Math.min(310, screen ? screen.height : 310)
    exclusionMode: ExclusionMode.Ignore
    color: "transparent"
    WlrLayershell.namespace: "jarvis-execution-airlock"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

    onBackingWindowVisibleChanged: if (backingWindowVisible) cancelButton.forceActiveFocus()
    onRequestIdChanged: if (backingWindowVisible) cancelButton.forceActiveFocus()

    Rectangle {
        anchors.fill: parent
        color: "#10141E"
        border.color: "#FFB300"
        radius: 14

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 10
            Keys.onEscapePressed: if (!airlock.busy) airlock.decided(airlock.request.id, false)

            Label {
                text: qsTr("Action approval")
                color: "#FFB300"
                font.pixelSize: 21
                Accessible.role: Accessible.Heading
            }
            Label {
                Layout.fillWidth: true
                text: qsTr("JARVIS paused this action until you approve it.")
                color: "#DBE6F3"
                wrapMode: Text.WordWrap
            }
            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                TextArea {
                    text: airlock.request.description
                    readOnly: true
                    selectByMouse: true
                    textFormat: TextEdit.PlainText
                    wrapMode: TextEdit.Wrap
                    Accessible.name: qsTr("Action details")
                }
            }
            Label {
                Layout.fillWidth: true
                visible: text.length > 0
                text: airlock.feedback
                textFormat: Text.PlainText
                color: "#FFCE69"
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                Button {
                    id: cancelButton
                    text: qsTr("Cancel")
                    enabled: !airlock.busy
                    onClicked: airlock.decided(airlock.request.id, false)
                }
                Button {
                    id: confirmButton
                    property string pressedId: ""
                    text: qsTr("Approve")
                    enabled: !airlock.busy
                    onPressed: pressedId = airlock.requestId
                    onClicked: if (pressedId === airlock.requestId) airlock.decided(pressedId, true)
                }
            }
        }
    }
}
