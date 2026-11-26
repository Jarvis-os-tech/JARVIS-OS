pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    property var node: ({type: "text", text: ""})
    property var context
    implicitHeight: renderer.item ? renderer.item.implicitHeight : 0
    objectName: node.id || ""
    Loader {
        id: renderer
        width: parent.width
        sourceComponent: root.node.type === "row" ? rowLayout : root.node.type === "column" ? columnLayout
            : root.node.type === "heading" || root.node.type === "text" ? textNode
            : root.node.type === "metric" ? metricNode : root.node.type === "input" ? inputNode
            : root.node.type === "slider" ? sliderNode : root.node.type === "toggle" ? toggleNode
            : root.node.type === "select" ? selectNode : root.node.type === "button" ? buttonNode
            : root.node.type === "entry" ? entryNode
            : root.node.type === "choice" ? choiceNode
            : root.node.type === "canvas" ? canvasNode : dividerNode
    }
    Component {
        id: columnLayout
        Column {
            spacing: 10
            Repeater {
                model: root.node.children
                Loader {
                    required property var modelData
                    width: parent.width
                    Component.onCompleted: setSource(Qt.resolvedUrl("ViewNode.qml"), {node: modelData, context: root.context})
                }
            }
        }
    }
    Component {
        id: rowLayout
        RowLayout {
            spacing: 16
            Repeater {
                model: root.node.children
                Loader {
                    required property var modelData
                    Layout.fillWidth: true; Layout.preferredWidth: 1
                    Layout.alignment: Qt.AlignTop
                    Component.onCompleted: setSource(Qt.resolvedUrl("ViewNode.qml"), {node: modelData, context: root.context})
                }
            }
        }
    }
    Component {
        id: textNode
        Text {
            text: root.context.format(root.node.text)
            textFormat: Text.PlainText; wrapMode: Text.WordWrap
            lineHeight: 1.4
            font.family: "Inter"
            font.pixelSize: root.node.type === "heading" ? 18 : 14
            font.weight: root.node.type === "heading" ? Font.DemiBold : Font.Normal
            color: root.node.tone === "muted" ? "#90BDB8" : root.node.tone === "accent" ? "#82FFF3" : "#E5F7F3"
        }
    }
    Component {
        id: metricNode
        Column {
            spacing: 4
            Text { text: root.context.format(root.node.label); textFormat: Text.PlainText; color: "#90BDB8"; font.pixelSize: 13 }
            Text { text: String(root.context.value(root.node.value)); textFormat: Text.PlainText; color: "#E5F7F3"; font.pixelSize: 28; font.weight: Font.DemiBold }
        }
    }
    Component {
        id: inputNode
        Column {
            spacing: 6
            Text { text: root.context.format(root.node.label); textFormat: Text.PlainText; color: "#90BDB8"; font.pixelSize: 13 }
            TextField {
                width: parent.width; implicitHeight: 44
                objectName: "control-" + (root.node.id || root.node.bind)
                text: String(root.context.formState[root.node.bind] ?? "")
                placeholderText: root.node.placeholder || ""
                maximumLength: 2000; selectByMouse: true
                color: "#E5F7F3"; font.pixelSize: 15
                Accessible.name: root.node.label
                background: Rectangle { radius: 10; color: "#041C20"; border.color: parent.activeFocus ? "#82FFF3" : "#305552" }
                onTextEdited: root.context.edit(root.node.bind, text)
            }
        }
    }
    Component {
        id: sliderNode
        Column {
            spacing: 4
            Text { text: root.context.format(root.node.label) + " · " + root.context.formState[root.node.bind]; textFormat: Text.PlainText; color: "#C7CFD9"; font.pixelSize: 14 }
            Slider {
                width: parent.width; implicitHeight: 44
                objectName: "control-" + (root.node.id || root.node.bind)
                from: root.node.min ?? 0; to: root.node.max ?? 100; stepSize: root.node.step ?? 1
                value: Number(root.context.formState[root.node.bind])
                Accessible.name: root.node.label
                onMoved: root.context.edit(root.node.bind, value)
                background: Rectangle { x: 8; y: parent.height / 2 - 2; width: parent.width - 16; height: 4; radius: 2; color: "#305552" }
                handle: Rectangle { x: 8 + parent.visualPosition * (parent.width - width - 16); y: parent.height / 2 - 9; width: 18; height: 18; radius: 9; color: "#82FFF3" }
            }
        }
    }
    Component {
        id: toggleNode
        CheckBox {
            id: taskToggle
            objectName: "control-" + (root.node.id || root.node.bind)
            text: root.context.format(root.node.label); checked: root.context.formState[root.node.bind] === true
            hoverEnabled: true
            implicitHeight: Math.max(44, contentItem.implicitHeight + 12)
            Accessible.name: text
            indicator: Rectangle {
                x: 2; y: (taskToggle.height - height) / 2
                width: 18; height: 18; radius: 4
                color: taskToggle.checked ? "#0B4548" : "#031C20"
                border.color: taskToggle.visualFocus || taskToggle.hovered ? "#A1FFF8" : "#59BDB6"
                border.width: taskToggle.visualFocus ? 2 : 1
                Text { anchors.centerIn: parent; text: taskToggle.checked ? "✓" : ""; color: "#82FFF3"; font.pixelSize: 14 }
            }
            contentItem: Text {
                leftPadding: 32
                text: taskToggle.text; textFormat: Text.PlainText
                font.family: "Inter"; font.pixelSize: 14
                color: taskToggle.checked ? "#90BDB8" : "#E5F7F3"
                font.strikeout: taskToggle.checked
                wrapMode: Text.WordWrap
                verticalAlignment: Text.AlignVCenter
            }
            onToggled: root.context.edit(root.node.bind, checked)
        }
    }
    Component {
        id: selectNode
        Column {
            spacing: 6
            Text { text: root.context.format(root.node.label); textFormat: Text.PlainText; color: "#90BDB8"; font.pixelSize: 13 }
            ComboBox {
                width: parent.width; implicitHeight: 44
                objectName: "control-" + (root.node.id || root.node.bind)
                model: root.node.options
                currentIndex: root.node.options.indexOf(root.context.formState[root.node.bind])
                palette.button: "#041C20"; palette.buttonText: "#E5F7F3"; palette.highlight: "#82FFF3"
                Accessible.name: root.node.label
                onActivated: root.context.edit(root.node.bind, currentText)
            }
        }
    }
    Component {
        id: buttonNode
        ActionButton {
            objectName: "control-" + (root.node.id || "action")
            text: root.context.format(root.node.label); primary: true
            enabled: !root.context.busy && root.context.validInputs(root.context.specification.layout)
            onClicked: root.context.submitted(root.context.format(root.node.prompt), root.context.formState)
        }
    }
    Component {
        id: choiceNode
        Button {
            id: choiceButton
            readonly property bool isSelected: Number(root.context.formState.selected_index || 0) === Number(root.node.index)
            readonly property string primaryText: root.context.format(root.node.label)
            readonly property string detailText: root.node.detail ? root.context.format(root.node.detail) : ""
            objectName: "control-" + (root.node.id || ("choice-" + root.node.index))
            width: parent.width
            implicitHeight: detailText.length > 0 ? 58 : 44
            hoverEnabled: true
            focusPolicy: Qt.StrongFocus
            enabled: !root.context.busy
            Accessible.name: String(root.node.index) + ". " + primaryText
            onClicked: root.context.choose(root.node)
            contentItem: RowLayout {
                spacing: 10
                Rectangle {
                    Layout.preferredWidth: 26
                    Layout.preferredHeight: 26
                    Layout.alignment: Qt.AlignVCenter
                    radius: 7
                    color: choiceButton.isSelected ? "#55DDEA" : "#122130"
                    border.color: choiceButton.isSelected || choiceButton.hovered || choiceButton.visualFocus ? "#55DDEA" : "#40596B"
                    border.width: 1
                    Text {
                        anchors.centerIn: parent
                        text: String(root.node.index)
                        textFormat: Text.PlainText
                        font.family: "monospace"
                        font.pixelSize: 13
                        font.weight: Font.Bold
                        color: choiceButton.isSelected ? "#09222A" : "#55DDEA"
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignVCenter
                    spacing: 2
                    Text {
                        Layout.fillWidth: true
                        text: choiceButton.primaryText
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        font.pixelSize: 14
                        font.weight: Font.DemiBold
                        color: !choiceButton.enabled ? "#8E9BAD" : "#F2F5FA"
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: choiceButton.detailText.length > 0
                        text: choiceButton.detailText
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        font.pixelSize: 12
                        color: "#90BDB8"
                    }
                }
            }
            background: Rectangle {
                radius: 10
                color: choiceButton.down ? "#2A3E52" : choiceButton.isSelected ? "#0B4548" : choiceButton.hovered ? "#093438" : "#031C20"
                border.width: choiceButton.visualFocus || choiceButton.isSelected ? 2 : 1
                border.color: choiceButton.visualFocus || choiceButton.isSelected ? "#55DDEA" : choiceButton.hovered ? "#4E6B82" : "#344759"
                opacity: choiceButton.enabled ? 1 : 0.6
            }
        }
    }
    Component {
        id: entryNode
        Button {
            id: entryButton
            objectName: "control-" + (root.node.id || "entry")
            readonly property color accent: root.node.style === "ideas" ? "#CB9AF4" : "#82FFF3"
            width: parent.width
            implicitHeight: entryContent.implicitHeight + 20
            padding: 10
            hoverEnabled: true
            focusPolicy: root.node.prompt ? Qt.StrongFocus : Qt.NoFocus
            enabled: !root.context.busy
            Accessible.name: root.node.label
            onClicked: if (root.node.prompt) root.context.submitted(root.node.prompt, root.context.formState)
            contentItem: RowLayout {
                id: entryContent
                spacing: 10
                Text {
                    text: root.node.style === "plan" ? String(root.node.number).padStart(2, "0") : root.node.style === "files" ? "▤" : "•"
                    font.pixelSize: 16; color: entryButton.accent
                    Layout.alignment: Qt.AlignTop
                }
                ColumnLayout {
                    spacing: 4
                    Layout.fillWidth: true
                    Text {
                        Layout.fillWidth: true
                        text: root.node.label; textFormat: Text.PlainText
                        wrapMode: Text.Wrap; color: "#E5F7F3"; font.pixelSize: 14
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: text.length > 0
                        text: root.node.detail || ""; textFormat: Text.PlainText
                        wrapMode: Text.Wrap; color: "#90BDB8"; font.pixelSize: 12
                    }
                }
            }
            background: Rectangle {
                radius: 9
                color: entryButton.down && root.node.prompt ? "#0B4548" : root.node.style === "ideas" ? "transparent" : "#60073F40"
                border.width: root.node.style === "ideas" && !entryButton.visualFocus ? 0 : 1
                border.color: entryButton.visualFocus || (entryButton.hovered && root.node.prompt) ? entryButton.accent : "#4055BDB6"
            }
        }
    }
    Component { id: canvasNode; DrawCanvas { node: root.node; viewContext: root.context } }
    Component { id: dividerNode; Rectangle { implicitHeight: 1; color: "#305552" } }
}
