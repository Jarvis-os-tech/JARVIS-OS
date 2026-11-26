import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland

PanelWindow {
    id: bar
    signal appsRequested()
    signal notificationsRequested()
    anchors { top: true; left: true; right: true }
    implicitHeight: 40
    color: "#101D27"
    WlrLayershell.namespace: "jarvis-session-bar"
    WlrLayershell.layer: WlrLayer.Top

    SystemClock { id: clock; precision: SystemClock.Minutes }

    component BarButton: ToolButton {
        id: control
        hoverEnabled: true
        contentItem: Text {
            text: control.text
            textFormat: Text.PlainText
            color: control.hovered || control.visualFocus ? "#84F1F3" : "#C4D6DE"
            font.pixelSize: 13
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            radius: 5
            color: control.hovered || control.visualFocus ? "#213540" : "transparent"
        }
    }
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 18
        anchors.rightMargin: 18
        spacing: 12
        Rectangle { width: 9; height: 9; radius: 5; color: "#62F7FF" }
        Text { text: "JARVIS OS"; font.letterSpacing: 1.8; font.pixelSize: 12; font.bold: true; color: "#DEF1F3" }
        Rectangle { width: 1; height: 14; color: "#38505C" }
        BarButton { text: qsTr("Applications"); onClicked: bar.appsRequested() }
        Item { Layout.fillWidth: true }
        BarButton { text: qsTr("Notifications"); onClicked: bar.notificationsRequested() }
        Text { text: Qt.formatTime(clock.date, "HH:mm"); textFormat: Text.PlainText; font.pixelSize: 13; color: "#D6E8EF" }
    }
}
