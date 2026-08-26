"""Per-caller data scoping: resolve repo IDs the signed-in user is allowed to see.

The BFF forwards X-User-Login (the GitHub login of the authenticated user).
We scope all dashboard queries to repos whose Installation.account_login
matches that login.  When no login is present (local dev with the gate open)
we return None, meaning unrestricted — preserving the no-auth dev UX.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from repopilot_api.deps import Caller
from repopilot_core.db.models import Installation, Repo


async def scoped_repo_ids(db: AsyncSession, caller: Caller) -> frozenset[int] | None:
    """Return frozenset of repo IDs visible to caller, or None (= all) for dev."""
    if caller.login is None:
        return None
    rows = await db.scalars(
        select(Repo.id)
        .join(Installation, Repo.installation_id == Installation.id)
        .where(Installation.account_login == caller.login)
    )
    return frozenset(rows.all())


def apply_repo_filter(
    query: Select[Any], repo_id_col: Any, ids: frozenset[int] | None
) -> Select[Any]:
    """Add .where(col.in_(ids)) only when ids is not None."""
    if ids is None:
        return query
    return query.where(repo_id_col.in_(ids))
