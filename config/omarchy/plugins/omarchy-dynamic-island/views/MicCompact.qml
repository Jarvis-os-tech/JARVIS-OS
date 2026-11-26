import QtQuick

// Something is listening to a microphone: glyph on the leading edge, the
// privacy dot on the trailing edge, both in the theme's warning color.
Item {
    id: view

    property var island: null

    Text {
        anchors.left: parent.left
        anchors.leftMargin: island ? island.s(13) : 13
        anchors.verticalCenter: parent.verticalCenter
        text: island && island.cameraActive ? "󰄀" : "󰍬"
        textFormat: Text.PlainText
        renderType: Text.NativeRendering
        font.family: island ? island.fontFamily : "sans-serif"
        font.pixelSize: island ? island.f(15) : 15
        color: island && island.cameraActive ? island.greenColor : (island ? island.orangeColor : "#f97316")
    }

    RecordDot {
        anchors.right: parent.right
        anchors.rightMargin: island ? island.s(14) : 14
        anchors.verticalCenter: parent.verticalCenter
        size: island ? island.s(8) : 8
        color: island && island.cameraActive ? island.greenColor : (island ? island.orangeColor : "#f97316")
        pulsing: false
    }
}
