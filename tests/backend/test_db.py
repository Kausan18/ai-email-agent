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

if __name__ == "__main__":
    print("\n── Phase 1 DB Tests ──\n")
    company = test_company()
    contact = test_contact(company)
    test_recruiter(contact, company)
    test_application(company)
    test_alias(company)
    test_planner_log()
    print("\n── All Phase 1 tests passed ✅ ──\n")