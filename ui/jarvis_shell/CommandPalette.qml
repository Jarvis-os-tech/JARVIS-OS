pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import "../jarvis_widgets" as Widgets

PanelWindow {
    id: root

    property string feedback: ""
    property bool busy: false
    property var stage
    readonly property string query: command.text.trim()
    readonly property string lowerQuery: query.toLowerCase()
    readonly property bool reservedCommand: /^(ask|windows|lock|log|confirm|show|audio|device|media|clear|dismiss|pin|unpin|notifications)(\s|$)/.test(lowerQuery)
    readonly property bool appSearch: !query || lowerQuery === "apps" || lowerQuery === "applications"
        || !reservedCommand
    readonly property bool windowSearch: query.toLowerCase() === "windows" || query.toLowerCase().startsWith("windows ")
    readonly property var matches: stage && appSearch ? stage.findApps(lowerQuery.startsWith("open ") ? query.slice(5) : ["apps", "applications", "open"].includes(lowerQuery) ? "" : query) : []
    readonly property var windows: stage && windowSearch ? stage.listWindows().filter(window => window.title.toLowerCase().includes(query.slice(8).toLowerCase())).slice(0, 8) : []
    readonly property var resultKeys: appSearch ? matches.map(app => app.id) : windows.map(window => window.address)
    property string selectedKey: ""
    onQueryChanged: selectedKey = ""

    signal appRequested(string id)
    signal windowRequested(string action, string address)
    signal submitted(string text)
    signal closeRequested()

    function selectResult(step) {
        if (busy || !resultKeys.length) return false
        const index = resultKeys.indexOf(selectedKey)
        const next = index === -1 ? (step > 0 ? 0 : resultKeys.length - 1)
            : Math.max(0, Math.min(resultKeys.length - 1, index + step))
        selectedKey = resultKeys[next]
        return true
    }

    function submit() {
        const value = command.text.trim()
        if (busy) return
        const selected = resultKeys.indexOf(selectedKey)
        if (selected >= 0) {
            if (appSearch) appRequested(matches[selected].id)
            else windowRequested("focus", windows[selected].address)
        } else if (value && appSearch && matches.length &&
                   [matches[0].id, matches[0].name].some(label => String(label).toLowerCase() === lowerQuery)) {
            appRequested(matches[0].id)
        } else if (value && appSearch && matches.length === 1) {
            appRequested(matches[0].id)
        } else if (value) {
            submitted(value)
        }
    }

    implicitWidth: Math.max(1, Math.min(560, screen ? screen.width - 32 : 560))
    implicitHeight: fields.implicitHeight + 36
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.namespace: "jarvis-command-palette"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

    onBackingWindowVisibleChanged: if (backingWindowVisible) command.forceActiveFocus()

    Rectangle {
        anchors.fill: parent
        radius: 8
        color: "#FA0C1626"
        border.color: "#00E5FF"

        Rectangle {
            x: 18
            width: 38
            height: 2
            color: "#82CFEA"
        }

        ColumnLayout {
            id: fields
            anchors.fill: parent
            anchors.margins: 18
            spacing: 10
            Keys.onEscapePressed: root.closeRequested()

            RowLayout {
                Layout.fillWidth: true

                Text {
                    Layout.fillWidth: true
                    text: qsTr("HUD commands")
                    color: "#F5F9FF"
                    font.pixelSize: 19
                    font.weight: Font.DemiBold
                    Accessible.role: Accessible.Heading
                    Accessible.name: text
                }

                Widgets.ActionButton {
                    objectName: "palette-close"
                    text: qsTr("Close")
                    implicitHeight: 32
                    onClicked: root.closeRequested()
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                TextField {
                    id: command
                    objectName: "palette-command"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 44
                    focus: true
                    maximumLength: 16000
                    readOnly: root.busy
                    selectByMouse: true
                    placeholderText: qsTr("Open an app, show windows, or ask JARVIS")
                    color: "#F5F9FF"
                    placeholderTextColor: "#ACBED0"
                    selectionColor: "#235B91"
                    font.pixelSize: 15
                    Accessible.name: qsTr("HUD command")
                    onAccepted: root.submit()
                    Keys.onDownPressed: event => { event.accepted = root.selectResult(1) }
                    Keys.onUpPressed: event => { event.accepted = root.selectResult(-1) }

                    background: Rectangle {
                        radius: 5
                        color: "#08101C"
                        border.color: command.activeFocus ? "#00E5FF" : "#405C78"
                    }
                }

                Widgets.ActionButton {
                    objectName: "palette-submit"
                    text: root.busy ? qsTr("Running…") : qsTr("Run")
                    primary: true
                    enabled: !root.busy && command.text.trim().length > 0
                    onClicked: root.submit()
                }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                visible: !root.query
                Repeater {
                    model: [
                        {label: "System", command: "Show system"},
                        {label: "Audio", command: "Audio controls"},
                        {label: "Devices", command: "Device controls"},
                        {label: "Media", command: "Media controls"}
                    ]
                    Widgets.ActionButton {
                        required property var modelData
                        Layout.fillWidth: true
                        text: modelData.label
                        enabled: !root.busy
                        onClicked: root.submitted(modelData.command)
                    }
                }
            }

            Repeater {
                model: root.matches
                Widgets.ActionButton {
                    required property var modelData
                    Layout.fillWidth: true
                    text: modelData.name
                    enabled: !root.busy
                    primary: root.selectedKey === modelData.id
                    onClicked: root.appRequested(modelData.id)
                }
            }

            Repeater {
                model: root.windows
                RowLayout {
                    id: windowRow
                    required property var modelData
                    Layout.fillWidth: true
                    Widgets.ActionButton {
                        Layout.fillWidth: true
                        enabled: !root.busy
                        primary: root.selectedKey === windowRow.modelData.address
                        text: windowRow.modelData.title.length > 52 ? windowRow.modelData.title.slice(0, 51) + "…" : windowRow.modelData.title
                        Accessible.name: "Focus " + windowRow.modelData.title
                        onClicked: root.windowRequested("focus", windowRow.modelData.address)
                    }
                    Widgets.ActionButton {
                        enabled: !root.busy
                        text: windowRow.modelData.parked ? "Restore" : "Park"
                        Accessible.name: text + " " + windowRow.modelData.title
                        onClicked: root.windowRequested(windowRow.modelData.parked ? "restore" : "park", windowRow.modelData.address)
                    }
                }
            }

            Text {
                Layout.fillWidth: true
                visible: root.feedback.length > 0
                text: root.feedback
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                maximumLineCount: 3
                elide: Text.ElideRight
                color: "#D2E5F4"
                font.pixelSize: 13
            }
        }
    }
}
