"""Triage CLI for manual runs against real data.

    uv run python -m repopilot_agent.cli --repo owner/name --issue 123

Creates (or reuses) the Issue row and a fresh TriageRun, executes the
graph, prints the outcome table.
"""

import argparse
import asyncio
import sys

from sqlalchemy import select

from repopilot_agent.deps import build_default_deps
from repopilot_agent.runner import execute_triage_run
from repopilot_core.db import Installation, Issue, Repo, TriageRun, get_session_factory


async def _triage(full_name: str, issue_number: int) -> None:
    async with get_session_factory()() as session:
        repo = await session.scalar(select(Repo).where(Repo.full_name == full_name))
        if repo is None:
            print(f"repo {full_name!r} not connected", file=sys.stderr)
            raise SystemExit(1)
        installation = await session.get(Installation, repo.installation_id)
        assert installation is not None

        issue = await session.scalar(
            select(Issue).where(Issue.repo_id == repo.id, Issue.github_issue_number == issue_number)
        )
        deps = build_default_deps(installation_id=installation.github_installation_id)
        if issue is None:
            if deps.github is None:
                print("issue not in DB and no GitHub credentials to fetch it", file=sys.stderr)
                raise SystemExit(1)
            data = await deps.github.request(
                installation.github_installation_id,
                "GET",
                f"/repos/{full_name}/issues/{issue_number}",
            )
            issue = Issue(
                repo_id=repo.id,
                github_issue_number=issue_number,
                title=data["title"],
                body=data.get("body") or "",
                author_login=(data.get("user") or {}).get("login", ""),
                state=data.get("state", "open"),
                github_labels=[label["name"] for label in data.get("labels", [])],
            )
            session.add(issue)
            await session.flush()

        run = TriageRun(issue_id=issue.id)
        session.add(run)
        await session.commit()

        final = await execute_triage_run(session, deps, run, issue, repo)

    print(f"\n=== triage run {run.id} ===")
    print(f"injection_risk: {final.injection_risk.value}")
    if final.classification:
        c = final.classification
        print(f"classification: {c.type.value} sev={c.severity} conf={c.confidence:.2f}")
        print(f"  {c.reasoning_summary}")
    print(f"duplicates: {[(d.issue_number, round(d.score, 3)) for d in final.duplicates]}")
    if final.missing_info and final.missing_info.missing:
        print(f"missing info: {final.missing_info.missing}")
    print(f"related files: {final.related_files}")
    print(f"assignees: {[(s.login, round(s.score, 2)) for s in final.assignee_suggestions]}")
    print(f"actions: {[(a.action_type, a.risk) for a in final.proposed_actions]}")
    print(f"guardrail flags: {final.guardrail_flags}")
    print(
        f"cost=${final.total_cost_usd:.6f} tokens={final.total_tokens} "
        f"escalated={final.escalation_used}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="repopilot-triage")
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--issue", required=True, type=int)
    args = parser.parse_args()
    asyncio.run(_triage(args.repo, args.issue))


if __name__ == "__main__":
    main()
