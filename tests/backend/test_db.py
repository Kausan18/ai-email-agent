"""
tests/backend/test_db.py

Phase 1 verification — run with:
    python -m tests.backend.test_db
"""

from backend.memory.db import (
    upsert_company,
    get_company_by_name,
    upsert_contact,
    get_contact_by_email,
    upsert_recruiter,
    get_recruiter_by_contact,
    insert_application,
    get_applications_by_company,
    get_active_applications,
    insert_alias,
    find_alias,
    log_planner_decision,
    get_planner_log,
    insert_conference_submission,
    update_conference_status,
    get_conference_by_name,
    get_active_conference_submissions,
    insert_unverified_event,
    get_unverified_events,
    resolve_unverified_event,
    flag_email,
    get_flagged_emails,
    mark_flag_reviewed,
    insert_email_note,
    get_notes_by_contact,
    get_notes_by_thread,
)

def test_company():
    company = upsert_company("ABC Technologies", domain="abc.ai")
    assert company["name"] == "ABC Technologies"
    fetched = get_company_by_name("ABC Technologies")
    assert fetched["id"] == company["id"]
    # Upsert again — should not duplicate
    same = upsert_company("ABC Technologies")
    assert same["id"] == company["id"]
    print("✅ company: PASS")
    return company

def test_contact(company):
    contact = upsert_contact("john@abc.ai", name="John Smith", company_id=company["id"])
    assert contact["email"] == "john@abc.ai"
    fetched = get_contact_by_email("john@abc.ai")
    assert fetched["id"] == contact["id"]
    # Upsert again — should not duplicate
    same = upsert_contact("john@abc.ai")
    assert same["id"] == contact["id"]
    print("✅ contact: PASS")
    return contact

def test_recruiter(contact, company):
    recruiter = upsert_recruiter(
        contact_id=contact["id"],
        company_id=company["id"],
        thread_id="thread_abc_001"
    )
    assert recruiter["contact_id"] == contact["id"]
    fetched = get_recruiter_by_contact(contact["id"])
    assert fetched["id"] == recruiter["id"]
    print("✅ recruiter: PASS")

def test_application(company):
    app = insert_application(
        company_id=company["id"],
        role="Software Engineering Intern",
        status="applied",
        platform="Internshala",
        application_id="INS-2026-001",
        application_date="2026-09-01T00:00:00Z",
    )
    assert app["role"] == "Software Engineering Intern"
    apps = get_applications_by_company(company["id"])
    assert any(a["id"] == app["id"] for a in apps)
    active = get_active_applications()
    assert any(a["id"] == app["id"] for a in active)
    print("✅ application: PASS")

def test_alias(company):
    alias = insert_alias(
        canonical_id=company["id"],
        alias="ABC Tech",
        entity_type="company",
        confidence=0.92,
    )
    assert alias["alias"] == "ABC Tech"
    found = find_alias("ABC Tech", "company")
    assert found["canonical_id"] == company["id"]
    # Unknown alias returns None
    not_found = find_alias("XYZ Corp", "company")
    assert not_found is None
    print("✅ entity_alias: PASS")

def test_planner_log():
    decisions = {
        "reply_required": True,
        "memory_action": "store_new",
        "confidence": 0.75,
        "reasoning": "Recruiter email with no prior context."
    }
    log = log_planner_decision("email_test_001", decisions)
    assert log["email_id"] == "email_test_001"
    fetched = get_planner_log("email_test_001")
    assert fetched["decisions"]["confidence"] == 0.75
    print("✅ planner_log: PASS")

def test_contact_relationship_type(company):
    # Test each relationship type stores correctly
    professor = upsert_contact(
        email="prof.sharma@university.edu",
        name="Prof. Sharma",
        company_id=company["id"],
        relationship_type="professor",
    )
    assert professor["relationship_type"] == "professor"

    colleague = upsert_contact(
        email="teammate@internship.com",
        name="Alex",
        relationship_type="colleague",
    )
    assert colleague["relationship_type"] == "colleague"

    friend = upsert_contact(
        email="friend@gmail.com",
        name="Rahul",
        relationship_type="friend",
    )
    assert friend["relationship_type"] == "friend"

    conf_organizer = upsert_contact(
        email="organizer@ieee.org",
        name="IEEE Organizer",
        relationship_type="conference_organizer",
    )
    assert conf_organizer["relationship_type"] == "conference_organizer"

    # Unknown defaults correctly
    unknown = upsert_contact(
        email="someone@unknown.com",
        name="Unknown Person",
    )
    assert unknown["relationship_type"] == "unknown"

    print("✅ contact_relationship_type: PASS")
    return professor


def test_email_notes(professor, company):
    # Store a note about a professor email
    note = insert_email_note(
        contact_id=professor["id"],
        thread_id="thread_prof_001",
        category="professor",
        summary="Prof. Sharma asked for a project update on the aneurysm ML pipeline.",
        raw_context="Deadline mentioned: Oct 15. Wants a progress report PDF.",
        email_date="2026-09-20T10:00:00Z",
    )
    assert note["category"] == "professor"
    assert note["contact_id"] == professor["id"]

    # Retrieve notes by contact
    by_contact = get_notes_by_contact(professor["id"])
    assert any(n["id"] == note["id"] for n in by_contact)

    # Retrieve notes by thread
    by_thread = get_notes_by_thread("thread_prof_001")
    assert any(n["id"] == note["id"] for n in by_thread)

    # Store a colleague note — no company link needed
    colleague = upsert_contact(
        email="teammate2@internship.com",
        name="Priya",
        relationship_type="colleague",
    )
    colleague_note = insert_email_note(
        contact_id=colleague["id"],
        thread_id="thread_colleague_001",
        category="colleague",
        summary="Priya sent an update on the frontend task she was handling.",
        raw_context="Task: dashboard component. ETA: Thursday.",
        email_date="2026-09-21T09:00:00Z",
    )
    assert colleague_note["category"] == "colleague"

    # Store a friend note
    friend = get_contact_by_email("friend@gmail.com")
    friend_note = insert_email_note(
        contact_id=friend["id"],
        thread_id="thread_friend_001",
        category="friend",
        summary="Rahul asking for help with his ML assignment.",
        raw_context="Topic: linear regression. Wants to meet this weekend.",
        email_date="2026-09-21T11:00:00Z",
    )
    assert friend_note["category"] == "friend"

    # Note with no contact (orphan thread — sender unknown)
    orphan_note = insert_email_note(
        contact_id=None,
        thread_id="thread_unknown_001",
        category="unknown",
        summary="Email from unrecognised sender about a workshop.",
        raw_context=None,
        email_date="2026-09-21T12:00:00Z",
    )
    assert orphan_note["contact_id"] is None

    print("✅ email_notes: PASS")

def test_conference_submission():
    submission = insert_conference_submission(
        conference_name="NITTE IEEE 2026",
        paper_title="Physics-Guided ML for Aneurysm Rupture Risk",
        submission_id="IEEE-2026-0042",
        status="submitted",
        submission_date="2026-09-15T00:00:00Z",
    )
    assert submission["conference_name"] == "NITTE IEEE 2026"

    fetched = get_conference_by_name("NITTE IEEE 2026")
    assert fetched["id"] == submission["id"]

    updated = update_conference_status(submission["id"], "under_review")
    assert updated["status"] == "under_review"

    active = get_active_conference_submissions()
    assert any(s["id"] == submission["id"] for s in active)
    print("✅ conference_submission: PASS")
    return submission


def test_unverified_event():
    event = insert_unverified_event(
        email_id="email_unknown_conf_001",
        event_type="conference",
        raw_data={"conference": "ICML 2026", "message": "Congratulations on your acceptance."},
        reason="No prior submission found in memory for ICML 2026",
    )
    assert event["event_type"] == "conference"

    all_events = get_unverified_events()
    assert any(e["id"] == event["id"] for e in all_events)

    typed_events = get_unverified_events(event_type="conference")
    assert any(e["id"] == event["id"] for e in typed_events)

    resolve_unverified_event(event["id"])
    remaining = get_unverified_events()
    assert not any(e["id"] == event["id"] for e in remaining)
    print("✅ unverified_event: PASS")


def test_flagged_email():
    flagged = flag_email(
        email_id="email_phish_001",
        reason="suspicious_link",
        sender="definitely-not-google@suspicious.ru",
    )
    assert flagged["reason"] == "suspicious_link"

    unreviewed = get_flagged_emails(reviewed=False)
    assert any(f["id"] == flagged["id"] for f in unreviewed)

    mark_flag_reviewed(flagged["id"])
    reviewed = get_flagged_emails(reviewed=True)
    assert any(f["id"] == flagged["id"] for f in reviewed)
    print("✅ flagged_email: PASS")

'''
if __name__ == "__main__":
    print("\n── Phase 1 DB Tests ──\n")
    company = test_company()
    contact = test_contact(company)
    test_recruiter(contact, company)
    test_application(company)
    test_alias(company)
    test_planner_log()
    print("\n── All Phase 1 tests passed ✅ ──\n")
'''
if __name__ == "__main__":
    print("\n── Phase 1 DB Tests ──\n")
    company = test_company()
    contact = test_contact(company)
    test_recruiter(contact, company)
    test_application(company)
    test_alias(company)
    test_planner_log()
    professor = test_contact_relationship_type(company)   
    test_email_notes(professor, company)                  
    test_conference_submission()
    test_unverified_event()
    test_flagged_email()
    print("\n── All Phase 1 tests passed ✅ ──\n")