.pragma library

function initial() { return {state: "offline", tools: 0, completeUntil: 0, level: 0, gesture: ""}; }
function update(previous, payload, now) {
    if (!payload || typeof payload !== "object" || typeof payload.state !== "string") return initial();
    var raw = payload.state.toLowerCase();
    var tools = Number(payload.tools_in_flight);
    tools = isFinite(tools) ? Math.max(0, tools) : 0;
    var alerts = Array.isArray(payload.recent_alerts) ? payload.recent_alerts : [];
    var alert = alerts.some(function(a) {
        if (!a || typeof a !== "object") return false;
        var age = now / 1000 - Number(a.timestamp);
        return (a.priority === "critical" || a.priority === "alert") && age >= 0 && age < 6;
    });
    var state = payload.standby ? "standby" : payload.muted ? "disabled"
        : alert || raw === "error" || raw === "alert" ? "alert"
        : raw === "offline" ? "offline"
        : tools > 0 || raw === "thinking" || raw === "processing" ? "thinking"
        : raw === "ducked" || raw === "barged_in" ? "listening" : raw;
    var until = previous.completeUntil || 0;
    if (previous.tools > 0 && tools === 0 && state !== "alert" && state !== "offline") until = now + 900;
    if (state === "idle" && until > now) state = "complete";
    var gesture = state === previous.state ? "" : state === "listening" ? "nod"
        : state === "complete" ? "roll" : state === "alert" ? "recoil" : "";
    var level = Number(payload.microphone_rms) || 0;
    return {state: state, tools: tools, completeUntil: until,
        level: Math.max(0, Math.min(1, level * 25)), gesture: gesture};
}
