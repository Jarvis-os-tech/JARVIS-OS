import QtQuick

// The little equalizer on the trailing edge of the media activity. Bars drift
// to new random heights while something plays and settle flat when paused.
Row {
  id: viz

  property bool playing: false
  property color color: "white"
  property int bars: 5
  property real barWidth: 3
  property real maxHeight: 14
  property bool reducedMotion: false

  spacing: Math.max(1, Math.round(barWidth * 0.75))
  height: maxHeight

  Repeater {
    id: repeater
    model: viz.bars

    Rectangle {
      property real level: 0.4

      anchors.verticalCenter: parent.verticalCenter
      width: viz.barWidth
      radius: width / 2
      height: Math.max(viz.barWidth, viz.maxHeight * (viz.playing && !viz.reducedMotion ? level : 0.2))
      gradient: Gradient {
        GradientStop { position: 0; color: Qt.lighter(viz.color, 1.35) }
        GradientStop { position: 1; color: viz.color }
      }

      Behavior on height { NumberAnimation { duration: 160; easing.type: Easing.InOutSine } }
    }
  }

  Timer {
    interval: 160
    repeat: true
    running: viz.playing && viz.visible && !viz.reducedMotion
    onTriggered: {
      for (var i = 0; i < repeater.count; i++) {
        var bar = repeater.itemAt(i)
        if (bar) bar.level = 0.25 + Math.random() * 0.75
      }
    }
  }
}
