"""Load configuration from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass


class MissingEndpointError(RuntimeError):
    """SUPERPOSITION_ENDPOINT was not set."""


@dataclass(frozen=True)
class Config:
    endpoint: str
    token: str | None
    default_org_id: str | None
    default_workspace: str | None
    log_level: str


def load_config() -> Config:
    endpoint = os.environ.get("SUPERPOSITION_ENDPOINT")
    if not endpoint:
        raise MissingEndpointError(
            "SUPERPOSITION_ENDPOINT must be set to the upstream Superposition API URL."
        )
    return Config(
        endpoint=endpoint,
        token=os.environ.get("SUPERPOSITION_TOKEN"),
        default_org_id=os.environ.get("SUPERPOSITION_ORG_ID"),
        default_workspace=os.environ.get("SUPERPOSITION_WORKSPACE"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
