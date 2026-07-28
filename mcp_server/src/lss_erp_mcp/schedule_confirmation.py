"""In-process confirmation state for prepared schedule mutations.

This store is intentionally separate from the timesheet ConfirmationStore.
Schedule authority also binds action, category, event identity, and etag.
It is local, bounded, expiring state; it is not a durable operation journal.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Callable, Literal


ScheduleAction = Literal["CREATE", "UPDATE", "DELETE"]
ScheduleCategory = Literal["company", "refresh"]

_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,256}$")
_IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_TOKEN_GENERATION_ATTEMPTS = 8


class ScheduleConfirmationUnavailable(RuntimeError):
    """The requested confirmation cannot authorize a commit."""


@dataclass(frozen=True)
class ScheduleConfirmation:
    user_id: int
    action: ScheduleAction
    category: ScheduleCategory
    event_id: str | None
    expected_etag: str | None
    proposal: dict[str, object]
    proposal_hash: str
    expires_at: datetime


@dataclass(frozen=True)
class ScheduleConfirmationLease:
    """Owner capability for one in-flight claim."""

    confirmation: ScheduleConfirmation
    lease_id: str


def _canonical_proposal(proposal: dict[str, object]) -> bytes:
    try:
        encoded = json.dumps(
            proposal,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("schedule proposal must be canonical JSON") from exc
    return encoded


def hash_schedule_proposal(proposal: dict[str, object]) -> str:
    """Return the stable SHA-256 hash used by prepare and claim."""
    return hashlib.sha256(_canonical_proposal(proposal)).hexdigest()


def _safe_equal(left: str | None, right: str | None) -> bool:
    if left is None or right is None:
        return left is right
    return hmac.compare_digest(left, right)


class ScheduleConfirmationStore:
    """Bounded, integrity-checked, single-inflight confirmation storage."""

    def __init__(
        self,
        *,
        ttl: timedelta = timedelta(minutes=10),
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        token_factory: Callable[[], str] = lambda: secrets.token_urlsafe(32),
        lease_factory: Callable[[], str] = lambda: secrets.token_urlsafe(32),
        max_items: int = 1024,
        max_proposal_bytes: int = 16384,
        max_leases_per_confirmation: int = 64,
    ) -> None:
        if ttl <= timedelta(0):
            raise ValueError("confirmation TTL must be positive")
        if max_items < 1:
            raise ValueError("max_items must be positive")
        if max_proposal_bytes < 1:
            raise ValueError("max_proposal_bytes must be positive")
        if max_leases_per_confirmation < 1:
            raise ValueError("max_leases_per_confirmation must be positive")
        self.ttl = ttl
        self.clock = clock
        self.token_factory = token_factory
        self.lease_factory = lease_factory
        self.max_items = max_items
        self.max_proposal_bytes = max_proposal_bytes
        self.max_leases_per_confirmation = max_leases_per_confirmation
        self._items: dict[str, ScheduleConfirmation] = {}
        self._idempotency_bindings: dict[str, str] = {}
        self._inflight: dict[str, str] = {}
        self._lease_history: dict[str, set[str]] = {}
        self._lock = RLock()

    def put(
        self,
        *,
        user_id: int,
        action: ScheduleAction,
        category: ScheduleCategory,
        event_id: str | None,
        expected_etag: str | None,
        proposal: dict[str, object],
    ) -> str:
        self._validate_binding_shape(
            user_id=user_id,
            action=action,
            category=category,
            event_id=event_id,
            expected_etag=expected_etag,
            proposal=proposal,
        )
        stored_proposal = deepcopy(proposal)
        encoded = _canonical_proposal(stored_proposal)
        if len(encoded) > self.max_proposal_bytes:
            raise ValueError("schedule proposal exceeds local confirmation bound")

        with self._lock:
            now = self._now()
            self._purge_expired(now)
            if len(self._items) >= self.max_items:
                raise ScheduleConfirmationUnavailable(
                    "schedule confirmation capacity reached"
                )
            token = self._new_token()
            self._items[token] = ScheduleConfirmation(
                user_id=user_id,
                action=action,
                category=category,
                event_id=event_id,
                expected_etag=expected_etag,
                proposal=stored_proposal,
                proposal_hash=hashlib.sha256(encoded).hexdigest(),
                expires_at=now + self.ttl,
            )
            self._lease_history[token] = set()
            return token

    def get(self, token: str) -> ScheduleConfirmation:
        with self._lock:
            item = self._items.get(token)
            if item is None:
                self._drop(token)
                raise ScheduleConfirmationUnavailable(
                    "schedule confirmation is unavailable"
                )
            if item.expires_at <= self._now():
                if token in self._inflight:
                    raise ScheduleConfirmationUnavailable(
                        "confirmation_commit_in_progress"
                    )
                self._drop(token)
                raise ScheduleConfirmationUnavailable(
                    "schedule confirmation is unavailable"
                )
            try:
                current_hash = hash_schedule_proposal(item.proposal)
            except ValueError:
                current_hash = None
            if current_hash is None or not hmac.compare_digest(
                current_hash,
                item.proposal_hash,
            ):
                self._drop(token)
                raise ScheduleConfirmationUnavailable(
                    "schedule confirmation integrity check failed"
                )
            return self._copy(item)

    def claim(
        self,
        token: str,
        idempotency_key: str,
        *,
        user_id: int,
        action: ScheduleAction,
        category: ScheduleCategory,
        event_id: str | None,
        expected_etag: str | None,
        proposal: dict[str, object],
    ) -> ScheduleConfirmationLease:
        self._validate_idempotency_key(idempotency_key)
        with self._lock:
            item = self.get(token)
            supplied_hash = hash_schedule_proposal(proposal)
            bindings_match = (
                item.user_id == user_id
                and hmac.compare_digest(item.action, action)
                and hmac.compare_digest(item.category, category)
                and _safe_equal(item.event_id, event_id)
                and _safe_equal(item.expected_etag, expected_etag)
                and hmac.compare_digest(item.proposal_hash, supplied_hash)
            )
            if not bindings_match:
                raise ScheduleConfirmationUnavailable(
                    "schedule confirmation binding mismatch"
                )

            bound_key = self._idempotency_bindings.get(token)
            if (
                bound_key is not None
                and not hmac.compare_digest(bound_key, idempotency_key)
            ):
                raise ScheduleConfirmationUnavailable(
                    "schedule confirmation idempotency key mismatch"
                )
            if token in self._inflight:
                raise ScheduleConfirmationUnavailable(
                    "confirmation_commit_in_progress"
                )
            lease_id = self._new_lease_id(token)
            if bound_key is None:
                self._idempotency_bindings[token] = idempotency_key
            self._inflight[token] = lease_id
            return ScheduleConfirmationLease(
                confirmation=item,
                lease_id=lease_id,
            )

    def release(self, token: str, lease_id: str | None = None) -> None:
        with self._lock:
            self._require_lease(token, lease_id)
            now = self._now()
            self._inflight.pop(token, None)
            item = self._items.get(token)
            if item is not None and item.expires_at <= now:
                self._drop(token)

    def consume(self, token: str, lease_id: str | None = None) -> None:
        with self._lock:
            self._require_lease(token, lease_id)
            self._drop(token)

    def _new_token(self) -> str:
        for _attempt in range(_TOKEN_GENERATION_ATTEMPTS):
            token = self.token_factory()
            if (
                isinstance(token, str)
                and _TOKEN_RE.fullmatch(token)
                and token not in self._items
            ):
                return token
        raise RuntimeError("could not generate a secure confirmation token")

    def _new_lease_id(self, token: str) -> str:
        history = self._lease_history.setdefault(token, set())
        if len(history) >= self.max_leases_per_confirmation:
            raise ScheduleConfirmationUnavailable(
                "schedule confirmation lease capacity reached"
            )
        active_leases = set(self._inflight.values())
        for _attempt in range(_TOKEN_GENERATION_ATTEMPTS):
            lease_id = self.lease_factory()
            if (
                isinstance(lease_id, str)
                and _TOKEN_RE.fullmatch(lease_id)
                and lease_id not in active_leases
                and lease_id not in history
            ):
                history.add(lease_id)
                return lease_id
        raise RuntimeError("could not generate a secure confirmation lease")

    def _purge_expired(self, now: datetime) -> None:
        expired = [
            token
            for token, item in self._items.items()
            if item.expires_at <= now and token not in self._inflight
        ]
        for token in expired:
            self._drop(token)

    def _drop(self, token: str) -> None:
        self._items.pop(token, None)
        self._idempotency_bindings.pop(token, None)
        self._inflight.pop(token, None)
        self._lease_history.pop(token, None)

    def _now(self) -> datetime:
        value = self.clock()
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError("confirmation_clock_not_timezone_aware")
        return value

    def _require_lease(
        self,
        token: str,
        lease_id: str | None,
    ) -> None:
        current = self._inflight.get(token)
        if (
            current is None
            or not isinstance(lease_id, str)
            or not hmac.compare_digest(current, lease_id)
        ):
            raise ScheduleConfirmationUnavailable(
                "schedule confirmation lease mismatch"
            )

    @staticmethod
    def _validate_idempotency_key(value: object) -> None:
        if (
            not isinstance(value, str)
            or not _IDEMPOTENCY_KEY_RE.fullmatch(value)
        ):
            raise ValueError("invalid_idempotency_key")

    @staticmethod
    def _copy(item: ScheduleConfirmation) -> ScheduleConfirmation:
        return ScheduleConfirmation(
            user_id=item.user_id,
            action=item.action,
            category=item.category,
            event_id=item.event_id,
            expected_etag=item.expected_etag,
            proposal=deepcopy(item.proposal),
            proposal_hash=item.proposal_hash,
            expires_at=item.expires_at,
        )

    @staticmethod
    def _validate_binding_shape(
        *,
        user_id: int,
        action: str,
        category: str,
        event_id: str | None,
        expected_etag: str | None,
        proposal: dict[str, object],
    ) -> None:
        if type(user_id) is not int or user_id < 1:
            raise ValueError("schedule confirmation user_id must be positive")
        if action not in {"CREATE", "UPDATE", "DELETE"}:
            raise ValueError("schedule confirmation action is invalid")
        if category not in {"company", "refresh"}:
            raise ValueError("schedule confirmation category is invalid")
        if action == "CREATE":
            if event_id is not None or expected_etag is not None or not proposal:
                raise ValueError("CREATE confirmation binding is invalid")
        elif event_id is None or expected_etag is None:
            raise ValueError("mutation confirmation target binding is incomplete")
        if action == "DELETE" and proposal:
            raise ValueError("DELETE confirmation proposal must be empty")
        if action == "UPDATE" and not proposal:
            raise ValueError("UPDATE confirmation proposal is required")
