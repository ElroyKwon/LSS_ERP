from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Callable


class ConfirmationUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Confirmation:
    user_id: int
    week_start: str
    expected_version: int
    proposal: dict[str, object]
    proposal_hash: str
    expires_at: datetime


def _proposal_hash(proposal: dict[str, object]) -> str:
    encoded = json.dumps(
        proposal,
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ConfirmationStore:
    def __init__(
        self,
        *,
        ttl: timedelta = timedelta(minutes=10),
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if ttl <= timedelta(0):
            raise ValueError("confirmation TTL must be positive")
        self.ttl = ttl
        self.clock = clock
        self._items: dict[str, Confirmation] = {}

    def put(
        self,
        *,
        user_id: int,
        week_start: str,
        expected_version: int,
        proposal: dict[str, object],
    ) -> str:
        stored_proposal = deepcopy(proposal)
        token = secrets.token_urlsafe(32)
        self._items[token] = Confirmation(
            user_id=user_id,
            week_start=week_start,
            expected_version=expected_version,
            proposal=stored_proposal,
            proposal_hash=_proposal_hash(stored_proposal),
            expires_at=self.clock() + self.ttl,
        )
        return token

    def get(self, token: str) -> Confirmation:
        item = self._items.get(token)
        if item is None or item.expires_at <= self.clock():
            self._items.pop(token, None)
            raise ConfirmationUnavailable("confirmation is unavailable")
        if not hmac.compare_digest(
            _proposal_hash(item.proposal),
            item.proposal_hash,
        ):
            self._items.pop(token, None)
            raise ConfirmationUnavailable("confirmation integrity check failed")
        return Confirmation(
            user_id=item.user_id,
            week_start=item.week_start,
            expected_version=item.expected_version,
            proposal=deepcopy(item.proposal),
            proposal_hash=item.proposal_hash,
            expires_at=item.expires_at,
        )

    def consume(self, token: str) -> None:
        self._items.pop(token, None)
