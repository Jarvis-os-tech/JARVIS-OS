import QtQuick
import QtQuick.Controls
import QtTest
import "../../ui/jarvis_widgets"
import "../../ui/jarvis_widgets/WidgetModel.js" as Model
import "../../ui/jarvis_widgets/ViewSchema.js" as Schema
import "../../ui/jarvis_widgets/TaskEvents.js" as Tasks
import "../../ui/jarvis_widgets/WorkspaceModel.js" as Workspace
import "../../ui/jarvis_widgets/SessionModel.js" as Session

TestCase {
    id: test
    name: "ExistingShellWidgets"
    width: 650; height: 520; visible: true
    when: windowShown

    Component { id: cardComponent; WidgetCard { width: 600; height: 450 } }
    InputBar { id: input; width: 600; draft: "Keep my draft" }
    SignalSpy { id: closed; target: input; signalName: "closeRequested" }
    Component { id: viewComponent; GeneratedView { width: 600 } }
    property var activeView: null
    SignalSpy { id: submitted; target: test.activeView; signalName: "submitted" }
    property var activeCard: null
    SignalSpy { id: cardSubmitted; target: test.activeCard; signalName: "submitted" }
    SignalSpy { id: cardDismissed; target: test.activeCard; signalName: "dismissRequested" }

    function test_form_edits_survive_recreation_and_refresh() {
        const state = Model.retainedState({topic: "", count: 2}, {topic: "My research", count: 4, removed: "old"});
        compare(state.topic, "My research"); compare(state.count, 4);
        verify(state.removed === undefined);
        compare(Model.retainedState({count: "new"}, state).count, "new");
        const view = createTemporaryObject(viewComponent, test, {
            specification: {state: {topic: ""}, layout: {type: "input", bind: "topic", label: "Topic"}},
            savedState: state
        });
        verify(view); compare(view.formState.topic, "My research");
    }

    function test_unframed_metric_uses_content_height() {
        const card = createTemporaryObject(cardComponent, test, {
            framed: false,
            widget: {id: "metric", kind: "view", title: "Progress", data: {
                layout: {type: "metric", label: "Completed", value: "72%"}
            }}
        });
        verify(card); wait(40);
        verify(card.generatedHeight > 0);
        compare(card.implicitHeight, card.generatedHeight + 32);
        card.framed = true;
        compare(card.implicitHeight, card.generatedHeight + 72);
    }

    function test_input_has_no_escape_navigation() {
        closed.clear();
        input.takeFocus(); keyClick(Qt.Key_Escape);
        compare(closed.count, 0); compare(input.draft, "Keep my draft");
    }
    function viewSpec() {
        return {state: {hours: 4, rate: 25}, computed: {cost: {op: "multiply", args: [{ref: "hours"}, {ref: "rate"}]}},
            layout: {type: "column", children: [
                {type: "slider", id: "hours", label: "Hours", bind: "hours", min: 1, max: 12},
                {type: "metric", label: "Cost", value: {ref: "cost"}},
                {type: "button", id: "apply", label: "Use estimate", prompt: "Use {{hours}} hours, total {{cost}}"}
            ]}};
    }
    function test_generated_controls_recalculate_and_submit_selected_values() {
        activeView = createTemporaryObject(viewComponent, test, {specification: Schema.validate(viewSpec())});
        verify(activeView); wait(30);
        compare(activeView.value({ref: "cost"}), 100);
        const slider = findChild(activeView, "control-hours"); verify(slider);
        slider.forceActiveFocus(); keyClick(Qt.Key_Right);
        compare(activeView.formState.hours, 5);
        compare(activeView.value({ref: "cost"}), 125);
        const action = findChild(activeView, "control-apply"); verify(action);
        submitted.clear(); action.forceActiveFocus(); keyClick(Qt.Key_Space);
        compare(submitted.count, 1);
        compare(submitted.signalArguments[0][0], "Use 5 hours, total 125");
        compare(submitted.signalArguments[0][1].hours, 5);
        activeView = null;
    }
    function test_generated_layouts_reject_code_cycles_and_unknown_bindings() {
        let failures = 0;
        for (const spec of [
            {layout: {type: "html", code: "alert(1)"}},
            {computed: {a: {ref: "a"}}, layout: {type: "text", text: "A"}},
            {state: {}, layout: {type: "input", label: "Bad", bind: "unknown"}}
        ]) { try { Schema.validate(spec); } catch (error) { failures++; } }
        compare(failures, 3);
        compare(Schema.resolve({op: "divide", args: [1, 0]}, {}, {}), "Unavailable");
    }
    function test_generated_canvas_and_nested_layout_render() {
        const spec = {state: {x: 200}, layout: {type: "row", children: [
            {type: "canvas", height: 180, shapes: [{type: "circle", x: {ref: "x"}, y: 500, r: 50}]},
            {type: "column", children: [{type: "heading", text: "Diagram"}, {type: "text", text: "Position {{x}}"}]}
        ]}};
        const view = createTemporaryObject(viewComponent, test, {specification: Schema.validate(spec)});
        verify(view); wait(30); verify(view.implicitHeight >= 180);
    }

    function test_required_native_form_blocks_empty_submission() {
        const spec = {state: {topic: ""}, layout: {type: "column", children: [
            {type: "input", bind: "topic", label: "Topic", placeholder: "Research topic", required: true},
            {type: "button", id: "send", label: "Research", prompt: "Research topic"}
        ]}};
        activeView = createTemporaryObject(viewComponent, test, {specification: Schema.validate(spec)});
        verify(activeView); wait(30);
        const button = findChild(activeView, "control-send");
        const field = findChild(activeView, "control-topic");
        verify(button); verify(field); verify(!button.enabled);
        compare(field.placeholderText, "Research topic");
        activeView.edit("topic", "  "); verify(!button.enabled);
        field.forceActiveFocus(); keyClick(Qt.Key_A); wait(10);
        verify(button.enabled);
        submitted.clear(); button.forceActiveFocus(); keyClick(Qt.Key_Space);
        compare(submitted.count, 1);
        verify(submitted.signalArguments[0][1].topic.trim().length > 0);
        activeView = null;
    }

    function test_workspace_entry_uses_existing_action_handler() {
        activeView = createTemporaryObject(viewComponent, test, {specification: Schema.validate({state: {}, layout: {
            type: "entry", id: "file", label: "Notes", detail: "Project notes", style: "files", number: 1, prompt: "Open project notes"
        }})});
        verify(activeView); wait(20);
        const button = findChild(activeView, "control-file"); verify(button);
        submitted.clear(); button.forceActiveFocus(); keyClick(Qt.Key_Space);
        compare(submitted.count, 1); compare(submitted.signalArguments[0][0], "Open project notes");
        activeView = null;
    }
    function test_task_reconnect_preserves_dismissal() {
        const event = taskEvent("running", 1);
        const first = Tasks.apply([], Tasks.initial(), taskBatch(event), 0);
        const hidden = Tasks.hide(first.state, event.widget_id);
        const resumed = Object.assign({}, event, {stream_id: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"});
        const updated = Tasks.apply([], hidden, taskBatch(resumed), 0);
        compare(updated.items.length, 0); compare(updated.state.stream_id, resumed.stream_id);
    }
    function test_drafts_cannot_restore_invalid_changed_controls() {
        const spec = {state: {amount: 5}, layout: {type: "slider", label: "Amount", bind: "amount", min: 0, max: 10}};
        compare(Model.compatibleDraft(spec, {amount: 8}).amount, 8);
        compare(Object.keys(Model.compatibleDraft(spec, {amount: 80})).length, 0);
        compare(Object.keys(Model.compatibleDraft(spec, {unknown: "value"})).length, 0);
    }
    function test_reopen_retries_cannot_undo_later_dismissal() {
        const payload = workspacePayload(2, "Current"); payload.data.reopen = true;
        const first = Workspace.apply([], Workspace.initial(), payload);
        const hidden = Workspace.dismiss(first.state, first.items[0]);
        compare(Workspace.apply(first.items.slice(1), hidden, payload).items.length, 1);
        const closed = Workspace.clear(first.state, first.items, false);
        verify(Workspace.apply([], closed, payload).dismissed);
        const ordinary = {id: "normal", kind: "text", title: "Text", data: {text: "Text"}, revision: 2, reopen: true};
        const state = Workspace.checkUpdate(Workspace.initial(), ordinary).state;
        verify(Workspace.checkUpdate(Workspace.dismiss(state, {id: "normal"}), ordinary).dismissed);
    }
    function test_widget_churn_does_not_exhaust_identity_capacity() {
        let state = Workspace.initial();
        for (let i = 0; i < 300; i++)
            state = Workspace.checkUpdate(state, {id: "card" + i, kind: "text", title: "Text", data: {text: "Text"}}).state;
        compare(Object.keys(state.versions).length, 0);
        for (let i = 0; i < 150; i++) {
            const payload = workspacePayload(0, "Ephemeral"); payload.id = "project" + i;
            state = Workspace.apply([], state, payload).state;
        }
        compare(Object.keys(state.groups).length, 1);
    }
    function test_workspace_and_ordinary_namespaces_cannot_collide() {
        const group = Workspace.apply([], Workspace.initial(), workspacePayload(1, "Project"));
        let rejected = false;
        try { Workspace.checkUpdate(group.state, {id: "project", kind: "text", title: "Conflict", data: {text: "X"}}); } catch (e) { rejected = true; }
        verify(rejected);
        const normal = {id: "project", kind: "text", title: "Conflict", data: {text: "X"}, revision: 1};
        const state = Workspace.checkUpdate(Workspace.initial(), normal).state;
        rejected = false;
        try { Workspace.apply([], state, workspacePayload(1, "Project")); } catch (e) { rejected = true; }
        verify(rejected);
    }
    function test_regular_widget_revision_and_dismissal_contract() {
        const payload = {id: "live", kind: "text", title: "Live", data: {text: "new"}, revision: 2};
        const first = Workspace.checkUpdate(Workspace.initial(), payload);
        verify(first.state);
        verify(Workspace.checkUpdate(first.state, Object.assign({}, payload, {revision: 1})).stale);
        verify(Workspace.checkUpdate(first.state, Object.assign({}, payload, {revision: 0})).stale);
        const closed = Workspace.dismiss(first.state, {id: "live"});
        verify(Workspace.checkUpdate(closed, Object.assign({}, payload, {revision: 3})).dismissed);
        verify(Workspace.checkUpdate(closed, Object.assign({}, payload, {revision: 3, reopen: true})).state);
        let rejected = false;
        try { Workspace.checkUpdate(first.state, Object.assign({}, payload, {data: {text: "conflict"}})); } catch (e) { rejected = true; }
        verify(rejected);
    }
    function test_unchanged_workspace_panels_keep_identity_and_geometry() {
        const initial = Workspace.apply([], Workspace.initial(), workspacePayload(1, "Brief"));
        initial.items[1].geometry = {x: 0.2, y: 0.3, w: 0.4, h: 0.4};
        const updated = Workspace.apply(initial.items, initial.state, workspacePayload(2, "Changed"));
        verify(updated.items[1] === initial.items[1]);
        compare(updated.items[1].geometry.x, 0.2);
    }
    function workspacePayload(revision, text) {
        return {id: "project", kind: "workspace", title: "Project", expires_seconds: 0,
            data: {revision: revision, reopen: false, panels: [
                {section: "brief", view: {state: {}, layout: {type: "text", text: text}}},
                {section: "tasks", view: {state: {done: false}, layout: {type: "toggle", label: "Check", bind: "done"}}}
            ]}};
    }
    function test_workspace_updates_are_atomic_and_revision_checked() {
        const first = Workspace.apply([], Workspace.initial(), workspacePayload(2, "Current"));
        compare(first.items.length, 2);
        const stale = Workspace.apply(first.items, first.state, workspacePayload(1, "Older"));
        verify(stale.stale); compare(stale.items[0].data.layout.text, "Current");
        let rejected = false;
        try { Workspace.apply(first.items, first.state, workspacePayload(2, "Conflict")); } catch (e) { rejected = true; }
        verify(rejected);
        const invalid = workspacePayload(3, "New"); invalid.data.panels[1].view.layout.bind = "missing";
        rejected = false;
        try { Workspace.apply(first.items, first.state, invalid); } catch (e) { rejected = true; }
        verify(rejected); compare(first.items[0].data.layout.text, "Current");
    }
    function test_workspace_dismissal_survives_updates_clear_and_saved_session() {
        const first = Workspace.apply([], Workspace.initial(), workspacePayload(1, "Current"));
        const hidden = Workspace.dismiss(first.state, first.items[0]);
        const updated = Workspace.apply(first.items.slice(1), hidden, workspacePayload(2, "New"));
        compare(updated.items.length, 1); compare(updated.items[0].section, "tasks");
        const closed = Workspace.clear(updated.state, updated.items, false);
        const saved = Session.encode([], closed, {}, Tasks.initial());
        const restored = Session.decode(saved, Date.now());
        verify(Workspace.apply([], restored.workspaces, workspacePayload(3, "Late")).dismissed);
        const reopen = workspacePayload(4, "Reopened"); reopen.data.reopen = true;
        compare(Workspace.apply([], restored.workspaces, reopen).items.length, 2);
    }
    function test_session_preserves_input_and_rejects_executable_content() {
        const first = Workspace.apply([], Workspace.initial(), workspacePayload(1, "Current"));
        const restored = Session.decode(Session.encode(first.items, first.state, {project__tasks: {done: true}}, Tasks.initial()), Date.now());
        compare(restored.drafts.project__tasks.done, true);
        const bad = JSON.parse(Session.encode(first.items, first.state, {}, Tasks.initial()));
        bad.widgets[0].data.layout.onClicked = "exec()";
        let rejected = false;
        try { Session.decode(JSON.stringify(bad), Date.now()); } catch (e) { rejected = true; }
        verify(rejected);
    }
    function fixture(id, kind, data) {
        return Model.validate({id: id, kind: kind, title: "Example", data: data, expires_seconds: 60});
    }
    function taskEvent(state, revision) {
        return {schema_version: 1, stream_id: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", sequence: revision,
            task_id: "file_task:example", widget_id: "jtask_aaaaaaaaaaaaaaaaaaaaaaaa", source: "file_task",
            revision: revision, generation: 1, state: state, terminal: state === "completed",
            title: "Save notes", message: "Observed task state", updated_at: "2026-11-03T00:00:00Z",
            evidence: {verified: state === "completed", scope: state === "completed" ? "file_step_checks" : "none"},
            progress: {completed: state === "completed" ? 3 : 1, total: 3}};
    }
    function taskBatch(event) { return {schema_version: 1, stream_id: event.stream_id, cursor: event.sequence, events: [event]}; }
    function test_task_card_renders_measured_progress_and_verified_state() {
        const event = taskEvent("completed", 2);
        const result = Tasks.apply([], Tasks.initial(), taskBatch(event), 100);
        const card = createTemporaryObject(cardComponent, test, {widget: result.items[0]});
        verify(card); wait(30);
        const label = findChild(card, "task-state"); verify(label); compare(label.text, "Completed");
        compare(card.widgetData.progress.completed, 3);
        compare(result.items[0].task.task_id, event.task_id);
    }
    function test_task_replay_cannot_overwrite_or_resurrect_a_completed_card() {
        const first = taskEvent("running", 1), last = taskEvent("completed", 2);
        let result = Tasks.apply([], Tasks.initial(), taskBatch(first), 0);
        result = Tasks.apply(result.items, result.state, taskBatch(last), 10);
        result = Tasks.apply(result.items, result.state, taskBatch(first), 20);
        compare(result.items.length, 1); compare(result.items[0].data.label, "Completed");
        const hidden = Tasks.hide(result.state, last.widget_id);
        compare(Tasks.apply([], hidden, taskBatch(last), 30).items.length, 0);
        const resumed = taskEvent("running", 3); resumed.generation = 2;
        compare(Tasks.apply([], hidden, taskBatch(resumed), 40).items.length, 1);
        let rejected = false;
        last.evidence.verified = false;
        try { Tasks.validate(last); } catch (error) { rejected = true; }
        verify(rejected);
    }
    function test_update_preserves_pin_and_identity() {
        let items = Model.upsert([], fixture("one", "text", {text: "First"}));
        items = Model.manage(items, "one", "pin");
        items = Model.upsert(items, fixture("one", "text", {text: "Updated"}));
        compare(items.length, 1); verify(items[0].pinned); compare(items[0].data.text, "Updated");
    }
    function test_expiration_respects_pins_and_interaction() {
        let a = fixture("a", "text", {text: "A"}); a.expiresAt = 1;
        let b = fixture("b", "text", {text: "B"}); b.expiresAt = 1; b.pinned = true;
        let c = fixture("c", "text", {text: "C"}); c.expiresAt = 1;
        let items = Model.prune([a, b, c], 100, ["c"]);
        compare(items.length, 2); compare(items[0].id, "b"); compare(items[1].id, "c");
    }
    function test_remote_media_and_code_rejected() {
        let failed = 0;
        try { fixture("one", "qml", {code: "exit"}); } catch (e) { failed++; }
        try { fixture("two", "image", {source: "https://example.org/a.png"}); } catch (e) { failed++; }
        compare(failed, 2);
    }
    function test_supported_card_renderers_data() {
        return [
            {tag: "text", kind: "text", value: {text: "Real retrieved text"}},
            {tag: "table", kind: "table", value: {columns: ["Release", "Memory"], rows: [["A", "418 MiB"]]}},
            {tag: "chart", kind: "chart", value: {labels: ["A", "B"], values: [418, 462], unit: "MiB"}},
            {tag: "progress", kind: "progress", value: {text: "Reading sources", value: 1, maximum: 3}},
            {tag: "view", kind: "view", value: viewSpec()}
        ];
    }
    function test_supported_card_renderers(row) {
        const card = createTemporaryObject(cardComponent, test, {widget: fixture("example", row.kind, row.value)});
        verify(card); wait(1); verify(card.width > 0); verify(card.visible);
    }

    function choicesSpec() {
        return {
            state: {target_kind: "file", choice_count: 2, selected_index: 0, selected_id: "", selected_value: "", selected_label: ""},
            layout: {
                type: "column",
                children: [
                    {type: "text", text: "Multiple matches found", tone: "muted"},
                    {type: "choice", id: "opt_1", index: 1, label: "<b>notes-final.md</b>", detail: "~/Documents", value: "/home/user/Documents/notes-final.md", prompt: "Select choice 1: /home/user/Documents/notes-final.md"},
                    {type: "choice", id: "opt_2", index: 2, label: "notes-draft.md", detail: "~/Downloads", value: "/home/user/Downloads/notes-draft.md", prompt: "Select choice 2: /home/user/Downloads/notes-draft.md"}
                ]
            }
        };
    }

    function test_disambiguation_choices_support_click_keys_1_to_9_esc_and_plaintext() {
        const spec = Schema.validate(choicesSpec());
        const card = createTemporaryObject(cardComponent, test, {widget: fixture("pick", "view", spec)});
        verify(card); activeCard = card; wait(30);
        const firstChoice = findChild(card, "control-opt_1");
        verify(firstChoice);
        compare(firstChoice.primaryText, "<b>notes-final.md</b>");
        cardSubmitted.clear(); cardDismissed.clear();
        mouseClick(firstChoice);
        compare(cardSubmitted.count, 1);
        compare(cardSubmitted.signalArguments[0][0], "Select choice 1: /home/user/Documents/notes-final.md");
        compare(cardSubmitted.signalArguments[0][1].selected_index, 1);
        compare(cardSubmitted.signalArguments[0][1].selected_value, "/home/user/Documents/notes-final.md");

        card.forceActiveFocus();
        keyClick(Qt.Key_2);
        compare(cardSubmitted.count, 2);
        compare(cardSubmitted.signalArguments[1][0], "Select choice 2: /home/user/Downloads/notes-draft.md");
        compare(cardSubmitted.signalArguments[1][1].selected_index, 2);

        const found = Model.findChoice(spec.layout, 2);
        verify(found); compare(found.id, "opt_2");
        compare(Model.choiceSelectionState(spec.state, found).selected_value, "/home/user/Downloads/notes-draft.md");

        keyClick(Qt.Key_Escape);
        compare(cardDismissed.count, 1);
        activeCard = null;
    }

    function test_digit_key_in_text_input_does_not_trigger_choice() {
        const spec = Schema.validate({
            state: {query: "", selected_index: 0, selected_id: "", selected_value: "", selected_label: ""},
            layout: {type: "column", children: [
                {type: "input", id: "q", label: "Filter", bind: "query"},
                {type: "choice", id: "c1", index: 1, label: "First", prompt: "Select choice 1: First"}
            ]}
        });
        activeView = createTemporaryObject(viewComponent, test, {specification: spec});
        verify(activeView); wait(30);
        const field = findChild(activeView, "control-q"); verify(field);
        submitted.clear();
        field.forceActiveFocus(); keyClick(Qt.Key_1); wait(10);
        compare(submitted.count, 0);
        compare(field.text, "1");
        activeView = null;
    }
}
