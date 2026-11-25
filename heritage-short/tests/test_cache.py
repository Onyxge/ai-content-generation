from pipeline.engine.cache import is_fresh, unit_key, write_sidecar
from pipeline.engine.workspace import canonical


def test_canonical_json_ignores_key_order():
    assert canonical({"b": 1, "a": {"y": 2, "x": [3, 1]}}) == canonical({"a": {"x": [3, 1], "y": 2}, "b": 1})


def test_any_change_changes_the_key():
    base = {"stage": "keyframes", "spec": {"prompt": "dawn", "seed": 1}, "upstream": {}}
    assert unit_key(base) == unit_key(dict(base))
    assert unit_key(base) != unit_key({**base, "spec": {"prompt": "dawn", "seed": 2}})
    assert unit_key(base) != unit_key({**base, "upstream": {"references:ref.1": "abc"}})


def test_fresh_needs_matching_key_and_untouched_file(tmp_path):
    artifact = tmp_path / "s01.png"
    artifact.write_bytes(b"first")
    write_sidecar(artifact, "k1", {"stage": "keyframes"})
    assert is_fresh(artifact, "k1")
    assert not is_fresh(artifact, "k2")
    artifact.write_bytes(b"edited by hand")
    assert not is_fresh(artifact, "k1")
