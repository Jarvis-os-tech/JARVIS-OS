pragma Singleton
import QtQuick

QtObject {
    id: root

    property bool reduceMotion: false
    readonly property var easeOut: [0.23, 1.0, 0.32, 1.0, 1.0, 1.0]

    function duration(ms) {
        var value = Number(ms);
        if (reduceMotion || !isFinite(value) || value <= 0)
            return 0;
        return Math.min(300, Math.round(value));
    }
}
