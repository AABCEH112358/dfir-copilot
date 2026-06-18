"""Launch all five DFIR agents concurrently with asyncio.

Loads .env, verifies required credentials (the per-agent key env var names are
read from agent_config.yaml so renaming a key there needs no change here), then
runs every agent's ``run_agent()`` coroutine together. A single agent crashing is
logged but does not take down the others, and Ctrl+C triggers a brief graceful
shutdown.

Run it with::

    python scripts/run_all.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import threading
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Make the project root importable so ``agents`` / ``lib`` resolve when this file
# is run directly as ``python scripts/run_all.py``.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dfir.run_all")

CONFIG_PATH = PROJECT_ROOT / "agent_config.yaml"
GLOBAL_REQUIRED_ENVS = ["GEMINI_API_KEY"]

# The agent keys (matching agent_config.yaml) and their module names under agents/.
AGENT_KEYS = [
    "liaison",
    "classifier",
    "host_forensics",
    "network_forensics",
    "captain",
]
SHUTDOWN_GRACE_SECONDS = 3.0
# Window to let agents establish their WebSocket connections before we claim the
# OS signal handlers from the transport library (which registers its own during
# connect). Claiming afterwards lets our orderly shutdown take precedence.
STARTUP_GRACE_SECONDS = 4.0


def _load_agents_config() -> dict:
    if not CONFIG_PATH.exists():
        sys.exit(f"ERROR: agent config not found at {CONFIG_PATH}")
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return config.get("agents", {})


def _required_key_envs(agents_cfg: dict) -> list[str]:
    """Collect the api_key_env var names from the YAML (no hardcoding)."""
    env_names: list[str] = []
    missing_cfg: list[str] = []
    for key in AGENT_KEYS:
        block = agents_cfg.get(key) or {}
        env_name = block.get("api_key_env")
        if not env_name:
            missing_cfg.append(key)
        else:
            env_names.append(env_name)
    if missing_cfg:
        sys.exit(
            "ERROR: agent_config.yaml is missing 'api_key_env' for: "
            + ", ".join(missing_cfg)
        )
    return env_names


def _verify_env(required_envs: list[str]) -> None:
    missing = [name for name in required_envs if not os.environ.get(name)]
    if missing:
        lines = "\n".join(f"  - {name}" for name in missing)
        sys.exit(
            "ERROR: missing required environment variables:\n"
            f"{lines}\n\n"
            "Set them in your .env file (see .env.example) and try again."
        )


def _import_agents() -> list[tuple[str, object]]:
    """Import the five agent modules; return [(agent_key, module), ...]."""
    from agents import (
        captain,
        classifier,
        host_forensics,
        liaison,
        network_forensics,
    )

    modules = {
        "liaison": liaison,
        "classifier": classifier,
        "host_forensics": host_forensics,
        "network_forensics": network_forensics,
        "captain": captain,
    }
    return [(key, modules[key]) for key in AGENT_KEYS]


def _display_name(module: object, agent_key: str) -> str:
    return (
        getattr(module, "AGENT_DISPLAY_NAME", None)
        or getattr(module, "DISPLAY_NAME", None)
        or agent_key
    )


def _model_for(module: object, agent_key: str, agents_cfg: dict) -> str:
    """Prefer the model from the agent's build_adapter(); fall back to YAML."""
    build_adapter = getattr(module, "build_adapter", None)
    if callable(build_adapter):
        try:
            return build_adapter().model
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Could not read model from %s.build_adapter(): %s", agent_key, exc)
    return (agents_cfg.get(agent_key) or {}).get("model", "unknown")


def _print_banner(agents: list[tuple[str, object]], agents_cfg: dict) -> None:
    rows = [
        (_display_name(mod, key), _model_for(mod, key, agents_cfg))
        for key, mod in agents
    ]
    name_w = max((len(n) for n, _ in rows), default=12)
    print("\n" + "=" * (name_w + 24))
    print("  DFIR Investigator — launching agents")
    print("=" * (name_w + 24))
    for name, model in rows:
        print(f"  {name.ljust(name_w)}   {model}")
    print("=" * (name_w + 24))
    print("  Press Ctrl+C to stop.\n")


async def _run_one(display: str, module: object) -> None:
    """Run a single agent, isolating its failures from the others."""
    try:
        await module.run_agent()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.error("Agent %s crashed: %s", display, exc, exc_info=True)


def _install_signal_handlers(loop: asyncio.AbstractEventLoop, stop: asyncio.Event) -> None:
    """Route SIGINT/SIGTERM to a stop event (instead of KeyboardInterrupt).

    Driving shutdown through an event keeps the multi-agent teardown deterministic
    and avoids the interrupt landing mid-gather. Falls back silently on platforms
    where add_signal_handler is unsupported (KeyboardInterrupt then handles it).
    """
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            pass


def _arm_hard_exit(seconds: float) -> None:
    """Guarantee the process exits even if a library teardown hangs.

    A daemon timer force-exits after the grace window so the launcher can never
    hang on a stuck WebSocket disconnect during shutdown.
    """

    def _kill() -> None:
        logger.warning("Grace window elapsed — forcing exit.")
        os._exit(0)

    timer = threading.Timer(seconds, _kill)
    timer.daemon = True
    timer.start()


async def _amain(agents: list[tuple[str, object]]) -> None:
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    tasks = [
        asyncio.create_task(_run_one(_display_name(mod, key), mod), name=key)
        for key, mod in agents
    ]

    # Run until a shutdown is requested OR every agent has exited on its own
    # (return_exceptions=True so one crash doesn't cancel the rest).
    all_done = asyncio.gather(*tasks, return_exceptions=True)
    stop_waiter = asyncio.ensure_future(stop.wait())

    async def _claim_signals_after_startup() -> None:
        await asyncio.sleep(STARTUP_GRACE_SECONDS)
        _install_signal_handlers(loop, stop)

    claim_task = asyncio.create_task(_claim_signals_after_startup())

    await asyncio.wait({all_done, stop_waiter}, return_when=asyncio.FIRST_COMPLETED)
    claim_task.cancel()

    if stop_waiter.done():
        logger.info(
            "Interrupt received — shutting down agents (up to %.0fs)...",
            SHUTDOWN_GRACE_SECONDS,
        )
    else:
        logger.warning("All agents have exited; shutting down.")

    # Safety net: never let a stuck disconnect hang the launcher.
    _arm_hard_exit(SHUTDOWN_GRACE_SECONDS + 2.0)

    for task in tasks:
        task.cancel()
    # Give agents a brief window to disconnect cleanly, then move on regardless.
    await asyncio.wait(tasks, timeout=SHUTDOWN_GRACE_SECONDS)
    stop_waiter.cancel()


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    agents_cfg = _load_agents_config()
    required_envs = GLOBAL_REQUIRED_ENVS + _required_key_envs(agents_cfg)
    _verify_env(required_envs)

    agents = _import_agents()
    _print_banner(agents, agents_cfg)

    try:
        asyncio.run(_amain(agents))
    except KeyboardInterrupt:
        logger.info("Interrupt received — shutting down agents gracefully...")
    logger.info("All agents stopped.")


if __name__ == "__main__":
    main()
