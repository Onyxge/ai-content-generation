"""JSON Patch over an id-keyed view of the storyboard (ADR-018).

Agents address shots, characters, references and music cues by id, never by array index:
`/shots/s04/image_prompt`, not `/shots/3/image_prompt`. Ids don't shift when a shot is
added or removed, so a proposal still means the same thing after another one lands, and an
LLM can't miscount its way into editing the wrong shot.

In the keyed view each collection is an object of items keyed by id, plus `@order`, the
list of ids in film order (ids can't start with `@`, so it never collides). Patches use the
RFC 6902 operations add, remove, replace and test on that view. `diff()` compares two
views leaf by leaf, which is what the ownership check and `film revert` work from."""
from __future__ import annotations

import copy
from typing import Any

COLLECTIONS = ("/shots", "/characters", "/references", "/music/cues")
ORDER = "@order"
MISSING = object()          # a value that isn't there (an added or removed key)


class PatchError(ValueError):
    pass


def split(pointer: str) -> list[str]:
    if pointer == "":
        return []
    if not pointer.startswith("/"):
        raise PatchError(f"'{pointer}' is not a JSON Pointer (it must start with '/')")
    return [p.replace("~1", "/").replace("~0", "~") for p in pointer[1:].split("/")]


def join(parts) -> str:
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts)


# ---------- keyed view ----------

def _get_parent(doc: dict, pointer: str):
    parts = split(pointer)
    node = doc
    for p in parts[:-1]:
        node = node[p] if isinstance(node, dict) else node[int(p)]
    return node, parts[-1]


def to_keyed(sb: dict) -> dict:
    view = copy.deepcopy(sb)
    for coll in COLLECTIONS:
        try:
            parent, name = _get_parent(view, coll)
        except (KeyError, IndexError, TypeError):
            continue
        items = parent.get(name)
        if not isinstance(items, list):
            continue
        keyed: dict[str, Any] = {ORDER: []}
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                raise PatchError(f"{coll}: every item needs a string id")
            if item["id"] in keyed:
                raise PatchError(f"{coll}: duplicate id '{item['id']}'")
            keyed[ORDER].append(item["id"])
            keyed[item["id"]] = item
        parent[name] = keyed
    return view


def from_keyed(view: dict) -> dict:
    sb = copy.deepcopy(view)
    for coll in COLLECTIONS:
        try:
            parent, name = _get_parent(sb, coll)
        except (KeyError, IndexError, TypeError):
            continue
        keyed = parent.get(name)
        if not isinstance(keyed, dict):
            continue
        order = keyed.get(ORDER, [])
        ids = [k for k in keyed if k != ORDER]
        if sorted(order) != sorted(ids):
            raise PatchError(f"{coll}/{ORDER} must list every id exactly once (has {order}, items are {ids})")
        parent[name] = [{**keyed[i], "id": i} for i in order]
    return sb


def _is_collection(parts: list[str]) -> bool:
    return join(parts) in COLLECTIONS


# ---------- apply ----------

def apply(sb: dict, patch: list[dict]) -> dict:
    """Apply a patch written against the keyed view; return a new storyboard. The input is untouched."""
    if not isinstance(patch, list) or not patch:
        raise PatchError("a patch is a non-empty list of operations")
    view = to_keyed(sb)
    for n, op in enumerate(patch, 1):
        try:
            _apply_op(view, op)
        except PatchError as e:
            raise PatchError(f"operation {n} ({op.get('op')} {op.get('path')}): {e}") from None
        except (KeyError, IndexError, ValueError, TypeError) as e:
            raise PatchError(f"operation {n} ({op.get('op')} {op.get('path')}): no such location ({e})") from None
    return from_keyed(view)


def _apply_op(view: dict, op: dict) -> None:
    kind, path = op.get("op"), op.get("path")
    if kind not in ("add", "remove", "replace", "test"):
        raise PatchError("supported operations are add, remove, replace and test")
    if not isinstance(path, str) or path == "":
        raise PatchError("every operation needs a non-empty path")
    parts = split(path)
    parent_parts, key = parts[:-1], parts[-1]
    parent = _resolve(view, parent_parts)
    in_collection = _is_collection(parent_parts)

    if kind == "test":
        if _read(parent, key) != op.get("value"):
            raise PatchError("test failed: the current value is different")
        return

    if in_collection and key == ORDER:
        if kind != "replace":
            raise PatchError(f"{ORDER} can only be replaced")
        value = op.get("value")
        ids = [k for k in parent if k != ORDER]
        if not isinstance(value, list) or sorted(value) != sorted(ids):
            raise PatchError(f"{ORDER} must be a reordering of the existing ids {ids}")
        parent[ORDER] = list(value)
        return

    if kind == "remove":
        if isinstance(parent, list):
            del parent[_index(parent, key)]
        else:
            del parent[key]
            if in_collection:
                parent[ORDER].remove(key)
        return

    if "value" not in op:
        raise PatchError(f"'{kind}' needs a value")
    value = copy.deepcopy(op["value"])

    if isinstance(parent, list):
        if kind == "add":
            parent.insert(len(parent) if key == "-" else _index(parent, key, insert=True), value)
        else:
            parent[_index(parent, key)] = value
        return

    if kind == "replace" and key not in parent:
        raise PatchError("replace needs an existing value; use add")
    if in_collection:
        if not isinstance(value, dict):
            raise PatchError("a collection item must be an object")
        if value.get("id", key) != key:
            raise PatchError(f"the item's id '{value.get('id')}' doesn't match its path '{key}'")
        value["id"] = key
        if key not in parent:
            parent[ORDER].append(key)       # new items go last; reorder with a replace of @order
    parent[key] = value


def _resolve(view, parts):
    node = view
    for p in parts:
        node = node[_index(node, p)] if isinstance(node, list) else node[p]
    return node


def _read(parent, key):
    if isinstance(parent, list):
        return parent[_index(parent, key)]
    return parent[key]


def _index(lst: list, key: str, insert: bool = False) -> int:
    if not key.isdigit():
        raise PatchError(f"'{key}' is not an array index")
    i = int(key)
    if i > len(lst) or (i == len(lst) and not insert):
        raise PatchError(f"index {i} is out of range")
    return i


# ---------- diff ----------

def diff(before: dict, after: dict) -> list[tuple[str, Any, Any]]:
    """Leaf-level changes between two storyboards, as (keyed path, old, new). An added or
    removed item appears once, at its own path, with MISSING on the other side."""
    out: list[tuple[str, Any, Any]] = []
    _diff(to_keyed(before), to_keyed(after), [], out)
    return out


def _diff(a, b, parts, out):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in list(a) + [k for k in b if k not in a]:
            _diff(a.get(k, MISSING), b.get(k, MISSING), parts + [k], out)
    elif a != b or type(a) is not type(b):
        out.append((join(parts), a, b))


def get(view: dict, pointer: str, default=MISSING):
    try:
        return _resolve(view, split(pointer))
    except (KeyError, IndexError, TypeError, PatchError):
        return default


def set_value(view: dict, pointer: str, value) -> None:
    """Set or delete (value=MISSING) one keyed path, keeping @order in step. Used by revert."""
    parts = split(pointer)
    parent = _resolve(view, parts[:-1])
    key = parts[-1]
    in_collection = _is_collection(parts[:-1]) and key != ORDER
    if value is MISSING:
        del parent[key]
        if in_collection and key in parent[ORDER]:
            parent[ORDER].remove(key)
        return
    if in_collection and key not in parent[ORDER]:
        parent[ORDER].append(key)
    parent[key] = copy.deepcopy(value)


# ---------- path patterns ----------

def matches(pattern: str, path: str) -> bool:
    """True when `path` is `pattern` or lies under it; `*` in the pattern matches any one segment."""
    pp, ps = split(pattern), split(path)
    if len(pp) > len(ps):
        return False
    return all(a == "*" or a == b for a, b in zip(pp, ps))
