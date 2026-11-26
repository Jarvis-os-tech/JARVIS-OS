import QtQuick
import "style"

Item {
    id: core
    property real energy: 0.3
    property string voiceState: "idle"
    property bool muted: false

    readonly property bool active: !muted && ["idle", "listening", "thinking", "speaking", "working", "complete", "alert"].includes(voiceState)
    readonly property bool animating: !muted && !Style.reduceMotion && ["listening", "thinking", "speaking", "working", "complete", "alert"].includes(voiceState)
    readonly property color accent: voiceState === "alert" ? "#FF5577"
        : voiceState === "complete" ? "#34D399" : muted ? "#FFB300"
        : ["offline", "connecting", "standby", "microphone_silent"].includes(voiceState) ? "#B6C9DB"
        : ["thinking", "speaking", "working"].includes(voiceState) ? "#FFCE69" : "#00E5FF"
    readonly property string statusText: core.voiceState === "complete" ? "COMPLETE"
        : core.voiceState === "alert" ? "ALERT"
        : core.voiceState === "microphone_muted" ? "MIC MUTED"
        : core.muted ? "MUTED"
        : core.voiceState === "offline" ? "OFFLINE"
        : core.voiceState === "connecting" ? "CONNECTING"
        : core.voiceState === "microphone_silent" ? "MIC LEVEL ZERO"
        : core.voiceState === "speaking" ? "SPEAKING"
        : core.voiceState === "thinking" ? "THINKING"
        : core.voiceState === "listening" ? "LISTENING"
        : core.voiceState === "working" ? "EXECUTING"
        : core.voiceState === "standby" ? "STANDBY"
        : "ONLINE"

    implicitWidth: 320
    implicitHeight: 320

    property real reactionX: 0
    property real reactionY: 0
    transform: Translate { x: core.reactionX; y: core.reactionY }
    onVoiceStateChanged: {
        if (Style.reduceMotion) return;
        if (voiceState === "listening") nod.restart();
        else if (voiceState === "complete") roll.restart();
        else if (voiceState === "alert") recoil.restart();
    }
    SequentialAnimation {
        id: nod
        NumberAnimation { target: core; property: "reactionY"; to: 6; duration: Style.duration(110); easing.type: Easing.OutCubic }
        NumberAnimation { target: core; property: "reactionY"; to: 0; duration: Style.duration(180); easing.type: Easing.OutCubic }
    }
    NumberAnimation { id: roll; target: contours; property: "rotation"; from: 0; to: 360; duration: Style.duration(280); easing.type: Easing.OutCubic }
    SequentialAnimation {
        id: recoil
        NumberAnimation { target: core; property: "reactionX"; to: -6; duration: Style.duration(70); easing.type: Easing.OutCubic }
        NumberAnimation { target: core; property: "reactionX"; to: 5; duration: Style.duration(90); easing.type: Easing.OutCubic }
        NumberAnimation { target: core; property: "reactionX"; to: 0; duration: Style.duration(110); easing.type: Easing.OutCubic }
    }

    Canvas {
        id: contours
        anchors.fill: parent
        property real phase: 0

        Timer {
            interval: 33
            repeat: true
            running: core.visible && core.animating
            onTriggered: {
                contours.phase = (contours.phase + (core.voiceState === "speaking" ? 0.036 : 0.018)) % (Math.PI * 2)
                contours.requestPaint()
            }
        }

        Connections {
            target: core
            function onActiveChanged() { contours.requestPaint() }
            function onAnimatingChanged() { if (!core.animating) { contours.phase = 0; contours.requestPaint() } }
            function onAccentChanged() { contours.requestPaint() }
            function onEnergyChanged() { contours.requestPaint() }
            function onVoiceStateChanged() { contours.requestPaint() }
            function onMutedChanged() { contours.requestPaint() }
        }

        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()

        onPaint: {
            const ctx = getContext("2d");
            ctx.reset();
            const radius = Math.min(width, height) / 2;
            if (radius <= 0) return;
            ctx.translate(width / 2, height * 0.42);
            ctx.scale(0.86, 0.86);
            const phase = core.active ? contours.phase : 0;
            const energy = core.active ? Math.max(0, Math.min(1, core.energy)) : 0;

            const warm = core.muted || ["thinking", "speaking", "working"].includes(core.voiceState);
            const light = warm ? "#FFD38B" : "#62F7FF";
            const glow = ctx.createRadialGradient(0, 0, 0, 0, 0, radius);
            glow.addColorStop(0, warm ? "#40291A" : "#0C3948");
            glow.addColorStop(0.65, "#0A1D32");
            glow.addColorStop(1, "transparent");
            ctx.fillStyle = glow;
            ctx.fillRect(-radius, -radius, radius * 2, radius * 2);

            const tau = 2 * Math.PI;
            function arc(r, start, end, color, weight) {
                ctx.beginPath();
                ctx.strokeStyle = color;
                ctx.lineWidth = weight;
                ctx.arc(0, 0, radius * r, start, end);
                ctx.stroke();
            }
            for (const ring of [0.19, 0.31, 0.54, 0.68, 0.79, 0.96])
                arc(ring, 0, tau, "#286076", 1);
            const ticks = core.width < 180 ? 48 : 120;
            for (let i = 0; i < ticks; i++) {
                const angle = i * tau / ticks;
                const major = i % 6 === 0;
                const inner = major ? 0.84 : 0.88;
                ctx.beginPath();
                ctx.moveTo(radius * inner * Math.cos(angle), radius * inner * Math.sin(angle));
                ctx.lineTo(radius * 0.91 * Math.cos(angle), radius * 0.91 * Math.sin(angle));
                ctx.strokeStyle = major ? "#588B9D" : "#214253";
                ctx.lineWidth = 1;
                ctx.stroke();
            }
            for (let segment = 0; segment < 3; segment++) {
                const start = segment * tau / 3 + phase * 0.08;
                arc(0.76, start, start + 0.96, "#174956", 7);
                arc(0.76, start, start + 0.96, light, 2);
            }
            for (let band = 0; band < 3; band++) {
                ctx.beginPath();
                for (let i = 0; i <= 192; i++) {
                    const a = i * tau / 192;
                    const ripple = Math.sin(9*a + phase + band*0.65) * Math.cos(4*a - phase);
                    const r = radius * (0.57 + band*0.026 + ripple*(0.055 + energy*0.065));
                    if (i === 0) ctx.moveTo(r*Math.cos(a), r*Math.sin(a));
                    else ctx.lineTo(r*Math.cos(a), r*Math.sin(a));
                }
                ctx.strokeStyle = band === 0 ? light : band === 1 ? "#308DAA" : "#4869C1";
                ctx.lineWidth = band === 0 ? 2 : 1;
                ctx.stroke();
            }
            for (let i = 0; i < 72; i++) {
                const a = i*tau/72;
                const r = radius*(0.22 + (0.11 + energy * 0.12)*Math.pow(Math.sin(13*a+phase), 4));
                ctx.beginPath();
                ctx.moveTo(radius*0.15*Math.cos(a), radius*0.15*Math.sin(a));
                ctx.lineTo(r*Math.cos(a), r*Math.sin(a));
                ctx.strokeStyle = i % 3 ? "#287688" : light;
                ctx.lineWidth = 1;
                ctx.stroke();
            }
            arc(0.13 + energy * 0.025, 0, tau, light, 2 + energy * 2);
        }
    }

    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height * 0.86 - height / 2
        text: "JARVIS"
        textFormat: Text.PlainText
        color: "#F5F9FF"
        font.family: "Inter"
        font.pixelSize: Math.max(11, Math.min(28, core.width * 0.054))
        font.weight: Font.Medium
        font.letterSpacing: core.width < 180 ? 2 : 4
    }

    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height * 0.96 - height / 2
        width: label.implicitWidth + 24
        height: core.width < 180 ? 17 : 23
        radius: height / 2
        color: "#0B1628"
        border.color: "#304E6C"

        Text {
            id: label
            anchors.centerIn: parent
            text: core.statusText
            textFormat: Text.PlainText
            color: core.accent
            font.family: "Inter"
            font.pixelSize: 11
            font.weight: Font.Medium
            font.letterSpacing: 1.2
        }
    }
}
