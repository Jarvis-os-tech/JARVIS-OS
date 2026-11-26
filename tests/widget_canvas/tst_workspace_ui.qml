import QtQuick
import QtTest
import "../../ui/jarvis_widgets"
import "../../ui/jarvis_widgets/WorkspaceModel.js" as Workspace
import "../../ui/jarvis_widgets/SessionModel.js" as Session
import "../../ui/jarvis_widgets/TaskEvents.js" as Tasks
import "../../ui/jarvis_shell/HudModel.js" as Hud

TestCase {
    id: test
    name: "WorkspaceUI"
    width: 800
    height: 400
    visible: true
    when: windowShown

    readonly property string filePrompt: "Open /tmp/Project Notes.md"
    readonly property var longChecklist: {
        const rows = [];
        for (let i = 1; i <= 20; i++)
            rows.push({type: "text", text: "Checklist item " + i});
        rows.push({type: "toggle", label: "Review last item", bind: "reviewed"});
        return {state: {reviewed: false}, layout: {type: "column", children: rows}};
    }

    Component {
        id: workspaceCards
        Item {
            property var snapshot
            property alias files: files
            property alias tasks: tasks
            WidgetCard {
                id: files
                width: 360
                height: 230
                widget: parent.snapshot.items[0]
            }
            WidgetCard {
                id: tasks
                x: 380
                width: 360
                height: 230
                widget: parent.snapshot.items[1]
                onStateEdited: values => savedState = Hud.draftChanges(widget.data.state, values)
            }
        }
    }
    SignalSpy { id: submitted; signalName: "submitted" }

    function payload(revision, label) {
        return {id: "project", kind: "workspace", title: "Project", data: {
            revision: revision, reopen: false, panels: [
                {section: "files", view: {layout: {type: "entry", id: "notes", style: "files",
                    number: 1, label: label, prompt: filePrompt}}},
                {section: "tasks", view: longChecklist}
            ]
        }};
    }

    function mountWorkspace() {
        const cards = createTemporaryObject(workspaceCards, test, {
            snapshot: Workspace.apply([], Workspace.initial(), payload(1, "Project notes"))
        });
        verify(cards);
        verify(waitForPolish(cards.files));
        verify(waitForPolish(cards.tasks));
        return cards;
    }

    function test_file_entry_keyboard_submission_and_busy_guard() {
        const files = mountWorkspace().files;
        const entry = findChild(files, "control-notes");
        verify(entry);
        submitted.target = files;
        submitted.clear();
        entry.forceActiveFocus();
        verify(entry.activeFocus);
        keyClick(Qt.Key_Space);
        compare(submitted.count, 1);
        compare(submitted.signalArguments[0][0], filePrompt);

        files.requestBusy = true;
        verify(!entry.enabled);
        keyClick(Qt.Key_Space);
        mouseClick(entry);
        compare(submitted.count, 1);

        files.requestBusy = false;
        entry.forceActiveFocus();
        keyClick(Qt.Key_Space);
        compare(submitted.count, 2);
    }

    function test_checklist_and_scroll_survive_another_panel_update() {
        const cards = mountWorkspace();
        const last = findChild(cards.tasks, "control-reviewed");
        verify(last);
        const viewport = cards.tasks.generatedView.parent.parent;
        tryVerify(() => viewport.contentHeight > viewport.height);
        verify(last.mapToItem(viewport, 0, last.height).y > viewport.height);

        for (let i = 0; i < 12; i++)
            mouseWheel(viewport, 20, 60, 0, -720, Qt.NoButton, Qt.NoModifier, 30);
        tryCompare(viewport, "moving", false);
        verify(Math.round(last.mapToItem(viewport, 0, last.height).y) <= viewport.height);
        verify(last.mapToItem(viewport, 0, 0).y >= 0);
        mouseClick(last);
        verify(last.checked);
        const scrollY = viewport.contentY;

        cards.snapshot = Workspace.apply(cards.snapshot.items, cards.snapshot.state, payload(2, "Updated notes"));
        verify(waitForPolish(cards.tasks));
        compare(cards.files.widget.data.layout.label, "Updated notes");
        compare(findChild(cards.tasks, "control-reviewed"), last);
        verify(last.checked);
        compare(viewport.contentY, scrollY);
    }

    function taskEvent(id, sequence, terminal) {
        return {schema_version: 1, stream_id: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", sequence: sequence,
            task_id: "file_task:" + id, widget_id: "jtask_" + id.repeat(24), source: "file_task",
            revision: 1, generation: 1, state: terminal ? "completed" : "running", terminal: terminal,
            title: "Save notes", message: "Observed task state", updated_at: "2026-11-03T00:00:00Z",
            evidence: {verified: terminal, scope: terminal ? "file_step_checks" : "none"}, progress: null};
    }

    function test_session_restores_active_tasks_and_fences_dismissed_and_expired_replay() {
        const active = taskEvent("a", 1, false);
        const hidden = taskEvent("b", 2, false);
        const finished = taskEvent("c", 3, true);
        const batch = {schema_version: 1, stream_id: active.stream_id, cursor: 3, events: [active, hidden, finished]};
        const observed = Tasks.apply([], Tasks.initial(), batch, 0);
        const state = Tasks.hide(observed.state, hidden.widget_id);
        const shown = observed.items.filter(item => item.id !== hidden.widget_id);
        const encoded = Session.encode(shown, Workspace.initial(), {}, state);
        const restored = Session.decode(encoded, 120001);
        compare(restored.widgets.length, 1);
        compare(restored.widgets[0].id, active.widget_id);
        compare(restored.widgets[0].data.label, "Working");
        compare(restored.widgets[0].data.text, active.message);
        compare(restored.tasks.cursor, 3);
        compare(restored.tasks.revisions[active.task_id].revision, 1);

        batch.cursor = 5;
        batch.events = [Object.assign({}, hidden, {sequence: 4, revision: 2}),
            Object.assign({}, finished, {sequence: 5, revision: 2})];
        const replay = Tasks.apply(restored.widgets, restored.tasks, batch, 120001);
        compare(replay.accepted, 0);
        compare(replay.items.length, 1);

        const invalid = JSON.parse(encoded);
        invalid.widgets[0].task.stream_id = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
        let rejected = false;
        try { Session.decode(JSON.stringify(invalid), 120001); } catch (error) { rejected = true; }
        verify(rejected);

        const legacy = JSON.parse(encoded);
        legacy.widgets = [];
        delete legacy.tasks.revisions;
        const old = Session.decode(JSON.stringify(legacy), 120001);
        compare(old.tasks.cursor, 3);
        compare(old.tasks.hidden[hidden.widget_id], 1);
    }
}
