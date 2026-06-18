"""DFIR-NetworkForensics agent — the on-the-wire evidence specialist.

Built on the Band SDK 1.0.0 (import name ``band``, NOT ``thenvoi``). Shares its
job, method, audit discipline, and output layout with DFIR-HostForensics via
``lib.specialist_base``; only the domain identity differs.

Run it with::

    python agents/network_forensics.py

Reference architecture: https://www.band.ai/hacker-guide
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Make the project root importable so ``lib`` resolves when this file is run
# directly as ``python agents/network_forensics.py``.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lib import specialist_base  # noqa: E402

AGENT_KEY = "network_forensics"
DISPLAY_NAME = "DFIR-NetworkForensics"

IDENTITY = """\
# Identity
You are DFIR-NetworkForensics. Your domain is traffic, DNS, firewall and VPN logs, C2 \
callbacks, lateral movement patterns, and data exfiltration signatures. You reason \
about what happened on the wire.\
"""

SYSTEM_PROMPT = specialist_base.compose_prompt(IDENTITY, domain_word="network")


def build_adapter() -> "specialist_base.GeminiAdapter":
    """Construct the Gemini adapter for DFIR-NetworkForensics (no network I/O)."""
    return specialist_base.build_adapter(DISPLAY_NAME, SYSTEM_PROMPT)


async def run_agent() -> None:
    """Wire up DFIR-NetworkForensics and run until interrupted."""
    await specialist_base.run_agent(AGENT_KEY, DISPLAY_NAME, SYSTEM_PROMPT)


if __name__ == "__main__":
    asyncio.run(run_agent())
