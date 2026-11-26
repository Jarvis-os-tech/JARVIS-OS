pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell.Services.Mpris
import "../widgets" as Widgets

ColumnLayout {
    id: controls
    readonly property var players: Mpris.players.values
    readonly property var player: players.find(item => item.isPlaying) || players[0] || null
    readonly property real duration: player && player.lengthSupported ? player.length : 0
    readonly property bool seekable: !!player && player.canSeek && player.positionSupported && duration > 0

    function snapshot() {
        return {available: !!player, playing: !!player && player.isPlaying, seekable: seekable}
    }

    Timer {
        interval: 1000
        running: controls.visible && controls.seekable && controls.player.isPlaying
        repeat: true
        onTriggered: controls.player.positionChanged()
    }

    Text {
        Layout.fillWidth: true
        text: controls.player ? controls.player.trackTitle || controls.player.identity : "No media player"
        textFormat: Text.PlainText
        elide: Text.ElideRight
        color: "#EAF8FF"
        font.weight: Font.DemiBold
    }

    Text {
        Layout.fillWidth: true
        visible: text !== ""
        text: controls.player ? controls.player.trackArtist : ""
        textFormat: Text.PlainText
        elide: Text.ElideRight
        color: "#A8BFCC"
    }

    Slider {
        Layout.fillWidth: true
        visible: controls.duration > 0
        enabled: controls.seekable
        from: 0
        to: controls.duration || 1
        value: controls.player && controls.player.positionSupported ? controls.player.position : 0
        Accessible.name: "Playback position"
        onMoved: {
            const player = controls.player
            if (controls.seekable && player) player.position = value
        }
    }

    RowLayout {
        Layout.fillWidth: true
        visible: !!controls.player

        Widgets.ActionButton {
            Layout.fillWidth: true
            text: "Previous"
            enabled: !!controls.player && controls.player.canGoPrevious
            onClicked: {
                const player = controls.player
                if (player && player.canGoPrevious) player.previous()
            }
        }

        Widgets.ActionButton {
            Layout.fillWidth: true
            text: controls.player && controls.player.isPlaying ? "Pause" : "Play"
            primary: true
            enabled: !!controls.player && (controls.player.isPlaying ? controls.player.canPause : controls.player.canPlay)
            onClicked: {
                const player = controls.player
                if (player && player.isPlaying && player.canPause) player.pause()
                else if (player && !player.isPlaying && player.canPlay) player.play()
            }
        }

        Widgets.ActionButton {
            Layout.fillWidth: true
            text: "Next"
            enabled: !!controls.player && controls.player.canGoNext
            onClicked: {
                const player = controls.player
                if (player && player.canGoNext) player.next()
            }
        }
    }
}
