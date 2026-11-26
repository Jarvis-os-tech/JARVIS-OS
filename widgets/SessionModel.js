.pragma library
.import "WidgetModel.js" as Widgets
.import "WorkspaceModel.js" as Workspaces
.import "TaskEvents.js" as Tasks

function decode(text, now) {
    if (text.length > 16777216) throw Error("Saved widget session exceeds limit");
    const s = JSON.parse(text);
    if (!s || s.version !== 1 || !Array.isArray(s.widgets) || s.widgets.length > 24 ||
        !s.workspaces || !s.workspaces.groups || !s.workspaces.dismissed ||
        !s.drafts || typeof s.drafts !== "object") throw Error("Invalid saved widget session");
    for (const records of [s.workspaces.groups, s.workspaces.dismissed, s.workspaces.versions ?? {}]) {
        if (typeof records !== "object" || Array.isArray(records)) throw Error("Invalid saved widget records");
    }
    Object.values(s.workspaces.dismissed).forEach(record => {
        if (typeof record === "boolean") return;
        if (!record || !Number.isSafeInteger(record.revision) || record.revision < 0 ||
            typeof record.workspace !== "string" || !/^[A-Za-z0-9_-]{0,64}$/.test(record.workspace))
            throw Error("Invalid saved widget dismissal");
    });
    Object.values(s.workspaces.versions || {}).forEach(record => {
        if (!Number.isSafeInteger(record.revision) || record.revision < 0 || typeof record.digest !== "string") throw Error("Invalid saved revision");
    });
    Object.values(s.workspaces.groups).forEach(group => {
        if (!Number.isSafeInteger(group.revision) || group.revision < 0 || typeof group.digest !== "string" || typeof group.closed !== "boolean")
            throw Error("Invalid workspace revision record");
    });
    for (const id of Object.keys(s.workspaces.groups)) {
        const group = s.workspaces.groups[id];
        if (!group.digest) continue;
        const digest = JSON.parse(group.digest);
        if (Array.isArray(digest) && digest.length && digest.every(panel => panel && typeof panel.section === "string")) {
            const panel = s.widgets.find(item => item.workspace === id.slice(3));
            group.digest = panel ? JSON.stringify([panel.title, digest]) : "";
        }
    }
    const tasks = Tasks.initial();
    if (s.tasks && typeof s.tasks.stream_id === "string" && /^[a-f0-9]{32}$/.test(s.tasks.stream_id) &&
        Number.isSafeInteger(s.tasks.cursor) && s.tasks.cursor >= 0 && s.tasks.hidden && Object.keys(s.tasks.hidden).length <= 256) {
        tasks.stream_id = s.tasks.stream_id; tasks.cursor = s.tasks.cursor;
        for (const id of Object.keys(s.tasks.hidden)) {
            if (!/^jtask_[a-f0-9]+$/.test(id) || !Number.isSafeInteger(s.tasks.hidden[id]) || s.tasks.hidden[id] < 1)
                throw Error("Invalid saved task dismissal");
        }
        tasks.hidden = s.tasks.hidden;
    }
    const events = s.widgets.filter(item => item?.kind === "task").map(item => item.task);
    const restored = events.length ? Tasks.apply([], Object.assign(Tasks.initial(), {hidden: tasks.hidden}), {
        schema_version: 1, stream_id: tasks.stream_id, cursor: tasks.cursor, events: events
    }, now) : {items: [], state: tasks};
    tasks.revisions = restored.state.revisions;
    if (s.tasks?.revisions !== undefined) {
        const revisions = s.tasks.revisions;
        if (!revisions || typeof revisions !== "object" || Array.isArray(revisions) || Object.keys(revisions).length > 256)
            throw Error("Invalid saved task revisions");
        for (const [id, record] of Object.entries(revisions)) {
            if (!/^[A-Za-z0-9_:-]{1,160}$/.test(id) || !record || !/^jtask_[a-f0-9]{24}$/.test(record.widget_id) ||
                ![record.revision, record.generation, record.sequence].every(n => Number.isSafeInteger(n) && n > 0) ||
                record.sequence > tasks.cursor || typeof record.terminal !== "boolean")
                throw Error("Invalid saved task revision");
        }
        const retained = Object.entries(revisions).filter(([id]) => !Object.prototype.hasOwnProperty.call(tasks.revisions, id));
        retained.sort((a, b) => b[1].sequence - a[1].sequence);
        for (const [id, record] of retained.slice(0, 256 - Object.keys(tasks.revisions).length))
            Object.defineProperty(tasks.revisions, id, {value: record, enumerable: true, configurable: true, writable: true});
    }
    const ids = new Set();
    const widgets = s.widgets.map(item => {
        const clean = item?.kind === "task" ? restored.items.find(widget => widget.id === item.id && widget.task === item.task)
            : Widgets.validate(Object.assign({}, item, {expires_seconds: 0}));
        if (!clean) throw Error("Invalid saved task widget");
        if (ids.has(clean.id)) throw Error("Duplicate saved widget");
        ids.add(clean.id);
        if (item.workspace && (!/^[A-Za-z0-9_-]{1,64}$/.test(item.workspace) ||
            !Workspaces.sections.includes(item.section) || item.id !== item.workspace + "__" + item.section))
            throw Error("Invalid saved workspace panel");
        if (!Number.isFinite(item.expiresAt) || item.expiresAt < 0) throw Error("Invalid saved expiry");
        if (item.geometry && (!Object.values(item.geometry).every(n => typeof n === "number" && Number.isFinite(n) && n >= 0 && n <= 1) ||
            !(item.geometry.w > 0) || !(item.geometry.h > 0))) throw Error("Invalid saved geometry");
        return Object.assign(clean, {geometry: item.geometry, workspace: item.workspace, section: item.section,
            side: item.side === "left" || (clean.kind === "task" && item.side !== "right") ? "left" : "right",
            pinned: item.pinned === true, expiresAt: item.expiresAt});
    }).filter(item => item.pinned || !item.expiresAt || item.expiresAt > now);
    // Drafts are checked against each view's existing state contract before restoration.
    const drafts = {};
    widgets.filter(item => item.kind === "view").forEach(item => {
        const values = s.drafts[item.id] || {};
        if (!values || typeof values !== "object" || Array.isArray(values)) throw Error("Invalid saved draft");
        drafts[item.id] = Widgets.compatibleDraft(item.data, values);
    });
    return {widgets: widgets, workspaces: s.workspaces, drafts: drafts, tasks: tasks};
}
function encode(widgets, workspaces, drafts, tasks) {
    return JSON.stringify({version: 1, widgets: widgets.filter(item => Widgets.kinds.includes(item.kind) || item.kind === "task"),
        workspaces: workspaces, drafts: drafts,
        tasks: {stream_id: tasks.stream_id, cursor: tasks.cursor, hidden: tasks.hidden, revisions: tasks.revisions}});
}
