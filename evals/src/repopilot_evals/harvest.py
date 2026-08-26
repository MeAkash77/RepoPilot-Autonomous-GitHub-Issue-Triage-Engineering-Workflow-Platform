"""Harvest real issues from public OSS repos into a labeling-ready JSONL.

    uv run python -m repopilot_evals.harvest --repo fastapi/fastapi --count 40

Pulls closed issues (their final labels make ground-truth labeling fast),
maps common label conventions to our four classes as a *suggestion*, and
writes one JSON object per line with `label` left for human confirmation.
Unauthenticated GitHub API allows 60 requests/hour — pass GITHUB_TOKEN for
more headroom.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

OUT_DIR = Path(__file__).parents[2] / "datasets" / "harvested"

LABEL_HINTS = {
    "bug": "bug",
    "confirmed bug": "bug",
    "type: bug": "bug",
    "enhancement": "feature",
    "feature": "feature",
    "feature request": "feature",
    "type: feature": "feature",
    "question": "question",
    "support": "question",
    "docs": "docs",
    "documentation": "docs",
    "type: docs": "docs",
}


def suggest_label(labels: list[str]) -> str | None:
    for label in labels:
        if (hint := LABEL_HINTS.get(label.lower())) is not None:
            return hint
    return None


def harvest(repo: str, count: int) -> Path:
    headers = {"Accept": "application/vnd.github+json"}
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"

    collected: list[dict[str, object]] = []
    page = 1
    with httpx.Client(base_url="https://api.github.com", headers=headers, timeout=30) as client:
        while len(collected) < count and page <= 10:
            response = client.get(
                f"/repos/{repo}/issues",
                params={"state": "closed", "per_page": 100, "page": page},
            )
            response.raise_for_status()
            for item in response.json():
                if "pull_request" in item or not item.get("body"):
                    continue
                labels = [label["name"] for label in item.get("labels", [])]
                collected.append(
                    {
                        "id": f"{repo.replace('/', '-')}-{item['number']}",
                        "repo": repo,
                        "issue_number": item["number"],
                        "title": item["title"],
                        "body": item["body"][:6000],
                        "github_labels": labels,
                        "suggested_label": suggest_label(labels),
                        "label": None,  # ← human fills this in
                        "url": item["html_url"],
                    }
                )
                if len(collected) >= count:
                    break
            page += 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{repo.replace('/', '-')}.jsonl"
    with out_path.open("w") as handle:
        for row in collected:
            handle.write(json.dumps(row) + "\n")
    print(f"wrote {len(collected)} issues → {out_path}", file=sys.stderr)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(prog="repopilot-harvest")
    parser.add_argument("--repo", required=True, help="owner/name of a public repo")
    parser.add_argument("--count", type=int, default=40)
    args = parser.parse_args()
    harvest(args.repo, args.count)


if __name__ == "__main__":
    main()
