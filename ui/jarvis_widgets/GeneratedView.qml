import QtQuick
import QtQuick.Window
import "ViewSchema.js" as Schema

Item {
    id: view
    property var specification: ({state: {}, computed: {}, layout: {type: "text", text: ""}})
    property var formState: ({})
    property var savedState: ({})
    function restoreState() {
        const next = Object.assign({}, specification.state || {});
        for (const key of Object.keys(next))
            if (Object.prototype.hasOwnProperty.call(savedState, key) && typeof savedState[key] === typeof next[key]) next[key] = savedState[key];
        formState = next;
    }
    onSavedStateChanged: restoreState()
    property bool busy: false
    readonly property var choiceNodes: collectChoices(specification.layout)
    readonly property bool hasChoices: choiceNodes.length > 0
    signal stateEdited(var values)
    signal submitted(string prompt, var values)
    signal dismissRequested()
    implicitHeight: tree.implicitHeight
    onSpecificationChanged: restoreState()
    Component.onCompleted: restoreState()
    function value(expression) { return Schema.resolve(expression, formState, specification.computed || {}); }
    function format(text) { return Schema.format(text, formState, specification.computed || {}); }
    function collectChoices(node) {
        if (!node || typeof node !== "object") return [];
        if (node.type === "choice") return [node];
        let items = [];
        for (const child of (node.children || [])) items = items.concat(collectChoices(child));
        return items;
    }
    function validInputs(node) {
        if (node.type === "input" && node.required && !String(formState[node.bind] || "").trim()) return false;
        return (node.children || []).every(child => validInputs(child));
    }
    function edit(key, value) {
        formState = Object.assign({}, formState, {[key]: value});
        stateEdited(formState);
    }
    function choose(node) {
        if (busy || !node || node.type !== "choice") return false;
        const next = Object.assign({}, formState, {
            selected_index: node.index,
            selected_id: node.id || ("choice_" + node.index),
            selected_value: node.value !== undefined ? node.value : node.label,
            selected_label: node.label
        });
        formState = next;
        stateEdited(formState);
        submitted(format(node.prompt), formState);
        return true;
    }
    function selectChoice(index) {
        const match = choiceNodes.find(item => item.index === index);
        return match ? choose(match) : false;
    }
    function handleKeyEvent(event) {
        const focused = Window.window ? Window.window.activeFocusItem : null;
        const editingText = focused && focused.cursorPosition !== undefined && focused.readOnly === false;
        if (!hasChoices || busy || editingText) return false;
        if (event.key >= Qt.Key_1 && event.key <= Qt.Key_9) {
            if (selectChoice(event.key - Qt.Key_0)) {
                event.accepted = true;
                return true;
            }
        } else if (event.key === Qt.Key_Escape) {
            dismissRequested();
            event.accepted = true;
            return true;
        }
        return false;
    }
    Keys.onPressed: event => handleKeyEvent(event)
    ViewNode {
        id: tree
        width: parent.width
        node: view.specification.layout
        context: view
    }
}
