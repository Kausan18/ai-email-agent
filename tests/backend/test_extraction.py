"""
Phase 2 tests — Entity Extraction

Run from project root:
    python -m tests.backend.test_extraction

These tests call Ollama directly (Mistral must be running).
No database is touched — Phase 2 is extraction only.

Each test prints:
  PASS / FAIL  —  what was checked
"""

import sys
from backend.extraction import (
    extract_entities,
    RecruiterEntity,
    ApplicationEntity,
    MeetingEntity,
    ConferenceEntity,
    GeneralEntity,
)

PASS = "  PASS"
FAIL = "  FAIL"


def check(label: str, condition: bool) -> bool:
    print(f"{PASS if condition else FAIL}  {label}")
    return condition


# ---------------------------------------------------------------------------
# Mock emails
# ---------------------------------------------------------------------------

RECRUITER_EMAIL = """
Hi Kausty,

I'm Priya Sharma, a Technical Recruiter at DataWave Technologies. I came across your
profile on LinkedIn and I think you'd be a great fit for our Software Engineering Intern
role based in Bangalore.

We're looking for candidates with strong Python and ML skills. The application deadline
is 2025-11-15. Could you let me know if you're interested in a quick call next week?

Best,
Priya Sharma
priya.sharma@datawave.io
DataWave Technologies
""".strip()

APPLICATION_EMAIL = """
Thank you for applying to ABC Technologies!

We have received your application for the Machine Learning Intern position.
Your application ID is APP-2025-48291. You applied via Internshala on 2025-10-01.

We will review your application and get back to you within 2 weeks.

Best regards,
ABC Technologies Recruitment Team
""".strip()

MEETING_EMAIL = """
Hi Kausty,

I'd like to schedule a project discussion with you and Riya (riya@college.edu).

Meeting: Project Status Review
Date: 2025-11-10 at 2:30 PM
Duration: 45 minutes
Link: https://meet.google.com/abc-defg-hij

Please confirm your availability.

Thanks,
Prof. Anand Rao
anand.rao@college.edu
""".strip()

CONFERENCE_EMAIL = """
Dear Author,

We are pleased to confirm receipt of your paper submission to the
NITTE International Conference on Emerging Technologies (NICET 2025).

Paper Title: Physics-Guided Machine Learning for Aneurysm Rupture Risk Prediction
Submission ID: NICET-2025-0142
Submission Date: 2025-10-05

The camera-ready deadline is 2025-12-01.
The conference presentation date is 2026-01-15.

For queries, contact: submissions@nicet2025.org

Best regards,
NICET 2025 Programme Committee
""".strip()

PROFESSOR_EMAIL = """
Hi Kausty,

Please share the updated results for the aneurysm rupture prediction model
by Friday. Also make sure the confusion matrix is included in the report.

Let me know if you need any clarification.

Best,
Prof. Mehta
mehta@research.edu
""".strip()

NEWSLETTER_EMAIL = """
IEEE Computer Society Weekly Digest — Issue #47

Top stories this week:
- Advances in transformer architectures
- New GPU benchmarks released

Unsubscribe | View in browser
""".strip()

AMBIGUOUS_EMAIL = """
Please let us know if you're still interested.
""".strip()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_recruiter():
    print("\n--- RecruiterEntity ---")
    result = extract_entities(RECRUITER_EMAIL, "RECRUITER")
    results = [
        check("Returns RecruiterEntity", isinstance(result, RecruiterEntity)),
        check("recruiter_name populated", bool(result.recruiter_name)),
        check("company populated", bool(result.company)),
        check("role populated", bool(result.role)),
        check("recruiter_email populated", bool(result.recruiter_email)),
        check("extraction_confidence > 0", result.extraction_confidence > 0),
        check("extraction_confidence <= 1", result.extraction_confidence <= 1.0),
    ]
    print(f"  company={result.company!r}  role={result.role!r}  confidence={result.extraction_confidence:.2f}")
    return all(results)


def test_application():
    print("\n--- ApplicationEntity ---")
    result = extract_entities(APPLICATION_EMAIL, "INTERNSHIP")
    results = [
        check("Returns ApplicationEntity", isinstance(result, ApplicationEntity)),
        check("company populated", bool(result.company)),
        check("role populated", bool(result.role)),
        check("application_id populated", bool(result.application_id)),
        check("status is 'applied'", result.status == "applied"),
        check("extraction_confidence > 0", result.extraction_confidence > 0),
    ]
    print(f"  company={result.company!r}  app_id={result.application_id!r}  confidence={result.extraction_confidence:.2f}")
    return all(results)


def test_meeting():
    print("\n--- MeetingEntity ---")
    result = extract_entities(MEETING_EMAIL, "MEETING", thread_id="thread-mock-001")
    results = [
        check("Returns MeetingEntity", isinstance(result, MeetingEntity)),
        check("title populated", bool(result.title)),
        check("scheduled_time populated", bool(result.scheduled_time)),
        check("participants is a list", isinstance(result.participants, list)),
        check("thread_id injected correctly", result.thread_id == "thread-mock-001"),
        check("extraction_confidence > 0", result.extraction_confidence > 0),
    ]
    print(f"  title={result.title!r}  time={result.scheduled_time!r}  confidence={result.extraction_confidence:.2f}")
    return all(results)


def test_conference():
    print("\n--- ConferenceEntity ---")
    result = extract_entities(CONFERENCE_EMAIL, "CONFERENCE")
    results = [
        check("Returns ConferenceEntity", isinstance(result, ConferenceEntity)),
        check("conference_name populated", bool(result.conference_name)),
        check("paper_title populated", bool(result.paper_title)),
        check("submission_id populated", bool(result.submission_id)),
        check("camera_ready_deadline populated", bool(result.camera_ready_deadline)),
        check("extraction_confidence > 0", result.extraction_confidence > 0),
    ]
    print(f"  conf={result.conference_name!r}  paper={result.paper_title!r}  confidence={result.extraction_confidence:.2f}")
    return all(results)


def test_general_professor():
    print("\n--- GeneralEntity (PROFESSOR) ---")
    result = extract_entities(PROFESSOR_EMAIL, "PROFESSOR")
    results = [
        check("Returns GeneralEntity", isinstance(result, GeneralEntity)),
        check("topic populated", bool(result.topic)),
        check("action_items is a list", isinstance(result.action_items, list)),
        check("extraction_confidence > 0", result.extraction_confidence > 0),
    ]
    print(f"  topic={result.topic!r}  actions={result.action_items}  confidence={result.extraction_confidence:.2f}")
    return all(results)


def test_newsletter_skipped():
    print("\n--- NEWSLETTER skipped (no extraction) ---")
    result = extract_entities(NEWSLETTER_EMAIL, "NEWSLETTER")
    results = [
        check("Returns None for NEWSLETTER", result is None),
    ]
    return all(results)


def test_promotion_skipped():
    print("\n--- PROMOTION skipped (no extraction) ---")
    result = extract_entities("Big sale — 50% off today only!", "PROMOTION")
    results = [
        check("Returns None for PROMOTION", result is None),
    ]
    return all(results)


def test_optional_fields_no_crash():
    print("\n--- Optional fields — no crash on sparse email ---")
    result = extract_entities(AMBIGUOUS_EMAIL, "UNKNOWN")
    results = [
        check("Does not raise", result is not None),
        check("Returns a known entity type", isinstance(result, (RecruiterEntity, ApplicationEntity, MeetingEntity, ConferenceEntity, GeneralEntity))),
        check("extraction_confidence present", hasattr(result, "extraction_confidence")),
    ]
    print(f"  type={type(result).__name__}  confidence={result.extraction_confidence:.2f}")
    return all(results)


def test_unknown_category_falls_back():
    print("\n--- Unknown category → GeneralEntity fallback ---")
    result = extract_entities("Hello, how are you?", "PERSONAL")
    results = [
        check("Returns GeneralEntity for PERSONAL", isinstance(result, GeneralEntity)),
        check("extraction_confidence present", result.extraction_confidence >= 0),
    ]
    return all(results)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    print("=" * 55)
    print("Phase 2 — Entity Extraction Tests")
    print("=" * 55)
    print("Requires: Ollama running with Mistral loaded\n")

    tests = [
        test_recruiter,
        test_application,
        test_meeting,
        test_conference,
        test_general_professor,
        test_newsletter_skipped,
        test_promotion_skipped,
        test_optional_fields_no_crash,
        test_unknown_category_falls_back,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            ok = t()
            if ok:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  FAIL  Unhandled exception in {t.__name__}: {e}")
            failed += 1

    print("\n" + "=" * 55)
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 55)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()