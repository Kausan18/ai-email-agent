"""
entity_resolver.py
------------------
Resolves raw company name strings (from LLM extraction) to canonical
company UUIDs stored in Supabase.

Resolution order:
  1. Exact match in entity_aliases table
  2. Exact match against canonical company names in companies table
  3. Fuzzy match via difflib against all known aliases + company names
     >= 0.85  → auto-accept  (HIGH confidence)
     0.50–0.84 → flag for user review (LOW confidence)
     < 0.50   → no match, caller should create a new company record

Public API
----------
resolve_company(raw_name: str) -> ResolvedCompany
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass

from backend.memory.db import _client


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ResolvedCompany:
    """
    Returned by resolve_company() for every call.

    Fields
    ------
    canonical_id        UUID of the matched company row, or None if no match.
    canonical_name      Display name of the matched company, or None.
    confidence          0.0 – 1.0 match score.
    resolution          One of:
                          "exact_alias"   — matched entity_aliases row exactly
                          "exact_name"    — matched companies.name exactly
                          "fuzzy_high"    — fuzzy >= 0.85, auto-accepted
                          "fuzzy_low"     — fuzzy 0.50–0.84, needs user review
                          "no_match"      — score < 0.50, create new company
    matched_alias       The alias string that produced the match, or None.
    """
    canonical_id: str | None
    canonical_name: str | None
    confidence: float
    resolution: str
    matched_alias: str | None = None


# ---------------------------------------------------------------------------
# Thresholds (matches Phase 1 schema decision)
# ---------------------------------------------------------------------------

AUTO_ACCEPT_THRESHOLD = 0.85   # >= this → fuzzy_high, auto-accept
LOW_CONFIDENCE_THRESHOLD = 0.50  # >= this → fuzzy_low, flag for review
                                  # <  this → no_match


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalise(name: str) -> str:
    """
    Lowercase, strip common legal suffixes and punctuation so that
    'Analytics Hub Pvt. Ltd.', 'Analytics Hub Pvt Ltd', and
    'Analytics Hub' all normalise to 'analytics hub'.
    """
    suffixes = [
        "pvt. ltd.", "pvt ltd", "pvt. ltd", "private limited",
        "ltd.", "ltd", "llc", "inc.", "inc", "corp.", "corp",
        "technologies", "technology", "tech", "solutions", "services",
        "group", "ai",
    ]
    result = name.lower().strip()
    # remove punctuation that difflib would penalise
    for ch in [".", ",", "-", "_", "("]:
        result = result.replace(ch, " ")
    # collapse whitespace
    result = " ".join(result.split())
    # strip known legal / generic suffixes iteratively so
    # 'abc pvt ltd technologies' → 'abc' (edge case, but safe)
    changed = True
    while changed:
        changed = False
        for suffix in suffixes:
            if result.endswith(suffix):
                result = result[: -len(suffix)].strip()
                changed = True
    return result


def _fuzzy_score(a: str, b: str) -> float:
    """
    SequenceMatcher ratio on normalised strings.
    Returns 0.0 – 1.0.
    """
    return difflib.SequenceMatcher(
        None, _normalise(a), _normalise(b)
    ).ratio()


def _fetch_all_aliases() -> list[dict]:
    """
    Returns every row from entity_aliases where entity_type = 'company'.
    Each row has: id, canonical_id, alias, entity_type, confidence
    """
    client = _client()
    response = (
        client.table("entity_aliases")
        .select("id, canonical_id, alias, confidence")
        .eq("entity_type", "company")
        .execute()
    )
    return response.data or []


def _fetch_all_companies() -> list[dict]:
    """
    Returns every row from companies table.
    Each row has at minimum: id, name
    """
    client = _client()
    response = (
        client.table("companies")
        .select("id, name")
        .execute()
    )
    return response.data or []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_company(raw_name: str) -> ResolvedCompany:
    """
    Resolve a raw company name string to a canonical company UUID.

    Parameters
    ----------
    raw_name : str
        Company name as extracted by the LLM (may be noisy / abbreviated).

    Returns
    -------
    ResolvedCompany
        See dataclass docstring for field descriptions.

    Notes
    -----
    - Never raises. On any Supabase error, returns resolution="no_match"
      so the caller can fall back to creating a new company record.
    - Does not write anything to the database. The caller (memory_writer)
      is responsible for inserting new alias records once a match is
      confirmed by the user (for fuzzy_low) or auto-accepted (fuzzy_high).
    """
    if not raw_name or not raw_name.strip():
        return ResolvedCompany(
            canonical_id=None,
            canonical_name=None,
            confidence=0.0,
            resolution="no_match",
        )

    raw_name = raw_name.strip()

    try:
        aliases = _fetch_all_aliases()
        companies = _fetch_all_companies()
    except Exception:
        # Supabase unreachable — safe fallback
        return ResolvedCompany(
            canonical_id=None,
            canonical_name=None,
            confidence=0.0,
            resolution="no_match",
        )

    # Build a lookup: company_id → company_name (for result enrichment)
    company_name_map: dict[str, str] = {c["id"]: c["name"] for c in companies}

    # ------------------------------------------------------------------
    # Pass 1: exact match against alias strings (case-insensitive)
    # ------------------------------------------------------------------
    raw_lower = raw_name.lower().strip()
    for row in aliases:
        if row["alias"].lower().strip() == raw_lower:
            cid = row["canonical_id"]
            return ResolvedCompany(
                canonical_id=cid,
                canonical_name=company_name_map.get(cid),
                confidence=1.0,
                resolution="exact_alias",
                matched_alias=row["alias"],
            )

    # ------------------------------------------------------------------
    # Pass 2: exact match against canonical company names
    # ------------------------------------------------------------------
    for company in companies:
        if company["name"].lower().strip() == raw_lower:
            return ResolvedCompany(
                canonical_id=company["id"],
                canonical_name=company["name"],
                confidence=1.0,
                resolution="exact_name",
                matched_alias=company["name"],
            )

    # ------------------------------------------------------------------
    # Pass 3: fuzzy match — score against all aliases + company names
    # ------------------------------------------------------------------
    best_score = 0.0
    best_canonical_id: str | None = None
    best_canonical_name: str | None = None
    best_alias: str | None = None

    # score against every alias
    for row in aliases:
        score = _fuzzy_score(raw_name, row["alias"])
        if score > best_score:
            best_score = score
            best_canonical_id = row["canonical_id"]
            best_canonical_name = company_name_map.get(row["canonical_id"])
            best_alias = row["alias"]

    # score against canonical company names too
    for company in companies:
        score = _fuzzy_score(raw_name, company["name"])
        if score > best_score:
            best_score = score
            best_canonical_id = company["id"]
            best_canonical_name = company["name"]
            best_alias = company["name"]

    # ------------------------------------------------------------------
    # Classify fuzzy result
    # ------------------------------------------------------------------
    if best_score >= AUTO_ACCEPT_THRESHOLD:
        return ResolvedCompany(
            canonical_id=best_canonical_id,
            canonical_name=best_canonical_name,
            confidence=round(best_score, 4),
            resolution="fuzzy_high",
            matched_alias=best_alias,
        )

    if best_score >= LOW_CONFIDENCE_THRESHOLD:
        return ResolvedCompany(
            canonical_id=best_canonical_id,
            canonical_name=best_canonical_name,
            confidence=round(best_score, 4),
            resolution="fuzzy_low",
            matched_alias=best_alias,
        )

    return ResolvedCompany(
        canonical_id=None,
        canonical_name=None,
        confidence=round(best_score, 4),
        resolution="no_match",
    )