"""DFIR-HostForensics agent — the endpoint/host evidence specialist.

Built on the Band SDK 1.0.0 (import name ``band``, NOT ``thenvoi``). Shares its
job, method, audit discipline, and output layout with DFIR-NetworkForensics via
``lib.specialist_base``; only the domain identity differs.

Run it with::

    python agents/host_forensics.py

Reference architecture: https://www.band.ai/hacker-guide
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Make the project root importable so ``lib`` resolves when this file is run
# directly as ``python agents/host_forensics.py``.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lib import specialist_base  # noqa: E402

AGENT_KEY = "host_forensics"
DISPLAY_NAME = "DFIR-HostForensics"

IDENTITY = """\
# Identity
You are DFIR-HostForensics. Your domain is endpoint artifacts: event logs, registry, \
filesystem, memory, processes, persistence mechanisms, scheduled tasks, service \
modifications, and antivirus alerts. You reason about what happened ON the affected \
machines.\
"""

SYSTEM_PROMPT = specialist_base.compose_prompt(IDENTITY, domain_word="host")


def build_adapter() -> "specialist_base.GeminiAdapter":
    """Construct the Gemini adapter for DFIR-HostForensics (no network I/O)."""
    return specialist_base.build_adapter(DISPLAY_NAME, SYSTEM_PROMPT)


async def run_agent() -> None:
    """Wire up DFIR-HostForensics and run until interrupted."""
    await specialist_base.run_agent(AGENT_KEY, DISPLAY_NAME, SYSTEM_PROMPT)


if __name__ == "__main__":
    asyncio.run(run_agent())
