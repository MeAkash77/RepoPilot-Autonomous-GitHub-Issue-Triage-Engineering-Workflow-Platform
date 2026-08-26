"""Eval runner + CI gate.

    uv run python -m repopilot_evals.runner --suite all
    uv run python -m repopilot_evals.runner --suite redteam

Suites:
  redteam        deterministic, always runs; gate: 100% pass (hard).
  classification runs the real classify node over the labeled dataset —
                 requires GROQ_API_KEY (skipped otherwise);
                 gate: macro-F1 must not drop >2pts vs baseline.

Results land in evals/results/latest.json; the committed baseline lives
in evals/baselines/main.json and is refreshed deliberately on main.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from repopilot_evals.classification_metrics import accuracy, macro_f1
from repopilot_evals.redteam import run_redteam

EVALS_DIR = Path(__file__).parents[2]
RESULTS_PATH = EVALS_DIR / "results" / "latest.json"
BASELINE_PATH = EVALS_DIR / "baselines" / "main.json"
CLASSIFICATION_DATASET = EVALS_DIR / "datasets" / "classification_seed.jsonl"

F1_REGRESSION_BUDGET = 0.02


def _suite_redteam() -> dict[str, Any]:
    results = run_redteam()
    failures = [r for r in results if not r.passed]
    for result in results:
        marker = "PASS" if result.passed else "FAIL"
        line = f"  [{marker}] {result.case_id} ({result.attack})"
        if result.reasons:
            line += f" — {'; '.join(result.reasons)}"
        print(line)
    return {
        "total": len(results),
        "passed": len(results) - len(failures),
        "pass_rate": (len(results) - len(failures)) / len(results) if results else 0.0,
        "failures": [{"id": r.case_id, "reasons": r.reasons} for r in failures],
    }


async def _suite_classification() -> dict[str, Any] | None:
    from repopilot_core.settings import get_settings

    if not get_settings().groq_api_key.get_secret_value():
        print("  skipped: GROQ_API_KEY not set")
        return None

    from repopilot_agent.graph import make_router
    from repopilot_agent.nodes import NodeDeps, classify
    from repopilot_agent.state import Classification, TriageState
    from repopilot_llm.router import GroqProvider

    deps = NodeDeps(
        session_factory=None,  # type: ignore[arg-type]  # classify never touches the DB
        router=make_router({"groq": GroqProvider(), "gemini": GroqProvider()}),
        embedder=None,  # type: ignore[arg-type]
        reranker=None,  # type: ignore[arg-type]
    )
    predicted: list[str] = []
    expected: list[str] = []
    with CLASSIFICATION_DATASET.open() as handle:
        cases = [json.loads(line) for line in handle if line.strip()]
    for case in cases:
        state = TriageState(
            repo_id=0,
            repo_full_name=case.get("repo", "eval/corpus"),
            issue_number=0,
            issue_title=case["title"],
            issue_body=case["body"],
            sanitized_body=case["body"],
        )
        update = await classify(state, deps)
        classification = update["classification"]
        assert isinstance(classification, Classification)
        predicted.append(classification.type.value)
        expected.append(case["label"])

    result = {
        "n": len(cases),
        "accuracy": accuracy(predicted, expected),
        "macro_f1": macro_f1(predicted, expected),
    }
    print(f"  n={result['n']} accuracy={result['accuracy']:.3f} macro_f1={result['macro_f1']:.3f}")
    return result


def _compare_to_baseline(results: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    redteam = results.get("redteam")
    if redteam and redteam["pass_rate"] < 1.0:
        violations.append(f"red-team pass rate {redteam['pass_rate']:.0%} < 100% (hard gate)")
    if not BASELINE_PATH.exists():
        return violations
    baseline = json.loads(BASELINE_PATH.read_text())
    base_cls = baseline.get("classification")
    new_cls = results.get("classification")
    if base_cls and new_cls:
        drop = base_cls["macro_f1"] - new_cls["macro_f1"]
        if drop > F1_REGRESSION_BUDGET:
            violations.append(
                f"classification macro-F1 dropped {drop:.3f} (> {F1_REGRESSION_BUDGET}) "
                f"vs baseline {base_cls['macro_f1']:.3f}"
            )
    return violations


def main() -> None:
    parser = argparse.ArgumentParser(prog="repopilot-evals")
    parser.add_argument("--suite", choices=["all", "redteam", "classification"], default="all")
    parser.add_argument(
        "--update-baseline", action="store_true", help="write results as the new baseline"
    )
    args = parser.parse_args()

    results: dict[str, Any] = {}
    if args.suite in ("all", "redteam"):
        print("== red-team suite ==")
        results["redteam"] = _suite_redteam()
    if args.suite in ("all", "classification"):
        print("== classification suite ==")
        classification = asyncio.run(_suite_classification())
        if classification is not None:
            results["classification"] = classification

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(results, indent=2) + "\n")
    print(
        f"\nresults → {RESULTS_PATH.relative_to(Path.cwd()) if RESULTS_PATH.is_relative_to(Path.cwd()) else RESULTS_PATH}"
    )

    if args.update_baseline:
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_PATH.write_text(json.dumps(results, indent=2) + "\n")
        print(f"baseline updated → {BASELINE_PATH}")
        return

    violations = _compare_to_baseline(results)
    if violations:
        print("\nGATE FAILURES:", file=sys.stderr)
        for violation in violations:
            print(f"  - {violation}", file=sys.stderr)
        raise SystemExit(1)
    print("\nall gates green")


if __name__ == "__main__":
    main()
