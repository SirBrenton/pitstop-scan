from receipts_429_floor_import import policy_module as p


def test_run_with_retry_obeys_retry_after_floor_and_stops():
    calls = {"n": 0}
    slept = []

    def do_request():
        calls["n"] += 1
        # First 2 calls: 429 w/ Retry-After=2
        if calls["n"] <= 2:
            return 429, {"Retry-After": "2"}, {"ok": False}
        # Third call: success
        return 200, {}, {"ok": True}

    def sleep_fn(s):
        slept.append(s)

    out_status, out_headers, out_payload = p.run_with_retry(
        do_request,
        policy=p.RetryPolicy(max_attempts=5, max_elapsed_s=30, base_delay_s=0.1, jitter_frac=0.9),
        sleep_fn=sleep_fn,
        rng=lambda: 0.0,  # worst-case jitter (tries to minimize backoff)
    )

    assert out_status == 200
    assert out_payload["ok"] is True
    assert calls["n"] == 3
    assert all(s >= 2.0 for s in slept)  # floor enforced