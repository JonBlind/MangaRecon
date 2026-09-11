from backend.utils import performance


def test_emit_elapsed_writes_structured_non_negative_duration(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        performance.time,
        "perf_counter",
        lambda: 10.125,
    )

    performance.emit_elapsed(
        "runtime_secret_load",
        10.0,
        outcome="success",
    )

    assert capsys.readouterr().out == (
        "MANGARECON_TIMING "
        "stage=runtime_secret_load "
        "duration_ms=125.00 "
        "outcome=success\n"
    )


def test_emit_elapsed_clamps_clock_anomaly_to_zero(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        performance.time,
        "perf_counter",
        lambda: 9.0,
    )

    performance.emit_elapsed("application_startup", 10.0)

    assert "duration_ms=0.00" in capsys.readouterr().out
