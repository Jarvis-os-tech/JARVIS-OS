import QtTest
import "../../ui/jarvis_shell"
import "../../ui/jarvis_shell/style"
import "../../ui/jarvis_shell/HudModel.js" as Hud

TestCase {
    name: "HudModel"
    when: windowShown

    ArcReactorCore { id: reactor; width: 120; height: 120; visible: true }

    function test_style_duration_and_reactor_idle_gating() {
        Style.reduceMotion = false;
        compare(Style.duration(220), 220);
        compare(Style.duration(700), 300);
        Style.reduceMotion = true;
        compare(Style.duration(220), 0);
        Style.reduceMotion = false;

        reactor.muted = false;
        reactor.voiceState = "idle";
        verify(reactor.active);
        verify(!reactor.animating);
        reactor.voiceState = "listening";
        verify(reactor.animating);
        reactor.voiceState = "standby";
        verify(!reactor.active);
        verify(!reactor.animating);
    }

    function test_live_voice_status_expires_and_recovers() {
        const snapshot = {status_written_at: 100, state: "connecting", microphone_rms: 0.02};
        compare(Hud.voicePresentation(snapshot, 100000).state, "connecting");
        compare(Hud.voicePresentation(snapshot, 106000), {state: "offline", muted: false, energy: 0});
        snapshot.status_written_at = 106;
        snapshot.state = "microphone_muted";
        compare(Hud.voicePresentation(snapshot, 106100), {state: "microphone_muted", muted: true, energy: 0});
        snapshot.state = "listening";
        compare(Hud.voicePresentation(snapshot, 106200), {state: "listening", muted: false, energy: 0.5});
    }

    function test_reactor_docks_and_holds_a_free_corner() {
        const rightApp = {x: 600, y: 0, width: 600, height: 800};
        const leftCard = {x: 0, y: 0, width: 300, height: 240};
        const idle = Hud.reactorPlacement(1200, 800, [], "");
        compare(idle, {corner: "", size: 440, x: 380, y: 180});

        const active = Hud.reactorPlacement(1200, 800, [rightApp, leftCard], "");
        compare(active.corner, "bottom-left");
        verify(active.size < idle.size);
        compare(Hud.reactorPlacement(1200, 800, [leftCard], active.corner).corner, "bottom-left");

        const fullscreen = {x: 0, y: 0, width: 1200, height: 800};
        compare(Hud.reactorPlacement(1200, 800, [fullscreen], active.corner).size, 0);
        compare(Hud.reactorPlacement(1200, 800, [], active.corner), idle);
    }

    function widget(id, side, pinned, expiresAt) {
        return {id: id, side: side, pinned: pinned, expiresAt: expiresAt, kind: "text", data: {text: id}};
    }

    function test_room_capacity_and_pinned_overflow() {
        let widgets = [widget("l1", "left", true), widget("l2", "left", true), widget("l3", "left", true),
            widget("r1", "right", true), widget("r2", "right", true)];
        let entries = Hud.reconcile([], widgets, 0);
        widgets.push(widget("left queued", "left", false), widget("right queued", "right", false));
        entries = Hud.reconcile(entries, widgets, 1);
        compare(entries.filter(entry => entry.mounted).map(entry => entry.id), ["l1", "l2", "l3", "r1", "r2"]);
        entries = Hud.manage(entries, "right queued", "restore", 2);
        verify(!entries.find(entry => entry.id === "right queued").mounted);
        entries = Hud.reconcile(entries, widgets.filter(entry => entry.id !== "r1"), 3);
        verify(entries.find(entry => entry.id === "right queued").mounted);
        compare(entries.filter(entry => entry.mounted).length, 5);
    }

    function test_restore_same_record_with_latest_payload() {
        let form = widget("form", "right", false, 100);
        let entries = Hud.reconcile([], [form], 0);
        entries = Hud.manage(entries, "form", "collapse", 20);
        verify(!entries[0].mounted);
        compare(Hud.deadline(entries), 0);

        form = Object.assign({}, form, {data: {text: "Updated body"}});
        const widgets = [form, widget("right 1", "right", false), widget("right 2", "right", false)];
        entries = Hud.reconcile(entries, widgets, 110);
        entries = Hud.manage(entries, "form", "restore", 120);
        verify(entries.find(entry => entry.id === "form").mounted);
        compare(entries.find(entry => entry.id === "form").data.text, "Updated body");
        verify(!entries.find(entry => entry.id === "right 1").mounted);
        compare(Hud.deadline(entries), 200);
        compare(Hud.expired(entries, 200), ["form"]);
    }

    function test_hover_focus_pauses_remaining_lifetime() {
        const form = widget("form", "right", false, 100);
        let entries = Hud.reconcile([], [form], 0);
        entries = Hud.interact(entries, "form", true, 0);
        entries = Hud.interact(entries, "form", true, 10);
        compare(Hud.deadline(entries), 0);
        compare(Hud.expired(entries, 500), []);
        entries = Hud.interact(entries, "form", false, 500);
        compare(Hud.deadline(entries), 600);
        entries = Hud.reconcile(entries, [form], 550);
        compare(Hud.expired(entries, 599), []);
        compare(Hud.expired(entries, 600), ["form"]);
    }

    function test_overflow_keeps_lifetime_without_mounting() {
        const pinned = [widget("r1", "right", true, 100), widget("r2", "right", true, 100)];
        const queued = widget("queued", "right", false, 110);
        let entries = Hud.reconcile(Hud.reconcile([], pinned, 0), pinned.concat(queued), 10);
        compare(Hud.deadline(entries), 0);
        entries = Hud.reconcile(entries, [pinned[0], queued], 500);
        compare(Hud.deadline(entries), 600);
        compare(Hud.expired(entries, 600), ["queued"]);
    }

    function test_restore_only_edited_compatible_fields() {
        const edits = Hud.draftChanges({label: "Initial", count: 2, mode: "A"},
                                      {label: "Edited", count: 2, mode: "B"});
        compare(Hud.restoreDraft({label: "Server", count: 5, mode: 1}, edits),
                {label: "Edited", count: 5, mode: 1});
    }

    function test_storage_cap_keeps_retained_entries() {
        const widgets = Array.from({length: 24}, (_, index) => widget("widget-" + index, "right", false));
        const entries = Hud.reconcile([], widgets, 0);
        compare(entries.length, 24);
        compare(entries.filter(entry => entry.mounted).length, 2);
        let capacityError = false;
        try {
            Hud.reconcile(entries, widgets.concat(widget("extra", "right", false)), 1);
        } catch (error) {
            capacityError = true;
        }
        verify(capacityError);
        compare(entries.length, 24);
    }
}
