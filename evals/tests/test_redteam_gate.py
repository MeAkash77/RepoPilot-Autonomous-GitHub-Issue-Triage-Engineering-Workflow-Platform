"""The red-team suite is also a pytest gate: any regression in the
injection defenses fails the normal test run, not just the eval CLI."""

from repopilot_evals.redteam import run_redteam


def test_redteam_pass_rate_is_100_percent() -> None:
    results = run_redteam()
    assert len(results) >= 26
    failures = [r for r in results if not r.passed]
    detail = "; ".join(f"{r.case_id}: {r.reasons}" for r in failures)
    assert not failures, f"red-team failures: {detail}"
