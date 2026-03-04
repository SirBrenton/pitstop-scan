from receipts_429_floor_import import policy_module as p


def test_run_with_retry_obeys_retry_after_floor_and_succeeds():
    calls = {"n": 0}
    slept = []

    def do_request():
        calls["n"] += 1
        if calls["n"] <= 2:
            return 429, {"Retry-After": "2"}, {"ok": False}
        return 200, {}, {"ok": True}

    def sleep_fn(s: float):
        slept.append(s)

    status, headers, payload = p.run_with_retry(
        do_request,
        policy=p.RetryPolicy(max_attempts=6, max_elapsed_s=30, base_delay_s=0.1, jitter_frac=0.9),
        sleep_fn=sleep_fn,
        rng=lambda: 0.0,  # worst-case jitter (tries to undercut backoff)
        now_fn=lambda: 0.0,
    )

    assert status == 200
    assert payload["ok"] is True
    assert calls["n"] == 3
    assert slept and all(s >= 2.0 for s in slept)  # floor enforced


def test_run_with_retry_does_not_retry_429_without_retry_after():
    calls = {"n": 0}
    slept = []

    def do_request():
        calls["n"] += 1
        return 429, {}, {"ok": False}

    status, headers, payload = p.run_with_retry(
        do_request,
        policy=p.RetryPolicy(max_attempts=6, max_elapsed_s=30),
        sleep_fn=lambda s: slept.append(s),
        rng=lambda: 0.5,
        now_fn=lambda: 0.0,
    )

    assert status == 429
    assert calls["n"] == 1
    assert slept == []