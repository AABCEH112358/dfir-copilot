"""Shared per-agent credential loading for the DFIR agents.

Band's model is one API key per agent: each agent has its own credential fetched
from its agent page in the Band UI. Each block in ``agent_config.yaml`` names the
environment variable that holds its key via an ``api_key_env`` field, e.g.::

    agents:
      liaison:
        agent_id: "..."
        api_key_env: LIAISON_API_KEY

``load_credentials("liaison")`` returns ``(agent_id, api_key)`` by reading the
agent_id from the YAML and the API key from the named env var. For backwards
compatibility it falls back to ``BAND_API_KEY`` (with a warning) when the
per-agent variable is absent.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml

logger = logging.getLogger("dfir.credentials")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "agent_config.yaml"
LEGACY_API_KEY_ENV = "BAND_API_KEY"


def load_credentials(
    agent_key: str,
    *,
    config_path: str | Path | None = None,
) -> tuple[str, str]:
    """Resolve ``(agent_id, api_key)`` for one agent.

    The agent_id is read from ``agent_config.yaml['agents'][agent_key]``. The API
    key is read from the env var named by that block's ``api_key_env`` field,
    falling back to ``BAND_API_KEY`` (with a warning) for backwards compatibility.

    Raises:
        FileNotFoundError: if the config file is missing.
        KeyError: if the agent or its agent_id is not in the config.
        RuntimeError: if no API key can be resolved from the environment.
    """
    path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Agent config not found at {path}")

    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    agents = config.get("agents", {})

    if agent_key not in agents:
        available = ", ".join(sorted(agents)) or "(none)"
        raise KeyError(
            f"Agent {agent_key!r} not found in {path}. Available agents: {available}"
        )

    block = agents[agent_key] or {}
    agent_id = block.get("agent_id")
    if not agent_id:
        raise KeyError(f"Agent {agent_key!r} is missing 'agent_id' in {path}")
    agent_id = str(agent_id).strip()

    api_key_env = block.get("api_key_env")
    api_key = os.environ.get(api_key_env) if api_key_env else None

    if not api_key:
        legacy = os.environ.get(LEGACY_API_KEY_ENV)
        if legacy:
            logger.warning(
                "Using legacy %s for agent %r; set %s instead for per-agent keys.",
                LEGACY_API_KEY_ENV,
                agent_key,
                api_key_env or f"an api_key_env entry in {path.name}",
            )
            api_key = legacy

    if not api_key:
        target = api_key_env or "(no api_key_env configured)"
        raise RuntimeError(
            f"No API key for agent {agent_key!r}. Set {target} "
            f"(or {LEGACY_API_KEY_ENV}) in the environment / .env file."
        )

    return agent_id, api_key
