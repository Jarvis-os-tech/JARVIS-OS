from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is needed to exercise the QML JavaScript handlers")
def test_widget_routes_gate_startup_and_share_revision_history():
    result = subprocess.run(
        ["node", "-"],
        input=r"""
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
function loadModel(path, imports = {}) {
    const source = fs.readFileSync(path, "utf8").replace(/^\.(pragma|import).*$/gm, "");
    vm.runInNewContext(source, imports);
    return imports;
}
const Views = loadModel("widgets/ViewSchema.js");
const Widgets = loadModel("widgets/WidgetModel.js", {Views});
const Workspaces = loadModel("widgets/WorkspaceModel.js", {Widgets});
const Hud = loadModel("shell/HudModel.js");
const source = fs.readFileSync("shell/HudPreview.qml", "utf8");
function method(name, indent) {
    const pad = " ".repeat(indent);
    const expression = new RegExp("^" + pad + "(function " + name +
        "\\([^\\n]*\\).*?\\n[\\s\\S]*?)\\n" + pad + "}", "m");
    const match = source.match(expression);
    assert.ok(match, "Missing QML handler " + name);
    return (match[1] + "\n}").replace(/: string(?=[,) {])/g, "");
}

const scope = vm.createContext({
    Widgets, Workspaces, Hud,
    desktopVisible: true, standaloneMode: false, liveMode: true,
    widgetSessionAvailable: false, sessionError: "", taskState: {pending: {}},
    sourceWidgets: [], entries: [], drafts: {}, submissionFeedback: {}, submissionErrors: {},
    workspaceState: Workspaces.initial(),
    sessionSaveTimer: {restart() {}}, saveSession() {},
    systemWidgetId: "jarvis_system_telemetry",
    audioWidgetId: "jarvis_audio_controls",
    mediaWidgetId: "jarvis_media_controls",
    deviceWidgetId: "jarvis_device_controls",
});
scope.root = scope;
const handlers = ["sessionUnavailable", "commit", "checkData", "event", "setGeometry",
    "clearWidgets", "clearHud", "showNativeWidget"].map(name => method(name, 4));
handlers.push(...["present", "manage", "taskEvents"].map(name => method(name, 8)));
vm.runInContext(handlers.join("\n"), scope);

const event = (action, payload) => scope.event(JSON.stringify({action, id: "project", payload}));
const snapshot = {id: "project", kind: "text", title: "Project", data: {text: "First"}, revision: 2};
for (const action of ["spawn_widget", "update_widget", "pin_widget", "dismiss_widget", "restore_widget"])
    assert.equal(event(action, snapshot).retryable, true, action);
for (const handler of ["present", "manage", "taskEvents"])
    assert.equal(JSON.parse(scope[handler]("{")).retryable, true, handler);
assert.equal(scope.clearHud().retryable, true);
assert.equal(scope.clearWidgets(false).retryable, true);
assert.equal(scope.setGeometry("project", {}).retryable, true);
assert.equal(scope.showNativeWidget(scope.systemWidgetId, "System", "system_telemetry").retryable, true);
assert.equal(scope.sourceWidgets.length, 0);
assert.equal(Object.keys(scope.workspaceState.dismissed).length, 0);
assert.equal(scope.event('{"action":"set_voice_state","payload":{"state":"listening"}}').ok, true);
assert.equal(scope.previewVoiceState, "listening");
scope.sessionError = "Cannot load saved widget state";
assert.equal(scope.clearHud().retryable, false);
assert.equal(scope.clearHud().error, scope.sessionError);

scope.widgetSessionAvailable = true;
scope.sessionError = "";
assert.equal(JSON.parse(scope.present(JSON.stringify(snapshot))).ok, true);
assert.equal(event("update_widget", {data: {text: "Unversioned"}}).stale, true);
assert.equal(event("update_widget", {revision: 1, data: {text: "Older"}}).stale, true);
assert.equal(event("update_widget", {revision: 2, data: {text: "Conflict"}}).ok, false);
assert.equal(scope.sourceWidgets[0].data.text, "First");
assert.equal(event("update_widget", {revision: 3, data: {text: "Current"}}).ok, true);
assert.equal(scope.sourceWidgets[0].title, "Project");
assert.equal(scope.sourceWidgets[0].data.text, "Current");
assert.equal(scope.workspaceState.versions["id:project"].revision, 3);

assert.equal(JSON.parse(scope.present(JSON.stringify(snapshot))).stale, true);
assert.equal(event("dismiss_widget").ok, true);
assert.equal(scope.workspaceState.versions["id:project"].digest, "");
const next = {...snapshot, revision: 4, data: {text: "Reopened"}};
assert.equal(JSON.parse(scope.present(JSON.stringify(next))).dismissed, true);
assert.equal(event("spawn_widget", {...next, reopen: true}).ok, true);
assert.equal(scope.sourceWidgets[0].data.text, "Reopened");
""",
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
