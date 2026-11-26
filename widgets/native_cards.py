"""Translate native-shell card data into the existing declarative QML views."""
import hashlib

try:
    from .view_schema import KEY, number, string, validate_view
except ImportError:
    from view_schema import KEY, number, string, validate_view


def objects(value, limit, fields):
    if not isinstance(value, list) or not 1 <= len(value) <= limit:
        raise ValueError(f"Expected 1–{limit} items")
    for item in value:
        if not isinstance(item, dict) or set(item) - fields:
            raise ValueError("Unexpected card item fields")
    return value


def view(kind, data):
    state, children = {}, []
    if kind == "workspace":
        for key, label in (("brief", "Brief"), ("files", "Files"), ("ideas", "Ideas"),
                           ("plan", "Plan"), ("tasks", "Next steps")):
            if key not in data:
                continue
            rows = []
            values = data[key] if isinstance(data[key], list) else [data[key]]
            if len(values) > 64:
                raise ValueError("Use at most 64 entries per workspace section")
            for value in values:
                if isinstance(value, dict):
                    caption = next((value[k] for k in ("label", "text", "title", "name", "path", "description")
                                    if isinstance(value.get(k), str) and value[k].strip()), None)
                else:
                    caption = value
                caption = string(caption, 160 if key == "tasks" else 2000)
                if key != "tasks":
                    rows.append({"type": "text", "text": caption})
                    continue
                task = value if isinstance(value, dict) else {}
                raw_id = str(task.get("id", caption))
                ident = raw_id if KEY.fullmatch(raw_id) else "task_" + hashlib.sha256(raw_id.encode()).hexdigest()[:20]
                base = ident
                suffix = 1
                while ident in state:
                    suffix += 1
                    ident = base[:40] + "_" + str(suffix)
                done = task.get("done", False)
                if isinstance(done, str) and done.lower() in ("true", "false"):
                    done = done.lower() == "true"
                if type(done) is not bool:
                    raise ValueError("Task done must be true or false")
                state[ident] = done
                rows.append({"type": "toggle", "bind": ident, "label": caption})
            if key == "tasks" and rows:
                rows.append({"type": "button", "label": "Apply changes", "prompt": "Apply these task selections"})
            if rows:
                children.append({"type": "heading", "text": label})
                for offset in range(0, len(rows), 12):
                    children.append({"type": "column", "children": rows[offset:offset + 12]})
    elif kind == "metric":
        value = data.get("value")
        number(value)
        children.append({"type": "metric", "label": string(data.get("detail", ""), 160),
                         "value": str(value) + string(data.get("unit", ""), 40)})
    elif kind == "list":
        for item in objects(data.get("items"), 15, {"id", "label", "detail", "done"}):
            identity = string(item.get("id", item.get("label")), 160)
            key = "item_" + hashlib.sha256(identity.encode()).hexdigest()[:20]
            if key in state:
                raise ValueError("Checklist items need unique IDs or distinct labels")
            done = item.get("done", False)
            if type(done) is not bool:
                raise ValueError("Checklist done must be boolean")
            state[key] = done
            children.append({"type": "toggle", "label": string(item.get("label"), 160), "bind": key})
            if item.get("detail"):
                children.append({"type": "text", "text": string(item["detail"]), "tone": "muted"})
        children.append({"type": "button", "label": "Apply", "prompt": "Apply these checklist selections"})
    elif kind == "actions":
        seen = set()
        for item in objects(data.get("buttons"), 16, {"id", "label"}):
            key = string(item.get("id"), 48)
            if not KEY.fullmatch(key) or key in seen:
                raise ValueError("Action IDs must be unique short identifiers")
            seen.add(key)
            children.append({"type": "button", "id": key, "label": string(item.get("label"), 160),
                             "prompt": key})
    elif kind == "form":
        for item in objects(data.get("fields"), 16, {"id", "label", "placeholder", "required"}):
            key = string(item.get("id"), 48)
            if not KEY.fullmatch(key) or key in state:
                raise ValueError("Form IDs must be unique short identifiers")
            required = item.get("required", False)
            if type(required) is not bool:
                raise ValueError("Required must be boolean")
            state[key] = ""
            children.append({"type": "input", "bind": key, "label": string(item.get("label"), 160),
                             "placeholder": string(item.get("placeholder", "")), "required": required})
        label = string(data.get("submit", "Submit"), 160)
        children.append({"type": "button", "label": label, "prompt": label})
    elif kind == "choices":
        prompt_text = string(data.get("prompt", ""), 300)
        target_kind = string(data.get("target_kind", "generic"), 40) or "generic"
        cancel_label = string(data.get("cancel_label", ""), 40)
        items = objects(data.get("items"), 9, {"id", "label", "detail", "value", "prompt"})
        state.update({
            "target_kind": target_kind,
            "choice_count": len(items),
            "selected_index": 0,
            "selected_id": "",
            "selected_value": "",
            "selected_label": "",
        })
        if prompt_text.strip():
            children.append({"type": "text", "text": prompt_text, "tone": "muted"})
        seen = set()
        for idx, item in enumerate(items, start=1):
            label = string(item.get("label"), 160)
            if not label.strip():
                raise ValueError("Choice label cannot be blank")
            detail = string(item.get("detail", ""), 300)
            value = string(item.get("value", label), 500)
            key = string(item.get("id", f"choice_{idx}"), 48)
            if not KEY.fullmatch(key) or key in seen:
                raise ValueError("Choice IDs must be unique short identifiers")
            seen.add(key)
            item_prompt = string(item.get("prompt", f"Select choice {idx}: {value}"), 500)
            if not item_prompt.strip():
                raise ValueError("Choice prompt cannot be blank")
            node = {"type": "choice", "id": key, "index": idx, "label": label, "value": value, "prompt": item_prompt}
            if detail:
                node["detail"] = detail
            children.append(node)
        hint = f"Say 1–{len(items)} or press 1–{len(items)}"
        hint += f" · Esc: {cancel_label.strip()}" if cancel_label.strip() else " · Esc to cancel"
        children.append({"type": "text", "text": hint, "tone": "muted"})
    else:
        raise ValueError("Unsupported native card")
    return validate_view({"state": state, "layout": {"type": "column", "children": children}})


def line_chart(data):
    labels, values = data["labels"], data["values"]
    for value in values:
        number(value)
    lo, hi = min(values), max(values)
    span = hi - lo or 1
    positions = [(80 + i * 840 / max(1, len(values) - 1), 850 - (value - lo) / span * 700)
                 for i, value in enumerate(values)]
    shapes = [{"type": "line", "x": 80, "y": 850, "x2": 920, "y2": 850, "stroke": "#8AA4C2"}]
    for i, (x, y) in enumerate(positions):
        shapes.append({"type": "circle", "x": x, "y": y, "r": 9, "fill": "#00E5FF"})
        if i:
            px, py = positions[i - 1]
            shapes.append({"type": "line", "x": px, "y": py, "x2": x, "y2": y,
                           "stroke": "#00E5FF", "width": 2})
    children = [{"type": "canvas", "height": 220, "shapes": shapes}]
    children.extend({"type": "text", "text": f"{label}: {value} {data.get('unit', '')}"}
                    for label, value in zip(labels, values))
    return validate_view({"layout": {"type": "column", "children": children}})
