import QtQuick

// One spring drives the painted shell, content clip and input region together.
// Retargeting an in-flight transition preserves its velocity.
Item {
    id: motion
    property real targetWidth: 126
    property real targetHeight: 32
    property real targetRadius: 16
    property bool pressed: false
    property bool hovered: false
    property bool expanded: false
    property bool reducedMotion: false
    property real hoverGrowth: 4

    readonly property real lift: hovered && !expanded && !pressed ? hoverGrowth : 0
    property real w: Math.max(0, targetWidth * (pressed ? 0.975 : 1) + lift)
    property real h: Math.max(0, targetHeight * (pressed ? 0.95 : 1) + lift * 0.5)
    property real r: targetRadius

    Behavior on w {
        enabled: !motion.reducedMotion
        SpringAnimation { spring: 5.2; damping: 0.42; mass: 1; epsilon: 0.15 }
    }
    Behavior on h {
        enabled: !motion.reducedMotion
        SpringAnimation { spring: 5.8; damping: 0.46; mass: 1; epsilon: 0.15 }
    }
    Behavior on r {
        enabled: !motion.reducedMotion
        SpringAnimation { spring: 5.2; damping: 0.46; mass: 1; epsilon: 0.15 }
    }
}
