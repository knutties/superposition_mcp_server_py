"""Load configuration from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass


class MissingEndpointError(RuntimeError):
    """SUPERPOSITION_ENDPOINT was not set."""


_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _env_flag(name: str, *, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUTHY


@dataclass(frozen=True)
class Config:
    endpoint: str
    token: str | None
    log_level: str
    readonly: bool


def load_config() -> Config:
    endpoint = os.environ.get("SUPERPOSITION_ENDPOINT")
    if not endpoint:
        raise MissingEndpointError(
            "SUPERPOSITION_ENDPOINT must be set to the upstream Superposition API URL."
        )
    return Config(
        endpoint=endpoint,
        token=os.environ.get("SUPERPOSITION_TOKEN"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        readonly=_env_flag("SUPERPOSITION_READONLY"),
    )


def writes_enabled() -> bool:
    """True unless the operator pinned this process to the read-only tool surface.

    Read directly from the environment (not via :func:`load_config`) because tool
    registration happens at import time, before ``SUPERPOSITION_ENDPOINT`` is
    necessarily validated. Set ``SUPERPOSITION_READONLY=1`` to restore the
    pre-0.2.0 posture where no mutating tool is exposed at all.
    """
    return not _env_flag("SUPERPOSITION_READONLY")
