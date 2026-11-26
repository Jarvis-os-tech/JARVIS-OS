pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Wayland
import "HudModel.js" as Hud
import "style"

PanelWindow {
    id: root

    required property var entries
    required property var drafts
    property bool liveActions: false
    property bool reducedMotion: Style.reduceMotion
    property string apiState: "Unavailable"
    property string sendingWidget: ""
    property var submissionErrors: ({})
    property var submissionFeedback: ({})
    signal submitted(string id, string prompt, var values)
    signal restoreRequested(string id)
    signal dismissRequested(string id)
    signal pinRequested(string id, bool pinned)
    signal interactionChanged(string id, bool active)
    signal draftChanged(string id, var values)
    signal geometryRequested(string id, var geometry)

    readonly property var left: entries.filter(card => card.mounted && card.side === "left")
    readonly property var right: entries.filter(card => card.mounted && card.side === "right")
    property var slots: []
    readonly property var occupiedBounds: {
        if (!visible) return []
        const items = slots.filter(slot => slot?.active && slot.width > 0 && slot.height > 0)
        if (!items.length) return []
        return items.map(item => ({x: item.x, y: item.y, width: item.width, height: item.height}))
    }

    function nativeStatus(name) {
        for (const slot of slots) {
            const card = slot ? slot.item : null
            if (card && card[name]) return card[name].snapshot()
        }
        return null
    }

    function telemetryStatus() {
        for (const slot of slots) {
            const card = slot ? slot.item : null
            if (card && card.telemetry) {
                const cpu = card.telemetry.cpu
                const memory = card.telemetry.memory
                return {cpu: cpu < 0 ? null : Math.round(cpu * 100),
                        memory: memory < 0 ? null : Math.round(memory * 100)}
            }
        }
        return null
    }

    anchors { left: true; right: true; top: true; bottom: true }
    exclusionMode: ExclusionMode.Ignore
    color: "transparent"
    WlrLayershell.namespace: "jarvis-hud"
    WlrLayershell.layer: WlrLayer.Top
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand

    mask: Region {
        Region { item: root.slots[0]?.active ? root.slots[0] : null; intersection: Intersection.Combine }
        Region { item: root.slots[1]?.active ? root.slots[1] : null; intersection: Intersection.Combine }
        Region { item: root.slots[2]?.active ? root.slots[2] : null; intersection: Intersection.Combine }
        Region { item: root.slots[3]?.active ? root.slots[3] : null; intersection: Intersection.Combine }
        Region { item: root.slots[4]?.active ? root.slots[4] : null; intersection: Intersection.Combine }
    }

    Repeater {
        model: 5
        onItemAdded: (index, item) => {
            const next = root.slots.slice()
            next[index] = item
            root.slots = next
        }
        onItemRemoved: (index, item) => {
            const next = root.slots.slice()
            next[index] = null
            root.slots = next
        }

        delegate: Loader {
            id: cardLoader
            required property int index
            readonly property bool onLeft: index < 3
            readonly property int rowIndex: onLeft ? index : index - 3
            readonly property var card: (onLeft ? root.left : root.right)[rowIndex] || null
            property string interactingId: ""
            readonly property Item contentItem: item as Item
            readonly property string cardId: card ? card.id : ""
            property bool instantiating: true

            active: root.visible && card !== null && instantiating
            readonly property var workspaceRects: ({
                brief: {x: 0.55, y: 0.07, w: 0.23, h: 0.18},
                files: {x: 0.025, y: 0.10, w: 0.25, h: 0.38},
                ideas: {x: 0.025, y: 0.53, w: 0.25, h: 0.40},
                plan: {x: 0.70, y: 0.29, w: 0.28, h: 0.64},
                tasks: {x: 0.355, y: 0.72, w: 0.315, h: 0.25}
            })
            readonly property var geometry: card?.geometry || (root.width >= 1000 && card?.section && root.entries.filter(entry => entry.mounted).every(entry => entry.workspace === card.workspace) ? workspaceRects[card.section] : null)
            function alterGeometry(dx, dy, resize) {
                const w = resize ? Math.max(240, Math.min(root.width - x, width + dx)) : width
                const h = resize ? Math.max(120, Math.min(root.height - y, height + dy)) : height
                const nx = resize ? x : Math.max(0, Math.min(root.width - w, x + dx))
                const ny = resize ? y : Math.max(40, Math.min(root.height - h, y + dy))
                root.geometryRequested(card.id, {x: nx/root.width, y: ny/root.height, w: w/root.width, h: h/root.height})
            }
            width: !active ? 0 : geometry ? Math.min(root.width, Math.max(240, geometry.w * root.width)) : Math.min(420, Math.floor((root.width - 64) / 2), Math.max(240, Math.floor(root.width * 0.30)))
            x: geometry ? Math.max(0, Math.min(root.width - width, geometry.x * root.width)) : onLeft ? 20 : root.width - width - 20
            readonly property real rowHeight: Math.floor((root.height - 80) / Math.max(1, (onLeft ? root.left : root.right).length))
            height: active && contentItem ? geometry ? Math.min(root.height - 40, Math.max(120, geometry.h * root.height)) : Math.max(0, Math.min(contentItem.implicitHeight, rowHeight - 12)) : 0
            y: {
                if (geometry) return Math.max(40, Math.min(root.height - height, geometry.y * root.height));
                let top = 62;
                const first = onLeft ? 0 : 3;
                for (let i = first; i < index; i++)
                    top += (root.slots[i] ? root.slots[i].height : 0) + 16;
                return top;
            }

            onCardIdChanged: {
                instantiating = false
                Qt.callLater(() => { instantiating = true })
                if (interactingId !== "" && (!card || card.id !== interactingId)) {
                    const previous = interactingId
                    interactingId = ""
                    Qt.callLater(() => root.interactionChanged(previous, false))
                }
            }

            sourceComponent: HologramCard {
                apiState: root.apiState
                reducedMotion: root.reducedMotion || Style.reduceMotion
                widget: {
                    const current = cardLoader.card
                    if (!current) return {title: "", kind: "text", data: {}}
                    return current
                }
                savedState: root.drafts[widget.id] || ({})
                requestFeedback: root.submissionFeedback[widget.id] || ""
                requestBusy: root.sendingWidget !== ""
                requestError: root.submissionErrors[widget.id] || submissionError
                property string submissionError: ""
                onSubmitted: (prompt, values) => {
                    if (root.liveActions) root.submitted(widget.id, prompt, values)
                    else submissionError = "Conversation actions are unavailable in this preview."
                }
                onMoved: (dx, dy) => cardLoader.alterGeometry(dx, dy, false)
                onResized: (dx, dy) => cardLoader.alterGeometry(dx, dy, true)
                onPinRequested: root.pinRequested(widget.id, !widget.pinned)
                onDismissRequested: root.dismissRequested(widget.id)
                onStateEdited: values => root.draftChanged(widget.id, values)
                onInteractingChanged: {
                    if (interacting && widget.id) {
                        cardLoader.interactingId = widget.id
                        root.interactionChanged(widget.id, true)
                    } else if (cardLoader.interactingId !== "") {
                        const previous = cardLoader.interactingId
                        cardLoader.interactingId = ""
                        root.interactionChanged(previous, false)
                    }
                }
            }
        }
    }

}
