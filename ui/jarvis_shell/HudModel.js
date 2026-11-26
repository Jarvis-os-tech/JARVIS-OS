.pragma library

function voicePresentation(snapshot, now) {
    const written = Number(snapshot.status_written_at) * 1000;
    if (!Number.isFinite(written) || Math.abs(now - written) > 5000)
        return {state: "offline", muted: false, energy: 0};
    const state = snapshot.state;
    const known = ["idle", "standby", "connecting", "listening", "thinking", "speaking",
        "muted", "microphone_muted", "microphone_silent"].includes(state);
    const muted = snapshot.muted === true || state === "muted" || state === "microphone_muted";
    return {
        state: known ? state : "offline",
        muted: muted,
        energy: !known || muted ? 0 : Math.max(0, Math.min(1, (Number(snapshot.microphone_rms) || 0) * 25))
    };
}

function reconcile(entries, widgets, now) {
    if (widgets.length > 24) throw Error("Close a card before adding more");
    const previous = new Map(entries.map(entry => [entry.id, entry]));
    const incoming = new Map(widgets.map(widget => [widget.id, widget]));
    const order = entries.filter(entry => incoming.has(entry.id)).map(entry => entry.id)
        .concat(widgets.filter(widget => !previous.has(widget.id)).map(widget => widget.id));
    return place(order.map(id => {
        const widget = incoming.get(id);
        const before = previous.get(id);
        const side = widget.side === "left" || widget.side === "right" ? widget.side
            : widget.kind === "task" || widget.kind === "progress" ? "left" : "right";
        const newLifetime = !before || before.sourceExpiresAt !== widget.expiresAt;
        return Object.assign({}, widget, {
            side: side,
            mounted: !!before && before.mounted && before.side === side,
            collapsed: !!before && before.collapsed,
            interacting: !!before && before.interacting && before.side === side,
            sourceExpiresAt: widget.expiresAt,
            expiresAt: newLifetime ? widget.expiresAt || 0 : before.expiresAt,
            pausedAt: newLifetime ? null : before.pausedAt
        });
    }), now);
}

function place(entries, now) {
    const remaining = {left: 3, right: 2};
    const mounted = new Set();
    entries.forEach(entry => {
        if (!entry.collapsed && entry.mounted && entry.pinned) {
            mounted.add(entry.id);
            remaining[entry.side]--;
        }
    });
    for (let index = entries.length - 1; index >= 0; index--) {
        const entry = entries[index];
        if (!entry.collapsed && !mounted.has(entry.id) && remaining[entry.side] > 0) {
            mounted.add(entry.id);
            remaining[entry.side]--;
        }
    }
    return entries.map(entry => {
        const visible = mounted.has(entry.id);
        return setClock(Object.assign({}, entry, {mounted: visible, interacting: visible && entry.interacting}), now);
    });
}

function setClock(entry, now) {
    if (!entry.expiresAt) {
        entry.pausedAt = null;
    } else if (!entry.mounted || entry.pinned || entry.interacting) {
        if (entry.pausedAt === null) entry.pausedAt = now;
    } else if (entry.pausedAt !== null) {
        entry.expiresAt += Math.max(0, now - entry.pausedAt);
        entry.pausedAt = null;
    }
    return entry;
}

function manage(entries, id, action, now) {
    const index = entries.findIndex(entry => entry.id === id);
    if (index < 0) throw Error("Widget not found");
    const next = entries.slice();
    if (action === "collapse") {
        next[index] = Object.assign({}, next[index], {collapsed: true});
    } else if (action === "restore") {
        const entry = next.splice(index, 1)[0];
        next.push(Object.assign({}, entry, {collapsed: false}));
    } else {
        throw Error("Unknown HUD action");
    }
    return place(next, now);
}

function interact(entries, id, active, now) {
    return entries.map(entry => entry.id === id && entry.mounted && entry.interacting !== active
        ? setClock(Object.assign({}, entry, {interacting: active}), now) : entry);
}

function expired(entries, now) {
    return entries.filter(entry => entry.expiresAt && entry.pausedAt === null && entry.expiresAt <= now)
        .map(entry => entry.id);
}

function deadline(entries) {
    const deadlines = entries.filter(entry => entry.expiresAt && entry.pausedAt === null)
        .map(entry => entry.expiresAt);
    return deadlines.length ? Math.min.apply(null, deadlines) : 0;
}

function draftChanges(defaults, values) {
    const changes = Object.create(null);
    for (const key of Object.keys(defaults)) {
        if (Object.prototype.hasOwnProperty.call(values, key) && values[key] !== defaults[key])
            changes[key] = values[key];
    }
    return changes;
}

function restoreDraft(defaults, changes) {
    const state = Object.assign({}, defaults);
    for (const key of Object.keys(state)) {
        if (Object.prototype.hasOwnProperty.call(changes, key) &&
            typeof changes[key] === typeof state[key]) state[key] = changes[key];
    }
    return state;
}

function reactorPlacement(width, height, occupied, previous) {
    const large = Math.floor(Math.min(width * 0.63, height * 0.60, 440));
    if (!occupied.length) {
        return {corner: "", size: large, x: (width - large) / 2, y: (height - large) / 2};
    }

    const margin = 20;
    const size = Math.max(0, Math.floor(Math.min(large * 0.36, width - margin * 2, height - margin * 2)));
    const corners = [
        {corner: "bottom-right", size, x: width - size - margin, y: height - size - margin},
        {corner: "bottom-left", size, x: margin, y: height - size - margin},
        {corner: "top-right", size, x: width - size - margin, y: margin},
        {corner: "top-left", size, x: margin, y: margin}
    ];
    const free = corners.filter(candidate => !occupied.some(rect =>
        candidate.x < rect.x + rect.width + 8 && candidate.x + size + 8 > rect.x &&
        candidate.y < rect.y + rect.height + 8 && candidate.y + size + 8 > rect.y));
    return free.find(candidate => candidate.corner === previous) || free[0] ||
        {corner: "", size: 0, x: width / 2, y: height / 2};
}
