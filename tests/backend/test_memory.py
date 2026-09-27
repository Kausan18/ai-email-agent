"""
tests/backend/test_memory.py
-----------------------------
Phase 3 test suite — Memory Read / Write.

Runs the full extract → resolve → read → write chain against
the real Supabase instance using emails.json fixtures.

All tests clean up after themselves via a registered teardown
so the database never accumulates junk across runs.

Run from project root:
    python -m tests.backend.test_memory

Test index
----------
 1  New recruiter email → contact + recruiter inserted
 2  Follow-up from same recruiter → update, no duplicate
 3  Application acknowledgment → application inserted
 4  Second email about same application → status update, no duplicate
 5  Company alias high-confidence → resolver returns canonical_id
 6  Company alias low-confidence → resolver returns fuzzy_low
 7  Conference acknowledgment, no prior submission → unverified_events
 8  Cold recruiter outreach → recruiter.application_id is None (EC-8)
 9  Two applications to same company → separate rows, correct retrieval
10  Newsletter email → writer returns skip, no DB write
"""

import json
import sys
import traceback
from pathlib import Path

from backend.config import MOCK_DATA_PATH
from backend.extraction.extractor import extract_entities
from backend.memory.db import _client
from backend.memory.entity_resolver import resolve_company
from backend.memory.memory_reader import get_context
from backend.memory.memory_writer import write_entity
from backend.memory.db import _client, insert_application, upsert_company




# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = "PASS"
FAIL = "FAIL"

_cleanup_ids: dict[str, list[str]] = {
    "companies": [],
    "contacts": [],
    "recruiters": [],
    "applications": [],
    "conference_submissions": [],
    "meetings": [],
    "email_notes": [],
    "unverified_events": [],
    "entity_aliases": [],
}


def _register(table: str, record_id: str) -> None:
    if record_id:
        _cleanup_ids[table].append(record_id)


def _teardown() -> None:
    """Delete every record created during the test run."""
    client = _client()
    # Delete in FK-safe order (children before parents)
    order = [
        "recruiters",
        "applications",
        "conference_submissions",
        "meetings",
        "email_notes",
        "unverified_events",
        "entity_aliases",
        "contacts",
        "companies",
    ]
    for table in order:
        ids = _cleanup_ids.get(table, [])
        if ids:
            try:
                client.table(table).delete().in_("id", ids).execute()
            except Exception as e:
                print(f"  [teardown] Warning: could not delete from {table}: {e}")
    print("\n[teardown] Test records cleaned up.")


def _load_email(email_id: str) -> dict:
    emails = json.loads(Path(MOCK_DATA_PATH).read_text())
    match = next((e for e in emails if e["id"] == email_id), None)
    if not match:
        raise ValueError(f"Email '{email_id}' not found in emails.json")
    return match


def _run(name: str, fn) -> bool:
    try:
        fn()
        print(f"  [{PASS}] {name}")
        return True
    except AssertionError as e:
        print(f"  [{FAIL}] {name}")
        print(f"         AssertionError: {e}")
        return False
    except Exception:
        print(f"  [{FAIL}] {name}")
        traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def _setup_cleanup() -> None:
    """Delete stale rows from previous runs in FK-safe order."""
    client = _client()
    client.table("recruiters").delete().eq("thread_id", "thread_001").execute()
    client.table("applications").delete().eq("application_id", "INS-2025-884721").execute()
    client.table("unverified_events").delete().eq("event_type", "conference").execute()
    client.table("entity_aliases").delete().eq("alias", "Analytics Hub").execute()
    client.table("contacts").delete().eq("email", "sarah.mitchell@techcorp.io").execute()
    client.table("contacts").delete().eq("email", "no-reply@internshala.com").execute()
    client.table("companies").delete().eq("name", "TechCorp").execute()
    client.table("companies").delete().eq("name", "Analytics Hub").execute()

def test_01_new_recruiter_insert():
    """New recruiter email → contact + recruiter inserted, action=insert_new."""
    email = _load_email("mock_001")
    entity = extract_entities(email["body"], "RECRUITER", email["thread_id"])

    result = write_entity(
        entity=entity,
        category="RECRUITER",
        thread_id=email["thread_id"],
        sender_email=email["sender"]["email"],
        sender_name=email["sender"]["name"],
    )

    assert result.action == "insert_new", f"Expected insert_new, got {result.action}"
    assert result.record_id is not None, "Expected a record_id, got None"
    assert result.entity_type == "RecruiterEntity"

    # Register for cleanup
    _register("recruiters", result.record_id)
    if result.extra.get("contact_id"):
        _register("contacts", result.extra["contact_id"])
    if result.extra.get("company_id"):
        _register("companies", result.extra["company_id"])


def test_02_follow_up_same_recruiter_no_duplicate():
    """
    Follow-up email from same recruiter on same thread →
    update_existing, no duplicate contact row.
    """
    # First email — baseline
    email1 = _load_email("mock_001")
    entity1 = extract_entities(email1["body"], "RECRUITER", email1["thread_id"])
    result1 = write_entity(
        entity=entity1,
        category="RECRUITER",
        thread_id=email1["thread_id"],
        sender_email=email1["sender"]["email"],
        sender_name=email1["sender"]["name"],
    )
    _register("recruiters", result1.record_id)
    if result1.extra.get("contact_id"):
        _register("contacts", result1.extra["contact_id"])
    if result1.extra.get("company_id"):
        _register("companies", result1.extra["company_id"])

    # Follow-up email — same thread_id, same sender
    email2 = _load_email("mock_007")
    entity2 = extract_entities(email2["body"], "RECRUITER", email2["thread_id"])
    result2 = write_entity(
        entity=entity2,
        category="RECRUITER",
        thread_id=email2["thread_id"],
        sender_email=email2["sender"]["email"],
        sender_name=email2["sender"]["name"],
    )

    assert result2.action == "update_existing", (
        f"Expected update_existing for follow-up, got {result2.action}"
    )
    # Same recruiter_id as the first write
    assert result2.record_id == result1.record_id, (
        "Expected same recruiter record_id for follow-up — duplicate detected"
    )


def test_03_application_acknowledgment_insert():
    """
    Internshala acknowledgment → ApplicationEntity inserted, action=insert_new.
    """
    email = _load_email("mock_005")
    entity = extract_entities(email["body"], "INTERNSHIP", email["thread_id"])

    result = write_entity(
        entity=entity,
        category="INTERNSHIP",
        thread_id=email["thread_id"],
        sender_email=email["sender"]["email"],
        sender_name=email["sender"]["name"],
    )

    assert result.action == "insert_new", f"Expected insert_new, got {result.action}"
    assert result.entity_type == "ApplicationEntity"
    assert result.record_id is not None

    _register("applications", result.record_id)
    if result.extra.get("company_id"):
        _register("companies", result.extra["company_id"])


def test_04_second_email_same_application_updates_status():
    """
    Follow-up from Analytics Hub on same thread →
    update_existing (status update), no second application row (EC-26).
    """
    # Insert baseline application first
    email1 = _load_email("mock_005")
    entity1 = extract_entities(email1["body"], "INTERNSHIP", email1["thread_id"])
    result1 = write_entity(
        entity=entity1,
        category="INTERNSHIP",
        thread_id=email1["thread_id"],
        sender_email=email1["sender"]["email"],
        sender_name=email1["sender"]["name"],
    )
    _register("applications", result1.record_id)
    if result1.extra.get("company_id"):
        _register("companies", result1.extra["company_id"])

    # Follow-up — screening invite from Analytics Hub
    email2 = _load_email("mock_008")
    entity2 = extract_entities(email2["body"], "INTERNSHIP", email2["thread_id"])
    result2 = write_entity(
        entity=entity2,
        category="INTERNSHIP",
        thread_id=email2["thread_id"],
        sender_email=email2["sender"]["email"],
        sender_name=email2["sender"]["name"],
    )

    assert result2.action == "update_existing", (
        f"Expected update_existing for follow-up, got {result2.action}"
    )
    assert result2.record_id == result1.record_id, (
        "Expected same application record_id — duplicate row detected (EC-26 violation)"
    )


def test_05_company_alias_high_confidence():
    """
    'Analytics Hub Pvt Ltd' from mock_009 should resolve to the
    canonical 'Analytics Hub' entry with confidence >= 0.85 (fuzzy_high).
    The writer uses the canonical_id, not a new company row.
    """
    # Seed the canonical company first
    company_row = upsert_company({"name": "Analytics Hub"})
    canonical_id = company_row["id"]
    _register("companies", canonical_id)

    # Seed an alias so the resolver has something to find
    alias_resp = (
        _client().table("entity_aliases")
        .insert({
            "canonical_id": canonical_id,
            "alias": "Analytics Hub",
            "entity_type": "company",
            "confidence": 1.0,
        })
        .execute()
    )
    _register("entity_aliases", alias_resp.data[0]["id"])

    # Resolve the fuzzy name
    resolved = resolve_company("Analytics Hub Pvt Ltd")

    assert resolved.resolution in ("fuzzy_high", "exact_alias", "exact_name"), (
        f"Expected high-confidence resolution, got '{resolved.resolution}' "
        f"(confidence={resolved.confidence})"
    )
    assert resolved.confidence >= 0.85, (
        f"Expected confidence >= 0.85, got {resolved.confidence}"
    )
    assert resolved.canonical_id == canonical_id, (
        f"Expected canonical_id={canonical_id}, got {resolved.canonical_id}"
    )


def test_06_company_alias_low_confidence():
    """
    A weakly matching name 'AH Solutions' should return fuzzy_low
    or no_match — never auto-accept when confidence < 0.85.
    """
    # Seed Analytics Hub again so there's something to compare against
    company_row = upsert_company({"name": "Analytics Hub"})
    _register("companies", company_row["id"])
    resolved = resolve_company("AH Solutions")

    assert resolved.resolution in ("fuzzy_low", "no_match"), (
        f"Expected fuzzy_low or no_match for 'AH Solutions', got '{resolved.resolution}' "
        f"(confidence={resolved.confidence})"
    )
    assert resolved.confidence < 0.85, (
        f"Low-confidence name should not auto-accept. confidence={resolved.confidence}"
    )


def test_07_conference_unknown_routes_to_unverified():
    """
    Conference acceptance email (mock_010) with no prior submission →
    action=route_to_unverified, unverified_events row created (EC-19).
    """
    email = _load_email("mock_010")
    entity = extract_entities(email["body"], "CONFERENCE", email["thread_id"])

    result = write_entity(
        entity=entity,
        category="CONFERENCE",
        thread_id=email["thread_id"],
        sender_email=email["sender"]["email"],
        sender_name=email["sender"]["name"],
    )

    assert result.action == "route_to_unverified", (
        f"Expected route_to_unverified for unknown conference, got '{result.action}'"
    )
    assert result.entity_type == "ConferenceEntity"
    assert result.record_id is not None, "Expected unverified_events row id"

    _register("unverified_events", result.record_id)


def test_08_cold_recruiter_outreach_nullable_application_id():
    """
    Cold recruiter outreach (mock_001) → recruiter.application_id is None (EC-8).
    """
    email = _load_email("mock_001")
    entity = extract_entities(email["body"], "RECRUITER", email["thread_id"])

    result = write_entity(
        entity=entity,
        category="RECRUITER",
        thread_id=email["thread_id"],
        sender_email=email["sender"]["email"],
        sender_name=email["sender"]["name"],
    )

    # Fetch the raw recruiter row and check application_id
    client = _client()
    row = (
        client.table("recruiters")
        .select("application_id")
        .eq("id", result.record_id)
        .maybe_single()
        .execute()
    )
    assert row.data is not None, "Recruiter row not found"
    assert row.data.get("application_id") is None, (
        f"Expected application_id=None for cold outreach, "
        f"got {row.data.get('application_id')}"
    )

    _register("recruiters", result.record_id)
    if result.extra.get("contact_id"):
        _register("contacts", result.extra["contact_id"])
    if result.extra.get("company_id"):
        _register("companies", result.extra["company_id"])


def test_09_two_applications_same_company():
    """
    mock_001 (recruiter — SWE Intern at TechCorp) and
    mock_011 (acknowledgment — ML Engineer Intern at TechCorp) →
    get_context returns two separate application rows (EC-28).
    """
    # --- Write SWE Intern application ---
    email1 = _load_email("mock_001")
    entity1 = extract_entities(email1["body"], "RECRUITER", email1["thread_id"])
    result1 = write_entity(
        entity=entity1,
        category="RECRUITER",
        thread_id=email1["thread_id"],
        sender_email=email1["sender"]["email"],
        sender_name=email1["sender"]["name"],
    )
    _register("recruiters", result1.record_id)
    company_id = result1.extra.get("company_id")
    if company_id:
        _register("companies", company_id)
    if result1.extra.get("contact_id"):
        _register("contacts", result1.extra["contact_id"])

    # Also insert an application row for SWE Intern explicitly
    from backend.memory.db import insert_application
    app1 = insert_application({
        "company_id": company_id,
        "role": "Software Engineer Intern",
        "platform": "LinkedIn",
        "status": "applied",
    })
    _register("applications", app1.get("id"))

    # --- Write ML Intern application ---
    email2 = _load_email("mock_011")
    entity2 = extract_entities(email2["body"], "INTERNSHIP", email2["thread_id"])
    result2 = write_entity(
        entity=entity2,
        category="INTERNSHIP",
        thread_id=email2["thread_id"],
        sender_email=email2["sender"]["email"],
        sender_name=email2["sender"]["name"],
    )
    _register("applications", result2.record_id)
    if result2.extra.get("company_id"):
        _register("companies", result2.extra["company_id"])

    # --- Read context and assert two separate rows ---
    ctx = get_context(
        sender_email=email1["sender"]["email"],
        company_name="TechCorp",
        thread_id=None,
    )

    roles = [a.get("role", "") for a in ctx.applications]
    assert len(ctx.applications) >= 2, (
        f"Expected >= 2 application rows for TechCorp, got {len(ctx.applications)}. "
        f"Roles found: {roles}"
    )

    role_names_lower = [r.lower() for r in roles]
    assert any("swe" in r or "software" in r for r in role_names_lower), (
        f"SWE Intern application not found in context. Roles: {roles}"
    )
    assert any("ml" in r or "machine" in r for r in role_names_lower), (
        f"ML Intern application not found in context. Roles: {roles}"
    )


def test_10_newsletter_writer_skip():
    """
    Newsletter email → write_entity returns action=skip, no DB write.
    """
    email = _load_email("mock_004")
    # Classifier would give this NEWSLETTER — we pass it explicitly
    entity = extract_entities(email["body"], "NEWSLETTER", email["thread_id"])

    result = write_entity(
        entity=entity,
        category="NEWSLETTER",
        thread_id=email["thread_id"],
        sender_email=email["sender"]["email"],
        sender_name=email["sender"]["name"],
    )

    assert result.action == "skip", (
        f"Expected action=skip for NEWSLETTER, got '{result.action}'"
    )
    assert result.record_id is None, (
        "Newsletter should not produce a record_id"
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    print("\n=== Phase 3 — Memory Read / Write Tests ===\n")
    _setup_cleanup() 
    tests = [
        ("Test 01 — New recruiter insert", test_01_new_recruiter_insert),
        ("Test 02 — Follow-up, no duplicate", test_02_follow_up_same_recruiter_no_duplicate),
        ("Test 03 — Application acknowledgment insert", test_03_application_acknowledgment_insert),
        ("Test 04 — Same application status update", test_04_second_email_same_application_updates_status),
        ("Test 05 — Company alias high-confidence", test_05_company_alias_high_confidence),
        ("Test 06 — Company alias low-confidence", test_06_company_alias_low_confidence),
        ("Test 07 — Unknown conference → unverified_events", test_07_conference_unknown_routes_to_unverified),
        ("Test 08 — Cold outreach, application_id=None", test_08_cold_recruiter_outreach_nullable_application_id),
        ("Test 09 — Two apps same company", test_09_two_applications_same_company),
        ("Test 10 — Newsletter → skip", test_10_newsletter_writer_skip),
    ]

    passed = 0
    failed = 0

    for name, fn in tests:
        ok = _run(name, fn)
        if ok:
            passed += 1
        else:
            failed += 1

    _teardown()

    print(f"\n{'='*44}")
    print(f"  Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print(f"{'='*44}\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()