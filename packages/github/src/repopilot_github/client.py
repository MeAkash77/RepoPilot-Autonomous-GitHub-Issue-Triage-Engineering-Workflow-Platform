"""GitHub App client: App JWT + installation token management.

Installation tokens expire after an hour; we cache them per installation
and refresh with a safety margin. All REST calls go through one httpx
client with retry on 5xx/connection errors.
"""

import time
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from repopilot_core.settings import get_settings

GITHUB_API = "https://api.github.com"
TOKEN_REFRESH_MARGIN_S = 120


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError)


_retry = retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10),
    reraise=True,
)


@dataclass
class _CachedToken:
    token: str
    expires_at: float


class GitHubAppClient:
    """Authenticates as a GitHub App and acts on behalf of installations."""

    def __init__(self, app_id: str | None = None, private_key: str | None = None) -> None:
        settings = get_settings()
        self._app_id = app_id or settings.github_app_id
        self._private_key = private_key or settings.github_app_private_key.get_secret_value()
        self._token_cache: dict[int, _CachedToken] = {}
        self._http = httpx.AsyncClient(
            base_url=GITHUB_API,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )

    def _app_jwt(self) -> str:
        now = int(time.time())
        return jwt.encode(
            {"iat": now - 60, "exp": now + 540, "iss": self._app_id},
            self._private_key,
            algorithm="RS256",
        )

    @_retry
    async def _fetch_installation_token(self, installation_id: int) -> _CachedToken:
        response = await self._http.post(
            f"/app/installations/{installation_id}/access_tokens",
            headers={"Authorization": f"Bearer {self._app_jwt()}"},
        )
        response.raise_for_status()
        data = response.json()
        # Tokens last one hour; track expiry locally instead of parsing the
        # returned timestamp so clock skew cannot extend a token's life.
        return _CachedToken(token=data["token"], expires_at=time.time() + 3600)

    async def installation_token(self, installation_id: int) -> str:
        cached = self._token_cache.get(installation_id)
        if cached and cached.expires_at - TOKEN_REFRESH_MARGIN_S > time.time():
            return cached.token
        fresh = await self._fetch_installation_token(installation_id)
        self._token_cache[installation_id] = fresh
        return fresh.token

    @_retry
    async def request(
        self,
        installation_id: int,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        token = await self.installation_token(installation_id)
        response = await self._http.request(
            method,
            path,
            json=json,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        if response.status_code == 204:
            return None
        return response.json()

    async def aclose(self) -> None:
        await self._http.aclose()
