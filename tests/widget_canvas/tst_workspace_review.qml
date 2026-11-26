import QtQuick
import QtTest
import "../../widgets/WorkspaceModel.js" as Workspace
import "../../widgets/SessionModel.js" as Session
import "../../widgets/TaskEvents.js" as Tasks

TestCase {
    name: "WorkspaceReviewRegressions"
    function payload(id, revision, section) {
        return {id: id, kind: "workspace", title: "Project", data: {revision: revision, reopen: false,
            panels: [{section: section, view: {state: {}, layout: {type: "text", text: "Content"}}}]}};
    }
    function test_previous_session_digest_migrates_without_conflict() {
        const input = payload("project", 1, "files");
        const first = Workspace.apply([], Workspace.initial(), input);
        first.state.groups[Workspace.key("project")].digest = JSON.stringify(input.data.panels);
        const restored = Session.decode(Session.encode(first.items, first.state, {}, Tasks.initial()), Date.now());
        compare(Workspace.apply(restored.widgets, restored.workspaces, input).items.length, 1);
    }
    function test_group_names_cannot_alias_generated_panel_names() {
        const first = Workspace.apply([], Workspace.initial(), payload("project__files", 1, "brief"));
        let rejected = false;
        try { Workspace.apply(first.items, first.state, payload("project", 1, "files")); } catch(e) { rejected = true; }
        verify(rejected);
        const reverse = Workspace.apply([], Workspace.initial(), payload("project", 1, "files"));
        rejected = false;
        try { Workspace.apply(reverse.items, reverse.state, payload("project__files", 1, "brief")); } catch(e) { rejected = true; }
        verify(rejected);
    }
    function test_compact_fence_requires_new_revision_even_for_reopen() {
        const card = {id: "normal", kind: "text", title: "Text", data: {text: "Original"}, revision: 1};
        const state = Workspace.prune([], Workspace.checkUpdate(Workspace.initial(), card).state);
        verify(Workspace.checkUpdate(state, Object.assign({}, card, {reopen: true, data: {text: "Changed"}})).stale);
        const initial = Workspace.apply([], Workspace.initial(), payload("project", 1, "files"));
        const retry = payload("project", 1, "files"); retry.data.reopen = true;
        verify(Workspace.apply([], Workspace.prune([], initial.state), retry).stale);
    }
    function test_title_is_part_of_workspace_revision() {
        const first = Workspace.apply([], Workspace.initial(), payload("project", 1, "files"));
        const next = payload("project", 1, "files"); next.title = "Changed";
        let rejected = false;
        try { Workspace.apply(first.items, first.state, next); } catch(e) { rejected = true; }
        verify(rejected);
    }
}
