pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "style"
import "../widgets" as Widgets

FocusScope {
    id: card

    property alias widget: renderer.widget
    property alias savedState: renderer.savedState
    property alias requestFeedback: renderer.requestFeedback
    property alias requestBusy: renderer.requestBusy
    property alias requestError: renderer.requestError
    property alias activeMedia: renderer.activeMedia
    property bool reducedMotion: Style.reduceMotion
    property string apiState: "Unavailable"
    readonly property bool interacting: pointer.hovered || activeFocus
    readonly property bool audioCard: widget.kind === "audio_controls"
    readonly property AudioControls audio: nativeLoader.item as AudioControls
    readonly property bool mediaCard: widget.kind === "media_controls"
    readonly property MediaControls media: nativeLoader.item as MediaControls
    readonly property bool deviceCard: widget.kind === "device_controls"
    readonly property DeviceControls devices: nativeLoader.item as DeviceControls
    readonly property bool nativeCard: audioCard || mediaCard || telemetryCard || deviceCard
    readonly property bool telemetryCard: widget.kind === "system_telemetry"
    readonly property SystemTelemetry telemetry: nativeLoader.item as SystemTelemetry
    readonly property bool pinned: widget.pinned === true
    readonly property color sectionAccent: widget.section === "brief" ? "#E7C67E" : widget.section === "ideas" ? "#CB9AF4" : "#82FFF3"
    readonly property color sectionFill: widget.section === "brief" ? "#F0252219" : widget.section === "ideas" ? "#F020162B" : "#F0052023"
    readonly property color edgeColor: interacting || pinned ? sectionAccent : Qt.darker(sectionAccent, 1.7)
    readonly property int revealTime: Style.duration(reducedMotion ? 0 : 220)
    property real revealProgress: 0

    function selectChoice(index) { return renderer.selectChoice(index) }
    Keys.onPressed: event => {
        if ((event.modifiers & Qt.AltModifier) && [Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down].includes(event.key)) {
            const dx = event.key === Qt.Key_Left ? -12 : event.key === Qt.Key_Right ? 12 : 0
            const dy = event.key === Qt.Key_Up ? -12 : event.key === Qt.Key_Down ? 12 : 0
            if (event.modifiers & Qt.ShiftModifier) card.resized(dx, dy)
            else card.moved(dx, dy)
            event.accepted = true
            return
        }
        if (renderer.visible && renderer.generatedView)
            renderer.generatedView.handleKeyEvent(event)
    }

    signal moved(real dx, real dy)
    signal resized(real dx, real dy)
    signal pinRequested()
    signal dismissRequested()
    signal stateEdited(var values)
    signal submitted(string prompt, var values)

    implicitWidth: renderer.implicitWidth
    implicitHeight: deviceCard ? 230 : audioCard ? 210 : mediaCard ? 184 : telemetryCard ? 224 : renderer.implicitHeight + 38

    HoverHandler { id: pointer }

    Accessible.role: Accessible.Pane
    Accessible.name: card.widget.title || "JARVIS widget"

    Canvas {
        id: surface
        anchors.fill: parent
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        Connections { target: card; function onEdgeColorChanged() { surface.requestPaint() } }
        onPaint: {
            const c = getContext("2d"); c.reset();
            const cut = 16, w = width - 1, h = height - 1;
            c.beginPath(); c.moveTo(cut, 1); c.lineTo(w-cut, 1);
            c.lineTo(w, cut); c.lineTo(w, h-cut); c.lineTo(w-cut, h);
            c.lineTo(cut, h); c.lineTo(1, h-cut); c.lineTo(1, cut); c.closePath();
            const fill = c.createLinearGradient(0, 0, w, h);
            fill.addColorStop(0, card.sectionFill); fill.addColorStop(1, "#F5020C10");
            c.fillStyle = fill; c.fill(); c.strokeStyle = card.edgeColor; c.lineWidth = 1; c.stroke();
            const edge = c.createLinearGradient(cut, 0, w-cut, 0);
            edge.addColorStop(0, "transparent"); edge.addColorStop(0.5, card.sectionAccent); edge.addColorStop(1, "transparent");
            c.fillStyle = edge; c.fillRect(cut, 1, w-2*cut, 2);
        }
    }
    // Keep controls available to keyboard users without a permanent title bar.
    Row {
        id: controls
        z: 2
        anchors.right: parent.right; anchors.rightMargin: 14
        anchors.bottom: parent.bottom; anchors.bottomMargin: 8
        spacing: 6
        opacity: card.interacting ? 1 : 0.35
        Widgets.ActionButton {
            objectName: "hologram-pin"
            implicitHeight: 28
            text: card.pinned ? qsTr("Unpin") : qsTr("Pin")
            Accessible.name: text + " " + card.widget.title
            onClicked: card.pinRequested()
        }
        Widgets.ActionButton {
            objectName: "hologram-dismiss"
            implicitHeight: 28
            text: "×"
            Accessible.name: "Dismiss " + card.widget.title
            onClicked: card.dismissRequested()
        }
    }

    MouseArea {
        id: dragGrip
        anchors.left: parent.left; anchors.leftMargin: 18
        anchors.bottom: parent.bottom; anchors.bottomMargin: 8
        width: 64; height: 28
        cursorShape: Qt.SizeAllCursor
        property point previous
        onPressed: mouse => { previous = mapToGlobal(mouse.x, mouse.y) }
        onPositionChanged: mouse => {
            if (!pressed) return
            const current = mapToGlobal(mouse.x, mouse.y)
            card.moved(current.x - previous.x, current.y - previous.y)
            previous = current
        }
        Text { anchors.centerIn: parent; text: "⠿"; color: card.sectionAccent; opacity: card.interacting ? 0.8 : 0.3 }
    }
    MouseArea {
        anchors.right: parent.right; anchors.bottom: parent.bottom
        width: 12; height: 12
        cursorShape: Qt.SizeFDiagCursor
        property point previous
        onPressed: mouse => { previous = mapToGlobal(mouse.x, mouse.y) }
        onPositionChanged: mouse => {
            if (!pressed) return
            const current = mapToGlobal(mouse.x, mouse.y)
            card.resized(current.x - previous.x, current.y - previous.y)
            previous = current
        }
    }

    Loader {
        id: nativeLoader
        active: card.nativeCard
        anchors.top: parent.top
        anchors.topMargin: 16
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 42
        anchors.left: parent.left
        anchors.leftMargin: card.telemetryCard ? 0 : 18
        anchors.right: parent.right
        anchors.rightMargin: card.telemetryCard ? 0 : 16
        sourceComponent: card.audioCard ? audioSurface : card.mediaCard ? mediaSurface : card.deviceCard ? deviceSurface : telemetrySurface
    }

    Component { id: deviceSurface; DeviceControls {} }
    Component { id: audioSurface; AudioControls {} }
    Component { id: mediaSurface; MediaControls {} }
    Component { id: telemetrySurface; SystemTelemetry { apiState: card.apiState } }

    Widgets.WidgetCard {
        id: renderer
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 38
        anchors.topMargin: 8
        anchors.left: parent.left
        anchors.right: parent.right
        visible: !card.nativeCard
        framed: false
        plainText: true
        opacity: (card.reducedMotion || Style.reduceMotion || card.revealTime === 0) ? 1 : card.revealProgress
        onStateEdited: values => card.stateEdited(values)
        onSubmitted: (prompt, values) => card.submitted(prompt, values)
        onDismissRequested: card.dismissRequested()
    }

    NumberAnimation on revealProgress {
        running: !card.reducedMotion && !Style.reduceMotion && card.revealTime > 0
        from: 0
        to: 1
        duration: card.revealTime
        easing.type: Easing.OutCubic
    }
}
