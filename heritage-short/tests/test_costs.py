"""`film costs` turns the logs into COSTS.md tables, priced only where a price was checked."""
from pipeline.costs import BEGIN, END, tables, write


def test_tables_count_attempts_failures_gpu_and_price():
    runs = [
        {"stage": "keyframes", "provider": "cloudflare", "model": "klein", "status": "ok", "latency_ms": 8000, "unit": "s01"},
        {"stage": "keyframes", "provider": "cloudflare", "model": "klein", "status": "transient", "latency_ms": 400, "unit": "s02"},
        {"stage": "shots", "provider": "gpu-runner (kaggle)", "model": "wan", "status": "ok", "latency_ms": 1737000, "gpu_s": 1737.0},
    ]
    stages = [{"stage": "assemble", "unit": "en.vertical", "duration_s": 71.8, "integrated_lufs": -14.8,
               "true_peak_db": -1.5, "pictures": {"kenburns": 9, "i2v": 1}, "music": "m1.13"}]
    text = tables(runs, stages, {"models": {"klein": {"usd_per_call": 0.01}}})
    assert "| keyframes | cloudflare | klein | 2 | 1 | transient 1 | 8.0 | 8.0 | — | $0.010 |" in text
    assert "| shots | gpu-runner (kaggle) | wan | 1 | 1 | — | 1737.0 | 1737.0 | 28.9 | no checked price |" in text
    assert "| en.vertical | 71.8 | -14.8 | -1.5 | kenburns 9, i2v 1 | m1.13 |" in text


def test_write_replaces_only_between_markers(tmp_path):
    (tmp_path / "COSTS.md").write_text(f"# COSTS\n\nprose kept\n\n{BEGIN}\nold\n{END}\n\nmore prose\n")
    write(tmp_path)
    text = (tmp_path / "COSTS.md").read_text()
    assert "prose kept" in text and "more prose" in text and "old" not in text and "Totals: 0 attempts" in text
