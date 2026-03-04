from datetime import datetime, timezone, timedelta

from receipts_429_floor_import import policy_module


def test_retry_after_is_a_floor():
    policy = policy_module.RetryPolicy(base_delay_s=0.5, max_delay_s=10.0, jitter_frac=0.0)
    sleep = policy_module.compute_sleep_s(
        attempt=1,
        retry_after_s=10.0,
        policy=policy,
        rng=lambda: 0.5,
    )
    assert sleep >= 10.0


def test_jitter_cannot_undercut_retry_after_floor():
    # rng=0.0 drives jitter to the minimum backoff (because span ~ -1)
    policy = policy_module.RetryPolicy(base_delay_s=1.0, max_delay_s=10.0, jitter_frac=0.5)
    sleep = policy_module.compute_sleep_s(
        attempt=1,
        retry_after_s=2.0,
        policy=policy,
        rng=lambda: 0.0,
    )
    assert sleep >= 2.0  # floor enforced


def test_budget_hard_stops():
    policy = policy_module.RetryPolicy()
    assert policy_module.should_retry(
        status_code=429,
        retry_after_s=None,
        attempt=1,
        elapsed_s=0.0,
        policy=policy,
    ) is False
