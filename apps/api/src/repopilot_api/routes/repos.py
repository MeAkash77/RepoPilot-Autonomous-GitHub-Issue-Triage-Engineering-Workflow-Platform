"""Connected repos: list and per-repo settings (autonomy level)."""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from repopilot_api.deps import CallerCtx, DbSession
from repopilot_api.scoping import scoped_repo_ids
from repopilot_core.db import Issue, Repo, TriageRun
from repopilot_core.db.models import AutonomyLevel

router = APIRouter(prefix="/api/v1/repos", tags=["repos"])


class RepoOut(BaseModel):
    id: int
    full_name: str
    default_branch: str
    autonomy_level: str
    indexed_at: datetime | None
    run_count: int


class RepoSettingsPatch(BaseModel):
    autonomy_level: AutonomyLevel


@router.get("", response_model=list[RepoOut])
async def list_repos(caller: CallerCtx, db: DbSession) -> list[RepoOut]:
    ids = await scoped_repo_ids(db, caller)
    run_counts = (
        select(Issue.repo_id, func.count(TriageRun.id).label("runs"))
        .join(TriageRun, TriageRun.issue_id == Issue.id)
        .group_by(Issue.repo_id)
        .subquery()
    )
    query = select(Repo, func.coalesce(run_counts.c.runs, 0)).outerjoin(
        run_counts, run_counts.c.repo_id == Repo.id
    )
    if ids is not None:
        query = query.where(Repo.id.in_(ids))
    rows = (await db.execute(query)).all()
    return [
        RepoOut(
            id=repo.id,
            full_name=repo.full_name,
            default_branch=repo.default_branch,
            autonomy_level=repo.autonomy_level.value,
            indexed_at=repo.indexed_at,
            run_count=count,
        )
        for repo, count in rows
    ]


@router.patch("/{repo_id}/settings", response_model=RepoOut)
async def update_settings(
    repo_id: int, patch: RepoSettingsPatch, caller: CallerCtx, db: DbSession
) -> RepoOut:
    repo = await db.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="repo not found")

    # Ownership check — 404 to avoid existence disclosure.
    ids = await scoped_repo_ids(db, caller)
    if ids is not None and repo.id not in ids:
        raise HTTPException(status_code=404, detail="repo not found")

    repo.autonomy_level = patch.autonomy_level
    await db.commit()
    return RepoOut(
        id=repo.id,
        full_name=repo.full_name,
        default_branch=repo.default_branch,
        autonomy_level=repo.autonomy_level.value,
        indexed_at=repo.indexed_at,
        run_count=0,
    )
