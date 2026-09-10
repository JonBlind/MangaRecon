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


def test_emit_elapsed_uses_captured_finished_at(
    monkeypatch,
    capsys,
):
    def unexpected_clock_read():
        raise AssertionError("live clock should not be read")

    monkeypatch.setattr(
        performance.time,
        "perf_counter",
        unexpected_clock_read,
    )

    performance.emit_elapsed(
        "first_database_connection_acquire",
        10.0,
        finished_at=10.25,
    )

    assert capsys.readouterr().out == (
        "MANGARECON_TIMING "
        "stage=first_database_connection_acquire "
        "duration_ms=250.00 "
        "outcome=success\n"
    )
