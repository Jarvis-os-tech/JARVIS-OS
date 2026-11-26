import QtQuick
import QtQuick.Controls

Button {
    id: button
    property bool primary: false
    implicitHeight: 44
    implicitWidth: Math.max(44, label.implicitWidth + 24)
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    Accessible.name: text
    contentItem: Text {
        id: label
        text: button.text
        textFormat: Text.PlainText
        elide: Text.ElideRight
        font.pixelSize: 13
        font.family: "Inter"
        color: !button.enabled ? "#8E9BAD" : button.primary ? "#A1FFF8" : "#C4E3DF"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: 6
        color: button.down ? "#125458" : button.hovered ? "#0B4548" : button.primary ? "#093438" : "#031C20"
        border.width: button.visualFocus ? 2 : 1
        border.color: button.visualFocus ? "#A1FFF8" : button.hovered || button.primary ? "#59BDB6" : "#305552"
        opacity: button.enabled ? 1 : 0.6
    }
}
