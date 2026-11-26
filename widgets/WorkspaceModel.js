.pragma library
.import "WidgetModel.js" as Widgets

var sections = ["brief", "files", "ideas", "plan", "tasks"];
function initial() { return {groups: {}, dismissed: {}, versions: {}}; }
function key(id) { return "id:" + id; }
function validate(payload) {
    if (!payload || payload.kind !== "workspace" || !/^[A-Za-z0-9_-]{1,64}$/.test(payload.id || "") ||
        typeof payload.title !== "string" || payload.title.length > 160 || JSON.stringify(payload).length > 65536)
        throw Error("Invalid workspace identity or size (ID max 64)");
    const data = payload.data;
    if (!data || !Number.isSafeInteger(data.revision) || data.revision < 0 || typeof data.reopen !== "boolean" ||
        !Array.isArray(data.panels) || data.panels.length < 1 || data.panels.length > 5)
        throw Error("Invalid workspace snapshot");
    const seen = new Set();
    return data.panels.map(panel => {
        if (!sections.includes(panel.section) || seen.has(panel.section)) throw Error("Invalid workspace panel");
        seen.add(panel.section);
        const widget = Widgets.validate({id: payload.id + "__" + panel.section, kind: "view",
            title: payload.title, data: panel.view, expires_seconds: payload.expires_seconds ?? 0});
        return Object.assign(widget, {workspace: payload.id, section: panel.section,
            side: ["brief", "files", "ideas"].includes(panel.section) ? "left" : "right"});
    });
}
function prune(items, state) {
    const next = {groups: Object.assign({}, state.groups), dismissed: Object.assign({}, state.dismissed), versions: Object.assign({}, state.versions || {})};
    Object.keys(next.groups).forEach(id => {
        if (items.some(item => key(item.workspace) === id)) return;
        const group = next.groups[id];
        const hasDismissal = sections.some(section => next.dismissed[key(id.slice(3) + "__" + section)]);
        if (!group.revision && !group.closed && !hasDismissal) delete next.groups[id];
        else next.groups[id] = Object.assign({}, group, {digest: ""});
    });
    Object.keys(next.versions).forEach(id => {
        if (!next.versions[id].revision) delete next.versions[id];
        else if (!items.some(item => key(item.id) === id)) next.versions[id] = Object.assign({}, next.versions[id], {digest: ""});
    });
    return next;
}
function dismissalRevision(marker, fallback) {
    return marker && typeof marker === "object" ? marker.revision : fallback || 0;
}
function apply(items, state, payload) {
    state = prune(items, state);
    const panels = validate(payload), id = key(payload.id), old = state.groups[id];
    if ((state.versions || {})[id] || state.dismissed[id] || items.some(item => item.id === payload.id))
        throw Error("This ID belongs to an ordinary widget");
    for (const panel of panels) {
        const marker = state.dismissed[key(panel.id)];
        if ((state.versions || {})[key(panel.id)] || (marker && typeof marker === "object" && !marker.workspace))
            throw Error("Workspace panel ID belongs to an ordinary widget");
    }
    const version = payload.data.revision;
    const digest = JSON.stringify(payload.data.panels);
    if (old && old.revision && version < old.revision) return {items: items, state: state, stale: true};
    if (old && old.closed && (!payload.data.reopen || version <= old.revision))
        return {items: items, state: state, dismissed: true};
    if (old && version && version === old.revision && old.digest && digest !== old.digest)
        throw Error("Workspace revision conflict; increment revision for changed content");
    if (old && old.revision && version === old.revision && !old.digest && !payload.data.reopen)
        return {items: items, state: state, stale: true};
    const next = {groups: Object.assign({}, state.groups), dismissed: Object.assign({}, state.dismissed), versions: state.versions || {}};
    next.groups[id] = {revision: version || (old ? old.revision : 0), digest: digest, closed: false};
    if (payload.data.reopen) panels.forEach(p => {
        const marker = next.dismissed[key(p.id)];
        if (marker && version > dismissalRevision(marker, old?.revision)) delete next.dismissed[key(p.id)];
    });
    const remaining = items.filter(item => item.workspace !== payload.id);
    const incoming = panels.filter(panel => !next.dismissed[key(panel.id)]).map(panel => {
        const before = items.find(item => item.id === panel.id);
        if (before && before.workspace !== payload.id) throw Error("Workspace widget identity collision");
        if (before && JSON.stringify(before.data) === JSON.stringify(panel.data))
            return before.title === panel.title ? before : Object.assign({}, before, {title: panel.title});
        if (before) { panel.pinned = before.pinned; panel.expiresAt = before.expiresAt; panel.geometry = before.geometry; }
        return panel;
    });
    if (remaining.some(item => incoming.some(panel => panel.id === item.id))) throw Error("Workspace identity collision");
    if (remaining.length + incoming.length > 24) throw Error("Close a workspace before adding more");
    return {items: remaining.concat(incoming), state: next, stale: false};
}
function dismiss(state, widget) {
    if (widget.task) return state;
    const revision = widget.workspace ? state.groups[key(widget.workspace)]?.revision || 0 : (state.versions || {})[key(widget.id)]?.revision || 0;
    return {groups: state.groups, versions: state.versions || {}, dismissed: Object.assign({}, state.dismissed,
        {[key(widget.id)]: {revision: revision, workspace: widget.workspace || ""}})};
}
function clear(state, items, keepPinned) {
    let next = {groups: Object.assign({}, state.groups), dismissed: Object.assign({}, state.dismissed), versions: state.versions || {}};
    items.forEach(item => { if (!keepPinned || !item.pinned) next = dismiss(next, item); });
    Object.keys(next.groups).forEach(id => {
        const retained = keepPinned && items.some(item => key(item.workspace) === id && item.pinned);
        if (!retained) next.groups[id] = Object.assign({}, next.groups[id], {closed: true});
    });
    return next;
}

function checkUpdate(state, payload) {
    Widgets.validate(payload);
    const revision = payload.revision === undefined ? 0 : payload.revision;
    if (!Number.isSafeInteger(revision) || revision < 0 || (payload.reopen !== undefined && typeof payload.reopen !== "boolean"))
        throw Error("Invalid widget revision or reopen flag");
    const k = key(payload.id), previous = (state.versions || {})[k];
    if (state.groups[k] || Object.keys(state.groups).some(id => sections.some(section => payload.id === id.slice(3) + "__" + section)))
        throw Error("This ID belongs to a workspace");
    const digest = JSON.stringify([payload.kind, payload.title, payload.data]);
    if (previous && previous.revision && revision < previous.revision) return {stale: true};
    if (state.dismissed[k] && (!payload.reopen || revision <= dismissalRevision(state.dismissed[k], previous?.revision))) return {dismissed: true};
    if (previous && revision && revision === previous.revision && previous.digest && digest !== previous.digest)
        throw Error("Widget revision conflict; increment revision for changed content");
    if (previous && revision && revision === previous.revision && !previous.digest && !payload.reopen) return {stale: true};
    const versions = Object.assign({}, state.versions || {});
    if (revision) versions[k] = {revision: revision, digest: digest};
    else delete versions[k];
    const dismissed = Object.assign({}, state.dismissed);
    delete dismissed[k];
    return {state: {groups: state.groups, dismissed: dismissed, versions: versions}};
}
