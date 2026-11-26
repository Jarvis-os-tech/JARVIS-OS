import QtQuick
import QtTest
import "../../ui/omarchy-ai.orbit/OrbitState.js" as State
import "../../ui/omarchy-ai.orbit"
TestCase {
    name: "OrbitReactions"
    when: windowShown
    width: 120; height: 120
    AuraFieldOrbit { id: aura; width: 100; height: 100 }
    function test_malformed_alerts_do_not_break_reactions() {
        const value = State.update(State.initial(), {state: "listening", tools_in_flight: "Infinity", recent_alerts: [null, "invalid"]}, 1000);
        compare(value.state, "listening"); compare(value.tools, 0);
    }
    function test_reactions() {
        var value = State.update(State.initial(), {state: "listening"}, 10000);
        compare(value.gesture, "nod");
        value = State.update(value, {state: "listening", tools_in_flight: 2}, 10200);
        compare(value.state, "thinking");
        value = State.update(value, {state: "idle", tools_in_flight: 0}, 10400);
        compare(value.state, "complete"); compare(value.gesture, "roll");
        value = State.update(value, {state: "idle"}, 10600);
        compare(value.gesture, ""); compare(value.state, "complete");
        value = State.update(value, {state: "idle"}, 12000);
        compare(value.state, "idle");
        value = State.update(value, {state: "error"}, 12200);
        compare(value.state, "alert"); compare(value.gesture, "recoil");
        aura.orbitState = value.state; wait(30);
        compare(aura.colorA, "#fb7185");
    }
    function test_offline_privacy_and_levels() {
        compare(State.update(State.initial(), {}, 1000).state, "offline");
        compare(State.update(State.initial(), {state: "speaking", standby: true}, 1000).state, "standby");
        compare(State.update(State.initial(), {state: "listening", muted: true}, 1000).state, "disabled");
        compare(State.update(State.initial(), {state: "listening", microphone_rms: -1}, 1000).level, 0);
        compare(State.update(State.initial(), {state: "listening", microphone_rms: 2}, 1000).level, 1);
        compare(State.update(State.initial(), {state: "idle", recent_alerts: [{priority: "critical", timestamp: 8}]}, 10000).state, "alert");
    }
}
