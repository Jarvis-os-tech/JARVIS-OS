pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import Quickshell.Services.Notifications
import "../widgets" as Widgets

Scope {
    id: center

    property bool active: false
    property bool historyOpen: false
    property var recent: []
    property var banner: null
    readonly property int count: recent.length

    function receive(notification) {
        if (!recent.includes(notification)) {
            notification.tracked = true
            notification.closed.connect(() => {
                center.recent = center.recent.filter(item => item !== notification)
                if (center.banner === notification) center.banner = null
            })
        }
        recent = [notification].concat(recent.filter(item => item !== notification))
        if (recent.length > 16) {
            const evicted = recent.slice(16)
            recent = recent.slice(0, 16)
            for (const item of evicted) item.dismiss()
        }
        banner = notification
        bannerTimer.restart()
    }

    function toggleHistory() {
        if (active) historyOpen = !historyOpen
    }

    LazyLoader {
        active: center.active
        NotificationServer {
            bodyMarkupSupported: false
            bodyHyperlinksSupported: false
            actionsSupported: true
            onNotification: notification => center.receive(notification)
        }
    }

    Timer {
        id: bannerTimer
        interval: 5000
        onTriggered: center.banner = null
    }

    PanelWindow {
        id: panel
        visible: center.active && (center.historyOpen || !!center.banner)
        anchors { top: true; right: true }
        margins { top: 16; right: 16 }
        implicitWidth: Math.max(1, Math.min(360, screen ? screen.width - 32 : 360))
        implicitHeight: center.historyOpen ? Math.min(460, screen ? screen.height - 32 : 460)
            : Math.min(230, notificationContent.implicitHeight + 20)
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.namespace: "jarvis-notifications"
        WlrLayershell.layer: WlrLayer.Top
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand
        color: "transparent"

        Rectangle {
            anchors.fill: parent
            color: "#F20A1722"
            border.color: "#4C90A0"
            radius: 10
        }

        ScrollView {
            anchors.fill: parent
            anchors.margins: 10
            contentWidth: availableWidth
            contentHeight: notificationContent.implicitHeight
            clip: true

            ColumnLayout {
                id: notificationContent
                width: parent.width
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    visible: center.historyOpen
                    Text {
                        Layout.fillWidth: true
                        text: center.count ? "Notifications" : "No notifications"
                        textFormat: Text.PlainText
                        color: "#EAF8FF"
                        font.weight: Font.DemiBold
                    }
                    Widgets.ActionButton {
                        text: "Close"
                        onClicked: center.historyOpen = false
                    }
                }

                Repeater {
                    model: center.historyOpen ? center.recent : center.banner ? [center.banner] : []

                    ColumnLayout {
                        id: row
                        required property var modelData
                        Layout.fillWidth: true

                        RowLayout {
                            Layout.fillWidth: true
                            Text {
                                Layout.fillWidth: true
                                text: String(row.modelData.summary || row.modelData.appName || "Notification").slice(0, 180)
                                textFormat: Text.PlainText
                                elide: Text.ElideRight
                                color: "#EAF8FF"
                                font.weight: Font.DemiBold
                            }
                            Widgets.ActionButton {
                                text: "Dismiss"
                                implicitHeight: 32
                                onClicked: row.modelData.dismiss()
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            text: String(row.modelData.body || "").slice(0, 500)
                            textFormat: Text.PlainText
                            wrapMode: Text.Wrap
                            maximumLineCount: 4
                            elide: Text.ElideRight
                            color: "#BBD6E4"
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            Repeater {
                                model: (row.modelData.actions || []).slice(0, 2)
                                Widgets.ActionButton {
                                    required property var modelData
                                    text: String(modelData.text || "Open").slice(0, 18)
                                    implicitHeight: 32
                                    onClicked: modelData.invoke()
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
