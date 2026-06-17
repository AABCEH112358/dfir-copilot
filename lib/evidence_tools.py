"""Evidence access tools for DFIR agents.

These functions are the agent-facing interface to case bundle JSONs stored in
``data/cases/``. They expose the scenario, collection plan, and evidence
bundle while guaranteeing that the ``ground_truth`` block (dev/eval only) is
never returned to any agent.

No external dependencies beyond the standard library.
"""

from __future__ import annotations

import json
from pathlib import Path

GROUND_TRUTH_KEY = "ground_truth"

CASES_DIR = Path(__file__).resolve().parent.parent / "data" / "cases"


def _read_case_file(path: Path) -> dict:
    """Read and parse a single case JSON file."""
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_case(case_id: str) -> dict:
    """Load a case bundle, stripping the eval-only ``ground_truth`` block.

    Resolution order:
      1. If ``data/cases/{case_id}.json`` exists, load it directly.
      2. Otherwise scan every ``*.json`` in the cases dir and return the first
         whose internal ``case_id`` field matches the requested id exactly.
      3. If nothing matches, raise FileNotFoundError listing the available
         case_ids.

    The scan in step 2 is fine for our small case count (<10); no caching.
    """
    direct = CASES_DIR / f"{case_id}.json"
    if direct.is_file():
        case = _read_case_file(direct)
        case.pop(GROUND_TRUTH_KEY, None)
        return case

    available: list[str] = []
    for path in sorted(CASES_DIR.glob("*.json")):
        case = _read_case_file(path)
        internal_id = case.get("case_id")
        if internal_id is not None:
            available.append(internal_id)
        if internal_id == case_id:
            case.pop(GROUND_TRUTH_KEY, None)
            return case

    raise FileNotFoundError(
        f"No case bundle found for case_id {case_id!r}. "
        f"Available case_ids: {available}"
    )


def get_scenario_brief(case_id: str) -> dict:
    """Return only the ``scenario`` block. Used by Liaison on case open."""
    return load_case(case_id).get("scenario", {})


def list_evidence_categories(case_id: str) -> list[str]:
    """Return the top-level evidence category keys for a case."""
    return list(load_case(case_id).get("evidence_bundle", {}).keys())


def get_evidence(case_id: str, category: str) -> dict:
    """Return the contents of one evidence category.

    This is the primary call specialists use to pull evidence. Raises KeyError
    if the category is not present in the bundle.
    """
    bundle = load_case(case_id).get("evidence_bundle", {})
    if category not in bundle:
        raise KeyError(f"Evidence category {category!r} not found in case {case_id!r}")
    return bundle[category]


def search_evidence(case_id: str, category: str, query: str) -> list[dict]:
    """Naive case-insensitive keyword search within one evidence category.

    Returns every item in the category whose serialized JSON form contains the
    query string. A category that is a list is searched element-by-element; a
    category that is a dict is searched over its values.
    """
    data = get_evidence(case_id, category)
    needle = query.lower()

    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = list(data.values())
    else:
        items = [data]

    results: list[dict] = []
    for item in items:
        serialized = json.dumps(item, sort_keys=True).lower()
        if needle in serialized:
            results.append(item)
    return results


def get_collection_plan(case_id: str) -> list[dict]:
    """Return the expected liaison collection plan.

    FOR EVALUATION ONLY. This is the graded answer key for the Liaison's
    collection planning and must not be called in the production demo flow.
    """
    return load_case(case_id).get("expected_liaison_collection_plan", [])
